from evennia import DefaultRoom
from evennia.utils import delay
from evennia.utils.ansi import ANSIString
from world.utils.calculation_utils import get_remaining_points
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider, footer_with_right_text
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
        Use character typeclass (source of truth for Edgerunner) when available;
        fall back to sheet for Complete Package / legacy.
        """
        if not hasattr(character, 'character_sheet'):
            return None, None

        # Character typeclass has the actual stats/skills for Edgerunner;
        # sheet can be stale. Prefer character.get_remaining_points().
        if hasattr(character, 'get_remaining_points'):
            try:
                return character.get_remaining_points()
            except Exception:
                pass
        return character.character_sheet.get_remaining_points()

    def update_remaining_points(self, character):
        """
        Update points display for the character who made changes.
        Called by commands that modify stats/skills - sends private message only, no room broadcast.
        """
        self.display_points(character)

    def display_points(self, character):
        """
        Display the remaining stat and skill points for a character.
        """
        if not hasattr(character, 'character_sheet') or not character.character_sheet:
            character.msg("You don't have a character sheet. Please contact an admin.")
            return

        remaining_stat_points, remaining_skill_points = self.get_remaining_points(character)
        if remaining_stat_points is not None and remaining_skill_points is not None:
            character.msg(f"|wRemaining Points:|n Stat Points: |g{remaining_stat_points}|n, Skill Points: |g{remaining_skill_points}|n")

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
        
        # Ensure the character sheet exists (use pk to avoid "Model instances must be saved" error)
        if not hasattr(looker, 'character_sheet') or looker.character_sheet is None:
            from world.cyberpunk_sheets.models import CharacterSheet
            looker_pk = getattr(looker, 'pk', None) or getattr(looker, 'id', None)
            if looker_pk is not None:
                defaults = {}
                if hasattr(looker, 'account') and looker.account:
                    defaults['account_id'] = looker.account.id
                sheet, created = CharacterSheet.objects.get_or_create(
                    character_id=looker_pk,
                    defaults=defaults
                )
                looker.db.character_sheet_id = sheet.id

        # Now it's safe to refresh the character sheet
        if looker.character_sheet:
            looker.character_sheet.refresh_from_db()

        name = self.get_display_name(looker, **kwargs)
        desc = self.db.desc

        # Header with room name
        string = header(name, width=78, bcolor="|m", fillchar=ANSIString("|m-|n")) + "\n"
        
        # Add remaining points and fashion budget for the looker
        if inherits_from(looker, "typeclasses.characters.Character"):
            # Force a refresh of the character sheet
            if hasattr(looker, 'character_sheet'):
                looker.character_sheet.refresh_from_db()
            
            remaining_stat_points, remaining_skill_points = self.get_remaining_points(looker)
            if remaining_stat_points is not None and remaining_skill_points is not None:
                points_info = f"|wRemaining Points:|n Stat Points: |g{remaining_stat_points}|n, Skill Points: |g{remaining_skill_points}|n"
                # Add fashion budget (use-it-or-lose-it for clothing in chargen)
                fashion_budget = getattr(looker.character_sheet, 'fashion_budget_remaining', 0)
                if fashion_budget is not None and fashion_budget > 0:
                    points_info += f", Fashion Budget: |g{fashion_budget}|n eb"
                points_info += "\n"
                string += points_info + "\n"

        # Process room description
        if desc:
            paragraphs = desc.split('%r')
            formatted_paragraphs = []
            for i, p in enumerate(paragraphs):
                if not p.strip():
                    formatted_paragraphs.append('')  # Add blank line for empty paragraph
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
            for obj in objects:
                string += f" {obj.get_display_name(looker)}\n"

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

        # Resource descriptor in lower right (Cyberpunk standard)
        from world.cyberpunk_constants import resource_level_to_descriptor
        res_level = self.db.resources if self.db.resources is not None else None
        res_desc = resource_level_to_descriptor(res_level)
        res_str = f"[Res: {res_desc}]" if res_desc != "Not set" else ""
        string += footer_with_right_text(width=78, right_text=res_str, fillchar="-", color="|m")

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
                return False
        return True

    def check_stats_complete(self, character):
        """
        Check if chargen can be finished. Stats may be 0 (players can clear them).
        Required skills must be >= 2: Athletics, Brawling, Concentration, Conversation,
        Education, Evasion, First Aid, Human Perception, Language (Streetslang),
        Local Expert (Instance), Perception, Persuasion, Stealth.
        """
        if not hasattr(character, 'character_sheet') or not character.character_sheet:
            character.msg("You don't have a character sheet. Please contact an admin.")
            return False
        cs = character.character_sheet
        from world.chargen_constants import CHARGEN_REQUIRED_SKILLS, CHARGEN_REQUIRED_SKILL_MIN

        # Stats: all must be set (>= 0 is valid; prefer character.db, fallback to sheet)
        required_stats = ['intelligence', 'reflexes', 'dexterity', 'technique', 'cool',
                         'willpower', 'luck', 'move', 'body', 'empathy']
        try:
            for stat in required_stats:
                val = getattr(character.db, stat, None)
                if val is None:
                    val = getattr(cs, stat, None)
                if val is None:
                    character.msg("You must set all stats before leaving. Use 'selfstat' to allocate.")
                    return False
        except AttributeError:
            logger.error(f"AttributeError in check_stats_complete for {character}")
            return False

        # Required skills must be >= 2
        missing = []
        for skill_key in CHARGEN_REQUIRED_SKILLS:
            if skill_key == "local_expert":
                # Local Expert (Instance): need at least one instance >= 2
                instances = character.db.skill_instances or {}
                max_le = 0
                for key, val in instances.items():
                    if key.startswith("local_expert("):
                        max_le = max(max_le, int(val) if val is not None else 0)
                if max_le < CHARGEN_REQUIRED_SKILL_MIN:
                    missing.append("Local Expert (Instance)")
            else:
                val = character.get_skill(skill_key) if hasattr(character, 'get_skill') else 0
                val = val or 0
                if val < CHARGEN_REQUIRED_SKILL_MIN:
                    display = skill_key.replace('_', ' ').title()
                    if skill_key == "human_perception":
                        display = "Human Perception"
                    missing.append(display)

        # Language (Streetslang) >= 2
        streetslang = character.get_language_level("Streetslang") if hasattr(character, 'get_language_level') else 0
        if (streetslang or 0) < CHARGEN_REQUIRED_SKILL_MIN:
            missing.append("Language (Streetslang)")

        if missing:
            character.msg(
                f"The following skills must be at least {CHARGEN_REQUIRED_SKILL_MIN} to finish chargen: "
                f"{', '.join(missing)}. Use 'selfstat' to set them."
            )
            return False
        return True
        
        
# To use this custom room, you would typically put this code in a file like
# typeclasses/rooms.py in your Evennia game directory, then set it as the
# default room typeclass in your settings file or use it explicitly when
# creating rooms.
