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
from world.factions import faction, faction_list

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
    help_category = "Game Info"

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
            if puppet.db.lfrp:
                name_suffix = f"${name_suffix}"
            
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
        if hasattr(puppet, 'db') and puppet.db.unfindable and not account.check_permstring("builders", "admin", "staff", "developer"):
            return "(Hidden)"
            
        # Staff can always see room names
        if account.check_permstring("builders", "admin", "staff", "developer"):
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
        is_staff = account.check_permstring("builders", "admin", "staff", "developer")  # Check if viewer is staff

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
            string += "|r" + "-" * 78 + "|n\n"
            
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
            string += "|r" + "-" * 78 + "|n\n"
            
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
        string += "|r" + "-" * 78 + "|n\n"
        string += f"{naccounts} unique account{'s' if not is_one else ''} logged in.\n"
        string += "|r" + "-" * 78 + "|n\n"
        string += "|yLegend: * = Staff, $ = Looking for RP, @ = In Umbra|n\n"  # Fixed legend formatting
        string += "|r" + "-" * 78 + "|n\n"
        string += footer(width=78)
        
        self.msg(string)

class CmdCensus(COMMAND_DEFAULT_CLASS):
    """
    Show a census of the current population in the game.
    +census will show a list of different splats and their counts.
    +census/<splat> will show a list of clans, traditions, tribes, etc. from that splat.
    +census/<stat_category> will show a list of how many players have a particular stat in a category.

    Usage:
      +census      - Shows a list of players by role.     
      +census/gang - Shows a list of gangs and their player counts.
      +census/zoner - Shows a list of zoners and their player counts.
      +census/corporate - Shows a list of corporations and their player counts.
      +census/street - Shows a list of street gangs and their player counts.
      +census/nomad - Shows a list of nomads and their player counts.
    """
    key = "+census"
    aliases = ["census"]
    locks = "cmd:all()"
    help_category = "Game Info"

    def get_faction_counts(self):
        """Get counts of approved characters by splat type."""
        from evennia.objects.models import ObjectDB
        from collections import defaultdict
        
        VALID_FACTIONS = {
            'gang': 'Gang',
            'zoner': 'Zoner',
            'corporate': 'Corporate',
            'street': 'Street',
            'nomad': 'Nomad',
            'other': 'Other',
        }
        
        faction_counts = defaultdict(int)
        characters = ObjectDB.objects.filter(
            db_typeclass_path__contains='typeclasses.characters.Character'
        )
        
        for char in characters:
            if not hasattr(char, 'db') or not char.db.stats or not char.db.approved:
                continue
                
            splat = char.db.stats.get('other', {}).get('splat', {}).get('Splat', {}).get('perm', '')
            if not splat or splat.lower() in ['none', 'unknown']:
                continue
                
            normalized_faction = VALID_FACTIONS.get(faction.lower(), faction)
            faction_counts[normalized_faction] += 1
                
        return dict(faction_counts)

