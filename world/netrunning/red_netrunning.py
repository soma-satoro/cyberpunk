"""
Cyberpunk RED netrunning data and helper mechanics.

This module centralizes:
- Program and Black ICE catalogs
- Architecture generation tables
- Interface/NET action math helpers
- Paydata generation

Adapted from the core Cyberpunk Red rulebook NET Architecture rules.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple


BOOSTER_PROGRAMS = {
    "eraser": {
        "name": "Eraser",
        "class": "Booster",
        "atk": 0,
        "def": 0,
        "rez": 7,
        "cost": 20,
        "effect": "Increase all Cloak checks by +2 while Rezzed.",
    },
    "see_ya": {
        "name": "See Ya",
        "class": "Booster",
        "atk": 0,
        "def": 0,
        "rez": 7,
        "cost": 20,
        "effect": "Increase all Pathfinder checks by +2 while Rezzed.",
    },
    "speedy_gonzalvez": {
        "name": "Speedy Gonzalvez",
        "class": "Booster",
        "atk": 0,
        "def": 0,
        "rez": 7,
        "cost": 100,
        "effect": "Increase your Speed by +2 while Rezzed.",
    },
    "worm": {
        "name": "Worm",
        "class": "Booster",
        "atk": 0,
        "def": 0,
        "rez": 7,
        "cost": 50,
        "effect": "Increase all Backdoor checks by +2 while Rezzed.",
    },
}

DEFENDER_PROGRAMS = {
    "armor": {
        "name": "Armor",
        "class": "Defender",
        "atk": 0,
        "def": 0,
        "rez": 7,
        "cost": 50,
        "effect": "Lowers all brain damage you would receive by 4 while Rezzed.",
    },
    "flak": {
        "name": "Flak",
        "class": "Defender",
        "atk": 0,
        "def": 1,
        "rez": 7,
        "cost": 50,
        "effect": "Reduce ATK of all Non-Black ICE attacker Programs run against you to 0 while Rezzed.",
    },
    "shield": {
        "name": "Shield",
        "class": "Defender",
        "atk": 0,
        "def": 0,
        "rez": 7,
        "cost": 20,
        "effect": "Stops first successful Non-Black ICE attack while Rezzed.",
    },
}

ATTACKER_PROGRAMS = {
    "banhammer": {
        "name": "Banhammer",
        "class": "Anti-Program Attacker",
        "atk": 1,
        "def": 0,
        "rez": 0,
        "cost": 50,
        "effect": "Deal 3d6 REZ to non-Black ICE Program or 2d6 REZ to Black ICE.",
    },
    "sword": {
        "name": "Sword",
        "class": "Anti-Program Attacker",
        "atk": 1,
        "def": 0,
        "rez": 0,
        "cost": 50,
        "effect": "Deal 3d6 REZ to Black ICE or 2d6 REZ to non-Black ICE Program.",
    },
    "deckkrash": {
        "name": "DeckKRASH",
        "class": "Anti-Personnel Attacker",
        "atk": 0,
        "def": 0,
        "rez": 0,
        "cost": 100,
        "effect": "Enemy Netrunner is forcibly and unsafely Jacked Out if not already affected.",
    },
    "hellbolt": {
        "name": "Hellbolt",
        "class": "Anti-Personnel Attacker",
        "atk": 2,
        "def": 0,
        "rez": 0,
        "cost": 100,
        "effect": "Deal 2d6 damage directly to enemy Netrunner's brain.",
    },
    "nervescrub": {
        "name": "Nervescrub",
        "class": "Anti-Personnel Attacker",
        "atk": 0,
        "def": 0,
        "rez": 0,
        "cost": 100,
        "effect": "Lower target's INT/REF/DEX each by 1d6 for next hour (minimum 1).",
    },
    "poison_flatline": {
        "name": "Poison Flatline",
        "class": "Anti-Personnel Attacker",
        "atk": 0,
        "def": 0,
        "rez": 0,
        "cost": 100,
        "effect": "Destroy one non-Black ICE Program installed on target's Cyberdeck at random.",
    },
    "superglue": {
        "name": "Superglue",
        "class": "Anti-Personnel Attacker",
        "atk": 2,
        "def": 0,
        "rez": 0,
        "cost": 100,
        "effect": "Enemy Netrunner cannot progress deeper for 1d6 rounds.",
    },
    "vrizzbolt": {
        "name": "Vrizzbolt",
        "class": "Anti-Personnel Attacker",
        "atk": 1,
        "def": 0,
        "rez": 0,
        "cost": 50,
        "effect": "Deal 1d6 brain damage and lower one NET action next turn.",
    },
}

BLACK_ICE = {
    "asp": {"name": "Asp", "class": "Anti-Personnel Black ICE", "per": 4, "spd": 6, "atk": 2, "def": 2, "rez": 15, "cost": 100, "effect": "Destroy one single Program installed on target's Cyberdeck."},
    "giant": {"name": "Giant", "class": "Anti-Personnel Black ICE", "per": 2, "spd": 2, "atk": 8, "def": 4, "rez": 25, "cost": 1000, "effect": "Deal 3d6 brain damage and force immediate unsafe Jack Out."},
    "hellhound": {"name": "Hellhound", "class": "Anti-Personnel Black ICE", "per": 6, "spd": 6, "atk": 6, "def": 2, "rez": 20, "cost": 500, "effect": "Deal 2d6 brain damage and set target on fire until dealt with."},
    "kraken": {"name": "Kraken", "class": "Anti-Personnel Black ICE", "per": 6, "spd": 2, "atk": 8, "def": 4, "rez": 30, "cost": 1000, "effect": "Deal 3d6 brain damage and lock deeper movement/safe Jack Out until end of target's next turn."},
    "liche": {"name": "Liche", "class": "Anti-Personnel Black ICE", "per": 8, "spd": 2, "atk": 6, "def": 2, "rez": 25, "cost": 500, "effect": "Lower INT/REF/DEX each by 1d6 for next hour (minimum 1)."},
    "raven": {"name": "Raven", "class": "Anti-Personnel Black ICE", "per": 6, "spd": 4, "atk": 4, "def": 2, "rez": 15, "cost": 50, "effect": "Derezzes one single Defender Program and deals 1d6 brain damage."},
    "scorpion": {"name": "Scorpion", "class": "Anti-Personnel Black ICE", "per": 2, "spd": 6, "atk": 2, "def": 2, "rez": 15, "cost": 100, "effect": "Lower MOVE by 1d6 for next hour (minimum 1)."},
    "skunk": {"name": "Skunk", "class": "Anti-Personnel Black ICE", "per": 2, "spd": 4, "atk": 4, "def": 2, "rez": 10, "cost": 500, "effect": "Until Derezzed, target Netrunner takes -2 on Slide checks."},
    "wisp": {"name": "Wisp", "class": "Anti-Personnel Black ICE", "per": 4, "spd": 4, "atk": 4, "def": 2, "rez": 15, "cost": 50, "effect": "Deal 1d6 brain damage and lower one NET action next turn."},
    "dragon": {"name": "Dragon", "class": "Anti-Program Black ICE", "per": 6, "spd": 4, "atk": 6, "def": 6, "rez": 30, "cost": 1000, "effect": "Deal 6d6 damage to a Program. Excess destroys instead of derezzing."},
    "killer": {"name": "Killer", "class": "Anti-Program Black ICE", "per": 4, "spd": 8, "atk": 6, "def": 2, "rez": 20, "cost": 500, "effect": "Deal 4d6 damage to a Program. Excess destroys instead of derezzing."},
    "sabertooth": {"name": "Sabertooth", "class": "Anti-Program Black ICE", "per": 8, "spd": 6, "atk": 6, "def": 2, "rez": 25, "cost": 1000, "effect": "Deal 6d6 damage to a Program. Excess destroys instead of derezzing."},
}

DEMONS = {
    "imp": {"name": "Imp", "rez": 15, "interface": 3, "net_actions": 2, "combat_number": 14, "cost": 1000},
    "efreet": {"name": "Efreet", "rez": 25, "interface": 4, "net_actions": 3, "combat_number": 14, "cost": 5000},
    "balron": {"name": "Balron", "rez": 30, "interface": 7, "net_actions": 4, "combat_number": 14, "cost": 10000},
}

ALL_PROGRAMS = {}
ALL_PROGRAMS.update(BOOSTER_PROGRAMS)
ALL_PROGRAMS.update(DEFENDER_PROGRAMS)
ALL_PROGRAMS.update(ATTACKER_PROGRAMS)

DIFFICULTY_DV = {
    "basic": 6,
    "standard": 8,
    "uncommon": 10,
    "advanced": 12,
}

LOBBY_TABLE = {
    1: "file_dv6",
    2: "password_dv6",
    3: "password_dv8",
    4: "skunk",
    5: "wisp",
    6: "killer",
}

BODY_TABLES = {
    "basic": {
        3: "hellhound", 4: "sabertooth", 5: "raven_x2", 6: "hellhound", 7: "wisp", 8: "raven",
        9: "password", 10: "file", 11: "control", 12: "password", 13: "skunk", 14: "asp",
        15: "scorpion", 16: "killer_skunk", 17: "wisp_x3", 18: "liche",
    },
    "standard": {
        3: "hellhound_x2", 4: "hellhound_killer", 5: "skunk_x2", 6: "sabertooth", 7: "scorpion",
        8: "hellhound", 9: "password", 10: "file", 11: "control", 12: "password", 13: "asp",
        14: "killer", 15: "liche", 16: "asp", 17: "raven_x3", 18: "liche_raven",
    },
    "uncommon": {
        3: "kraken", 4: "hellhound_scorpion", 5: "hellhound_killer", 6: "raven_x2", 7: "sabertooth",
        8: "hellhound", 9: "password", 10: "file", 11: "control", 12: "password", 13: "killer",
        14: "liche", 15: "dragon", 16: "asp_raven", 17: "dragon_wisp", 18: "giant",
    },
    "advanced": {
        3: "hellhound_x3", 4: "asp_x2", 5: "hellhound_liche", 6: "wisp_x3", 7: "hellhound_sabertooth",
        8: "kraken", 9: "password", 10: "file", 11: "control", 12: "password", 13: "giant",
        14: "dragon", 15: "killer_scorpion", 16: "kraken", 17: "raven_wisp_hellhound", 18: "dragon_x2",
    },
}

CONTROL_NODE_DEFENSES = [
    "Observation Cameras",
    "Automated Turret",
    "Automated Melee Weapon",
    "Electrical Flooring",
    "Laser Grid",
    "Tanglefoot Flooring",
    "Ground Drone",
    "Large Air Drone",
    "Spider Walking Drone",
]

ACTIVE_DEFENSE_TEMPLATES = {
    "observation_cameras": {
        "name": "Observation Cameras",
        "profile": "hacker",
        "level": "mook",
        "weapon_name": "Sensor Feed",
        "weapon_damage": "0d6",
        "hp": 5,
        "trigger": "Detects intruders and calls response teams.",
        "counter_dv": 9,
        "counter_time_min": 1,
    },
    "tanglefoot_flooring": {
        "name": "Tanglefoot Flooring",
        "profile": "security guard",
        "level": "mook",
        "weapon_name": "Nanowire Snare",
        "weapon_damage": "0d6",
        "hp": 20,
        "trigger": "Reduces MOVE by 1d6 on trigger.",
        "counter_dv": 13,
        "counter_time_min": 1,
    },
    "electrical_flooring": {
        "name": "Electrical Flooring",
        "profile": "security guard",
        "level": "lieutenant",
        "weapon_name": "Grid Shock",
        "weapon_damage": "6d6",
        "hp": 20,
        "trigger": "Body damage (armor reduces, no ablation), repeats while standing on grid.",
        "counter_dv": 13,
        "counter_time_min": 1,
    },
    "laser_grid": {
        "name": "Laser Grid",
        "profile": "security guard",
        "level": "lieutenant",
        "weapon_name": "Laser Lattice",
        "weapon_damage": "4d6",
        "hp": 0,
        "trigger": "Strikes when crossing grid lanes.",
        "counter_dv": 17,
        "counter_time_min": 5,
    },
    "tip_floor": {
        "name": "Tip-Floor",
        "profile": "security guard",
        "level": "mook",
        "weapon_name": "Drop Trap",
        "weapon_damage": "6d6",
        "hp": 0,
        "trigger": "Drops targets into pit traps; DV15 Athletics to avoid.",
        "counter_dv": 13,
        "counter_time_min": 1,
    },
    "goop": {
        "name": "Goop",
        "profile": "security guard",
        "level": "mook",
        "weapon_name": "Polymer Foam",
        "weapon_damage": "0d6",
        "hp": 10,
        "trigger": "Reduces MOVE by 2d6 until escaped or disabled.",
        "counter_dv": 13,
        "counter_time_min": 1,
    },
    "ceiling_wall_punchers": {
        "name": "Ceiling/Wall Punchers",
        "profile": "combat gunner",
        "level": "lieutenant",
        "weapon_name": "Hydraulic Strike Grid",
        "weapon_damage": "6d6",
        "hp": 20,
        "trigger": "Crushes occupants in defended grid.",
        "counter_dv": 13,
        "counter_time_min": 5,
    },
    "slip_floor": {
        "name": "Slip-Floor",
        "profile": "security guard",
        "level": "mook",
        "weapon_name": "Slick Sprayer",
        "weapon_damage": "0d6",
        "hp": 10,
        "trigger": "Forces DV15 Athletics check to avoid going prone on movement.",
        "counter_dv": 13,
        "counter_time_min": 1,
    },
    "stun_panels": {
        "name": "Stun Panels",
        "profile": "hacker",
        "level": "lieutenant",
        "weapon_name": "Flash/Stun Burst",
        "weapon_damage": "0d6",
        "hp": 5,
        "trigger": "DV15 Resist Torture/Drugs or temporary eye/ear critical injuries.",
        "counter_dv": 13,
        "counter_time_min": 1,
    },
    "sleep_gas_elevator": {
        "name": "Sleep Gas Elevator",
        "profile": "hacker",
        "level": "mini-boss",
        "weapon_name": "Sleep Gas Dispersion",
        "weapon_damage": "0d6",
        "hp": 60,
        "trigger": "DV13 Resist Torture/Drugs each round until disabled.",
        "counter_dv": 17,
        "counter_time_min": 5,
    },
    "air_swarm_drone_cloud": {
        "name": "Air Swarm Drone Cloud",
        "profile": "combat gunner",
        "level": "lieutenant",
        "weapon_name": "Drone Swarm Blades",
        "weapon_damage": "4d6",
        "hp": 15,
        "move": 8,
        "trigger": "Damages targets when entering or sharing area.",
        "counter_dv": 17,
        "counter_time_min": 5,
    },
    "ground_drone": {
        "name": "Ground Drone",
        "profile": "combat gunner",
        "level": "mook",
        "weapon_name": "Mounted Weapon",
        "weapon_damage": "4d6",
        "hp": 15,
        "move": 8,
        "trigger": "Mobile ground security platform.",
        "counter_dv": 17,
        "counter_time_min": 5,
    },
    "large_air_drone": {
        "name": "Large Air Drone",
        "profile": "combat gunner",
        "level": "lieutenant",
        "weapon_name": "Aerial Payload",
        "weapon_damage": "4d6",
        "hp": 15,
        "move": 8,
        "trigger": "Patrol drone with ranged payloads.",
        "counter_dv": 17,
        "counter_time_min": 5,
    },
    "mini_air_drone": {
        "name": "Mini Air Drone",
        "profile": "combat gunner",
        "level": "lieutenant",
        "weapon_name": "Mini Drone Payload",
        "weapon_damage": "4d6",
        "hp": 20,
        "move": 6,
        "trigger": "Compact strike drone.",
        "counter_dv": 21,
        "counter_time_min": 5,
    },
    "spider_walking_drone": {
        "name": "Spider Walking Drone",
        "profile": "combat gunner",
        "level": "lieutenant",
        "weapon_name": "Spider Drone Armament",
        "weapon_damage": "5d6",
        "hp": 15,
        "move": 6,
        "trigger": "Tracked assault drone; can carry launchers or melee tools.",
        "counter_dv": 17,
        "counter_time_min": 5,
    },
    "automated_blood_swarm": {
        "name": "Automated Blood Swarm",
        "profile": "hacker",
        "level": "mini-boss",
        "weapon_name": "Nanite Blood Swarm",
        "weapon_damage": "3d6",
        "hp": 0,
        "trigger": "Auto-hit cloud, DV15 Resist Torture/Drugs or direct 3d6 HP.",
        "counter_dv": 21,
        "counter_time_min": 5,
    },
    "automated_melee_weapon": {
        "name": "Automated Melee Weapon",
        "profile": "martial artist",
        "level": "lieutenant",
        "weapon_name": "Automated Melee Tool",
        "weapon_damage": "4d6",
        "hp": 25,
        "trigger": "Fixed heavy melee device in defended area.",
        "counter_dv": 17,
        "counter_time_min": 5,
    },
    "automated_turret": {
        "name": "Automated Turret",
        "profile": "combat gunner",
        "level": "lieutenant",
        "weapon_name": "Automated Turret",
        "weapon_damage": "5d6",
        "hp": 25,
        "trigger": "Autonomous ranged weapon emplacement.",
        "counter_dv": 17,
        "counter_time_min": 5,
    },
}


def normalize_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def get_program(name: str) -> Optional[dict]:
    return ALL_PROGRAMS.get(normalize_name(name))


def get_black_ice(name: str) -> Optional[dict]:
    return BLACK_ICE.get(normalize_name(name))


def get_demon(name: str) -> Optional[dict]:
    return DEMONS.get(normalize_name(name))


def get_active_defense_template(name: str) -> Optional[dict]:
    return ACTIVE_DEFENSE_TEMPLATES.get(normalize_name(name))


def get_interface_rank(character) -> int:
    """Get Interface rank from character sheet (for Netrunners) or skills."""
    sheet = getattr(character, "character_sheet", None)
    if sheet:
        return int(getattr(sheet, "interface", 0) or 0)
    # Fallback for db-based characters
    role_ability = getattr(character.db, "role_ability", None) or {}
    if isinstance(role_ability, dict) and (role_ability.get("name") or "").lower() == "interface":
        return int(role_ability.get("rank", 0) or 0)
    skills = getattr(character.db, "skills", None) or {}
    return int(skills.get("interface", 0) or 0)


def net_actions_for_rank(interface_rank: int) -> int:
    if interface_rank >= 10:
        return 5
    if interface_rank >= 7:
        return 4
    if interface_rank >= 4:
        return 3
    if interface_rank >= 1:
        return 2
    return 0


def roll_d10() -> int:
    return random.randint(1, 10)


def _format_interface_dice(details: dict, bonus: int = 0) -> str:
    """Format dice part for interface check display."""
    segments = [str(details["first_roll"])]
    for roll_val, added in details.get("extra_rolls", []):
        if added:
            segments.append(f"+ {roll_val} (crit)")
        else:
            segments.append(f"- {roll_val} (fumble: 2nd d10 = {roll_val})")
    if bonus != 0:
        segments.append(f"+ {bonus}" if bonus > 0 else f"- {-bonus}")
    return " ".join(segments)


def interface_check(character, bonus: int = 0) -> Tuple[int, int, int, dict]:
    """
    Interface check: rank + 1d10 + bonus, with critical success/failure rules.
    Returns (total, rank, first_roll, details).
    details has: first_roll, is_crit_success, is_crit_failure, extra_rolls, dice_total.
    """
    from world.utils.roll_utils import roll_d10_with_crits

    rank = get_interface_rank(character)
    dice_total, first_roll, is_crit_success, is_crit_failure, extra_rolls = roll_d10_with_crits()
    total = rank + dice_total + bonus
    details = {
        "first_roll": first_roll,
        "dice_total": dice_total,
        "is_crit_success": is_crit_success,
        "is_crit_failure": is_crit_failure,
        "extra_rolls": extra_rolls,
    }
    return total, rank, first_roll, details


def _floor_from_token(token: str, floor_num: int, default_dv: int) -> dict:
    if token.startswith("password"):
        dv = 6 if token.endswith("dv6") else 8 if token.endswith("dv8") else default_dv
        return {"floor": floor_num, "type": "password", "name": "Password", "dv": dv}
    if token.startswith("file"):
        dv = 6 if token.endswith("dv6") else default_dv
        return {"floor": floor_num, "type": "file", "name": "File", "dv": dv}
    if token == "control":
        return {"floor": floor_num, "type": "control", "name": f"Control Node {floor_num}", "dv": default_dv}
    if token in BLACK_ICE:
        return {"floor": floor_num, "type": "black_ice", "name": BLACK_ICE[token]["name"], "dv": None}
    if "_x" in token or "_" in token:
        parts = token.split("_")
        names = []
        idx = 0
        while idx < len(parts):
            part = parts[idx]
            if part in BLACK_ICE:
                count = 1
                if idx + 1 < len(parts):
                    nxt = parts[idx + 1]
                    if nxt.startswith("x") and nxt[1:].isdigit():
                        count = max(1, int(nxt[1:]))
                        idx += 1
                names.extend([BLACK_ICE[part]["name"]] * count)
            idx += 1
        if len(names) == 1:
            return {"floor": floor_num, "type": "black_ice", "name": names[0], "dv": None}
        if names:
            return {"floor": floor_num, "type": "black_ice_group", "name": ", ".join(names), "dv": None}
    return {"floor": floor_num, "type": "misc", "name": token.replace("_", " ").title(), "dv": None}


def _split_branch_lengths(total_floors: int, branch_count: int) -> Tuple[int, List[int]]:
    """
    Split total node count into one guaranteed-longest main branch + side branches.
    """
    main_len = 3
    branch_lengths = [2 for _ in range(branch_count)]
    remaining = total_floors - main_len - sum(branch_lengths)
    buckets = ["main"] + [f"b{i+1}" for i in range(branch_count)]
    while remaining > 0:
        pick = random.choice(buckets)
        if pick == "main":
            main_len += 1
        else:
            idx = int(pick[1:]) - 1
            branch_lengths[idx] += 1
        remaining -= 1
    if branch_lengths:
        # Ensure main is strictly longest.
        while main_len <= max(branch_lengths):
            src_idx = max(range(len(branch_lengths)), key=lambda i: branch_lengths[i])
            if branch_lengths[src_idx] <= 2:
                main_len += 1
                break
            branch_lengths[src_idx] -= 1
            main_len += 1
    return main_len, branch_lengths


def _pick_token_for_depth(depth: int, difficulty: str) -> str:
    if depth <= 2:
        roll = random.randint(1, 6)
        return LOBBY_TABLE[roll]
    roll = sum(random.randint(1, 6) for _ in range(3))
    return BODY_TABLES[difficulty].get(roll, "file")


def generate_demon_for_architecture(difficulty: str, floor_count: int) -> Optional[dict]:
    """
    Lightweight demon generator:
      - none on tiny architectures
      - one demon on 6+ floors, scaling by difficulty
    """
    if int(floor_count or 0) < 6:
        return None
    d = normalize_name(difficulty or "standard")
    if d == "basic":
        choice = "imp"
    elif d == "standard":
        choice = "efreet" if random.randint(1, 10) >= 7 else "imp"
    elif d == "uncommon":
        choice = random.choice(["imp", "efreet", "efreet", "balron"])
    else:
        choice = random.choice(["efreet", "balron", "balron"])
    demon = dict(DEMONS[choice])
    demon["name"] = demon.get("name", choice.title())
    return demon


def generate_architecture(difficulty: str = "standard", floor_count: Optional[int] = None) -> List[dict]:
    difficulty = normalize_name(difficulty)
    if difficulty not in BODY_TABLES:
        difficulty = "standard"
    dv = DIFFICULTY_DV[difficulty]
    if floor_count is None:
        floor_count = sum(random.randint(1, 6) for _ in range(3))
    floor_count = max(3, min(18, int(floor_count)))

    # Determine branch count: roll d10; 7+ adds a branch; repeat until fail.
    branch_count = 0
    while branch_count < 4 and random.randint(1, 10) >= 7:
        branch_count += 1
    max_branches_for_size = max(0, (floor_count - 3) // 2)
    branch_count = min(branch_count, max_branches_for_size)
    main_len, branch_lengths = _split_branch_lengths(floor_count, branch_count)

    nodes = []
    children_map: Dict[int, List[int]] = {}

    # Build main chain.
    node_id = 1
    prev = None
    for depth in range(1, main_len + 1):
        nodes.append(
            {
                "floor": node_id,
                "parent": prev,
                "children": [],
                "depth": depth,
                "branch": "main",
            }
        )
        if prev is not None:
            children_map.setdefault(prev, []).append(node_id)
        prev = node_id
        node_id += 1

    # Build side branches attached after floor 2 on main.
    attach_candidates = list(range(3, max(4, main_len)))
    for bidx, blen in enumerate(branch_lengths, start=1):
        attach = random.choice(attach_candidates) if attach_candidates else 2
        parent = attach
        attach_depth = next(n["depth"] for n in nodes if n["floor"] == attach)
        for hop in range(1, blen + 1):
            nodes.append(
                {
                    "floor": node_id,
                    "parent": parent,
                    "children": [],
                    "depth": attach_depth + hop,
                    "branch": f"branch_{bidx}",
                }
            )
            children_map.setdefault(parent, []).append(node_id)
            parent = node_id
            node_id += 1

    node_lookup = {n["floor"]: n for n in nodes}
    for parent, kids in children_map.items():
        node_lookup[parent]["children"] = list(kids)

    # Choose a single, deterministic bottom node (deepest; tiebreak by highest floor id).
    bottom_node = sorted(nodes, key=lambda n: (int(n["depth"]), int(n["floor"])))[-1]["floor"]

    floors: List[dict] = []
    for node in sorted(nodes, key=lambda n: n["floor"]):
        token = _pick_token_for_depth(int(node["depth"]), difficulty)
        floor = _floor_from_token(token, int(node["floor"]), dv)
        floor["parent"] = node.get("parent")
        floor["children"] = list(node.get("children") or [])
        floor["depth"] = int(node.get("depth", 1))
        floor["branch"] = node.get("branch", "main")
        floor["is_bottom"] = int(node["floor"]) == int(bottom_node)
        if floor.get("type") == "control":
            floor["defense"] = random.choice(CONTROL_NODE_DEFENSES)
        floors.append(floor)
    return floors


def generate_paydata_entry(difficulty: str, floor_number: int) -> dict:
    difficulty = normalize_name(difficulty)
    base_values = {
        "basic": (100, 500),
        "standard": (500, 1500),
        "uncommon": (1500, 5000),
        "advanced": (5000, 10000),
    }
    low, high = base_values.get(difficulty, base_values["standard"])
    value = random.randint(low, high) + (floor_number * random.randint(10, 75))
    dv = DIFFICULTY_DV.get(difficulty, 8)
    tags = ["financial", "research", "blackmail", "operations", "security", "personnel"]
    return {
        "label": f"{random.choice(tags).title()} Package F{floor_number}",
        "value": value,
        "dv": dv,
        "claimed_by": [],
    }
