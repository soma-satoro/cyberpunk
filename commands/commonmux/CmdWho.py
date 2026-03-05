from datetime import datetime, timedelta
import pytz
import ephem
from evennia.utils.ansi import ANSIString
from evennia import default_cmds
from world.utils import ansi_utils
import time
from evennia import SESSION_HANDLER as evennia
from evennia.utils import utils
from world.utils.formatting import header, footer, divider
from evennia.utils.utils import class_from_module
from evennia.utils.ansi import strip_ansi
from django.conf import settings

COMMAND_DEFAULT_CLASS = class_from_module(settings.COMMAND_DEFAULT_CLASS)

class CmdWho(COMMAND_DEFAULT_CLASS):
    """
    list who is currently online, showing character names

    Usage:
      who
      doing

    Shows who is currently online using character names instead of account names.
    'doing' is an alias that limits info also for those with all permissions.
    """

    key = "who"
    aliases = ["doing"]
    locks = "cmd:all()"
    account_caller = False  # important for Account commands
    help_category = "Roleplaying Tools"

    def format_name(self, puppet, account):
        """Helper function to format character names consistently"""
        if puppet:
            # Get display name but strip any existing ANSI formatting
            display_name = puppet.get_display_name(account)
            clean_name = strip_ansi(display_name)
            
            # Add indicators using tags
            name_suffix = ""
            if puppet.check_permstring("builders"):
                name_suffix += f"*{name_suffix}"
            if puppet.tags.has("in_umbra", category="state"):
                name_suffix = f"@{name_suffix}"
            if puppet.db.lfrp:
                name_suffix = f"${name_suffix}"
            
            # For debugging
            # self.msg(f"Tags for {puppet.key}: {puppet.tags.all()}")
            
            # If no prefix, add a space to maintain alignment
            name_suffix = name_suffix or " "
            
            # Add the dbref
            name = f"{name_suffix}{clean_name}"
            return utils.crop(name, width=17)
        return "None".ljust(17)

    def get_location_display(self, puppet, account):
        """Helper function to format location display, respecting unfindable status"""
        if not puppet or not puppet.location:
            return "None"
            
        # Check if character is unfindable
        if hasattr(puppet, 'db') and puppet.db.unfindable and not account.check_permstring("Builder"):
            return "(Hidden)"
            
        # Staff can always see room names
        if account.check_permstring("Builder"):
            return puppet.location.key
            
        # Check if room is unfindable
        if hasattr(puppet.location, 'db') and puppet.location.db.unfindable:
            return "(Hidden)"
            
        return puppet.location.key

    def func(self):
        """
        Get all connected accounts by polling session.
        """
        account = self.account
        session_list = evennia.get_sessions()
        is_staff = account.check_permstring("builders")  # Check if viewer is staff

        session_list = sorted(session_list, key=lambda o: o.get_puppet().key if o.get_puppet() else o.account.key)

        if self.cmdstring == "doing":
            show_session_data = False
        else:
            show_session_data = account.check_permstring("Developer") or account.check_permstring(
                "Admins"
            )

        naccounts = evennia.account_count()
        if show_session_data:
            # privileged info
            string = header("Online Characters", width=78) + "\n"
            string += "|wName              On       Idle     Account     Room            Cmds  Host|n\n"
            string += divider(78) + "\n"
            
            for session in session_list:
                if not session.logged_in:
                    continue
                delta_cmd = time.time() - session.cmd_last_visible
                delta_conn = time.time() - session.conn_time
                session_account = session.get_account()
                puppet = session.get_puppet()
                
                # Skip if in dark mode (unless it's the viewer or both are staff)
                if puppet and puppet != self.caller:
                    is_dark = (session_account.tags.get("dark_mode", category="staff_status") or 
                             (puppet and puppet.tags.get("dark_mode", category="staff_status")))
                    target_is_staff = (session_account.tags.get("staff", category="role") or 
                                     (puppet and puppet.tags.get("staff", category="role")))
                    if is_dark and not (is_staff and target_is_staff):
                        continue
                
                location = self.get_location_display(puppet, account)
                
                string += " %-17s %-8s %-8s %-10s %-15s %-5s %s\n" % (
                    self.format_name(puppet, account),
                    utils.time_format(delta_conn, 0),
                    utils.time_format(delta_cmd, 1),
                    utils.crop(session_account.get_display_name(account), width=10),
                    utils.crop(location, width=15),
                    str(session.cmd_total).ljust(5),
                    isinstance(session.address, tuple) and session.address[0] or session.address
                )
        else:
            # unprivileged
            string = header("Online Characters", width=78) + "\n"
            string += "|wName              On       Idle     Room|n\n"
            string += divider(78) + "\n"
            
            for session in session_list:
                if not session.logged_in:
                    continue
                delta_cmd = time.time() - session.cmd_last_visible
                delta_conn = time.time() - session.conn_time
                puppet = session.get_puppet()
                session_account = session.get_account()
                
                # Skip if in dark mode (unless it's the viewer or both are staff)
                if puppet and puppet != self.caller:
                    is_dark = (session_account.tags.get("dark_mode", category="staff_status") or 
                             (puppet and puppet.tags.get("dark_mode", category="staff_status")))
                    target_is_staff = (session_account.tags.get("staff", category="role") or 
                                     (puppet and puppet.tags.get("staff", category="role")))
                    if is_dark and not (is_staff and target_is_staff):
                        continue
                
                location = self.get_location_display(puppet, account)
                
                string += " %-17s %-8s %-8s %s\n" % (
                    self.format_name(puppet, account),
                    utils.time_format(delta_conn, 0),
                    utils.time_format(delta_cmd, 1),
                    utils.crop(location, width=25)
                )

        is_one = naccounts == 1
        string += divider(78) + "\n"
        string += f"{naccounts} unique account{'s' if not is_one else ''} logged in.\n"
        string += divider(78) + "\n"
        string += "|yLegend: * = Staff, $ = Looking for RP, @ = In Hisil|n\n"
        string += divider(78) + "\n"
        string += footer(width=78)
        
        self.msg(string)

class CmdCensus(COMMAND_DEFAULT_CLASS):
    """
    Show a census of the current population in the game.
    +census will show a list of different templates and their counts.
    +census <template> will show a list of clans, orders, seemings, kiths, tribes, etc. from that template.
    +census <stat_category> <template> will show a list of how many players have a particular stat in a category from that template.

    Usage:
      +census
      +census <template>
      +census <stat_category>
    """
    key = "+census"
    aliases = ["census"]
    locks = "cmd:all()"
    help_category = "Roleplaying Tools"

    def format_counts(self, counts, title):
        """Format the counts into a nice table with either 2 or 3 columns based on content."""
        if not counts:
            return f"No {title} found."
            
        # Sort by count (descending) then name
        sorted_items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        
        # Calculate column widths
        name_width = max(len(str(name)) for name, _ in sorted_items)
        count_width = max(len(str(count)) for _, count in sorted_items)
        # Make sure we have minimum widths
        name_width = max(name_width, 10)
        count_width = max(count_width, 5)
        
        # Determine if we should use 2 or 3 columns based on the title
        use_two_columns = any(word.lower() in title.lower() for word in 
            ['vampire', 'mage', 'changeling', 'mortal+', 'hunter', 'demon', 'beast', 'deviant', 'promethean', 'werewolf', 'mortal']) or title.lower() == "mortal"
        
        # Calculate total width for each column (name + count + spacing)
        if use_two_columns:
            col_width = name_width + count_width + 2
        else:
            col_width = name_width + count_width + 2
        
        # Create the table
        table = [header(f"{title}", width=78)]
        
        # Split items into rows
        rows = []
        current_row = []
        max_cols = 2 if use_two_columns else 3
        
        for item in sorted_items:
            current_row.append(item)
            if len(current_row) == max_cols:
                rows.append(current_row)
                current_row = []
        
        # Add any remaining items
        if current_row:
            rows.append(current_row)
        
        # Format and add each row
        for row in rows:
            line = ""
            for i, (name, count) in enumerate(row):
                # Format each column with proper padding
                column = f"{str(name):<{name_width}} {count:>{count_width}}"
                # Add pipe after column unless it's the last column in the row
                if i < len(row) - 1:
                    line += f"{column} | "
                else:
                    # For last column in row, add pipe only if it's not a full row
                    line += f"{column}{' ' * (3 if len(row) == max_cols else 2) + ('|' if len(row) < max_cols else '')}"
            table.append(line.rstrip())
            
        # Add dividers
        table.insert(1, divider(78))
        table.append(divider(78))
        table.append(footer(width=78))
        
        return "\n".join(table)

    def func(self):
        """Execute the census command."""
        if not self.args:
            # Show overall population by template
            counts = self.get_template_counts()
            self.msg(self.format_counts(counts, "Character Types"))
            return
            
        args = self.args.strip().lower()
        
        # Check if it's a template-specific census
        template_mappings = {
            'vampire': 'Vampire',
            'mage': 'Mage', 
            'changeling': 'Changeling',
            'werewolf': 'Werewolf',
            'garou': 'Werewolf',
            'shifter': 'Werewolf',
            'mortal': 'Mortal',
            'mortal+': 'Mortal+',
            'hunter': 'Hunter'
        }
        
        if args in template_mappings:
            template = template_mappings[args]
            counts = self.get_template_subcounts(template)
            self.msg(self.format_counts(counts, f"{template} Population"))
            return
        
        # Check if it's a stat category
        stat_categories = ['attributes', 'skills', 'merits', 'advantages']
        if args in stat_categories:
            counts = self.get_stat_category_counts(args)
            self.msg(self.format_counts(counts, f"{args.title()} Distribution"))
            return
        
        # Check for groups census
        if args == 'groups':
            group_data = self.get_group_census()
            self.msg(self.format_counts(group_data['types'], "Group Types"))
            self.msg("\n" + self.format_counts(group_data['sizes'], "Group Sizes"))
            return
        
        # Invalid argument
        self.msg(f"Unknown census category '{args}'.")
        self.msg("Available options: vampire, mage, changeling, werewolf, mortal, mortal+, hunter, demon, beast, deviant, promethean, groups")
        self.msg("Or stat categories: attributes, skills, merits, advantages")

    def get_all_characters(self):
        """Get all approved characters in the game."""
        from typeclasses.characters import Character
        from evennia.utils.search import search_object
        
        all_chars = search_object("", typeclass=Character)
        # Filter to only approved characters with stats
        approved_chars = []
        for char in all_chars:
            if (hasattr(char, 'db') and 
                char.db.approved and 
                char.db.stats):
                approved_chars.append(char)
        
        return approved_chars

    def get_template_counts(self):
        """Get counts of characters by template."""
        characters = self.get_all_characters()
        counts = {}
        
        for char in characters:
            template = char.db.stats.get("other", {}).get("template", "Unknown")
            if template == "Unknown":
                template = "Mortal"  # Default fallback
            
            counts[template] = counts.get(template, 0) + 1
        
        return counts

    def get_template_subcounts(self, template):
        """Get subcounts for a specific template (clans, tribes, etc.)."""
        characters = self.get_all_characters()
        counts = {}
        
        # Template-specific field mappings - PRIMARY field comes first
        template_fields = {
            'Vampire': ['clan', 'covenant'],
            'Mage': ['path', 'order', 'legacy'],
            'Changeling': ['seeming', 'kith', 'court', 'entitlement'],
            'Werewolf': ['tribe', 'auspice', 'lodge'],
            'Hunter': ['compact', 'profession'],
            'Mortal': ['profession', 'organization'],
            'Mortal+': ['type', 'organization'],
            'Demon': ['incarnation', 'agenda', 'catalyst'],
            'Beast': ['family', 'hunger', 'horror'],
            'Deviant': ['origin', 'clade', 'scar'],
            'Promethean': ['lineage', 'refinement', 'creator'],
            'Geist': ['archetype', 'threshold']
        }
        
        fields_to_check = template_fields.get(template, ['clan', 'covenant', 'tribe', 'court', 'order'])
        
        for char in characters:
            char_template = char.db.stats.get("other", {}).get("template", "Unknown")
            if char_template != template:
                continue
                
            bio = char.db.stats.get("bio", {})
            
            # Try to build a meaningful category string from available fields
            # For most templates, we'll use the primary field (first in list)
            primary_field = fields_to_check[0] if fields_to_check else None
            
            if primary_field:
                value = bio.get(primary_field)
                
                # Check if value is valid
                if value and value != "<not set>" and str(value).strip():
                    # For some templates, combine multiple fields for better categorization
                    if template == 'Changeling' and len(fields_to_check) >= 3:
                        # For Changeling: Show "Seeming (Court)" format
                        seeming = bio.get('seeming', '')
                        court = bio.get('court', '')
                        
                        if seeming and seeming != "<not set>" and str(seeming).strip():
                            if court and court != "<not set>" and str(court).strip():
                                category_name = f"{seeming} ({court})"
                            else:
                                category_name = f"{seeming}"
                        else:
                            category_name = "Unspecified"
                    elif template == 'Vampire' and len(fields_to_check) >= 2:
                        # For Vampire: Show "Clan (Covenant)" format
                        clan = bio.get('clan', '')
                        covenant = bio.get('covenant', '')
                        
                        if clan and clan != "<not set>" and str(clan).strip():
                            if covenant and covenant != "<not set>" and str(covenant).strip():
                                category_name = f"{clan} ({covenant})"
                            else:
                                category_name = f"{clan}"
                        else:
                            category_name = "Unspecified"
                    elif template == 'Werewolf' and len(fields_to_check) >= 2:
                        # For Werewolf: Show "Tribe (Auspice)" format
                        tribe = bio.get('tribe', '')
                        auspice = bio.get('auspice', '')
                        
                        if tribe and tribe != "<not set>" and str(tribe).strip():
                            if auspice and auspice != "<not set>" and str(auspice).strip():
                                category_name = f"{tribe} ({auspice})"
                            else:
                                category_name = f"{tribe}"
                        else:
                            category_name = "Unspecified"
                    elif template == 'Mage' and len(fields_to_check) >= 2:
                        # For Mage: Show "Path (Order)" format
                        path = bio.get('path', '')
                        order = bio.get('order', '')
                        
                        if path and path != "<not set>" and str(path).strip():
                            if order and order != "<not set>" and str(order).strip():
                                category_name = f"{path} ({order})"
                            else:
                                category_name = f"{path}"
                        else:
                            category_name = "Unspecified"
                    else:
                        # Default: just use primary field with label
                        category_name = f"{value}"
                    
                    counts[category_name] = counts.get(category_name, 0) + 1
                else:
                    counts["Unspecified"] = counts.get("Unspecified", 0) + 1
            else:
                # No fields defined for this template
                counts["Unspecified"] = counts.get("Unspecified", 0) + 1
        
        return counts

    def get_stat_category_counts(self, category):
        """Get counts for a specific stat category."""
        characters = self.get_all_characters()
        counts = {}
        
        for char in characters:
            stats = char.db.stats.get(category, {})
            
            if category == "merits":
                # For merits, count each merit name
                for merit_name, merit_data in stats.items():
                    if isinstance(merit_data, dict) and merit_data.get("dots", 0) > 0:
                        display_name = f"{merit_name.replace('_', ' ').title()}"
                        counts[display_name] = counts.get(display_name, 0) + 1
            else:
                # For other categories, count stat names and their values
                for stat_name, value in stats.items():
                    if value and value > 0:  # Only count stats with positive values
                        display_name = f"{stat_name.replace('_', ' ').title()}"
                        if display_name not in counts:
                            counts[display_name] = 0
                        counts[display_name] += 1
        
        return counts

    def get_group_census(self):
        """Get census information about groups."""
        from typeclasses.groups import get_all_groups
        
        groups = get_all_groups()
        
        # Count by group type
        type_counts = {}
        member_counts = {}
        
        for group in groups:
            group_type = group.get_group_type_display()
            type_counts[group_type] = type_counts.get(group_type, 0) + 1
            
            member_count = group.get_member_count()
            if member_count > 0:
                range_key = self.get_member_count_range(member_count)
                member_counts[range_key] = member_counts.get(range_key, 0) + 1
        
        return {
            'types': type_counts,
            'sizes': member_counts
        }

    def get_member_count_range(self, count):
        """Get a range description for member count."""
        if count == 1:
            return "1 member"
        elif count <= 3:
            return "2-3 members"
        elif count <= 5:
            return "4-5 members"
        elif count <= 10:
            return "6-10 members"
        else:
            return "10+ members"
