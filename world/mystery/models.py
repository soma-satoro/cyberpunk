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
    last_concentrate_date = models.DateField(
        null=True,
        blank=True,
        help_text="Last date +rest/concentrate was used (once per day for +5 bonus).",
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
    """An investigation mystery with Goal and Complexity (Interface RED)."""
    name = models.CharField(max_length=255)
    goal = models.TextField(help_text="End state: e.g., who stole the cyberware.")
    difficulty_level = models.CharField(
        max_length=30,
        default="average",
        help_text="easy, average, challenging, difficult, legendary",
    )
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
    public_description = models.TextField(
        blank=True,
        default="",
        help_text="Player-facing summary for +mystery and +mystery/info.",
    )
    starting_location_hint = models.TextField(
        blank=True,
        default="",
        help_text="Where to start looking (relative location).",
    )
    scan_dv = models.PositiveSmallIntegerField(
        default=13,
        help_text="DV for +investigate/scan where this mystery's clues appear.",
    )

    def __str__(self):
        return self.name

    def solve(self):
        self.is_solved = True
        self.current_complexity = 0
        self.save()
        if self.mission:
            from world.mystery.services import update_mission_on_mystery_solve
            update_mission_on_mystery_solve(self)


class MysteryFollower(SharedMemoryModel):
    """Character is following a mystery (manual +auto from mission link)."""

    character = models.ForeignKey(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name="mystery_follows",
    )
    mystery = models.ForeignKey(
        Mystery,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["character", "mystery"]]

    def __str__(self):
        return f"{self.character_id} -> Mystery #{self.mystery_id}"


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
    fumble_effect = models.TextField(
        blank=True,
        help_text="Special consequence on Fumble (roll 1 and fail). Overrides CLUE_TYPES default.",
    )
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
    player_hint = models.TextField(
        blank=True,
        default="",
        help_text="Shown when this clue is exposed to a character (after scan).",
    )
    discovery_priority = models.PositiveSmallIntegerField(
        default=0,
        help_text="Lower = appears earlier on scan results.",
    )
    gating_obstacle = models.ForeignKey(
        "MysteryObstacle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gated_clues",
        help_text="If set, character must overcome this obstacle before the clue can be exposed or investigated.",
    )

    def __str__(self):
        return f"{self.mystery.name}: {self.clue_type}"

    def get_skills_list(self):
        return [s.strip() for s in self.skills_used.split(",") if s.strip()]


class ClueLocation(SharedMemoryModel):
    """Links a MysteryClue to a location (room, NPC, object, exit) on the grid."""
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
    element_key = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Named feature within a room (e.g. storm drain). Empty = whole target (room-wide, object, or exit).",
    )

    class Meta:
        unique_together = [["clue", "location_object", "element_key"]]

    def __str__(self):
        if self.element_key:
            return f"{self.clue} @ {self.location_object} ({self.element_key})"
        return f"{self.clue} @ {self.location_object}"


class ClueExposure(SharedMemoryModel):
    """A character has 'noticed' this clue (via scan); may then attempt evidence checks."""

    character = models.ForeignKey(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name="clue_exposures",
    )
    clue = models.ForeignKey(
        MysteryClue,
        on_delete=models.CASCADE,
        related_name="exposures",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["character", "clue"]]

    def __str__(self):
        return f"{self.character} sees clue {self.clue_id}"


class MysteryObstacle(SharedMemoryModel):
    """Obstacle linked to a Mystery. Overcome = 1d6 Focus damage; fail = 2d6 Focus damage."""
    mystery = models.ForeignKey(
        Mystery,
        on_delete=models.CASCADE,
        related_name="obstacles",
    )
    obstacle_type = models.CharField(
        max_length=50,
        help_text="Authority, Digital, Distraction, etc.",
    )
    description = models.TextField(blank=True)
    skill_used = models.CharField(
        max_length=80,
        blank=True,
        help_text="Skill for overcoming (e.g. streetwise, persuasion).",
    )
    dv = models.PositiveIntegerField(
        default=13,
        help_text="Difficulty Value for overcoming.",
    )
    is_ticking_clock = models.BooleanField(
        default=False,
        help_text="Time-sensitive obstacle.",
    )

    def __str__(self):
        return f"{self.mystery.name}: {self.obstacle_type}"


class ObstacleAttempt(SharedMemoryModel):
    """Tracks Obstacle overcome attempts (one per Obstacle per character per day)."""
    character = models.ForeignKey(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name="obstacle_attempts",
    )
    obstacle = models.ForeignKey(
        MysteryObstacle,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    attempted_date = models.DateField()
    success = models.BooleanField(default=False)
    focus_lost = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [["obstacle", "character", "attempted_date"]]


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
