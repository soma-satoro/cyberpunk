"""
Role-ability helpers used by combat, rolling, and commerce systems.
"""

from __future__ import annotations

from typing import Dict, Tuple

from world.improvement_points import get_character_stat_value, parse_skill_instance


CA_KEYS = (
    "damage_deflection",
    "fumble_recovery",
    "initiative_reaction",
    "precision_attack",
    "spot_weakness",
    "threat_detection",
)


def get_role_ability_rank(character, key: str) -> int:
    """Safely fetch a role ability rank from the canonical stat resolver."""
    try:
        return int(get_character_stat_value(character, key) or 0)
    except Exception:
        return 0


def get_default_combat_awareness_loadout(rank: int) -> Dict[str, int]:
    """
    Default Solo loadout.
    Keeps prior behavior (initiative +1 when rank > 0) by assigning one point
    to Initiative Reaction, then leaving the rest unspent.
    """
    base = {k: 0 for k in CA_KEYS}
    if rank > 0:
        base["initiative_reaction"] = 1
    return base


def _normalize_ca_loadout(loadout: Dict) -> Dict[str, int]:
    out = {k: 0 for k in CA_KEYS}
    if not isinstance(loadout, dict):
        return out
    for key in CA_KEYS:
        try:
            out[key] = int(loadout.get(key, 0) or 0)
        except Exception:
            out[key] = 0
    return out


def _validate_ca_constraints(loadout: Dict[str, int], rank: int) -> Tuple[bool, str]:
    dd = int(loadout.get("damage_deflection", 0) or 0)
    fr = int(loadout.get("fumble_recovery", 0) or 0)
    ir = int(loadout.get("initiative_reaction", 0) or 0)
    pa = int(loadout.get("precision_attack", 0) or 0)
    sw = int(loadout.get("spot_weakness", 0) or 0)
    td = int(loadout.get("threat_detection", 0) or 0)

    if dd not in (0, 2, 4, 6, 8, 10):
        return False, "Damage Deflection must be one of: 0, 2, 4, 6, 8, 10."
    if fr not in (0, 4):
        return False, "Fumble Recovery must be 0 or 4."
    if pa not in (0, 3, 6, 9):
        return False, "Precision Attack must be one of: 0, 3, 6, 9."
    for key, val in (("Initiative Reaction", ir), ("Spot Weakness", sw), ("Threat Detection", td)):
        if val < 0 or val > 10:
            return False, f"{key} must be between 0 and 10."

    spent = dd + fr + ir + pa + sw + td
    if spent > rank:
        return False, f"Combat Awareness allocation spends {spent}, but your rank is {rank}."
    return True, ""


def get_combat_awareness_loadout(character) -> Dict[str, int]:
    """Get validated loadout; reset to safe default if malformed."""
    rank = get_role_ability_rank(character, "combat_awareness")
    raw = getattr(character.db, "combat_awareness_loadout", None)
    loadout = _normalize_ca_loadout(raw)
    ok, _ = _validate_ca_constraints(loadout, rank)
    if not ok:
        loadout = get_default_combat_awareness_loadout(rank)
        character.db.combat_awareness_loadout = loadout
    return loadout


def set_combat_awareness_loadout(character, new_loadout: Dict[str, int]) -> Tuple[bool, str, Dict[str, int]]:
    """Validate and persist a Solo loadout."""
    rank = get_role_ability_rank(character, "combat_awareness")
    loadout = _normalize_ca_loadout(new_loadout)
    ok, err = _validate_ca_constraints(loadout, rank)
    if not ok:
        return False, err, loadout
    character.db.combat_awareness_loadout = loadout
    return True, "", loadout


def get_combat_awareness_spent(loadout: Dict[str, int]) -> int:
    return sum(int(loadout.get(k, 0) or 0) for k in CA_KEYS)


def get_solo_initiative_bonus(character) -> int:
    return int(get_combat_awareness_loadout(character).get("initiative_reaction", 0) or 0)


def get_solo_precision_attack_bonus(character) -> int:
    spent = int(get_combat_awareness_loadout(character).get("precision_attack", 0) or 0)
    return 1 if spent >= 3 else 2 if spent >= 6 else 3 if spent >= 9 else 0


def get_solo_spot_weakness_bonus(character) -> int:
    return int(get_combat_awareness_loadout(character).get("spot_weakness", 0) or 0)


def get_solo_threat_detection_bonus(character) -> int:
    return int(get_combat_awareness_loadout(character).get("threat_detection", 0) or 0)


def get_solo_damage_deflection_value(character) -> int:
    spent = int(get_combat_awareness_loadout(character).get("damage_deflection", 0) or 0)
    return 1 if spent >= 2 else 2 if spent >= 4 else 3 if spent >= 6 else 4 if spent >= 8 else 5 if spent >= 10 else 0


def has_solo_fumble_recovery(character) -> bool:
    spent = int(get_combat_awareness_loadout(character).get("fumble_recovery", 0) or 0)
    return spent >= 4


def _current_combat_round_token(character) -> str:
    """Return a stable room:round token for first-hit/first-damage Solo effects."""
    room = getattr(character, "location", None)
    if not room:
        return ""
    scene = getattr(room.ndb, "combat_state", None)
    if not isinstance(scene, dict):
        return ""
    try:
        round_num = int(scene.get("round", 0) or 0)
    except Exception:
        round_num = 0
    if round_num <= 0:
        return ""
    return f"{getattr(room, 'id', 0)}:{round_num}"


def solo_spot_weakness_available(character) -> bool:
    token = _current_combat_round_token(character)
    if not token:
        return False
    return (getattr(character.db, "ca_spot_weakness_used_round", "") or "") != token


def consume_solo_spot_weakness(character):
    token = _current_combat_round_token(character)
    if token:
        character.db.ca_spot_weakness_used_round = token


def solo_damage_deflection_available(character) -> bool:
    token = _current_combat_round_token(character)
    if not token:
        return False
    return (getattr(character.db, "ca_damage_deflection_used_round", "") or "") != token


def consume_solo_damage_deflection(character):
    token = _current_combat_round_token(character)
    if token:
        character.db.ca_damage_deflection_used_round = token


MOTO_SKILL_KEYS = frozenset(
    {
        "drive_land",
        "pilot_air",
        "pilot_sea",
        "air_vehicle_tech",
        "land_vehicle_tech",
        "sea_vehicle_tech",
    }
)


def get_moto_skill_bonus(character, skill_name: str) -> int:
    """Nomad Moto rank bonus for vehicle operation/tech checks."""
    base, _ = parse_skill_instance(skill_name)
    if base not in MOTO_SKILL_KEYS:
        return 0
    return int(get_role_ability_rank(character, "moto") or 0)
