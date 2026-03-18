"""Parse modifier strings like +2, -3, -2+3+1-1 for attack/dodge rolls."""

import re


def parse_modifier_string(s):
    """
    Parse a modifier string that may contain multiple +/- numbers.
    Examples: "+2", "-3", "-2+3+1-1", "+3-1-4"
    Returns the sum as an integer, or 0 if invalid/empty.
    """
    if not s or not str(s).strip():
        return 0
    s = str(s).strip()
    # Match sequences of optional sign followed by digits: +2, -3, + 1, etc.
    parts = re.findall(r'([+-])\s*(\d+)|(\d+)', s)
    total = 0
    for m in parts:
        if m[2]:  # Just digits (no sign) - treat as positive
            total += int(m[2])
        else:
            sign, num = m[0], int(m[1])
            total += num if sign == '+' else -num
    return total
