"""
Health command - Display HP, wound state, death save, injuries, armor, and healing skills.

health [character] - Show your health (or staff: another character's health)
"""

from evennia.commands.default.muxcommand import MuxCommand
from world.utils.character_utils import get_character_sheet, get_staff_target_character
from world.utils.formatting import sheet_header, sheet_section, footer
from world.wound_utils import (
    get_current_hp,
    get_max_hp,
    get_wound_state,
    get_death_save_penalty,
    is_dead,
)
from world.wound_data import (
    WOUND_SLIGHTLY,
    WOUND_SERIOUSLY,
    WOUND_MORTALLY,
    WOUND_DEAD,
    get_injury_data_by_name,
    INJURY_EFFECT_DESCRIPTIONS,
)
from world.inventory.models import InventoryArmor
import time


def _get_sheet(char):
    if not char:
        return None
    return getattr(char, "character_sheet", None)


def _get_first_aid(char):
    sheet = _get_sheet(char)
    if sheet:
        return getattr(sheet, "first_aid", 0) or 0
    db = getattr(char, "db", None)
    skills = getattr(db, "skills", None) or {} if db else {}
    return skills.get("first_aid", 0) or 0


def _get_paramedic(char):
    sheet = _get_sheet(char)
    if sheet:
        return getattr(sheet, "paramedic", 0) or 0
    db = getattr(char, "db", None)
    skills = getattr(db, "skills", None) or {} if db else {}
    return skills.get("paramedic", 0) or 0


def _get_surgery(char):
    if hasattr(char, "get_skill"):
        return char.get_skill("surgery") or 0
    db = getattr(char, "db", None)
    skills = getattr(db, "skills", None) or {} if db else {}
    return skills.get("surgery", 0) or 0


def _is_injury_quick_fixed(sheet, injury_name):
    fixes = getattr(sheet, "critical_injury_quick_fixes", {}) or {}
    expiry = fixes.get(injury_name, 0)
    return expiry > 0 and time.time() < expiry


class CmdHealth(MuxCommand):
    """
    Display health status: HP, wound state, death save, injuries, armor, healing skills.

    Usage:
      health              - Show your health
      health <character>   - Staff: show another character's health
    """

    key = "health"
    aliases = ["hp", "wounds"]
    lock = "cmd:all()"
    help_category = "Combat"

    def func(self):
        raw = (self.args or "").strip()

        # Staff can view another: health <name>
        if raw:
            from world.utils.character_utils import is_staff
            target_char, character_sheet = get_staff_target_character(
                self.caller, raw, quiet=True
            )
            if target_char is not None and character_sheet is not None:
                self._show_health(character_sheet, target_char)
                return
            if is_staff(self.caller):
                self.caller.msg(f"No character named '{raw}' found.")
            else:
                self.caller.msg("You don't have permission to view other characters' health.")
            return

        character_sheet = get_character_sheet(self.caller)
        if not character_sheet:
            self.caller.msg("You don't have a character sheet. Please create one using the 'chargen' command.")
            return

        self._show_health(character_sheet, self.caller)

    def _show_health(self, sheet, char):
        """Build and display the health sheet."""
        W = 80
        display_name = getattr(sheet, "full_name", None) or char.key

        output = sheet_header(f"Health for {display_name}", width=W)
        output += sheet_section("Vitals", width=W)

        current_hp = get_current_hp(char)
        max_hp = get_max_hp(char)
        state = get_wound_state(char)
        dead = is_dead(char)

        # HP
        hp_str = f"{current_hp}/{max_hp}"
        if dead:
            hp_str += " |r(DEAD)|n"
        elif state == WOUND_MORTALLY:
            hp_str += " |r(Mortally Wounded)|n"
        elif state == WOUND_SERIOUSLY:
            hp_str += " |y(Seriously Wounded)|n"
        elif state == WOUND_SLIGHTLY:
            hp_str += " |y(Lightly Wounded)|n"
        output += f"  |yHP:|n {hp_str}\n"

        # Wound state
        state_names = {
            None: "Unwounded",
            WOUND_SLIGHTLY: "Lightly Wounded",
            WOUND_SERIOUSLY: "Seriously Wounded",
            WOUND_MORTALLY: "Mortally Wounded",
            WOUND_DEAD: "Dead",
        }
        state_str = state_names.get(state, "Unknown")
        output += f"  |yWound State:|n {state_str}\n"

        # Death save (BODY target)
        death_save = getattr(sheet, "death_save", 0) or getattr(char.db, "death_save", 0) or 0
        output += f"  |yDeath Save (BODY):|n {death_save}\n"

        # Death save penalties
        penalty = get_death_save_penalty(char)
        base_penalty = getattr(sheet, "base_death_save_penalty", 0) or 0
        output += f"  |yDeath Save Penalty:|n {penalty}"
        if base_penalty > 0:
            output += f" (base: {base_penalty})"
        output += "\n"

        # Injuries
        output += sheet_section("Injuries", width=W)
        injuries = list(getattr(sheet, "critical_injuries", []) or [])
        if not injuries:
            output += "  None\n"
        else:
            for name in injuries:
                data, _ = get_injury_data_by_name(name)
                effect_key = (data or {}).get("effect", "none")
                desc = INJURY_EFFECT_DESCRIPTIONS.get(effect_key, effect_key)
                qf = " |g(quick-fixed)|n" if _is_injury_quick_fixed(sheet, name) else ""
                output += f"  • {name}{qf}\n"
                output += f"    {desc}\n"

        # Armor
        output += sheet_section("Armor", width=W)
        eqarmor = getattr(sheet, "eqarmor", None)
        if not eqarmor:
            output += "  None equipped\n"
        else:
            inv = getattr(sheet, "inventory", None)
            current_sp = eqarmor.sp
            max_sp = eqarmor.sp
            if inv:
                try:
                    inst = InventoryArmor.objects.filter(
                        inventory=inv, armor=eqarmor
                    ).first()
                    if inst:
                        current_sp = inst.get_effective_sp()
                        max_sp = inst.original_sp if inst.original_sp is not None else eqarmor.sp
                except Exception:
                    pass
            output += f"  {eqarmor.name}: SP {current_sp}/{max_sp}\n"

        # Healing skills
        output += sheet_section("Healing Skills", width=W)
        first_aid = _get_first_aid(char)
        paramedic = _get_paramedic(char)
        surgery = _get_surgery(char)
        output += f"  |yFirst Aid:|n {first_aid}\n"
        output += f"  |yParamedic:|n {paramedic}\n"
        output += f"  |ySurgery:|n {surgery}\n"

        output += footer(width=W, fillchar="-")
        self.caller.msg(output)
