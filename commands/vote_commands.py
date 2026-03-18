"""
Vote command for Improvement Points.

When the vote system is enabled, players can use +vote <name> to vote for
other characters. The voted character receives IP. Staff can award IP directly
via +ip/award; they do not need the vote system.

Rules:
- +vote by itself does nothing.
- Cannot vote for staff.
- Cannot vote for characters who are not approved.
- Cannot vote for yourself.
"""
from evennia.commands.default.muxcommand import MuxCommand
from datetime import datetime
from world.improvement_points import get_character_ip, add_ip_log_entry
from world.ip_config import get_vote_system_enabled, get_vote_ip_amount, get_vote_cooldown_hours
from world.utils.character_utils import is_character_approved, can_receive_ip, is_staff


def get_target_character(caller, name):
    """Resolve name to a puppetable character (typeclass)."""
    if not name:
        return None
    target = caller.search(name, global_search=True)
    if not target:
        return None
    if hasattr(target, "db") and hasattr(target, "attributes"):
        return target
    if hasattr(target, "characters") and target.characters:
        return list(target.characters)[0] if not callable(target.characters) else target.characters[0]
    if hasattr(target, "character") and target.character:
        return target.character
    return target


class CmdVote(MuxCommand):
    """
    Vote for another character to give them Improvement Points.

    Usage:
      +vote <name>    - Vote for another character (when vote system is enabled)

    When the vote system is enabled, you can vote for other approved characters
    once per cooldown period. You cannot vote for staff or unapproved characters.
    Staff can award IP directly via +ip/award.
    """

    key = "+vote"
    aliases = ["vote"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        if not get_vote_system_enabled():
            self.caller.msg("The vote IP system is not currently enabled.")
            return

        # +vote by itself does nothing
        if not self.args or not self.args.strip():
            return

        self._vote_for_character()

    def _vote_for_character(self):
        """Player votes for another character."""
        voter_char = self._get_self_char()
        if not voter_char:
            self.caller.msg("You must be puppeting a character to vote.")
            return
        if not is_character_approved(voter_char):
            self.caller.msg("You must be approved by staff before you can vote.")
            return

        target = get_target_character(self.caller, self.args.strip())
        if not target:
            self.caller.msg("Could not find that character.")
            return

        # Cannot vote for staff
        if is_staff(target):
            self.caller.msg("You cannot vote for staff members.")
            return

        # Cannot vote for unapproved characters
        if not can_receive_ip(target):
            self.caller.msg("You cannot vote for characters who are not approved.")
            return

        # Cannot vote for yourself
        caller_acct = getattr(self.caller, "account", self.caller)
        if hasattr(caller_acct, "characters") and caller_acct.characters:
            my_chars = list(caller_acct.characters) if not callable(caller_acct.characters) else list(caller_acct.characters)
            if target in my_chars:
                self.caller.msg("You cannot vote for your own character.")
                return

        # Check voter cooldown - can only cast one vote per period
        cooldown_hours = get_vote_cooldown_hours()
        last_cast = voter_char.attributes.get("ip_last_vote_cast", default=None)
        now = datetime.now()
        if last_cast:
            if isinstance(last_cast, str):
                try:
                    last_cast = datetime.fromisoformat(last_cast)
                except ValueError:
                    last_cast = None
            if last_cast:
                elapsed = (now - last_cast).total_seconds()
                if elapsed < cooldown_hours * 3600:
                    remaining_mins = int((cooldown_hours * 3600 - elapsed) / 60)
                    self.caller.msg(
                        f"You can vote again in {remaining_mins} minutes."
                    )
                    return

        # Check recipient cooldown - target must not have received vote IP recently
        last_vote = target.attributes.get("ip_last_vote", default=None)
        if last_vote:
            if isinstance(last_vote, str):
                try:
                    last_vote = datetime.fromisoformat(last_vote)
                except ValueError:
                    last_vote = None
            if last_vote:
                elapsed = (now - last_vote).total_seconds()
                if elapsed < cooldown_hours * 3600:
                    remaining_mins = int((cooldown_hours * 3600 - elapsed) / 60)
                    self.caller.msg(
                        f"{target.get_display_name(self.caller)} has received a vote recently. "
                        f"Try again in {remaining_mins} minutes."
                    )
                    return

        amount = get_vote_ip_amount()
        if amount <= 0:
            self.caller.msg("Vote IP amount is set to 0.")
            return

        # Award IP to target
        current, _, _, _, _ = get_character_ip(target)
        new_current = current + amount
        target.attributes.add("improvement_points", new_current)
        target.attributes.add("ip_last_vote", now.isoformat())
        add_ip_log_entry(target, amount, "Vote", f"Voted by {voter_char.get_display_name(self.caller)}", exclude_from_recent=True)

        # Update voter cooldown
        voter_char.attributes.add("ip_last_vote_cast", now.isoformat())

        self.caller.msg(f"You voted for {target.get_display_name(self.caller)}. They received {amount} IP.")
        if target.sessions.all():
            target.msg(f"You received {amount} IP from a vote by {voter_char.get_display_name(self.caller)}. New total: {new_current}")

    def _get_self_char(self):
        if hasattr(self.caller, "db") and hasattr(self.caller, "attributes"):
            return self.caller
        if hasattr(self.caller, "character") and self.caller.character:
            return self.caller.character
        if hasattr(self.caller, "characters") and self.caller.characters:
            chars = list(self.caller.characters) if not callable(self.caller.characters) else list(self.caller.characters())
            return chars[0] if chars else None
        return None
