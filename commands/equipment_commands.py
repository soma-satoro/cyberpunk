from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand
from django.utils import timezone
from datetime import timedelta
from world.inventory.models import Weapon, Armor, Gear, Ammunition, Cyberdeck, Inventory
from world.cyberware.models import Cyberware
from world.equipment_data import populate_weapons, populate_armor, populate_gear, populate_all_equipment
from world.cyberpunk_sheets.models import CharacterSheet
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider, format_stat
from world.cyberware.utils import populate_cyberware
from evennia.utils.ansi import ANSIString
from evennia.utils import evtable
from math import ceil

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

class CmdViewEquipment(MuxCommand):
    """
    View all equipment in the database.

    Usage:
      equipment [type]

    Options:
      type - Optional. Can be 'weapons', 'armor', 'gear', 'ammo', or 'cyberdecks'.
             If not specified, shows all equipment.
    """

    key = "equipdb"
    aliases = ["itemsdb"]
    lock = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        valid_types = ['weapons', 'armor', 'gear', 'ammo', 'cyberdecks']
        if self.args and self.args.strip().lower() not in valid_types:
            self.caller.msg(f"Invalid equipment type. Use one of: {', '.join(valid_types)}.")
            return

        output = []

        if not self.args:
            for equip_type in valid_types:
                output.append(getattr(self, f"display_{equip_type}")())
        else:
            output.append(getattr(self, f"display_{self.args.strip().lower()}")())

        self.caller.msg("\n".join(filter(None, output)))

    def display_weapons(self):
        weapons = Weapon.objects.all()
        if not weapons:
            return divider("Weapons", width=80, fillchar="|m-|n") + "\nNo weapons found in the database.\n"
        
        output = [divider("Weapons", width=80, fillchar="|m-|n")]
        for weapon in weapons:
            name_damage = f"|c{weapon.name:<25}|n |gDamage:|n {weapon.damage:<10}"
            rof_hands = f"|gROF:|n {weapon.rof:<5} |gHands:|n {weapon.hands}"
            output.append(f"{name_damage}{rof_hands:>40}")
            concealable = "Yes" if weapon.concealable else "No"
            weight_value = f"|gWeight:|n {weapon.weight:<5} |gValue:|n |y{weapon.value:>4} eb|n"
            output.append(f"  |gConcealable:|n {concealable:<5}{weight_value:>58}")
        output.append(divider("", width=80, fillchar="|m-|n"))
        return "\n".join(output) + "\n"

    def display_armor(self):
        armors = Armor.objects.all()
        if not armors:
            return divider("Armor", width=80, fillchar="|m-|n") + "\nNo armor found in the database.\n"
        
        output = [divider("Armor", width=80, fillchar="|m-|n")]
        for armor in armors:
            name_sp_ev = f"|c{armor.name:<25}|n |gSP:|n {armor.sp:<5} |gEV:|n {armor.ev:<5}"
            weight_value = f"|gWeight:|n {armor.weight:<5} |gValue:|n |y{armor.value:>4} eb|n"
            output.append(f"{name_sp_ev}{weight_value:>35}")
            output.append(f"  |gLocations:|n {armor.locations}")
        output.append(divider("", width=80, fillchar="|m-|n"))
        return "\n".join(output) + "\n"

    def display_gear(self):
        gears = Gear.objects.all()
        if not gears:
            return divider("Gear", width=80, fillchar="|m-|n") + "\nNo gear found in the database.\n"
        
        output = [divider("Gear", width=80, fillchar="|m-|n")]
        for gear in gears:
            name_cat = f"|c{gear.name:<25}|n |gCategory:|n {gear.category:<15}"
            weight_value = f"|gWeight:|n {gear.weight:<5} |gValue:|n |y{gear.value:>4} eb|n"
            output.append(f"{name_cat}{weight_value:>35}")
            
            description = wrap_ansi(gear.description, 76)  # Wrap to 76 to account for initial spaces
            if len(ANSIString(description)) > 76:
                description = description[:73] + "..."
            output.append(f"  |gDescription:|n {description}")
        
        output.append(divider("", width=80, fillchar="|m-|n"))
        return "\n".join(output) + "\n"

    def display_ammo(self):
        ammos = Ammunition.objects.all()
        if not ammos:
            return divider("Ammunition", width=80, fillchar="|m-|n") + "\nNo ammunition found in the database.\n"
        
        output = [divider("Ammunition", width=80, fillchar="|m-|n")]
        for ammo in ammos:
            name_type = f"|c{ammo.name:<25}|n |gType:|n {ammo.ammo_type:<15}"
            weapon_type = f"|gWeapon Type:|n {ammo.weapon_type}"
            output.append(f"{name_type}{weapon_type:>35}")
            damage_ap = f"|gDamage Mod:|n {ammo.damage_modifier:<5} |gAP:|n {ammo.armor_piercing:<5}"
            cost = f"|gCost:|n |y{ammo.cost:>4} eb|n"
            output.append(f"  {damage_ap}{cost:>53}")
        output.append(divider("", width=80, fillchar="|m-|n"))
        return "\n".join(output) + "\n"

    def display_cyberdecks(self):
        cyberdecks = Cyberdeck.objects.all()
        if not cyberdecks:
            return divider("Cyberdecks", width=80, fillchar="|m-|n") + "\nNo cyberdecks found in the database.\n"
        
        output = [divider("Cyberdecks", width=80, fillchar="|m-|n")]
        for deck in cyberdecks:
            output.append(f"|c{deck.name:<80}|n")
            slots = f"|gHardware Slots:|n {deck.hardware_slots:<5} |gProgram Slots:|n {deck.program_slots:<5} |gAny Slots:|n {deck.any_slots:<5}"
            value = f"|gValue:|n |y{deck.value:>4} eb|n"
            output.append(f"  {slots}{value:>27}")
        output.append(divider("", width=80, fillchar="|m-|n"))
        return "\n".join(output) + "\n"

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