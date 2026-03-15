import traceback
from django.conf import settings
from evennia import Command, CmdSet
from world.jobs.models import Job
from world.languages.language_dictionary import LANGUAGES
from world.languages.models import Language, CharacterLanguage
from world.utils.character_utils import ALL_ATTRIBUTES, SKILL_MAPPING, STAT_MAPPING, get_full_attribute_name
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.utils import evmenu
from world.cyberpunk_constants import ROLE_SKILLS, ROLE_SKILL_NAME_MAP
from world.cyberpunk_sheets.edgerunner import EdgerunnerChargen
from world.cyberpunk_constants import EQUIPMENT_OR_CHOICES
from commands.edgerunner_gear_menu import start_edgerunner_gear_menu
from world.cyberpunk_sheets.services import CharacterMoneyService
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import logger
from typeclasses.chargen import ChargenRoom
from evennia.utils.utils import class_from_module
from world.sellyoursoul_menu import start_sellyoursoul_menu
from world.chargen_constants import FASHION_BUDGET

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

        # Add English and Streetslang as default languages at 4, then a random language
        sheet.add_language("English", 4)
        sheet.add_language("Streetslang", 4)
        sheet.skill_points -= 8
        from world.cyberpunk_constants import LANGUAGES as CYBERPUNK_LANGUAGES
        import random
        known = [lang['name'].lower() if isinstance(lang, dict) else str(lang).lower() for lang in sheet.language_list]
        available = [l for l in CYBERPUNK_LANGUAGES if l.lower() not in known]
        if available:
            random_lang = random.choice(available)
            random_level = random.randint(1, 3)
            sheet.add_language(random_lang, random_level)
            sheet.skill_points -= random_level

        sheet.save()

class CmdChargen(MuxCommand):
    """
    Create a new character using either the Edgerunner or Complete Package method.

    Usage:
      chargen <method> <role> <full_name>
      chargen/delete or chargen/reset
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

        if "delete" in self.switches or "reset" in self.switches:
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
            if method == "edgerunner" and EQUIPMENT_OR_CHOICES.get(role):
                if start_edgerunner_gear_menu(
                    self.caller, method, role, full_name,
                    on_complete=self._on_gear_menu_complete
                ):
                    return
            self.create_character(method, role, full_name)
            return

        args = self.args.split(None, 2)
        if len(args) < 3:
            self.caller.msg("Please provide a method, role, and full name.")
            return

        method, role, full_name = args
        method = method.lower()
        # Normalize aliases for complete_package
        if method in ("complete", "completepackage"):
            method = "complete_package"
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

        # Check for existing character initialization - only role indicates chargen was completed
        # (full_name default was removed; empty role means first-time chargen)
        if self.caller.db.role:
            self.caller.msg("You already have a character initialized. Use 'chargen/reset' to reset it or type 'chargen yes' to confirm overwriting it.")
            self.caller.ndb._chargen_confirm = (method, role, full_name)
            logger.info("Waiting for user confirmation.")
            return

        # Check for sheet - only prompt for reset if sheet has been through chargen (has role set)
        # Empty sheets (from old auto-creation or migration) get a free first-time chargen
        try:
            caller_pk = getattr(self.caller, 'pk', None) or getattr(self.caller, 'id', None)
            if caller_pk is None:
                existing_completed_sheets = CharacterSheet.objects.none()
            else:
                existing_sheets = CharacterSheet.objects.filter(character_id=caller_pk)
                existing_completed_sheets = [s for s in existing_sheets if getattr(s, 'role', None) and str(s.role).strip()]
            if existing_completed_sheets:
                self.caller.msg(f"You have existing character sheet(s) with completed chargen. Use 'chargen/reset' to reset it or type 'chargen yes' to confirm overwriting it.")
                self.caller.ndb._chargen_confirm = (method, role, full_name)
                logger.info("Waiting for user confirmation.")
                return
        except Exception as e:
            logger.error(f"Error checking for existing sheets: {str(e)}")

        # No existing character data found - show gear OR menu if needed, else proceed
        if method == "edgerunner" and EQUIPMENT_OR_CHOICES.get(role):
            if start_edgerunner_gear_menu(
                self.caller, method, role, full_name,
                on_complete=self._on_gear_menu_complete
            ):
                return  # Menu is running; it will call create_character when done
        self.create_character(method, role, full_name)

    def _on_gear_menu_complete(self, caller, menu=None):
        """Called when gear choices menu exits. Run create_character with stored choices."""
        if hasattr(caller.ndb, "_chargen_params") and hasattr(caller.ndb, "_chargen_gear_choices"):
            method, role, full_name = caller.ndb._chargen_params
            gear_choices = caller.ndb._chargen_gear_choices
            del caller.ndb._chargen_params
            del caller.ndb._chargen_gear_choices
            self.create_character(method, role, full_name, gear_choices=gear_choices)
        # If no params (menu was aborted?), do nothing

    def create_character(self, method, role, full_name, gear_choices=None):
        logger.info(f"Creating character with method: {method}, role: {role}, full_name: {full_name}")
        try:
            char = self.caller

            # Ensure character is persisted before any DB operations (fixes "Model instances
            # passed to related filters must be saved" - caller may be unsaved in some setups)
            char_pk = getattr(char, 'pk', None) or getattr(char, 'id', None)
            if char_pk is None and hasattr(char, 'save'):
                char.save()
                char_pk = getattr(char, 'pk', None) or getattr(char, 'id', None)
            if char_pk is None:
                raise ValueError(
                    "Character must be saved before chargen. Ensure you are puppeting a character "
                    "in the chargen room, not connecting OOC."
                )

            # Set basic character attributes (full_name is stored in db - never change char.key)
            char.db.full_name = full_name
            char.db.role = role
            char.db.gender = char.db.gender or "Other"  # Set default gender if not set
            
            # For backward compatibility, also update/create character sheet
            if not hasattr(char, 'character_sheet') or char.character_sheet is None:
                sheet = CharacterSheet.objects.create(
                    character_id=char_pk,
                    account=self.caller.account
                )
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
                result = self.edgerunner_chargen(char, sheet, role, gear_choices=gear_choices)
            else:  # complete_package
                result = self.complete_package_chargen(char, sheet)
            
            self.caller.msg(result)
            return True

        except Exception as e:
            logger.error(f"Error in create_character: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.caller.msg(f"An error occurred during character creation: {str(e)}")
            return False

    def edgerunner_chargen(self, char, sheet, role, gear_choices=None):
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
            setattr(char.db, stat, value)
            # For compatibility, also update sheet
            setattr(sheet, stat, value)
        
        # Initialize humanity and luck
        char.db.humanity = char.db.empathy * 10
        char.db.current_luck = char.db.luck
        
        # For compatibility
        sheet.initialize_humanity()
        sheet.save()
        
        # Assign skills (map ROLE_SKILLS names to model field names)
        skills = ROLE_SKILLS.get(role, {})
        for skill_name, skill_value in skills.items():
            sheet_skill_name = ROLE_SKILL_NAME_MAP.get(skill_name, skill_name)
            # Store in character skills dict
            char.set_skill(sheet_skill_name, skill_value)
            # For compatibility, also update sheet if the attribute exists
            if hasattr(sheet, sheet_skill_name):
                setattr(sheet, sheet_skill_name, skill_value)
        
        # Assign gear and cyberware
        EdgerunnerChargen.assign_gear(sheet, role, gear_choices=gear_choices or {})
        EdgerunnerChargen.assign_cyberware(sheet, role)  # Still using sheet for now

        # Edgerunners get 500 eb extra to spend or keep (per rulebook p. 98)
        _, fashion_cost = EdgerunnerChargen.calculate_edgerunner_package_cost_split(role)
        CharacterMoneyService.add_money(char, 500)

        # Fashion budget: 800 eb use-it-or-lose-it, reduced by clothing/fashionware in package
        if hasattr(sheet, 'fashion_budget_remaining'):
            sheet.fashion_budget_remaining = max(0, FASHION_BUDGET - fashion_cost)
            sheet.save(skip_recalculation=True)
        
        # Initialize default languages: English and Streetslang at 4, then a random language
        char.add_language("English", 4)
        char.add_language("Streetslang", 4)
        from world.cyberpunk_constants import LANGUAGES as CYBERPUNK_LANGUAGES
        known = [l.lower() for l in char.get_languages()]
        available = [l for l in CYBERPUNK_LANGUAGES if l.lower() not in known]
        if available:
            import random
            char.add_language(random.choice(available), random.randint(1, 3))
        
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

        fashion_budget = getattr(sheet, 'fashion_budget_remaining', 0)
        fashion_info = f"You have {fashion_budget} eb fashion budget for clothing/fashionware (use it or lose it). " if fashion_budget > 0 else ""
        
        return (
            f"Character created using the Edgerunner method for role: {role}.\n"
            f"Your stats have been assigned as follows:\n{stat_display}\n{detailed_info}\n"
            f"500 Eurodollars have been added to your account (extra spending money per the rulebook).\n"
            f"{fashion_info}"
            f"Use 'sheet' to view your full character details, 'inv' to view inventory, and 'inv/balance' to check your money."
        )

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
        
        # Add default languages: English and Streetslang at 4, then a random language
        char.add_language("English", 4)
        char.add_language("Streetslang", 4)
        from world.cyberpunk_constants import LANGUAGES as CYBERPUNK_LANGUAGES
        known = [l.lower() for l in char.get_languages()]
        available = [l for l in CYBERPUNK_LANGUAGES if l.lower() not in known]
        if available:
            import random
            char.add_language(random.choice(available), random.randint(1, 3))

        # For compatibility
        sheet.eurodollars = 2550
        sheet.fashion_budget_remaining = 800  # 800 eb for fashion/fashionware (use-it-or-lose-it)
        for skill in default_skills:
            setattr(sheet, skill, 2)
        sheet.add_language("English", 4)
        sheet.add_language("Streetslang", 4)
        sheet.save()
        
        return (
            f"Character created using the Complete Package method.\n"
            f"You have 62 attribute points and 52 skill points to spend.\n"
            f"You have 800 eb fashion budget for clothing/fashionware (use it or lose it).\n"
            f"Use 'selfstat' to allocate them."
        )

    def reset_character(self):
        """Reset the character to default values."""
        char = self.caller
        
        # First, try to delete any existing character sheet for backward compatibility
        # Only delete if the sheet exists in DB (pk is not None) - unsaved sheets can't be deleted
        if hasattr(char, 'character_sheet') and char.character_sheet:
            sheet = char.character_sheet
            if sheet.pk is not None:  # Only delete persisted sheets
                sheet.delete()
        
        # Delete any remaining sheets for this character (handles stale refs) and clear the ID
        try:
            char_pk = getattr(char, 'pk', None) or getattr(char, 'id', None)
            if char_pk is not None:
                CharacterSheet.objects.filter(character_id=char_pk).delete()
        except Exception:
            pass
        char.db.character_sheet_id = None
        
        # Reset all character attributes to defaults
        char.db.full_name = ""
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

        # Delete CharacterLanguage records linked to this character (handles both character and sheet links)
        try:
            char_pk = getattr(char, 'pk', None) or getattr(char, 'id', None)
            if char_pk is not None:
                CharacterLanguage.objects.filter(character_id=char_pk).delete()
        except Exception:
            pass

        # Clear lifepath data
        char.db.lifepath = {}

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
            chargen_cmd.create_character(method, role, full_name)
        else:
            self.caller.msg("There's nothing to confirm.")

class ConfirmCmdSet(CmdSet):
    key = "confirm_cmdset"
    priority = 1
    mergetype = "Union"

    def at_cmdset_creation(self):
        self.add(CmdConfirmReset())


class CmdSellYourSoul(Command):
    """
    During chargen: opt into Sell Your Soul for 1500 eb + free Neural Link.
    Choose employer (Military/Crime/Corporation) and catch (Hostages, Blackmail, etc.).

    Usage:
      sellyoursoul
    """
    key = "sellyoursoul"
    aliases = ["sellyoursoul", "soul"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("You can only use this command in a character generation room.")
            return
        if self.caller.tags.has("approved", category="approval"):
            self.caller.msg("Your character is already approved.")
            return
        start_sellyoursoul_menu(self.caller)


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

        caller_pk = getattr(self.caller, 'pk', None) or getattr(self.caller, 'id', None)
        sheets = CharacterSheet.objects.filter(character_id=caller_pk) if caller_pk else []
        if sheets:
            self.caller.msg("Character sheets associated with your character:")
            for sheet in sheets:
                self.caller.msg(f"Sheet ID: {sheet.id}, Role: {sheet.role}")
        else:
            self.caller.msg("You don't have any character sheets.")

class CmdSelfStat(MuxCommand):
    """
    Set a stat, skill, topsheet attribute, or language for your character.

    Usage:
      selfstat <attribute>=<value>
      selfstat <skill>(instance)=<value>
      selfstat <language>=<rank>

    Examples:
      selfstat INT=5
      selfstat AUTO=3
      selfstat HANDLE=CoolRunner
      selfstat AGE=25
      selfstat charismatic impact=6
      selfstat play instrument(guitar)=3
      selfstat Spanish=4
      selfstat Japanese=6

    Languages cost 1 skill point per rank (max rank 6). Use +lang all to see available languages.
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
        char = self.caller

        # Check if this is a language (before rejecting unknown attributes)
        if not full_attr_name:
            lang_match = next((l for l in LANGUAGES if l.name.lower() == attr.lower()), None)
            if lang_match:
                # Handle language assignment: 1 skill point per rank, max rank 6
                try:
                    value = int(value)
                    if value < 0 or value > 6:
                        self.caller.msg("Language rank must be between 0 and 6. Use 0 to remove a language.")
                        return
                except ValueError:
                    self.caller.msg("You must specify an integer value (0-6) for language rank.")
                    return

                lang_name = lang_match.name
                current_level = char.get_language_level(lang_name) if hasattr(char, 'get_language_level') else char.languages.get(lang_name, 0)
                points_needed = value - current_level

                _, skill_points_spent = char.calculate_spent_points()
                remaining_skill_points = max(0, 86 - skill_points_spent)

                if points_needed > remaining_skill_points:
                    self.caller.msg(f"Not enough skill points. You need {points_needed} but only have {remaining_skill_points}.")
                    return

                if value == 0:
                    char.remove_language(lang_name)
                    self.caller.msg(f"Removed {lang_name} from your languages.")
                else:
                    char.add_language(lang_name, value)
                    self.caller.msg(f"Set {lang_name} to rank {value}.")

                new_remaining_stat_points, new_remaining_skill_points = char.get_remaining_points()
                self.caller.msg(f"You have {new_remaining_stat_points} stat points and {new_remaining_skill_points} skill points remaining to spend.")
                return

        if not full_attr_name:
            self.caller.msg(f"Invalid attribute name. Choose from: {', '.join(ALL_ATTRIBUTES.values())} or a language from +lang all.")
            return

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
            current_value = getattr(char.db, full_attr_name, 1)  # Default to 1 if not set
            points_needed = value - current_value
            
            # Calculate remaining points
            stat_points_spent, _ = char.calculate_spent_points()
            remaining_stat_points = max(0, 62 - stat_points_spent)

            if points_needed > remaining_stat_points:
                self.caller.msg(f"Not enough stat points. You need {points_needed} but only have {remaining_stat_points}.")
                return
                
            # Set the new value directly on the character's DB
            setattr(char.db, full_attr_name, value)

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
            setattr(char.db, full_attr_name, value)

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
        
        # Show remaining points (private to user only - no room broadcast)
        if full_attr_name in STAT_MAPPING.values() or full_attr_name in SKILL_MAPPING.values():
            new_remaining_stat_points, new_remaining_skill_points = char.get_remaining_points()
            self.caller.msg(f"You have {new_remaining_stat_points} stat points and {new_remaining_skill_points} skill points remaining to spend.")

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
        from commands.lifepath_menu import start_lifepath_menu
        start_lifepath_menu(self.caller)
