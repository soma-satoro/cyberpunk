# -*- coding: utf-8 -*-
"""
Maker (Tech Role Ability) craft order models.
Techs can queue fabrication/upgrade jobs; when time elapses, the system auto-rolls and delivers via voucher.
"""
from django.db import models
from evennia.utils.idmapper.models import SharedMemoryModel
from evennia.objects.models import ObjectDB


class CraftOrder(SharedMemoryModel):
    """
    A single item in a Tech's fabrication queue.
    When completed_at is reached, the MakerCraftScript processes it: rolls skill, creates voucher or refunds.
    """

    CRAFT_TYPE_FABRICATION = "fabrication"
    CRAFT_TYPE_UPGRADE = "upgrade"
    CRAFT_TYPE_PHARMA = "pharma"  # MedTech pharmaceutical crafting
    CRAFT_TYPE_PROGRAM = "program"  # Netrunner program crafting
    CRAFT_TYPE_DECKOPTION = "deckoption"  # Netrunner deck option (hardware) crafting
    CRAFT_TYPE_CHOICES = [
        (CRAFT_TYPE_FABRICATION, "Fabrication"),
        (CRAFT_TYPE_UPGRADE, "Upgrade"),
        (CRAFT_TYPE_PHARMA, "Pharmaceutical"),
        (CRAFT_TYPE_PROGRAM, "Program"),
        (CRAFT_TYPE_DECKOPTION, "Deck Option"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    # Tech (or MedTech for pharma) performing the craft
    crafter = models.ForeignKey(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name="maker_craft_orders",
        help_text="Character (Tech/MedTech) doing the crafting",
    )

    craft_type = models.CharField(max_length=20, choices=CRAFT_TYPE_CHOICES, default=CRAFT_TYPE_FABRICATION)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)

    # Item being crafted
    item_type = models.CharField(max_length=20)  # weapon, armor, gear, cyberware, ammunition, vehicle, drug
    item_name = models.CharField(max_length=255)
    item_category = models.CharField(max_length=100, blank=True)  # e.g. Electronics, land
    item_data = models.JSONField(default=dict)  # Serialized item stats for voucher creation

    # Cost and timing
    materials_cost = models.PositiveIntegerField(default=0)  # eb paid by Tech
    price_category = models.CharField(max_length=30, default="Cheap/Everyday")
    dv = models.PositiveIntegerField(default=9)
    time_hours = models.PositiveIntegerField(default=1)

    # Skill used (tech_skill key, e.g. weaponstech, basic_tech)
    tech_skill = models.CharField(max_length=50, default="basic_tech")
    specialty_rank = models.PositiveIntegerField(default=0)  # Fabrication/Upgrade/Pharma specialty

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)  # When craft began (for time calculation)
    completed_at = models.DateTimeField(null=True, blank=True)  # When to process (roll + deliver)

    # Result
    roll_result = models.IntegerField(null=True, blank=True)  # Total of TECH + skill + specialty + 1d10
    success = models.BooleanField(null=True, blank=True)
    voucher = models.ForeignKey(
        ObjectDB,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maker_craft_source",
        help_text="Voucher created on success",
    )

    # Optional: who receives the item (default: crafter). For commissioned work.
    recipient = models.ForeignKey(
        ObjectDB,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maker_craft_recipient",
    )

    class Meta:
        app_label = "maker"
        ordering = ["completed_at", "created_at"]

    def __str__(self):
        return f"CraftOrder #{self.id}: {self.item_name} ({self.craft_type}) by {self.crafter_id}"
