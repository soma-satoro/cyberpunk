from django.db import models
from django.conf import settings
from evennia.objects.models import ObjectDB

class MailMessage(models.Model):
    """
    Represents a mail message in the game.
    """
    sender = models.CharField(max_length=255)
    recipients = models.CharField(max_length=1024)  # Keep for backward compatibility
    # Add new field to store recipients as object references
    character_recipients = models.ManyToManyField(
        ObjectDB, 
        related_name='received_mail',
        blank=True
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    date_sent = models.DateTimeField(auto_now_add=True)
    read_by = models.CharField(max_length=1024, default='')  # Keep for backward compatibility
    # Add new field for readers as objects
    read_by_characters = models.ManyToManyField(
        ObjectDB,
        related_name='read_mail',
        blank=True
    )

    def mark_read(self, reader):
        """Mark message as read by a character or account"""
        # Handle string readers for backward compatibility
        if isinstance(reader, str):
            if reader not in self.read_by.split(','):
                if self.read_by:
                    self.read_by += f',{reader}'
                else:
                    self.read_by = reader
                self.save()
        # Handle character object readers
        elif isinstance(reader, ObjectDB):
            self.read_by_characters.add(reader)
            # Also update the string field for backward compatibility
            reader_name = reader.key
            if reader_name not in self.read_by.split(','):
                if self.read_by:
                    self.read_by += f',{reader_name}'
                else:
                    self.read_by = reader_name
                self.save()
        return True
        
    def is_read_by(self, reader):
        """Check if message is read by a character or account"""
        # Handle string readers for backward compatibility
        if isinstance(reader, str):
            return reader in self.read_by.split(',')
        # Handle character object readers
        elif isinstance(reader, ObjectDB):
            return self.read_by_characters.filter(id=reader.id).exists() or reader.key in self.read_by.split(',')
        return False
        
    @classmethod
    def send_mail(cls, sender, recipients, subject, body):
        """Send a mail message to recipients"""
        # Create the message
        msg = cls.objects.create(
            sender=sender if isinstance(sender, str) else sender.key,
            recipients=','.join(r.key if hasattr(r, 'key') else r for r in recipients),
            subject=subject,
            body=body
        )
        
        # Add character recipients
        for recipient in recipients:
            if isinstance(recipient, ObjectDB):
                msg.character_recipients.add(recipient)
                
        return msg
        
    @classmethod
    def get_mail_for_character(cls, character, unread_only=False):
        """Get all mail for a character"""
        # Try using the character_recipients relation
        messages = cls.objects.filter(character_recipients=character)
        
        # If no messages found, try the legacy string field
        if not messages.exists():
            char_name = character.key
            messages = cls.objects.filter(recipients__contains=char_name)
            
            # Connect these messages to the character for future lookups
            for msg in messages:
                msg.character_recipients.add(character)
        
        # Filter to unread if requested
        if unread_only:
            return [msg for msg in messages if not msg.is_read_by(character)]
            
        return messages