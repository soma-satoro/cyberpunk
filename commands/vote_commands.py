"""
Vote command for claiming Improvement Points.

When the vote system is enabled, players can use +vote to claim IP
for voting on the game (e.g. on TopMUDs). A cooldown prevents abuse.
Staff can use +vote <name> to manually award vote IP (cannot vote for
self or other staff; same cooldown applies per character).
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
    Claim Improvement Points for voting.

    Usage:
      +vote           - Claim your vote IP (when vote system is enabled)
      +vote <name>    - [Staff] Manually award vote IP to a player

    When the vote system is enabled, you can claim IP once per day (or as
    configured). Staff cannot vote for themselves or other staff.
    """

    key = "+vote"
    aliases = ["vote"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        if not get_vote_system_enabled():
            self.caller.msg("The vote IP system is not currently enabled.")
            return

        # Staff: +vote <name> to manually award
        if self.args:
            acct = getattr(self.caller, "account", self.caller)
            if acct and acct.check_permstring("Builder"):
                self._staff_award()
                return
            self.caller.msg("Only staff can award vote IP to another player.")

        # Self-claim
        self._self_claim()

    def _staff_award(self):
        """Staff manually awards vote IP to a player."""
        target = get_target_character(self.caller, self.args.strip())
        if not target:
            self.caller.msg("Could not find that character.")
            return
        if not can_receive_ip(target):
            if is_staff(target):
                self.caller.msg("You cannot award vote IP to staff members.")
            else:
                self.caller.msg("That character must be approved before receiving vote IP.")
            return

        # Cannot vote for yourself (any of your characters)
        caller_acct = getattr(self.caller, "account", self.caller)
        if hasattr(caller_acct, "characters") and caller_acct.characters:
            my_chars = list(caller_acct.characters) if not callable(caller_acct.characters) else list(caller_acct.characters)
            if target in my_chars:
                self.caller.msg("You cannot award vote IP to your own character.")
                return

        # Check cooldown - target must not have received vote IP recently
        cooldown_hours = get_vote_cooldown_hours()
        last_vote = target.attributes.get("ip_last_vote", default=None)
        if last_vote:
            if isinstance(last_vote, str):
                try:
                    last_vote = datetime.fromisoformat(last_vote)
                except ValueError:
                    last_vote = None
            if last_vote:
                elapsed = (datetime.now() - last_vote).total_seconds()
                if elapsed < cooldown_hours * 3600:
                    remaining_mins = int((cooldown_hours * 3600 - elapsed) / 60)
                    self.caller.msg(
                        f"{target.get_display_name(self.caller)} last received vote IP recently. "
                        f"Try again in {remaining_mins} minutes."
                    )
                    return

        amount = get_vote_ip_amount()
        if amount <= 0:
            self.caller.msg("Vote IP amount is set to 0.")
            return

        current, spent, _, _, _ = get_character_ip(target)
        new_current = current + amount
        target.attributes.add("improvement_points", new_current)
        target.attributes.add("ip_last_vote", datetime.now().isoformat())
        add_ip_log_entry(target, amount, "Vote", "Awarded by staff", exclude_from_recent=True)

        self.caller.msg(f"Awarded {amount} vote IP to {target.get_display_name(self.caller)}.")
        if target.sessions.all():
            target.msg(f"You have been awarded {amount} IP for voting. New total: {new_current}")

    def _self_claim(self):
        """Player claims their own vote IP (with cooldown). Staff cannot receive vote IP."""
        char = self._get_self_char()
        if not char:
            self.caller.msg("You must be puppeting a character to claim vote IP.")
            return
        if not can_receive_ip(char):
            if not is_character_approved(char):
                self.caller.msg("You must be approved by staff before claiming vote IP.")
            else:
                self.caller.msg("Staff do not receive IP from voting.")
            return

        cooldown_hours = get_vote_cooldown_hours()
        last_vote = char.attributes.get("ip_last_vote", default=None)
        now = datetime.now()
        if last_vote:
            if isinstance(last_vote, str):
                try:
                    last_vote = datetime.fromisoformat(last_vote)
                except ValueError:
                    last_vote = None
            if last_vote:
                elapsed = (now - last_vote).total_seconds()
                if elapsed < cooldown_hours * 3600:
                    remaining = int((cooldown_hours * 3600 - elapsed) / 60)
                    self.caller.msg(
                        f"You can claim vote IP again in {remaining} minutes. "
                        "Vote on our game listing, then try again!"
                    )
                    return

        amount = get_vote_ip_amount()
        if amount <= 0:
            self.caller.msg("Vote IP is currently disabled.")
            return

        current, _, _, _, _ = get_character_ip(char)
        new_current = current + amount
        char.attributes.add("improvement_points", new_current)
        char.attributes.add("ip_last_vote", now.isoformat())
        add_ip_log_entry(char, amount, "Vote", "", exclude_from_recent=True)

        self.caller.msg(
            f"Thanks for voting! You received {amount} IP. "
            f"New total: {new_current}. You can vote again in {cooldown_hours} hours."
        )

    def _get_self_char(self):
        if hasattr(self.caller, "db") and hasattr(self.caller, "attributes"):
            return self.caller
        if hasattr(self.caller, "character") and self.caller.character:
            return self.caller.character
        if hasattr(self.caller, "characters") and self.caller.characters:
            chars = list(self.caller.characters) if not callable(self.caller.characters) else list(self.caller.characters())
            return chars[0] if chars else None
        return None
