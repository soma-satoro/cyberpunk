from world.inventory.models import Weapon, Armor, Gear, Ammunition, AmmoType, Cyberdeck, Vehicle
from world.cyberware.models import Cyberware
from world.cyberware.utils import populate_cyberware
from enum import Enum
from django.db import transaction
from evennia.utils import logger

class AmmoType(Enum):
    BASIC = "Basic"
    ARMOR_PIERCING = "Armor Piercing"
    EXPANSIVE = "Expansive"
    RUBBER = "Rubber"
    INCENDIARY = "Incendiary"
    BIOTOXIN = "Biotoxin"
    SLEEP_INDUCING = "Sleep Inducing"
    EMP = "EMP"

# Cyberpunk Red vehicles - Land, Sea, and Air (from core rulebook)
# All CHOOH² powered, Super Luxury category
# speed_combat: MOVE units; speed_narrative: "X MPH / Y KPH"
vehicles = [
    # Land Vehicles
    {
        "name": "Roadbike",
        "description": "Common CHOOH² powered bike.",
        "category": "land",
        "sdp": 35,
        "seats": 2,
        "speed_combat": 20,
        "speed_narrative": "100 MPH / 161 KPH",
        "value": 20000,
    },
    {
        "name": "Superbike",
        "description": "Exotic CHOOH² streetbike, capable of extreme speeds.",
        "category": "land",
        "sdp": 35,
        "seats": 2,
        "speed_combat": 60,
        "speed_narrative": "300 MPH / 483 KPH",
        "value": 100000,
    },
    {
        "name": "Compact Groundcar",
        "description": "Common CHOOH² powered car.",
        "category": "land",
        "sdp": 50,
        "seats": 4,
        "speed_combat": 20,
        "speed_narrative": "100 MPH / 161 KPH",
        "value": 30000,
    },
    {
        "name": "High Performance Groundcar",
        "description": "CHOOH² powered sportscar.",
        "category": "land",
        "sdp": 50,
        "seats": 4,
        "speed_combat": 40,
        "speed_narrative": "200 MPH / 322 KPH",
        "value": 50000,
    },
    {
        "name": "Super Groundcar",
        "description": "Exotic CHOOH² sportscar, capable of extreme speeds.",
        "category": "land",
        "sdp": 50,
        "seats": 2,
        "speed_combat": 60,
        "speed_narrative": "300 MPH / 483 KPH",
        "value": 100000,
    },
    # Sea Vehicles
    {
        "name": "Jetski",
        "description": "Common CHOOH² powered personal watercraft.",
        "category": "sea",
        "sdp": 35,
        "seats": 2,
        "speed_combat": 20,
        "speed_narrative": "60 MPH / 97 KPH",
        "value": 20000,
    },
    {
        "name": "Speedboat",
        "description": "CHOOH² powered speedboat.",
        "category": "sea",
        "sdp": 50,
        "seats": 4,
        "speed_combat": 20,
        "speed_narrative": "60 MPH / 97 KPH",
        "value": 30000,
    },
    {
        "name": "Cabin Cruiser",
        "description": "Luxury CHOOH² powerboat with room to provide accommodations for a small, privileged few. Cabin Cruisers have customized rooms.",
        "category": "sea",
        "sdp": 60,
        "seats": 4,  # 2 per room, minimum 2 rooms
        "speed_combat": 10,
        "speed_narrative": "15 MPH / 24 KPH",
        "value": 60000,  # 30,000eb per room, minimum 2 rooms
    },
    {
        "name": "Yacht",
        "description": "Luxury CHOOH² pleasurecraft with ample room to provide accommodations and entertainment for a host and their distinguished guests. Yachts have customized rooms.",
        "category": "sea",
        "sdp": 100,
        "seats": 16,  # 4 per room, minimum 4 rooms
        "speed_combat": 10,
        "speed_narrative": "15 MPH / 24 KPH",
        "value": 200000,  # 50,000eb per room, minimum 4 rooms
    },
    # Air Vehicles
    {
        "name": "Gyrocopter",
        "description": "A tiny CHOOH² powered rotorcraft favored by flying enthusiasts.",
        "category": "air",
        "sdp": 35,
        "seats": 2,
        "speed_combat": 20,
        "speed_narrative": "100 MPH / 161 KPH",
        "value": 20000,
    },
    {
        "name": "Helicopter",
        "description": "Full featured CHOOH² powered helicopter capable of sustained flight.",
        "category": "air",
        "sdp": 60,
        "seats": 4,
        "speed_combat": 40,
        "speed_narrative": "200 MPH / 322 KPH",
        "value": 40000,
    },
    {
        "name": "AV-4 Multipurpose Aerodyne",
        "description": "Highly advanced CHOOH² vertical thrust engine powered flying vehicle.",
        "category": "air",
        "sdp": 100,
        "seats": 6,
        "speed_combat": 40,
        "speed_narrative": "200 MPH / 322 KPH",
        "value": 50000,
    },
    {
        "name": "AV-9 Super Aerodyne",
        "description": "Exotic CHOOH² vertical thrust engine flying vehicle, capable of extreme speeds.",
        "category": "air",
        "sdp": 60,
        "seats": 2,
        "speed_combat": 60,
        "speed_narrative": "300 MPH / 483 KPH",
        "value": 100000,
    },
    {
        "name": "Aerozep",
        "description": "Modern cargo blimps that range wildly in size depending on their function. Aerozeps have customized rooms.",
        "category": "air",
        "sdp": 100,
        "seats": 4,  # 2 per room, minimum 2 rooms
        "speed_combat": 20,
        "speed_narrative": "100 MPH / 161 KPH",
        "value": 60000,  # 30,000eb per room, minimum 2 rooms
    },
    # Black Chrome vehicles
    {
        "name": "Tanson JetBoy Hoverboard",
        "description": "Hoverboard with twin turbines. 15 MOVE, 30 MPH. Driven with Athletics. 10 SDP. Cannot be upgraded.",
        "category": "land",
        "sdp": 10,
        "seats": 1,
        "speed_combat": 15,
        "speed_narrative": "30 MPH / 48 KPH",
        "value": 1000,
    },
    {
        "name": "Tanson Bellhop",
        "description": "Folds into luggage-sized gyrocopter. 1 seat. Transform with Action. Incompatible with Seating Upgrade.",
        "category": "air",
        "sdp": 35,
        "seats": 1,
        "speed_combat": 20,
        "speed_narrative": "100 MPH / 161 KPH",
        "value": 16000,
    },
    {
        "name": "Zonda Molly 1K",
        "description": "Classic off-road workhorse. 2 seats. No Interface Plug control. 60 MPH max.",
        "category": "land",
        "sdp": 50,
        "seats": 2,
        "speed_combat": 20,
        "speed_narrative": "60 MPH / 97 KPH",
        "value": 15000,
    },
    {
        "name": "AmeriCar EconoCompact",
        "description": "Affordable no-frills compact. 3 seats. Rear folds for storage.",
        "category": "land",
        "sdp": 50,
        "seats": 3,
        "speed_combat": 20,
        "speed_narrative": "100 MPH / 161 KPH",
        "value": 20000,
    },
    {
        "name": "Harvey 100",
        "description": "AmeriCar 'motorcycle for everyone.' Customizable. Frankenbike reputation.",
        "category": "land",
        "sdp": 35,
        "seats": 2,
        "speed_combat": 20,
        "speed_narrative": "100 MPH / 161 KPH",
        "value": 20000,
    },
    {
        "name": "Makigai Ebi",
        "description": "Reliable mini-hatchback. 35 SDP. Incompatible with Heavy Chassis. Great fuel efficiency.",
        "category": "land",
        "sdp": 35,
        "seats": 4,
        "speed_combat": 20,
        "speed_narrative": "100 MPH / 161 KPH",
        "value": 23000,
    },
    {
        "name": "The Grundy",
        "description": "Grundy Salvage scrap-built truck. Heavy Chassis, Armored Chassis, Combat Plow. Mobile bunker.",
        "category": "land",
        "sdp": 50,
        "seats": 4,
        "speed_combat": 20,
        "speed_narrative": "100 MPH / 161 KPH",
        "value": 41000,
    },
    {
        "name": "Zetatech AeroVox",
        "description": "Economy-class aerodyne. Heavy Chassis. Sturdy corporate transport.",
        "category": "air",
        "sdp": 100,
        "seats": 6,
        "speed_combat": 40,
        "speed_narrative": "200 MPH / 322 KPH",
        "value": 51000,
    },
    {
        "name": "Zetatech Destination",
        "description": "Compact aerodyne. 4 seats. Affordable and reliable.",
        "category": "air",
        "sdp": 100,
        "seats": 4,
        "speed_combat": 40,
        "speed_narrative": "200 MPH / 322 KPH",
        "value": 40000,
    },
    # Interface RED Vol 3: Spinning Your Wheels
    {
        "name": "Bicycle",
        "description": "Yang's Wheels. Speed BODY-dependent. Upgrades: Electric Pedal Assist, Enclosure, etc.",
        "category": "land",
        "sdp": 15,
        "seats": 1,
        "speed_combat": 15,
        "speed_narrative": "BODY Dependent",
        "value": 100,
    },
]

ammunition = [
    {
        "name": "Basic Pistol Ammo",
        "ammo_type": "BASIC",
        "weapon_type": "Pistol",
        "damage_modifier": 0,
        "armor_piercing": 0,
        "description": "Standard ammunition for pistols.",
        "cost": 10,
        "quantity": 50
    },
    {
        "name": "Basic Rifle Ammo",
        "ammo_type": "BASIC",
        "weapon_type": "Rifle",
        "damage_modifier": 0,
        "armor_piercing": 0,
        "description": "Standard ammunition for rifles.",
        "cost": 10,
        "quantity": 50
    },
    {
        "name": "Basic Shotgun Ammo",
        "ammo_type": "BASIC",
        "weapon_type": "Shotgun",
        "damage_modifier": 0,
        "armor_piercing": 0,
        "description": "Standard ammunition for shotguns.",
        "cost": 10,
        "quantity": 50
    },
    {
        "name": "Basic SMG Ammo",
        "ammo_type": "BASIC",
        "weapon_type": "SMG",
        "damage_modifier": 0,
        "armor_piercing": 0,
        "description": "Standard ammunition for SMGs.",
        "cost": 10,
        "quantity": 50
    },
    {
        "name": "Rocket Ammo",
        "ammo_type": "EXPLOSIVE",
        "weapon_type": "Heavy Weapons",
        "damage_modifier": 0,
        "armor_piercing": 0,
        "description": "Standard ammunition for rocket launchers.",
        "cost": 50,
        "quantity": 10
    },
    {
        "name": "Flamethrower Ammo",
        "ammo_type": "FLAMETHROWER",
        "weapon_type": "Heavy Weapons",
        "damage_modifier": 0,
        "armor_piercing": 0,
        "description": "Standard ammunition for flamethrowers.",
        "cost": 50,
        "quantity": 10
    },
    {
        "name": "Basic LMG Ammo",
        "ammo_type": "BASIC",
        "weapon_type": "Heavy Weapons",
        "damage_modifier": 0,
        "armor_piercing": 0,
        "description": "Standard ammunition for light machine guns.",
        "cost": 20,
        "quantity": 100
    },
    # Solo of Fortune 2045 (Mr. A-Maaaaaaze) ammunition types
    {"name": "Burrowing Ammo", "ammo_type": "BURROWING", "weapon_type": "Generic", "damage_modifier": 0, "armor_piercing": 0, "description": "Rounds dig into target. Solo of Fortune 2045.", "cost": 100},
    {"name": "Explosive Ammo", "ammo_type": "EXPLOSIVE", "weapon_type": "Generic", "damage_modifier": 0, "armor_piercing": 0, "description": "Explosive rounds. Solo of Fortune 2045.", "cost": 100},
    {"name": "High Precision Ammo", "ammo_type": "HIGH_PRECISION", "weapon_type": "Generic", "damage_modifier": 0, "armor_piercing": 0, "description": "Improved accuracy ammunition. Solo of Fortune 2045.", "cost": 100},
    {"name": "High Velocity Ammo", "ammo_type": "HIGH_VELOCITY", "weapon_type": "Generic", "damage_modifier": 0, "armor_piercing": 0, "description": "Increased muzzle velocity. Solo of Fortune 2045.", "cost": 100},
    {"name": "Hyper Expansive Ammo", "ammo_type": "HYPER_EXPANSIVE", "weapon_type": "Generic", "damage_modifier": 0, "armor_piercing": 0, "description": "Enhanced expansive rounds. Solo of Fortune 2045.", "cost": 100},
    {"name": "Serrated Arrow", "ammo_type": "SERRATED_ARROW", "weapon_type": "Archery", "damage_modifier": 0, "armor_piercing": 0, "description": "Serrated arrow ammunition. Solo of Fortune 2045.", "cost": 100},
    {"name": "Hollow Point Ammo", "ammo_type": "HOLLOW_POINT", "weapon_type": "Generic", "damage_modifier": 0, "armor_piercing": 0, "description": "Hollow point expansion. Solo of Fortune 2045.", "cost": 100},
    {"name": "Tracer Ammo", "ammo_type": "TRACER", "weapon_type": "Generic", "damage_modifier": 0, "armor_piercing": 0, "description": "Tracer rounds for visibility. Solo of Fortune 2045.", "cost": 50},
    # Danger Gal Dossier
    {"name": "Junk Ammunition", "ammo_type": "JUNK", "weapon_type": "Generic", "damage_modifier": 0, "armor_piercing": 0, "description": "Poor quality rounds. -1d6 vs SP 1+, Autofire -1. Arrows, Bullets, Slugs. 50 rounds.", "cost": 10},
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
    },
    # Black Chrome weapons
    {
        "name": "Militech Fox Dual Ammo Pistol",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 10,
        "description": "Exotic Heavy Pistol with twin helical magazines. Each magazine can hold different ammo types. Reload each magazine separately."
    },
    {
        "name": "Militech Mastiff SMG",
        "damage": "2d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "handgun",
        "clip": 30,
        "description": "Exotic Combination SMG and Shotgun. Shotgun has 3 shots. Both modes use separate magazines."
    },
    {
        "name": "ModFire 10X",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 8,
        "description": "Exotic Heavy Pistol that transforms into SMG or Assault Rifle with modular parts. 1 minute to convert."
    },
    {
        "name": "Westwood",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "handgun",
        "clip": 6,
        "description": "Chrome .44 magnum from Nova Arms Classic Guns of Film series. Incompatible with magazine attachments."
    },
    {
        "name": "Sanroo HelloCutie Ultra-K8",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 5000,
        "category": "handgun",
        "clip": 30,
        "description": "Excellent Quality Exotic Very Heavy Pistol reconfigurable to Heavy SMG. 2 attachment slots."
    },
    {
        "name": "Superchrome Sidearm",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 8,
        "description": "Exotic Very Heavy Pistol. +2 Wardrobe and Style when worn openly."
    },
    {
        "name": "Sternmeyer M-04 Variable Assault",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 25,
        "description": "Exotic Combination Assault Rifle and Grenade Launcher. Rifle: 20 rounds, GL: 2 grenades. Poor Quality."
    },
    {
        "name": "Superchrome Glam Rifle",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 25,
        "description": "Exotic Assault Rifle. +2 Wardrobe and Style when worn openly."
    },
    {
        "name": "Tommyknocker",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "handgun",
        "clip": 8,
        "description": "Exotic Combination Very Heavy Pistol and Poor Quality Shotgun. BODY 10+ or two hands or it flies from grip."
    },
    {
        "name": "E-TACK Public Defender",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "handgun",
        "clip": 8,
        "description": "Exotic Heavy Pistol with Smartgun Link and stun setting. Requires Subdermal Grip. Less-than-lethal mode available."
    },
    {
        "name": "Kendachi Mono-Katana",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "melee",
        "description": "Monofilament katana. Very Heavy Melee Weapon."
    },
    {
        "name": "Zhirafa Rhinocefist",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "melee",
        "description": "Heavy Melee Weapon. Carbo-glass knuckle dusters. Concealable."
    },
    # Edgerunners Mission Kit weapons (2070s)
    {
        "name": "Arasaka HJKE-11 Yukimura",
        "damage": "3d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "handgun",
        "clip": 30,
        "description": "Exotic SMG with Smart Rebuild. Single shot: 3d6, 3 rounds/check. Autofire x3. +1 Attack. Improved Smart Ammo compatible."
    },
    {
        "name": "Arasaka HJSH-18 Masamune",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 24,
        "description": "Exotic Assault Rifle with Power Rebuild. 5d6 single (3 rounds), 4d6 if fewer. Power: +5 Critical Bonus, ricochet shots."
    },
    {
        "name": "Arasaka TKI-20 Shingen",
        "damage": "3d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "handgun",
        "clip": 30,
        "description": "Exotic Heavy SMG with Smart Rebuild. Autofire x4. 3d6/3 rounds or 2d6. +1 Attack. Improved Smart Ammo."
    },
    {
        "name": "Budget Arms Carnage",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "shoulder_arms",
        "clip": 5,
        "description": "Poor Quality Shotgun with Power Rebuild. BODY 10+ or Torn Muscle. Power: +5 Critical Bonus, ricochet."
    },
    {
        "name": "Constitutional Arms Unity",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "handgun",
        "clip": 12,
        "description": "Exotic Heavy Pistol with Power Rebuild. Aimed Shot: 4d6. Power: +5 Critical Bonus, ricochet."
    },
    {
        "name": "Kang Tao L-69 Zhuo",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 32,
        "description": "Exotic Shotgun with Smart Rebuild. Improved Smart Shells only. 8 shells per shot. 4d6 to 6m area."
    },
    {
        "name": "Militech Crusher",
        "damage": "3d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 12,
        "description": "Exotic Very Heavy Pistol with Power Rebuild. Shotgun Shells only. 3d6 to 6m area. Power: ricochet."
    },
    {
        "name": "Militech M-10AF Lexington",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 21,
        "description": "Exotic Heavy Pistol with Power Rebuild. Power: +5 Critical Bonus, ricochet."
    },
    {
        "name": "Militech M-76e Omaha",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "handgun",
        "clip": 9,
        "description": "Exotic Heavy Pistol with Tech Rebuild. Charge: ROF2, 3 rounds/shot, fire through Thin Cover, half SP."
    },
    {
        "name": "Rostović DB-2 Satara Shotgun",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 2,
        "description": "Exotic Shotgun with Tech Rebuild. Dual barrels, separate ammo types. Charge: fire through Thin Cover, half SP."
    },
    {
        "name": "Techtronika RT-46 Burya",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 4,
        "description": "Exotic Very Heavy Pistol with Tech Rebuild. Charge without Move Action. Muscle&Bone Lace or Cyberarm or Broken Arm."
    },
    {
        "name": "Techtronika SPT32 Grad",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 4,
        "description": "Excellent Quality Exotic Sniper Rifle with Power Rebuild. +1 Attack. Bolt action: 1 Action between shots."
    },
    {
        "name": "Tsunami Arms Nekomata",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 4,
        "description": "Sniper Rifle with Tech Rebuild. Charged: fire through Thin and Thick Cover, half SP."
    },
    # Interface RED Vol 2: The 12 Days of Gunmas
    {
        "name": "Arasaka WAA Bullpup Assault Weapon",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 30,
        "description": "Exotic Assault Rifle with Smartgun Link. Autofire (4), Suppressive Fire. Loads Non-Basic Ammunition."
    },
    {
        "name": "Constitutional Arms Multi-Ammo Pistol",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 500,
        "category": "handgun",
        "clip": 5,
        "description": "Exotic Very Heavy Pistol. Load with up to 5 different Very Heavy Pistol ammo types, select per shot."
    },
    {
        "name": "IMI Chainknife",
        "damage": "2d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 500,
        "category": "melee",
        "description": "Exotic Medium Melee. Action to rev up; while revved = Excellent Quality Very Heavy Melee (4d6). Until dropped/stowed/revved down."
    },
    {
        "name": "Kendachi Dragon Flamethrower",
        "damage": "5d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "heavy_weapons",
        "clip": 2,
        "description": "Exotic Shotgun. Heavy Weapons Skill. Incendiary Shotgun Shells only. Targets take 4 HP/turn until Action to put out. No Critical Injury, no Aimed Shots."
    },
    {
        "name": "Magnum Opus Hellbringer",
        "damage": "5d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 3,
        "description": "Exotic Very Heavy Pistol. BODY 10+ or jams after each shot; Action to unjam."
    },
    {
        "name": "Malorian Arms Sub-Flechette Gun",
        "damage": "3d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 2,
        "value": 5000,
        "category": "handgun",
        "clip": 25,
        "description": "Excellent Quality Exotic Heavy SMG. Autofire (4), Suppressive Fire, Smartgun Link. Unique AP ammo ablates 4/ hit."
    },
    {
        "name": "Militech Crusher SSG",
        "damage": "3d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "handgun",
        "clip": 6,
        "description": "Exotic Very Heavy Pistol (2020 classic). Shotgun Shell Ammunition only."
    },
    {
        "name": "Mustang Arms ARS-5 Submachine Gun",
        "damage": "3d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "handgun",
        "clip": 40,
        "description": "Exotic Heavy SMG. Autofire (3), Suppressive Fire, Smartgun Link, Infrared Nightvision Scope, Sniping Scope."
    },
    {
        "name": "Nomad Pneumatic Bolt Gun",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 8,
        "description": "Exotic Sniper Rifle. Fires Arrows, loads all Non-Basic Ammunition. 4 rotating barrels, built-in air compressor."
    },
    {
        "name": "Nova Model 757 Cityhunter",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 18,
        "description": "Exotic Heavy Pistol. Smartgun Link, Smart Ammo. Unique caseless trounds; ammo in 18-round packs."
    },
    {
        "name": "Stolbovoy ST-5 Assault Rifle",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "shoulder_arms",
        "clip": 20,
        "description": "Poor Quality Exotic Assault Rifle. Autofire (4), Suppressive Fire. When jammed, 50% chance to fire and clear jam. Loads Non-Basic Ammunition."
    },
    {
        "name": "Teen Dreem",
        "damage": "2d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 20,
        "category": "handgun",
        "clip": 10,
        "description": "Poor Quality Exotic SMG. Autofire/Suppressive Fire (2+ bullets): drains clip, barrel melts and weapon destroyed."
    },
    # Interface RED Vol 3: Woodchipper's Garage
    {
        "name": "Biotechnica Enviro-Launcher",
        "damage": "8d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 500,
        "category": "heavy_weapons",
        "clip": 1,
        "description": "Exotic Rocket Launcher. Explosive, Decomposable ammunition."
    },
    {
        "name": "BudgetArms Triple Threat",
        "damage": "8d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 500,
        "category": "heavy_weapons",
        "clip": 2,
        "description": "Exotic Rocket Launcher. Explosive. Integrated Poor Quality Grenade Launcher."
    },
    {
        "name": "Flare Gun",
        "damage": "6d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 100,
        "category": "heavy_weapons",
        "clip": 1,
        "description": "Exotic Grenade Launcher. Explosive, Roadflare ammunition."
    },
    {
        "name": "Midnight Arms SDF-45",
        "damage": "8d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 1000,
        "category": "heavy_weapons",
        "clip": 4,
        "description": "Exotic Rocket Launcher. Explosive, Double Launch. Max range 400 m/yd."
    },
    {
        "name": "Militech Aegis",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "heavy_weapons",
        "clip": 8,
        "description": "Poor Quality Exotic Shotgun. Battery-powered. Shotgun Shells, less-than-lethal. 8 charges, 1hr recharge. No Critical Injury, no armor ablation. Reduces to 1 HP Unconscious if would kill."
    },
    {
        "name": "Militech Archimedes",
        "damage": "8d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 5000,
        "category": "heavy_weapons",
        "clip": 1,
        "description": "Excellent Quality Exotic Rocket Launcher. Pilot Air Vehicle Skill. Smart Rockets only. Requires Targeting Scope. Includes 1 Smart Rocket."
    },
    {
        "name": "Nomad Air Cannon",
        "damage": "0",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "heavy_weapons",
        "clip": 1,
        "description": "Exotic Shotgun (Shoulder Arms). 1 shot. Coats targets in liquid (paint/water/acid). Acid: -1 SP to coated targets. Poison/Biotoxin: 3 vials per shot, Resist Check."
    },
    {
        "name": "Pursuit Security Inc. TearJerker",
        "damage": "0",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "heavy_weapons",
        "clip": 3,
        "description": "Excellent Quality Exotic Grenade Launcher. Smoke or Teargas ammunition only."
    },
    {
        "name": "SlamDance Ballistic Harpoon",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 1000,
        "category": "melee",
        "description": "Exotic Very Heavy Melee. Can be fired: Heavy Weapons, Bow/Crossbow Range, ignores half armor. Reload with Action."
    },
    {
        "name": "Sternmeyer M-02 Heavy Rifle",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 80,
        "description": "Exotic Assault Rifle. No Autofire/Suppressive Fire. Heavy Weapons Skill. Unique tround ammo: 500eb per 80 AP drum."
    },
    {
        "name": "Towa Pocket Launcher",
        "damage": "8d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "heavy_weapons",
        "clip": 1,
        "description": "Poor Quality Exotic Rocket Launcher. Smartgun Link, unique ammo. Collapsible; concealable when unloaded."
    },
    {
        "name": "UrbanTech Burst Flamethrower",
        "damage": "3d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 1000,
        "category": "heavy_weapons",
        "clip": 4,
        "description": "Exotic Shotgun. Heavy Weapons. Incendiary Shells only. 4 HP/turn until Action to put out. Burst: drain clip for incendiary grenade (Grenade Launcher Range). User catches fire."
    },
    # Interface RED Vol 5: Solo of Fortune 2045
    {
        "name": "Arasaka Neo Rapid Assault 16",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 8,
        "attachment_slots": 0,
        "description": "Excellent Shotgun. Autofire (Machine Pistol 4)."
    },
    {
        "name": "Arasaka Takanami SMG",
        "damage": "3d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "handgun",
        "clip": 40,
        "attachment_slots": 0,
        "description": "Excellent Heavy SMG. Autofire (SMG 4)."
    },
    {
        "name": "MetaCorp Chaingun Victoria",
        "damage": "5d6",
        "rof": "5",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 5000,
        "category": "heavy_weapons",
        "clip": 200,
        "attachment_slots": 0,
        "description": "Excellent Machine Gun. Autofire (Machine Gun 5)."
    },
    {
        "name": "Midnight Arms Dawnmaker AMR",
        "damage": "6d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 5000,
        "category": "shoulder_arms",
        "clip": 5,
        "attachment_slots": 1,
        "description": "Anti-Materiel Rifle. Sniper Rifle."
    },
    {
        "name": "Midnight Assault HB",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 30,
        "attachment_slots": 1,
        "description": "Exotic Assault Rifle."
    },
    {
        "name": "Militech MK.27 LMG",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 1000,
        "category": "heavy_weapons",
        "clip": 100,
        "attachment_slots": 0,
        "description": "Exotic Machine Gun. Autofire (4)."
    },
    {
        "name": "Militech Mountain Goat Rifle",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 5,
        "attachment_slots": 1,
        "description": "Sniper Rifle. Portable."
    },
    {
        "name": "Techtronika Russia BMG-500",
        "damage": "6d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 4,
        "value": 10000,
        "category": "heavy_weapons",
        "clip": 10,
        "attachment_slots": 0,
        "description": "Exotic Heavy Sniper. .50 BMG."
    },
    {
        "name": "Tsunami Arms Helix (Citrus Edition)",
        "damage": "3d6",
        "rof": "4",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "handgun",
        "clip": 25,
        "attachment_slots": 0,
        "description": "Exotic Heavy SMG. Autofire (4)."
    },
    {
        "name": "Scatter Ratter",
        "damage": "4d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "handgun",
        "clip": 20,
        "attachment_slots": 0,
        "description": "Exotic Heavy SMG. Autofire (Machine Pistol 4)."
    },
    {
        "name": "Tsunami Arms Deathwind Railgun",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 4,
        "value": 12000,
        "category": "heavy_weapons",
        "clip": 1,
        "attachment_slots": 0,
        "description": "Exotic Railgun. Ignores armor below SP12. Single shot."
    },
    {
        "name": "Highland Defense Stickybomb Launcher",
        "damage": "8d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 2000,
        "category": "heavy_weapons",
        "clip": 4,
        "attachment_slots": 0,
        "description": "Exotic Grenade Launcher. Fires Mini C9 sticky charges."
    },
    # Danger Gal Dossier
    {
        "name": "Sanroo Hello Cutie MicroCutie",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 10,
        "description": "Excellent Quality Exotic Medium Pistol. Hypurrburst: Action to toggle; drains mag for 4d6 shot (min 4 rounds). No Aimed Shots. Purrs audibly."
    },
]

# Solo of Fortune 2045 weapon attachments (DV17 Weaponstech to install)
weapon_attachments = [
    {
        "name": "Ammunition Compatibility Internals",
        "value": 100,
        "description": "Internal modification allowing non-flamethrower ranged weapons to load any non-Basic Ammunition type.",
        "eligible_categories": ["handgun", "shoulder_arms", "archery", "heavy_weapons"],
        "requires_slot": False,
        "install_dv": 17,
        "effect_description": "Weapon can load any non-Basic Ammunition type.",
    },
    {
        "name": "Reinforced String",
        "value": 250,
        "description": "Upgrades bow or crossbow draw. +1d6 damage (max 5d6).",
        "eligible_categories": ["archery"],
        "requires_slot": False,
        "install_dv": 17,
        "effect_description": "+1d6 damage, max 5d6.",
    },
    {
        "name": "Sniper Rifle Rechamber",
        "value": 300,
        "description": "Rechamber sniper rifles for increased power. +1d6 damage (max 6d6).",
        "eligible_categories": ["shoulder_arms"],
        "requires_slot": False,
        "install_dv": 17,
        "effect_description": "+1d6 damage, max 6d6. Sniper rifles only.",
    },
    {
        "name": "Compatibility Rail",
        "value": 50,
        "description": "Adds a scope-only attachment slot to exotic ranged weapons.",
        "eligible_categories": ["handgun", "shoulder_arms"],
        "requires_slot": False,
        "slot_type": "scope",
        "install_dv": 17,
        "effect_description": "Adds 1 scope attachment slot.",
    },
    {
        "name": "Range Table Modification",
        "value": 100,
        "description": "Modifies the weapon's range table for its category.",
        "eligible_categories": ["handgun", "shoulder_arms", "archery", "heavy_weapons"],
        "requires_slot": False,
        "install_dv": 17,
        "effect_description": "Changes range table (see Solo of Fortune 2045).",
    },
    {
        "name": "Pistol Autosear",
        "value": 100,
        "description": "Adds autofire to pistols. Autofire (Machine Pistol 3 or 4).",
        "eligible_categories": ["handgun"],
        "requires_slot": False,
        "install_dv": 17,
        "effect_description": "Grants Autofire (Machine Pistol 3 or 4).",
    },
    {
        "name": "Shotgun Automatic Control Group",
        "value": 100,
        "description": "Adds autofire for slugs/shells.",
        "eligible_categories": ["shoulder_arms"],
        "requires_slot": False,
        "install_dv": 17,
        "effect_description": "Autofire for shotgun slugs/shells.",
    },
    {
        "name": "SMG Cyclic Internals",
        "value": 100,
        "description": "Upgrades Autofire (SMG 3) to (SMG 4) or (Machine Pistol 4).",
        "eligible_categories": ["handgun"],
        "requires_slot": False,
        "install_dv": 17,
        "effect_description": "Upgrades SMG autofire rate.",
    },
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
    },
    # Black Chrome fashion and armor
    {
        "name": "Dirk Combat Jacket",
        "sp": 11,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 500,
        "description": "Light Armorjack with Leisurewear appearance. Two clips can be concealed without a Check."
    },
    {
        "name": "Gibson Shock Armor",
        "sp": 7,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 500,
        "description": "Kevlar Body Armor. Action to shock grappler: DV15 Resist Torture/Drugs or grapple ends."
    },
    {
        "name": "Gibson Tactical Smart Armor",
        "sp": 12,
        "ev": 2,
        "locations": "Body, Head",
        "weight": 2,
        "value": 1000,
        "description": "Medium Armorjack with built-in Smart Glasses. Worn on body and head."
    },
    {
        "name": "Fire Brand Bunker Gear",
        "sp": 15,
        "ev": 4,
        "locations": "Body, Head, Arms, Legs",
        "weight": 3,
        "value": 1000,
        "description": "Flak Armor. Immune to fire. Built-in gas mask and 30min oxygen tank."
    },
    {
        "name": "Laser Light Street Jacket",
        "sp": 11,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 500,
        "description": "Light Armorjack with Urban Flash appearance. Counts as 1 Light Tattoo for Style bonus."
    },
    {
        "name": "SkidRow Trench",
        "sp": 13,
        "ev": 4,
        "locations": "Body",
        "weight": 2,
        "value": 100,
        "description": "Flak Body Armor with SP 13 instead of 15."
    },
    {
        "name": "T&C Executive Armor",
        "sp": 11,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 1000,
        "description": "Light Armorjack with Businesswear appearance. Repairs 1 SP per day when no damage taken."
    },
    {
        "name": "Street Viper Riding Suit",
        "sp": 7,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 100,
        "description": "Kevlar Body Armor with 2 built-in Medium Melee Weapons (elbow blades)."
    },
    {
        "name": "MechaMan Motorcycle Helmet",
        "sp": 15,
        "ev": 4,
        "locations": "Head",
        "weight": 1,
        "value": 5000,
        "description": "Flak Head Armor with Smart Glasses (Chyron, Low Light/IR/UV)."
    },
    # Danger Gal Dossier
    {
        "name": "Scavenged Armor",
        "sp": 7,
        "ev": 0,
        "locations": "Head, Body",
        "weight": 1,
        "value": 0,
        "description": "Patchwork armor scavenged from the dead. SP 7 Head and Body. Common in Combat Zones."
    },
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
        "name": "Tent and Camping Equipment",
        "category": "Survival",
        "description": "Tent and camping gear for nomads",
        "weight": 3,
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
    # Black Chrome gear and apps
    {
        "name": "Shower-in-a-Can",
        "category": "Survival",
        "description": "Biotechnica disinfectant and deodorizer. One use per can. Classic Clean or Fresh Pine.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Drink Master 3000",
        "category": "Electronics",
        "description": "Rolling bar unit. Holds 32 fluids, dispenses 3000 drink combinations. 10 beverages before refill (100eb). Can dispense Smash.",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "Hydrosubsidium Universal Aqualung",
        "category": "Survival",
        "description": "Donut-shaped neck device. Breathe water within 10m of surface. Filters oxygen from seawater.",
        "weight": 1,
        "value": 5000
    },
    {
        "name": "Jeeves Executive Garment Bag",
        "category": "Clothing",
        "description": "Repairs damaged Fashion or Armor. Time: Cheap 1hr, Costly 6hr, Premium 1 day, Expensive 1 week, V.Expensive 2 weeks.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Zetatech Porta-Printer",
        "category": "Electronics",
        "description": "Backpack 3D printer. Tech can use Upgrade/Fabrication Expertise anywhere with assembly tools.",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "ChipVault by SecSystems",
        "category": "Electronics",
        "description": "Holds 8 Chipware. EMP shielding. Biometric lock. DV17 Electronics/Security to bypass.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Streetcase by SecSystems",
        "category": "Electronics",
        "description": "Briefcase with Heavy Pistol holster, laptop space, ChipVault, Smoke Grenade. Draw pistol without Action. Floats.",
        "weight": 2,
        "value": 500
    },
    {
        "name": "RapiDeploy Sheath",
        "category": "Tools",
        "description": "Rapid deployment for pistols/light melee. +2 Conceal/Reveal Object. Wrist or back config. Repairable when destroyed.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Everest VentureWare AirWell 50",
        "category": "Survival",
        "description": "Atmospheric water condenser. Produces 17oz per 5 hours. Solar powered.",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Everest VentureWare One Touch Habitat",
        "category": "Survival",
        "description": "Self-deploying tent. Protection from Exposure. Heating/AC. Deploy/undeploy as Action.",
        "weight": 2,
        "value": 100
    },
    {
        "name": "Mr. Biscuit Multi-Food Processor",
        "category": "Survival",
        "description": "Converts organic material to nutritious wafers in 10 min. Feeds 10 without Lifestyle in Outskirts.",
        "weight": 2,
        "value": 500
    },
    {
        "name": "WorldSat Aerial Sphere",
        "category": "Electronics",
        "description": "Helium balloon relay. 1hr setup. CitiNet access within 50 miles. 100m range to control unit.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "KillStrom Banshee Microphone",
        "category": "Music",
        "description": "Wireless headset. +2 Play Instrument (Singing). 48hr runtime per 1hr charge.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "KillStrom Sonic Boom Amp",
        "category": "Music",
        "description": "Action: DV15 Resist Torture/Drugs for everyone within 10m or Damaged Ear 1min. Requires outlet.",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "Laser Light Electric Guitar",
        "category": "Music",
        "description": "Laser fret display. +1 Play Instrument (Guitar). Counts as 1 Light Tattoo for Style.",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "Digital Gladiator App",
        "category": "Electronics",
        "description": "Segotari. Head-to-head virtual combat. Loser's Agent destroyed. Rank 4 Solo Gladiators. 20eb.",
        "weight": 0,
        "value": 20
    },
    {
        "name": "4Tify App",
        "category": "Electronics",
        "description": "SecSystems. Scan cover 5min for +1d6 next damage vs it. Requires CitiNet. 100eb.",
        "weight": 0,
        "value": 100
    },
    {
        "name": "NCPD Crime Database App",
        "category": "Electronics",
        "description": "Upload photos for crime records check. 1hr for results. Night City CitiNet only. 500eb.",
        "weight": 0,
        "value": 500
    },
    {
        "name": "Ziggurat City Database App",
        "category": "Electronics",
        "description": "+1 Local Expert for one city. One city per purchase. 100eb.",
        "weight": 0,
        "value": 100
    },
    {
        "name": "Trauma Team MedScan App",
        "category": "Electronics",
        "description": "Connects to remote specialist. 100eb: +1 First Aid/Paramedic 1hr. 500eb: +1 Medical Tech/Surgery 4hr. 20eb.",
        "weight": 0,
        "value": 20
    },
    # Edgerunners Mission Kit gear (2070s)
    {
        "name": "Immunoblockers",
        "category": "Drugs",
        "description": "Primary: Restore 2d6 Humanity for 1 month (cannot exceed therapy max). Secondary (DV21): Lose gain, -2 Checks 60sec, 4d6 HL if no 2 doses. 100eb/dose.",
        "weight": 0.1,
        "value": 100
    },
    {
        "name": "Power Rebuild",
        "category": "Weapon Attachments",
        "description": "2 attachment slots. Transforms weapon to Power: +5 Critical Injury bonus damage, ricochet shots at -4.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Smart Rebuild",
        "category": "Weapon Attachments",
        "description": "2 attachment slots. Transforms to Smart Weapon. +1 Attack. Improved Smart Ammo compatible. Requires Interface Plug or Subdermal Grip.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Tech Rebuild",
        "category": "Weapon Attachments",
        "description": "2 attachment slots. Transforms to Tech Weapon. Charge (Move Action): fire through Thin Cover, half SP. No GL/RL.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Improved Smart Ammunition (10)",
        "category": "Ammunition",
        "description": "Smart Weapons only. Ignore darkness/smoke/fog penalties. Miss by 5 or less: retry with 14+1d10 vs same DV. Bullets, Slugs, Shells, Arrows.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Improved Smart Grenade/Rocket",
        "category": "Ammunition",
        "description": "Smart Weapons only. One grenade or rocket. Same benefits as Improved Smart Ammo.",
        "weight": 0.5,
        "value": 500
    },
    # Interface RED Vol 2: Night City Weather gear
    {
        "name": "Cold-Weather Jacket Lining",
        "category": "Clothing",
        "description": "Insulated lining for existing jacket. Protects against Exposure (extreme cold).",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Hot-Weather Jacket Lining",
        "category": "Clothing",
        "description": "Wicking, vented lining for jacket. Protects against Exposure (extreme heat). Lowers Heat Wave armor penalty by 1.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Militech Tactical Umbrella",
        "category": "Tools",
        "description": "Protects vs Acid/Blood Rain. Excellent Quality Exotic Heavy Melee + Poor Quality Exotic Heavy Pistol (2 rounds). Armed Executive line.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Umbrella",
        "category": "Tools",
        "description": "Negates Acid Rain armor ablation. +2 Resist Torture/Drugs vs Blood Rain. Hand holding umbrella cannot hold anything else.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Waterproof Jacket Lining",
        "category": "Clothing",
        "description": "Treated lining for jacket. Negates Acid Rain ablation, +2 Resist Torture/Drugs vs Blood Rain. Not for submersion.",
        "weight": 0.5,
        "value": 500
    },
    # Interface RED Vol 3: Spinning Your Wheels
    {
        "name": "Inline Skates",
        "category": "Sports",
        "description": "Roller skates, four wheels in a line. +4 m/yds when using Run Action. Action to put on/off. Cyberleg options inaccessible while worn.",
        "weight": 1,
        "value": 50
    },
    {
        "name": "Skateboard",
        "category": "Sports",
        "description": "Deck, trucks, four wheels. +4 m/yds Run on level/downward ground. Athletics for tricks.",
        "weight": 1,
        "value": 50
    },
    # Interface RED Vol 4: Hornet's Pharmacy
    {
        "name": "Berserker",
        "category": "Drugs",
        "description": "Combat drug. 10 min: no Bonus Damage from Criticals; Seriously/Mortally wounded penalties halved; Facedown penalties halved. Secondary (DV17): 2 HL, addicted (Base Death Save +1).",
        "weight": 0.1,
        "value": 100
    },
    {
        "name": "Prime Time",
        "category": "Drugs",
        "description": "Combat drug. 4 hrs: 4d6 HL (returned after); COOL/WILL +2 (WILL doesn't increase HP). Secondary (DV17): 1 HL, addicted (COOL -2 unless on drug).",
        "weight": 0.1,
        "value": 50
    },
    {
        "name": "Sixgun",
        "category": "Drugs",
        "description": "Netrunner drug. 4 hrs: MOVE/REF -2; +2 Speed Jacked In; Unsafe Jack Out = Safe; 1 HL per extra NET Action/turn. Secondary (DV17): addicted (-2 Speed unless on drug).",
        "weight": 0.1,
        "value": 100
    },
    {
        "name": "Timewarp",
        "category": "Drugs",
        "description": "Stimulant. 1 min: +3 Initiative (or +3 if already in queue). Secondary (DV17): addicted (-2 Initiative unless on drug).",
        "weight": 0.1,
        "value": 100
    },
    {
        "name": "Delaying Compound",
        "category": "Tools",
        "description": "Mix with Poison/Biotoxin: delay effects 1 min or 1 hr after target takes it.",
        "weight": 0.1,
        "value": 50
    },
    {
        "name": "Distilling Compound",
        "category": "Tools",
        "description": "Mix with Poison/Biotoxin: +2 DV to Resist Torture/Drugs.",
        "weight": 0.1,
        "value": 100
    },
    {
        "name": "Osmosis Compound",
        "category": "Tools",
        "description": "Mix with Poison/Biotoxin: enters through skin. Place on surface up to 2 sq ft. Lasts 1 hr. DV17 Perception to notice.",
        "weight": 0.1,
        "value": 50
    },
    # Interface RED Vol 5: Solo of Fortune 2045 - Explosives
    {
        "name": "C9 Charge",
        "category": "Explosives",
        "description": "Military-grade explosive. Solo of Fortune 2045.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "C9 Kill Switch",
        "category": "Explosives",
        "description": "C9 Charge with remote detonation. Solo of Fortune 2045.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Mini C9 Charge",
        "category": "Explosives",
        "description": "Compact C9 for Stickybomb Launcher. Solo of Fortune 2045.",
        "weight": 0.2,
        "value": 500
    },
    # Danger Gal Dossier
    {
        "name": "Molotov Cocktail",
        "category": "Explosives",
        "description": "Incendiary grenade 5d6. If carrier takes penetrating damage, 50% each Molotov destroyed; destroyed one sets carrier Deadly on Fire and destroys all others carried.",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "The Observer",
        "category": "Electronics",
        "description": "Flying quadcopter drone. 6 MOVE, 15 HP. Links to Agent. Standby/Auto/Direct Control. Records 1hr. Observation Camera. DV17 Electronics/Security to counter.",
        "weight": 0.5,
        "value": 1000
    },
]

# Extend with Cyberpunk RED fashion items (core rulebook)
from world.fashion_data import build_fashion_gear_list
gears.extend(build_fashion_gear_list())

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
        "name": "SGI Technologies Warlock's Book",
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

    allowed_keys = {
        'damage', 'rof', 'hands', 'concealable', 'weight', 'value',
        'category', 'clip', 'description', 'attachment_slots', 'range_dvs'
    }
    for weapon_data in weapons:
        if not all(weapon_data.get(k) is not None for k in ('name', 'damage', 'rof', 'hands')):
            logger.warn(f"Incomplete weapon data found: {weapon_data}")
            continue

        defaults = {k: v for k, v in weapon_data.items() if k in allowed_keys}
        weapon, created = Weapon.objects.get_or_create(
            name=weapon_data['name'],
            defaults=defaults
        )
        if created:
            logger.info(f"Created weapon: {weapon.name}")
        else:
            updated = False
            for key in allowed_keys:
                if key in weapon_data and getattr(weapon, key, None) != weapon_data[key]:
                    setattr(weapon, key, weapon_data[key])
                    updated = True
            if updated:
                weapon.save()
                logger.info(f"Updated weapon: {weapon.name}")


@transaction.atomic
def initialize_weapon_attachments():
    from world.inventory.models import WeaponAttachment

    for data in weapon_attachments:
        att, created = WeaponAttachment.objects.update_or_create(
            name=data['name'],
            defaults={
                'value': data.get('value', 0),
                'description': data.get('description', ''),
                'eligible_categories': data.get('eligible_categories', []),
                'requires_slot': data.get('requires_slot', False),
                'slot_type': data.get('slot_type', ''),
                'install_dv': data.get('install_dv', 17),
                'install_skill': data.get('install_skill', 'Weaponstech'),
                'effect_description': data.get('effect_description', ''),
            }
        )
        if created:
            logger.info(f"Created weapon attachment: {att.name}")

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
        print(f"Initialized {len(cyberdecks)} cyberdeck types.")


@transaction.atomic
def initialize_vehicles():
    from world.inventory.models import Vehicle

    for vehicle_data in vehicles:
        if not all(k in vehicle_data and vehicle_data[k] is not None for k in ('name', 'value')):
            logger.warn(f"Incomplete vehicle data found: {vehicle_data}")
            continue

        vehicle, created = Vehicle.objects.get_or_create(
            name=vehicle_data['name'],
            defaults={
                'description': vehicle_data.get('description', ''),
                'category': vehicle_data.get('category', 'land'),
                'sdp': vehicle_data.get('sdp', 35),
                'seats': vehicle_data.get('seats', 2),
                'speed_combat': vehicle_data.get('speed_combat', 20),
                'speed_narrative': vehicle_data.get('speed_narrative', ''),
                'value': vehicle_data['value'],
            }
        )
        if created:
            logger.info(f"Created vehicle: {vehicle.name}")
        else:
            updated = False
            for key, value in vehicle_data.items():
                if key == 'value' and hasattr(vehicle, 'value'):
                    if vehicle.value != value:
                        vehicle.value = value
                        updated = True
                elif hasattr(vehicle, key) and getattr(vehicle, key) != value:
                    setattr(vehicle, key, value)
                    updated = True
            if updated:
                vehicle.save()
                logger.info(f"Updated vehicle: {vehicle.name}")
    print(f"Initialized {len(vehicles)} vehicle types.")


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
    existing_names = set(Weapon.objects.values_list("name", flat=True))
    created = 0
    allowed_keys = {
        "damage", "rof", "hands", "concealable", "weight", "value",
        "category", "clip", "description", "attachment_slots", "range_dvs",
    }
    for weapon_data in weapons:
        if weapon_data.get("name") in existing_names:
            continue
        defaults = {k: v for k, v in weapon_data.items() if k in allowed_keys and k != "name"}
        Weapon.objects.get_or_create(name=weapon_data["name"], defaults=defaults)
        created += 1
        existing_names.add(weapon_data["name"])
    print(f"Populated {len(weapons)} weapons ({created} new).")


def populate_armor():
    existing_names = set(Armor.objects.values_list("name", flat=True))
    created = 0
    for armor_data in armors:
        if armor_data.get("name") in existing_names:
            continue
        Armor.objects.get_or_create(
            name=armor_data["name"],
            defaults={
                "sp": armor_data.get("sp", 0),
                "ev": armor_data.get("ev", 0),
                "locations": armor_data.get("locations", ""),
                "description": armor_data.get("description", ""),
                "weight": armor_data.get("weight", 0),
                "value": armor_data.get("value", 0),
            },
        )
        created += 1
        existing_names.add(armor_data["name"])
    print(f"Populated {len(armors)} armor pieces ({created} new).")


def populate_gear():
    existing_names = set(Gear.objects.values_list("name", flat=True))
    created = 0
    for gear_data in gears:
        if gear_data.get("name") in existing_names:
            continue
        Gear.objects.get_or_create(
            name=gear_data["name"],
            defaults={
                "category": gear_data.get("category", ""),
                "description": gear_data.get("description", ""),
                "weight": gear_data.get("weight", 0),
                "value": gear_data.get("value", 0),
            },
        )
        created += 1
        existing_names.add(gear_data["name"])
    print(f"Populated {len(gears)} gear items ({created} new).")


def populate_cyberdecks():
    existing_names = set(Cyberdeck.objects.values_list("name", flat=True))
    created = 0
    for cyberdeck_data in cyberdecks:
        if cyberdeck_data.get("name") in existing_names:
            continue
        Cyberdeck.objects.get_or_create(
            name=cyberdeck_data["name"],
            defaults={
                "description": cyberdeck_data.get("description", ""),
                "hardware_slots": cyberdeck_data.get("hardware_slots", 0),
                "program_slots": cyberdeck_data.get("program_slots", 0),
                "any_slots": cyberdeck_data.get("any_slots", 0),
                "value": cyberdeck_data.get("value", 0),
            },
        )
        created += 1
        existing_names.add(cyberdeck_data["name"])
    print(f"Populated {len(cyberdecks)} cyberdecks ({created} new).")


def populate_vehicles():
    existing_names = set(Vehicle.objects.values_list("name", flat=True))
    created = 0
    for vehicle_data in vehicles:
        if vehicle_data.get("name") in existing_names:
            continue
        Vehicle.objects.get_or_create(
            name=vehicle_data["name"],
            defaults={
                "description": vehicle_data.get("description", ""),
                "category": vehicle_data.get("category", "land"),
                "sdp": vehicle_data.get("sdp", 35),
                "seats": vehicle_data.get("seats", 2),
                "speed_combat": vehicle_data.get("speed_combat", 20),
                "speed_narrative": vehicle_data.get("speed_narrative", ""),
                "value": vehicle_data["value"],
            },
        )
        created += 1
        existing_names.add(vehicle_data["name"])
    print(f"Populated {len(vehicles)} vehicles ({created} new).")


def populate_ammunition():
    from world.inventory.models import AmmoType as InventoryAmmoType

    existing = set(
        Ammunition.objects.values_list("name", "ammo_type").order_by()
    )
    created = 0
    for ammo_data in ammunition:
        ammo_type_val = getattr(InventoryAmmoType, ammo_data["ammo_type"], ammo_data["ammo_type"])
        key = (ammo_data["name"], ammo_type_val)
        if key in existing:
            continue
        Ammunition.objects.get_or_create(
            name=ammo_data["name"],
            ammo_type=ammo_type_val,
            defaults={
                "weapon_type": ammo_data.get("weapon_type", "Generic"),
                "damage_modifier": ammo_data.get("damage_modifier", 0),
                "armor_piercing": ammo_data.get("armor_piercing", 0),
                "description": ammo_data.get("description", "Standard ammunition"),
                "cost": ammo_data.get("cost", 10),
                "quantity": ammo_data.get("quantity", 0),
            },
        )
        created += 1
        existing.add(key)
    print(f"Populated {len(ammunition)} ammunition types ({created} new).")

def populate_all_equipment():
    populate_weapons()
    populate_armor()
    populate_gear()
    populate_cyberware()
    populate_ammunition()
    populate_cyberdecks()
    populate_vehicles()
    print("All equipment populated successfully.")
