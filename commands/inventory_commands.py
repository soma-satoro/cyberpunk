from evennia import Command
from evennia.utils.ansi import ANSIString
from evennia.commands.default.muxcommand import MuxCommand
from world.cyberpunk_sheets.models import CharacterSheet
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
      inv/balance - shows your Eurodollars and Night City Reputation

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

class CmdEquip(Command):
    """
    Admin equipment commands.

    Usage:
      equip/add <player>=<item> - Give a player an item from the database
      equip/remove <player>=<item> - Remove an item from a player's inventory

    """

    key = "equip"
    aliases = ["equipment"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: equip/add <player>=<item> or equip/remove <player>=<item>")
            return

        if "add" in self.args:
            self.add_item()
        elif "remove" in self.args:
            self.remove_item()
    
    def add_item(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: equip/add <player>=<item>")
            return
        
        player_name, item_name = self.args.split(None, 1)
        player = self.caller.search(player_name)
        if not player:
            return

        item = self.caller.search(item_name)
        if not item:
            self.caller.msg(f"Item '{item_name}' does not exist.")
            return
        
        if item.type == "weapon":
            self.add_weapon()
        elif item.type == "armor":
            self.add_armor()
        elif item.type == "gear":
            self.add_gear()
        else:
            self.caller.msg(f"Item '{item_name}' is not a valid weapon, armor, or gear.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return
        
        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.weapons.add(item)
        self.caller.msg(f"Added {item.name} to {player.name}'s inventory.")
        player.msg(f"A {item.name} has been added to your inventory.")

    def remove_item(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: equip/remove <player>=<item>")
            return

        player_name, item_name = self.args.split(None, 1)
        player = self.caller.search(player_name)
        if not player:
            return
        
        try:
            item = Weapon.objects.get(name__iexact=item_name.strip('"'))
        except Weapon.DoesNotExist:
            self.caller.msg(f"Weapon '{item_name}' does not exist.")
            return
        
        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return
        
        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.weapons.remove(item)
        self.caller.msg(f"Removed {item.name} from {player.name}'s inventory.")
        player.msg(f"A {item.name} has been removed from your inventory.")

    def add_weapon(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: addweapon <player> <weapon_name>")
            return

        player_name, weapon_name = self.args.split(None, 1)
        player = self.caller.search(player_name)
        if not player:
            return

        try:
            weapon = Weapon.objects.get(name__iexact=weapon_name.strip('"'))
        except Weapon.DoesNotExist:
            self.caller.msg(f"Weapon '{weapon_name}' does not exist.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.weapons.add(weapon)
        self.caller.msg(f"Added {weapon.name} to {player.name}'s inventory.")
        player.msg(f"A {weapon.name} has been added to your inventory.")

    def add_armor(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: addarmor <player> <armor_name>")
            return

        player_name, armor_name = self.args.split(None, 1)
        player = self.caller.search(player_name)
        if not player:
            return

        try:
            armor = Armor.objects.get(name__iexact=armor_name.strip('"'))
        except Armor.DoesNotExist:
            self.caller.msg(f"Armor '{armor_name}' does not exist.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.armor.add(armor)
        self.caller.msg(f"Added {armor.name} to {player.name}'s inventory.")
        player.msg(f"A {armor.name} has been added to your inventory.")

    def add_gear(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: addgear <player> <gear_name>")
            return

        player_name, gear_name = self.args.split(None, 1)
        player = self.caller.search(player_name)
        if not player:
            return

        try:
            gear = Gear.objects.get(name__iexact=gear_name.strip('"'))
        except Gear.DoesNotExist:
            self.caller.msg(f"Gear '{gear_name}' does not exist.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        inventory, created = Inventory.objects.get_or_create(character=character_sheet)
        inventory.gear.add(gear)
        self.caller.msg(f"Added {gear.name} to {player.name}'s inventory.")
        player.msg(f"A {gear.name} has been added to your inventory.")