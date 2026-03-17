import traceback
from django.conf import settings
from evennia import Command, CmdSet
from world.jobs.models import Job, Queue
from world.languages.language_dictionary import LANGUAGES
from world.languages.models import Language, CharacterLanguage
from world.utils.character_utils import (
    ALL_ATTRIBUTES,
    SKILL_MAPPING,
    STAT_MAPPING,
    get_full_attribute_name,
    MEDICINE_SPECIALTY_ATTRIBUTES,
    MAKER_SPECIALTY_ATTRIBUTES,
)
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.utils import evmenu
from world.cyberpunk_constants import ROLE_SKILLS, ROLE_SKILL_NAME_MAP
from world.cyberpunk_sheets.edgerunner import EdgerunnerChargen
from world.cyberpunk_constants import EQUIPMENT_OR_CHOICES
from commands.edgerunner_gear_menu import start_edgerunner_gear_menu
from world.medtech_medicine_menu import start_medtech_medicine_menu
from world.tech_maker_menu import start_tech_maker_menu
from world.edgerunner_skill_instances_menu import start_edgerunner_skill_instances_menu
from world.cyberpunk_sheets.services import CharacterMoneyService
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import logger
from typeclasses.chargen import ChargenRoom
from evennia.utils.utils import class_from_module
from world.sellyoursoul_menu import start_sellyoursoul_menu
from world.chargen_constants import (
    FASHION_BUDGET,
    ROLE_ABILITY_SKILLS,
    CHARGEN_STAT_MIN,
    CHARGEN_STAT_MAX,
    CHARGEN_SKILL_MIN,
    CHARGEN_SKILL_MAX,
    COMPLETE_PACKAGE_SKILL_POOL,
    EDGERUNNER_SKILL_POOL,
    validate_medicine_specialties,
    validate_maker_specialties,
)

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
        # Implementation of complete package chargen (86 skill points per book)
        sheet.attribute_points = 62
        sheet.skill_points = 86
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

        # Streetslang 4 only at start (free) - other languages come from lifepath (Cultural Origin)
        sheet.add_language("Streetslang", 4)

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
            self.caller.msg("You already have a character initialized. Use 'chargen/reset' to reset it first.")
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
                self.caller.msg("You have existing character sheet(s) with completed chargen. Use 'chargen/reset' to reset first.")
                return
        except Exception as e:
            logger.error(f"Error checking for existing sheets: {str(e)}")

        # No existing character data found - chain menus: gear (if needed) -> medicine (Medtech) / maker (Tech) -> skill instances -> create
        if method == "edgerunner" and EQUIPMENT_OR_CHOICES.get(role):
            if start_edgerunner_gear_menu(
                self.caller, method, role, full_name,
                on_complete=self._on_gear_menu_complete
            ):
                return  # Gear menu running; on exit -> medicine (Medtech) / maker (Tech) or skill instances
        if method == "edgerunner" and role == "Medtech":
            if start_medtech_medicine_menu(
                self.caller, method, role, full_name,
                on_complete=self._on_medicine_menu_complete
            ):
                return  # Medicine menu running; on exit -> skill instances
        if method == "edgerunner" and role == "Tech":
            if start_tech_maker_menu(
                self.caller, method, role, full_name,
                on_complete=self._on_maker_menu_complete
            ):
                return  # Maker menu running; on exit -> skill instances
        if method == "edgerunner":
            if start_edgerunner_skill_instances_menu(
                self.caller, method, role, full_name,
                on_complete=self._on_skill_instances_menu_complete
            ):
                return  # Skill instances menu; on exit -> create_character
        if method == "complete_package" and role == "Medtech":
            if start_medtech_medicine_menu(
                self.caller, method, role, full_name,
                on_complete=self._on_complete_package_medicine_menu_complete
            ):
                return  # Medicine menu running; on exit -> skill instances -> create_character
        if method == "complete_package" and role == "Tech":
            if start_tech_maker_menu(
                self.caller, method, role, full_name,
                on_complete=self._on_complete_package_maker_menu_complete
            ):
                return  # Maker menu running; on exit -> skill instances -> create_character
        if method == "complete_package":
            if start_edgerunner_skill_instances_menu(
                self.caller, method, role, full_name,
                on_complete=self._on_skill_instances_menu_complete
            ):
                return  # Skill instances menu; on exit -> create_character
        self.create_character(method, role, full_name)

    def _on_gear_menu_complete(self, caller, menu=None):
        """Called when gear menu exits. Chain to medicine (Medtech), maker (Tech), or skill instances menu."""
        if hasattr(caller.ndb, "_chargen_params") and hasattr(caller.ndb, "_chargen_gear_choices"):
            method, role, full_name = caller.ndb._chargen_params
            if role == "Medtech":
                start_medtech_medicine_menu(
                    caller, method, role, full_name,
                    on_complete=self._on_medicine_menu_complete
                )
            elif role == "Tech":
                start_tech_maker_menu(
                    caller, method, role, full_name,
                    on_complete=self._on_maker_menu_complete
                )
            else:
                start_edgerunner_skill_instances_menu(
                    caller, method, role, full_name,
                    on_complete=self._on_skill_instances_menu_complete
                )
        # If no params (menu was aborted?), do nothing

    def _on_medicine_menu_complete(self, caller, menu=None):
        """Called when Medtech Medicine specialty menu exits. Chain to skill instances menu."""
        if hasattr(caller.ndb, "_chargen_params") and hasattr(caller.ndb, "_chargen_medicine_specialties"):
            method, role, full_name = caller.ndb._chargen_params
            start_edgerunner_skill_instances_menu(
                caller, method, role, full_name,
                on_complete=self._on_skill_instances_menu_complete
            )
        # If no params (menu was aborted?), do nothing

    def _on_maker_menu_complete(self, caller, menu=None):
        """Called when Tech Maker specialty menu exits. Chain to skill instances menu."""
        if hasattr(caller.ndb, "_chargen_params") and hasattr(caller.ndb, "_chargen_maker_specialties"):
            method, role, full_name = caller.ndb._chargen_params
            start_edgerunner_skill_instances_menu(
                caller, method, role, full_name,
                on_complete=self._on_skill_instances_menu_complete
            )
        # If no params (menu was aborted?), do nothing

    def _on_complete_package_medicine_menu_complete(self, caller, menu=None):
        """Called when Complete Package Medtech medicine menu exits. Chain to skill instances menu."""
        if not hasattr(caller.ndb, "_chargen_params") or not hasattr(caller.ndb, "_chargen_medicine_specialties"):
            return  # User aborted - don't create character
        method, role, full_name = caller.ndb._chargen_params
        # Do NOT clear ndb - skill instances menu's on_complete will use both
        start_edgerunner_skill_instances_menu(
            caller, method, role, full_name,
            on_complete=self._on_skill_instances_menu_complete
        )

    def _on_complete_package_maker_menu_complete(self, caller, menu=None):
        """Called when Complete Package Tech Maker menu exits. Chain to skill instances menu."""
        if not hasattr(caller.ndb, "_chargen_params") or not hasattr(caller.ndb, "_chargen_maker_specialties"):
            return  # User aborted - don't create character
        method, role, full_name = caller.ndb._chargen_params
        start_edgerunner_skill_instances_menu(
            caller, method, role, full_name,
            on_complete=self._on_skill_instances_menu_complete
        )

    def _on_skill_instances_menu_complete(self, caller, menu=None):
        """Called when skill instances menu exits. Run create_character with all gathered data."""
        if not hasattr(caller.ndb, "_chargen_skill_instances"):
            # User aborted the menu - don't create character
            return
        method, role, full_name = caller.ndb._chargen_params
        skill_instances = caller.ndb._chargen_skill_instances
        gear_choices = getattr(caller.ndb, "_chargen_gear_choices", None)
        medicine_specialties = getattr(caller.ndb, "_chargen_medicine_specialties", None)
        maker_specialties = getattr(caller.ndb, "_chargen_maker_specialties", None)
        # Clear ndb
        for key in ("_chargen_params", "_chargen_skill_instances", "_chargen_gear_choices", "_chargen_medicine_specialties", "_chargen_maker_specialties"):
            if hasattr(caller.ndb, key):
                delattr(caller.ndb, key)
        self.create_character(
            method, role, full_name,
            gear_choices=gear_choices,
            medicine_specialties=medicine_specialties,
            maker_specialties=maker_specialties,
            skill_instance_choices=skill_instances,
        )

    def create_character(self, method, role, full_name, gear_choices=None, medicine_specialties=None, maker_specialties=None, skill_instance_choices=None):
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
            char.db.handle = full_name  # Default Handle to full name; user can change later
            char.db.role = role
            char.db.gender = char.db.gender or "Other"  # Set default gender if not set
            
            # For backward compatibility, also update/create character sheet
            if not hasattr(char, 'character_sheet') or char.character_sheet is None:
                sheet = CharacterSheet.objects.create(
                    character_id=char_pk,
                    account=self.caller.account
                )
                char.db.character_sheet_id = sheet.id
                logger.info(f"Created new character sheet with ID {sheet.id} for character {char_pk}")
            else:
                sheet = char.character_sheet
                logger.info(f"Using existing character sheet with ID {sheet.id}")
            
            # Update sheet with role, name, and handle
            sheet.role = role
            sheet.full_name = full_name
            sheet.handle = full_name  # Default Handle to full name; user can change later
            sheet.save()

            # Ensure inventory exists (assign_gear creates it for edgerunner; complete_package does not)
            from world.inventory.models import Inventory
            Inventory.objects.get_or_create(character_id=sheet.pk)

            # Generate character based on method
            char.db.chargen_method = method  # Store for point calculation (edgerunner vs complete_package)
            if method == "edgerunner":
                result = self.edgerunner_chargen(
                    char, sheet, role,
                    gear_choices=gear_choices,
                    medicine_specialties=medicine_specialties,
                    maker_specialties=maker_specialties,
                    skill_instance_choices=skill_instance_choices,
                )
            else:  # complete_package
                result = self.complete_package_chargen(
                    char, sheet,
                    medicine_specialties=medicine_specialties,
                    maker_specialties=maker_specialties,
                    skill_instance_choices=skill_instance_choices,
                )
            
            self.caller.msg(result)
            return True

        except Exception as e:
            logger.error(f"Error in create_character: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.caller.msg(f"An error occurred during character creation: {str(e)}")
            return False

    def edgerunner_chargen(self, char, sheet, role, gear_choices=None, medicine_specialties=None, maker_specialties=None, skill_instance_choices=None):
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
        # Skip local_expert, play_instrument (set via skill_instance_choices), and Medtech zoology (replaced by chosen science)
        skill_instance_choices = skill_instance_choices or {}
        skills = ROLE_SKILLS.get(role, {})
        skip_skills = {"local_expert", "play_instrument"}
        if role == "Medtech":
            skip_skills.add("zoology")
        for skill_name, skill_value in skills.items():
            if skill_name in skip_skills:
                continue
            sheet_skill_name = ROLE_SKILL_NAME_MAP.get(skill_name, skill_name)
            char.set_skill(sheet_skill_name, skill_value)
            if hasattr(sheet, sheet_skill_name):
                setattr(sheet, sheet_skill_name, skill_value)

        # Apply skill instance choices: Local Expert (all), Play Instrument (Rockerboy), Science (Tech/Medtech)
        local_expert_area = skill_instance_choices.get("local_expert") or "Unknown"
        char.set_skill_instance("local_expert", local_expert_area, 2)
        if role == "Rockerboy":
            play_inst = skill_instance_choices.get("play_instrument") or "guitar"
            char.set_skill_instance("play_instrument", play_inst, 2)
        if role in ("Tech", "Medtech"):
            science_skill = skill_instance_choices.get("science") or "zoology"
            char.set_skill(science_skill, 2)
            if hasattr(sheet, science_skill):
                setattr(sheet, science_skill, 2)

        # Medtech: set Medicine specialties from menu or defaults
        if role == "Medtech":
            if medicine_specialties:
                char.db.medicine_surgery = medicine_specialties.get("surgery", 2)
                char.db.medicine_pharma = medicine_specialties.get("pharma", 1)
                char.db.medicine_cryo = medicine_specialties.get("cryo", 1)
            else:
                char.db.medicine_surgery = 2
                char.db.medicine_pharma = 1
                char.db.medicine_cryo = 1

        # Tech: set Maker specialties from menu or defaults (2,2,2,2 = 8 total for Maker 4)
        if role == "Tech":
            if maker_specialties:
                char.db.maker_field = maker_specialties.get("field", 2)
                char.db.maker_upgrade = maker_specialties.get("upgrade", 2)
                char.db.maker_fabrication = maker_specialties.get("fabrication", 2)
                char.db.maker_invention = maker_specialties.get("invention", 2)
            else:
                char.db.maker_field = 2
                char.db.maker_upgrade = 2
                char.db.maker_fabrication = 2
                char.db.maker_invention = 2
        
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
        
        # Streetslang 4 only at start - other languages come from lifepath (Cultural Origin)
        char.add_language("Streetslang", 4)
        
        # Save the sheet again after all assignments (for backward compatibility)
        sheet.save()
        
        # Recalculate derived stats using Character's method
        char.recalculate_derived_stats()
        # HP is always full after edgerunner chargen
        char.db.current_hp = char.db.max_hp
        sheet._current_hp = char.db.current_hp
        sheet._max_hp = char.db.max_hp
        sheet.save(skip_recalculation=True)

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

    def complete_package_chargen(self, char, sheet, medicine_specialties=None, maker_specialties=None, skill_instance_choices=None):
        """Create character using complete package method."""
        # Set default stats (all 1's, already handled at character creation)
        
        # Set eurodollars
        char.db.eurodollars = 2550
        
        # Set default skills to 2 (local_expert handled via skill_instance_choices)
        default_skills = [
            'athletics', 'brawling', 'concentration', 'conversation', 'education',
            'evasion', 'first_aid', 'human_perception', 'perception',
            'persuasion', 'stealth'
        ]
        
        for skill in default_skills:
            char.set_skill(skill, 2)
        
        # Local Expert, Play Instrument (Rockerboy), Science (Tech/Medtech) from skill instances menu
        role = getattr(char.db, 'role', None) or getattr(sheet, 'role', None)
        skill_instance_choices = skill_instance_choices or {}
        local_expert_area = skill_instance_choices.get("local_expert") or "Unknown"
        char.set_skill_instance("local_expert", local_expert_area, 2)
        if role == "Rockerboy":
            play_inst = skill_instance_choices.get("play_instrument") or "guitar"
            char.set_skill_instance("play_instrument", play_inst, 2)
        if role in ("Tech", "Medtech"):
            science_skill = skill_instance_choices.get("science") or "zoology"
            char.set_skill(science_skill, 2)
            if hasattr(sheet, science_skill):
                setattr(sheet, science_skill, 2)
        
        # Set role ability to 4 (free points per rules)
        if role:
            role_ability_skill = ROLE_ABILITY_SKILLS.get(role)
            if role_ability_skill:
                char.set_skill(role_ability_skill, 4)
                if hasattr(sheet, role_ability_skill):
                    setattr(sheet, role_ability_skill, 4)
            # Medtech: set medicine specialties from EvMenu or defaults
            if role == "Medtech":
                if medicine_specialties:
                    char.db.medicine_surgery = medicine_specialties.get("surgery", 2)
                    char.db.medicine_pharma = medicine_specialties.get("pharma", 1)
                    char.db.medicine_cryo = medicine_specialties.get("cryo", 1)
                else:
                    char.db.medicine_surgery = 2
                    char.db.medicine_pharma = 1
                    char.db.medicine_cryo = 1
            # Tech: set Maker specialties from EvMenu or defaults (2,2,2,2 = 8 total for Maker 4)
            if role == "Tech":
                if maker_specialties:
                    char.db.maker_field = maker_specialties.get("field", 2)
                    char.db.maker_upgrade = maker_specialties.get("upgrade", 2)
                    char.db.maker_fabrication = maker_specialties.get("fabrication", 2)
                    char.db.maker_invention = maker_specialties.get("invention", 2)
                else:
                    char.db.maker_field = 2
                    char.db.maker_upgrade = 2
                    char.db.maker_fabrication = 2
                    char.db.maker_invention = 2
        
        # Streetslang 4 only at start - other languages come from lifepath (Cultural Origin)
        char.add_language("Streetslang", 4)

        # For compatibility
        sheet.eurodollars = 2550
        sheet.fashion_budget_remaining = 800  # 800 eb for fashion/fashionware (use-it-or-lose-it)
        for skill in default_skills:
            setattr(sheet, skill, 2)
        sheet.add_language("Streetslang", 4)
        sheet.save()
        
        remaining_stat, remaining_skill = char.get_remaining_points() if hasattr(char, 'get_remaining_points') else (62, COMPLETE_PACKAGE_SKILL_POOL)
        return (
            f"Character created using the Complete Package method.\n"
            f"You have {remaining_stat} stat points and {remaining_skill} skill points remaining to allocate (62 stat, {COMPLETE_PACKAGE_SKILL_POOL} skill total).\n"
            f"You have 800 eb fashion budget for clothing/fashionware (use it or lose it).\n"
            f"Use 'selfstat' to allocate them."
        )

    def reset_character(self):
        """Nuclear reset: fully restore character to baseline. Clears all chargen, lifepath,
        user input, languages, and session state. Character is as if freshly created."""
        char = self.caller
        char_pk = getattr(char, 'pk', None) or getattr(char, 'id', None)

        # --- Clear all languages (before deleting sheets) ---
        char.db.languages = {}
        char.attributes.add("selected_language", "None")
        try:
            if char_pk is not None:
                CharacterLanguage.objects.filter(character_id=char_pk).delete()
                CharacterLanguage.objects.filter(character_sheet__character_id=char_pk).delete()
        except Exception:
            pass

        # --- Delete character sheets (and cascade: inventory, cyberware, sell your soul, etc.) ---
        if hasattr(char, 'character_sheet') and char.character_sheet:
            sheet = char.character_sheet
            if sheet.pk is not None:
                sheet.delete()
        try:
            if char_pk is not None:
                CharacterSheet.objects.filter(character_id=char_pk).delete()
        except Exception:
            pass
        char.db.character_sheet_id = None

        # --- Core identity & stats ---
        char.db.full_name = ""
        char.db.handle = ""
        char.db.chargen_method = ""
        char.db.role = ""
        char.db.gender = ""
        char.db.age = 0
        char.db.hometown = ""
        char.db.height = 0
        char.db.weight = 0

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

        char.db.max_hp = 10 + (5 * ((char.db.body + char.db.willpower) // 2))
        char.db.current_hp = char.db.max_hp
        char.db.humanity = char.db.empathy * 10
        char.db.humanity_loss = 0
        char.db.total_cyberware_humanity_loss = 0
        char.db.serious_wounds = char.db.body
        char.db.death_save = char.db.body

        # --- Economy & IP ---
        char.db.eurodollars = 0
        char.db.reputation_points = 0
        char.db.rep = 0
        char.db.notoriety_points = 0
        char.db.notoriety = 0
        char.db.improvement_points = 0
        char.db.ip_spent = 0
        char.db.ip_staff_awarded = 0
        char.db.ip_log = []
        char.db.ip_last_purchase = None

        # --- Status & flags ---
        char.db.is_complete = False
        char.db.has_cyberarm = False
        char.db.combat_position = 0

        # --- Medtech specialties ---
        char.db.medicine_surgery = 0
        char.db.medicine_pharma = 0
        char.db.medicine_cryo = 0
        char.db.maker_field = 0
        char.db.maker_upgrade = 0
        char.db.maker_fabrication = 0
        char.db.maker_invention = 0

        # --- Faction ---
        char.db.faction = None
        char.db.faction_rep = {}

        # --- Lifepath (all user-chosen / rolled background) ---
        char.db.lifepath = {}
        char.db.cultural_origin = ""
        char.db.personality = ""
        char.db.clothing_style = ""
        char.db.hairstyle = ""
        char.db.affectation = ""
        char.db.motivation = ""
        char.db.life_goal = ""
        char.db.valued_person = ""
        char.db.valued_possession = ""
        char.db.family_background = ""
        char.db.environment = ""
        char.db.family_crisis = ""
        char.db.role_lifepath = {}

        # --- Skills ---
        char.db.skills = {skill: 0 for skill in (char.db.skills or {})}
        char.db.skill_instances = {}

        # --- OOC / user input (finger, alias, shortdesc, alts) ---
        char.db.shortdesc = ""
        char.db.public_alts = []
        if char.attributes.has("alias"):
            char.attributes.remove("alias")
        if char.attributes.has("finger_data"):
            char.attributes.remove("finger_data")

        # --- Notes & notifications (preserve +notes) ---
        char.db.notifications = {
            "say": True, "pose": True, "emit": True,
            "page": True, "whisper": True, "new_page": True,
        }
        if char.attributes.has("notification_settings"):
            char.attributes.remove("notification_settings")

        # --- Clear session state (EvMenu, chargen flow, sell your soul, etc.) ---
        try:
            if hasattr(char.ndb, "clear"):
                char.ndb.clear()
        except Exception:
            pass

        self.caller.msg("Your character has been fully reset to baseline. All chargen, lifepath, and character data cleared.")

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

        # Refresh from DB to ensure we use latest data (chargen room does this before display)
        sheet.refresh_from_db()

        # Use character typeclass (source of truth) for point calculation; sheet can be stale
        # and doesn't handle skill_instances or double-cost skills correctly.
        char = self.caller
        if hasattr(char, 'get_remaining_points'):
            try:
                remaining_stat_points, remaining_skill_points = char.get_remaining_points()
            except Exception:
                remaining_stat_points, remaining_skill_points = sheet.get_remaining_points()
        else:
            remaining_stat_points, remaining_skill_points = sheet.get_remaining_points()
        total_remaining_points = remaining_stat_points + remaining_skill_points

        if total_remaining_points > 0:
            self.caller.msg(f"You still have {total_remaining_points} points to spend ({remaining_stat_points} stat points and {remaining_skill_points} skill points). Use 'selfstat' to allocate them before finishing.")
            return

        sheet.is_complete = True
        sheet.save()
        self.caller.msg("Character creation complete. Your character sheet is now locked for approval.")
        
        # Create a +job indicating that the character is ready for approval
        queue, _ = Queue.objects.get_or_create(
            name="Approval",
            defaults={"automatic_assignee": None}
        )
        char_name = getattr(self.caller.db, "full_name", None) or self.caller.key or "Unknown"
        Job.objects.create(
            title=f"Character approval: {char_name}",
            description="Character is ready for approval",
            requester=self.caller.account,
            queue=queue,
            status="open",
            template_args={"character_id": self.caller.id, "character_name": char_name},
        )


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
      selfstat handgun=6
      selfstat play instrument(guitar)=3
      selfstat Spanish=4
      selfstat Japanese=6

    Languages cost 1 skill point per rank (max rank 6). Role abilities cannot be
    modified at chargen (they start at 4); improve them with +ip during play.
    Role abilities cannot be modified at chargen; they start at 4 and are improved with +ip during play.
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
                skill_pool = EDGERUNNER_SKILL_POOL if (char.db.chargen_method or "").strip().lower() == "edgerunner" else COMPLETE_PACKAGE_SKILL_POOL
                remaining_skill_points = max(0, skill_pool - skill_points_spent)

                if remaining_skill_points <= 0 and points_needed > 0:
                    self.caller.msg("You have no skill points remaining. Lower a skill or language value first to free up points.")
                    return
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
            # Edgerunner: stats are pre-assigned from the table; no allocation
            if (char.db.chargen_method or "").strip().lower() == "edgerunner":
                self.caller.msg("Edgerunner characters have pre-assigned stats from the role table. Use 'selfstat' to allocate skill points only.")
                return

            try:
                value = int(value)
                if value < CHARGEN_STAT_MIN or value > CHARGEN_STAT_MAX:
                    self.caller.msg(f"Stat value must be between {CHARGEN_STAT_MIN} and {CHARGEN_STAT_MAX} at chargen.")
                    return
            except ValueError:
                self.caller.msg("You must specify an integer value for stats.")
                return

            # Get current value - use get_attribute so stats come from attributes, never skills
            current_value = char.get_attribute(full_attr_name) if hasattr(char, 'get_attribute') else getattr(char.db, full_attr_name, 1)
            current_value = current_value if current_value is not None else 1
            points_needed = value - current_value

            # Calculate remaining points
            stat_points_spent, _ = char.calculate_spent_points()
            remaining_stat_points = max(0, 62 - stat_points_spent)

            if remaining_stat_points <= 0 and points_needed > 0:
                self.caller.msg("You have no stat points remaining. Lower a stat value first to free up points.")
                return
            if points_needed > remaining_stat_points:
                self.caller.msg(f"Not enough stat points. You need {points_needed} but only have {remaining_stat_points}.")
                return

            # Set the new value directly on the character's DB
            setattr(char.db, full_attr_name, value)

        # Check if this is a skill
        elif full_attr_name in SKILL_MAPPING.values():
            try:
                value = int(value)
            except ValueError:
                self.caller.msg("You must specify an integer value for skills.")
                return

            # Block ALL role abilities during chargen - none can be purchased, only improved with IP in play
            all_role_abilities = frozenset(ROLE_ABILITY_SKILLS.values())
            if full_attr_name in all_role_abilities:
                self.caller.msg(
                    "Role abilities cannot be purchased during character generation. "
                    "Your role ability starts at 4 and can only be improved using improvement points (+ip) during play."
                )
                return

            # Medtech: surgery and medical_tech are derived from medicine specialties
            # use medicine_surgery, medicine_pharma, medicine_cryo instead
            if (char.db.role or "").strip() == "Medtech" and full_attr_name in ("surgery", "medical_tech"):
                self.caller.msg(
                    "For Medtechs, Surgery and Medical Tech are derived from Medicine specialties. "
                    "Use 'selfstat medicine_surgery=', 'medicine_pharma=', or 'medicine_cryo=' instead."
                )
                return

            # Local Expert, Play Instrument, and Martial Arts require an instance (e.g. local_expert(Night City)=4, martial_arts(Krav Maga)=4)
            if full_attr_name in ("local_expert", "play_instrument", "martial_arts") and not instance:
                examples = {
                    "local_expert": "selfstat local_expert(Night City)=4",
                    "play_instrument": "selfstat play_instrument(guitar)=4",
                    "martial_arts": "selfstat martial_arts(Tae Kwon Do)=4",
                }
                example = examples.get(full_attr_name, f"selfstat {full_attr_name}(instance)=value")
                self.caller.msg(
                    f"{full_attr_name.replace('_', ' ').title()} requires an instance. "
                    f"Use 'selfstat {full_attr_name}(instance)=value', e.g. {example}"
                )
                return

            if value < CHARGEN_SKILL_MIN or value > CHARGEN_SKILL_MAX:
                self.caller.msg(f"Skill value must be between {CHARGEN_SKILL_MIN} and {CHARGEN_SKILL_MAX} at chargen.")
                return

            # If instance is provided, handle it as a skill instance
            if instance:
                # Chargen: skill instances 2-8 (no role ability for instances)
                if value < CHARGEN_SKILL_MIN or value > CHARGEN_SKILL_MAX:
                    self.caller.msg(f"Skill instance value must be between {CHARGEN_SKILL_MIN} and {CHARGEN_SKILL_MAX} at chargen.")
                    return

                # Create a skill instance key
                skill_instance_key = f"{full_attr_name}({instance})"
                
                # Get current skill instance value (default 0 if not set)
                current_value = char.get_skill_instance(full_attr_name, instance) if hasattr(char, 'get_skill_instance') else 0
                points_needed = value - current_value
                
                # Check for double-cost skills
                is_double_cost = full_attr_name in ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics_security_tech', 'paramedic']
                actual_points_needed = points_needed * 2 if is_double_cost else points_needed

                # Calculate remaining skill points (Edgerunner and Complete Package: 86)
                _, skill_points_spent = char.calculate_spent_points()
                skill_pool = EDGERUNNER_SKILL_POOL if (char.db.chargen_method or "").strip().lower() == "edgerunner" else COMPLETE_PACKAGE_SKILL_POOL
                remaining_skill_points = max(0, skill_pool - skill_points_spent)

                if remaining_skill_points <= 0 and actual_points_needed > 0:
                    self.caller.msg("You have no skill points remaining. Lower a skill value first to free up points.")
                    return
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
                # Regular skill without instance (role abilities blocked above)
                current_value = char.get_skill(full_attr_name)
                points_needed = value - current_value

                is_double_cost = full_attr_name in ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics_security_tech', 'paramedic']
                actual_points_needed = points_needed * 2 if is_double_cost else points_needed

                _, skill_points_spent = char.calculate_spent_points()
                skill_pool = EDGERUNNER_SKILL_POOL if (char.db.chargen_method or "").strip().lower() == "edgerunner" else COMPLETE_PACKAGE_SKILL_POOL
                remaining_skill_points = max(0, skill_pool - skill_points_spent)

                if remaining_skill_points <= 0 and actual_points_needed > 0:
                    self.caller.msg("You have no skill points remaining. Lower a skill value first to free up points.")
                    return
                if actual_points_needed > remaining_skill_points:
                    self.caller.msg(f"Not enough skill points. You need {actual_points_needed} but only have {remaining_skill_points}.")
                    return

                char.set_skill(full_attr_name, value)

        # Medicine specialties (Medtech only, chargen only) - allocate Medicine rank
        elif full_attr_name in MEDICINE_SPECIALTY_ATTRIBUTES:
            if (char.db.role or "").strip() != "Medtech":
                self.caller.msg("Medicine specialties are only for Medtechs.")
                return
            try:
                value = int(value)
            except ValueError:
                self.caller.msg("You must specify an integer value.")
                return
            medicine = char.get_skill("medicine") or 0
            s = getattr(char.db, "medicine_surgery", 0) or 0
            p = getattr(char.db, "medicine_pharma", 0) or 0
            c = getattr(char.db, "medicine_cryo", 0) or 0
            if full_attr_name == "medicine_surgery":
                s = value
            elif full_attr_name == "medicine_pharma":
                p = value
            else:
                c = value
            ok, err = validate_medicine_specialties(medicine, s, p, c)
            if not ok:
                self.caller.msg(err)
                return
            char.set_medicine_specialty(
                "surgery" if full_attr_name == "medicine_surgery" else "pharma" if full_attr_name == "medicine_pharma" else "cryo",
                value,
            )
            s, p, c = char.get_medicine_specialties()
            self.caller.msg(
                f"Set {full_attr_name.replace('_', ' ').title()} to {value}. "
                f"Medicine allocation: Surgery {s}, Pharma {p}, Cryo {c} (must sum to {medicine})."
            )
            return

        # Maker specialties (Tech only, chargen only) - allocate Maker rank × 2
        elif full_attr_name in MAKER_SPECIALTY_ATTRIBUTES:
            if (char.db.role or "").strip() != "Tech":
                self.caller.msg("Maker specialties are only for Techs.")
                return
            try:
                value = int(value)
            except ValueError:
                self.caller.msg("You must specify an integer value.")
                return
            maker = char.get_skill("maker") or 0
            f = getattr(char.db, "maker_field", 0) or 0
            u = getattr(char.db, "maker_upgrade", 0) or 0
            fab = getattr(char.db, "maker_fabrication", 0) or 0
            inv = getattr(char.db, "maker_invention", 0) or 0
            if full_attr_name == "maker_field":
                f = value
            elif full_attr_name == "maker_upgrade":
                u = value
            elif full_attr_name == "maker_fabrication":
                fab = value
            else:
                inv = value
            ok, err = validate_maker_specialties(maker, f, u, fab, inv)
            if not ok:
                self.caller.msg(err)
                return
            spec = "field" if full_attr_name == "maker_field" else "upgrade" if full_attr_name == "maker_upgrade" else "fabrication" if full_attr_name == "maker_fabrication" else "invention"
            char.set_maker_specialty(spec, value)
            f, u, fab, inv = char.get_maker_specialties()
            self.caller.msg(
                f"Set {full_attr_name.replace('_', ' ').title()} to {value}. "
                f"Maker allocation: Field {f}, Upgrade {u}, Fabrication {fab}, Invention {inv} (must sum to {maker * 2})."
            )
            return

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
            # Weight and height accept decimals (e.g. 70.5 kg, 1.75 m)
            if full_attr_name in ('weight', 'height'):
                try:
                    value = float(value)
                    if value < 0:
                        self.caller.msg(f"{full_attr_name.title()} must be a positive number.")
                        return
                except ValueError:
                    self.caller.msg(f"Please specify a valid number for {full_attr_name} (e.g. 70.5 for kg, 1.75 for meters).")
                    return
            # Age must be integer
            elif full_attr_name == 'age':
                try:
                    value = int(value)
                    if value < 0 or value > 150:
                        self.caller.msg("Age must be between 0 and 150.")
                        return
                except ValueError:
                    self.caller.msg("Please specify an integer for age.")
                    return
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
                # Recalculate when body or has_cyberarm changes (affects unarmed damage)
                if full_attr_name in ('body', 'has_cyberarm'):
                    sheet.recalculate_derived_stats()
                    char.db.unarmed_damage_dice = sheet.unarmed_damage_dice
                    char.db.unarmed_damage_die_type = sheet.unarmed_damage_die_type
                else:
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
