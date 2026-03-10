# world/commerce/pricing.py
"""
Commerce pricing rules: expensive item thresholds, role-based discounts,
and purchase eligibility for weapons, armor, gear, cyberware, cyberdecks, and programs.
"""

# Items over this value (eb) are "very expensive" - chargen-only for non-role buyers
EXPENSIVE_THRESHOLD = 1000

# Max discount cap (base 10% + up to 50% from ability = 60% max)
MAX_DISCOUNT_PERCENT = 60
BASE_ROLE_DISCOUNT_PERCENT = 10
ABILITY_DISCOUNT_PER_LEVEL_PERCENT = 5

# Role -> (ability_skill_name, eligible_categories for discount AND for 1000+ purchase)
ROLE_CONFIG = {
    "Fixer": {
        "ability": "operator",
        "categories": {"weapon", "armor", "Survival", "Tools", "Electronics"},
    },
    "Medtech": {
        "ability": "medicine",
        "categories": {"Drugs", "Medical", "cyberware"},  # cyberware is special
    },
    "Netrunner": {
        "ability": "interface",
        "categories": {"cyberdeck", "Electronics", "program"},
    },
    "Tech": {
        "ability": "maker",
        "categories": {"Electronics", "Tools", "upgrade"},
    },
    "Nomad": {
        "ability": "moto",
        "categories": {"vehicle"},
    },
}


def get_role_ability_level(character):
    """Get the character's role ability level (0-10 typically)."""
    role = _get_character_role(character)
    if not role or role not in ROLE_CONFIG:
        return 0
    ability_name = ROLE_CONFIG[role]["ability"]
    skills = getattr(character.db, "skills", None) or {}
    level = skills.get(ability_name, 0)
    # Fallback to character sheet if skills not synced (e.g. moto for Nomad)
    if level == 0 and hasattr(character, "character_sheet") and character.character_sheet:
        level = getattr(character.character_sheet, ability_name, 0) or 0
    return level


def _get_character_role(character):
    """Get character's role string, checking typeclass then sheet."""
    if hasattr(character, "db") and hasattr(character.db, "role"):
        r = character.db.role
        if r:
            return str(r).capitalize()
    if hasattr(character, "character_sheet") and character.character_sheet:
        return getattr(character.character_sheet, "role", None)
    return None


def _item_matches_role_category(item_info, role_categories, item_type, gear_category=None):
    """
    Check if an item falls into one of the role's eligible categories.
    item_info: dict with 'name', possibly 'category', 'value'
    item_type: 'weapon', 'armor', 'gear', 'cyberware', 'cyberdeck', 'program', 'upgrade'
    gear_category: for gear items, the category string (e.g. 'Electronics', 'Tools')
    """
    if not role_categories:
        return False
    role_cats_lower = {c.lower() for c in role_categories}
    # Direct type matches
    if item_type.lower() in role_cats_lower:
        return True
    if item_type == "weapon" and "weapon" in role_cats_lower:
        return True
    if item_type == "armor" and "armor" in role_cats_lower:
        return True
    if item_type == "gear" and gear_category:
        return gear_category in role_categories
    if item_type == "cyberware" and "cyberware" in role_cats_lower:
        return True
    if item_type == "cyberdeck" and "cyberdeck" in role_cats_lower:
        return True
    if item_type == "program" and "program" in role_cats_lower:
        return True
    if item_type == "upgrade" and "upgrade" in role_cats_lower:
        return True
    if item_type == "vehicle" and "vehicle" in role_cats_lower:
        return True
    return False


def can_purchase_expensive_from_vendor(character, item_value, item_type, gear_category=None):
    """
    Can this character buy an item over EXPENSIVE_THRESHOLD from a vendor?
    True if: item_value <= EXPENSIVE_THRESHOLD, OR character has a role that allows
    expensive purchase in this item's category.
    """
    if item_value <= EXPENSIVE_THRESHOLD:
        return True
    role = _get_character_role(character)
    if not role or role not in ROLE_CONFIG:
        return False
    config = ROLE_CONFIG[role]
    item_info = {"value": item_value}
    return _item_matches_role_category(item_info, config["categories"], item_type, gear_category)


def get_purchase_discount_percent(character, item_type, gear_category=None):
    """
    Returns the discount percent (0-60) for this character buying this item type.
    """
    role = _get_character_role(character)
    if not role or role not in ROLE_CONFIG:
        return 0
    config = ROLE_CONFIG[role]
    if not _item_matches_role_category({}, config["categories"], item_type, gear_category):
        return 0
    ability_level = get_role_ability_level(character)
    discount = BASE_ROLE_DISCOUNT_PERCENT + (ability_level * ABILITY_DISCOUNT_PER_LEVEL_PERCENT)
    return min(discount, MAX_DISCOUNT_PERCENT)


def calculate_final_price(base_price, discount_percent):
    """Apply discount to base price, return integer cost."""
    if discount_percent <= 0:
        return base_price
    mult = 1 - (discount_percent / 100.0)
    return max(1, int(base_price * mult))


def is_expensive_item(value):
    """Items over 1000 eb are 'very expensive'."""
    return value > EXPENSIVE_THRESHOLD
