"""
HP (Hit Points) lookup table per Cyberpunk Red rules.
HP is determined by BODY (2-15) and WILL (2-10).
Values outside range are clamped to the nearest valid index.
"""

# HP chart: [WILL][BODY] - WILL 2-10 (index 0-8), BODY 2-15 (index 0-13)
# Rows = WILL 2..10, Cols = BODY 2..15
HP_CHART = [
    # WILL 2: BODY 2-15
    [20, 25, 25, 30, 30, 35, 35, 40, 40, 45, 45, 50, 50, 55],
    # WILL 3
    [25, 25, 30, 30, 35, 35, 40, 40, 45, 45, 50, 50, 55, 55],
    # WILL 4
    [25, 30, 30, 35, 35, 40, 40, 45, 45, 50, 50, 55, 55, 60],
    # WILL 5
    [30, 30, 35, 35, 40, 40, 45, 45, 50, 50, 55, 55, 60, 60],
    # WILL 6
    [30, 35, 35, 40, 40, 45, 45, 50, 50, 55, 55, 60, 60, 65],
    # WILL 7
    [35, 35, 40, 40, 45, 45, 50, 50, 55, 55, 60, 60, 65, 65],
    # WILL 8
    [35, 40, 40, 45, 45, 50, 50, 55, 55, 60, 60, 65, 65, 70],
    # WILL 9
    [40, 40, 45, 45, 50, 50, 55, 55, 60, 60, 65, 65, 70, 70],
    # WILL 10
    [40, 45, 45, 50, 50, 55, 55, 60, 60, 65, 65, 70, 70, 75],
]


def get_hp_from_chart(body, willpower):
    """
    Look up HP from the official chart. BODY 2-15, WILL 2-10.
    Values outside range are clamped to the nearest valid index.
    """
    body = int(body or 0)
    willpower = int(willpower or 0)
    # Clamp to chart range: BODY 2-15, WILL 2-10
    body_idx = max(0, min(13, body - 2))
    will_idx = max(0, min(8, willpower - 2))
    return HP_CHART[will_idx][body_idx]
