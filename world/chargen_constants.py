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

# Corporations from Cyberpunk 2077 Database (cyberpunk.fandom.com)
SELL_YOUR_SOUL_CORPORATION_OPTIONS = [
    "Arasaka",
    "Militech",
    "Kang Tao",
    "Biotechnica",
    "Petrochem",
    "Night Corp",
    "Trauma Team International",
    "Zetatech",
    "NetWatch",
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
