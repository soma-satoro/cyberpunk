from django.db.models import Count
from evennia import Command
from django.core.management.base import BaseCommand
from evennia.utils import logger, evtable, utils
from evennia.utils.utils import list_to_string
from world.inventory.models import Gear
from world.equipment_data import populate_weapons, populate_armor, populate_gear, populate_all_equipment
from world.cyberpunk_sheets.models import CharacterSheet
from world.cyberware.npcs import create_cyberware_merchant
from world.inventory.models import Weapon, Armor
from typeclasses.rental import RentableRoom
from evennia.objects.models import ObjectDB
import re

class CmdCleanupDuplicateGear(Command):
    """
    Admin command to clean up duplicate gear items.

    Usage:
      cleanup_gear
    """

    key = "cleanup_gear"
    locks = "cmd:perm(Admin)"

    def func(self):
        duplicates = Gear.objects.values('name').annotate(name_count=Count('id')).filter(name_count__gt=1)
        
        for duplicate in duplicates:
            name = duplicate['name']
            items = Gear.objects.filter(name=name).order_by('id')
            primary_item = items.first()
            for item in items[1:]:
                item.delete()
            self.caller.msg(f"Cleaned up duplicate gear: {name}")
        
        self.caller.msg("Duplicate gear cleanup completed.")

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

class CmdStat(Command):
    """
    Set or modify stats on a player character.
    Usage:
      stat <character> <stat> = <value>
      stat <character> <stat> +<value>
      stat <character> <stat> -<value>
    Examples:
      stat Bob intelligence = 5
      stat Alice cool +2
      stat Charlie empathy -1
      stat David full_name = David Martinez
    This command allows you to set or modify various stats on a player character.
    You can set a stat to an absolute value, or increase/decrease it by a certain amount.
    String fields (like full_name, role, gender) only support the '=' operation.
    """
    key = "stat"
    aliases = ["staffstat", "modstat"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
   
    def func(self):
        if not self.args:
            self.caller.msg("Usage: stat <character> <stat> = <value>")
            return
        try:
            char_name, stat, operation, value = self.parse_input(self.args)
        except ValueError as e:
            self.caller.msg(str(e))
            return
       
        # Find the character
        char = self.caller.search(char_name, global_search=True)
        if not char:
            return
        
        # Check if the character has a character sheet
        try:
            cs = CharacterSheet.objects.get(character=char)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{char.name} doesn't have a character sheet.")
            return
        
        # Get the current value of the stat
        try:
            current_value = getattr(cs, stat)
        except AttributeError:
            self.caller.msg(f"{char.name} doesn't have a stat named '{stat}'.")
            return
       
        # Determine the new value
        try:
            if isinstance(current_value, int):
                if operation == '=':
                    new_value = int(value)
                elif operation == '+':
                    new_value = current_value + int(value)
                elif operation == '-':
                    new_value = current_value - int(value)
                else:
                    raise ValueError("Invalid operation for numeric stat. Use '=', '+', or '-'.")
                new_value = max(0, min(new_value, 10))  # Ensure value is between 0 and 10 for numerical stats
            elif isinstance(current_value, str):
                if operation != '=':
                    raise ValueError("String fields only support the '=' operation.")
                new_value = value  # For string fields, we just use the value as-is
            else:
                raise ValueError(f"Unsupported data type for stat '{stat}'.")
        except ValueError as e:
            self.caller.msg(str(e))
            return
       
        # Set the new value
        try:
            setattr(cs, stat, new_value)
            if hasattr(cs, 'recalculate_derived_stats'):
                cs.recalculate_derived_stats()
            cs.save()
            self.caller.msg(f"Set {char.name}'s {stat} to {new_value}.")
            char.msg(f"Your {stat} has been changed to {new_value}.")
           
            # Show updated derived stats only for numeric fields
            if isinstance(new_value, int):
                derived_stats = self.get_derived_stats(cs)
                self.caller.msg("Updated derived statistics:")
                for stat, value in derived_stats.items():
                    self.caller.msg(f"{stat}: {value}")
        except Exception as e:
            self.caller.msg(f"Error setting {stat} on {char.name}: {str(e)}")
   
    def parse_input(self, args):
        parts = args.split()
        if len(parts) < 4:
            raise ValueError("Not enough arguments. Usage: stat <character> <stat> = <value>")
       
        char_name = parts[0]
        stat = parts[1].lower()
        operation = parts[2]
        value = " ".join(parts[3:])
        if operation not in ['=', '+', '-']:
            raise ValueError("Invalid operation. Use '=', '+', or '-'.")
        return char_name, stat, operation, value
   
    def get_derived_stats(self, sheet):
        return {
            "Max HP": sheet._max_hp,
            "Current HP": sheet._current_hp,
            "Death Save": sheet.death_save,
            "Serious Wounds": sheet.serious_wounds,
            "Humanity": sheet.humanity
        }

# Update this in your commands/admin_commands.py file

from evennia import Command
from evennia.utils import utils

class CmdClearAllStates(Command):
    """
    Clear all lingering states for a character.
    Usage:
      clearstates [<character>]
    This command removes any lingering EvMenu state, custom cmdsets, and ndb attributes
    from the specified character or from yourself if no character is specified.
    """
    key = "clearstates"
    aliases = ["clearevmenu", "resetstates"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if self.args:
            target = self.caller.search(self.args.strip())
            if not target:
                return
        else:
            target = self.caller

        # Clear ndb attributes
        for attr in list(target.ndb.all):
            try:
                delattr(target.ndb, attr)
            except AttributeError:
                pass

        # Clear specific db attributes
        if hasattr(target.db, '_menutree'):
            delattr(target.db, '_menutree')

        # Remove all non-default cmdsets
        default_cmdsets = ['CharacterCmdSet']  # Add any other default cmdsets here
        cmdsets = target.cmdset.all()  # Call the method to get the list of cmdsets
        for cmdset in cmdsets:
            if cmdset.key not in default_cmdsets:
                target.cmdset.delete(cmdset.key)

        # Rebuild the default cmdset
        target.cmdset.update()

        # Clear any scripts on the character
        for script in target.scripts.all():
            script.stop()

        self.caller.msg(f"All states cleared for {target.name}. Default cmdset restored.")
        if target != self.caller:
            target.msg("Your character states have been reset by an admin.")

        # Force a look to refresh the character's view
        target.execute_cmd('look')

class CmdHeal(Command):
    """
    Heal yourself or another character.

    Usage:
      heal <character> <amount>

    This command allows you to heal a character of HP damage.
    """

    key = "heal"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: heal <character> <amount>")
            return

        target_name, heal_amount = self.args.split()
        target = self.caller.search(target_name)
        if not target:
            return

        try:
            heal_amount = int(heal_amount)
        except ValueError:
            self.caller.msg("Heal amount must be a number.")
            return

        if heal_amount <= 0:
            self.caller.msg("Heal amount must be a positive number.")
            return

        if not hasattr(target, 'character_sheet'):
            self.caller.msg("Target doesn't have a character sheet.")
            return

        try:
            cs = target.character_sheet
            old_hp = cs._current_hp
            cs._current_hp = min(cs._current_hp + heal_amount, cs._max_hp)
            cs.save()
            
            actual_heal = cs._current_hp - old_hp
            
            self.caller.msg(f"You healed {target.name} for {actual_heal} HP.")
            target.msg(f"{self.caller.name} healed you for {actual_heal} HP.")
        except Exception as e:
            self.caller.msg(f"Error healing {target.name}: {str(e)}")

class CmdHurt(Command):
    """
    Inflict damage on yourself or another character.

    Usage:
      hurt <character> <amount>

    This command allows you to inflict damage on a character.
    """

    key = "hurt"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: hurt <character> <amount>")
            return

        target_name, damage = self.args.split()
        target = self.caller.search(target_name)
        if not target:
            return

        try:
            damage = int(damage)
        except ValueError:
            self.caller.msg("Damage must be a number.")
            return

        if damage <= 0:
            self.caller.msg("Damage must be a positive number.")
            return

        if not hasattr(target, 'character_sheet'):
            self.caller.msg("Target doesn't have a character sheet.")
            return

        try:
            cs = target.character_sheet
            old_hp = cs._current_hp
            cs._current_hp = max(0, cs._current_hp - damage)
            cs.save()
            
            actual_damage = old_hp - cs._current_hp
            
            self.caller.msg(f"You hurt {target.name} for {actual_damage} damage.")
            target.msg(f"{self.caller.name} hurt you for {actual_damage} damage.")

            if cs._current_hp == 0:
                self.caller.msg(f"{target.name} has been incapacitated!")
                target.msg("You have been incapacitated!")
        except Exception as e:
            self.caller.msg(f"Error hurting {target.name}: {str(e)}")

class CmdApprove(Command):
    """
    Approve a player's character.

    Usage:
      approve <character_name>

    This command approves a player's character, removing the 'unapproved' tag
    and adding the 'approved' tag. This allows the player to start playing.
    """
    key = "approve"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: approve <character_name>")
            return

        target = self.caller.search(self.args)
        if not target:
            return

        if not target.tags.has("unapproved", category="approval"):
            self.caller.msg(f"{target.name} is already approved.")
            return

        target.tags.remove("unapproved", category="approval")
        target.tags.add("approved", category="approval")
        logger.log_info(f"{target.name} has been approved by {self.caller.name}")

        self.caller.msg(f"You have approved {target.name}.")
        target.msg("Your character has been approved. You may now begin playing.")

class CmdUnapprove(Command):
    """
    Set a character's status to unapproved.

    Usage:
      unapprove <character_name>

    This command removes the 'approved' tag from a character and adds the 'unapproved' tag.
    This effectively reverts the character to an unapproved state, allowing them to use
    chargen commands again.
    """
    key = "unapprove"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: unapprove <character_name>")
            return

        target = self.caller.search(self.args)
        if not target:
            return

        if target.tags.has("unapproved", category="approval"):
            self.caller.msg(f"{target.name} is already unapproved.")
            return

        target.tags.remove("approved", category="approval")
        target.tags.add("unapproved", category="approval")
        logger.log_info(f"{target.name} has been unapproved by {self.caller.name}")

        self.caller.msg(f"You have unapproved {target.name}.")
        target.msg("Your character has been unapproved. You may now use chargen commands again.")

from evennia import Command
from evennia.utils import evtable
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import Weapon, Armor

class CmdAdminViewSheet(Command):
    """
    View a character's sheet as an admin.

    Usage:
      adminsheet <character_name>

    This command allows admins to view the complete character sheet
    of any character in the game.
    """
    key = "adminsheet"
    aliases = ["adminview"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: adminsheet <character_name>")
            return

        target = self.caller.search(self.args)
        if not target:
            return

        try:
            cs = CharacterSheet.objects.get(character=target)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{target.name} doesn't have a character sheet.")
            return

        self.show_sheet(target, cs)

    def show_sheet(self, target, cs):
        width = 78

        # Main header
        header = f"Character Sheet for {cs.full_name}"
        self.caller.msg(f"|044{'-' * 78}|n")
        self.caller.msg(f"|044|c{header.center(76)}|n|044|n")
        self.caller.msg(f"|044{'-' * 78}|n")

        # Basic Info
        basic_info = evtable.EvTable(border="table", table_pad=2)
        basic_info.add_column("|cBasic Info|n", align="l", width=20)
        basic_info.add_column("", align="l", width=58)
        basic_info.add_row("Name:", cs.full_name)
        basic_info.add_row("Role:", cs.role)
        basic_info.add_row("Gender:", cs.gender)
        basic_info.add_row("Luck:", f"{cs.current_luck}/{cs.luck}")
        self.caller.msg(basic_info)

        # Stats
        stats = evtable.EvTable(border="table", table_pad=2)
        stats.add_column("|cSTATS|n", align="l", width=76)
        stats_row = evtable.EvTable(border=None, table_pad=1)
        stats_row.add_column("Intelligence:", align="l", width=18)
        stats_row.add_column(str(cs.intelligence), align="l", width=4)
        stats_row.add_column("Technology:", align="l", width=18)
        stats_row.add_column(str(cs.technology), align="l", width=4)
        stats_row.add_column("Move:", align="l", width=18)
        stats_row.add_column(str(cs.move), align="l", width=4)
        stats.add_row(stats_row)
        stats_row = evtable.EvTable(border=None, table_pad=1)
        stats_row.add_column("Reflexes:", align="l", width=18)
        stats_row.add_column(str(cs.reflexes), align="l", width=4)
        stats_row.add_column("Cool:", align="l", width=18)
        stats_row.add_column(str(cs.cool), align="l", width=4)
        stats_row.add_column("Body:", align="l", width=18)
        stats_row.add_column(str(cs.body), align="l", width=4)
        stats.add_row(stats_row)
        stats_row = evtable.EvTable(border=None, table_pad=1)
        stats_row.add_column("Dexterity:", align="l", width=18)
        stats_row.add_column(str(cs.dexterity), align="l", width=4)
        stats_row.add_column("Willpower:", align="l", width=18)
        stats_row.add_column(str(cs.willpower), align="l", width=4)
        stats_row.add_column("Empathy:", align="l", width=18)
        stats_row.add_column(str(cs.empathy), align="l", width=4)
        stats.add_row(stats_row)
        self.caller.msg(stats)

        # Skills
        skills = evtable.EvTable(border="table", table_pad=2)
        skills.add_column("|cSKILLS|n", align="l", width=76)
        # Add logic to display skills here
        # For example:
        skills.add_row("Evasion 5")
        skills.add_row("Handgun 5")
        self.caller.msg(skills)

        # Derived Statistics
        derived = evtable.EvTable(border="table", table_pad=2)
        derived.add_column("|cDerived Statistics|n", align="l", width=76)
        derived_row = evtable.EvTable(border=None, table_pad=1)
        derived_row.add_column("Hit Points:", align="l", width=18)
        derived_row.add_column(f"{cs._current_hp}/{cs._max_hp}", align="l", width=10)
        derived_row.add_column("Death Save:", align="l", width=18)
        derived_row.add_column(str(cs.death_save), align="l", width=10)
        derived.add_row(derived_row)
        derived_row = evtable.EvTable(border=None, table_pad=1)
        derived_row.add_column("Serious Wounds:", align="l", width=18)
        derived_row.add_column(str(cs.serious_wounds), align="l", width=10)
        derived_row.add_column("Humanity:", align="l", width=18)
        derived_row.add_column(str(cs.humanity), align="l", width=10)
        derived.add_row(derived_row)
        self.caller.msg(derived)

        # Equipment
        equipment = evtable.EvTable(border="table", table_pad=2)
        equipment.add_column("|cEquipment|n", align="l", width=76)
        equipment.add_row("Weapons:")
        for weapon in Weapon.objects.filter(inventory__character=cs):
            equipment.add_row(f"- {weapon.name} (Damage: {weapon.damage}, ROF: {weapon.rof})")
        equipment.add_row("Armor:")
        for armor in Armor.objects.filter(inventory__character=cs):
            equipment.add_row(f"- {armor.name} (SP: {armor.sp}, EV: {armor.ev}, Locations: {armor.locations})")
        self.caller.msg(equipment)

class CmdAdminViewLifepath(Command):
    """
    View a character's lifepath as an admin.

    Usage:
      adminlifepath <character_name>

    This command allows admins to view the lifepath information
    of any character in the game.
    """
    key = "adminlifepath"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: adminlifepath <character_name>")
            return

        target = self.caller.search(self.args)
        if not target:
            return

        try:
            cs = CharacterSheet.objects.get(character=target)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"{target.name} doesn't have a character sheet.")
            return

        self.show_lifepath(target, cs)

    def show_lifepath(self, target, cs):
        width = 78

        # Main header
        header = f"Character Sheet for {cs.full_name}"
        self.caller.msg(f"|044{'-' * 78}|n")
        self.caller.msg(f"|044|c{header.center(76)}|n|044|n")
        self.caller.msg(f"|044{'-' * 78}|n")
        # Create the main table
        table = evtable.EvTable(border="table", table_pad=2)
        table.add_column("|cBasic Information|n", align="l", width=30)
        table.add_column("", align="l", width=50)

        # Add general lifepath information
        general_fields_1 = [
            ("Cultural Origin", "cultural_origin"),
            ("Personality", "personality"),
            ("Clothing Style", "clothing_style"),
            ("Hairstyle", "hairstyle"),
            ("Affectation", "affectation"),
            ("Motivation", "motivation"),
            ("Life Goal", "life_goal"),
        ]
        for title, field in general_fields_1:
            value = getattr(cs, field, "Not set")
            table.add_row(title, value)
    
            # Continue general lifepath information
        general_fields_2 = [
            ("Most Valued Person", "valued_person"),
            ("Valued Possession", "valued_possession"),
            ("Family Background", "family_background"),
            ("Origin Environment", "environment"),
            ("Family Crisis", "family_crisis")
        ]
        table.add_row("|cBackground Data|n", "")  # Empty row for separation
        for title, field in general_fields_2:
            value = getattr(cs, field, "Not set")
            table.add_row(title, value)

        # Add role-specific information
        if cs.role:
            table.add_row("", "")  # Empty row for separation
            table.add_row(f"|c{cs.role}-specific Lifepath|n", "")

            role_specific_fields = {
                "Rockerboy": [
                    "what_kind_of_rockerboy_are_you",
                    "whos_gunning_for_you_your_group",
                    "where_do_you_perform"
                ],
                "Solo": [
                    "what_kind_of_solo_are_you",
                    "whats_your_moral_compass_like",
                    "whos_gunning_for_you",
                    "whats_your_operational_territory"
                ],
                "Netrunner": [
                    "what_kind_of_runner_are_you",
                    "who_are_some_of_your_other_clients",
                    "where_do_you_get_your_programs",
                    "whos_gunning_for_you"
                ],
                "Tech": [
                    "what_kind_of_tech_are_you",
                    "whats_your_workspace_like",
                    "who_are_your_main_clients",
                    "where_do_you_get_your_supplies"
                ],
                "Medtech": [
                    "what_kind_of_medtech_are_you",
                    "who_are_your_main_clients",
                    "where_do_you_get_your_supplies"
                ],
                "Media": [
                    "what_kind_of_media_are_you",
                    "how_does_your_work_reach_the_public",
                    "how_ethical_are_you",
                    "what_types_of_stories_do_you_want_to_tell"
                ],
                "Exec": [
                    "what_kind_of_corp_do_you_work_for",
                    "what_division_do_you_work_in",
                    "how_good_bad_is_your_corp",
                    "where_is_your_corp_based",
                    "current_state_with_your_boss"
                ],
                "Lawman": [
                    "what_is_your_position_on_the_force",
                    "how_wide_is_your_groups_jurisdiction",
                    "how_corrupt_is_your_group",
                    "who_is_your_groups_major_target"
                ],
                "Fixer": [
                    "what_kind_of_fixer_are_you",
                    "who_are_your_side_clients",
                    "whos_gunning_for_you"
                ],
                "Nomad": [
                    "how_big_is_your_pack",
                    "what_do_you_do_for_your_pack",
                    "whats_your_packs_overall_philosophy",
                    "is_your_pack_based_on_land_air_or_sea"
                ]
            }

            for field in role_specific_fields.get(cs.role, []):
                value = getattr(cs, field, None)
                if value:
                    title = field.replace('_', ' ').title()
                    table.add_row(title, value)

        # Send the formatted table to the caller
        self.caller.msg(table)

class CmdFixSheet(Command):
    help = 'Check and fix character sheet associations'

    def handle(self, *args, **options):
        characters = ObjectDB.objects.filter(db_typeclass_path__contains='characters')
        for char in characters:
            sheet, created = CharacterSheet.objects.get_or_create(db_object=char)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created sheet for {char}'))
            else:
                self.stdout.write(f'Sheet already exists for {char}')

class CmdSpawnRipperdoc(Command):
    """
    Spawn a Ripperdoc NPC in the current location.

    Usage:
      spawn_ripperdoc
    """
    key = "spawn_ripperdoc"
    locks = "cmd:perm(Builders)"
    help_category = "Admin"

    def func(self):
        ripperdoc = create_cyberware_merchant(self.caller.location)
        self.caller.msg(f"Spawned Ripperdoc '{ripperdoc.key}' in {self.caller.location}.")


class CmdGradientName(Command):
    """
    Apply a gradient color to your name

    Usage:
      gradientname <start_color> <end_color>

    This command applies a gradient color effect to your name,
    transitioning from the start color to the end color.
    You can use named colors or hex color codes (#RRGGBB).

    Examples:
      gradientname crimson gold
      gradientname #FF0000 #0000FF
      gradientname red #00FF00
    """

    key = "gradientname"
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    # Color map (unchanged from previous version)
    COLOR_MAP = {
        "black": (0, 0, 0),
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "yellow": (255, 255, 0),
        "blue": (0, 0, 255),
        "magenta": (255, 0, 255),
        "cyan": (0, 255, 255),
        "white": (255, 255, 255),
        "gray": (128, 128, 128),
        "maroon": (128, 0, 0),
        "olive": (128, 128, 0),
        "navy": (0, 0, 128),
        "purple": (128, 0, 128),
        "teal": (0, 128, 128),
        "silver": (192, 192, 192),
        "lime": (0, 255, 0),
        "aqua": (0, 255, 255),
        "fuchsia": (255, 0, 255),
        "orange": (255, 165, 0),
        "pink": (255, 192, 203),
        "gold": (255, 215, 0),
        "crimson": (220, 20, 60),
        "violet": (238, 130, 238),
        "indigo": (75, 0, 130),
        "turquoise": (64, 224, 208),
        "coral": (255, 127, 80),
        "salmon": (250, 128, 114),
        "skyblue": (135, 206, 235),
        "khaki": (240, 230, 140),
        "plum": (221, 160, 221),
    }

    def func(self):
        if not self.args:
            self.caller.msg("Usage: gradientname <start_color> <end_color>")
            return

        try:
            start_color, end_color = self.args.split()[:2]
        except ValueError:
            self.caller.msg("Please provide both start and end colors.")
            return

        start_rgb = self.parse_color(start_color)
        end_rgb = self.parse_color(end_color)

        if start_rgb is None or end_rgb is None:
            self.caller.msg("Invalid color(s). Use named colors or hex codes (#RRGGBB).")
            return

        name = self.caller.key
        gradient_name = self.create_gradient(name, start_rgb, end_rgb)
        
        self.caller.db.gradient_name = gradient_name
        self.caller.msg(f"Your name now appears as: {gradient_name}")

    def parse_color(self, color):
        if color.startswith('#'):
            # Parse hex color code
            match = re.match(r'^#([0-9A-Fa-f]{6})$', color)
            if match:
                hex_color = match.group(1)
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        elif color in self.COLOR_MAP:
            # Use named color
            return self.COLOR_MAP[color]
        return None

    def create_gradient(self, text, start_rgb, end_rgb):
        gradient = []
        for i, char in enumerate(text):
            r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * i / (len(text) - 1))
            g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * i / (len(text) - 1))
            b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * i / (len(text) - 1))
            
            ansi_code = self.rgb_to_ansi(r, g, b)
            gradient.append(f"\033[38;5;{ansi_code}m{char}\033[0m")

        return "".join(gradient)

    def rgb_to_ansi(self, r, g, b):
        # Convert RGB to the closest ANSI 256 color code
        return 16 + (36 * (r // 51)) + (6 * (g // 51)) + (b // 51)

class CmdClearRental(Command):
    """
    Clear a room's renter property

    Usage:
      @clearrental <room>
      @clearrental here

    Clears the renter property of the specified room.
    Use 'here' to clear the rental of the room you're currently in.
    This is an admin command to be used in case of database corruption
    or if a character gets deleted.
    """

    key = "@clearrental"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("Usage: @clearrental <room> or @clearrental here")
            return

        if self.args.strip().lower() == "here":
            room = caller.location
        else:
            room = caller.search(self.args.strip(), global_search=True)

        if not room:
            return

        if not isinstance(room, RentableRoom):
            caller.msg("That is not a rentable room.")
            return

        old_renter = room.db.renter
        room.db.renter = None
        room.db.rent_due_date = None

        # Remove the rent collection script
        for script in room.scripts.all():
            if script.key.startswith("rent_collection_"):
                script.stop()

        caller.msg(f"Cleared renter property for room '{room.name}'.")
        if old_renter:
            caller.msg(f"Previous renter was: {old_renter.name}")
            # Remove the rented_room attribute from the old renter if they still exist
            if old_renter.attributes.has('rented_room'):
                old_renter.attributes.remove('rented_room')
                caller.msg(f"Removed 'rented_room' attribute from {old_renter.name}.")
        else:
            caller.msg("There was no previous renter.")

        room.msg_contents("This room's rental status has been reset by an admin.")

from evennia import Command
from evennia import search_object
from typeclasses.characters import Character

class CmdCleanupDuplicates(Command):
    """
    Clean up duplicate character objects.

    Usage:
      @cleanup_duplicates
    """

    key = "@cleanup_duplicates"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        all_chars = Character.objects.all()
        accounts = set(char.account for char in all_chars if char.account)

        for account in accounts:
            chars = [char for char in all_chars if char.account == account]
            if len(chars) > 1:
                # Sort by id in descending order and keep the first one (most recent)
                chars.sort(key=lambda x: x.id, reverse=True)
                for char in chars[1:]:
                    self.caller.msg(f"Deleting duplicate character: {char.name} (#{char.id})")
                    char.delete()

        self.caller.msg("Cleanup of duplicate characters complete.")