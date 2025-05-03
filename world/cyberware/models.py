from evennia.utils.idmapper.models import SharedMemoryModel
from django.db import models
from evennia.objects.models import ObjectDB

class Cyberware(SharedMemoryModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    cost = models.IntegerField()
    humanity_loss = models.IntegerField()
    type = models.CharField(max_length=50)
    slots = models.IntegerField(default=1)
    is_weapon = models.BooleanField(default=False)
    damage_dice = models.IntegerField(default=0)
    damage_die_type = models.IntegerField(default=6)  # Assuming all dice are d6
    rate_of_fire = models.IntegerField(default=1)

    def __str__(self):
        return self.name

# Add CyberwareInstance class to link cyberware to characters
class CyberwareInstance(SharedMemoryModel):
    cyberware = models.ForeignKey(Cyberware, on_delete=models.CASCADE, related_name='cyberware_app_instances')
    # For backward compatibility with CharacterSheet
    character_sheet = models.ForeignKey(
        'cyberpunk_sheets.CharacterSheet', 
        related_name='cyberware_instances_old',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    # New direct link to character object
    character_object = models.ForeignKey(
        ObjectDB,
        related_name='cyberware_instances',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    installed = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    
    class Meta:
        # Ensure at least one character field is populated
        constraints = [
            models.CheckConstraint(
                check=models.Q(character_object__isnull=False) | models.Q(character_sheet__isnull=False),
                name='cyberware_app_instance_has_character'
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
    
CYBERWARE_HUMANITY_LOSS = {
    "Audio Recorder": 2,
    "Chemskin": 0,
    "Cyberaudio Suite": 7,
    "Techhair": 3,
    "Neural Link": 7,
    "Biomonitor": 0,
    "Sandevistan": 7,
    "Wolvers": 7,
    "Interface Plugs": 7,
    "Shift Tacts": 0,
    "Skinwatch": 0,
    "Tool Hand": 3,
    "Nasal Filters": 2,
    "Amplified Hearing": 3,
    "Light Tattoo": 0,
    "Hidden Holster": 7,
    "Subdermal Pocket": 3,
    "Internal Agent": 3,
    "Toxin Binders": 2,
    "EMP Threading": 0,
    "Braindance Recorder": 7,
    "Chipware Socket": 7,
    "Kerenzikov": 14,
    "Chemical Analyzer": 3,
    "Memory Chip": 0,
    "Olfactory Boost": 7,
    "Pain Editor": 14,
    "Skill Chip": 7,
    "Tactile Boost": 7,
    "Cybereye": 7,
    "Anti-Dazzle": 2,
    "Chyron": 2,
    "Color Shift": 2,
    "Dartgun": 2,
    "Image Enhance": 3,
    "Low Light/Infrared/UV": 3,
    "MicroOptics": 2,
    "MicroVideo": 2, 
    "Radiation Detector": 3,
    "Targeting Scope": 3,
    "TeleOptics": 3,
    "Virtuality": 2,
    "Bug Detector": 2,
    "Homing Tracer": 2,
    "Internal Agent": 3,
    "Level Damper": 2,
    "Radio Communicator": 2,
    "Radio Scanner and Music Player": 2,
    "Radar Detector": 2,
    "Scrambler Descrambler": 2,
    "Voice Stress Analyzer": 3,
    "AudioVox": 3,
    "Contraceptive Implant": 0,
    "Enhanced Antibodies": 2,
    "Cybersnake": 14,
    "Gills": 7,
    "Grafted Muscle and Bone Lace": 14,
    "Independent Air Supply": 2,
    "Midnight Lady Sexual Implant": 7,
    "Mr. Studd Sexual Implant": 7,
    "Radar/Sonar Implant": 7,
    "Vampyres": 14,
    "Skin Weave": 7,
    "Subdermal Armor": 14,
    "Cyberarm": 7,
    "Standard Hand": 0,
    "Big Knucks": 3,
    "Cyberdeck": 3,
    "Grapple Hand": 3,
    "Medscanner": 7,
    "Popup Grenade Launcher": 7,
    "Popup Melee Weapon": 7,
    "Popup Shield": 7,
    "Popup Ranged Weapon": 7,
    "Quick Change Mount": 7,
    "Rippers": 3,
    "Scratchers": 2,
    "Shoulder Cam": 7,
    "Slice n Dice": 3,
    "Subdermal Grip": 3,
    "Techscanner": 7,
    "Cyberleg": 3,
    "Standard Foot": 0,
    "Grip Foot": 3,
    "Jump Booster": 3,
    "Skate Foot": 3,
    "Talon Foot": 3,
    "Web Foot": 3,
    "Hardened Shielding": 3,
    "Plastic Covering": 0,
    "Realskinn Covering": 0,
    "Superchrome Covering": 0,
    "Artificial Shoulder Mount": 14,
    "Implanted Linear Frame Sigma": 14,
    "Implanted Linear Frame Beta": 14,
    "MultiOptic Mount": 14,
    "Sensor Array": 14
}

CYBERWARE_COSTS = {
		"Biomonitor": 100,
        "Chemskin": 100,
        "EMP Threading": 10,
        "Light Tattoo": 100,
        "Shift Tacts": 100,
        "Skinwatch": 100,
        "Techhair": 100,
		"Neural Link": 500,
        "Kerenzikov": 500,
        "Braindance Recorder": 500,
        "Chipware Socket": 500,
        "Interface Plugs": 500,
        "Sandevistan": 500,
        "Chemical Analyzer": 500,
        "Memory Chip": 10,
        "Olfactory Boost": 100,
        "Pain Editor": 1000,
        "Basic Skill Chip": 500,
        "Advanced Skill Chip": 1000,
        "Tactile Boost": 100,
		"Cybereye": 100,
        "Chyron": 100,
        "Color Shift": 100,
        "Dartgun": 500,
        "Image Enhance": 1000,
        "Low Light-IR-UV": 1000,
        "MicroVideo": 1000,
        "Radiation Detector": 1000,
        "Targeting Scope": 500,
        "TeleOptics": 500,
        "Virtuality": 200,
		"Cyberaudio Suite": 500,
        "Amplified Hearing": 100,
        "Audio Recorder": 100,
        "Bug Detector": 100,
        "Homing Tracer": 100,
        "Internal Agent": 100,
        "Level Damper": 100,
        "Radio Communicator": 100,
        "Radio Scanner and Music Player": 50,
        "Radar Detector": 500,
        "Scrambler Descrambler": 100,
        "Voice Stress Analyzer": 100,
		"AudioVox": 500,
        "Contraceptive Implant": 10,
        "Enhanced Antibodies": 500,
        "Cybersnake": 1000,
        "Gills": 1000,
        "Grafted Muscle and Bone Lace": 1000,
        "Independent Air Supply": 1000,
        "Midnight Lady Sexual Implant": 100,
        "Mr. Studd Sexual Implant": 100,
        "Nasal Filters": 100,
        "Radar Sonar Implant": 1000,
        "Toxin Binders": 100,
        "Vampyres": 500,
		"Hidden Holster": 500,
	    "Skin Weave": 500,
        "Subdermal Armor": 1000,
        "Subdermal Pocket": 100,
    	"Cyberarm": 500,
        "Standard Hand": 100,
        "Big Knucks": 100,
        "Cyberdeck": 500,
        "Grapple Hand": 100,
        "Medscanner": 500,
        "Popup Grenade Launcher": 500,
        "Popup Melee Weapon": 500,
        "Popup Shield": 500,
        "Popup Ranged Weapon": 500,
        "Quick Change Mount": 100,
        "Rippers": 500,
        "Scratchers": 100,
        "Shoulder Cam": 500,
        "Slice N Dice": 500,
        "Subdermal Grip": 100,
        "Techscanner": 500,
		"Wolvers": 500,
        "Cyberleg": 100,
        "Standard Foot": 100,
        "Grip Foot": 1000,
        "Jump Booster": 1000,
        "Skate Foot": 1000,
        "Talon Foot": 500,
        "Web Foot": 1000,
        "Hardened Shielding": 1000,
        "Plastic Covering": 100,
        "Realskinn Covering": 500,
        "Superchrome Covering": 1000,
		"Artificial Shoulder Mount": 1000,
        "Implanted Linear Frame Sigma": 1000,
        "Implanted Linear Frame Beta": 5000,
        "MultiOptic Mount": 1000,
        "Sensor Array": 1000
}