"""
Account

The Account represents the game "account" and each login has only one
Account object. An Account is what chats on default channels but has no
other in-game-world existence. Rather the Account puppets Objects (such
as Characters) in order to actually participate in the game world.


Guest

Guest accounts are simple low-level accounts that are created/deleted
on the fly and allows users to test the game without the commitment
of a full registration. Guest accounts are deactivated by default; to
activate them, add the following line to your settings file:

    GUEST_ENABLED = True

You will also need to modify the connection screen to reflect the
possibility to connect with a guest account. The setting file accepts
several more options for customizing the Guest account system.

"""

from evennia import logger
from evennia import DefaultAccount
from evennia.accounts.accounts import DefaultAccount, DefaultGuest
from evennia.accounts.models import AccountDB

class Account(DefaultAccount):
    """
    This class describes the actual OOC account (i.e. the user connecting
    to the MUD). It does NOT have visual appearance in the game world (that
    is handled by the character which is connected to this). Accounts are
    created when the user first connects to the game (with a unique
    username) and reconnects to it ever after with the same user to gain
    access. An account can be connected to several characters.
    """
    class Meta:
        """
        This defines metadata for the Account model.
        """
        app_label = 'accounts'

    objects = AccountDB.objects

    def at_account_creation(self):
        """
        This is called once, the very first time the account is created
        (i.e. first time they register with the game). It's a good
        place to store attributes all accounts should have, like
        configuration values etc.
        """
        # set an (empty) attribute holding the characters this account has
        self.db.characters = []

    def __init__(self, *args, **kwargs):
        logger.log_info(f"Initializing custom Account: {args[0] if args else 'No args'}")
        super().__init__(*args, **kwargs)

    def at_server_reload(self):
        logger.log_info(f"at_server_reload called for Account {self.id}")
        super().at_server_reload()

    def unpuppet_all(self):
        logger.log_info(f"unpuppet_all called for Account {self.id}")
        for session in self.sessions.all():
            self.unpuppet_object(session)

    def unpuppet_object(self, session):
        logger.log_info(f"unpuppet_object called for Account {self.id}")
        super().unpuppet_object(session)

    def at_server_shutdown(self):
        logger.log_info(f"at_server_shutdown called for Account {self.id}")
        self.msg("Server is shutting down. Thank you for playing!")
        super().at_server_shutdown()
        
    def at_post_login(self, session=None):
        """
        Called after the account has successfully logged in.
        """
        super().at_post_login(session)
        logger.log_info(f"Account logged in: {self.name}")

class Guest(DefaultGuest):
    """
    This class is used for guest logins. Unlike Accounts, Guests and their
    characters are deleted after disconnection.
    """

    pass

logger.log_info(f"Account class methods: {[method for method in dir(Account) if not method.startswith('__')]}")
