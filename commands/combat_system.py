"""Scene-local combat tracker with ephemeral mooks and initiative roster."""

from __future__ import annotations

import random
import re
from typing import Dict, List, Optional, Tuple

from evennia.commands.default.muxcommand import MuxCommand

from world.utils.character_utils import is_character_approved
from world.utils.formatting import sheet_header, sheet_section, footer

COMBAT_STATE_ATTR = "combat_state"
PROFILE_ALIASES = {
    "ncpd": "ncpd beat cop",
    "cop": "ncpd beat cop",
    "medic": "combat medic",
    "corpsec": "corporate security",
}
LEVEL_ALIASES = {
    "mook": "mook",
    "basic": "mook",
    "base": "mook",
    "lieutenant": "lieutenant",
    "lt": "lieutenant",
    "mini-boss": "mini-boss",
    "miniboss": "mini-boss",
    "mini": "mini-boss",
}
MOOK_LEVEL_MODS: Dict[str, Dict] = {
    "mook": {"stat_bonus": 0, "skill_bonus": 0, "hp_mult": 1.0, "hp_flat": 0, "armor_bonus": 0, "damage_dice_bonus": 0, "initiative_bonus": 0},
    "lieutenant": {"stat_bonus": 1, "skill_bonus": 2, "hp_mult": 1.35, "hp_flat": 3, "armor_bonus": 2, "damage_dice_bonus": 1, "initiative_bonus": 1},
    "mini-boss": {"stat_bonus": 2, "skill_bonus": 4, "hp_mult": 1.75, "hp_flat": 8, "armor_bonus": 4, "damage_dice_bonus": 2, "initiative_bonus": 2},
}
# Screenshot-inspired named archetypes that map to base profile + default level.
NAMED_ARCHETYPES: Dict[str, Tuple[str, str]] = {
    "netrunner": ("hacker", "lieutenant"),
    "reclaimer chief": ("gang member", "lieutenant"),
    "security officer": ("corporate security", "lieutenant"),
    "outrider": ("combat gunner", "mini-boss"),
    "pyro": ("grenadier", "mini-boss"),
    "cyberpsycho": ("martial artist", "mini-boss"),
    "road ganger": ("gang member", "mook"),
    "security operative": ("security guard", "mook"),
    "bodyguard": ("security guard", "mook"),
    "booster ganger": ("punk", "mook"),
}
ENCOUNTER_PRESETS: Dict[str, Dict] = {
    "street-ambush": {
        "description": "Street punks and gangers with occasional lieutenant support.",
        "mook_pool": ["punk", "booster ganger", "road ganger", "gang member"],
        "lieutenant_pool": ["reclaimer chief", "security officer"],
        "boss_pool": ["cyberpsycho"],
        "mook_mult": 2.0,
        "mook_min": 2,
        "lt_ratio": 2,   # 1 per 2 PCs
        "boss_ratio": 0, # none by default
    },
    "corp-response": {
        "description": "Corporate/security response team with tactical escalation.",
        "mook_pool": ["security operative", "bodyguard", "security guard"],
        "lieutenant_pool": ["security officer", "netrunner"],
        "boss_pool": ["outrider"],
        "mook_mult": 1.5,
        "mook_min": 2,
        "lt_ratio": 2,
        "boss_ratio": 4,  # 1 per 4 PCs
    },
    "gang-raid": {
        "description": "Large gang push with heavier mook counts and leaders.",
        "mook_pool": ["booster ganger", "road ganger", "gang member", "punk"],
        "lieutenant_pool": ["reclaimer chief"],
        "boss_pool": ["pyro"],
        "mook_mult": 2.5,
        "mook_min": 3,
        "lt_ratio": 2,
        "boss_ratio": 5,
    },
    "kill-team": {
        "description": "Mil-spec assault group with strong officer support.",
        "mook_pool": ["militech soldier", "combat gunner", "security operative"],
        "lieutenant_pool": ["security officer", "netrunner"],
        "boss_pool": ["outrider", "cyberpsycho"],
        "mook_mult": 1.25,
        "mook_min": 2,
        "lt_ratio": 2,
        "boss_ratio": 3,  # 1 per 3 PCs
    },
}

MOOK_PROFILES: Dict[str, Dict] = {
    "melee": {"stats": {"reflexes": 5, "dexterity": 6, "body": 6, "willpower": 5, "move": 6}, "skills": {"melee": 6, "evasion": 5, "brawling": 4, "athletics": 4}, "weapon": ("Heavy Melee Weapon", "3d6"), "armor": ("Leathers", 4, 0)},
    "ranged": {"stats": {"reflexes": 6, "dexterity": 5, "body": 5, "willpower": 5, "move": 5}, "skills": {"handgun": 6, "shoulder_arms": 5, "evasion": 4, "concentration": 4}, "weapon": ("Heavy Pistol", "3d6"), "armor": ("Kevlar Vest", 7, 0)},
    "tank": {"stats": {"reflexes": 4, "dexterity": 4, "body": 8, "willpower": 7, "move": 4}, "skills": {"heavy_weapons": 5, "shoulder_arms": 5, "evasion": 3, "brawling": 5}, "weapon": ("Shotgun", "5d6"), "armor": ("Heavy Armorjack", 13, -2)},
    "martial artist": {"stats": {"reflexes": 7, "dexterity": 8, "body": 6, "willpower": 6, "move": 7}, "skills": {"martial_arts": 7, "evasion": 7, "brawling": 6, "athletics": 5}, "weapon": ("Unarmed", "3d6"), "armor": ("Street Gi", 4, 0)},
    "gang member": {"stats": {"reflexes": 5, "dexterity": 5, "body": 5, "willpower": 4, "move": 5}, "skills": {"handgun": 5, "melee": 5, "evasion": 4, "brawling": 4}, "weapon": ("Medium Pistol", "2d6"), "armor": ("Leathers", 4, 0)},
    "bareknuckle boxer": {"stats": {"reflexes": 6, "dexterity": 7, "body": 7, "willpower": 6, "move": 6}, "skills": {"brawling": 8, "evasion": 6, "athletics": 5, "concentration": 5}, "weapon": ("Fists", "3d6"), "armor": ("None", 0, 0)},
    "security guard": {"stats": {"reflexes": 5, "dexterity": 5, "body": 6, "willpower": 5, "move": 5}, "skills": {"handgun": 5, "shoulder_arms": 4, "evasion": 4, "concentration": 4}, "weapon": ("Heavy Pistol", "3d6"), "armor": ("Kevlar Vest", 7, 0)},
    "corporate security": {"stats": {"reflexes": 6, "dexterity": 6, "body": 6, "willpower": 6, "move": 5}, "skills": {"handgun": 6, "shoulder_arms": 6, "evasion": 5, "concentration": 5}, "weapon": ("Assault Rifle", "5d6"), "armor": ("Armorjack", 11, -2)},
    "ncpd beat cop": {"stats": {"reflexes": 6, "dexterity": 5, "body": 6, "willpower": 6, "move": 5}, "skills": {"handgun": 6, "shoulder_arms": 5, "evasion": 5, "human_perception": 4}, "weapon": ("Very Heavy Pistol", "4d6"), "armor": ("Armorjack", 11, -2)},
    "combat medic": {"stats": {"reflexes": 5, "dexterity": 6, "body": 5, "willpower": 6, "move": 5}, "skills": {"handgun": 5, "evasion": 5, "first_aid": 7, "paramedic": 6}, "weapon": ("Heavy Pistol", "3d6"), "armor": ("Kevlar Vest", 7, 0)},
    "paramedic": {"stats": {"reflexes": 4, "dexterity": 6, "body": 4, "willpower": 6, "move": 5}, "skills": {"handgun": 4, "evasion": 4, "first_aid": 7, "paramedic": 7}, "weapon": ("Medium Pistol", "2d6"), "armor": ("Light Vest", 4, 0)},
    "doctor": {"stats": {"reflexes": 4, "dexterity": 5, "body": 4, "willpower": 6, "move": 5}, "skills": {"handgun": 4, "first_aid": 6, "paramedic": 6, "concentration": 6}, "weapon": ("Holdout Pistol", "2d6"), "armor": ("Medical Coat", 0, 0)},
    "engineer": {"stats": {"reflexes": 4, "dexterity": 5, "body": 5, "willpower": 5, "move": 5}, "skills": {"handgun": 4, "evasion": 4, "basic_tech": 7, "demolitions": 5}, "weapon": ("Heavy Pistol", "3d6"), "armor": ("Work Vest", 4, 0)},
    "grenadier": {"stats": {"reflexes": 6, "dexterity": 5, "body": 6, "willpower": 6, "move": 5}, "skills": {"heavy_weapons": 6, "shoulder_arms": 5, "evasion": 4, "demolitions": 6}, "weapon": ("Grenade Launcher", "6d6"), "armor": ("Armorjack", 11, -2)},
    "sapper": {"stats": {"reflexes": 5, "dexterity": 5, "body": 6, "willpower": 6, "move": 5}, "skills": {"heavy_weapons": 5, "demolitions": 7, "evasion": 4, "basic_tech": 6}, "weapon": ("Shotgun", "5d6"), "armor": ("Armorjack", 11, -2)},
    "hacker": {"stats": {"reflexes": 4, "dexterity": 5, "body": 4, "willpower": 6, "move": 5}, "skills": {"handgun": 4, "evasion": 4, "interface": 6, "electronics_security_tech": 7}, "weapon": ("SMG", "2d6"), "armor": ("Light Jacket", 4, 0)},
    "punk": {"stats": {"reflexes": 5, "dexterity": 5, "body": 5, "willpower": 4, "move": 6}, "skills": {"handgun": 4, "melee": 5, "brawling": 4, "evasion": 4}, "weapon": ("Medium Melee Weapon", "2d6"), "armor": ("Leathers", 4, 0)},
    "getaway driver": {"stats": {"reflexes": 6, "dexterity": 5, "body": 5, "willpower": 5, "move": 7}, "skills": {"handgun": 4, "evasion": 4, "drive_land": 8, "concentration": 5}, "weapon": ("SMG", "2d6"), "armor": ("Light Vest", 4, 0)},
    "combat gunner": {"stats": {"reflexes": 7, "dexterity": 6, "body": 6, "willpower": 6, "move": 5}, "skills": {"heavy_weapons": 7, "shoulder_arms": 6, "evasion": 5, "autofire": 6}, "weapon": ("LMG", "5d6"), "armor": ("Heavy Armorjack", 13, -2)},
    "militech soldier": {"stats": {"reflexes": 7, "dexterity": 6, "body": 7, "willpower": 7, "move": 6}, "skills": {"shoulder_arms": 7, "autofire": 6, "evasion": 6, "athletics": 6}, "weapon": ("Assault Rifle", "5d6"), "armor": ("Heavy Armorjack", 13, -2)},
    "arasaka ninja": {"stats": {"reflexes": 8, "dexterity": 8, "body": 6, "willpower": 7, "move": 8}, "skills": {"martial_arts": 8, "melee": 8, "evasion": 8, "stealth": 7}, "weapon": ("Mono Katana", "4d6"), "armor": ("Bodyweave", 7, 0)},
}

# Lawman Backup spawning presets mapped onto temporary mook profiles.
BACKUP_COMPOSITIONS: Dict[int, List[Tuple[str, str, int]]] = {
    1: [("security guard", "mook", 4)],
    2: [("security guard", "mook", 4)],
    3: [("ncpd beat cop", "mook", 4)],
    4: [("ncpd beat cop", "mook", 4)],
    5: [("ncpd beat cop", "lieutenant", 2)],
    6: [("ncpd beat cop", "lieutenant", 2)],
    7: [("ncpd beat cop", "lieutenant", 2)],
    8: [("militech soldier", "mini-boss", 1)],
    9: [("combat gunner", "mini-boss", 2)],
    10: [("militech soldier", "lieutenant", 2)],
}


def _ensure_turn_state(scene: Dict):
    if not isinstance(scene.get("turn_state"), dict):
        scene["turn_state"] = {}


def _get_turn_state(scene: Dict, entry_id: str) -> Dict:
    _ensure_turn_state(scene)
    key = str(entry_id or "")
    state = scene["turn_state"].get(key)
    if not isinstance(state, dict):
        state = {"action_used": False, "move_used": False, "run_used": False}
        scene["turn_state"][key] = state
    return state


def _reset_turn_state_for_entry(scene: Dict, entry_id: str):
    _ensure_turn_state(scene)
    scene["turn_state"][str(entry_id or "")] = {
        "action_used": False,
        "move_used": False,
        "run_used": False,
    }


def _resolve_entry_by_id(scene: Dict, entry_id: str) -> Optional[Dict]:
    eid = str(entry_id or "")
    for e in scene.get("roster", []):
        if str(e.get("id", "")) == eid:
            return e
    return None


def _entry_for_character(scene: Dict, character) -> Optional[Dict]:
    if not scene or not character:
        return None
    for e in scene.get("roster", []):
        if e.get("kind") in ("pc", "npc") and int(e.get("obj_id", 0) or 0) == int(getattr(character, "id", 0) or 0):
            return e
    return None


def get_active_scene(room) -> Optional[Dict]:
    """Public helper for other command modules."""
    if not room:
        return None
    return getattr(room.ndb, COMBAT_STATE_ATTR, None)


def consume_action_for_character(room, character, label: str = "action") -> Tuple[bool, str]:
    """
    Consume current turn Action for character if active combat and it's their turn.
    Returns (ok, message). If no active scene, returns (True, "").
    """
    scene = get_active_scene(room)
    if not scene:
        return True, ""
    entry = _entry_for_character(scene, character)
    if not entry:
        return True, ""
    current = _current_turn_entry(scene)
    if not current or current.get("id") != entry.get("id"):
        cur_name = current.get("name") if current else "(none)"
        return False, f"It is currently {cur_name}'s turn."
    state = _get_turn_state(scene, entry.get("id"))
    if state.get("action_used", False):
        return False, "You have already used your Action this turn."
    state["action_used"] = True
    state["last_action"] = label
    return True, ""


def consume_move_for_character(room, character, label: str = "move") -> Tuple[bool, str]:
    """
    Consume current turn Move Action for character if active combat and it's their turn.
    Returns (ok, message). If no active scene, returns (True, "").
    """
    scene = get_active_scene(room)
    if not scene:
        return True, ""
    entry = _entry_for_character(scene, character)
    if not entry:
        return True, ""
    current = _current_turn_entry(scene)
    if not current or current.get("id") != entry.get("id"):
        cur_name = current.get("name") if current else "(none)"
        return False, f"It is currently {cur_name}'s turn."
    state = _get_turn_state(scene, entry.get("id"))
    if state.get("move_used", False):
        return False, "You have already used your Move Action this turn."
    state["move_used"] = True
    state["last_move"] = label
    return True, ""


def consume_run_for_character(room, character, label: str = "run") -> Tuple[bool, str]:
    """
    Consume Run Action in active combat:
    - requires Move Action already used this turn
    - consumes Action
    """
    scene = get_active_scene(room)
    if not scene:
        return True, ""
    entry = _entry_for_character(scene, character)
    if not entry:
        return True, ""
    current = _current_turn_entry(scene)
    if not current or current.get("id") != entry.get("id"):
        cur_name = current.get("name") if current else "(none)"
        return False, f"It is currently {cur_name}'s turn."
    state = _get_turn_state(scene, entry.get("id"))
    if not state.get("move_used", False):
        return False, "Run requires that you have already used your Move Action this turn."
    if state.get("action_used", False):
        return False, "You have already used your Action this turn."
    state["action_used"] = True
    state["run_used"] = True
    state["last_action"] = label
    return True, ""


def _normalize_team_name(raw: str) -> str:
    """Normalize team labels for consistent roster grouping."""
    team = (raw or "").strip().lower()
    if not team:
        return "neutral"
    return re.sub(r"[^a-z0-9_-]+", "-", team).strip("-") or "neutral"


def _normalize_level_name(raw: str) -> str:
    level = (raw or "").strip().lower()
    return LEVEL_ALIASES.get(level, "mook")


def _clamp_stat(val, low=2, high=10):
    return max(low, min(high, int(val)))


def _roll_d10():
    return random.randint(1, 10)


def _normalize_profile_name(raw: str) -> str:
    key = (raw or "").strip().lower()
    key = PROFILE_ALIASES.get(key, key)
    return key


def _lookup_profile(raw: str) -> Tuple[Optional[str], Optional[Dict]]:
    key = _normalize_profile_name(raw)
    if key in MOOK_PROFILES:
        return key, MOOK_PROFILES[key]
    partial = [k for k in MOOK_PROFILES.keys() if key and key in k]
    if len(partial) == 1:
        k = partial[0]
        return k, MOOK_PROFILES[k]
    return None, None


def _compute_max_hp(body: int, willpower: int) -> int:
    try:
        from world.hp_chart import get_hp_from_chart

        return int(get_hp_from_chart(body, willpower))
    except Exception:
        return int((body * 5) + (willpower * 2))


def _scale_damage_string(damage: str, add_dice: int) -> str:
    if add_dice <= 0:
        return damage
    m = re.match(r"^\s*(\d+)\s*d\s*6\s*$", str(damage or ""), re.IGNORECASE)
    if not m:
        return damage
    return f"{max(1, int(m.group(1)) + add_dice)}d6"


def _apply_level_scaling(stats: Dict[str, int], skills: Dict[str, int], max_hp: int, armor_sp: int, weapon_dmg: str, level: str):
    mods = MOOK_LEVEL_MODS.get(level, MOOK_LEVEL_MODS["mook"])
    stat_bonus = int(mods.get("stat_bonus", 0) or 0)
    skill_bonus = int(mods.get("skill_bonus", 0) or 0)
    for key in list(stats.keys()):
        stats[key] = _clamp_stat(stats[key] + stat_bonus)
    for key in list(skills.keys()):
        skills[key] = max(0, int(skills[key]) + skill_bonus)
    hp_mult = float(mods.get("hp_mult", 1.0) or 1.0)
    hp_flat = int(mods.get("hp_flat", 0) or 0)
    new_hp = max(1, int(round(max_hp * hp_mult)) + hp_flat)
    armor = max(0, int(armor_sp) + int(mods.get("armor_bonus", 0) or 0))
    dmg = _scale_damage_string(weapon_dmg, int(mods.get("damage_dice_bonus", 0) or 0))
    return stats, skills, new_hp, armor, dmg


def _resolve_profile_and_level(raw_profile: str, raw_level: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict], str]:
    """Resolve profile and default/explicit level, including named archetypes."""
    level = _normalize_level_name(raw_level or "mook")
    profile_text = (raw_profile or "").strip().lower()
    if profile_text in NAMED_ARCHETYPES:
        mapped_profile, default_level = NAMED_ARCHETYPES[profile_text]
        if raw_level:
            return mapped_profile, MOOK_PROFILES.get(mapped_profile), level
        return mapped_profile, MOOK_PROFILES.get(mapped_profile), default_level
    key, profile = _lookup_profile(profile_text)
    return key, profile, level


def _normalize_preset_name(raw: str) -> str:
    key = (raw or "").strip().lower()
    key = key.replace("_", "-")
    if key in ENCOUNTER_PRESETS:
        return key
    partial = [p for p in ENCOUNTER_PRESETS.keys() if key and key in p]
    if len(partial) == 1:
        return partial[0]
    return ""


def _count_active_pcs(scene: Dict) -> int:
    return sum(
        1
        for e in scene.get("roster", [])
        if e.get("kind") == "pc" and e.get("active", True) and int(e.get("current_hp", 1)) > 0
    )


def _pick_from_pool(pool: List[str]) -> str:
    if not pool:
        return "gang member"
    return random.choice(pool)


def _randomize_mook_from_profile(profile_key: str, profile: Dict, mook_num: int, level: str = "mook") -> Dict:
    level = _normalize_level_name(level)
    base_stats = profile.get("stats", {})
    base_skills = profile.get("skills", {})
    stats = {}
    for key, base in base_stats.items():
        stats[key] = _clamp_stat(base + random.randint(-1, 1))
    skills = {}
    for key, base in base_skills.items():
        skills[key] = max(0, int(base + random.randint(-1, 1)))
    body = stats.get("body", 5)
    will = stats.get("willpower", 5)
    max_hp = _compute_max_hp(body, will)
    weapon_name, weapon_dmg = profile.get("weapon", ("Unarmed", "2d6"))
    armor_name, armor_sp, armor_ev = profile.get("armor", ("None", 0, 0))
    stats, skills, max_hp, armor_sp, weapon_dmg = _apply_level_scaling(
        stats, skills, max_hp, int(armor_sp), weapon_dmg, level
    )
    level_title = "Mini-Boss" if level == "mini-boss" else level.title()
    display_name = f"{profile_key.title()} {level_title} {mook_num}" if level != "mook" else f"{profile_key.title()} Mook {mook_num}"
    return {
        "id": f"mook-{mook_num}",
        "kind": "mook",
        "name": display_name,
        "profile": profile_key,
        "stats": stats,
        "skills": skills,
        "max_hp": max_hp,
        "current_hp": max_hp,
        "weapon_name": weapon_name,
        "weapon_damage": weapon_dmg,
        "armor_name": armor_name,
        "armor_sp": int(armor_sp),
        "armor_ev": int(armor_ev),
        "init_roll": 0,
        "initiative": 0,
        "active": True,
        "team": "neutral",
        "level": level,
    }


def _living_characters_in_room(room):
    if not room:
        return []
    out = []
    for obj in room.contents:
        if not getattr(obj, "db", None):
            continue
        # Any room object with core combat stats can be used (players or NPC objects).
        if getattr(obj.db, "reflexes", None) is None:
            continue
        out.append(obj)
    return out


def _get_pc_stat(char, key: str) -> int:
    sheet = getattr(char, "character_sheet", None)
    if sheet and hasattr(sheet, key):
        return int(getattr(sheet, key) or 0)
    return int(getattr(char.db, key, 0) or 0)


def _get_pc_skill(char, key: str) -> int:
    sheet = getattr(char, "character_sheet", None)
    if sheet and hasattr(sheet, key):
        return int(getattr(sheet, key) or 0)
    skills = getattr(char.db, "skills", None) or {}
    return int(skills.get(key, 0) or 0)


def _get_pc_hp(char) -> Tuple[int, int]:
    sheet = getattr(char, "character_sheet", None)
    if sheet:
        cur = int(getattr(sheet, "_current_hp", 0) or 0)
        max_hp = int(getattr(sheet, "_max_hp", 0) or 0)
        return cur, max_hp
    cur = int(getattr(char.db, "current_hp", 0) or 0)
    max_hp = int(getattr(char.db, "max_hp", 0) or 0)
    return cur, max_hp


def _build_pc_entry(char) -> Dict:
    cur_hp, max_hp = _get_pc_hp(char)
    eqweapon = getattr(getattr(char, "character_sheet", None), "eqweapon", None)
    eqarmor = getattr(getattr(char, "character_sheet", None), "eqarmor", None)
    armor_sp = int(getattr(eqarmor, "sp", 0) or 0)
    armor_ev = int(getattr(eqarmor, "ev", 0) or 0)
    weapon_name = getattr(eqweapon, "name", "Unarmed")
    weapon_dmg = getattr(eqweapon, "damage", "2d6")
    kind = "pc" if getattr(char, "has_account", False) else "npc"
    default_team = "players" if kind == "pc" else "neutral"
    initiative_bonus = 0
    try:
        from world.role_abilities import get_solo_initiative_bonus
        initiative_bonus = int(get_solo_initiative_bonus(char) or 0)
    except Exception:
        initiative_bonus = 0
    return {
        "id": f"pc-{char.id}",
        "kind": kind,
        "obj_id": char.id,
        "name": char.key,
        "profile": "player" if kind == "pc" else "npc",
        "stats": {
            "reflexes": _get_pc_stat(char, "reflexes"),
            "dexterity": _get_pc_stat(char, "dexterity"),
            "body": _get_pc_stat(char, "body"),
            "willpower": _get_pc_stat(char, "willpower"),
            "move": _get_pc_stat(char, "move"),
        },
        "skills": {},
        "max_hp": max_hp,
        "current_hp": cur_hp,
        "weapon_name": weapon_name,
        "weapon_damage": weapon_dmg,
        "armor_name": getattr(eqarmor, "name", "None"),
        "armor_sp": armor_sp,
        "armor_ev": armor_ev,
        "init_roll": 0,
        "initiative": 0,
        "initiative_bonus": initiative_bonus,
        "active": cur_hp > 0 if max_hp else True,
        "team": default_team,
        "level": "pc",
    }


def _roll_initiative_for_entry(entry: Dict):
    ref = int((entry.get("stats") or {}).get("reflexes", 0) or 0)
    d10 = _roll_d10()
    lvl = _normalize_level_name(entry.get("level", "mook"))
    lvl_bonus = int(MOOK_LEVEL_MODS.get(lvl, {}).get("initiative_bonus", 0) or 0) if entry.get("kind") == "mook" else 0
    entry["init_roll"] = d10
    ca_bonus = int(entry.get("initiative_bonus", 0) or 0)
    entry["initiative"] = d10 + ref + lvl_bonus + ca_bonus
    entry["tie_break"] = random.randint(1, 10)


def _sort_roster(roster: List[Dict]) -> List[Dict]:
    return sorted(
        roster,
        key=lambda e: (
            int(e.get("initiative", 0) or 0),
            int((e.get("stats") or {}).get("reflexes", 0) or 0),
            int(e.get("tie_break", 0) or 0),
        ),
        reverse=True,
    )


def _active_roster_entries(scene: Dict) -> List[Dict]:
    return [e for e in scene.get("roster", []) if e.get("active", True) and int(e.get("current_hp", 1)) > 0]


def _resolve_entry(scene: Dict, query: str) -> Optional[Dict]:
    q = (query or "").strip().lower()
    if not q:
        return None
    roster = scene.get("roster", [])
    for e in roster:
        if (e.get("id") or "").lower() == q:
            return e
    exact = [e for e in roster if (e.get("name") or "").lower() == q]
    if len(exact) == 1:
        return exact[0]
    partial = [e for e in roster if q in (e.get("name") or "").lower()]
    if len(partial) == 1:
        return partial[0]
    # #<index> support based on visible roster order
    if q.startswith("#") and q[1:].isdigit():
        idx = int(q[1:])
        ordered = scene.get("roster", [])
        if 1 <= idx <= len(ordered):
            return ordered[idx - 1]
    return None


def _resolve_roll_values(scene: Dict, entry: Dict, stat_key: str, skill_key: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Resolve stat/skill values for a roster entry; returns (stat, skill, error)."""
    if entry.get("kind") == "pc":
        from evennia.utils.search import search_object

        found = search_object(f"#{entry.get('obj_id')}")
        char = found[0] if found else None
        if not char:
            return None, None, "Could not resolve player combatant object."
        stat_val = _get_pc_stat(char, stat_key)
        skill_val = _get_pc_skill(char, skill_key) if skill_key else 0
        return stat_val, skill_val, None
    stat_val = int((entry.get("stats") or {}).get(stat_key, 0) or 0)
    skill_val = int((entry.get("skills") or {}).get(skill_key, 0) or 0) if skill_key else 0
    return stat_val, skill_val, None


def _parse_stat_skill_expr(raw_expr: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse <stat>[+<skill>] into keys; returns (stat, skill, error)."""
    expr = (raw_expr or "").strip().lower().replace(" ", "")
    if not expr:
        return None, None, "Roll expression cannot be empty."
    m = re.match(r"^([a-z_]+)(?:\+([a-z_]+))?$", expr)
    if not m:
        return None, None, "Use format: <stat> or <stat>+<skill> (e.g. reflexes+handgun)"
    return m.group(1), m.group(2), None


def _roll_entry_expr(scene: Dict, entry: Dict, stat_key: str, skill_key: Optional[str]) -> Tuple[Optional[Dict], Optional[str]]:
    """Roll 1d10 + stat + optional skill for entry; returns ({parts}, err)."""
    stat_val, skill_val, err = _resolve_roll_values(scene, entry, stat_key, skill_key)
    if err:
        return None, err
    d10 = _roll_d10()
    total = d10 + int(stat_val or 0) + int(skill_val or 0)
    return {
        "d10": int(d10),
        "stat": int(stat_val or 0),
        "skill": int(skill_val or 0),
        "total": int(total),
    }, None


def _current_turn_entry(scene: Dict) -> Optional[Dict]:
    roster = scene.get("roster") or []
    if not roster:
        return None
    idx = int(scene.get("turn_index", 0) or 0)
    if idx < 0 or idx >= len(roster):
        idx = 0
        scene["turn_index"] = 0
    return roster[idx]


def _advance_turn(scene: Dict) -> Optional[Dict]:
    roster = scene.get("roster") or []
    if not roster:
        return None
    start_idx = int(scene.get("turn_index", 0) or 0)
    idx = start_idx
    total = len(roster)
    wrapped = False
    for _ in range(total):
        idx = (idx + 1) % total
        if idx == 0:
            wrapped = True
        e = roster[idx]
        if e.get("active", True) and int(e.get("current_hp", 1)) > 0:
            scene["turn_index"] = idx
            if wrapped:
                scene["round"] = int(scene.get("round", 1) or 1) + 1
            return e
    return None


def _maybe_end_combat(room, scene) -> bool:
    alive = _active_roster_entries(scene)
    if len(alive) <= 1:
        winner = alive[0]["name"] if alive else "No one"
        room.msg_contents(f"|rCombat has ended.|n Remaining active combatant: |w{winner}|n.")
        room.ndb.combat_state = None
        return True
    return False


def _hazard_damage_for_entry(entry: Dict, hazard: Dict) -> Tuple[int, str]:
    """
    Compute hazard damage for one tick.
    Returns (damage, detail).
    """
    htype = str(hazard.get("type", "")).strip().lower()
    intensity = str(hazard.get("intensity", "")).strip().lower() or "mild"
    if htype == "fire":
        fire_map = {"mild": 2, "strong": 4, "deadly": 6}
        if intensity.isdigit():
            dmg = max(0, int(intensity))
        else:
            dmg = fire_map.get(intensity, 2)
        return dmg, f"fire ({intensity})"
    if htype == "drowning":
        body = int((entry.get("stats") or {}).get("body", 0) or 0)
        return max(1, body), "drowning"
    if htype == "electrocution":
        dice = 6
        if intensity.isdigit():
            dice = max(1, int(intensity))
        rolls = [random.randint(1, 6) for _ in range(dice)]
        raw = sum(rolls)
        sp = int(entry.get("armor_sp", 0) or 0)
        dmg = max(0, raw - sp)
        return dmg, f"electrocution ({dice}d6={raw}, armor {sp})"
    return 0, htype or "hazard"


def _apply_hazards_for_entry(room, scene: Dict, entry: Dict) -> bool:
    """
    Apply start-of-turn hazard ticks for an entry.
    Returns True if combat ended.
    """
    hazards = list(scene.get("hazards", []) or [])
    if not hazards:
        return False
    eid = str(entry.get("id", ""))
    remaining = []
    for hz in hazards:
        if str(hz.get("entry_id", "")) != eid:
            remaining.append(hz)
            continue
        if not entry.get("active", True) or int(entry.get("current_hp", 0) or 0) <= 0:
            continue
        dmg, detail = _hazard_damage_for_entry(entry, hz)
        cur = int(entry.get("current_hp", 0) or 0)
        new_hp = max(0, cur - int(dmg))
        entry["current_hp"] = new_hp
        entry["active"] = new_hp > 0
        room.msg_contents(
            f"|xHazard tick:|n |w{entry.get('name', '?')}|n suffers |r{dmg}|n from {detail} ({cur}->{new_hp})."
        )
        rounds = int(hz.get("rounds", 0) or 0)
        if rounds > 1:
            hz["rounds"] = rounds - 1
            remaining.append(hz)
        elif rounds <= 0:
            # rounds<=0 means persistent until cleared
            remaining.append(hz)
        if new_hp <= 0:
            room.msg_contents(f"|r{entry.get('name', '?')} is down from hazards!|n")
            if _maybe_end_combat(room, scene):
                scene["hazards"] = remaining
                return True
    scene["hazards"] = remaining
    return False


def _initiative_display(scene: Dict, width: int = 98) -> str:
    out = sheet_header("Combat Initiative", width=width)
    out += sheet_section(f"Round {scene.get('round', 1)}", width=width)
    out += (
        f"  |y{'#':>2}|n  |w{'Name':<20}|n  |w{'Type':<7}|n  |w{'Lvl':<9}|n  |w{'Team':<9}|n  |w{'A/M':<5}|n  "
        f"|w{'Init':>4}|n  |w{'HP':>9}|n  |w{'Armor':<11}|n  |wWeapon|n\n"
    )
    current = _current_turn_entry(scene)
    for idx, e in enumerate(scene.get("roster", []), start=1):
        marker = "|g>>|n" if current and e.get("id") == current.get("id") else "  "
        st = _get_turn_state(scene, e.get("id"))
        am = f"{'X' if st.get('action_used') else '-'}{'X' if st.get('move_used') else '-'}"
        hp = f"{int(e.get('current_hp', 0))}/{int(e.get('max_hp', 0))}"
        armor = f"{e.get('armor_name', 'None')} ({int(e.get('armor_sp', 0))})"
        out += (
            f"{marker}|y{idx:>2}|n  |w{str(e.get('name', '?'))[:20]:<20}|n  "
            f"|m{str(e.get('kind', '?')):<7}|n  |y{str(e.get('level', 'mook'))[:9]:<9}|n  "
            f"|c{str(e.get('team', 'neutral'))[:9]:<9}|n  |x{am:<5}|n  "
            f"|c{int(e.get('initiative', 0)):>4}|n  |w{hp:>9}|n  |w{armor[:11]:<11}|n  "
            f"|w{str(e.get('weapon_name', 'Unarmed'))[:16]}|n\n"
        )
    out += "|x  >> indicates current turn. A/M: Action/Move used (X=spent).|n\n"
    held = len(scene.get("held_actions", []) or [])
    if held:
        out += f"|x  Held actions queued: {held}|n\n"
    hz_count = len(scene.get("hazards", []) or [])
    if hz_count:
        out += f"|x  Active hazards: {hz_count}|n\n"
    out += footer(width=width, fillchar="-")
    return out


def queue_backup_arrival(room, source_name: str, tiers: List[int], eta_rounds: int, team: str = "backup") -> bool:
    """
    Queue Lawman backup arrival into active scene combat.
    Returns True if queued into combat scene, False if no active scene.
    """
    if not room:
        return False
    scene = getattr(room.ndb, COMBAT_STATE_ATTR, None)
    if not scene:
        return False
    pending = list(scene.get("pending_backup_arrivals", []) or [])
    pending.append(
        {
            "source": source_name or "unknown",
            "tiers": [max(1, min(10, int(t))) for t in (tiers or [1])],
            "eta_rounds": max(1, int(eta_rounds or 1)),
            "team": _normalize_team_name(team),
        }
    )
    scene["pending_backup_arrivals"] = pending
    return True


def _spawn_backup_group(scene: Dict, tier: int, team: str = "backup") -> int:
    """Spawn one backup tier composition into scene roster. Returns count spawned."""
    comp = BACKUP_COMPOSITIONS.get(int(tier), BACKUP_COMPOSITIONS[1])
    spawned = 0
    for profile_name, level, count in comp:
        key, profile, resolved_level = _resolve_profile_and_level(profile_name, level)
        if not profile:
            continue
        for _ in range(max(1, int(count))):
            scene["mook_counter"] = int(scene.get("mook_counter", 0) or 0) + 1
            m = _randomize_mook_from_profile(key, profile, scene["mook_counter"], level=resolved_level)
            m["team"] = _normalize_team_name(team)
            m["profile"] = f"backup:{tier}:{m.get('profile', key)}"
            _roll_initiative_for_entry(m)
            scene["roster"].append(m)
            spawned += 1
    return spawned


def _resolve_pending_backup_arrivals(room, scene) -> int:
    """
    Decrement ETA for pending backup arrivals by one round and spawn any that arrive.
    Returns number of spawned combatants.
    """
    pending = list(scene.get("pending_backup_arrivals", []) or [])
    if not pending:
        return 0

    current = _current_turn_entry(scene)
    current_id = current.get("id") if current else None
    remaining = []
    spawned_total = 0

    for item in pending:
        eta = int(item.get("eta_rounds", 1) or 1) - 1
        if eta > 0:
            item["eta_rounds"] = eta
            remaining.append(item)
            continue

        tiers = [max(1, min(10, int(t))) for t in (item.get("tiers") or [1])]
        team = _normalize_team_name(item.get("team", "backup"))
        src = item.get("source", "Backup")
        labels = []
        for tier in tiers:
            labels.append(f"Tier {tier}")
            spawned_total += _spawn_backup_group(scene, tier, team=team)
        room.msg_contents(
            f"|gBackup arrives!|n {src} receives {', '.join(labels)} responders "
            f"on team |c{team}|n."
        )

    scene["pending_backup_arrivals"] = remaining

    if spawned_total > 0:
        scene["roster"] = _sort_roster(scene["roster"])
        if current_id:
            for idx, e in enumerate(scene["roster"]):
                if e.get("id") == current_id:
                    scene["turn_index"] = idx
                    break
    return spawned_total

class CmdCombat(MuxCommand):
    """
    Scene combat tracker with ephemeral mooks (no NPC object creation).

    Usage:
      combat
      combat/start
      combat/end
      combat/next
      combat/backups
      combat/presets
      combat/spawn <preset>[=<team>]
      combat/teams
      combat/team <combatant>=<team>
      combat/team/clear <combatant>
      combat/add <character or npc>
      combat/profiles
      combat/addmook <profile>[:count][=<team>]
      combat/addmook <profile>/<mook|lieutenant|mini-boss>[:count][=<team>]
      combat/addlieutenant <profile>[:count][=<team>]
      combat/addminiboss <profile>[:count][=<team>]
      combat/removemook <name or #>
      combat/hold <combatant>=<#N|combatant>:<action text>
      combat/hold/roll <combatant>=<#N|combatant>:<stat>[+<skill>][ vs <dv>|<target>:<stat>[+<skill>]]
      combat/hold/store <combatant>=<#N|combatant>:<stat>[+<skill>][ vs <dv>|<target>:<stat>[+<skill>]]
      combat/act <combatant>=<what they do>
      combat/move <combatant>[=<distance text>]
      combat/run <combatant>[=<distance text>]
      combat/roll <combatant>=<stat>[+<skill>]
      combat/contest <combatant>=<stat>[+<skill>] vs <target>:<stat>[+<skill>]
      combat/hazard <combatant>=<fire|electrocution|drowning>[:<intensity>][:<rounds>]
      combat/hazard/clear <combatant>[=<type>]
      combat/hazards
      combat/damage <combatant>=<amount>
      combat/heal <combatant>=<amount>
    """
    key = "combat"
    aliases = ["fight"]
    help_category = "Combat"

    def func(self):
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before using the combat command.")
            return
        room = self.caller.location
        if not room:
            self.caller.msg("You are nowhere.")
            return

        sw = (self.switches[0].lower() if self.switches else "")
        if not sw and self.args:
            first = self.args.strip().split(None, 1)[0].lower()
            legacy_map = {
                "start": "start",
                "end": "end",
                "next": "next",
                "backups": "backups",
                "presets": "presets",
                "spawn": "spawn",
                "teams": "teams",
                "team": "team",
                "add": "add",
                "profiles": "profiles",
                "addmook": "addmook",
                "addlieutenant": "addlieutenant",
                "addminiboss": "addminiboss",
                "removemook": "removemook",
                "hold": "hold",
                "act": "act",
                "move": "move",
                "run": "run",
                "roll": "roll",
                "contest": "contest",
                "hazard": "hazard",
                "hazards": "hazards",
                "damage": "damage",
                "heal": "heal",
            }
            if first in legacy_map:
                sw = legacy_map[first]
                remainder = self.args.strip()[len(first):].strip()
                self.args = remainder
        if not sw and not self.args:
            self._status(room)
            return

        if sw == "start":
            self._start(room)
            return
        if sw == "end":
            self._end(room)
            return
        if sw == "next":
            self._next_turn(room)
            return
        if sw == "backups":
            self._backups(room)
            return
        if sw == "presets":
            self._presets()
            return
        if sw == "spawn":
            self._spawn(room)
            return
        if sw == "teams":
            self._teams(room)
            return
        if sw == "team":
            self._team(room)
            return
        if sw == "add":
            self._add_combatant(room)
            return
        if sw == "profiles":
            self._profiles()
            return
        if sw == "addmook":
            self._add_mook(room, forced_level=None)
            return
        if sw == "addlieutenant":
            self._add_mook(room, forced_level="lieutenant")
            return
        if sw == "addminiboss":
            self._add_mook(room, forced_level="mini-boss")
            return
        if sw == "removemook":
            self._remove_mook(room)
            return
        if sw == "hold":
            self._hold(room)
            return
        if sw == "act":
            self._act(room)
            return
        if sw == "move":
            self._move(room)
            return
        if sw == "run":
            self._run(room)
            return
        if sw == "roll":
            self._roll(room)
            return
        if sw == "contest":
            self._contest(room)
            return
        if sw == "hazard":
            self._hazard(room)
            return
        if sw == "hazards":
            self._hazards(room)
            return
        if sw == "damage":
            self._adjust_hp(room, heal=False)
            return
        if sw == "heal":
            self._adjust_hp(room, heal=True)
            return

        self.caller.msg(
            "Usage: combat, combat/start, combat/end, combat/next, combat/backups, combat/presets, combat/spawn, combat/teams, combat/team, combat/add, combat/profiles, "
            "combat/addmook, combat/addlieutenant, combat/addminiboss, combat/removemook, combat/hold, combat/act, combat/move, combat/run, combat/roll, combat/contest, "
            "combat/hazard, combat/hazards, combat/damage, combat/heal"
        )

    def _scene(self, room) -> Optional[Dict]:
        return getattr(room.ndb, COMBAT_STATE_ATTR, None)

    def _set_scene(self, room, scene: Optional[Dict]):
        room.ndb.combat_state = scene

    def _status(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat in this room. Use |wcombat/start|n.")
            return
        self.caller.msg(_initiative_display(scene))

    def _start(self, room):
        if self._scene(room):
            self.caller.msg("Combat is already active here. Use |wcombat|n or |wcombat/end|n.")
            return
        chars = _living_characters_in_room(room)
        roster = []
        for char in chars:
            roster.append(_build_pc_entry(char))
        if not roster:
            self.caller.msg("No valid player combatants found in this room.")
            return
        for e in roster:
            _roll_initiative_for_entry(e)
        roster = _sort_roster(roster)
        scene = {
            "active": True,
            "round": 1,
            "turn_index": 0,
            "mook_counter": 0,
            "pending_backup_arrivals": [],
            "held_actions": [],
            "hazards": [],
            "turn_state": {},
            "roster": roster,
            "started_by": self.caller.id,
        }
        current = _current_turn_entry(scene)
        if current:
            _reset_turn_state_for_entry(scene, current.get("id"))
        self._set_scene(room, scene)
        room.msg_contents(f"|rCombat has started!|n ({len(roster)} combatants)")
        room.msg_contents(_initiative_display(scene))
        if current:
            room.msg_contents(f"|yRound 1, turn:|n |w{current.get('name')}|n")

    def _end(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("There is no active combat to end.")
            return
        self._set_scene(room, None)
        room.msg_contents(f"|rCombat has ended by {self.caller.key}.|n Mooks and scene roster have been cleared.")

    def _next_turn(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat. Use |wcombat/start|n.")
            return
        prev_round = int(scene.get("round", 1) or 1)
        nxt = _advance_turn(scene)
        if not nxt:
            self.caller.msg("Could not advance turn.")
            return
        new_round = int(scene.get("round", 1) or 1)
        if new_round > prev_round:
            _resolve_pending_backup_arrivals(room, scene)
        _reset_turn_state_for_entry(scene, nxt.get("id"))
        if _apply_hazards_for_entry(room, scene, nxt):
            return
        self._resolve_held_actions(room, scene, nxt)
        room.msg_contents(_initiative_display(scene))
        room.msg_contents(f"|yRound {scene.get('round', 1)}, turn:|n |w{nxt.get('name')}|n")

    def _resolve_held_actions(self, room, scene: Dict, current_entry: Dict):
        """Resolve held actions that trigger on current queue slot/combatant."""
        held = list(scene.get("held_actions", []) or [])
        if not held:
            return
        cur_id = str(current_entry.get("id", ""))
        try:
            cur_pos = int(scene.get("turn_index", 0) or 0) + 1
        except Exception:
            cur_pos = 0
        keep = []
        for item in held:
            trigger_type = item.get("trigger_type")
            trigger_value = str(item.get("trigger_value", ""))
            fire = False
            if trigger_type == "entry" and trigger_value == cur_id:
                fire = True
            elif trigger_type == "index":
                try:
                    fire = int(trigger_value) == cur_pos
                except Exception:
                    fire = False
            if not fire:
                keep.append(item)
                continue
            holder = _resolve_entry_by_id(scene, item.get("holder_id", ""))
            holder_name = holder.get("name", "Unknown") if holder else "Unknown"
            if not holder or not holder.get("active", True) or int(holder.get("current_hp", 1) or 0) <= 0:
                room.msg_contents(
                    f"|xHeld action fizzles:|n {holder_name} is no longer able to act."
                )
                continue
            action_kind = str(item.get("action_kind", "text")).lower()
            if action_kind == "roll":
                expr = str(item.get("roll_expr", "")).strip()
                stat_key = str(item.get("stat_key", "")).strip()
                skill_key = str(item.get("skill_key", "")).strip() or None
                pre_rolled = bool(item.get("pre_rolled", False))
                compare_mode = str(item.get("compare_mode", "none")).strip().lower()
                compare_dv = int(item.get("compare_dv", 0) or 0)
                compare_target_mode = str(item.get("compare_target_mode", "trigger")).strip().lower()
                compare_target_id = str(item.get("compare_target_id", "")).strip()
                compare_target_stat = str(item.get("compare_target_stat", "")).strip()
                compare_target_skill = str(item.get("compare_target_skill", "")).strip() or None
                holder_roll: Dict[str, int]
                if pre_rolled:
                    holder_roll = {
                        "d10": int(item.get("stored_d10", 0) or 0),
                        "stat": int(item.get("stored_stat", 0) or 0),
                        "skill": int(item.get("stored_skill", 0) or 0),
                        "total": int(item.get("stored_total", 0) or 0),
                    }
                else:
                    holder_roll, err = _roll_entry_expr(scene, holder, stat_key, skill_key)
                    if err:
                        room.msg_contents(f"|xHeld roll fizzles:|n {holder_name} - {err}")
                        continue
                base_line = (
                    f"|w{holder_name}|n's held roll triggers on |w{current_entry.get('name', '?')}|n: "
                    f"{expr} -> 1d10[{holder_roll['d10']}] + {holder_roll['stat']}"
                    + (f" + {holder_roll['skill']}" if skill_key else "")
                    + f" = |g{holder_roll['total']}|n"
                    + (" |x(stored)|n" if pre_rolled else "")
                )
                if compare_mode == "dv":
                    success = int(holder_roll["total"]) >= int(compare_dv)
                    room.msg_contents(
                        f"{base_line} vs DV{compare_dv}: "
                        + ("|gSUCCESS|n" if success else "|rFAIL|n")
                    )
                elif compare_mode == "opposed":
                    if compare_target_mode == "entry" and compare_target_id:
                        opp_entry = _resolve_entry_by_id(scene, compare_target_id)
                    else:
                        opp_entry = current_entry
                    if not opp_entry or not opp_entry.get("active", True) or int(opp_entry.get("current_hp", 1) or 0) <= 0:
                        room.msg_contents(f"|xHeld roll fizzles:|n Opposed target is unavailable.")
                        continue
                    opp_roll, err = _roll_entry_expr(
                        scene,
                        opp_entry,
                        compare_target_stat,
                        compare_target_skill,
                    )
                    if err:
                        room.msg_contents(f"|xHeld roll fizzles:|n {err}")
                        continue
                    opp_expr = compare_target_stat + (f"+{compare_target_skill}" if compare_target_skill else "")
                    if int(holder_roll["total"]) > int(opp_roll["total"]):
                        result = "|gWIN|n"
                    elif int(holder_roll["total"]) < int(opp_roll["total"]):
                        result = "|rLOSE|n"
                    else:
                        result = "|yTIE|n"
                    room.msg_contents(
                        f"{base_line} vs |w{opp_entry.get('name', '?')}|n({opp_expr}) "
                        f"[1d10[{opp_roll['d10']}] + {opp_roll['stat']}"
                        + (f" + {opp_roll['skill']}" if compare_target_skill else "")
                        + f" = |c{opp_roll['total']}|n]: {result}"
                    )
                else:
                    room.msg_contents(base_line)
            else:
                action_text = str(item.get("action_text", "")).strip() or "acts"
                room.msg_contents(
                    f"|w{holder_name}|n's held action triggers on |w{current_entry.get('name', '?')}|n: {action_text}"
                )
        scene["held_actions"] = keep

    def _backups(self, room):
        """Show pending backup arrivals in this combat scene."""
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat. Use |wcombat/start|n.")
            return
        pending = list(scene.get("pending_backup_arrivals", []) or [])
        if not pending:
            self.caller.msg("No pending backup arrivals in this scene.")
            return

        lines = [sheet_header("Pending Backup Arrivals", width=84), sheet_section("Inbound Units", width=84)]
        lines.append(f"  |y{'#':>2}|n  |w{'Source':<18}|n  |w{'Tiers':<12}|n  |w{'Team':<10}|n  |wETA (rounds)|n")
        for idx, item in enumerate(pending, start=1):
            src = str(item.get("source", "unknown"))[:18]
            tiers = ",".join(str(t) for t in (item.get("tiers") or []))[:12]
            team = str(item.get("team", "backup"))[:10]
            eta = int(item.get("eta_rounds", 0) or 0)
            lines.append(f"  |y{idx:>2}|n  |w{src:<18}|n  |c{tiers:<12}|n  |m{team:<10}|n  |w{eta}|n")
        lines.append(footer(width=84, fillchar="-"))
        self.caller.msg("\n".join(lines))

    def _presets(self):
        lines = [sheet_header("Encounter Presets", width=84), sheet_section("Auto-spawn templates", width=84)]
        for key in sorted(ENCOUNTER_PRESETS.keys()):
            p = ENCOUNTER_PRESETS[key]
            lines.append(f"|w{key}|n - {p.get('description', '')}")
        lines.append("")
        lines.append("|xScaling: mooks scale by preset multiplier; lieutenants are ~1 per 2 PCs; mini-bosses by preset ratio.|n")
        lines.append("|xUse: combat/spawn <preset>[=<team>] (defaults to team 'enemy').|n")
        lines.append(footer(width=84, fillchar="-"))
        self.caller.msg("\n".join(lines))

    def _spawn(self, room):
        """
        Auto-spawn balanced encounter composition.
        If combat is not active, starts combat with current room characters first.
        """
        raw = (self.args or "").strip()
        if not raw:
            self.caller.msg("Usage: combat/spawn <preset>[=<team>] (see combat/presets)")
            return
        team = "enemy"
        if "=" in raw:
            raw, team_raw = raw.split("=", 1)
            team = _normalize_team_name(team_raw)
        preset_key = _normalize_preset_name(raw)
        if not preset_key:
            self.caller.msg("Unknown preset. Use |wcombat/presets|n.")
            return

        scene = self._scene(room)
        if not scene:
            self._start(room)
            scene = self._scene(room)
        if not scene:
            self.caller.msg("Could not start or access combat scene.")
            return

        preset = ENCOUNTER_PRESETS[preset_key]
        pc_count = max(1, _count_active_pcs(scene))
        mook_mult = float(preset.get("mook_mult", 2.0) or 2.0)
        mook_min = int(preset.get("mook_min", 2) or 2)
        mook_count = max(mook_min, int(round(pc_count * mook_mult)))

        lt_ratio = int(preset.get("lt_ratio", 2) or 2)
        boss_ratio = int(preset.get("boss_ratio", 0) or 0)
        lt_count = pc_count // lt_ratio if lt_ratio > 0 else 0
        boss_count = pc_count // boss_ratio if boss_ratio > 0 else 0

        spawned = {"mook": 0, "lieutenant": 0, "mini-boss": 0}
        for _ in range(mook_count):
            profile_name = _pick_from_pool(preset.get("mook_pool", []))
            key, profile, level = _resolve_profile_and_level(profile_name, "mook")
            if not profile:
                continue
            scene["mook_counter"] = int(scene.get("mook_counter", 0) or 0) + 1
            m = _randomize_mook_from_profile(key, profile, scene["mook_counter"], level=level)
            m["team"] = team
            _roll_initiative_for_entry(m)
            scene["roster"].append(m)
            spawned["mook"] += 1

        for _ in range(lt_count):
            profile_name = _pick_from_pool(preset.get("lieutenant_pool", []))
            key, profile, level = _resolve_profile_and_level(profile_name, "lieutenant")
            if not profile:
                continue
            scene["mook_counter"] = int(scene.get("mook_counter", 0) or 0) + 1
            m = _randomize_mook_from_profile(key, profile, scene["mook_counter"], level=level)
            m["team"] = team
            _roll_initiative_for_entry(m)
            scene["roster"].append(m)
            spawned["lieutenant"] += 1

        for _ in range(boss_count):
            profile_name = _pick_from_pool(preset.get("boss_pool", []))
            key, profile, level = _resolve_profile_and_level(profile_name, "mini-boss")
            if not profile:
                continue
            scene["mook_counter"] = int(scene.get("mook_counter", 0) or 0) + 1
            m = _randomize_mook_from_profile(key, profile, scene["mook_counter"], level=level)
            m["team"] = team
            _roll_initiative_for_entry(m)
            scene["roster"].append(m)
            spawned["mini-boss"] += 1

        scene["roster"] = _sort_roster(scene["roster"])
        scene["turn_index"] = 0
        room.msg_contents(
            f"|mSpawned preset|n |w{preset_key}|n for |c{pc_count}|n active PC(s) on team |c{team}|n: "
            f"{spawned['mook']} mook(s), {spawned['lieutenant']} lieutenant(s), {spawned['mini-boss']} mini-boss(es)."
        )
        room.msg_contents(_initiative_display(scene))

    def _teams(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        team_map: Dict[str, List[str]] = {}
        for e in scene.get("roster", []):
            team = _normalize_team_name(e.get("team", "neutral"))
            team_map.setdefault(team, []).append(e.get("name", "?"))
        lines = [sheet_header("Combat Teams", width=80), sheet_section("Current assignment", width=80)]
        for team, names in sorted(team_map.items(), key=lambda kv: kv[0]):
            lines.append(f"|c{team}|n: {', '.join(names)}")
        lines.append(footer(width=80, fillchar="-"))
        self.caller.msg("\n".join(lines))

    def _team(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        if "clear" in (self.switches or []):
            query = (self.args or "").strip()
            if not query:
                self.caller.msg("Usage: combat/team/clear <combatant>")
                return
            entry = _resolve_entry(scene, query)
            if not entry:
                self.caller.msg("Combatant not found.")
                return
            entry["team"] = "neutral"
            room.msg_contents(f"|w{entry.get('name')}|n is now on team |cneutral|n.")
            room.msg_contents(_initiative_display(scene))
            return
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: combat/team <combatant>=<team>")
            return
        left, team_raw = self.args.split("=", 1)
        entry = _resolve_entry(scene, left.strip())
        if not entry:
            self.caller.msg("Combatant not found.")
            return
        team = _normalize_team_name(team_raw)
        entry["team"] = team
        room.msg_contents(f"|w{entry.get('name')}|n assigned to team |c{team}|n.")
        room.msg_contents(_initiative_display(scene))

    def _add_combatant(self, room):
        """Add an existing room character/NPC object into active combat roster."""
        scene = self._scene(room)
        if not scene:
            self.caller.msg("Start combat first with |wcombat/start|n.")
            return
        target_q = (self.args or "").strip()
        if not target_q:
            self.caller.msg("Usage: combat/add <character or npc>")
            return
        target = self.caller.search(target_q, location=room)
        if not target:
            return
        if getattr(target.db, "reflexes", None) is None:
            self.caller.msg(f"{target.key} has no combat stats (missing reflexes).")
            return
        existing = next((e for e in scene.get("roster", []) if e.get("kind") in ("pc", "npc") and e.get("obj_id") == target.id), None)
        if existing:
            self.caller.msg(f"{target.key} is already on the combat roster.")
            return
        entry = _build_pc_entry(target)
        _roll_initiative_for_entry(entry)
        scene["roster"].append(entry)
        scene["roster"] = _sort_roster(scene["roster"])
        scene["turn_index"] = 0
        room.msg_contents(f"|mAdded combatant:|n |w{entry.get('name')}|n ({entry.get('kind')}).")
        room.msg_contents(_initiative_display(scene))

    def _profiles(self):
        names = sorted(MOOK_PROFILES.keys())
        named = sorted(NAMED_ARCHETYPES.keys())
        self.caller.msg(
            "Available base mook profiles:\n  "
            + ", ".join(names)
            + "\n\nNamed archetype shortcuts (from CPR examples):\n  "
            + ", ".join(named)
            + "\n\nLevels: mook, lieutenant, mini-boss"
        )

    def _add_mook(self, room, forced_level: Optional[str] = None):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("Start combat first with |wcombat/start|n.")
            return
        raw = (self.args or "").strip()
        if not raw:
            self.caller.msg(
                "Usage: combat/addmook <profile>[:count][=<team>]\n"
                "       combat/addmook <profile>/<mook|lieutenant|mini-boss>[:count][=<team>]"
            )
            return
        team = "neutral"
        if "=" in raw:
            raw, team_raw = raw.split("=", 1)
            team = _normalize_team_name(team_raw)
        count = 1
        profile_raw = raw
        if ":" in raw:
            profile_raw, cnt = raw.rsplit(":", 1)
            if cnt.strip().isdigit():
                count = max(1, min(20, int(cnt.strip())))
        level = forced_level or "mook"
        if "/" in profile_raw:
            left, right = [p.strip() for p in profile_raw.split("/", 1)]
            # support both <profile>/<level> and <level>/<profile>
            if left.lower() in LEVEL_ALIASES:
                level = _normalize_level_name(left)
                profile_raw = right
            elif right.lower() in LEVEL_ALIASES:
                level = _normalize_level_name(right)
                profile_raw = left
        key, profile, resolved_level = _resolve_profile_and_level(profile_raw, level)
        if not profile:
            self.caller.msg("Unknown profile. Use |wcombat/profiles|n.")
            return
        level = _normalize_level_name(resolved_level)
        for _ in range(count):
            scene["mook_counter"] = int(scene.get("mook_counter", 0) or 0) + 1
            m = _randomize_mook_from_profile(key, profile, scene["mook_counter"], level=level)
            m["team"] = team
            _roll_initiative_for_entry(m)
            scene["roster"].append(m)
        scene["roster"] = _sort_roster(scene["roster"])
        scene["turn_index"] = 0
        room.msg_contents(f"|m{count} mook(s) added:|n {key} [{level}] (team: {team}).")
        room.msg_contents(_initiative_display(scene))

    def _remove_mook(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        query = (self.args or "").strip()
        if not query:
            self.caller.msg("Usage: combat/removemook <name or #>")
            return
        entry = _resolve_entry(scene, query)
        if not entry:
            self.caller.msg(f"No combatant found for '{query}'.")
            return
        if entry.get("kind") != "mook":
            self.caller.msg("Only mooks can be removed with this command.")
            return
        scene["roster"] = [e for e in scene["roster"] if e.get("id") != entry.get("id")]
        if scene.get("turn_index", 0) >= len(scene["roster"]):
            scene["turn_index"] = 0
        room.msg_contents(f"|mRemoved mook:|n |w{entry.get('name')}|n")
        if _maybe_end_combat(room, scene):
            return
        room.msg_contents(_initiative_display(scene))

    def _hold(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        if "=" not in self.args or ":" not in self.args:
            self.caller.msg(
                "Usage: combat/hold <combatant>=<#N|combatant>:<action text>\n"
                "Usage: combat/hold/roll <combatant>=<#N|combatant>:<stat>[+<skill>][ vs <dv>|<target>:<stat>[+<skill>]]\n"
                "Usage: combat/hold/store <combatant>=<#N|combatant>:<stat>[+<skill>][ vs <dv>|<target>:<stat>[+<skill>]]\n"
                "Example: combat/hold Soma=#3:shoot if they move\n"
                "Example: combat/hold/roll Soma=#3:reflexes+handgun\n"
                "Example: combat/hold/store Soma=Booster Ganger 1:reflexes+handgun vs 15\n"
                "Example: combat/hold/roll Soma=#3:reflexes+evasion vs trigger:dexterity+evasion"
            )
            return
        left, right = self.args.split("=", 1)
        trigger_raw, action_text = right.split(":", 1)
        action_text = action_text.strip()
        if not action_text:
            self.caller.msg("Held action text cannot be empty.")
            return
        holder = _resolve_entry(scene, left.strip())
        if not holder:
            self.caller.msg("Combatant not found.")
            return
        current = _current_turn_entry(scene)
        if not current or current.get("id") != holder.get("id"):
            cur_name = current.get("name") if current else "(none)"
            self.caller.msg(f"It is currently {cur_name}'s turn.")
            return
        st = _get_turn_state(scene, holder.get("id"))
        if st.get("action_used", False):
            self.caller.msg(f"{holder.get('name')} has already used their Action this turn.")
            return
        hold_switches = [s.lower() for s in (self.switches or [])]
        is_roll_hold = "roll" in hold_switches or "store" in hold_switches
        pre_store = "store" in hold_switches

        trigger_raw = trigger_raw.strip()
        trigger_type = None
        trigger_value = ""
        if trigger_raw.startswith("#") and trigger_raw[1:].isdigit():
            idx = int(trigger_raw[1:])
            if idx < 1 or idx > len(scene.get("roster", [])):
                self.caller.msg(f"Queue position must be between #1 and #{len(scene.get('roster', []))}.")
                return
            trigger_type = "index"
            trigger_value = str(idx)
            trigger_label = f"queue slot #{idx}"
        else:
            trig_entry = _resolve_entry(scene, trigger_raw)
            if not trig_entry:
                self.caller.msg("Trigger combatant not found.")
                return
            trigger_type = "entry"
            trigger_value = str(trig_entry.get("id", ""))
            trigger_label = trig_entry.get("name", trigger_raw)

        held = list(scene.get("held_actions", []) or [])
        item = {
            "holder_id": str(holder.get("id", "")),
            "trigger_type": trigger_type,
            "trigger_value": trigger_value,
            "set_round": int(scene.get("round", 1) or 1),
        }
        if is_roll_hold:
            raw_expr = action_text.strip()
            compare_mode = "none"
            compare_dv = 0
            compare_target_mode = "trigger"
            compare_target_id = ""
            compare_target_stat = ""
            compare_target_skill = ""

            split = re.split(r"\s+vs\s+", raw_expr, maxsplit=1, flags=re.IGNORECASE)
            base_expr = split[0].strip()
            compare_expr = split[1].strip() if len(split) == 2 else ""
            stat_key, skill_key, err = _parse_stat_skill_expr(base_expr)
            if err:
                self.caller.msg(f"Roll hold format is <stat>[+<skill>] (e.g. reflexes+handgun). {err}")
                return
            expr = base_expr.lower().replace(" ", "")

            if compare_expr:
                if compare_expr.isdigit():
                    compare_mode = "dv"
                    compare_dv = max(0, int(compare_expr))
                else:
                    if ":" not in compare_expr:
                        self.caller.msg("Compare target format is <target>:<stat>[+<skill>] or a numeric DV.")
                        return
                    target_raw, target_expr = compare_expr.split(":", 1)
                    t_stat, t_skill, t_err = _parse_stat_skill_expr(target_expr)
                    if t_err:
                        self.caller.msg(t_err)
                        return
                    target_raw = target_raw.strip()
                    if target_raw.lower() in {"trigger", "current"}:
                        compare_target_mode = "trigger"
                    else:
                        target_entry = _resolve_entry(scene, target_raw)
                        if not target_entry:
                            self.caller.msg("Compare target combatant not found.")
                            return
                        compare_target_mode = "entry"
                        compare_target_id = str(target_entry.get("id", ""))
                    compare_mode = "opposed"
                    compare_target_stat = str(t_stat or "")
                    compare_target_skill = str(t_skill or "")

            item["action_kind"] = "roll"
            item["roll_expr"] = expr
            item["stat_key"] = stat_key
            item["skill_key"] = skill_key or ""
            item["pre_rolled"] = bool(pre_store)
            item["compare_mode"] = compare_mode
            item["compare_dv"] = int(compare_dv)
            item["compare_target_mode"] = compare_target_mode
            item["compare_target_id"] = compare_target_id
            item["compare_target_stat"] = compare_target_stat
            item["compare_target_skill"] = compare_target_skill
            if pre_store:
                roll_data, err = _roll_entry_expr(scene, holder, stat_key, skill_key)
                if err:
                    self.caller.msg(err)
                    return
                item["stored_d10"] = int(roll_data["d10"])
                item["stored_stat"] = int(roll_data["stat"])
                item["stored_skill"] = int(roll_data["skill"])
                item["stored_total"] = int(roll_data["total"])
        else:
            item["action_kind"] = "text"
            item["action_text"] = action_text
        st["action_used"] = True
        st["last_action"] = "hold"
        held.append(item)
        scene["held_actions"] = held
        if is_roll_hold:
            mode = "stored roll" if pre_store else "roll"
            room.msg_contents(
                f"|w{holder.get('name')}|n holds a {mode} for |c{trigger_label}|n: {action_text}"
            )
        else:
            room.msg_contents(
                f"|w{holder.get('name')}|n holds an action for |c{trigger_label}|n: {action_text}"
            )
        room.msg_contents(_initiative_display(scene))

    def _act(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        if "=" not in self.args:
            self.caller.msg("Usage: combat/act <combatant>=<action text>")
            return
        left, action_text = self.args.split("=", 1)
        action_text = action_text.strip()
        entry = _resolve_entry(scene, left.strip())
        if not entry:
            self.caller.msg("Combatant not found.")
            return
        if not action_text:
            self.caller.msg("Action text cannot be empty.")
            return
        current = _current_turn_entry(scene)
        if not current or current.get("id") != entry.get("id"):
            cur_name = current.get("name") if current else "(none)"
            self.caller.msg(f"It is currently {cur_name}'s turn.")
            return
        st = _get_turn_state(scene, entry.get("id"))
        if st.get("action_used", False):
            self.caller.msg(f"{entry.get('name')} has already used their Action this turn.")
            return
        st["action_used"] = True
        st["last_action"] = "act"
        room.msg_contents(f"|w{entry.get('name')}|n acts: {action_text}")
        room.msg_contents(_initiative_display(scene))

    def _move(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        raw = (self.args or "").strip()
        if not raw:
            self.caller.msg("Usage: combat/move <combatant>[=<distance text>]")
            return
        if "=" in raw:
            left, dist = raw.split("=", 1)
            dist = dist.strip()
        else:
            left, dist = raw, ""
        entry = _resolve_entry(scene, left.strip())
        if not entry:
            self.caller.msg("Combatant not found.")
            return
        current = _current_turn_entry(scene)
        if not current or current.get("id") != entry.get("id"):
            cur_name = current.get("name") if current else "(none)"
            self.caller.msg(f"It is currently {cur_name}'s turn.")
            return
        st = _get_turn_state(scene, entry.get("id"))
        if st.get("move_used", False):
            self.caller.msg(f"{entry.get('name')} has already used their Move Action this turn.")
            return
        st["move_used"] = True
        st["last_move"] = "move"
        suffix = f" ({dist})" if dist else ""
        room.msg_contents(f"|w{entry.get('name')}|n moves{suffix}.")
        room.msg_contents(_initiative_display(scene))

    def _run(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        raw = (self.args or "").strip()
        if not raw:
            self.caller.msg("Usage: combat/run <combatant>[=<distance text>]")
            return
        if "=" in raw:
            left, dist = raw.split("=", 1)
            dist = dist.strip()
        else:
            left, dist = raw, ""
        entry = _resolve_entry(scene, left.strip())
        if not entry:
            self.caller.msg("Combatant not found.")
            return
        current = _current_turn_entry(scene)
        if not current or current.get("id") != entry.get("id"):
            cur_name = current.get("name") if current else "(none)"
            self.caller.msg(f"It is currently {cur_name}'s turn.")
            return
        st = _get_turn_state(scene, entry.get("id"))
        if not st.get("move_used", False):
            self.caller.msg("Run requires a prior Move Action this turn.")
            return
        if st.get("action_used", False):
            self.caller.msg("Run uses your Action, and Action is already spent.")
            return
        st["action_used"] = True
        st["run_used"] = True
        st["last_action"] = "run"
        suffix = f" ({dist})" if dist else ""
        room.msg_contents(f"|w{entry.get('name')}|n runs{suffix}.")
        room.msg_contents(_initiative_display(scene))

    def _roll(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        if "=" not in self.args:
            self.caller.msg("Usage: combat/roll <combatant>=<stat>[+<skill>][ vs <dv>]")
            return
        left, expr = self.args.split("=", 1)
        entry = _resolve_entry(scene, left.strip())
        if not entry:
            self.caller.msg("Combatant not found.")
            return
        current = _current_turn_entry(scene)
        if not current or current.get("id") != entry.get("id"):
            cur_name = current.get("name") if current else "(none)"
            self.caller.msg(f"It is currently {cur_name}'s turn.")
            return
        st = _get_turn_state(scene, entry.get("id"))
        if st.get("action_used", False):
            self.caller.msg(f"{entry.get('name')} has already used their Action this turn.")
            return

        split = re.split(r"\s+vs\s+", (expr or "").strip(), maxsplit=1, flags=re.IGNORECASE)
        base_expr = split[0].strip()
        compare_expr = split[1].strip() if len(split) == 2 else ""
        stat_key, skill_key, err = _parse_stat_skill_expr(base_expr)
        if err:
            self.caller.msg(err)
            return
        roll_data, err = _roll_entry_expr(scene, entry, str(stat_key), skill_key)
        if err:
            self.caller.msg(err)
            return
        rhs = f"{stat_key}" + (f" + {skill_key}" if skill_key else "")
        line = (
            f"|w{entry.get('name')}|n rolls |c{rhs}|n: 1d10[{roll_data['d10']}] + {roll_data['stat']}"
            + (f" + {roll_data['skill']}" if skill_key else "")
            + f" = |g{roll_data['total']}|n"
        )
        if compare_expr:
            if not compare_expr.isdigit():
                self.caller.msg("Roll compare supports numeric DV only: <stat>[+<skill>] vs <dv>")
                return
            dv = int(compare_expr)
            success = int(roll_data["total"]) >= dv
            line += f" vs DV{dv}: " + ("|gSUCCESS|n" if success else "|rFAIL|n")
        room.msg_contents(line)
        st["action_used"] = True
        st["last_action"] = "roll"
        room.msg_contents(_initiative_display(scene))

    def _contest(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        if "=" not in self.args or " vs " not in self.args.lower():
            self.caller.msg(
                "Usage: combat/contest <combatant>=<stat>[+<skill>] vs <target>:<stat>[+<skill>]\n"
                "Example: combat/contest Soma=reflexes+evasion vs Booster Ganger 1:dexterity+evasion"
            )
            return
        left, rhs = self.args.split("=", 1)
        entry = _resolve_entry(scene, left.strip())
        if not entry:
            self.caller.msg("Combatant not found.")
            return
        current = _current_turn_entry(scene)
        if not current or current.get("id") != entry.get("id"):
            cur_name = current.get("name") if current else "(none)"
            self.caller.msg(f"It is currently {cur_name}'s turn.")
            return
        st = _get_turn_state(scene, entry.get("id"))
        if st.get("action_used", False):
            self.caller.msg(f"{entry.get('name')} has already used their Action this turn.")
            return

        split = re.split(r"\s+vs\s+", rhs, maxsplit=1, flags=re.IGNORECASE)
        if len(split) != 2:
            self.caller.msg("Use format: <stat>[+<skill>] vs <target>:<stat>[+<skill>]")
            return
        actor_expr = split[0].strip()
        target_part = split[1].strip()
        if ":" not in target_part:
            self.caller.msg("Target side must be <target>:<stat>[+<skill>].")
            return
        target_query, target_expr = target_part.split(":", 1)
        target = _resolve_entry(scene, target_query.strip())
        if not target:
            self.caller.msg("Target combatant not found.")
            return
        if not target.get("active", True) or int(target.get("current_hp", 1) or 0) <= 0:
            self.caller.msg("Target is not currently active.")
            return
        a_stat, a_skill, err = _parse_stat_skill_expr(actor_expr)
        if err:
            self.caller.msg(err)
            return
        t_stat, t_skill, err = _parse_stat_skill_expr(target_expr)
        if err:
            self.caller.msg(err)
            return
        actor_roll, err = _roll_entry_expr(scene, entry, str(a_stat), a_skill)
        if err:
            self.caller.msg(err)
            return
        target_roll, err = _roll_entry_expr(scene, target, str(t_stat), t_skill)
        if err:
            self.caller.msg(err)
            return
        a_rhs = f"{a_stat}" + (f" + {a_skill}" if a_skill else "")
        t_rhs = f"{t_stat}" + (f" + {t_skill}" if t_skill else "")
        if int(actor_roll["total"]) > int(target_roll["total"]):
            result = f"|g{entry.get('name')} wins|n"
        elif int(actor_roll["total"]) < int(target_roll["total"]):
            result = f"|r{target.get('name')} wins|n"
        else:
            result = "|yTie|n"
        room.msg_contents(
            f"|w{entry.get('name')}|n contests |w{target.get('name')}|n: "
            f"|c{a_rhs}|n [1d10[{actor_roll['d10']}] + {actor_roll['stat']}"
            + (f" + {actor_roll['skill']}" if a_skill else "")
            + f" = |g{actor_roll['total']}|n] vs "
            f"|c{t_rhs}|n [1d10[{target_roll['d10']}] + {target_roll['stat']}"
            + (f" + {target_roll['skill']}" if t_skill else "")
            + f" = |c{target_roll['total']}|n] -> {result}"
        )
        st["action_used"] = True
        st["last_action"] = "contest"
        room.msg_contents(_initiative_display(scene))

    def _hazard(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        switches = [s.lower() for s in (self.switches or [])]
        is_clear = "clear" in switches
        if is_clear:
            raw = (self.args or "").strip()
            if not raw:
                self.caller.msg("Usage: combat/hazard/clear <combatant|all>[=<type>]")
                return
            if "=" in raw:
                target_raw, htype = raw.split("=", 1)
                htype = htype.strip().lower()
            else:
                target_raw, htype = raw, ""
            target_raw = target_raw.strip()
            entry = None
            eid = ""
            if target_raw.lower() != "all":
                entry = _resolve_entry(scene, target_raw)
                if not entry:
                    self.caller.msg("Combatant not found.")
                    return
                eid = str(entry.get("id", ""))
            hazards = list(scene.get("hazards", []) or [])
            kept = []
            removed = 0
            for hz in hazards:
                if target_raw.lower() != "all":
                    if str(hz.get("entry_id", "")) != eid:
                        kept.append(hz)
                        continue
                if htype and str(hz.get("type", "")).strip().lower() != htype:
                    kept.append(hz)
                    continue
                removed += 1
            scene["hazards"] = kept
            if target_raw.lower() == "all":
                self.caller.msg(f"Removed {removed} hazard(s) globally.")
            else:
                self.caller.msg(f"Removed {removed} hazard(s) from {entry.get('name')}.")
            room.msg_contents(_initiative_display(scene))
            return

        if "=" not in (self.args or ""):
            self.caller.msg(
                "Usage: combat/hazard <combatant>=<fire|electrocution|drowning>[:<intensity>][:<rounds>]\n"
                "Examples:\n"
                "  combat/hazard Soma=fire:strong:3\n"
                "  combat/hazard Booster Ganger 1=electrocution:6:2\n"
                "  combat/hazard Netrunner=drowning::0"
            )
            return
        left, rhs = self.args.split("=", 1)
        entry = _resolve_entry(scene, left.strip())
        if not entry:
            self.caller.msg("Combatant not found.")
            return
        parts = [p.strip() for p in rhs.split(":")]
        htype = (parts[0] if parts else "").lower()
        if htype not in {"fire", "electrocution", "drowning"}:
            self.caller.msg("Hazard type must be one of: fire, electrocution, drowning.")
            return
        intensity = parts[1].lower() if len(parts) > 1 and parts[1] else ""
        rounds = 3
        if len(parts) > 2 and parts[2]:
            try:
                rounds = int(parts[2])
            except ValueError:
                self.caller.msg("Rounds must be a number (0 = persistent).")
                return
        if rounds < 0:
            rounds = 0
        if htype == "fire" and not intensity:
            intensity = "mild"
        if htype == "electrocution" and not intensity:
            intensity = "6"
        hazard = {
            "entry_id": str(entry.get("id", "")),
            "type": htype,
            "intensity": intensity,
            "rounds": int(rounds),
            "source": str(self.caller.key),
        }
        hazards = list(scene.get("hazards", []) or [])
        hazards.append(hazard)
        scene["hazards"] = hazards
        dur = "persistent" if rounds == 0 else f"{rounds} rounds"
        self.caller.msg(
            f"Applied hazard to {entry.get('name')}: {htype}"
            + (f" ({intensity})" if intensity else "")
            + f", {dur}."
        )
        room.msg_contents(_initiative_display(scene))

    def _hazards(self, room):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        hazards = list(scene.get("hazards", []) or [])
        if not hazards:
            self.caller.msg("No active hazards in this scene.")
            return
        lines = ["|wActive hazards:|n"]
        for idx, hz in enumerate(hazards, start=1):
            entry = _resolve_entry_by_id(scene, hz.get("entry_id", ""))
            who = entry.get("name", "Unknown") if entry else "Unknown"
            htype = str(hz.get("type", "hazard"))
            intensity = str(hz.get("intensity", "")).strip()
            rounds = int(hz.get("rounds", 0) or 0)
            dur = "persistent" if rounds == 0 else f"{rounds}r"
            lines.append(
                f"  {idx:>2}. {who}: {htype}"
                + (f" ({intensity})" if intensity else "")
                + f" [{dur}]"
            )
        self.caller.msg("\n".join(lines))

    def _adjust_hp(self, room, heal: bool):
        scene = self._scene(room)
        if not scene:
            self.caller.msg("No active combat.")
            return
        if "=" not in self.args:
            cmd = "heal" if heal else "damage"
            self.caller.msg(f"Usage: combat/{cmd} <combatant>=<amount>")
            return
        left, amt_str = self.args.split("=", 1)
        entry = _resolve_entry(scene, left.strip())
        if not entry:
            self.caller.msg("Combatant not found.")
            return
        try:
            amt = max(0, int(amt_str.strip()))
        except ValueError:
            self.caller.msg("Amount must be a number.")
            return
        if amt <= 0:
            self.caller.msg("Amount must be positive.")
            return

        cur = int(entry.get("current_hp", 0) or 0)
        max_hp = int(entry.get("max_hp", 0) or 0)
        if heal:
            new_hp = min(max_hp, cur + amt)
        else:
            new_hp = max(0, cur - amt)
        entry["current_hp"] = new_hp
        entry["active"] = new_hp > 0

        verb = "heals" if heal else "damages"
        room.msg_contents(f"|w{self.caller.key}|n {verb} |w{entry.get('name')}|n for |c{amt}|n ({cur}->{new_hp}).")
        if not heal and new_hp <= 0:
            room.msg_contents(f"|r{entry.get('name')} is down!|n")
            if _maybe_end_combat(room, scene):
                return
        room.msg_contents(_initiative_display(scene))