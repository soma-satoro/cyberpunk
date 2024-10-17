"""
from evennia.server.serversession import ServerSession
from evennia.server.sessionhandler import SESSIONS
from evennia.accounts.models import AccountDB
from evennia.utils import logger
from evennia.server import amp
from evennia.objects.models import ObjectDB
import evennia
from twisted.internet import reactor

class CustomServerSession(ServerSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.log_info("CustomServerSession initialized")

    def disconnect(self, reason=""):

        Disconnect the session from the server.

        logger.log_info(f"Custom disconnect initiated: reason={reason}")
        super().disconnect(reason)

def custom_shutdown(mode='reload', _reactor_stopping=False):

    Custom shutdown function.

    logger.log_info(f"Custom shutdown initiated: mode={mode}")
    for p in AccountDB.objects.all():
        logger.log_info(f"Processing account: {p.id}, class: {p.__class__}, is custom: {isinstance(p, AccountDB)}")
        
        if hasattr(p, 'unpuppet_all'):
            p.unpuppet_all()
        elif hasattr(p, 'disconnect_all'):
            p.disconnect_all()
        else:
            logger.log_warn(f"Account {p.id} does not have unpuppet_all or disconnect_all method")
        
        if mode == "reload" and hasattr(p, 'at_server_reload'):
            p.at_server_reload()
        elif mode == "shutdown" and hasattr(p, 'at_server_shutdown'):
            p.at_server_shutdown()
        else:
            logger.log_warn(f"Account {p.id} does not have appropriate shutdown method for mode: {mode}")

    SESSIONS.disconnect_all()

    if not _reactor_stopping:
        reactor.callLater(0, reactor.stop)

    logger.log_info("Server shutdown complete")

# Replace the default ServerSession with our custom one
SESSIONS.server_session_class = CustomServerSession

# Store the original shutdown function
original_shutdown = evennia.EVENNIA_SERVER_SERVICE.shutdown

# Replace the shutdown function with our custom one
evennia.EVENNIA_SERVER_SERVICE.shutdown = custom_shutdown
"""