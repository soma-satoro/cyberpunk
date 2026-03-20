"""
Elflines Online data - skills, armory, titles, and constants from the RTG source.
"""

# ELO uses 50 STAT points, 60 skill points, no LUCK. Stats 3-8 at creation.
ELO_STAT_POINTS = 50
ELO_SKILL_POINTS = 60
ELO_STAT_MIN = 3
ELO_STAT_MAX_START = 8
ELO_STAT_ABSOLUTE_MAX = 10
ELO_SKILL_MAX_START = 6
ELO_SKILL_ABSOLUTE_MAX = 10
ELO_STARTING_GP = 200
ELO_MAX_RANK = 10
ELO_DEATH_TAX = 2000
ELO_PVP_KILL_REWARD = 1000

# Subscription: 20eb/month (Generic Prepak+ includes it)
# Segotari RUSH REVOLUTION headset: 500eb, Elflines Online: 50eb
ELO_SUBSCRIPTION_COST_EB = 20
ELO_HEADSET_COST_EB = 500
ELO_GAME_COST_EB = 50

# 1eb = 100gp pay-to-win conversion
ELO_GP_PER_EB = 100

# ELO skill list (altered from CPR - some combined, STAT/cost changes)
# Format: (skill_key, stat_abbrev, is_double_cost)
ELO_SKILLS = [
    ("animal_handling", "EMP", False),
    ("language_elven", "INT", False),  # Auto 4 for all elves
    ("archery", "REF", True),
    ("melee_weapon", "REF", True),
    ("athletics_contortionist", "DEX", False),
    ("perception", "INT", False),
    ("basic_tech_weaponstech", "TECH", False),
    ("persuasion_trading", "COOL", False),
    ("brawling", "DEX", False),
    ("pick_lock_pick_pocket", "TECH", False),
    ("composition_education", "INT", False),
    ("pilot_sea_vehicle", "REF", False),
    ("concentration", "WILL", False),
    ("play_instrument", "COOL", False),
    ("conceal_reveal_object", "COOL", False),
    ("riding", "REF", False),  # EMP in ELO
    ("endurance_resist_torture_drugs", "WILL", False),
    ("stealth", "DEX", False),
    ("evasion_dance", "DEX", True),
    ("tracking", "INT", False),
    ("first_aid_paramedic_surgery", "TECH", True),
    ("wilderness_survival", "INT", False),
]

# Stats for ELO (no LUCK)
ELO_STATS = ["intelligence", "reflexes", "dexterity", "technology", "cool", "willpower", "move", "body", "empathy"]

# Titles at Rank 3 based on highest increased STAT
ELO_TITLES_BY_STAT = {
    "intelligence": "Sage",
    "reflexes": "Bowmaster",
    "dexterity": "Bladedancer",
    "technology": "Quickhand",
    "cool": "Warmheart",
    "willpower": "Wildblood",
    "move": "Windkin",
    "body": "Barkshield",
    "empathy": "Druid",
    "even_spread": "Wayfarer",
}

# Elflines Online Armory - (internal_key, name, gp_cost, cpr_equivalent)
ELO_ARMORY = [
    # Armor
    ("leather_armor", "Leather Armor", 20, "Leathers"),
    ("studded_leather", "Studded Leather Armor", 50, "Kevlar(R)"),
    ("chainmail", "Chainmail Armor", 100, "Medium Armorjack"),
    ("full_plate", "Full Plate Armor", 500, "Flak"),
    # Melee
    ("dagger", "Dagger", 50, "Light Melee Weapon"),
    ("shortsword", "Shortsword", 50, "Medium Melee Weapon"),
    ("longsword", "Longsword", 100, "Heavy Melee Weapon"),
    ("greataxe", "Greataxe", 500, "Very Heavy Melee Weapon"),
    ("shield", "Shield", 100, "Bulletproof Shield"),
    # Ranged
    ("bow", "Bow", 100, "Bow"),
    ("arrow", "Arrow", 1, "Basic Arrow"),
    ("poison_arrow", "Poison Arrow", 10, "Poison Arrow"),
    ("vial_of_poison", "Vial of Poison", 100, "Vial of Poison"),
    # Consumable
    ("sacred_herbs_speedheal", "Sacred Herbs Speedheal", 50, "Speedheal (anyone can use, no cooldown)"),
]


def get_elo_skill_key(skill_name):
    """Convert display name to internal key."""
    return skill_name.lower().replace(" ", "_").replace("/", "_").replace(",", "")
