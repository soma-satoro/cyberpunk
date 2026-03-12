"""
Improvement Points (IP) system for Cyberpunk MUSH.

Handles IP cost calculations, character IP storage, and configuration.
Cost tables based on Cyberpunk Red rules:
- Typical skills: 20 IP per level (level 1 = 20, level 2 = 40, etc.)
- Difficult (x2) skills: 40 IP per level
- Role abilities: 60 IP per rank
"""
from datetime import datetime

# Attributes that can be purchased with IP (stats 1-10)
IP_ATTRIBUTES = [
    "intelligence", "reflexes", "dexterity", "technology", "cool",
    "willpower", "luck", "move", "body", "empathy"
]

# Role abilities - use Role Ability cost table (60 per rank)
IP_ROLE_ABILITIES = [
    "charismatic_impact", "combat_awareness", "interface", "maker", "medicine",
    "credibility", "teamwork", "backup", "operator", "moto"
]

# Difficult skills (x2 cost)
IP_DIFFICULT_SKILLS = [
    "autofire", "martial_arts", "pilot_air", "heavy_weapons",
    "demolitions", "electronics", "paramedic"
]

# All skills (typical cost except those in IP_DIFFICULT_SKILLS)
IP_SKILLS = [
    "concentration", "conceal_object", "lip_reading", "perception", "tracking",
    "athletics", "contortionist", "dance", "endurance", "resist_torture_drugs",
    "stealth", "drive_land", "pilot_sea", "riding", "accounting", "animal_handling",
    "bureaucracy", "business", "composition", "criminology", "cryptography",
    "deduction", "education", "gamble", "library_search", "local_expert",
    "zoology", "physics", "stock_market", "biology", "chemistry", "neuroscience",
    "data_science", "economics", "sociology", "political_science", "genetics",
    "anatomy", "robotics", "nanotechnology", "tactics", "wilderness_survival",
    "brawling", "evasion", "melee", "acting", "singing", "theater", "archery",
    "handgun", "shoulder_arms", "bribery", "conversation", "human_perception",
    "interrogation", "persuasion", "play_instrument", "personal_grooming",
    "streetwise", "trading", "style", "air_vehicle_tech", "basic_tech",
    "cybertech", "first_aid", "forgery", "land_vehicle_tech", "artistry",
    "photography", "pick_lock", "pick_pocket", "sea_vehicle_tech", "weaponstech",
] + IP_DIFFICULT_SKILLS

# Cost to reach NEXT level/rank (cost is for the level you're going TO)
# Typical: Level 1=20, Level 2=40, ..., Level 10=200
IP_COST_TYPICAL = {i: i * 20 for i in range(1, 11)}

# Difficult (x2): Level 1=40, Level 2=80, ..., Level 10=400
IP_COST_DIFFICULT = {i: i * 40 for i in range(1, 11)}

# Role ability: Rank 1=60, Rank 2=120, ..., Rank 10=600
IP_COST_ROLE_ABILITY = {i: i * 60 for i in range(1, 11)}

# Attribute (stats): Same as typical - 20 per point. Stats start at 1, so to go 1->2 costs 40 (level 2)
# Actually for attributes, we're raising from 1-10. Cost for next level: 1->2 = 40 (level 2 cost)
# The table says "cost for NEXT level" - so current 0->1 = 20, 1->2 = 40, etc.
# For attributes (1-10 base), going from 1 to 2 = cost for level 2 = 40? No.
# Looking at the table: "Level" column 1 means "to reach level 1" = 20 IP. So 0->1 = 20.
# Level 2 = 40 means 1->2 = 40. So cost for level N = N * 20 (typical).
# Attributes go 1-10, so raising INT from 1 to 2 costs 40 (cost for level 2). Yes.
IP_COST_ATTRIBUTE = IP_COST_TYPICAL


def normalize_stat_name(name):
    """Convert stat name to internal format (lowercase, underscores)."""
    if not name:
        return None
    return name.lower().replace(" ", "_").strip()


def get_ip_cost(stat_name, current_level, is_attribute=False, is_role_ability=False):
    """
    Get the IP cost to raise stat from current_level to current_level + 1.

    Args:
        stat_name: Internal stat/skill name
        current_level: Current level (0-9 for next would be 1-10)
        is_attribute: True if this is a core attribute
        is_role_ability: True if this is a role ability

    Returns:
        (cost, next_level) or (None, None) if invalid
    """
    next_level = current_level + 1
    if next_level > 10:
        return None, None

    stat_key = normalize_stat_name(stat_name)
    if not stat_key:
        return None, None

    if is_attribute or stat_key in IP_ATTRIBUTES:
        cost = IP_COST_ATTRIBUTE.get(next_level, None)
    elif is_role_ability or stat_key in IP_ROLE_ABILITIES:
        cost = IP_COST_ROLE_ABILITY.get(next_level, None)
    elif stat_key in IP_DIFFICULT_SKILLS:
        cost = IP_COST_DIFFICULT.get(next_level, None)
    elif stat_key in IP_SKILLS:
        cost = IP_COST_TYPICAL.get(next_level, None)
    else:
        return None, None

    return cost, next_level


def is_valid_stat(stat_name):
    """Check if stat_name is a valid purchasable stat."""
    key = normalize_stat_name(stat_name)
    return key in IP_ATTRIBUTES or key in IP_SKILLS or key in IP_ROLE_ABILITIES


def get_stat_display_name(stat_name):
    """Get display name for a stat (e.g. handgun -> Handgun)."""
    key = normalize_stat_name(stat_name)
    if not key:
        return stat_name
    return key.replace("_", " ").title()


def get_character_stat_value(character, stat_name):
    """Get current value of a stat from character (works with both typeclass and sheet).
    Missing skills are treated as level 0 (so buying them goes 0 -> 1).
    """
    key = normalize_stat_name(stat_name)
    if not key:
        return None

    # Try typeclass first (db.skills or db.attribute)
    if hasattr(character, "db"):
        if key in IP_ATTRIBUTES:
            return getattr(character.db, key, 1)
        if hasattr(character.db, "skills") and character.db.skills is not None:
            return character.db.skills.get(key, 0)
        return getattr(character.db, key, 0)

    # Fallback to character sheet model - missing skills/attrs = level 0
    if hasattr(character, key):
        val = getattr(character, key, 0)
        return val if val is not None else 0
    return 0


def set_character_stat_value(character, stat_name, value):
    """Set stat value on character. Mirrors to character_sheet if present."""
    key = normalize_stat_name(stat_name)
    if not key:
        return False

    if hasattr(character, "db"):
        if key in IP_ATTRIBUTES:
            setattr(character.db, key, value)
        else:
            skills = character.db.skills or {}
            skills[key] = value
            character.db.skills = skills

        # Mirror to character sheet
        if hasattr(character, "character_sheet") and character.character_sheet:
            sheet = character.character_sheet
            if hasattr(sheet, key):
                setattr(sheet, key, value)
                sheet.save(skip_recalculation=True)
        return True

    if hasattr(character, key):
        setattr(character, key, value)
        if hasattr(character, "save"):
            character.save()
        return True
    return False


def get_character_ip(character):
    """Get (current_ip, spent_ip, staff_awarded, last_purchase, log) for character."""
    if hasattr(character, "attributes"):
        current = character.attributes.get("improvement_points", 0) or 0
        spent = character.attributes.get("ip_spent", 0) or 0
        staff_awarded = character.attributes.get("ip_staff_awarded", 0) or 0
        last_purchase = character.attributes.get("ip_last_purchase")
        log = character.attributes.get("ip_log", []) or []
        return current, spent, staff_awarded, last_purchase, log
    return 0, 0, 0, None, []


def add_ip_log_entry(character, amount, reason, details="", exclude_from_recent=False):
    """
    Add an entry to the character's IP log.

    Args:
        character: Character object
        amount: IP change (+ or -)
        reason: Short reason (e.g. "Staff Award", "Athletics", "Weekly Allotment")
        details: Optional details (e.g. "Awarded by Soma", "1 > 2")
        exclude_from_recent: If True, this won't appear in "recent changes" (e.g. votes)
    """
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "amount": amount,
        "reason": reason,
        "details": details,
        "exclude_from_recent": exclude_from_recent,
    }
    log = character.attributes.get("ip_log", default=[]) or []
    log.insert(0, entry)
    # Keep last 500 entries to avoid bloat
    character.attributes.add("ip_log", log[:500])


def get_recent_ip_changes(character, limit=10, exclude_votes=True):
    """Get recent IP log entries, optionally excluding votes."""
    log = character.attributes.get("ip_log", default=[]) or []
    filtered = [e for e in log if not e.get("exclude_from_recent", False)] if exclude_votes else log
    return filtered[:limit]


def format_log_entry(entry):
    """Format a log entry for display."""
    amt = entry.get("amount", 0)
    sign = "+" if amt >= 0 else ""
    reason = entry.get("reason", "Unknown")
    details = entry.get("details", "")
    ts = entry.get("timestamp", "")

    if details:
        return f"{ts} {sign}{amt} IP from {reason} - {details}"
    return f"{ts} {sign}{amt} IP from {reason}"
