from evennia import Command, CmdSet
from evennia.utils import create
from evennia.utils.evtable import EvTable
from .models import MailMessage
from django.utils.timezone import localtime
from django.utils.dateformat import format as date_format


class CmdMail(Command):
    """
    Send a mail message to another player.

    Usage:
      send <recipient>[,<recipient2>,...] = <subject> / <message>

    Sends a mail message to the specified recipient(s). Separate multiple
    recipients with commas. The subject and message are separated by a forward
    slash (/).
    """
    key = "send"
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: send <recipient>[,<recipient2>,...] = <subject> / <message>")
            return

        recipients_string, arg = self.args.split("=", 1)
        recipients = [r.strip() for r in recipients_string.split(",")]
        
        if "/" not in arg:
            self.caller.msg("You must specify both a subject and a message, separated by '/'.")
            return

        subject, body = arg.split("/", 1)
        subject = subject.strip()
        body = body.strip()

        if not subject or not body:
            self.caller.msg("You must specify both a subject and a message.")
            return

        # Validate recipients
        valid_recipients = []
        for recipient in recipients:
            player = self.caller.search(recipient)
            if player:
                valid_recipients.append(player)
            else:
                self.caller.msg(f"Could not find player: {recipient}")

        if not valid_recipients:
            self.caller.msg("No valid recipients found. Message not sent.")
            return

        # Send the mail
        try:
            MailMessage.objects.create(
                sender=self.caller.key,
                recipients=','.join([r.key for r in valid_recipients]),
                subject=subject,
                body=body
            )
            for recipient in valid_recipients:
                if hasattr(recipient, 'msg'):
                    recipient.msg(f"You have received a new mail from {self.caller.key} with subject: {subject}")
            self.caller.msg(f"Mail sent to {', '.join(r.key for r in valid_recipients)}.")
        except Exception as e:
            self.caller.msg(f"Error sending mail: {str(e)}")

class CmdMailbox(Command):
    """
    Check your mailbox.

    Usage:
      mailbox [<message number>]

    Lists all your mail messages or displays a specific message if a number
    is provided.
    """
    key = "mailbox"
    aliases = ["mail"]
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        messages = MailMessage.objects.filter(recipients__contains=self.caller.key).order_by('-date_sent')

        if not messages:
            self.caller.msg("Your mailbox is empty.")
            return

        if self.args:
            try:
                message_num = int(self.args) - 1
                message = messages[message_num]
                message.mark_read(self.caller.key)
                self.caller.msg(f"From: {message.sender}")
                self.caller.msg(f"To: {message.recipients}")
                self.caller.msg(f"Subject: {message.subject}")
                self.caller.msg(f"Sent: {date_format(localtime(message.date_sent), 'Y-m-d H:i:s')}")
                self.caller.msg("-" * 78)
                self.caller.msg(message.body)
            except (ValueError, IndexError):
                self.caller.msg("Invalid message number.")
        else:
            table = EvTable("ID", "From", "Subject", "Date", "Read", border="cells")
            for i, msg in enumerate(messages, 1):
                read = "Yes" if self.caller.key in msg.read_by.split(',') else "No"
                formatted_date = date_format(localtime(msg.date_sent), 'Y-m-d H:i:s')
                table.add_row(i, msg.sender, msg.subject, formatted_date, read)
            self.caller.msg(table)

class CmdMailDelete(Command):
    """
    Delete a mail message.

    Usage:
      maildelete <message number>

    Deletes the specified message from your mailbox.
    """
    key = "maildelete"
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: maildelete <message number>")
            return

        try:
            message_num = int(self.args) - 1
            handler = self.caller.scripts.get("mail_handler")
            if not handler:
                handler = create.create_script("world.mail.handlers.MailHandler", obj=self.caller)

                messages = MailMessage.objects.filter(recipients__contains=self.caller.key).order_by('-date_sent')
            if 0 <= message_num < len(messages):
                message = messages[message_num]
                if handler.delete_message(message.id):
                    self.caller.msg(f"Message {self.args} deleted.")
                else:
                    self.caller.msg("Error deleting message.")
            else:
                self.caller.msg("Invalid message number.")
        except ValueError:
            self.caller.msg("Please provide a valid message number.")

class MailCmdSet(CmdSet):
    """
    Cmdset for mail-related commands.
    """
    key = "mail"

    def at_cmdset_creation(self):
        self.add(CmdMail())
        self.add(CmdMailbox())
        self.add(CmdMailDelete())