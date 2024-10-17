from enum import Enum
from django.db import transaction
from evennia.utils import logger

class AmmoType(Enum):
    ('BASIC', "Basic"),
    ('ARMOR_PIERCING', "Armor Piercing"),
    ('EXPANSIVE', "Expansive"),
    ('RUBBER', "Rubber"),
    ('INCENDIARY', "Incendiary"),
    ('BIOTOXIN', "Biotoxin"),
    ('SLEEP_INDUCING', "Sleep Inducing"),
    ('EMP', "EMP")

    @classmethod
    def choices(cls):
        return [(item.name, item.value) for item in cls]

class Vehicle:
    def __init__(self, description, sdp, seats, speed_combat, speed_narrative, cost):
        self.description = description
        self.sdp = sdp
        self.seats = seats
        self.speed_combat = speed_combat
        self.speed_narrative = speed_narrative
        self.cost = cost
        self.occupants = []

    def enter(self, character):
        if len(self.occupants) < self.seats:
            self.occupants.append(character)
            return True
        return False

    def exit(self, character):
        if character in self.occupants:
            self.occupants.remove(character)
            return True
        return False

class Motorcycle(Vehicle):
    def __init__(self, description, sdp, speed_combat, speed_narrative, cost):
        super().__init__(description, sdp, 2, speed_combat, speed_narrative, cost)

class Car(Vehicle):
    pass

class Boat(Vehicle):
    pass

class Helicopter(Vehicle):
    pass

class Aerodyne(Vehicle):
    pass

# Example usage
roadbike = Motorcycle(
    description="High-performance sport bike with advanced cybernetic controls",
    sdp=35,
    speed_combat=8,
    speed_narrative=(100, 290),  # (mph, km/h)
    cost=20000
)

player = "Player1"  # Assume this is a character object
roadbike.enter(player)

ammunition = [
    {
        "name": "Basic Pistol Ammo",
        "ammo_type": "Basic",
        "weapon_type": "Pistol",
        "damage_modifier": 0,
        "armor_piercing": 0,
        "description": "Standard ammunition for pistols.",
        "cost": 10,
        "quantity": 50
    }
    # ... (add more ammunition types as needed)
]

weapons = [
    {
        "name": "Medium Pistol",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 50,
        "category": "handgun",
        "clip": 12
    },
    {
        "name": "Heavy Pistol",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 100,
        "category": "handgun",
        "clip": 8
    },
    {

        "name": "Very Heavy Pistol",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 100,
        "category": "handgun",
        "clip": 8
    },
    {
        "name": "SMG",
        "damage": "2d6",
        "rof": "4",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 100,
        "category": "handgun",
        "clip": 30
    },
    {

        "name": "Heavy SMG",
        "damage": "3d6",
        "rof": "3",
        "hands": 2,
        "concealable": True,
        "weight": 2,
        "value": 100,
        "category": "handgun",
        "clip": 40
    },
    {
        "name": "Shotgun",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 4
    },
    {
        "name": "Assault Rifle",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 25
    },
    {
        "name": "Sniper Rifle",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 4
    },
    {
        "name": "Bow",
        "damage": "4d6",
        "rof": "2",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "archery"
    },
    {
        "name": "Crossbow",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "archery"
    },
    {
        "name": "Grenade Launcher",
        "damage": "6d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "heavy_weapons",
        "clip": 2
    },
    {
        "name": "Rocket Launcher",
        "damage": "8d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 500,
        "category": "heavy_weapons",
        "clip": 1
    },
    {
        "name": "Flamethrower",
        "damage": "5d6",
        "rof": "2",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 500,
        "category": "heavy_weapons",
        "clip": 4
    },
    {
        "name": "Melee Weapon (Light)",
        "damage": "1d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 50,
        "category": "melee"
    },

    {
        "name": "Melee Weapon (Medium)",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 50,
        "category": "melee"
    },
    {
        "name": "Melee Weapon (Heavy)",
        "damage": "3d6",
        "rof": "2",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "melee"
    },
    {
        "name": "Melee Weapon (Very Heavy)",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 100,
        "category": "melee"
    },
    {
        "name": "Cyberarm (Medium)",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 0,
        "value": 500,
        "category": "brawling"
    },
    {
        "name": "Cyberarm (Heavy)",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 0,
        "value": 1000,
        "category": "brawling"
    },
    {
        "name": "Cyberarm (Very Heavy)",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 0,
        "value": 2500,
        "category": "brawling"
    }
]

    # Armor
armors = [
    {
        "name": "Leather Jacket",
        "sp": 4,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 20
    },
    {
        "name": "Kevlar",
        "sp": 7,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 50
    },
    {
        "name": "Light Armorjack",
        "sp": 11,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Medium Armorjack",
        "sp": 12,
        "ev": 2,
        "locations": "Body",
        "weight": 2,
        "value": 500
    },
    {
        "name": "Heavy Armorjack",
        "sp": 13,
        "ev": 2,
        "locations": "Body",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "Flak",
        "sp": 15,
        "ev": 4,
        "locations": "Body",
        "weight": 3,
        "value": 5000
    },
    {
        "name": "Metalgear",
        "sp": 18,
        "ev": 4,
        "locations": "Body",
        "weight": 3,
        "value": 5000
    },
    {
        "name": "Bulletproof Shield",
        "sp": 10,
        "ev": 2,
        "locations": "Shield",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Helmet",
        "sp": 7,
        "ev": 0,
        "locations": "Head",
        "weight": 1,
        "value": 50
    },
    {
        "name": "Light Bodyweight Suit",
        "sp": 11,
        "ev": 0,
        "locations": "Body, Head, Arms, Legs",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "Medium Bodyweight Suit",
        "sp": 12,
        "ev": 2,
        "locations": "Body, Head, Arms, Legs",
        "weight": 2,
        "value": 5000
    },
    {
        "name": "Heavy Bodyweight Suit",
        "sp": 13,
        "ev": 2,
        "locations": "Body, Head, Arms, Legs",
        "weight": 3,
        "value": 10000
    },
    {
        "name": "Virtuality Goggles",
        "sp": 0,
        "ev": 0,
        "locations": "Eyes",
        "weight": 0,
        "value": 100
    },
    {
        "name": "Radiation Suit",
        "sp": 0,
        "ev": 2,
        "locations": "Body, Head, Arms, Legs",
        "weight": 2,
        "value": 1000
    }
]
    # Gear
gears = [
    {
        "name": "Agent",
        "category": "Electronics",
        "description": "Smartphone-like personal assistant device",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Audio Recorder",
        "category": "Electronics",
        "description": "Records audio",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Binoculars",
        "category": "Optics",
        "description": "Magnifies distant objects",
        "weight": 1,
        "value": 50
    },
    {
        "name": "Braindance Viewer",
        "category": "Electronics",
        "description": "Allows viewing of braindance recordings",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Bug Detector",
        "category": "Electronics",
        "description": "Detects surveillance devices",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Carryall",
        "category": "Clothing",
        "description": "Large bag for carrying gear",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Chemical Analyzer",
        "category": "Electronics",
        "description": "Analyzes chemical compounds",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Computer",
        "category": "Electronics",
        "description": "Portable computer",
        "weight": 1,
        "value": 500
    },
    {
        "name": "Disposable Cell Phone",
        "category": "Electronics",
        "description": "One-time use phone",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Drum Synthesizer",
        "category": "Music",
        "description": "Electronic drum kit",
        "weight": 1,
        "value": 500
    },
    {
        "name": "Duct Tape",
        "category": "Tools",
        "description": "Multipurpose adhesive tape",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Electric Guitar",
        "category": "Music",
        "description": "Musical instrument",
        "weight": 2,
        "value": 500
    },
    {
        "name": "Flashlight",
        "category": "Tools",
        "description": "Portable light source",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Food Stick",
        "category": "Survival",
        "description": "Nutritional meal replacement",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Glow Paint",
        "category": "Tools",
        "description": "Luminescent paint",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Glow Stick",
        "category": "Tools",
        "description": "Chemical light source",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Grapple Gun",
        "category": "Tools",
        "description": "Fires a grappling hook",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Handcuffs",
        "category": "Tools",
        "description": "Restrains a person's wrists",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Homing Tracer",
        "category": "Electronics",
        "description": "Tracking device",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Inflatable Bed & Sleep-bag",
        "category": "Survival",
        "description": "Portable sleeping arrangement",
        "weight": 1,
        "value": 20
    },
    {
        "name": "Kibble Pack",
        "category": "Survival",
        "description": "Dry pet food for human consumption",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Linear Frame Sigma",
        "category": "Cyberware",
        "description": "Exoskeleton for enhanced strength",
        "weight": 2,
        "value": 5000
    },
    {
        "name": "Linear Frame Beta",
        "category": "Cyberware",
        "description": "Advanced exoskeleton",
        "weight": 3,
        "value": 10000
    },
    {
        "name": "Lock Picking Set",
        "category": "Tools",
        "description": "Tools for picking locks",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Medscanner",
        "category": "Medical",
        "description": "Scans for medical issues",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Medtech Bag",
        "category": "Medical",
        "description": "Contains medical supplies",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Memory Chip",
        "category": "Electronics",
        "description": "Data storage device",
        "weight": 0.1,
        "value": 10
    },
    {
        "name": "MRE",
        "category": "Survival",
        "description": "Meal Ready to Eat",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Personal CarePak",
        "category": "Survival",
        "description": "Basic hygiene and care products",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Pocket Amplifier",
        "category": "Music",
        "description": "Small, portable amplifier",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Radar Detector",
        "category": "Electronics",
        "description": "Detects radar signals",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Radio Communicator",
        "category": "Electronics",
        "description": "Two-way radio",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Radio Scanner/Music Player",
        "category": "Electronics",
        "description": "Scans radio frequencies and plays music",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Roadflare",
        "category": "Tools",
        "description": "Bright emergency light",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Rope",
        "category": "Tools",
        "description": "Strong, durable rope",
        "weight": 1,
        "value": 20
    },
    {
        "name": "Scrambler/Descrambler",
        "category": "Electronics",
        "description": "Encrypts and decrypts communications",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Smart Glasses",
        "category": "Electronics",
        "description": "Computerized eyewear",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Techtool",
        "category": "Tools",
        "description": "Multipurpose tool for tech work",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Camping Equipment",
        "category": "Survival",
        "description": "Basic camping gear",
        "weight": 2,
        "value": 50
    },
    {
        "name": "Tool Bag",
        "category": "Tools",
        "description": "Contains various tools",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Biotoxin",
        "category": "Medical",
        "description": "Dangerous biological toxin",
        "weight": 0.1,
        "value": 500
    },
    {
        "name": "Poison",
        "category": "Medical",
        "description": "Toxic substance",
        "weight": 0.1,
        "value": 100
    },
    {
        "name": "Video Camera",
        "category": "Electronics",
        "description": "Records video footage",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Virtuality Goggles",
        "category": "Electronics",
        "description": "For viewing virtual reality",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Black Lace",
        "category": "Drugs",
        "description": "Primary Effect - Lasts 24 Hours. User takes 2d6 Humanity Loss upon taking a dose, which is returned if the user isn't affected by Black Lace's Secondary Effect. For the duration of the Primary Effect, the user ignores the effects of the Seriously Wounded Wound State. Secondary Effect (DV17) Humanity Loss from Primary Effect isn't returned. If the user wasn't already addicted to Black Lace, they are now. While addicted, unless the user is currently experiencing the Primary Effect of Black Lace, their REF is lowered by 2 points.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Blue Glass",
        "category": "Drugs",
        "description": "",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Boost",
        "category": "Drugs",
        "description": "",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Smash",
        "category": "Drugs",
        "description": "",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Synthcoke",
        "category": "Drugs",
        "description": "",
        "weight": 0.5,
        "value": 20
    },
]
#Cyberdecks (External)
cyberdecks = [
    {
        "name": "SGI Technologies Elysia Mark V",
        "description": "The Elysia has a controversial history, being the favored deck of Rache Bartmoss. The Mark V capitalizes on the punk aesthetic by building a powerful machine in a trendy, anti-corporate case. One of the more expensive decks on the market.",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 9,
        "value": 1000,
    },
    {
        "name": "Militech Dataknight-7",
        "description": "The Militech DataKnight-7 is a reliable, mid-range cyberdeck and is Militech's primary - and longest lasting - entry into the personal cyberdeck market. It has decent specs and is used by consumers and netrunners alike.",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 7,
        "value": 500,
    },
    {
        "name": "Zhirafa Deshevyy X3",
        "description": "The Deshevyy X3 was rumored to come from a Zhirafa program to develop in-house netrunners. Affectionately known as the DX3, its main saving grace was Zhirafa dumping the lot of them on the market at a budget rate for would-be elite netrunners.",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 5,
        "value": 100,
    },
    {
        "name": "Kiraama Advanced Deck",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 5,
        "value": 500,
    },
    {
        "name": "Kirama Entry Deck",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 5,
        "any_slots": 0,
        "value": 100,
    },
    {
        "name": "Kirama Training Deck",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 5,
        "any_slots": 0,
        "value": 20,
    },
    {
        "name": "Microtech Assault",
        "description": "",
        "hardware_slots": 5,
        "program_slots": 4,
        "any_slots": 0,
        "value": 500,
    },
    {
        "name": "Microtech Scout",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 5,
        "value": 500,
    },
    {
        "name": "Microtech Warrior",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 7,
        "any_slots": 0,
        "value": 1000,
    },
    {
        "name": "Raven Microcyb Hummingbird",
        "description": "",
        "hardware_slots": 2,
        "program_slots": 0,
        "any_slots": 0,
        "value": 1000,
    },
    {
        "name": "Raven Microcyb Kestrel 2",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 7,
        "any_slots": 0,
        "value": 1000,
    },
    {
        "name": "Raven Microcyb Phoenix",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 6,
        "value": 1000,
    },
    {
        "name": "SGI Technologies Kerberos",
        "description": "",
        "hardware_slots": 5,
        "program_slots": 6,
        "any_slots": 0,
        "value": 1000,
    },
    {
        "name": "SGI Technologies Verdant Knight",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 9,
        "any_slots": 0,
        "value": 500,
    },
    {
        "name": "SIG Technologies Warlock's Book",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 9,
        "value": 500,
    },
    {
        "name": "Zetatech Kaliya",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 3,
        "any_slots": 6,
        "value": 500,
    },
    {
        "name": "Zetatech MicroMate",
        "description": "",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 9,
        "value": 500,
    },
    {
        "name": "Zetatech Parraline 6000",
        "description": "",
        "hardware_slots": 6,
        "program_slots": 3,
        "any_slots": 0,
        "value": 500,
    }
]

@transaction.atomic
def initialize_weapons():
    from world.inventory.models import Weapon
    
    for weapon_data in weapons:
        if not all(weapon_data.values()):
            logger.warn(f"Incomplete weapon data found: {weapon_data}")
            continue
        
        weapon, created = Weapon.objects.get_or_create(
            name=weapon_data['name'],
            defaults={
                'damage': weapon_data['damage'],
                'rof': weapon_data['rof'],
                'hands': weapon_data['hands'],
                'concealable': weapon_data['concealable'],
                'weight': weapon_data['weight'],
                'value': weapon_data['value']
            }
        )
        if created:
            logger.info(f"Created weapon: {weapon.name}")
        else:
            # Update existing weapon if data has changed
            updated = False
            for key, value in weapon_data.items():
                if getattr(weapon, key) != value:
                    setattr(weapon, key, value)
                    updated = True
            if updated:
                weapon.save()
                logger.info(f"Updated weapon: {weapon.name}")

@transaction.atomic
def initialize_armor():
    from world.inventory.models import Armor
    
    for armor_data in armors:
        if not all(armor_data.values()):
            logger.warn(f"Incomplete armor data found: {armor_data}")
            continue
        
        armor, created = Armor.objects.get_or_create(
            name=armor_data['name'],
            defaults={
                'sp': armor_data['sp'],
                'ev': armor_data['ev'],
                'locations': armor_data['locations']
            }
        )
        if created:
            logger.info(f"Created armor: {armor.name}")
        else:
            # Update existing armor if data has changed
            updated = False
            for key, value in armor_data.items():
                if getattr(armor, key) != value:
                    setattr(armor, key, value)
                    updated = True
            if updated:
                armor.save()
                logger.info(f"Updated armor: {armor.name}")

@transaction.atomic
def initialize_gear():
    from world.inventory.models import Gear
    
    for gear_data in gears:
        if not all(gear_data.values()):
            logger.warn(f"Incomplete gear data found: {gear_data}")
            continue
        
        gear, created = Gear.objects.get_or_create(
            name=gear_data['name'],
            defaults={
                'category': gear_data['category'],
                'description': gear_data['description'],
                'weight': gear_data['weight'],
                'value': gear_data['value']
            }
        )
        if created:
            logger.info(f"Created gear: {gear.name}")
        else:
            # Update existing gear if data has changed
            updated = False
            for key, value in gear_data.items():
                if getattr(gear, key) != value:
                    setattr(gear, key, value)
                    updated = True
            if updated:
                gear.save()
                logger.info(f"Updated gear: {gear.name}")

@transaction.atomic
def initialize_cyberdecks():
    from world.inventory.models import Cyberdeck
    
    for cyberdeck_data in cyberdecks:
        if not all(cyberdeck_data.values()):
            logger.warn(f"Incomplete gear data found: {cyberdeck_data}")
            continue
        
        cyberdeck, created = Cyberdeck.objects.get_or_create(
            name=cyberdeck_data['name'],
            defaults={
                'description': cyberdeck_data['description'],
                'hardware_slots': cyberdeck_data['hardware_slots'],
                'program_slots': cyberdeck_data['program_slots'],
                'any_slots': cyberdeck_data['any_slots'],
                'value': cyberdeck_data['value']
            }
        )
        if created:
            logger.info(f"Created gear: {cyberdeck.name}")
        else:
            # Update existing cyberdeck if data has changed
            updated = False
            for key, value in cyberdeck_data.items():
                if getattr(cyberdeck, key) != value:
                    setattr(cyberdeck, key, value)
                    updated = True
            if updated:
                cyberdeck.save()
                logger.info(f"Updated gear: {cyberdeck.name}")
        print(f"Initilized {len(cyberdeck)} cyberdeck types.")


@transaction.atomic
def initialize_ammunition():
    from world.inventory.models import Ammunition, AmmoType
    for ammo_data in ammunition:
        Ammunition.objects.get_or_create(
            name=ammo_data['name'],
            defaults={
                'ammo_type': getattr(AmmoType, ammo_data['ammo_type']),
                'weapon_type': ammo_data['weapon_type'],
                'damage_modifier': ammo_data['damage_modifier'],
                'armor_piercing': ammo_data['armor_piercing'],
                'description': ammo_data['description'],
                'cost': ammo_data['cost'],
                'quantity': 0
            }
        )
    print(f"Initialized {len(ammunition)} ammunition types.")

def populate_weapons():
    from world.inventory.models import Weapon
    for weapon_data in weapons:
        Weapon.objects.get_or_create(**weapon_data)
    print(f"Populated {len(weapons)} weapons.")

def populate_armor():
    from world.inventory.models import Armor
    for armor_data in armors:
        Armor.objects.get_or_create(**armor_data)
    print(f"Populated {len(armors)} armor pieces.")

def populate_gear():
    from world.inventory.models import Gear
    for gear_data in gears:
        Gear.objects.get_or_create(**gear_data)
    print(f"Populated {len(gears)} gear items.")

def populate_cyberdecks():
    from world.inventory.models import Cyberdeck
    for cyberdeck_data in cyberdecks:
        Cyberdeck.objects.get_or_create(**cyberdeck_data)
    print(f"Populated {len(cyberdecks)} cyberdecks.")

def populate_ammunition():
    from world.inventory.models import Ammunition
    for ammo_data in ammunition:
        Ammunition.objects.get_or_create(**ammo_data)
    print(f"Populated {len(ammunition)} cyberdecks.")

def populate_all_equipment():
    from world.cyberware.utils import populate_cyberware
    populate_weapons()
    populate_armor()
    populate_gear()
    populate_cyberware()
    populate_ammunition()
    populate_cyberdecks()
    print("All equipment populated successfully.")
