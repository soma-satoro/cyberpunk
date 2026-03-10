from evennia import Command
from evennia.utils.ansi import ANSIString
from evennia.commands.default.muxcommand import MuxCommand
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import Weapon, Armor, Gear, Inventory, Ammunition, CyberwareInstance
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from world.utils.formatting import sheet_header, sheet_section, footer
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

        if self.switches and "equip" in self.switches:
            self.equip_item()
            return
        if self.switches and "unequip" in self.switches:
            self.unequip_item()
            return

        inv = character_sheet.inventory
        W = 80
        display_name = getattr(self.caller.db, 'full_name', None) or self.caller.name

        output = sheet_header(f"Inventory for {display_name}", width=W)

        # Currency and Reputation
        balance = CharacterSheetMoneyService.get_balance(character_sheet)
        logger.info(f"Retrieved balance for character sheet ID {character_sheet.id}: {balance}")
        output += sheet_section("Currency and Reputation", width=W)
        output += f"|yCurrent Bank Balance:|n |w{balance} Eurodollars|n\n"
        rep = character_sheet.rep
        pts = getattr(character_sheet, 'reputation_points', 0) or 0
        if rep >= 10:
            rep_str = f"Rank {rep} ({pts} pts, max rank)"
        else:
            next_threshold = (rep + 1) * 100
            pts_needed = next_threshold - pts
            rep_str = f"Rank {rep} ({pts} pts, {pts_needed} to Rank {rep + 1})"
        output += f"|yNight City Rep:|n |w{rep_str}|n\n"
        noto = getattr(character_sheet, 'notoriety', 0) or 0
        noto_pts = getattr(character_sheet, 'notoriety_points', 0) or 0
        if noto >= 10:
            noto_str = f"Rank {noto} ({noto_pts} pts, max rank)"
        elif noto_pts > 0:
            next_threshold = (noto + 1) * 100
            pts_needed = next_threshold - noto_pts
            noto_str = f"Rank {noto} ({noto_pts} pts, {pts_needed} to Rank {noto + 1})"
        else:
            noto_str = "None"
        output += f"|yNight City Notoriety:|n |w{noto_str}|n\n\n"

        # Weapons
        output += sheet_section("Weapons", width=W)
        weapons = inv.weapons.all()
        if weapons:
            output += f"|y{'Weapon':<25}{'Damage':<20}{'ROF':<20}|n\n"
            for weapon in weapons:
                output += f"|w{weapon.name:<25}{weapon.damage or 'N/A':<20}{weapon.rof or 'N/A':<20}|n\n"
        else:
            output += "|wNo weapons in inventory.|n\n"
        output += "\n"

        # Armor
        output += sheet_section("Armor", width=W)
        armors = inv.armor.all()
        if armors:
            output += f"|y{'Armor':<20}{'SP':<15}{'EV':<15}{'Locations':<20}|n\n"
            for armor in armors:
                output += f"|w{armor.name:<20}{str(armor.sp) if armor.sp is not None else 'N/A':<15}{armor.ev or 'N/A':<15}{armor.locations or 'N/A':<20}|n\n"
        else:
            output += "|wNo armor in inventory.|n\n"
        output += "\n"

        # Gear
        output += sheet_section("Gear", width=W)
        gears = inv.gear.all()
        if gears:
            output += f"|y{'Gear':<25}{'Category':<20}{'Description':<30}|n\n"
            for gear in gears:
                description = (gear.description[:27] + "...") if len(gear.description or "") > 30 else (gear.description or "")
                output += f"|w{gear.name:<25}{gear.category:<20}{description:<30}|n\n"
        else:
            output += "|wNo gear in inventory.|n\n"
        output += "\n"

        # Ammunition
        output += sheet_section("Ammunition", width=W)
        ammo = inv.ammunition.all()
        if ammo:
            output += f"|y{'Ammunition':<25}{'Weapon Type':<25}{'Quantity':<20}|n\n"
            for a in ammo:
                output += f"|w{a.name:<25}{a.weapon_type:<25}{a.quantity:<20}|n\n"
        else:
            output += "|wNo ammunition in inventory.|n\n"
        output += "\n"

        # Vehicles
        output += sheet_section("Vehicles", width=W)
        vehicles = inv.vehicles.all()
        if vehicles:
            output += f"|y{'Vehicle':<22}{'Category':<8}{'SDP':<6}{'Seats':<6}{'Speed':<18}{'Value':<10}|n\n"
            for v in vehicles:
                speed = (v.speed_narrative or "N/A")[:17]
                output += f"|w{v.name:<22}{v.category:<8}{v.sdp:<6}{v.seats:<6}{speed:<18}{v.value or 0:<10}|n\n"
        else:
            output += "|wNo vehicles in inventory.|n\n"
        output += "\n"

        # Cyberware
        output += sheet_section("Cyberware", width=W)
        cyberware = inv.cyberware.filter(installed=True)
        if cyberware:
            output += f"|y{'Cyberware':<25}{'Type':<18}{'Status':<15}{'Humanity Loss':<15}|n\n"
            for cw in cyberware:
                status = "Installed" if cw.installed else "Uninstalled"
                output += f"|w{cw.cyberware.name:<25}{cw.cyberware.type:<18}{status:<15}{cw.cyberware.humanity_loss:<15}|n\n"
        else:
            output += "|wNo cyberware in inventory.|n\n"
        output += "\n"

        # Vouchers (physical IC objects - hide concealed from self-view, they're always visible to owner)
        output += sheet_section("Vouchers", width=W)
        try:
            from typeclasses.vouchers import Voucher
            vouchers = [o for o in self.caller.contents if o.is_typeclass("typeclasses.vouchers.Voucher")]
            if vouchers:
                output += f"|y{'Voucher':<30}{'Items':<15}{'Locked':<10}|n\n"
                for v in vouchers:
                    items = v.get_items() if hasattr(v, 'get_items') else []
                    item_count = sum(it.get("quantity", 1) for it in items)
                    locked = "Yes" if (v.db.locked if hasattr(v, 'db') else False) else "No"
                    output += f"|w{v.key:<30}{item_count:<15}{locked:<10}|n\n"
            else:
                output += "|wNo vouchers in inventory.|n\n"
        except ImportError:
            pass

        output += footer(width=W, fillchar="-")
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
        player = self.caller.search(player_name, global_search=True)
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
        player = self.caller.search(player_name, global_search=True)
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
        player = self.caller.search(player_name, global_search=True)
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
        player = self.caller.search(player_name, global_search=True)
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
        player = self.caller.search(player_name, global_search=True)
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