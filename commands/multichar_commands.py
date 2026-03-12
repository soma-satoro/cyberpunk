"""
Multi-character account commands.

Allows players to create up to 4 characters per account
and switch between them.
"""

from evennia import Command, create_object, search_object
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import logger
from django.conf import settings


class CmdCharCreate(MuxCommand):
    """
    Create a new character on your account.

    Usage:
      +charcreate <character name>

    Creates a new character and places them in the character
    generation room. You can have up to 4 characters per account.
    """

    key = "+charcreate"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        account = self.account or self.caller.account

        if not account:
            self.msg("You must be logged in to create a character.")
            return

        if not self.args:
            self.msg("Usage: +charcreate <character name>")
            return

        char_name = self.args.strip().strip('"')

        if not char_name:
            self.msg("You must provide a name for your character.")
            return

        characters = account.db._playable_characters or []
        max_chars = settings.MAX_NR_CHARACTERS or 4

        if len(characters) >= max_chars:
            self.msg(f"You already have {max_chars} characters. Delete one before creating another.")
            return

        existing = [c for c in characters if c.key.lower() == char_name.lower()]
        if existing:
            self.msg(f"You already have a character named '{char_name}'.")
            return

        typeclass = settings.BASE_CHARACTER_TYPECLASS

        # ****************************************************
        # * Find the chargen room to place new characters    *
        # ****************************************************
        from evennia.objects.models import ObjectDB
        chargen_rooms = ObjectDB.objects.filter(
            db_typeclass_path="typeclasses.chargen.ChargenRoom"
        )
        if chargen_rooms.exists():
            start_location = chargen_rooms.first()
        else:
            start_location = search_object("#2")[0]

        try:
            new_char = create_object(
                typeclass,
                key=char_name,
                location=start_location,
                home=start_location,
                permissions=["Player"],
            )

            new_char.locks.add(
                f"puppet:id({account.id}) or pid({account.id}) or pperm(Developer);delete:id({account.id}) or perm(Admin)"
            )

            account.db._playable_characters = characters + [new_char]

            self.msg(f"|gCharacter '{char_name}' created successfully!|n")
            self.msg(f"Use |w+ic {char_name}|n to start playing.")
            self.msg("Your character is in the character generation room.")

        except Exception as e:
            logger.log_err(f"Error creating character '{char_name}': {str(e)}")
            self.msg("An error occurred creating your character. Please try again or contact staff.")


class CmdCharList(MuxCommand):
    """
    List all characters on your account.

    Usage:
      +charlist
    """

    key = "+charlist"
    aliases = ["charlist"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        account = self.account or self.caller.account

        if not account:
            self.msg("You must be logged in.")
            return

        characters = account.db._playable_characters or []

        if not characters:
            self.msg("You have no characters. Use +charcreate <name> to make one.")
            return

        self.msg("|r==================== Your Characters ====================|n")
        for i, char in enumerate(characters, 1):
            status = ""
            if char.tags.has("approved", category="approval"):
                status = "|g[Approved]|n"
            else:
                status = "|y[Pending]|n"

            location = char.location.key if char.location else "Nowhere"
            self.msg(f"  {i}. |c{char.key:<20}|n {status:<20} Location: {location}")

        remaining = (settings.MAX_NR_CHARACTERS or 4) - len(characters)
        self.msg(f"\n|wCharacter slots remaining:|n {remaining}")
        self.msg("|r=========================================================|n")


class CmdCharDelete(MuxCommand):
    """
    Delete one of your characters.

    Usage:
      +chardelete <character name>
      +chardelete/confirm <character name>

    You must use the /confirm switch to actually delete.
    This action cannot be undone.
    """

    key = "+chardelete"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        account = self.account or self.caller.account

        if not account:
            self.msg("You must be logged in.")
            return

        if not self.args:
            self.msg("Usage: +chardelete <character name>")
            return

        char_name = self.args.strip()
        characters = account.db._playable_characters or []
        target = None

        for char in characters:
            if char.key.lower() == char_name.lower():
                target = char
                break

        if not target:
            self.msg(f"You don't have a character named '{char_name}'.")
            return

        if "confirm" not in self.switches:
            self.msg(f"|rWARNING:|n This will permanently delete '{target.key}'.")
            self.msg(f"Type |w+chardelete/confirm {target.key}|n to confirm.")
            return

        characters.remove(target)
        account.db._playable_characters = characters
        target.delete()
        self.msg(f"|rCharacter '{char_name}' has been permanently deleted.|n")
