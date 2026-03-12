"""
Cyberpunk RED netrunning data and helper mechanics.

This module centralizes:
- Program and Black ICE catalogs
- Architecture generation tables
- Interface/NET action math helpers
- Paydata generation
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
        "effect": "Reduce first Non-Black ICE attacker damage by 1 while Rezzed.",
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
        "effect": "Deal 3d6 REZ to Black ICE or 2d6 REZ to non-Black ICE Program.",
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
    "asp": {
        "name": "Asp",
        "class": "Anti-Personnel Black ICE",
        "per": 4,
        "spd": 6,
        "atk": 2,
        "def": 2,
        "rez": 15,
        "cost": 100,
        "effect": "Destroy one single Program installed on target's Cyberdeck.",
    },
    "giant": {
        "name": "Giant",
        "class": "Anti-Personnel Black ICE",
        "per": 2,
        "spd": 2,
        "atk": 8,
        "def": 4,
        "rez": 25,
        "cost": 1000,
        "effect": "Deal 3d6 brain damage and force immediate unsafe Jack Out.",
    },
    "hellhound": {
        "name": "Hellhound",
        "class": "Anti-Personnel Black ICE",
        "per": 6,
        "spd": 6,
        "atk": 6,
        "def": 2,
        "rez": 20,
        "cost": 500,
        "effect": "Deal 2d6 brain damage and set target on fire until dealt with.",
    },
    "kraken": {
        "name": "Kraken",
        "class": "Anti-Personnel Black ICE",
        "per": 6,
        "spd": 2,
        "atk": 8,
        "def": 4,
        "rez": 30,
        "cost": 1000,
        "effect": "Deal 3d6 brain damage and force immediate unsafe Jack Out.",
    },
    "liche": {
        "name": "Liche",
        "class": "Anti-Personnel Black ICE",
        "per": 8,
        "spd": 2,
        "atk": 6,
        "def": 2,
        "rez": 25,
        "cost": 500,
        "effect": "Lower INT/REF/DEX each by 1d6 for next hour (minimum 1).",
    },
    "raven": {
        "name": "Raven",
        "class": "Anti-Personnel Black ICE",
        "per": 6,
        "spd": 4,
        "atk": 4,
        "def": 2,
        "rez": 15,
        "cost": 50,
        "effect": "Derezzes one single Defender Program and deals 1d6 brain damage.",
    },
    "scorpion": {
        "name": "Scorpion",
        "class": "Anti-Personnel Black ICE",
        "per": 2,
        "spd": 6,
        "atk": 2,
        "def": 2,
        "rez": 15,
        "cost": 100,
        "effect": "Lower MOVE by 1d6 for next hour (minimum 1).",
    },
    "skunk": {
        "name": "Skunk",
        "class": "Anti-Personnel Black ICE",
        "per": 2,
        "spd": 4,
        "atk": 2,
        "def": 4,
        "rez": 10,
        "cost": 500,
        "effect": "Until next turn's beginning, all slide checks at -2.",
    },
    "wisp": {
        "name": "Wisp",
        "class": "Anti-Personnel Black ICE",
        "per": 4,
        "spd": 4,
        "atk": 4,
        "def": 2,
        "rez": 15,
        "cost": 50,
        "effect": "Deal 1d6 brain damage and lower one NET action next turn.",
    },
    "dragon": {
        "name": "Dragon",
        "class": "Anti-Program Black ICE",
        "per": 6,
        "spd": 4,
        "atk": 6,
        "def": 6,
        "rez": 30,
        "cost": 1000,
        "effect": "Deal 6d6 damage to a Program. Excess destroys instead of derezzing.",
    },
    "killer": {
        "name": "Killer",
        "class": "Anti-Program Black ICE",
        "per": 4,
        "spd": 8,
        "atk": 6,
        "def": 2,
        "rez": 20,
        "cost": 500,
        "effect": "Deal 6d6 damage to a Program. Excess destroys instead of derezzing.",
    },
    "sabertooth": {
        "name": "Sabertooth",
        "class": "Anti-Program Black ICE",
        "per": 8,
        "spd": 6,
        "atk": 6,
        "def": 2,
        "rez": 25,
        "cost": 1000,
        "effect": "Deal 6d6 damage to a Program. Excess destroys instead of derezzing.",
    },
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
        3: "hellhound",
        4: "sabertooth",
        5: "raven_x2",
        6: "hellhound",
        7: "wisp",
        8: "raven",
        9: "password",
        10: "file",
        11: "control",
        12: "password",
        13: "skunk",
        14: "asp",
        15: "scorpion",
        16: "killer_skunk",
        17: "wisp_x3",
        18: "liche",
    },
    "standard": {
        3: "hellhound_x2",
        4: "hellhound_killer",
        5: "skunk_x2",
        6: "sabertooth",
        7: "scorpion",
        8: "hellhound",
        9: "password",
        10: "file",
        11: "control",
        12: "password",
        13: "asp",
        14: "killer",
        15: "liche",
        16: "asp",
        17: "raven_x3",
        18: "liche_raven",
    },
    "uncommon": {
        3: "kraken",
        4: "hellhound_scorpion",
        5: "hellhound_killer",
        6: "raven_x2",
        7: "sabertooth",
        8: "hellhound",
        9: "password",
        10: "file",
        11: "control",
        12: "password",
        13: "killer",
        14: "liche",
        15: "dragon",
        16: "asp_raven",
        17: "dragon_wisp",
        18: "giant",
    },
    "advanced": {
        3: "hellhound_x3",
        4: "asp_x2",
        5: "hellhound_liche",
        6: "wisp_x3",
        7: "hellhound_sabertooth",
        8: "kraken",
        9: "password",
        10: "file",
        11: "control",
        12: "password",
        13: "giant",
        14: "dragon",
        15: "killer_scorpion",
        16: "kraken",
        17: "raven_wisp_hellhound",
        18: "dragon_x2",
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


def get_interface_rank(character) -> int:
    role_ability = character.db.role_ability or {}
    if (role_ability.get("name") or "").lower() == "interface":
        return int(role_ability.get("rank", 0) or 0)
    return int(character.get_skill("interface") or 0)


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


def interface_check(character, bonus: int = 0) -> Tuple[int, int, int]:
    rank = get_interface_rank(character)
    die = roll_d10()
    return rank + die + bonus, rank, die


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
        for part in parts:
            if part == "x2" or part == "x3":
                continue
            if part in BLACK_ICE:
                names.append(BLACK_ICE[part]["name"])
        if names:
            return {"floor": floor_num, "type": "black_ice_group", "name": ", ".join(names), "dv": None}
    return {"floor": floor_num, "type": "misc", "name": token.replace("_", " ").title(), "dv": None}


def generate_architecture(difficulty: str = "standard", floor_count: Optional[int] = None) -> List[dict]:
    difficulty = normalize_name(difficulty)
    if difficulty not in BODY_TABLES:
        difficulty = "standard"
    dv = DIFFICULTY_DV[difficulty]
    if floor_count is None:
        floor_count = sum(random.randint(1, 6) for _ in range(3))
    floor_count = max(3, min(18, int(floor_count)))

    floors = []
    for floor in range(1, floor_count + 1):
        if floor <= 2:
            roll = random.randint(1, 6)
            token = LOBBY_TABLE[roll]
        else:
            roll = sum(random.randint(1, 6) for _ in range(3))
            token = BODY_TABLES[difficulty].get(roll, "file")
        floors.append(_floor_from_token(token, floor, dv))
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

