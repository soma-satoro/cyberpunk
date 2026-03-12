"""
Faction utilities: channel creation, default sponsor, room tag checks.
"""
import re
from evennia.utils import create
from evennia.comms.models import ChannelDB
from evennia.utils import logger


# Leading articles to strip from channel names (case-insensitive)
_CHANNEL_ARTICLES = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)


def _channel_key_from_faction_name(faction_name):
    """
    Return channel key: faction name with leading articles (The, A, An) stripped.
    E.g. 'The CZ OGs' -> 'CZ OGs', 'Arasaka' -> 'Arasaka'.
    """
    return _CHANNEL_ARTICLES.sub("", faction_name.strip()).strip() or faction_name


def faction_channel_alias(faction_name):
    """
    Return a short alias for the faction channel (first 3 alphanumeric chars, lowercase).
    E.g. 'Arasaka' -> 'ara', 'Militech' -> 'mil', 'NCPD' -> 'ncp'.
    """
    alpha = re.sub(r"[^a-zA-Z0-9]", "", faction_name)
    return (alpha[:3] or faction_name[:3] or "fc").lower()


def _single_word_aliases(faction_name):
    """
    Return aliases for a faction channel (single-word only, no spaces).
    Includes short 3-letter alias; full faction name only if it has no spaces.
    """
    short_alias = faction_channel_alias(faction_name)
    aliases = [short_alias]
    if " " not in faction_name.strip():
        aliases.insert(0, faction_name.strip())
    return aliases


def create_faction_channel(faction_name):
    """
    Create a channel for a faction, or ensure an existing one has correct aliases.
    Channel key is faction name with leading articles stripped (no 'Faction-' prefix).
    Aliases are single-word only (no spaces) - e.g. short abbrev 'ara', or full name 'Arasaka'.
    Returns the channel or None.
    """
    channel_key = _channel_key_from_faction_name(faction_name)
    aliases_to_add = _single_word_aliases(faction_name)
    legacy_key = f"Faction-{faction_name}"  # backward compat for old channels
    try:
        existing = ChannelDB.objects.channel_search(channel_key)
        if not existing:
            existing = ChannelDB.objects.channel_search(legacy_key)
        if existing:
            channel = existing[0]
            current = getattr(channel.aliases, 'all', lambda: [])() or []
            # Remove any multi-word aliases
            for al in list(current):
                if " " in str(al):
                    try:
                        channel.aliases.remove(al)
                        logger.log_info(f"Removed multi-word alias '{al}' from faction channel {channel_key}")
                    except Exception:
                        pass
            # Add single-word aliases that are missing
            for al in aliases_to_add:
                if al not in current:
                    channel.aliases.add(al)
                    logger.log_info(f"Added alias '{al}' to faction channel {channel_key}")
            return channel
        channel = create.create_channel(
            channel_key,
            aliases=aliases_to_add,
            typeclass="typeclasses.channels.Channel",
            locks="control:perm(Admin);listen:all();send:all()"
        )
        logger.log_info(f"Created faction channel: {channel_key} (aliases: {aliases_to_add})")
        return channel
    except Exception as e:
        logger.log_err(f"Failed to create faction channel for {faction_name}: {e}")
        return None


def get_default_staff_sponsor():
    """
    Get the default staff sponsor for new factions.
    Stored on FactionConfig script. Returns AccountDB or None.
    """
    from evennia.scripts.models import ScriptDB
    try:
        config = ScriptDB.objects.filter(db_key="FactionConfig").first()
        if config and hasattr(config, 'db_default_sponsor_id'):
            sponsor_id = config.db.default_sponsor_id
            if sponsor_id:
                from evennia.accounts.models import AccountDB
                return AccountDB.objects.filter(id=sponsor_id).first()
    except Exception as e:
        logger.log_err(f"Error getting default faction sponsor: {e}")
    return None


def set_default_staff_sponsor(account):
    """
    Set the default staff sponsor for new factions.
    account: AccountDB or None to clear.
    """
    from evennia.scripts.models import ScriptDB
    from evennia import create_script
    try:
        config = ScriptDB.objects.filter(db_key="FactionConfig").first()
        if not config:
            config = create_script(
                "evennia.scripts.scripts.DefaultScript",
                key="FactionConfig",
                persistent=True
            )
        config.db.default_sponsor_id = account.id if account else None
        return True
    except Exception as e:
        logger.log_err(f"Error setting default faction sponsor: {e}")
        return False


def room_has_faction_vendor_tags(room, faction_name):
    """
    Check if room has both the faction tag and 'Vendor' tag.
    Room tags are in room.db.tags (list) or room.tags (Evennia tag handler).
    """
    if not room:
        return False
    tags = getattr(room.db, 'tags', []) or []
    if hasattr(room, 'tags') and hasattr(room.tags, 'all'):
        # Evennia tag handler - get tags in 'room' or no category
        try:
            tag_objs = list(room.tags.all())
            tags = list(tags) + [t.key for t in tag_objs if hasattr(t, 'key')]
        except Exception:
            pass
    tags_lower = [str(t).lower() for t in tags]
    faction_lower = faction_name.lower().replace(" ", "")
    return 'vendor' in tags_lower and (faction_name.lower() in tags_lower or faction_lower in tags_lower)


def subscribe_character_to_faction_channel(character, faction):
    """
    Subscribe a character's account to the faction's channel.
    Call when character gains faction rep.
    """
    if not character or not faction or not getattr(faction, 'channel_id', None):
        return
    try:
        from evennia.comms.models import ChannelDB
        channel = ChannelDB.objects.filter(id=faction.channel_id).first()
        if not channel:
            return
        account = getattr(character, 'account', None)
        if not account:
            return
        if not channel.has_connection(account):
            channel.connect(account)
            logger.log_info(f"Subscribed {character.key} to faction channel {faction.name}")
    except Exception as e:
        logger.log_err(f"Error subscribing to faction channel: {e}")


def character_has_faction_rep(character, faction, min_rep=0):
    """
    Check if character has FactionReputation with this faction (optionally with min rep).
    character: ObjectDB (puppeted character)
    faction: Faction model
    min_rep: minimum rep rank (default 0 = any standing)
    """
    from world.factions.models import FactionReputation
    try:
        fr = FactionReputation.objects.get(character=character, faction=faction)
        return fr.rep >= min_rep or fr.notoriety > 0
    except FactionReputation.DoesNotExist:
        return False
