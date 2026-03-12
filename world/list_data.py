"""
Reference data for the +list command: stats, skills, roles, and role abilities.
Descriptions follow Cyberpunk RED Core Rulebook.
"""

# Stat descriptions (abbreviated names and full descriptions)
STAT_DESCRIPTIONS = {
    "intelligence": {
        "abbrev": "INT",
        "name": "Intelligence",
        "description": "Governs your mental acuity and problem-solving. Used for Awareness and Education skills.",
    },
    "reflexes": {
        "abbrev": "REF",
        "name": "Reflexes",
        "description": "Measures how quickly you react. Used for Control and Ranged Weapon skills.",
    },
    "dexterity": {
        "abbrev": "DEX",
        "name": "Dexterity",
        "description": "Your agility and coordination. Used for Body and Fighting skills.",
    },
    "technology": {
        "abbrev": "TECH",
        "name": "Technology",
        "description": "Technical aptitude and mechanical know-how. Used for Technique skills.",
    },
    "cool": {
        "abbrev": "COOL",
        "name": "Cool",
        "description": "Composure under pressure. Used for performance and social skills.",
    },
    "willpower": {
        "abbrev": "WILL",
        "name": "Willpower",
        "description": "Mental fortitude and determination. Used for concentration and endurance.",
    },
    "luck": {
        "abbrev": "LUCK",
        "name": "Luck",
        "description": "Random chance modifier. Can be spent to add to rolls (1d10 per point).",
    },
    "move": {
        "abbrev": "MOVE",
        "name": "Move",
        "description": "Speed and agility in movement. Determines movement rate in combat.",
    },
    "body": {
        "abbrev": "BOD",
        "name": "Body",
        "description": "Physical endurance and strength. Affects HP, death save, and body skills.",
    },
    "empathy": {
        "abbrev": "EMP",
        "name": "Empathy",
        "description": "Emotional awareness and connection. Used for social and performance skills.",
    },
}

# Brief skill descriptions by category
SKILL_DESCRIPTIONS = {
    # Awareness
    "concentration": ("Awareness", "Focus and mental clarity under stress."),
    "conceal_object": ("Awareness", "Hide objects from sight and searches."),
    "lip_reading": ("Awareness", "Understand speech by watching lips."),
    "perception": ("Awareness", "Notice details, spot hidden things."),
    "tracking": ("Awareness", "Follow trails and locate targets."),
    # Body
    "athletics": ("Body", "Running, jumping, climbing, physical exertion."),
    "contortionist": ("Body", "Squeeze through tight spaces, flexibility."),
    "dance": ("Body", "Perform dance and movement arts."),
    "endurance": ("Body", "Resist fatigue and physical strain."),
    "resist_torture_drugs": ("Body", "Withstand torture, drugs, and coercion."),
    "stealth": ("Body", "Move undetected and avoid notice."),
    # Control
    "drive_land": ("Control", "Operate land vehicles."),
    "pilot_air": ("Control", "Operate air vehicles. (Double skill cost)"),
    "pilot_sea": ("Control", "Operate watercraft."),
    "riding": ("Control", "Ride animals and exotic mounts."),
    # Education
    "accounting": ("Education", "Financial records and analysis."),
    "animal_handling": ("Education", "Train and work with animals."),
    "bureaucracy": ("Education", "Navigate institutions and red tape."),
    "business": ("Education", "Commerce and trade."),
    "composition": ("Education", "Writing and creative expression."),
    "criminology": ("Education", "Understand crime and investigation."),
    "cryptography": ("Education", "Codes and secure communications."),
    "deduction": ("Education", "Logical reasoning and detective work."),
    "education": ("Education", "General knowledge and academics."),
    "gamble": ("Education", "Games of chance and betting."),
    "languages": ("Education", "Speak and understand languages."),
    "library_search": ("Education", "Research and find information."),
    "local_expert": ("Education", "Knowledge of a specific area."),
    "tactics": ("Education", "Military strategy and coordination."),
    "wilderness_survival": ("Education", "Survive in the wild."),
    # Fighting
    "brawling": ("Fighting", "Unarmed combat."),
    "evasion": ("Fighting", "Dodge attacks."),
    "martial_arts": ("Fighting", "Structured unarmed combat. (Double skill cost)"),
    "melee": ("Fighting", "Melee weapon combat."),
    # Performance
    "acting": ("Performance", "Portray roles and deceive."),
    "play_instrument": ("Performance", "Play musical instruments."),
    "style": ("Performance", "Personal grooming and presence. Wardrobe & Style, Personal Grooming."),
    # Ranged Weapon
    "archery": ("Ranged Weapon", "Bows and crossbows."),
    "autofire": ("Ranged Weapon", "Automatic weapons. (Double skill cost)"),
    "handgun": ("Ranged Weapon", "Pistols and handguns."),
    "heavy_weapons": ("Ranged Weapon", "Heavy weapons. (Double skill cost)"),
    "shoulder_arms": ("Ranged Weapon", "Rifles and shotguns."),
    # Social
    "bribery": ("Social", "Bribe and influence."),
    "conversation": ("Social", "Talk and negotiate."),
    "human_perception": ("Social", "Read people and motives."),
    "interrogation": ("Social", "Extract information."),
    "persuasion": ("Social", "Convince and influence."),
    "streetwise": ("Social", "Street culture and contacts."),
    "trading": ("Social", "Buy, sell, haggle."),
    # Technique
    "air_vehicle_tech": ("Technique", "Repair air vehicles."),
    "basic_tech": ("Technique", "General repair and tech."),
    "cybertech": ("Technique", "Install and repair cyberware."),
    "demolitions": ("Technique", "Explosives. (Double skill cost)"),
    "electronics": ("Technique", "Electronics and security tech. (Double skill cost)"),
    "first_aid": ("Technique", "Emergency medical care."),
    "forgery": ("Technique", "Counterfeit and falsify."),
    "land_vehicle_tech": ("Technique", "Repair land vehicles."),
    "paramedic": ("Technique", "Advanced medical care. (Double skill cost)"),
    "pick_lock": ("Technique", "Open locks."),
    "pick_pocket": ("Technique", "Steal from pockets."),
    "sea_vehicle_tech": ("Technique", "Repair watercraft."),
    "weaponstech": ("Technique", "Modify and repair weapons."),
    # Role abilities
    "charismatic_impact": ("Rockerboy", "Inspire crowds through performance."),
    "combat_awareness": ("Solo", "Spot threats, gain tactical edge."),
    "interface": ("Netrunner", "Jack into the Net and run programs."),
    "maker": ("Tech", "Improve and upgrade items."),
    "medicine": ("Medtech", "Treat critical injuries and disease."),
    "credibility": ("Media", "Use reputation to influence."),
    "teamwork": ("Lawman", "Call backup from your department."),
    "backup": ("Lawman", "Role ability: call backup."),
    "operator": ("Exec", "Command your team asset."),
    "moto": ("Nomad", "Call upon family resources."),
}

# Role abilities (primary ability per role)
ROLE_ABILITIES = {
    "Rockerboy": {
        "ability": "Charismatic Impact",
        "skill": "charismatic_impact",
        "description": "Through your performance, you can inspire a crowd. Once per session, make a Charismatic Impact + COOL check. Success: influence the crowd's mood or actions for the scene.",
    },
    "Solo": {
        "ability": "Combat Awareness",
        "skill": "combat_awareness",
        "description": "Your combat instincts let you spot threats and gain tactical advantage. +1 to Initiative, can spot ambushes and assess enemy capabilities.",
    },
    "Netrunner": {
        "ability": "Interface",
        "skill": "interface",
        "description": "Jack into the Net and run programs. Navigate Architectures, fight Black ICE, and affect the real world through the NET.",
    },
    "Tech": {
        "ability": "Maker",
        "skill": "maker",
        "description": "Upgrade and innovate. Use Maker + TECH to improve weapons, armor, and gear beyond their base stats.",
    },
    "Medtech": {
        "ability": "Medicine",
        "skill": "medicine",
        "description": "Heal critical injuries and treat disease. Use Medicine + TECH to stabilize, heal, or install speedheal.",
    },
    "Media": {
        "ability": "Credibility",
        "skill": "credibility",
        "description": "Your reputation gives you influence. Use Credibility + COOL to leverage your audience and affect how people act.",
    },
    "Lawman": {
        "ability": "Teamwork",
        "skill": "teamwork",
        "description": "Call backup from your department. Once per session, backup arrives to assist. Strength depends on rank and situation.",
    },
    "Exec": {
        "ability": "Operator",
        "skill": "operator",
        "description": "Command your team asset. You have a loyal subordinate (bodyguard, assistant, etc.) who follows your orders.",
    },
    "Fixer": {
        "ability": "Operator",
        "skill": "operator",
        "description": "Your network of contacts. Use Operator to arrange deals, find buyers, source rare items, or call in favors.",
    },
    "Nomad": {
        "ability": "Moto",
        "skill": "moto",
        "description": "Your family provides. Call upon family resources: vehicles, shelter, supplies, or family members to help.",
    },
}
