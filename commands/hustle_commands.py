from evennia import Command
from evennia.utils.evmenu import EvMenu
from world.hustle_system import get_or_create_hustle_system, get_character_role, get_role_ability_rank
from world.utils.character_utils import is_character_approved
from evennia.utils import logger
import traceback


def hustle_menu(caller):
    """Entry node: explain the hustle and offer to attempt."""
    logger.log_info(f"Entering hustle_menu for {caller.name}")
    try:
        hustle_system = get_or_create_hustle_system()
        if not hustle_system:
            logger.log_err(f"Failed to initialize hustle system for {caller.name}")
            caller.msg("Error: Unable to initialize the hustle system. Please contact an admin.")
            return "exit_menu"

        if not hustle_system.can_attempt_hustle(caller):
            caller.msg("You have already attempted your hustle this week. Please try again next week.")
            return "exit_menu"

        if not hustle_system.has_valid_role(caller):
            caller.msg("No hustle available for your role.")
            return "exit_menu"

        role = get_character_role(caller)
        rank = get_role_ability_rank(caller, role)
        tier = "1-4" if rank <= 4 else ("5-7" if rank <= 7 else "8-10")

        text = "|wThe Hustle|n\n"
        text += "You have a full seven days free. Time to earn some eb.\n\n"
        text += f"Your role: |c{role or 'Unknown'}|n\n"
        text += f"Role Ability Rank: |c{rank}|n (tier {tier})\n\n"
        text += "You'll roll 1d6 to determine what you did this week and how much you earned.\n"
        text += "Higher ranks mean better pay for the same outcome.\n\n"
        text += "Do you want to attempt your hustle?"

        options = (
            {"key": ("Yes", "y"), "desc": "Roll 1d6 and complete your hustle", "goto": "attempt_hustle"},
            {"key": ("No", "n"), "desc": "Return to the game", "goto": "exit_menu"},
        )
        return text, options
    except Exception as e:
        logger.log_trace(f"Error in hustle_menu for {caller.name}: {str(e)}")
        caller.msg("An error occurred while accessing the hustle menu. Please try again later or contact an admin.")
        return "exit_menu"


def attempt_hustle(caller):
    """Roll 1d6, look up result, pay character."""
    logger.log_info(f"Entering attempt_hustle for {caller.name}")
    try:
        hustle_system = get_or_create_hustle_system()
        if not hustle_system:
            caller.msg("Error: Unable to initialize the hustle system. Please contact an admin.")
            return None

        if not hustle_system.can_attempt_hustle(caller):
            caller.msg("You have already attempted your hustle this week. Please try again next week.")
            return None

        success, message, roll, rank, eb = hustle_system.attempt_hustle(caller)
        if not success:
            caller.msg(message)
            return None

        result_text = "|wHustle Complete|n\n"
        result_text += f"Roll: 1d6 = |c{roll}|n\n"
        result_text += f"Role Ability Rank: |c{rank}|n\n"
        result_text += f"Result: {message}\n"
        caller.msg(result_text)
        logger.log_info(f"Hustle result for {caller.name}: roll={roll}, rank={rank}, eb={eb}")

        return None  # End EvMenu
    except Exception as e:
        logger.log_trace(f"Error in attempt_hustle for {caller.name}: {str(e)}\n{traceback.format_exc()}")
        caller.msg("An error occurred while attempting the hustle. Please try again later or contact an admin.")
        return None


def exit_menu(caller):
    logger.log_info(f"Exiting hustle menu for {caller.name}")
    caller.msg("Exiting hustle menu.")
    return None


class CmdHustle(Command):
    """
    Access the weekly hustle menu.

    Usage:
      hustle

    Spend a full seven days working a side job. Your pay depends on your
    Role, Role Ability Rank, and a 1d6 roll (Cyberpunk Red rules as written).
    """
    key = "hustle"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before doing hustles.")
            return
        logger.log_info(f"{self.caller.name} is accessing the hustle menu")
        EvMenu(self.caller, "commands.hustle_commands", startnode="hustle_menu", cmd_on_exit=None)


class CmdClearHustleAttempt(Command):
    """
    Clear the current hustle attempt for a character.

    Usage:
      clearhustle <character_name>

    Admin-only. Clears the hustle attempt for a character, allowing them
    to attempt another hustle before the weekly reset.
    """
    key = "clearhustle"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: clearhustle <character_name>")
            return

        target = self.caller.search(self.args, global_search=True)
        if not target:
            return

        hustle_system = get_or_create_hustle_system()
        if not hustle_system:
            self.caller.msg("Error: Unable to initialize the hustle system.")
            return

        if target.id in hustle_system.db.last_attempt:
            del hustle_system.db.last_attempt[target.id]
            self.caller.msg(f"Cleared hustle attempt for {target.name}.")
            logger.log_info(f"Admin {self.caller.name} cleared hustle attempt for {target.name}")
        else:
            self.caller.msg(f"{target.name} has no recorded hustle attempt.")


class CmdResetHustles(Command):
    """
    Reset all hustle attempts (weekly reset).

    Usage:
      resethustles

    Admin-only. Resets hustle attempt tracking for everyone, as if a new
    week has started. Useful for testing.
    """
    key = "resethustles"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        hustle_system = get_or_create_hustle_system()
        if not hustle_system:
            self.caller.msg("Error: Unable to initialize the hustle system.")
            return
        hustle_system.db.last_attempt = {}
        self.caller.msg("All hustle attempts have been reset. Everyone can attempt a hustle.")
        logger.log_info(f"Admin {self.caller.name} reset all hustle attempts")


class CmdDebugHustle(Command):
    """
    Debug the hustle system for a character.

    Usage:
      debughustle <character_name>

    Admin-only. Shows role, Role Ability Rank, and hustle eligibility.
    """
    key = "debughustle"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: debughustle <character_name>")
            return

        target = self.caller.search(self.args, global_search=True)
        if not target:
            return

        hustle_system = get_or_create_hustle_system()
        if not hustle_system:
            self.caller.msg("Error: Unable to initialize the hustle system.")
            return

        role = get_character_role(target)
        rank = get_role_ability_rank(target, role) if role else 0

        debug_info = [
            f"Debug for {target.name}:",
            f"  Role: {role or 'None'}",
            f"  Role Ability Rank: {rank}",
            f"  Has valid role: {hustle_system.has_valid_role(target)}",
            f"  Can attempt hustle: {hustle_system.can_attempt_hustle(target)}",
            f"  Last attempt: {hustle_system.db.last_attempt.get(target.id, 'Never')}",
        ]
        self.caller.msg("\n".join(debug_info))
