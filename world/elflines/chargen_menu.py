"""
Elflines Online EvMenu character generation flow.
Steps: stats (50 pts, 3-8 each) -> skills (60 pts, max 6 each) -> elfname -> equipment (200gp)
"""

from evennia.utils import evmenu
from evennia.utils.evmenu import EvMenu

from .models import ElflineSheet
from .services import get_or_create_elfline_sheet
from .elflines_data import (
    ELO_STATS,
    ELO_SKILLS,
    ELO_ARMORY,
    ELO_STAT_POINTS,
    ELO_SKILL_POINTS,
    ELO_STAT_MIN,
    ELO_STAT_MAX_START,
    ELO_SKILL_MAX_START,
    ELO_STARTING_GP,
)


def _get_sheet(caller):
    return get_or_create_elfline_sheet(caller)


def _stat_spent(sheet):
    return sum(getattr(sheet, s) for s in ELO_STATS)


def _skill_spent(sheet):
    skills = sheet.skills or {}
    total = 0
    for sk, _, dbl in ELO_SKILLS:
        val = skills.get(sk, 0)
        total += val * (2 if dbl else 1)
    return total


def node_start(caller, raw_string, **kwargs):
    sheet = _get_sheet(caller)
    if sheet.is_complete:
        text = (
            f"|wElflines Online Character|n\n"
            f"Your ELO character |c{sheet.elfname}|n is complete.\n"
            f"Rank {sheet.rank} | gp: {sheet.gp} | HP: {sheet.current_hp}/{sheet.max_hp}\n\n"
            f"Use |w+elo/sheet|n to view, or |w+elo|n for status."
        )
        options = None
    else:
        spent_stat = _stat_spent(sheet)
        spent_skill = _skill_spent(sheet)
        text = (
            f"|wElflines Online Character Generation|n\n"
            f"Create your elf: 50 STAT points (3-8 each), 60 skill points (max 6 per skill), elfname, 200gp equipment.\n\n"
            f"Current: STATs {spent_stat}/{ELO_STAT_POINTS} | Skills {spent_skill}/{ELO_SKILL_POINTS} | Elfname: {sheet.elfname or 'Not set'}\n\n"
            f"Choose a step:"
        )
        options = (
            {"key": "stats", "desc": "Allocate STAT points (50 total, 3-8 each)", "goto": "node_stats"},
            {"key": "skills", "desc": "Allocate skill points (60 total, max 6 each)", "goto": "node_skills"},
            {"key": "elfname", "desc": "Set your elfname", "goto": "node_elfname"},
            {"key": "equipment", "desc": "Pick equipment (200gp budget)", "goto": "node_equipment"},
            {"key": "finish", "desc": "Finish and lock sheet (when complete)", "goto": "node_finish"},
        )
    return text, options


def _process_stat_input(caller, raw_string, **kwargs):
    if raw_string.strip().lower() in ("b", "back", "q"):
        return "node_start"
    sheet = _get_sheet(caller)
    spent = _stat_spent(sheet)
    if "=" in raw_string:
        parts = raw_string.strip().split("=", 1)
        if len(parts) == 2:
            stat_key = parts[0].strip().lower().replace(" ", "_")
            try:
                val = int(parts[1].strip())
            except ValueError:
                caller.msg("|rInvalid number.|n")
                return "node_stats"
            if stat_key in ELO_STATS:
                if ELO_STAT_MIN <= val <= ELO_STAT_MAX_START:
                    old_val = getattr(sheet, stat_key)
                    delta = val - old_val
                    if spent + delta <= ELO_STAT_POINTS:
                        setattr(sheet, stat_key, val)
                        sheet.save()
                        caller.msg(f"|gSet {stat_key} to {val}.|n")
                    else:
                        caller.msg(f"|rThat would exceed your STAT budget.|n")
                else:
                    caller.msg(f"|rValue must be between {ELO_STAT_MIN} and {ELO_STAT_MAX_START} at creation.|n")
            else:
                caller.msg(f"|rUnknown stat. Options: {', '.join(ELO_STATS)}|n")
        return "node_stats"
    return "node_stats"


def node_stats(caller, raw_string, **kwargs):
    sheet = _get_sheet(caller)
    spent = _stat_spent(sheet)
    remaining = ELO_STAT_POINTS - spent
    lines = [f"|wSTAT Allocation|n ({ELO_STAT_POINTS} pts total, 3-8 per stat)\n"]
    for s in ELO_STATS:
        val = getattr(sheet, s)
        lines.append(f"  {s.capitalize()}: {val}")
    lines.append(f"\nSpent: {spent} | Remaining: {remaining}")
    lines.append("\nEnter |wstat=value|n (e.g. reflexes=6) or |wb|n to go back.")
    text = "\n".join(lines)
    options = (
        {"key": "_default", "desc": "Enter stat=value", "goto": _process_stat_input},
        {"key": "b", "desc": "Back to menu", "goto": "node_start"},
    )
    return text, options


def _process_skill_input(caller, raw_string, **kwargs):
    if raw_string.strip().lower() in ("b", "back", "q"):
        return "node_start"
    sheet = _get_sheet(caller)
    skills = sheet.skills or {}
    spent = _skill_spent(sheet)
    if "=" in raw_string:
        parts = raw_string.strip().split("=", 1)
        if len(parts) == 2:
            skill_key = parts[0].strip().lower().replace(" ", "_").replace("/", "_")
            try:
                val = int(parts[1].strip())
            except ValueError:
                caller.msg("|rInvalid number.|n")
                return "node_skills"
            sk_lookup = {s[0]: s for s in ELO_SKILLS}
            if skill_key in sk_lookup:
                sk, stat, dbl = sk_lookup[skill_key]
                if 0 <= val <= ELO_SKILL_MAX_START:
                    old_val = skills.get(sk, 0)
                    cost_per = 2 if dbl else 1
                    delta_cost = (val - old_val) * cost_per
                    if spent + delta_cost <= ELO_SKILL_POINTS:
                        skills[sk] = val
                        sheet.skills = dict(skills)
                        sheet.save()
                        caller.msg(f"|gSet {sk} to {val}.|n")
                    else:
                        caller.msg(f"|rNot enough skill points.|n")
                else:
                    caller.msg(f"|rValue must be 0-{ELO_SKILL_MAX_START} at creation.|n")
            else:
                caller.msg(f"|rUnknown skill. Use exact key (e.g. archery, melee_weapon).|n")
        return "node_skills"
    return "node_skills"


def node_skills(caller, raw_string, **kwargs):
    sheet = _get_sheet(caller)
    skills = sheet.skills or {}
    spent = _skill_spent(sheet)
    remaining = ELO_SKILL_POINTS - spent
    lines = [f"|wSkill Allocation|n ({ELO_SKILL_POINTS} pts, max 6 per skill, x2 skills cost double)\n"]
    for sk, stat, dbl in ELO_SKILLS:
        val = skills.get(sk, 0)
        cost_str = "x2" if dbl else ""
        lines.append(f"  {sk}: {val} {cost_str}")
    lines.append(f"\nSpent: {spent} | Remaining: {remaining}")
    lines.append("\nEnter |wskill=value|n (e.g. archery=4) or |wb|n to go back.")
    text = "\n".join(lines)
    options = (
        {"key": "_default", "desc": "Enter skill=value", "goto": _process_skill_input},
        {"key": "b", "desc": "Back to menu", "goto": "node_start"},
    )
    return text, options


def _process_elfname_input(caller, raw_string, **kwargs):
    if raw_string.strip().lower() in ("b", "back", "q", "skip"):
        return "node_start"
    sheet = _get_sheet(caller)
    name = raw_string.strip()[:80]
    if name:
        sheet.elfname = name
        sheet.save()
        caller.msg(f"|gElfname set to: {name}|n")
    return "node_start"


def node_elfname(caller, raw_string, **kwargs):
    sheet = _get_sheet(caller)
    text = (
        f"|wSet Elfname|n\n"
        f"Current: {sheet.elfname or '(not set)'}\n\n"
        f"Enter your elf's name (e.g. Daeric Sylar):"
    )
    options = (
        {"key": "_default", "desc": "Enter name", "goto": _process_elfname_input},
        {"key": "b", "desc": "Skip for now", "goto": "node_start"},
    )
    return text, options


def _process_equipment_input(caller, raw_string, **kwargs):
    if raw_string.strip().lower() in ("b", "back", "q"):
        return "node_start"
    sheet = _get_sheet(caller)
    gp_left = sheet.gp
    inv = list(sheet.inventory or [])
    args = raw_string.strip().split()
    if len(args) >= 2:
        cmd = args[0].lower()
        key = args[1].lower().replace(" ", "_")
        armory_map = {a[0]: a for a in ELO_ARMORY}
        if key in armory_map:
            _, name, cost, _ = armory_map[key]
            if cmd == "buy":
                if gp_left >= cost:
                    inv.append(key)
                    sheet.inventory = inv
                    sheet.gp -= cost
                    sheet.save()
                    caller.msg(f"|gBought {name} for {cost}gp.|n")
                else:
                    caller.msg(f"|rNot enough gp. Need {cost}, have {gp_left}.|n")
            elif cmd == "remove":
                if key in inv:
                    inv.remove(key)
                    sheet.inventory = inv
                    sheet.gp += cost
                    sheet.save()
                    caller.msg(f"|gRemoved {name}. Refunded {cost}gp.|n")
                else:
                    caller.msg(f"|rYou don't have {key}.|n")
        else:
            caller.msg(f"|rUnknown item. Use |w+elo/armory|n for list.|n")
    elif args and args[0].lower() not in ("b", "back"):
        caller.msg("|rUse |wbuy <key>|n or |wremove <key>|n (e.g. buy bow)|n")
    return "node_equipment"


def node_equipment(caller, raw_string, **kwargs):
    sheet = _get_sheet(caller)
    inv = sheet.inventory or []
    gp_left = sheet.gp
    lines = [f"|wEquipment|n (200gp budget)\n"]
    lines.append("Available:")
    for key, name, gp, _ in ELO_ARMORY:
        lines.append(f"  |w{key}|n - {name} ({gp}gp)")
    lines.append(f"\nYour inventory: {', '.join(inv) or 'Empty'}")
    lines.append(f"gp remaining: {gp_left}")
    lines.append("\nEnter |wbuy <key>|n or |wremove <key>|n or |wb|n to go back.")
    text = "\n".join(lines)
    options = (
        {"key": "_default", "desc": "Enter buy/remove command", "goto": _process_equipment_input},
        {"key": "b", "desc": "Back to menu", "goto": "node_start"},
    )
    return text, options


def node_finish(caller, raw_string, **kwargs):
    sheet = _get_sheet(caller)
    stat_ok = _stat_spent(sheet) == ELO_STAT_POINTS
    skill_ok = _skill_spent(sheet) == ELO_SKILL_POINTS
    name_ok = bool(sheet.elfname and sheet.elfname.strip())

    if not stat_ok or not skill_ok or not name_ok:
        issues = []
        if not stat_ok:
            issues.append(f"STATs: need exactly {ELO_STAT_POINTS} (have {_stat_spent(sheet)})")
        if not skill_ok:
            issues.append(f"Skills: need exactly {ELO_SKILL_POINTS} (have {_skill_spent(sheet)})")
        if not name_ok:
            issues.append("Elfname not set")
        text = (
            f"|rCannot finish yet.|n\n"
            f"Issues: {'; '.join(issues)}\n\n"
            f"Equipment is optional. Go back to fix."
        )
        options = ({"key": "back", "desc": "Back", "goto": "node_start"},)
        return text, options

    sheet.is_complete = True
    sheet.save()
    caller.msg(f"|gElflines character |c{sheet.elfname}|n complete! Use +elo/sheet to view, +elo/login to enter the Elflands.|n")
    return None, None  # Exit menu


def start_elo_chargen(caller):
    """Launch the ELO chargen EvMenu."""
    EvMenu(caller, "world.elflines.chargen_menu", startnode="node_start", persistent=False)
