"""
Cyberpunk RED wound states, critical injuries, and cover data.
"""

# Wound state thresholds and effects
WOUND_SLIGHTLY = "slightly_wounded"  # < full HP
WOUND_SERIOUSLY = "seriously_wounded"  # < half HP (rounded up)
WOUND_MORTALLY = "mortally_wounded"  # < 1 HP
WOUND_DEAD = "dead"  # failed death save

STABILIZATION_DV = {
    WOUND_SLIGHTLY: 10,
    WOUND_SERIOUSLY: 13,
    WOUND_MORTALLY: 15,
    WOUND_DEAD: None,
}

# Critical Injuries to the Body (roll 2d6)
# quick_fix: {"skill": "first_aid"|"paramedic", "dv": N} or None if N/A
# treatment: {"paramedic": N, "surgery": N} - one or both; surgery is Medtech-only
CRITICAL_INJURIES_BODY = {
    2: {"name": "Dismembered Arm", "death_save_penalty": 1, "effect": "drop_arm_hand",
        "quick_fix": None, "treatment": {"surgery": 17}},
    3: {"name": "Dismembered Hand", "death_save_penalty": 1, "effect": "drop_hand",
        "quick_fix": None, "treatment": {"surgery": 17}},
    4: {"name": "Collapsed Lung", "death_save_penalty": 1, "effect": "move_penalty_2",
        "quick_fix": {"skill": "paramedic", "dv": 15}, "treatment": {"surgery": 15}},
    5: {"name": "Broken Ribs", "death_save_penalty": 0, "effect": "re_suffer_on_move",
        "quick_fix": {"skill": "paramedic", "dv": 13}, "treatment": {"paramedic": 15, "surgery": 13}},
    6: {"name": "Broken Arm", "death_save_penalty": 0, "effect": "drop_arm",
        "quick_fix": {"skill": "paramedic", "dv": 13}, "treatment": {"paramedic": 15, "surgery": 13}},
    7: {"name": "Foreign Object", "death_save_penalty": 0, "effect": "re_suffer_on_move",
        "quick_fix": {"skill": "first_aid", "dv": 13}, "treatment": {"paramedic": 13, "surgery": 13}},
    8: {"name": "Broken Leg", "death_save_penalty": 0, "effect": "move_penalty_4",
        "quick_fix": {"skill": "paramedic", "dv": 13}, "treatment": {"paramedic": 15, "surgery": 13}},
    9: {"name": "Torn Muscle", "death_save_penalty": 0, "effect": "melee_penalty_2",
        "quick_fix": {"skill": "first_aid", "dv": 13}, "treatment": {"paramedic": 13, "surgery": 13}},
    10: {"name": "Spinal Injury", "death_save_penalty": 1, "effect": "no_action_next_turn",
         "quick_fix": {"skill": "paramedic", "dv": 15}, "treatment": {"surgery": 15}},
    11: {"name": "Crushed Fingers", "death_save_penalty": 0, "effect": "hand_penalty_4",
         "quick_fix": {"skill": "paramedic", "dv": 13}, "treatment": {"surgery": 15}},
    12: {"name": "Dismembered Leg", "death_save_penalty": 1, "effect": "drop_leg_no_dodge",
         "quick_fix": None, "treatment": {"surgery": 17}},
}

# Critical Injuries to the Head (roll 2d6)
CRITICAL_INJURIES_HEAD = {
    2: {"name": "Lost Eye", "death_save_penalty": 1, "effect": "ranged_perception_penalty_4",
        "quick_fix": None, "treatment": {"surgery": 17}},
    3: {"name": "Brain Injury", "death_save_penalty": 1, "effect": "all_actions_penalty_2",
        "quick_fix": None, "treatment": {"surgery": 17}},
    4: {"name": "Damaged Eye", "death_save_penalty": 0, "effect": "ranged_perception_penalty_2",
        "quick_fix": {"skill": "paramedic", "dv": 15}, "treatment": {"surgery": 13}},
    5: {"name": "Concussion", "death_save_penalty": 0, "effect": "all_actions_penalty_2",
        "quick_fix": {"skill": "first_aid", "dv": 13}, "treatment": {"paramedic": 13, "surgery": 13}},
    6: {"name": "Broken Jaw", "death_save_penalty": 0, "effect": "speech_penalty_4",
        "quick_fix": {"skill": "paramedic", "dv": 13}, "treatment": {"paramedic": 13, "surgery": 13}},
    7: {"name": "Foreign Object", "death_save_penalty": 0, "effect": "re_suffer_on_move",
        "quick_fix": {"skill": "first_aid", "dv": 13}, "treatment": {"paramedic": 13, "surgery": 13}},
    8: {"name": "Whiplash", "death_save_penalty": 1, "effect": "none",
        "quick_fix": {"skill": "paramedic", "dv": 13}, "treatment": {"paramedic": 13, "surgery": 13}},
    9: {"name": "Cracked Skull", "death_save_penalty": 1, "effect": "head_multiplier_3",
        "quick_fix": {"skill": "paramedic", "dv": 15}, "treatment": {"paramedic": 15, "surgery": 15}},
    10: {"name": "Damaged Ear", "death_save_penalty": 0, "effect": "ear_move_penalty",
         "quick_fix": {"skill": "paramedic", "dv": 13}, "treatment": {"surgery": 13}},
    11: {"name": "Crushed Windpipe", "death_save_penalty": 1, "effect": "cannot_speak",
         "quick_fix": None, "treatment": {"surgery": 15}},
    12: {"name": "Lost Ear", "death_save_penalty": 1, "effect": "ear_move_penalty_4",
         "quick_fix": None, "treatment": {"surgery": 17}},
}

# Human-readable effect descriptions for injury display
INJURY_EFFECT_DESCRIPTIONS = {
    "drop_arm_hand": "Arm gone; held items dropped",
    "drop_hand": "Hand gone; held items dropped",
    "move_penalty_2": "-2 to MOVE (min 1)",
    "re_suffer_on_move": "Re-suffer bonus damage when moving >4m on foot",
    "drop_arm": "Arm unusable; items in that hand dropped",
    "move_penalty_4": "-4 to MOVE (min 1)",
    "melee_penalty_2": "-2 to Melee Attacks",
    "no_action_next_turn": "Next turn: no Action, can still Move",
    "hand_penalty_4": "-4 to Actions involving that hand",
    "drop_leg_no_dodge": "Leg gone; -6 MOVE (min 1); cannot dodge",
    "ranged_perception_penalty_4": "-4 to Ranged Attacks & Perception (vision)",
    "all_actions_penalty_2": "-2 to all Actions",
    "ranged_perception_penalty_2": "-2 to Ranged Attacks & Perception (vision)",
    "speech_penalty_4": "-4 to Actions involving speech",
    "none": "Base Death Save Penalty +1",
    "head_multiplier_3": "Aimed shots to head: damage x3 (instead of x2)",
    "ear_move_penalty": "Move >4m: no Move Action next turn; -2 Perception (hearing)",
    "cannot_speak": "Cannot speak",
    "ear_move_penalty_4": "Ear gone; Move >4m: no Move Action next turn; -4 Perception (hearing)",
}


# Cover data: item name -> (cover_hp, material)
# From CPR Cover Material and Thickness Examples
COVER_DATA = {
    "bank vault door": (50, "Thick Steel"),
    "bank window glass": (30, "Thick Bulletproof Glass"),
    "bar": (20, "Thick Wood"),
    "boulder": (40, "Thick Stone"),
    "bulletproof windshield": (15, "Thin Bulletproof Glass"),  # 15 or 30 for thick
    "bulletproof windshield thick": (30, "Thick Bulletproof Glass"),
    "car door": (25, "Thin Steel"),
    "data term": (25, "Thick Concrete"),
    "engine block": (50, "Thick Steel"),
    "hydrant": (50, "Thick Steel"),
    "log cabin wall": (20, "Thick Wood"),
    "metal door": (20, "Thin Steel"),
    "office cubicle": (0, "Not Cover"),
    "office wall": (15, "Thick Plaster/Foam/Plastic"),
    "overturned table": (5, "Thin Wood"),
    "prison visitation glass": (15, "Thin Bulletproof Glass"),
    "refrigerator": (25, "Thin Steel"),
    "shipping container": (25, "Thin Steel"),
    "sofa": (15, "Thick Plaster/Foam/Plastic"),
    "statue": (20, "Thin Stone"),
    "tree": (20, "Thick Wood"),
    "utility pole": (25, "Thick Concrete"),
    "wardrobe": (5, "Thin Wood"),
    "windshield": (0, "Not Cover"),
    "wooden door": (5, "Thin Wood"),
}


def get_cover_hp(item_name):
    """Get cover_hp for an item. Returns (cover_hp, material) or (0, None) if not cover."""
    key = (item_name or "").strip().lower()
    return COVER_DATA.get(key, (0, None))


def get_cover_by_name(item_name):
    """Fuzzy match cover item. Returns (cover_hp, material) or (0, None)."""
    key = (item_name or "").strip().lower()
    if key in COVER_DATA:
        return COVER_DATA[key]
    for k, v in COVER_DATA.items():
        if k in key or key in k:
            return v
    return (0, None)


# Hospital/surgical restoration cost by highest DC (treat/hospital)
HOSPITAL_COST_BY_DC = {
    17: 1000,  # DC 17+
    15: 500,
    13: 100,
    10: 50,
}

# Limb-loss injuries that can be replaced with cyberware at hospital.
# If character has 2x of that limb type (or Cyberaudio Suite for Lost Ear),
# Medtech alone cannot treat; requires Cybertech (Ripperdoc or Medtech with Surgery + Cybertech).
# Format: injury_name -> {"cyberware": ["Cyberarm"], "cost": 500} or list for arm (standard vs neo-soviet)
INJURY_CYBERWARE_REPLACEMENT = {
    "Dismembered Hand": {"cyberware": ["Cyberarm"], "cost": 500},  # Cyberarm includes Standard Hand
    "Dismembered Arm": {"cyberware": ["Cyberarm"], "cost": 500},   # Standard Cyberarm; Neo-Soviet 100 eb
    "Dismembered Leg": {"cyberware": ["Cyberleg"], "cost": 200},   # Cyberleg + Standard Foot
    "Lost Eye": {"cyberware": ["Cybereye"], "cost": 100},
    "Lost Ear": {"cyberware": ["Cyberaudio Suite"], "cost": 500},
}

# Cyberware that prevents certain injuries when paired
# Hardened Cybereye Casing (paired) -> prevents Damaged Eye
# Reinforced Cyberlimb Upgrade (paired) -> prevents Broken Leg (on leg) or Broken Arm (on arm)
CYBERWARE_INJURY_PREVENTION = {
    "Damaged Eye": {"cyberware": "Hardened Cybereye Casing", "requires_paired": True, "parent": "Cybereye"},
    "Broken Leg": {"cyberware": "Reinforced Cyberlimb Upgrade", "requires_paired": True, "parent": "Cyberleg"},
    "Broken Arm": {"cyberware": "Reinforced Cyberlimb Upgrade", "requires_paired": True, "parent": "Cyberarm"},
}


def get_hospital_cost_for_injuries(injury_names):
    """
    Get surgical restoration cost based on highest treatment DC among injuries.
    DC 17+: 1000 eb, DC 15: 500 eb, DC 13: 100 eb, DC 10: 50 eb.
    Returns (cost: int, highest_dc: int).
    """
    highest_dc = 0
    for name in injury_names or []:
        data, _ = get_injury_data_by_name(name)
        if data:
            treatment = data.get("treatment") or {}
            for key, dc in treatment.items():
                if isinstance(dc, (int, float)):
                    highest_dc = max(highest_dc, int(dc))
    # Map DC to cost (use highest matching tier)
    cost = 50  # default DC 10
    for dc in sorted(HOSPITAL_COST_BY_DC.keys(), reverse=True):
        if highest_dc >= dc:
            cost = HOSPITAL_COST_BY_DC[dc]
            break
    return cost, highest_dc


def get_injury_data_by_name(injury_name):
    """Get injury data by name from body or head tables. Returns (data, table) or (None, None)."""
    name_lower = (injury_name or "").strip().lower()
    for roll, data in CRITICAL_INJURIES_BODY.items():
        if (data.get("name") or "").strip().lower() == name_lower:
            return data, "body"
    for roll, data in CRITICAL_INJURIES_HEAD.items():
        if (data.get("name") or "").strip().lower() == name_lower:
            return data, "head"
    # Fuzzy match
    for roll, data in CRITICAL_INJURIES_BODY.items():
        if name_lower in (data.get("name") or "").strip().lower():
            return data, "body"
    for roll, data in CRITICAL_INJURIES_HEAD.items():
        if name_lower in (data.get("name") or "").strip().lower():
            return data, "head"
    return None, None


def get_installed_cyberware_counts(sheet):
    """
    Count installed cyberware by type for limb-loss replacement eligibility.
    Returns dict: cyberarm, cyberleg, cybereye, cyberaudio_suite (int counts).
    Accepts CharacterSheet or character object with character_sheet.
    """
    from world.inventory.models import CyberwareInstance

    sheet_obj = getattr(sheet, "character_sheet", sheet) if sheet else None
    if not sheet_obj or not getattr(sheet_obj, "pk", None):
        return {"cyberarm": 0, "cyberleg": 0, "cybereye": 0, "cyberaudio_suite": 0}

    qs = CyberwareInstance.objects.filter(
        character_sheet=sheet_obj,
        installed=True,
        parent__isnull=True,
    )
    counts = {"cyberarm": 0, "cyberleg": 0, "cybereye": 0, "cyberaudio_suite": 0}
    for inst in qs:
        name = (inst.cyberware.name or "").strip().lower()
        if name == "cyberarm" or name == "neo-soviet cyberarm":
            counts["cyberarm"] += 1
        elif name == "cyberleg":
            counts["cyberleg"] += 1
        elif name == "cybereye":
            counts["cybereye"] += 1
        elif name == "cyberaudio suite":
            counts["cyberaudio_suite"] += 1
    return counts


def injury_requires_cybertech_for_replacement(injury_name, counts):
    """
    True if this limb-loss injury cannot be treated by Medtech alone
    (character has 2x of that limb type or Cyberaudio Suite for Lost Ear).
    """
    repl = INJURY_CYBERWARE_REPLACEMENT.get(injury_name)
    if not repl:
        return False
    cw_list = repl.get("cyberware") or []
    if "Cyberarm" in cw_list and counts.get("cyberarm", 0) >= 2:
        return True
    if "Cyberleg" in cw_list and counts.get("cyberleg", 0) >= 2:
        return True
    if "Cybereye" in cw_list and counts.get("cybereye", 0) >= 2:
        return True
    if "Cyberaudio Suite" in cw_list and counts.get("cyberaudio_suite", 0) >= 1:
        return True
    return False


def is_injury_prevented_by_cyberware(character, injury_name):
    """
    Check if injury is prevented by installed cyberware.
    Hardened Cybereye Casing (paired) -> Damaged Eye
    Reinforced Cyberlimb Upgrade (paired) -> Broken Leg (on leg) or Broken Arm (on arm)
    """
    prev = CYBERWARE_INJURY_PREVENTION.get(injury_name)
    if not prev:
        return False
    from world.inventory.models import CyberwareInstance

    sheet = getattr(character, "character_sheet", None)
    if not sheet or not getattr(sheet, "pk", None):
        return False

    cw_name = prev.get("cyberware")
    parent_name = prev.get("parent")
    requires_paired = prev.get("requires_paired", False)

    # Find the protective cyberware (e.g. Hardened Cybereye Casing) installed as child of parent
    qs = CyberwareInstance.objects.filter(
        character_sheet=sheet,
        installed=True,
        cyberware__name__iexact=cw_name,
        parent__isnull=False,
    )
    for inst in qs:
        if not inst.parent:
            continue
        if (inst.parent.cyberware.name or "").strip().lower() != (parent_name or "").strip().lower():
            continue
        if requires_paired:
            parent = inst.parent
            if not parent or not getattr(parent, "paired_with_id", None):
                continue
        return True
    return False


def can_replace_injury_with_cyberware(injury_name, counts):
    """
    True if this limb-loss injury can be replaced with cyberware
    (character has room for another limb of that type).
    """
    repl = INJURY_CYBERWARE_REPLACEMENT.get(injury_name)
    if not repl:
        return False
    cw_list = repl.get("cyberware") or []
    if "Cyberarm" in cw_list and counts.get("cyberarm", 0) >= 2:
        return False
    if "Cyberleg" in cw_list and counts.get("cyberleg", 0) >= 2:
        return False
    if "Cybereye" in cw_list and counts.get("cybereye", 0) >= 2:
        return False
    if "Cyberaudio Suite" in cw_list and counts.get("cyberaudio_suite", 0) >= 1:
        return False
    return True


def roll_critical_injury(table_name, existing_injuries):
    """
    Roll 2d6 on the appropriate table until we get an injury the target doesn't have.
    table_name: "body" or "head"
    existing_injuries: set of injury names already applied
    Returns (injury_name, injury_data) or (None, None) if all already applied.
    """
    import random
    table = CRITICAL_INJURIES_HEAD if table_name == "head" else CRITICAL_INJURIES_BODY
    attempts = 0
    max_attempts = 20  # safety
    while attempts < max_attempts:
        roll = random.randint(1, 6) + random.randint(1, 6)
        data = table.get(roll)
        if data and data["name"] not in existing_injuries:
            return data["name"], data
        attempts += 1
    return (None, None)
