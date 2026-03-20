from evennia import Command
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import CyberwareInstance
from world.utils.character_utils import get_staff_target_character
from world.cyberware.models import Cyberware
from evennia.commands.default.muxcommand import MuxCommand
from world.utils.formatting import sheet_header, footer, header, divider
from world.utils.name_fuzzy import pick_named_candidate
from django.db.models import Q
from world.equipment_data import (
    get_popup_melee_weapons,
    get_popup_ranged_weapons,
    get_weapon_by_name,
    get_weapon_damage_dice,
)
from world.cyberware.validation import (
    validate_parent_child,
    validate_parent_for_new_child,
    select_child_instance_for_parenting,
)
from world.cyberware.merchants import check_cyberware_requirements

class CmdCyberware(MuxCommand):
    """
    Show installed cyberware and its information.

    Usage:
      cyberware                    - List your cyberware
      cyberware/info <item>        - Detailed info on a cyberware item
      cyberware <name>             - Staff: list another's cyberware
      cyberware/info <name>/<item> - Staff: detailed info on another's cyberware
      cyberware/activate <name>
      cyberware/deactivate [<name>]
      cyberware/install <name>
      cyberware/install "Popup Melee Weapon" = "<weapon>"
      cyberware/install "Popup Ranged Weapon" = "<weapon>"
      cyberware/parent <option>=<parent>   - Assign option to parent (e.g. image enhance=cybereye)
      cyberware/unparent <cyberware child>     - Disconnect option from parent; uninstall and refund humanity
      cyberware/unparent <name>/<child>       - Staff: unparent from another character

    Activate/deactivate: cyberware weapons (Big Knucks, Rippers, Slice N Dice, Wolvers, Popup Melee/Ranged).
    """

    key = "cyberware"
    aliases = ["cyber"]
    lock = "cmd:all()"
    help_category = "Character"

    def func(self):
        raw = (self.args or "").strip()

        # cyberware/info <name>/<item> or cyberware/info <item>
        if "info" in self.switches:
            self._do_info(raw)
            return

        # Staff can view another: cyberware <name> (list only). Skip when using activate/deactivate/install/parent/unparent - args are cyberware names.
        if raw and not any(s in (self.switches or []) for s in ("activate", "deactivate", "install", "parent", "unparent")):
            first_word = raw.split()[0]
            target_char, character_sheet = get_staff_target_character(
                self.caller, first_word, quiet=True
            )
            if target_char is not None and character_sheet is not None:
                self.list_cyberware(character_sheet)
                return
            if len(raw.split()) == 1:
                from world.utils.character_utils import is_staff
                if is_staff(self.caller):
                    self.caller.msg(f"No character named '{first_word}' found.")
                    return

        try:
            character_sheet = CharacterSheet.objects.get(character=self.caller)
        except CharacterSheet.DoesNotExist:
            self.caller.msg("You don't have a character sheet. Please create one using the 'chargen' command.")
            return

        if not character_sheet:
            self.caller.msg("You don't have a character sheet. Please create one using the 'chargen' command.")
            return

        if self.switches and "activate" in self.switches:
            self.activate_cyberware(character_sheet, raw if raw else "")
            return
        if self.switches and "deactivate" in self.switches:
            self.deactivate_cyberware(character_sheet, raw if raw else None)
            return
        if self.switches and "install" in self.switches:
            if "=" in raw:
                parts = raw.split("=", 1)
                self.install_cyberware(character_sheet, parts[0].strip(), parts[1].strip())
            else:
                self.install_cyberware(character_sheet, raw, None)
            return
        if self.switches and "parent" in self.switches:
            if "=" in raw:
                option_name, parent_name = raw.split("=", 1)
            elif "/" in raw:
                option_name, parent_name = raw.split("/", 1)
            else:
                self.caller.msg("Usage: cyberware/parent <option>=<parent> (e.g. cyberware/parent image enhance=cybereye)")
                return
            self._do_parent(character_sheet, option_name.strip(), parent_name.strip())
            return
        if self.switches and "unparent" in self.switches:
            if not raw:
                self.caller.msg("Usage: cyberware/unparent <cyberware child>")
                return
            # Staff: <name>/<child> to unparent from another character
            from world.utils.character_utils import is_staff
            if is_staff(self.caller) and "/" in raw:
                name_part, child_name = raw.split("/", 1)
                name_part = name_part.strip()
                child_name = child_name.strip()
                target_char, target_sheet = get_staff_target_character(
                    self.caller, name_part, quiet=True
                )
                if target_char is None or target_sheet is None:
                    self.caller.msg(f"No character named '{name_part}' found.")
                    return
                self._do_unparent(target_sheet, child_name)
            else:
                self._do_unparent(character_sheet, raw.strip())
            return
        if not raw:
            self.list_cyberware(character_sheet)
        else:
            self.view_specific_cyberware(character_sheet, raw)

    def _do_info(self, raw):
        """Handle cyberware/info <item> or cyberware/info <name>/<item>."""
        if not raw:
            self.caller.msg("Usage: cyberware/info <item> or cyberware/info <name>/<item> (staff)")
            return
        target_char, character_sheet = None, None
        item_name = raw
        if "/" in raw:
            from world.utils.character_utils import is_staff
            if not is_staff(self.caller):
                self.caller.msg("Only staff can view another character's cyberware.")
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
        else:
            try:
                character_sheet = CharacterSheet.objects.get(character=self.caller)
            except CharacterSheet.DoesNotExist:
                self.caller.msg("You don't have a character sheet.")
                return
        self.view_specific_cyberware(character_sheet, item_name)

    def _do_parent(self, character_sheet, child_name, parent_name):
        """Assign a cyberware option (child) to its parent limb."""
        child_candidates = CyberwareInstance.objects.filter(
            character_sheet=character_sheet,
            installed=True,
            cyberware__name__iexact=child_name,
        )
        if not child_candidates.exists():
            self.caller.msg(f"You don't have installed cyberware named '{child_name}'.")
            return
        parent_inst = CyberwareInstance.objects.filter(
            character_sheet=character_sheet,
            installed=True,
            cyberware__name__iexact=parent_name,
        ).first()
        if not parent_inst:
            self.caller.msg(f"You don't have installed cyberware named '{parent_name}'.")
            return
        child_inst, pick_status = select_child_instance_for_parenting(child_candidates, parent_inst)
        if pick_status == "already":
            self.caller.msg(f"{child_inst.cyberware.name} is already assigned to {parent_inst.cyberware.name}.")
            return
        if pick_status == "all_busy" or child_inst is None:
            self.caller.msg(
                f"Every '{child_name}' you have is already assigned to another limb. "
                f"Unparent or uninstall one first, or buy another copy."
            )
            return
        ok, err = validate_parent_child(parent_inst, child_inst)
        if not ok:
            self.caller.msg(err)
            return
        child_inst.parent = parent_inst
        child_inst.save()
        self.caller.msg(f"Assigned {child_inst.cyberware.name} to {parent_inst.cyberware.name}.")

    def _do_unparent(self, character_sheet, child_name):
        """Disconnect a cyberware option from its parent; uninstall and refund humanity."""
        child_inst = CyberwareInstance.objects.filter(
            character_sheet=character_sheet,
            cyberware__name__iexact=child_name,
            installed=True,
            parent__isnull=False,
        ).select_related("cyberware", "parent").first()

        if not child_inst:
            self.caller.msg(
                f"No installed {child_name} with a parent found. "
                "Use cyberware/parent to assign options to limbs."
            )
            return

        cyberware = child_inst.cyberware
        parent_name = child_inst.parent.cyberware.name if child_inst.parent else "?"

        child_inst.parent = None
        child_inst.installed = False
        child_inst.active = False
        child_inst.save()

        character_sheet.calculate_humanity_loss()
        char = getattr(character_sheet, "character", None)
        if char and hasattr(char, "db"):
            from world.cyberpunk_sheets.edgerunner import EdgerunnerChargen
            EdgerunnerChargen.recalculate_humanity_for_typeclass(char)

        self.caller.msg(
            f"Unparented {cyberware.name} from {parent_name}. "
            f"Humanity refunded ({cyberware.humanity_loss}). Use cyberware/parent to re-assign."
        )
        # Notify the character if different from caller (staff unparenting)
        if char and char != self.caller and hasattr(char, "msg"):
            char.msg(
                f"Your {cyberware.name} has been disconnected from {parent_name} and uninstalled. "
                f"Humanity refunded. Use cyberware/parent to re-assign it."
            )

    def list_cyberware(self, character_sheet):
        # Use inventory.cyberware (same source as sheet display) so staff sees all installed items
        from world.inventory.models import Inventory
        try:
            inv = character_sheet.inventory
        except (Inventory.DoesNotExist, AttributeError):
            sheet_pk = getattr(character_sheet, "pk", None)
            if sheet_pk:
                inv, _ = Inventory.objects.get_or_create(character_id=sheet_pk)
            else:
                inv = None
        if inv:
            installed = list(
                inv.cyberware.filter(installed=True).select_related(
                    "cyberware", "parent", "parent__cyberware", "paired_with"
                )
            )
        else:
            installed = list(
                CyberwareInstance.objects.filter(character_sheet=character_sheet, installed=True)
                .select_related("cyberware", "parent", "parent__cyberware", "paired_with")
            )
        if not installed:
            self.caller.msg("You have no cyberware installed.")
            return

        from world.cyberware.utils import format_cyberware_by_category

        W = 78
        output = sheet_header("Installed Cyberware", width=W)
        output += format_cyberware_by_category(installed, character_sheet)
        output += footer(width=W, fillchar="-")
        output += "\nUse cyberware/info <cyberware name> for more information."
        self.caller.msg(output)

    def view_specific_cyberware(self, character_sheet, cyberware_name):
        cyberware_name = cyberware_name.strip()
        # Use inventory.cyberware (same source as list) for consistency
        from world.inventory.models import Inventory
        try:
            inv = character_sheet.inventory
        except (Inventory.DoesNotExist, AttributeError):
            inv = None
        if inv:
            instances = list(
                inv.cyberware.filter(installed=True).select_related(
                    "cyberware", "parent", "paired_with"
                )
            )
        else:
            instances = list(
                CyberwareInstance.objects.filter(
                    character_sheet=character_sheet,
                    installed=True,
                ).select_related("cyberware", "parent", "paired_with")
            )
        if not instances:
            self.caller.msg("You have no cyberware installed.")
            return
        candidates = [(inst.cyberware.name or "", inst) for inst in instances]
        cyberware_instance, err = pick_named_candidate(cyberware_name, candidates)
        if err:
            self.caller.msg(err)
            return
        if not cyberware_instance:
            self.caller.msg(
                f"You don't have a piece of cyberware named '{cyberware_name}' installed."
            )
            return

        cyberware = cyberware_instance.cyberware
        
        output = header(cyberware.name, width=78, fillchar="|m-|n") + "\n"
        output += f"|cType:|n {cyberware.type}\n"
        output += f"|cSlots:|n {cyberware.slots}\n"
        output += f"|cHumanity Loss:|n {cyberware.humanity_loss}\n"
        output += f"|cCost:|n {cyberware.cost} eb\n"
        output += divider("Description", width=78, fillchar="|m-|n") + "\n"
        output += f"{cyberware.description}\n"
        if getattr(cyberware_instance, "popup_weapon_name", None):
            output += f"\n|cWeapon:|n {cyberware_instance.popup_weapon_name}\n"
        output += footer(width=78, fillchar="|m-|n")
        
        self.caller.msg(output)
    def install_cyberware(self, character_sheet, cyberware_name, weapon_name=None):
        """Install uninstalled cyberware (e.g. purchased from Ripperdoc).
        For Popup Melee Weapon / Popup Ranged Weapon: cyberware/install "Popup Melee Weapon" = "Light Melee Weapon"
        """
        if not cyberware_name:
            self.caller.msg("Usage: cyberware/install <name>")
            self.caller.msg("For Popup Melee/Ranged: cyberware/install \"Popup Melee Weapon\" = \"Light Melee Weapon\"")
            return
        cw_instance = CyberwareInstance.objects.filter(
            Q(character_sheet=character_sheet) | Q(character_object=self.caller),
            cyberware__name__iexact=cyberware_name,
            installed=False
        ).first()
        if not cw_instance:
            self.caller.msg(
                f"You don't have uninstalled cyberware named '{cyberware_name}'. "
                "Check your inventory with 'inv' to see uninstalled cyberware."
            )
            return
        cw = cw_instance.cyberware
        cw_lower = cw.name.lower()
        # Popup Melee/Ranged require weapon selection - you must specify the weapon
        if cw_lower == "popup melee weapon":
            if not weapon_name or not weapon_name.strip():
                melee_list = get_popup_melee_weapons()
                names = ", ".join(w["name"] for w in melee_list[:15])
                self.caller.msg(
                    "|rError:|n Popup Melee Weapon requires specifying a one-handed melee weapon. "
                    "You must provide the weapon name."
                )
                self.caller.msg(
                    f"Usage: |wcyberware/install \"Popup Melee Weapon\" = \"<weapon>\"|n "
                    "(e.g. Light Melee Weapon, Medium Melee Weapon, Heavy Melee Weapon)"
                )
                self.caller.msg(f"Eligible one-handed melee weapons: {names}{'...' if len(melee_list) > 15 else ''}")
                return
            w = get_weapon_by_name(weapon_name)
            if not w or w.get("category") != "melee" or w.get("hands", 2) != 1:
                self.caller.msg(f"'{weapon_name}' is not a one-handed melee weapon. Use equipdb weapons to browse.")
                return
            cw_instance.popup_weapon_name = w["name"]
        elif cw_lower == "popup ranged weapon":
            if not weapon_name or not weapon_name.strip():
                ranged_list = get_popup_ranged_weapons()
                names = ", ".join(w["name"] for w in ranged_list[:15])
                self.caller.msg(
                    "|rError:|n Popup Ranged Weapon requires specifying a one-handed handgun. "
                    "You must provide the weapon name."
                )
                self.caller.msg(
                    f"Usage: |wcyberware/install \"Popup Ranged Weapon\" = \"<weapon>\"|n "
                    "(e.g. Medium Pistol, Heavy Pistol, Very Heavy Pistol)"
                )
                self.caller.msg(f"Eligible one-handed handguns: {names}{'...' if len(ranged_list) > 15 else ''}")
                return
            w = get_weapon_by_name(weapon_name)
            if not w or w.get("category") != "handgun" or w.get("hands", 2) != 1:
                self.caller.msg(f"'{weapon_name}' is not a one-handed handgun/SMG. Use equipdb weapons to browse.")
                return
            cw_instance.popup_weapon_name = w["name"]
        # Popup Melee/Ranged require a Cyberarm parent with available slots
        if cw_lower in ("popup melee weapon", "popup ranged weapon"):
            parent_arm = None
            for inst in CyberwareInstance.objects.filter(
                character_sheet=character_sheet,
                installed=True,
                cyberware__name__in=["Cyberarm", "Neo-Soviet Cyberarm"],
            ).select_related("cyberware"):
                ok, _ = validate_parent_for_new_child(inst, cw_instance.cyberware)
                if ok:
                    parent_arm = inst
                    break
            if not parent_arm:
                self.caller.msg(
                    f"You need an installed Cyberarm (or Neo-Soviet Cyberarm) with at least 2 free option slots "
                    f"to install {cw.name}. Install a Cyberarm first, or free up slots with cyberware/unparent."
                )
                return
            cw_instance.parent = parent_arm
        # Validate requirements (solo-limb, Self-ICE limit, etc.) same as purchase
        requirements_met, error_message = check_cyberware_requirements(character_sheet, cw)
        if not requirements_met:
            self.caller.msg(error_message)
            return
        cw_instance.installed = True
        if not cw_instance.character_sheet:
            cw_instance.character_sheet = character_sheet
        cw_instance.save()
        character_sheet.consume_uninstalled_hl_for_cyberware(cw)
        character_sheet.calculate_humanity_loss()
        # Cyberarm grants minimum 2d6 brawling damage (CPR p.169)
        if cw_lower == "cyberarm":
            character_sheet.has_cyberarm = True
            character_sheet.recalculate_derived_stats()
        char = getattr(character_sheet, "character", None)
        if char and hasattr(char, "recalculate_derived_stats"):
            char.recalculate_derived_stats()
        try:
            from world.cyberware.implanted_armor import ensure_implanted_armor_for_sheet

            ensure_implanted_armor_for_sheet(character_sheet)
        except Exception:
            pass
        msg = f"You have installed {cw.name}."
        if cw_instance.popup_weapon_name:
            msg += f" Weapon: {cw_instance.popup_weapon_name}."
        msg += f" Humanity loss: {cw.humanity_loss}. Current humanity: {character_sheet.humanity}."
        self.caller.msg(msg)

    def _get_cyberware_weapon_damage(self, cw_instance):
        """Get damage dice for a cyberware weapon (built-in or popup template)."""
        cw = cw_instance.cyberware
        if cw.is_weapon and cw.damage_dice:
            return cw.damage_dice
        # Popup Melee/Ranged use equipment_data template
        popup_name = (getattr(cw_instance, "popup_weapon_name", None) or "").strip()
        if popup_name and cw.name.lower() in ("popup melee weapon", "popup ranged weapon"):
            return get_weapon_damage_dice(popup_name)
        return 0

    def activate_cyberware(self, character_sheet, cyberware_name):
        cyberware_name = (cyberware_name or "").strip()
        if not cyberware_name:
            self.caller.msg("Usage: cyberware/activate <name>")
            return
        # Find installed cyberware: built-in weapons (is_weapon) OR Popup Melee/Ranged with popup_weapon_name
        cw_instance = CyberwareInstance.objects.filter(
            character_sheet=character_sheet,
            installed=True,
        ).filter(
            Q(cyberware__name__iexact=cyberware_name) | Q(cyberware__name__icontains=cyberware_name)
        ).first()
        if not cw_instance:
            self.caller.msg(f"You don't have installed cyberware named '{cyberware_name}'.")
            return
        cw = cw_instance.cyberware
        # Must be a weapon: built-in (is_weapon) or Popup with template
        weapon_damage = self._get_cyberware_weapon_damage(cw_instance)
        if not weapon_damage and not cw.is_weapon:
            self.caller.msg(f"'{cw.name}' is not a cyberware weapon. Use cyberware/activate for Big Knucks, Rippers, Popup Melee Weapon, etc.")
            return
        if cw.name.lower() in ("popup melee weapon", "popup ranged weapon") and not cw_instance.popup_weapon_name:
            self.caller.msg(f"Your {cw.name} has no weapon configured. Reinstall with a weapon: cyberware/install \"{cw.name}\" = \"<weapon>\"")
            return

        # Deactivate any previously activated cyberware
        CyberwareInstance.objects.filter(character_sheet=character_sheet, active=True).update(active=False)

        cw_instance.active = True
        cw_instance.save()

        base_damage_dice = character_sheet.calculate_base_unarmed_damage()
        character_sheet.unarmed_damage_dice = max(base_damage_dice, weapon_damage)
        character_sheet.unarmed_damage_die_type = 6
        character_sheet.save()

        # Sync to character.db for combat/display
        char = getattr(character_sheet, "character", None)
        if char:
            char.db.unarmed_damage_dice = character_sheet.unarmed_damage_dice
            char.db.unarmed_damage_die_type = character_sheet.unarmed_damage_die_type

        display_name = f"{cw.name} ({cw_instance.popup_weapon_name})" if cw_instance.popup_weapon_name else cw.name
        self.caller.msg(f"You have activated {display_name}. Your unarmed strike now deals {character_sheet.unarmed_damage_dice}d6 damage.")

    def deactivate_cyberware(self, character_sheet, cyberware_name=None):
        """Deactivate cyberware weapon; return unarmed damage to base (BODY + has_cyberarm)."""
        active_inst = CyberwareInstance.objects.filter(
            character_sheet=character_sheet, installed=True, active=True
        ).select_related("cyberware").first()
        if not active_inst:
            self.caller.msg("You have no cyberware weapon currently activated.")
            return
        if cyberware_name:
            name_match = (
                active_inst.cyberware.name.lower() == cyberware_name.strip().lower()
                or cyberware_name.strip().lower() in active_inst.cyberware.name.lower()
            )
            if not name_match:
                self.caller.msg(f"'{cyberware_name}' is not your active weapon. Your active weapon is {active_inst.cyberware.name}.")
                return
        active_inst.active = False
        active_inst.save()
        character_sheet.recalculate_derived_stats()
        char = getattr(character_sheet, "character", None)
        if char:
            char.db.unarmed_damage_dice = character_sheet.unarmed_damage_dice
            char.db.unarmed_damage_die_type = character_sheet.unarmed_damage_die_type
        display = f"{active_inst.cyberware.name} ({active_inst.popup_weapon_name})" if active_inst.popup_weapon_name else active_inst.cyberware.name
        self.caller.msg(f"You have deactivated {display}. Unarmed damage returns to base: {character_sheet.unarmed_damage_dice}d6.")
