# -*- coding: utf-8 -*-
"""
Maker (Tech Role Ability) constants for fabrication, upgrade, and invention.
Based on Cyberpunk Red core rulebook Maker expertise rules.
"""

# Price categories for Maker DV/Time table (Cheap/Everyday combined per rulebook)
# Order: index 0 = Cheap/Everyday, 1 = Costly, 2 = Premium, 3 = Expensive, 4 = Very Expensive, 5 = Luxury, 6 = Super Luxury
MAKER_PRICE_CATEGORIES = (
    "Cheap/Everyday",
    "Costly",
    "Premium",
    "Expensive",
    "Very Expensive",
    "Luxury",
    "Super Luxury",
)

# DV and time per price category (from rulebook p.149)
# Super Luxury: time = 1 month per 10,000eb of cost
MAKER_DV_BY_CATEGORY = {
    "Cheap/Everyday": 9,
    "Costly": 13,
    "Premium": 17,
    "Expensive": 21,
    "Very Expensive": 24,
    "Luxury": 29,
    "Super Luxury": 29,
}

# Time in hours for each category (Super Luxury uses value-based calculation)
MAKER_TIME_HOURS_BY_CATEGORY = {
    "Cheap/Everyday": 1,
    "Costly": 6,
    "Premium": 24,  # 1 day
    "Expensive": 24 * 7,  # 1 week
    "Very Expensive": 24 * 14,  # 2 weeks
    "Luxury": 24 * 30,  # 1 month
    "Super Luxury": None,  # 1 month per 10,000eb - calculated from value
}

# Value (eb) thresholds for price category (Cyberpunk Red)
# Cheap: 0-20, Everyday: 21-50, Costly: 51-100, Premium: 101-500, Expensive: 501-1000
# Very Expensive: 1001-5000, Luxury: 5001-10000, Super Luxury: 10001+
# (threshold, category) - first match where value <= threshold
VALUE_TO_PRICE_CATEGORY = [
    (20, "Cheap/Everyday"),
    (50, "Cheap/Everyday"),
    (100, "Costly"),
    (500, "Premium"),
    (1000, "Expensive"),
    (5000, "Very Expensive"),
    (10000, "Luxury"),
]


def value_to_price_category(value):
    """Convert item value (eb) to Maker price category."""
    if value is None or value < 0:
        return "Cheap/Everyday"
    if value > 10000:
        return "Super Luxury"
    for threshold, category in VALUE_TO_PRICE_CATEGORY:
        if value <= threshold:
            return category
    return "Super Luxury"


def get_maker_dv(price_category):
    """Get DV for a price category."""
    return MAKER_DV_BY_CATEGORY.get(price_category, 29)


def get_maker_time_hours(price_category, value=None):
    """
    Get fabrication/upgrade time in hours for a price category.
    Super Luxury: 1 month (720 hours) per 10,000eb.
    """
    if price_category == "Super Luxury" and value is not None:
        months = max(1, value / 10000)
        return int(24 * 30 * months)
    return MAKER_TIME_HOURS_BY_CATEGORY.get(price_category, 720) or 720


def get_materials_cost_fabrication(value, price_category):
    """
    Fabrication: materials one price category lower than item.
    Super Luxury: materials = half the item's price (per rulebook).
    Cheap/Everyday: 5eb (per rulebook p.149).
    """
    if price_category == "Super Luxury":
        return max(1, value // 2)
    if price_category == "Cheap/Everyday":
        return 5  # "Fabricating a Cheap item costs 5eb" - rulebook p.149
    # One category lower - approximate midpoints
    _MATERIALS_BY_CATEGORY = {
        "Costly": 25,       # Cheap/Everyday midpoint
        "Premium": 75,      # Costly midpoint
        "Expensive": 300,   # Premium midpoint
        "Very Expensive": 1500,  # Expensive midpoint
        "Luxury": 5000,    # Very Expensive midpoint
    }
    return _MATERIALS_BY_CATEGORY.get(price_category, max(5, value // 2))


def get_materials_cost_upgrade(value, price_category):
    """Upgrade: materials same price category as item. Vehicle upgrades = Very Expensive (1000eb)."""
    if price_category == "Super Luxury":
        return value  # Same category = full value for materials
    cat_idx = MAKER_PRICE_CATEGORIES.index(price_category) if price_category in MAKER_PRICE_CATEGORIES else 0
    lower_bounds = [20, 50, 100, 500, 1000, 5000, 10000]
    if cat_idx < len(lower_bounds):
        low = 0 if cat_idx == 0 else lower_bounds[cat_idx - 1]
        high = lower_bounds[cat_idx]
        return (low + high) // 2
    return value


# Tech skill mapping: item type/category -> TECH skill used for repair/fabrication
# From rulebook: Basic Tech, Cybertech, Electronics/Security Tech, Weaponstech, Land/Sea/Air Vehicle Tech
ITEM_TYPE_TO_TECH_SKILL = {
    "weapon": "weaponstech",
    "armor": "basic_tech",  # Armor/fashion typically Basic Tech
    "gear": None,  # Resolved by category
    "cyberware": "cybertech",
    "ammunition": "weaponstech",
    "vehicle": None,  # Resolved by vehicle category
    "cyberdeck": "electronics",
}

# Gear category -> tech skill
GEAR_CATEGORY_TO_TECH_SKILL = {
    "Electronics": "electronics",
    "Tools": "basic_tech",
    "Medical": "basic_tech",
    "Drugs": "basic_tech",  # MedTech pharma uses Medical Tech
    "Clothing": "basic_tech",
    "Survival": "basic_tech",
    "Optics": "basic_tech",
    "Music": "basic_tech",
    "Cyberware": "cybertech",
}

# Vehicle category -> tech skill
VEHICLE_CATEGORY_TO_TECH_SKILL = {
    "land": "land_vehicle_tech",
    "sea": "sea_vehicle_tech",
    "air": "air_vehicle_tech",
}


def get_tech_skill_for_item(item_type, category=None):
    """
    Get the TECH skill key (CharacterSheet field name) for an item.
    Used for: TECH + tech_skill + specialty + 1d10 vs DV
    """
    skill = ITEM_TYPE_TO_TECH_SKILL.get(item_type)
    if skill:
        return skill
    if item_type == "gear" and category:
        return GEAR_CATEGORY_TO_TECH_SKILL.get(category, "basic_tech")
    if item_type == "vehicle" and category:
        return VEHICLE_CATEGORY_TO_TECH_SKILL.get((category or "").lower(), "land_vehicle_tech")
    return "basic_tech"
