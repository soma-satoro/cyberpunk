from evennia import DefaultRoom
from evennia.utils import evtable
from evennia.utils.ansi import ANSIString
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider
from evennia import DefaultRoom
from evennia.utils.utils import make_iter, justify
from evennia.utils.ansi import ANSIString
from evennia.utils import ansi
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider
from datetime import datetime
import random
from evennia.utils.search import search_channel
import re

class Room(DefaultRoom):
    """
    This is a custom room typeclass for Evennia that displays information
    in a specific format: room name at the top, description in the center,
    then separating locations and exits.
    """

    def get_display_name(self, looker, **kwargs):
        """
        Get the name to display for the character.
        """
        
        name = self.key
        
        if self.db.gradient_name:
            name = ANSIString(self.db.gradient_name)
            if looker.check_permstring("builders"):
                name += f"({self.dbref})"
            return name
        
        # If the looker is builder+ show the dbref
        if looker.check_permstring("builders"):
            name += f"({self.dbref})"

        return name

    def return_appearance(self, looker, **kwargs):
        if not looker:
            return ""

        name = self.get_display_name(looker, **kwargs)
        desc = self.db.desc

        # Header with room name
        string = header(name, width=78, bcolor="|m", fillchar=ANSIString("|m-|n")) + "\n"
        
        # Process room description
        if desc:
            paragraphs = desc.split('%r')
            formatted_paragraphs = []
            for i, p in enumerate(paragraphs):
                if not p.strip():
                    if i > 0 and not paragraphs[i-1].strip():
                        formatted_paragraphs.append('')  # Add blank line for double %r
                    continue
                
                lines = p.split('%t')
                formatted_lines = []
                for j, line in enumerate(lines):
                    if j == 0 and line.strip():
                        formatted_lines.append(wrap_ansi(line.strip(), width=76))
                    elif line.strip():
                        formatted_lines.append(wrap_ansi('    ' + line.strip(), width=76))
                
                formatted_paragraphs.append('\n'.join(formatted_lines))
            
            string += '\n'.join(formatted_paragraphs) + "\n\n"

        # List all characters in the room
        characters = [obj for obj in self.contents if obj.has_account]
        if characters:
            string += divider("Characters", width=78, fillchar=ANSIString("|m-|n")) + "\n"
            for character in characters:
                idle_time = self.idle_time_display(character.idle_time)
                if character == looker:
                    idle_time = self.idle_time_display(0)

                shortdesc = character.db.shortdesc
                if shortdesc:
                    shortdesc_str = f"{shortdesc}"
                else:
                    shortdesc_str ="|h|xType '|n+shortdesc <desc>|h|x' to set a short description.|n"

                if len(ANSIString(shortdesc_str).strip()) > 43:
                    shortdesc_str = ANSIString(shortdesc_str)[:43]
                    shortdesc_str = ANSIString(shortdesc_str[:-3] + "...|n")
                else:
                    shortdesc_str = ANSIString(shortdesc_str).ljust(43, ' ')
                
                string += ANSIString(f" {character.get_display_name(looker).ljust(25)} {ANSIString(idle_time).rjust(7)}|n {shortdesc_str}\n")

        # List all objects in the room
        objects = [obj for obj in self.contents if not obj.has_account and not obj.destination]
        if objects:
            string += divider("Objects", width=78, fillchar=ANSIString("|m-|n")) + "\n"
            
            # get shordesc or dhoe s blsnk string
            for obj in objects:
                if obj.db.shortdesc:
                    shortdesc = obj.db.shortdesc
                else:
                    shortdesc = ""


            # if looker builder+ show dbref.

                string +=" "+  ANSIString(f"{obj.get_display_name(looker)}").ljust(25) + ANSIString(f"{shortdesc}") .ljust(53, ' ') + "\n"

        # Separate exits into directions and building exits
        exits = [ex for ex in self.contents if ex.destination]
        directions = []
        building_exits = []

        direction_aliases = ['n', 's', 'e', 'w', 'ne', 'se', 'nw', 'sw', 'u', 'd', 'o']
        
        for ex in exits:
            if any(alias in ex.aliases.all() for alias in direction_aliases):
                directions.append(ex)
            else:
                building_exits.append(ex)

        # Building Exits section
        if building_exits:
            string += divider("Exits", width=78, fillchar=ANSIString("|m-|n")) + "\n"
            exit_strings = []
            for ex in building_exits:
                aliases = ex.aliases.all() or []
                short = min(aliases, key=len) if aliases else ""
                exit_strings.append(ANSIString(f" <|y{short.upper()}|n> {ex.get_display_name(looker)}"))
            
            # Split into two columns
            string += self.format_two_columns(exit_strings)

        # Directions section
        if directions:
            string += divider("Directions", width=78, fillchar=ANSIString("|m-|n")) + "\n"
            direction_strings = []
            for ex in directions:
                aliases = ex.aliases.all() or []
                short = min(aliases, key=len) if aliases else ""
                direction_strings.append(ANSIString(f" <|y{short.upper()}|n> {ex.get_display_name(looker)}"))
            
            # Split into two columns
            string += self.format_two_columns(direction_strings)

        string += footer(width=78, fillchar=ANSIString("|m-|n"))

        return string

    def format_two_columns(self, items):
        """
        Format a list of items into two columns.
        """
        output = ""
        for i in range(0, len(items), 2):
            left = items[i].ljust(38)
            right = items[i+1] if i+1 < len(items) else ""
            output += f"{left} {right}\n"
        return output

    def idle_time_display(self, idle_time):
        """
        Formats the idle time display.
        """
        idle_time = int(idle_time)  # Convert to int
        if idle_time < 60:
            time_str = f"{idle_time}s"
        elif idle_time < 3600:
            time_str = f"{idle_time // 60}m"
        else:
            time_str = f"{idle_time // 3600}h"

        # Color code based on idle time intervals
        if idle_time < 900:  # less than 15 minutes
            color = "|g"  # green
        elif idle_time < 1800:  # 15-30 minutes
            color = "|y"  # yellow
        elif idle_time < 2700:  # 30-45 minutes
            color = "|o"  # orange
        elif idle_time < 3600:
            color = "|r"  # red
        else:
            color = "|h|x"
        

        return f"{color}{time_str}|n"

    def at_object_creation(self):
        """
        Called when the room is first created.
        """
        super().at_object_creation()
        # Add any custom attributes or tags here
        self.db.custom_info = "This is a custom room."

    def initialize(self):
        """Initialize default attributes."""
        if not self.attributes.has("initialized"):
            # Initialize attributes
            self.db.location_type = None  # "District", "Sector", "Neighborhood", or "Site"
            self.db.order = 0
            self.db.infrastructure = 0
            self.db.resolve = 0
            self.db.resources = {}  # Empty dict for resources
            self.db.owners = []
            self.db.sub_locations = []
            self.db.roll_log = []  # Initialize an empty list for roll logs
            self.db.initialized = True  # Mark this room as initialized
            self.save()  # Save immediately to avoid ID-related issues
            
            # Initialize housing data with proper structure
            self.db.housing_data = {
                'is_housing': False,
                'max_apartments': 0,
                'current_tenants': {},
                'apartment_numbers': set(),
                'required_resources': 0,
                'building_zone': None,
                'connected_rooms': set(),
                'is_lobby': False
            }
            
            # Initialize home data
            self.db.home_data = {
                'locked': False,
                'keyholders': set(),
                'owner': None
            }
            
            # Set resources as integer instead of dict
            self.db.resources = 0
            
            self.db.initialized = True
        else:
            # Ensure roll_log exists even for previously initialized rooms
            if not hasattr(self.db, 'roll_log'):
                self.db.roll_log = []

    def at_object_creation(self):
        """Called when the room is first created."""
        super().at_object_creation()
        
        # Initialize scene tracking with proper structure
        self.db.scene_data = {
            'start_time': None,
            'participants': set(),
            'last_activity': None,
            'completed': False
        }
        
        self.db.unfindable = False
        self.db.roll_log = []  # Initialize empty roll log
        self.db.home_data = {
            'locked': False,
            'keyholders': set(),
            'owner': None
        }
        # Initialize housing data
        self.db.housing_data = {
            'is_housing': False,
            'max_apartments': 0,
            'current_tenants': {},
            'apartment_numbers': set(),
            'required_resources': 0,
            'building_zone': None,
            'connected_rooms': set(),
            'is_lobby': False,
            'available_types': []
        }

    def set_as_district(self):
        self.initialize()
        self.db.location_type = "District"

    def set_as_sector(self):
        self.initialize()
        self.db.location_type = "Sector"

    def set_as_neighborhood(self):
        self.initialize()
        self.db.location_type = "Neighborhood"
        self.db.order = 5
        self.db.infrastructure = 5
        self.db.resolve = 5

    def set_as_site(self):
        self.initialize()
        self.db.location_type = "Site"

    def add_sub_location(self, sub_location):
        """
        Add a sub-location to this room. Automatically sets the type of the sub-location.
        """
        self.initialize()
        sub_location.initialize()

        if self.db.location_type == "District":
            sub_location.set_as_sector()
        elif self.db.location_type == "Sector":
            sub_location.set_as_neighborhood()
        elif self.db.location_type == "Neighborhood":
            sub_location.set_as_site()

        self.db.sub_locations.append(sub_location)
        sub_location.db.parent_location = self
        self.save()  # Ensure changes are saved

    def remove_sub_location(self, sub_location):
        """
        Remove a sub-location from this room.
        """
        self.initialize()
        sub_location.initialize()
        if sub_location in self.db.sub_locations:
            self.db.sub_locations.remove(sub_location)
            sub_location.db.parent_location = None
            self.save()  # Ensure changes are saved

    def get_sub_locations(self):
        self.initialize()
        return self.db.sub_locations

    def update_values(self):
        """
        Update the Order, Infrastructure, and Resolve values based on the averages of sub-locations.
        Only applies if this room is a District or Sector.
        """
        self.initialize()
        if self.db.location_type in ["District", "Sector"]:
            sub_locations = self.get_sub_locations()
            if sub_locations:
                averages = {
                    "avg_order": sum(loc.db.order for loc in sub_locations) / len(sub_locations),
                    "avg_infrastructure": sum(loc.db.infrastructure for loc in sub_locations) / len(sub_locations),
                    "avg_resolve": sum(loc.db.resolve for loc in sub_locations) / len(sub_locations),
                }
                self.db.order = averages['avg_order']
                self.db.infrastructure = averages['avg_infrastructure']
                self.db.resolve = averages['avg_resolve']
            else:
                self.db.order = 0
                self.db.infrastructure = 0
                self.db.resolve = 0
            self.save()

    def save(self, *args, **kwargs):
        """
        Overriding save to ensure initialization happens after the object is fully created.
        """
        super().save(*args, **kwargs)
        self.initialize()
        if self.db.location_type in ["Sector", "Neighborhood"] and hasattr(self.db, "parent_location"):
            self.db.parent_location.update_values()

    def add_owner(self, owner):
        self.initialize()
        if owner not in self.db.owners:
            self.db.owners.append(owner)
            self.save()

    def remove_owner(self, owner):
        self.initialize()
        if owner in self.db.owners:
            self.db.owners.remove(owner)
            self.save()

    def log_roll(self, roller, description, result):
        """
        Log a dice roll in this room.
        
        Args:
            roller (str): Name of the character making the roll
            description (str): Description of the roll
            result (str): Result of the roll
        """

        pass

    def get_roll_log(self):
        """
        Get the roll log for this room.
        
        Returns:
            list: List of roll log entries
        """
        pass

    def ensure_housing_data(self):
        """Ensure housing data exists and is properly initialized."""
        if not self.db.housing_data:
            self.db.housing_data = {
                'is_housing': False,
                'max_apartments': 0,
                'current_tenants': {},
                'apartment_numbers': set(),
                'required_resources': 0,
                'building_zone': None,
                'connected_rooms': set(),
                'is_lobby': False,
                'available_types': []
            }
        return self.db.housing_data

    def is_housing_area(self):
        """Check if this is a housing area."""
        self.ensure_housing_data()  # Ensure housing data exists
        return (hasattr(self.db, 'roomtype') and 
                self.db.roomtype in [
                    "Apartment Building", "Apartments", 
                    "Condos", "Condominiums",
                    "Residential Area", "Residential Neighborhood", 
                    "Neighborhood", "Splat Housing", "Motel",
                    "Encampment"  # Add Encampment to valid housing types
                ])

    def is_apartment_building(self):
        """Check if this is an apartment building."""
        self.ensure_housing_data()
        return (hasattr(self.db, 'roomtype') and 
                self.db.roomtype in [
                    "Apartment Building", "Apartments", 
                    "Condos", "Condominiums",
                    "Splat Housing"  # Add Splat Housing to apartment-style buildings
                ])

    def is_residential_area(self):
        """Check if this is a residential neighborhood."""
        self.ensure_housing_data()
        return (hasattr(self.db, 'roomtype') and 
                self.db.roomtype in [
                    "Residential Area", "Residential Neighborhood", 
                    "Neighborhood", "Encampment"  # Add Encampment to residential areas
                ])

    def setup_housing(self, housing_type="Apartment Building", max_units=20):
        """Set up room as a housing area."""
        # Set room type
        self.db.roomtype = housing_type
        
        # Initialize housing data
        housing_data = self.ensure_housing_data()
        
        # Set initial available types based on housing type
        initial_types = []
        if housing_type == "Splat Housing":
            initial_types = ["Splat Housing"]
        elif housing_type == "Motel":
            initial_types = ["Motel Room"]
        
        housing_data.update({
            'is_housing': True,
            'max_apartments': max_units,
            'current_tenants': {},
            'apartment_numbers': set(),
            'is_lobby': True,
            'available_types': initial_types,
            'building_zone': self.dbref,  # Set building zone to self
            'connected_rooms': {self.dbref}  # Initialize connected rooms with self
        })

        # For splat housing, modify any existing exits to use initials
        if housing_type == "Splat Housing":
            for exit in self.exits:
                if exit.destination:
                    # Get the destination room's name and create initials
                    room_name = exit.destination.key
                    # Split on spaces and get first letter of each word
                    initials = ''.join(word[0].lower() for word in room_name.split())
                    # Update exit key and add original name as alias
                    original_key = exit.key
                    exit.key = initials
                    if original_key != initials:
                        exit.aliases.add(original_key)
                    
                    # Set up the destination room as a splat residence
                    dest = exit.destination
                    if dest:
                        # Determine splat type from room name if possible
                        room_name = dest.key.lower()
                        if "mage" in room_name:
                            splat_type = "Mage"
                        elif "vampire" in room_name:
                            splat_type = "Vampire"
                        elif "werewolf" in room_name:
                            splat_type = "Werewolf"
                        elif "changeling" in room_name:
                            splat_type = "Changeling"
                        else:
                            splat_type = "Splat"  # Generic if can't determine
                            
                        dest.setup_splat_room(splat_type, self)
        
        # Force room appearance update
        self.at_object_creation()

    def get_available_housing_types(self):
        """Get available housing types based on area type."""
        self.ensure_housing_data()  # Ensure housing data exists
        from commands.housing import CmdRent
        if self.db.roomtype == "Motel":
            return {"Motel Room": CmdRent.APARTMENT_TYPES["Motel Room"]}
        elif self.db.roomtype == "Encampment":
            return {"Encampment": CmdRent.RESIDENTIAL_TYPES["Encampment"]}
        elif self.is_apartment_building():
            return CmdRent.APARTMENT_TYPES
        elif self.is_residential_area():
            return CmdRent.RESIDENTIAL_TYPES
        return {}

    def get_housing_cost(self, unit_type):
        """Calculate housing cost based on area resources and unit type."""
        self.ensure_housing_data()
        housing_types = self.get_available_housing_types()
        if unit_type in housing_types:
            base_resources = self.db.resources or 0
            return max(1, base_resources + housing_types[unit_type]['resource_modifier'])
        return 0

    def list_available_units(self):
        """Return formatted list of available units and their costs."""
        self.ensure_housing_data()
        if not self.is_housing_area():
            return "This is not a housing area."
            
        housing_types = self.get_available_housing_types()
        if not housing_types:
            return "No housing types available."
            
        from evennia.utils import evtable
        table = evtable.EvTable(
            "|wType|n", 
            "|wRooms|n", 
            "|wRequired Resources|n", 
            border="table"
        )
        
        for rtype, data in housing_types.items():
            cost = self.get_housing_cost(rtype)
            table.add_row(rtype, data['rooms'], cost)
            
        return str(table)

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        """Called when an object enters the room."""
        super().at_object_receive(moved_obj, source_location, **kwargs)
        
        # If this is a freezer room, notify the character
        if self.db.roomtype == "freezer" and moved_obj.has_account:
            moved_obj.msg("|rYou have been frozen and cannot leave this room or speak.|n")
            moved_obj.msg("Contact staff if you believe this is in error.")
        
        # If this is a Quiet Room, notify the character
        elif self.db.roomtype == "Quiet Room" and moved_obj.has_account:
            moved_obj.msg("|rYou have entered a Quiet Room. Communication commands are disabled here.|n")
            
    def at_object_leave(self, moved_obj, target_location, **kwargs):
        """Called when an object leaves the room."""
        # If this is a Quiet Room, notify the character they're leaving
        if self.db.roomtype == "Quiet Room" and moved_obj.has_account:
            moved_obj.msg("|gYou have left the Quiet Room. Communication commands are now available.|n")
            
        super().at_object_leave(moved_obj, target_location, **kwargs)

    def is_command_restricted_in_quiet_room(self, cmdname, switches=None):
        """
        Check if a command is restricted in a Quiet Room.
        
        Args:
            cmdname (str): The command being checked
            switches (list): Optional list of command switches
            
        Returns:
            bool: True if command is restricted, False if allowed
        """
        if self.db.roomtype != "Quiet Room":
            return False
            
        # Basic communication commands are always restricted
        restricted_commands = [
            "say", "pose", "emit", "ooc", 
            "::", ";", "'", '"',
            "+fpose", "+femit", 
            "+shift", "+step"
        ]
        
        # Handle the +roll command - only allow with --job switch
        if cmdname == "+roll":
            # Allow if --job switch is present
            if switches and "--job" in switches:
                return False
            # Otherwise restrict
            return True
            
        # Check if command is in restricted list
        return cmdname in restricted_commands
            
    def prevent_exit_use(self, exit_obj, character):
        """
        Called by exits to check if character can use them.
        Returns True if exit use should be prevented.
        """
        if self.db.roomtype == "freezer":
            character.msg("|rYou are frozen and cannot leave this room.|n")
            return True
        
        # Prevent non-Fae from using exits in Dreaming
        if self.db.fae_only and not self.can_perceive_fae(character):
            character.msg("|mYou cannot interact with the paths of the Dreaming.|n")
            return True
            
        return False

    def is_netspace(self):
        """Check if this room has a net architecture in it."""
        pass

    def is_residence(self):
        """Check if this room is a residence."""
        self.ensure_housing_data()
        return (hasattr(self.db, 'roomtype') and 
                (self.db.roomtype == "Residence" or
                 "Room" in self.db.roomtype or  # Check for "Mage Room", "Vampire Room", etc.
                 self.db.housing_data.get('is_residence', False)))

    def is_valid_residence(self):
        """
        Check if this room is a valid residence that can be used with home commands.
        
        Returns:
            bool: True if this is a valid residence, False otherwise
        """
        if not hasattr(self, 'db'):
            return False
            
        # Check for housing data
        home_data = self.db.home_data if hasattr(self.db, 'home_data') else None
        housing_data = self.db.housing_data if hasattr(self.db, 'housing_data') else None
        
        # Valid room types for residences
        valid_types = [
            "Cube Hotel",
            "Cargo Container",
            "Studio Apartment",
            "Two-Bedroom Apartment",
            "Corporate Conapt",
            "Upscale Conapt",
            "Luxury Penthouse",
        ]
        
        # Check if room type is valid
        has_valid_type = False
        roomtype = self.db.roomtype if hasattr(self.db, 'roomtype') else None
        if roomtype:
            roomtype_lower = roomtype.lower()
            has_valid_type = (
                roomtype_lower in [t.lower() for t in valid_types] or
                roomtype_lower.endswith("room")
            )
        
        # Check both roomtype and housing data
        has_housing_data = (
            (home_data is not None and (home_data.get('owner') or home_data.get('co_owners'))) or
            (housing_data is not None and housing_data.get('is_residence')) or
            hasattr(self.db, 'owner')  # Legacy check
        )
        
        return has_valid_type and has_housing_data


class RoomParent(Room):
    pass

# To use this custom room, you would typically put this code in a file like
# typeclasses/rooms.py in your Evennia game directory, then set it as the
# default room typeclass in your settings file or use it explicitly when
# creating rooms.