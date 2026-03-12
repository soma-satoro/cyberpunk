"""
Account

The Account represents the game "account" and each login has only one
Account object. An Account is what chats on default channels but has no
other in-game-world existence. Rather the Account puppets Objects (such
as Characters) in order to actually participate in the game world.
"""

from django.apps import apps
from evennia import logger
from evennia.accounts.models import AccountDB

# use app registry to avoid nonetype error
DefaultAccount = apps.get_model("accounts", "DefaultAccount")
DefaultGuest = apps.get_model("accounts", "DefaultGuest")

class Account(DefaultAccount):
    """
    Player account that supports multiple characters (up to 4).
    Use +charlist to see your characters, +ic <name> to play one,
    and +charcreate <name> to make a new one.
    """

    def at_account_creation(self):
        """
        Called once when the account is first created.
        """
        self.db.characters = []

    def at_post_login(self, session=None, **kwargs):
        """
        Called after the account has successfully logged in.
        Shows a character selection screen.
        """
        super().at_post_login(session, **kwargs)
        self.show_character_menu(session)

    def show_character_menu(self, session=None):
        """
        Display the list of available characters and instructions.
        """
        characters = self.db._playable_characters or []

        self.msg("|r============================================================|n")
        self.msg("|r  Welcome back to Night City, %s|n" % self.key)
        self.msg("|r============================================================|n")

        if characters:
            self.msg("|wYour characters:|n")
            for i, char in enumerate(characters, 1):
                status = ""
                if char.tags.has("approved", category="approval"):
                    status = "|g[Approved]|n"
                else:
                    status = "|y[Pending]|n"
                self.msg(f"  {i}. |c{char.key}|n {status}")
            self.msg("")
            self.msg("|wTo play a character:|n +ic <character name>")
        else:
            self.msg("|wYou have no characters yet.|n")

        remaining = 4 - len(characters)
        if remaining > 0:
            self.msg(f"|wTo create a new character:|n +charcreate <name>")
            self.msg(f"|wCharacter slots remaining:|n {remaining}")

        self.msg("|r============================================================|n")


class Guest(DefaultGuest):
    """
    This class is used for guest logins. Unlike Accounts, Guests and their
    characters are deleted after disconnection.
    """
    pass
