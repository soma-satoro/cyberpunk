"""
Repair and Juryrig commands for equipment maintenance.

+repair <armor name> - Open a job to repair armor (staff handles roll, money, approve)
+repair/approve <character>=<item> - Staff: reset armor SP to original
+repair/subdermal - Skin Weave / Subdermal: +1 SP each (24h between uses); Sycust Fleshweave: full repair
+armor/staff <char>=<name>, sp=<n|full> - Staff: set worn armor or implanted layer SP
juryrig <name>=<item> - Tech role: temporarily repair at DV (quick fix)
juryrig/off <name>=<item> - Tech or staff: turn off juryrig
"""

import re

from evennia.commands.default.muxcommand import MuxCommand
from world.inventory.models import Armor, Inventory, InventoryArmor
from world.jobs.models import Job, Queue
from world.utils.character_utils import get_character_sheet
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from world.cyberware.implanted_armor import repair_subdermal_command, staff_set_implanted_sp


def _get_inventory_for_character(char):
    """Get Inventory for character (via sheet or object)."""
    sheet = get_character_sheet(char)
    if sheet and hasattr(sheet, "inventory"):
        return sheet.inventory
    from world.inventory.models import Inventory
    inv, _ = Inventory.get_or_create_for_character(char)
    return inv


def _find_armor_in_inventory(inv, armor_name):
    """Find armor by name in inventory. Returns (Armor, InventoryArmor) or (None, None)."""
    armor_name_lower = (armor_name or "").strip().lower()
    for armor in inv.armor.all():
        if (armor.name or "").strip().lower() == armor_name_lower:
            inst, _ = InventoryArmor.objects.get_or_create(
                inventory=inv, armor=armor,
                defaults={"current_sp": armor.sp, "original_sp": armor.sp}
            )
            return armor, inst
    return None, None


class CmdRepair(MuxCommand):
    """
    Request equipment repair (opens a job) or approve repair (staff).

    Usage:
      +repair <armor name>           - Open a repair job for your armor
      +repair/subdermal             - Repair implanted Skin Weave / Subdermal / Sycust (see help)
      +repair/approve <character>=<item> - Staff: mark item repaired (reset SP)

    Repair workflow:
      1. Player: +repair Light Armorjack
      2. Staff assigns, asks player to roll into job: roll/job <#>=<stat> + <skill>
      3. Staff deducts cost: money <name>=-<amount>
      4. Staff approves: +repair/approve <character>=<item>
    """

    key = "+repair"
    help_category = "Inventory"

    def func(self):
        if "approve" in self.switches:
            self._repair_approve()
            return
        # Staff: +repair <name>=<item> (no switch) also runs approve
        if self.args and "=" in self.args and (
            hasattr(self.caller, "check_permstring")
            and (self.caller.check_permstring("builders") or self.caller.check_permstring("wizards"))
        ):
            self._repair_approve()
            return

        if not self.args:
            self.caller.msg("Usage: +repair <armor name>")
            return

        char = self.caller
        if not hasattr(char, "character_sheet") or not char.character_sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        inv = _get_inventory_for_character(char)
        armor, inst = _find_armor_in_inventory(inv, self.args.strip())
        if not armor:
            self.caller.msg(f"You don't have armor named '{self.args.strip()}' in your inventory.")
            return

        base_sp = inst.original_sp if inst.original_sp is not None else armor.sp
        if inst.current_sp is None or inst.current_sp >= base_sp:
            self.caller.msg(f"Your {armor.name} doesn't need repair (SP at {base_sp}).")
            return

        queue, _ = Queue.objects.get_or_create(name="EQUIP", defaults={"automatic_assignee": None})
        char_name = getattr(char.db, "full_name", None) or char.key
        title = f"Repair: {armor.name}"
        description = (
            f"{char_name} requests repair of {armor.name}.\n\n"
            f"Current SP: {inst.current_sp}/{base_sp}\n\n"
            f"Staff: Ask the player to roll into this job (roll/job <#>=<stat> + <skill>). "
            f"If successful, deduct cost (money <name>=-<amount>) and approve with:\n"
            f"+repair/approve {char_name}={armor.name}"
        )

        job = Job.objects.create(
            title=title,
            description=description,
            requester=self.caller.account,
            queue=queue,
            status="open",
            template_args={"repair_armor_name": armor.name, "repair_character_id": char.id},
        )
        self.caller.msg(f"|gRepair job #{job.id} created for {armor.name}.|n Staff will process it.")
        self.caller.msg(
            "Staff will ask you to roll into the job. Use: |wroll/job <job#>=<stat> + <skill>|n"
        )

    def _repair_subdermal_implanted(self):
        ok, msg = repair_subdermal_command(self.caller)
        color = "|g" if ok else "|r"
        self.caller.msg(f"{color}{msg}|n")

    def _repair_approve(self):
        """Staff: +repair/approve <character>=<item> - Reset armor SP to original."""
        if not (
            hasattr(self.caller, "check_permstring")
            and (self.caller.check_permstring("builders") or self.caller.check_permstring("wizards"))
        ):
            self.caller.msg("Only staff can use +repair/approve.")
            return

        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +repair/approve <character>=<item name>")
            return

        char_name, item_name = self.args.split("=", 1)
        char_name = char_name.strip()
        item_name = item_name.strip()

        char = self.caller.search(char_name, global_search=True)
        if not char:
            return
        if not hasattr(char, "character_sheet") or not char.character_sheet:
            self.caller.msg(f"{char.key} doesn't have a character sheet.")
            return

        inv = _get_inventory_for_character(char)
        armor, inst = _find_armor_in_inventory(inv, item_name)
        if not armor:
            self.caller.msg(f"{char.key} doesn't have armor named '{item_name}'.")
            return

        base_sp = inst.original_sp if inst.original_sp is not None else armor.sp
        inst.current_sp = base_sp
        inst.juryrigged = False
        inst.save()

        self.caller.msg(f"|g{armor.name} repaired for {char.key}. SP reset to {base_sp}.|n")
        char.msg(f"Your {armor.name} has been repaired. SP is now {base_sp}.")


class CmdJuryrig(MuxCommand):
    """
    Tech role: jury-rig equipment for temporary repair.

    Usage:
      juryrig <name>=<item>   - Jury-rig item (Tech only, at DV you specify or default)
      juryrig/off <name>=<item> - Turn off juryrig (Tech or staff)

    Jury-rigging temporarily restores SP to normal. Shows as (juryrigged) on inventory.
    """

    key = "juryrig"
    help_category = "Inventory"

    def _is_tech(self, char):
        role = getattr(char.db, "role", None) or (
            getattr(char.character_sheet, "role", None) if hasattr(char, "character_sheet") and char.character_sheet else None
        )
        return (role or "").strip().lower() == "tech"

    def _is_staff(self):
        return hasattr(self.caller, "check_permstring") and (
            self.caller.check_permstring("builders") or self.caller.check_permstring("wizards")
        )

    def func(self):
        if "off" in self.switches:
            self._juryrig_off()
            return

        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: juryrig <character>=<item>\n"
                "  Temporarily restores armor SP. Tech role only.\n"
                "  Staff/Tech can turn off with: juryrig/off <name>=<item>"
            )
            return

        if not self._is_tech(self.caller):
            self.caller.msg("Only characters with the Tech role can juryrig.")
            return

        char_name, item_name = self.args.split("=", 1)
        char_name = char_name.strip()
        item_name = item_name.strip()

        char = self.caller.search(char_name, global_search=True)
        if not char:
            return
        if char != self.caller and not self._is_staff():
            self.caller.msg("You can only juryrig your own equipment.")
            return

        inv = _get_inventory_for_character(char)
        armor, inst = _find_armor_in_inventory(inv, item_name)
        if not armor:
            self.caller.msg(f"No armor named '{item_name}' found for {char.key}.")
            return

        base_sp = inst.original_sp if inst.original_sp is not None else armor.sp
        inst.juryrigged = True
        if inst.original_sp is None:
            inst.original_sp = armor.sp
        inst.save()

        eff = inst.get_effective_sp()
        self.caller.msg(f"|gJuryrigged {armor.name} for {char.key}. SP temporarily {eff}.|n")
        if char != self.caller:
            char.msg(f"Your {armor.name} has been juryrigged. SP is temporarily {eff}.")

    def _juryrig_off(self):
        """Turn off juryrig - Tech or staff."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: juryrig/off <character>=<item>")
            return

        char_name, item_name = self.args.split("=", 1)
        char_name = char_name.strip()
        item_name = item_name.strip()

        char = self.caller.search(char_name, global_search=True)
        if not char:
            return

        if not self._is_tech(self.caller) and not self._is_staff():
            self.caller.msg("Only Tech or staff can turn off juryrig.")
            return
        if char != self.caller and not self._is_staff():
            self.caller.msg("Only staff can turn off juryrig for another character.")
            return

        inv = _get_inventory_for_character(char)
        armor, inst = _find_armor_in_inventory(inv, item_name)
        if not armor:
            self.caller.msg(f"No armor named '{item_name}' found for {char.key}.")
            return

        if not inst.juryrigged:
            self.caller.msg(f"{armor.name} is not juryrigged.")
            return

        inst.juryrigged = False
        inst.save()

        self.caller.msg(f"|yJuryrig turned off for {armor.name} ({char.key}).|n")
        if char != self.caller:
            char.msg(f"The juryrig on your {armor.name} has been turned off.")


_IMPLANT_KEY_ALIASES = {
    "skin_weave": "skin_weave",
    "skin weave": "skin_weave",
    "subdermal": "subdermal_armor",
    "subdermal_armor": "subdermal_armor",
    "subdermal armor": "subdermal_armor",
    "sycust": "sycust_fleshweave",
    "sycust_fleshweave": "sycust_fleshweave",
    "sycust fleshweave": "sycust_fleshweave",
}


class CmdArmorStaff(MuxCommand):
    """
    Staff: set armor SP for a character (worn inventory armor or implanted layers).

    Usage:
      +armor/staff <character>=<armor name>, sp=<number>
      +armor/staff <character>=<armor name>, sp=full
      +armor/staff <character>=subdermal, sp=11
      +armor/staff <character>=skin_weave, sp=7

    Implanted keys: skin_weave, subdermal_armor, sycust_fleshweave (aliases: subdermal, sycust, ...)
    """

    key = "+armor"
    help_category = "Admin"

    def func(self):
        if "staff" not in self.switches:
            self.caller.msg("Usage: +armor/staff <char>=<armor or implant key>, sp=<n|full>")
            return
        if not (
            hasattr(self.caller, "check_permstring")
            and (self.caller.check_permstring("builders") or self.caller.check_permstring("wizards"))
        ):
            self.caller.msg("Only staff can use +armor/staff.")
            return
        raw = (self.args or "").strip()
        m = re.match(
            r"^\s*(.+?)\s*=\s*(.+?),\s*sp\s*=\s*(.+)\s*$",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            self.caller.msg("Usage: +armor/staff <char>=<armor name or implant>, sp=<number|full>")
            return
        char_name = m.group(1).strip()
        ident = m.group(2).strip()
        sp_raw = m.group(3).strip().lower()

        char = self.caller.search(char_name, global_search=True)
        if not char:
            return
        if not hasattr(char, "character_sheet") or not char.character_sheet:
            self.caller.msg(f"{char.key} has no character sheet.")
            return
        sheet = char.character_sheet

        if sp_raw == "full":
            sp_val = None
        else:
            try:
                sp_val = int(sp_raw)
            except ValueError:
                self.caller.msg("sp= must be an integer or 'full'.")
                return

        ident_l = ident.lower()
        implant_key = _IMPLANT_KEY_ALIASES.get(ident_l)
        if implant_key:
            from world.cyberware.implanted_armor import ensure_implanted_armor_for_sheet

            ensure_implanted_armor_for_sheet(sheet)
            ok, msg = staff_set_implanted_sp(sheet, implant_key, sp_val)
            if ok:
                self.caller.msg(f"|g{char.key}:|n {msg}")
                if char != self.caller:
                    char.msg(f"Staff adjusted your implanted {implant_key} armor: {msg}")
            else:
                self.caller.msg(f"|r{msg}|n")
            return

        inv = _get_inventory_for_character(char)
        armor, inst = _find_armor_in_inventory(inv, ident)
        if not armor:
            self.caller.msg(f"No armor or implant key matching '{ident}'.")
            return
        base = inst.original_sp if inst.original_sp is not None else armor.sp
        if sp_val is None:
            new_sp = base
        else:
            new_sp = max(0, min(int(sp_val), int(base)))
        inst.current_sp = new_sp
        if inst.original_sp is None:
            inst.original_sp = base
        inst.save()
        self.caller.msg(f"|g{char.key}|n - {armor.name} SP set to {new_sp} (max {base}).")
        if char != self.caller:
            char.msg(f"Staff set your {armor.name} SP to {new_sp}.")
