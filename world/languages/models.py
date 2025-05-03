from django.db import models
from django.apps import apps
from evennia.utils.idmapper.models import SharedMemoryModel
from evennia.objects.models import ObjectDB

class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)
    local = models.BooleanField(default=False)
    corporate = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class CharacterLanguage(models.Model):
    # Keep the old field for backward compatibility
    character_sheet = models.ForeignKey(
        'cyberpunk_sheets.CharacterSheet',
        on_delete=models.CASCADE,
        related_name='character_languages',
        null=True,  # Keep it nullable for now
        blank=True  # Allow blank in forms
    )
    # Add new field to link directly to character object
    character = models.ForeignKey(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name='languages',
        null=True,
        blank=True
    )
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    level = models.IntegerField(default=1)

    class Meta:
        # Update unique constraint to include both options
        unique_together = [
            ('character_sheet', 'language'),
            ('character', 'language')
        ]
        # Make sure at least one character field is filled
        constraints = [
            models.CheckConstraint(
                check=models.Q(character__isnull=False) | models.Q(character_sheet__isnull=False),
                name='character_language_has_character'
            )
        ]

    def __str__(self):
        character_name = self._get_character_name()
        return f"{character_name} - {self.language} (Level {self.level})"
    
    def _get_character_name(self):
        """Get character name from typeclass or sheet"""
        # Try character typeclass first
        if self.character:
            if hasattr(self.character.db, 'full_name') and self.character.db.full_name:
                return self.character.db.full_name
            return self.character.key
        
        # Fall back to character sheet
        if self.character_sheet:
            return str(self.character_sheet)
        
        return "Unknown Character"
    
    @classmethod
    def get_or_create_for_character(cls, character, language_name, level=1):
        """Create a language entry for a character, handling both models"""
        # First, get or create the language
        language, _ = Language.objects.get_or_create(
            name=language_name
        )
        
        # Check if we already have an entry for this character and language
        if hasattr(character, 'character_sheet') and character.character_sheet:
            # Try using character sheet relationship
            char_lang, created = cls.objects.get_or_create(
                character_sheet=character.character_sheet,
                language=language,
                defaults={'level': level}
            )
            
            # Also create the character link for future compatibility
            if created:
                char_lang.character = character
                char_lang.save()
                
            return char_lang, created
        else:
            # Use direct character relationship
            return cls.objects.get_or_create(
                character=character,
                language=language,
                defaults={'level': level}
            )
