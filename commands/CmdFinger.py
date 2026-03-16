from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import utils
from evennia import SESSION_HANDLER
from world.utils.search_helpers import search_character
from evennia.utils.ansi import ANSIString
import time


class CmdFinger(MuxCommand):
    """
    Display OOC information about a character.
    
    Usage:
      +finger <name>
      +finger me
      +finger/set <attribute>=<value>
    
    Examples:
      +finger Melvin
      +finger me
      +finger/set fame=Princess Angelina Contessa Louisa Francesca Banana Fanna Bobesca the Third
      +finger/set email=myemail@example.com
      +finger/set rp-prefs=Whatever goes!
    
    This command shows various OOC information about a character. +finger is
    generally a command that displays OOC information and should not be 
    considered IC unless game policy specifically says otherwise.
    
    Available attributes that can be set with /set:
      EMAIL         - Your email address (optional)
      POSITION      - Your Position
      AGE           - Your real age
      FAME          - What you are known for
      APP-AGE       - Your apparent age
      PLAN          - Any plans your character may have
      RP-PREFS      - Any RP preferences that you may have as a person
      ALTS          - Alternate characters (auto-populated, see +alts command)
      THEMESONG     - Your Theme Song
      QUOTE         - A typical quote from your character
      OFF-HOURS     - When you are usually online
      TEMPERAMENT   - Your character's temperament
      VACATION      - The dates you expect to be gone
      URL           - Your homepage, if any
    """
    
    key = "+finger"
    aliases = ["finger"]
    locks = "cmd:all()"
    help_category = "Chargen & Character Info"
    
    # Valid finger attributes
    VALID_ATTRIBUTES = [
        "email", "position", "age", "fame", "app-age", "plan",
        "rp-prefs", "themesong", "quote", "off-hours", 
        "temperament", "vacation", "url"
    ]
    
    # Attribute display names
    ATTRIBUTE_LABELS = {
        "email": "E-Mail",
        "position": "Position",
        "age": "Age",
        "fame": "Fame",
        "app-age": "App-Age",
        "plan": "Plan",
        "rp-prefs": "RP-Prefs",
        "themesong": "Themesong",
        "quote": "Quote",
        "off-hours": "Off-Hours",
        "temperament": "Temperament",
        "vacation": "Vacation",
        "url": "URL"
    }
    
    def func(self):
        """Execute the finger command."""
        
        # Handle /set switch
        if "set" in self.switches:
            self.set_finger_attribute()
            return
        
        # Handle display
        if not self.args:
            self.caller.msg("Usage: +finger <name> or +finger me")
            return
        
        # Determine target
        if self.args.strip().lower() == "me":
            target = self.caller
        else:
            target = search_character(self.caller, self.args.strip())
            if not target:
                return
        
        # Display finger information
        self.display_finger(target)
    
    def set_finger_attribute(self):
        """Set a finger attribute for the caller."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +finger/set <attribute>=<value>")
            self.caller.msg(f"Valid attributes: {', '.join(self.VALID_ATTRIBUTES)}")
            return
        
        # Parse the attribute and value
        attr_name, value = self.args.split("=", 1)
        attr_name = attr_name.strip().lower()
        value = value.strip()
        
        # Validate attribute name
        if attr_name not in self.VALID_ATTRIBUTES:
            self.caller.msg(f"Invalid attribute '{attr_name}'.")
            self.caller.msg(f"Valid attributes: {', '.join(self.VALID_ATTRIBUTES)}")
            return
        
        # Special handling for email - can be set to "unlisted"
        if attr_name == "email" and value.lower() == "unlisted":
            value = "(unlisted)"
        
        # Store the attribute
        finger_data = self.caller.attributes.get("finger_data", default={})
        finger_data[attr_name] = value
        self.caller.attributes.add("finger_data", finger_data)
        
        display_name = self.ATTRIBUTE_LABELS.get(attr_name, attr_name.title())
        self.caller.msg(f"Your {display_name} has been set to: {value}")
    
    def get_session_info(self, target):
        """Get session information for a character."""
        # Get all sessions and find the one for this character
        all_sessions = SESSION_HANDLER.get_sessions()
        
        target_session = None
        for session in all_sessions:
            if session.logged_in and session.get_puppet() == target:
                target_session = session
                break
        
        if not target_session:
            return None, None, False
        
        # Calculate connection time and idle time
        delta_conn = time.time() - target_session.conn_time
        delta_idle = time.time() - target_session.cmd_last_visible
        
        on_time = utils.time_format(delta_conn, 0)
        idle_time = utils.time_format(delta_idle, 1)
        
        return on_time, idle_time, True
    
    def get_mail_info(self, target):
        """Get mail information for a character."""
        # Try to get unread mail count
        try:
            if hasattr(target, 'account') and target.account:
                unread = 0
                total = 0
                
                # Check if mail system is available
                from evennia.contrib.game_systems.mail.mail import MailDB
                
                # Get all mail for this account
                mails = MailDB.objects.get_all_mail(target.account)
                total = len(mails)
                unread = sum(1 for m in mails if not m.db_date_read)
                
                return f"{unread} unread / {total} total"
        except:
            pass
        
        return "N/A"
    
    def escape_ansi(self, text):
        """Escape ANSI codes by doubling pipe characters."""
        if text:
            return str(text).replace('|', '||')
        return text
    
    def display_finger(self, target):
        """Display finger information for a target."""
        # Get finger data
        finger_data = target.attributes.get("finger_data", default={})
        
        # Get session info
        on_time, idle_time, is_online = self.get_session_info(target)
        
        # Get mail info
        mail_info = self.get_mail_info(target)
        
        # Get alias
        alias = target.attributes.get("alias", None)
        
        # Get sex/gender
        sex = finger_data.get("sex", "None Set")
        
        # Get location
        location = "Unknown"
        if target.location:
            # Escape ANSI codes in location name
            location = self.escape_ansi(target.location.key)
        
        # Get alts (from the +alts system)
        alts = target.db.public_alts or []
        alts_display = ", ".join(alts) if alts else "None listed"
        
        # Build the display (blue/yellow/white color scheme)
        output = []
        
        # Header with character name (escape ANSI) - blue borders, yellow name
        name_clean = self.escape_ansi(target.name)
        if len(name_clean) > 40:
            name_clean = name_clean[:37] + "..."
        name_part = f"[ {name_clean} ]"
        header_line = f"|b<---======##======================|n|y{name_part}|n|b======================##======--->|n"
        output.append(header_line)
        
        # First info section
        left_col = []
        right_col = []
        
        # Left column - labels in yellow, values in white
        left_col.append(f"|yAlias:|n {self.escape_ansi(alias) if alias else 'None'}")
        left_col.append(f"|ySex:|n {self.escape_ansi(sex)}")
        
        email = self.escape_ansi(finger_data.get("email", "(unlisted)"))
        left_col.append(f"|yE-Mail:|n {email}")
        
        # Right column
        if is_online:
            right_col.append(f"|yOn for:|n {on_time}          |yIdle:|n {idle_time}")
        else:
            right_col.append("|wNot currently online|n")
        
        right_col.append(f"|yMail:|n {mail_info}")
        
        # Combine columns (use || for literal pipe - single | triggers ANSI when followed by M, O, etc.)
        max_lines = max(len(left_col), len(right_col))
        for i in range(max_lines):
            left = left_col[i] if i < len(left_col) else ""
            right = right_col[i] if i < len(right_col) else ""
            
            # Calculate visible length (without ANSI codes)
            left_visible_len = len(ANSIString(left).clean())
            right_visible_len = len(ANSIString(right).clean())
            
            # Add padding based on visible length
            left_padded = left + " " * (38 - left_visible_len)
            right_padded = right + " " * (39 - right_visible_len)
            
            # Combine with separator (|| = literal pipe to avoid |M, |O etc. being interpreted as ANSI)
            line = f"{left_padded}||{right_padded}"
            output.append(line)
        
        # Divider - blue
        output.append("|b<-------------=============++++++++++++++++++++++++=============------------>|n")
        
        # Location and RP-Prefs
        if target.location:
            output.append(f"|yLocation:|n       {location}")
        
        rp_prefs = finger_data.get("rp-prefs", None)
        if rp_prefs:
            output.append(f"|yRP-Prefs:|n       {self.escape_ansi(rp_prefs)}")
        
        # Other finger attributes
        display_attrs = [
            ("position", "Position"),
            ("age", "Age"),
            ("app-age", "Apparent Age"),
            ("fame", "Fame"),
            ("plan", "Plan"),
            ("themesong", "Themesong"),
            ("quote", "Quote"),
            ("off-hours", "Off-Hours"),
            ("temperament", "Temperament"),
            ("vacation", "Vacation"),
            ("url", "URL")
        ]
        
        for attr_key, attr_label in display_attrs:
            value = finger_data.get(attr_key, None)
            if value:
                output.append(f"|y{attr_label + ':':<16}|n{self.escape_ansi(value)}")
        
        # Alts section
        if alts:
            output.append(f"|yAlts:|n           {self.escape_ansi(alts_display)}")
        
        # Bottom divider - blue
        output.append("|b<-------------=============++++++++++++++++++++++++=============------------>|n")
        
        # Send the output
        self.caller.msg("\n".join(output))

