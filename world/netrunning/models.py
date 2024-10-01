# world/netrunning/models.py

from django.db import models
from evennia.utils.idmapper.models import SharedMemoryModel
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import CyberwareInstance, Cyberdeck

class Cyberdeck(SharedMemoryModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    hardware_slots = models.IntegerField(default=0)
    program_slots = models.IntegerField(default=0)
    any_slots = models.IntegerField(default=0)
    value = models.IntegerField(default=0)
    owner = models.ForeignKey(CharacterSheet, on_delete=models.SET_NULL, null=True, related_name='cyberdecks')
    cyberdeck_gear = models.OneToOneField(Cyberdeck, on_delete=models.SET_NULL, null=True, blank=True, related_name='cyberdeck')
    cyberware = models.OneToOneField(CyberwareInstance, on_delete=models.SET_NULL, null=True, blank=True, related_name='cyberdeck')

    def __str__(self):
        return self.name

    @property
    def is_cyberware(self):
        return self.cyberware is not None

    def save(self, *args, **kwargs):
        if self.gear and self.cyberware:
            raise ValueError("A Cyberdeck cannot be both gear and cyberware simultaneously.")
        super().save(*args, **kwargs)

class Program(SharedMemoryModel):
    name = models.CharField(max_length=255, default="Unnamed Program")
    atk = models.IntegerField(default=0)
    dfv = models.IntegerField(default=0)
    rez = models.IntegerField(default=0)
    effect = models.TextField(blank=True, default="")
    cost = models.IntegerField(default=0)
    icon = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return self.name

class Hardware(SharedMemoryModel):
    name = models.CharField(max_length=100)
    description = models.TextField()
    cost = models.IntegerField(default=0)
    slots = models.IntegerField(default=0)

class PlayerICE(SharedMemoryModel):
    name = models.CharField(max_length=100)
    per = models.IntegerField(default=0)
    spd = models.IntegerField(default=0)
    atk = models.IntegerField(default=0)
    dfv = models.IntegerField(default=0)
    rez = models.IntegerField(default=0)
    effect = models.TextField(blank=True, default="")
    cost = models.IntegerField(default=0)

class NetArchitecture(SharedMemoryModel):
    name = models.CharField(max_length=100)
    description = models.TextField()
    difficulty = models.IntegerField(default=1)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.create_default_node()

    def create_default_node(self):
        if not self.nodes.exists():
            Node.objects.create(
                architecture=self,
                name="Entry Point",
                description="You've just entered the system.",
                level=1
            )

class Node(SharedMemoryModel):
    architecture = models.ForeignKey(NetArchitecture, on_delete=models.CASCADE, related_name='nodes')
    name = models.CharField(max_length=100)
    description = models.TextField()
    level = models.IntegerField(default=1)
    is_ice = models.BooleanField(default=False)
    ice_type = models.CharField(max_length=50, null=True, blank=True)
    ice_strength = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} (Level {self.level})"

class NetrunSession(SharedMemoryModel):
    netrunner = models.ForeignKey(CharacterSheet, on_delete=models.CASCADE, related_name='netrun_sessions')
    architecture = models.ForeignKey(NetArchitecture, on_delete=models.CASCADE)
    current_node = models.ForeignKey(Node, on_delete=models.SET_NULL, null=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.netrunner.full_name} - {self.architecture.name}"

class ICE:
    def __init__(self, name, rez, perception, attack, speed, defense):
        self.name = name
        self.rez = rez
        self.perception = perception
        self.atk = attack
        self.spd = speed
        self.dfv = defense

    def react(self, netrunner):
        # Implement ICE reaction logic here
        pass

class BlackICE(ICE):
    def react(self, netrunner):
        # Implement more aggressive behavior for Black ICE
        pass
