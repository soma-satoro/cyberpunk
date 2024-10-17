from evennia import CmdSet
from evennia import create_object
from typeclasses.rental import RentableRoom
from evennia.utils import search, delay
from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand

class CmdCreateRentableRoom(MuxCommand):
    """
    Create a rentable room or building
    
    Usage:
      @digrent[/temp] <room name> = <rental_type>, <exit name>;<exit alias>
    
    Switches:
      /temp - Create a temporary unit that will be destroyed when not in use
    
    Creates a new rentable room or building of the specified type with a custom exit.
    Available rental types:
      Cube Hotel, Cargo Container, Studio Apartment, Two-Bedroom Apartment,
      Corporate Conapt, Upscale Conapt, Luxury Penthouse
    
    Example:
      @digrent/temp Luxury Suite 42 = Luxury Penthouse, Grand Entrance;suite
    """

    key = "@digrent"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        
        is_temporary = 'temp' in self.switches
        
        if not self.args or "=" not in self.args:
            caller.msg("Usage: @digrent[/temp] <room name> = <rental_type>, <exit name>;<exit alias>")
            return
        
        name, rest = [part.strip() for part in self.args.split("=")]
        if not name or "," not in rest:
            caller.msg("You must specify a name, rental type, and exit information.")
            return
        
        rental_type, exit_info = [part.strip() for part in rest.split(",", 1)]
        
        if ";" in exit_info:
            exit_name, exit_alias = [part.strip() for part in exit_info.split(";")]
        else:
            exit_name = exit_info.strip()
            exit_alias = exit_name.lower()
        
        if rental_type not in RentableRoom.RENTAL_TYPES:
            caller.msg(f"Invalid rental type. Choose from: {', '.join(RentableRoom.RENTAL_TYPES.keys())}")
            return
        
        # Create the main rentable room
        new_room = create_object(RentableRoom, key=name, location=caller.location)
        new_room.set_rental_type(rental_type, is_temporary=is_temporary)
        
        # Set up exits
        exit_to_new = create_object("evennia.objects.objects.DefaultExit", key=exit_name, aliases=[exit_alias], location=caller.location, destination=new_room)
        exit_back = create_object("evennia.objects.objects.DefaultExit", key="Out", aliases=["o"], location=new_room, destination=caller.location)
        
        caller.msg(f"Created rentable {rental_type} '{name}' with {len(new_room.db.child_rooms) + 1} rooms.")
        caller.msg(f"Created exit '{exit_name}' (alias: {exit_alias}) to the new room.")
        
        # If it's a multi-room rental, create exits between rooms
        if new_room.db.child_rooms:
            for i, child_room in enumerate(new_room.db.child_rooms, start=2):
                create_object("evennia.objects.objects.DefaultExit", key=f"Room {i}", location=new_room, destination=child_room)
                create_object("evennia.objects.objects.DefaultExit", key="Main Room", location=child_room, destination=new_room)
            
            caller.msg(f"Created exits between all {len(new_room.db.child_rooms) + 1} rooms.")

        if is_temporary:
            caller.msg(f"Created temporary rentable {rental_type} '{name}'. It will be destroyed when not in use.")
            # Schedule the first check for destruction
            delay(3600, new_room.check_and_destroy)
        else:
            caller.msg(f"Created permanent rentable {rental_type} '{name}'.")

class BuildingCmdSet(CmdSet):
    def at_cmdset_creation(self):
        self.add(CmdCreateRentableRoom())