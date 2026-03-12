"""Did Someone Say Murder? - Investigation System models."""

from django.db import models
from evennia.utils.idmapper.models import SharedMemoryModel
from evennia.objects.models import ObjectDB


class CharacterFocus(SharedMemoryModel):
    """Tracks Focus pool for investigation system. One per character."""
    character_sheet = models.OneToOneField(
        "cyberpunk_sheets.CharacterSheet",
        on_delete=models.CASCADE,
        related_name="mystery_focus",
        null=True,
        blank=True,
    )
    character_object = models.OneToOneField(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name="mystery_focus",
        null=True,
        blank=True,
    )
    current_focus = models.IntegerField(
        default=0,
        help_text="Depletes on failed Evidence Checks. At 0 or below, cannot make Evidence Checks.",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(character_sheet__isnull=False) | models.Q(character_object__isnull=False),
                name="mystery_focus_has_character",
            )
        ]

    def get_max_focus(self):
        from .mystery_data import get_max_focus
        int_val = will_val = 5
        if self.character_sheet:
            int_val = getattr(self.character_sheet, "intelligence", 5) or 5
            will_val = getattr(self.character_sheet, "willpower", 5) or 5
        elif self.character_object:
            int_val = getattr(self.character_object.db, "intelligence", 5) or 5
            will_val = getattr(self.character_object.db, "willpower", 5) or 5
        return get_max_focus(int_val, will_val)

    def can_investigate(self):
        return self.current_focus > 0


class Mystery(SharedMemoryModel):
    """An investigation mystery with Goal and Complexity."""
    name = models.CharField(max_length=255)
    goal = models.TextField(help_text="End state: e.g., who stole the cyberware.")
    max_complexity = models.PositiveIntegerField(
        default=50,
        help_text="Initial Complexity. When reduced to 0, mystery is solved.",
    )
    current_complexity = models.PositiveIntegerField(default=50)
    is_solved = models.BooleanField(default=False)
    mission = models.ForeignKey(
        "mission_board.Mission",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mysteries",
    )
    created_by = models.ForeignKey(
        ObjectDB,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_mysteries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def solve(self):
        self.is_solved = True
        self.current_complexity = 0
        self.save()
        if self.mission:
            from world.mystery.services import update_mission_on_mystery_solve
            update_mission_on_mystery_solve(self)


class MysteryClue(SharedMemoryModel):
    """A clue linked to a Mystery."""
    mystery = models.ForeignKey(
        Mystery,
        on_delete=models.CASCADE,
        related_name="clues",
    )
    clue_type = models.CharField(
        max_length=50,
        help_text="auditing, autopsy, forensics, gossip, etc.",
    )
    skills_used = models.CharField(
        max_length=200,
        help_text="Comma-separated: accounting, bureaucracy",
    )
    dv = models.PositiveIntegerField(default=13)
    damage_dice = models.CharField(max_length=20, default="3d6")
    focus_damage_dice = models.CharField(max_length=20, default="2d6")
    obfuscation = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    # Clues that must be successfully deciphered before this clue can be attempted
    required_clues = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="unlocks",
    )
    # Linked clues (informational; for staff to see relationships)
    linked_clues = models.ManyToManyField(
        "self",
        symmetrical=True,
        blank=True,
        related_name="linked_to",
    )

    def __str__(self):
        return f"{self.mystery.name}: {self.clue_type}"

    def get_skills_list(self):
        return [s.strip() for s in self.skills_used.split(",") if s.strip()]


class ClueLocation(SharedMemoryModel):
    """Links a MysteryClue to a location (room, NPC, object) on the grid."""
    clue = models.ForeignKey(
        MysteryClue,
        on_delete=models.CASCADE,
        related_name="locations",
    )
    location_object = models.ForeignKey(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name="mystery_clues",
    )

    class Meta:
        unique_together = [["clue", "location_object"]]

    def __str__(self):
        return f"{self.clue} @ {self.location_object}"


class ClueAttempt(SharedMemoryModel):
    """Tracks Evidence Check attempts (one per Clue per character per day)."""
    character = models.ForeignKey(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name="clue_attempts",
    )
    clue = models.ForeignKey(
        MysteryClue,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempted_date = models.DateField(
        help_text="Used to enforce one Evidence Check per Clue per day.",
    )
    success = models.BooleanField(default=False)
    damage_dealt = models.PositiveIntegerField(default=0)
    focus_lost = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [["clue", "character", "attempted_date"]]
