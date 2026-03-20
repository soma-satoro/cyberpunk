# Character generation constants - fashion budget, Netrunner cyberdecks, Sell Your Soul

FASHION_BUDGET = 800

# Eurodollar allotments for chargen refund cap (refund cannot exceed this)
CHARGEN_EURODOLLARS_EDGERUNNER = 500
CHARGEN_EURODOLLARS_COMPLETE_PACKAGE = 2550

# Chargen point limits (Complete Package / Edgerunner allocation)
# Complete Package: 62 stat points, 86 skill points (per book p. 88-89)
# Edgerunner: stats from table, 86 skill points
COMPLETE_PACKAGE_SKILL_POOL = 86
EDGERUNNER_SKILL_POOL = 86
# Stats: min 0 (allow clearing), max 8
CHARGEN_STAT_MIN = 0
CHARGEN_STAT_MAX = 8
# Skills: min 0 (allow clearing), max 8; required skills must be >= 2 at chargen finish
CHARGEN_SKILL_MIN = 0
CHARGEN_SKILL_MAX = 8
CHARGEN_REQUIRED_SKILL_MIN = 2

# Skills that must be >= CHARGEN_REQUIRED_SKILL_MIN to finish chargen
CHARGEN_REQUIRED_SKILLS = frozenset({
    "athletics", "brawling", "concentration", "conversation", "education",
    "evasion", "first_aid", "human_perception", "local_expert", "perception",
    "persuasion", "stealth",
})
# Language (Streetslang) is required >= 2 - checked separately via get_language_level
# Role ability: 4 free points (not deducted from skill pool), min 4, max 8
ROLE_ABILITY_FREE_POINTS = 4
CHARGEN_ROLE_ABILITY_MIN = 4
CHARGEN_ROLE_ABILITY_MAX = 8

# Medicine (Medtech) specialty system - allocate Medicine rank across three branches:
# - Surgery: each point = 2 Surgery skill (max 10)
# - Pharmaceuticals: each point = 1 Medical Tech, unlocks drugs (max 5)
# - Cryosystem: each point = 1 Medical Tech, unlocks cryo equipment (max 5)
# Medical Tech skill = pharma + cryo (max 10)
# Constraint: medicine_surgery + medicine_pharma + medicine_cryo == medicine
MEDICINE_SPECIALTIES = ("surgery", "pharma", "cryo")
MEDICINE_PHARMA_MAX = 5
MEDICINE_CRYO_MAX = 5
MEDICINE_SURGERY_SKILL_MULTIPLIER = 2  # 1 surgery pt = 2 Surgery skill


def get_medicine_surgery_skill(medicine_surgery):
    """Surgery skill = medicine_surgery * 2, capped at 10."""
    return min(10, (medicine_surgery or 0) * MEDICINE_SURGERY_SKILL_MULTIPLIER)


def get_medical_tech_skill(medicine_pharma, medicine_cryo):
    """Medical Tech skill = pharma + cryo, capped at 10."""
    return min(10, (medicine_pharma or 0) + (medicine_cryo or 0))


def validate_medicine_specialties(medicine, surgery, pharma, cryo):
    """Check specialty allocation is valid. Returns (ok, error_msg)."""
    s, p, c = int(surgery or 0), int(pharma or 0), int(cryo or 0)
    m = int(medicine or 0)
    if s + p + c != m:
        return False, f"Medicine specialties must sum to Medicine rank ({m}): Surgery + Pharma + Cryo = {s}+{p}+{c}={s+p+c}"
    if p > MEDICINE_PHARMA_MAX:
        return False, f"Pharmaceuticals cannot exceed {MEDICINE_PHARMA_MAX}."
    if c > MEDICINE_CRYO_MAX:
        return False, f"Cryosystem cannot exceed {MEDICINE_CRYO_MAX}."
    if s < 0 or p < 0 or c < 0:
        return False, "Specialty values cannot be negative."
    return True, None


# Maker (Tech) specialty system - each Maker point allows 1 pt to two different specializations (2*Maker total)
# Constraints: maker_field + maker_upgrade + maker_fabrication + maker_invention == maker * 2
#             each specialty <= maker (capped by Maker skill)
MAKER_SPECIALTIES = ("field", "upgrade", "fabrication", "invention")
MAKER_ALLOCATION_PER_RANK = 2  # Each Maker rank = 2 allocation points


def validate_maker_specialties(maker, field, upgrade, fabrication, invention):
    """Check Maker specialty allocation is valid. Returns (ok, error_msg)."""
    f, u, fab, inv = int(field or 0), int(upgrade or 0), int(fabrication or 0), int(invention or 0)
    m = int(maker or 0)
    total = f + u + fab + inv
    expected = m * MAKER_ALLOCATION_PER_RANK
    if total != expected:
        return False, (
            f"Maker specialties must sum to Maker rank x 2 ({m}x2={expected}): "
            f"Field + Upgrade + Fabrication + Invention = {f}+{u}+{fab}+{inv}={total}"
        )
    if f < 0 or u < 0 or fab < 0 or inv < 0:
        return False, "Specialty values cannot be negative."
    if f > m or u > m or fab > m or inv > m:
        return False, f"Each Maker specialty cannot exceed Maker rank ({m})."
    return True, None


# Role -> role ability skill key (for chargen: 4 free, min 4, max 8)
ROLE_ABILITY_SKILLS = {
    "Rockerboy": "charismatic_impact",
    "Solo": "combat_awareness",
    "Netrunner": "interface",
    "Tech": "maker",
    "Medtech": "medicine",  # ROLE_SKILL_NAME_MAP: diagnosis -> medicine
    "Media": "credibility",
    "Exec": "teamwork",
    "Lawman": "backup",
    "Fixer": "operator",
    "Nomad": "moto",
}

# Netrunners using Edgerunner system get a random 7-slot cyberdeck from equipment DB
NETRUNNER_7_SLOT_CYBERDECKS = [
    "Militech Dataknight-7",
    "Microtech Warrior",
    "Raven Microcyb Kestrel 2",
]

# Gear/armor items that count as fashion (clothing) - deduct from fashion budget
FASHION_ITEM_NAMES = frozenset({
    "Generic Chic", "Leisurewear", "Urban Flash", "Urbanflash",
    "Businesswear", "Bohemian Chic", "Nomad Leathers", "Mirrorshades",
})

# Sell Your Soul - employer categories and options
SELL_YOUR_SOUL_EBOOST = 1500

SELL_YOUR_SOUL_CATCHES = [
    "Hostages",
    "Blackmail",
    "Sabotage Cybernetics",
    "Monitored",
    "Command Kill",
    "Company Safeguard",
    "Remote Detonator",
]

SELL_YOUR_SOUL_MILITARY_OPTIONS = [
    "NUSA Mechanised Combat Force",
    "Arasaka Shadow Operatives",
    "Militech Covert Ops",
    "Lazarus Group",
    "Japanese Self Defense Force",
    "NorCal Military Police",
    "British Combined Forces",
    "Danger Girl",
    "Night City Police Department",
]

SELL_YOUR_SOUL_CRIME_OPTIONS = [
    "Italian Mob",
    "Russian Organitskaya",
    "Yakuza",
    "Wong Wandeun Triad",
    "Ghost Shadow Triad",
    "Eastern Tiger Triad",
    "Consortium",
    "Kanzaki Family",
    "El Norte Cartel",
]

# Corporations from Cyberpunk 2077 / Red universe
SELL_YOUR_SOUL_CORPORATION_OPTIONS = [
    # Major mega-corps
    "Arasaka",
    "Militech",
    "Kang Tao",
    "Biotechnica",
    "Petrochem",
    "Night Corp",
    "Trauma Team International",
    "Zetatech",
    "NetWatch",
    # Additional corps from Red-2077
    "Network News 54",
    "Nippon Network",
    "Diverse Media Systems",
    "Akaromi BioCorp",
    "ConAg",
    "SovOil",
    "Tsunami Defense Systems",
    "Microtech",
    "Adrek Robotics",
    "Akagi Systems Incorporated",
    "Raven Microcybernetics",
    "Rocklin Augmentics",
    "Kenjiri Technology",
    "Kiroshi Optics",
    "InfoComp",
    "Merrill, Asukaga, & Finch",
    "Orbital Air",
    "REO Meatwagon",
    "WorldSat Communications Network",
    "Meiji Sumitomo",
    "EuroBank",
]

SELL_YOUR_SOUL_GANG_OPTIONS = [
    "Raffen Shiv",
    "6th Street",
    "Maelstrom",
    "Animals",
    "Tyger Claws",
    "Valentinos",
    "Voodoo Boys",
    "Scavengers",
    "Wraiths",
]

# Science skills - Tech and Medtech choose one at chargen (Edgerunner)
SCIENCE_SKILLS = (
    "zoology",
    "physics",
    "biology",
    "chemistry",
    "neuroscience",
    "data_science",
    "economics",
    "sociology",
    "political_science",
    "genetics",
    "anatomy",
    "robotics",
    "nanotechnology",
    "stock_market",
)

# Gangs (street gangs, nomad clans, etc.) - separate from corporations
SELL_YOUR_SOUL_GANG_OPTIONS = [
    "Raffen Shiv",
    "6th Street",
    "Maelstrom",
    "Animals",
    "Tyger Claws",
    "Valentinos",
    "Voodoo Boys",
    "Scavengers",
    "Wraiths",
    "Aldecaldos",
    "Solo of Fortune",
]
