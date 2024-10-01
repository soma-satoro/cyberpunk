# world/netrunning/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import NetrunSession

@receiver(post_save, sender=NetrunSession)
def handle_netrun_session_save(sender, instance, created, **kwargs):
    if created:
        # Log the start of a new netrun session
        print(f"New netrun session started: {instance}")
    elif not instance.is_active and instance.end_time:
        # Log the end of a netrun session
        print(f"Netrun session ended: {instance}")