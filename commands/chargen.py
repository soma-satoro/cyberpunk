import traceback
from django.conf import settings
from evennia import Command, CmdSet
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
      chargen/reset

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

        if "reset" in self.switches:
            self.reset_character_sheet()
            return

        if not self.args:
            self.caller.msg("Usage: chargen <method> <role> <full_name>")
            return

        if self.args.lower() == "yes" and hasattr(self.caller.ndb, '_chargen_confirm'):
            logger.info("User confirmed. Proceeding with character creation.")
            method, role, full_name = self.caller.ndb._chargen_confirm
            del self.caller.ndb._chargen_confirm
            self.create_character_sheet(method, role, full_name)
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

        try:
            existing_sheets = CharacterSheet.objects.filter(account=self.caller.account)
            logger.info(f"Existing sheets found: {existing_sheets.count()}")
            
            if existing_sheets.exists():
                self.caller.msg(f"Debug: Found {existing_sheets.count()} existing character sheet(s).")
                for sheet in existing_sheets:
                    self.caller.msg(f"Debug: Existing sheet ID: {sheet.id}, Role: {sheet.role}")
                self.caller.msg("You already have a character sheet. Use 'chargen/reset' to reset it or type 'chargen yes' to confirm overwriting it.")
                self.caller.ndb._chargen_confirm = (method, role, full_name)
                logger.info("Waiting for user confirmation.")
                return
            else:
                logger.info("No existing sheet found. Proceeding with character creation.")
                self.create_character_sheet(method, role, full_name)
        except Exception as e:
            logger.error(f"Error in CmdChargen.func(): {str(e)}")
            self.caller.msg(f"Debug: Error checking for existing sheets: {str(e)}")

    def create_character_sheet(self, method, role, full_name):
        logger.info(f"Creating/updating character sheet with method: {method}, role: {role}, full_name: {full_name}")
        try:
            char = self.caller
            logger.info(f"Using caller's character object with ID {char.id}")

            # Check if the character already has a sheet
            if hasattr(char, 'character_sheet'):
                sheet = char.character_sheet
                logger.info(f"Using existing character sheet with ID {sheet.id}")
            else:
                # If not, create a new one
                sheet = CharacterSheet.objects.create(character=char, account=self.caller.account)
                logger.info(f"Created new character sheet with ID {sheet.id}")

            # Update the character's name if it has changed
            if char.key != full_name:
                char.key = full_name
                char.save()
                logger.info(f"Updated character name to {full_name}")

            # Associate the sheet ID with the character
            char.db.character_sheet_id = sheet.id
            char.save()

            # After creating the sheet, set a default gender if not already set
            if not sheet.gender:
                sheet.gender = "Other"  # Or you could prompt the user to choose a gender
                sheet.save()

            result = EdgerunnerChargen.create_character(sheet, role, method, full_name)

            self.caller.msg(result)
            return sheet

        except Exception as e:
            logger.error(f"Error in create_character_sheet: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.caller.msg(f"An error occurred during character creation: {str(e)}")
            return None

    def reset_character_sheet(self):
        try:
            sheet = CharacterSheet.objects.get(account=self.caller.account)
            sheet.reset()
            sheet.save()
            self.caller.msg("Character sheet reset and marked as unapproved.")
            logger.info(f"Character sheet reset for {self.caller.key} and marked as unapproved.")
        except CharacterSheet.DoesNotExist:
            self.caller.msg("You don't have a character sheet to reset.")
        except Exception as e:
            self.caller.msg(f"An error occurred while resetting the character sheet: {str(e)}")
            logger.error(f"Error resetting character sheet for {self.caller.key}: {str(e)}")

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

class CmdChargenFinish(Command):
    """
    Finish character creation and lock your character sheet.

    Usage:
      chargen finish
    """

    key = "chargen finish"
    locks = "cmd:all()"

    def func(self):
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
        # Here you might want to notify staff that a new character is ready for approval

class CmdChargenDelete(MuxCommand):
    """
    Delete the character sheet for a character.

    Usage:
      chargen/delete

    This command deletes the character sheet associated with your character.
    """

    key = "chargen/delete"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("You can only use this command in a character generation room.")
            return

        try:
            cs = CharacterSheet.objects.get(character=self.caller)
            cs.delete()
            self.caller.msg("Your character sheet has been deleted.")
        except CharacterSheet.DoesNotExist:
            self.caller.msg("You don't have a character sheet to delete.")
        except Exception as e:
            self.caller.msg(f"An error occurred while deleting your character sheet: {str(e)}")
            logger.log_err(f"Error deleting character sheet for {self.caller.key}: {str(e)}")

class CmdClearSheet(Command):
    """
    Forcefully clear all character sheets for debugging.
    """
    key = "clearsheet"
    locks = "cmd:perm(Admin)"

    def func(self):
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("You can only use this command in a character generation room.")
            return

        CharacterSheet.objects.filter(character=self.caller).delete()
        self.caller.msg("All character sheets for this character have been forcefully cleared.")
        
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

class CmdSetStat(MuxCommand):
    """
    Set a stat, skill, or topsheet attribute for your character.

    Usage:
      selfstat <attribute>=<value>

    Examples:
      selfstat INT=5
      selfstat AUTO=3
      selfstat HANDLE=CoolRunner
      selfstat AGE=25
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

        attr, value = self.args.split("=", 1)
        attr = attr.strip()
        value = value.strip()

        full_attr_name = get_full_attribute_name(attr)
        if not full_attr_name:
            self.caller.msg(f"Invalid attribute name. Choose from: {', '.join(ALL_ATTRIBUTES.values())}")
            return

        sheet = self.caller.character_sheet
        if not sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        if full_attr_name in STAT_MAPPING.values():
            try:
                value = int(value)
                if value < 0 or value > 10:
                    self.caller.msg("Stat value must be between 0 and 10.")
                    return
            except ValueError:
                self.caller.msg("You must specify an integer value for stats.")
                return

            current_value = getattr(sheet, full_attr_name)
            points_needed = value - current_value
            remaining_stat_points, _ = sheet.get_remaining_points()

            if points_needed > remaining_stat_points:
                self.caller.msg(f"Not enough stat points. You need {points_needed} but only have {remaining_stat_points}.")
                return

        elif full_attr_name in SKILL_MAPPING.values():
            try:
                value = int(value)
                if value < 0 or value > 10:
                    self.caller.msg("Skill value must be between 0 and 10.")
                    return
            except ValueError:
                self.caller.msg("You must specify an integer value for skills.")
                return

            current_value = getattr(sheet, full_attr_name)
            points_needed = value - current_value
            is_double_cost = full_attr_name in ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics', 'paramedic']
            actual_points_needed = points_needed * 2 if is_double_cost else points_needed

            _, remaining_skill_points = sheet.get_remaining_points()

            if actual_points_needed > remaining_skill_points:
                self.caller.msg(f"Not enough skill points. You need {actual_points_needed} but only have {remaining_skill_points}.")
                return

        # For topsheet attributes, we don't need to check points
        setattr(sheet, full_attr_name, value)

        # If the attribute being set is Body, update hit points
        if full_attr_name == 'body':
            new_max_hp = 10 + (5 * int(value))  # Calculate new max HP
            sheet._max_hp = new_max_hp
            sheet._current_hp = new_max_hp  # Set current HP to max
            self.caller.msg(f"Hit Points updated to {new_max_hp}/{new_max_hp}")

        sheet.save()

        pronouns = get_pronouns(sheet.gender)

        self.caller.msg(f"Set {full_attr_name} to {value}.")
        
        if full_attr_name in STAT_MAPPING.values() or full_attr_name in SKILL_MAPPING.values():
            new_remaining_stat_points, new_remaining_skill_points = sheet.get_remaining_points()
            self.caller.msg(f"You have {new_remaining_stat_points} stat points and {new_remaining_skill_points} skill points remaining to spend.")

        # Update the room's display
        if isinstance(self.caller.location, ChargenRoom):
            self.caller.location.update_remaining_points(self.caller)
            self.caller.location.msg_contents(f"{self.caller.name} has updated {pronouns['possessive']} stats. Remaining points have been updated.", exclude=[self.caller])

    def get_derived_stats(self, sheet):
        return {
            "Max HP": sheet._max_hp,
            "Current HP": sheet._current_hp,
            "Death Save": sheet.death_save,
            "Serious Wounds": sheet.serious_wounds,
            "Humanity": sheet.humanity
        }

class CmdSetLanguage(MuxCommand):
    """
    Set a language skill for your character.

    Usage:
      setlanguage <language name> <level>
      setlanguage/remove <language name>
      setlanguage/list

    Examples:
      setlanguage Streetslang 3
      setlanguage/remove Streetslang
      setlanguage/list

    This command allows you to add, update, remove, or list language skills.
    The level should be between 1 and 10.
    """
    key = "setlanguage"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet!")
            return

        sheet = self.caller.character_sheet

        if "list" in self.switches:
            languages = sheet.character_languages.all()
            if languages:
                self.caller.msg("Your languages:")
                for lang in languages:
                    self.caller.msg(f"{lang.language} (Level {lang.level})")
            else:
                self.caller.msg("You don't know any languages.")
            return

        if "remove" in self.switches:
            if not self.args:
                self.caller.msg("Usage: setlanguage/remove <language name>")
                return
            language_name = self.args.strip()
            sheet.remove_language(language_name)
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
            sheet.add_language(language_info["name"], level)
            self.caller.msg(f"Added {language_info['name']} at level {level} to your character sheet.")
        else:
            # If not found in LANGUAGES, try to get it from the database
            try:
                language_obj = Language.objects.get(name__iexact=language_name)
                sheet.add_language(language_obj.name, level)
                self.caller.msg(f"Added {language_obj.name} at level {level} to your character sheet.")
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
       
"""
class CmdChargenReset(Command):
"""
"""
    Reset your character sheet and start over.
    Usage:
      chargen/reset
    """"""
            key = "chargen/reset"
    locks = "cmd:all()"

    def func(self):
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("You can only use this command in a character generation room.")
            return

        if self.caller.tags.has("approved", category="approval"):
            self.caller.msg("Your character is already approved. You cannot use chargen commands.")
            return

        method = self.args.strip().lower() if self.args else "complete"
        
        if method not in ["complete", "edgerunner"]:
            self.caller.msg("Invalid method. Choose 'complete' or 'edgerunner'.")
            return

        # Check if character sheet exists
        sheets = CharacterSheet.objects.filter(character=self.caller)
        self.caller.msg(f"Debug: Found {sheets.count()} character sheet(s).")
        for sheet in sheets:
            self.caller.msg(f"Debug: Existing sheet ID: {sheet.id}, Role: {sheet.role}")

        if not sheets.exists():
            self.caller.msg("You don't have a character sheet to reset. Use the 'chargen' command to create a new one.")
            return

        # Ask for confirmation
        self.caller.msg(f"Are you sure you want to reset your current character sheet and create a new one using the {method} method?")
        self.caller.msg("This action cannot be undone. Type 'yes' to confirm or anything else to cancel.")

        # Set up the confirmation
        self.caller.ndb._confirm_reset = True
        self.caller.ndb._cmd_reset = self
        self.caller.ndb._chargen_method = method
        self.caller.cmdset.add(ConfirmCmdSet)

    def reset_sheet(self, method):
        self.caller.msg(f"Debug: Entering reset_sheet method with method: {method}")
        try:
            sheets = CharacterSheet.objects.filter(character=self.caller)
            self.caller.msg(f"Debug: Found {sheets.count()} character sheet(s) to reset.")
            for sheet in sheets:
                self.caller.msg(f"Debug: Resetting sheet ID: {sheet.id}, Role: {sheet.role}")
                sheet.reset()
                sheet.role = ""  # Explicitly set role to empty string
                sheet.save()
                self.caller.msg(f"Debug: After reset - Sheet ID: {sheet.id}, Role: {sheet.role}")
            
            # Ensure the character is marked as unapproved
            self.caller.tags.clear(category="approval")
            
            self.caller.msg("Your character sheet has been reset. Use the 'sheet' command to view it.")
            self.caller.msg("Remember to set your stats and skills using the 'selfstat' command.")
            self.caller.msg("Your character is now unapproved and will need to be approved by an admin.")
            logger.log_info(f"Character sheet reset for {self.caller.key} and marked as unapproved.")
        except Exception as e:
            self.caller.msg(f"Debug: Error in reset_sheet: {str(e)}")
            logger.log_err(f"Error resetting character sheet for {self.caller.key}: {str(e)}")
            self.caller.msg("An error occurred while resetting your character sheet. Please contact an admin for assistance.")
"""