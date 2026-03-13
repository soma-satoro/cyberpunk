# world/fashion_data.py
# Cyberpunk RED fashion items from the core rulebook - costs by style and category.
# Each style has specific costs for Top, Jacket, Footwear, Jewelry, Mirrorshades, Glasses, Contact Lenses, Hats.
# Bottoms are included for completeness (table also has Bottoms column).

FASHION_STYLES = [
    "Bag Lady Chic",
    "Gang Colors",
    "Generic Chic",
    "Bohemian",
    "Leisurewear",
    "Nomad Leathers",
    "Asia Pop",
    "Urban Flash",
    "Businesswear",
    "High Fashion",
]

# Item categories that can be purchased (excluding Bottoms which uses same logic)
FASHION_CATEGORIES = [
    "Top",
    "Jacket",
    "Footwear",
    "Jewelry",
    "Mirrorshades",
    "Glasses",
    "Contact Lenses",
    "Hats",
]

# Cost in eb for each (style, category) - from core rulebook fashion table
# Format: FASHION_COSTS[(style, category)] = cost
FASHION_COSTS = {
    # Bag Lady Chic (Homeless, Ragged, Vagrant)
    ("Bag Lady Chic", "Bottoms"): 20,
    ("Bag Lady Chic", "Top"): 10,
    ("Bag Lady Chic", "Jacket"): 20,
    ("Bag Lady Chic", "Footwear"): 20,
    ("Bag Lady Chic", "Jewelry"): 20,
    ("Bag Lady Chic", "Mirrorshades"): 20,
    ("Bag Lady Chic", "Glasses"): 10,
    ("Bag Lady Chic", "Contact Lenses"): 10,
    ("Bag Lady Chic", "Hats"): 10,
    # Gang Colors (Dangerous, Violent, Rebellious)
    ("Gang Colors", "Bottoms"): 50,
    ("Gang Colors", "Top"): 20,
    ("Gang Colors", "Jacket"): 50,
    ("Gang Colors", "Footwear"): 20,
    ("Gang Colors", "Jewelry"): 50,
    ("Gang Colors", "Mirrorshades"): 20,
    ("Gang Colors", "Glasses"): 20,
    ("Gang Colors", "Contact Lenses"): 10,
    ("Gang Colors", "Hats"): 10,
    # Generic Chic (Standard, Colorful, Modular)
    ("Generic Chic", "Bottoms"): 50,
    ("Generic Chic", "Top"): 20,
    ("Generic Chic", "Jacket"): 50,
    ("Generic Chic", "Footwear"): 20,
    ("Generic Chic", "Jewelry"): 50,
    ("Generic Chic", "Mirrorshades"): 20,
    ("Generic Chic", "Glasses"): 20,
    ("Generic Chic", "Contact Lenses"): 10,
    ("Generic Chic", "Hats"): 10,
    # Bohemian (Folksy, Retro, Free Spirited)
    ("Bohemian", "Bottoms"): 50,
    ("Bohemian", "Top"): 20,
    ("Bohemian", "Jacket"): 50,
    ("Bohemian", "Footwear"): 50,
    ("Bohemian", "Jewelry"): 100,
    ("Bohemian", "Mirrorshades"): 50,
    ("Bohemian", "Glasses"): 50,
    ("Bohemian", "Contact Lenses"): 10,
    ("Bohemian", "Hats"): 10,
    # Leisurewear (Comfort, Agility, Athleticism)
    ("Leisurewear", "Bottoms"): 100,
    ("Leisurewear", "Top"): 20,
    ("Leisurewear", "Jacket"): 100,
    ("Leisurewear", "Footwear"): 50,
    ("Leisurewear", "Jewelry"): 100,
    ("Leisurewear", "Mirrorshades"): 50,
    ("Leisurewear", "Glasses"): 50,
    ("Leisurewear", "Contact Lenses"): 20,
    ("Leisurewear", "Hats"): 50,
    # Nomad Leathers (Western, Rugged, Tribal)
    ("Nomad Leathers", "Bottoms"): 100,
    ("Nomad Leathers", "Top"): 20,
    ("Nomad Leathers", "Jacket"): 100,
    ("Nomad Leathers", "Footwear"): 100,
    ("Nomad Leathers", "Jewelry"): 100,
    ("Nomad Leathers", "Mirrorshades"): 50,
    ("Nomad Leathers", "Glasses"): 50,
    ("Nomad Leathers", "Contact Lenses"): 20,
    ("Nomad Leathers", "Hats"): 100,
    # Asia Pop (Bright, Costume-like, Youthful)
    ("Asia Pop", "Bottoms"): 100,
    ("Asia Pop", "Top"): 20,
    ("Asia Pop", "Jacket"): 100,
    ("Asia Pop", "Footwear"): 100,
    ("Asia Pop", "Jewelry"): 100,
    ("Asia Pop", "Mirrorshades"): 100,
    ("Asia Pop", "Glasses"): 100,
    ("Asia Pop", "Contact Lenses"): 100,
    ("Asia Pop", "Hats"): 100,
    # Urban Flash (Flashy, Technological, Streetwear)
    ("Urban Flash", "Bottoms"): 100,
    ("Urban Flash", "Top"): 20,
    ("Urban Flash", "Jacket"): 100,
    ("Urban Flash", "Footwear"): 100,
    ("Urban Flash", "Jewelry"): 100,
    ("Urban Flash", "Mirrorshades"): 100,
    ("Urban Flash", "Glasses"): 100,
    ("Urban Flash", "Contact Lenses"): 100,
    ("Urban Flash", "Hats"): 100,
    # Businesswear (Leadership, Presence, Authority)
    ("Businesswear", "Bottoms"): 500,
    ("Businesswear", "Top"): 50,
    ("Businesswear", "Jacket"): 500,
    ("Businesswear", "Footwear"): 500,
    ("Businesswear", "Jewelry"): 5000,
    ("Businesswear", "Mirrorshades"): 500,
    ("Businesswear", "Glasses"): 500,
    ("Businesswear", "Contact Lenses"): 100,
    ("Businesswear", "Hats"): 500,
    # High Fashion (Exclusive, Designer, Couture)
    ("High Fashion", "Bottoms"): 1000,
    ("High Fashion", "Top"): 500,
    ("High Fashion", "Jacket"): 1000,
    ("High Fashion", "Footwear"): 5000,
    ("High Fashion", "Jewelry"): 5000,
    ("High Fashion", "Mirrorshades"): 1000,
    ("High Fashion", "Glasses"): 1000,
    ("High Fashion", "Contact Lenses"): 1000,
    ("High Fashion", "Hats"): 5000,
}


def get_fashion_item_cost(style, category):
    """Return cost in eb for a fashion item, or None if not found."""
    return FASHION_COSTS.get((style, category))


def get_fashion_item_name(style, category):
    """Return the gear name for a fashion item (e.g. 'Generic Chic Top')."""
    return f"{style} {category}"


def build_fashion_gear_list():
    """
    Build list of gear dicts for equipment_data - one entry per (style, category) with name and value.
    Used to populate equipment_data.gears with all fashion items.
    """
    result = []
    for style in FASHION_STYLES:
        for category in FASHION_CATEGORIES:
            cost = FASHION_COSTS.get((style, category))
            if cost is not None:
                result.append({
                    "name": get_fashion_item_name(style, category),
                    "category": "Clothing",
                    "description": f"{style} {category} - Cyberpunk RED fashion from the core rulebook.",
                    "weight": 0.5,
                    "value": cost,
                })
        # Also add Bottoms for each style
        cost = FASHION_COSTS.get((style, "Bottoms"))
        if cost is not None:
            result.append({
                "name": get_fashion_item_name(style, "Bottoms"),
                "category": "Clothing",
                "description": f"{style} Bottoms - Cyberpunk RED fashion from the core rulebook.",
                "weight": 0.5,
                "value": cost,
            })
    return result
