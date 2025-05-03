# Roles
ROLES = ["Rockerboy", "Solo", "Netrunner", "Tech", "Medtech", "Media", "Lawman", "Exec", "Fixer", "Nomad"]

# Stats
STATS = ['intelligence', 'reflexes', 'dexterity', 'technology', 'cool', 'willpower', 'luck', 'move', 'body', 'empathy']

# Role-specific stat tables
ROLE_STAT_TABLES = {
    "Rockerboy": [
        [7, 6, 6, 5, 6, 8, 7, 7, 3, 8],
        [3, 7, 7, 7, 7, 6, 7, 7, 5, 8],
        [4, 5, 7, 7, 6, 6, 7, 7, 5, 8],
        [4, 5, 7, 7, 6, 8, 7, 6, 3, 8],
        [3, 7, 7, 7, 6, 8, 6, 5, 4, 7],
        [5, 6, 7, 5, 7, 8, 5, 7, 3, 7],
        [5, 6, 6, 7, 7, 8, 7, 6, 3, 6],
        [5, 7, 7, 5, 6, 6, 6, 6, 4, 8],
        [3, 5, 5, 6, 7, 8, 7, 5, 5, 7],
        [4, 5, 6, 5, 8, 8, 7, 6, 4, 7]
    ],
    "Solo": [
        [6, 8, 6, 3, 6, 7, 6, 6, 7, 5],
        [4, 8, 6, 4, 7, 6, 6, 6, 8, 5],
        [5, 7, 7, 4, 6, 7, 6, 7, 7, 4],
        [5, 8, 6, 3, 7, 7, 7, 6, 7, 4],
        [4, 8, 7, 4, 6, 6, 6, 7, 8, 4],
        [5, 7, 6, 3, 7, 7, 6, 6, 7, 6],
        [6, 8, 7, 3, 6, 6, 7, 7, 7, 3],
        [4, 7, 6, 4, 7, 7, 6, 6, 8, 5],
        [5, 8, 7, 3, 6, 7, 7, 7, 7, 3],
        [5, 7, 6, 4, 7, 6, 6, 6, 8, 5]
    ],
    "Netrunner": [
        [7, 6, 6, 8, 5, 6, 5, 5, 3, 6],
        [6, 5, 7, 8, 6, 7, 5, 5, 3, 5],
        [7, 6, 6, 7, 5, 6, 6, 6, 4, 5],
        [6, 5, 7, 8, 6, 6, 5, 5, 3, 6],
        [7, 6, 6, 8, 5, 7, 5, 5, 4, 4],
        [6, 5, 7, 7, 6, 6, 6, 6, 3, 5],
        [7, 6, 6, 8, 5, 6, 5, 5, 4, 5],
        [6, 5, 7, 8, 6, 7, 5, 5, 3, 5],
        [7, 6, 6, 7, 5, 6, 6, 6, 3, 6],
        [6, 5, 7, 8, 6, 6, 5, 5, 4, 5]
    ],
    "Tech": [
        [7, 5, 6, 8, 4, 6, 5, 5, 4, 6],
        [6, 4, 7, 8, 5, 7, 5, 5, 3, 6],
        [7, 5, 6, 7, 4, 6, 6, 6, 4, 5],
        [6, 4, 7, 8, 5, 6, 5, 5, 3, 7],
        [7, 5, 6, 8, 4, 7, 5, 5, 4, 5],
        [6, 4, 7, 7, 5, 6, 6, 6, 3, 6],
        [7, 5, 6, 8, 4, 6, 5, 5, 4, 5],
        [6, 4, 7, 8, 5, 7, 5, 5, 3, 6],
        [7, 5, 6, 7, 4, 6, 6, 6, 4, 5],
        [6, 4, 7, 8, 5, 6, 5, 5, 3, 7]
    ],
    "Medtech": [
        [6, 5, 6, 6, 5, 7, 5, 5, 4, 7],
        [5, 4, 7, 7, 6, 8, 5, 5, 3, 7],
        [6, 5, 6, 6, 5, 7, 6, 6, 4, 6],
        [5, 4, 7, 7, 6, 7, 5, 5, 3, 8],
        [6, 5, 6, 6, 5, 8, 5, 5, 4, 6],
        [5, 4, 7, 7, 6, 7, 6, 6, 3, 7],
        [6, 5, 6, 6, 5, 7, 5, 5, 4, 7],
        [5, 4, 7, 7, 6, 8, 5, 5, 3, 7],
        [6, 5, 6, 6, 5, 7, 6, 6, 4, 6],
        [5, 4, 7, 7, 6, 7, 5, 5, 3, 8]
    ],
    "Media": [
        [7, 5, 6, 5, 6, 7, 6, 6, 3, 7],
        [6, 4, 7, 6, 7, 8, 6, 6, 4, 6],
        [7, 5, 6, 5, 6, 7, 7, 7, 3, 6],
        [6, 4, 7, 6, 7, 7, 6, 6, 4, 7],
        [7, 5, 6, 5, 6, 8, 6, 6, 3, 6],
        [6, 4, 7, 6, 7, 7, 7, 7, 4, 6],
        [7, 5, 6, 5, 6, 7, 6, 6, 3, 7],
        [6, 4, 7, 6, 7, 8, 6, 6, 4, 6],
        [7, 5, 6, 5, 6, 7, 7, 7, 3, 6],
        [6, 4, 7, 6, 7, 7, 6, 6, 4, 7]
    ],
    "Lawman": [
        [6, 7, 6, 4, 6, 7, 6, 6, 6, 6],
        [5, 6, 7, 5, 7, 8, 6, 6, 7, 5],
        [6, 7, 6, 4, 6, 7, 7, 7, 6, 5],
        [5, 6, 7, 5, 7, 7, 6, 6, 7, 6],
        [6, 7, 6, 4, 6, 8, 6, 6, 6, 5],
        [5, 6, 7, 5, 7, 7, 7, 7, 7, 5],
        [6, 7, 6, 4, 6, 7, 6, 6, 6, 6],
        [5, 6, 7, 5, 7, 8, 6, 6, 7, 5],
        [6, 7, 6, 4, 6, 7, 7, 7, 6, 5],
        [5, 6, 7, 5, 7, 7, 6, 6, 7, 6]
    ],
    "Exec": [
        [7, 5, 5, 5, 7, 8, 6, 5, 4, 6],
        [6, 4, 6, 6, 8, 9, 6, 5, 5, 5],
        [7, 5, 5, 5, 7, 8, 7, 6, 4, 5],
        [6, 4, 6, 6, 8, 8, 6, 5, 5, 6],
        [7, 5, 5, 5, 7, 9, 6, 5, 4, 5],
        [6, 4, 6, 6, 8, 8, 7, 6, 5, 5],
        [7, 5, 5, 5, 7, 8, 6, 5, 4, 6],
        [6, 4, 6, 6, 8, 9, 6, 5, 5, 5],
        [7, 5, 5, 5, 7, 8, 7, 6, 4, 5],
        [6, 4, 6, 6, 8, 8, 6, 5, 5, 6]
    ],
    "Fixer": [
        [6, 6, 6, 5, 7, 7, 7, 6, 4, 6],
        [5, 5, 7, 6, 8, 8, 7, 6, 5, 5],
        [6, 6, 6, 5, 7, 7, 8, 7, 4, 5],
        [5, 5, 7, 6, 8, 7, 7, 6, 5, 6],
        [6, 6, 6, 5, 7, 8, 7, 6, 4, 5],
        [5, 5, 7, 6, 8, 7, 8, 7, 5, 5],
        [6, 6, 6, 5, 7, 7, 7, 6, 4, 6],
        [5, 5, 7, 6, 8, 8, 7, 6, 5, 5],
        [6, 6, 6, 5, 7, 7, 8, 7, 4, 5],
        [5, 5, 7, 6, 8, 7, 7, 6, 5, 6]
    ],
    "Nomad": [
        [5, 6, 7, 6, 6, 6, 6, 7, 6, 5],
        [4, 5, 8, 7, 7, 7, 6, 7, 7, 4],
        [5, 6, 7, 6, 6, 6, 7, 8, 6, 4],
        [4, 5, 8, 7, 7, 6, 6, 7, 7, 5],
        [5, 6, 7, 6, 6, 7, 6, 7, 6, 4],
        [4, 5, 8, 7, 7, 6, 7, 8, 7, 4],
        [5, 6, 7, 6, 6, 6, 6, 7, 6, 5],
        [4, 5, 8, 7, 7, 7, 6, 7, 7, 4],
        [5, 6, 7, 6, 6, 6, 7, 8, 6, 4],
        [4, 5, 8, 7, 7, 6, 6, 7, 7, 5]
    ]
}

# Role-specific skills
ROLE_SKILLS = {
    "Rockerboy": {
        'charismatic_impact': 2,
        'athletics': 2, 
        'brawling': 2, 
        'concentration': 2, 
        'conversation': 2, 
        'education': 2,
        'evasion': 2, 
        'first_aid': 2, 
        'human_perception': 2, 
        'local_expert': 2,
        'perception': 2, 
        'persuasion': 2, 
        'stealth': 2, 
        'composition': 2, 
        'handgun': 2,
        'melee_weapon': 2, 
        'personal_grooming': 2, 
        'play_instrument': 2, 
        'streetwise': 2, 
        'wardrobe_and_style': 2
    },
    "Solo": {
        'combat_awareness': 2,
        'athletics': 2,
        'brawling': 2,
        'concentration': 2,
        'conversation': 2,
        'education': 2,
        'evasion': 2,
        'first_aid': 2,
        'human_perception': 2,
        'local_expert': 2,
        'perception': 2,
        'persuasion': 2,
        'stealth': 2,
        'autofire': 2,
        'interrogation': 2, 
        'melee_weapon': 2, 
        'resist_torture_drugs': 2, 
        'shoulder_arms': 2, 
        'tactics': 2
    },
    "Netrunner": {
        'athletics': 2, 
        'basic_tech': 2, 
        'brawling': 2, 
        'concentration': 2, 
        'conversation': 2,
        'cryptography': 2, 
        'cyberdeck_programming': 2, 
        'education': 2, 
        'electronics': 2, 
        'evasion': 2,
        'first_aid': 2,
        'human_perception': 2,
        'interface': 2,
        'library_search': 2,
        'local_expert': 2,
        'perception': 2,
        'persuasion': 2,
        'stealth': 2,
        'system_knowledge': 2
            },
    "Tech": {
        'athletics': 2,
        'basic_tech': 2,
        'brawling': 2,
        'concentration': 2,
        'conversation': 2,
        'cyberdeck_programming': 2,
        'cybertech': 2,
        'education': 2,
        'electronics': 2,
        'evasion': 2,
        'first_aid': 2,
        'handgun': 2,
        'human_perception': 2,
        'local_expert': 2,
        'perception': 2,
        'persuasion': 2,
        'pick_lock': 2,
        'shoulder_arms': 2,
        'stealth': 2
    },
    "Medtech": {
        'athletics': 2,
        'basic_tech': 2,
        'brawling': 2,
        'concentration': 2,
        'conversation': 2,
        'deduction': 2,
        'diagnosis': 2,
        'education': 2,
        'first_aid': 2,
        'human_perception': 2,
        'local_expert': 2,
        'paramedic': 2,
        'perception': 2,
        'persuasion': 2,
        'pharmaceuticals': 2,
        'pick_lock': 2,
        'stealth': 2,
        'surgery': 2,
        'zoology': 2
    },
    "Media": {
        'athletics': 2,
        'brawling': 2,
        'composition': 2,
        'concentration': 2,
        'conversation': 2,
        'credibility': 2,
        'cryptography': 2,
        'deduction': 2,
        'education': 2,
        'evasion': 2,
        'first_aid': 2,
        'handgun': 2,
        'human_perception': 2,
        'library_search': 2,
        'local_expert': 2,
        'perception': 2,
        'persuasion': 2,
        'photography': 2,
        'stealth': 2
    },
    "Lawman": {
        'athletics': 2,
        'autofire': 2,
        'brawling': 2,
        'concentration': 2,
        'conversation': 2,
        'criminology': 2,
        'deduction': 2,
        'education': 2,
        'evasion': 2,
        'first_aid': 2,
        'handgun': 2,
        'human_perception': 2,
        'interrogation': 2,
        'local_expert': 2,
        'perception': 2,
        'persuasion': 2,
        'shoulder_arms': 2,
        'stealth': 2,
        'tracking': 2
    },
    "Exec": {
        'accounting': 2,
        'athletics': 2,
        'brawling': 2,
        'bureaucracy': 2,
        'business': 2,
        'composition': 2,
        'concentration': 2,
        'conversation': 2,
        'deduction': 2,
        'education': 2,
        'evasion': 2,
        'handgun': 2,
        'human_perception': 2,
        'local_expert': 2,
        'perception': 2,
        'persuasion': 2,
        'personal_grooming': 2,
        'resources': 2,
        'stock_market': 2
    },
    "Fixer": {
        'athletics': 2,
        'brawling': 2,
        'bribery': 2,
        'business': 2,
        'concentration': 2,
        'conversation': 2,
        'criminology': 2,
        'deduction': 2,
        'education': 2,
        'evasion': 2,
        'forgery': 2,
        'handgun': 2,
        'human_perception': 2,
        'local_expert': 2,
        'perception': 2,
        'persuasion': 2,
        'pick_lock': 2,
        'streetwise': 2,
        'trading': 2
    },
    "Nomad": {
        'animal_handling': 2,
        'athletics': 2,
        'basic_tech': 2,
        'brawling': 2,
        'concentration': 2,
        'conversation': 2,
        'drive_land_vehicle': 2,
        'education': 2,
        'evasion': 2,
        'first_aid': 2,
        'handgun': 2,
        'human_perception': 2,
        'local_expert': 2,
        'navigation': 2,
        'perception': 2,
        'persuasion': 2,
        'shoulder_arms': 2,
        'stealth': 2,
        'survival': 2
    }    
}

# Role-specific equipment
EQUIPMENT = {
                "Rockerboy": {
                    "weapons": ["Very Heavy Pistol", "Heavy Melee Weapon"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Agent", "Computer", "Bug Detector", "Glow Paint", "Pocket Amp", 
                          "Radio Scanner/Music Player", "Video Camera", "Generic Chic", 
                          "Leisurewear", "Urbanflash"],
                },
                "Solo": {
                    "weapons": ["Assault Rifle", "Very Heavy Pistol", "Heavy Melee Weapon"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Bulletproof Shield", "Agent", "Leisurewear"]
                },
                "Netrunner": {
                    "weapons": ["Very Heavy Pistol"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Agent", "Cyberdeck", "Virtuality Goggles", 
                        "Generic Chic", "Leisurewear", "Urban Flash"]
                },
                "Tech": {
                    "weapons": ["Shotgun", "Assault Rifle"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Flashbang Grenade", "Agent", "Anti-Smog Breathing Mask", "Disposable Cell Phone", "Duct Tape", "Flashlight", 
                     "Road Flare", "Tech Bag", "Generic Chic", "Leisurewear"]
                },
                "Medtech": {
                    "weapons": ["Shotgun", "Assault Rifle"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Agent", "Airhypo", "Handcuffs", "Flashlight", "Generic Chic", "Glow Paint", 
                        "Medtech Bag", "Leisurewear"]
                },
                "Media": {
                    "weapons": ["Heavy Pistol", "Very Heavy Pistol"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Agent", "Audio Recorder", "Binoculars", "Disposable Cellphone", "Flashlight", 
                      "Computer", "Radio Scanner/Music Player", "Scrambler/Descrambler", "Video Camera", 
                      "Generic Chic", "Leisurewear", "Mirrorshades"]
                },
                "Lawman": {
                    "weapons": ["Assault Rifle", "Shotgun", "Heavy Pistol"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Bulletproof Shield", "Smoke Grenade", "Agent", "Flashlight", "Handcuffs", "Radio Communicator", "Road Flare", 
                       "Generic Chic", "Leisurewear", "Mirrorshades"]
                },
                "Exec": {
                    "weapons": ["Very Heavy Pistol"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Radio Communicator", "Scrambler/Descrambler", "Businesswear", "Mirrorshades"]
                },
                "Fixer": {
                    "weapons": ["Heavy Pistol", "Very Heavy Pistol", "Light Melee Weapon"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Agent", "Bug Detector", "Computer", "Disposable Phone", "Generic Chic", 
                      "Mirrorshades", "Urbanflash"]
                },
                "Nomad": {
                    "weapons": ["Heavy Pistol", "Very Heavy Pistol", "Heavy Melee Weapon"],
                    "armor": ["Light Armorjack"],
                    "gear": ["Agent", "Anti-Smog Breathing Mask", "Duct Tape", "Flashlight", "Grapple Gun", "Inflatable Bed & Sleep-Bag", 
                      "Medtech Bag", "Radio Communicator", "Rope", "Techtool", "Tent and Camping Equipment", 
                      "Bohemian Chic", "Nomad Leathers"]
                }
}

# Role-specific cyberware
ROLE_CYBERWARE = {
            "Rockerboy": ["Audio Recorder", "Chemskin", "Cyberaudio Suite", "Techhair"],
            "Solo": ["Biomonitor", "Neural Link", "Sandevistan", "Wolvers"],
            "Netrunner": ["Interface Plugs", "Neural Link", "Shift Tacts"],
            "Tech": ["Cybereye", "MicroOptics", "Skinwatch", "Tool Hand"],
            "Medtech": ["Biomonitor", "Cybereye", "Nasal Filters", "TeleOptics"],
            "Media": ["Amplified Hearing", "Cyberaudio Suite", "Light Tattoo"],
            "Lawman": ["Hidden Holster", "Subdermal Pocket"],
            "Exec": ["Biomonitor", "Internal Agent", "Subdermal Pocket", "Voice Stress Analyzer"],
            "Fixer": ["Cyberaudio Suite", "Internal Agent", "Subdermal Pocket", "Voice Stress Analyzer"],
            "Nomad": ["Interface Plugs", "Neural Link"]
}

# Languages
LANGUAGES = [
    "English", "Streetslang", "Spanish", "Japanese", "Mandarin", "Italian",
    "Russian", "Amharic", "Hindi", "Cantonese", "Vietnamese", "Thai",
    "Arabic", "German", "Turkish", "Swedish", "French", "Farsi",
    "Portuguese", "Hausa", "Swahili", "Navajo", "Korean", "Hebrew", "Tagalog",
    "Punjabi", "Malay", "Bengali", "Pashto", "Ukrainian", "Polish", "Greek", "Finnish", 
    "Norwegian", "Dutch", "Tamil", "Telugu", "Burmese", "Lao", "Khmer", "Zulu",
    "Yoruba", "Maori", "Inuktitut", "Cherokee"
]

# You can add more constants as needed

