"""
Evennia settings file.

The available options are found
here:

https://www.evennia.com/docs/latest/Setup/Settings-Default.html

Remember:

Don't copy more from the default file than you actually intend to
change; this will make sure that you don't overload upstream updates
unnecessarily.

When changing a setting requiring a file system path (like
path/to/actual/file.py), use GAME_DIR and EVENNIA_DIR to reference
your game folder and the Evennia library folders respectively. Python
paths (path.to.module) should be given relative to the game's root
folder (typeclasses.foo) whereas paths within the Evennia library
needs to be given explicitly (evennia.foo).

If you want to share your game dir, including its settings, you can
put secret game- or server-specific settings in secret_settings.py.

"""

# Use the defaults from Evennia unless explicitly overridden
from evennia.settings_default import *

######################################################################
# Evennia base server config
######################################################################

# This is the name of your game. Make it catchy!
SERVERNAME = "cyberpunk"
DEBUG = True
SITE_ID = 1
DEFAULT_CMDSETS = [
    'commands.mycmdset.MyCmdset'
]
# Server ports. If enabled and marked as "visible", the port
# should be visible to the outside world on a production server.
# Note that there are many more options available beyond these.

# Telnet ports. Visible.
TELNET_ENABLED = True
TELNET_PORTS = [4000]
# (proxy, internal). Only proxy should be visible.
WEBSERVER_ENABLED = True
WEBSERVER_PORTS = [(4001, 4002)]
# Telnet+SSL ports, for supporting clients. Visible.
SSL_ENABLED = False
SSL_PORTS = [4003]
# SSH client ports. Requires crypto lib. Visible.
SSH_ENABLED = False
SSH_PORTS = [4004]
# Websocket-client port. Visible.
WEBSOCKET_CLIENT_ENABLED = True
WEBSOCKET_CLIENT_PORT = 4005
# Internal Server-Portal port. Not visible.
AMP_PORT = 4006

INSTALLED_APPS += [  # type: ignore
    'world.cyberpunk_sheets',
    'world.inventory',
    'world.cyberware',
    'world.factions',
    'world.mail',
    'world.requests',
    'world.languages',
    'world.netrunning'
]
CMDSET_CHARACTER = "commands.default_cmdsets.CharacterCmdSet"
BASE_ROOM_TYPECLASS = "typeclasses.rooms.Room"
BASE_EXIT_TYPECLASS = "typeclasses.exits.Exit"
BASE_OBJECT_TYPECLASS = "typeclasses.objects.Object"
BASE_CHARACTER_TYPECLASS = "typeclasses.characters.Character"
BASE_ACCOUNT_TYPECLASS = "typeclasses.accounts.Account"
# Add this line to force Evennia to reload typeclasses on startup
TYPECLASS_PATHS = ["typeclasses"]
TYPECLASS_RELOAD_ON_CHANGE = True
RELOAD_AT_SERVER_STARTSTOP = True
######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")


