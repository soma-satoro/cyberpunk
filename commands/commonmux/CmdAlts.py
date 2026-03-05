from evennia import default_cmds
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.search import search_object
from evennia.utils import logger
import uuid
from time import time
from world.utils.formatting import footer
from utils.search_helpers import search_character

class CmdAlts(MuxCommand):
    """
    Manage character alts.
    
    Usage:
      +alts                     - Show your list of alts
      +alts <name>              - Show the public alts of a character
      +alts/add <name>          - Request to add a character as your alt
      +alts/confirm <code>      - Confirm an alt request using the code
      +alts/del <name>          - Remove a character from your list of alts
      +alts/pending             - List all your pending alt requests
    
    The +alts command allows you to manage which characters are publicly 
    linked to your character. When you request to add someone as an alt,
    they receive a confirmation code via mail. Both parties must agree 
    to be linked as alts.
    """
    
    key = "+alts"
    aliases = ["alts"]
    locks = "cmd:all()"
    help_category = "Chargen & Character Info"
    
    def func(self):
        """Implement the command functionality."""
        caller = self.caller
        
        # No arguments, show the caller's alts
        if not self.args and not self.switches:
            self.list_own_alts()
            return
            
        # Check for /add switch
        if "add" in self.switches:
            self.add_alt()
            return
            
        # Check for /confirm switch
        if "confirm" in self.switches:
            self.confirm_alt()
            return
            
        # Check for /del switch
        if "del" in self.switches:
            self.remove_alt()
            return
            
        # Check for /pending switch
        if "pending" in self.switches:
            self.list_pending_requests()
            return
            
        # If we have args but no switches, show the public alts of the target
        if self.args and not self.switches:
            self.list_public_alts()
            return
    
    def list_own_alts(self):
        """List the caller's own alts."""
        caller = self.caller
        alts = caller.db.public_alts or []
        
        # Build the display
        msg = footer(78, char="=") + "\n"
        msg += f"|w {caller.name}'s Alts|n\n"
        msg += footer(78, char="=") + "\n"
        
        if not alts:
            msg += "You have not declared any alt characters.\n"
        else:
            for alt_name in alts:
                msg += f"  • {alt_name}\n"
        
        # Check for pending requests
        pending_requests = caller.db.pending_alt_requests or {}
        if pending_requests:
            msg += f"\n|yYou have pending alt requests. Use |w+alts/pending|y to view them.|n\n"
        
        msg += f"\n|xUse |w+alts/add <name>|x to request to add an alt.|n"
        caller.msg(msg)
    
    def list_public_alts(self):
        """List another character's public alts."""
        caller = self.caller
        
        # Find the target character
        target = search_character(self.caller, self.args.strip())
        if not target:
            return
        alts = target.db.public_alts or []
        
        # Build the display
        msg = footer(78, char="=") + "\n"
        msg += f"|w {target.name}'s Public Alts|n\n"
        msg += footer(78, char="=") + "\n"
        
        if not alts:
            msg += f"{target.name} has not declared any alt characters."
        else:
            for alt_name in alts:
                msg += f"  • {alt_name}\n"
        
        caller.msg(msg)
    
    def add_alt(self):
        """Request to add a character as an alt."""
        caller = self.caller
        
        if not self.args:
            caller.msg("Usage: +alts/add <character name>")
            return
        
        # Find the target character
        target = search_character(self.caller, self.args.strip())
        if not target:
            return
        
        # Don't add yourself as an alt
        if target == caller:
            caller.msg("You can't add yourself as an alt.")
            return
        
        # Check if already listed
        caller_alts = caller.db.public_alts or []
        if target.name in caller_alts:
            caller.msg(f"{target.name} is already listed as your alt.")
            return
        
        # Generate confirmation code
        confirmation_code = str(uuid.uuid4())[:8].upper()
        
        # Create pending request
        pending_request = {
            'requester': caller.name,
            'code': confirmation_code,
            'timestamp': time()
        }
        
        # Store pending request on target
        target_pending = target.db.pending_alt_requests or {}
        target_pending[caller.name] = pending_request
        target.db.pending_alt_requests = target_pending
        
        # Send mail to target
        if target.account:
            subject = f"Alt Confirmation Request from {caller.name}"
            message = f"{caller.name} has requested to add you as their alt character.\n\n"
            message += f"To approve: |w+alts/confirm {confirmation_code}|n\n\n"
            message += "You can ignore this message if you do not wish to be listed as their alt."
            
            mail_cmd = f"@mail {target.account.username}={subject}/{message}"
            caller.execute_cmd(mail_cmd)
            
            # Notify target if online
            if target.sessions.all():
                target.msg(f"|yYou have received an alt request from {caller.name}. Check your mail for the confirmation code.|n")
            
            caller.msg(f"Alt request sent to {target.name}. They will receive a confirmation code via mail.")
        else:
            caller.msg(f"Error: {target.name} doesn't have a player account.")
            
    def confirm_alt(self):
        """Confirm an alt request using the code."""
        caller = self.caller
        
        if not self.args:
            caller.msg("Usage: +alts/confirm <code>")
            return
        
        # Get pending requests
        pending_requests = caller.db.pending_alt_requests or {}
        if not pending_requests:
            caller.msg("You have no pending alt requests to confirm.")
            return
        
        # Find matching confirmation code
        confirmation_code = self.args.strip().upper()
        requester_name = None
        
        for name, req in pending_requests.items():
            if req.get('code', '').upper() == confirmation_code:
                requester_name = name
                break
        
        if not requester_name:
            caller.msg(f"Invalid confirmation code. Use |w+alts/pending|n to see your pending requests.")
            return
        
        # Find requester character
        requester = search_character(self.caller, requester_name, quiet=True)
        if not requester:
            caller.msg(f"Error: Could not find character '{requester_name}'.")
            # Clean up the invalid request
            del pending_requests[requester_name]
            caller.db.pending_alt_requests = pending_requests
            return
        
        # Add both characters to each other's alt lists
        caller_alts = caller.db.public_alts or []
        if requester.name not in caller_alts:
            caller_alts.append(requester.name)
            caller.db.public_alts = caller_alts
        
        requester_alts = requester.db.public_alts or []
        if caller.name not in requester_alts:
            requester_alts.append(caller.name)
            requester.db.public_alts = requester_alts
        
        # Clean up pending request
        del pending_requests[requester_name]
        caller.db.pending_alt_requests = pending_requests
        
        # Notify both parties
        caller.msg(f"|gYou have confirmed {requester.name} as your alt. You are now linked.|n")
        if requester.sessions.all():
            requester.msg(f"|g{caller.name} has confirmed your alt request. You are now linked.|n")
    
    def list_pending_requests(self):
        """List pending alt requests."""
        caller = self.caller
        pending_requests = caller.db.pending_alt_requests or {}
        
        if not pending_requests:
            caller.msg("You have no pending alt requests.")
            return
        
        # Build the display
        msg = footer(78, char="=") + "\n"
        msg += f"|w Pending Alt Requests|n\n"
        msg += footer(78, char="=") + "\n"
        
        for requester, request in pending_requests.items():
            code = request.get('code', 'NO_CODE')
            timestamp = request.get('timestamp', time())
            time_ago = int((time() - timestamp) / 86400)  # Days
            
            if time_ago == 0:
                time_str = "today"
            elif time_ago == 1:
                time_str = "yesterday"
            else:
                time_str = f"{time_ago} days ago"
            
            msg += f"  • {requester} (requested {time_str})\n"
            msg += f"    Code: |w{code}|n\n"
        
        msg += f"\n|xUse |w+alts/confirm <code>|x to approve a request.|n"
        caller.msg(msg)
    
    def remove_alt(self):
        """Remove a character from your list of alts."""
        caller = self.caller
        
        if not self.args:
            caller.msg("Usage: +alts/del <character name>")
            return
        
        # Get the list of alts
        alts = caller.db.public_alts or []
        
        # Check if the character is in the list
        if self.args not in alts:
            caller.msg(f"{self.args} is not listed as your alt.")
            return
        
        # Remove the character from the caller's alts
        alts.remove(self.args)
        caller.db.public_alts = alts
        
        # Try to find the target character to remove the two-way relationship
        target = search_character(self.caller, self.args, quiet=True)
        if target:
            target_alts = target.db.public_alts or []
            
            if caller.name in target_alts:
                target_alts.remove(caller.name)
                target.db.public_alts = target_alts
                
                # Notify them if online
                if target.sessions.all():
                    target.msg(f"{caller.name} has removed you from their list of alts.")
        
        caller.msg(f"Removed {self.args} from your list of alts.")

