"""
Mission Board models - virtual mission board for Fixers and Staff to post jobs.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from evennia.utils.idmapper.models import SharedMemoryModel
from evennia.objects.models import ObjectDB
from evennia.accounts.models import AccountDB


class StorySeed(SharedMemoryModel):
    """
    Staff-created plot seeds available on the fixer-only board.
    Fixers grab seeds and create missions from them. Max budget is staff allocation;
    fixer sets player payout; fixer's cut = max_budget - payout.
    """
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('claimed', 'Claimed'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField()
    # Max total budget (eddies) - fixer's cut + player payout cannot exceed this
    max_budget = models.IntegerField(default=0)
    # Optional rewards (items/vouchers) - passed through to mission
    voucher_rewards = models.JSONField(default=list)
    item_rewards = models.JSONField(default=list)
    # Rep amounts for the mission (fixer can use or adjust)
    rep_amount = models.IntegerField(default=0)
    faction_rep_amount = models.IntegerField(default=0)
    faction = models.ForeignKey(
        'factions.Faction', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='story_seeds', help_text="Faction the faction_rep_amount applies to"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='created_story_seeds'
    )
    claimed_by = models.ForeignKey(
        ObjectDB, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='claimed_story_seeds'
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'mission_board'
        ordering = ['-created_at']

    def __str__(self):
        return f"StorySeed #{self.id}: {self.name}"


class Mission(SharedMemoryModel):
    """A mission posted to the virtual mission board."""

    STATUS_CHOICES = [
        ('open', 'Open'),       # Available for acceptance
        ('active', 'Active'),   # Has team, in progress
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    GM_TYPE_CHOICES = [
        ('assigned', 'Assigned'),  # GM was explicitly assigned
        ('pickup', 'Pickup'),      # Any staff/storyteller can claim
    ]

    FAILURE_PENALTY_SCOPE = [
        ('leader', 'Leader only'),
        ('team', 'Entire team'),
    ]

    # Core info
    name = models.CharField(max_length=255)
    description = models.TextField()
    posted_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    # Poster: Fixer character or staff (use character for display name)
    posted_by = models.ForeignKey(
        ObjectDB, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='posted_missions'
    )
    posted_by_staff = models.BooleanField(default=False)  # True = staff created, uncapped rewards

    # Money payout
    money_amount = models.IntegerField(default=0)
    money_pay_on_delivery = models.BooleanField(default=False)

    # Rep payout (points, Fixer max 20, staff uncapped)
    rep_amount = models.IntegerField(default=0)  # General/street rep
    faction_rep_amount = models.IntegerField(default=0)  # Rep with mission's faction (if faction set)
    # Faction this mission is for (enables faction missions, faction rep, visibility)
    faction = models.ForeignKey(
        'factions.Faction', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='missions'
    )
    # public = everyone sees; faction_only = only faction members see
    faction_visibility = models.CharField(
        max_length=20, default='public',
        choices=[('public', 'Public'), ('faction_only', 'Faction Only')]
    )

    # Item/voucher rewards - stored as list of dbrefs
    voucher_rewards = models.JSONField(default=list)  # [dbref, dbref, ...]
    item_rewards = models.JSONField(default=list)     # [dbref, dbref, ...]
    rewards_pay_on_delivery = models.BooleanField(default=False)

    # Failure handling
    failure_penalty_amount = models.IntegerField(default=0)  # Eurodollar penalty
    failure_penalty_scope = models.CharField(
        max_length=10, choices=[(s, s) for s in ['leader', 'team']],
        default='leader', blank=True
    )

    # GM assignment - use character (ObjectDB) for display; keep gm account for job sync
    gm_character = models.ForeignKey(
        ObjectDB, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='gm_missions'
    )
    gm = models.ForeignKey(
        AccountDB, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='gm_missions'
    )  # Denormalized for job sync; set when gm_character set
    gm_type = models.CharField(max_length=20, choices=GM_TYPE_CHOICES, default='pickup')

    # Linked job for tracking
    job = models.ForeignKey(
        'jobs.Job', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mission'
    )
    # When mission created from fixer grabbing a story seed
    source_seed = models.ForeignKey(
        'StorySeed', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='missions'
    )

    # Updates and scene info
    updates = models.JSONField(default=list)  # [{"date": "...", "author": "...", "text": "..."}]
    scene_description = models.TextField(blank=True)
    scene_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'mission_board'
        ordering = ['-posted_date']

    def __str__(self):
        return f"Mission #{self.id}: {self.name}"

    def get_poster_name(self):
        """Display name of poster (Fixer or staff)."""
        if self.posted_by:
            if hasattr(self.posted_by.db, 'full_name') and self.posted_by.db.full_name:
                return self.posted_by.db.full_name
            return self.posted_by.key
        return "Staff"

    def get_team_in_order(self):
        """Return team members in add order (lead first, then by MissionTeamMember.order)."""
        return list(
            self.team_members.order_by('order').values_list('character', flat=True)
        )


class FactionMissionPoster(SharedMemoryModel):
    """Characters designated by faction head to post missions for a faction."""
    faction = models.ForeignKey(
        'factions.Faction', on_delete=models.CASCADE, related_name='mission_posters'
    )
    character = models.ForeignKey(ObjectDB, on_delete=models.CASCADE)

    class Meta:
        app_label = 'mission_board'
        unique_together = ('faction', 'character')


class MissionTeamMember(SharedMemoryModel):
    """Tracks characters on a mission team, preserving add order."""
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name='team_members')
    character = models.ForeignKey(ObjectDB, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)  # 0 = lead (first accept), 1+ = added members
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'mission_board'
        unique_together = ('mission', 'character')
        ordering = ['order']
