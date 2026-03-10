"""
Vehicle commands - Enter and exit vehicles.
"""

from evennia import Command
from evennia.utils.search import search_object


class CmdEnterVehicle(Command):
    """
    Enter a vehicle.

    Usage:
      enter <vehicle>
      board <vehicle>

    You must be in the same location as the vehicle and either own it
    or it must be enterable by anyone.
    """

    key = "enter"
    aliases = ["board"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        if not self.args:
            self.caller.msg("Enter what? Usage: enter <vehicle>")
            return

        vehicle_name = self.args.strip()
        location = self.caller.location
        if not location:
            self.caller.msg("You are nowhere.")
            return

        # Find vehicle in location
        vehicles = [
            obj for obj in location.contents
            if obj.is_typeclass("typeclasses.vehicles.Vehicle")
            and vehicle_name.lower() in obj.key.lower()
        ]
        if not vehicles:
            self.caller.msg(f"You don't see a vehicle called '{vehicle_name}' here.")
            return
        vehicle = vehicles[0]

        # Check capacity
        try:
            from world.inventory.models import Vehicle as VehicleModel
            vt_id = vehicle.db.vehicle_type_id
            if vt_id:
                vt = VehicleModel.objects.filter(id=vt_id).first()
                if vt:
                    interior = vehicle.get_interior()
                    occupants = [o for o in interior.contents if o.has_account]
                    if len(occupants) >= vt.seats:
                        self.caller.msg(f"{vehicle.key} is full ({vt.seats} seats).")
                        return
        except Exception:
            pass

        interior = vehicle.get_interior()
        self.caller.move_to(interior, quiet=True)
        self.caller.msg(f"You enter {vehicle.key}.")
        location.msg_contents(f"{self.caller.name} enters {vehicle.key}.", exclude=[self.caller])
        interior.msg_contents(f"{self.caller.name} enters.", exclude=[self.caller])


class CmdExitVehicle(Command):
    """
    Exit a vehicle.

    Usage:
      exit
      exit <vehicle>
      disembark
      get out

    Exits the vehicle you're currently in.
    """

    key = "exit"
    aliases = ["disembark", "get out"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        location = self.caller.location
        if not location:
            self.caller.msg("You are nowhere.")
            return

        # Check if we're inside a vehicle (our location's location is a vehicle)
        vehicle = None
        if location.db.vehicle_parent_id:
            from evennia.utils.search import search_object
            results = search_object(f"#{location.db.vehicle_parent_id}")
            if results:
                vehicle = results[0]

        if not vehicle:
            self.caller.msg("You're not inside a vehicle.")
            return

        # Move to the vehicle's location (where it's "parked")
        dest = vehicle.location
        if not dest:
            self.caller.msg("The vehicle seems to be in limbo. You can't exit.")
            return

        self.caller.move_to(dest, quiet=True)
        self.caller.msg(f"You exit {vehicle.key}.")
        location.msg_contents(f"{self.caller.name} exits.", exclude=[self.caller])
        dest.msg_contents(f"{self.caller.name} exits {vehicle.key}.", exclude=[self.caller])
