from evennia import DefaultRoom
from evennia.utils import delay
from evennia.utils.ansi import ANSIString
from world.utils.calculation_utils import get_remaining_points
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider
from world.cyberpunk_constants import STATS, ROLE_SKILLS
from evennia.utils.utils import inherits_from
import logging

logger = logging.getLogger('cyberpunk.chargen')

class ChargenRoom(DefaultRoom):
    """
    This room class is used for character generation. It allows the use of the
    `setstat` command and returns players to this room if they try to leave before
    character creation is complete.
    """

    def get_remaining_points(self, character):
        """
        Calculate and return the remaining stat and skill points for the character.
        """
        if not hasattr(character, 'character_sheet'):
            return None, None

        return character.character_sheet.get_remaining_points()

    def update_remaining_points(self, character):
        remaining_stat_points, remaining_skill_points = self.get_remaining_points(character)
        self.db.remaining_points = {
            "stat_points": remaining_stat_points,
            "skill_points": remaining_skill_points
        }
        self.msg_contents(f"{character.name} has updated their stats. Remaining points have been updated.")

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
        """
        This is called when a looker looks at this object.
        """
        if not looker:
            return ""
        
        # Ensure the character sheet exists
        if not hasattr(looker, 'character_sheet') or looker.character_sheet is None:
            from world.cyberpunk_sheets.models import CharacterSheet
            sheet, created = CharacterSheet.objects.get_or_create(character=looker)
            looker.db.character_sheet_id = sheet.id

        # Now it's safe to refresh the character sheet
        if looker.character_sheet:
            looker.character_sheet.refresh_from_db()

        name = self.get_display_name(looker, **kwargs)
        desc = self.db.desc

        # Header with room name
        string = header(name, width=78, bcolor="|m", fillchar=ANSIString("|m-|n")) + "\n"
        
        # Add remaining points information for the looker
        if inherits_from(looker, "typeclasses.characters.Character"):
            # Force a refresh of the character sheet
            if hasattr(looker, 'character_sheet'):
                looker.character_sheet.refresh_from_db()
            
            remaining_stat_points, remaining_skill_points = self.get_remaining_points(looker)
            if remaining_stat_points is not None and remaining_skill_points is not None:
                points_info = f"|wRemaining Points:|n Stat Points: |g{remaining_stat_points}|n, Skill Points: |g{remaining_skill_points}|n\n"
                string += points_info + "\n"

        # Optional: add custom room description here if available
        if desc:
            string += wrap_ansi(desc, 78, left_padding=1) + "\n\n"

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
            for obj in objects:
                string += f" {obj.get_display_name(looker)}\n"

        # List all exits
        exits = [obj for obj in self.contents if obj.destination]
        if exits:
            string += divider("Exits", width=78, fillchar=ANSIString("|m-|n")) + "\n"
            for exit in exits:
                string += f" {exit.get_display_name(looker)}\n"

        string += footer(width=78, fillchar=ANSIString("|m-|n"))

        return string

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

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        """
        When an object enters the room.
        """
        if moved_obj.has_account:
            moved_obj.msg("Welcome to the character generation room. Use the 'setstat' command to set your character's stats.")
            moved_obj.msg("You must set all your stats before leaving this room.")

    def at_object_leave(self, moved_obj, target_location, **kwargs):
        """
        When an object tries to leave the room.
        """
        if moved_obj.has_account:
            if not self.check_stats_complete(moved_obj):
                moved_obj.msg("You must set all your stats before leaving this room.")
                return False
        return True

    def check_stats_complete(self, character):
        """
        Check if all necessary stats have been set.
        """
        if not hasattr(character, 'character_sheet'):
            return False
        cs = character.character_sheet
        required_stats = ['intelligence', 'reflexes', 'dexterity', 'technology', 'cool', 
                        'willpower', 'luck', 'move', 'body', 'empathy']
        try:
            return all(getattr(cs, stat, 0) > 0 for stat in required_stats)
        except AttributeError:
            # Log the error and return False if any attribute is missing
            logger.error(f"AttributeError in is_character_complete for {character}") # type: ignore
            return False
        
        
# To use this custom room, you would typically put this code in a file like
# typeclasses/rooms.py in your Evennia game directory, then set it as the
# default room typeclass in your settings file or use it explicitly when
# creating rooms.
