from evennia import Command
from django.utils import timezone
from datetime import timedelta
from evennia.utils.evtable import EvTable
from world.inventory.models import Weapon, Armor, Gear, Inventory
from world.cyberware.models import Cyberware
from world.equipment_data import populate_weapons, populate_armor, populate_gear, populate_all_equipment
from world.cyberpunk_sheets.models import CharacterSheet
from world.cyberware.utils import populate_cyberware


class CmdAddWeapon(Command):
    """
    Add a weapon to a player's inventory.

    Usage:
      addweapon <player> <weapon_name>

    Example:
      addweapon Bob "Medium Pistol"
    """
    key = "addweapon"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
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

class CmdAddArmor(Command):
    """
    Add armor to a player's inventory.

    Usage:
      addarmor <player> <armor_name>

    Example:
      addarmor Alice "Leather Jacket"
    """
    key = "addarmor"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
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

class CmdAddGear(Command):
    """
    Add gear to a player's inventory.

    Usage:
      addgear <player> <gear_name>

    Example:
      addgear Charlie "Agent"
    """
    key = "addgear"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
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

class CmdPopulateWeapons(Command):
    """
    Populate the database with weapons from Cyberpunk RED.

    Usage:
      populate_weapons

    This command should only be run once to initialize the weapon database.
    """

    key = "populate_weapons"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        populate_weapons()
        self.caller.msg("Weapon database populated successfully.")

class CmdPopulateArmor(Command):
    """
    Populate the database with armor from Cyberpunk RED.

    Usage:
      populate_armor

    This command should only be run once to initialize the armor database.
    """

    key = "populate_armor"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        populate_armor()
        self.caller.msg("Armor database populated successfully.")

class CmdPopulateGear(Command):
    """
    Populate the database with gear from Cyberpunk RED.

    Usage:
      populate_gear

    This command should only be run once to initialize the gear database.
    """

    key = "populate_gear"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        populate_gear()
        self.caller.msg("Gear database populated successfully.")

class CmdPopulateAllEquipment(Command):
    """
    Populate the database with all equipment from Cyberpunk RED.

    Usage:
      populate_all_equipment

    This command should only be run once to initialize the entire equipment database.
    """

    key = "populate_all_equipment"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        populate_all_equipment()
        self.caller.msg("All equipment databases populated successfully.")

class CmdDepopulateAllEquipment(Command):
    """
    Remove all equipment from the database.

    Usage:
      depopulate_all_equipment
      depopulate_all_equipment yes

    This command will delete all weapons, armor, gear, and cyberware from the database.
    Use with caution as this action cannot be undone.
    """

    key = "depopulate_all_equipment"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        now = timezone.now()
        confirmation_timeout = timedelta(minutes=1)

        # Debug information
        self.caller.msg(f"Debug: Args received: '{self.args}'")
        self.caller.msg(f"Debug: Confirmation time: {self.caller.attributes.get('confirm_depopulate_time', 'Not set')}")

        if self.caller.attributes.has("confirm_depopulate_time"):
            confirm_time = self.caller.attributes.get("confirm_depopulate_time")
            if now - confirm_time > confirmation_timeout:
                self.caller.attributes.remove("confirm_depopulate_time")
                self.caller.msg("Confirmation timeout. Please start over if you want to depopulate equipment.")
                return

            if self.args and self.args.strip().lower() == "yes":
                # Confirmed, proceed with deletion
                Weapon.objects.all().delete()
                Armor.objects.all().delete()
                Gear.objects.all().delete()
                Cyberware.objects.all().delete()
                
                self.caller.msg("All equipment has been deleted from the database.")
                self.caller.attributes.remove("confirm_depopulate_time")
                return

        # If we get here, either it's the first run or confirmation failed
        self.caller.msg("Are you sure you want to delete all equipment? This cannot be undone.")
        self.caller.msg("Type 'depopulate_all_equipment yes' within the next minute to confirm, or anything else to cancel.")
        
        # Set the confirmation time
        self.caller.attributes.add("confirm_depopulate_time", now)

class CmdYes(Command):
    """
    Confirm an action that requires confirmation.
    """

    key = "yes"
    locks = "cmd:all()"

    def func(self):
        if self.caller.db.confirm_depopulate:
            self.caller.db.confirm_depopulate(self.caller, "yes", "yes")
            del self.caller.db.confirm_depopulate
        else:
            self.caller.msg("There's nothing to confirm right now.")

class CmdPopulateCyberware(Command):
    """
    Populate the database with all cyberware from Cyberpunk RED.
    Usage:
      populate_cyberware
    This command should only be run once to initialize the entire cyberware database.
    """
    key = "populate_cyberware"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        try:
            populate_cyberware()
            self.caller.msg("All cyberware populated successfully.")
        except Exception as e:
            self.caller.msg(f"An error occurred while populating cyberware: {str(e)}")

class CmdViewEquipment(Command):
    """
    View all equipment in the database.

    Usage:
      equipment [type]

    Options:
      type - Optional. Can be 'weapons', 'armor', or 'gear'.
             If not specified, shows all equipment.

    Examples:
      equipdb
      equipdb weapons
      equipdb armor
      equipdb gear
    """

    key = "equipdb"
    aliases = ["itemsdb"]
    lock = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        if self.args and self.args.strip().lower() not in ['weapons', 'armor', 'gear']:
            self.caller.msg("Invalid equipment type. Use 'weapons', 'armor', or 'gear'.")
            return

        if not self.args or self.args.strip().lower() == 'weapons':
            self.display_weapons()
        
        if not self.args or self.args.strip().lower() == 'armor':
            self.display_armor()
        
        if not self.args or self.args.strip().lower() == 'gear':
            self.display_gear()

    def display_weapons(self):
        weapons = Weapon.objects.all()
        if not weapons:
            self.caller.msg("No weapons found in the database.")
            return
        
        table = EvTable("Name", "Damage", "ROF", "Hands", "Concealable", "Weight", "Value", border="cells")
        for weapon in weapons:
            table.add_row(
                weapon.name,
                weapon.damage,
                weapon.rof,
                weapon.hands,
                "Yes" if weapon.concealable else "No",
                weapon.weight,
                f"{weapon.value} eb"
            )
        
        self.caller.msg("|cWeapons:|n")
        self.caller.msg(table)

    def display_armor(self):
        armors = Armor.objects.all()
        if not armors:
            self.caller.msg("No armor found in the database.")
            return
        
        table = EvTable("Name", "SP", "EV", "Locations", "Weight", "Value", border="cells")
        for armor in armors:
            table.add_row(
                armor.name,
                armor.sp,
                armor.ev,
                armor.locations,
                armor.weight,
                f"{armor.value} eb"
            )
        
        self.caller.msg("|cArmor:|n")
        self.caller.msg(table)

    def display_gear(self):
        gears = Gear.objects.all()
        if not gears:
            self.caller.msg("No gear found in the database.")
            return
        
        table = EvTable("Name", "Category", "Description", "Weight", "Value", border="cells")
        for gear in gears:
            table.add_row(
                gear.name,
                gear.category,
                gear.description[:30] + "..." if len(gear.description) > 30 else gear.description,
                gear.weight,
                f"{gear.value} eb"
            )
        
        self.caller.msg("|cGear:|n")
        self.caller.msg(table)

class CmdRemoveEquipment(Command):
    """
    Remove a weapon, armor, or gear from a player's inventory.

    Usage:
      removeequip <player> <equipment_type> <equipment_name>

    Equipment types:
      weapon, armor, gear

    Examples:
      removeequip Bob weapon "Medium Pistol"
      removeequip Alice armor "Leather Jacket"
      removeequip Charlie gear "Agent"
    """
    key = "removeequip"
    aliases = ["remove_equipment", "remequip"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or len(self.args.split()) < 3:
            self.caller.msg("Usage: removeequip <player> <equipment_type> <equipment_name>")
            return

        player_name, equipment_type, equipment_name = self.args.split(None, 2)
        player = self.caller.search(player_name)
        if not player:
            return

        equipment_type = equipment_type.lower()
        if equipment_type not in ['weapon', 'armor', 'gear']:
            self.caller.msg("Invalid equipment type. Use 'weapon', 'armor', or 'gear'.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(account=player.account)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{player.name} doesn't have a character sheet.")
            return

        inventory, created = Inventory.objects.get_or_create(character=character_sheet)

        if equipment_type == 'weapon':
            self.remove_weapon(inventory, equipment_name, player)
        elif equipment_type == 'armor':
            self.remove_armor(inventory, equipment_name, player)
        elif equipment_type == 'gear':
            self.remove_gear(inventory, equipment_name, player)

    def remove_weapon(self, inventory, weapon_name, player):
        try:
            weapon = inventory.weapons.get(name__iexact=weapon_name.strip('"'))
            inventory.weapons.remove(weapon)
            self.caller.msg(f"Removed {weapon.name} from {player.name}'s inventory.")
            player.msg(f"A {weapon.name} has been removed from your inventory.")
        except Weapon.DoesNotExist:
            self.caller.msg(f"Weapon '{weapon_name}' not found in {player.name}'s inventory.")

    def remove_armor(self, inventory, armor_name, player):
        try:
            armor = inventory.armor.get(name__iexact=armor_name.strip('"'))
            inventory.armor.remove(armor)
            self.caller.msg(f"Removed {armor.name} from {player.name}'s inventory.")
            player.msg(f"A {armor.name} has been removed from your inventory.")
        except Armor.DoesNotExist:
            self.caller.msg(f"Armor '{armor_name}' not found in {player.name}'s inventory.")

    def remove_gear(self, inventory, gear_name, player):
        try:
            gear = inventory.gear.get(name__iexact=gear_name.strip('"'))
            inventory.gear.remove(gear)
            self.caller.msg(f"Removed {gear.name} from {player.name}'s inventory.")
            player.msg(f"A {gear.name} has been removed from your inventory.")
        except Gear.DoesNotExist:
            self.caller.msg(f"Gear '{gear_name}' not found in {player.name}'s inventory.")