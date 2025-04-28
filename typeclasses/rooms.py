from evennia import DefaultRoom
from evennia.utils import evtable
from evennia.utils.ansi import ANSIString
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider
from evennia.utils import logger

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

# To use this custom room, you would typically put this code in a file like
# typeclasses/rooms.py in your Evennia game directory, then set it as the
# default room typeclass in your settings file or use it explicitly when
# creating rooms.