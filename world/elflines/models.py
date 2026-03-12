"""
Elflines Online models - character sheets and Elflines (guilds).
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from evennia.utils.idmapper.models import SharedMemoryModel
from evennia.objects.models import ObjectDB
from evennia.accounts.models import AccountDB

from .elflines_data import (
    ELO_STATS,
    ELO_SKILLS,
    ELO_MAX_RANK,
    ELO_DEATH_TAX,
    ELO_TITLES_BY_STAT,
)


class ElflineSheet(SharedMemoryModel):
    """
    Elflines Online character sheet. One per Cyberpunk character.
    Uses ELO rules: 50 STAT pts, 60 skill pts, no LUCK, stats 3-8 at creation.
    """

    character = models.OneToOneField(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name="elfline_sheet",
        null=True,
        blank=True,
    )
    character_sheet = models.OneToOneField(
        "cyberpunk_sheets.CharacterSheet",
        on_delete=models.CASCADE,
        related_name="elfline_sheet",
        null=True,
        blank=True,
    )

    elfname = models.CharField(max_length=80, blank=True)
    elfline = models.ForeignKey(
        "Elfline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )

    # Economy
    gp = models.IntegerField(default=200, validators=[MinValueValidator(0)])
    revive_sickness = models.BooleanField(
        default=False,
        help_text="MOVE 1 until 2000gp paid to remove.",
    )
    last_camp_room = models.ForeignKey(
        ObjectDB,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Teleport here on death.",
    )

    # Rank and progression (0-10)
    rank = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(ELO_MAX_RANK)],
    )
    title = models.CharField(max_length=50, blank=True)
    stat_increases_by_rank = models.JSONField(
        default=list,
        help_text="STATs increased at ranks 1-3: ['reflexes','dex','body']",
    )

    # STATs (no LUCK) - 3-8 at creation, max 10
    intelligence = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    reflexes = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    dexterity = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    technology = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    cool = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    willpower = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    move = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    body = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])
    empathy = models.PositiveIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(10)])

    # Skills stored as JSON: {"archery": 4, "melee_weapon": 6, ...}
    # Language (Elven) auto 4
    skills = models.JSONField(default=dict)

    # HP
    max_hp = models.PositiveIntegerField(default=0)
    current_hp = models.PositiveIntegerField(default=0)

    # Equipment (armory item keys)
    equipped_armor = models.CharField(max_length=80, blank=True)
    equipped_weapon = models.CharField(max_length=80, blank=True)
    inventory = models.JSONField(default=list)  # List of armory item keys

    is_complete = models.BooleanField(
        default=False,
        help_text="Sheet has been finalized (50 STAT, 60 skill pts spent, elfname set).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Elfline Sheet"
        verbose_name_plural = "Elfline Sheets"

    def __str__(self):
        return f"ELO: {self.elfname or 'Unnamed'}"

    def save(self, *args, **kwargs):
        self.recalculate_hp()
        super().save(*args, **kwargs)

    def recalculate_hp(self):
        """ELO HP: 10 + (5 * ((BODY + WILL) // 2))"""
        self.max_hp = 10 + (5 * ((self.body + self.willpower) // 2))
        if self.current_hp > self.max_hp or self.current_hp == 0:
            self.current_hp = self.max_hp
        self.current_hp = max(0, min(self.current_hp, self.max_hp))

    def get_effective_move(self):
        """Revive Sickness reduces MOVE to 1."""
        if self.revive_sickness:
            return 1
        return self.move

    def get_title_display(self):
        if self.rank < 3:
            return ""
        if self.title:
            return self.title
        # Determine from stat increases
        if not self.stat_increases_by_rank:
            return ELO_TITLES_BY_STAT.get("even_spread", "Wayfarer")
        from collections import Counter
        counts = Counter(self.stat_increases_by_rank)
        top = counts.most_common(1)
        if top:
            return ELO_TITLES_BY_STAT.get(top[0][0], "Wayfarer")
        return ELO_TITLES_BY_STAT.get("even_spread", "Wayfarer")

    def apply_death(self):
        """On death: teleport to last camp, lose 2000gp or get Revive Sickness."""
        if self.gp >= ELO_DEATH_TAX:
            self.gp -= ELO_DEATH_TAX
            self.revive_sickness = False
        else:
            self.revive_sickness = True
        self.current_hp = self.max_hp
        self.save()


class Elfline(SharedMemoryModel):
    """
    An Elfline (guild) in Elflines Online. Named with {brackets} in-fiction.
    """

    name = models.CharField(max_length=100)
    display_name = models.CharField(
        max_length=120,
        blank=True,
        help_text="In-fiction name with brackets e.g. {nature's_thorns}",
    )
    description = models.TextField(blank=True)
    leader = models.ForeignKey(
        ObjectDB,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_elflines",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Elfline"
        verbose_name_plural = "Elflines"
        ordering = ["name"]

    def __str__(self):
        return self.display_name or self.name

    def get_bracket_name(self):
        """Return name in {brackets} format for display."""
        if self.display_name and self.display_name.strip():
            return self.display_name
        return "{" + self.name.replace(" ", "_").lower() + "}"


class ElflineMembership(SharedMemoryModel):
    """Membership in an Elfline."""

    elfline = models.ForeignKey(
        Elfline,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    character = models.ForeignKey(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name="elfline_memberships",
    )
    role = models.CharField(max_length=50, blank=True)  # e.g. "Recruit", "Officer"
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("elfline", "character")
        verbose_name = "Elfline Membership"
        verbose_name_plural = "Elfline Memberships"

    def __str__(self):
        return f"{self.character} in {self.elfline}"
