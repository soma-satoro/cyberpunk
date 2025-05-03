import traceback
from django.conf import settings
from evennia import Command, CmdSet
from world.jobs.models import Job
from world.languages.language_dictionary import LANGUAGES
from world.languages.models import Language
from world.utils.character_utils import ALL_ATTRIBUTES, SKILL_MAPPING, STAT_MAPPING, get_full_attribute_name
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.utils import evmenu
from world.cyberpunk_sheets.edgerunner import EdgerunnerChargen
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import logger
from typeclasses.chargen import ChargenRoom
from evennia.utils.utils import class_from_module

def get_character_model():
    return class_from_module(settings.BASE_CHARACTER_TYPECLASS)

class ChargenManager:
    @staticmethod
    def edgerunner_chargen(sheet):
        role = sheet.role
        if not role:
            return "You need to set your role first. Use the 'role' command."

        # Generate stat table
        stat_templates = EdgerunnerChargen.generate_stat_table(role)
        
        # Calculate final stats
        final_stats, rows_selected = EdgerunnerChargen.calculate_final_stats(stat_templates)
        
        # Assign stats to sheet
        stat_names = ['intelligence', 'reflexes', 'dexterity', 'technology', 'cool',
                      'willpower', 'luck', 'move', 'body', 'empathy']
        for stat, value in zip(stat_names, final_stats):
            setattr(sheet, stat, value)
        sheet.initialize_humanity()
        # Save the sheet before assigning skills and gear
        sheet.save()

        # Assign skills and gear
        EdgerunnerChargen.assign_skills(sheet, role)
        EdgerunnerChargen.assign_gear(sheet, role)
        EdgerunnerChargen.assign_cyberware(sheet, role)

        # Save the sheet again after all assignments
        sheet.save()

        # Prepare stat display for user feedback
        stat_display = " | ".join(f"{name.upper()}: {value}" for name, value in zip(stat_names, final_stats))
        
        # Prepare detailed stat generation info
        detailed_info = "\nDetailed stat generation:\n"
        for name, value, row in zip(stat_names, final_stats, rows_selected):
            detailed_info += f"{name.capitalize()}: {value} (Row {row})\n"
        
        # Recalculate derived stats one final time
        sheet.recalculate_derived_stats()
        sheet.save()

        return f"Character created using the Edgerunner method for role: {role}.\nYour stats have been assigned as follows:\n{stat_display}\n{detailed_info}\nUse 'sheet' to view your full character details."

    @staticmethod
    def complete_package_chargen(sheet):
        # Implementation of complete package chargen
        sheet.attribute_points = 62
        sheet.skill_points = 60
        sheet.eurodollars = 2550

        # Set default skills to 2
        default_skills = [
            'athletics', 'brawling', 'concentration', 'conversation', 'education',
            'evasion', 'first_aid', 'human_perception', 'local_expert', 'perception',
            'persuasion', 'stealth'
        ]
        for skill in default_skills:
            setattr(sheet, skill, 2)
            sheet.skill_points -= 2

        # Add Streetslang as a default language
        sheet.add_language("Streetslang", 4)
        sheet.skill_points -= 4

        sheet.save()

class CmdChargen(MuxCommand):
    """
    Create a new character using either the Edgerunner or Complete Package method.

    Usage:
      chargen <method> <role> <full_name>
      chargen/delete
      chargen/finish

    Methods:
      edgerunner
      complete_package

    Roles:
      Rockerboy, Solo, Netrunner, Tech, Medtech, Media, Exec, Lawman, Fixer, Nomad
    """

    key = "chargen"
    locks = "cmd:all()"

    def func(self):
        Character = get_character_model()
        
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("You can only use this command in a character generation room.")
            return

        logger.info(f"CmdChargen.func() called with args: {self.args}")
        
        if self.caller.tags.has("approved", category="approval"):
            self.caller.msg("Your character is already approved. You cannot use chargen commands.")
            return

        if "delete" in self.switches:
            self.reset_character()
            return

        if "finish" in self.switches:
            self.finish_chargen()
            return

        if not self.args:
            self.caller.msg("Usage: chargen <method> <role> <full_name>")
            return

        if self.args.lower() == "yes" and hasattr(self.caller.ndb, '_chargen_confirm'):
            logger.info("User confirmed. Proceeding with character creation.")
            method, role, full_name = self.caller.ndb._chargen_confirm
            del self.caller.ndb._chargen_confirm
            self.create_character(method, role, full_name)
            return

        args = self.args.split(None, 2)
        if len(args) < 3:
            self.caller.msg("Please provide a method, role, and full name.")
            return

        method, role, full_name = args
        method = method.lower()
        role = role.capitalize()
        full_name = full_name.strip('"')  # Remove quotes if present

        logger.info(f"Parsed args - method: {method}, role: {role}, full_name: {full_name}")

        if method not in ["edgerunner", "complete_package"]:
            self.caller.msg("Invalid method. Choose 'edgerunner' or 'complete_package'.")
            return

        if role not in ["Rockerboy", "Solo", "Netrunner", "Tech", "Medtech", "Media", "Exec", "Lawman", "Fixer", "Nomad"]:
            self.caller.msg("Invalid role. Choose from: Rockerboy, Solo, Netrunner, Tech, Medtech, Media, Exec, Lawman, Fixer, Nomad")
            return

        logger.info(f"Chargen command called with method: {method}, role: {role}, full_name: {full_name}")

        # Check for existing character initialization
        if self.caller.db.get('role') or self.caller.db.get('full_name'):
            self.caller.msg("You already have a character initialized. Use 'chargen/reset' to reset it or type 'chargen yes' to confirm overwriting it.")
            self.caller.ndb._chargen_confirm = (method, role, full_name)
            logger.info("Waiting for user confirmation.")
            return

        # Also check for sheet for backwards compatibility
        try:
            existing_sheets = CharacterSheet.objects.filter(character=self.caller)
            if existing_sheets.exists():
                self.caller.msg(f"You have {existing_sheets.count()} existing character sheet(s). Use 'chargen/reset' to reset it or type 'chargen yes' to confirm overwriting it.")
                self.caller.ndb._chargen_confirm = (method, role, full_name)
                logger.info("Waiting for user confirmation.")
                return
        except Exception as e:
            logger.error(f"Error checking for existing sheets: {str(e)}")

        # No existing character data found, proceed with creation
        self.create_character(method, role, full_name)

    def create_character(self, method, role, full_name):
        logger.info(f"Creating character with method: {method}, role: {role}, full_name: {full_name}")
        try:
            char = self.caller
            
            # Update the character's name if it has changed
            if char.key != full_name:
                char.key = full_name
                char.save()
                logger.info(f"Updated character name to {full_name}")
            
            # Set basic character attributes
            char.db.full_name = full_name
            char.db.role = role
            char.db.gender = char.db.gender or "Other"  # Set default gender if not set
            
            # For backward compatibility, also update/create character sheet
            if not hasattr(char, 'character_sheet') or char.character_sheet is None:
                sheet = CharacterSheet.objects.create(character=char, account=self.caller.account)
                char.db.character_sheet_id = sheet.id
                logger.info(f"Created new character sheet with ID {sheet.id}")
            else:
                sheet = char.character_sheet
                logger.info(f"Using existing character sheet with ID {sheet.id}")
            
            # Update sheet with role and name
            sheet.role = role
            sheet.full_name = full_name
            sheet.save()
            
            # Generate character based on method
            if method == "edgerunner":
                result = self.edgerunner_chargen(char, sheet, role)
            else:  # complete_package
                result = self.complete_package_chargen(char, sheet)
            
            self.caller.msg(result)
            return True

        except Exception as e:
            logger.error(f"Error in create_character: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.caller.msg(f"An error occurred during character creation: {str(e)}")
            return False

    def edgerunner_chargen(self, char, sheet, role):
        """Create character using edgerunner method, storing data in DB attributes."""
        # Generate stat table
        stat_templates = EdgerunnerChargen.generate_stat_table(role)
        
        # Calculate final stats
        final_stats, rows_selected = EdgerunnerChargen.calculate_final_stats(stat_templates)
        
        # Assign stats to character
        stat_names = ['intelligence', 'reflexes', 'dexterity', 'technology', 'cool',
                    'willpower', 'luck', 'move', 'body', 'empathy']
        
        # Store in character db
        for stat, value in zip(stat_names, final_stats):
            char.db[stat] = value
            # For compatibility, also update sheet
            setattr(sheet, stat, value)
        
        # Initialize humanity and luck
        char.db.humanity = char.db.empathy * 10
        char.db.current_luck = char.db.luck
        
        # For compatibility
        sheet.initialize_humanity()
        sheet.save()
        
        # Assign skills
        skills = EdgerunnerChargen.get_skills_for_role(role)
        for skill_name, skill_value in skills.items():
            # Store in character skills dict
            char.set_skill(skill_name, skill_value)
            # For compatibility, also update sheet if the attribute exists
            if hasattr(sheet, skill_name):
                setattr(sheet, skill_name, skill_value)
        
        # Assign gear and cyberware
        EdgerunnerChargen.assign_gear(sheet, role)  # Still using sheet for now
        EdgerunnerChargen.assign_cyberware(sheet, role)  # Still using sheet for now
        
        # Initialize default language
        char.add_language("Streetslang", 4)
        
        # Save the sheet again after all assignments (for backward compatibility)
        sheet.save()
        
        # Recalculate derived stats using Character's method
        char.recalculate_derived_stats()
        
        # Prepare stat display for user feedback
        stat_display = " | ".join(f"{name.upper()}: {value}" for name, value in zip(stat_names, final_stats))
        
        # Prepare detailed stat generation info
        detailed_info = "\nDetailed stat generation:\n"
        for name, value, row in zip(stat_names, final_stats, rows_selected):
            detailed_info += f"{name.capitalize()}: {value} (Row {row})\n"
        
        return f"Character created using the Edgerunner method for role: {role}.\nYour stats have been assigned as follows:\n{stat_display}\n{detailed_info}\nUse 'sheet' to view your full character details."

    def complete_package_chargen(self, char, sheet):
        """Create character using complete package method."""
        # Set default stats (all 1's, already handled at character creation)
        
        # Set eurodollars
        char.db.eurodollars = 2550
        
        # Set default skills to 2
        default_skills = [
            'athletics', 'brawling', 'concentration', 'conversation', 'education',
            'evasion', 'first_aid', 'human_perception', 'local_expert', 'perception',
            'persuasion', 'stealth'
        ]
        
        for skill in default_skills:
            char.set_skill(skill, 2)
        
        # Add Streetslang as a default language
        char.add_language("Streetslang", 4)
        
        # For compatibility
        sheet.eurodollars = 2550
        for skill in default_skills:
            setattr(sheet, skill, 2)
        sheet.add_language("Streetslang", 4)
        sheet.save()
        
        return f"Character created using the Complete Package method.\nYou have 62 attribute points and 52 skill points to spend.\nUse 'selfstat' to allocate them."

    def reset_character(self):
        """Reset the character to default values."""
        char = self.caller
        
        # First, try to delete any existing character sheet for backward compatibility
        if hasattr(char, 'character_sheet') and char.character_sheet:
            char.character_sheet.delete()
        
        # Reset all character attributes to defaults
        char.db.full_name = char.name
        char.db.handle = ""
        char.db.role = ""
        char.db.gender = ""
        char.db.age = 0
        char.db.hometown = ""
        char.db.height = 0
        char.db.weight = 0
        
        # Core attributes
        char.db.intelligence = 1
        char.db.reflexes = 1
        char.db.dexterity = 1
        char.db.technology = 1
        char.db.cool = 1
        char.db.willpower = 1
        char.db.luck = 1
        char.db.current_luck = 1
        char.db.move = 1
        char.db.body = 1
        char.db.empathy = 1
        
        # Derived stats
        char.db.max_hp = 10 + (5 * ((char.db.body + char.db.willpower) // 2))
        char.db.current_hp = char.db.max_hp
        char.db.humanity = char.db.empathy * 10
        char.db.humanity_loss = 0
        char.db.total_cyberware_humanity_loss = 0
        char.db.serious_wounds = char.db.body
        char.db.death_save = char.db.body
        
        # Economy
        char.db.eurodollars = 0
        char.db.reputation_points = 0
        char.db.rep = 0
        
        # Status flags
        char.db.is_complete = False
        char.db.has_cyberarm = False
        
        # Reset skills
        char.db.skills = {skill: 0 for skill in char.db.skills} if char.db.skills else {}
        
        # Reset skill instances
        char.db.skill_instances = {}
        
        # Reset languages
        char.db.languages = {}
        
        self.caller.msg("Your character has been reset to default values.")

    def finish_chargen(self):
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("You can only use this command in a character generation room.")
            return

        if self.caller.tags.has("approved", category="approval"):
            self.caller.msg("Your character is already approved. You cannot use chargen commands.")
            return

        sheet = self.caller.character_sheet
        if not sheet:
            self.caller.msg("You don't have a character sheet. Use 'chargen' to create one.")
            return

        remaining_stat_points, remaining_skill_points = sheet.get_remaining_points()
        total_remaining_points = remaining_stat_points + remaining_skill_points

        if total_remaining_points > 0:
            self.caller.msg(f"You still have {total_remaining_points} points to spend ({remaining_stat_points} stat points and {remaining_skill_points} skill points). Use 'selfstat' to allocate them before finishing.")
            return

        sheet.is_complete = True
        sheet.save()
        self.caller.msg("Character creation complete. Your character sheet is now locked for approval.")
        
        # create a +job indicating that the character is ready for approval
        job = Job.objects.create(
            character=self.caller,
            job_type="approval",
            description="Character is ready for approval"
        )
        job.save()


class CmdConfirmReset(Command):
    """
    Confirm the reset or overwrite of the character sheet.
    """
    key = "yes"
    locks = "cmd:all()"

    def func(self):
        if self.caller.tags.has("approved", category="approval"):
            self.caller.msg("Your character is already approved. You cannot use chargen commands.")
            return

        if self.caller.ndb._confirm_reset:
            method = self.caller.ndb._chargen_method
            reset_cmd = self.caller.ndb._cmd_reset
            del self.caller.ndb._confirm_reset
            del self.caller.ndb._chargen_method
            del self.caller.ndb._cmd_reset
            self.caller.cmdset.remove(ConfirmCmdSet)
            reset_cmd.reset_sheet(method)  # Pass the method here
        elif self.caller.ndb._confirm_overwrite:
            method = self.caller.ndb._chargen_method
            role = self.caller.ndb._chargen_role
            full_name = self.caller.ndb._chargen_full_name
            del self.caller.ndb._confirm_overwrite
            del self.caller.ndb._chargen_method
            del self.caller.ndb._chargen_role
            del self.caller.ndb._chargen_full_name
            self.caller.cmdset.remove(ConfirmCmdSet)
            chargen_cmd = CmdChargen()
            chargen_cmd.caller = self.caller
            chargen_cmd.create_character_sheet(method, role, full_name)
        else:
            self.caller.msg("There's nothing to confirm.")

class ConfirmCmdSet(CmdSet):
    key = "confirm_cmdset"
    priority = 1
    mergetype = "Union"

    def at_cmdset_creation(self):
        self.add(CmdConfirmReset())

class CmdListCharacterSheets(Command):
    """
    List all character sheet IDs associated with this character.

    Usage:
      list_sheets
    """

    key = "list_sheets"
    locks = "cmd:all()"

    def func(self):
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("You can only use this command in a character generation room.")
            return

        sheets = CharacterSheet.objects.filter(character=self.caller)
        if sheets:
            self.caller.msg("Character sheets associated with your character:")
            for sheet in sheets:
                self.caller.msg(f"Sheet ID: {sheet.id}, Role: {sheet.role}")
        else:
            self.caller.msg("You don't have any character sheets.")

from world.utils.character_utils import get_pronouns

class CmdSelfStat(MuxCommand):
    """
    Set a stat, skill, or topsheet attribute for your character.

    Usage:
      selfstat <attribute>=<value>
      selfstat <skill>(instance)=<value>

    Examples:
      selfstat INT=5
      selfstat AUTO=3
      selfstat HANDLE=CoolRunner
      selfstat AGE=25
      selfstat charismatic impact=6
      selfstat play instrument(guitar)=3
    """

    key = "selfstat"
    locks = "cmd:all()"

    def func(self):
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("You can only use this command in a character generation room.")
            return

        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: selfstat <attribute>=<value>")
            return

        # First, try to find the equals sign in the args
        attr_and_value = self.args.split("=", 1)
        
        if len(attr_and_value) != 2:
            self.caller.msg("Usage: selfstat <attribute>=<value>")
            return
            
        attr = attr_and_value[0].strip()
        value = attr_and_value[1].strip()
        
        # Check if the attribute contains an instance specification like "skill(instance)"
        instance = None
        if "(" in attr and ")" in attr:
            # Extract the instance name
            instance_start = attr.find("(")
            instance_end = attr.find(")")
            if instance_start < instance_end:  # Valid parentheses
                instance = attr[instance_start+1:instance_end].strip()
                attr = attr[:instance_start].strip()  # Remove the instance part from the attribute name
        
        # If the attribute name contains spaces, try joining with underscores
        if " " in attr:
            attr = attr.replace(" ", "_")

        full_attr_name = get_full_attribute_name(attr)
        if not full_attr_name:
            self.caller.msg(f"Invalid attribute name. Choose from: {', '.join(ALL_ATTRIBUTES.values())}")
            return

        # Get the character object (caller)
        char = self.caller
        
        # Check if this is a core stat
        if full_attr_name in STAT_MAPPING.values():
            try:
                value = int(value)
                if value < 0 or value > 10:
                    self.caller.msg("Stat value must be between 0 and 10.")
                    return
            except ValueError:
                self.caller.msg("You must specify an integer value for stats.")
                return

            # Get current value from DB attributes
            current_value = char.db.get(full_attr_name, 1)  # Default to 1 if not set
            points_needed = value - current_value
            
            # Calculate remaining points
            stat_points_spent, _ = char.calculate_spent_points()
            remaining_stat_points = max(0, 62 - stat_points_spent)

            if points_needed > remaining_stat_points:
                self.caller.msg(f"Not enough stat points. You need {points_needed} but only have {remaining_stat_points}.")
                return
                
            # Set the new value directly on the character's DB
            char.db[full_attr_name] = value

        # Check if this is a skill
        elif full_attr_name in SKILL_MAPPING.values():
            try:
                value = int(value)
                if value < 0 or value > 10:
                    self.caller.msg("Skill value must be between 0 and 10.")
                    return
            except ValueError:
                self.caller.msg("You must specify an integer value for skills.")
                return

            # If instance is provided, handle it as a skill instance
            if instance:
                # Create a skill instance key
                skill_instance_key = f"{full_attr_name}({instance})"
                
                # Get current skill instance value (default 0 if not set)
                current_value = char.get_skill_instance(full_attr_name, instance) if hasattr(char, 'get_skill_instance') else 0
                points_needed = value - current_value
                
                # Check for double-cost skills
                is_double_cost = full_attr_name in ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics', 'paramedic']
                actual_points_needed = points_needed * 2 if is_double_cost else points_needed

                # Calculate remaining skill points
                _, skill_points_spent = char.calculate_spent_points()
                remaining_skill_points = max(0, 86 - skill_points_spent)

                if actual_points_needed > remaining_skill_points:
                    self.caller.msg(f"Not enough skill points. You need {actual_points_needed} but only have {remaining_skill_points}.")
                    return
                    
                # Set the skill instance value
                # Initialize skill instances dict if it doesn't exist
                if not char.db.skill_instances:
                    char.db.skill_instances = {}
                
                # Store the skill instance
                char.db.skill_instances[skill_instance_key] = value
                
                # Display success message with instance
                self.caller.msg(f"Set {full_attr_name.replace('_', ' ').title()} ({instance}) to {value}.")
            else:
                # Regular skill without instance
                # Get current skill value
                current_value = char.get_skill(full_attr_name)
                points_needed = value - current_value
                
                # Check for double-cost skills
                is_double_cost = full_attr_name in ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics', 'paramedic']
                actual_points_needed = points_needed * 2 if is_double_cost else points_needed

                # Calculate remaining skill points
                _, skill_points_spent = char.calculate_spent_points()
                remaining_skill_points = max(0, 86 - skill_points_spent)

                if actual_points_needed > remaining_skill_points:
                    self.caller.msg(f"Not enough skill points. You need {actual_points_needed} but only have {remaining_skill_points}.")
                    return
                    
                # Set the skill value using the character's skill setter method
                char.set_skill(full_attr_name, value)

        # For role attribute specifically, validate against allowed values
        elif full_attr_name == 'role':
            valid_roles = ['Rockerboy', 'Solo', 'Netrunner', 'Tech', 'Medtech', 'Media', 'Exec', 'Lawman', 'Fixer', 'Nomad']
            value_cap = value.capitalize()
            
            if value_cap not in valid_roles:
                self.caller.msg(f"Invalid role. Choose from: {', '.join(valid_roles)}")
                return
            
            # Use the character's set_role method
            if hasattr(char, 'set_role') and callable(char.set_role):
                if char.set_role(value_cap):
                    self.caller.msg(f"Your role has been set to {value_cap}.")
                else:
                    self.caller.msg(f"There was an error setting your role to {value_cap}.")
                return
            else:
                # Fallback for older character implementations
                char.db.role = value_cap
                
                # For backward compatibility also update sheet
                if hasattr(char, 'character_sheet') and char.character_sheet:
                    sheet = char.character_sheet
                    sheet.role = value_cap
                    sheet.save(skip_recalculation=True)
                
                self.caller.msg(f"Your role has been set to {value_cap}.")
                return

        # For other attributes (non-stat, non-skill)
        else:
            # Set the attribute directly on the character's DB
            char.db[full_attr_name] = value

        # Special handling for body attribute (affects HP)
        if full_attr_name == 'body':
            # Recalculate derived stats
            char.recalculate_derived_stats()
            self.caller.msg(f"Hit Points updated to {char.db.max_hp}/{char.db.current_hp}")

        # For backward compatibility, also update the character sheet if it exists
        if hasattr(char, 'character_sheet') and char.character_sheet:
            sheet = char.character_sheet
            if hasattr(sheet, full_attr_name):
                setattr(sheet, full_attr_name, value)
                sheet.save(skip_recalculation=True)  # Skip recalculation to avoid circular updates

        # Display success message (for non-instance skills)
        if not instance or full_attr_name not in SKILL_MAPPING.values():
            self.caller.msg(f"Set {full_attr_name} to {value}.")
        
        # Show remaining points
        if full_attr_name in STAT_MAPPING.values() or full_attr_name in SKILL_MAPPING.values():
            new_remaining_stat_points, new_remaining_skill_points = char.get_remaining_points()
            self.caller.msg(f"You have {new_remaining_stat_points} stat points and {new_remaining_skill_points} skill points remaining to spend.")

        # Update the room's display
        if isinstance(self.caller.location, ChargenRoom):
            self.caller.location.update_remaining_points(self.caller)
            pronouns = get_pronouns(char.db.gender)
            self.caller.location.msg_contents(f"{self.caller.name} has updated {pronouns['possessive']} stats. Remaining points have been updated.", exclude=[self.caller])

class CmdSetLanguage(MuxCommand):
    """
    Set a language skill for your character.

    Usage:
      language <language name> <level>
      language/remove <language name>
      language/list

    Examples:
      language Streetslang 3
      language/remove Streetslang
      language/list

    This command allows you to add, update, remove, or list language skills.
    The level should be between 1 and 10.
    """
    key = "language"
    aliases = ["lang"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        char = self.caller

        if "list" in self.switches:
            languages = char.languages
            if languages:
                self.caller.msg("Your languages:")
                for name, level in languages.items():
                    self.caller.msg(f"{name} (Level {level})")
            else:
                self.caller.msg("You don't know any languages.")
            return

        if "remove" in self.switches:
            if not self.args:
                self.caller.msg("Usage: setlanguage/remove <language name>")
                return
            language_name = self.args.strip()
            char.remove_language(language_name)
            self.caller.msg(f"Removed {language_name} from your languages.")
            return

        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: setlanguage <language name> <level>")
            return

        try:
            language_name, level = self.args.rsplit(None, 1)
            level = int(level)
            if not 1 <= level <= 10:
                raise ValueError
        except ValueError:
            self.caller.msg("Please provide a valid language name and level (1-10).")
            return

        language_info = next((lang for lang in LANGUAGES if lang["name"].lower() == language_name.lower()), None)

        if language_info:
            char.add_language(language_info["name"], level)
            self.caller.msg(f"Added {language_info['name']} at level {level} to your languages.")
        else:
            # If not found in LANGUAGES, try to get it from the database
            try:
                language_obj = Language.objects.get(name__iexact=language_name)
                char.add_language(language_obj.name, level)
                self.caller.msg(f"Added {language_obj.name} at level {level} to your languages.")
            except Language.DoesNotExist:
                self.caller.msg(f"Language '{language_name}' not found. Please check the spelling and try again.")

class CmdLifepath(Command):
    """
    Start the lifepath creation process.

    Usage:
      lifepath
    """
    key = "lifepath"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
       evmenu.EvMenu(self.caller, 
               "commands.lifepath_functions",
               startnode="start_lifepath",
               cmdset_mergetype="Replace",
               cmdset_priority=1,
               auto_quit=True,
               cmd_on_exit=None)
