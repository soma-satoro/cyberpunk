"""
Tag-based vendor system: maps room tags to equipment categories.

Rooms with vendor tags (set via +room/tag) become vendor locations. Players use
`list` and `buy` without specifying a merchant - the room's tags determine what
is available.

Tags can be broad (ranged, melee, weapons, armor, gear, cyberware) or tight
(handguns, shoulder_arms, drugs, medical, etc.). Use +room/tag here=handguns,drugs
to create a room that sells handguns and drugs.
"""

# Tag -> (main_type, subcategory_or_filter)
# main_type: weapons, armor, gear, cyberware
# subcategory: weapon category (handgun, shoulder_arms, etc.), gear category (Medical, Drugs, etc.),
#   or cyberware type. None = all of that main type.
#
# For weapons, "ranged" and "melee" are broad tags that map to multiple subcategories.
VENDOR_TAG_MAPPING = {
    # Broad weapon tags
    "ranged": ("weapons", ["handgun", "shoulder_arms", "archery", "heavy_weapons"]),
    "melee": ("weapons", ["melee", "brawling"]),
    "weapons": ("weapons", None),  # All weapons
    # Tight weapon tags (exact category match)
    "handguns": ("weapons", "handgun"),
    "handgun": ("weapons", "handgun"),
    "shoulder_arms": ("weapons", "shoulder_arms"),
    "archery": ("weapons", "archery"),
    "heavy_weapons": ("weapons", "heavy_weapons"),
    "melee_weapons": ("weapons", "melee"),
    "brawling": ("weapons", "brawling"),
    # Armor
    "armor": ("armor", None),
    "armour": ("armor", None),
    # Gear - broad and tight
    "gear": ("gear", None),
    "medical": ("gear", "Medical"),
    "drugs": ("gear", "Drugs"),
    "electronics": ("gear", "Electronics"),
    "tools": ("gear", "Tools"),
    "clothing": ("gear", "Clothing"),
    "cyberdecks": ("gear", "Cyberdeck"),
    "cyberdeck": ("gear", "Cyberdeck"),
    # Cyberware (body implants - replaces ripperdoc NPCs)
    "cyberware": ("cyberware", None),
    "ripperdoc": ("cyberware", None),  # Alias for cyberware
}

# Category for room tags used for vending (so we can distinguish from other tags)
VENDOR_TAG_CATEGORY = "vendor"


def get_room_vendor_tags(room):
    """
    Get vendor-relevant tags from a room.
    Checks room.db.tags (list) and room.tags with category=VENDOR_TAG_CATEGORY.
    Returns set of lowercase tag strings that match VENDOR_TAG_MAPPING.
    """
    tags = set()
    # room.db.tags - list set via +room/tag
    db_tags = getattr(room.db, "tags", None) or []
    for t in db_tags:
        if t and isinstance(t, str):
            key = t.strip().lower().replace(" ", "_")
            if key in VENDOR_TAG_MAPPING:
                tags.add(key)
    # Also check Evennia tag system with vendor category
    if hasattr(room, "tags"):
        for tag in room.tags.get(category=VENDOR_TAG_CATEGORY) or []:
            key = str(tag).strip().lower().replace(" ", "_")
            if key in VENDOR_TAG_MAPPING:
                tags.add(key)
    return tags


def is_vendor_room(room):
    """Return True if the room has any vendor tags."""
    return bool(room and get_room_vendor_tags(room))


def get_vendor_catalog_filters(room):
    """
    Given a vendor room, return a list of (main_type, subcategory) filters.
    Each filter defines what items to include. For weapons with multiple
    subcategories (e.g. "ranged"), we expand to multiple filters.
    """
    vendor_tags = get_room_vendor_tags(room)
    if not vendor_tags:
        return []

    filters = set()
    for tag in vendor_tags:
        mapping = VENDOR_TAG_MAPPING.get(tag)
        if not mapping:
            continue
        main_type, sub = mapping
        if sub is None:
            filters.add((main_type, None))
        elif isinstance(sub, list):
            for s in sub:
                filters.add((main_type, s))
        else:
            filters.add((main_type, sub))

    return list(filters)


def item_matches_vendor_filters(item_info, filters):
    """
    Check if an item (dict from catalog) matches any of the vendor filters.
    item_info: dict with _type, category, _cyberware, etc.
    filters: list of (main_type, subcategory) from get_vendor_catalog_filters.
    """
    for main_type, subcategory in filters:
        if main_type == "weapons":
            if item_info.get("_type") != "weapon":
                continue
            cat = item_info.get("category", "")
            if subcategory is None:
                return True
            if isinstance(subcategory, list):
                if str(cat).lower() in [str(s).lower() for s in subcategory]:
                    return True
            elif str(cat).lower() == str(subcategory).lower():
                return True
        elif main_type == "armor":
            if item_info.get("_type") == "armor":
                return True
        elif main_type == "gear":
            itype = item_info.get("_type")
            cat = item_info.get("category", "")
            if itype == "cyberdeck":
                if subcategory is None or str(subcategory).lower() == "cyberdeck":
                    return True
            elif itype == "gear" and cat and cat != "Cyberware":
                if subcategory is None:
                    return True
                if str(cat).lower() == str(subcategory).lower():
                    return True
        elif main_type == "cyberware":
            if item_info.get("_type") == "cyberware_implant":
                cw = item_info.get("_cyberware")
                if cw:
                    cw_type = getattr(cw, "type", "")
                    if subcategory is None or str(cw_type).lower() == str(subcategory).lower():
                        return True
            elif item_info.get("category") == "Cyberware":
                if subcategory is None:
                    return True
    return False


def get_available_main_categories(room):
    """
    Return the main categories (weapons, armor, gear, cyberware) that this
    vendor room offers, for menu display.
    """
    filters = get_vendor_catalog_filters(room)
    return sorted(set(mt for mt, _ in filters))


def get_available_subcategories(room, main_category):
    """
    Return subcategories for a main category in this vendor room.
    """
    filters = get_vendor_catalog_filters(room)
    subs = [sc for mt, sc in filters if mt == main_category and sc]
    return sorted(set(subs))
