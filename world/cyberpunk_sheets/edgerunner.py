import random, logging
import traceback
from world.cyberpunk_constants import ROLES, STATS, ROLE_SKILLS, EQUIPMENT, ROLE_STAT_TABLES, ROLE_CYBERWARE
from world.cyberpunk_constants import LANGUAGES as CYBERPUNK_LANGUAGES
from world.inventory.models import Inventory, Weapon, Armor, Gear, CyberwareInstance, Ammunition, AmmoType
from world.equipment_data import weapons, armors, gears, ammunition
from world.equipment_data import weapons as weapon_data, armors as armor_data, gears as gear_data
from world.cyberware.cyberware_data import CYBERWARE_DATA
from world.cyberware.models import Cyberware, CYBERWARE_HUMANITY_LOSS, CYBERWARE_COSTS
from world.cyberware.utils import calculate_humanity_loss
from evennia.utils import logger
from django.core.exceptions import MultipleObjectsReturned

logger = logging.getLogger('cyberpunk.chargen')

from world.cyberpunk_sheets.services import CharacterSheetMoneyService

class EdgerunnerChargen:
    @classmethod
    def create_character(cls, sheet, role, method, full_name):
        logger.info(f"Starting create_character for {full_name}, role: {role}")
        try:
            # Reset the character sheet
            cls.reset_character(sheet)
            
            # Set the role
            sheet.role = role
            sheet.save()
            
            result = cls.edgerunner_chargen(sheet, role, full_name)
            logger.info(f"Edgerunner chargen completed for {full_name}")
            
            # Log all attributes of the sheet
            for attr, value in vars(sheet).items():
                logger.info(f"Sheet attribute {attr}: {value}")
            
            # Calculate remaining skill and stat points
            remaining_stat_points = cls.calculate_remaining_stat_points(sheet)
            remaining_skill_points = cls.calculate_remaining_skill_points(sheet, role)
            
            # Add 500 Eurodollars to the character's account
            new_balance = CharacterSheetMoneyService.add_money(sheet, 500)
            logger.info(f"Added 500 Eurodollars to sheet ID {sheet.id}. New balance: {new_balance}")
            
            # Ensure the character's db attribute is updated with the sheet ID
            character = sheet.character
            if character:
                character.db.character_sheet_id = sheet.id
                logger.info(f"Set character_sheet_id to {sheet.id} for character {character.name}")
            else:
                logger.warning(f"No character associated with sheet ID {sheet.id}")
            
            sheet.save()
            logger.info(f"Sheet saved for {full_name}")
            
            # Prepare the final message
            final_message = (
                f"Character created using the Edgerunner method for role: {role}.\n"
                f"You have {remaining_stat_points} stat points and {remaining_skill_points} skill points left to allocate.\n"
                f"500 Eurodollars have been added to your account and default inventory has been set.\n"
                f"Use 'sheet' to view your full character details, 'inv' to view your inventory"
                f"and 'inv/balance' to check your money."
            )
            
            return final_message
        except Exception as e:
            logger.error(f"Error in create_character: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error args: {e.args}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    @classmethod
    def calculate_remaining_stat_points(cls, sheet):
        total_stats = sum([getattr(sheet, stat.lower()) for stat in STATS])
        return max(0, 62 - total_stats)  # Assuming 62 is the total stat points available

    @classmethod
    def calculate_remaining_skill_points(cls, sheet, role):
        role_skills = ROLE_SKILLS.get(role, [])
        total_skills = sum([getattr(sheet, skill.lower()) for skill in role_skills])
        return max(0, 86 - total_skills)  # Assuming 86 is the total skill points available

    @classmethod
    def edgerunner_chargen(cls, sheet, role, full_name):
        logger.info(f"Starting edgerunner_chargen for {full_name}, role: {role}")
        try:
            cls.assign_stats(sheet, role)
            logger.info("Stats assigned")
            
            cls.assign_skills(sheet, role)
            logger.info("Skills assigned")
            
            cls.assign_languages(sheet, role)
            logger.info("Languages assigned")
            
            cls.assign_gear(sheet, role)
            logger.info(f"Gear assigned for role: {role}")

            cls.assign_cyberware(sheet, role)
            logger.info(f"Cyberware assigned for role: {role}")

            cls.recalculate_humanity(sheet)
            logger.info("Humanity recalculated")

            sheet.recalculate_derived_stats()
            logger.info("Derived stats recalculated")

            # Log all attributes of the sheet again
            for attr, value in vars(sheet).items():
                logger.info(f"Final sheet attribute {attr}: {value}")

            return f"Character created using the Edgerunner method for role: {role}.\nUse 'sheet' to view your full character details."
        except Exception as e:
            logger.error(f"Error in edgerunner_chargen: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error args: {e.args}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    @classmethod
    def complete_package_chargen(cls, sheet):
        sheet.attribute_points = 62
        sheet.skill_points = 60
        sheet.eurodollars = 2550

        default_skills = [
            'athletics', 'brawling', 'concentration', 'conversation', 'education',
            'evasion', 'first_aid', 'human_perception', 'local_expert', 'perception',
            'persuasion', 'stealth'
        ]
        for skill in default_skills:
            setattr(sheet, skill, 2)
            sheet.skill_points -= 2

        sheet.add_language("Streetslang", 2)
        sheet.skill_points -= 2

        sheet.save()
        return "Character created using the Complete Package method. Use 'sheet' to view your character details."

    @classmethod
    def generate_stat_table(cls, role):
        return ROLE_STAT_TABLES.get(role, [])

    @classmethod
    def calculate_final_stats(cls, stat_templates):
        final_stats = []
        rows_selected = []
        for _ in range(10):  # For each of the 10 stats
            row = random.choice(stat_templates)
            stat = random.choice(row)
            try:
                stat_value = int(stat)  # Ensure the stat is an integer
            except ValueError:
                logger.error(f"Invalid stat value: {stat}")
                stat_value = 1  # Default to 1 if conversion fails
            final_stats.append(stat_value)
            rows_selected.append(stat_templates.index(row) + 1)
            row.remove(stat)
            if not row:
                stat_templates.remove(row)
        return final_stats, rows_selected

    @classmethod
    def assign_stats(cls, sheet, role):
        stat_templates = cls.generate_stat_table(role)
        final_stats, rows_selected = cls.calculate_final_stats(stat_templates)
        
        for stat, value in zip(STATS, final_stats):
            if isinstance(stat, str):
                stat_name = stat.lower()
            elif isinstance(stat, dict):
                stat_name = stat['name'].lower()
            else:
                logger.error(f"Unexpected stat type: {type(stat)}")
                continue
            
            try:
                value = int(value)  # Ensure the value is an integer
                setattr(sheet, stat_name, value)
                logger.info(f"Set {stat_name} to {value}")
            except ValueError:
                logger.error(f"Invalid value for {stat_name}: {value}")
                # Set a default value (e.g., 1) if conversion fails
                setattr(sheet, stat_name, 1)

    @classmethod
    def assign_skills(cls, sheet, role):
        role_skills = ROLE_SKILLS.get(role, {})
        for skill, value in role_skills.items():
            setattr(sheet, skill.lower(), value)

    @classmethod
    def assign_languages(cls, sheet, role):
        sheet.add_language("Streetslang", 4)
        logger.info(f"Language list: {sheet.language_list}")
        known_languages = [lang['name'].lower() if isinstance(lang, dict) else lang.lower() for lang in sheet.language_list]
        available_languages = [lang for lang in CYBERPUNK_LANGUAGES if lang.lower() not in known_languages]
        logger.info(f"Known languages: {known_languages}")
        if available_languages:
            random_lang = random.choice(available_languages)
            random_level = random.randint(1, 3)
            sheet.add_language(random_lang, random_level)

    @staticmethod
    def assign_gear(sheet, role):
        logger.info(f"Starting assign_gear for role: {role}")
        from world.inventory.models import Inventory, Weapon, Armor, Gear, Ammunition, AmmoType
        
        # Ensure the character has an inventory
        inventory, created = Inventory.objects.get_or_create(character=sheet)
        
        # Clear existing inventory
        inventory.weapons.clear()
        inventory.armor.clear()
        inventory.gear.clear()
        inventory.ammunition.clear()
        
        role_equipment = EQUIPMENT.get(role, {})
        
        # Assign weapons
        for weapon_name in role_equipment.get('weapons', []):
            weapon_stats = next((w for w in weapon_data if w['name'] == weapon_name), None)
            if weapon_stats:
                weapon, created = Weapon.objects.get_or_create(
                    name=weapon_name,
                    defaults={
                        'damage': weapon_stats['damage'],
                        'rof': weapon_stats['rof'],
                        'hands': weapon_stats['hands'],
                        'concealable': weapon_stats['concealable'],
                        'weight': weapon_stats['weight'],
                        'value': weapon_stats['value']
                    }
                )
                inventory.weapons.add(weapon)
                logger.info(f"Added weapon: {weapon_name}")
        
        # Assign armor
        for armor_name in role_equipment.get('armor', []):
            armor_stats = next((a for a in armor_data if a['name'] == armor_name), None)
            if armor_stats:
                armor, created = Armor.objects.get_or_create(
                    name=armor_name,
                    defaults={
                        'sp': armor_stats['sp'],
                        'ev': armor_stats['ev'],
                        'locations': armor_stats['locations']
                    }
                )
                inventory.armor.add(armor)
                logger.info(f"Added armor: {armor_name}")
        
        # Assign gear
        for gear_name in role_equipment.get('gear', []):
            gear_stats = next((g for g in gear_data if g['name'] == gear_name), None)
            if gear_stats:
                gear, created = Gear.objects.get_or_create(
                    name=gear_name,
                    defaults={
                        'category': gear_stats['category'],
                        'description': gear_stats['description'],
                        'weight': gear_stats['weight'],
                        'value': gear_stats['value']
                    }
                )
                inventory.gear.add(gear)
                logger.info(f"Added gear: {gear_name}")
        
        # Assign ammunition
        for weapon in inventory.weapons.all():
            weapon_type = weapon.name.split()[-1]  # Get the last word of the weapon name
            ammo = next((a for a in ammunition if a['weapon_type'] == weapon_type), None)
            if ammo:
                ammo_obj, created = Ammunition.objects.get_or_create(
                    name=ammo['name'],
                    defaults={
                        'ammo_type': getattr(AmmoType, ammo['ammo_type']),
                        'weapon_type': ammo['weapon_type'],
                        'damage_modifier': ammo['damage_modifier'],
                        'armor_piercing': ammo['armor_piercing'],
                        'description': ammo['description'],
                        'cost': ammo['cost'],
                        'quantity': 50  # Give 50 rounds of ammo
                    }
                )
                if not created:
                    # If the ammo already exists, update its quantity
                    ammo_obj.quantity += 50
                    ammo_obj.save()
                inventory.ammunition.add(ammo_obj)
                logger.info(f"Added ammunition: {ammo_obj.name}")
        
        logger.info("Gear assignment completed")

    @staticmethod
    def assign_cyberware(sheet, role):
        logger.info(f"Starting assign_cyberware for role: {role}")
        from world.cyberware.models import Cyberware, CyberwareInstance
        
        # Clear existing cyberware
        CyberwareInstance.objects.filter(character=sheet).delete()
        
        role_cyberware = ROLE_CYBERWARE.get(role, [])
        
        for cyberware_name in role_cyberware:
            cyberware, created = Cyberware.objects.get_or_create(name=cyberware_name)
            CyberwareInstance.objects.create(character=sheet, cyberware=cyberware)
            logger.info(f"Added cyberware: {cyberware_name}")
        
        logger.info("Cyberware assignment completed")
        sheet.calculate_humanity_loss()

    @staticmethod
    def assign_cyberware(sheet, role):
        logger.info(f"Starting assign_cyberware for role: {role}")
        from world.cyberware.models import Cyberware
        from world.inventory.models import CyberwareInstance
        
        role_cyberware = {
            "Rockerboy": ["Audio Recorder", "Chemskin", "Cyberaudio Suite", "Techhair"],
            "Solo": ["Biomonitor", "Neural Link", "Sandevistan", "Wolvers"],
            "Netrunner": ["Interface Plugs", "Neural Link", "Shift Tacts"],
            "Tech": ["Cybereye", "MicroOptics", "Skinwatch", "Tool Hand"],
            "Medtech": ["Biomonitor", "Cybereye", "Nasal Filters", "TeleOptics"],
            "Media": ["Amplified Hearing", "Cyberaudio Suite", "Light Tattoo"],
            "Lawman": ["Hidden Holster", "Subdermal Pocket"],
            "Exec": ["Biomonitor", "Cyberaudio Suite", "Internal Agent", "Toxin Binders"],
            "Fixer": ["Cyberaudio Suite", "Internal Agent", "Subdermal Pocket", "Voice Stress Analyzer"],
            "Nomad": ["Interface Plugs", "Neural Link"]
        }

        cyberware_list = role_cyberware.get(role, [])
        logger.info(f"Cyberware list: {cyberware_list}")
        
        for item_name in cyberware_list:
            logger.info(f"Processing cyberware: {item_name}")
            cyberware_item, created = Cyberware.objects.get_or_create(name=item_name)
            if created:
                # Set default values for new cyberware items
                cyberware_item.type = "Implant"
                cyberware_item.description = f"{item_name} for {role}"
                cyberware_item.humanity_loss = 14 // len(cyberware_list)  # This is a placeholder calculation
                cyberware_item.save()
            
            CyberwareInstance.objects.create(
                cyberware=cyberware_item,
                character=sheet,
                installed=True
            )
            logger.info(f"Added cyberware instance: {item_name}")

        logger.info("About to calculate humanity loss")
        sheet.calculate_humanity_loss()
        logger.info(f"Humanity loss calculated. New humanity: {sheet.humanity}")
        
        logger.info(f"Cyberware assignment completed for role: {role}. Total humanity loss: {sheet.total_cyberware_humanity_loss}")

    @staticmethod
    def recalculate_humanity(sheet):
        logger.info("Starting recalculate_humanity")
        sheet.calculate_humanity_loss()
        logger.info(f"Recalculated humanity for sheet ID: {sheet.id}. New humanity: {sheet.humanity}, Total loss: {sheet.total_cyberware_humanity_loss}")

    @classmethod
    def reset_character(cls, sheet):
        # Reset all attributes to 1
        for stat in STATS:
            setattr(sheet, stat.lower(), 1)
        
        # Reset all skills to 0
        for skill in set(skill for role_skills in ROLE_SKILLS.values() for skill in role_skills):
            setattr(sheet, skill.lower(), 0)
        
        # Clear languages
        sheet.character_languages.all().delete()
        
        # Clear inventory
        if hasattr(sheet, 'inventory'):
            sheet.inventory.weapons.all().delete()
            sheet.inventory.armor.all().delete()
            sheet.inventory.gear.all().delete()
        
        # Clear cyberware
        CyberwareInstance.objects.filter(character=sheet).delete()
        
        # Reset money
        sheet.eurodollars = 0
        
        # Reset derived stats
        sheet.initialize_humanity()
        sheet.recalculate_derived_stats()
        
        # Reset role
        sheet.role = ""
        
        # Reset other attributes
        sheet.total_cyberware_humanity_loss = 0
        sheet._max_hp = 10
        sheet._current_hp = 10
        
        sheet.save()
        return sheet

    @classmethod
    def clean_duplicate_gear(cls):
        from django.db.models import Count
        from world.inventory.models import Inventory

        duplicate_gear = Gear.objects.values('name').annotate(name_count=Count('name')).filter(name_count__gt=1)
        for item in duplicate_gear:
            gear_items = Gear.objects.filter(name=item['name']).order_by('id')
            primary_item = gear_items.first()
            for duplicate_item in gear_items[1:]:
                # Update all inventories that use the duplicate item
                inventories = Inventory.objects.filter(gear=duplicate_item)
                for inventory in inventories:
                    inventory.gear.remove(duplicate_item)
                    inventory.gear.add(primary_item)
                duplicate_item.delete()
        logger.info("Cleaned up duplicate gear entries")