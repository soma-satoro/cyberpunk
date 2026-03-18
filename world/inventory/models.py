from django.db import models
from django.db.utils import IntegrityError
from evennia.utils.idmapper.models import SharedMemoryModel
from world.cyberware.models import Cyberware
from django.db.models import JSONField  # If using PostgreSQL
from evennia.objects.models import ObjectDB

class AmmoType(models.TextChoices):
    BASIC = 'Basic', 'Basic Ammunition'
    ARMOR_PIERCING = 'Armor-Piercing', 'Armor-Piercing Ammunition'
    BIOTOXIN = 'Biotoxin', 'Biotoxin Ammunition'
    BURROWING = 'Burrowing', 'Burrowing Ammunition'
    EMP = 'EMP', 'EMP Ammunition'
    EXPLOSIVE = 'Explosive', 'Explosive Ammunition'
    EXPANSIVE = 'Expansive', 'Expansive Ammunition'
    FLASHBANG = 'Flashbang', 'Flashbang Ammunition'
    HIGH_PRECISION = 'High Precision', 'High Precision Ammunition'
    HIGH_VELOCITY = 'High Velocity', 'High Velocity Ammunition'
    HOLLOW_POINT = 'Hollow Point', 'Hollow Point Ammunition'
    HYPER_EXPANSIVE = 'Hyper Expansive', 'Hyper Expansive Ammunition'
    INCENDIARY = 'Incendiary', 'Incendiary Ammunition'
    POISON = 'Poison', 'Poison Ammunition'
    RUBBER = 'Rubber', 'Rubber Ammunition'
    SERRATED_ARROW = 'Serrated Arrow', 'Serrated Arrow Ammunition'
    SLEEP = 'Sleep', 'Sleep Ammunition'
    SMART = 'Smart', 'Smart Ammunition'
    SMOKE = 'Smoke', 'Smoke Ammunition'
    TEARGAS = 'Teargas', 'Teargas Ammunition'
    TRACER = 'Tracer', 'Tracer Ammunition'
    JUNK = 'Junk', 'Junk Ammunition'
    ARROWHYPO = 'Arrowhypo', 'Arrowhypo Ammunition'
    AIRBURST = 'Airburst', 'Airburst Ammunition'

class Ammunition(SharedMemoryModel):
    name = models.CharField(max_length=100)
    ammo_type = models.CharField(max_length=20, choices=AmmoType.choices)
    quantity = models.PositiveIntegerField(default=0)
    cost = models.IntegerField()  # Cost per unit
    weapon_type = models.CharField(max_length=100, default='Generic')
    damage_modifier = models.IntegerField(default=0)
    armor_piercing = models.IntegerField(default=0)
    description = models.CharField(max_length=200, default='Standard ammunition')

    def __str__(self):
        return f"{self.name} ({self.quantity})"

    @classmethod
    def get_cost_category(cls, ammo_type):
        if ammo_type in ['Basic', 'Rubber']:
            return 10
        elif ammo_type in ['Armor-Piercing', 'Expansive', 'Flashbang', 'Incendiary', 'Poison',
                           'Burrowing', 'Explosive', 'High Precision', 'High Velocity',
                           'Hyper Expansive', 'Serrated Arrow', 'Hollow Point']:
            return 100
        elif ammo_type in ['Biotoxin', 'EMP', 'Sleep', 'Smart']:
            return 500
        elif ammo_type in ['Smoke', 'Teargas', 'Tracer']:
            return 50
        else:
            return 0  # or some default value
        
class Item(SharedMemoryModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    weight = models.FloatField(default=0)
    value = models.IntegerField(default=0)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

# Update to match the definition in cyberware/models.py
class CyberwareInstance(SharedMemoryModel):
    cyberware = models.ForeignKey(Cyberware, on_delete=models.CASCADE, related_name='inventory_app_instances')
    # For backward compatibility with CharacterSheet
    character_sheet = models.ForeignKey(
        'cyberpunk_sheets.CharacterSheet', 
        related_name='cyberware_instances',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    # New direct link to character object
    character_object = models.ForeignKey(
        ObjectDB,
        related_name='cyberware_objects',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    installed = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    # For Popup Melee/Ranged Weapon: stores weapon name from equipment_data when installed
    popup_weapon_name = models.CharField(max_length=100, blank=True)
    # Parent: options (Image Enhance, Popup Shotgun, etc.) link to their base piece (Cybereye, Cyberarm, etc.)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    # Paired: second Cybereye/Cyberarm/Cyberleg points to the first (paired_with=first_instance)
    paired_with = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paired_instances",
    )
    
    class Meta:
        # Ensure at least one character field is populated
        constraints = [
            models.CheckConstraint(
                condition=models.Q(character_object__isnull=False) | models.Q(character_sheet__isnull=False),
                name='inventory_cyberware_instance_has_character'
            )
        ]

    def __str__(self):
        return f"{self.cyberware.name} - {self.get_character_name()}"
        
    def get_character_name(self):
        """Get the character's name from typeclass or sheet"""
        # Try character typeclass first
        if self.character_object:
            if hasattr(self.character_object.db, 'full_name') and self.character_object.db.full_name:
                return self.character_object.db.full_name
            return self.character_object.key
            
        # Fall back to character sheet
        if self.character_sheet:
            if hasattr(self.character_sheet, 'full_name') and self.character_sheet.full_name:
                return self.character_sheet.full_name
            return f"Character #{self.character_sheet.id}"
            
        return "Unknown Character"

    @property
    def is_cyberdeck(self):
        return 'cyberdeck' in self.cyberware.name.lower()
        
    @classmethod
    def get_installed_for_character(cls, character):
        """Get all installed cyberware for a character"""
        # Check for direct link to character object
        character_instances = cls.objects.filter(
            character_object=character,
            installed=True
        )
        
        # Check for link via character sheet
        if not character_instances.exists() and hasattr(character, 'character_sheet'):
            character_instances = cls.objects.filter(
                character_sheet=character.character_sheet,
                installed=True
            )
            
        return character_instances

class WeaponAttachment(SharedMemoryModel):
    """Installable weapon attachment (Solo of Fortune 2045 / Interface RED Vol 5)."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    value = models.IntegerField(default=0)
    # Eligible: JSON list or "all_ranged", "shoulder_arms", "all_except_bow"
    eligible_categories = models.JSONField(default=list)
    requires_slot = models.BooleanField(default=False)
    slot_cost = models.PositiveIntegerField(default=1)  # 1 or 2 attachment slots
    slot_type = models.CharField(max_length=50, blank=True)
    clip_modifier = models.CharField(max_length=20, blank=True)  # "extended", "drum", or blank
    install_dv = models.IntegerField(default=17)
    install_skill = models.CharField(max_length=50, default="Weaponstech")
    effect_description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def is_eligible_for_weapon(self, weapon):
        """Check if this attachment can be installed on the given weapon."""
        cats = self.eligible_categories
        if not cats:
            return False
        if "all_ranged_except_flamethrower" in cats:
            return weapon.category != "heavy_weapons" or "flamethrower" not in (weapon.name or "").lower()
        if "all_ranged" in cats:
            return weapon.category in ("handgun", "shoulder_arms", "heavy_weapons")
        if "shoulder_arms" in cats:
            return str(weapon.category or "").lower() == "shoulder_arms"
        if "all_except_bow" in cats:
            return weapon.category not in ("archery",) and "bow" not in (weapon.weapon_type or "").lower()
        return weapon.category in cats


class Weapon(Item):
    damage = models.CharField(max_length=50)
    rof = models.CharField(max_length=50)
    hands = models.IntegerField(default=1)
    concealable = models.BooleanField(default=False)
    category = models.CharField(max_length=50, default='handgun')
    weapon_type = models.CharField(max_length=80, blank=True, default='')
    quality = models.CharField(max_length=20, default='standard')
    jammed = models.BooleanField(default=False)
    ammo_type = models.CharField(max_length=20, choices=AmmoType.choices, default=AmmoType.BASIC)
    current_ammo = models.PositiveIntegerField(default=0)
    max_ammo = models.PositiveIntegerField(default=0)
    clip = models.PositiveIntegerField(default=0)  # New field for clip size
    range_dvs = JSONField(default=dict)  # This will store the DVs for each range bracket
    attachment_slots = models.PositiveIntegerField(default=0)  # Scope/barrel slots (Solo of Fortune 2045)

    def reload(self, ammunition):
        if ammunition.ammo_type == self.ammo_type and ammunition.quantity > 0:
            ammo_to_load = min(self.clip - self.current_ammo, ammunition.quantity)
            self.current_ammo += ammo_to_load
            ammunition.quantity -= ammo_to_load
            ammunition.save()
            self.save()
            return ammo_to_load
        return 0

    @property
    def is_ranged(self):
        return self.category in ['handgun', 'smg', 'shotgun', 'assault rifle', 'sniper rifle', 'heavy weapons']

    def get_dv_for_range(self, range_in_meters):
        # Logic to return the appropriate DV based on the range
        for range_bracket, dv in self.range_dvs.items():
            min_range, max_range = map(int, range_bracket.split('-'))
            if min_range <= range_in_meters <= max_range:
                return dv
        return None  # or a default value if out of all ranges

class Armor(Item):
    sp = models.IntegerField(default=0)
    ev = models.IntegerField(default=0)
    locations = models.CharField(max_length=255)


class InventoryArmor(SharedMemoryModel):
    """Through model for per-inventory armor state: current SP (after ablation), juryrig status."""
    inventory = models.ForeignKey(
        'Inventory',
        on_delete=models.CASCADE,
        related_name='inventory_armor_instances'
    )
    armor = models.ForeignKey(
        'Armor',
        on_delete=models.CASCADE,
        related_name='inventory_instances'
    )
    current_sp = models.IntegerField(null=True, blank=True)  # None = use armor.sp (no ablation)
    original_sp = models.IntegerField(null=True, blank=True)  # None = use armor.sp
    juryrigged = models.BooleanField(default=False)

    class Meta:
        unique_together = [['inventory', 'armor']]

    def get_effective_sp(self):
        """SP to use: if juryrigged, use original; else use current or base."""
        if self.juryrigged:
            return self.original_sp if self.original_sp is not None else self.armor.sp
        return self.current_sp if self.current_sp is not None else self.armor.sp


class Gear(SharedMemoryModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    weight = models.FloatField(default=0)
    value = models.IntegerField(default=0)
    category = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    @property
    def is_cyberdeck(self):
        return 'cyberdeck' in self.name.lower() or (getattr(self, 'category', '') or '').lower() == 'cyberdeck'


class Vehicle(SharedMemoryModel):
    """Cyberpunk Red vehicle template - land, sea, or air."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50)  # land, sea, air
    sdp = models.PositiveIntegerField(default=35)  # Structural Damage Points
    seats = models.PositiveIntegerField(default=2)
    speed_combat = models.PositiveIntegerField(default=20)  # MOVE units
    speed_narrative = models.CharField(max_length=50, default="")  # e.g. "100 MPH / 161 KPH"
    value = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class InventoryWeapon(SharedMemoryModel):
    """Through model for character weapon instances; supports installed attachments (Solo of Fortune 2045)."""
    inventory = models.ForeignKey(
        'Inventory',
        on_delete=models.CASCADE,
        related_name='inventory_weapons'
    )
    weapon = models.ForeignKey(
        'Weapon',
        on_delete=models.CASCADE,
        related_name='inventory_instances'
    )
    installed_attachments = models.ManyToManyField(
        WeaponAttachment,
        blank=True,
        related_name='installed_on_weapons'
    )

    class Meta:
        unique_together = [['inventory', 'weapon']]


class Inventory(SharedMemoryModel):
    # Keep for backward compatibility
    character = models.OneToOneField(
        'cyberpunk_sheets.CharacterSheet', 
        on_delete=models.CASCADE, 
        related_name='inventory',
        null=True,
        blank=True
    )
    # New direct link to character object
    character_object = models.OneToOneField(
        ObjectDB,
        on_delete=models.CASCADE,
        related_name='inventory_object',
        null=True,
        blank=True
    )
    weapons = models.ManyToManyField(
        'Weapon',
        through='InventoryWeapon',
        through_fields=('inventory', 'weapon'),
        blank=True
    )
    armor = models.ManyToManyField('Armor', blank=True)
    gear = models.ManyToManyField('Gear', blank=True)
    vehicles = models.ManyToManyField('Vehicle', blank=True)
    cyberware = models.ManyToManyField(CyberwareInstance, blank=True)
    ammunition = models.ManyToManyField(Ammunition, blank=True)
    # Tracks items purchased during chargen (buy command in ChargenRoom) for refund eligibility.
    # Format: [{"type": "weapon"|"armor"|"gear"|"cyberware", "name": "Item Name"}, ...]
    # Items from edgerunner role package are NOT recorded here and cannot be refunded.
    # null=True allows legacy/create paths that don't set it; code uses "or []" when reading.
    chargen_purchased = models.JSONField(default=list, blank=True, null=True)

    class Meta:
        # Ensure at least one character field is populated
        constraints = [
            models.CheckConstraint(
                condition=models.Q(character_object__isnull=False) | models.Q(character__isnull=False),
                name='inventory_has_character'
            )
        ]

    def __str__(self):
        return f"Inventory for {self.get_character_name()}"

    def add_gear(self, gear, quantity=1):
        """Add gear to inventory (quantity ignored for simple M2M)."""
        self.gear.add(gear)

    def remove_gear(self, gear, quantity=1):
        """Remove gear from inventory (quantity ignored for simple M2M)."""
        self.gear.remove(gear)

    def clear_gear(self):
        """Remove all gear from inventory."""
        self.gear.clear()

    def get_gear_with_quantities(self):
        """Return list of (gear, quantity) tuples. Quantity is always 1 for simple M2M."""
        return [(g, 1) for g in self.gear.all()]
        
    def get_character_name(self):
        """Get the character's name from typeclass or sheet"""
        # Try character typeclass first
        if self.character_object:
            if hasattr(self.character_object.db, 'full_name') and self.character_object.db.full_name:
                return self.character_object.db.full_name
            return self.character_object.key
            
        # Fall back to character sheet
        if self.character:
            if hasattr(self.character, 'full_name') and self.character.full_name:
                return self.character.full_name
            return f"Character #{self.character.id}"
            
        return "Unknown Character"
    
    @classmethod
    def get_or_create_for_character(cls, character):
        """Get or create inventory for character. Prefers character_sheet link (same as +inventory)."""
        char_pk = getattr(character, 'pk', None) or getattr(character, 'id', None)

        # Prefer character sheet link first - matches +inventory display (character_sheet.inventory)
        if hasattr(character, 'character_sheet') and character.character_sheet:
            sheet = character.character_sheet
            sheet_pk = getattr(sheet, 'pk', None)
            if sheet_pk is not None:
                try:
                    inventory = cls.objects.get(character_id=sheet_pk)
                    # Update with direct link for future lookups
                    if char_pk is not None and inventory.character_object_id != char_pk:
                        # Check for duplicate: another inventory may already have character_object_id
                        duplicate = cls.objects.filter(character_object_id=char_pk).exclude(id=inventory.id).first()
                        if duplicate:
                            # Merge duplicate into canonical (sheet-linked) inventory
                            for obj in duplicate.weapons.all():
                                inventory.weapons.add(obj)
                            for obj in duplicate.armor.all():
                                inventory.armor.add(obj)
                            for gear_obj in duplicate.gear.all():
                                inventory.gear.add(gear_obj)
                            for obj in duplicate.vehicles.all():
                                inventory.vehicles.add(obj)
                            for obj in duplicate.cyberware.all():
                                inventory.cyberware.add(obj)
                            for obj in duplicate.ammunition.all():
                                inventory.ammunition.add(obj)
                            duplicate.delete()
                        inventory.character_object_id = char_pk
                        try:
                            inventory.save()
                        except IntegrityError:
                            # Duplicate exists - merge and retry (may have been missed or created by race)
                            duplicate = cls.objects.filter(character_object_id=char_pk).exclude(id=inventory.id).first()
                            if duplicate:
                                for obj in duplicate.weapons.all():
                                    inventory.weapons.add(obj)
                                for obj in duplicate.armor.all():
                                    inventory.armor.add(obj)
                                for gear_obj in duplicate.gear.all():
                                    inventory.gear.add(gear_obj)
                                for obj in duplicate.vehicles.all():
                                    inventory.vehicles.add(obj)
                                for obj in duplicate.cyberware.all():
                                    inventory.cyberware.add(obj)
                                for obj in duplicate.ammunition.all():
                                    inventory.ammunition.add(obj)
                                duplicate.delete()
                            inventory.character_object_id = char_pk
                            inventory.save()
                    return inventory, False
                except cls.DoesNotExist:
                    pass

        # Fallback: try direct link to character object
        if char_pk is not None:
            try:
                inventory = cls.objects.get(character_object_id=char_pk)
                return inventory, False
            except cls.DoesNotExist:
                pass

        # Create new inventory (character must have pk for FK)
        if char_pk is not None:
            inventory = cls.objects.create(character_object_id=char_pk)
        else:
            raise ValueError("Character must be saved before creating inventory")

        # Also link to character sheet if available
        if hasattr(character, 'character_sheet') and character.character_sheet:
            inventory.character = character.character_sheet
            inventory.save()

        return inventory, True


class Cyberdeck(SharedMemoryModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    hardware_slots = models.IntegerField(default=0)
    program_slots = models.IntegerField(default=0)
    any_slots = models.IntegerField(default=0)
    value = models.IntegerField(default=0)

    def __str__(self):
        return self.name
    
    @property
    def is_cyberdeck(self):
        return True
    
