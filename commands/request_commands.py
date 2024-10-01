# in mygame/commands/request_commands.py

from evennia import Command
from evennia.utils.evtable import EvTable
from evennia.utils.utils import crop
from django.conf import settings
from world.requests.models import Request, Comment
from itertools import cycle
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.utils import crop
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider
from evennia.utils.ansi import ANSIString


class CmdRequests(MuxCommand):
    """
    View and manage requests

    Usage:
      request
      request <#>
      request/create <category>/<title>=<text>
      request/comment <#>=<text>
      request/cancel <#>
      request/addplayer <#>=<player>

    Switches:
      create - Create a new request
      comment - Add a comment to a request
      cancel - Cancel one of your requests
      addplayer - Add another player to your request
    """
    key = "+request"
    aliases = ["+requests", "+myjob", "+myjobs"]
    help_category = "Requests"

    def func(self):
        if not self.args and not self.switches:
            self.list_requests()
        elif self.args and not self.switches:
            self.view_request()
        elif "create" in self.switches:
            self.create_request()
        elif "comment" in self.switches:
            self.add_comment()
        elif "cancel" in self.switches:
            self.cancel_request()
        elif "addplayer" in self.switches:
            self.add_player()
        else:
            self.caller.msg("Invalid switch. See help +request for usage.")

    def list_requests(self):
        requests = Request.objects.filter(requester=self.caller.account)
        if not requests:
            self.caller.msg("You have no open requests.")
            return

        output = header("Night City MUSH Jobs", width=78, fillchar="|m-|n") + "\n"
        
        # Create the header row
        header_row = "|cReq #  Category   Request Title              Started  Handler           Status|n"
        output += header_row + "\n"
        output += ANSIString("|m" + "-" * 78 + "|n") + "\n"

        # Add each request as a row
        for req in requests:
            handler = req.handler.username if req.handler else "-----"
            row = (
                f"{req.id:<6}"
                f"{req.category:<11}"
                f"{crop(req.title, width=25):<25}"
                f"{req.date_created.strftime('%m/%d/%y'):<9}"
                f"{handler:<18}"
                f"{req.status}"
            )
            output += row + "\n"

        output += ANSIString("|m" + "-" * 78 + "|n") + "\n"
        output += divider("End Requests", width=78, fillchar="|m-=|n")
        self.caller.msg(output)

    def view_request(self):
        try:
            req_id = int(self.args)
            request = Request.objects.get(id=req_id, requester=self.caller.account)
        except (ValueError, Request.DoesNotExist):
            self.caller.msg("Request not found.")
            return

        output = header(f"Job {request.id}", width=78, fillchar="|m-|n") + "\n"
        output += f"|cJob Title:|n {request.title}\n"
        output += f"|cCategory:|n {request.category:<15} |cStatus:|n {request.status}\n"
        output += f"|cCreated:|n {request.date_created.strftime('%a %b %d %H:%M:%S %Y'):<30} |cHandler:|n {request.handler.username if request.handler else '-----'}\n"
        output += f"|cAdditional Players:|n\n"
        output += divider("Request", width=78, fillchar="|m-|n") + "\n"
        output += wrap_ansi(request.text, width=74, left_padding=2) + "\n\n"

        comments = request.comments.all().order_by('date_posted')
        if comments:
            output += divider("Comments", width=78, fillchar="|m-|n") + "\n"
            for comment in comments:
                output += f"{comment.author.username} [{comment.date_posted.strftime('%m/%d/%Y %H:%M')}]: "
                output += wrap_ansi(comment.text, width=74, left_padding=4) + "\n"

        output += footer(width=78, fillchar="|m-|n")
        self.caller.msg(output)

    def create_request(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +request/create <category>/<title>=<text>")
            return

        category_title, text = self.args.split("=", 1)
        category, title = category_title.split("/", 1)

        category = category.upper().strip()
        title = title.strip()
        text = text.strip()

        if category not in dict(Request.CATEGORIES):
            self.caller.msg(f"Invalid category. Choose from: {', '.join(dict(Request.CATEGORIES).keys())}")
            return

        new_request = Request.objects.create(
            category=category,
            title=title,
            text=text,
            requester=self.caller.account,
            status='NEW'
        )

        self.caller.msg(f"Request #{new_request.id} created successfully.")

    def add_comment(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +request/comment <#>=<text>")
            return

        req_id, comment_text = self.args.split("=", 1)
        
        try:
            req_id = int(req_id)
            request = Request.objects.get(id=req_id, requester=self.caller.account)
        except (ValueError, Request.DoesNotExist):
            self.caller.msg("Request not found.")
            return

        Comment.objects.create(
            request=request,
            author=self.caller.account,
            text=comment_text.strip()
        )

        self.caller.msg(f"Comment added to request #{req_id}.")

    def cancel_request(self):
        try:
            req_id = int(self.args)
            request = Request.objects.get(id=req_id, requester=self.caller.account)
        except (ValueError, Request.DoesNotExist):
            self.caller.msg("Request not found.")
            return

        request.status = 'CLOSED'
        request.save()
        self.caller.msg(f"Request #{req_id} has been cancelled.")

    def add_player(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +request/addplayer <#>=<player>")
            return

        req_id, player_name = self.args.split("=", 1)
        
        try:
            req_id = int(req_id)
            request = Request.objects.get(id=req_id, requester=self.caller.account)
        except (ValueError, Request.DoesNotExist):
            self.caller.msg("Request not found.")
            return

        player = self.caller.search(player_name)
        if not player:
            return

        # Here you might want to add logic to associate the player with the request
        # For simplicity, we'll just add a comment
        Comment.objects.create(
            request=request,
            author=self.caller.account,
            text=f"Added player {player.name} to the request."
        )

        self.caller.msg(f"Player {player.name} added to request #{req_id}.")


class CmdStaffRequest(Command):
    """
    Staff command to view all requests.

    Usage:
      staffrequest

    """
    key = "staffrequest"
    aliases = ["managerequest", "managerequests"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    """
    def func(self):
        if not self.args and not self.switches:
            self.list_all_requests()
        elif self.args and not self.switches:
            self.view_request()
        elif "assign" in self.switches:
            self.assign_request()
        elif "comment" in self.switches:
            self.add_comment()
        elif "close" in self.switches:
            self.close_request()
        else:
            self.caller.msg("Invalid switch. See help +requests for usage.")
"""
    def func(self):
        requests = Request.objects.all().order_by('-date_created')
        if not requests:
            self.caller.msg("There are no open requests.")
            return

        table = EvTable("ID", "Category", "Title", "Requester", "Status", border="cells")
        for req in requests:
            table.add_row(req.id, req.category, crop(req.title, width=30), req.requester.username, req.status)
        
        self.caller.msg(str(table))

class CmdStaffRequestView(Command):
    """
    View a request by ID number.

    Usage:
      staffrequest/view <#>

    """
    key = "staffrequest/view"
    aliases = ["managerequest/view", "managerequests/view"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        try:
            req_id = int(self.args)
            request = Request.objects.get(id=req_id)
        except (ValueError, Request.DoesNotExist):
            self.caller.msg("Request not found.")
            return

        self.caller.msg(f"Request #{request.id}: {request.title}")
        self.caller.msg(f"Category: {request.category}")
        self.caller.msg(f"Status: {request.status}")
        self.caller.msg(f"Requester: {request.requester.username}")
        self.caller.msg(f"Handler: {request.handler.username if request.handler else 'Unassigned'}")
        self.caller.msg(f"Created: {request.date_created.strftime('%Y-%m-%d %H:%M:%S')}")
        self.caller.msg(f"Text: {request.text}")

        comments = request.comments.all().order_by('date_posted')
        if comments:
            self.caller.msg("\nComments:")
            for comment in comments:
                self.caller.msg(f"{comment.author.username} ({comment.date_posted.strftime('%Y-%m-%d %H:%M')}): {comment.text}")

class CmdStaffRequestAssign(Command):
    """
    Assign a request to a staff member
    
    Usage:
      staffrequest/assign <#>=<staff>
    """
    key = "staffrequest/assign"
    aliases = ["managerequest/assign", "managerequests/assign"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +requests/assign <#>=<staff>")
            return

        req_id, staff_name = self.args.split("=", 1)
        
        try:
            req_id = int(req_id)
            request = Request.objects.get(id=req_id)
        except (ValueError, Request.DoesNotExist):
            self.caller.msg("Request not found.")
            return

        staff = self.caller.search(staff_name)
        if not staff:
            return

        request.handler = staff.account
        request.status = 'OPEN'
        request.save()

        Comment.objects.create(
            request=request,
            author=self.caller.account,
            text=f"Assigned to {staff.name}."
        )

        self.caller.msg(f"Request #{req_id} assigned to {staff.name}.")

class CmdStaffRequestComment(Command):
    """
    Comment on a request.

    Usage:
      staffrequest/comment <#>=<text>

    """
    key = "staffrequest/comment"
    aliases = ["managerequest/comment", "managerequests/comment"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: staffrequest/comment <#>=<text>")
            return

        req_id, comment_text = self.args.split("=", 1)
        
        try:
            req_id = int(req_id)
            request = Request.objects.get(id=req_id)
        except (ValueError, Request.DoesNotExist):
            self.caller.msg("Request not found.")
            return

        Comment.objects.create(
            request=request,
            author=self.caller.account,
            text=comment_text.strip()
        )

        self.caller.msg(f"Comment added to request #{req_id}.")

class CmdStaffRequestClose(Command):
    """
     Close a request

    Usage:
      staffrequest/close <#>
    """
    key = "staffrequest/close"
    aliases = ["managerequest/close", "managerequests/close"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        try:
            req_id = int(self.args)
            request = Request.objects.get(id=req_id)
        except (ValueError, Request.DoesNotExist):
            self.caller.msg("Request not found.")
            return

        request.status = 'CLOSED'
        request.save()

        Comment.objects.create(
            request=request,
            author=self.caller.account,
            text="Request closed."
        )

        self.caller.msg(f"Request #{req_id} has been closed.")