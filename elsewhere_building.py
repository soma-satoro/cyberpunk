"""
Building Commands

Commands for world building including areas, rooms, and mapping.
"""

from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.evtable import EvTable
from evennia.utils import utils
from evennia.utils.search import search_object
from utils.text import process_special_characters
from world.area_manager import get_area_manager


class CmdAreaManage(MuxCommand):
    """
    Manage game areas and their codes.
    
    Usage:
      +area/list - List all defined areas
      +area/add <code>=<name>/<description> - Add a new area
      +area/remove <code> - Remove an area (if no rooms use it)
      +area/info <code> - Show detailed info about an area
      +area/rooms <code> - List all rooms in an area
      +area/init - Initialize/reset area manager (admin only)
      
    Examples:
      +area/list
      +area/add TW=The Thorns/Twisted pathways of the deep Hedge
      +area/info HE
      +area/rooms HE
      +area/remove TW
      +area/init
    """
    
    key = "+area"
    locks = "cmd:perm(builders)"
    help_category = "Building Commands"
    
    def func(self):
        caller = self.caller
        area_manager = get_area_manager()
        
        if not self.switches:
            caller.msg("Usage: +area/list, +area/add, +area/remove, +area/info, +area/rooms, +area/init")
            return
        
        switch = self.switches[0].lower()
        
        if switch == "list":
            self.list_areas(area_manager)
        elif switch == "add":
            self.add_area(area_manager)
        elif switch == "remove":
            self.remove_area(area_manager)
        elif switch == "info":
            self.area_info(area_manager)
        elif switch == "rooms":
            self.list_area_rooms(area_manager)
        elif switch == "init":
            self.init_area_manager(area_manager)
        else:
            caller.msg("Valid switches: /list, /add, /remove, /info, /rooms, /init")
    
    def list_areas(self, area_manager):
        """List all defined areas."""
        areas = area_manager.get_areas()
        
        table = EvTable("Code", "Name", "Rooms", "Next #", border="cells")
        
        for code, info in sorted(areas.items()):
            room_count = len(info['rooms'])
            next_num = info['next_room']
            table.add_row(code, info['name'], room_count, f"{code}{next_num:02d}")
        
        self.caller.msg(f"Defined Areas:\n{table}")
    
    def add_area(self, area_manager):
        """Add a new area."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +area/add <code>=<name>/<description>")
            return
        
        code, rest = self.args.split("=", 1)
        code = code.strip().upper()
        
        if "/" in rest:
            name, description = rest.split("/", 1)
            name = name.strip()
            description = description.strip()
        else:
            name = rest.strip()
            description = ""
        
        if len(code) != 2:
            self.caller.msg("Area code must be exactly 2 characters.")
            return
        
        success, message = area_manager.add_area(code, name, description)
        self.caller.msg(message)
    
    def remove_area(self, area_manager):
        """Remove an area."""
        if not self.args:
            self.caller.msg("Usage: +area/remove <code>")
            return
        
        code = self.args.strip().upper()
        success, message = area_manager.remove_area(code)
        self.caller.msg(message)
    
    def area_info(self, area_manager):
        """Show detailed information about an area."""
        if not self.args:
            self.caller.msg("Usage: +area/info <code>")
            return
        
        code = self.args.strip().upper()
        info = area_manager.get_area_info(code)
        
        if not info:
            self.caller.msg(f"Area code {code} not found.")
            return
        
        self.caller.msg(f"|wArea Information: {code}|n")
        self.caller.msg(f"Name: {info['name']}")
        self.caller.msg(f"Description: {info['description'] or 'No description set'}")
        self.caller.msg(f"Next Room Number: {code}{info['next_room']:02d}")
        self.caller.msg(f"Total Rooms: {len(info['rooms'])}")
        
        if info['rooms']:
            self.caller.msg(f"\nRoom Numbers: {', '.join([f'{code}{num:02d}' for num in sorted(info['rooms'].keys())])}")
    
    def list_area_rooms(self, area_manager):
        """List all rooms in an area."""
        if not self.args:
            self.caller.msg("Usage: +area/rooms <code>")
            return
        
        code = self.args.strip().upper()
        info = area_manager.get_area_info(code)
        
        if not info:
            self.caller.msg(f"Area code {code} not found.")
            return
        
        rooms = info['rooms']
        if not rooms:
            self.caller.msg(f"No rooms found in area {code}.")
            return
        
        table = EvTable("Room Code", "Room Name", "DB#", border="cells")
        
        for room_num in sorted(rooms.keys()):
            room_id = rooms[room_num]
            room_obj = search_object(f"#{room_id}")
            
            room_code = f"{code}{room_num:02d}"
            
            if room_obj:
                room_name = room_obj[0].name
                table.add_row(room_code, room_name, f"#{room_id}")
            else:
                table.add_row(room_code, "|rDeleted Room|n", f"#{room_id}")
        
        self.caller.msg(f"Rooms in Area {code} ({info['name']}):\n{table}")
    
    def init_area_manager(self, area_manager):
        """Initialize/reset the area manager (admin only)."""
        if not self.caller.check_permstring("admin"):
            self.caller.msg("Only administrators can initialize the area manager.")
            return
        
        # Force re-initialization
        area_manager._init_default_areas()
        self.caller.msg("Area manager initialized with default areas.")
        
        # Show the areas
        areas = area_manager.get_areas()
        self.caller.msg(f"Initialized {len(areas)} default areas: {', '.join(areas.keys())}")


class CmdRoomSetup(MuxCommand):
    """
    Set up room area information and display properties.
    
    Usage:
      +room/area here=<area_code>           - Set area and auto-assign room code
      +room/area <target>=<area_code>
      +room/code here=<specific_code>       - Manual override of room code (advanced)
      +room/code <target>=<specific_code>
      +room/coords here=<x>,<y>             - Set room coordinates for mapping
      +room/coords <target>=<x>,<y>
      +room/hierarchy here=<location1>,<location2>
      +room/hierarchy <target>=<location1>,<location2>
      +room/places here=on/off
      +room/places <target>=on/off
      +room/tag <target>=<tag1>,<tag2>,...  - Set room tags (comma-separated)
      +room/tags <target>                   - View room tags
      +room/hisil <target>=<description>    - Set Shadow/Hisil description
      +room/gauntlet <target>=<0-5>         - Set Gauntlet strength rating
      +room/chargen <target>=on/off         - Convert room to/from ChargenRoom typeclass
      
    Target must be specified:
      - 'here' for current room
      - Room name (e.g., "The Square")
      - Database reference (e.g., "#123")
      
    How it works:
      - Use /area with a 2-letter area code (HE, SH, WD, CT)
      - This automatically sets the area name and assigns the next room code
      - Use /code only for manual overrides of specific room codes
      - Use /coords to set room position for ASCII maps
      
    Examples:
      +room/area here=HE               - Set current room to Hedge area
      +room/area #123=SH               - Set room #123 to Shadow area
      +room/code here=HE05             - Manual override to set current room to HE05
      +room/coords here=10,5           - Set current room coordinates for mapping
      +room/hierarchy here=The Square,New Redoubt
      +room/places here=on
      +room/tag here=library,research          - Tag room for investigation purposes
      +room/tags here                          - View current room tags
      +room/hisil here=A twisted reflection...  - Set Shadow description
      +room/gauntlet here=3                     - Set Gauntlet strength
      +room/chargen here=on                     - Convert room to ChargenRoom (shows point tracking)
    
    Common Room Tags:
      Research & Knowledge:
        library, occult_library, archive, computer, research, scriptorium,
        museum, university, laboratory, observatory, clinic, morgue
      
      Social & Gathering:
        bar, nightclub, restaurant, cafe, theater, church, synagogue, mosque,
        gathering_hall, marketplace, stadium, playground, park
      
      Supernatural:
        locus, consecrated, desecrated, hollow, verge, nexus, ley_line,
        haunted, possessed, tainted, blessed, cursed, warded, elysium,
        shadow, underworld, arcadia, hedge, supernal, freehold, consilium,
        sanctum, avernian_gate, dead_road, goblin_market, 
      
      Investigation:
        crime_scene, evidence_room, interrogation, surveillance, safe_house,
        black_market, underground, hidden, secret, restricted
      
      Functional:
        workshop, forge, armory, vault, treasury, stable, garage, warehouse,
        storage, kitchen, infirmary, training_ground, ritual_chamber
      
      Time Period Specific:
        ancient (ruins, catacombs, temple, amphitheater, stadium, bathhouse, forum, agora)
        medieval (castle, monastery, scriptorium, dungeon, keep, bailey)
        victorian (parlor, ballroom, gentlemens_club, opium_den, factory)
        modern (office, apartment, penthouse, parking_garage, server_room)
    """
    
    key = "+room"
    locks = "cmd:perm(builders)"
    help_category = "Building Commands"
    
    def parse(self):
        """
        Custom parsing to handle switch=value and target=value syntax.
        """
        super().parse()
        
        # Parse the arguments to handle both formats:
        # +room/switch=value (no target, use current room)
        # +room/switch target=value (specific target)
        
        self.target_room = None
        self.switch_value = None
        
        if self.switches and self.args:
            args = self.args.strip()
            
            # Check if there's a target specified (format: target=value)
            if '=' in args:
                target_part, value_part = args.split('=', 1)
                target_part = target_part.strip()
                value_part = value_part.strip()
                
                # Target is now required - no empty target allowed
                if not target_part:
                    self.target_room = None  # Will cause error in func()
                    self.switch_value = None
                else:
                    # Format was /switch target=value
                    self.target_room = target_part
                    self.switch_value = value_part
            else:
                # No = found, invalid syntax
                self.target_room = None
                self.switch_value = None
        elif self.switches:
            # Switch but no args - will show usage error
            self.target_room = "here"
            self.switch_value = None
        else:
            # No switches, handle old syntax in func()
            self.target_room = None
            self.switch_value = None
    
    def get_target_room(self, target_str):
        """
        Resolve a target string to a room object.
        
        Args:
            target_str (str): Target specification ('here', room name, or #dbref)
            
        Returns:
            Room object or None if not found
        """
        if not target_str or target_str.lower() == "here":
            return self.caller.location
        
        # Handle database reference (#123)
        if target_str.startswith('#'):
            try:
                dbref = int(target_str[1:])
                rooms = search_object(f"#{dbref}")
                if rooms and hasattr(rooms[0], 'location') and rooms[0].location is None:
                    # Verify it's actually a room (rooms have location=None)
                    return rooms[0]
            except ValueError:
                pass
        
        # Handle room name search
        rooms = search_object(target_str, typeclass='typeclasses.rooms.Room')
        if rooms:
            return rooms[0]
        
        # Fallback: try general search and filter for rooms
        objects = search_object(target_str)
        for obj in objects:
            if hasattr(obj, 'location') and obj.location is None:
                # This is likely a room
                return obj
        
        return None
    
    def func(self):
        caller = self.caller
        
        # Determine target room
        if self.switches:
            # Using switch syntax, get target room
            target_room = self.get_target_room(self.target_room)
            if not target_room:
                if self.target_room and self.target_room.lower() != "here":
                    caller.msg(f"Room '{self.target_room}' not found.")
                else:
                    caller.msg("You must be in a room to use this command.")
                return
            location = target_room
        else:
            # Using old syntax, use current location
            location = caller.location
            if not location:
                caller.msg("You must be in a room to use this command.")
                return
            
        # If no switches and no args, display current settings
        if not self.switches and not self.args:
            self.display_current_settings(location)
            return
            
        # Handle switch-based syntax
        if self.switches:
            switch = self.switches[0].lower()
            
            # Check if target and value are properly specified (except for /tags which doesn't need value)
            if switch not in ["tags"] and (not self.target_room or not self.switch_value):
                caller.msg(f"Usage: +room/{switch} <target>=<value>")
                caller.msg("Target must be 'here', a room name, or #dbref")
                caller.msg(f"Example: +room/{switch} here=<value>")
                return
            
            # Handle /tags separately since it doesn't use = syntax
            if switch == "tags":
                if not self.target_room and self.args:
                    # Format: +room/tags here (no = sign)
                    self.target_room = self.args.strip()
                elif not self.target_room:
                    self.target_room = "here"
                
                # Get the target room
                target_room = self.get_target_room(self.target_room)
                if not target_room:
                    caller.msg(f"Room '{self.target_room}' not found.")
                    return
                
                room_info = f"#{target_room.id}" if target_room != caller.location else "here"
                tags = getattr(target_room.db, 'tags', []) or []
                if tags:
                    caller.msg(f"Room tags for {target_room.name} ({room_info}): {', '.join(tags)}")
                else:
                    caller.msg(f"No tags set for room {target_room.name} ({room_info})")
                return
            
            value = self.switch_value
                
            if switch == "area":
                # Area switch now expects a 2-letter area code and auto-assigns room code
                area_manager = get_area_manager()
                
                if len(value) != 2:
                    caller.msg("Area code must be exactly 2 letters (e.g., HE, SH, WD, CT). Use '+area/list' to see available areas.")
                    return
                
                area_code = value.upper()
                if not area_manager.validate_area_code(area_code):
                    caller.msg(f"Area code {area_code} is not defined. Use '+area/list' to see available areas.")
                    return
                
                # Get area info and auto-assign room code
                area_info = area_manager.get_area_info(area_code)
                full_code = area_manager.get_next_room_number(area_code)
                
                # Set both area name and room code
                location.db.area_name = area_info['name']
                location.db.area_code = full_code
                
                # Register with area manager
                room_number = int(full_code[2:])
                area_manager.register_room(area_code, room_number, location.id)
                
                room_info = f"#{location.id}" if location != caller.location else "here"
                caller.msg(f"Room assigned to area '{area_info['name']}' with code {full_code} for room {location.name} ({room_info})")
                
            elif switch == "code":
                # Code switch is for manual override of specific room codes only
                area_manager = get_area_manager()
                
                if len(value) != 4:
                    caller.msg("Room code must be exactly 4 characters (e.g., HE03). Use '+room/area=HE' for auto-assignment.")
                    return
                
                area_code = value[:2].upper()
                try:
                    room_number = int(value[2:])
                    full_code = f"{area_code}{room_number:02d}"
                except ValueError:
                    caller.msg("Invalid room code format. Must be like HE03.")
                    return
                
                if not area_manager.validate_area_code(area_code):
                    caller.msg(f"Area code {area_code} is not defined. Use '+area/list' to see available areas.")
                    return
                
                # Check if room number is already taken
                area_rooms = area_manager.get_area_rooms(area_code)
                if room_number in area_rooms and area_rooms[room_number] != location.id:
                    existing_room = search_object(f"#{area_rooms[room_number]}")
                    if existing_room:
                        caller.msg(f"Room code {full_code} is already assigned to: {existing_room[0].name}")
                        return
                
                # Set the room code and area name
                location.db.area_code = full_code
                area_info = area_manager.get_area_info(area_code)
                if area_info:
                    location.db.area_name = area_info['name']
                
                # Register with area manager
                area_manager.register_room(area_code, room_number, location.id)
                
                # Update next room number if this is higher
                if room_number >= area_info['next_room']:
                    area_manager.db.areas[area_code]['next_room'] = room_number + 1
                
                room_info = f"#{location.id}" if location != caller.location else "here"
                caller.msg(f"Room code manually set to {full_code} for room {location.name} ({room_info})")
                
            elif switch == "coords":
                # Set room coordinates for mapping
                area_manager = get_area_manager()
                
                if "," not in value:
                    caller.msg("Usage: +room/coords <target>=<x>,<y>")
                    return
                
                try:
                    x_str, y_str = value.split(",", 1)
                    x = int(x_str.strip())
                    y = int(y_str.strip())
                except ValueError:
                    caller.msg("Coordinates must be integers. Usage: +room/coords <target>=<x>,<y>")
                    return
                
                success = area_manager.set_room_coordinates(location.id, x, y)
                if success:
                    room_info = f"#{location.id}" if location != caller.location else "here"
                    caller.msg(f"Room coordinates set to ({x}, {y}) for room {location.name} ({room_info})")
                else:
                    caller.msg("Error setting room coordinates.")
                
            elif switch == "hierarchy":
                hierarchy = [item.strip() for item in value.split(",")]
                if len(hierarchy) != 2:
                    caller.msg("Hierarchy must have exactly 2 location names separated by commas.")
                    return
                location.db.location_hierarchy = hierarchy
                room_info = f"#{location.id}" if location != caller.location else "here"
                caller.msg(f"Location hierarchy set to '{' - '.join(hierarchy)}' for room {location.name} ({room_info})")
                
            elif switch == "places":
                room_info = f"#{location.id}" if location != caller.location else "here"
                if value.lower() in ["on", "true", "yes", "1"]:
                    location.db.places_active = True
                    caller.msg(f"Places system enabled for room {location.name} ({room_info})")
                elif value.lower() in ["off", "false", "no", "0"]:
                    location.db.places_active = False
                    caller.msg(f"Places system disabled for room {location.name} ({room_info})")
                else:
                    caller.msg("Places setting must be 'on' or 'off'.")
            
            elif switch == "tag":
                # Set room tags
                tags = [tag.strip() for tag in value.split(",") if tag.strip()]
                if not hasattr(location.db, 'tags') or location.db.tags is None:
                    location.db.tags = []
                location.db.tags = tags
                room_info = f"#{location.id}" if location != caller.location else "here"
                if tags:
                    caller.msg(f"Room tags set to: {', '.join(tags)} for room {location.name} ({room_info})")
                else:
                    caller.msg(f"Room tags cleared for room {location.name} ({room_info})")
            
            elif switch == "hisil":
                # Set Hisil/Shadow description
                hisil_desc = process_special_characters(value)
                location.db.hisil_desc = hisil_desc
                room_info = f"#{location.id}" if location != caller.location else "here"
                caller.msg(f"Hisil description set for room {location.name} ({room_info})")
                caller.msg(f"Preview:\n{hisil_desc}")
            
            elif switch == "gauntlet":
                # Set Gauntlet rating
                try:
                    gauntlet_strength = int(value)
                except ValueError:
                    caller.msg("Gauntlet strength must be a number between 0 and 5.")
                    return
                
                if gauntlet_strength < 0 or gauntlet_strength > 5:
                    caller.msg("Gauntlet strength must be between 0 and 5.")
                    return
                
                location.db.gauntlet_strength = gauntlet_strength
                
                # Show the rating with description
                strength_desc = {
                    0: "Verge (no Gauntlet)",
                    1: "Locus (+2 dice)",
                    2: "Wilderness (0 modifier)",
                    3: "Small town (-1 dice)",
                    4: "City suburbs (-2 dice)",
                    5: "Dense urban (-3 dice)"
                }
                
                room_info = f"#{location.id}" if location != caller.location else "here"
                caller.msg(f"Gauntlet strength set to {gauntlet_strength} for room {location.name} ({room_info})")
                caller.msg(f"Description: {strength_desc.get(gauntlet_strength, 'Unknown')}")
            
            elif switch == "chargen":
                # Convert room to/from ChargenRoom typeclass
                from evennia import create_object
                
                room_info = f"#{location.id}" if location != caller.location else "here"
                value_lower = value.lower()
                
                if value_lower in ["on", "true", "yes", "1"]:
                    # Convert to ChargenRoom
                    if location.typename == "ChargenRoom":
                        caller.msg(f"Room {location.name} ({room_info}) is already a ChargenRoom.")
                        return
                    
                    # Swap typeclass to ChargenRoom
                    from typeclasses.rooms import ChargenRoom
                    old_typeclass = location.typename
                    location.swap_typeclass("typeclasses.rooms.ChargenRoom", clean_attributes=False)
                    
                    # Ensure chargen and ooc tags are set
                    if not hasattr(location.db, 'tags') or not location.db.tags:
                        location.db.tags = []
                    if 'chargen' not in location.db.tags:
                        location.db.tags.append('chargen')
                    if 'ooc' not in location.db.tags:
                        location.db.tags.append('ooc')
                    
                    caller.msg(f"Room {location.name} ({room_info}) converted to ChargenRoom.")
                    caller.msg("This room will now display character generation progress for all characters present.")
                    caller.msg("Tags 'chargen' and 'ooc' have been automatically applied.")
                    
                elif value_lower in ["off", "false", "no", "0"]:
                    # Convert back to normal Room
                    if location.typename != "ChargenRoom":
                        caller.msg(f"Room {location.name} ({room_info}) is not a ChargenRoom.")
                        return
                    
                    # Swap typeclass back to normal Room
                    from typeclasses.rooms import Room
                    location.swap_typeclass("typeclasses.rooms.Room", clean_attributes=False)
                    
                    caller.msg(f"Room {location.name} ({room_info}) converted back to normal Room.")
                    caller.msg("Character generation progress display has been disabled.")
                else:
                    caller.msg("Chargen setting must be 'on' or 'off'.")
                    
            else:
                caller.msg("Valid switches: /area, /code, /coords, /hierarchy, /places, /tag, /tags, /hisil, /gauntlet, /chargen")
        else:
            # Old syntax fallback for backwards compatibility
            if "=" not in self.args:
                caller.msg("Usage: +room/<switch> <target>=<value>")
                caller.msg("Target must be 'here', a room name, or #dbref")
                caller.msg("Example: +room/area here=HE")
                return
                
            setting, value = self.args.split("=", 1)
            setting = setting.strip().lower()
            value = value.strip()
            
            # For old syntax, assume 'here' as target
            caller.msg("Note: Old syntax detected. Please use: +room/<switch> here=<value>")
            caller.msg("Proceeding with current room as target...")
            
            if setting == "area":
                # Legacy syntax: treat as area code assignment
                area_manager = get_area_manager()
                
                if len(value) != 2:
                    caller.msg("Area code must be exactly 2 letters (e.g., HE, SH, WD, CT). Use '+area/list' to see available areas.")
                    return
                
                area_code = value.upper()
                if not area_manager.validate_area_code(area_code):
                    caller.msg(f"Area code {area_code} is not defined. Use '+area/list' to see available areas.")
                    return
                
                # Get area info and auto-assign room code
                area_info = area_manager.get_area_info(area_code)
                full_code = area_manager.get_next_room_number(area_code)
                
                # Set both area name and room code
                location.db.area_name = area_info['name']
                location.db.area_code = full_code
                
                # Register with area manager
                room_number = int(full_code[2:])
                area_manager.register_room(area_code, room_number, location.id)
                
                caller.msg(f"Room assigned to area '{area_info['name']}' with code {full_code}")
                
            elif setting == "code":
                # Legacy syntax: manual room code override
                area_manager = get_area_manager()
                
                if len(value) != 4:
                    caller.msg("Room code must be exactly 4 characters (e.g., HE03). Use 'area=HE' for auto-assignment.")
                    return
                
                area_code = value[:2].upper()
                try:
                    room_number = int(value[2:])
                    full_code = f"{area_code}{room_number:02d}"
                except ValueError:
                    caller.msg("Invalid room code format. Must be like HE03.")
                    return
                
                if not area_manager.validate_area_code(area_code):
                    caller.msg(f"Area code {area_code} is not defined. Use '+area/list' to see available areas.")
                    return
                
                # Set the room code and area name
                location.db.area_code = full_code
                area_info = area_manager.get_area_info(area_code)
                if area_info:
                    location.db.area_name = area_info['name']
                
                # Register with area manager
                area_manager.register_room(area_code, room_number, location.id)
                
                caller.msg(f"Room code manually set to {full_code}")
                
            elif setting == "hierarchy":
                hierarchy = [item.strip() for item in value.split(",")]
                if len(hierarchy) != 2:
                    caller.msg("Hierarchy must have exactly 2 location names separated by commas.")
                    return
                location.db.location_hierarchy = hierarchy
                caller.msg(f"Location hierarchy set to: {' - '.join(hierarchy)}")
                
            elif setting == "places":
                if value.lower() in ["on", "true", "yes", "1"]:
                    location.db.places_active = True
                    caller.msg("Places system enabled for this room.")
                elif value.lower() in ["off", "false", "no", "0"]:
                    location.db.places_active = False
                    caller.msg("Places system disabled for this room.")
                else:
                    caller.msg("Places setting must be 'on' or 'off'.")
                    
            else:
                caller.msg("Valid settings: area, code, hierarchy, places")
            
    def display_current_settings(self, location):
        """Display the current room settings."""
        table = EvTable("Setting", "Value", border="cells")
        
        table.add_row("Area Name", location.db.area_name or "Not set")
        table.add_row("Area Code", location.db.area_code or "Not set")
        
        hierarchy = location.db.location_hierarchy
        if hierarchy:
            # Convert _SaverList to regular list if needed
            if hasattr(hierarchy, '__iter__') and not isinstance(hierarchy, (str, bytes)):
                hierarchy = list(hierarchy)
            table.add_row("Hierarchy", " - ".join(hierarchy))
        else:
            table.add_row("Hierarchy", "Not set")
            
        table.add_row("Places Active", "Yes" if location.db.places_active else "No")
        
        # Show coordinates if set
        if hasattr(location.db, 'map_x') and hasattr(location.db, 'map_y'):
            table.add_row("Map Coordinates", f"({location.db.map_x}, {location.db.map_y})")
        else:
            table.add_row("Map Coordinates", "Not set")
        
        self.caller.msg(f"Room Settings for {location.name}:\n{table}")


class CmdPlaces(MuxCommand):
    """
    Add a place to the current room.
    
    Usage:
      places/add <name>=<description>
      places/remove <number>
      places/list or places
      places/info <number>
      
    Examples:
      places/add The Stone Pool=A shallow pool in the center of the square
      places/remove 5
      places/list
      places/info 5
    """
    
    key = "places"
    locks = "cmd:perm(builders)"
    help_category = "Building Commands"

    def func(self):
        caller = self.caller
        location = caller.location
        
        if not location:
            caller.msg("You must be in a room to use this command.")
            return
            
        places = getattr(location.db, 'places', {})
        if not places:
            caller.msg("No places defined in this room.")
            return
            
        table = EvTable("#", "Name", "Description", border="cells")
        
        for place_num in sorted(places.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            place = places[place_num]
            table.add_row(place_num, place['name'], place['desc'][:50] + "..." if len(place['desc']) > 50 else place['desc'])
            
        caller.msg(f"Places in {location.name}:\n{table}")

    def func_add(self):
        caller = self.caller
        location = caller.location
        
        if not location:
            caller.msg("You must be in a room to use this command.")
            return
            
        if not self.args or "=" not in self.args:
            caller.msg("Usage: places/add <name>=<description> or places/add <number>:<name>=<description>")
            return
            
        # Check if we have a custom number
        place_number = None
        if ":" in self.args and self.args.split(":")[0].isdigit():
            number_part, rest = self.args.split(":", 1)
            place_number = int(number_part)
            name, desc = rest.split("=", 1)
        else:
            name, desc = self.args.split("=", 1)
            
        name = name.strip()
        desc = desc.strip()
        
        if not name or not desc:
            caller.msg("Both name and description are required.")
            return
        
        # Process special characters in the description
        desc = process_special_characters(desc)
            
        # Add the place using the room's method
        if hasattr(location, 'add_place'):
            place_num = location.add_place(name, desc, place_number)
            caller.msg(f"Place #{place_num} '{name}' added to {location.name}.")
        else:
            caller.msg("This room doesn't support the places system.")

    def func_remove(self):
        caller = self.caller
        location = caller.location
        
        if not location:
            caller.msg("You must be in a room to use this command.")
            return
            
        if not self.args or not self.args.isdigit():
            caller.msg("Usage: places/remove <number>")
            return
            
        place_num = self.args.strip()
        places = getattr(location.db, 'places', {})
        
        if place_num not in places:
            caller.msg(f"No place #{place_num} found in this room.")
            return
            
        place_name = places[place_num]['name']
        del places[place_num]
        location.db.places = places
        
        caller.msg(f"Place #{place_num} '{place_name}' removed from {location.name}.")
  
    def func_info(self):
        caller = self.caller
        location = caller.location
        
        if not location:
            caller.msg("You must be in a room to use this command.")
            return
            
        places = getattr(location.db, 'places', {})
        if not places:
            caller.msg("There are no special places to look at here.")
            return
            
        # If no argument, list all places
        if not self.args:
            table = EvTable("#", "Place", border="cells", width=60)
            for place_num in sorted(places.keys(), key=lambda x: int(x) if x.isdigit() else 0):
                place = places[place_num]
                table.add_row(place_num, place['name'])
            caller.msg(f"Places you can look at here:\n{table}")
            caller.msg("Use 'places/info <number>' or 'places/info <name>' to look at a specific place.")
            return
            
        search_term = self.args.strip().lower()
        
        # First try to find by number
        if search_term in places:
            place = places[search_term]
            caller.msg(f"|w{place['name']}|n\n{place['desc']}")
            return
            
        # Then try to find by name
        for place_num, place in places.items():
            if search_term in place['name'].lower():
                caller.msg(f"|w{place['name']}|n\n{place['desc']}")
                return
                
        caller.msg(f"No place matching '{self.args}' found here.")


class CmdRoomInfo(MuxCommand):
    """
    Display detailed information about the current room's settings.
    
    Usage:
      roominfo
    """
    
    key = "roominfo"
    locks = "cmd:perm(builders)"
    help_category = "Building Commands"
    
    def func(self):
        caller = self.caller
        location = caller.location
        
        if not location:
            caller.msg("You must be in a room to use this command.")
            return
            
        # Basic room info
        caller.msg(f"|wRoom Information for: {location.name}|n")
        caller.msg(f"Dbref: #{location.id}")
        caller.msg(f"Typeclass: {location.typename}")
        
        # Area info
        caller.msg(f"\n|cArea Information:|n")
        caller.msg(f"Area Name: {location.db.area_name or 'Not set'}")
        caller.msg(f"Area Code: {location.db.area_code or 'Not set'}")
        
        hierarchy = location.db.location_hierarchy
        if hierarchy:
            # Convert _SaverList to regular list if needed
            if hasattr(hierarchy, '__iter__') and not isinstance(hierarchy, (str, bytes)):
                hierarchy = list(hierarchy)
            caller.msg(f"Location Hierarchy: {' - '.join(hierarchy)}")
        else:
            caller.msg("Location Hierarchy: Not set")
            
        # Coordinates info
        if hasattr(location.db, 'map_x') and hasattr(location.db, 'map_y'):
            caller.msg(f"Map Coordinates: ({location.db.map_x}, {location.db.map_y})")
        else:
            caller.msg("Map Coordinates: Not set")
            
        # Places info
        caller.msg(f"\n|cPlaces System:|n")
        caller.msg(f"Places Active: {'Yes' if location.db.places_active else 'No'}")
        
        places = getattr(location.db, 'places', {})
        if places is None:
            places = {}
        caller.msg(f"Places Defined: {len(places)}")
        
        # Tags info
        caller.msg(f"\n|cRoom Tags:|n")
        tags = getattr(location.db, 'tags', []) or []
        if tags:
            caller.msg(f"Tags: {', '.join(tags)}")
        else:
            caller.msg("Tags: None")
        
        # Exits info
        caller.msg(f"\n|cExits:|n")
        if location.exits:
            for exit_obj in location.exits:
                dest_name = exit_obj.destination.name if exit_obj.destination else "None"
                caller.msg(f"  {exit_obj.name} -> {dest_name}")
        else:
            caller.msg("  No exits")
            
        # Contents info (characters only)
        characters = [obj for obj in location.contents if obj.has_account]
        caller.msg(f"\n|cCharacters Present:|n")
        caller.msg(f"Count: {len(characters)}")
        for char in characters:
            shortdesc = char.db.shortdesc or "No short description"
            caller.msg(f"  {char.name}: {shortdesc}")


class CmdMap(MuxCommand):
    """
    Display an ASCII map of rooms in an area.
    
    Usage:
      +map - Show map of current area
      +map <area_code> - Show map of specific area
      +map/legend - Show map legend and symbols
      
    Examples:
      +map - Show map of current room's area
      +map HE - Show map of Hedge area
      +map/legend - Show what symbols mean
    """
    
    key = "+map"
    locks = "cmd:all()"
    help_category = "Roleplaying Tools"
    
    def func(self):
        caller = self.caller
        area_manager = get_area_manager()
        
        # Handle legend switch
        if self.switches and self.switches[0].lower() == "legend":
            self.show_legend()
            return
        
        # Determine area code
        area_code = None
        if self.args:
            area_code = self.args.strip().upper()
            if not area_manager.validate_area_code(area_code):
                caller.msg(f"Area code {area_code} not found. Use '+area/list' to see available areas.")
                return
        else:
            # Use current room's area
            location = caller.location
            if not location or not location.db.area_code:
                caller.msg("You must specify an area code or be in a room with an area code set.")
                caller.msg("Usage: +map <area_code>")
                return
            area_code = location.db.area_code[:2]  # First 2 characters
        
        # Generate and display the map
        self.generate_map(area_manager, area_code)
    
    def show_legend(self):
        """Show the map legend."""
        legend = """
|wMap Legend:|n

|c@|n - Your current location
|w#|n - Room with coordinates set
|r?|n - Room without coordinates
|g+|n - Connection between rooms
|y||n - Vertical connection
|y-|n - Horizontal connection

|wNotes:|n
- Only rooms with coordinates set using '+room/coords' will show precise positions
- Rooms without coordinates will be listed separately
- Use '+room/coords here=<x>,<y>' to set room positions for better maps
"""
        self.caller.msg(legend)
    
    def generate_map(self, area_manager, area_code):
        """Generate ASCII map for an area."""
        area_info = area_manager.get_area_info(area_code)
        if not area_info:
            self.caller.msg(f"Area {area_code} not found.")
            return
        
        rooms = area_info['rooms']
        if not rooms:
            self.caller.msg(f"No rooms found in area {area_code}.")
            return
        
        # Get room objects and coordinates
        room_coords = {}
        rooms_without_coords = []
        current_room_coords = None
        
        for room_num, room_id in rooms.items():
            room_obj = search_object(f"#{room_id}")
            if not room_obj:
                continue
            
            room_obj = room_obj[0]
            coords = area_manager.get_room_coordinates(room_id)
            
            if coords:
                room_coords[coords] = {
                    'room': room_obj,
                    'code': f"{area_code}{room_num:02d}",
                    'id': room_id
                }
                
                # Check if this is the caller's current room
                if self.caller.location and self.caller.location.id == room_id:
                    current_room_coords = coords
            else:
                rooms_without_coords.append({
                    'room': room_obj,
                    'code': f"{area_code}{room_num:02d}",
                    'id': room_id
                })
        
        if not room_coords:
            self.caller.msg(f"No rooms in area {area_code} have coordinates set.")
            self.caller.msg("Use '+room/coords here=<x>,<y>' to set room positions.")
            self.caller.msg("Example: +room/coords here=0,0")
            if rooms_without_coords:
                self.caller.msg(f"\nRooms without coordinates:")
                for room_info in rooms_without_coords:
                    self.caller.msg(f"  {room_info['code']}: {room_info['room'].name}")
            return
        
        # Calculate map bounds - ensure we have valid coordinates
        coords_list = list(room_coords.keys())
        if not coords_list:
            self.caller.msg(f"No valid coordinates found for area {area_code}.")
            return
            
        min_x = min(coord[0] for coord in coords_list)
        max_x = max(coord[0] for coord in coords_list)
        min_y = min(coord[1] for coord in coords_list)
        max_y = max(coord[1] for coord in coords_list)
        
        # Create the map grid
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        
        # Limit map size for display
        if width > 50 or height > 30:
            self.caller.msg("Map too large to display (max 50x30). Consider adjusting room coordinates.")
            return
        
        # Initialize map with spaces
        map_grid = []
        for y in range(height):
            map_grid.append([' '] * width)
        
        # Place rooms on the map
        for (x, y), room_info in room_coords.items():
            grid_x = x - min_x
            grid_y = max_y - y  # Flip Y axis for display (top = higher Y)
            
            if (x, y) == current_room_coords:
                map_grid[grid_y][grid_x] = '|c@|n'  # Current location
            else:
                map_grid[grid_y][grid_x] = '|w#|n'  # Regular room
        
        # Add connections (basic implementation)
        self.add_connections_to_map(map_grid, room_coords, min_x, max_y)
        
        # Display the map
        self.caller.msg(f"|wMap of {area_info['name']} ({area_code}):|n\n")
        
        for row in map_grid:
            self.caller.msg(''.join(row))
        
        # Show room list
        self.caller.msg(f"\n|wRooms in {area_code}:|n")
        for (x, y), room_info in sorted(room_coords.items()):
            symbol = '@' if (x, y) == current_room_coords else '#'
            self.caller.msg(f"  {symbol} ({x:2},{y:2}) {room_info['code']}: {room_info['room'].name}")
        
        if rooms_without_coords:
            self.caller.msg(f"\n|yRooms without coordinates:|n")
            for room_info in rooms_without_coords:
                self.caller.msg(f"  ? {room_info['code']}: {room_info['room'].name}")
    
    def add_connections_to_map(self, map_grid, room_coords, min_x, max_y):
        """Add basic connections between adjacent rooms."""
        height = len(map_grid)
        width = len(map_grid[0]) if map_grid else 0
        
        # This is a simple implementation that shows connections between 
        # horizontally and vertically adjacent rooms
        for (x, y), room_info in room_coords.items():
            room_obj = room_info['room']
            grid_x = x - min_x
            grid_y = max_y - y
            
            # Check exits and see if they connect to adjacent coordinates
            for exit_obj in room_obj.exits:
                if not exit_obj.destination:
                    continue
                
                dest_coords = None
                for (dx, dy), dest_info in room_coords.items():
                    if dest_info['id'] == exit_obj.destination.id:
                        dest_coords = (dx, dy)
                        break
                
                if dest_coords:
                    dest_x, dest_y = dest_coords
                    dest_grid_x = dest_x - min_x
                    dest_grid_y = max_y - dest_y
                    
                    # Add connection lines for adjacent rooms
                    if abs(dest_grid_x - grid_x) == 1 and dest_grid_y == grid_y:
                        # Horizontal connection
                        conn_x = min(grid_x, dest_grid_x) + 1
                        if 0 <= conn_x < width and 0 <= grid_y < height:
                            if map_grid[grid_y][conn_x] == ' ':
                                map_grid[grid_y][conn_x] = '|y-|n'
                    elif abs(dest_grid_y - grid_y) == 1 and dest_grid_x == grid_x:
                        # Vertical connection
                        conn_y = min(grid_y, dest_grid_y) + 1
                        if 0 <= grid_x < width and 0 <= conn_y < height:
                            if map_grid[conn_y][grid_x] == ' ':
                                map_grid[conn_y][grid_x] = '|y||n'

