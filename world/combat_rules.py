"""
Cyberpunk RED combat rules: range DVs, weapon type mapping, armor locations.
"""

# Single Shot DVs by Range (meters) - from CPR core rulebook
# Keys: range table type; values: (min, max) -> DV. None = N/A
RANGE_DV_TABLE = {
    "pistol": {
        (0, 6): 13,
        (7, 12): 15,
        (13, 25): 20,
        (26, 50): 25,
        (51, 100): 30,
        (101, 200): 30,
        (201, 400): None,
        (401, 800): None,
    },
    "smg": {
        (0, 6): 15,
        (7, 12): 13,
        (13, 25): 15,
        (26, 50): 20,
        (51, 100): 25,
        (101, 200): 25,
        (201, 400): 30,
        (401, 800): None,
    },
    "shotgun": {
        (0, 6): 13,
        (7, 12): 15,
        (13, 25): 20,
        (26, 50): 25,
        (51, 100): 30,
        (101, 200): 35,
        (201, 400): None,
        (401, 800): None,
    },
    "assault_rifle": {
        (0, 6): 17,
        (7, 12): 16,
        (13, 25): 15,
        (26, 50): 13,
        (51, 100): 15,
        (101, 200): 20,
        (201, 400): 25,
        (401, 800): 30,
    },
    "sniper_rifle": {
        (0, 6): 30,
        (7, 12): 25,
        (13, 25): 25,
        (26, 50): 20,
        (51, 100): 15,
        (101, 200): 16,
        (201, 400): 17,
        (401, 800): 20,
    },
    "bows_crossbow": {
        (0, 6): 15,
        (7, 12): 13,
        (13, 25): 15,
        (26, 50): 17,
        (51, 100): 20,
        (101, 200): 22,
        (201, 400): None,
        (401, 800): None,
    },
    "grenade_launcher": {
        (0, 6): 16,
        (7, 12): 15,
        (13, 25): 15,
        (26, 50): 17,
        (51, 100): 20,
        (101, 200): 22,
        (201, 400): 25,
        (401, 800): None,
    },
    "rocket_launcher": {
        (0, 6): 17,
        (7, 12): 16,
        (13, 25): 15,
        (26, 50): 15,
        (51, 100): 20,
        (101, 200): 20,
        (201, 400): 25,
        (401, 800): 30,
    },
}

# Autofire DVs by Range - from CPR core rulebook
AUTOFIRE_RANGE_DV_TABLE = {
    "smg": {(0, 6): 20, (7, 12): 17, (13, 25): 20, (26, 50): 25, (51, 100): 30},
    "assault_rifle": {(0, 6): 22, (7, 12): 20, (13, 25): 17, (26, 50): 20, (51, 100): 25},
}

# Weapon name (lowercase) -> range table type for single shot
WEAPON_TO_RANGE_TYPE = {
    "shotgun": "shotgun",
    "sniper rifle": "sniper_rifle",
    "assault rifle": "assault_rifle",
    "smg": "smg",
    "heavy smg": "smg",
    "grenade launcher": "grenade_launcher",
    "rocket launcher": "rocket_launcher",
    "flamethrower": "grenade_launcher",  # splash, use GL range
    "bow": "bows_crossbow",
    "crossbow": "bows_crossbow",
}

# Category fallback when weapon name not in map
CATEGORY_TO_RANGE_TYPE = {
    "handgun": "pistol",
    "smg": "smg",
    "shoulder_arms": "assault_rifle",  # default; override by name
    "heavy_weapons": "grenade_launcher",
    "archery": "bows_crossbow",
}

# Autofire multiplier: SMG=3, Assault Rifle=4
AUTOFIRE_MULTIPLIER = {
    "smg": 3,
    "heavy smg": 3,
    "assault rifle": 4,
}

# Point blank range (meters) - within this, target can dodge
POINT_BLANK_RANGE = 6

# Armor location names (for aimed shots)
ARMOR_LOCATIONS = ("head", "body", "arms", "legs")


def _weapon_to_range_type(weapon_name, weapon_category):
    """Resolve range table type from weapon name and category."""
    name_lower = (weapon_name or "").strip().lower()
    cat_lower = (weapon_category or "").strip().lower()
    for key, rtype in WEAPON_TO_RANGE_TYPE.items():
        if key in name_lower:
            return rtype
    return CATEGORY_TO_RANGE_TYPE.get(cat_lower, "pistol")


def get_dv_for_range(weapon_name, weapon_category, distance_meters, autofire=False):
    """
    Get DV for a ranged attack at given distance.
    Returns (dv, range_type) or (None, range_type) if out of range.
    """
    range_type = _weapon_to_range_type(weapon_name, weapon_category)
    table = AUTOFIRE_RANGE_DV_TABLE if autofire else RANGE_DV_TABLE
    bands = table.get(range_type)
    if not bands and autofire:
        bands = AUTOFIRE_RANGE_DV_TABLE.get("smg", {})
    if not bands:
        bands = RANGE_DV_TABLE.get(range_type, RANGE_DV_TABLE["pistol"])
    dist = int(distance_meters)
    for (lo, hi), dv in sorted(bands.items()):
        if lo <= dist <= hi:
            return (dv, range_type) if dv is not None else (None, range_type)
    return (None, range_type)


def get_weapon_range_type(weapon_name, weapon_category):
    """Get range table type for weapon."""
    name_lower = (weapon_name or "").strip().lower()
    cat_lower = (weapon_category or "").strip().lower()
    return WEAPON_TO_RANGE_TYPE.get(name_lower) or CATEGORY_TO_RANGE_TYPE.get(cat_lower, "pistol")


def is_splash_weapon(weapon_name, weapon_category=None):
    """True if weapon affects a zone (grenade, rocket, flamethrower) - 10m area."""
    name_lower = (weapon_name or "").strip().lower()
    return "grenade launcher" in name_lower or "rocket launcher" in name_lower or "flamethrower" in name_lower


def is_shotgun_zone_weapon(weapon_name, weapon_category=None):
    """True if weapon is shotgun (6m cone, shell damage 3d6)."""
    name_lower = (weapon_name or "").strip().lower()
    return "shotgun" in name_lower


def is_autofire_capable(weapon_name, weapon_category):
    """True if weapon can use autofire (SMG, Assault Rifle)."""
    name_lower = (weapon_name or "").strip().lower()
    cat_lower = (weapon_category or "").strip().lower()
    return "smg" in name_lower or "assault rifle" in name_lower or cat_lower == "handgun" and "smg" in name_lower
