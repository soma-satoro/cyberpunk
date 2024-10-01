from evennia import Command
from evennia.utils.evmenu import EvMenu
from world.hustle_system import get_or_create_hustle_system
from evennia.utils import logger
import traceback

def hustle_menu(caller):
    logger.log_info(f"Entering hustle_menu for {caller.name}")
    try:
        hustle_system = get_or_create_hustle_system()
        if not hustle_system:
            logger.log_err(f"Failed to initialize hustle system for {caller.name}")
            caller.msg("Error: Unable to initialize the hustle system. Please contact an admin.")
            return "exit_menu"

        if not hasattr(hustle_system, 'can_attempt_hustle'):
            logger.log_err(f"HustleSystem instance is invalid for {caller.name}")
            caller.msg("Error: The hustle system is not properly initialized. Please contact an admin.")
            return "exit_menu"

        if not hustle_system.can_attempt_hustle(caller):
            caller.msg("You have already attempted your hustle this week. Please try again next week.")
            return "exit_menu"

        hustle = hustle_system.get_available_hustle(caller)

        if not hustle:
            logger.log_info(f"No hustle available for {caller.name}")
            caller.msg("No hustle available for your role.")
            return "exit_menu"

        text = f"Available Hustle: {hustle['name']}\n"
        text += f"Difficulty: {hustle['difficulty']}\n"
        text += f"Potential Payout: {hustle['payout']} eb\n\n"
        text += "Do you want to attempt this hustle?"

        options = (
            {"key": ("Yes", "y"), "desc": "Attempt the hustle", "goto": "attempt_hustle"},
            {"key": ("No", "n"), "desc": "Return to the game", "goto": "exit_menu"},
        )

        return text, options
    except Exception as e:
        logger.log_trace(f"Error in hustle_menu for {caller.name}: {str(e)}")
        caller.msg("An error occurred while accessing the hustle menu. Please try again later or contact an admin.")
        return "exit_menu"

def attempt_hustle(caller):
    logger.log_info(f"Entering attempt_hustle for {caller.name}")
    try:
        hustle_system = get_or_create_hustle_system()
        if not hustle_system:
            logger.log_err(f"Failed to initialize hustle system for {caller.name} during attempt")
            caller.msg("Error: Unable to initialize the hustle system. Please contact an admin.")
            return None

        if not hustle_system.can_attempt_hustle(caller):
            caller.msg("You have already attempted your hustle this week. Please try again next week.")
            return None

        hustle = hustle_system.get_available_hustle(caller)
        
        if not hustle:
            logger.log_err(f"No hustle available for {caller.name} with role {caller.character_sheet.role} during attempt")
            caller.msg("Error: No hustle available. Please contact an admin.")
            return None
        
        logger.log_info(f"Attempting hustle for {caller.name}: {hustle['name']}")
        success, message, total_roll, cool_value, role_ability_value = hustle_system.attempt_hustle(caller, hustle)
        
        dice_roll = total_roll - cool_value - role_ability_value
        
        result_text = f"Hustle: {hustle['name']} (Difficulty: {hustle['difficulty']})\n"
        result_text += f"Roll: Cool ({cool_value}) + Role Ability ({role_ability_value}) + 1d10 ({dice_roll}) = {total_roll}\n"
        result_text += message
        
        caller.msg(result_text)
        logger.log_info(f"Hustle attempt result for {caller.name}: {'Success' if success else 'Failure'}")
        
        return None  # This will end the EvMenu
    except Exception as e:
        error_msg = f"Error in attempt_hustle for {caller.name}: {str(e)}\n{traceback.format_exc()}"
        logger.log_trace(error_msg)
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

    This command opens the hustle menu, where you can view and attempt
    your character's weekly side job based on their role.
    """
    key = "hustle"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        logger.log_info(f"{self.caller.name} is accessing the hustle menu")
        EvMenu(self.caller, "commands.hustle_commands", startnode="hustle_menu", cmd_on_exit=None)

class CmdClearHustleAttempt(Command):
    """
    Clear the current hustle attempt for a character.

    Usage:
      clearhustle <character_name>

    This admin-only command allows clearing the hustle attempt for a specific character,
    allowing them to attempt another hustle before the weekly reset.
    """
    key = "clearhustle"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: clearhustle <character_name>")
            return

        target = self.caller.search(self.args)
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

class CmdRegenerateHustles(Command):
    """
    Force regeneration of hustles for all roles.

    Usage:
      regenhusts

    This admin-only command forces the hustle system to regenerate hustles for all roles.
    """
    key = "regenhusts"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        hustle_system = get_or_create_hustle_system()
        if not hustle_system:
            self.caller.msg("Error: Unable to initialize the hustle system.")
            return

        hustle_system.generate_hustles()
        self.caller.msg("Hustles have been regenerated for all roles.")
        logger.log_info(f"Admin {self.caller.name} forced hustle regeneration")

class CmdDebugHustle(Command):
    """
    Debug the hustle system for a character.

    Usage:
      debughustle <character_name>

    This admin-only command provides debug information about a character's hustle status.
    """
    key = "debughustle"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: debughustle <character_name>")
            return

        target = self.caller.search(self.args)
        if not target:
            return

        hustle_system = get_or_create_hustle_system()
        if not hustle_system:
            self.caller.msg("Error: Unable to initialize the hustle system.")
            return

        debug_info = [
            f"Debug information for {target.name}:",
            f"Has character sheet: {hasattr(target, 'character_sheet')}",
        ]

        if hasattr(target, 'character_sheet'):
            cs = target.character_sheet
            debug_info.extend([
                f"Role: {cs.role}",
                f"Cool: {getattr(cs, 'cool', 'N/A')}",
                f"Role Ability: {getattr(cs, cs.role_ability, 'N/A') if hasattr(cs, 'role_ability') else 'N/A'}",
            ])

        debug_info.extend([
            f"Last hustle attempt: {hustle_system.db.last_attempt.get(target.id, 'Never')}",
            f"Can attempt hustle: {hustle_system.can_attempt_hustle(target)}",
        ])

        hustle = hustle_system.get_available_hustle(target)
        if hustle:
            debug_info.extend([
                "Available Hustle:",
                f"  Name: {hustle['name']}",
                f"  Difficulty: {hustle['difficulty']}",
                f"  Payout: {hustle['payout']} eb",
            ])
        else:
            debug_info.append("No available hustle found.")

        debug_info.append(f"All available hustles: {hustle_system.db.available_hustles}")

        self.caller.msg("\n".join(debug_info))
