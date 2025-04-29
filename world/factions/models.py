from django.db import models
from evennia.utils.idmapper.models import SharedMemoryModel
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.typeclasses.models import TypedObject
from evennia.utils import logger

class Group(SharedMemoryModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    ic_description = models.TextField(blank=True)
    leader = models.ForeignKey(CharacterSheet, on_delete=models.SET_NULL, null=True, related_name='led_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        logger.log_info(f"Saving Group: {self.name}")
        logger.log_info(f"Current leader: {self.leader}")
        super().save(*args, **kwargs)
        logger.log_info(f"Group saved. Leader after save: {self.leader}")

    @property
    def leader_object(self):
        """Returns the leader's db_object if it exists, otherwise None."""
        return self.leader.db_object if self.leader else None

class GroupRole(SharedMemoryModel):
    name = models.CharField(max_length=50)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='roles')
    can_invite = models.BooleanField(default=False)
    can_kick = models.BooleanField(default=False)
    can_promote = models.BooleanField(default=False)
    can_edit_info = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.group.name}"

class GroupMembership(SharedMemoryModel):
    character = models.ForeignKey(CharacterSheet, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    role = models.ForeignKey(GroupRole, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('character', 'group')

    def __str__(self):
        return f"{self.character.full_name} - {self.group.name} ({self.role.name if self.role else 'No Role'})"

class GroupJoinRequest(SharedMemoryModel):
    character = models.ForeignKey(CharacterSheet, on_delete=models.CASCADE, related_name='join_requests')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='join_requests')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('character', 'group')

    def __str__(self):
        return f"{self.character.full_name} - {self.group.name}"

class Faction(SharedMemoryModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    ic_description = models.TextField(blank=True)
    influence = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class FactionReputation(SharedMemoryModel):
    character = models.ForeignKey(CharacterSheet, on_delete=models.CASCADE)
    faction = models.ForeignKey(Faction, on_delete=models.CASCADE)
    reputation = models.IntegerField(default=0)

    class Meta:
        unique_together = ('character', 'faction')

    def __str__(self):
        return f"{self.character} - {self.faction}: {self.reputation}"

class GroupInfo(TypedObject):
    """
    This model stores group and faction information for characters.
    """
    db_character = models.OneToOneField('objects.ObjectDB', related_name='group_info', on_delete=models.CASCADE)
    db_group_description = models.TextField(blank=True, default="")
    db_faction_description = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Group Info"
        verbose_name_plural = "Group Data"

    def __str__(self):
        return f"Group Info for {self.db_character}"
    
from django.contrib.auth.models import User
from django.db import models
from django.conf import settings

class Roster(models.Model):
    """Model for managing character rosters."""
    ROSTER_CHOICES = [
        ('ganger', 'Ganger'),
        ('nomad', 'Nomad'),
        ('corporate', 'Corporate'),
        ('mercenary', 'Mercenary'),
        ('other', 'Other')
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    roster_type = models.CharField(max_length=50, choices=ROSTER_CHOICES, default='other')
    website = models.URLField(blank=True)
    admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='administered_rosters',
        blank=True
    )
    managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='managed_rosters',
        blank=True
    )
    hangouts = models.ManyToManyField(
        'objects.ObjectDB',
        related_name='roster_hangouts',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'cyberpunk'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_members(self):
        """Get all approved members of this roster."""
        return self.members.filter(approved=True)

    def get_online_members(self):
        """Get all online approved members of this roster."""
        return self.members.filter(
            approved=True,
            character__db_account__db_is_connected=True
        )

    def can_manage(self, account):
        """Check if an account can manage this roster."""
        if not account:
            return False
        return (
            account.is_staff or 
            self.admins.filter(id=account.id).exists() or 
            self.managers.filter(id=account.id).exists()
        )

class RosterMember(models.Model):
    """Model for tracking character membership in rosters."""
    roster = models.ForeignKey(
        Roster,
        on_delete=models.CASCADE,
        related_name='members'
    )
    character = models.ForeignKey(
        'objects.ObjectDB',
        on_delete=models.CASCADE,
        related_name='roster_memberships'
    )
    title = models.CharField(max_length=255, blank=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_roster_members'
    )
    approved_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'cyberpunk'
        unique_together = ('roster', 'character')
        ordering = ['character__db_key']

    def __str__(self):
        return f"{self.character} in {self.roster}" 