# Character generation constants - fashion budget, Netrunner cyberdecks, Sell Your Soul

FASHION_BUDGET = 800

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
