"""
Server configuration module.

Customizes ServerSession. The default Evennia shutdown is used - it properly
coordinates with the Portal (all_sessions_portal_sync) for reload.
"""
from evennia.server.serversession import ServerSession
from evennia.server.sessionhandler import SESSIONS
from evennia.utils import logger

class CustomServerSession(ServerSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.log_info("CustomServerSession initialized")

    def disconnect(self, reason=""):
        """Disconnect the session from the server."""
        logger.log_info(f"Custom disconnect initiated: reason={reason}")
        super().disconnect(reason)

# Replace the default ServerSession with our custom one
SESSIONS.server_session_class = CustomServerSession