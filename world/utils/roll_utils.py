"""
Cyberpunk RED skill check roll utilities.

Handles:
- Critical Success: Natural 10 on d10 -> roll another d10 and add. If another 10, do not add again.
- Critical Failure: Natural 1 on d10 -> roll another d10 and subtract. If another 1, do not subtract again.
- Luck spending: +1 per luck point spent (deducted from character's pool before roll).
- Success = total exceeds DV (total > dv). Hitting the DV exactly is failure.
"""
import random
from typing import Optional, Tuple, Any


def roll_d10_with_crits() -> Tuple[int, int, bool, bool, list]:
    """
    Roll 1d10 with Cyberpunk RED critical success/failure rules.

    Returns:
        (total, first_roll, is_crit_success, is_crit_failure, extra_rolls)
        - total: The final dice total (first roll + crit bonuses/penalties)
        - first_roll: The initial d10 result (1-10)
        - is_crit_success: True if first roll was 10
        - is_crit_failure: True if first roll was 1
        - extra_rolls: List of (roll, added) - roll value and whether it was added (True) or subtracted (False)
    """
    first = random.randint(1, 10)
    total = first
    extra_rolls = []
    is_crit_success = first == 10
    is_crit_failure = first == 1

    # Critical Success: roll another d10 and add. If another 10, do not add again.
    if first == 10:
        extra = random.randint(1, 10)
        extra_rolls.append((extra, True))
        if extra != 10:  # Only add if not another 10
            total += extra

    # Critical Failure: roll another d10 and subtract. If another 1, do not subtract again.
    if first == 1:
        extra = random.randint(1, 10)
        extra_rolls.append((extra, False))
        if extra != 1:  # Only subtract if not another 1
            total -= extra

    return total, first, is_crit_success, is_crit_failure, extra_rolls


def roll_skill_check(
    stat_val: int,
    skill_val: int,
    modifier: int = 0,
    luck_spend: int = 0,
    character: Optional[Any] = None,
) -> Tuple[int, dict]:
    """
    Perform a Cyberpunk RED skill check: stat + skill + 1d10 + modifier + luck.

    Handles critical success/failure and optional luck spending.

    Args:
        stat_val: Stat value (e.g. Intelligence)
        skill_val: Skill value (e.g. Interface rank)
        modifier: Player-specified modifier (+1, -3, etc.)
        luck_spend: Luck points to spend (+1 per point). If character provided, deducts from current_luck.
        character: Character object - required if luck_spend > 0, to deduct luck.

    Returns:
        (total, details)
        details: dict with keys:
            - dice_total: raw d10 total (with crits)
            - first_roll: initial d10
            - is_crit_success, is_crit_failure
            - extra_rolls: list of (roll, added)
            - luck_spent: amount actually spent (may be less if insufficient)
    """
    # Resolve luck - deduct from character if provided
    actual_luck = 0
    if luck_spend > 0 and character:
        current = getattr(character.db, "current_luck", 0) or 0
        actual_luck = min(luck_spend, max(0, current))
        if actual_luck > 0:
            character.db.current_luck = current - actual_luck
    elif luck_spend > 0:
        actual_luck = luck_spend  # No character - assume caller handles it

    dice_total, first_roll, is_crit_success, is_crit_failure, extra_rolls = roll_d10_with_crits()
    total = stat_val + skill_val + dice_total + modifier + actual_luck

    details = {
        "dice_total": dice_total,
        "first_roll": first_roll,
        "is_crit_success": is_crit_success,
        "is_crit_failure": is_crit_failure,
        "extra_rolls": extra_rolls,
        "luck_spent": actual_luck,
    }
    return total, details


def check_success(total: int, dv: int) -> bool:
    """
    Determine if a roll succeeds against a DV.
    Success = total exceeds DV (total > dv). Hitting the DV exactly is failure.
    Critical Success only adds another d10 to your roll; it does not auto-succeed.
    """
    return total > dv


def format_roll_details(details: dict, stat_val: int, skill_val: int, modifier: int = 0) -> str:
    """Build a readable breakdown string for a roll."""
    segments = [f"{stat_val} + {skill_val} + {details['first_roll']}"]
    for roll_val, added in details.get("extra_rolls", []):
        if added:
            segments.append(f"+ {roll_val} (crit)")
        else:
            # Fumble: rolled another d10 and subtract it. Explain the -X as "2nd d10 = X"
            segments.append(f"- {roll_val} (fumble: 2nd d10 = {roll_val})")
    if modifier != 0:
        segments.append(f"{'+' if modifier > 0 else ''}{modifier}")
    if details.get("luck_spent", 0) > 0:
        segments.append(f"+ {details['luck_spent']} (luck)")
    return " ".join(segments)
