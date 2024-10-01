from django.db import models
from evennia.utils.idmapper.models import SharedMemoryModel
from world.cyberware.models import Cyberware
from django.db.models import JSONField  # If using PostgreSQL

class AmmoType(models.TextChoices):
    BASIC = 'Basic', 'Basic Ammunition'
    ARMOR_PIERCING = 'Armor-Piercing', 'Armor-Piercing Ammunition'
    BIOTOXIN = 'Biotoxin', 'Biotoxin Ammunition'
    EMP = 'EMP', 'EMP Ammunition'
    EXPANSIVE = 'Expansive', 'Expansive Ammunition'
    FLASHBANG = 'Flashbang', 'Flashbang Ammunition'
    INCENDIARY = 'Incendiary', 'Incendiary Ammunition'
    POISON = 'Poison', 'Poison Ammunition'
    RUBBER = 'Rubber', 'Rubber Ammunition'
    SLEEP = 'Sleep', 'Sleep Ammunition'
    SMART = 'Smart', 'Smart Ammunition'
    SMOKE = 'Smoke', 'Smoke Ammunition'
    TEARGAS = 'Teargas', 'Teargas Ammunition'

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
        elif ammo_type in ['Armor-Piercing', 'Expansive', 'Flashbang', 'Incendiary', 'Poison']:
            return 100
        elif ammo_type in ['Biotoxin', 'EMP', 'Sleep', 'Smart']:
            return 500
        elif ammo_type in ['Smoke', 'Teargas']:
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

class CyberwareInstance(SharedMemoryModel):
    cyberware = models.ForeignKey(Cyberware, on_delete=models.CASCADE)
    character = models.ForeignKey('cyberpunk_sheets.CharacterSheet', related_name='cyberware_instances', on_delete=models.CASCADE)
    installed = models.BooleanField(default=False)
    active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cyberware.name} - {self.character.full_name}"

    @property
    def is_cyberdeck(self):
        return 'cyberdeck' in self.cyberware.name.lower()

class Weapon(Item):
    damage = models.CharField(max_length=50)
    rof = models.CharField(max_length=50)
    hands = models.IntegerField(default=1)
    concealable = models.BooleanField(default=False)
    category = models.CharField(max_length=50, default='handgun')
    ammo_type = models.CharField(max_length=20, choices=AmmoType.choices, default=AmmoType.BASIC)
    current_ammo = models.PositiveIntegerField(default=0)
    max_ammo = models.PositiveIntegerField(default=0)
    clip = models.PositiveIntegerField(default=0)  # New field for clip size
    range_dvs = JSONField(default=dict)  # This will store the DVs for each range bracket

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
        return 'cyberdeck' in self.name.lower()

class Inventory(SharedMemoryModel):
    character = models.OneToOneField('cyberpunk_sheets.CharacterSheet', on_delete=models.CASCADE, related_name='inventory')
    weapons = models.ManyToManyField('Weapon', blank=True)
    armor = models.ManyToManyField('Armor', blank=True)
    gear = models.ManyToManyField('Gear', blank=True)
    cyberware = models.ManyToManyField(CyberwareInstance, blank=True)
    ammunition = models.ManyToManyField(Ammunition, blank=True)

    def __str__(self):
        return f"Inventory for {self.character.full_name if self.character else 'Unknown'}"

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
    
