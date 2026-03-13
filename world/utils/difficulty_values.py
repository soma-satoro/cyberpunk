"""Difficulty Values (DV) for skill checks - from Cyberpunk Red."""

DIFFICULTY_VALUES = {
    9: ("Simple", "This is something most people can do without thinking, but which might be hard for a small child."),
    13: ("Everyday", "This feat is something most people can do without a lot of special training."),
    15: ("Difficult", "This feat is difficult to accomplish without training or natural talent."),
    17: ("Professional", "This feat takes actual training and the user can be considered to be a professional, skilled in their abilities."),
    21: ("Heroic", "This is a highly skilled feat; one that only the best of the best can pull off. This is the level of sports stars and other highly regarded superstars."),
    24: ("Incredible", "This is a tremendous feat. Pulling this off would rate you among the very best of your class professionally. You are of truly Olympian mettle."),
    29: ("Legendary", "An awe-inspiring feat. This is something people write stories about; a truly amazing accomplishment that will be spoken of in hushed tones for years to come."),
}
DIFFICULTY_NAMES = {name.lower(): (dv, desc) for dv, (name, desc) in DIFFICULTY_VALUES.items()}


def parse_dv(vs_str):
    """
    Parse DV from numeric or named difficulty.
    Returns (dv, difficulty_name, description) or None.
    """
    vs_str = vs_str.strip().lower()
    # Try numeric first
    try:
        dv = int(vs_str)
        if dv in DIFFICULTY_VALUES:
            name, desc = DIFFICULTY_VALUES[dv]
            return (dv, name, desc)
        return (dv, None, None)
    except ValueError:
        pass
    # Try named difficulty
    if vs_str in DIFFICULTY_NAMES:
        dv, desc = DIFFICULTY_NAMES[vs_str]
        name = DIFFICULTY_VALUES[dv][0]
        return (dv, name, desc)
    return None
