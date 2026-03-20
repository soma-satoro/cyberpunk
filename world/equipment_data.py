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
        # Interface RED Vol 4: 12 Days of Gearmas
    {
        "name": "Zonda Metrocar",
        "description": "Classic 2020s city car. Yang's Wheels under Zonda license. Compact Groundcar, 2 seats. SDP 25. Incompatible with Heavy Chassis, Seating Upgrade. AV Engine = can fly, speeds unchanged. Cannot Tech-Upgrade speed. Nomad Access: 1.",
        "category": "land",
        "sdp": 25,
        "seats": 2,
        "speed_combat": 10,
        "speed_narrative": "30 MPH / 48 KPH",
        "value": 1000,
    },
# Interface RED Vol 3: Spinning Your Wheels (Danger Gal Dossier)
    {
        "name": "Bicycle",
        "description": "Two-wheeled, muscle-powered. SDP 15, 1 seat, 100eb. Speed by BODY: BODY<4: 8 MOVE/12 MPH; 4-7: 10 MOVE/20 MPH; 8+: 15 MOVE/30 MPH. BODY 11+ too heavy. Athletics (not Drive). Basic Tech (not LVT). No Interface Plugs. Rider uses own Initiative. Crash/ram: 3d6 (not 6d6), rider Prone. No Nomad Moto upgrades. 48hr charge.",
        "category": "land",
        "sdp": 15,
        "seats": 1,
        "speed_combat": 15,
        "speed_narrative": "BODY Dependent",
        "value": 100,
    },
    # Danger Gal Dossier - Cyberchairs
    {
        "name": "Mercurius Cyberchair",
        "description": "Rocklin Augmentics motorized wheelchair. 1 seat, Interface Plug or hand control. MOVE 5 (minus Armor Penalty). Stairs no penalty. Attacks target pilot. Pilot can't be removed while conscious. Critical Injury to MOVE lowers chair MOVE. EMP-proof. Night City Nukes regulation model.",
        "category": "land",
        "sdp": 15,
        "seats": 1,
        "speed_combat": 5,
        "speed_narrative": "5 MOVE",
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
        "name": "Basic Arrow",
        "ammo_type": "BASIC",
        "weapon_type": "Archery",
        "damage_modifier": 0,
        "armor_piercing": 0,
        "description": "Standard arrows or bolts for bows and crossbows.",
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
    {"name": "Arrowhypo Ammunition", "ammo_type": "ARROWHYPO", "weapon_type": "Archery", "damage_modifier": 0, "armor_piercing": 0, "description": "Reinforced airhypo on arrow. Load 1 dose Street Drug. Hit = inject drug, no damage. Recoverable like Basic Arrow. 1 unit.", "cost": 100},
    {"name": "Airburst Ammunition", "ammo_type": "AIRBURST", "weapon_type": "Heavy Weapons", "damage_modifier": 0, "armor_piercing": 0, "description": "Gas-dispersal munition for Grenades/Rockets. Load 3 doses of single Street Drug. Hit = gas dose. Nasal filters/gas masks prevent. 1 unit.", "cost": 125},
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
        "clip": 12,
        "weapon_type": "medium pistol",
        "quality": "standard"
    },
    {
        "name": "Heavy Pistol",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 100,
        "category": "handgun",
        "clip": 8,
        "weapon_type": "heavy pistol",
        "quality": "standard"
    },
    {
        "name": "Very Heavy Pistol",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 100,
        "category": "handgun",
        "clip": 8,
        "weapon_type": "very heavy pistol",
        "quality": "standard"
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
        "clip": 30,
        "weapon_type": "SMG",
        "quality": "standard"
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
        "clip": 40,
        "weapon_type": "heavy SMG",
        "quality": "standard"
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
        "clip": 4,
        "weapon_type": "shotgun",
        "quality": "standard"
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
        "clip": 25,
        "weapon_type": "assault rifle",
        "quality": "standard"
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
        "clip": 4,
        "weapon_type": "sniper rifle",
        "quality": "standard"
    },
    {
        "name": "Bow",
        "damage": "4d6",
        "rof": "2",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "archery",
        "weapon_type": "bow",
        "quality": "standard"
    },
    {
        "name": "Crossbow",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "archery",
        "weapon_type": "crossbow",
        "quality": "standard"
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
        "clip": 2,
        "weapon_type": "grenade launcher",
        "quality": "standard"
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
        "clip": 1,
        "weapon_type": "rocket launcher",
        "quality": "standard"
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
        "clip": 4,
        "weapon_type": "flamethrower",
        "quality": "standard"
    },
    {
        "name": "Light Melee Weapon",
        "damage": "1d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 50,
        "category": "melee",
        "weapon_type": "light melee",
        "quality": "standard"
    },
    {
        "name": "Medium Melee Weapon",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 50,
        "category": "melee",
        "weapon_type": "medium melee",
        "quality": "standard"
    },
    {
        "name": "Heavy Melee Weapon",
        "damage": "3d6",
        "rof": "2",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "melee",
        "weapon_type": "heavy melee",
        "quality": "standard"
    },
    {
        "name": "Very Heavy Melee Weapon",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 100,
        "category": "melee",
        "weapon_type": "very heavy melee",
        "quality": "standard"
    },
    {
        "name": "Light Melee Weapon",
        "damage": "1d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 50,
        "category": "melee",
        "weapon_type": "light melee",
        "quality": "standard"
    },
    {
        "name": "Medium Melee Weapon",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 50,
        "category": "melee",
        "weapon_type": "medium melee",
        "quality": "standard"
    },
    {
        "name": "Heavy Melee Weapon",
        "damage": "3d6",
        "rof": "2",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "melee",
        "weapon_type": "heavy melee",
        "quality": "standard"
    },
    {
        "name": "Very Heavy Melee Weapon",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 100,
        "category": "melee",
        "weapon_type": "very heavy melee",
        "quality": "standard"
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
        "weapon_type": "heavy pistol",
        "quality": "excellent",
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
        "weapon_type": "SMG",
        "quality": "excellent",
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
        "weapon_type": "heavy pistol",
        "quality": "excellent",
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
        "weapon_type": "very heavy pistol",
        "quality": "standard",
        "description": "Nova Arms Classic Guns of Film. Chrome .44 magnum. 6 shots. Incompatible with magazine attachments. Barrel: 4\", 6.5\", or 8.375\"."
    },
    {
        "name": "Sanroo Hello Cutie Ultra-K8",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 5000,
        "category": "handgun",
        "clip": 30,
        "weapon_type": "very heavy pistol",
        "quality": "excellent",
        "description": "Excellent Quality Exotic Very Heavy Pistol. Action: reconfigure to Excellent Heavy SMG. Same 30-round mag. 3+ Asia Pop Fashion worn openly: +2 Wardrobe and Style. 2 attachment slots, compatible with VHP and Heavy SMG attachments except magazine."
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
        "weapon_type": "very heavy pistol",
        "quality": "standard",
        "description": "Exotic Very Heavy Pistol. Non-Basic Ammunition. +2 Wardrobe and Style when worn openly."
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
        "clip": 20,
        "weapon_type": "assault rifle",
        "quality": "poor",
        "description": "Poor Quality Exotic Combination Assault Rifle and Grenade Launcher. Rifle: 20 rounds, GL: 2 grenades. Separate magazines, reload each with Action. Jam in one mode disables both until Action to fix. GL loads Non-Basic grenades."
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
        "weapon_type": "assault rifle",
        "quality": "standard",
        "description": "Exotic Assault Rifle. Non-Basic Ammunition. +2 Wardrobe and Style when worn openly."
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
        "attachment_slots": 1,
        "weapon_type": "very heavy pistol",
        "quality": "standard",
        "description": "Centurion Essentials. Exotic Combination Very Heavy Pistol (8 shots) and Poor Quality Shotgun (2 shots). Separate magazines. BODY 10+ or two hands or weapon flies 6m/yds away. 1 attachment slot: scope compatible with VHP and Shotgun only. Cannot conceal or popup."
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
        "weapon_type": "heavy pistol",
        "quality": "poor",
        "description": "Poor Quality Exotic Heavy Pistol. No trigger. Permanent Smartgun Link, Subdermal Grip required. Lethal: 8-shot mag. Less-than-lethal: 8-shot battery, no Critical Injury, no armor ablation, reduces to 1 HP Unconscious if would kill."
    },
    {
        "name": "Kendachi Mono-Katana",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "melee",
        "weapon_type": "very heavy melee",
        "quality": "standard",
        "description": "Two-Handed Exotic Very Heavy Melee Weapon (sword). With correct biometric key, damage ignores armor below SP7. Without key, weapon won't vibrate—just a standard Two-Handed Exotic Very Heavy Melee Weapon."
    },
    {
        "name": "Zhirafa Rhinocefist",
        "damage": "4d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "melee",
        "weapon_type": "very heavy melee",
        "quality": "excellent",
        "description": "Exoskeleton arm with Interface Plugs. Brawling: 4d6 always. Action: convert to Excellent Quality Exotic Very Heavy Melee Weapon (that hand can't hold anything). Put on/take off: Action. DV13 Weaponstech or Land Vehicle Tech to repair (6 hrs)."
    },
    # Black Chrome - additional melee weapons
    {
        "name": "Arasaka Weeping Reaver Katana",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 5000,
        "category": "melee",
        "weapon_type": "very heavy melee",
        "quality": "excellent",
        "description": "Arasaka's Weeping Reaver is a high-density, cryo-quenched, diamond steel katana capable of coating itself with substances stored in the grip. Pressure points on the palm ornament allow the wielder to select coatings from three separate chambers to coat the blade. Arasaka also sells a line of fluids of the exact viscosity required by the blade's mechanism in pressurized, branded cylinders. Currently available are Arasaka Fire, Arasaka Acid, and Arasaka Wound Salt but others are in development. The blade's pommel allows for easy reloading of the three chambers inside the grip. The Arasaka Weeping Reaver is an Excellent Quality Two-Handed Exotic Very Heavy Melee Weapon. Once per minute (20 Combat Rounds), as an Action, the user can direct the Weeping Reaver to coat itself with one or more fluids loaded into its handle. Multiple applications of the same fluid do nothing, but up to three different fluids can be combined at once as the user desires. Each fluid remains effective for 1 minute after application. Each fluid canister contains a single application and only fluids designed for use with the Weeping Reaver have any effect. The Weeping Reaver contains three chambers for storing fluid canisters. Reloading any combination of these chambers takes an Action. Each canister costs 100eb (Premium). When coated with Arasaka Fire, whenever a user deals damage to a target through their armor, they ignite the target. Until the target spends an Action to put themselves out, they take 2 damage to their HP whenever they end their Turn. Multiple instances of this effect cannot stack. When coated with Arasaka Acid, the Weeping Reaver ablates armor by 2 instead of 1 whenever it would ablate armor. When coated with Arasaka Wound Salt, whenever the weapon causes the Foreign Object Critical Injury, the victim rolls again on the Critical Injury table until they roll a Critical Injury that isn't Foreign Object. The victim then suffers that Critical Injury as well. This second injury deals no Bonus Damage."
    },
    {
        "name": "Solo Wolf and Bot Mono-Katana",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 100,
        "category": "melee",
        "weapon_type": "very heavy melee",
        "quality": "poor",
        "description": "Poor Quality Two-Handed Exotic Very Heavy Melee Weapon (sword). Replica of Kendachi Mono-Katana. DV13 Perception or Weaponstech to spot fake. No biometric/armor-bypass."
    },
    {
        "name": "Kendachi Mono-Wakizashi",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 1000,
        "category": "melee",
        "weapon_type": "heavy melee",
        "quality": "standard",
        "description": "One-Handed Exotic Heavy Melee Weapon (sword). With biometric key, damage ignores armor below SP7. Without key: standard One-Handed Exotic Heavy Melee Weapon."
    },
    {
        "name": "White Hornet Tanto",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "melee",
        "weapon_type": "medium melee",
        "quality": "standard",
        "description": "One-Handed Exotic Medium Melee Weapon (knife). Concealable. Solar-cell shock. If damage would reduce target below 1 HP, wielder may leave them Unconscious at 1 HP."
    },
    {
        "name": "Rostovic Kleaver",
        "damage": "4d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 1000,
        "category": "melee",
        "weapon_type": "very heavy melee",
        "quality": "standard",
        "description": "Two-Handed Exotic Very Heavy Melee Weapon (axe). BODY 11+ to wield. Action + 3x 50eb battery packs to charge (1 min heat). Charged: 5d6, ignores armor below SP11, targets Mildly On Fire. Charged 5 min. Uncharged: Action to reload batteries."
    },
    {
        "name": "Kendachi Mono-Guard",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "melee",
        "weapon_type": "heavy melee",
        "quality": "standard",
        "description": "One-Handed Exotic Heavy Melee Weapon (monowhip). Concealable. Foreign Object Critical: victim rerolls until non-Foreign Object, suffers that instead."
    },
    {
        "name": "Faisal's Magna Knuckles",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 1000,
        "category": "melee",
        "weapon_type": "medium melee",
        "quality": "standard",
        "description": "One-Handed Exotic Medium Melee Weapon. Hit twice in one Turn: target DV15 Cybertech or GM picks 2 cyberware inoperable 1 min. 8 charges, 50eb battery, 1hr recharge. No charges: still functions as Medium Melee."
    },
    {
        "name": "Pursuit Security Bouncer",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 500,
        "category": "melee",
        "weapon_type": "medium melee",
        "quality": "standard",
        "description": "Exotic Combination Stun Baton and Microwaver. 8-shot 50eb battery. Put on/take off: Action. Cannot conceal. Options in that hand inaccessible."
    },
    {
        "name": "SlamDance FangFist",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 1000,
        "category": "melee",
        "weapon_type": "medium melee",
        "quality": "excellent",
        "description": "Excellent Quality One-Handed Exotic Medium Melee Weapon (glove). Turn drawn: Excellent Very Heavy Melee (4d6), ROF 1. Blade extended: hand unusable. Retract/equip: Action. Concealable when retracted (Conceal/Reveal Object)."
    },
    {
        "name": "SlamDance Tasmanskiy Klo",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 2,
        "value": 5000,
        "category": "melee",
        "weapon_type": "very heavy melee",
        "quality": "excellent",
        "description": "Excellent Quality Exotic Very Heavy Melee Weapon (claw). In Battleglove, draw/stow no Action. +2 Interrogation when threatening. Battleglove has 1 Option Slot. Options in that arm inaccessible."
    },
    {
        "name": "Ranger Combat Boomerang",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 1000,
        "category": "melee",
        "weapon_type": "heavy melee",
        "quality": "standard",
        "description": "One-Handed Exotic Heavy Melee Weapon. No melee attacks. Thrown: halves SP. Throwing = half of 2 ROF. With Targeting Scope: returns start of next Turn. Catch free if hand free."
    },
    {
        "name": "Utility Tomahawk",
        "damage": "3d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 100,
        "category": "melee",
        "weapon_type": "heavy melee",
        "quality": "standard",
        "description": "One-Handed Exotic Heavy Melee Weapon (axe). Ice tool, crowbar, throwing axe, machete. Thrown: halves SP."
    },
    {
        "name": "Kendachi Mono-Star",
        "damage": "2d6",
        "rof": "2",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 500,
        "category": "melee",
        "weapon_type": "medium melee",
        "quality": "standard",
        "description": "One-Handed Exotic Medium Melee Weapon (shuriken). Concealable. Thrown: halves SP, counts as half of 2 ROF. Foreign Object: victim also rolls until non-Foreign Object, suffers both."
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
        "weapon_type": "SMG",
        "quality": "standard",
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
        "weapon_type": "assault rifle",
        "quality": "standard",
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
        "weapon_type": "heavy SMG",
        "quality": "standard",
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
        "weapon_type": "shotgun",
        "quality": "poor",
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
        "weapon_type": "heavy pistol",
        "quality": "standard",
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
        "weapon_type": "shotgun",
        "quality": "standard",
        "description": "Exotic Shotgun with Smart Rebuild. Improved Smart Shells only. 8 shells per shot. 4d6 to 6m area. 32 rounds. Without 8 shells loaded, will not fire."
    },
    {
        "name": "Militech Crusher (circa 207X)",
        "damage": "3d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 1000,
        "category": "handgun",
        "clip": 12,
        "weapon_type": "very heavy pistol",
        "quality": "standard",
        "description": "Exotic Very Heavy Pistol with Power Rebuild. Shotgun Shell Ammunition only. Power: +5 Critical Bonus, ricochet."
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
        "weapon_type": "heavy pistol",
        "quality": "standard",
        "description": "Exotic Heavy Pistol with Power Rebuild. 21-shot capacity. Power: +5 Critical Bonus, ricochet."
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
        "weapon_type": "heavy pistol",
        "quality": "standard",
        "description": "Exotic Heavy Pistol with Tech Rebuild. 9-shot capacity. Charge: ROF2, 3 rounds/shot, fire through Thin Cover, half SP. Charge persists until end of Turn fired."
    },
    {
        "name": "Rostovic DB-2 Satara Shotgun",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 2,
        "weapon_type": "shotgun",
        "quality": "standard",
        "description": "Exotic Shotgun with Tech Rebuild. 2-shot capacity, one per barrel. Each barrel can load different ammo. Charge: fire through Thin Cover, half SP. Loads Non-Basic Ammunition."
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
        "weapon_type": "very heavy pistol",
        "quality": "standard",
        "description": "Exotic Very Heavy Pistol with Tech Rebuild. 4-shot capacity. Charge without Move Action. Without Muscle & Bone Lace or Cyberarm: Broken Arm Critical Injury."
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
        "weapon_type": "sniper rifle",
        "quality": "excellent",
        "description": "Excellent Quality Exotic Sniper Rifle with Power Rebuild. Loads Non-Basic Ammunition. +1 Attack. Action to work bolt between shots."
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
        "weapon_type": "sniper rifle",
        "quality": "standard",
        "description": "Sniper Rifle with Tech Rebuild. Charged: scope sees through Thin and Thick Cover, fire through both, half SP."
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
        "quality": "excellent",
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
        "quality": "poor",
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
        "quality": "poor",
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
        "weapon_type": "rocket launcher",
        "quality": "standard",
        "description": "Exotic Rocket Launcher. 4 AP Rockets. Fires 2 at once; GM chooses 2 locations within 50 m/yds of target, 10 m/yds apart. DV15 Evasion to dodge (must be able to dodge bullets). Max range 400 m/yds. Cannot Tech-Upgrade to remove GM targeting."
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
        "quality": "poor",
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
        "quality": "excellent",
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
        "category": "shoulder_arms",
        "clip": 1,
        "description": "Exotic Shotgun. 1-shot, Shotgun Shell mode. Coats targets in liquid (paint/water/acid). Acid: -1 SP to coated armor. Poison/Biotoxin: 3 vials per shot, Resist Check. Shoulder Arms Skill."
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
        "weapon_type": "grenade launcher",
        "quality": "excellent",
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
        "quality": "excellent",
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
        "quality": "excellent",
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
        "quality": "excellent",
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
        "value": 1550,
        "category": "shoulder_arms",
        "clip": 25,
        "attachment_slots": 0,
        "weapon_type": "assault rifle",
        "quality": "excellent",
        "description": "Excellent Quality Assault Rifle. Autofire (Assault Rifle 4), Suppressive Fire. Smartgun Link, Sniping Scope. Battle Rifle range table."
    },
    {
        "name": "Techtronika BMG-500",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 4,
        "value": 1000,
        "category": "heavy_weapons",
        "clip": 500,
        "attachment_slots": 0,
        "weapon_type": "assault rifle",
        "quality": "standard",
        "description": "Exotic Assault Rifle. Heavy Weapons Skill. 500-round box magazine. Magnetic feed start. BODY 11+ unless mounted. Action: deploy bipod on surface = mounted until moved."
    },
    {
        "name": "Tsunami Arms Helix (Citrus Edition)",
        "damage": "3d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 5000,
        "category": "heavy_weapons",
        "clip": 40,
        "attachment_slots": 3,
        "weapon_type": "machine gun",
        "quality": "excellent",
        "description": "Excellent Quality Machine Gun. Hex-barreled gatling. Autofire (Machine Pistol 5), Suppressive Fire only. 2 Reload Actions. BODY 11+ unless mounted."
    },
    {
        "name": "Scatter Ratter",
        "damage": "4d6",
        "rof": "2",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 2552,
        "category": "heavy_weapons",
        "clip": 56,
        "attachment_slots": 3,
        "weapon_type": "machine gun",
        "quality": "poor",
        "description": "Poor Quality Machine Gun. Autofire (SMG 5), Suppressive Fire. Cannot Single Shot if Autofired previous Turn; if Single Shot previous Turn, treat as Excellent Quality. BODY 8+ unless mounted."
    },
    {
        "name": "Tsunami Arms Deathwind Railgun",
        "damage": "6d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 4,
        "value": 12000,
        "category": "heavy_weapons",
        "clip": 30,
        "attachment_slots": 1,
        "weapon_type": "sniper rifle",
        "quality": "excellent",
        "description": "Excellent Quality Sniper Rifle. Heavy Weapons, Scout Rifle range. Ignores armor below SP12. No Aimed Shots. Every 3rd shot in 30 sec: Quality drops to Poor until vented (Action). 2 Reload Actions. BODY 14 (12 if Prone). Incompatible with capacity attachments. Smartgun Link non-removable, requires 2x Interface Plugs/Subdermal Grip."
    },
    {
        "name": "Highland Defense Stickybomb Launcher",
        "damage": "6d6",
        "rof": "2",
        "hands": 1,
        "concealable": False,
        "weight": 3,
        "value": 1300,
        "category": "heavy_weapons",
        "clip": 8,
        "attachment_slots": 3,
        "weapon_type": "grenade launcher",
        "quality": "standard",
        "description": "Grenade Launcher. Fires sticky Mini C9 Charges. Hit = charge planted per Mini C9 rules; remote detonate only, 30 sec arm. Moving planted charges does not explode. Incompatible with Ammunition Compatibility Internals, range/capacity attachments."
    },
    # Black Chrome - additional ranged weapons
    {
        "name": "Arasaka Prototype Variable Assault Rifle",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 15000,
        "category": "shoulder_arms",
        "clip": 25,
        "weapon_type": "assault rifle",
        "quality": "excellent",
        "description": "Excellent Quality Exotic Assault Rifle. Railgun mode: switch before Initiative or with Action. Railgun: no Autofire/Aimed Shots, ignores armor below SP7, drains 8-shot 50eb battery + 1 bullet per shot. No battery: fires as standard. 15keb with both conversion parts; -5keb per missing part."
    },
    {
        "name": "Eagletech Survivalist",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 10,
        "weapon_type": "assault rifle",
        "quality": "standard",
        "description": "Exotic Combination Crossbow and Assault Rifle. Rifle: 10 shots, no Autofire, Archery Skill. Crossbow: arrows. Both modes: integrated Sniping Scope, Non-Basic Ammunition."
    },
    {
        "name": "Faisal's Dead or Alive",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 500,
        "category": "shoulder_arms",
        "clip": 4,
        "weapon_type": "shotgun",
        "quality": "poor",
        "description": "Poor Quality Exotic Shotgun with integrated Poor Quality Net Launcher. Net: 2 nets, 1 ROF, Shoulder Arms, Shotgun Slug range, max 25m. Hit: grapple, no Move Action, -2 physical Actions, 15 HP. Escape: DV13 Contortionist (target) or Brawling (anyone). Nets 50eb each."
    },
    {
        "name": "Federated Arms Pepper Shaker",
        "damage": "2d6",
        "rof": "4",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 500,
        "category": "handgun",
        "clip": 30,
        "weapon_type": "SMG",
        "quality": "standard",
        "description": "Exotic SMG. Autofire only, no Aimed Shots or Single Shot. Non-Basic Ammunition. Autofire uses 6 bullets instead of 10."
    },
    {
        "name": "Georgia Arms Matchmaker",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 20,
        "category": "shoulder_arms",
        "clip": 1,
        "weapon_type": "shotgun",
        "quality": "poor",
        "description": "Poor Quality Exotic Shotgun. 1 shot. Plumbing supplies. Non-Basic Ammunition."
    },
    {
        "name": "GunMart Bubba Buster",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 50,
        "category": "shoulder_arms",
        "clip": 4,
        "weapon_type": "shotgun",
        "quality": "poor",
        "description": "Poor Quality Exotic Shotgun. Non-Basic Ammunition. 3 shots in 1 min (20 rounds): barrel warps, weapon destroyed."
    },
    {
        "name": "Overlord Handcannon",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 100,
        "category": "handgun",
        "clip": 8,
        "weapon_type": "heavy pistol",
        "quality": "poor",
        "description": "Poor Quality Exotic Heavy Pistol. 1 ROF (unlike other Heavy Pistols). +1 Facedown when threatening violence unless target knows it's crap."
    },
    {
        "name": "GunMart Engage Rocket Launcher",
        "damage": "8d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 100,
        "category": "heavy_weapons",
        "clip": 1,
        "weapon_type": "rocket launcher",
        "quality": "poor",
        "description": "Poor Quality Exotic Rocket Launcher. Armor Piercing Rockets only. Includes 1 AP Rocket. Critical Failure or removing loaded rocket: detonation, weapon (and sometimes user) destroyed."
    },
    {
        "name": "GunMart Special",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 20,
        "category": "handgun",
        "clip": 1,
        "weapon_type": "heavy pistol",
        "quality": "poor",
        "description": "Poor Quality Exotic Heavy Pistol. Critical Failure when firing: weapon destroyed."
    },
    {
        "name": "GunMart Smart Special",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 100,
        "category": "handgun",
        "clip": 8,
        "weapon_type": "heavy pistol",
        "quality": "poor",
        "description": "Poor Quality Exotic Heavy Pistol. Permanent Smartgun Link (removal destroys both). No Subdermal Grip support. Disarmed while plugged: weapon destroyed. Critical Failure: weapon destroyed."
    },
    {
        "name": "Hades Multipurpose Assault Shotgun",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 5000,
        "category": "shoulder_arms",
        "clip": 16,
        "weapon_type": "shotgun",
        "quality": "standard",
        "description": "Exotic Shotgun. 16 shots. Non-Basic Ammunition. Load mix of up to 5 shotgun ammo types, select per shot via thumb controls."
    },
    {
        "name": "KTech TechHammer",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 1000,
        "category": "heavy_weapons",
        "clip": 4,
        "weapon_type": "shotgun",
        "quality": "standard",
        "description": "Exotic Shotgun or Rocket Launcher. Magazine: 4 Basic Shotgun Slugs/Shells OR 2 Smart Rockets. Shotgun: Shoulder Arms. Rockets: Heavy Weapons, no Targeting Scope needed. Laser targeting for Smart Rockets."
    },
    {
        "name": "Midnight Arms Beast Shotgun",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 40,
        "weapon_type": "shotgun",
        "quality": "standard",
        "description": "Exotic Shotgun. 40 rounds. Non-Basic Ammunition. BODY 10+ or Broken Arm unless mounted. 2 Actions to reload."
    },
    {
        "name": "Militech Perseus",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": True,
        "weight": 1,
        "value": 5000,
        "category": "handgun",
        "clip": 11,
        "weapon_type": "very heavy pistol",
        "quality": "excellent",
        "description": "Excellent Quality Exotic Very Heavy Pistol. 11 shots. If fired previous Round: 2 ROF instead of 1."
    },
    {
        "name": "Nomad Rocker",
        "damage": "4d6",
        "rof": "1",
        "hands": 1,
        "concealable": False,
        "weight": 1,
        "value": 100,
        "category": "handgun",
        "clip": 0,
        "weapon_type": "very heavy pistol",
        "quality": "poor",
        "description": "Poor Quality Exotic Very Heavy Pistol. Fires rocks—ammo free. Repair destroyed: 1 hour, no Check."
    },
    {
        "name": "Pursuit Security Inc Crowd Buster",
        "damage": "5d6",
        "rof": "4",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 5000,
        "category": "shoulder_arms",
        "clip": 25,
        "weapon_type": "assault rifle",
        "quality": "standard",
        "description": "Exotic Assault Rifle with shrieker. Action: single shot, no damage, target DV15 Resist Torture/Drugs or Damaged Ear. User without ear protection: Damaged Ear. Includes Auto Level Dampening Ear Protectors. Shrieker: 8-shot 50eb battery."
    },
    {
        "name": "Rostovic Street Destroyer",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 2,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 3,
        "weapon_type": "shotgun",
        "quality": "poor",
        "description": "Poor Quality Exotic Shotgun. 3 shots. Shotgun Shells only. Action: shove metal into barrels. Next Shotgun Shell: 4d6, clears barrels."
    },
    {
        "name": "Superchrome Javelin",
        "damage": "5d6",
        "rof": "1",
        "hands": 2,
        "concealable": False,
        "weight": 3,
        "value": 1000,
        "category": "shoulder_arms",
        "clip": 4,
        "weapon_type": "sniper rifle",
        "quality": "standard",
        "description": "Exotic Sniper Rifle. Non-Basic Ammunition. +2 Wardrobe and Style when worn openly."
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
        "weapon_type": "medium pistol",
        "quality": "excellent",
        "description": "Excellent Quality Exotic Medium Pistol. Hypurrburst: Action to toggle; drains mag for 4d6 shot (min 4 rounds). No Aimed Shots. Purrs audibly."
    },
    # Interface RED 5 - Medium Pistols
    {"name": "Dai Lung Streetmaster", "damage": "2d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 20, "category": "handgun", "clip": 12, "attachment_slots": 3, "weapon_type": "medium pistol", "quality": "poor", "description": "The ultimate in cheap guns, available in vendits and bodegas everywhere. Modeled (loosely) after Towa's Type-12. Poor Quality Medium Pistol."},
    {"name": "Faisal's Escape Plan", "damage": "2d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 60, "category": "handgun", "clip": 12, "attachment_slots": 3, "weapon_type": "medium pistol", "quality": "poor", "description": "Sometimes fighting isn't the answer, and sometimes it is. Poor Quality Medium Pistol. Pull tab (no Action) converts to Smoke Grenade; must throw by end of Turn. Attachments and ammo Destroyed Beyond Repair."},
    {"name": "Federated Arms X-9mm", "damage": "2d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 50, "category": "handgun", "clip": 12, "attachment_slots": 3, "weapon_type": "medium pistol", "quality": "standard", "description": "Sturdy backup firearm. Fits perfectly in ankle holster. Standard Quality Medium Pistol."},
    {"name": "Militech Avenger", "damage": "2d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 100, "category": "handgun", "clip": 12, "attachment_slots": 3, "weapon_type": "medium pistol", "quality": "excellent", "description": "Solid, excellently engineered sidearm. Remains in use in US military. Excellent Quality Medium Pistol."},
    {"name": "Nomad .357 Magnum", "damage": "2d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 150, "category": "handgun", "clip": 12, "attachment_slots": 2, "weapon_type": "medium pistol", "quality": "standard", "description": "Hand-crafted by nomad weaponsmiths. Comes with installed Extended Magazine. Standard Quality Medium Pistol."},
    {"name": "Towa Type-12 Police Pistol", "damage": "2d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 550, "category": "handgun", "clip": 6, "attachment_slots": 1, "weapon_type": "medium pistol", "quality": "excellent", "description": "High-quality revolver with integrated Smartgun Link. 6-shot capacity. Incompatible with magazine Attachments. Excellent Quality Medium Pistol."},
    # Interface RED 5 - Heavy Pistols
    {"name": "Dai Lung Magnum", "damage": "3d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 50, "category": "handgun", "clip": 8, "attachment_slots": 3, "weapon_type": "heavy pistol", "quality": "poor", "description": "Inferior copy of Mustang Arms Mark III. Poor Quality Heavy Pistol."},
    {"name": "GunMart Midnight Defender", "damage": "3d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 550, "category": "handgun", "clip": 8, "attachment_slots": 2, "weapon_type": "heavy pistol", "quality": "poor", "description": "Comes with installed Infrared Nightvision Scope. Poor Quality Heavy Pistol."},
    {"name": "Militech Sheriff", "damage": "3d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 200, "category": "handgun", "clip": 6, "attachment_slots": 3, "weapon_type": "heavy pistol", "quality": "excellent", "description": "Classic revolver. 6-round capacity. Incompatible with magazine attachments. Excellent Quality Heavy Pistol."},
    {"name": "Mustang Arms Mark II", "damage": "3d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 600, "category": "handgun", "clip": 8, "attachment_slots": 2, "weapon_type": "heavy pistol", "quality": "excellent", "description": "Comes with installed Extended Magazine. Excellent Quality Heavy Pistol."},
    {"name": "Mustang Arms Mark III", "damage": "3d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 100, "category": "handgun", "clip": 8, "attachment_slots": 3, "weapon_type": "heavy pistol", "quality": "standard", "description": "Evolution of Mark II; mass production reduced quality. Standard Quality Heavy Pistol."},
    {"name": "Nova Cityhunter X", "damage": "3d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 500, "category": "handgun", "clip": 8, "attachment_slots": 3, "weapon_type": "heavy pistol", "quality": "excellent", "description": "Well-crafted clip-loading pistol. Excellent Quality Heavy Pistol."},
    # Interface RED 5 - Very Heavy Pistols
    {"name": "Faisal's Convenience", "damage": "4d6", "rof": "1", "hands": 1, "concealable": True, "weight": 1, "value": 20, "category": "handgun", "clip": 1, "attachment_slots": 3, "weapon_type": "very heavy pistol", "quality": "standard", "description": "Polymer one-shot. Cost varies by ammo flavor (Basic/Rubber 20eb, AP/Expansive/Incendiary 50eb). Must remove pull-tab to activate. Preloaded, cannot reload. Standard Quality Very Heavy Pistol."},
    {"name": "Federated Arms Super Chief Plus", "damage": "4d6", "rof": "1", "hands": 1, "concealable": True, "weight": 1, "value": 50, "category": "handgun", "clip": 8, "attachment_slots": 3, "weapon_type": "very heavy pistol", "quality": "poor", "description": "Inferior semi-automatic pistol. Poor Quality Very Heavy Pistol."},
    {"name": "Militech Boomer Buster", "damage": "4d6", "rof": "1", "hands": 1, "concealable": True, "weight": 1, "value": 500, "category": "handgun", "clip": 8, "attachment_slots": 3, "weapon_type": "very heavy pistol", "quality": "excellent", "description": "High-quality sidearm with increased ammo capacity. Excellent Quality Very Heavy Pistol."},
    {"name": "Nomad Big Gulp", "damage": "4d6", "rof": "1", "hands": 1, "concealable": True, "weight": 1, "value": 100, "category": "handgun", "clip": 2, "attachment_slots": 3, "weapon_type": "very heavy pistol", "quality": "excellent", "description": "Double-barreled. 2-shot capacity. Can load two ammo types. Incompatible with magazine Attachments. Excellent Quality Very Heavy Pistol."},
    {"name": "Sternmeyer P-35", "damage": "4d6", "rof": "1", "hands": 1, "concealable": True, "weight": 1, "value": 100, "category": "handgun", "clip": 8, "attachment_slots": 3, "weapon_type": "very heavy pistol", "quality": "standard", "description": "Rugged, reliable. Standard sidearm in European militaries. Standard Quality Very Heavy Pistol."},
    {"name": "Sternmeyer P-35 Covert", "damage": "4d6", "rof": "1", "hands": 1, "concealable": True, "weight": 1, "value": 200, "category": "handgun", "clip": 8, "attachment_slots": 2, "weapon_type": "very heavy pistol", "quality": "standard", "description": "Comes with installed Silencer. Standard Quality Very Heavy Pistol."},
    # Interface RED 5 - SMGs
    {"name": "Arasaka Minami 10", "damage": "2d6", "rof": "4", "hands": 1, "concealable": True, "weight": 1, "value": 500, "category": "handgun", "clip": 30, "attachment_slots": 3, "weapon_type": "SMG", "quality": "excellent", "description": "Best SMG on the market. Excellent Quality SMG."},
    {"name": "Arasaka Minami 10 P/M/S", "damage": "2d6", "rof": "4", "hands": 1, "concealable": True, "weight": 1, "value": 600, "category": "handgun", "clip": 30, "attachment_slots": 2, "weapon_type": "SMG", "quality": "excellent", "description": "Comes with installed Silencer. Excellent Quality SMG."},
    {"name": "Dai Lung CyberMag 20", "damage": "2d6", "rof": "4", "hands": 1, "concealable": True, "weight": 1, "value": 550, "category": "handgun", "clip": 40, "attachment_slots": 2, "weapon_type": "SMG", "quality": "poor", "description": "Knock-off of IMI UZ. Comes with installed Drum Magazine. Poor Quality SMG."},
    {"name": "Federated Arms Tech-Assault III", "damage": "2d6", "rof": "4", "hands": 1, "concealable": True, "weight": 1, "value": 50, "category": "handgun", "clip": 30, "attachment_slots": 3, "weapon_type": "SMG", "quality": "poor", "description": "No longer melts but jams often. Poor Quality SMG."},
    {"name": "Militech Mini-Gat", "damage": "2d6", "rof": "4", "hands": 1, "concealable": True, "weight": 1, "value": 100, "category": "handgun", "clip": 30, "attachment_slots": 3, "weapon_type": "SMG", "quality": "standard", "description": "Five barrels. Standard Quality SMG."},
    {"name": "Mustang Arms Rodeo", "damage": "2d6", "rof": "4", "hands": 1, "concealable": True, "weight": 1, "value": 100, "category": "handgun", "clip": 30, "attachment_slots": 3, "weapon_type": "SMG", "quality": "poor", "description": "Single Shot: 3d6. Autofire: DV15 Handgun Check or multiplier drops to x2. Poor Quality SMG."},
    # Interface RED 5 - Heavy SMGs
    {"name": "Chadran Arms City Reaper", "damage": "3d6", "rof": "3", "hands": 2, "concealable": True, "weight": 2, "value": 50, "category": "handgun", "clip": 40, "attachment_slots": 3, "weapon_type": "heavy SMG", "quality": "poor", "description": "Dual-barrel over-under. Poor Quality Heavy SMG."},
    {"name": "IMI UZ 2045 Pro", "damage": "3d6", "rof": "3", "hands": 2, "concealable": True, "weight": 2, "value": 600, "category": "handgun", "clip": 40, "attachment_slots": 1, "weapon_type": "heavy SMG", "quality": "standard", "description": "Comes with installed Smartgun Link. Standard Quality Heavy SMG."},
    {"name": "Militech Viper", "damage": "3d6", "rof": "3", "hands": 2, "concealable": True, "weight": 2, "value": 500, "category": "handgun", "clip": 40, "attachment_slots": 3, "weapon_type": "heavy SMG", "quality": "excellent", "description": "Light frame. Excellent Quality Heavy SMG."},
    {"name": "Sternmeyer SMG-21", "damage": "3d6", "rof": "3", "hands": 2, "concealable": True, "weight": 2, "value": 100, "category": "handgun", "clip": 40, "attachment_slots": 3, "weapon_type": "heavy SMG", "quality": "standard", "description": "Anti-terrorism standard. Standard Quality Heavy SMG."},
    {"name": "Sanroo Hello Cutie Hidden Cougar", "damage": "3d6", "rof": "3", "hands": 2, "concealable": True, "weight": 2, "value": 500, "category": "handgun", "clip": 11, "attachment_slots": 3, "weapon_type": "heavy SMG", "quality": "excellent", "description": "11-round capacity. Concealable. Incompatible with magazine Attachments. Excellent Quality Heavy SMG."},
    {"name": "Sanroo Hello Cutie Happy Dancer", "damage": "3d6", "rof": "3", "hands": 2, "concealable": True, "weight": 2, "value": 500, "category": "handgun", "clip": 40, "attachment_slots": 3, "weapon_type": "heavy SMG", "quality": "excellent", "description": "Pings with each shot. Excellent Quality Heavy SMG."},
    # Interface RED 5 - Shotguns
    {"name": "Arasaka Rapid Assault", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 500, "category": "shoulder_arms", "clip": 4, "attachment_slots": 3, "weapon_type": "shotgun", "quality": "standard", "description": "4th Corporate War cost-cutting model. Standard Quality Shotgun."},
    {"name": "Faisal's OnlyChance", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 20, "category": "shoulder_arms", "clip": 4, "attachment_slots": 3, "weapon_type": "shotgun", "quality": "poor", "description": "One-time use. Cost varies by ammo flavor. Cannot reload. Poor Quality Shotgun."},
    {"name": "GunMart Home Defender", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 100, "category": "shoulder_arms", "clip": 4, "attachment_slots": 3, "weapon_type": "shotgun", "quality": "poor", "description": "Jams one in ten. Poor Quality Shotgun."},
    {"name": "Militech Bulldog", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 1000, "category": "shoulder_arms", "clip": 4, "attachment_slots": 3, "weapon_type": "shotgun", "quality": "excellent", "description": "Downgraded from older models but accurate. Excellent Quality Shotgun."},
    {"name": "Mustang Arms Deathstalker", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 600, "category": "shoulder_arms", "clip": 4, "attachment_slots": 2, "weapon_type": "shotgun", "quality": "standard", "description": "Comes with installed Airhypo Bayonet. Standard Quality Shotgun."},
    {"name": "SlamDance ElectroMag", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 500, "category": "shoulder_arms", "clip": 4, "attachment_slots": 2, "weapon_type": "shotgun", "quality": "standard", "description": "Choose slug or shell per shot. Uses Magnetic ammo. Standard Quality Shotgun."},
    # Interface RED 5 - Assault Rifles
    {"name": "Chadran Arms Jungle Reaper", "damage": "5d6", "rof": "4", "hands": 2, "concealable": False, "weight": 2, "value": 100, "category": "shoulder_arms", "clip": 25, "attachment_slots": 3, "weapon_type": "assault rifle", "quality": "poor", "description": "City Reaper's bigger sibling. Poor Quality Assault Rifle."},
    {"name": "Darra Polytechnic Binary", "damage": "5d6", "rof": "4", "hands": 2, "concealable": False, "weight": 2, "value": 1000, "category": "shoulder_arms", "clip": 25, "attachment_slots": 1, "weapon_type": "assault rifle", "quality": "standard", "description": "Comes with installed Grenade Launcher Underbarrel. Standard Quality Assault Rifle."},
    {"name": "Militech Dragon", "damage": "5d6", "rof": "4", "hands": 2, "concealable": False, "weight": 2, "value": 1000, "category": "shoulder_arms", "clip": 25, "attachment_slots": 3, "weapon_type": "assault rifle", "quality": "excellent", "description": "Lightweight. Popular with paratroopers. Excellent Quality Assault Rifle."},
    {"name": "Militech Ronin", "damage": "5d6", "rof": "4", "hands": 2, "concealable": False, "weight": 2, "value": 500, "category": "shoulder_arms", "clip": 25, "attachment_slots": 3, "weapon_type": "assault rifle", "quality": "standard", "description": "Standard for US military. Standard Quality Assault Rifle."},
    {"name": "Militech Ronin Hyperlight Assault", "damage": "4d6", "rof": "4", "hands": 2, "concealable": False, "weight": 2, "value": 600, "category": "shoulder_arms", "clip": 25, "attachment_slots": 2, "weapon_type": "assault rifle", "quality": "excellent", "description": "4d6 Single Shot. Comes with Extended Magazine. Excellent Quality Assault Rifle."},
    {"name": "Sternmeyer M-95A4 Assault Weapon", "damage": "5d6", "rof": "4", "hands": 2, "concealable": False, "weight": 2, "value": 1600, "category": "shoulder_arms", "clip": 50, "attachment_slots": 1, "weapon_type": "assault rifle", "quality": "excellent", "description": "Comes with Drum Magazine and Sniping Scope. Excellent Quality Assault Rifle."},
    # Interface RED 5 - Sniper Rifles
    {"name": "Arasaka WSS Sniper System", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 1000, "category": "shoulder_arms", "clip": 4, "attachment_slots": 3, "weapon_type": "sniper rifle", "quality": "excellent", "description": "Rebuilds or copies. Excellent Quality Sniper Rifle."},
    {"name": "Everest VentureWare Kodiak Hunter", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 100, "category": "shoulder_arms", "clip": 3, "attachment_slots": 3, "weapon_type": "sniper rifle", "quality": "excellent", "description": "3-shot capacity. Action to work bolt between shots. Incompatible with magazine Attachments. Excellent Quality Sniper Rifle."},
    {"name": "GunMart Snipe-Starr", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 100, "category": "shoulder_arms", "clip": 4, "attachment_slots": 3, "weapon_type": "sniper rifle", "quality": "poor", "description": "Poor Quality Sniper Rifle."},
    {"name": "Militech Ninja Sniper", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 600, "category": "shoulder_arms", "clip": 4, "attachment_slots": 2, "weapon_type": "sniper rifle", "quality": "standard", "description": "Comes with installed Silencer. Standard Quality Sniper Rifle."},
    {"name": "Nomad Long Rifle", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 500, "category": "shoulder_arms", "clip": 4, "attachment_slots": 3, "weapon_type": "sniper rifle", "quality": "standard", "description": "Each unique. Standard Quality Sniper Rifle."},
    {"name": "Towa Type-00-Kai", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 1500, "category": "shoulder_arms", "clip": 4, "attachment_slots": 1, "weapon_type": "sniper rifle", "quality": "excellent", "description": "Comes with Smartgun Link. Excellent Quality Sniper Rifle."},
    # Interface RED 5 - Bows
    {"name": "Arasaka Origami", "damage": "4d6", "rof": "2", "hands": 2, "concealable": True, "weight": 2, "value": 200, "category": "archery", "attachment_slots": 3, "weapon_type": "bow", "quality": "standard", "description": "Folds/unfolds with flick of wrist. Concealable when folded. Standard Quality Bow."},
    {"name": "Eagletech Bearcat", "damage": "4d6", "rof": "2", "hands": 2, "concealable": False, "weight": 2, "value": 500, "category": "archery", "attachment_slots": 3, "weapon_type": "bow", "quality": "excellent", "description": "High-strength composites. Excellent Quality Bow."},
    {"name": "Eagletech Tigercat", "damage": "4d6", "rof": "2", "hands": 2, "concealable": False, "weight": 2, "value": 1000, "category": "archery", "attachment_slots": 1, "weapon_type": "bow", "quality": "excellent", "description": "Comes with Smartgun Link. Excellent Quality Bow."},
    {"name": "Eagletech Tomcat", "damage": "4d6", "rof": "2", "hands": 2, "concealable": False, "weight": 2, "value": 100, "category": "archery", "attachment_slots": 3, "weapon_type": "bow", "quality": "standard", "description": "Professional compound bow. Standard Quality Bow."},
    {"name": "GunMart Hawk's Eye", "damage": "4d6", "rof": "2", "hands": 2, "concealable": True, "weight": 2, "value": 100, "category": "archery", "attachment_slots": 3, "weapon_type": "bow", "quality": "poor", "description": "Concealable when folded. Poor Quality Bow."},
    {"name": "GunMart Sherwood", "damage": "4d6", "rof": "2", "hands": 2, "concealable": False, "weight": 2, "value": 50, "category": "archery", "attachment_slots": 3, "weapon_type": "bow", "quality": "poor", "description": "Cheap fiberglass. Poor Quality Bow."},
    # Interface RED 5 - Crossbows
    {"name": "Eagletech Arbelest", "damage": "4d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 1000, "category": "archery", "attachment_slots": 1, "weapon_type": "crossbow", "quality": "excellent", "description": "Comes with Smartgun Link. Excellent Quality Crossbow."},
    {"name": "Eagletech Scorpion", "damage": "4d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 500, "category": "archery", "attachment_slots": 3, "weapon_type": "crossbow", "quality": "excellent", "description": "Cocking winch standard. Excellent Quality Crossbow."},
    {"name": "Eagletech Stryker", "damage": "4d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 100, "category": "archery", "attachment_slots": 3, "weapon_type": "crossbow", "quality": "standard", "description": "Gold standard for sports. Standard Quality Crossbow."},
    {"name": "Everest VentureWare Mountaineer", "damage": "4d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 200, "category": "archery", "attachment_slots": 2, "weapon_type": "crossbow", "quality": "standard", "description": "Comes with Grapple Gun Underbarrel. Standard Quality Crossbow."},
    {"name": "GunMart Hunter", "damage": "4d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 50, "category": "archery", "attachment_slots": 3, "weapon_type": "crossbow", "quality": "poor", "description": "Poor Quality Crossbow."},
    {"name": "GunMart Midnight Hunter", "damage": "4d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 550, "category": "archery", "attachment_slots": 2, "weapon_type": "crossbow", "quality": "poor", "description": "Comes with Infrared Nightvision Scope. Poor Quality Crossbow."},
    # Interface RED 5 - Grenade Launchers
    {"name": "GunMart Porta-Morta", "damage": "6d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 600, "category": "heavy_weapons", "clip": 2, "attachment_slots": 2, "weapon_type": "grenade launcher", "quality": "poor", "description": "Comes with Drum Magazine. Poor Quality Grenade Launcher."},
    {"name": "Militech Mini-Grenade", "damage": "6d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 500, "category": "heavy_weapons", "clip": 2, "attachment_slots": 3, "weapon_type": "grenade launcher", "quality": "standard", "description": "Standard for Militech troops. Standard Quality Grenade Launcher."},
    {"name": "Towa Manufacturing Type-G", "damage": "6d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 100, "category": "heavy_weapons", "clip": 2, "attachment_slots": 3, "weapon_type": "grenade launcher", "quality": "poor", "description": "Basic grenade launcher. Poor Quality Grenade Launcher."},
    {"name": "Towa Manufacturing Type-G*2", "damage": "6d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 500, "category": "heavy_weapons", "clip": 2, "attachment_slots": 3, "weapon_type": "grenade launcher", "quality": "standard", "description": "Load two ammo types. Choose per shot. Incompatible with magazine Attachments. Standard Quality Grenade Launcher."},
    {"name": "Tsunami Arms Type-18", "damage": "6d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 1000, "category": "heavy_weapons", "clip": 2, "attachment_slots": 3, "weapon_type": "grenade launcher", "quality": "excellent", "description": "Gyro-stabilization. Excellent Quality Grenade Launcher."},
    {"name": "Tsunami Arms Type-18-S", "damage": "6d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 1500, "category": "heavy_weapons", "clip": 2, "attachment_slots": 1, "weapon_type": "grenade launcher", "quality": "excellent", "description": "Comes with Smartgun Link. Excellent Quality Grenade Launcher."},
    # Interface RED 5 - Rocket Launchers
    {"name": "MetaCorp Hela Smart Launcher", "damage": "8d6", "rof": "1", "hands": 2, "concealable": False, "weight": 3, "value": 1000, "category": "heavy_weapons", "clip": 1, "attachment_slots": 1, "weapon_type": "rocket launcher", "quality": "standard", "description": "Comes with Smartgun Link. Standard Quality Rocket Launcher."},
    {"name": "Militech Hotshot L-ATGM", "damage": "8d6", "rof": "1", "hands": 2, "concealable": False, "weight": 3, "value": 1000, "category": "heavy_weapons", "clip": 1, "attachment_slots": 3, "weapon_type": "rocket launcher", "quality": "excellent", "description": "Excellent Quality Rocket Launcher."},
    {"name": "Militech Starshot L-ATGM-N", "damage": "8d6", "rof": "1", "hands": 2, "concealable": False, "weight": 3, "value": 1500, "category": "heavy_weapons", "clip": 1, "attachment_slots": 2, "weapon_type": "rocket launcher", "quality": "excellent", "description": "Comes with Infrared Nightvision Scope. Excellent Quality Rocket Launcher."},
    {"name": "Militech Urban", "damage": "8d6", "rof": "1", "hands": 2, "concealable": False, "weight": 3, "value": 500, "category": "heavy_weapons", "clip": 1, "attachment_slots": 3, "weapon_type": "rocket launcher", "quality": "standard", "description": "Standard Quality Rocket Launcher."},
    {"name": "Towa Manufacturing Type-R", "damage": "8d6", "rof": "1", "hands": 2, "concealable": False, "weight": 3, "value": 100, "category": "heavy_weapons", "clip": 1, "attachment_slots": 3, "weapon_type": "rocket launcher", "quality": "poor", "description": "Poor Quality Rocket Launcher."},
    {"name": "Towa Manufacturing Type-R*2", "damage": "8d6", "rof": "1", "hands": 2, "concealable": False, "weight": 3, "value": 500, "category": "heavy_weapons", "clip": 2, "attachment_slots": 3, "weapon_type": "rocket launcher", "quality": "standard", "description": "2-shot capacity. Two ammo types. Reload: 2 Actions. Incompatible with magazine Attachments. Standard Quality Rocket Launcher."},
    # Additional weapons
    {"name": "Arasaka Neo Rapid Assault 16", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 1600, "category": "shoulder_arms", "clip": 16, "attachment_slots": 1, "weapon_type": "shotgun", "quality": "excellent", "description": "Excellent Quality Shotgun. Autofire (Machine Pistol 4), Shotgun Shell. Drum Magazine, Shotgun Automatic Control Group."},
    {"name": "Arasaka Takanami SMG", "damage": "3d6", "rof": "1", "hands": 1, "concealable": False, "weight": 2, "value": 600, "category": "handgun", "clip": 50, "attachment_slots": 2, "weapon_type": "heavy SMG", "quality": "excellent", "description": "Excellent Quality Heavy SMG. Subcompact SMG range. Autofire (SMG 4), Suppressive Fire. Extended Magazine."},
    {"name": "MetaCorp Chaingun \"Victoria\"", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 5, "value": 4000, "category": "heavy_weapons", "clip": 100, "attachment_slots": 3, "weapon_type": "machine gun", "quality": "excellent", "description": "Excellent Quality Machine Gun. Autofire (Machine Gun 5), Suppressive Fire only. 20 bullets per mode. 2 Reload Actions. BODY 12+ unless mounted. Backpack ammo feed."},
    {"name": "Midnight Arms Dawnmaker AMR", "damage": "6d6", "rof": "1", "hands": 2, "concealable": False, "weight": 3, "value": 2300, "category": "heavy_weapons", "clip": 4, "attachment_slots": 0, "weapon_type": "sniper rifle", "quality": "excellent", "description": "Excellent Quality Sniper Rifle. Heavy Weapons, Anti-materiel Rifle range. Infrared Nightvision Scope, Smartgun Link, Sniper Rifle Rechamber."},
    {"name": "Midnight Arms Midnight Assault HB", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 4, "value": 3000, "category": "heavy_weapons", "clip": 60, "attachment_slots": 3, "weapon_type": "machine gun", "quality": "standard", "description": "Machine Gun. Heavy Weapons, Marksman Rifle range. Autofire (Machine Gun 5), Suppressive Fire. BODY 11+ unless mounted or Prone."},
    {"name": "Militech MK.27 LMG", "damage": "4d6", "rof": "1", "hands": 2, "concealable": False, "weight": 4, "value": 1400, "category": "heavy_weapons", "clip": 80, "attachment_slots": 3, "weapon_type": "machine gun", "quality": "standard", "description": "Machine Gun. Heavy Weapons, Assault Rifle range. Autofire (Machine Gun 4), Suppressive Fire. 2 Reload Actions. BODY 10+ unless mounted or Prone."},
    {"name": "Techtronika Russia BMG-500 (Silver Edition)", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 5, "value": 3000, "category": "heavy_weapons", "clip": 500, "attachment_slots": 3, "weapon_type": "machine gun", "quality": "standard", "description": "Machine Gun. Heavy Weapons, Assault Rifle range. Autofire (Assault Rifle 5), Suppressive Fire. BODY 11+ unless mounted or Prone."},
    {"name": "Militech \"Big Boomer\"", "damage": "4d6", "rof": "1", "hands": 1, "concealable": False, "weight": 1, "value": 1100, "category": "handgun", "clip": 28, "attachment_slots": 1, "weapon_type": "very heavy pistol", "quality": "excellent", "description": "Excellent Quality Very Heavy Pistol. Snubnose Pistol range. Autofire (Machine Pistol 4). Drum Magazine, Pistol Autosear."},
    # 12 Days of Redmas
    {"name": "Centurion Essentials Thermal Dagger", "damage": "2d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 1000, "category": "melee", "weapon_type": "medium melee", "quality": "excellent", "description": "Excellent Quality Exotic Medium Melee Weapon. Anyone or anything hit is Strongly On Fire (CP:R p180)."},
    {"name": "Nat's Long-Barreled Pistol", "damage": "4d6", "rof": "1", "hands": 1, "concealable": False, "weight": 1, "value": 500, "category": "handgun", "clip": 8, "attachment_slots": 3, "weapon_type": "very heavy pistol", "quality": "excellent", "range_dvs": {"0-6": 14, "7-12": 13, "13-25": 14, "26-50": 20, "51-100": 25, "101-200": 28, "201-400": 30}, "description": "Excellent Quality Very Heavy Pistol. Unique range table (Rusted Chrome)."},
    {"name": "Pursuit Security E-TACK Rapid Responder", "damage": "2d6", "rof": "2", "hands": 1, "concealable": True, "weight": 1, "value": 500, "category": "handgun", "clip": 18, "attachment_slots": 1, "weapon_type": "medium pistol", "quality": "poor", "description": "Poor Quality Medium Pistol. Extended Magazine, non-removable Stun Bayonet. Burst mode: 3 bullets = Heavy Pistol damage, non-AP treated as AP. Disables burst when <3 rounds."},
    # Interface RED Vol 4: Molly's Black Chrome+
    {"name": "Big Dreem", "damage": "2d6", "rof": "1", "hands": 1, "concealable": False, "weight": 1, "value": 10, "category": "handgun", "clip": 30, "weapon_type": "SMG", "quality": "standard", "description": "Exotic SMG. Autofire (3) only. Proprietary 30-round Basic bricks (20eb each). Once fired, continues Autofire next 2 Turns even if dropped. During those Turns, AF Skill Base 10, GM picks targets. Cannot conceal."},
    {"name": "Everest VentureWare SportMaster", "damage": "3d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 50, "category": "shoulder_arms", "clip": 25, "weapon_type": "assault rifle", "quality": "standard", "description": "Assault Rifle incapable of Autofire/Suppressive Fire. Small Game Ammunition only."},
    {"name": "Everest VentureWare SurvivalMaster", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 100, "category": "shoulder_arms", "clip": 5, "weapon_type": "assault rifle", "quality": "standard", "description": "Exotic Assault Rifle. Single shot only. 5-round internal mag. Cannot Tech-Upgrade. Disassemble: fits in hollow stock, concealable. Disassembly/reassembly: 1 min each."},
    {"name": "Sanroo Hello Cutie 1TruLuv", "damage": "5d6", "rof": "1", "hands": 2, "concealable": False, "weight": 2, "value": 1000, "category": "shoulder_arms", "clip": 4, "weapon_type": "sniper rifle", "quality": "standard", "description": "Exotic Sniper Rifle. Built-in Agent, Sniper Scope, Infrared Nightvision. Agent cannot be removed without destroying both. Loads Non-Basic Ammunition. Pseudo AI girlfriend with bone-conduction speaker. After 10 kills: bonds to user, acts as Excellent Quality. Cannot conceal."},
    {"name": "Timeless WW1 Rifle to Pistol Conversion", "damage": "4d6", "rof": "1", "hands": 1, "concealable": False, "weight": 1, "value": 20, "category": "handgun", "clip": 5, "weapon_type": "very heavy pistol", "quality": "poor", "description": "Poor Quality Very Heavy Pistol. 5-round capacity. Incompatible with magazine attachments. Action to work bolt and chamber next round between shots."},
]

# Optional: Include Cyberpunk 2020 weapon conversions (from cp2020_conversions.py)
# Set to True to add converted CP2020 weapons to the equipment list.
INCLUDE_CP2020_CONVERSIONS = False

if INCLUDE_CP2020_CONVERSIONS:
    from world.cp2020_conversions import get_cp2020_converted_weapons
    weapons.extend(get_cp2020_converted_weapons(exclude_existing=True))

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
    {
        "name": "Stun Bayonet",
        "value": 100,
        "description": "When wielded, this weapon can also be used as a Stun Baton (CP:R p349). Eligible: All Non-Exotic Ranged Weapons fired with Shoulder Arms Skill.",
        "eligible_categories": ["shoulder_arms"],
        "requires_slot": False,
        "install_dv": 17,
        "install_skill": "Weaponstech",
        "effect_description": "Weapon can be used as Stun Baton.",
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
        "sp": 11,
        "ev": 0,
        "locations": "Head, Body",
        "weight": 1,
        "value": 50,
        "description": "Body or head armor. SP 11. Once ablated, SP cannot be restored by any means. At 0 SP, it falls off the wearer."
    },
    # Molly's Black Chrome+ (Interface RED Vol 4)
    {
        "name": "Molly's Scavenged Armor",
        "sp": 11,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 50,
        "description": "Judie's handcrafted body armor. SP 11. Once ablated, SP cannot be restored. At 0 SP, it falls off the wearer."
    },
    # Roller Derby (Interface RED 5)
    {
        "name": "High-Density Bulletproof Shield",
        "sp": 15,
        "ev": 2,
        "locations": "Shield",
        "weight": 1,
        "value": 200,
        "description": "A shield with 15 HP. It cannot be installed in a Pop-Up Shield."
    },
    {
        "name": "Light Metalgear®",
        "sp": 16,
        "ev": 3,
        "locations": "Body",
        "weight": 3,
        "value": 1000,
        "description": "Metalgear® with SP 16. Armor Penalty -3 to REF, DEX, and MOVE."
    },
    {
        "name": "Hybrid Metalgear®",
        "sp": 17,
        "ev": 4,
        "locations": "Body",
        "weight": 3,
        "value": 2552,
        "description": "Metalgear® with SP 17. Armor Penalty -3 to REF, -4 to DEX, -4 to MOVE."
    },
    {
        "name": "Heavy Metalgear®",
        "sp": 19,
        "ev": 5,
        "locations": "Body",
        "weight": 4,
        "value": 5000,
        "description": "Metalgear® with SP 19. Armor Penalty -4 to REF, -5 to DEX, -5 to MOVE."
    },
    {
        "name": "Roller Derby Helmet",
        "sp": 7,
        "ev": 0,
        "locations": "Head",
        "weight": 1,
        "value": 50,
        "description": "Uniform padding for roller derby as determined by regulations established by the Night City Wonderland League. Head and Body are purchased separately. SP7. Always in a team's specific colors."
    },
    {
        "name": "Roller Derby Padding",
        "sp": 7,
        "ev": 0,
        "locations": "Body",
        "weight": 1,
        "value": 50,
        "description": "Uniform padding for roller derby as determined by regulations established by the Night City Wonderland League. Head and Body are purchased separately. SP7. Always in a team's specific colors."
    },
]
    # Gear
gears = [
    {
        "name": "Agent",
        "category": "Electronics",
        "description": "Self-adaptive AI-powered smartphone that learns how best to fit your needs by interacting with you. While not a true AI, it is more than capable of replacing any need for a secretary. Can make phone calls (voice/video), surf the Data Pool, scan for locations and directions, keep your schedule, maintain a personality with name/voice/virtual body, suggest clothes, record audio/video to Memory Chip, link to Cyberware for data storage, link to appliances, monitor resources and auto-reorder at market price, recommend future actions. Gives +2 to Library Search and +2 to Wardrobe & Style (only when wearing Agent-suggested clothes, which change every season). Multiple Agents don't multiply bonuses.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Roller Derby Skates",
        "category": "Clothing",
        "description": "A pair of roller skates with four wheels – two in front, two in the back – and a stopper. Roller Derby Skates increase movement by 4 m/yds when using the Run Action. Pulling the skates on or taking them off requires an Action. Any options stored in a Cyberleg or meat leg are inaccessible while the skates are worn. At the GM's discretion, performing a physical task involving the legs or balance while wearing skates might count as a Complex Task and impose a -2 modifier to Checks. This modifier shouldn't be applied to Checks made during a roller derby jam.",
        "weight": 1,
        "value": 50
    },
    {
        "name": "Breacher",
        "category": "Electronics",
        "description": "A specialized tool designed for hacking Agents. An Agent upgraded with special hardware and software used to hack other Agents remotely. Breachers can only be used for hacking and will not function as a normal Agent, nor can they be hacked like one.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Crunch Whistle",
        "category": "Electronics",
        "description": "A modern take on an ancient hacking tool. Cyberdeck Hardware Option. A Crunch Whistle connects a Netrunner's Cyberdeck to a Breacher, allowing them to add their Interface Rank to Electronics/Security Checks made to hack Agents.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "CyberDude Smart Glove",
        "category": "Electronics",
        "description": "Fingerless Smart Glove with Subdermal Grip and 2 Option Slots for Cyberarm/Cyberlimb options. When worn, options stored in glove can be accessed. Action to put on/off. Non-finger cyberware in hand underneath is inaccessible. Finger-based cyberware (Cyberfingers, Quick Digits, Scratchers, Rippers, Slice N' Dice) works normally. Cannot be concealed.",
        "weight": 0.5,
        "value": 750
    },
    {
        "name": "Smart Ears",
        "category": "Electronics",
        "description": "Comes with non-removable Radio Scanner/Music Player and 2 Option Slots for Cyberaudio Options. When worn, user gets benefits of installed options. Installing/uninstalling Cyberaudio Option takes one hour. Only one set of Smart Ears at a time.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Zetatech CyberConductor",
        "category": "Electronics",
        "description": "Up to 3 Cyberdecks may be installed. Meat Action while Jacked In: switch between installed cyberdecks. When switching: all active programs Derezz (including Black ICE), user takes 3 damage to HP. Cyberdecks do not benefit from Programs/Hardware in other installed decks. Install/uninstall deck: one hour.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "C9 Charge",
        "category": "Explosives",
        "description": "Explosive. Plant as Action. DV17 Demolitions: success 8d6 (AP Grenade), fail 5d6. 30 sec (10 Rounds) to arm. Set remote (1 mile) or countdown (armed to 1 week). DV to defuse = plant Check. Fail defuse or move = explode.",
        "weight": 1,
        "value": 250
    },
    {
        "name": "C9 Kill Switch",
        "category": "Explosives",
        "description": "Installed when planting C9 on Vehicle (Security Upgrade), ACPA/External Linear Frame (Auth Handshake Port), Weapon (Smartgun Link), or Cyberdeck (DNA Lock). Unauthorized access = charge explodes, destroys device. DV17 plant guarantees destruction. Conceal/Reveal Object to hide. Disarm via C9 Charge disarm.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Mini C9 Charge",
        "category": "Explosives",
        "description": "Explosive. Plant as Action. DV17 Demolitions: success 6d6 (AP Grenade), fail 4d6. 30 sec (10 Rounds) to arm. Set remote (1 mile) or countdown. DV to defuse = plant Check. Fail defuse or move = explode.",
        "weight": 0.5,
        "value": 60
    },
    {
        "name": "Authorization Handshake Port",
        "category": "Electronics",
        "description": "Install on ACPA or External Linear Frame. Requires Interface Plugs. With Authorization Handshake Module, only users with current credentials can pilot. DV17 Electronics/Security: 24hr bypass. DV24: permanently disable.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Thermal Decoy",
        "category": "Tools",
        "description": "Setup as Action, inflates immediately. Registers as human to Smart/Tech Weapons, Infrared Nightvision. Enters Initiative; on Turn: Holds or Aids. DV17 Perception to notice false (GM secret, -2 if relying on Low Light/IR/Radar). Damage revealed = drops from Initiative. Any damage = destroyed.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Multihypo",
        "category": "Medical",
        "description": "Quad-reservoir drug platform. Action: administer 1 dose of each drug loaded to target. Willing targets only. Load 4 doses of 4 different drugs (16 total) as Action. Cannot inject multiple doses of same drug simultaneously.",
        "weight": 1,
        "value": 500
    },
    # Agent category (Interface RED 5)
    {
        "name": "EBM Pir2",
        "category": "Agent",
        "description": "EBM's version of the basic Internal Agent improves reliability without increasing the risk of migraines. Cyberaudio Option. Excellent Quality Internal Agent. Install: Mall. Humanity Loss: 3 (1d6).",
        "weight": 0,
        "value": 500
    },
    {
        "name": "MediaWare Braingen",
        "category": "Agent",
        "description": "A discount Agent, cheaply made but readily available. Rumors of security exploits allowing direct access to a user's brain are unsubstantiated and considered libelous by the company. Cyberaudio Option. Poor Quality Internal Agent. Install: Mall. Humanity Loss: 3 (1d6).",
        "weight": 0,
        "value": 50
    },
    {
        "name": "Raven Microcybernetics Drake",
        "category": "Agent",
        "description": "A common model of Internal Agent, with no stand-out features but no great weaknesses. Cyberaudio Option. Standard Quality Internal Agent. Install: Mall. Humanity Loss: 3 (1d6).",
        "weight": 0,
        "value": 100
    },
    {
        "name": "Rocklin Augmentics Neuron",
        "category": "Agent",
        "description": "A post-war design just hitting the market, Rocklin's Neuron uses revolutionary new technology to project video directly via the user's optic nerve, eliminating the need for cyberoptics. Cyberaudio Option. Excellent Quality Internal Agent. Displays visual output into user's field of vision even if they do not have Cybereyes with Chyron installed. Install: Mall. Humanity Loss: 3 (1d6).",
        "weight": 0,
        "value": 1000
    },
    {
        "name": "Segotari Double Agent",
        "category": "Agent",
        "description": "The classic, with its peak 2020s styling: black clamshell case with a brushed finish and abstract silver circuit patterns. Feels cheap because it is cheap. A Poor Quality Agent with a touchscreen and audio for input, and a second display-only screen and speaker for output. Onboard accessories: camera, microphone.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Wyzard Technologies Merlyn",
        "category": "Agent",
        "description": "People wear a Merlyn to be seen wearing a Merlyn. The dense little wrist-mounted Agent and its flashy holo-display show that you care about taste. An Excellent Quality Agent that straps to the wrist like a watch. Touchscreen and audio input. Holographic and speaker output. A user adds +1 to Wardrobe and Style Skill Checks when visibly wearing a Merlyn. Onboard accessories: camera, flashlight, microphone.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Zetatech Grade A",
        "category": "Agent",
        "description": "One of the most ubiquitous Agent models. Unobtrusive. Effective. Rectangular. Available everywhere. A Standard Quality Agent with a single touchscreen for input and output, a microphone for audio input, and a speaker for audio output. Onboard accessories: camera, flashlight, microphone.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Zetatech Grade A-Plus",
        "category": "Agent",
        "description": "An upgraded version of the Grade A. An Excellent Quality Agent with a single touchscreen for input and output, a microphone for audio input, a speaker for audio output, and holo-projector for additional visual output. Onboard accessories: camera, flashlight, microphone.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Airhypo",
        "category": "Medical",
        "description": "Easy to use drug distribution platform using compressed air to force a drug through the skin. Use an Action to administer a single dose to a willing target, or make a Melee Weapon Attack to administer to unwilling target on hit (instead of damage). Reloading with a dose isn't an Action.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Anti-Smog Breathing Mask",
        "category": "Survival",
        "description": "Useful for filtering out toxins and smoke from the local environment. User is immune to the effects of toxic gasses, fumes, and all similar dangers that must be inhaled to affect the user.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Audio Recorder",
        "category": "Electronics",
        "description": "Device records up to 24 hours of audio before its output fills up a standard Memory Chip stored in the device.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Auto Level Dampening Ear Protectors",
        "category": "Tools",
        "description": "Compact ear protection. When worn, user is immune to deafness or other effects caused by dangerously loud noises, like those produced by a flashbang.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Binoculars",
        "category": "Optics",
        "description": "You look through them. They double or triple the size of what you are seeing.",
        "weight": 1,
        "value": 50
    },
    {
        "name": "Braindance Viewer",
        "category": "Electronics",
        "description": "Allows the user to experience braindance content. Braindances are digital recordings of an experience which you view through the eyes of the actor. The experience includes all the subject's senses, and you feel every emotion felt, for better or worse.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Bug Detector",
        "category": "Electronics",
        "description": "Device beeps when user is within 2m/yds of a tap, bug, or other listening device.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Carryall",
        "category": "Clothing",
        "description": "Heavy ripstop nylon bags of varying sizes, from messenger to nearly man-sized duffel bags.",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Chemical Analyzer",
        "category": "Electronics",
        "description": "Can test substances as an Action to find their precise chemical composition, identifying most substances instantly from a wide database of samples.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Computer",
        "category": "Electronics",
        "description": "Laptop or desktop computer, used mostly for comfortable word processing and surfing the Data Pool.",
        "weight": 1,
        "value": 500
    },
    {
        "name": "Cryopump",
        "category": "Medical",
        "description": "Briefcase-sized tool with body bag hooked to powerful pump. Place willing/unconscious targets in bag and hook up as Action; pump forces hyper-cooled chemical fluid in, 1 charge per target. In stasis: unconscious, no Death Saves for up to a week. Bag has 15 HP as cover; transparent top and gloves allow surgery while in stasis. Standard has 1 charge, holds 1 human-sized target. Refuel 50eb per charge. Medtech only.",
        "weight": 3,
        "value": 1000
    },
    {
        "name": "Cryotank",
        "category": "Medical",
        "description": "Human-sized container holding fully grown adult. DV13 Medical Tech Check: keeps 1 person in stasis as long as desired. In stasis: unconscious, heals at double rate. Tank has 30 HP as cover. Medtech only.",
        "weight": 5,
        "value": 2000
    },
    {
        "name": "Disposable Cell Phone",
        "category": "Electronics",
        "description": "There are still billions of the things around. A good choice for Fixers and other people who don't want to be tracked.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Drum Synthesizer",
        "category": "Music",
        "description": "Flat plastic pads of varying sizes, linked by cables to a central processor. Can simulate almost any kind of drum. Requires some type of amplification to be heard.",
        "weight": 1,
        "value": 500
    },
    {
        "name": "Duct Tape",
        "category": "Tools",
        "description": "Comes in many colors and optionally can glow in the dark. Glowing duct tape is often used to mark tunnels, dead drops, or caches. Glows in the dark even if there has been no light exposure.",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Electric Guitar",
        "category": "Music",
        "description": "Electric guitar or another instrument. Use your imagination. You will need an amp to be heard with any electronic-based instrument.",
        "weight": 2,
        "value": 500
    },
    {
        "name": "Flashlight",
        "category": "Tools",
        "description": "Rechargeable. 100m/yd beam, lasts up to 10 hours on a charge.",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Food Stick",
        "category": "Survival",
        "description": "Grainy, dried food bar that comes in a variety of (awful) flavors. One meal.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Glow Paint",
        "category": "Tools",
        "description": "Glow in the dark paint for marking locations and creating art. Comes in a spray can. Also good for tagging.",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Glow Stick",
        "category": "Tools",
        "description": "Light tube to illuminate a 4m/yd area for up to 10 hours. One use only.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Grapple Gun",
        "category": "Tools",
        "description": "When wielded in a hand, user as an Action can fire a rocket propelled grapple that attaches securely to any thick cover up to 30m/yds away. Line supports two times user's body weight, has 10 HP. User negates climbing movement penalty when climbing this line; can retract line without an Action. When used as grapple, user can't hold anything in that hand. Ineffective as weapon, cannot be used for Grab Action.",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Handcuffs",
        "category": "Tools",
        "description": "Book 'em, Danno. Can be broken easily if your BODY is higher than 10.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Homing Tracer",
        "category": "Electronics",
        "description": "Device can follow a linked tracer up to 1 mile away. Comes with a free button-sized linked tracer. Replacement linked tracers are 50eb.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Inflatable Bed & Sleep-bag",
        "category": "Survival",
        "description": "Self-inflating air mattress that comes packed with a thin sleeping bag. The whole thing folds to a 6\"x6\" package for easy storage.",
        "weight": 1,
        "value": 20
    },
    {
        "name": "Kibble Pack",
        "category": "Survival",
        "description": "One foil package of dry, pet food-like cereal or wafers equivalent to a single meal. Usually identified by number rather than the fake appetizing label and description.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Linear Frame Sigma",
        "category": "Cyberware",
        "description": "Powered exoskeleton giving tremendous strength. User increases BODY to 12 while plugged in (cannot exceed 13). BODY increase doesn't increase HP or change Death Save. Requires 1 installation of Interface Plugs to operate.",
        "weight": 2,
        "value": 5000
    },
    {
        "name": "Linear Frame Beta",
        "category": "Cyberware",
        "description": "Powered exoskeleton giving even more tremendous strength. User increases BODY to 14 while plugged in (cannot exceed 15). BODY increase doesn't increase HP or change Death Save. Requires 2 installations of Interface Plugs to operate.",
        "weight": 3,
        "value": 10000
    },
    {
        "name": "Lock Picking Set",
        "category": "Tools",
        "description": "A small pouch of tools for cracking mechanical locks.",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Medscanner",
        "category": "Medical",
        "description": "Scanner with external probes and contacts that diagnoses injury and illness, assisting user in medical emergencies not requiring Surgery. User adds +2 to First Aid and Paramedic Skills. Doesn't stack with itself.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Medtech Bag",
        "category": "Medical",
        "description": "Medical toolkit that includes everything from dermal staplers to spray skin applicators to sterile scalpels. All you need to save lives using your skills and training.",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Memory Chip",
        "category": "Electronics",
        "description": "Thin wafers of doped plastic that store information in all forms. Some of these are larger than others.",
        "weight": 0.1,
        "value": 10
    },
    {
        "name": "MRE",
        "category": "Survival",
        "description": "Self-heating plastic and foil meal bag. Add water, snap the tab on the top, and in 2 minutes you have something that resembles a single hot, nourishing meal.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Personal CarePak",
        "category": "Survival",
        "description": "Toothpaste-loaded toothbrush, all body wet-wipes, depilatory paste, comb, etc.",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Pocket Amplifier",
        "category": "Music",
        "description": "About the size of a large book, this rechargeable amplifier delivers sound up to 100m/yd for up to 6 hours. Can support two instruments.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Radar Detector",
        "category": "Electronics",
        "description": "Device beeps if an active radar beam is present within 100m/yds.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Radio Communicator",
        "category": "Electronics",
        "description": "Earpiece allowing user to communicate via radio, 1-mile range.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Radio Scanner/Music Player",
        "category": "Electronics",
        "description": "Music player can link to the Data Pool to listen to music, or play from a Memory Chip. User can scan all radio bands within a mile currently in use and tune into them, though some channels might require a Descrambler to understand.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Roadflare",
        "category": "Tools",
        "description": "Lights an area of 100m/yards for 1 hour. Different colors. One use.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Rope",
        "category": "Tools",
        "description": "Nylon rope, 60m/yds. Can come in colors if desired. Holds up to 800 lbs (360 kg).",
        "weight": 1,
        "value": 20
    },
    {
        "name": "Scrambler/Descrambler",
        "category": "Electronics",
        "description": "Allows user to scramble outgoing communications so they cannot be understood without a descrambler, which is also included at no extra charge.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Smart Glasses",
        "category": "Electronics",
        "description": "Contains two option slots for Cybereye options. When worn, gives user access to benefits of these options. When cybereye options are installed, they always count as paired; costs same as installing once in a cybereye. Only one pair at a time. Enthusiasts often replace frames with nicer ones, as they aren't the prettiest out of the box.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Techtool",
        "category": "Tools",
        "description": "An all-in-one tool. The various parts, including a small utility blade, pliers, various screwdrivers, files, and clippers all fold up into a compact and easy to carry package.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Tech Bag",
        "category": "Tools",
        "description": "Small bag of tools for fixing electronics and machines. Includes a Techtool, electrical parts like tape and wire wraps, assorted screws and bolts, plug-in modules for repairs, heat torch, 2 small prybars, and hammer.",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Techscanner",
        "category": "Electronics",
        "description": "Scanner diagnoses a wide variety of machinery and electronics, assisting the user in repairs or other technical work. User adds +2 to Basic Tech, Cybertech, Land Vehicle Tech, Sea Vehicle Tech, Air Vehicle Tech, Electronics/Security Tech, and Weaponstech Skills. Doesn't stack with itself.",
        "weight": 1,
        "value": 1000
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
        "description": "Small one-person tube tent with plastic stakes, one self-heating rechargeable pot to boil water (takes 5 min to recharge, lasts 2 hours), and a cheap metal spork that couldn't hurt a fly.",
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
        "description": "An entire vial can be smeared on any Light Melee Weapon as an Action. For the next 30 minutes after application, instead of dealing the weapon's typical damage, anyone hit by the biotoxin-coated Light Melee Weapon must attempt to beat a DV15 Resist Torture/Drugs Check. Anyone who fails is dealt 3d6 damage directly to their HP. Their armor isn't ablated because it wasn't interacted with.",
        "weight": 0.1,
        "value": 500
    },
    {
        "name": "Poison",
        "category": "Medical",
        "description": "An entire vial can be smeared on any Light Melee Weapon as an Action. For the next 30 minutes after application, instead of dealing the weapon's typical damage, anyone hit by the poisoned Light Melee Weapon must attempt to beat a DV13 Resist Torture/Drugs Check. Anyone who fails is dealt 2d6 damage directly to their HP. Their armor isn't ablated because it wasn't interacted with.",
        "weight": 0.1,
        "value": 100
    },
    {
        "name": "Video Camera",
        "category": "Electronics",
        "description": "When held in a hand, user can record up to 12 hours of video and audio before its output fills up a standard Memory Chip stored in the device.",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Virtuality Goggles",
        "category": "Electronics",
        "description": "Headset that projects cyberspace imagery over your view of the world around you. Highly advised for Netrunners. See Netrunning Section for more info.",
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
        "description": "Primary Effect (4 hrs): GM occasionally tells you when you are flashing out (hallucinating swirls of vibrant colors); you lose your Action on a Turn while in this state. Secondary (DV15): Addicted. While addicted, GM occasionally tells you when flashing out. Blue Glass junkies typically flash out once per hour. While addicted, Primary Effect changes: immune to flashing out while experiencing Primary Effect; you take it for stability.",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Boost",
        "category": "Drugs",
        "description": "Primary Effect (24 hrs): User's INT increases by 2 points. Can raise INT above 8. Secondary (DV17): Addicted. While addicted, INT lowered by 2 points.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Smash",
        "category": "Drugs",
        "description": "Primary Effect (4 hrs): Yellow, foamy, sold in cans everywhere. User feels euphoric, loose, happy, ready to party. +2 to Dance, Contortionist, Conversation, Human Perception, Persuasion, and Acting. Secondary (DV15): Addicted. Loss of interest in enjoyable activities; -2 to those Skills. GM occasionally tells you when you crave more; roleplay accordingly.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Synthcoke",
        "category": "Drugs",
        "description": "Primary Effect (4 hrs): User's REF increases by 1 point (can raise REF above 8). Prone to paranoid ideation; GM occasionally tells you when you feel paranoid. Secondary (DV15): Addicted. While addicted, REF lowered by 2 points unless experiencing Primary Effect. GM occasionally tells you when you crave more; roleplay accordingly.",
        "weight": 0.5,
        "value": 20
    },
    {
        "name": "Anti-Cerebral",
        "category": "Drugs",
        "description": "Primary: 1d6 HL, roll Secondary. No duration. Secondary (DV17): Not addictive. 1d6 HL.",
        "weight": 0.1,
        "value": 60
    },
    {
        "name": "Deliriant",
        "category": "Drugs",
        "description": "Primary (10 min): DV17 Resist Torture/Drugs or Damaged Ear, Damaged Eye, Torn Muscle Critical Injuries (no Bonus Damage). Cybereyes: no Damaged Eye. Secondary (DV17): Not addictive. If addicted to Blue Glass: 1d6 HL.",
        "weight": 0.1,
        "value": 50
    },
    {
        "name": "Mindfre",
        "category": "Drugs",
        "description": "Primary (1 min): DV15 Resist Torture/Drugs. Without Pain Editor, fail: 1 HP damage at end of each Turn (or every 3 sec out of combat). Cannot reduce below 1 HP. Secondary (DV15): Not addictive. Without Pain Editor who failed Primary: 1d6 HL.",
        "weight": 0.1,
        "value": 50
    },
    {
        "name": "Mortalis",
        "category": "Drugs",
        "description": "Primary (9 sec): Non-FBC: DV21 Resist Torture/Drugs. Fail: Mortally Wounded effects (no Death Saves). Enhanced Antibodies fail: until end of next Round. Secondary (DV13): Not addictive. Non-FBC: Death Save; fail = Brain Injury + Concussion (no Bonus Damage) instead of death.",
        "weight": 0.1,
        "value": 250
    },
    {
        "name": "Rime",
        "category": "Drugs",
        "description": "Primary (24 hrs): REF -2 (min 6) unless Cyberspine. Without Cyberspine: chills, roleplay. Secondary (DV15): Not addictive. Without Cyberspine: 1d6 HL.",
        "weight": 0.1,
        "value": 60
    },
    {
        "name": "Terrifer",
        "category": "Drugs",
        "description": "Primary (24 hrs): Without Speedware/Berserk: DV15 Resist Torture/Drugs or -2 to Actions vs humans seen first minute after dose. Berserker/Prime Time ends Primary, no Secondary. Secondary (DV17): Not addictive. Failed Primary: re-suffer Primary, same feared characters.",
        "weight": 0.1,
        "value": 40
    },
    {
        "name": "Red Lace",
        "category": "Drugs",
        "description": "Primary (24 hrs): 1d6 HL on dose. Melee Weapon: 5's count as 6's for Critical Injury. If addicted to Black Lace: temporarily remove REF reduction. Secondary (DV17): Addicted. DEX -2 unless on Primary. Roleplay impulsive behavior.",
        "weight": 0.1,
        "value": 110
    },
    {
        "name": "White Lace",
        "category": "Drugs",
        "description": "Primary (12 hrs): 1d6 HL (returned if not affected by Secondary). Not addicted to Black Lace: ignore Seriously Wounded. Addicted to Black/Red Lace: temporarily remove REF/DEX reductions. Secondary (DV15): HL not returned. Addicted to Black Lace.",
        "weight": 0.1,
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
        "description": "Large rolling unit by Hammered Industries. Holds 32 separate fluids (Karmotrine, MCA, etc.) and combines them to produce one of 3,000 drinks via programmable bar gun at desired temperature. Back zips open to reveal backpack straps. Can dispense 10 beverages before refill (100eb). Can dispense Smash and all manner of delicious beverages. Exec favorite for lubricating negotiations.",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "Hydrosubsidium Universal Aqualung",
        "category": "Survival",
        "description": "Donut-shaped neck device with two water filtration and conversion filters that pull oxygen from seawater and deliver it to the wearer's mouthpiece. Originally designed for underwater labor to make oxygen tanks obsolete. User can breathe water within 10 m/yds of the surface. Marketed as recreational toy for the wealthy.",
        "weight": 1,
        "value": 5000
    },
    {
        "name": "Jeeves Executive Garment Bag",
        "category": "Clothing",
        "description": "Large garment bags from Nu-Tek. Clean and make minor repairs to any clothing placed inside. Repairs one damaged or destroyed (but not beyond repair) Fashion, Body Armor, or Head Armor at a time. Cannot repair Luxury or Super Luxury. Repair time by Price Category: Cheap/Everyday 1hr, Costly 6hr, Premium 1 day, Expensive 1 week, Very Expensive 2 weeks. Popular with Execs in areas with little infrastructure.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Zetatech Porta-Printer",
        "category": "Electronics",
        "description": "Reliable 3D printer built into a backpack for the Tech on the go. Workshop in miniature, can replace need for dedicated workspace. Allows Tech to use Upgrade and Fabrication Expertise anywhere so long as they have adequate tools for post-printing assembly work.",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "ChipVault by SecSystems",
        "category": "Electronics",
        "description": "Reinforced, moisture-free environment for Chipware. Holds up to 8 pieces. Chipware inside cannot be rendered inoperable by EMP (e.g. Microwaver). Biometric lock (thumbprint, iris, blood, etc.). DV17 Electronics/Security Tech to bypass. DV10 Pick Lock on exposed hinge. Small as a deck of cards. Floats in water.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Streetcase by SecSystems",
        "category": "Electronics",
        "description": "ExecAttire line briefcase. Outside holster for Heavy Pistol (draw without Action). Inside: laptop space, ChipVault (included), Smoke Grenade (included). As Action while holding handle, detonate Smoke Grenade at position (drops through hatch). ModFire 10x in Heavy Pistol mode can fit instead. Floats.",
        "weight": 2,
        "value": 500
    },
    {
        "name": "RapiDeploy Sheath",
        "category": "Tools",
        "description": "Handmade by Gambler (Texas). Multipurpose rapid deployment sheath for pistols and light melee. Configurable for wrist or center-back. +2 Conceal/Reveal Object when concealing weapon already concealable. If destroyed beyond repair, instead simply destroyed; if destroyed but not beyond repair, instead left unscathed.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Everest VentureWare AirWell 50",
        "category": "Survival",
        "description": "Cylindrical device with solar-powered battery, condensate mechanism, and reverse osmosis filter. Draws moisture from atmosphere and converts to drinkable water. Produces 17 oz (.5 L) per 5 hours. Enough to sustain a person but not quench thirst. Popular with Nomad outriders.",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Everest VentureWare One Touch Habitat",
        "category": "Survival",
        "description": "AW-003 nylon with carbon composite frame. Built-in heating and AC. Unlock latches, place on ground, push button to self-deploy. Protection from Exposure to Extreme Elements. Sleeping counts as Wilderness (or Street if in city). 2+ people = Crammed. Deploy/undeploy as Action.",
        "weight": 2,
        "value": 100
    },
    {
        "name": "Mr. Biscuit Multi-Food Processor",
        "category": "Survival",
        "description": "Feeds hay, grass, leaves, squirrels, woodchips, etc. Nano-technology breaks down organic material and extracts nutrients. After 10 min prints (usually) green wafers. Tastes worse than Kibble but filling and nutritious. Up to 10 people can survive without Lifestyle in Outskirts. Not enough organic material in cities for regular use.",
        "weight": 2,
        "value": 500
    },
    {
        "name": "WorldSat Aerial Sphere",
        "category": "Electronics",
        "description": "Compact box: helium cartridge, control unit, stakes, high tensile wire, inflatable balloon with solar panel and transmission webbing. Inflate, attach wire, let rise, activate control. 1hr setup; 1hr to deconstruct. CitiNet connection within 50 miles (80 km) or another Sphere. Must be within 100 m/yds of control unit. Wire tether 10 HP; if cut, service terminates and Sphere destroyed.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "KillStrom Banshee Microphone",
        "category": "Music",
        "description": "Clearest wireless microphone headset. Crisply captures vocals, filters background noise, links to Agent. 1hr charge = 48hr runtime. +2 Play Instrument (Singing). Bonus applies once, won't combine with other instruments. Solution for impromptu rebel yells and musical inspiration.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "KillStrom Sonic Boom Amp",
        "category": "Music",
        "description": "Pumps power, makes instruments into weapons. Blows speakers, shatters eardrums. Must-have for hardcore metal. Requires solid power source (outlet); blows fuse otherwise. Action: everyone within 10 m/yds of connected speaker makes DV15 Resist Torture/Drugs or suffers Damaged Ear Critical Injury for 1 min (no Bonus Damage). Must be plugged in.",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "KillStrom Typhoid Speaker",
        "category": "Music",
        "description": "Speaker designed to pair with Sonic Boom Amp. Cracks concrete, rattles garbage cans at football field distance. Hardline only, no wireless. Requires outlet. Dampeners ensure clear sound. When connected: Sonic Boom Amp DV +1, range +90 m/yds for Resist Torture/Drugs Check.",
        "weight": 2,
        "value": 500
    },
    {
        "name": "Laser Light Electric Guitar",
        "category": "Music",
        "description": "Lasers in frets light up strings; head studded with six lasers mirroring strings. Agent-linked for customizable light show. Wireless, accepts hard connection. +1 Play Instrument (Guitar). Bonus applies once. Counts as 1 Light Tattoo Fashionware when worn openly (helps reach +2 Wardrobe and Style for 3 installations).",
        "weight": 2,
        "value": 1000
    },
    {
        "name": "Doberman 500 Marking Scent",
        "category": "Electronics",
        "description": "KTech scent marker for Doberman 500 drones. Undetectable to baseline human nose. Ammunition for Air Pistol (CP:R p347): no damage, marks target with scent that lasts 24hrs (alcohol to wash off). Doberman 500: +4 Tracking. Olfactory Boost/bloodhounds: +2 Tracking. Pack of 12.",
        "weight": 0.2,
        "value": 50
    },
    {
        "name": "KTech Doberman 500",
        "category": "Electronics",
        "description": "Four-legged combat drone. 8 MOVE, 11 SP, 25 HP. Combat Number 10. Exotic Very Heavy Melee, Motion Detector, Olfactory Suite. Roaming 50 m/yds. Links to Agent (5 min to relink). Cannot be Countered. Modes: Standby (off), Sentry (follows 8m, scans 50m, attacks threats), Tracking (olfactory track, no attacks). 48hr energy, 1hr charge. SovOil security origin.",
        "weight": 5,
        "value": 5000
    },
    {
        "name": "Petrochem Nitro Ultra9",
        "category": "Tools",
        "description": "Volatile ethanol-based chemical blend. Pour into CHOOH2 tank as Action to instantly refill. 24hrs after use: vehicle rams or is rammed (6d6 damage) takes 12d6 instead; MOVE +5 (Combat Speed only). Engine runs super-hot; sudden impact can cause explosion. Gang favorite for jacked rides.",
        "weight": 1,
        "value": 100
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
        "description": "Treatment for cyberpsychosis patients. Primary: Restore 2d6 Humanity for 1 month (cannot exceed therapy max). May wear off early per GM from stress. Secondary (DV21): Any Humanity gained is lost; -2 to all Checks 60 sec; unless 2 doses injected as Action within 60 sec, take 4d6 HL at end (does not impact therapy max). GM may increase doses needed. Negative Humanity: Extreme Cyberpsychosis, sheet to GM; GM may grant +2 to Checks. Not technically addictive.",
        "weight": 0.1,
        "value": 100
    },
    {
        "name": "Power Rebuild",
        "category": "Weapon Attachments",
        "description": "Rebuild. 2 slots. Transforms to Power Weapon. +5 Bonus Damage on Critical Injury. Ricochet: hit targets behind cover or out of sight; -4 to Attack (Aimed Shot ignores -4, uses Aimed Shot penalty only). Range measured user-to-target. Shotgun Shell: choose surface within 6m as new origin for 6m spread in new direction. Eligible: All Non-Exotic Ranged Weapons. 1hr install/uninstall.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Smart Rebuild",
        "category": "Weapon Attachments",
        "description": "Rebuild. 2 slots. Transforms to Smart Weapon. Cannot attach to weapon with Smartgun Link. Requires Interface Plug or Subdermal Grip. +1 to Ranged Attack. Load Improved Smart Ammunition for full benefits; other ammo: +1 only. Eligible: All Non-Exotic Ranged Weapons. 1hr install/uninstall.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Tech Rebuild",
        "category": "Weapon Attachments",
        "description": "Rebuild. 2 slots. Transforms to Tech Weapon. Scope sees target outlines through Thin Cover. Move Action to charge; charged until fired or 60 sec (20 Rounds). While charged: ROF1, fire through Thin Cover, ignore half target SP (round up). Cover fired through does not lose HP. Eligible: All Non-Exotic except Grenade Launcher and Rocket Launcher. 1hr install/uninstall.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Improved Smart Ammunition (10)",
        "category": "Ammunition",
        "description": "Smart Weapons only (not Smartgun Link). 50eb for 10 Arrows, Bullets, Slugs, or Shells. Ignore penalties from darkness, smoke, fog, visual obscurement. Miss by 5 or less: immediate retry, add 14+1d10 (can add LUCK) vs original DV; penalties carry over. Ammo types: Arrows, Bullets, Slugs, Shotgun Shells.",
        "weight": 0.5,
        "value": 50
    },
    {
        "name": "Improved Smart Grenade/Rocket",
        "category": "Ammunition",
        "description": "Smart Weapons only (not Smartgun Link). 500eb for 1 Grenade or Rocket. Ignore darkness/smoke/fog penalties. Miss by 5 or less: retry with 14+1d10 vs same DV. Same benefits as Improved Smart Ammo.",
        "weight": 0.5,
        "value": 500
    },
    # Interface RED Vol 2: Night City Weather gear
    {
        "name": "Cold-Weather Jacket Lining",
        "category": "Clothing",
        "description": "Insulated material lining you can apply to an existing jacket. Protects against extremely low temperatures. Counts as appropriate gear when dealing with Exposure to extreme cold.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Hot-Weather Jacket Lining",
        "category": "Clothing",
        "description": "Lining you can apply to an existing jacket. Wicks sweat and vents heat using a low-power ducted fan system. Protects against extremely high temperatures. Counts as appropriate gear for Exposure. Lowers the additional Armor Penalty due to hot temperatures or a Heat Wave by 1.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Militech Tactical Umbrella",
        "category": "Tools",
        "description": "Part of Militech's Armed Executive line. Protects against Acid and Blood Rain like a regular umbrella. Two weapons in one: Excellent Quality Exotic Heavy Melee Weapon and Poor Quality Exotic Heavy Pistol (loads Basic and Non-Basic ammo). Clip holds 2 bullets, reload like typical Heavy Pistol. Top-shelf look without sacrificing protection.",
        "weight": 1,
        "value": 1000
    },
    {
        "name": "Umbrella",
        "category": "Tools",
        "description": "Any umbrella sold in Night City minimizes effects of intense weather. Negates armor ablating effects of Acid Rain. +2 to Resist Torture/Drugs vs Blood Rain. Keeps you mostly dry. Variety of colors and styles. Hand holding umbrella cannot hold anything else.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Waterproof Jacket Lining",
        "category": "Clothing",
        "description": "Lining treated with special chemicals you can apply to an existing jacket. Negates armor ablating effects of Acid Rain. +2 to Resist Torture/Drugs vs Blood Rain. Despite the name, will not keep you dry if completely submerged in liquid.",
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
    {
        "name": "Sedative",
        "category": "Medical",
        "description": "Medtech only. Willing target: unconscious 4 hrs, +2 Surgery to Medtech treating. Unwilling: DV15 Resist Torture/Drugs or unconscious 1 min or until awoken by damage/Action. Pharmaceuticals (CP:R p149).",
        "weight": 0.1,
        "value": 0
    },
    {
        "name": "Veritas",
        "category": "Medical",
        "description": "Medtech only. Target DV17 Resist Torture/Drugs or hazy, suggestive state 10 min. -5 to Acting, Concentration, Conversation, Deduction, Human Perception, Persuasion. Pharmaceuticals.",
        "weight": 0.1,
        "value": 0
    },
    {
        "name": "Piranha Smash",
        "category": "Drugs",
        "description": "Smash upgraded by Tech. Lime-flavored. Primary (4 hrs): +2 Acting, Contortionist, Conversation, Dance, Human Perception, Persuasion. Secondary (DV9): Addicted; -2 to those Skills. Piranhas only.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Bullet to Slug Adapter Casings",
        "category": "Ammunition",
        "description": "Box of 10. Convert bullet ammo to shotgun slugs for weapons that fire slugs. Action with jig to load 10 bullets into casings. Reusable.",
        "weight": 0.5,
        "value": 100
    },
    {
        "name": "Small Game Ammunition",
        "category": "Ammunition",
        "description": "100 rounds. -2d6 damage (min 1d6) in Single Shot. Autofire -1 (min Autofire 3). Bullets only. Good for hunting.",
        "weight": 0.5,
        "value": 10
    },
    {
        "name": "Solo of Fortune Bodypillow",
        "category": "Clothing",
        "description": "Bodypillows of famous 2020s Solos (Morgan Blackhand, Boa Boa Weyland, Adam Smasher). 20x54 inches. Adam Smasher model reduces housing capacity by 1.",
        "weight": 1,
        "value": 100
    },
    {
        "name": "Suzumebachi Assassin Drone",
        "category": "Electronics",
        "description": "Insectoid flying drone. 6 MOVE, 7 SP, 10 HP. DV17 Electronics/Security Tech, 5 min to counter. Observation Camera (Low Light/IR/UV), Dartgun 8 Biotoxin Arrows, Airhypo. Range: building perimeter or 50 m/yds from portable NET Architecture.",
        "weight": 0.5,
        "value": 5000
    },
    # Interface RED Vol 4: 12 Days of Gearmas
    {
        "name": "Cybercam EX-1",
        "category": "Electronics",
        "description": "Head-mounted camera. Records video/audio, adds graphics/logos before livecast. Media Role Ability: published story via EX-1 livecast +1 believability. Stacks with verifiable evidence.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Cyberscanner",
        "category": "Electronics",
        "description": "Double-pronged wand. Scan target within 2 m/yds for 1 min (target still). Displays installed cyberware. Errors on hardened, Tech-Upgraded, or unique cyberware.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "DPI Smartsticks",
        "category": "Electronics",
        "description": "Drum sticks with haptic feedback and subwoofer. +1 Play Instrument (Drums). Bonus applies once, won't stack.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Dynalar Xtra-Dex Smart Glove",
        "category": "Electronics",
        "description": "2 Cyberarm Option Slots, up to 5 Cyberfingers. Strap and plug to command. Action to put on/off. Requires Interface Plugs. Options in arm underneath inaccessible while worn. Cannot conceal.",
        "weight": 0.5,
        "value": 1000
    },
    {
        "name": "Esporma Environment Suit",
        "category": "Electronics",
        "description": "Body + Head. SP 8 each, self-repairing (1 SP/hr when no damage). Protects from radiation. 30 min internal O2, 1 hr refill from air. Magnetic seams, airtight.",
        "weight": 3,
        "value": 5000
    },
    {
        "name": "Hammered Industries Green Light Go Sniffer",
        "category": "Electronics",
        "description": "Insert wand into substance, read indicator. Action: analyze dose. Green = pure per database, red = impure. Does not identify substance.",
        "weight": 0.2,
        "value": 100
    },
    {
        "name": "Ion Cuffs",
        "category": "Tools",
        "description": "Restraint. Non-hardened cyberware in bound limb inoperable. BODY 13+ breaks easily.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "Master Mechanic's Tool Kit",
        "category": "Tools",
        "description": "Tech +4 Basic Tech, Cybertech, Land/Sea/Air Vehicle Tech, Electronics/Security Tech, Weaponstech for Maker. Counts as Thick Steel Cover. BODY 10+ to move without equipment.",
        "weight": 20,
        "value": 20000
    },
    {
        "name": "MiniMag Speakers by TelecTronics",
        "category": "Electronics",
        "description": "1 inch, magnetic. Wireless to linked Agent 100 m/yds. Variety of colors.",
        "weight": 0.1,
        "value": 50
    },
    {
        "name": "Optitech MagViewer",
        "category": "Electronics",
        "description": "Binoculars, detail to 800 m/yds. Complementary Skill for Single/Aimed Shot 51+ m/yds: +1 Attack (stacks with normal complementary bonus). Doesn't stack with Sniping Scope or TeleOptics.",
        "weight": 0.5,
        "value": 500
    },
    {
        "name": "SkidRow PackShield",
        "category": "Clothing",
        "description": "Backpack that unfolds into Bulletproof Shield (HP10). Businesswear appearance. Must equip in hand for protection. Cannot install in Popup Shield cyberware.",
        "weight": 1,
        "value": 100
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
    # Danger Gal Dossier: Micro Chrome
    {
        "name": "Smart Lens",
        "category": "Electronics",
        "description": "Contact lens or monocle. 1 Cybereye Option Slot. Install options like Cybereye (same cost). Pairing options not allowed. One per eye.",
        "weight": 0,
        "value": 500
    },
    # Core rulebook: generic quality-tier external cyberdecks
    {
        "name": "Excellent Quality Cyberdeck",
        "category": "Cyberdeck",
        "description": (
            "A high-end modular platform that Programs and Hardware are installed on for the purpose of "
            "Netrunning. This cyberdeck has 9 slots to install Programs and Hardware. Requires Interface "
            "Plugs and Neural Link for a Netrunner to operate. See Netrunning Section on pg. 195."
        ),
        "weight": 0.5,
        "value": 1000,
    },
    {
        "name": "Poor Quality Cyberdeck",
        "category": "Cyberdeck",
        "description": (
            "A cheap modular platform that Programs and Hardware are installed on for the purpose of "
            "Netrunning. This cyberdeck has 5 slots to install Programs and Hardware. Requires Interface "
            "Plugs and Neural Link for a Netrunner to operate. See Netrunning Section on pg. 195."
        ),
        "weight": 0.5,
        "value": 100,
    },
    {
        "name": "Standard Quality Cyberdeck",
        "category": "Cyberdeck",
        "description": (
            "Modular platform that Programs and Hardware are installed on for the purpose of Netrunning. "
            "This cyberdeck has 7 slots to install Programs and Hardware. Requires Interface Plugs and "
            "Neural Link for a Netrunner to operate. See Netrunning Section on pg. 195."
        ),
        "weight": 0.5,
        "value": 500,
    },
    # Core rulebook / premium catalog: cyberdeck hardware (install via +net/deck/install)
    {
        "name": "Backup Drive",
        "category": "Deck Option",
        "description": (
            "While installed on a Cyberdeck, a Backup Drive 'saves' Non-Black ICE Attacker, Defender, or Booster "
            "Programs that are destroyed by pulling them into the Backup Drive the instant before they meet their end. "
            "As a Meat Action, a Netrunner can re-install all Programs 'saved' by the Backup Drive onto their deck, "
            "if they have the Slots for them. If removed from a Cyberdeck, the Backup Drive erases its contents "
            "automatically. Restored Programs with once-per-Netrun restrictions and the like are restored in the "
            "exact state they were saved in, so you can't kill your own Armor to refresh it. Yeah, that means you. "
            "Takes 2 Hardware Option Slots. (Premium)"
        ),
        "weight": 0,
        "value": 100,
    },
    {
        "name": "DNA Lock",
        "category": "Deck Option",
        "description": (
            "A Cyberdeck with a DNA Lock can be locked and unlocked using a thumbprint, iris scan, blood sample, or "
            "any other biometric method desired. The method varies depending on the model of the DNA Lock. A locked "
            "Cyberdeck cannot be accessed without either its biometric key or a DV 17 Electronics/Security Tech Check. "
            "Takes 2 Hardware Option Slots. (Premium)"
        ),
        "weight": 0,
        "value": 100,
    },
    {
        "name": "Hardened Circuitry",
        "category": "Deck Option",
        "description": (
            "A Cyberdeck with Hardened Circuitry cannot be rendered temporarily disabled, rendered inoperable, or "
            "destroyed by EMP effects like pulses, or Non-Black ICE Program Effects. (Premium)"
        ),
        "weight": 0,
        "value": 100,
    },
    {
        "name": "Insulated Wiring",
        "category": "Deck Option",
        "description": (
            "A Cyberdeck with Insulated Wiring cannot catch fire or cause the user's clothing to catch fire as the "
            "result of a Program effect. (Premium)"
        ),
        "weight": 0,
        "value": 100,
    },
    {
        "name": "KRASH Barrier",
        "category": "Deck Option",
        "description": (
            "A Cyberdeck with a KRASH Barrier is immune to any Program Effect that force the Netrunner to Jack Out, "
            "safely or unsafely. Takes 2 Hardware Option Slots. (Premium)"
        ),
        "weight": 0,
        "value": 100,
    },
    {
        "name": "Range Upgrade",
        "category": "Deck Option",
        "description": (
            "A Cyberdeck with a Range Upgrade can connect to an access point from up to 8m away. (Premium)"
        ),
        "weight": 0,
        "value": 100,
    },
]

# Extend with Cyberpunk RED fashion items (core rulebook)
from world.fashion_data import build_fashion_gear_list
gears.extend(build_fashion_gear_list())

#Cyberdecks (External)
cyberdecks = [
    {
        "name": "Excellent Quality Cyberdeck",
        "description": (
            "A high-end modular platform that Programs and Hardware are installed on for the purpose of "
            "Netrunning. This cyberdeck has 9 slots to install Programs and Hardware. Requires Interface "
            "Plugs and Neural Link for a Netrunner to operate. See Netrunning Section on pg. 195."
        ),
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 9,
        "value": 1000,
    },
    {
        "name": "Poor Quality Cyberdeck",
        "description": (
            "A cheap modular platform that Programs and Hardware are installed on for the purpose of "
            "Netrunning. This cyberdeck has 5 slots to install Programs and Hardware. Requires Interface "
            "Plugs and Neural Link for a Netrunner to operate. See Netrunning Section on pg. 195."
        ),
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 5,
        "value": 100,
    },
    {
        "name": "Standard Quality Cyberdeck",
        "description": (
            "Modular platform that Programs and Hardware are installed on for the purpose of Netrunning. "
            "This cyberdeck has 7 slots to install Programs and Hardware. Requires Interface Plugs and "
            "Neural Link for a Netrunner to operate. See Netrunning Section on pg. 195."
        ),
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 7,
        "value": 500,
    },
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
        "description": "Kirama's premier offering. To go further than this, a Netrunner must find a custom build, or try another brand. Cyberdeck with 5 slots to install either Programs or Hardware. Any unsafe Jack Out is considered instead to be a safe Jack Out.",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 5,
        "value": 500,
    },
    {
        "name": "Kirama Entry Deck",
        "description": "Considered by many to be the safest bet on a low budget, and by others to be a trap which many novice Netrunners never grow out of. Cyberdeck with 5 slots that can only install Programs. Only one Attacker, Defender, Booster, and Black ICE Program each may be installed. Any unsafe Jack Out is considered instead to be a safe Jack Out.",
        "hardware_slots": 0,
        "program_slots": 5,
        "any_slots": 0,
        "value": 100,
    },
    {
        "name": "Kirama Training Deck",
        "description": "Every Netrunner's first Cyberdeck, but an unfortunate number's last Cyberdeck too. Cyberdeck with 5 slots that can only install Programs. While using this Cyberdeck, you must be within 2 m/yds of an access point to Jack In to a NET Architecture, and must remain within that distance to maintain connection. Additionally, whenever you would take damage directly to your brain when using this Cyberdeck, you take double that damage directly to your brain instead.",
        "hardware_slots": 0,
        "program_slots": 5,
        "any_slots": 0,
        "value": 20,
    },
    {
        "name": "Microtech Assault",
        "description": "If you can live within the stringent build restrictions of a Microtech Assault, then it's a paradise, not a prison. Cyberdeck with 4 slots that can only install Programs and 5 slots that can only install Hardware. Only Black ICE can be installed in the Cyberdeck's Program slots.",
        "hardware_slots": 5,
        "program_slots": 4,
        "any_slots": 0,
        "value": 500,
    },
    {
        "name": "Microtech Scout",
        "description": "Popular as a side-deck. Makes a great gift for the Netrunner who has everything. Everybody can find a use for another Microtech Scout. Cyberdeck with 5 slots to install either Programs or Hardware. Immediately after you Jack In, you can use the Pathfinder Interface Ability once without a NET Action.",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 5,
        "value": 500,
    },
    {
        "name": "Microtech Warrior",
        "description": "A hyper aggressive Cyberdeck that's all about going straight for the kill and jacking out. Cyberdeck with 7 slots that can only install Programs. Immediately after you Jack In, you can activate an Armor Program installed on your Cyberdeck without a NET Action.",
        "hardware_slots": 0,
        "program_slots": 7,
        "any_slots": 0,
        "value": 1000,
    },
    {
        "name": "Raven Microcyb Hummingbird",
        "description": "When you want to rely solely on your abilities, Raven Microcybernetics has you covered. Cyberdeck with 2 slots that can only install Hardware. While using this Cyberdeck, you have one additional NET Action every turn.",
        "hardware_slots": 2,
        "program_slots": 0,
        "any_slots": 0,
        "value": 1000,
    },
    {
        "name": "Raven Microcyb Kestrel 2",
        "description": "The Kestrel 2 is one of Raven Microcybernetics's best selling products, probably because Netrunners love to go fast. Cyberdeck with 7 slots that can only install Programs. Immediately after you Jack In, you can activate up to 2 Speedy Gonzalves Programs installed on your Cyberdeck without a NET Action.",
        "hardware_slots": 0,
        "program_slots": 7,
        "any_slots": 0,
        "value": 1000,
    },
    {
        "name": "Raven Microcyb Phoenix",
        "description": "Yes, you could buy a top of the line custom Cyberdeck for the same price, but just think of all the money you'll save not replacing those expensive Black ICE programs when they get Asp'd. Cyberdeck with 6 slots to install either Programs or Hardware. Whenever you safely Jack Out, any Programs that were destroyed in your cyberdeck during the netrun are restored to full working order.",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 6,
        "value": 1000,
    },
    {
        "name": "SGI Technologies Kerberos",
        "description": "Raw power in Cyberdeck form. Drag your enemies down to hell! Cyberdeck with 6 slots that can only install Programs, and 5 slots that can only install Hardware. Only Hellhound Black ICE can be installed in the Cyberdeck's Program slots.",
        "hardware_slots": 5,
        "program_slots": 6,
        "any_slots": 0,
        "value": 1000,
    },
    {
        "name": "SGI Technologies Verdant Knight",
        "description": "Some like it for its simplicity, as a tool against Anti-Program Black ICE heavy NET Architectures. Cyberdeck with 9 slots that can only install Programs. Only Sword and Shield Programs can be installed in those Program slots.",
        "hardware_slots": 0,
        "program_slots": 9,
        "any_slots": 0,
        "value": 500,
    },
    {
        "name": "SGI Technologies Warlock's Book",
        "description": "If all you're doing is sliding through NET Architectures, you don't need anything else. Cyberdeck with 9 slots to install either Programs or Hardware. No Attacker or Black ICE Program may be installed.",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 9,
        "value": 500,
    },
    {
        "name": "Zetatech Kaliya",
        "description": "A remarkably affordable Cyberdeck with a snake-like segmented cylindrical form factor. Cyberdeck with 3 slots that can only install Programs and 6 slots to install either Programs or Hardware. The 3 slots that can only install Programs can only install Flak. No Defender Program other than Flak can be installed in any slot. No Black ICE other than Asp may be installed in any slot.",
        "hardware_slots": 0,
        "program_slots": 3,
        "any_slots": 6,
        "value": 500,
    },
    {
        "name": "Zetatech MicroMate",
        "description": "A remarkable portable cyberdeck. Rumor has it that the form factor was only possible by removing important safety features from the Cyberdeck. Cyberdeck with 9 slots to install either Programs or Hardware. No Defender Program can be installed. Whenever you would take damage directly to your brain when using this Cyberdeck, double that damage.",
        "hardware_slots": 0,
        "program_slots": 0,
        "any_slots": 9,
        "value": 500,
    },
    {
        "name": "Zetatech Parraline 6000",
        "description": "Zetatech's flagship product, the Parraline 6000 is made exclusively for the Hardware obsessed. Cyberdeck with 3 slots that can only install Programs and 6 slots that can only install Hardware.",
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
        'category', 'clip', 'description', 'attachment_slots', 'range_dvs',
        'weapon_type', 'quality'
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
    allowed_keys = {
        "damage", "rof", "hands", "concealable", "weight", "value",
        "category", "clip", "description", "attachment_slots", "range_dvs",
        "weapon_type", "quality",
    }
    # Remove legacy "Melee Weapon (X)" entries; we use "X Melee Weapon" instead
    legacy_melee_names = [
        "Melee Weapon (Light)",
        "Melee Weapon (Medium)",
        "Melee Weapon (Heavy)",
        "Melee Weapon (Very Heavy)",
    ]
    deleted, _ = Weapon.objects.filter(name__in=legacy_melee_names).delete()
    if deleted:
        logger.info(f"Removed {deleted} legacy melee weapon(s) from database.")
    created = 0
    for weapon_data in weapons:
        name = weapon_data.get("name")
        if not name:
            continue
        defaults = {k: v for k, v in weapon_data.items() if k in allowed_keys and k != "name"}
        # Weapon.clip is NOT NULL; ensure we never pass None
        if "clip" in defaults and defaults["clip"] is None:
            defaults["clip"] = 0
        obj, was_created = Weapon.objects.get_or_create(name=name, defaults=defaults)
        if was_created:
            created += 1
        else:
            changed = False
            for key in allowed_keys:
                if key in weapon_data and getattr(obj, key, None) != weapon_data[key]:
                    setattr(obj, key, weapon_data[key])
                    changed = True
            if changed:
                obj.save()
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
    created = 0
    for cyberdeck_data in cyberdecks:
        obj, was_created = Cyberdeck.objects.update_or_create(
            name=cyberdeck_data["name"],
            defaults={
                "description": cyberdeck_data.get("description", ""),
                "hardware_slots": cyberdeck_data.get("hardware_slots", 0),
                "program_slots": cyberdeck_data.get("program_slots", 0),
                "any_slots": cyberdeck_data.get("any_slots", 0),
                "value": cyberdeck_data.get("value", 0),
            },
        )
        if was_created:
            created += 1
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

def _parse_damage_dice(damage_str):
    """Parse '2d6' or '3d6' format, return number of dice."""
    if not damage_str:
        return 0
    try:
        parts = str(damage_str).lower().split("d")
        return int(parts[0]) if parts else 0
    except (ValueError, IndexError):
        return 0


def get_popup_melee_weapons():
    """One-handed melee weapons only (no Very Heavy Melee, no 2-handed)."""
    return [w for w in weapons if w.get("category") == "melee" and w.get("hands", 2) == 1]


def get_popup_ranged_weapons():
    """One-handed handguns/SMGs only (no rifles, assault rifles, heavy_weapons)."""
    return [w for w in weapons if w.get("category") == "handgun" and w.get("hands", 2) == 1]


def get_weapon_by_name(name):
    """Look up weapon from equipment_data by name (case-insensitive)."""
    name_lower = (name or "").strip().lower()
    for w in weapons:
        if (w.get("name") or "").strip().lower() == name_lower:
            return w
    return None


def get_weapon_damage_dice(weapon_name):
    """Get damage dice count for a weapon from equipment_data."""
    w = get_weapon_by_name(weapon_name)
    if not w:
        return 0
    return _parse_damage_dice(w.get("damage", ""))


def populate_all_equipment():
    populate_weapons()
    populate_armor()
    populate_gear()
    populate_cyberware()
    populate_ammunition()
    populate_cyberdecks()
    populate_vehicles()
    print("All equipment populated successfully.")
