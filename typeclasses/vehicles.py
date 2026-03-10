"""
Vehicle typeclass - Enterable vehicles from Cyberpunk Red.

Vehicles are objects that can be entered by characters. Each vehicle has an
interior room; entering moves the character into that room.
"""

from evennia import DefaultObject, create_object
from evennia.objects.objects import DefaultRoom


class Vehicle(DefaultObject):
    """
    An enterable vehicle (land, sea, or air). Characters can enter/exit.
    The vehicle has an interior room as a child object.
    """

    def at_object_creation(self):
        super().at_object_creation()
        # db.vehicle_type_id - FK to world.inventory.models.Vehicle (template)
        # db.owner_id - dbref of character who owns this vehicle instance
        # db.interior_id - dbref of the interior room (created on first enter)
        self.db.vehicle_type_id = None
        self.db.owner_id = None
        self.db.interior_id = None

    def get_interior(self):
        """Get or create the interior room for this vehicle."""
        interior_id = self.db.interior_id
        if interior_id:
            from evennia.utils.search import search_object
            results = search_object(f"#{interior_id}")
            if results:
                return results[0]
        # Create interior room
        interior = create_object(
            "typeclasses.rooms.Room",
            key=f"Inside {self.key}",
            location=self,
        )
        interior.db.desc = f"The interior of {self.key}. {self.db.desc or ''}"
        interior.db.vehicle_parent_id = self.id
        self.db.interior_id = interior.id
        return interior

    def get_owner(self):
        """Get the character who owns this vehicle."""
        owner_id = self.db.owner_id
        if not owner_id:
            return None
        from evennia.utils.search import search_object
        results = search_object(f"#{owner_id}")
        return results[0] if results else None

    def return_appearance(self, looker, **kwargs):
        """Customize how the vehicle appears when looked at."""
        base = super().return_appearance(looker, **kwargs)
        if not looker:
            return base
        # Add vehicle stats if we have template data
        try:
            from world.inventory.models import Vehicle as VehicleModel
            vt_id = self.db.vehicle_type_id
            if vt_id:
                vt = VehicleModel.objects.filter(id=vt_id).first()
                if vt:
                    stats = f"\n|y[{vt.category.upper()}]|n SDP: {vt.sdp} | Seats: {vt.seats} | Speed: {vt.speed_narrative}"
                    return base + stats
        except Exception:
            pass
        return base
