"""
Weapon-related constants: clip chart, quality pricing, attachment data.
"""

# Clip Chart: weapon_type -> (standard, extended, drum)
# From CPR Core Book
CLIP_CHART = {
    "medium pistol": (12, 18, 36),
    "heavy pistol": (8, 14, 28),
    "very heavy pistol": (8, 14, 28),
    "SMG": (30, 40, 50),
    "heavy smg": (40, 50, 60),
    "shotgun": (4, 8, 16),
    "assault rifle": (25, 35, 45),
    "sniper rifle": (4, 8, 12),
    "grenade launcher": (2, 4, 6),
    "rocket launcher": (1, 2, 3),
    "machine pistol": (30, 40, 50),
    "machine gun": (200, 200, 200),  # No extended/drum in chart; use standard
}

# Fallback for weapon types not in chart (e.g. "handgun" category)
CLIP_CHART_FALLBACK = (10, 15, 30)


def get_clip_size(weapon_type, magazine_type="standard"):
    """
    Get clip size for weapon type and magazine attachment.
    magazine_type: "standard", "extended", "drum"
    """
    wt = (weapon_type or "").strip().lower()
    entry = CLIP_CHART.get(wt) or CLIP_CHART.get(wt.replace(" ", "_")) or CLIP_CHART_FALLBACK
    if magazine_type == "extended":
        return entry[1]
    if magazine_type == "drum":
        return entry[2]
    return entry[0]


def get_effective_clip(weapon, inventory=None):
    """
    Get effective clip size for a weapon, considering Extended/Drum Magazine attachments.
    If inventory is provided, checks InventoryWeapon.installed_attachments for clip_modifier.
    Otherwise falls back to weapon.clip (standard).
    """
    base_clip = getattr(weapon, "clip", 0) or 0
    if not inventory:
        return base_clip
    try:
        from world.inventory.models import InventoryWeapon
        iw = InventoryWeapon.objects.filter(inventory=inventory, weapon=weapon).first()
        if not iw:
            return base_clip
        for att in iw.installed_attachments.all():
            mod = (att.clip_modifier or "").strip().lower()
            if mod in ("extended", "drum"):
                return get_clip_size(getattr(weapon, "weapon_type", "") or "", mod)
    except Exception:
        pass
    return base_clip


def get_quality_price(base_value, quality):
    """
    Get price for weapon at given quality. Base value is standard price.
    User-specified mappings:
    - 1000 standard -> poor 500, excellent 5000
    - 5000 standard -> poor 1000, excellent 10000
    - 10000 standard -> poor 5000, excellent 15000
    Interpolate for values in between.
    """
    q = (quality or "").strip().lower()
    if q == "standard":
        return base_value
    if base_value <= 0:
        return base_value
    if q == "poor":
        if base_value <= 1000:
            return int(base_value * 0.5)
        if base_value <= 5000:
            return int(500 + (1000 - 500) * (base_value - 1000) / 4000)
        if base_value <= 10000:
            return int(1000 + (5000 - 1000) * (base_value - 5000) / 5000)
        return int(base_value * 0.5)
    if q == "excellent":
        if base_value <= 1000:
            return int(base_value * 5)
        if base_value <= 5000:
            return int(5000 + (10000 - 5000) * (base_value - 1000) / 4000)
        if base_value <= 10000:
            return int(10000 + (15000 - 10000) * (base_value - 5000) / 5000)
        return int(base_value * 1.5)
    return base_value


# Core book attachments: name, cost_eb, cost_category, eligible, slot_cost, clip_modifier
# eligible: "all_ranged", "shoulder_arms", "all_except_bow"
# clip_modifier: None (use weapon clip), "extended", "drum"
ATTACHMENT_DATA = [
    {
        "name": "Bayonet",
        "cost": 100,
        "cost_category": "Premium",
        "eligible": "shoulder_arms",
        "slot_cost": 1,
        "clip_modifier": None,
        "description": "When wielded, this weapon can also be used as a Light Melee Weapon. Cannot conceal while attached.",
    },
    {
        "name": "Drum Magazine",
        "cost": 500,
        "cost_category": "Expensive",
        "eligible": "all_except_bow",
        "slot_cost": 1,
        "clip_modifier": "drum",
        "description": "Weapon holds Drum entry from Clip Chart. Only one clip attachment. Cannot conceal while attached.",
    },
    {
        "name": "Extended Magazine",
        "cost": 100,
        "cost_category": "Premium",
        "eligible": "all_except_bow",
        "slot_cost": 1,
        "clip_modifier": "extended",
        "description": "Weapon holds Extended entry from Clip Chart. Only one clip attachment. Cannot conceal while attached.",
    },
    {
        "name": "Grenade Launcher Underbarrel",
        "cost": 500,
        "cost_category": "Expensive",
        "eligible": "shoulder_arms",
        "slot_cost": 2,
        "clip_modifier": None,
        "description": "When wielded in two hands, can also be used as Grenade Launcher (1 grenade). Cannot conceal while attached.",
    },
    {
        "name": "Infrared Nightvision Scope",
        "cost": 500,
        "cost_category": "Expensive",
        "eligible": "all_ranged",
        "slot_cost": 1,
        "clip_modifier": None,
        "description": "Reduces penalties from darkness, smoke, fog to 0. Can distinguish hot from cold.",
    },
    {
        "name": "Shotgun Underbarrel",
        "cost": 500,
        "cost_category": "Expensive",
        "eligible": "shoulder_arms",
        "slot_cost": 2,
        "clip_modifier": None,
        "description": "When wielded in two hands, can also be used as Shotgun (2 shots). Cannot conceal while attached.",
    },
    {
        "name": "Smartgun Link",
        "cost": 500,
        "cost_category": "Expensive",
        "eligible": "all_ranged",
        "slot_cost": 2,
        "clip_modifier": None,
        "description": "+1 to Ranged Attacks. Requires Interface Plugs or Subdermal Grip. Installing/uninstalling takes 1 hour.",
    },
    {
        "name": "Sniping Scope",
        "cost": 100,
        "cost_category": "Premium",
        "eligible": "all_ranged",
        "slot_cost": 1,
        "clip_modifier": None,
        "description": "See detail up to 800m. +1 to single shot or Aimed Shot at 51m+.",
    },
]

# Default attachment slots for non-exotic ranged weapons
DEFAULT_RANGED_ATTACHMENT_SLOTS = 3


def populate_core_attachments():
    """Create or update core book weapon attachments in the database."""
    from world.inventory.models import WeaponAttachment
    for data in ATTACHMENT_DATA:
        obj, created = WeaponAttachment.objects.update_or_create(
            name=data["name"],
            defaults={
                "value": data["cost"],
                "description": data.get("description", ""),
                "eligible_categories": [data["eligible"]],
                "requires_slot": True,
                "slot_cost": data["slot_cost"],
                "clip_modifier": data.get("clip_modifier") or "",
                "install_dv": 17,
                "install_skill": "Weaponstech",
            }
        )
    return len(ATTACHMENT_DATA)
