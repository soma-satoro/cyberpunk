from evennia import Command
from evennia.utils.ansi import ANSIString
from evennia.commands.default.muxcommand import MuxCommand
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import Weapon, Armor, Gear, Inventory, Ammunition, CyberwareInstance, InventoryArmor
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from world.utils.formatting import sheet_header, sheet_section, footer, header, divider
from world.utils.character_utils import get_character_sheet, get_staff_target_character
import logging

logger = logging.getLogger('cyberpunk.inventory')

class CmdInventory(MuxCommand):
    """
    Show character inventory

    Usage:
      inv                    - Shows your inventory
      inv/info <item>       - Detailed info on an inventory item
      inv <character>       - Staff: shows another's inventory
      inv/info <name>/<item> - Staff: detailed info on another's item
      inv/equip <weapon>
      inv/unequip
      inv/wear <armor>
      inv/remove

    Switches:
      inv/equip, inv/unequip, inv/wear, inv/remove - Modify your equipment
    """

    key = "inventory"
    aliases = ["inv"]
    lock = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        logger.info(f"Inventory command called for {self.caller.name}")
        # inv/info - handle first (may parse <name>/<item>)
        if self.switches and "info" in self.switches:
            character_sheet = get_character_sheet(self.caller)
            if not character_sheet:
                self.caller.msg("You don't have a character sheet.")
                return
            self._do_info(self.args, character_sheet, self.caller)
            return

        # Staff can view another character: inv <name>
        target_char, character_sheet = get_staff_target_character(self.caller, self.args)
        if target_char is not None and character_sheet is not None:
            # Staff viewing another - only allow view, not equip/wear/etc
            if self.switches and any(s in self.switches for s in ("equip", "unequip", "wear", "remove")):
                self.caller.msg("You can only view another character's inventory, not modify it.")
                return
            self._show_inventory(character_sheet, target_char)
            return
        if self.args and (target_char is None or character_sheet is None):
            self.caller.msg("You don't have permission to view other character inventories, or no such character found.")
            return

        character_sheet = get_character_sheet(self.caller)
        if not character_sheet:
            logger.warning(f"No character sheet found for {self.caller.name}")
            self.caller.msg("You don't have a character sheet. Please create one using the 'chargen' command.")
            return

        if self.switches and "equip" in self.switches:
            self.equip_item()
            return
        if self.switches and "unequip" in self.switches:
            self.unequip_item()
            return
        if self.switches and "wear" in self.switches:
            self.wear_armor()
            return
        if self.switches and "remove" in self.switches:
            self.remove_armor()
            return

        self._show_inventory(character_sheet, self.caller)

    def _do_info(self, raw, character_sheet, display_char):
        """Handle inv/info <item> or inv/info <name>/<item> (staff)."""
        from world.utils.character_utils import is_staff
        if not raw or not raw.strip():
            self.caller.msg("Usage: inv/info <item> or inv/info <name>/<item> (staff)")
            return
        raw = raw.strip()
        item_name = raw
        if "/" in raw:
            if not is_staff(self.caller):
                self.caller.msg("Only staff can view another character's inventory items.")
                return
            name_part, item_name = raw.split("/", 1)
            name_part = name_part.strip()
            item_name = item_name.strip()
            target_char, character_sheet = get_staff_target_character(
                self.caller, name_part, quiet=True
            )
            if target_char is None or character_sheet is None:
                self.caller.msg(f"No character named '{name_part}' found.")
                return
            display_char = target_char
        inv = character_sheet.inventory
        item_name_lower = item_name.lower()
        # Search: weapons, armor, gear, ammunition, vehicles, cyberware
        for weapon in inv.weapons.all():
            if (weapon.name or "").lower() == item_name_lower:
                self._format_weapon_info(weapon, display_char)
                return
        for armor in inv.armor.all():
            if (armor.name or "").lower() == item_name_lower:
                inst, _ = InventoryArmor.objects.get_or_create(
                    inventory=inv, armor=armor,
                    defaults={"current_sp": armor.sp, "original_sp": armor.sp}
                )
                self._format_armor_info(armor, inst, character_sheet, display_char)
                return
        for gear in inv.gear.all():
            if (gear.name or "").lower() == item_name_lower:
                self._format_gear_info(gear, display_char)
                return
        for ammo in inv.ammunition.all():
            if (ammo.name or "").lower() == item_name_lower:
                self._format_ammo_info(ammo, display_char)
                return
        for vehicle in inv.vehicles.all():
            if (vehicle.name or "").lower() == item_name_lower:
                self._format_vehicle_info(vehicle, display_char)
                return
        for cw in inv.cyberware.all():
            if (cw.cyberware.name or "").lower() == item_name_lower:
                self._format_cyberware_info(cw, display_char)
                return
        self.caller.msg(f"No inventory item named '{item_name}' found.")

    def _format_weapon_info(self, weapon, display_char):
        """Format weapon details for display."""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = header(f"{weapon.name}{owner}", width=78, fillchar="|m-|n") + "\n"
        out += f"|cDamage:|n {weapon.damage or 'N/A'}\n"
        out += f"|cROF:|n {weapon.rof or 'N/A'}\n"
        out += f"|cCategory:|n {weapon.category or 'N/A'}\n"
        out += f"|cAmmo:|n {weapon.ammo_type or 'N/A'} (current: {weapon.current_ammo}/{weapon.max_ammo or weapon.clip})\n"
        if weapon.description:
            out += divider("Description", width=78, fillchar="|m-|n") + "\n"
            out += f"{weapon.description}\n"
        out += footer(width=78, fillchar="|m-|n")
        self.caller.msg(out)

    def _format_armor_info(self, armor, inst, character_sheet, display_char):
        """Format armor details for display."""
        base_sp = inst.original_sp if inst.original_sp is not None else armor.sp
        eff_sp = inst.get_effective_sp()
        worn = " |y(worn)|n" if getattr(character_sheet, 'eqarmor', None) == armor else ""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = header(f"{armor.name}{owner}", width=78, fillchar="|m-|n") + "\n"
        out += f"|cSP:|n {eff_sp} (base {base_sp})"
        if inst.current_sp is not None and inst.current_sp != base_sp:
            out += f" |y(ablation: {inst.current_sp})"
        out += "\n"
        out += f"|cEV:|n {armor.ev or 0}\n"
        out += f"|cLocations:|n {armor.locations or 'N/A'}\n"
        if inst.juryrigged:
            out += "|yJuryrigged:|n Yes\n"
        if armor.description:
            out += divider("Description", width=78, fillchar="|m-|n") + "\n"
            out += f"{armor.description}\n"
        out += footer(width=78, fillchar="|m-|n")
        self.caller.msg(out)

    def _format_gear_info(self, gear, display_char):
        """Format gear details for display."""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = header(f"{gear.name}{owner}", width=78, fillchar="|m-|n") + "\n"
        out += f"|cCategory:|n {gear.category or 'N/A'}\n"
        out += f"|cValue:|n {gear.value or 0} eb\n"
        if gear.description:
            out += divider("Description", width=78, fillchar="|m-|n") + "\n"
            out += f"{gear.description}\n"
        out += footer(width=78, fillchar="|m-|n")
        self.caller.msg(out)

    def _format_ammo_info(self, ammo, display_char):
        """Format ammunition details for display."""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = header(f"{ammo.name}{owner}", width=78, fillchar="|m-|n") + "\n"
        out += f"|cType:|n {ammo.ammo_type or 'N/A'}\n"
        out += f"|cQuantity:|n {ammo.quantity}\n"
        out += f"|cWeapon Type:|n {ammo.weapon_type or 'Generic'}\n"
        if ammo.description:
            out += divider("Description", width=78, fillchar="|m-|n") + "\n"
            out += f"{ammo.description}\n"
        out += footer(width=78, fillchar="|m-|n")
        self.caller.msg(out)

    def _format_vehicle_info(self, vehicle, display_char):
        """Format vehicle details for display."""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = header(f"{vehicle.name}{owner}", width=78, fillchar="|m-|n") + "\n"
        out += f"|cCategory:|n {vehicle.category or 'N/A'}\n"
        out += f"|cSDP:|n {vehicle.sdp or 0}\n"
        out += f"|cSeats:|n {vehicle.seats or 0}\n"
        out += f"|cSpeed:|n {vehicle.speed_narrative or 'N/A'}\n"
        if vehicle.description:
            out += divider("Description", width=78, fillchar="|m-|n") + "\n"
            out += f"{vehicle.description}\n"
        out += footer(width=78, fillchar="|m-|n")
        self.caller.msg(out)

    def _format_cyberware_info(self, cw_instance, display_char):
        """Format cyberware instance details for display."""
        cw = cw_instance.cyberware
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = header(f"{cw.name}{owner}", width=78, fillchar="|m-|n") + "\n"
        out += f"|cType:|n {cw.type or 'N/A'}\n"
        out += f"|cHumanity Loss:|n {cw.humanity_loss}\n"
        out += f"|cStatus:|n {'Installed' if cw_instance.installed else 'Uninstalled'}\n"
        if getattr(cw_instance, "popup_weapon_name", None):
            out += f"|cWeapon:|n {cw_instance.popup_weapon_name}\n"
        if cw.description:
            out += divider("Description", width=78, fillchar="|m-|n") + "\n"
            out += f"{cw.description}\n"
        out += footer(width=78, fillchar="|m-|n")
        self.caller.msg(out)

    def _show_inventory(self, character_sheet, display_char):
        """Display inventory for a character (used for self or staff viewing another)."""
        inv = character_sheet.inventory
        W = 80
        display_name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', display_char) or str(display_char)

        output = sheet_header(f"Inventory for {display_name}", width=W)

        # Currency and Reputation
        balance = CharacterSheetMoneyService.get_balance(character_sheet)
        logger.info(f"Retrieved balance for character sheet ID {character_sheet.id}: {balance}")
        output += sheet_section("Currency and Reputation", width=W)
        output += f"|yCurrent Bank Balance:|n |w{balance} Eurodollars|n\n"
        rep = character_sheet.rep
        pts = getattr(character_sheet, 'reputation_points', 0) or 0
        if rep >= 10:
            rep_str = f"Rank {rep} ({pts} pts, max rank)"
        else:
            next_threshold = (rep + 1) * 100
            pts_needed = next_threshold - pts
            rep_str = f"Rank {rep} ({pts} pts, {pts_needed} to Rank {rep + 1})"
        output += f"|yNight City Rep:|n |w{rep_str}|n\n"
        noto = getattr(character_sheet, 'notoriety', 0) or 0
        noto_pts = getattr(character_sheet, 'notoriety_points', 0) or 0
        if noto >= 10:
            noto_str = f"Rank {noto} ({noto_pts} pts, max rank)"
        elif noto_pts > 0:
            next_threshold = (noto + 1) * 100
            pts_needed = next_threshold - noto_pts
            noto_str = f"Rank {noto} ({noto_pts} pts, {pts_needed} to Rank {noto + 1})"
        else:
            noto_str = "None"
        output += f"|yNight City Notoriety:|n |w{noto_str}|n\n\n"

        # Weapons
        output += sheet_section("Weapons", width=W)
        weapons = inv.weapons.all()
        if weapons:
            output += f"|y{'Weapon':<25}{'Damage':<20}{'ROF':<20}|n\n"
            for weapon in weapons:
                output += f"|w{weapon.name:<25}{weapon.damage or 'N/A':<20}{weapon.rof or 'N/A':<20}|n\n"
        else:
            output += "|wNo weapons in inventory.|n\n"
        output += "\n"

        # Armor
        output += sheet_section("Armor", width=W)
        armors = inv.armor.all()
        if armors:
            output += f"|y{'Armor':<20}{'SP':<15}{'EV':<15}{'Locations':<20}|n\n"
            for armor in armors:
                inst, _ = InventoryArmor.objects.get_or_create(
                    inventory=inv, armor=armor,
                    defaults={"current_sp": armor.sp, "original_sp": armor.sp}
                )
                base_sp = inst.original_sp if inst.original_sp is not None else armor.sp
                eff_sp = inst.get_effective_sp()
                if inst.juryrigged:
                    sp_display = f"{eff_sp} |y(juryrigged)|n"
                elif inst.current_sp is not None and inst.current_sp != base_sp:
                    sp_display = f"{inst.current_sp}/{base_sp}"
                else:
                    sp_display = str(eff_sp) if eff_sp is not None else "N/A"
                worn = " |y(worn)|n" if getattr(character_sheet, 'eqarmor', None) == armor else ""
                output += f"|w{armor.name:<20}{sp_display:<25}{armor.ev or 'N/A':<15}{armor.locations or 'N/A':<20}{worn}|n\n"
        else:
            output += "|wNo armor in inventory.|n\n"
        output += "\n"

        # Gear (use get_gear_with_quantities if available to show qty)
        output += sheet_section("Gear", width=W)
        gear_items = inv.get_gear_with_quantities() if hasattr(inv, 'get_gear_with_quantities') else [(g, 1) for g in inv.gear.all()]
        if gear_items:
            output += f"|y{'Gear':<32}{'Category':<18}{'Description':<30}|n\n"
            for gear, qty in gear_items:
                desc = (gear.description[:27] + "...") if len(gear.description or "") > 30 else (gear.description or "")
                name_display = f"{gear.name} (x{qty})" if qty > 1 else gear.name
                output += f"|w{name_display:<32}{gear.category:<18}{desc:<30}|n\n"
        else:
            output += "|wNo gear in inventory.|n\n"
        output += "\n"

        # Ammunition
        output += sheet_section("Ammunition", width=W)
        ammo = inv.ammunition.all()
        if ammo:
            output += f"|y{'Ammunition':<25}{'Weapon Type':<25}{'Quantity':<20}|n\n"
            for a in ammo:
                output += f"|w{a.name:<25}{a.weapon_type:<25}{a.quantity:<20}|n\n"
        else:
            output += "|wNo ammunition in inventory.|n\n"
        output += "\n"

        # Vehicles
        output += sheet_section("Vehicles", width=W)
        vehicles = inv.vehicles.all()
        if vehicles:
            output += f"|y{'Vehicle':<22}{'Category':<8}{'SDP':<6}{'Seats':<6}{'Speed':<18}{'Value':<10}|n\n"
            for v in vehicles:
                speed = (v.speed_narrative or "N/A")[:17]
                output += f"|w{v.name:<22}{v.category:<8}{v.sdp:<6}{v.seats:<6}{speed:<18}{v.value or 0:<10}|n\n"
        else:
            output += "|wNo vehicles in inventory.|n\n"
        output += "\n"

        # Cyberware
        output += sheet_section("Cyberware", width=W)
        cyberware = inv.cyberware.filter(installed=True)
        if cyberware:
            output += f"|y{'Cyberware':<25}{'Type':<18}{'Status':<15}{'Humanity Loss':<15}|n\n"
            for cw in cyberware:
                status = "Installed" if cw.installed else "Uninstalled"
                output += f"|w{cw.cyberware.name:<25}{cw.cyberware.type:<18}{status:<15}{cw.cyberware.humanity_loss:<15}|n\n"
        else:
            output += "|wNo cyberware in inventory.|n\n"
        output += "\n"

        # Vouchers (physical IC objects - in character's contents)
        output += sheet_section("Vouchers", width=W)
        try:
            from typeclasses.vouchers import Voucher
            char_contents = display_char.contents if hasattr(display_char, 'contents') else []
            vouchers = [o for o in char_contents if o.is_typeclass("typeclasses.vouchers.Voucher")]
            if vouchers:
                output += f"|y{'Voucher':<30}{'Items':<15}{'Locked':<10}|n\n"
                for v in vouchers:
                    items = v.get_items() if hasattr(v, 'get_items') else []
                    item_count = sum(it.get("quantity", 1) for it in items)
                    locked = "Yes" if (v.db.locked if hasattr(v, 'db') else False) else "No"
                    output += f"|w{v.key:<30}{item_count:<15}{locked:<10}|n\n"
            else:
                output += "|wNo vouchers in inventory.|n\n"
        except ImportError:
            pass

        output += footer(width=W, fillchar="-")
        output += "\nUse 'inv/info <item>' to view detailed info on a specific item."
        self.caller.msg(output)
        
    def equip_item(self):
        if not self.args:
            self.caller.msg("Usage: equip <weapon name>")
            return

        weapon_name = self.args.strip().lower()

        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = self.caller.character_sheet
        
        if not hasattr(sheet, 'inventory'):
            self.caller.msg("You don't have an inventory.")
            return

        inventory = sheet.inventory

        try:
            weapon = inventory.weapons.get(name__iexact=weapon_name)
        except Weapon.DoesNotExist:
            self.caller.msg(f"You don't have a weapon named '{weapon_name}' in your inventory.")
            return
        except Weapon.MultipleObjectsReturned:
            self.caller.msg(f"You have multiple weapons named '{weapon_name}'. Please be more specific.")
            return

        sheet.eqweapon = weapon
        sheet.save()

        self.caller.msg(f"You have equipped {weapon.name}.")

    def unequip_item(self):
        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = self.caller.character_sheet
        
        if not sheet.eqweapon:
            self.caller.msg("You don't have any weapon equipped.")
            return

        weapon_name = sheet.eqweapon.name
        sheet.eqweapon = None
        sheet.save()

        self.caller.msg(f"You have unequipped your {weapon_name}.")

    def wear_armor(self):
        """inv/wear <armor name> - Wear armor from inventory. Applies EV penalty to evasion."""
        if not self.args:
            self.caller.msg("Usage: inv/wear <armor name> or wear <armor name>")
            return

        if not hasattr(self.caller, 'character_sheet') or not self.caller.character_sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = self.caller.character_sheet
        if not hasattr(sheet, 'inventory') or not sheet.inventory:
            self.caller.msg("You don't have an inventory.")
            return

        armor_name = self.args.strip()
        try:
            armor = sheet.inventory.armor.get(name__iexact=armor_name)
        except Armor.DoesNotExist:
            self.caller.msg(f"You don't have armor named '{armor_name}' in your inventory.")
            return
        except Armor.MultipleObjectsReturned:
            self.caller.msg(f"You have multiple pieces of armor named '{armor_name}'. Be more specific.")
            return

        sheet.eqarmor = armor
        sheet.save()
        ev = armor.ev or 0
        self.caller.msg(f"You are now wearing {armor.name}." + (f" (EV {ev} penalty to evasion)" if ev else ""))

    def remove_armor(self):
        """inv/remove - Remove worn armor."""
        if not hasattr(self.caller, 'character_sheet') or not self.caller.character_sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = self.caller.character_sheet
        if not sheet.eqarmor:
            self.caller.msg("You aren't wearing any armor.")
            return

        armor_name = sheet.eqarmor.name
        sheet.eqarmor = None
        sheet.save()
        self.caller.msg(f"You have removed your {armor_name}.")


class CmdWear(MuxCommand):
    """
    Wear or remove armor.

    Usage:
      wear <armor name>   - Wear armor from your inventory
      remove             - Remove worn armor

    Worn armor shows in your description when others look at you, and applies
    an EV (evasion) penalty to your dodge rolls.
    """
    key = "wear"
    aliases = ["remove"]
    help_category = "Inventory"

    def func(self):
        char = self.caller
        if not hasattr(char, 'character_sheet') or not char.character_sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        if self.cmdstring == "remove":
            sheet = char.character_sheet
            if not sheet.eqarmor:
                self.caller.msg("You aren't wearing any armor.")
                return
            armor_name = sheet.eqarmor.name
            sheet.eqarmor = None
            sheet.save()
            self.caller.msg(f"You have removed your {armor_name}.")
            return

        if not self.args:
            self.caller.msg("Usage: wear <armor name>")
            return

        sheet = char.character_sheet
        if not hasattr(sheet, 'inventory') or not sheet.inventory:
            self.caller.msg("You don't have an inventory.")
            return

        armor_name = self.args.strip()
        try:
            armor = sheet.inventory.armor.get(name__iexact=armor_name)
        except Armor.DoesNotExist:
            self.caller.msg(f"You don't have armor named '{armor_name}' in your inventory.")
            return
        except Armor.MultipleObjectsReturned:
            self.caller.msg(f"You have multiple pieces of armor named '{armor_name}'. Be more specific.")
            return

        sheet.eqarmor = armor
        sheet.save()
        ev = armor.ev or 0
        self.caller.msg(f"You are now wearing {armor.name}." + (f" (EV {ev} penalty to evasion)" if ev else ""))


class CmdEquip(Command):
    """
    Admin equipment commands.

    Usage:
      equip/add <player>=<item> - Give a player an item from the database
      equip/remove <player>=<item> - Remove an item from a player's inventory

    """

    key = "equip"
    aliases = ["equipment"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: equip/add <player>=<item> or equip/remove <player>=<item>")
            return

        if "add" in self.args:
            self.add_item()
        elif "remove" in self.args:
            self.remove_item()
    
    def add_item(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: equip/add <player>=<item>")
            return
        
        player_name, item_name = self.args.split(None, 1)
        player = self.caller.search(player_name, global_search=True)
        if not player:
            return

        item = self.caller.search(item_name)
        if not item:
            self.caller.msg(f"Item '{item_name}' does not exist.")
            return
        
        if item.type == "weapon":
            self.add_weapon()
        elif item.type == "armor":
            self.add_armor()
        elif item.type == "gear":
            self.add_gear()
        else:
            self.caller.msg(f"Item '{item_name}' is not a valid weapon, armor, or gear.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return
        
        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.weapons.add(item)
        self.caller.msg(f"Added {item.name} to {player.name}'s inventory.")
        player.msg(f"A {item.name} has been added to your inventory.")

    def remove_item(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: equip/remove <player>=<item>")
            return

        player_name, item_name = self.args.split(None, 1)
        player = self.caller.search(player_name, global_search=True)
        if not player:
            return
        
        try:
            item = Weapon.objects.get(name__iexact=item_name.strip('"'))
        except Weapon.DoesNotExist:
            self.caller.msg(f"Weapon '{item_name}' does not exist.")
            return
        
        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return
        
        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.weapons.remove(item)
        self.caller.msg(f"Removed {item.name} from {player.name}'s inventory.")
        player.msg(f"A {item.name} has been removed from your inventory.")

    def add_weapon(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: addweapon <player> <weapon_name>")
            return

        player_name, weapon_name = self.args.split(None, 1)
        player = self.caller.search(player_name, global_search=True)
        if not player:
            return

        try:
            weapon = Weapon.objects.get(name__iexact=weapon_name.strip('"'))
        except Weapon.DoesNotExist:
            self.caller.msg(f"Weapon '{weapon_name}' does not exist.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.weapons.add(weapon)
        self.caller.msg(f"Added {weapon.name} to {player.name}'s inventory.")
        player.msg(f"A {weapon.name} has been added to your inventory.")

    def add_armor(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: addarmor <player> <armor_name>")
            return

        player_name, armor_name = self.args.split(None, 1)
        player = self.caller.search(player_name, global_search=True)
        if not player:
            return

        try:
            armor = Armor.objects.get(name__iexact=armor_name.strip('"'))
        except Armor.DoesNotExist:
            self.caller.msg(f"Armor '{armor_name}' does not exist.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.armor.add(armor)
        self.caller.msg(f"Added {armor.name} to {player.name}'s inventory.")
        player.msg(f"A {armor.name} has been added to your inventory.")

    def add_gear(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: addgear <player> <gear_name>")
            return

        player_name, gear_name = self.args.split(None, 1)
        player = self.caller.search(player_name, global_search=True)
        if not player:
            return

        try:
            gear = Gear.objects.get(name__iexact=gear_name.strip('"'))
        except Gear.DoesNotExist:
            self.caller.msg(f"Gear '{gear_name}' does not exist.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.add_gear(gear)
        self.caller.msg(f"Added {gear.name} to {player.name}'s inventory.")
        player.msg(f"A {gear.name} has been added to your inventory.")