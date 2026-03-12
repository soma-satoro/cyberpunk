"""
Elflines Online services - business logic.
"""

from django.apps import apps
from evennia.utils import create

from .elflines_data import ELO_SKILLS, ELO_STATS, ELO_ARMORY, ELO_STAT_POINTS, ELO_SKILL_POINTS
from .models import ElflineSheet, Elfline, ElflineMembership


def get_or_create_elfline_sheet(character):
    """Get or create an Elfline sheet for a character."""
    sheet, created = ElflineSheet.objects.get_or_create(
        character=character,
        defaults={
            "gp": 200,
            "intelligence": 3,
            "reflexes": 3,
            "dexterity": 3,
            "technology": 3,
            "cool": 3,
            "willpower": 3,
            "move": 3,
            "body": 3,
            "empathy": 3,
        },
    )
    if created:
        sheet.skills = {"language_elven": 4}  # Auto for all elves
        if hasattr(character, "character_sheet") and character.character_sheet:
            sheet.character_sheet = character.character_sheet
        sheet.recalculate_hp()
        sheet.save()
    return sheet


def get_elo_sheet_for_character(character):
    """Get ELO sheet by character or character_sheet."""
    try:
        return ElflineSheet.objects.get(character=character)
    except ElflineSheet.DoesNotExist:
        pass
    if hasattr(character, "character_sheet") and character.character_sheet:
        try:
            return ElflineSheet.objects.get(character_sheet=character.character_sheet)
        except ElflineSheet.DoesNotExist:
            pass
    return None


def get_elo_lobby():
    """Get the ELO lobby room. Returns None if not created (staff must +elosetup)."""
    from evennia.utils import search_object

    rooms = search_object("ELO Lobby", typeclass="typeclasses.elflines_rooms.ElflinesRoom")
    return rooms[0] if rooms else None


def is_in_elo(character):
    """Check if character is currently in an ELO room."""
    loc = character.location
    if not loc:
        return False
    return getattr(loc, "is_elflines_room", False)


def can_enter_elo(character):
    """Check if character can log into ELO (subscription, equipment - can be relaxed for MUSH)."""
    # For MUSH, we can waive equipment/subscription or gate by lifestyle
    return True


def elo_login(character):
    """Move character into ELO. Saves meat location, moves to ELO lobby."""
    if is_in_elo(character):
        return False, "You are already in the Elflands."
    lobby = get_elo_lobby()
    if not lobby:
        return False, "The Elflines Online server is not configured. Contact staff."
    if not can_enter_elo(character):
        return False, "You need an active subscription and a Segotari RUSH REVOLUTION headset to play."
    character.db.pre_elo_location = character.location
    character.move_to(lobby, quiet=True)
    return True, None


def elo_logout(character):
    """Move character out of ELO back to meat world."""
    if not is_in_elo(character):
        return False, "You are not in the Elflands."
    meat_loc = character.db.pre_elo_location
    if not meat_loc:
        meat_loc = get_elo_lobby()  # Fallback
    character.db.pre_elo_location = None
    if meat_loc:
        character.move_to(meat_loc, quiet=True)
    return True, None
