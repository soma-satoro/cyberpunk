"""
IP (Improvement Points) configuration script and accessors.

Stores game-wide IP settings:
- Vote system: enabled, IP per vote
- Weekly allotment: enabled, IP per week
"""
from evennia import DefaultScript, create_script
from evennia.scripts.models import ScriptDB


IP_CONFIG_KEY = "IPConfig"


def get_ip_config():
    """Get or create the IP config script. Returns None on failure."""
    try:
        script = ScriptDB.objects.get(db_key=IP_CONFIG_KEY)
    except ScriptDB.DoesNotExist:
        script = create_script(IPConfigScript, key=IP_CONFIG_KEY)
        if script is True or script is False:
            try:
                script = ScriptDB.objects.get(db_key=IP_CONFIG_KEY)
            except ScriptDB.DoesNotExist:
                return None
    except ScriptDB.MultipleObjectsReturned:
        script = ScriptDB.objects.filter(db_key=IP_CONFIG_KEY).first()

    return script


def get_vote_system_enabled():
    """Check if vote system is enabled."""
    config = get_ip_config()
    if not config:
        return False
    return config.db.vote_system_enabled or False


def get_vote_ip_amount():
    """Get IP awarded per vote."""
    config = get_ip_config()
    if not config:
        return 0.5
    val = config.db.vote_ip_amount
    return float(val) if val is not None else 0.5


def get_vote_cooldown_hours():
    """Get hours between vote IP awards per character (default 24 = once per day)."""
    config = get_ip_config()
    if not config:
        return 24
    val = config.db.vote_cooldown_hours
    return int(val) if val is not None else 24


def get_weekly_allotment_enabled():
    """Check if weekly allotment is enabled."""
    config = get_ip_config()
    if not config:
        return False
    return config.db.weekly_allotment_enabled or False


def get_weekly_allotment_amount():
    """Get IP awarded per week."""
    config = get_ip_config()
    if not config:
        return 3
    val = config.db.weekly_allotment_amount
    return int(val) if val is not None else 3


class IPConfigScript(DefaultScript):
    """Global script storing IP system configuration."""

    def at_script_creation(self):
        self.key = IP_CONFIG_KEY
        self.desc = "IP (Improvement Points) system configuration"
        self.persistent = True
        # Vote system
        self.db.vote_system_enabled = False
        self.db.vote_ip_amount = 0.5
        self.db.vote_cooldown_hours = 24  # Once per day by default
        # Weekly allotment
        self.db.weekly_allotment_enabled = False
        self.db.weekly_allotment_amount = 3
