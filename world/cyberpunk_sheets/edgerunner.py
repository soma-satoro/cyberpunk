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
from world.cyberpunk_sheets.services import CharacterMoneyService

logger = logging.getLogger('cyberpunk.chargen')

class EdgerunnerChargen:
    @classmethod
    def create_character(cls, character, role, method, full_name):
        logger.info(f"Starting create_character for {full_name}, role: {role}")
        try:
            # Determine if we have a character object or a sheet
            if hasattr(character, 'db'):
                # We have a character typeclass - update directly and also mirror to sheet
                cls.reset_character_typeclass(character)
                character.db.role = role
                character.db.full_name = full_name
                
                # If there's also a character sheet, mirror the changes
                if hasattr(character, 'character_sheet') and character.character_sheet:
                    sheet = character.character_sheet
                    cls.reset_character(sheet)
                    sheet.role = role
                    sheet.full_name = full_name
                    sheet.save()
                
                result = cls.edgerunner_chargen_for_typeclass(character, role, full_name)
            else:
                # We have a character sheet - legacy method
                sheet = character
                cls.reset_character(sheet)
                sheet.role = role
                sheet.full_name = full_name
                sheet.save()
                
                result = cls.edgerunner_chargen(sheet, role, full_name)
                
                # If there's a character object associated, mirror the changes
                if hasattr(sheet, 'character') and sheet.character:
                    cls.mirror_sheet_to_typeclass(sheet, sheet.character)
            
            logger.info(f"Edgerunner chargen completed for {full_name}")
            
            # Add money to the character
            if hasattr(character, 'db'):
                CharacterMoneyService.add_money(character, 500)
                remaining_stat_points = cls.calculate_remaining_stat_points_typeclass(character)
                remaining_skill_points = cls.calculate_remaining_skill_points_typeclass(character, role)
            else:
                CharacterMoneyService.add_money(character, 500)
                remaining_stat_points = cls.calculate_remaining_stat_points(character)
                remaining_skill_points = cls.calculate_remaining_skill_points(character, role)
            
            logger.info(f"Added 500 Eurodollars to character {full_name}")
            
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
    def mirror_sheet_to_typeclass(cls, sheet, character):
        """Mirror character sheet data to typeclass attributes"""
        if not hasattr(character, 'db'):
            return
            
        # Basic info
        character.db.full_name = sheet.full_name
        character.db.role = sheet.role
        character.db.handle = sheet.handle
        character.db.gender = sheet.gender
        character.db.age = sheet.age
        character.db.hometown = sheet.hometown
        character.db.height = sheet.height
        character.db.weight = sheet.weight
        
        # Stats
        character.db.intelligence = sheet.intelligence
        character.db.reflexes = sheet.reflexes
        character.db.dexterity = sheet.dexterity
        character.db.technology = sheet.technology
        character.db.cool = sheet.cool
        character.db.willpower = sheet.willpower
        character.db.luck = sheet.luck
        character.db.current_luck = sheet.current_luck
        character.db.move = sheet.move
        character.db.body = sheet.body
        character.db.empathy = sheet.empathy
        
        # Derived stats
        character.db.max_hp = sheet._max_hp
        character.db.current_hp = sheet._current_hp
        character.db.humanity = sheet.humanity
        character.db.humanity_loss = sheet.humanity_loss
        character.db.total_cyberware_humanity_loss = sheet.total_cyberware_humanity_loss
        character.db.death_save = sheet.body
        character.db.serious_wounds = sheet.body
        
        # Economy
        character.db.eurodollars = sheet.eurodollars
        character.db.reputation_points = sheet.reputation_points
        character.db.rep = sheet.rep
        
        # Copy skills
        skills = {}
        for skill_name in ROLE_SKILLS.get(sheet.role, {}):
            value = getattr(sheet, skill_name, 0)
            skills[skill_name] = value
            
        character.db.skills = skills
            
        logger.info(f"Mirrored character sheet data to typeclass for {sheet.full_name}")

    @classmethod
    def reset_character_typeclass(cls, character):
        """Reset a character typeclass for chargen"""
        # Reset basic info
        character.db.full_name = character.name
        character.db.role = ""
        character.db.handle = ""
        character.db.gender = ""
        character.db.age = 0
        character.db.hometown = ""
        character.db.height = 0
        character.db.weight = 0
        
        # Reset stats (each to 1)
        for stat in STATS:
            if isinstance(stat, str):
                stat_name = stat.lower()
            elif isinstance(stat, dict):
                stat_name = stat['name'].lower()
            else:
                continue
            setattr(character.db, stat_name, 1)
        
        # Reset role abilities and skills (each to 0)
        character.db.skills = {}
        
        # Reset derived stats
        character.db.max_hp = 10
        character.db.current_hp = 10
        character.db.humanity = 10  # Will be recalculated based on empathy
        character.db.humanity_loss = 0
        character.db.total_cyberware_humanity_loss = 0
        character.db.death_save = 1  # Based on body stat
        character.db.serious_wounds = 1  # Based on body stat
        
        # Reset economy
        character.db.eurodollars = 0
        character.db.reputation_points = 0
        character.db.rep = 0
        
        # Reset languages (using separate method)
        character.db.languages = {}
        
        # Also clear the character sheet if it exists
        if hasattr(character, 'character_sheet') and character.character_sheet:
            cls.reset_character(character.character_sheet)
            
        logger.info(f"Reset character typeclass for {character.name}")

    @classmethod
    def calculate_remaining_stat_points_typeclass(cls, character):
        """Calculate remaining stat points for a typeclass character"""
        total_stats = sum([getattr(character.db, stat.lower(), 0) for stat in STATS 
                           if isinstance(stat, str) or 
                           (isinstance(stat, dict) and isinstance(stat.get('name'), str))])
        return max(0, 62 - total_stats)

    @classmethod
    def calculate_remaining_skill_points_typeclass(cls, character, role):
        """Calculate remaining skill points for a typeclass character"""
        role_skills = ROLE_SKILLS.get(role, {})
        if hasattr(character.db, 'skills'):
            total_skills = sum([character.db.skills.get(skill, 0) for skill in role_skills])
        else:
            total_skills = 0
        return max(0, 86 - total_skills)

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
    def edgerunner_chargen_for_typeclass(cls, character, role, full_name):
        """Create an Edgerunner character using the typeclass directly"""
        logger.info(f"Starting edgerunner_chargen_for_typeclass for {full_name}, role: {role}")
        try:
            cls.assign_stats_to_typeclass(character, role)
            logger.info("Stats assigned to typeclass")
            
            cls.assign_skills_to_typeclass(character, role)
            logger.info("Skills assigned to typeclass")
            
            cls.assign_languages_to_typeclass(character, role)
            logger.info("Languages assigned to typeclass")
            
            cls.assign_gear_to_typeclass(character, role)
            logger.info(f"Gear assigned for role: {role}")

            cls.assign_cyberware_to_typeclass(character, role)
            logger.info(f"Cyberware assigned for role: {role}")

            cls.recalculate_humanity_for_typeclass(character)
            logger.info("Humanity recalculated for typeclass")

            cls.recalculate_derived_stats_for_typeclass(character)
            logger.info("Derived stats recalculated for typeclass")

            return f"Character created using the Edgerunner method for role: {role}.\nUse 'sheet' to view your full character details."
        except Exception as e:
            logger.error(f"Error in edgerunner_chargen_for_typeclass: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    @classmethod
    def assign_stats_to_typeclass(cls, character, role):
        """Assign stats to character typeclass"""
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
                setattr(character.db, stat_name, value)
                logger.info(f"Set typeclass {stat_name} to {value}")
            except ValueError:
                logger.error(f"Invalid value for {stat_name}: {value}")
                # Set a default value (e.g., 1) if conversion fails
                setattr(character.db, stat_name, 1)

    @classmethod
    def assign_skills_to_typeclass(cls, character, role):
        """Assign skills to character typeclass"""
        role_skills = ROLE_SKILLS.get(role, {})
        skills_dict = {}
        
        for skill, value in role_skills.items():
            skills_dict[skill.lower()] = value
            
        character.db.skills = skills_dict
        logger.info(f"Assigned {len(skills_dict)} skills to character typeclass")

    @classmethod
    def assign_languages_to_typeclass(cls, character, role):
        """Assign languages to character typeclass"""
        # Create languages dictionary if it doesn't exist
        if not hasattr(character.db, 'languages'):
            character.db.languages = {}
            
        # Add Streetslang
        character.db.languages['Streetslang'] = 4
        
        # Get current language list
        languages = character.db.languages
        known_languages = [lang.lower() for lang in languages.keys()]
        
        # Find available languages not already known
        available_languages = [lang for lang in CYBERPUNK_LANGUAGES if lang.lower() not in known_languages]
        
        # Add a random language
        if available_languages:
            random_lang = random.choice(available_languages)
            random_level = random.randint(1, 3)
            character.db.languages[random_lang] = random_level
            logger.info(f"Added language {random_lang} (level {random_level}) to character")
            
            # Also update any character sheet that exists
            if hasattr(character, 'character_sheet') and character.character_sheet:
                for lang, level in character.db.languages.items():
                    character.character_sheet.add_language(lang, level)

    @classmethod
    def assign_gear_to_typeclass(cls, character, role):
        """Assign gear to character typeclass directly"""
        logger.info(f"Starting assign_gear_to_typeclass for role: {role}")
        from world.inventory.models import Inventory, Weapon, Armor, Gear, Ammunition, AmmoType
        
        # Get or create the inventory for this character
        inventory, created = Inventory.objects.get_or_create(
            character_object=character,
            defaults={}
        )
        
        # If we also have a character sheet, link it
        if hasattr(character, 'character_sheet') and character.character_sheet:
            inventory.character = character.character_sheet
            inventory.save()
        
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
        
        logger.info("Gear assignment for typeclass completed")

    @classmethod
    def assign_cyberware_to_typeclass(cls, character, role):
        """Assign cyberware to character typeclass"""
        logger.info(f"Starting assign_cyberware_to_typeclass for role: {role}")
        from world.cyberware.models import Cyberware
        from world.inventory.models import CyberwareInstance
        
        # Clear existing cyberware
        CyberwareInstance.objects.filter(character_object=character).delete()
        
        # Also clear any attached to character sheet
        if hasattr(character, 'character_sheet') and character.character_sheet:
            CyberwareInstance.objects.filter(character_sheet=character.character_sheet).delete()
        
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
            
            # Create instance linked to character typeclass
            instance = CyberwareInstance.objects.create(
                cyberware=cyberware_item,
                character_object=character,
                installed=True
            )
            
            # If character sheet exists, create a link to it as well
            if hasattr(character, 'character_sheet') and character.character_sheet:
                instance.character_sheet = character.character_sheet
                instance.save()
                
            logger.info(f"Added cyberware instance: {item_name}")

        logger.info("About to calculate humanity loss")
        cls.recalculate_humanity_for_typeclass(character)
        logger.info(f"Humanity loss calculated. New humanity: {character.db.humanity}")

    @classmethod
    def recalculate_humanity_for_typeclass(cls, character):
        """Recalculate humanity for character typeclass"""
        from world.inventory.models import CyberwareInstance
        
        # Get all installed cyberware
        cyberware_instances = CyberwareInstance.objects.filter(
            character_object=character,
            installed=True
        )
        
        # Calculate total humanity loss
        total_humanity_loss = sum(cw.cyberware.humanity_loss for cw in cyberware_instances)
        
        # Store total loss
        character.db.total_cyberware_humanity_loss = total_humanity_loss
        
        # Calculate humanity based on empathy
        if not hasattr(character.db, 'empathy'):
            character.db.empathy = 1
            
        character.db.humanity = max(0, character.db.empathy * 10 - total_humanity_loss)
        
        # Recalculate empathy if humanity reduction is significant
        if character.db.empathy * 10 <= total_humanity_loss:
            character.db.empathy = max(1, character.db.humanity // 10)
            
        logger.info(f"Recalculated humanity for {character.name}: {character.db.humanity}")
        
        # Also update character sheet if it exists
        if hasattr(character, 'character_sheet') and character.character_sheet:
            character.character_sheet.calculate_humanity_loss()

    @classmethod
    def recalculate_derived_stats_for_typeclass(cls, character):
        """Recalculate derived stats for character typeclass"""
        # Calculate max HP based on body and willpower
        if not hasattr(character.db, 'body'):
            character.db.body = 1
        if not hasattr(character.db, 'willpower'):
            character.db.willpower = 1
            
        character.db.max_hp = 10 + (5 * ((character.db.body + character.db.willpower) // 2))
        
        # Set current HP to max if not set
        if not hasattr(character.db, 'current_hp') or character.db.current_hp == 0:
            character.db.current_hp = character.db.max_hp
        
        # Cap current HP at max
        character.db.current_hp = min(character.db.current_hp, character.db.max_hp)
        
        # Set death save and serious wounds based on body
        character.db.death_save = character.db.body
        character.db.serious_wounds = character.db.body
        
        logger.info(f"Recalculated derived stats for {character.name}")
        
        # Also update character sheet if it exists
        if hasattr(character, 'character_sheet') and character.character_sheet:
            character.character_sheet.recalculate_derived_stats()

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
                character_sheet=sheet,
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
        CyberwareInstance.objects.filter(character_sheet=sheet).delete()
        
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