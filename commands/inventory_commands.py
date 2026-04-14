from evennia import Command
from evennia.utils.ansi import ANSIString
from evennia.commands.default.muxcommand import MuxCommand
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import Weapon, Armor, Gear, Inventory, Ammunition, CyberwareInstance, InventoryArmor, InventoryWeapon, WeaponAttachment
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from world.utils.formatting import (
    sheet_header,
    sheet_section,
    footer,
    inv_info_centered_title,
    inv_info_section_rule,
    inv_info_footer,
    inv_visible_cell,
)
from world.utils.name_fuzzy import pick_named_candidate
from world.utils.ansi_utils import wrap_ansi
from world.lore_weapons import get_flavor_long_description
from world.utils.character_utils import get_character_sheet, get_staff_target_character, is_staff
import logging
import re

logger = logging.getLogger('cyberpunk.inventory')


def _inventory_weapon_type_cell(weapon):
    """Weapon type for the inv table: ``weapon_type`` or ``category``; abbreviates *Very* to *v.*."""
    wt = (getattr(weapon, "weapon_type", None) or "").strip()
    if not wt:
        wt = (getattr(weapon, "category", None) or "").replace("_", " ").strip() or "-"
    return re.sub(r"(?i)\bvery\b", "v.", wt)

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
      inv/attach <weapon>=<attachment> - Attach an attachment to a weapon
      inv/reflavor <char>=<weapon>[/quality] - Staff: random flavor name on target's generic gun (default quality: standard)

    Switches:
      inv/equip, inv/unequip, inv/wear, inv/remove, inv/attach - Modify your equipment
      inv/reflavor - Staff only
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

        # Staff: reflavor before inv <name> parsing (args look like Char=weapon/quality)
        if self.switches and "reflavor" in self.switches:
            self.reflavor_weapon()
            return

        # Staff can view another character: inv <name>
        target_char, character_sheet = get_staff_target_character(self.caller, self.args)
        if target_char is not None and character_sheet is not None:
            # Staff viewing another - only allow view, not equip/wear/etc
            if self.switches and any(s in self.switches for s in ("equip", "unequip", "wear", "remove", "attach")):
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
        if self.switches and "attach" in self.switches:
            self.attach_weapon()
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
        candidates = []
        for weapon in inv.weapons.all():
            candidates.append((weapon.name or "", ("weapon", weapon)))
        for armor in inv.armor.all():
            candidates.append((armor.name or "", ("armor", armor)))
        for gear in inv.gear.all():
            candidates.append((gear.name or "", ("gear", gear)))
        for ammo in inv.ammunition.all():
            candidates.append((ammo.name or "", ("ammo", ammo)))
        for vehicle in inv.vehicles.all():
            candidates.append((vehicle.name or "", ("vehicle", vehicle)))
        for cw in inv.cyberware.all():
            candidates.append((cw.cyberware.name or "", ("cyberware", cw)))

        picked, err = pick_named_candidate(item_name, candidates)
        if err:
            self.caller.msg(err)
            return
        if not picked:
            self.caller.msg(f"No inventory item named '{item_name}' found.")
            return
        kind, obj = picked
        if kind == "weapon":
            self._format_weapon_info(obj, display_char, inv)
        elif kind == "armor":
            inst, _ = InventoryArmor.objects.get_or_create(
                inventory=inv, armor=obj,
                defaults={"current_sp": obj.sp, "original_sp": obj.sp}
            )
            self._format_armor_info(obj, inst, character_sheet, display_char)
        elif kind == "gear":
            self._format_gear_info(obj, display_char)
        elif kind == "ammo":
            self._format_ammo_info(obj, display_char)
        elif kind == "vehicle":
            self._format_vehicle_info(obj, display_char)
        else:
            self._format_cyberware_info(obj, display_char)

    def _format_weapon_info(self, weapon, display_char, inv=None):
        """Format weapon details for display."""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = inv_info_centered_title(f"{weapon.name}{owner}", width=78)
        out += f"|cDamage:|n {weapon.damage or 'N/A'}\n"
        out += f"|cROF:|n {weapon.rof or 'N/A'}\n"
        out += f"|cCategory:|n {weapon.category or 'N/A'}\n"
        quality = getattr(weapon, 'quality', None) or 'standard'
        out += f"|cQuality:|n {quality}\n"
        hands = getattr(weapon, 'hands', None)
        out += f"|cHands:|n {hands if hands is not None else 'N/A'}\n"
        eff_clip = weapon.clip
        if inv and weapon.category not in ("archery", "melee"):
            from world.weapon_constants import get_effective_clip
            eff_clip = get_effective_clip(weapon, inv)
        out += f"|cAmmo:|n {weapon.ammo_type or 'N/A'} (current: {weapon.current_ammo or 0}/{eff_clip})\n"
        flavor_lore = get_flavor_long_description(weapon.name or "")
        if flavor_lore:
            out += inv_info_section_rule("Model", width=78)
            out += wrap_ansi(flavor_lore, width=78) + "\n"
        if weapon.description:
            out += inv_info_section_rule("Description", width=78)
            out += f"{weapon.description}\n"
        out += inv_info_footer(width=78)
        self.caller.msg(out)

    def _format_armor_info(self, armor, inst, character_sheet, display_char):
        """Format armor details for display."""
        base_sp = inst.original_sp if inst.original_sp is not None else armor.sp
        eff_sp = inst.get_effective_sp()
        worn = " |y(worn)|n" if getattr(character_sheet, 'eqarmor', None) == armor else ""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = inv_info_centered_title(f"{armor.name}{owner}", width=78)
        out += f"|cSP:|n {eff_sp} (base {base_sp})"
        if inst.current_sp is not None and inst.current_sp != base_sp:
            out += f" |y(ablation: {inst.current_sp})"
        out += "\n"
        out += f"|cEV:|n {armor.ev or 0}\n"
        out += f"|cLocations:|n {armor.locations or 'N/A'}\n"
        if inst.juryrigged:
            out += "|yJuryrigged:|n Yes\n"
        if armor.description:
            out += inv_info_section_rule("Description", width=78)
            out += f"{armor.description}\n"
        out += inv_info_footer(width=78)
        self.caller.msg(out)

    def _format_gear_info(self, gear, display_char):
        """Format gear details for display."""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = inv_info_centered_title(f"{gear.name}{owner}", width=78)
        out += f"|cCategory:|n {gear.category or 'N/A'}\n"
        out += f"|cValue:|n {gear.value or 0} eb\n"
        if gear.description:
            out += inv_info_section_rule("Description", width=78)
            out += f"{gear.description}\n"
        out += inv_info_footer(width=78)
        self.caller.msg(out)

    def _format_ammo_info(self, ammo, display_char):
        """Format ammunition details for display."""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = inv_info_centered_title(f"{ammo.name}{owner}", width=78)
        out += f"|cType:|n {ammo.ammo_type or 'N/A'}\n"
        out += f"|cQuantity:|n {ammo.quantity}\n"
        out += f"|cWeapon Type:|n {ammo.weapon_type or 'Generic'}\n"
        if ammo.description:
            out += inv_info_section_rule("Description", width=78)
            out += f"{ammo.description}\n"
        out += inv_info_footer(width=78)
        self.caller.msg(out)

    def _format_vehicle_info(self, vehicle, display_char):
        """Format vehicle details for display."""
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = inv_info_centered_title(f"{vehicle.name}{owner}", width=78)
        out += f"|cCategory:|n {vehicle.category or 'N/A'}\n"
        out += f"|cSDP:|n {vehicle.sdp or 0}\n"
        out += f"|cSeats:|n {vehicle.seats or 0}\n"
        out += f"|cSpeed:|n {vehicle.speed_narrative or 'N/A'}\n"
        if vehicle.description:
            out += inv_info_section_rule("Description", width=78)
            out += f"{vehicle.description}\n"
        out += inv_info_footer(width=78)
        self.caller.msg(out)

    def _format_cyberware_info(self, cw_instance, display_char):
        """Format cyberware instance details for display."""
        cw = cw_instance.cyberware
        name = getattr(display_char.db, 'full_name', None) or getattr(display_char, 'key', '')
        owner = f" ({name}'s)" if display_char != self.caller else ""
        out = inv_info_centered_title(f"{cw.name}{owner}", width=78)
        out += f"|cType:|n {cw.type or 'N/A'}\n"
        out += f"|cHumanity Loss:|n {cw.humanity_loss}\n"
        out += f"|cStatus:|n {'Installed' if cw_instance.installed else 'Uninstalled'}\n"
        if getattr(cw_instance, "popup_weapon_name", None):
            out += f"|cWeapon:|n {cw_instance.popup_weapon_name}\n"
        if cw.description:
            out += inv_info_section_rule("Description", width=78)
            out += f"{cw.description}\n"
        out += inv_info_footer(width=78)
        self.caller.msg(out)

    def _show_inventory(self, character_sheet, display_char):
        """Display inventory for a character (used for self or staff viewing another)."""
        inv = character_sheet.inventory
        W = 78
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
        # 78 visible chars incl. `` |y*|n`` (2 vis): cols + 4 single spaces between 5 columns
        wn, wd, wtyp, wr, wa = 37, 7, 12, 5, 11
        if weapons:
            from world.weapon_constants import get_effective_clip
            output += (
                f"|y{inv_visible_cell('Weapon', wn)} {inv_visible_cell('Damage', wd)} "
                f"{inv_visible_cell('Type', wtyp)} {inv_visible_cell('ROF', wr)} "
                f"{inv_visible_cell('Ammo', wa)}|n\n"
            )
            for weapon in weapons:
                eq_mark = " |y*|n" if getattr(character_sheet, 'eqweapon', None) == weapon else ""
                if getattr(weapon, "clip", 0) and weapon.category not in ("archery", "melee"):
                    eff_clip = get_effective_clip(weapon, inv)
                    ammo_display = f"{weapon.current_ammo or 0}/{eff_clip}"
                else:
                    ammo_display = "-"
                type_cell = _inventory_weapon_type_cell(weapon)
                output += (
                    f"|w{inv_visible_cell(weapon.name, wn)}|n "
                    f"|w{inv_visible_cell(weapon.damage or 'N/A', wd)}|n "
                    f"|w{inv_visible_cell(type_cell, wtyp)}|n "
                    f"|w{inv_visible_cell(weapon.rof or 'N/A', wr)}|n "
                    f"|c{inv_visible_cell(ammo_display, wa)}|n"
                )
                output += eq_mark + "\n"
                try:
                    iw = InventoryWeapon.objects.get(inventory=inv, weapon=weapon)
                    for att in iw.installed_attachments.all():
                        output += f"  |y-|n {att.name}\n"
                except InventoryWeapon.DoesNotExist:
                    pass
        else:
            output += "|wNo weapons in inventory.|n\n"
        output += "\n"

        # Armor (inventory pieces + implanted Skin Weave / Subdermal / Sycust rows)
        output += sheet_section("Armor", width=W)
        from world.cyberware.implanted_armor import get_inventory_implanted_armor_rows

        armors = inv.armor.all()
        implant_rows = get_inventory_implanted_armor_rows(character_sheet)
        cn, cs, ce, cl = 26, 12, 6, 31
        if armors or implant_rows:
            output += (
                f"|y{inv_visible_cell('Armor', cn)} {inv_visible_cell('SP', cs)} "
                f"{inv_visible_cell('EV', ce)} {inv_visible_cell('Locations', cl)}|n\n"
            )
            for armor in armors:
                inst, _ = InventoryArmor.objects.get_or_create(
                    inventory=inv, armor=armor,
                    defaults={"current_sp": armor.sp, "original_sp": armor.sp}
                )
                base_sp = inst.original_sp if inst.original_sp is not None else armor.sp
                eff_sp = inst.get_effective_sp()
                if inst.juryrigged:
                    sp_plain = f"{eff_sp} (jury)"
                elif inst.current_sp is not None and inst.current_sp != base_sp:
                    sp_plain = f"{inst.current_sp}/{base_sp}"
                else:
                    sp_plain = str(eff_sp) if eff_sp is not None else "N/A"
                worn_mark = " |y*|n" if getattr(character_sheet, 'eqarmor', None) == armor else ""
                output += (
                    f"|w{inv_visible_cell(armor.name, cn)}|n "
                    f"|w{inv_visible_cell(sp_plain, cs)}|n "
                    f"|w{inv_visible_cell(armor.ev or 'N/A', ce)}|n "
                    f"|w{inv_visible_cell(armor.locations or 'N/A', cl)}|n"
                )
                output += worn_mark + "\n"
            for row in implant_rows:
                output += row
        else:
            output += "|wNo armor in inventory.|n\n"
        output += "\n"

        # Gear (use get_gear_with_quantities if available to show qty)
        output += sheet_section("Gear", width=W)
        gear_items = inv.get_gear_with_quantities() if hasattr(inv, 'get_gear_with_quantities') else [(g, 1) for g in inv.gear.all()]
        gn, gc, gd = 23, 14, 39
        has_cyberdeck = False
        has_program_payload = False
        if gear_items:
            output += (
                f"|y{inv_visible_cell('Gear', gn)} {inv_visible_cell('Category', gc)} "
                f"{inv_visible_cell('Description', gd)}|n\n"
            )
            for gear, qty in gear_items:
                category = (gear.category or "")
                category_lower = category.strip().lower()
                is_cyberdeck = bool(getattr(gear, "is_cyberdeck", False)) or category_lower == "cyberdeck"
                if is_cyberdeck:
                    has_cyberdeck = True
                if category_lower in ("program", "black ice"):
                    has_program_payload = True
                desc_src = gear.description or ""
                if is_cyberdeck and not desc_src:
                    desc_src = "Use `deck` for installed programs/hardware."
                name_display = f"{gear.name} (x{qty})" if qty > 1 else gear.name
                output += (
                    f"|w{inv_visible_cell(name_display, gn)}|n "
                    f"|w{inv_visible_cell(category or 'N/A', gc)}|n "
                    f"|w{inv_visible_cell(desc_src, gd)}|n\n"
                )
        else:
            output += "|wNo gear in inventory.|n\n"
        if has_program_payload and not has_cyberdeck:
            output += "|yYou have Programs/Black ICE in inventory but no cyberdeck. Buy or add a cyberdeck to use them.|n\n"
        if has_cyberdeck:
            output += "|wCyberdeck detected in inventory. Use |cdeck|n for deck slots and loadout details.|n\n"
        output += "\n"

        # Ammunition
        output += sheet_section("Ammunition", width=W)
        ammo = inv.ammunition.all()
        an, aty, aq = 28, 24, 24
        if ammo:
            output += (
                f"|y{inv_visible_cell('Ammunition', an)} {inv_visible_cell('Weapon Type', aty)} "
                f"{inv_visible_cell('Quantity', aq)}|n\n"
            )
            for a in ammo:
                output += (
                    f"|w{inv_visible_cell(a.name, an)}|n "
                    f"|w{inv_visible_cell(a.weapon_type, aty)}|n "
                    f"|w{inv_visible_cell(str(a.quantity), aq)}|n\n"
                )
        else:
            output += "|wNo ammunition in inventory.|n\n"
        output += "\n"

        # Vehicles
        output += sheet_section("Vehicles", width=W)
        vehicles = inv.vehicles.all()
        vn, vcat, vsdp, vseat, vspd, vval = 23, 8, 5, 5, 19, 11
        if vehicles:
            output += (
                f"|y{inv_visible_cell('Vehicle', vn)} {inv_visible_cell('Cat', vcat)} "
                f"{inv_visible_cell('SDP', vsdp)} {inv_visible_cell('Seat', vseat)} "
                f"{inv_visible_cell('Speed', vspd)} {inv_visible_cell('Value', vval)}|n\n"
            )
            for v in vehicles:
                speed = v.speed_narrative or "N/A"
                output += (
                    f"|w{inv_visible_cell(v.name, vn)}|n "
                    f"|w{inv_visible_cell(v.category, vcat)}|n "
                    f"|w{inv_visible_cell(str(v.sdp or 0), vsdp)}|n "
                    f"|w{inv_visible_cell(str(v.seats or 0), vseat)}|n "
                    f"|w{inv_visible_cell(speed, vspd)}|n "
                    f"|w{inv_visible_cell(str(v.value or 0), vval)}|n\n"
                )
        else:
            output += "|wNo vehicles in inventory.|n\n"
        output += "\n"

        # Uninstalled Cyberware (installed items shown via cyberware command)
        output += sheet_section("Uninstalled Cyberware", width=W)
        cyberware = list(inv.cyberware.filter(installed=False).select_related("cyberware"))
        if cyberware:
            name_w, type_w, hl_w = 48, 23, 5
            output += (
                f"|y{inv_visible_cell('Cyberware', name_w)} {inv_visible_cell('Type', type_w)} "
                f"{inv_visible_cell('HL', hl_w)}|n\n"
            )
            for cw_inst in cyberware:
                cw = cw_inst.cyberware
                hl = cw.humanity_loss or 0
                output += (
                    f"|w{inv_visible_cell(cw.name or '', name_w)}|n "
                    f"|w{inv_visible_cell(cw.type or '', type_w)}|n "
                    f"|w{inv_visible_cell(str(hl), hl_w)}|n\n"
                )
            output += "|wUse the 'cyberware' command to see installed cyberware.|n\n"
        else:
            output += "|wNo uninstalled cyberware in inventory.|n\n"
            output += "|wUse the 'cyberware' command to see installed cyberware.|n\n"
        output += "\n"

        # Vouchers (physical IC objects - in character's contents)
        output += sheet_section("Vouchers", width=W)
        try:
            from typeclasses.vouchers import Voucher
            char_contents = display_char.contents if hasattr(display_char, 'contents') else []
            vouchers = [o for o in char_contents if o.is_typeclass("typeclasses.vouchers.Voucher")]
            if vouchers:
                vvn, vvi, vvl = 34, 18, 24
                output += (
                    f"|y{inv_visible_cell('Voucher', vvn)} {inv_visible_cell('Items', vvi)} "
                    f"{inv_visible_cell('Locked', vvl)}|n\n"
                )
                for v in vouchers:
                    items = v.get_items() if hasattr(v, 'get_items') else []
                    item_count = sum(it.get("quantity", 1) for it in items)
                    locked = "Yes" if (v.db.locked if hasattr(v, 'db') else False) else "No"
                    output += (
                        f"|w{inv_visible_cell(v.key, vvn)}|n "
                        f"|w{inv_visible_cell(str(item_count), vvi)}|n "
                        f"|w{inv_visible_cell(locked, vvl)}|n\n"
                    )
            else:
                output += "|wNo vouchers in inventory.|n\n"
        except ImportError:
            pass

        output += footer(width=W, fillchar="-")
        output += "\nUse 'inv/info <item>' to view detailed info on a specific item."
        self.caller.msg(output)

    def equip_item(self):
        if not self.args:
            self.caller.msg("Usage: inv/equip <weapon name> or equip <weapon name>")
            return

        weapon_name = self.args.strip()

        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = self.caller.character_sheet

        if not hasattr(sheet, 'inventory'):
            self.caller.msg("You don't have an inventory.")
            return

        inventory = sheet.inventory
        weapon = _find_weapon_for_equip(self.caller, inventory, weapon_name)
        if weapon is None:
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

    def attach_weapon(self):
        """inv/attach <weapon>=<attachment> - Attach an attachment to a weapon."""
        from world.weapon_constants import (
            populate_core_attachments,
            get_clip_size,
            DEFAULT_RANGED_ATTACHMENT_SLOTS,
        )
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: inv/attach <weapon>=<attachment>")
            return
        weapon_name, attachment_name = self.args.split("=", 1)
        weapon_name = weapon_name.strip()
        attachment_name = attachment_name.strip()
        if not weapon_name or not attachment_name:
            self.caller.msg("Usage: inv/attach <weapon>=<attachment>")
            return

        if not hasattr(self.caller, 'character_sheet') or not self.caller.character_sheet:
            self.caller.msg("You don't have a character sheet.")
            return
        sheet = self.caller.character_sheet
        if not hasattr(sheet, 'inventory') or not sheet.inventory:
            self.caller.msg("You don't have an inventory.")
            return
        inv = sheet.inventory

        weapon = _find_weapon_for_equip(self.caller, inv, weapon_name)
        if not weapon:
            return

        # Ensure core attachments exist
        populate_core_attachments()

        att = WeaponAttachment.objects.filter(name__iexact=attachment_name).first()
        if not att:
            candidates = list(WeaponAttachment.objects.filter(name__icontains=attachment_name)[:5])
            if len(candidates) == 1:
                att = candidates[0]
            elif candidates:
                self.caller.msg(f"Did you mean: {', '.join(a.name for a in candidates)}?")
                return
            else:
                self.caller.msg(f"Attachment '{attachment_name}' not found. Use 'list equipment attachments' to see available.")
                return

        if not att.is_eligible_for_weapon(weapon):
            self.caller.msg(f"{att.name} cannot be attached to {weapon.name}.")
            return

        try:
            iw = InventoryWeapon.objects.get(inventory=inv, weapon=weapon)
        except InventoryWeapon.DoesNotExist:
            self.caller.msg("Weapon not found in your inventory.")
            return

        if att in iw.installed_attachments.all():
            self.caller.msg(f"{att.name} is already attached to {weapon.name}.")
            return

        slots_used = sum(a.slot_cost for a in iw.installed_attachments.all())
        weapon_slots = weapon.attachment_slots or (
            DEFAULT_RANGED_ATTACHMENT_SLOTS if weapon.category in ("handgun", "shoulder_arms", "heavy_weapons") else 0
        )
        if slots_used + att.slot_cost > weapon_slots:
            self.caller.msg(
                f"Not enough attachment slots. {weapon.name} has {weapon_slots} slots, "
                f"using {slots_used}, {att.name} needs {att.slot_cost}."
            )
            return

        iw.installed_attachments.add(att)

        # Apply clip modifier if Extended/Drum Magazine
        if att.clip_modifier in ("extended", "drum"):
            wt = weapon.weapon_type or weapon.category or "medium pistol"
            new_clip = get_clip_size(wt, att.clip_modifier)
            weapon.clip = new_clip
            weapon.max_ammo = new_clip
            weapon.save()

        self.caller.msg(f"You attach {att.name} to {weapon.name}.")

    def reflavor_weapon(self):
        """
        Staff: inv/reflavor <character name>=<weapon>[/quality]

        Quality optional: poor | standard | excellent. If omitted or blank after /, uses standard.
        """
        from world.edgerunner_weapon_flavor import reflavor_weapon_instance

        if not is_staff(self.caller):
            self.caller.msg("Only staff (Builder+) can use inv/reflavor.")
            return

        raw = (self.args or "").strip()
        if "=" not in raw:
            self.caller.msg(
                "Usage: inv/reflavor <character name>=<weapon>[/quality]\n"
                "Examples:\n"
                "  inv/reflavor Alice=Very Heavy Pistol\n"
                "  inv/reflavor Alice=Very Heavy Pistol/excellent\n"
                "Quality defaults to standard when omitted."
            )
            return

        char_name, rhs = raw.split("=", 1)
        char_name = char_name.strip()
        rhs = rhs.strip()
        if not char_name or not rhs:
            self.caller.msg(
                "Usage: inv/reflavor <character name>=<weapon>[/quality]"
            )
            return

        if "/" in rhs:
            weapon_part, qpart = rhs.split("/", 1)
            weapon_part = weapon_part.strip()
            qpart = (qpart or "").strip().lower()
            if qpart and qpart not in ("poor", "standard", "excellent"):
                self.caller.msg("Quality must be poor, standard, or excellent.")
                return
            quality = qpart if qpart else "standard"
        else:
            weapon_part = rhs
            quality = "standard"

        if not weapon_part:
            self.caller.msg("Weapon name is required after '=' (e.g. Alice=Very Heavy Pistol).")
            return

        target_char, sheet = get_staff_target_character(self.caller, char_name, quiet=True)
        if not sheet:
            self.caller.msg(
                f"No character with a character sheet found for '{char_name}'."
            )
            return

        inv = getattr(sheet, "inventory", None)
        if not inv:
            self.caller.msg(f"{char_name} has no inventory.")
            return

        weapon = _find_weapon_for_equip(self.caller, inv, weapon_part)
        if not weapon:
            return

        tkey = getattr(target_char, "key", None) or char_name
        ok, msg = reflavor_weapon_instance(
            weapon,
            quality=quality,
            source_note=f"Staff reflavor by {getattr(self.caller, 'key', 'staff')}",
        )
        if ok:
            self.caller.msg(
                f"|g{tkey}|n: {msg}"
            )
        else:
            self.caller.msg(f"|r{tkey}: {msg}|n")


def _find_weapon_for_equip(caller, inventory, weapon_name):
    """Find weapon by exact name, generic category, flavor chart name, or fuzzy match."""
    from world import edgerunner_weapon_flavor as ewf

    if not weapon_name:
        return None
    raw = weapon_name.strip()
    weapon_name_lower = raw.lower()

    # 1. Exact match (case-insensitive)
    try:
        return inventory.weapons.get(name__iexact=raw)
    except Weapon.DoesNotExist:
        pass
    except Weapon.MultipleObjectsReturned:
        caller.msg(f"You have multiple weapons named '{weapon_name}'. Please be more specific.")
        return None

    # 2. Generic weapon category from flavor chart / quality buy (e.g. "Very Heavy Pistol")
    generic_key = None
    for k in ewf.WEAPON_FLAVOR_BY_QUALITY:
        if k.lower() == raw.lower():
            generic_key = k
            break
    if generic_key:
        matches = [w for w in inventory.weapons.all() if ewf.generic_category_for_weapon(w) == generic_key]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            caller.msg(f"You don't have a {generic_key} in your inventory.")
            return None
        names = ", ".join(w.name for w in matches)
        caller.msg(
            f"You have multiple {generic_key} weapons: {names}. "
            f"Use the weapon's full name to equip one."
        )
        return None

    # 3. Flavor model name from edgerunner_weapon_flavor (matches inventory display name)
    norm_in = ewf.normalize_weapon_label(raw)
    if norm_in and norm_in in ewf.FLAVOR_NAME_TO_GENERIC_TIER:
        matches = [
            w for w in inventory.weapons.all()
            if ewf.normalize_weapon_label(w.name) == norm_in
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            caller.msg(f"You don't have '{weapon_name}' in your inventory.")
            return None
        names = ", ".join(w.name for w in matches)
        caller.msg(f"Multiple weapons match: {names}. Please be more specific.")
        return None

    # 4. Fuzzy: name startswith / contains
    candidates = list(inventory.weapons.filter(name__istartswith=weapon_name_lower))
    if not candidates:
        candidates = list(inventory.weapons.filter(name__icontains=weapon_name_lower))

    if not candidates:
        caller.msg(f"You don't have a weapon matching '{weapon_name}' in your inventory.")
        return None
    if len(candidates) > 1:
        names = ", ".join(w.name for w in candidates)
        caller.msg(f"Multiple weapons match: {names}. Please be more specific.")
        return None
    return candidates[0]


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


class CmdEquipWeapon(MuxCommand):
    """
    Equip a weapon from your inventory for use with attack and dodge commands.

    Usage:
      equip <weapon name>
      wield <weapon name>   - same as equip
      unequip / unwield

    Examples:
      equip Very Heavy Pistol
      wield Arasaka "Raijin"
      unequip
    """
    key = "equip"
    aliases = ["unequip", "wield", "unwield"]
    help_category = "Combat"

    def func(self):
        if self.cmdstring in ("unequip", "unwield"):
            self._unequip()
            return

        if not self.args:
            self.caller.msg("Usage: equip <weapon name>  (aliases: wield <weapon>)")
            return

        if not hasattr(self.caller, 'character_sheet') or not self.caller.character_sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = self.caller.character_sheet
        if not hasattr(sheet, 'inventory') or not sheet.inventory:
            self.caller.msg("You don't have an inventory.")
            return

        weapon = _find_weapon_for_equip(self.caller, sheet.inventory, self.args.strip())
        if weapon is None:
            return

        sheet.eqweapon = weapon
        sheet.save()
        self.caller.msg(f"You have equipped {weapon.name}.")

    def _unequip(self):
        if not hasattr(self.caller, 'character_sheet') or not self.caller.character_sheet:
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