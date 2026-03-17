"""
Did Someone Say Murder? - Investigation System (Interface RED Vol 5)
Constants: Focus formula, clue types, complexity tiers, obfuscation.
"""

import math

# Focus formula: 10 + 5 * ceil((INT + WILL) / 2)
def calculate_max_focus(intelligence: int, willpower: int) -> int:
    return 10 + 5 * math.ceil((intelligence + willpower) / 2)


# Focus table: WILL (rows) x INT (cols) -> max Focus. INT/WILL 2-10.
FOCUS_TABLE = {
    (2, 2): 20, (2, 3): 25, (2, 4): 25, (2, 5): 30, (2, 6): 30, (2, 7): 35, (2, 8): 35, (2, 9): 40, (2, 10): 40,
    (3, 2): 25, (3, 3): 25, (3, 4): 30, (3, 5): 30, (3, 6): 35, (3, 7): 35, (3, 8): 40, (3, 9): 40, (3, 10): 45,
    (4, 2): 25, (4, 3): 30, (4, 4): 30, (4, 5): 35, (4, 6): 35, (4, 7): 40, (4, 8): 40, (4, 9): 45, (4, 10): 45,
    (5, 2): 30, (5, 3): 30, (5, 4): 35, (5, 5): 35, (5, 6): 40, (5, 7): 40, (5, 8): 45, (5, 9): 45, (5, 10): 50,
    (6, 2): 30, (6, 3): 35, (6, 4): 35, (6, 5): 40, (6, 6): 40, (6, 7): 45, (6, 8): 45, (6, 9): 50, (6, 10): 50,
    (7, 2): 35, (7, 3): 35, (7, 4): 40, (7, 5): 40, (7, 6): 45, (7, 7): 45, (7, 8): 50, (7, 9): 50, (7, 10): 55,
    (8, 2): 35, (8, 3): 40, (8, 4): 40, (8, 5): 45, (8, 6): 45, (8, 7): 50, (8, 8): 50, (8, 9): 55, (8, 10): 55,
    (9, 2): 40, (9, 3): 40, (9, 4): 45, (9, 5): 45, (9, 6): 50, (9, 7): 50, (9, 8): 55, (9, 9): 55, (9, 10): 60,
    (10, 2): 40, (10, 3): 45, (10, 4): 45, (10, 5): 50, (10, 6): 50, (10, 7): 55, (10, 8): 55, (10, 9): 60, (10, 10): 60,
}


def get_max_focus(intelligence: int, willpower: int) -> int:
    """Look up max Focus from table; bounds INT/WILL to 2-10."""
    i = max(2, min(10, intelligence))
    w = max(2, min(10, willpower))
    return FOCUS_TABLE.get((w, i), calculate_max_focus(i, w))


# Complexity tiers
COMPLEXITY_TIERS = {
    "easy": {"value": 25, "description": "One part of a single Mission (e.g., Night Market location)."},
    "average": {"value": 50, "description": "Basis of or large part of a single Mission."},
    "challenging": {"value": 100, "description": "Ongoing over multiple Missions."},
    "difficult": {"value": 150, "description": "Important subplot for campaign or Edgerunner."},
    "legendary": {"value": 200, "description": "Underpins the whole campaign."},
}

# Obfuscation levels
OBFUSCATION_LEVELS = {
    "none": {"value": 0, "description": "Fresh witness, complete recording."},
    "light": {"value": 2, "description": "Drunk witness, partial recording."},
    "heavy": {"value": 4, "description": "Secondhand account, poor-quality recording."},
    "near_total": {"value": 6, "description": "Rumor, poor and incomplete recording."},
}

# Clue types: type -> damage_dice, focus_damage_dice, fumble_effect
CLUE_TYPES = {
    "auditing": {
        "skills": ["accounting", "bureaucracy"],
        "damage_dice": "3d6",
        "focus_damage_dice": "2d6",
        "fumble_effect": None,
    },
    "autopsy": {
        "skills": ["paramedic"],
        "damage_dice": "4d6",
        "focus_damage_dice": "3d6",
        "fumble_effect": "Body damaged; further Evidence Checks -4.",
    },
    "chemical_analysis": {
        "skills": ["basic_tech"],
        "damage_dice": "3d6",
        "focus_damage_dice": "2d6",
        "fumble_effect": "Sample destroyed.",
    },
    "deciphering": {
        "skills": ["cryptography"],
        "damage_dice": "2d6",
        "focus_damage_dice": "1d6",
        "fumble_effect": None,
    },
    "digital_scavenging": {
        "skills": ["electronics_security_tech"],
        "damage_dice": "4d6",
        "focus_damage_dice": "3d6",
        "fumble_effect": "Device destroyed.",
    },
    "forensics": {
        "skills": ["criminology", "deduction"],
        "damage_dice": "4d6",
        "focus_damage_dice": "3d6",
        "fumble_effect": "Evidence destroyed beyond repair.",
    },
    "gossip": {
        "skills": ["conversation", "persuasion", "streetwise"],
        "damage_dice": "2d6",
        "focus_damage_dice": "1d6",
        "fumble_effect": None,
    },
    "interrogation": {
        "skills": ["human_perception", "interrogation"],
        "damage_dice": "3d6",
        "focus_damage_dice": "2d6",
        "fumble_effect": "Cannot retry by any Crew member.",
    },
    "observation": {
        "skills": ["human_perception", "perception"],
        "damage_dice": "2d6",
        "focus_damage_dice": "1d6",
        "fumble_effect": None,
    },
    "research": {
        "skills": ["education", "library_search"],
        "damage_dice": "2d6",
        "focus_damage_dice": "1d6",
        "fumble_effect": None,
    },
    "tailing": {
        "skills": ["stealth"],
        "damage_dice": "3d6",
        "focus_damage_dice": "2d6",
        "fumble_effect": "Subject becomes aggressive/scared.",
    },
    "tracking": {
        "skills": ["tracking"],
        "damage_dice": "2d6",
        "focus_damage_dice": "1d6",
        "fumble_effect": None,
    },
}

# Obstacle types (for reference)
OBSTACLE_TYPES = [
    "Authority", "Cultural Disputes", "Digital", "Distraction", "Fatigue",
    "Legal", "Location", "Misdirection", "Missing Clue", "Red Herring",
    "Social Engineering", "Technological", "Territory Disputes", "Ticking Clock",
]
