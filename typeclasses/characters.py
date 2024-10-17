"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.
"""
from evennia import DefaultCharacter
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.utils.ansi import ANSIString
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider
import logging, re

logger = logging.getLogger('cyberpunk.character')

class Character(DefaultCharacter):
    def at_object_creation(self):
        super().at_object_creation()
        self.db.combat_position = 0  # Default starting position
        self.cmdset.add("commands.default_cmdsets.CharacterCmdSet", permanent=True)
        self.create_character_sheet()

    def create_character_sheet(self):
        try:
            sheet = CharacterSheet.objects.get(character=self)
            logger.info(f"Found existing character sheet for {self.name}")
        except CharacterSheet.DoesNotExist:
            sheet = CharacterSheet(character=self, account=self.account)
            sheet.save()
            logger.info(f"Created new character sheet for {self.name}")
        
        self.db.character_sheet_id = sheet.id
        return sheet

    def initialize_character_sheet(self, sheet):
        sheet.full_name = self.name  # Set the full name to the puppet object's name
        sheet.gender = ""
        sheet.intelligence = 1
        sheet.reflexes = 1
        sheet.dexterity = 1
        sheet.technology = 1
        sheet.cool = 1
        sheet.willpower = 1
        sheet.luck = 1
        sheet.move = 1
        sheet.empathy = 1
        sheet.body = 1
        sheet.save()

    def at_post_puppet(self, **kwargs):
        super().at_post_puppet(**kwargs)
        if not hasattr(self, 'character_sheet'):
            self.create_character_sheet()

    @property
    def character_sheet(self):
        sheet_id = self.db.character_sheet_id
        if sheet_id is not None:
            try:
                sheet = CharacterSheet.objects.get(id=sheet_id)
                if not sheet.full_name:
                    self.initialize_character_sheet(sheet)
                return sheet
            except CharacterSheet.DoesNotExist:
                logger.warning(f"Character sheet with ID {sheet_id} not found for {self.name}")
        return None

    @property
    def humanity(self):
        """Calculate and return the character's humanity."""
        return self.character_sheet.current_humanity if self.character_sheet else None

    def adjust_humanity(self, amount):
        """Adjust the character's humanity."""
        if self.character_sheet:
            self.character_sheet.reduce_humanity(amount)

    def get_attribute(self, attr_name):
        """Get the value of a character attribute."""
        return getattr(self.character_sheet, attr_name, None) if self.character_sheet else None

    def set_attribute(self, attr_name, value):
        """Set the value of a character attribute."""
        if self.character_sheet and hasattr(self.character_sheet, attr_name):
            setattr(self.character_sheet, attr_name, value)
            self.character_sheet.save()
        else:
            raise AttributeError(f"CharacterSheet has no attribute '{attr_name}'")

    @property
    def language_list(self):
        if not self.character_sheet:
            return []
        return [f"{cl.language.name} (Level {cl.level})" 
                for cl in self.character_sheet.character_languages.all()]

    def knows_language(self, language_name):
        if not self.character_sheet:
            return False
        return self.character_sheet.character_languages.filter(
            language__name__iexact=language_name
        ).exists()

    def at_post_move(self, source_location, **kwargs):
        super().at_post_move(source_location, **kwargs)
        if self.character_sheet:
            self.character_sheet.refresh_from_db()

    def return_appearance(self, looker, **kwargs):
        """
        This formats a description for any object looking at this object.
        """
        if not looker:
            return ""
        
        # Get the description
        desc = self.db.desc

        # Start with the name
        string = f"|c{self.get_display_name(looker)}|n\n"

        # Process character description
        if desc:
            # Replace both %t and |- with a consistent tab marker
            desc = desc.replace('%t', '|t').replace('|-', '|t')
            
            paragraphs = desc.split('%r')
            formatted_paragraphs = []
            for p in paragraphs:
                if not p.strip():
                    formatted_paragraphs.append('')  # Add blank line for empty paragraph
                    continue
                
                # Handle tabs manually
                lines = p.split('|t')
                indented_lines = [line.strip() for line in lines]
                indented_text = '\n    '.join(indented_lines)
                
                # Wrap each line individually
                wrapped_lines = [wrap_ansi(line, width=78) for line in indented_text.split('\n')]
                formatted_paragraphs.append('\n'.join(wrapped_lines))
            
            # Join paragraphs with a single newline, and remove any consecutive newlines
            joined_paragraphs = '\n'.join(formatted_paragraphs)
            joined_paragraphs = re.sub(r'\n{3,}', '\n\n', joined_paragraphs)
            
            string += joined_paragraphs + "\n"

        # Add any other details you want to include in the character's appearance
        # For example, you might want to add information about their equipment, stats, etc.

        return string

    def execute_cmd(self, raw_string, session=None, **kwargs):
        # Use regex to match ':' followed immediately by any non-space character
        if re.match(r'^:\S', raw_string):
            # Treat it as a pose command, inserting a space after the colon
            raw_string = "pose " + raw_string[1:]
        return super().execute_cmd(raw_string, session=session, **kwargs)

    def add_note(self, name, text, category='General', is_public=False):
        if self.character_sheet:
            return self.character_sheet.add_note(name, text, category, is_public)
        return None

    def get_note(self, name):
        if self.character_sheet:
            return self.character_sheet.get_note(name)
        return None

    def update_note(self, name, new_text, new_category=None):
        if self.character_sheet:
            return self.character_sheet.update_note(name, new_text, new_category)
        return None

    def delete_note(self, name):
        if self.character_sheet:
            return self.character_sheet.delete_note(name)
        return False

    def get_notes_by_category(self, category):
        if self.character_sheet:
            return self.character_sheet.get_notes_by_category(category)
        return []

    def get_all_notes(self):
        if self.character_sheet:
            return self.character_sheet.get_all_notes()
        return []

    def approve_note(self, name):
        if self.character_sheet:
            return self.character_sheet.approve_note(name)
        return False

    def unapprove_note(self, name):
        if self.character_sheet:
            return self.character_sheet.unapprove_note(name)
        return False

    def change_note_status(self, name, is_public):
        if self.character_sheet:
            return self.character_sheet.change_note_status(name, is_public)
        return False
