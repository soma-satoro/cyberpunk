"""
Rental data for apartment types, costs, and room layouts.

Based on Cyberpunk Red/Edgerunners Real Estate table.
All costs in Eurodollars (eb).
"""

# Exit name to alias mapping for child rooms
ROOM_EXIT_ALIASES = {
    "Bedroom 1": "B1",
    "Bedroom 2": "B2",
    "Bedroom 3": "B3",
    "Side Room": "SR",
    "Yard": "YA",
    "Attic": "AT",
    "Patio": "PT",
}
OUT_EXIT_ALIAS = "O"

# Apartment types with rent, purchase cost, room count, and room layout
# room_layout: list of (room_name, exit_alias) - Main room is always first
# Rooms connect to main room via "Out" (alias O)
RENTAL_TYPES = {
    "Living on The Street": {
        "rent": None,
        "purchase": None,
        "rooms": 1,
        "room_layout": [("Main Room", None)],
        "max_co_residents": 0,
        "max_partners": 0,
        "role_required": None,
    },
    "Living on The Street in a Vehicle": {
        "rent": None,
        "purchase": None,
        "rooms": 1,
        "room_layout": [("Main Room", None)],
        "max_co_residents": 0,
        "max_partners": 0,
        "role_required": None,
    },
    "Cube Hotel": {
        "rent": 500,
        "purchase": None,
        "rooms": 1,
        "room_layout": [("Main Room", None)],
        "max_co_residents": 0,
        "max_partners": 1,
        "role_required": None,
    },
    "Cargo Container": {
        "rent": 1000,
        "purchase": 15000,
        "rooms": 1,
        "room_layout": [("Main Room", None)],
        "max_co_residents": 0,
        "max_partners": 1,
        "role_required": None,
    },
    "Studio Apartment": {
        "rent": 1500,
        "purchase": 25000,
        "rooms": 1,
        "room_layout": [("Main Room", None)],
        "max_co_residents": 0,
        "max_partners": 1,
        "role_required": None,
    },
    "One-Bedroom Apartment": {
        "rent": 2000,
        "purchase": 30000,
        "rooms": 2,
        "room_layout": [
            ("Main Room", None),
            ("Bedroom", "B1"),
        ],
        "max_co_residents": 1,
        "max_partners": 1,
        "role_required": None,
    },
    "Two-Bedroom Apartment": {
        "rent": 2500,
        "purchase": 35000,
        "rooms": 3,
        "room_layout": [
            ("Main Room", None),
            ("Bedroom 1", "B1"),
            ("Bedroom 2", "B2"),
        ],
        "max_co_residents": 2,
        "max_partners": 1,
        "role_required": None,
    },
    "Corporate Conapt": {
        "rent": 0,  # Given by Corp
        "purchase": None,
        "rooms": 3,
        "room_layout": [
            ("Main Room", None),
            ("Bedroom", "B1"),
            ("Side Room", "SR"),
        ],
        "max_co_residents": 2,
        "max_partners": 1,
        "role_required": "Exec",
    },
    "Upscale Conapt": {
        "rent": 7500,
        "purchase": 85000,
        "rooms": 4,
        "room_layout": [
            ("Main Room", None),
            ("Bedroom 1", "B1"),
            ("Bedroom 2", "B2"),
            ("Side Room", "SR"),
        ],
        "max_co_residents": 3,
        "max_partners": 1,
        "role_required": None,
    },
    "Luxury Penthouse": {
        "rent": 15000,
        "purchase": 150000,
        "rooms": 5,
        "room_layout": [
            ("Main Room", None),
            ("Bedroom 1", "B1"),
            ("Bedroom 2", "B2"),
            ("Side Room", "SR"),
            ("Patio", "PT"),
        ],
        "max_co_residents": 3,
        "max_partners": 1,
        "role_required": None,
    },
    "Corporate Beaverville House": {
        "rent": 0,  # Given by Corp
        "purchase": 200000,
        "rooms": 5,
        "room_layout": [
            ("Main Room", None),
            ("Bedroom 1", "B1"),
            ("Bedroom 2", "B2"),
            ("Side Room", "SR"),
            ("Yard", "YA"),
        ],
        "max_co_residents": 3,
        "max_partners": 1,
        "role_required": None,
    },
    "Corporate Beaverville McMansion": {
        "rent": 0,  # Given by Corp
        "purchase": 500000,
        "rooms": 6,
        "room_layout": [
            ("Main Room", None),
            ("Bedroom 1", "B1"),
            ("Bedroom 2", "B2"),
            ("Bedroom 3", "B3"),
            ("Side Room", "SR"),
            ("Yard", "YA"),
        ],
        "max_co_residents": 3,
        "max_partners": 1,
        "role_required": None,
    },
    "Custom": {
        "rent": None,  # Set per-apartment by staff
        "purchase": None,
        "rooms": 1,
        "room_layout": [("Main Room", None)],
        "max_co_residents": 3,
        "max_partners": 1,
        "role_required": None,
    },
    "Encampment": {
        "rent": 0,
        "purchase": None,
        "rooms": 1,
        "room_layout": [("Main Room", None)],
        "max_co_residents": 0,
        "max_partners": 1,
        "role_required": None,
    },
}

# Types that support cost modification by staff (exclude free corp housing)
RENTABLE_TYPES = [
    k for k, v in RENTAL_TYPES.items()
    if v["rent"] is not None or v["purchase"] is not None
]

# Default max units per floor
DEFAULT_MAX_UNITS_PER_FLOOR = 6

# Ordinal words for floor name parsing (name -> number)
FLOOR_NAME_TO_NUM = {
    "first": 1, "1st": 1, "lobby": 1, "one": 1,
    "second": 2, "2nd": 2, "two": 2,
    "third": 3, "3rd": 3, "three": 3,
    "fourth": 4, "4th": 4, "four": 4,
    "fifth": 5, "5th": 5, "five": 5,
    "sixth": 6, "6th": 6, "six": 6,
    "seventh": 7, "7th": 7, "seven": 7,
    "eighth": 8, "8th": 8, "eight": 8, "eigth": 8,  # "eigth" common typo
    "ninth": 9, "9th": 9, "nine": 9,
    "tenth": 10, "10th": 10, "ten": 10,
    "eleventh": 11, "11th": 11, "eleven": 11,
    "twelfth": 12, "12th": 12, "twelve": 12,
    "thirteenth": 13, "13th": 13,
    "fourteenth": 14, "14th": 14,
    "fifteenth": 15, "15th": 15,
    "sixteenth": 16, "16th": 16,
    "seventeenth": 17, "17th": 17,
    "eighteenth": 18, "18th": 18,
    "nineteenth": 19, "19th": 19,
    "twentieth": 20, "20th": 20, "twenty": 20,
    "twenty-first": 21, "21st": 21, "twentyfirst": 21,
    "twenty-second": 22, "22nd": 22,
    "twenty-third": 23, "23rd": 23,
    "twenty-fourth": 24, "24th": 24,
    "twenty-fifth": 25, "25th": 25,
}


def parse_floor_from_room_name(room_name):
    """
    Extract floor number from room name. E.g. 'Third Floor' -> 3, '21st Floor' -> 21.
    Only parses when 'floor' appears in the name (avoids false matches like 'Sixth Street').
    Returns int or None if not parseable.
    """
    import re
    if not room_name or not isinstance(room_name, str):
        return None
    name = room_name.strip().lower()
    # Must contain "floor" to avoid false matches (e.g. "Sixth Street")
    if "floor" not in name:
        return None
    # Prefer explicit patterns: "3rd floor", "floor 3", "third floor"
    m = re.search(r"(\d+)(?:st|nd|rd|th)?\s*floor|floor\s*(\d+)", name)
    if m:
        for g in m.groups():
            if g:
                return int(g)
    # Word match: only match ordinals that appear adjacent to "floor"
    # e.g. "third floor", "first floor", "lobby floor"
    floor_match = re.search(r"(\w+)\s+floor|floor\s+(\w+)", name)
    if floor_match:
        for g in floor_match.groups():
            if g and g in FLOOR_NAME_TO_NUM:
                return FLOOR_NAME_TO_NUM[g]
    return None


def get_custom_room_layout(num_rooms):
    """
    Generate room layout for custom/bespoke apartments.
    num_rooms: total rooms (1 = main only, 2+ = main + Room 2, Room 3, ...)
    Returns list of (room_name, exit_alias) tuples.
    """
    if num_rooms < 1:
        num_rooms = 1
    layout = [("Main Room", None)]
    for i in range(2, num_rooms + 1):
        layout.append((f"Room {i}", f"R{i}"))
    return layout
