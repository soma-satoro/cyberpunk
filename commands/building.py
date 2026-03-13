from evennia import CmdSet
from evennia import create_object
from typeclasses.rental import RentableRoom

from evennia.utils import search, delay
from evennia.utils.search import search_object
from evennia import Command
from world.utils.formatting import divider, footer, format_stat, header
from world.cyberpunk_constants import (
    resource_level_to_descriptor,
    descriptor_to_resource_level,
) 
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.evtable import EvTable

try:
    from world.area_manager import get_area_manager
except ImportError:
    get_area_manager = None


class CmdAreaManage(MuxCommand):
    """
    Manage game areas and their codes for room organization.

    Usage:
      +area/list - List all defined areas
      +area/add <code>=<name>/<description> - Add a new area
      +area/remove <code> - Remove an area (if no rooms use it)
      +area/info <code> - Show detailed info about an area
      +area/rooms <code> - List all rooms in an area
      +area/init - Initialize/reset area manager (admin only)

    Examples:
      +area/list
      +area/add NC=Night City/A sprawling metropolis
      +area/info NC
      +area/rooms NC
    """

    key = "+area"
    locks = "cmd:perm(Builder)"
    help_category = "Building and Housing"

    def func(self):
        if not get_area_manager:
            self.caller.msg("Area manager is not available.")
            return

        caller = self.caller
        area_manager = get_area_manager()

        if not self.switches:
            caller.msg("Usage: +area/list, +area/add, +area/remove, +area/info, +area/rooms, +area/init")
            return

        switch = self.switches[0].lower()

        if switch == "list":
            areas = area_manager.get_areas()
            table = EvTable("Code", "Name", "Rooms", "Next #", border="cells")
            for code, info in sorted(areas.items()):
                room_count = len(info['rooms'])
                next_num = info['next_room']
                table.add_row(code, info['name'], room_count, f"{code}{next_num:02d}")
            caller.msg(f"Defined Areas:\n{table}")

        elif switch == "add":
            if not self.args or "=" not in self.args:
                caller.msg("Usage: +area/add <code>=<name>/<description>")
                return
            code, rest = self.args.split("=", 1)
            code = code.strip().upper()
            if "/" in rest:
                name, description = rest.split("/", 1)
                name, description = name.strip(), description.strip()
            else:
                name, description = rest.strip(), ""
            if len(code) != 2:
                caller.msg("Area code must be exactly 2 characters.")
                return
            success, message = area_manager.add_area(code, name, description)
            caller.msg(message)

        elif switch == "remove":
            if not self.args:
                caller.msg("Usage: +area/remove <code>")
                return
            code = self.args.strip().upper()
            success, message = area_manager.remove_area(code)
            caller.msg(message)

        elif switch == "info":
            if not self.args:
                caller.msg("Usage: +area/info <code>")
                return
            code = self.args.strip().upper()
            info = area_manager.get_area_info(code)
            if not info:
                caller.msg(f"Area code {code} not found.")
                return
            caller.msg(f"|wArea Information: {code}|n")
            caller.msg(f"Name: {info['name']}")
            caller.msg(f"Description: {info['description'] or 'No description set'}")
            caller.msg(f"Next Room Number: {code}{info['next_room']:02d}")
            caller.msg(f"Total Rooms: {len(info['rooms'])}")
            if info['rooms']:
                caller.msg(f"\nRoom Numbers: {', '.join([f'{code}{int(num):02d}' for num in sorted(info['rooms'].keys(), key=int)])}")

        elif switch == "rooms":
            if not self.args:
                caller.msg("Usage: +area/rooms <code>")
                return
            code = self.args.strip().upper()
            info = area_manager.get_area_info(code)
            if not info:
                caller.msg(f"Area code {code} not found.")
                return
            rooms = info['rooms']
            if not rooms:
                caller.msg(f"No rooms found in area {code}.")
                return
            table = EvTable("Room Code", "Room Name", "DB#", border="cells")
            for room_num in sorted(rooms.keys(), key=int):
                room_id = rooms[room_num]
                room_obj = search_object(f"#{room_id}")
                room_code = f"{code}{int(room_num):02d}"
                room_name = room_obj[0].name if room_obj else "|rDeleted Room|n"
                table.add_row(room_code, room_name, f"#{room_id}")
            caller.msg(f"Rooms in Area {code} ({info['name']}):\n{table}")

        elif switch == "init":
            if not self.caller.check_permstring("admin"):
                caller.msg("Only administrators can initialize the area manager.")
                return
            area_manager._init_default_areas()
            areas = area_manager.get_areas()
            caller.msg(f"Area manager initialized. Areas: {', '.join(areas.keys())}")

        else:
            caller.msg("Valid switches: /list, /add, /remove, /info, /rooms, /init")


class CmdRoom(MuxCommand):
    """
    Comprehensive room setup and display properties.

    Usage:
      +room                          - Show current room settings
      +room/res <target>=<value>     - Set room resources (0-6 or: Cheap, Everyday, Costly, Premium, Expensive, Very Expensive, Luxury)
      +room/type <target>=<type>     - Set room type
      +room/unfindable <target>=<on/off> - Set room findability
      +room/area <target>=<code>     - Set area and auto-assign room code (e.g. NC)
      +room/code <target>=<code>     - Manual room code override (e.g. NC01)
      +room/hierarchy <target>=<district>,<area> - Set location hierarchy for display
      +room/tag <target>=<tag1>,<tag2> - Set room tags
      +room/tags <target>            - View room tags
      +room/coords <target>=<x>,<y>  - Set coordinates for mapping
      +room/chargen <target>=<on/off> - Convert room to/from ChargenRoom typeclass

    Target: 'here', room name, or #dbref

    Examples:
      +room/res here=4
      +room/type here=Beach Town
      +room/area here=NC
      +room/hierarchy here=Watson,Northside
      +room/tag here=bar,nightlife
      +room/tags here
    """

    key = "+room"
    locks = "cmd:perm(Builder)"
    help_category = "Building and Housing"

    def get_target_room(self, args):
        """Helper method to get target room from args."""
        if not args:
            return self.caller.location

        target = args.strip()
        if target.lower() == "here":
            return self.caller.location

        # Handle database reference (#123)
        if target.startswith('#'):
            try:
                dbref = int(target[1:])
                objs = search_object(f"#{dbref}")
                if objs and hasattr(objs[0], 'location') and objs[0].location is None:
                    return objs[0]
            except ValueError:
                pass

        room = self.caller.search(target)
        if not room:
            return None

        # Verify the target is actually a room (Room, RoomParent, or ChargenRoom)
        if not (room.is_typeclass("typeclasses.rooms.Room") or room.is_typeclass("typeclasses.rooms.RoomParent") or
                room.is_typeclass("typeclasses.chargen.ChargenRoom")):
            self.caller.msg("That is not a room.")
            return None

        return room

    def display_current_settings(self, room):
        """Display the current room settings."""
        table = EvTable("Setting", "Value", border="cells")
        table.add_row("Area Name", room.db.area_name or "Not set")
        table.add_row("Area Code", room.db.area_code or "Not set")
        hierarchy = room.db.location_hierarchy
        if hierarchy:
            hierarchy = list(hierarchy) if hasattr(hierarchy, '__iter__') and not isinstance(hierarchy, (str, bytes)) else hierarchy
            table.add_row("Hierarchy", " - ".join(hierarchy))
        else:
            table.add_row("Hierarchy", "Not set")
        res_display = resource_level_to_descriptor(room.db.resources)
        table.add_row("Resources", res_display)
        table.add_row("Room Type", room.db.roomtype or "Not set")
        table.add_row("Unfindable", "Yes" if room.db.unfindable else "No")
        tags = getattr(room.db, 'tags', []) or []
        table.add_row("Tags", ", ".join(tags) if tags else "None")
        if hasattr(room.db, 'map_x') and hasattr(room.db, 'map_y'):
            table.add_row("Coords", f"({room.db.map_x}, {room.db.map_y})")
        else:
            table.add_row("Coords", "Not set")
        self.caller.msg(f"Room Settings for {room.name}:\n{table}")

    def func(self):
        if not self.switches:
            room = self.get_target_room(self.args or "here")
            if not room:
                self.caller.msg("You must be in a room or specify a valid room.")
                return
            self.display_current_settings(room)
            return

        switch = self.switches[0].lower()

        # /tags doesn't require a value
        if switch == "tags":
            room = self.get_target_room(self.lhs or self.args or "here")
            if not room:
                self.caller.msg("You must be in a room or specify a valid room.")
                return
            tags = getattr(room.db, 'tags', []) or []
            room_info = f"#{room.id}" if room != self.caller.location else "here"
            if tags:
                self.caller.msg(f"Room tags for {room.name} ({room_info}): {', '.join(tags)}")
            else:
                self.caller.msg(f"No tags set for room {room.name} ({room_info})")
            return

        # All other switches require a value
        if not self.rhs:
            self.caller.msg(f"Usage: +room/{switch} <target>=<value>")
            return

        room = self.get_target_room(self.lhs)
        if not room:
            return

        value = self.rhs
        room_info = f"#{room.id}" if room != self.caller.location else "here"

        if switch == "res":
            # Accept descriptor name or 0-6
            val = descriptor_to_resource_level(value)
            if val is None:
                try:
                    val = int(value)
                    if val < 0 or val > 6:
                        self.caller.msg("Resource level must be 0-6, or use: Cheap, Everyday, Costly, Premium, Expensive, Very Expensive, Luxury.")
                        return
                except ValueError:
                    self.caller.msg("Use 0-6 or a descriptor: Cheap, Everyday, Costly, Premium, Expensive, Very Expensive, Luxury.")
                    return
            room.db.resources = val
            desc = resource_level_to_descriptor(val)
            self.caller.msg(f"Set resources to {desc} for {room.get_display_name(self.caller)}.")

        elif switch == "type":
            room.db.roomtype = value
            self.caller.msg(f"Set room type to '{value}' for {room.get_display_name(self.caller)}.")

        elif switch == "unfindable":
            setting = value.lower()
            if setting not in ["on", "off"]:
                self.caller.msg("Please specify either 'on' or 'off'.")
                return
            room.db.unfindable = (setting == "on")
            self.caller.msg(f"{room.get_display_name(self.caller)} is now {'unfindable' if setting == 'on' else 'findable'}.")

        elif switch == "area":
            if not get_area_manager:
                self.caller.msg("Area manager is not available. Use +area/init first.")
                return
            area_manager = get_area_manager()
            if len(value) != 2:
                self.caller.msg("Area code must be exactly 2 letters (e.g., NC, WB). Use '+area/list' to see areas.")
                return
            area_code = value.upper()
            if not area_manager.validate_area_code(area_code):
                self.caller.msg(f"Area code {area_code} is not defined. Use '+area/list' to see areas.")
                return
            area_info = area_manager.get_area_info(area_code)
            full_code = area_manager.get_next_room_number(area_code)
            room.db.area_name = area_info['name']
            room.db.area_code = full_code
            room_number = int(full_code[2:])
            area_manager.register_room(area_code, room_number, room.id)
            self.caller.msg(f"Room assigned to area '{area_info['name']}' with code {full_code} ({room_info})")

        elif switch == "code":
            if not get_area_manager:
                self.caller.msg("Area manager is not available.")
                return
            area_manager = get_area_manager()
            if len(value) != 4:
                self.caller.msg("Room code must be 4 characters (e.g., NC01). Use '+room/area here=NC' for auto-assign.")
                return
            area_code = value[:2].upper()
            try:
                room_number = int(value[2:])
                full_code = f"{area_code}{room_number:02d}"
            except ValueError:
                self.caller.msg("Invalid room code format.")
                return
            if not area_manager.validate_area_code(area_code):
                self.caller.msg(f"Area code {area_code} is not defined.")
                return
            area_rooms = area_manager.get_area_rooms(area_code)
            if room_number in area_rooms and area_rooms[room_number] != room.id:
                self.caller.msg(f"Room code {full_code} is already assigned to another room.")
                return
            room.db.area_code = full_code
            area_info = area_manager.get_area_info(area_code)
            if area_info:
                room.db.area_name = area_info['name']
            area_manager.register_room(area_code, room_number, room.id)
            self.caller.msg(f"Room code set to {full_code} ({room_info})")

        elif switch == "hierarchy":
            hierarchy = [item.strip() for item in value.split(",")]
            if len(hierarchy) != 2:
                self.caller.msg("Hierarchy must be: <district>,<area> (e.g., Watson,Northside)")
                return
            room.db.location_hierarchy = hierarchy
            self.caller.msg(f"Location hierarchy set to '{' - '.join(hierarchy)}' ({room_info})")

        elif switch == "tag":
            tags = [t.strip() for t in value.split(",") if t.strip()]
            room.db.tags = tags
            self.caller.msg(f"Room tags set to: {', '.join(tags)} ({room_info})")

        elif switch == "coords":
            if not get_area_manager:
                self.caller.msg("Area manager is not available.")
                return
            area_manager = get_area_manager()
            if "," not in value:
                self.caller.msg("Usage: +room/coords <target>=<x>,<y>")
                return
            try:
                x_str, y_str = value.split(",", 1)
                x, y = int(x_str.strip()), int(y_str.strip())
            except ValueError:
                self.caller.msg("Coordinates must be integers.")
                return
            if area_manager.set_room_coordinates(room.id, x, y):
                self.caller.msg(f"Room coordinates set to ({x}, {y}) ({room_info})")
            else:
                self.caller.msg("Error setting coordinates.")

        elif switch == "chargen":
            # Convert room to/from ChargenRoom typeclass
            value_lower = value.lower()
            if value_lower in ["on", "true", "yes", "1"]:
                if room.is_typeclass("typeclasses.chargen.ChargenRoom"):
                    self.caller.msg(f"Room {room.name} ({room_info}) is already a ChargenRoom.")
                    return
                room.swap_typeclass("typeclasses.chargen.ChargenRoom", clean_attributes=False)
                room.tags.add("chargen")
                room.tags.add("ooc")
                self.caller.msg(f"Room {room.name} ({room_info}) converted to ChargenRoom.")
                self.caller.msg("Tags 'chargen' and 'ooc' have been applied. Character generation progress will display for characters present.")
            elif value_lower in ["off", "false", "no", "0"]:
                if not room.is_typeclass("typeclasses.chargen.ChargenRoom"):
                    self.caller.msg(f"Room {room.name} ({room_info}) is not a ChargenRoom.")
                    return
                room.swap_typeclass("typeclasses.rooms.Room", clean_attributes=False)
                room.tags.remove("chargen")
                room.tags.remove("ooc")
                self.caller.msg(f"Room {room.name} ({room_info}) converted back to normal Room.")
            else:
                self.caller.msg("Chargen setting must be 'on' or 'off'.")

        else:
            self.caller.msg("Valid switches: res, type, unfindable, area, code, hierarchy, tag, tags, coords, chargen")

    def access(self, srcobj, access_type="cmd", default=False):
        if access_type != "cmd":
            return super().access(srcobj, access_type, default)
        return True

class CmdView(MuxCommand):
    """
    View additional details about objects, rooms, and characters.

    Usage:
      +view                           - List all views in current location
      +view <target>                 - List all views on a specific target
      +view <target>/<viewname>      - Show specific view on target
      +view/set <viewname>/<target>=<text>  - Set a view
      +view/del <viewname>/<target>  - Delete a view

    Views are a way to add detail to items or locations without cluttering
    the main description. Views can be set on any object, character, or room.

    Examples:
      +view                  - Shows all views in current room
      +view here            - Same as above
      +view sword           - Lists all views on the sword
      +view sword/hilt      - Shows the 'hilt' view of the sword
      +view/set window/here=Through the window you see a beautiful garden
      +view/del window/here - Removes the 'window' view from current room
    """

    key = "+view"
    aliases = ["view"]
    locks = "cmd:all()"
    help_category = "Building and Housing"

    def func(self):
        caller = self.caller
        location = caller.location

        if not self.args and not self.switches:
            # Show all views in current location
            self._list_views(location)
            return

        if "set" in self.switches:
            # Setting a new view
            if not self.rhs:
                caller.msg("Usage: +view/set <viewname>/<target>=<description>")
                return

            try:
                viewname, target = self.lhs.split("/", 1)
                viewname = viewname.strip().lower()
                target = target.strip().lower()
            except ValueError:
                caller.msg("Usage: +view/set <viewname>/<target>=<description>")
                return

            # Find the target object
            if target == "here":
                target_obj = location
            else:
                target_obj = caller.search(target)
                if not target_obj:
                    return

            # Check permissions
            if not (target_obj.access(caller, "control") or target_obj.access(caller, "edit")):
                caller.msg(f"You don't have permission to add views to {target_obj.get_display_name(caller)}.")
                return

            # Initialize views dict if it doesn't exist
            if not target_obj.db.views:
                target_obj.db.views = {}

            # Store the view
            target_obj.db.views[viewname] = self.rhs
            caller.msg(f"Added view '{viewname}' to {target_obj.get_display_name(caller)}.")
            return

        if "del" in self.switches:
            # Deleting a view
            if not self.args:
                caller.msg("Usage: +view/del <viewname>/<target>")
                return

            try:
                viewname, target = self.args.split("/", 1)
                viewname = viewname.strip().lower()
                target = target.strip().lower()
            except ValueError:
                caller.msg("Usage: +view/del <viewname>/<target>")
                return

            # Find the target object
            if target == "here":
                target_obj = location
            else:
                target_obj = caller.search(target)
                if not target_obj:
                    return

            # Check permissions
            if not (target_obj.access(caller, "control") or target_obj.access(caller, "edit")):
                caller.msg(f"You don't have permission to remove views from {target_obj.get_display_name(caller)}.")
                return

            # Remove the view
            if target_obj.db.views and viewname in target_obj.db.views:
                del target_obj.db.views[viewname]
                caller.msg(f"Removed view '{viewname}' from {target_obj.get_display_name(caller)}.")
            else:
                caller.msg(f"No view named '{viewname}' found on {target_obj.get_display_name(caller)}.")
            return

        # Handle viewing
        if "/" in self.args:
            # View specific detail
            try:
                target, viewname = self.args.split("/", 1)
                viewname = viewname.strip().lower()
            except ValueError:
                caller.msg("Usage: +view <target>/<viewname>")
                return

            # Find the target object
            if target.lower() == "here":
                target_obj = location
            else:
                target_obj = caller.search(target)
                if not target_obj:
                    return

            # Show the view if it exists
            if target_obj.db.views and viewname in target_obj.db.views:
                caller.msg(target_obj.db.views[viewname])
            else:
                caller.msg(f"No view named '{viewname}' found on {target_obj.get_display_name(caller)}.")
        else:
            # List all views on target
            if self.args.lower() == "here":
                target_obj = location
            else:
                target_obj = caller.search(self.args)
                if not target_obj:
                    return

            self._list_views(target_obj)

    def _list_views(self, target):
        """Helper method to list all views on a target."""
        if not target.db.views or not target.db.views.keys():
            self.caller.msg(f"No views found on {target.get_display_name(self.caller)}.")
            return

        table = EvTable("|wView Name|n", border="table")
        for view in sorted(target.db.views.keys()):
            table.add_row(view)
        
        self.caller.msg(f"|wViews available on {target.get_display_name(self.caller)}:|n")
        self.caller.msg(table)

class CmdPlaces(MuxCommand):
    """
    Handle places in a room.
    
    Usage:
        +place/create <name>
        +place/delete <name>
        +place/list
        +place/join <name>
        +place/leave
    """
    
    key = "+place"
    aliases = ["place", "places", "+places"]
    locks = "cmd:all()"
    help_category = "Building and Housing"
    
    def _leave_place(self, quiet=False):
        """Leave current place."""
        if not self.caller.db.place:
            if not quiet:
                self.caller.msg("You are not at any place.")
            return
            
        place = self.caller.db.place
        if not quiet:
            self.caller.msg(f"You leave {place}.")
            self.caller.location.msg_contents(
                f"{self.caller.name} leaves {place}.",
                exclude=[self.caller]
            )
        self.caller.db.place = None
        
    def func(self):
        """Execute command."""
        if not self.switches:
            self.caller.msg("Usage: +place/<switch>")
            return
            
        switch = self.switches[0]
        location = self.caller.location
        
        # Initialize places dictionary if it doesn't exist
        if not hasattr(location.db, 'places') or location.db.places is None:
            location.db.places = {}
            
        if switch == "create":
            if not self.args:
                self.caller.msg("Usage: +place/create <name>")
                return
                
            name = self.args.strip()
            if name in location.db.places:
                self.caller.msg(f"Place '{name}' already exists.")
                return
                
            location.db.places[name] = []
            self.caller.msg(f"Created place '{name}'.")
            
        elif switch == "delete":
            if not self.args:
                self.caller.msg("Usage: +place/delete <name>")
                return
                
            name = self.args.strip()
            if name not in location.db.places:
                self.caller.msg(f"Place '{name}' not found.")
                return
                
            # Move any occupants out
            for occupant in location.db.places[name]:
                if occupant.db.place == name:
                    occupant.db.place = None
                    occupant.msg(f"Place '{name}' has been deleted.")
                    
            del location.db.places[name]
            self.caller.msg(f"Deleted place '{name}'.")
            
        elif switch == "list":
            if not location.db.places:
                self.caller.msg("No places found in this room.")
                return
                
            from evennia.utils.evtable import EvTable
            table = EvTable("|wPlace|n", "|wOccupants|n", border="table")
            for place, occupants in location.db.places.items():
                # Clean up stale occupants
                valid_occupants = []
                for occ in occupants:
                    if (occ and occ.location == location and 
                        occ.db.place == place):
                        valid_occupants.append(occ)
                location.db.places[place] = valid_occupants
                
                # Add to table
                table.add_row(
                    place,
                    ", ".join(o.name for o in valid_occupants) or "Empty"
                )
            self.caller.msg(table)
            
        elif switch == "join":
            if not self.args:
                self.caller.msg("Usage: +place/join <name>")
                return
                
            target = self.args.strip()
            
            try:
                place_num = int(target) - 1
                place_name = list(location.db.places.keys())[place_num]
            except (ValueError, IndexError):
                place_name = target
                
            if place_name not in location.db.places:
                self.caller.msg(f"Place '{target}' not found.")
                return
                
            if self.caller.db.place:
                if self.caller.db.place == place_name:
                    self.caller.msg(f"You are already at {place_name}.")
                    return
                self._leave_place(quiet=True)
                
            location.db.places[place_name].append(self.caller)
            self.caller.db.place = place_name
            self.caller.msg(f"You join {place_name}. You can now use the |wtt|n command to talk privately with others at this place. Type |whelp tt|n for more information.")
            self.caller.location.msg_contents(
                f"{self.caller.name} joins {place_name}.",
                exclude=[self.caller]
            )
            
        elif switch == "leave":
            self._leave_place()

class CmdManageBuilding(MuxCommand):
    """
    Manage apartment building zones.
    
    Usage:
        +manage/setlobby          - Sets current room as building lobby
        +manage/addroom           - Adds current room to building zone (alias: addfloor)
        +manage/floor <num> [max] - Set floor number and max units for rental floor
        +manage/setcost <room>=<rent_mod>,<purchase_mod> - Modify apartment costs
        +manage/createapt [type] [=rent,purchase,rooms] - Create apartment (staff)
        +manage/removeroom        - Removes current room from building zone
        +manage/info              - Shows building zone information
        +manage/clear             - Clears all building zone data
        +manage/types             - Lists available apartment types
        +manage/addtype <type>    - Add an apartment type to this building
        +manage/remtype <type>    - Remove an apartment type from this building
        
        +manage/updateapts         - Update all apartment exits in building
        +manage/updateapts <room>  - Update apartment exits in specific room
        
        +manage/apartments         - List all apartments in current building
        +manage/apartments <player>  - List apartments owned by player
        +manage/apartments/search=<text>  - Search apartments by name/desc
        +manage/apartments/floor=<number>  - List apartments on specific floor
        
        +manage/sethousing/apartment <resources> [max_units] - Apartment building
        +manage/sethousing/motel <resources> [max_units]    - Motel
        +manage/sethousing/residential <resources> [max_units] - Residential area
        +manage/sethousing/encampment <resources> [max_units] - Encampment area
        +manage/sethousing/clear              - Clear housing settings
        
    Example:
        +manage/setlobby
        +manage/addtype Studio
        +manage/addtype "Two-Bedroom"
        +manage/sethousing/apartment 2 20
    """
    
    key = "+manage"
    locks = "cmd:perm(builders)"
    help_category = "Building and Housing"
    
    def initialize_housing_data(self, location):
        """Helper method to initialize housing data"""
        if not hasattr(location.db, 'housing_data') or not location.db.housing_data:
            location.db.housing_data = {
                'is_housing': False,
                'max_apartments': 0,
                'current_tenants': {},
                'apartment_numbers': set(),
                'required_resources': 0,
                'building_zone': None,
                'connected_rooms': set(),
                'is_lobby': False,
                'available_types': [],
                'allowed_splats': set()  # Added for splat restrictions
            }
        return location.db.housing_data

    def get_lobby_for_location(self, location):
        """
        Get the correct lobby for this location.
        When on a floor, use building_zone to get THIS building's lobby (isolates from other buildings).
        """
        if not location or not hasattr(location, 'db'):
            return None
        hd = getattr(location.db, 'housing_data', None) or {}
        if hd.get('is_lobby'):
            return location
        building_zone = hd.get('building_zone')
        if building_zone:
            lobby = self.caller.search(f"#{building_zone}")
            if lobby and hasattr(lobby, 'db'):
                lobby_hd = getattr(lobby.db, 'housing_data', None)
                if lobby_hd and lobby_hd.get('is_lobby'):
                    return lobby
        return self.find_lobby(location)

    def find_lobby(self, location):
        """Helper method to find the connected lobby"""
        # First check if this room is a lobby
        if location.db.housing_data and location.db.housing_data.get('is_lobby'):
            return location
            
        # Then check all connected exits
        for exit in location.exits:
            if not exit.destination:
                continue
                
            # Check if this exit leads to lobby (by name or alias)
            exit_names = [exit.key.lower()]
            if exit.aliases:
                exit_names.extend([alias.lower() for alias in exit.aliases.all()])
            
            if any(name in ['lobby', 'l'] for name in exit_names):
                dest = exit.destination
                if (hasattr(dest, 'db') and 
                    hasattr(dest.db, 'housing_data') and 
                    dest.db.housing_data and 
                    dest.db.housing_data.get('is_lobby')):
                    return dest
                    
            # Check the destination directly
            dest = exit.destination
            if (hasattr(dest, 'db') and 
                hasattr(dest.db, 'housing_data') and 
                dest.db.housing_data and 
                dest.db.housing_data.get('is_lobby')):
                return dest
                
            # Also check if the destination has exits leading to a lobby
            if hasattr(dest, 'exits'):
                for other_exit in dest.exits:
                    if not other_exit.destination:
                        continue
                    
                    other_dest = other_exit.destination
                    if (hasattr(other_dest, 'db') and 
                        hasattr(other_dest.db, 'housing_data') and 
                        other_dest.db.housing_data and 
                        other_dest.db.housing_data.get('is_lobby')):
                        return other_dest
        
        return None

    def check_lobby_required(self, location, switch):
        """Check if command requires an active lobby setup"""
        # These commands can be used without a lobby
        if switch in ["setlobby", "clear", "info", "sethousing"]:
            return True
            
        # For other commands, check if this is a lobby or connected to one
        if location.db.housing_data.get('is_lobby'):
            return True
            
        # Try to find a connected lobby
        lobby = self.find_lobby(location)
        if lobby:
            return True
                
        self.caller.msg("You must set up this room as a lobby first using +manage/setlobby")
        return False

    def func(self):
        if not self.switches:
            self.caller.msg("Usage: +manage/<switch>")
            return
            
        switch = self.switches[0].lower()
        location = self.caller.location

        # Alias: addfloor -> addroom (add current room as rental floor)
        if switch == "addfloor":
            switch = "addroom"

        # Initialize housing data for all commands
        self.initialize_housing_data(location)

        # Check if command requires lobby setup
        if not self.check_lobby_required(location, switch):
            return

        if switch == "types":
            try:
                from world.rental_data import RENTAL_TYPES
                from evennia.utils.evtable import EvTable
                table = EvTable(
                    "|wType|n",
                    "|wRooms|n",
                    "|wRent|n",
                    "|wPurchase|n",
                    border="table",
                    table_width=78
                )
                for apt_type, data in RENTAL_TYPES.items():
                    if data.get("rent") is None and data.get("purchase") is None:
                        continue
                    rent = data.get("rent")
                    purchase = data.get("purchase")
                    rent_str = f"{rent}eb" if rent is not None else "Corp"
                    purchase_str = f"{purchase}eb" if purchase is not None else "-"
                    table.add_row(apt_type, str(data.get("rooms", 1)), rent_str, purchase_str)
                table.add_row("Custom (bespoke)", "varies", "varies", "varies")
                self.caller.msg(table)
                if location.db.housing_data.get('available_types', []):
                    self.caller.msg("\nTypes available in this building:")
                    from textwrap import wrap
                    wrapped = wrap(", ".join(location.db.housing_data['available_types']), width=76)
                    for line in wrapped:
                        self.caller.msg(line)
            except Exception as e:
                import logging
                logging.getLogger("cyberpunk.building").exception("Error displaying housing types")
                self.caller.msg(f"Error displaying housing types: {e}")

        elif switch == "addtype":
            if not self.args:
                self.caller.msg("Usage: +manage/addtype <type>")
                return
            from world.rental_data import RENTAL_TYPES
            apt_type_input = self.args.strip()
            if apt_type_input and apt_type_input[0] == apt_type_input[-1] and apt_type_input[0] in '"\'':
                apt_type_input = apt_type_input[1:-1].strip()
            if not apt_type_input:
                self.caller.msg("Please specify a type name.")
                return
            apt_type_lower = apt_type_input.lower()
            if apt_type_lower == "custom":
                canonical = "Custom"
            else:
                canonical = None
                for key in RENTAL_TYPES:
                    if key.lower() == apt_type_lower:
                        canonical = key
                        break
                if not canonical:
                    valid = ", ".join(sorted(RENTAL_TYPES.keys()))
                    self.caller.msg(f"Invalid type '{apt_type_input}'. Valid types: {valid}")
                    return
            hd = location.db.housing_data
            if 'available_types' not in hd:
                hd['available_types'] = []
            available = list(hd.get('available_types', []) or [])
            if canonical in available:
                self.caller.msg(f"{canonical} is already available in this building.")
                return
            available.append(canonical)
            location.db.housing_data['available_types'] = available
            self.caller.msg(f"Added {canonical} to available types.")

        elif switch == "setlobby":
            # Set this room as the lobby
            location.db.housing_data['is_lobby'] = True
            location.db.housing_data['building_zone'] = location.dbref
            if 'connected_rooms' not in location.db.housing_data:
                location.db.housing_data['connected_rooms'] = set()
            location.db.housing_data['connected_rooms'].add(location.dbref)
            
            # Ensure room type and max_apartments are set
            if not location.db.roomtype or location.db.roomtype == "Unknown":
                location.db.roomtype = "Apartment Building"
                location.db.housing_data['max_apartments'] = 20  # Default value if not set
            
            # Ensure max_apartments exists
            if 'max_apartments' not in location.db.housing_data:
                location.db.housing_data['max_apartments'] = 20  # Default value
            
            location.tags.add("rental_lobby")  # For +rent/search global lookup
            self.caller.msg(f"Set {location.get_display_name(self.caller)} as building lobby.")
            
        elif switch == "addroom":
            # Find the lobby this room should connect to
            lobby = self.find_lobby(location)
                    
            if not lobby:
                self.caller.msg("Could not find a lobby connected to this room.")
                return
            
            # Initialize housing data for this room if needed
            self.initialize_housing_data(location)
            
            # Copy relevant data from lobby
            location.db.roomtype = lobby.db.roomtype
            location.db.resources = lobby.db.resources
            
            # Add this room to the building zone
            location.db.housing_data.update({
                'building_zone': lobby.dbref,
                'is_housing': True,
                'max_apartments': lobby.db.housing_data.get('max_apartments', 20),
                'available_types': lobby.db.housing_data.get('available_types', [])
            })
            
            # Update lobby's connected rooms (reassign to ensure persistence)
            lhd = dict(lobby.db.housing_data or {})
            cr = set(lhd.get('connected_rooms') or set())
            cr.add(location.dbref)
            lhd['connected_rooms'] = cr
            lobby.db.housing_data = lhd
            
            # Initialize floor rental data
            location.db.housing_data['floor_number'] = location.db.housing_data.get('floor_number', 1)
            location.db.housing_data['max_units_per_floor'] = location.db.housing_data.get('max_units_per_floor', 6)
            location.db.housing_data['apartment_numbers'] = set()

            # Tag for +rent/search: rental_floor links floor to lobby via building_zone
            if not location.tags.has("rental_floor"):
                location.tags.add("rental_floor")

            self.caller.msg(f"Added {location.get_display_name(self.caller)} to building zone. Use +manage/floor <number> [max_units] to set floor number.")
            
        elif switch == "floor":
            # Set floor number for rental floor: +manage/floor <number> [max_units]
            if not self.args:
                self.caller.msg("Usage: +manage/floor <floor_number> [max_units_per_floor]")
                return
            parts = self.args.split()
            try:
                floor_num = int(parts[0])
                max_units = int(parts[1]) if len(parts) > 1 else 6
            except ValueError:
                self.caller.msg("Floor number and max_units must be integers.")
                return
            self.initialize_housing_data(location)
            location.db.housing_data['floor_number'] = floor_num
            location.db.housing_data['max_units_per_floor'] = max_units
            if 'apartment_numbers' not in location.db.housing_data:
                location.db.housing_data['apartment_numbers'] = set()
            self.caller.msg(f"Set floor number to {floor_num}, max {max_units} units per floor.")
            
        elif switch == "setcost":
            # Modify rent/purchase cost: +manage/setcost <room>=<rent_mod>,<purchase_mod>
            if not self.rhs or "," not in self.rhs:
                self.caller.msg("Usage: +manage/setcost <room>=<rent_modifier>,<purchase_modifier>")
                return
            room = self.caller.search(self.lhs)
            if not room:
                return
            if not isinstance(room, RentableRoom):
                self.caller.msg("Target must be a RentableRoom (apartment).")
                return
            try:
                rent_mod, purchase_mod = [int(x.strip()) for x in self.rhs.split(",", 1)]
            except ValueError:
                self.caller.msg("Modifiers must be integers.")
                return
            main = room.get_main_room()
            main.db.rent_cost_modifier = rent_mod
            main.db.purchase_cost_modifier = purchase_mod
            for child in (main.db.child_rooms or []):
                if child:
                    child.db.rent_cost_modifier = rent_mod
                    child.db.purchase_cost_modifier = purchase_mod
            self.caller.msg(f"Set cost modifiers: rent +{rent_mod}eb, purchase +{purchase_mod}eb.")

        elif switch == "createapt":
            # Create apartment: +manage/createapt [type] [=rent,purchase,rooms]
            self._do_createapt(location)

        elif switch == "removeroom":
            if not location.db.housing_data.get('building_zone'):
                self.caller.msg("This room is not part of a building zone.")
                return

            # Remove rental_floor tag (for +rent/search)
            if location.tags.has("rental_floor"):
                location.tags.remove("rental_floor")

            # Get the lobby
            lobby = self.caller.search(location.db.housing_data['building_zone'])

            if lobby and 'connected_rooms' in lobby.db.housing_data and location.dbref in lobby.db.housing_data['connected_rooms']:
                lobby.db.housing_data['connected_rooms'].remove(location.dbref)

            # Reset room data
            location.db.housing_data['building_zone'] = None
            location.db.housing_data['is_housing'] = False
            location.db.roomtype = "Room"
            location.db.resources = 0

            self.caller.msg(f"Removed {location.get_display_name(self.caller)} from building zone.")
            
        elif switch == "info":
            if location.db.housing_data.get('is_lobby'):
                if 'connected_rooms' not in location.db.housing_data:
                    location.db.housing_data['connected_rooms'] = set()
                    
                connected = location.db.housing_data['connected_rooms']
                rooms = []
                for room_dbref in connected:
                    room = self.caller.search(room_dbref)
                    if room and room != location:
                        rooms.append(room)
                
                # Build the display using our custom formatting
                output = []
                output.append(header("Building Information"))
                
                # Building Lobby
                output.append(format_stat("Building Lobby", location.get_display_name(self.caller), width=78))
                
                # Connected Rooms
                if rooms:
                    room_list = "\n".join(r.get_display_name(self.caller) for r in rooms)
                    output.append(divider("Connected Rooms"))
                    output.append(room_list)
                else:
                    output.append(divider("Connected Rooms"))
                    output.append("None")
                
                # Building Stats (use rental service for consistent unit counts)
                from world.rental_service import get_building_rental_info
                info = get_building_rental_info(location)
                output.append(divider("Building Stats"))
                output.append(format_stat("Max Units", info.get('total_units', 0), width=78))
                output.append(format_stat("Available Units", info.get('available_count', 0), width=78))
                output.append(format_stat("Resources", location.db.resources, width=78))
                
                # Available Types
                types = location.db.housing_data.get('available_types', [])
                output.append(divider("Available Types"))
                if types:
                    output.append(", ".join(types))
                else:
                    output.append("None")
                
                # Send the formatted output to the caller
                self.caller.msg("\n".join(output))
            else:
                lobby_dbref = location.db.housing_data.get('building_zone')
                if lobby_dbref:
                    lobby = self.caller.search(lobby_dbref)
                    if lobby:
                        self.caller.msg(f"This room is part of {lobby.get_display_name(self.caller)}'s building zone.")
                    else:
                        self.caller.msg("Error: Building lobby not found.")
                else:
                    self.caller.msg("This room is not part of any building zone.")
                    
        elif switch == "clear":
            if location.db.housing_data.get('is_lobby'):
                # Clear all connected rooms
                if 'connected_rooms' in location.db.housing_data:
                    for dbref in location.db.housing_data['connected_rooms']:
                        room = self.caller.search(dbref)
                        if room:
                            room.db.housing_data['building_zone'] = None
                            room.db.housing_data['is_housing'] = False
                            room.db.roomtype = "Room"
                            room.db.resources = 0
                            
            # Reset housing data
            self.initialize_housing_data(location)
            location.db.roomtype = "Room"
            location.db.resources = 0
            if location.tags.has("rental_lobby"):
                location.tags.remove("rental_lobby")
            self.caller.msg("Cleared building zone data.")

        elif switch == "updateapts":
            # Get the target building
            target = None
            if self.args:
                target = self.caller.search(self.args)
                if not target:
                    return
            else:
                target = location

            # Find the lobby if we're not in it
            if not target.db.housing_data.get('is_lobby'):
                lobby = self.find_lobby(target)
                if not lobby:
                    self.caller.msg("You must be in a building lobby or specify a valid building.")
                    return
                target = lobby

            # Update all apartments in the building
            updated = 0
            for room_id in target.db.housing_data.get('connected_rooms', set()):
                room = self.caller.search(f"#{room_id}")
                if room and room.db.housing_data:
                    # Update room properties from the lobby
                    room.db.housing_data.update({
                        'max_apartments': target.db.housing_data.get('max_apartments', 20),
                        'available_types': target.db.housing_data.get('available_types', []),
                        'allowed_splats': target.db.housing_data.get('allowed_splats', set())
                    })
                    updated += 1

            self.caller.msg(f"Updated {updated} rooms in {target.get_display_name(self.caller)}.")

        elif switch == "apartments":
            # Get the target building
            building = None
            if not location.db.housing_data.get('is_lobby'):
                building = self.find_lobby(location)
                if not building:
                    self.caller.msg("You must be in a building lobby.")
                    return
            else:
                building = location

            # Initialize variables for filtering
            target_player = None
            search_text = None
            floor_number = None

            # Parse arguments and switches
            if self.args and "=" not in self.args:
                # Looking for a specific player's apartments
                from evennia.accounts.models import AccountDB
                target_account = AccountDB.objects.filter(username__iexact=self.args).first()
                if target_account:
                    target_player = target_account.puppet or target_account.db._last_puppet
                else:
                    self.caller.msg(f"Player '{self.args}' not found.")
                    return
            elif "search" in self.switches and self.rhs:
                search_text = self.rhs.lower()
            elif "floor" in self.switches and self.rhs:
                try:
                    floor_number = int(self.rhs)
                except ValueError:
                    self.caller.msg("Please specify a valid floor number.")
                    return

            # Get all apartments in the building
            apartments = []
            for room_id in building.db.housing_data.get('connected_rooms', set()):
                room = self.caller.search(f"#{room_id}")
                if room and room.db.housing_data:
                    # Filter based on criteria
                    if target_player:
                        # Check if player owns this apartment
                        if not self.is_owner(room, target_player):
                            continue
                    elif search_text:
                        # Check if search text matches name or description
                        if (search_text not in room.key.lower() and 
                            (not room.db.desc or search_text not in room.db.desc.lower())):
                            continue
                    elif floor_number is not None:
                        # Check if apartment is on the specified floor
                        try:
                            room_floor = int(room.key.split()[1])  # Assumes format "Apartment X-Y"
                            if room_floor != floor_number:
                                continue
                        except (IndexError, ValueError):
                            continue

                    apartments.append(room)

            if not apartments:
                if target_player:
                    self.caller.msg(f"{target_player.name} doesn't own any apartments in this building.")
                elif search_text:
                    self.caller.msg(f"No apartments found matching '{search_text}'.")
                elif floor_number is not None:
                    self.caller.msg(f"No apartments found on floor {floor_number}.")
                else:
                    self.caller.msg("No apartments found in this building.")
                return

            # Display results
            from evennia.utils.evtable import EvTable
            table = EvTable("|wApartment|n", "|wOwner|n", "|wType|n", "|wStatus|n", border="table")
            for apt in apartments:
                owner = "None"
                if apt.db.housing_data and 'owner' in apt.db.housing_data:
                    owner_char = self.caller.search(f"#{apt.db.housing_data['owner']}")
                    if owner_char:
                        owner = owner_char.name
                apt_type = apt.db.roomtype if apt.db.roomtype else "Unknown"
                status = "Locked" if apt.db.housing_data.get('locked', False) else "Unlocked"
                table.add_row(
                    apt.get_display_name(self.caller),
                    owner,
                    apt_type,
                    status
                )
            self.caller.msg(table)

        elif switch == "sethousing":
            # Handle sethousing functionality
            if not self.switches[1:]:  # No sub-switch provided
                self.caller.msg("Please specify the type: /apartment, /motel, /residential, /encampment, /splat, or /clear")
                return

            sub_switch = self.switches[1]
            location = self.caller.location

            # Handle clear switch first
            if sub_switch == "clear":
                # Clear housing data
                if hasattr(location.db, 'housing_data'):
                    location.db.housing_data = {
                        'is_housing': False,
                        'max_apartments': 0,
                        'current_tenants': {},
                        'apartment_numbers': set(),
                        'required_resources': 0,
                        'building_zone': None,
                        'connected_rooms': set(),
                        'is_lobby': False
                    }
                
                # Reset room attributes
                location.db.roomtype = "Room"
                location.db.resources = 0
                
                # Re-initialize home data
                location.db.home_data = {
                    'locked': False,
                    'keyholders': set(),
                    'owner': None
                }
                
                # Force room appearance update
                location.at_object_creation()
                if location.tags.has("rental_lobby"):
                    location.tags.remove("rental_lobby")
                self.caller.msg("Cleared housing settings for this room.")
                return

            # Splat housing (no resources/max_units)
            if sub_switch == "splat":
                max_units = 20  # Default for splat
                # Set up basic room configuration first
                location.db.roomtype = "Splat Housing"
                location.db.resources = 0  # Splat housing is free
                
                # Set up housing data directly
                housing_data = {
                    'is_housing': True,
                    'max_apartments': max_units,
                    'current_tenants': {},
                    'apartment_numbers': set(),
                    'required_resources': 0,
                    'building_zone': location.dbref,
                    'connected_rooms': {location.dbref},
                    'is_lobby': True,
                    'available_types': ["Splat Housing"]
                }
                
                # Set the housing data directly
                location.db.housing_data = housing_data
                
                # Force a save by accessing the attribute again
                _ = location.db.housing_data
                location.tags.add("rental_lobby")
                self.caller.msg(f"Set up room as free splat-specific housing with {max_units} maximum units. Room is automatically set as a lobby.")
                return

            # Parse arguments for non-splat housing
            try:
                args = self.args.split()
                resources = int(args[0])
                max_units = int(args[1]) if len(args) > 1 else 20  # Default to 20 if not specified
                
                if resources < 0:
                    self.caller.msg("Resources cannot be negative.")
                    return
                    
                if max_units < 1:
                    self.caller.msg("Maximum units must be at least 1.")
                    return
                    
            except (ValueError, IndexError):
                self.caller.msg("Usage: +manage/sethousing/<type> <resources> [max_units]")
                return
            
            # Initialize housing data first
            housing_data = self.initialize_housing_data(location)
            
            # Set up housing based on sub-switch
            if sub_switch == "apartment":
                location.db.roomtype = "Apartment Building"
                location.db.resources = resources
                
                # Set up housing data
                housing_data.update({
                    'is_housing': True,
                    'max_apartments': max_units,
                    'current_tenants': {},
                    'apartment_numbers': set(),
                    'required_resources': resources,
                    'building_zone': location.dbref,
                    'connected_rooms': {location.dbref},
                    'is_lobby': True,
                    'available_types': []
                })
                location.tags.add("rental_lobby")
                self.caller.msg(f"Set up room as apartment building with {resources} resources and {max_units} maximum units.")
                
            elif sub_switch == "motel":
                location.db.roomtype = "Motel"
                location.db.resources = resources
                
                # Set up housing data
                housing_data.update({
                    'is_housing': True,
                    'max_apartments': max_units,
                    'current_tenants': {},
                    'apartment_numbers': set(),
                    'required_resources': resources,
                    'building_zone': location.dbref,
                    'connected_rooms': {location.dbref},
                    'is_lobby': True,
                    'available_types': []
                })
                location.tags.add("rental_lobby")
                self.caller.msg(f"Set up room as motel with {resources} resources and {max_units} maximum units.")
                
            elif sub_switch == "residential":
                location.db.roomtype = "Residential Area"
                location.db.resources = resources
                
                # Set up housing data
                housing_data.update({
                    'is_housing': True,
                    'max_apartments': max_units,
                    'current_tenants': {},
                    'apartment_numbers': set(),
                    'required_resources': resources,
                    'building_zone': location.dbref,
                    'connected_rooms': {location.dbref},
                    'is_lobby': True,
                    'available_types': []
                })
                location.tags.add("rental_lobby")
                self.caller.msg(f"Set up room as residential area with {resources} resources and {max_units} maximum units.")

            elif sub_switch == "encampment":
                location.db.roomtype = "Encampment"
                location.db.resources = resources
                
                # Set up housing data
                housing_data.update({
                    'is_housing': True,
                    'max_apartments': max_units,
                    'current_tenants': {},
                    'apartment_numbers': set(),
                    'required_resources': resources,
                    'building_zone': location.dbref,
                    'connected_rooms': {location.dbref},
                    'is_lobby': True,
                    'available_types': ["Encampment"]
                })
                location.tags.add("rental_lobby")
                self.caller.msg(f"Set up room as encampment with {resources} resources and {max_units} maximum tents.")
                
            else:
                self.caller.msg("Invalid housing type. Use /apartment, /motel, /residential, /encampment, /splat, or /clear")

    def _do_createapt(self, location):
        """Create an apartment (staff). +manage/createapt [type] [=rent,purchase,rooms]"""
        import random
        from evennia.utils import create
        from evennia.utils.search import search_object
        from world.rental_data import RENTAL_TYPES, get_custom_room_layout
        from world.rental_service import create_apartment_rooms, get_apartment_hierarchy

        from world.rental_service import get_lobby_for_rent, normalize_housing_data
        lobby = get_lobby_for_rent(location) or self.get_lobby_for_location(location)
        if not lobby:
            self.caller.msg("You must be in a building lobby or on a rental floor.")
            return

        hd = getattr(lobby.db, 'housing_data', None) or {}
        available = hd.get('available_types', [])

        # Parse args: [type] [=rent,purchase,rooms]
        apt_type = None
        rent_override = None
        purchase_override = None
        rooms_override = None
        if self.args:
            if "=" in self.args:
                lhs, rhs = self.args.split("=", 1)
                apt_type = lhs.strip() or None
                parts = [p.strip() for p in rhs.split(",")]
                if len(parts) >= 1 and parts[0]:
                    try:
                        rent_override = int(parts[0])
                    except ValueError:
                        self.caller.msg("Rent must be a number.")
                        return
                if len(parts) >= 2 and parts[1]:
                    try:
                        purchase_override = int(parts[1])
                    except ValueError:
                        self.caller.msg("Purchase cost must be a number.")
                        return
                if len(parts) >= 3 and parts[2]:
                    try:
                        rooms_override = int(parts[2])
                    except ValueError:
                        self.caller.msg("Rooms must be a number.")
                        return
            else:
                apt_type = self.args.strip()

        is_custom = apt_type and apt_type.lower() == "custom"
        if is_custom:
            if rent_override is None or purchase_override is None or rooms_override is None:
                self.caller.msg("Usage: +manage/createapt Custom=<rent>,<purchase>,<rooms>")
                return
            rental_type = "Custom"
            rent_cost = rent_override
            purchase_cost = purchase_override
            num_rooms = max(1, rooms_override)
            custom_layout = get_custom_room_layout(num_rooms)
        else:
            if not apt_type and available:
                apt_type = available[0]
            elif not apt_type:
                self.caller.msg("Usage: +manage/createapt [type] [=rent,purchase,rooms] or +manage/createapt Custom=rent,purchase,rooms")
                return
            apt_type_lower = apt_type.lower()
            canonical = None
            for key in RENTAL_TYPES:
                if key.lower() == apt_type_lower:
                    canonical = key
                    break
            if not canonical:
                self.caller.msg(f"Unknown type '{apt_type}'. Use +manage/types to see valid types.")
                return
            rental_type = canonical
            data = RENTAL_TYPES[canonical]
            rent_cost = rent_override if rent_override is not None else (data.get("rent") or 0)
            purchase_cost = purchase_override if purchase_override is not None else (data.get("purchase") or 0)
            num_rooms = rooms_override if rooms_override is not None else data.get("rooms", 1)
            custom_layout = None
            if rooms_override is not None and rooms_override != data.get("rooms", 1):
                custom_layout = get_custom_room_layout(rooms_override)

        # Determine floor (use normalize for legacy housing_data)
        from world.rental_service import get_floor_rooms, get_available_apartment_number, get_used_apartment_numbers
        hd = normalize_housing_data(hd) or {}
        floor_room = None
        if location.id == lobby.id:
            floors = get_floor_rooms(lobby)
            if not floors:
                self.caller.msg("No floors set up. Use +manage/addroom on each floor, or ensure lobby has exits to floors (e.g. Up).")
                return
            floor_room = random.choice(floors)
        else:
            floors = get_floor_rooms(lobby)
            for f in floors:
                if f.id == location.id:
                    floor_room = location
                    break

        if not floor_room:
            self.caller.msg("You must be in the lobby or on a rental floor.")
            return

        apt_num = get_available_apartment_number(floor_room)
        if not apt_num:
            self.caller.msg("No apartment slots available on this floor.")
            return

        main_hierarchy = get_apartment_hierarchy(lobby, floor_room=floor_room)
        building_name = main_hierarchy[0] if (main_hierarchy and main_hierarchy[0]) else lobby.key
        district = main_hierarchy[1] if len(main_hierarchy) >= 2 else "Unknown"

        # Apartment must be sibling of floor (location=floor's parent), not child.
        # Otherwise it appears as Object in floor instead of traversable via exit.
        main = create.create_object(
            RentableRoom,
            key=f"{apt_num} Main Room",
            location=floor_room.location,
        )
        main.db.rental_type = rental_type
        main.db.apartment_number = apt_num
        main.db.building_name = building_name
        main.db.location_hierarchy = main_hierarchy
        main.db.area_name = main_hierarchy[0] if main_hierarchy else building_name
        main.db.area_code = apt_num
        main.db.rent_cost = rent_cost
        main.db.purchase_cost = purchase_cost
        main.db.owner = None
        main.db.residents = []
        main.db.co_residents = {}
        main.db.partners = []
        main.db.room_owners = {}
        main.db.purchased = False

        create.create_object(
            typeclass="typeclasses.exits.Exit",
            key=apt_num,
            location=floor_room,
            destination=main,
            aliases=[apt_num],
        )
        create.create_object(
            typeclass="typeclasses.exits.Exit",
            key="Out",
            location=main,
            destination=floor_room,
            aliases=["O"],
        )

        floor_hd = normalize_housing_data(getattr(floor_room.db, 'housing_data', None)) or {}
        used = get_used_apartment_numbers(floor_room)
        used.add(str(apt_num))
        floor_hd['apartment_numbers'] = used
        floor_room.db.housing_data = floor_hd

        if num_rooms > 1:
            if custom_layout:
                create_apartment_rooms(main, rental_type, apt_num, building_name, district, custom_layout=custom_layout)
            else:
                create_apartment_rooms(main, rental_type, apt_num, building_name, district)

        self.caller.msg(f"Created apartment {apt_num} ({rental_type}): {num_rooms} rooms, {rent_cost}eb rent, {purchase_cost}eb purchase. Vacant and ready for +rent <type>.")

    def is_owner(self, room, player):
        """
        Check if a player owns a residence.
        
        Args:
            room (Object): The room to check
            player (Object): The player to check ownership for
            
        Returns:
            bool: True if the player owns the residence, False otherwise
        """
        if not room or not player or not hasattr(room, 'db'):
            return False

        # Check home_data first
        home_data = room.db.home_data if hasattr(room.db, 'home_data') else None
        if home_data:
            # Check primary owner
            if home_data.get('owner') and home_data['owner'].id == player.id:
                return True
            # Check co-owners
            if player.id in home_data.get('co_owners', set()):
                return True
            
        # Check housing_data next
        housing_data = room.db.housing_data if hasattr(room.db, 'housing_data') else None
        if housing_data:
            # Check owner field
            if housing_data.get('owner'):
                is_housing_owner = housing_data['owner'].id == player.id
                if is_housing_owner:
                    return True
            
            # Check current_tenants - handle both string and integer keys
            if housing_data.get('current_tenants'):
                # Check both string and integer versions of the room ID
                str_id = str(room.id)
                int_id = room.id
                is_tenant = (
                    (str_id in housing_data['current_tenants'] and housing_data['current_tenants'][str_id] == player.id) or
                    (int_id in housing_data['current_tenants'] and housing_data['current_tenants'][int_id] == player.id)
                )
                if is_tenant:
                    return True
            
        # Finally check legacy owner
        if hasattr(room.db, 'owner') and room.db.owner:
            is_legacy_owner = room.db.owner.id == player.id
            if is_legacy_owner:
                return True
            
        return False

class CmdSetLock(MuxCommand):
    """
    Set various types of locks on an exit or room.
    
    Usage:
        +setlock <target>=<locktype>:<value>[,<locktype>:<value>...]
        +setlock/view <target>=<locktype>:<value>[,<locktype>:<value>...]
        +setlock/list <target>          - List current locks
        +setlock/clear <target>         - Clear all locks
        
    Lock Types:

    Examples:
        +setlock door=
    """
    
    key = "+setlock"
    aliases = ["+lock", "+locks", "+setlocks"]
    locks = "cmd:perm(builders)"
    help_category = "Building and Housing"
    
    def format_lock_table(self, target):
        """Helper method to format lock table consistently"""
        table = EvTable("|wLock Type|n", "|wDefinition|n", border="table")
        for lockstring in target.locks.all():
            try:
                locktype, definition = lockstring.split(":", 1)
                table.add_row(locktype, definition)
            except ValueError:
                table.add_row("unknown", lockstring)
        return table
    
    def func(self):
        # Handle clear switch first
        if "clear" in self.switches:
            if not self.args:
                self.caller.msg("Usage: +setlock/clear <target>")
                return
                
            target = self.caller.search(self.args, location=self.caller.location)
            if not target:
                return
                
            # Clear all locks
            target.locks.clear()
            
            # Re-add basic locks for exits
            if target.is_typeclass("typeclasses.exits.Exit") or target.is_typeclass("typeclasses.exits.ApartmentExit"):
                # Add standard exit locks
                standard_locks = {
                    "call": "true()",
                    "control": "id(1) or perm(Admin)",
                    "delete": "id(1) or perm(Admin)",
                    "drop": "holds()",
                    "edit": "id(1) or perm(Admin)",
                    "examine": "perm(Builder)",
                    "get": "false()",
                    "puppet": "false()",
                    "teleport": "false()",
                    "teleport_here": "false()",
                    "tell": "perm(Admin)",
                    "traverse": "all()"
                }
                
                for lock_type, lock_def in standard_locks.items():
                    target.locks.add(f"{lock_type}:{lock_def}")
            
            self.caller.msg(f"Cleared all locks from {target.get_display_name(self.caller)}.")
            return

        # Validate base arguments
        if not self.args:
            self.caller.msg("Usage: +setlock <target>=<locktype>:<value>[,<locktype>:<value>...]")
            return
            
        # Handle list switch
        if "list" in self.switches:
            target = self.caller.search(self.lhs, location=self.caller.location)
            if not target:
                return
                
            if not target.locks.all():
                self.caller.msg(f"No locks set on {target.get_display_name(self.caller)}.")
                return
                
            table = self.format_lock_table(target)
            self.caller.msg(f"Locks on {target.get_display_name(self.caller)}:")
            self.caller.msg(table)
            return

        # Validate lock definition
        if not self.rhs:
            self.caller.msg("Usage: +setlock <target>=<locktype>:<value>[,<locktype>:<value>...]")
            return
            
        target = self.caller.search(self.lhs, location=self.caller.location)
        if not target:
            return
            
        # Split OR conditions first (separated by ;)
        or_parts = self.rhs.split(';')
        or_lock_defs = []
        
        for or_part in or_parts:
            # Split AND conditions (separated by ,)
            and_parts = or_part.split(',')
            and_lock_defs = []
            
            for lock_part in and_parts:
                try:
                    locktype, value = lock_part.strip().split(':', 1)
                    locktype = locktype.strip().lower()
                    value = value.strip().lower()
                    
                   
                except ValueError:
                    self.caller.msg(f"Invalid lock format: {lock_part}")
                    return
            
            # Combine AND conditions
            if and_lock_defs:
                or_lock_defs.append(" and ".join(and_lock_defs))
        
        # Combine OR conditions
        final_lock_def = " or ".join(or_lock_defs)
        
        try:
            if target.is_typeclass("typeclasses.exits.Exit") or target.is_typeclass("typeclasses.exits.ApartmentExit"):
                # Get all current locks
                current_locks = []
                for lockstring in target.locks.all():
                    try:
                        lock_type, definition = lockstring.split(":", 1)
                        if lock_type != ("traverse" if "view" not in self.switches else "view"):
                            current_locks.append((lock_type, definition))
                    except ValueError:
                        continue
                
                # Clear and restore locks
                target.locks.clear()
                for lock_type, lock_def in current_locks:
                    target.locks.add(f"{lock_type}:{lock_def}")
                    
                # Add standard exit locks
                standard_locks = {
                    "call": "true()",
                    "control": "id(1) or perm(Admin)",
                    "delete": "id(1) or perm(Admin)",
                    "drop": "holds()",
                    "edit": "id(1) or perm(Admin)",
                    "examine": "perm(Builder)",
                    "get": "false()",
                    "puppet": "false()",
                    "teleport": "false()",
                    "teleport_here": "false()",
                    "tell": "perm(Admin)",
                }
                
                for lock_type, lock_def in standard_locks.items():
                    if not any(l.startswith(f"{lock_type}:") for l in target.locks.all()):
                        target.locks.add(f"{lock_type}:{lock_def}")
                
                # Add new lock
                lock_type = "view" if "view" in self.switches else "traverse"
                target.locks.add(f"{lock_type}:{final_lock_def}")
                target.locks.cache_lock_bypass(target)
                
                self.caller.msg(f"Added {lock_type} lock to {target.get_display_name(self.caller)}.")
            else:
                target.locks.add(f"view:{final_lock_def}")
                self.caller.msg(f"Added view lock to {target.get_display_name(self.caller)}.")
            
        except Exception as e:
            self.caller.msg(f"Error setting lock: {str(e)}")

class BuildingCmdSet(CmdSet):
    def at_cmdset_creation(self):
        self.priority = 1  # Override default commands
        self.add(CmdRoom())  # Add the new unified room command
        self.add(CmdManageBuilding())  # Includes +manage/updateapts, +manage/apartments, +manage/splats
        self.add(CmdSetLock())
        self.add(CmdView())
        self.add(CmdPlaces())