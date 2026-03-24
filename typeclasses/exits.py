"""
Exits

Exits are connectors between Rooms. An exit always has a destination property
set and has a single command defined on itself with the same name as its key,
for allowing Characters to traverse the exit to its destination.

"""

from evennia.objects.objects import DefaultExit

from .objects import ObjectParent
from world.utils.character_utils import is_character_approved


def _is_ooc_room(room):
    """Check if a room is an OOC area."""
    if not room or not hasattr(room, "db"):
        return False
    if getattr(room.db, "roomtype", None) == "OOC Area":
        return True
    if hasattr(room, "tags") and room.tags.has("ooc", category=None):
        return True
    # Check room.db.tags (list from +room/tag) - case-insensitive
    tags_list = getattr(room.db, "tags", []) or []
    if any(str(t).lower() == "ooc" for t in tags_list):
        return True
    return False


def _is_ic_room(room):
    """Check if a room is an IC area (not OOC)."""
    if not room:
        return False
    return not _is_ooc_room(room)


class Exit(ObjectParent, DefaultExit):
    """
    Exits are connectors between rooms. Exits are normal Objects except
    they defines the `destination` property and overrides some hooks
    and methods to represent the exits.

    Unapproved characters cannot traverse from OOC areas to IC areas.

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Objects child classes like this.

    """

    def _get_exit_cmd_signature(self):
        """
        Return a normalized signature for the exit command identity.

        We compare this between command-handler calls so alias/key changes
        automatically trigger an ExitCmdSet rebuild.
        """
        key = (self.db_key or "").strip().lower()
        aliases = tuple(
            sorted(alias.strip().lower() for alias in self.aliases.all() if alias and alias.strip())
        )
        return key, aliases

    def at_cmdset_get(self, **kwargs):
        """
        Keep ExitCmdSet in sync with live key/alias changes.

        Evennia only rebuilds exit commands when `force_init=True` is passed.
        If aliases are edited after creation, the commandset can become stale.
        """
        call_kwargs = dict(kwargs)

        current_signature = self._get_exit_cmd_signature()
        cached_signature = getattr(self.ndb, "_exit_cmd_signature", None)
        if current_signature != cached_signature:
            call_kwargs["force_init"] = True

        super().at_cmdset_get(**call_kwargs)
        self.ndb._exit_cmd_signature = current_signature

    def at_traverse(self, traversing_object, target_location, **kwargs):
        """
        Block unapproved characters from leaving OOC areas to enter the IC grid.
        Staff bypass via is_character_approved().
        """
        if traversing_object and traversing_object.has_account:
            source = self.location
            if _is_ooc_room(source) and _is_ic_room(target_location):
                if not is_character_approved(traversing_object):
                    traversing_object.msg(
                        "You must be approved by staff before entering IC areas. "
                        "Use +ic only after your character has been approved."
                    )
                    self.at_failed_traverse(traversing_object)
                    return
        super().at_traverse(traversing_object, target_location, **kwargs)
