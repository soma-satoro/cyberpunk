
from evennia import DefaultScript
from .models import MailMessage

class MailHandler(DefaultScript):
    """
    Script to handle mail operations.
    """
    def at_script_creation(self):
        self.key = "mail_handler"
        self.persistent = True

    def delete_message(self, message_id):
        try:
            message = MailMessage.objects.get(id=message_id)
            message.delete()
            return True
        except MailMessage.DoesNotExist:
            return False