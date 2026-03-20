from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.utils import crop
from django.db import models
from django.utils import timezone
from datetime import timedelta
from world.inventory.models import Weapon, Armor, Gear, Vehicle as VehicleModel, Ammunition, Cyberdeck, Inventory, WeaponAttachment
from world.cyberware.models import Cyberware
from world.equipment_data import populate_weapons, populate_armor, populate_gear, populate_vehicles, populate_all_equipment, initialize_vehicles
from world.cyberpunk_sheets.models import CharacterSheet
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider, section_header
from .list_commands import _find_item_info, format_item_info, try_resolve_equipdb_catalog_name
from world.cyberware.utils import populate_cyberware
from evennia.utils.ansi import ANSIString
from evennia.utils import evtable
from math import ceil

class CmdAddItem(Command):
    """
    Add an item to a player's inventory (staff only).
    Auto-detects item type: weapon, armor, gear, or vehicle.

    Usage:
      additem <player>=<item name>

    Examples:
      additem Bob=Medium Pistol
      additem Alice="Light Armorjack"
      additem Charlie=Agent
      additem Bob=Roadbike
    """
    key = "additem"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: additem <player>=<item name>")
            return

        player_name, item_name = self.args.split("=", 1)
        player_name = player_name.strip()
        item_name = item_name.strip().strip('"')

        player = self.caller.search(player_name, global_search=True)
        if not player:
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except (CharacterSheet.DoesNotExist, AttributeError):
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        inventory, _ = Inventory.get_or_create_for_character(player)

        # Try weapon, armor, gear, vehicle in order
        try:
            weapon = Weapon.objects.get(name__iexact=item_name)
            inventory.weapons.add(weapon)
            self.caller.msg(f"Added {weapon.name} to {player.name}'s inventory.")
            player.msg(f"A {weapon.name} has been added to your inventory.")
            return
        except Weapon.DoesNotExist:
            pass

        try:
            armor = Armor.objects.get(name__iexact=item_name)
            inventory.armor.add(armor)
            self.caller.msg(f"Added {armor.name} to {player.name}'s inventory.")
            player.msg(f"A {armor.name} has been added to your inventory.")
            return
        except Armor.DoesNotExist:
            pass

        try:
            gear = Gear.objects.get(name__iexact=item_name)
            inventory.add_gear(gear)
            self.caller.msg(f"Added {gear.name} to {player.name}'s inventory.")
            player.msg(f"A {gear.name} has been added to your inventory.")
            return
        except Gear.DoesNotExist:
            pass

        try:
            vehicle = VehicleModel.objects.get(name__iexact=item_name)
            if inventory.vehicles.filter(id=vehicle.id).exists():
                self.caller.msg(f"{player.name} already has a {vehicle.name}.")
                return
            inventory.vehicles.add(vehicle)
            self.caller.msg(f"Added {vehicle.name} to {player.name}'s inventory.")
            player.msg(f"A {vehicle.name} has been added to your inventory.")
            return
        except VehicleModel.DoesNotExist:
            pass

        # Ammunition: additem <player>=<ammo type>/<units> (each unit = 10 rounds)
        if "/" in item_name:
            ammo_part, units_part = item_name.split("/", 1)
            ammo_part = ammo_part.strip()
            try:
                units = int(units_part.strip())
                if units > 0:
                    from world.inventory.models import Ammunition
                    from world.equipment_data import ammunition as ammo_data
                    ammo_match = None
                    for a in ammo_data:
                        if ammo_part.lower() in (a.get("name", "") or "").lower():
                            ammo_match = a
                            break
                    if ammo_match:
                        rounds = units * 10
                        existing = inventory.ammunition.filter(ammo_type=ammo_match.get("ammo_type", "Basic")).first()
                        if existing:
                            existing.quantity += rounds
                            existing.save()
                        else:
                            ammo = Ammunition.objects.create(
                                name=ammo_match["name"],
                                ammo_type=ammo_match.get("ammo_type", "Basic"),
                                quantity=rounds,
                                cost=ammo_match.get("cost", 10),
                                weapon_type=ammo_match.get("weapon_type", "Generic"),
                            )
                            inventory.ammunition.add(ammo)
                        self.caller.msg(f"Added {rounds} rounds of {ammo_match['name']} to {player.name}'s inventory.")
                        player.msg(f"{rounds} rounds of {ammo_match['name']} have been added to your inventory.")
                        return
            except ValueError:
                pass

        self.caller.msg(f"Item '{item_name}' not found. Check weapon, armor, gear, vehicle names, or use ammo/units (e.g. hollow point/10).")

class CmdAddVehicle(Command):
    """
    Add a vehicle to a player's inventory.

    Usage:
      addvehicle <player> <vehicle_name>

    Example:
      addvehicle Bob Roadbike
      addvehicle Alice "AV-4 Multipurpose Aerodyne"
    """
    key = "addvehicle"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: addvehicle <player> <vehicle_name>")
            return

        player_name, vehicle_name = self.args.split(None, 1)
        vehicle_name = vehicle_name.strip('"')

        player = self.caller.search(player_name, global_search=True)
        if not player:
            return

        try:
            vehicle_model = VehicleModel.objects.get(name__iexact=vehicle_name)
        except VehicleModel.DoesNotExist:
            self.caller.msg(f"Vehicle '{vehicle_name}' does not exist. Use 'equipdb vehicles' to list available vehicles.")
            return

        # Use same inventory lookup as +inventory (get_or_create_for_character prefers character_sheet)
        try:
            inventory, _ = Inventory.get_or_create_for_character(player)
        except (ValueError, AttributeError):
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        if inventory.vehicles.filter(id=vehicle_model.id).exists():
            self.caller.msg(f"{player.name} already has a {vehicle_model.name}.")
            return

        inventory.vehicles.add(vehicle_model)
        self.caller.msg(f"Added {vehicle_model.name} to {player.name}'s inventory.")
        player.msg(f"A {vehicle_model.name} has been added to your inventory.")

class CmdRemoveVehicle(Command):
    """
    Remove a vehicle from a player's inventory.

    Usage:
      removevehicle <player> <vehicle_name>

    Example:
      removevehicle Bob Roadbike
      removevehicle Alice "Cabin Cruiser"
    """
    key = "removevehicle"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: removevehicle <player> <vehicle_name>")
            return

        player_name, vehicle_name = self.args.split(None, 1)
        vehicle_name = vehicle_name.strip('"')

        player = self.caller.search(player_name, global_search=True)
        if not player:
            return

        # Use same inventory lookup as +inventory
        try:
            inventory, _ = Inventory.get_or_create_for_character(player)
        except (ValueError, AttributeError):
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        try:
            vehicle_model = inventory.vehicles.get(name__iexact=vehicle_name)
        except VehicleModel.DoesNotExist:
            self.caller.msg(f"Vehicle '{vehicle_name}' not found in {player.name}'s inventory.")
            return

        inventory.vehicles.remove(vehicle_model)
        self.caller.msg(f"Removed {vehicle_model.name} from {player.name}'s inventory.")
        player.msg(f"Your {vehicle_model.name} has been removed from your inventory.")

class CmdPopulateWeapons(Command):
    """
    Populate the database with weapons from Cyberpunk RED.

    Usage:
      populate_weapons

    This command should only be run once to initialize the weapon database.
    """

    key = "populate_weapons"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        populate_weapons()
        self.caller.msg("Weapon database populated successfully.")

class CmdPopulateArmor(Command):
    """
    Populate the database with armor from Cyberpunk RED.

    Usage:
      populate_armor

    This command should only be run once to initialize the armor database.
    """

    key = "populate_armor"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        populate_armor()
        self.caller.msg("Armor database populated successfully.")

class CmdPopulateGear(Command):
    """
    Populate the database with gear from Cyberpunk RED.

    Usage:
      populate_gear

    This command should only be run once to initialize the gear database.
    """

    key = "populate_gear"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        populate_gear()
        self.caller.msg("Gear database populated successfully.")

class CmdPopulateVehicles(Command):
    """
    Populate the database with vehicles from Cyberpunk RED.

    Usage:
      populate_vehicles

    This command initializes all vehicle types (land, sea, air) from the
    core rulebook. Run once to set up the vehicle database.
    """

    key = "populate_vehicles"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        populate_vehicles()
        self.caller.msg("Vehicle database populated successfully.")

class CmdPopulateAllEquipment(Command):
    """
    Populate the database with all equipment from Cyberpunk RED.

    Usage:
      populate_all_equipment

    This command should only be run once to initialize the entire equipment database.
    """

    key = "populate_all_equipment"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        populate_all_equipment()
        self.caller.msg("All equipment databases populated successfully.")

class CmdDepopulateAllEquipment(Command):
    """
    Remove all equipment from the database.

    Usage:
      depopulate_all_equipment
      depopulate_all_equipment yes

    This command will delete all weapons, armor, gear, and cyberware from the database.
    Use with caution as this action cannot be undone.
    """

    key = "depopulate_all_equipment"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        now = timezone.now()
        confirmation_timeout = timedelta(minutes=1)

        # Debug information
        self.caller.msg(f"Debug: Args received: '{self.args}'")
        self.caller.msg(f"Debug: Confirmation time: {self.caller.attributes.get('confirm_depopulate_time', 'Not set')}")

        if self.caller.attributes.has("confirm_depopulate_time"):
            confirm_time = self.caller.attributes.get("confirm_depopulate_time")
            if now - confirm_time > confirmation_timeout:
                self.caller.attributes.remove("confirm_depopulate_time")
                self.caller.msg("Confirmation timeout. Please start over if you want to depopulate equipment.")
                return

            if self.args and self.args.strip().lower() == "yes":
                # Confirmed, proceed with deletion
                Weapon.objects.all().delete()
                Armor.objects.all().delete()
                Gear.objects.all().delete()
                Cyberware.objects.all().delete()
                
                self.caller.msg("All equipment has been deleted from the database.")
                self.caller.attributes.remove("confirm_depopulate_time")
                return

        # If we get here, either it's the first run or confirmation failed
        self.caller.msg("Are you sure you want to delete all equipment? This cannot be undone.")
        self.caller.msg("Type 'depopulate_all_equipment yes' within the next minute to confirm, or anything else to cancel.")
        
        # Set the confirmation time
        self.caller.attributes.add("confirm_depopulate_time", now)


class CmdPopulateCyberware(Command):
    """
    Populate the database with all cyberware from Cyberpunk RED.
    Usage:
      populate_cyberware
    This command should only be run once to initialize the entire cyberware database.
    """
    key = "populate_cyberware"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        try:
            populate_cyberware()
            self.caller.msg("All cyberware populated successfully.")
        except Exception as e:
            self.caller.msg(f"An error occurred while populating cyberware: {str(e)}")

def _match_subcategory(user_input, valid_subcategories):
    """
    Match user input to a valid subcategory. Supports:
    - Exact: heavy_weapons, heavy weapons
    - First word: heavy -> heavy_weapons
    """
    user_norm = (user_input or "").lower().replace(" ", "_").strip()
    if not user_norm:
        return None
    for sub in valid_subcategories:
        sub_norm = (sub or "").lower().replace(" ", "_")
        if sub_norm == user_norm:
            return sub
        if sub_norm.startswith(user_norm + "_"):
            return sub
        first_word = sub_norm.split("_")[0]
        if first_word == user_norm:
            return sub
    return None


def _get_equipdb_subcategories():
    """Return dict of main_category -> sorted list of subcategories from DB."""
    result = {
        "weapons": [],
        "armor": [],
        "gear": [],
        "ammo": [],
        "cyberdecks": [],
        "cyberware": [],
        "vehicles": [],
        "attachments": [],
    }
    for cat in Weapon.objects.values_list("category", flat=True).distinct():
        if cat:
            result["weapons"].append(cat)
    for wt in Weapon.objects.exclude(weapon_type="").values_list("weapon_type", flat=True).distinct():
        if wt and wt not in result["weapons"]:
            result["weapons"].append(wt)
    for loc_str in Armor.objects.values_list("locations", flat=True):
        for loc in (loc_str or "").split(","):
            loc = loc.strip()
            if loc and loc not in result["armor"]:
                result["armor"].append(loc)
    for cat in Gear.objects.values_list("category", flat=True).distinct():
        if cat and cat != "Cyberware":
            result["gear"].append(cat)
    if Cyberdeck.objects.exists():
        result["gear"].append("Cyberdeck")
    result["gear"] = sorted(set(result["gear"]))
    for at in Ammunition.objects.values_list("ammo_type", flat=True).distinct():
        if at:
            result["ammo"].append(at)
    for cat in VehicleModel.objects.values_list("category", flat=True).distinct():
        if cat:
            result["vehicles"].append(cat)
    for cw_type in Cyberware.objects.values_list("type", flat=True).distinct():
        if cw_type:
            result["cyberware"].append(cw_type)
    result["weapons"] = sorted(set(result["weapons"]))
    result["armor"] = sorted(set(result["armor"]))
    result["ammo"] = sorted(set(result["ammo"]))
    result["vehicles"] = sorted(set(result["vehicles"]))
    result["cyberware"] = sorted(set(result["cyberware"]))
    return result


class CmdViewEquipment(MuxCommand):
    """
    View all equipment in the database.

    Usage:
      equipdb                    - Show category menu (like list chargen)
      equipdb [type [category]]
      equipdb weapons [handgun|shoulder_arms|archery|heavy_weapons|melee|brawling]
      equipdb gear [Electronics|Tools|Medical|Drugs|Clothing|...]
      equipdb vehicles [land|sea|air]
      equipdb medical            - Gear in Medical category (subcategory shorthand)
      equipdb list [type [category]]  - Same as above (list/list gear/list gear medical)
      equipdb/search <string>    - Search all equipment by name, category, or description
      equipdb/info <item>       - Detailed info on a specific item (like +lookup/info)

    Types: weapons, armor, gear, ammo, cyberdecks, cyberware, vehicles, attachments
    Use |wequipdb|n alone to see available categories and subcategories.
    Subcategories with underscores (e.g. heavy_weapons) accept spaces or first word: heavy weapons, heavy
    """

    key = "equipdb"
    aliases = ["itemsdb"]
    lock = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        valid_types = ['weapons', 'armor', 'gear', 'cyberware', 'ammo', 'cyberdecks', 'vehicles', 'attachments']
        subcats = _get_equipdb_subcategories()

        # equipdb/search <string> - search across all equipment
        if "search" in (self.switches or []):
            search_str = (self.args or "").strip()
            if not search_str:
                self.caller.msg("Usage: equipdb/search <string>")
                return
            self._search_equipment(search_str)
            return

        # equipdb/info <item> - detailed info on a specific item (like +lookup/info)
        if "info" in (self.switches or []):
            self._info_equipment()
            return

        # Parse args: support "equipdb", "equipdb weapons", "equipdb weapons handgun",
        # "equipdb gear medical", "equipdb medical" (subcategory shorthand)
        # Also support "equipdb/weapons" or "equipdb/gear medical" via MuxCommand switches
        # "equipdb list" or "equipdb/list" -> show menu; "equipdb list gear" -> show gear
        switches = self.switches or []
        switch_part = (switches[0] if switches else "").strip()
        args_part = (self.args or "").strip()
        raw = (switch_part + " " + args_part).strip() if switch_part else args_part
        raw = raw.lower()
        parts = raw.split(None, 1) if raw else []
        equip_type = parts[0] if parts else None
        subcategory = parts[1] if len(parts) > 1 else None

        # equipdb list / equipdb/list: show menu; equipdb list gear [medical] -> treat as equipdb gear [medical]
        if equip_type == "list":
            if subcategory:
                sub_parts = subcategory.split(None, 1)
                equip_type = sub_parts[0]
                subcategory = sub_parts[1] if len(sub_parts) > 1 else None
            else:
                equip_type = None

        # Resolve subcategory-only: "equipdb medical" -> gear medical
        if equip_type and equip_type not in valid_types and not subcategory:
            resolved = self._resolve_subcategory(equip_type, subcats)
            if resolved:
                equip_type, subcategory = resolved
            else:
                self.caller.msg(
                    f"Unknown category '{equip_type}'. Use |wequipdb|n to see available categories."
                )
                return

        if equip_type and equip_type not in valid_types:
            self.caller.msg(f"Invalid type. Use one of: {', '.join(valid_types)}.")
            return

        # Resolve flexible subcategory: "heavy weapons", "heavy" -> "heavy_weapons"
        if subcategory and equip_type in subcats:
            resolved = _match_subcategory(subcategory, subcats[equip_type])
            if resolved is not None:
                subcategory = resolved

        output = []
        if not equip_type:
            self._display_menu(valid_types, subcats)
            return

        output.append(header(f"Equipment: {equip_type.title()}" + (f" ({subcategory})" if subcategory else "")))
        output.append(getattr(self, f"display_{equip_type}")(subcategory))
        output.append(footer())

        self.caller.msg("\n".join(filter(None, output)))

    def _search_equipment(self, search_str):
        """Search for equipment matching string across all types."""
        self.caller.msg("\n".join(format_search_equipment(search_str, chargen_only=False)))

    def _info_equipment(self):
        """Show detailed info on a specific item (like +lookup/info)."""
        if not self.args or not self.args.strip():
            self.caller.msg("Usage: equipdb/info <item name>")
            return

        raw_q = self.args.strip()
        source, data = _find_item_info(raw_q)
        if not data:
            resolved, ferr = try_resolve_equipdb_catalog_name(raw_q)
            if ferr:
                self.caller.msg(ferr)
                return
            if resolved:
                source, data = _find_item_info(resolved)
        if not data:
            self.caller.msg(
                f"Item '{raw_q}' not found. Try |wequipdb/search <name>|n to find items."
            )
            return

        self.caller.msg("\n".join(format_item_info(source, data)))

    def _resolve_subcategory(self, subcat, subcats):
        """If subcat is a subcategory (not main type), return (main_type, subcategory)."""
        for main_cat, subs in subcats.items():
            if not subs:
                continue
            resolved = _match_subcategory(subcat, subs)
            if resolved is not None:
                return (main_cat, resolved)
        return None

    def _display_menu(self, valid_types, subcats):
        """Show equipdb category menu like list chargen."""
        output = []
        output.append(header("Equipment Database"))
        output.append("Browse equipment by type and category. Use |wequipdb <type>|n or |wequipdb/<type>|n")
        output.append("to list all items of that type. Add a category to filter (e.g. |wequipdb gear medical|n).")
        output.append("|b-----------------------------------------------------------------------------|n")
        for t in valid_types:
            subs = subcats.get(t, [])
            if subs:
                sub_links = " | ".join(f"|w{s.lower().replace(' ', '_')}|n" for s in subs)
                output.append(f"  |y{t.title()}|n: {sub_links}")
                output.append(f"      Or |w{t}|n for all")
            else:
                output.append(f"  |y{t.title()}|n: |w{t}|n")
        output.append("")
        output.append("Examples: |wequipdb gear|n  |wequipdb cyberware|n  |wequipdb/search pistol|n  |wequipdb/info Medium Pistol|n")
        output.append(footer())
        self.caller.msg("\n".join(output))

    def display_weapons(self, subcategory=None):
        qs = Weapon.objects.all().order_by('category', 'name')
        if subcategory:
            qs = qs.filter(
                models.Q(category__iexact=subcategory) |
                models.Q(weapon_type__iexact=subcategory)
            )
        weapons = list(qs)
        if not weapons:
            return section_header("Weapons", width=78) + "\nNo weapons found.\n"
        out = [section_header("Weapons", width=78)]
        for w in weapons:
            nm = crop(w.name, width=28, suffix="...")
            wt = getattr(w, 'weapon_type', '') or ''
            qual = getattr(w, 'quality', 'standard') or 'standard'
            out.append(f"|c{nm:<28}|n |gDamage:|n {w.damage:<8} |gROF:|n {w.rof:<4} |gHands:|n {w.hands} |gValue:|n |y{w.value} eb|n")
            out.append(f"  |gType:|n {(wt or w.category):<16} |gQuality:|n {qual:<10} |gConceal:|n {'Yes' if w.concealable else 'No'} |gWeight:|n {w.weight}")
        out.append(divider("", width=78))
        return "\n".join(out) + "\n"

    def display_armor(self, subcategory=None):
        armors = list(Armor.objects.all().order_by('name'))
        if subcategory:
            sub_lower = subcategory.lower()
            armors = [a for a in armors if sub_lower in [loc.strip().lower() for loc in (a.locations or "").split(",")]]
        if not armors:
            return section_header("Armor", width=78) + "\nNo armor found.\n"
        out = [section_header("Armor", width=78)]
        for a in armors:
            nm = crop(a.name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gSP:|n {a.sp:<3} |gEV:|n {a.ev:<3} |gValue:|n |y{a.value} eb|n |gLocations:|n {a.locations}")
        out.append(divider("", width=78))
        return "\n".join(out) + "\n"

    def display_gear(self, subcategory=None):
        qs = Gear.objects.all().order_by('category', 'name')
        if subcategory:
            qs = qs.filter(category__iexact=subcategory)
        gears = list(qs)
        if not gears:
            return section_header("Gear", width=78) + "\nNo gear found.\n"
        out = [section_header("Gear", width=78)]
        for g in gears:
            nm = crop(g.name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gCategory:|n {g.category:<14} |gValue:|n |y{g.value} eb|n")
            desc = wrap_ansi(g.description, 74) if g.description else "—"
            out.append(f"  {desc}")
        out.append(divider("", width=78))
        return "\n".join(out) + "\n"

    def display_ammo(self, subcategory=None):
        qs = Ammunition.objects.all().order_by('ammo_type', 'name')
        if subcategory:
            qs = qs.filter(ammo_type__iexact=subcategory)
        ammos = list(qs)
        if not ammos:
            return section_header("Ammunition", width=78) + "\nNo ammunition found.\n"
        out = [section_header("Ammunition", width=78)]
        seen = set()
        for a in ammos:
            # Normalize ammo_type for dedupe: "HIGH_PRECISION" and "High Precision" -> same key
            ammo_key = (a.ammo_type or "").lower().replace("_", " ")
            key = (a.name.lower(), ammo_key)
            if key in seen:
                continue
            seen.add(key)
            nm = crop(a.name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gType:|n {a.ammo_type:<16} |gCost:|n |y{a.cost} eb|n")
        out.append(divider("", width=78))
        return "\n".join(out) + "\n"

    def display_cyberware(self, subcategory=None):
        qs = Cyberware.objects.all().order_by('type', 'name')
        if subcategory:
            qs = qs.filter(type__iexact=subcategory)
        cyberware = list(qs)
        if not cyberware:
            return section_header("Cyberware", width=78) + "\nNo cyberware found.\n"
        out = [section_header("Cyberware", width=78)]
        for cw in cyberware:
            ctype = getattr(cw, "type", "?")
            slots = getattr(cw, "slots", 0)
            hl = getattr(cw, "humanity_loss", 0)
            value = cw.cost
            nm = crop(cw.name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gType:|n {str(ctype):<20} |gSlots:|n {slots} |gHL:|n {hl} |gValue:|n |y{value} eb|n")
        out.append(divider("", width=78))
        return "\n".join(out) + "\n"

    def display_cyberdecks(self, subcategory=None):
        decks = list(Cyberdeck.objects.all().order_by('name'))
        if not decks:
            return section_header("Cyberdecks", width=78) + "\nNo cyberdecks found.\n"
        out = [section_header("Cyberdecks", width=78)]
        for d in decks:
            nm = crop(d.name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n    |gHW:|n {d.hardware_slots} |gProg:|n {d.program_slots} |gAny:|n {d.any_slots} |gValue:|n |y{d.value} eb|n")
        out.append(divider("", width=78))
        return "\n".join(out) + "\n"

    def display_vehicles(self, subcategory=None):
        qs = VehicleModel.objects.all().order_by('category', 'name')
        if subcategory:
            qs = qs.filter(category__iexact=subcategory)
        vehicles = list(qs)
        if not vehicles:
            return section_header("Vehicles", width=78) + "\nNo vehicles found.\n"
        out = [section_header("Vehicles", width=78)]
        for v in vehicles:
            nm = crop(v.name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gCategory:|n {v.category:<8} |gSDP:|n {v.sdp} |gSeats:|n {v.seats} |gValue:|n |y{v.value} eb|n")
        out.append(divider("", width=78))
        return "\n".join(out) + "\n"

    def display_attachments(self, subcategory=None):
        atts = list(WeaponAttachment.objects.all().order_by('name'))
        if not atts:
            return section_header("Weapon Attachments", width=78) + "\nNo attachments found.\n"
        out = [section_header("Weapon Attachments", width=78)]
        for a in atts:
            nm = crop(a.name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gValue:|n |y{a.value} eb|n DV{a.install_dv} {a.install_skill}")
            out.append(f"  {a.effect_description or a.description or '—'}")
        out.append(divider("", width=78))
        return "\n".join(out) + "\n"


def format_search_equipment(search_str, chargen_only=False):
    """Search equipment by name/category/description. Returns list of output lines.
    chargen_only: if True, restrict to items value/cost <= 1000 eb."""
    CHARGEN_MAX = 1000
    q = search_str.lower()
    output = []
    title = f"Chargen Search: '{search_str}'" if chargen_only else f"Equipment Search: '{search_str}'"
    output.append(header(title))

    # Weapons
    weapons_q = Weapon.objects.filter(
        models.Q(name__icontains=q) | models.Q(category__icontains=q) |
        models.Q(weapon_type__icontains=q) | models.Q(quality__icontains=q) |
        models.Q(description__icontains=q)
    )
    if chargen_only:
        weapons_q = weapons_q.filter(value__lte=CHARGEN_MAX)
    weapons = list(weapons_q.order_by('category', 'name')[:50])
    if weapons:
        output.append(section_header("Weapons", width=78))
        for w in weapons:
            nm = crop(w.name, width=28, suffix="...")
            qual = getattr(w, 'quality', 'standard') or 'standard'
            output.append(f"|c{nm:<28}|n |gDamage:|n {w.damage:<8} |gROF:|n {w.rof:<4} |gQuality:|n {qual:<10} |gValue:|n |y{w.value} eb|n")
        output.append("")

    # Armor
    armors_q = Armor.objects.filter(
        models.Q(name__icontains=q) | models.Q(locations__icontains=q) |
        models.Q(description__icontains=q)
    )
    if chargen_only:
        armors_q = armors_q.filter(value__lte=CHARGEN_MAX)
    armors = list(armors_q.order_by('name')[:50])
    if armors:
        output.append(section_header("Armor", width=78))
        for a in armors:
            nm = crop(a.name, width=28, suffix="...")
            output.append(f"|c{nm:<28}|n |gSP:|n {a.sp} |gEV:|n {a.ev} |gValue:|n |y{a.value} eb|n")
        output.append("")

    # Gear
    gears_q = Gear.objects.filter(
        models.Q(name__icontains=q) | models.Q(category__icontains=q) |
        models.Q(description__icontains=q)
    )
    if chargen_only:
        gears_q = gears_q.filter(value__lte=CHARGEN_MAX)
    gears = list(gears_q.order_by('category', 'name')[:50])
    if gears:
        output.append(section_header("Gear", width=78))
        for g in gears:
            nm = crop(g.name, width=28, suffix="...")
            output.append(f"|c{nm:<28}|n |gCategory:|n {g.category:<14} |gValue:|n |y{g.value} eb|n")
        output.append("")

    # Cyberware
    cyberware_q = Cyberware.objects.filter(
        models.Q(name__icontains=q) | models.Q(type__icontains=q) |
        models.Q(description__icontains=q)
    )
    if chargen_only:
        cyberware_q = cyberware_q.filter(cost__lte=CHARGEN_MAX)
    cyberware = list(cyberware_q.order_by('type', 'name')[:50])
    if cyberware:
        output.append(section_header("Cyberware", width=78))
        for cw in cyberware:
            nm = crop(cw.name, width=28, suffix="...")
            output.append(f"|c{nm:<28}|n |gType:|n {str(cw.type):<16} |gValue:|n |y{cw.cost} eb|n")
        output.append("")

    # Ammunition
    ammos_q = Ammunition.objects.filter(
        models.Q(name__icontains=q) | models.Q(ammo_type__icontains=q) |
        models.Q(description__icontains=q)
    )
    if chargen_only:
        ammos_q = ammos_q.filter(cost__lte=CHARGEN_MAX)
    ammos = list(ammos_q.order_by('ammo_type', 'name')[:50])
    if ammos:
        seen = set()
        output.append(section_header("Ammunition", width=78))
        for a in ammos:
            key = (a.name.lower(), (a.ammo_type or "").lower().replace("_", " "))
            if key in seen:
                continue
            seen.add(key)
            nm = crop(a.name, width=28, suffix="...")
            output.append(f"|c{nm:<28}|n |gType:|n {a.ammo_type:<16} |gCost:|n |y{a.cost} eb|n")
        output.append("")

    # Cyberdecks
    decks_q = Cyberdeck.objects.filter(
        models.Q(name__icontains=q) | models.Q(description__icontains=q)
    )
    if chargen_only:
        decks_q = decks_q.filter(value__lte=CHARGEN_MAX)
    decks = list(decks_q.order_by('name')[:50])
    if decks:
        output.append(section_header("Cyberdecks", width=78))
        for d in decks:
            nm = crop(d.name, width=28, suffix="...")
            output.append(f"|c{nm:<28}|n |gHW:|n {d.hardware_slots} |gProg:|n {d.program_slots} |gValue:|n |y{d.value} eb|n")
        output.append("")

    # Vehicles
    vehicles_q = VehicleModel.objects.filter(
        models.Q(name__icontains=q) | models.Q(category__icontains=q) |
        models.Q(description__icontains=q)
    )
    if chargen_only:
        vehicles_q = vehicles_q.filter(value__lte=CHARGEN_MAX)
    vehicles = list(vehicles_q.order_by('category', 'name')[:50])
    if vehicles:
        output.append(section_header("Vehicles", width=78))
        for v in vehicles:
            nm = crop(v.name, width=28, suffix="...")
            output.append(f"|c{nm:<28}|n |gCategory:|n {v.category:<8} |gValue:|n |y{v.value} eb|n")
        output.append("")

    # Attachments
    atts_q = WeaponAttachment.objects.filter(
        models.Q(name__icontains=q) | models.Q(description__icontains=q) |
        models.Q(effect_description__icontains=q)
    )
    if chargen_only:
        atts_q = atts_q.filter(value__lte=CHARGEN_MAX)
    atts = list(atts_q.order_by('name')[:50])
    if atts:
        output.append(section_header("Weapon Attachments", width=78))
        for a in atts:
            nm = crop(a.name, width=28, suffix="...")
            output.append(f"|c{nm:<28}|n |gValue:|n |y{a.value} eb|n")
        output.append("")

    if len(output) <= 1:
        output.append("No equipment found matching that search.")
    output.append(footer())
    return output


class CmdRemoveEquipment(Command):
    """
    Remove a weapon, armor, gear, or vehicle from a player's inventory.

    Usage:
      removeequip <player> <equipment_type> <equipment_name>

    Equipment types:
      weapon, armor, gear, vehicle

    Examples:
      removeequip Bob weapon "Medium Pistol"
      removeequip Alice armor "Leather Jacket"
      removeequip Charlie gear "Agent"
      removeequip Bob vehicle Roadbike
    """
    key = "removeequip"
    aliases = ["remove_equipment", "remequip"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or len(self.args.split()) < 3:
            self.caller.msg("Usage: removeequip <player> <equipment_type> <equipment_name>")
            return

        player_name, equipment_type, equipment_name = self.args.split(None, 2)
        player = self.caller.search(player_name, global_search=True)
        if not player:
            return

        equipment_type = equipment_type.lower()
        if equipment_type not in ['weapon', 'armor', 'gear', 'vehicle']:
            self.caller.msg("Invalid equipment type. Use 'weapon', 'armor', 'gear', or 'vehicle'.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        inventory, created = Inventory.get_or_create_for_character(player)

        if equipment_type == 'weapon':
            self.remove_weapon(inventory, equipment_name, player)
        elif equipment_type == 'armor':
            self.remove_armor(inventory, equipment_name, player)
        elif equipment_type == 'gear':
            self.remove_gear(inventory, equipment_name, player)
        elif equipment_type == 'vehicle':
            self.remove_vehicle(inventory, equipment_name, player)

    def remove_weapon(self, inventory, weapon_name, player):
        try:
            weapon = inventory.weapons.get(name__iexact=weapon_name.strip('"'))
            inventory.weapons.remove(weapon)
            self.caller.msg(f"Removed {weapon.name} from {player.name}'s inventory.")
            player.msg(f"A {weapon.name} has been removed from your inventory.")
        except Weapon.DoesNotExist:
            self.caller.msg(f"Weapon '{weapon_name}' not found in {player.name}'s inventory.")

    def remove_armor(self, inventory, armor_name, player):
        try:
            armor = inventory.armor.get(name__iexact=armor_name.strip('"'))
            inventory.armor.remove(armor)
            self.caller.msg(f"Removed {armor.name} from {player.name}'s inventory.")
            player.msg(f"A {armor.name} has been removed from your inventory.")
        except Armor.DoesNotExist:
            self.caller.msg(f"Armor '{armor_name}' not found in {player.name}'s inventory.")

    def remove_gear(self, inventory, gear_name, player):
        try:
            gear = inventory.gear.get(name__iexact=gear_name.strip('"'))
            inventory.remove_gear(gear)
            self.caller.msg(f"Removed {gear.name} from {player.name}'s inventory.")
            player.msg(f"A {gear.name} has been removed from your inventory.")
        except Gear.DoesNotExist:
            self.caller.msg(f"Gear '{gear_name}' not found in {player.name}'s inventory.")

    def remove_vehicle(self, inventory, vehicle_name, player):
        """Remove vehicle from inventory."""
        try:
            vehicle_model = inventory.vehicles.get(name__iexact=vehicle_name.strip('"'))
        except VehicleModel.DoesNotExist:
            self.caller.msg(f"Vehicle '{vehicle_name}' not found in {player.name}'s inventory.")
            return

        inventory.vehicles.remove(vehicle_model)
        self.caller.msg(f"Removed {vehicle_model.name} from {player.name}'s inventory.")
        player.msg(f"Your {vehicle_model.name} has been removed from your inventory.")