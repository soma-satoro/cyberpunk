from django.db.models.signals import post_save
from django.dispatch import receiver
from evennia.accounts.models import AccountDB
from evennia.objects.models import ObjectDB
from .models import CharacterSheet

# Temporarily commented out to allow migrations to run
# @receiver(post_save, sender=AccountDB)
# def create_character_sheet_for_account(sender, instance, created, **kwargs):
#     if created:
#         CharacterSheet.objects.get_or_create(account=instance)

# @receiver(post_save, sender=ObjectDB)
# def update_character_sheet_for_character(sender, instance, **kwargs):
#     if instance.db_typeclass_path and 'characters' in instance.db_typeclass_path:
#         if instance.account:
#             sheet, created = CharacterSheet.objects.get_or_create(account=instance.account)
#             if not sheet.db_object:
#                 sheet.db_object = instance
#                 sheet.save()