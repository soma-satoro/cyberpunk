from evennia import Command
from evennia.utils.ansi import ANSIString
from evennia.commands.default.muxcommand import MuxCommand
from world.inventory.models import Weapon, Armor, Gear, Inventory, Ammunition
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from world.utils.formatting import header, footer, divider
from world.utils.character_utils import get_character_sheet
import logging

logger = logging.getLogger('cyberpunk.inventory')

class CmdInventory(MuxCommand):
    """
    Show character inventory

    Usage:
      <inv>entory - shows your inventory
      inv <character> - shows another character's inventory (staff/GM only)
      inv/equip - equips an item
      inv/unequip - unequips an item

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

        if self.switches.get("equip"):
            self.equip_item()
        elif self.switches.get("unequip"):
            self.unequip_item()
        else:
            self.show_inventory()

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
        
    def equip_item(self):
        if not self.args:
            self.caller.msg("Usage: equip <weapon name>")
            return

        weapon_name = self.args.strip().lower()

        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = self.caller.character_sheet
        
        if not hasattr(sheet, 'inventory'):
            self.caller.msg("You don't have an inventory.")
            return

        inventory = sheet.inventory

        try:
            weapon = inventory.weapons.get(name__iexact=weapon_name)
        except Weapon.DoesNotExist:
            self.caller.msg(f"You don't have a weapon named '{weapon_name}' in your inventory.")
            return
        except Weapon.MultipleObjectsReturned:
            self.caller.msg(f"You have multiple weapons named '{weapon_name}'. Please be more specific.")
            return

        sheet.eqweapon = weapon
        sheet.save()

        self.caller.msg(f"You have equipped {weapon.name}.")

    def unequip_item(self):
        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = self.caller.character_sheet
        
        if not sheet.eqweapon:
            self.caller.msg("You don't have any weapon equipped.")
            return

        weapon_name = sheet.eqweapon.name
        sheet.eqweapon = None
        sheet.save()

        self.caller.msg(f"You have unequipped your {weapon_name}.")
