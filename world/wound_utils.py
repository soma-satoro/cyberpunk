"""
Wound state, damage application, death save, and critical injury logic.
"""

from world.wound_data import (
    WOUND_SLIGHTLY,
    WOUND_SERIOUSLY,
    WOUND_MORTALLY,
    WOUND_DEAD,
    STABILIZATION_DV,
    roll_critical_injury,
    CRITICAL_INJURIES_BODY,
    CRITICAL_INJURIES_HEAD,
    is_injury_prevented_by_cyberware,
)
import random


def get_current_hp(character):
    """Get current HP from character (sheet or db)."""
    if hasattr(character, "character_sheet") and character.character_sheet:
        return getattr(character.character_sheet, "_current_hp", 0) or 0
    return getattr(character.db, "current_hp", 0) or 0


def get_max_hp(character):
    """Get max HP from character."""
    if hasattr(character, "character_sheet") and character.character_sheet:
        return getattr(character.character_sheet, "_max_hp", 0) or 0
    return getattr(character.db, "max_hp", 0) or 0


def get_wound_state(character):
    """
    Determine wound state from HP.
    Slightly: < full HP
    Seriously: < half HP (rounded up)
    Mortally: < 1 HP
    Dead: failed death save (character.db.dead or sheet)
    """
    if getattr(character.db, "dead", False):
        return WOUND_DEAD
    current = get_current_hp(character)
    max_hp = get_max_hp(character)
    if max_hp <= 0:
        return WOUND_SLIGHTLY
    if current < 1:
        return WOUND_MORTALLY
    half = (max_hp + 1) // 2  # rounded up
    if current < half:
        return WOUND_SERIOUSLY
    if current < max_hp:
        return WOUND_SLIGHTLY
    return None  # unwounded


def get_action_penalty(character):
    """Get penalty to all actions from wound state."""
    state = get_wound_state(character)
    if state == WOUND_SERIOUSLY:
        return -2
    if state == WOUND_MORTALLY:
        return -4
    return 0


def get_move_penalty(character):
    """Get penalty to MOVE from wound state (mortally = -6, min 1)."""
    state = get_wound_state(character)
    if state == WOUND_MORTALLY:
        return -6
    return 0


def requires_death_save(character):
    """True if character must make death save at start of turn."""
    return get_wound_state(character) == WOUND_MORTALLY


def is_dead(character):
    """True if character has failed death save."""
    return getattr(character.db, "dead", False) or get_wound_state(character) == WOUND_DEAD


def get_armor_sp(character, aim_location=None):
    """
    Get effective SP for target. Uses InventoryArmor current SP (after ablation) when available.
    For aimed shots, use location-specific SP if armor has it.
    """
    sheet = getattr(character, "character_sheet", None)
    armor = None
    if sheet:
        armor = getattr(sheet, "eqarmor", None)
    if not armor and hasattr(character, "db") and getattr(character.db, "eqarmor", None):
        armor = character.db.eqarmor
    if not armor:
        return 0
    sp = getattr(armor, "sp", 0) or 0
    # Use InventoryArmor effective SP (ablated) when character has inventory
    if sheet:
        inv = getattr(sheet, "inventory", None)
        if inv and armor:
            try:
                from world.inventory.models import InventoryArmor
                inst = InventoryArmor.objects.filter(inventory=inv, armor=armor).first()
                if inst:
                    return inst.get_effective_sp()
            except Exception:
                pass
    return sp


def get_cover_sp(character):
    """Get cover's current HP as additional protection. Returns (cover_hp, cover_current_hp)."""
    cover = getattr(character.db, "cover", None)
    if not cover:
        return 0, 0
    cover_hp = cover.get("cover_hp", 0) or 0
    cover_current = cover.get("cover_current_hp", cover_hp) or 0
    return cover_hp, cover_current


def apply_damage_to_character(character, amount, source=None, location=None):
    """
    Apply damage to character's HP. Syncs to sheet and db.
    Returns actual damage applied.
    """
    sheet = getattr(character, "character_sheet", None)
    old_hp = get_current_hp(character)
    new_hp = max(0, old_hp - amount)
    actual = old_hp - new_hp

    if sheet:
        sheet._current_hp = new_hp
        sheet.save(skip_recalculation=True)
    if hasattr(character, "db"):
        character.db.current_hp = new_hp
    return actual


def add_injury_to_character(character, injury_name):
    """
    Add a critical injury to a character (staff/GM fiat). No bonus damage applied.
    Returns (success: bool, canonical_name_or_error: str).
    """
    from world.wound_data import get_injury_data_by_name

    sheet = getattr(character, "character_sheet", None)
    if not sheet:
        return (False, "Target has no character sheet.")

    data, _ = get_injury_data_by_name(injury_name)
    if not data:
        return (False, f"Unknown injury: {injury_name}")

    canonical = data.get("name", "").strip()
    injuries = list(getattr(sheet, "critical_injuries", []) or [])
    if canonical in injuries:
        return (False, f"Target already has {canonical}.")

    injuries.append(canonical)
    sheet.critical_injuries = injuries

    dsp = data.get("death_save_penalty", 0) or 0
    if dsp:
        base = getattr(sheet, "base_death_save_penalty", 0) or 0
        sheet.base_death_save_penalty = base + dsp
        current = getattr(sheet, "death_save_penalty", 0) or 0
        sheet.death_save_penalty = current + dsp
        if hasattr(character, "db"):
            character.db.death_save_penalty = sheet.death_save_penalty

    sheet.save(skip_recalculation=True)
    return (True, canonical)


def remove_injury_from_character(character, injury_name):
    """
    Remove a critical injury from a character (staff/GM fiat).
    Returns (success: bool, canonical_name_or_error: str).
    """
    from world.wound_data import get_injury_data_by_name

    sheet = getattr(character, "character_sheet", None)
    if not sheet:
        return (False, "Target has no character sheet.")

    data, _ = get_injury_data_by_name(injury_name)
    if not data:
        return (False, f"Unknown injury: {injury_name}")

    canonical = data.get("name", "").strip()
    injuries = list(getattr(sheet, "critical_injuries", []) or [])
    if canonical not in injuries:
        return (False, f"Target does not have {canonical}.")

    injuries.remove(canonical)
    sheet.critical_injuries = injuries

    dsp = data.get("death_save_penalty", 0) or 0
    if dsp:
        base = getattr(sheet, "base_death_save_penalty", 0) or 0
        sheet.base_death_save_penalty = max(0, base - dsp)
        new_base = getattr(sheet, "base_death_save_penalty", 0) or 0
        current = getattr(sheet, "death_save_penalty", 0) or 0
        sheet.death_save_penalty = max(new_base, current - dsp)
        if hasattr(character, "db"):
            character.db.death_save_penalty = sheet.death_save_penalty

    fixes = dict(getattr(sheet, "critical_injury_quick_fixes", {}) or {})
    fixes.pop(canonical, None)
    sheet.critical_injury_quick_fixes = fixes
    sheet.save(skip_recalculation=True)
    return (True, canonical)


def apply_critical_injury_to_character(character, table_name, aim_location=None):
    """
    Roll and apply a critical injury. table_name: "body" or "head".
    Adds to critical_injuries list, applies 5 bonus damage, increases base_death_save_penalty if applicable.
    Returns (injury_name, injury_data) or (None, None).
    """
    sheet = getattr(character, "character_sheet", None)
    if not sheet:
        return (None, None)
    existing = set(getattr(sheet, "critical_injuries", []) or [])
    injury_name, injury_data = roll_critical_injury(table_name, existing)
    if not injury_name:
        return (None, None)

    # Check if injury is prevented by cyberware (Hardened Cybereye Casing, Reinforced Cyberlimb)
    if is_injury_prevented_by_cyberware(character, injury_name):
        return (None, None)

    # Add to list
    injuries = list(existing)
    injuries.append(injury_name)
    sheet.critical_injuries = injuries

    # Apply 5 bonus damage (doesn't ablate armor)
    apply_damage_to_character(character, 5, source="critical_injury")

    # Increase base_death_save_penalty if injury has it; add dsp to death_save_penalty (preserve cumulative)
    dsp = injury_data.get("death_save_penalty", 0)
    if dsp:
        base = getattr(sheet, "base_death_save_penalty", 0) or 0
        sheet.base_death_save_penalty = base + dsp
        current_penalty = getattr(sheet, "death_save_penalty", 0) or 0
        sheet.death_save_penalty = current_penalty + dsp
        if hasattr(character, "db"):
            character.db.death_save_penalty = sheet.death_save_penalty
    sheet.save(skip_recalculation=True)
    return (injury_name, injury_data)


def increase_death_save_penalty(character):
    """Add +1 to death_save_penalty (each death save roll and each hit at 0 HP adds +1)."""
    sheet = getattr(character, "character_sheet", None)
    if sheet:
        current = getattr(sheet, "death_save_penalty", 0) or 0
        sheet.death_save_penalty = current + 1
        sheet.save(skip_recalculation=True)
    if hasattr(character, "db"):
        character.db.death_save_penalty = (character.db.death_save_penalty or 0) + 1


def stabilize_character(character):
    """
    Stabilize a mortally wounded character: set HP to 1, reset death_save_penalty to base,
    set unconscious for 1 minute. Call after successful stabilization roll.
    """
    import time
    sheet = getattr(character, "character_sheet", None)
    if sheet:
        sheet._current_hp = 1
        base = getattr(sheet, "base_death_save_penalty", 0) or 0
        sheet.death_save_penalty = base
        sheet.save(skip_recalculation=True)
        if hasattr(character, "db"):
            character.db.death_save_penalty = base
    if hasattr(character, "db"):
        character.db.current_hp = 1
        character.db.unconscious_until = time.time() + 60  # 1 minute


def is_unconscious(character):
    """True if character is unconscious (e.g. after stabilization from mortally wounded)."""
    import time
    until = getattr(character.db, "unconscious_until", 0) or 0
    return until > 0 and time.time() < until


def clear_unconscious(character):
    """Clear unconscious state."""
    if hasattr(character, "db"):
        character.db.unconscious_until = 0


def reset_death_save_penalty_to_base(character):
    """When stabilized to 1 HP, reset death_save_penalty to base_death_save_penalty."""
    sheet = getattr(character, "character_sheet", None)
    if sheet:
        base = getattr(sheet, "base_death_save_penalty", 0) or 0
        sheet.death_save_penalty = base
        sheet.save(skip_recalculation=True)
    if hasattr(character, "db"):
        character.db.death_save_penalty = getattr(sheet, "base_death_save_penalty", 0) or 0


def make_death_save(character):
    """
    Roll death save. Roll d10 + death_save_penalty. If result < BODY (death_save attribute), live.
    If roll is 10 (on d10), auto-fail.
    Each roll adds +1 to death_save_penalty. Base comes from injuries only; stabilization resets to base.
    Returns (success: bool, roll: int, total: int, penalty_used: int).
    """
    body = getattr(character.db, "death_save", 0) or 0
    if hasattr(character, "character_sheet") and character.character_sheet:
        body = getattr(character.character_sheet, "death_save", body) or body
    penalty = 0
    if hasattr(character, "character_sheet") and character.character_sheet:
        penalty = getattr(character.character_sheet, "death_save_penalty", 0) or 0
    elif hasattr(character, "db"):
        penalty = getattr(character.db, "death_save_penalty", 0) or 0

    roll = random.randint(1, 10)
    total = roll + penalty

    # Each roll adds +1 to penalty for next time
    increase_death_save_penalty(character)

    if roll == 10:
        character.db.dead = True
        if hasattr(character, "character_sheet") and character.character_sheet:
            character.character_sheet.save(skip_recalculation=True)
        return (False, roll, total, penalty)
    success = total < body
    if not success:
        character.db.dead = True
        if hasattr(character, "character_sheet") and character.character_sheet:
            character.character_sheet.save(skip_recalculation=True)
    return (success, roll, total, penalty)


def get_death_save_penalty(character):
    """Get current death save penalty for display."""
    if hasattr(character, "character_sheet") and character.character_sheet:
        return getattr(character.character_sheet, "death_save_penalty", 0) or 0
    return getattr(character.db, "death_save_penalty", 0) or 0
