"""
Cyberpunk RED NET Architecture typeclasses.

NetArchitecture: Physical access point representing a floor-based NET structure.
NetrunBodyMarker: Invisible marker showing a netrunner's body location while jacked in.
"""

from evennia import DefaultObject


class NetArchitecture(DefaultObject):
    """
    A NET Architecture access point. Netrunners must be in the same room to jack in.

    Uses db.floors (list of floor dicts) for the CPR floor-based structure.
    db.difficulty: basic, standard, uncommon, advanced
    db.is_net_architecture: True (for search filtering)
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.is_net_architecture = True
        self.db.difficulty = "standard"
        self.db.floors = []
        self.db.auto_paydata = False
        self.tags.add("net_architecture")

    def at_desc(self, looker=None):
        if looker and self.db.is_net_architecture:
            return f"A NET access point. Difficulty: {self.db.difficulty or 'standard'}. {len(self.db.floors or [])} floors."


class NetrunBodyMarker(DefaultObject):
    """
    Invisible marker for a netrunner's physical body location while jacked in.
    Allows room to see the runner is present but "elsewhere" in the NET.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.owner_id = None  # Character id

    def at_desc(self, looker=None):
        return ""

    def return_appearance(self, looker, **kwargs):
        if looker and getattr(looker, "id", None) == self.db.owner_id:
            return "You are here in the meat, but your awareness is in the NET."
        return ""
