from evennia import Command
from evennia.utils.evtable import EvTable
from world.inventory.models import Weapon, Armor, Inventory
from world.cyberpunk_sheets.models import CharacterSheet
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from typeclasses.rental import RentableRoom
from evennia.utils import delay
import logging

logger = logging.getLogger('cyberpunk.economy')

class CmdBalance(Command):
    """
    Check your Eurodollar balance

    Usage:
      balance
      money
    """

    key = "balance"
    aliases = ["creds"]
    lock = "cmd:all()"
    help_category = "Economy"

    def func(self):
        logger.info(f"Balance command called for {self.caller.name}")
        character_sheet = self.caller.character_sheet
        if not character_sheet:
            logger.warning(f"No character sheet found for {self.caller.name}")
            self.caller.msg("You don't have a character sheet!")
            return

        balance = CharacterSheetMoneyService.get_balance(character_sheet)
        logger.info(f"Retrieved balance for character sheet ID {character_sheet.id}: {balance}")
        self.caller.msg(f"You have {balance} Eurodollars.")


class CmdGiveMoney(Command):
    """
    Give Eurodollars to another character

    Usage:
      transfer <amount> to <character>
    """

    key = "transfer"
    lock = "cmd:all()"
    help_category = "Economy"

    def func(self):
        if not self.args or "to" not in self.args:
            self.caller.msg("Usage: transfer <amount> to <character>")
            return

        amount, target = self.args.split("to")
        try:
            amount = int(amount.strip())
        except ValueError:
            self.caller.msg("Please provide a valid amount.")
            return

        target = self.caller.search(target.strip())
        if not target:
            return

        if not hasattr(self.caller, 'character_sheet') or not hasattr(target, 'character_sheet'):
            self.caller.msg("Both you and the target must have character sheets!")
            return

        giver_cs = self.caller.character_sheet
        receiver_cs = target.character_sheet

        if giver_cs.spend_money(amount):
            receiver_cs.add_money(amount)
            self.caller.msg(f"You give {amount} Eurodollars to {target.name}.")
            target.msg(f"{self.caller.name} gives you {amount} Eurodollars.")
        else:
            self.caller.msg("You don't have enough Eurodollars.")


class CmdAdminMoney(Command):
    """
    Admin command to add or remove Eurodollars from a character

    Usage:
      money <character> = <amount>

    Use a positive amount to add money, negative to remove.
    """

    key = "money"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: money <character> = <amount>")
            return

        target, amount = [part.strip() for part in self.args.split("=")]
        target = self.caller.search(target)
        if not target:
            return

        try:
            amount = int(amount)
        except ValueError:
            self.caller.msg("Please provide a valid amount.")
            return

        if not hasattr(target, 'character_sheet'):
            self.caller.msg(f"No character sheet found for {target.name}.")
            return

        sheet = target.character_sheet
        if isinstance(sheet, CharacterSheet):
            target_cs = sheet
        else:
            try:
                target_cs = CharacterSheet.objects.get(id=sheet)
            except CharacterSheet.DoesNotExist:
                self.caller.msg(f"No character sheet found with ID {sheet} for {target.name}.")
                return

        if amount >= 0:
            new_balance = CharacterSheetMoneyService.add_money(target_cs, amount)
            self.caller.msg(f"Added {amount} Eurodollars to {target.name}'s account. New balance: {new_balance}")
            target.msg(f"An admin has added {amount} Eurodollars to your account. New balance: {new_balance}")
        else:
            if CharacterSheetMoneyService.spend_money(target_cs, abs(amount)):
                new_balance = CharacterSheetMoneyService.get_balance(target_cs)
                self.caller.msg(f"Removed {abs(amount)} Eurodollars from {target.name}'s account. New balance: {new_balance}")
                target.msg(f"An admin has removed {abs(amount)} Eurodollars from your account. New balance: {new_balance}")
            else:
                self.caller.msg(f"{target.name} doesn't have enough Eurodollars to remove {abs(amount)}.")

        self.caller.msg(f"Current balance for {target.name}: {CharacterSheetMoneyService.get_balance(target_cs)} Eurodollars")

class CmdRentRoom(Command):
    """
    Rent a room
    
    Usage:
      rent [<room name>]
    
    Attempts to rent the specified room or the current room for your character.
    """

    key = "rent"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        caller = self.caller
        if self.args:
            room = caller.search(self.args, global_search=True)
        else:
            room = caller.location

        if not room or not isinstance(room, RentableRoom):
            caller.msg("That doesn't seem to be a rentable room.")
            return
        
        success, message = room.rent_to(caller)
        caller.msg(message)
        if success and room.db.is_temporary:
            # Cancel any scheduled destruction for temporary rooms
            for script in room.scripts.all():
                if script.key == "check_and_destroy":
                    script.stop()

class CmdLeaveRental(Command):
    """
    Leave your current rental
    
    Usage:
      leaverental
    
    Allows you to leave your current rented room.
    """

    key = "leaverental"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        caller = self.caller
        rented_room = caller.attributes.get('rented_room', None)

        if not rented_room:
            caller.msg("You are not currently renting any room.")
            return

        success, message = rented_room.leave_rental(caller)
        caller.msg(message)

        if success:
            caller.move_to(rented_room.location, quiet=True)
            caller.msg(f"You have been moved out of {rented_room.name}.")
            if rented_room.db.is_temporary:
                # Schedule room destruction for temporary rooms
                delay(300, rented_room.check_and_destroy)