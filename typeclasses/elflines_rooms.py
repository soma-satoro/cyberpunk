"""
Elflines Online room typeclass. Rooms in the ELO "game" reality.
"""

from typeclasses.rooms import Room


class ElflinesRoom(Room):
    """
    A room in the Elflands - the virtual world of Elflines Online.
    Characters here are "logged in" to the MMO. Uses same display format as meat-world rooms.
    """

    is_elflines_room = True

    def at_object_creation(self):
        super().at_object_creation()
        self.db.roomtype = "ELO"
        self.db.is_miasma = False  # Major cities and camps = no miasma (no PvP)

    def get_display_name(self, looker, **kwargs):
        """Add ELO indicator to room name."""
        base = super().get_display_name(looker, **kwargs)
        return f"|c[ELO]|n {base}"
