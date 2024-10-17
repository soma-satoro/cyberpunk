from evennia import Command
from evennia.utils.ansi import ANSIString
from world.inventory.models import Weapon, Armor, Gear, Inventory, Ammunition
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from world.utils.formatting import header, footer, divider
from world.utils.character_utils import get_character_sheet
import logging

logger = logging.getLogger('cyberpunk.inventory')

class CmdInventory(Command):
    """
    Show character inventory

    Usage:
      inventory
      inv

    This command displays your character's inventory, including weapons, armor, and gear.
    """

    key = "inventory"
    aliases = ["inv"]
    lock = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        logger.info(f"Inventory command called for {self.caller.name}")
        character_sheet = get_character_sheet(self.caller)
        if not character_sheet:
            logger.warning(f"No character sheet found for {self.caller.name}")
            self.caller.msg("You don't have a character sheet. Please create one using the 'chargen' command.")
            return

        inv = character_sheet.inventory

        output = header(f"Inventory for {self.caller.name}", width=78, fillchar="|m-|n") + "\n"

        # Display balance and rep
        balance = CharacterSheetMoneyService.get_balance(character_sheet)
        logger.info(f"Retrieved balance for character sheet ID {character_sheet.id}: {balance}")
        output += divider("Currency and Reputation", width=78, fillchar="|m-|n") + "\n"
        output += f"|cCurrent Bank Balance:|n {balance} Eurodollars\n"
        output += f"|cNight City Rep:|n Rank {character_sheet.rep}\n\n"

        # Weapons
        output += divider("Weapons", width=78, fillchar="|m-|n") + "\n"
        output += f"|c{'Weapon':<25}{'Damage':<20}{'ROF':<20}|n\n"
        weapons = inv.weapons.all()
        if weapons:
            for weapon in weapons:
                output += f"{weapon.name:<25}{weapon.damage or 'N/A':<20}{weapon.rof or 'N/A':<20}\n"
        else:
            output += "No weapons in inventory.\n"
        output += "\n"

        # Armor
        output += divider("Armor", width=78, fillchar="|m-|n") + "\n"
        output += f"|c{'Armor':<20}{'SP':<15}{'EV':<15}{'Locations':<20}|n\n"
        armors = inv.armor.all()
        if armors:
            for armor in armors:
                output += f"{armor.name:<20}{armor.sp or 'N/A':<15}{armor.ev or 'N/A':<15}{armor.locations or 'N/A':<20}\n"
        else:
            output += "No armor in inventory.\n"
        output += "\n"

        # Gear
        output += divider("Gear", width=78, fillchar="|m-|n") + "\n"
        output += f"|c{'Gear':<25}{'Category':<20}{'Description':<30}|n\n"
        gears = inv.gear.all()
        if gears:
            for gear in gears:
                description = gear.description[:27] + "..." if len(gear.description) > 30 else gear.description
                output += f"{gear.name:<25}{gear.category:<20}{description:<30}\n"
        else:
            output += "No gear in inventory.\n"
        output += "\n"

        # Ammunition
        output += divider("Ammunition", width=78, fillchar="|m-|n") + "\n"
        output += f"|c{'Ammunition':<25}{'Weapon Type':<25}{'Quantity':<20}|n\n"
        ammo = inv.ammunition.all()
        if ammo:
            for a in ammo:
                output += f"{a.name:<25}{a.weapon_type:<25}{a.quantity:<20}\n"
        else:
            output += "No ammunition in inventory.\n"
        output += "\n"

        output += footer(width=78, fillchar="|m-|n")
        self.caller.msg(output)

class CmdEquipment(Command):
    """
    Show character equipment

    Usage:
      equipment
      eq

    This command displays your character's equipped weapons, armor, and gear.
    """

    key = "equipment"
    aliases = ["eq"]
    lock = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        # Implementation similar to CmdInventory, but focusing on equipped items
        pass
