from django.db import models
from django.apps import apps
from evennia.utils.idmapper.models import SharedMemoryModel

class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)
    local = models.BooleanField(default=False)
    corporate = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class CharacterLanguage(models.Model):
    character_sheet = models.ForeignKey(
        'cyberpunk_sheets.CharacterSheet',
        on_delete=models.CASCADE,
        related_name='character_languages',
        null=True,  # Keep it nullable for now
        blank=True  # Allow blank in forms
    )
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    level = models.IntegerField(default=1)

    class Meta:
        unique_together = ('character_sheet', 'language')

    def __str__(self):
        return f"{self.character_sheet} - {self.language} (Level {self.level})"
