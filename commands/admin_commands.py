from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from evennia import Command
from world.cyberware.utils import populate_cyberware
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.utils.evtable import EvTable
from .character_commands import CmdSheet
from evennia.utils.search import search_object
from evennia.objects.models import ObjectDB
from world.languages.language_dictionary import LANGUAGES
from world.cyberpunk_sheets.models import CharacterSheet
from world.languages.models import Language, CharacterLanguage
from evennia.utils import logger
from world.inventory.models import Gear
from world.equipment_data import populate_weapons, populate_armor, populate_gear, populate_all_equipment
from world.cyberpunk_sheets.models import CharacterSheet
from world.cyberpunk_sheets.merchants import create_cyberware_merchant
from typeclasses.rental import RentableRoom
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.utils import inherits_from
from world.utils.ansi_utils import wrap_ansi
import re


class CmdPopulate(MuxCommand):
    """
    Populate the database with equipment from Cyberpunk RED.

    Usage:
      populate[/switch]

    Switches:
      /weapons   - Populate weapon database
      /armor     - Populate armor database
      /gear      - Populate gear database
      /cyberware - Populate cyberware database
      /all       - Populate all equipment types
      /cleanup   - Clean up duplicate gear items

    This command initializes the database with equipment from Cyberpunk RED.
    Use the appropriate switch to populate specific types of equipment or all at once.
    The cleanup switch can be used to remove duplicate gear entries.
    """

    key = "populate"
    aliases = ["populate_equipment"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.switches:
            self.caller.msg("You must specify a switch. See 'help populate' for options.")
            return

        if "weapons" in self.switches:
            populate_weapons()
            self.caller.msg("Weapon database populated successfully.")
        
        elif "armor" in self.switches:
            populate_armor()
            self.caller.msg("Armor database populated successfully.")
        
        elif "gear" in self.switches:
            populate_gear()
            self.caller.msg("Gear database populated successfully.")
        
        elif "cyberware" in self.switches:
            populate_cyberware()
            self.caller.msg("Cyberware database populated successfully.")
        
        elif "all" in self.switches:
            populate_all_equipment()
            self.caller.msg("All equipment databases populated successfully.")
        
        elif "cleanup" in self.switches:
            duplicates = Gear.objects.values('name').annotate(name_count=Count('id')).filter(name_count__gt=1)
            
            for duplicate in duplicates:
                name = duplicate['name']
                items = Gear.objects.filter(name=name).order_by('id')
                primary_item = items.first()
                for item in items[1:]:
                    item.delete()
                self.caller.msg(f"Cleaned up duplicate gear: {name}")
            
            self.caller.msg("Duplicate gear cleanup completed.")
        
        else:
            self.caller.msg("Invalid switch. See 'help populate' for options.")

class AdminCommand(MuxCommand):
    """
    Base class for admin commands.
    Update with any additional definitions that may be useful to admin, then call the class by using 'CmdName(AdminCommand)', which
    will apply the following functions.
    """

    #search for a character by name match or dbref.
    def search_for_character(self, search_string):
        # First, try to find by exact name match
        results = search_object(search_string, typeclass="typeclasses.characters.Character")
        if results:
            return results[0]
        
        # If not found, try to find by dbref
        if search_string.startswith("#") and search_string[1:].isdigit():
            results = search_object(search_string, typeclass="typeclasses.characters.Character")
            if results:
                return results[0]
        
        # If still not found, return None
        return None

class CmdStat(AdminCommand):
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

from evennia import Command
from evennia.utils import utils

class CmdClearAllStates(AdminCommand):
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

class CmdHeal(AdminCommand):
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

class CmdHurt(AdminCommand):
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

class CmdApprove(AdminCommand):
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

class CmdUnapprove(AdminCommand):
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

from evennia.commands.default.building import CmdExamine as EvenniaCmdExamine
from evennia import Command

class CmdExamine(EvenniaCmdExamine):
    """
    Examine an object in detail.

    Usage:
      examine [<object>[/attrname]]
      examine [*<account>[/attrname]]

    Switch:
      /script - examine the object's scripts instead of attributes

    The examine command shows detailed game info about an
    object and optionally a specific attribute or script.
    If object is not specified, the current location is examined.

    Append a * before the search string to examine an account
    rather than an object. Use examine *self to examine
    yourself.
    """

    key = "examine"
    aliases = ["ex", "exam", "@ex"]
    locks = "cmd:perm(examine) or perm(Builder)"
    help_category = "Building"

    def format_single_attribute(self, attr):
        try:
            value = attr.value
            if isinstance(value, str):
                return f"{attr.key}={value} [type: str]"
            else:
                return super().format_single_attribute(attr)
        except Exception as e:
            return f"{attr.key}=<ERROR: {str(e)}> [type: {type(attr.value)}]"

# Add this command to your custom command set
from evennia import CmdSet

class CmdViewCharacterSheetID(Command):
    """
    View your character sheet ID.

    Usage:
      viewsheetid
    """
    key = "viewsheetid"
    locks = "cmd:all()"

    def func(self):
        sheet_id = self.caller.db.character_sheet_id
        if sheet_id:
            self.caller.msg(f"Your character sheet ID is: {sheet_id}")
        else:
            self.caller.msg("You don't have a character sheet ID set.")

class CmdSetCharacterSheetID(Command):
    """
    Set your character sheet ID.

    Usage:
      setsheetid <id>
    """
    key = "setsheetid"
    locks = "cmd:all()"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: setsheetid <id>")
            return

        try:
            sheet_id = int(self.args)
            sheet = CharacterSheet.objects.get(id=sheet_id)
            self.caller.db.character_sheet_id = sheet_id
            sheet.character = self.caller
            sheet.save()
            self.caller.msg(f"Character sheet ID set to: {sheet_id}")
            logger.log_info(f"Character {self.caller.name} associated with sheet ID {sheet_id}")
        except ValueError:
            self.caller.msg("Please provide a valid integer ID.")
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"No character sheet found with ID {sheet_id}")

class CmdAllSheets(Command):
    """
    List all character sheets in the database.

    Usage:
      listsheets
    """
    key = "@sheets"
    locks = "cmd:perm(Admin)"

    def func(self):
        sheets = CharacterSheet.objects.all()
        if sheets:
            self.caller.msg("Character Sheets in the database:")
            for sheet in sheets:
                character_name = sheet.character.name if sheet.character else "No character"
                self.caller.msg(f"ID: {sheet.id}, Character: {character_name}, Role: {sheet.role}")
        else:
            self.caller.msg("No character sheets found in the database.")

class CmdAssociateAllCharacterSheets(Command):
    """
    Associate all characters with their character sheets.

    Usage:
      associatesheets
    """
    key = "associatesheets"
    locks = "cmd:perm(Admin)"

    def func(self):
        from evennia.objects.models import ObjectDB
        characters = ObjectDB.objects.filter(db_typeclass_path__contains="characters.Character")
        associated_count = 0

        for character in characters:
            sheet = CharacterSheet.objects.filter(character=character).first()
            if sheet:
                character.db.character_sheet_id = sheet.id
                associated_count += 1
                logger.log_info(f"Associated character {character.name} with sheet ID {sheet.id}")

        self.caller.msg(f"Associated {associated_count} characters with their character sheets.")

class CmdViewSheetAttributes(Command):
    """
    View all attributes of a specific character sheet.

    Usage:
      viewsheet <sheet_id>
    """
    key = "viewsheet"
    locks = "cmd:perm(Admin)"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: viewsheet <sheet_id>")
            return

        try:
            sheet_id = int(self.args)
            sheet = CharacterSheet.objects.get(id=sheet_id)
            
            # Get all fields of the CharacterSheet model
            fields = CharacterSheet._meta.get_fields()
            
            self.caller.msg(f"Attributes for Character Sheet ID {sheet_id}:")
            for field in fields:
                field_name = field.name
                try:
                    if field.is_relation:
                        if field.many_to_many or field.one_to_many:
                            related_objects = getattr(sheet, field_name).all()
                            field_value = ", ".join([str(obj) for obj in related_objects])
                        elif field.many_to_one or field.one_to_one:
                            field_value = str(getattr(sheet, field_name))
                    else:
                        field_value = getattr(sheet, field_name)
                    
                    self.caller.msg(f"{field_name}: {field_value}")
                except Exception as e:
                    self.caller.msg(f"Error processing field '{field_name}': {str(e)}")
            
            # Display character_sheet_id from the associated character if it exists
            if sheet.character:
                character_sheet_id = sheet.character.db.character_sheet_id
                self.caller.msg(f"Associated character's character_sheet_id: {character_sheet_id}")
            else:
                self.caller.msg("No character associated with this sheet.")

            # Display languages
            languages = sheet.character.language_list
            if languages:
                self.caller.msg("Languages:")
                for lang in languages:
                    self.caller.msg(f"- {lang}")
            else:
                self.caller.msg("No languages.")

            # Display group memberships
            self.display_related_objects(sheet, 'group_memberships', "Group Memberships")

            # Display faction reputations
            self.display_related_objects(sheet, 'faction_reputations', "Faction Reputations")

            # Display cyberware
            self.display_related_objects(sheet, 'cyberware_instances', "Cyberware")

            # Display owned cyberdecks
            self.display_related_objects(sheet, 'owned_cyberdecks', "Owned Cyberdecks")

            # Display netrun sessions
            self.display_related_objects(sheet, 'netrun_sessions', "Netrun Sessions")

        except ValueError:
            self.caller.msg("Please provide a valid integer ID.")
        except ObjectDoesNotExist:
            self.caller.msg(f"No character sheet found with ID {sheet_id}")
        except Exception as e:
            self.caller.msg(f"An error occurred: {str(e)}")
            logger.log_err(f"Error in viewsheet command: {str(e)}")

    def display_related_objects(self, sheet, relation_name, display_name):
        try:
            related_objects = getattr(sheet, relation_name).all()
            if related_objects:
                self.caller.msg(f"{display_name}:")
                for obj in related_objects:
                    if relation_name == 'character_languages':
                        self.caller.msg(f"- {obj.language.name} (Level {obj.level})")
                    else:
                        self.caller.msg(f"- {obj}")
            else:
                self.caller.msg(f"No {display_name.lower()}.")
        except AttributeError:
            self.caller.msg(f"Error: '{relation_name}' is not a valid attribute for this character sheet.")
        except Exception as e:
            self.caller.msg(f"Error displaying {display_name.lower()}: {str(e)}")

class CmdVerifySheets(Command):
    key = "verifysheets"
    locks = "cmd:perm(Admin)"
    help = 'Verify and fix character sheet data'

    def handle(self, *args, **options):
        characters = ObjectDB.objects.filter(db_typeclass_path__contains='characters.Character')
        for char in characters:
            sheet, created = CharacterSheet.objects.get_or_create(character=char)
            if created:
                self.stdout.write(f"Created new character sheet for {char.key}")
            
            # Ensure Streetslang is added
            streetslang, _ = Language.objects.get_or_create(name="Streetslang")
            CharacterLanguage.objects.get_or_create(
                character_sheet=sheet,
                language=streetslang,
                defaults={'level': 4}
            )

        self.stdout.write(self.style.SUCCESS('Character sheet verification complete'))

class CmdSyncLanguages(Command):
    """
    Sync languages in the database with the LANGUAGES list

    Usage:
      sync_languages

    This command will update the language database to match the LANGUAGES list
    defined in the language_dictionary.py file.
    """

    key = "sync_languages"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        try:
            added = 0
            updated = 0
            removed = 0

            for lang_data in LANGUAGES:
                lang, created = Language.objects.update_or_create(
                    name=lang_data['name'],
                    defaults={
                        'local': lang_data['local'],
                        'corporate': lang_data['corporate']
                    }
                )
                if created:
                    added += 1
                else:
                    updated += 1

            # Remove languages that are in the database but not in LANGUAGES
            db_languages = set(Language.objects.values_list('name', flat=True))
            list_languages = set(lang['name'] for lang in LANGUAGES)
            languages_to_remove = db_languages - list_languages
            removed = Language.objects.filter(name__in=languages_to_remove).delete()[0]

            self.caller.msg(f"Languages synced successfully:")
            self.caller.msg(f"Added: {added}")
            self.caller.msg(f"Updated: {updated}")
            self.caller.msg(f"Removed: {removed}")

        except ObjectDoesNotExist:
            self.caller.msg("Error: Language model not found. Make sure the languages app is installed and migrated.")
        except Exception as e:
            self.caller.msg(f"An error occurred: {str(e)}")

class CmdSummon(AdminCommand):
    """
    Summon a player to your location.

    Usage:
      +summon <player>

    Teleports the specified player to your location.
    """

    key = "+summon"
    locks = "cmd:perm(admin)"
    help_category = "Admin"

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("Usage: +summon <player>")
            return

        target = self.search_for_character(self.args)
        if not target:
            caller.msg(f"Could not find character '{self.args}'.")
            return

        if not inherits_from(target, "typeclasses.characters.Character"):
            caller.msg("You can only summon characters.")
            return

        old_location = target.location
        target.move_to(caller.location, quiet=True)
        caller.msg(f"You have summoned {target.name} to your location.")
        target.msg(f"{caller.name} has summoned you.")
        old_location.msg_contents(f"{target.name} has been summoned by {caller.name}.", exclude=target)
        caller.location.msg_contents(f"{target.name} appears, summoned by {caller.name}.", exclude=[caller, target])

class CmdJoin(AdminCommand):
    """
    Join a player at their location.

    Usage:
      +join <player>

    Teleports you to the specified player's location.
    """

    key = "+join"
    locks = "cmd:perm(admin)"
    help_category = "Admin"

    def func(self):
        caller = self.caller

        if not self.args:
            caller.msg("Usage: +join <player>")
            return

        target = self.search_for_character(self.args)
        if not target:
            caller.msg(f"Could not find character '{self.args}'.")
            return

        if not inherits_from(target, "typeclasses.characters.Character"):
            caller.msg("You can only join characters.")
            return

        caller.move_to(target.location, quiet=True)
        caller.msg(f"You have joined {target.name} at their location.")
        target.location.msg_contents(f"{caller.name} appears in the room.", exclude=caller)