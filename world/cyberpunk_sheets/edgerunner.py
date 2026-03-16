import random, logging
import traceback
from world.cyberpunk_constants import ROLES, STATS, ROLE_SKILLS, ROLE_SKILL_NAME_MAP, EQUIPMENT, EQUIPMENT_OR_CHOICES, ROLE_STAT_TABLES, ROLE_CYBERWARE
DOUBLE_COST_SKILLS = ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics', 'paramedic']
from world.cyberpunk_constants import LANGUAGES as CYBERPUNK_LANGUAGES
from world.inventory.models import Inventory, Weapon, Armor, Gear, CyberwareInstance, Ammunition, AmmoType
from world.equipment_data import weapons, armors, gears, ammunition, cyberdecks as cyberdecks_data
from world.equipment_data import weapons as weapon_data, armors as armor_data, gears as gear_data
from world.chargen_constants import (
    FASHION_BUDGET,
    FASHION_ITEM_NAMES,
    NETRUNNER_7_SLOT_CYBERDECKS,
)
from world.cyberware.cyberware_data import CYBERWARE_DATA
from world.cyberware.models import Cyberware, CYBERWARE_HUMANITY_LOSS, CYBERWARE_COSTS
from world.cyberware.utils import calculate_humanity_loss
from evennia.utils import logger
from django.core.exceptions import MultipleObjectsReturned
from world.cyberpunk_sheets.services import CharacterMoneyService
from typeclasses.npcs import is_npc

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

            # Edgerunners get 500 eb extra to spend or keep (per rulebook p. 98)
            _, fashion_cost = cls.calculate_edgerunner_package_cost_split(role)
            CharacterMoneyService.add_money(character, 500)

            # Fashion budget: 800 eb use-it-or-lose-it (reduced by fashion items in package)
            sheet = character.character_sheet if hasattr(character, 'character_sheet') and character.character_sheet else character
            if hasattr(sheet, 'fashion_budget_remaining'):
                sheet.fashion_budget_remaining = max(0, FASHION_BUDGET - fashion_cost)
                sheet.save(skip_recalculation=True)

            if hasattr(character, 'db'):
                remaining_stat_points = cls.calculate_remaining_stat_points_typeclass(character)
                remaining_skill_points = cls.calculate_remaining_skill_points_typeclass(character, role)
            else:
                remaining_stat_points = cls.calculate_remaining_stat_points(character)
                remaining_skill_points = cls.calculate_remaining_skill_points(character, role)

            logger.info(f"Added 500 Eurodollars, {sheet.fashion_budget_remaining} fashion budget to character {full_name}")

            # Prepare the final message
            fashion_info = f"You have {sheet.fashion_budget_remaining} eb fashion budget (use for clothing/fashionware, or lose it). " if getattr(sheet, 'fashion_budget_remaining', 0) > 0 else ""
            final_message = (
                f"Character created using the Edgerunner method for role: {role}.\n"
                f"You have {remaining_stat_points} stat points and {remaining_skill_points} skill points left to allocate.\n"
                f"500 Eurodollars have been added to your account (extra spending money per the rulebook).\n"
                f"{fashion_info}"
                f"Use 'sheet' to view your full character details, 'inv' to view your inventory "
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

        # Reset Medicine specialties (Medtech)
        character.db.medicine_surgery = 0
        character.db.medicine_pharma = 0
        character.db.medicine_cryo = 0

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
        """Calculate remaining skill points for a typeclass character (role skills only, with double-cost).
        Role ability: first 4 points are free (not deducted from skill pool).
        """
        from world.chargen_constants import ROLE_ABILITY_FREE_POINTS, ROLE_ABILITY_SKILLS
        role_skills = ROLE_SKILLS.get(role, {})
        skills_dict = character.db.skills or {}
        total = 0
        role_ability_skill = ROLE_ABILITY_SKILLS.get(role)
        for orig_skill in role_skills:
            mapped = ROLE_SKILL_NAME_MAP.get(orig_skill, orig_skill).lower().replace(' ', '_')
            val = skills_dict.get(mapped, 0)
            mult = 2 if mapped in DOUBLE_COST_SKILLS else 1
            if mapped == role_ability_skill:
                billable = max(0, int(val) - ROLE_ABILITY_FREE_POINTS)
                total += billable * mult
            else:
                total += int(val) * mult
        langs = getattr(character.db, 'languages', {}) or {}
        lang_pts = sum(v for v in langs.values() if v)
        return max(0, 86 - total - lang_pts)

    @classmethod
    def spend_remaining_points_for_npc(cls, character, role):
        """Randomly spend remaining stat and skill points. For NPCs only (minor/major) - never for player characters."""
        if not is_npc(character):
            return
        # Spend stat points: 62 total, stats cap at 10
        total_stats = sum([getattr(character.db, s, 0) for s in STATS])
        stat_points = max(0, 62 - total_stats)
        eligible_stats = [s for s in STATS if getattr(character.db, s, 0) < 10]
        for _ in range(stat_points):
            if not eligible_stats:
                break
            stat = random.choice(eligible_stats)
            current = getattr(character.db, stat, 0)
            setattr(character.db, stat, current + 1)
            if current + 1 >= 10:
                eligible_stats = [s for s in eligible_stats if s != stat]

        # Spend skill points: 86 total, role skills only, double-cost for some
        # Role ability: first 4 points free (not counted toward spent)
        from world.chargen_constants import ROLE_ABILITY_FREE_POINTS, ROLE_ABILITY_SKILLS
        role_skills = ROLE_SKILLS.get(role, {})
        skills_dict = dict(character.db.skills or {})
        for orig, val in role_skills.items():
            mapped = ROLE_SKILL_NAME_MAP.get(orig, orig).lower().replace(' ', '_')
            if mapped not in skills_dict:
                skills_dict[mapped] = 0
        role_ability_skill = ROLE_ABILITY_SKILLS.get(role)
        spent = 0
        for o in role_skills:
            mapped = ROLE_SKILL_NAME_MAP.get(o, o).lower().replace(' ', '_')
            val = skills_dict.get(mapped, 0)
            mult = 2 if mapped in DOUBLE_COST_SKILLS else 1
            if mapped == role_ability_skill:
                spent += max(0, int(val) - ROLE_ABILITY_FREE_POINTS) * mult
            else:
                spent += int(val) * mult
        langs = getattr(character.db, 'languages', {}) or {}
        lang_pts = sum(v for v in langs.values() if v)
        skill_points = max(0, 86 - spent - lang_pts)

        skill_keys = [ROLE_SKILL_NAME_MAP.get(o, o).lower().replace(' ', '_') for o in role_skills]
        while skill_points >= 1:
            affordable = [sk for sk in skill_keys if (2 if sk in DOUBLE_COST_SKILLS else 1) <= skill_points]
            if not affordable:
                break
            sk = random.choice(affordable)
            cost = 2 if sk in DOUBLE_COST_SKILLS else 1
            skills_dict[sk] = skills_dict.get(sk, 0) + 1
            skill_points -= cost
        character.db.skills = skills_dict

        if hasattr(character, 'recalculate_derived_stats'):
            character.recalculate_derived_stats()

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
    def calculate_edgerunner_package_cost(cls, role):
        """Calculate the total cost of weapons, armor, gear, ammo, and cyberware for Edgerunner chargen.
        Characters start with 2550 eurodollars; this returns what is spent, so remainder goes to the character."""
        total_cost = 0
        role_equipment = EQUIPMENT.get(role, {})

        # Weapons
        for weapon_name in role_equipment.get("weapons", []):
            weapon_stats = next((w for w in weapon_data if w["name"] == weapon_name), None)
            if weapon_stats:
                total_cost += weapon_stats.get("value", 0)

        # Armor (including Virtuality Goggles which are in armors)
        for armor_name in role_equipment.get("armor", []):
            armor_stats = next((a for a in armor_data if a["name"] == armor_name), None)
            if armor_stats:
                total_cost += armor_stats.get("value", 0)

        # Gear
        for gear_name in role_equipment.get("gear", []):
            gear_stats = next((g for g in gear_data if g["name"] == gear_name), None)
            if gear_stats:
                total_cost += gear_stats.get("value", 0)

        # Ammunition: 50 rounds per weapon that uses ammo
        for weapon_name in role_equipment.get("weapons", []):
            weapon_type = weapon_name.split()[-1]  # "Very Heavy Pistol" -> "Pistol"
            ammo = next((a for a in ammunition if a.get("weapon_type") == weapon_type), None)
            if ammo and "cost" in ammo:
                total_cost += 50 * ammo["cost"]

        # Cyberware
        for item_name in ROLE_CYBERWARE.get(role, []):
            cw_data = CYBERWARE_DATA.get(item_name, {})
            cost = cw_data.get("cost", CYBERWARE_COSTS.get(item_name, 100))
            total_cost += cost

        return total_cost

    @classmethod
    def calculate_edgerunner_package_cost_split(cls, role):
        """Return (total_cost, fashion_cost). Fashion cost is deducted from 800 eb fashion budget."""
        total_cost = 0
        fashion_cost = 0
        role_equipment = EQUIPMENT.get(role, {})

        def _is_fashion_item(equip_type, name, stats_or_data):
            if equip_type == "gear":
                if name in FASHION_ITEM_NAMES:
                    return True
                return (stats_or_data or {}).get("category") == "Clothing"
            if equip_type == "armor":
                return name in FASHION_ITEM_NAMES
            if equip_type == "cyberware":
                return (stats_or_data or {}).get("type") == "Fashionware"
            return False

        # Weapons
        for weapon_name in role_equipment.get("weapons", []):
            weapon_stats = next((w for w in weapon_data if w["name"] == weapon_name), None)
            if weapon_stats:
                total_cost += weapon_stats.get("value", 0)

        # Armor
        for armor_name in role_equipment.get("armor", []):
            armor_stats = next((a for a in armor_data if a["name"] == armor_name), None)
            if armor_stats:
                total_cost += armor_stats.get("value", 0)
                if _is_fashion_item("armor", armor_name, armor_stats):
                    fashion_cost += armor_stats.get("value", 0)

        # Gear (skip Cyberdeck for Netrunner - handled separately with named deck)
        # Support (name, qty) tuples, plain name (qty 1), or {"or": index} (use first option for cost)
        for gear_entry in role_equipment.get("gear", []):
            if isinstance(gear_entry, dict) and "or" in gear_entry:
                or_idx = gear_entry["or"]
                or_groups = EQUIPMENT_OR_CHOICES.get(role, [])
                if or_idx >= len(or_groups):
                    continue
                gear_entry = or_groups[or_idx]["options"][0]
            if isinstance(gear_entry, (list, tuple)):
                gear_name, qty = gear_entry[0], int(gear_entry[1])
            else:
                gear_name, qty = gear_entry, 1
            if role == "Netrunner" and gear_name == "Cyberdeck":
                continue
            gear_stats = next((g for g in gear_data if g["name"] == gear_name), None)
            if gear_stats:
                item_val = gear_stats.get("value", 0) * qty
                total_cost += item_val
                if _is_fashion_item("gear", gear_name, gear_stats):
                    fashion_cost += item_val

        # Ammunition
        for weapon_name in role_equipment.get("weapons", []):
            weapon_type = weapon_name.split()[-1]
            ammo = next((a for a in ammunition if a.get("weapon_type") == weapon_type), None)
            if ammo and "cost" in ammo:
                total_cost += 50 * ammo["cost"]

        # Cyberware
        for item_name in ROLE_CYBERWARE.get(role, []):
            cw_data = CYBERWARE_DATA.get(item_name, {})
            cost = cw_data.get("cost", CYBERWARE_COSTS.get(item_name, 100))
            total_cost += cost
            if _is_fashion_item("cyberware", item_name, cw_data):
                fashion_cost += cost

        return total_cost, fashion_cost

    @classmethod
    def edgerunner_chargen_for_typeclass(cls, character, role, full_name, gear_choices=None):
        """Create an Edgerunner character using the typeclass directly"""
        logger.info(f"Starting edgerunner_chargen_for_typeclass for {full_name}, role: {role}")
        try:
            cls.assign_stats_to_typeclass(character, role)
            logger.info("Stats assigned to typeclass")
            
            cls.assign_skills_to_typeclass(character, role)
            logger.info("Skills assigned to typeclass")
            
            cls.assign_languages_to_typeclass(character, role)
            logger.info("Languages assigned to typeclass")
            
            cls.assign_gear_to_typeclass(character, role, gear_choices=gear_choices)
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
        from world.chargen_constants import MEDICINE_PHARMA_MAX, MEDICINE_CRYO_MAX
        role_skills = ROLE_SKILLS.get(role, {})
        skills_dict = {}
        
        for skill, value in role_skills.items():
            sheet_skill_name = ROLE_SKILL_NAME_MAP.get(skill, skill).lower()
            skills_dict[sheet_skill_name] = value
            
        character.db.skills = skills_dict

        # Medtech: initialize Medicine specialties (surgery 2, pharma 1, cryo 1 = 4 total)
        if role == "Medtech":
            character.db.medicine_surgery = 2
            character.db.medicine_pharma = 1
            character.db.medicine_cryo = 1
            logger.info("Assigned Medicine specialties: Surgery 2, Pharma 1, Cryo 1")

        logger.info(f"Assigned {len(skills_dict)} skills to character typeclass")

    @classmethod
    def assign_languages_to_typeclass(cls, character, role):
        """Assign Streetslang 4 only at start. Other languages come from lifepath (Cultural Origin)."""
        character.add_language("Streetslang", 4)

    @classmethod
    def assign_gear_to_typeclass(cls, character, role, gear_choices=None):
        """Assign gear to character typeclass directly. gear_choices resolves {\"or\": index} entries."""
        gear_choices = gear_choices or {}
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
        inventory.clear_gear()
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
        
        # Assign gear (Netrunner: skip generic "Cyberdeck", get random 7-slot named deck instead)
        # Support (name, qty) tuples, plain name (qty 1), or {"or": index} for menu choices
        for gear_entry in role_equipment.get('gear', []):
            if isinstance(gear_entry, dict) and "or" in gear_entry:
                or_idx = gear_entry["or"]
                choice_key = f"{role}_{or_idx}"
                chosen = gear_choices.get(choice_key)
                or_groups = EQUIPMENT_OR_CHOICES.get(role, [])
                if chosen is None and or_idx < len(or_groups):
                    chosen = or_groups[or_idx]["options"][0]  # default to first option
                if chosen is None:
                    continue
                gear_entry = chosen  # resolve to (name, qty) or name
            if isinstance(gear_entry, (list, tuple)):
                gear_name, qty = gear_entry[0], int(gear_entry[1])
            else:
                gear_name, qty = gear_entry, 1
            if role == "Netrunner" and gear_name == "Cyberdeck":
                continue  # Handled separately below
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
                inventory.add_gear(gear, quantity=qty)
                logger.info(f"Added gear: {gear_name} x{qty}")

        # Netrunner: assign random 7-slot cyberdeck from equipment DB
        if role == "Netrunner":
            deck_name = random.choice(NETRUNNER_7_SLOT_CYBERDECKS)
            cd_data = next((cd for cd in cyberdecks_data if cd["name"] == deck_name), None)
            if cd_data:
                gear, created = Gear.objects.get_or_create(
                    name=deck_name,
                    defaults={
                        'category': 'Cyberdeck',
                        'description': cd_data.get('description', ''),
                        'weight': 0.5,
                        'value': cd_data.get('value', 500)
                    }
                )
                inventory.add_gear(gear)
                logger.info(f"Added Netrunner cyberdeck: {deck_name}")
        
        # Assign ammunition
        for weapon in inventory.weapons.all():
            weapon_type = weapon.name.split()[-1]  # Get the last word of the weapon name
            ammo = next((a for a in ammunition if a['weapon_type'] == weapon_type), None)
            if ammo:
                # Use filter().first() to handle duplicate Ammunition rows (e.g. from multiple populates)
                ammo_obj = Ammunition.objects.filter(
                    name=ammo['name'],
                    weapon_type=ammo['weapon_type'],
                    ammo_type=getattr(AmmoType, ammo['ammo_type']),
                ).first()
                if ammo_obj is None:
                    ammo_obj = Ammunition.objects.create(
                        name=ammo['name'],
                        weapon_type=ammo['weapon_type'],
                        ammo_type=getattr(AmmoType, ammo['ammo_type']),
                        damage_modifier=ammo['damage_modifier'],
                        armor_piercing=ammo['armor_piercing'],
                        description=ammo['description'],
                        cost=ammo['cost'],
                        quantity=50,
                    )
                    created = True
                else:
                    created = False
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
            # Get defaults from CYBERWARE_DATA to satisfy NOT NULL constraints (cost, etc.)
            cw_data = CYBERWARE_DATA.get(item_name, {})
            defaults = {
                'description': cw_data.get('description', f"{item_name} for {role}"),
                'cost': cw_data.get('cost', CYBERWARE_COSTS.get(item_name, 100)),
                'humanity_loss': cw_data.get('humanity_loss', CYBERWARE_HUMANITY_LOSS.get(item_name, 0)),
                'type': cw_data.get('type', "Implant"),
                'slots': cw_data.get('slots', 1),
            }
            cyberware_item, created = Cyberware.objects.get_or_create(
                name=item_name,
                defaults=defaults
            )
            if created:
                logger.info(f"Created new Cyberware entry for {item_name}")
            
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

            # Add to inventory (same as vendor purchase) so it shows in inv/sheet
            inventory, _ = Inventory.get_or_create_for_character(character)
            inventory.cyberware.add(instance)
                
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
        trauma_loss = getattr(character.db, 'trauma_humanity_loss', 0) or 0

        # Store total loss
        character.db.total_cyberware_humanity_loss = total_humanity_loss

        # Calculate humanity based on empathy (includes trauma)
        if not hasattr(character.db, 'empathy'):
            character.db.empathy = 1

        character.db.humanity = max(0, character.db.empathy * 10 - total_humanity_loss - trauma_loss)

        # Recalculate empathy if humanity reduction is significant
        if character.db.empathy * 10 <= total_humanity_loss + trauma_loss:
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
        sheet.fashion_budget_remaining = FASHION_BUDGET  # 800 eb use-it-or-lose-it for fashion/fashionware

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
            sheet_skill_name = ROLE_SKILL_NAME_MAP.get(skill, skill).lower()
            if hasattr(sheet, sheet_skill_name):
                setattr(sheet, sheet_skill_name, value)

    @classmethod
    def assign_languages(cls, sheet, role):
        """Assign Streetslang 4 only at start. Other languages come from lifepath (Cultural Origin)."""
        sheet.add_language("Streetslang", 4)

    @staticmethod
    def assign_gear(sheet, role, gear_choices=None):
        """Assign role equipment to sheet's inventory. gear_choices resolves {"or": index} entries."""
        gear_choices = gear_choices or {}
        logger.info(f"Starting assign_gear for role: {role}")
        from world.inventory.models import Inventory, Weapon, Armor, Gear, Ammunition, AmmoType
        
        # Ensure the character has an inventory (use pk to avoid unsaved instance error)
        sheet_pk = getattr(sheet, 'pk', None)
        if sheet_pk is None:
            raise ValueError("Character sheet must be saved before assigning gear")
        inventory, created = Inventory.objects.get_or_create(character_id=sheet_pk)
        
        # Clear existing inventory
        inventory.weapons.clear()
        inventory.armor.clear()
        inventory.clear_gear()
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
        
        # Assign gear (support (name, qty) tuples, plain name, or {"or": index} for menu choices)
        for gear_entry in role_equipment.get('gear', []):
            if isinstance(gear_entry, dict) and "or" in gear_entry:
                or_idx = gear_entry["or"]
                choice_key = f"{role}_{or_idx}"
                chosen = gear_choices.get(choice_key)
                or_groups = EQUIPMENT_OR_CHOICES.get(role, [])
                if chosen is None and or_idx < len(or_groups):
                    chosen = or_groups[or_idx]["options"][0]  # default to first option
                if chosen is None:
                    continue
                gear_entry = chosen
            if isinstance(gear_entry, (list, tuple)):
                gear_name, qty = gear_entry[0], int(gear_entry[1])
            else:
                gear_name, qty = gear_entry, 1
            # Netrunner: replace generic "Cyberdeck" with random 7-slot named cyberdeck
            if role == "Netrunner" and gear_name == "Cyberdeck":
                deck_name = random.choice(NETRUNNER_7_SLOT_CYBERDECKS)
                deck_stats = next((d for d in cyberdecks_data if d.get("name") == deck_name), None)
                if deck_stats:
                    gear, created = Gear.objects.get_or_create(
                        name=deck_name,
                        defaults={
                            'category': 'Cyberdeck',
                            'description': deck_stats.get('description', ''),
                            'weight': 0.5,
                            'value': deck_stats.get('value', 500)
                        }
                    )
                    inventory.add_gear(gear)
                    logger.info(f"Added cyberdeck: {deck_name}")
                continue
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
                inventory.add_gear(gear, quantity=qty)
                logger.info(f"Added gear: {gear_name} x{qty}")
        
        # Assign ammunition
        for weapon in inventory.weapons.all():
            weapon_type = weapon.name.split()[-1]  # Get the last word of the weapon name
            ammo = next((a for a in ammunition if a['weapon_type'] == weapon_type), None)
            if ammo:
                # Use filter().first() to handle duplicate Ammunition rows (e.g. from multiple populates)
                ammo_obj = Ammunition.objects.filter(
                    name=ammo['name'],
                    weapon_type=ammo['weapon_type'],
                    ammo_type=getattr(AmmoType, ammo['ammo_type']),
                ).first()
                if ammo_obj is None:
                    ammo_obj = Ammunition.objects.create(
                        name=ammo['name'],
                        weapon_type=ammo['weapon_type'],
                        ammo_type=getattr(AmmoType, ammo['ammo_type']),
                        damage_modifier=ammo['damage_modifier'],
                        armor_piercing=ammo['armor_piercing'],
                        description=ammo['description'],
                        cost=ammo['cost'],
                        quantity=50,
                    )
                    created = True
                else:
                    created = False
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
            # Get defaults from CYBERWARE_DATA to satisfy NOT NULL constraints (cost, etc.)
            cw_data = CYBERWARE_DATA.get(item_name, {})
            defaults = {
                'description': cw_data.get('description', f"{item_name} for {role}"),
                'cost': cw_data.get('cost', CYBERWARE_COSTS.get(item_name, 100)),
                'humanity_loss': cw_data.get('humanity_loss', CYBERWARE_HUMANITY_LOSS.get(item_name, 0)),
                'type': cw_data.get('type', "Implant"),
                'slots': cw_data.get('slots', 1),
            }
            cyberware_item, created = Cyberware.objects.get_or_create(
                name=item_name,
                defaults=defaults
            )
            if created:
                logger.info(f"Created new Cyberware entry for {item_name}")
            
            sheet_pk = getattr(sheet, 'pk', None)
            if sheet_pk is None:
                raise ValueError("Character sheet must be saved before assigning cyberware")
            cw_instance = CyberwareInstance.objects.create(
                cyberware=cyberware_item,
                character_sheet_id=sheet_pk,
                installed=True
            )
            # Add to inventory (same as vendor purchase) so it shows in inv/sheet
            inventory, _ = Inventory.objects.get_or_create(character_id=sheet_pk)
            inventory.cyberware.add(cw_instance)
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
        
        # Reset all skills to 0 (use mapped names for sheet fields)
        for skill in set(skill for role_skills in ROLE_SKILLS.values() for skill in role_skills):
            sheet_skill_name = ROLE_SKILL_NAME_MAP.get(skill, skill).lower()
            if hasattr(sheet, sheet_skill_name):
                setattr(sheet, sheet_skill_name, 0)
        
        # Clear languages
        sheet.sheet_language_proficiencies.all().delete()
        
        # Clear inventory
        if hasattr(sheet, 'inventory'):
            sheet.inventory.weapons.all().delete()
            sheet.inventory.armor.all().delete()
            sheet.inventory.clear_gear()
        
        # Clear cyberware (use pk to avoid unsaved instance error)
        sheet_pk = getattr(sheet, 'pk', None)
        if sheet_pk is not None:
            CyberwareInstance.objects.filter(character_sheet_id=sheet_pk).delete()
        
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
        sheet.fashion_budget_remaining = 0
        sheet.sell_your_soul = False
        sheet.sell_your_soul_employer_type = ""
        sheet.sell_your_soul_employer = ""
        sheet.sell_your_soul_catch = ""
        
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
                for inv in Inventory.objects.filter(gear=duplicate_item).distinct():
                    inv.gear.remove(duplicate_item)
                    inv.gear.add(primary_item)
                duplicate_item.delete()
        logger.info("Cleaned up duplicate gear entries")