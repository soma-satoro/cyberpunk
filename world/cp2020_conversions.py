"""
Cyberpunk 2020 to Cyberpunk RED Weapon Conversions

Converts CP2020 firearms and melee weapons to RED using the official conversion
framework from R. Talsorian Games. Weapons are sourced from the Cyberpunk 2020
weapons list (tyrfing.org, fandom wiki). Excludes weapons already in equipment_data.py.

Conversion Steps (summary):
1. Match to RED Weapon Type (stats come from type)
2. Flatten WA: -1 or less -> 0, +1 or more -> +1 (Excellent)
3. UR Reliability -> Poor Reliability
4. Quality: Poor (UR+0WA), Standard (+0 WA, not UR), Excellent (+1 WA)
5. Replace attachments with RED equivalents; add Extended/Drum if mag > RED standard
6. Cost from base + attachments

To use: Call get_cp2020_converted_weapons() and optionally merge into equipment_data.weapons
"""

# Attachment costs (eb) for cost calculation
ATTACHMENT_COSTS = {
    "smartgun_link": 500,
    "extended_magazine": 100,
    "drum_magazine": 500,
    "silencer": 100,
    "infrared_nightvision_scope": 500,
    "sniping_scope": 500,
}

# RED weapon type baselines (damage, rof, hands, concealable, clip, category, weapon_type, base_value)
RED_WEAPON_TYPES = {
    "medium pistol": {
        "damage": "2d6", "rof": "2", "hands": 1, "concealable": True, "clip": 12,
        "category": "handgun", "weapon_type": "medium pistol", "base_value": 50,
    },
    "heavy pistol": {
        "damage": "3d6", "rof": "2", "hands": 1, "concealable": True, "clip": 8,
        "category": "handgun", "weapon_type": "heavy pistol", "base_value": 100,
    },
    "very heavy pistol": {
        "damage": "4d6", "rof": "1", "hands": 1, "concealable": True, "clip": 8,
        "category": "handgun", "weapon_type": "very heavy pistol", "base_value": 100,
    },
    "SMG": {
        "damage": "2d6", "rof": "4", "hands": 1, "concealable": True, "clip": 30,
        "category": "handgun", "weapon_type": "SMG", "base_value": 100,
    },
    "heavy SMG": {
        "damage": "3d6", "rof": "3", "hands": 2, "concealable": True, "clip": 40,
        "category": "handgun", "weapon_type": "heavy SMG", "base_value": 100,
    },
    "shotgun": {
        "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "clip": 4,
        "category": "shoulder_arms", "weapon_type": "shotgun", "base_value": 500,
    },
    "assault rifle": {
        "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "clip": 25,
        "category": "shoulder_arms", "weapon_type": "assault rifle", "base_value": 500,
    },
    "sniper rifle": {
        "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "clip": 4,
        "category": "shoulder_arms", "weapon_type": "sniper rifle", "base_value": 500,
    },
    "bow": {
        "damage": "4d6", "rof": "2", "hands": 2, "concealable": False,
        "category": "archery", "weapon_type": "bow", "base_value": 100,
    },
    "crossbow": {
        "damage": "4d6", "rof": "1", "hands": 2, "concealable": False,
        "category": "archery", "weapon_type": "crossbow", "base_value": 100,
    },
    "grenade launcher": {
        "damage": "6d6", "rof": "1", "hands": 2, "concealable": False, "clip": 2,
        "category": "heavy_weapons", "weapon_type": "grenade launcher", "base_value": 500,
    },
    "rocket launcher": {
        "damage": "8d6", "rof": "1", "hands": 2, "concealable": False, "clip": 1,
        "category": "heavy_weapons", "weapon_type": "rocket launcher", "base_value": 500,
    },
    "flamethrower": {
        "damage": "5d6", "rof": "2", "hands": 2, "concealable": False, "clip": 4,
        "category": "heavy_weapons", "weapon_type": "flamethrower", "base_value": 500,
    },
    "machine gun": {
        "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "clip": 40,
        "category": "heavy_weapons", "weapon_type": "machine gun", "base_value": 500,
    },
    "light melee": {
        "damage": "1d6", "rof": "2", "hands": 1, "concealable": True,
        "category": "melee", "weapon_type": "light melee", "base_value": 50,
    },
    "medium melee": {
        "damage": "2d6", "rof": "2", "hands": 1, "concealable": False,
        "category": "melee", "weapon_type": "medium melee", "base_value": 50,
    },
    "heavy melee": {
        "damage": "3d6", "rof": "2", "hands": 2, "concealable": False,
        "category": "melee", "weapon_type": "heavy melee", "base_value": 100,
    },
    "very heavy melee": {
        "damage": "4d6", "rof": "1", "hands": 2, "concealable": False,
        "category": "melee", "weapon_type": "very heavy melee", "base_value": 100,
    },
}

# CP2020 weapons from tyrfing.org / fandom wiki
# Format: name, cp2020_type, wa, reliability, shots, features, cost_2020, notes
# cp2020_type: P, MP, SMG, RIF, SHT, LMG, HVY, MGL, EX, M (melee)
# reliability: ST=Standard, VR=Very Reliable, UR=Unreliable
# Skip: Exotic (Step 0), already in equipment_data
CP2020_WEAPONS_RAW = [
    # Pistols - Medium (d6 to 2d6+1)
    ("Budget Arms C-13", "P", -1, "ST", 8, [], 75, "5mm"),
    ("Dai Lung Cybermag 15", "P", -1, "UR", 10, [], 50, "6mm"),
    ("Federated Arms X-22", "P", 0, "ST", 10, [], 150, "6mm"),
    ("Goncz-Taurus Pistol", "P", 0, "ST", 15, [], 250, "9mm"),
    ("Budget Arms Laser-Niner", "P", 1, "ST", 15, ["smartgun_link"], 675, "9mm, laser"),
    ("Beretta 97P", "P", 2, "VR", 18, [], 350, "9mm"),
    ("Colt Alpha-Omega 10mm", "P", 2, "VR", 10, [], 500, "10mm"),
    ("Dai Lung Streetmaster", "P", 0, "UR", 12, [], 250, "10mm"),
    ("Budget Arms Auto 3", "P", -1, "UR", 8, [], 350, "11mm"),
    ("Sternmeyer Type 35", "P", 0, "VR", 8, [], 400, "11mm"),
    ("Armalite 44", "P", 0, "ST", 8, [], 450, "12mm"),
    ("Colt AMT Model 2000", "P", 0, "VR", 8, [], 500, "12mm"),
    ("Federated Arms 454 DA Super Chief", "P", 0, "VR", 5, [], 375, ".454"),
    # Machine Pistol / SMG
    ("Goncz-Taurus MP", "MP", -1, "ST", 15, [], 350, "9mm"),
    ("Militech Arms Avenger", "P", 0, "VR", 10, [], 250, "9mm - different from Militech Avenger"),
    # SMGs
    ("Federated Arms Tech Assault II", "SMG", 1, "ST", 50, [], 400, "6mm"),
    ("Setsuko-Arasaka PMS SMG", "SMG", 1, "ST", 40, [], 950, "7mm"),
    ("H&K MPK-9", "SMG", 1, "ST", 35, [], 520, "9mm"),
    ("Uzi Miniauto 9", "SMG", 1, "VR", 30, [], 475, "9mm"),
    ("Militech-10 SMG", "SMG", 1, "ST", 30, [], 455, "10mm"),
    ("H&K MP-2013", "SMG", 1, "ST", 35, [], 450, "10mm"),
    ("Sternmeyer SMG-21", "SMG", -1, "VR", 30, [], 500, "11mm - exists as Sternmeyer SMG-21"),
    ("H&K MPK-11", "SMG", 0, "ST", 30, [], 700, "12mm -> heavy SMG"),
    ("Ingram MAC-14", "SMG", -2, "ST", 20, [], 650, "12mm -> heavy SMG"),
    # Rifles
    ("Militech M31a1 Rifle", "RIF", 2, "VR", 150, ["grenade_launcher"], 1695, "4.5mm"),
    ("Darra-Polytechnic M9 Assault Rifle", "RIF", 0, "ST", 40, [], 300, "5.5mm"),
    ("Militech Ronin Light Assault", "RIF", 1, "VR", 35, [], 450, "5.56mm"),
    ("AKR-20 Medium Assault", "RIF", 0, "ST", 30, [], 500, "5.56mm"),
    ("Federated Arms Light Assault 15", "RIF", 0, "VR", 30, [], 400, "7mm"),
    ("FN-RAL Heavy Assault Rifle", "RIF", -1, "VR", 30, [], 600, "7.62mm"),
    ("Kalashnikov A-80 Heavy Rifle", "RIF", -1, "ST", 35, [], 550, "7.62mm"),
    ("FR-F6 Sniping Rifle", "RIF", 4, "ST", 10, ["smartgun_link"], 2000, "7.62mm"),
    ("Remington Gyro Sniping Rifle", "RIF", 2, "ST", 6, [], 1000, "18mm API"),
    ("Militech Cyborg Rifle", "RIF", 1, "ST", 30, [], 800, ".300WM"),
    ("Tsunami Arms Ramjet Rifle", "RIF", 3, "VR", 9, [], 1230, "8.5mm"),
    # Shotguns
    ("Militech Crusher SSG", "SHT", -1, "ST", 6, [], 450, "20ga"),
    ("Arasaka Rapid Assault 12", "SHT", -1, "ST", 20, [], 900, "12ga"),
    ("Constitution Arms Hurricane", "SHT", 0, "ST", 40, [], 1000, "12ga"),
    ("Sternmeyer Stakeout 10", "SHT", -2, "ST", 10, [], 450, "12ga"),
    ("Luigi Franchi King Buck Multi-Magnum", "SHT", -1, "VR", 4, [], 800, "10ga"),
    ("Militech Military Police Shotgun 12ga", "SHT", 0, "ST", 8, [], 300, "12ga"),
    ("Militech Military Police Shotgun 10ga", "SHT", 0, "ST", 8, [], 300, "10ga"),
    # LMG / Heavy
    ("H&K G-6 Advanced Squad Automatic", "LMG", 1, "VR", 100, [], 2050, "6mm"),
    ("Confederation Arms Cyclone", "LMG", 1, "VR", 100, [], 1200, "7.62mm"),
    ("Barrett-Arasaka Light 20mm", "HVY", 0, "VR", 10, [], 2000, "20mm"),
    ("Militech Arms RPG-A", "HVY", -2, "VR", 1, [], 1500, "rocket"),
    ("Scorpion 16 Missile Launcher", "HVY", -1, "VR", 1, [], 3000, "missile"),
    ("Kenshiri-Adachi F-254 Flamethrower", "HVY", -2, "ST", 10, [], 1500, "flame"),
    ("Militech Minigrenade Launcher", "MGL", -1, "ST", 4, [], 255, "25mm pump"),
    ("Rostovic Wrist Rocket", "MGL", 0, "ST", 6, [], 380, "30mm"),
    # Bows / Crossbows
    ("EagleTech Tomcat Compound Bow", "EX", 0, "VR", 12, [], 150, "bow"),
    ("EagleTech Stryker Crossbow", "EX", -1, "ST", 12, [], 220, "crossbow"),
]

# Weapons to exclude (already in equipment_data.py) - normalized lowercase
EXCLUDE_WEAPONS = {
    "militech avenger",
    "federated arms x-9mm",
    "arasaka minami 10",
    "militech crusher",
    "militech ronin",
    "sternmeyer smg-21",
    "militech mini-gat",
    "stolbovoy st-5",
    "stolbovoy st-5 assault rifle",
    "beretta m-24 smg",
    "eagletech tomcat",
    "eagletech stryker",
    "eagletech bearcat",
    "eagletech tigercat",
    "eagletech scorpion",
    "eagletech arbelest",
    "eagletech hawk's eye",
    "eagletech sherwood",
    "eagletech hunter",
    "eagletech midnight hunter",
    "eagletech mountaineer",
    "arasaka rapid assault",
    "militech bulldog",
    "militech dragon",
    "militech ninja sniper",
    "militech urban",
    "militech hotshot",
    "militech minigrenade",
    "militech mini-grenade",
    "kendachi dragon",
    "rostovic wrist",
    "constitutional arms multi-ammo pistol",
    "constitutional arms hurricane",
}


def _normalize_name(name):
    return (name or "").strip().lower()


def _flatten_wa(wa):
    """Step 2: Flatten Weapon Accuracy."""
    if wa is None:
        return 0
    if wa <= -1:
        return 0
    if wa >= 1:
        return 1
    return 0


def _is_poor_reliability(rel):
    """Step 3: UR -> Poor Reliability."""
    return (rel or "").upper() == "UR"


def _get_quality(wa_flat, poor_rel):
    """Step 4: Determine quality."""
    if wa_flat >= 1:
        return "excellent"
    if poor_rel:
        return "poor"
    return "standard"


def _map_cp2020_to_red_type(cp2020_type, notes="", name=""):
    """Map CP2020 weapon type to RED weapon_type."""
    t = (cp2020_type or "").upper()
    combined = f"{name} {notes}".lower()
    # Parse damage for pistol subtyping from notes (e.g. "11mm" -> medium/heavy)
    if t == "P":
        if "4d6" in str(notes) or "6d6" in str(notes) or ".454" in str(notes):
            return "very heavy pistol"
        if "3d6" in str(notes) or "12mm" in str(notes):
            return "heavy pistol"
        return "medium pistol"
    if t == "MP":
        return "SMG"
    if t == "SMG":
        if "4d6" in str(notes) or "12mm" in str(notes):
            return "heavy SMG"
        return "SMG"
    if t == "RIF":
        if "snip" in combined or "gyro" in combined or "ramjet" in combined or "fr-f6" in combined:
            return "sniper rifle"
        return "assault rifle"
    if t == "SHT":
        return "shotgun"
    if t == "LMG":
        return "machine gun"
    if t == "HVY":
        if "flame" in combined:
            return "flamethrower"
        if "rpg" in combined or "missile" in combined or "rocket" in combined:
            return "rocket launcher"
        return "machine gun"  # 20mm etc
    if t == "MGL":
        return "grenade launcher"
    if t == "EX":
        if "bow" in combined:
            return "bow"
        if "crossbow" in combined:
            return "crossbow"
    return "medium pistol"


def _resolve_attachments(features, cp2020_shots, red_clip, red_type):
    """Step 5: Resolve attachments. Return (attachments_list, clip, slots_used, cost_add)."""
    attachments = list(features) if features else []
    clip = red_clip or 0
    cost_add = 0
    slots_used = 0

    # Map 2020 features to RED attachments
    red_attachments = []
    for f in attachments:
        if f == "smartgun_link":
            red_attachments.append(("smartgun_link", 2, 500))
        elif f == "grenade_launcher":
            pass  # Underbarrel, exotic - skip for simplicity

    # If 2020 mag > RED standard, add Extended or Drum (skip for archery - no magazine)
    if red_type in ("bow", "crossbow"):
        pass
    elif cp2020_shots and red_clip and cp2020_shots > red_clip:
        diff = cp2020_shots - red_clip
        if diff <= 10:
            red_attachments.append(("extended_magazine", 1, 100))
            clip = min(cp2020_shots, red_clip + 10)
        else:
            red_attachments.append(("drum_magazine", 2, 500))
            clip = min(cp2020_shots, red_clip + 25)  # approximate

    for _name, slots, cost in red_attachments:
        slots_used += slots
        cost_add += cost

    if slots_used > 3:
        slots_used = 3  # Cap; would make exotic

    return red_attachments, clip, slots_used, cost_add


def convert_cp2020_weapon(
    name,
    cp2020_type,
    wa,
    reliability,
    shots,
    features,
    cost_2020,
    notes="",
):
    """Convert a single CP2020 weapon to RED format."""
    wa_flat = _flatten_wa(wa)
    poor_rel = _is_poor_reliability(reliability)
    quality = _get_quality(wa_flat, poor_rel)

    red_type = _map_cp2020_to_red_type(cp2020_type, notes, name)
    baseline = RED_WEAPON_TYPES.get(red_type)
    if not baseline:
        return None

    red_clip = baseline.get("clip", 0)
    att_list, clip, slots_used, cost_add = _resolve_attachments(
        features, shots, red_clip, red_type
    )

    # Base cost from quality (RED: Poor ~half, Standard=base, Excellent ~2x)
    base_val = baseline["base_value"]
    if quality == "excellent":
        base_val = base_val * 2
    elif quality == "poor":
        base_val = max(50, base_val // 2)

    value = base_val + cost_add

    # Build description
    desc_parts = [f"CP2020 conversion. {quality.capitalize()} Quality {red_type.replace('_', ' ').title()}."]
    if att_list:
        att_names = [a[0].replace("_", " ").title() for a in att_list]
        desc_parts.append(f"Comes with: {', '.join(att_names)}.")

    attachment_slots = max(0, 3 - slots_used)

    # Weapon model requires clip to be non-null; use 0 for archery (bows/crossbows)
    clip_val = clip if baseline.get("clip") is not None else 0

    return {
        "name": name,
        "damage": baseline["damage"],
        "rof": baseline["rof"],
        "hands": baseline["hands"],
        "concealable": baseline["concealable"],
        "weight": 1 if "pistol" in red_type or "SMG" in red_type else 2,
        "value": value,
        "category": baseline["category"],
        "clip": clip_val,
        "attachment_slots": attachment_slots,
        "weapon_type": red_type,
        "quality": quality,
        "description": " ".join(desc_parts),
    }


def get_cp2020_converted_weapons(exclude_existing=True):
    """
    Return list of RED-format weapons converted from CP2020.
    If exclude_existing=True, skip weapons whose names match equipment_data.
    """
    existing_names = set(EXCLUDE_WEAPONS)
    if exclude_existing:
        try:
            from world.equipment_data import weapons as existing_weapons
            for w in existing_weapons:
                n = w.get("name")
                if n:
                    existing_names.add(_normalize_name(n))
        except ImportError:
            pass

    result = []
    for row in CP2020_WEAPONS_RAW:
        name = row[0]
        norm = _normalize_name(name)
        if norm in existing_names:
            continue
        converted = convert_cp2020_weapon(
            name=row[0],
            cp2020_type=row[1],
            wa=row[2],
            reliability=row[3],
            shots=row[4],
            features=row[5],
            cost_2020=row[6],
            notes=row[7],
        )
        if converted:
            result.append(converted)

    return result


# Pre-computed list for direct import (avoids circular import at module load)
# Populated on first access
_CP2020_WEAPONS_CACHE = None


def get_cp2020_weapons_list(include_conversions=True, exclude_existing=True):
    """
    Return weapons list. If include_conversions=True, merges CP2020 conversions.
    Used by equipment_data to optionally add 2020 weapons.
    """
    global _CP2020_WEAPONS_CACHE
    if not include_conversions:
        return []
    if _CP2020_WEAPONS_CACHE is None:
        _CP2020_WEAPONS_CACHE = get_cp2020_converted_weapons(exclude_existing=exclude_existing)
    return _CP2020_WEAPONS_CACHE
