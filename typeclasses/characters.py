"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.
"""
from evennia import DefaultCharacter
from world.cyberpunk_sheets.models import CharacterSheet
import logging

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
        return [f"{lang.language.name if hasattr(lang.language, 'name') else lang.language['name']} (Level {lang.level})" 
                for lang in self.character_languages.all()]

    def at_post_move(self, source_location, **kwargs):
        super().at_post_move(source_location, **kwargs)
        if self.character_sheet:
            self.character_sheet.refresh_from_db()
