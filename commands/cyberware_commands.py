from evennia import Command
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import CyberwareInstance
from world.utils.character_utils import get_staff_target_character
from world.cyberware.models import Cyberware
from evennia.commands.default.muxcommand import MuxCommand
from world.utils.formatting import sheet_header, footer, header, divider
from django.db.models import Q
from world.equipment_data import (
    get_popup_melee_weapons,
    get_popup_ranged_weapons,
    get_weapon_by_name,
    get_weapon_damage_dice,
)

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
      cyberware/parent <cyberware child>=<cyberware parent>

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

        # Staff can view another: cyberware <name> (list only)
        if raw:
            first_word = raw.split()[0]
            target_char, character_sheet = get_staff_target_character(
                self.caller, first_word, quiet=True
            )
            if target_char is not None and character_sheet is not None:
                if self.switches and any(s in self.switches for s in ("activate", "deactivate", "install")):
                    self.caller.msg("You can only view another character's cyberware, not modify it.")
                    return
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
            if "=" not in raw:
                self.caller.msg("Usage: cyberware/parent <cyberware child>=<cyberware parent>")
                return
            child_name, parent_name = raw.split("=", 1)
            self._do_parent(character_sheet, child_name.strip(), parent_name.strip())
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
        child_inst = CyberwareInstance.objects.filter(
            character_sheet=character_sheet,
            installed=True,
            cyberware__name__iexact=child_name,
        ).first()
        if not child_inst:
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
        if child_inst.parent_id == parent_inst.id:
            self.caller.msg(f"{child_inst.cyberware.name} is already assigned to {parent_inst.cyberware.name}.")
            return
        child_inst.parent = parent_inst
        child_inst.save()
        self.caller.msg(f"Assigned {child_inst.cyberware.name} to {parent_inst.cyberware.name}.")

    def list_cyberware(self, character_sheet):
        installed = list(
            CyberwareInstance.objects.filter(character_sheet=character_sheet, installed=True)
            .select_related("cyberware", "parent", "paired_with")
        )
        if not installed:
            self.caller.msg("You have no cyberware installed.")
            return

        W = 78
        output = sheet_header("Installed Cyberware", width=W)
        output += f"|y{'Name':<30}{'Type':<20}{'Humanity Loss':<15}|n\n"

        # Roots: no parent, not paired (paired items are shown under their first-of-pair)
        roots = [i for i in installed if i.parent_id is None and not getattr(i, "paired_with_id", None)]
        shown_ids = set()

        def render_instance(inst, indent=""):
            cw = inst.cyberware
            label = f"{cw.name} (Paired)" if getattr(inst, "paired_with_id", None) else cw.name
            return f"{indent}|w{label:<30}{cw.type:<20}{cw.humanity_loss:<15}|n\n"

        for root in roots:
            if root.id in shown_ids:
                continue
            output += render_instance(root)
            shown_ids.add(root.id)
            for child in installed:
                if child.parent_id == root.id:
                    output += render_instance(child, "- ")
            for paired in installed:
                if getattr(paired, "paired_with_id", None) == root.id:
                    output += render_instance(paired, "- ")
                    shown_ids.add(paired.id)
                    for pchild in installed:
                        if pchild.parent_id == paired.id:
                            output += render_instance(pchild, "- ")

        output += footer(width=W, fillchar="-")
        output += "\nUse cyberware/info <cyberware name> for more information."
        self.caller.msg(output)

    def view_specific_cyberware(self, character_sheet, cyberware_name):
        cyberware_name = cyberware_name.strip()
        instances = list(
            CyberwareInstance.objects.filter(
                character_sheet=character_sheet,
                cyberware__name__iexact=cyberware_name,
                installed=True,
            ).select_related("cyberware", "parent", "paired_with")
        )
        if not instances:
            self.caller.msg(f"You don't have a piece of cyberware named '{cyberware_name}' installed.")
            return
        cyberware_instance = instances[0]

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
        # Popup Melee/Ranged require weapon selection
        if cw_lower == "popup melee weapon":
            if not weapon_name:
                melee_list = get_popup_melee_weapons()
                names = ", ".join(w["name"] for w in melee_list[:15])
                self.caller.msg(f"Popup Melee Weapon requires a one-handed melee weapon. Usage: cyberware/install \"Popup Melee Weapon\" = \"<weapon>\"")
                self.caller.msg(f"Eligible: {names}{'...' if len(melee_list) > 15 else ''}")
                return
            w = get_weapon_by_name(weapon_name)
            if not w or w.get("category") != "melee" or w.get("hands", 2) != 1:
                self.caller.msg(f"'{weapon_name}' is not a one-handed melee weapon. Use equipdb weapons to browse.")
                return
            cw_instance.popup_weapon_name = w["name"]
        elif cw_lower == "popup ranged weapon":
            if not weapon_name:
                ranged_list = get_popup_ranged_weapons()
                names = ", ".join(w["name"] for w in ranged_list[:15])
                self.caller.msg(f"Popup Ranged Weapon requires a one-handed handgun/SMG. Usage: cyberware/install \"Popup Ranged Weapon\" = \"<weapon>\"")
                self.caller.msg(f"Eligible: {names}{'...' if len(ranged_list) > 15 else ''}")
                return
            w = get_weapon_by_name(weapon_name)
            if not w or w.get("category") != "handgun" or w.get("hands", 2) != 1:
                self.caller.msg(f"'{weapon_name}' is not a one-handed handgun/SMG. Use equipdb weapons to browse.")
                return
            cw_instance.popup_weapon_name = w["name"]
        cw_instance.installed = True
        if not cw_instance.character_sheet:
            cw_instance.character_sheet = character_sheet
        cw_instance.save()
        character_sheet.calculate_humanity_loss()
        # Cyberarm grants minimum 2d6 brawling damage (CPR p.169)
        if cw_lower == "cyberarm":
            character_sheet.has_cyberarm = True
            character_sheet.recalculate_derived_stats()
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
