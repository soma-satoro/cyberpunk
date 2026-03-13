"""
Solo of Fortune 2045 (Interface RED Volume 5) expanded range tables.

Range brackets in meters/yards: 0-6, 7-12, 13-25, 26-50, 51-100, 101-200, 201-400, 401-800.
Each weapon category has single-shot DVs and optionally autofire DVs per bracket.
"""

# Range bracket keys (meters/yards)
RANGE_BRACKETS = [
    (0, 6), (7, 12), (13, 25), (26, 50), (51, 100), (101, 200), (201, 400), (401, 800),
]

# Weapon category -> (single_shot_dvs, autofire_dvs) per bracket
# DVs from Interface RED Vol 5 Solo of Fortune 2045
RANGE_TABLES = {
    "snubnose_pistol": {
        "single": [13, 15, 17, 19, 21, 23, 25, 27],
        "autofire": None,
    },
    "pistol": {
        "single": [13, 15, 17, 19, 21, 23, 25, 27],
        "autofire": [17, 19, 21, 23, 25, 27, 29, 31],
    },
    "long_barrel_pistol": {
        "single": [13, 13, 15, 17, 19, 21, 23, 25],
        "autofire": [17, 17, 19, 21, 23, 25, 27, 29],
    },
    "smg": {
        "single": [13, 15, 17, 19, 21, 23, 25, 27],
        "autofire": [17, 19, 21, 23, 25, 27, 29, 31],
    },
    "shotgun": {
        "single": [13, 15, 17, 19, 21, 23, 25, 27],
        "autofire": [17, 19, 21, 23, 25, 27, 29, 31],
    },
    "assault_rifle": {
        "single": [13, 13, 15, 17, 19, 21, 23, 25],
        "autofire": [17, 17, 19, 21, 23, 25, 27, 29],
    },
    "sniper_rifle": {
        "single": [13, 13, 13, 15, 17, 19, 21, 23],
        "autofire": None,
    },
    "bow": {
        "single": [13, 15, 17, 19, 21, 23, 25, 27],
        "autofire": None,
    },
    "crossbow": {
        "single": [13, 13, 15, 17, 19, 21, 23, 25],
        "autofire": None,
    },
    "machine_gun": {
        "single": [13, 13, 15, 17, 19, 21, 23, 25],
        "autofire": [17, 17, 19, 21, 23, 25, 27, 29],
    },
    "handgun": {
        "single": [13, 15, 17, 19, 21, 23, 25, 27],
        "autofire": [17, 19, 21, 23, 25, 27, 29, 31],
    },
    "shoulder_arms": {
        "single": [13, 13, 15, 17, 19, 21, 23, 25],
        "autofire": [17, 17, 19, 21, 23, 25, 27, 29],
    },
    "archery": {
        "single": [13, 15, 17, 19, 21, 23, 25, 27],
        "autofire": None,
    },
    "heavy_weapons": {
        "single": [13, 13, 15, 17, 19, 21, 23, 25],
        "autofire": None,
    },
}


def get_dv_for_range(weapon_category: str, range_meters: int, autofire: bool = False) -> int | None:
    """
    Return the DV for a given weapon category and range.
    Uses Solo of Fortune 2045 expanded range tables.
    """
    table = RANGE_TABLES.get(weapon_category)
    if not table:
        return None
    mode = "autofire" if autofire and table.get("autofire") else "single"
    dvs = table.get(mode)
    if not dvs:
        return None
    for i, (lo, hi) in enumerate(RANGE_BRACKETS):
        if lo <= range_meters <= hi:
            return dvs[i]
    return dvs[-1] if range_meters > RANGE_BRACKETS[-1][1] else dvs[0]
