from django.db import models
from django.conf import settings

class MailMessage(models.Model):
    """
    Represents a mail message in the game.
    """
    sender = models.CharField(max_length=255)
    recipients = models.CharField(max_length=1024)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    date_sent = models.DateTimeField(auto_now_add=True)
    read_by = models.CharField(max_length=1024, default='')

    def mark_read(self, reader):
        if reader not in self.read_by.split(','):
            if self.read_by:
                self.read_by += f',{reader}'
            else:
                self.read_by = reader
            self.save()