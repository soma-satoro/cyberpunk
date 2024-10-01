import random
from evennia import Command, logger
from world.utils.character_utils import get_full_attribute_name, ALL_ATTRIBUTES, TOPSHEET_MAPPING
from world.utils.calculation_utils import get_remaining_points, STAT_MAPPING, SKILL_MAPPING
from typeclasses.chargen import ChargenRoom
from evennia.utils import evtable
from evennia.utils.utils import list_to_string
from evennia.utils.create import create_object
from world.cyberpunk_sheets.models import CharacterSheet
from world.languages.models import Language
from evennia.utils.evtable import EvTable
from world.utils.formatting import header, footer, divider
from world.utils.ansi_utils import wrap_ansi
from world.languages.language_dictionary import LANGUAGES
from world.languages.models import Language, CharacterLanguage
from world.inventory.models import Weapon, Armor, Gear, Inventory
from evennia.commands.default.muxcommand import MuxCommand
from math import ceil

class CmdSheet(Command):
    """
    Show character sheet

    Usage:
      sheet
    """

    key = "sheet"
    aliases = ["char", "character"]
    lock = "cmd:all()"
    help_category = "Character"

    def safe_get_attr(self, obj, attr):
        """Safely get an attribute value, returning 'N/A' if it doesn't exist."""
        return getattr(obj, attr, 'N/A')

    def func(self):
        cs = self.caller.character_sheet
        if not cs:
            self.caller.msg("You don't have a character sheet.")
            return

        # Main header
        output = header(f"Character Sheet for {cs.full_name}", width=80, fillchar="|m-|n") + "\n"

        # Basic Information
        output += divider("Basic Information", width=80, fillchar="|m-|n") + "\n"
        basic_info = [
            ("Full Name:", self.safe_get_attr(cs, 'full_name'), "Gender:", self.safe_get_attr(cs, 'gender')),
            ("Handle:", self.safe_get_attr(cs, 'handle'), "Age:", self.safe_get_attr(cs, 'age')),
            ("Hometown:", self.safe_get_attr(cs, 'hometown'), "Height:", f"{self.safe_get_attr(cs, 'height')} cm"),
            ("Night City Reputation:", self.safe_get_attr(cs, 'reputation'), "Weight:", f"{self.safe_get_attr(cs, 'weight')} kg"),
            ("Role:", self.safe_get_attr(cs, 'role'), "Luck:", f"{self.safe_get_attr(cs, 'current_luck')}/{self.safe_get_attr(cs, 'luck')}")
        ]
        for row in basic_info:
            output += f"|c{row[0]:<25}|n {row[1]:<20} |c{row[2]:<25}|n {row[3]:<20}\n"
        output += "\n"

        # Stats
        output += divider("STATS", width=80, fillchar="|m-|n") + "\n"
        stats = [
            ("Intelligence:", cs.intelligence, "Technology:", cs.technology, "Move:", cs.move),
            ("Reflexes:", cs.reflexes, "Cool:", cs.cool, "Body:", cs.body),
            ("Dexterity:", cs.dexterity, "Willpower:", cs.willpower, "Empathy:", cs.empathy)
        ]
        for row in stats:
            output += "".join(f"|c{label:<13}|n {value:<8}" for label, value in zip(row[::2], row[1::2])) + "\n"
        output += "\n"

        # Skills
        output += divider("SKILLS", width=80, fillchar="|m-|n") + "\n"
        active_skills = self.get_active_skills(cs)
        for i in range(0, len(active_skills), 3):
            row = active_skills[i:i+3]
            output += "".join(f"|c{skill:<20}|n {value:<5}" for skill, value in row).ljust(80) + "\n"
        output += "\n"

        # Derived Stats
        output += divider("Derived Statistics", width=80, fillchar="|m-|n") + "\n"
        derived_stats = [
            ("Hit Points:", f"{cs._current_hp}/{cs._max_hp}", "Death Save:", cs.death_save),
            ("Serious Wounds:", cs.serious_wounds, "Humanity:", cs.humanity)
        ]
        for row in derived_stats:
            output += "".join(f"|c{label:<16}|n {value:<18}" for label, value in zip(row[::2], row[1::2])) + "\n"
        output += "\n"

        # Equipment
        output += divider("Equipment", width=80, fillchar="|m-|n") + "\n"
        try:
            inv = Inventory.objects.get(character=cs)
        except Inventory.DoesNotExist:
            output += "None\n"
        except Exception as e:
            logger.log_err(f"Error retrieving inventory for {self.caller}: {str(e)}")
            output += "Error retrieving inventory\n"
        else:
            weapons = inv.weapons.all()
            if weapons:
                output += "|cWeapons:|n\n"
                for weapon in weapons:
                    if weapon.name and weapon.damage and weapon.rof:
                        output += f"- {weapon.name:<20} Damage: {weapon.damage:<10} ROF: {weapon.rof}\n"
                    else:
                        logger.log_warn(f"Incomplete weapon data found: {weapon.id}")
            else:
                output += "Weapons: None\n"

            armor = inv.armor.all()
            if armor:
                output += "|cArmor:|n\n"
                for piece in armor:
                    output += f"- {piece.name:<20} SP: {piece.sp}, EV: {piece.ev:<10} Locations: {piece.locations}\n"
            else:
                output += "Armor: None\n"

            gear = inv.gear.all()
            if gear:
                output += "|cGear:|n\n"
                gear_list = [f"- {item.name}" for item in gear]
                max_items = max(4, ceil(len(gear_list) / 2))  # At least 4 items in first column
                col1 = gear_list[:max_items]
                col2 = gear_list[max_items:]
                
                for i in range(max(len(col1), len(col2))):
                    left = col1[i] if i < len(col1) else ""
                    right = col2[i] if i < len(col2) else ""
                    output += f"{left:<39} {right}\n"
            else:
                output += "Gear: None\n"
        output += "\n"

        # Languages
        output += divider("Languages", width=80, fillchar="|m-|n") + "\n"
        languages = cs.character_languages.all()
        if languages:
            for lang in languages:
                output += f"- {lang.language} (Level {lang.level})\n"
        else:
            output += "None\n"

        output += footer(width=80, fillchar="|m-|n")
        self.caller.msg(output)

    def get_active_skills(self, cs):
        """
        Get a list of active skills (skills with value > 0).
        """
        skill_list = []
        excluded_fields = ['id', 'age', 'height', 'weight', 'hometown', 'account', 'total_cyberware_humanity_loss', 'rep', 'full_name', 'handle', 'gender', 'unarmed_damage_die_type', 'unarmed_damage_dice', 'current_luck', '_max_hp', '_current_hp', 'humanity', 'death_save', 'serious_wounds', 'eurodollars', 'role', 'eqweapon', 'eqarmor', 'humanity_loss', 'is_complete']
        excluded_prefixes = ('intelligence', 'reflexes', 'dexterity', 'technology', 'cool', 'willpower', 'luck', 'move', 'body', 'empathy')
        
        for field in cs._meta.get_fields():
            if (field.name not in excluded_fields and 
                not field.name.startswith(excluded_prefixes) and
                not field.is_relation):  # This line excludes relation fields
                value = getattr(cs, field.name, 0)
                if isinstance(value, int) and value > 0:
                    skill_list.append([field.name.replace('_', ' ').title(), value])
        
        skill_list.sort(key=lambda x: (-x[1], x[0]))
        return skill_list

class CmdShortDesc(Command):
    """
    shortdesc <text>

    Usage:
      shortdesc <text>
      shortdesc <character>=<text>

    Create or set a short description for your character. Builders+ can set the short description for others.

    Examples:
      shortdesc Tall and muscular
      shortdesc Bob=Short and stocky
    """
    key = "shortdesc"
    help_category = "Roleplay Utilities"

    def parse(self):
        """
        Custom parser to handle the possibility of targeting another character.
        """
        args = self.args.strip()
        if "=" in args:
            self.target_name, self.shortdesc = [part.strip() for part in args.split("=", 1)]
        else:
            self.target_name = None
            self.shortdesc = args

    def func(self):
        "Implement the command"
        caller = self.caller

        if self.target_name:
            # Check if the caller has permission to set short descriptions for others
            if not caller.check_permstring("builders"):
                caller.msg("|rYou don't have permission to set short descriptions for others.|n")
                return

            # Find the target character
            target = caller.search(self.target_name)
            if not target:
                caller.msg(f"|rCharacter '{self.target_name}' not found.|n")
                return

            # Set the short description for the target
            target.db.shortdesc = self.shortdesc
            caller.msg(f"Short description for {target.name} set to '|w{self.shortdesc}|n'.")
            target.msg(f"Your short description has been set to '|w{self.shortdesc}|n' by {caller.name}.")
        else:
            # Set the short description for the caller
            if not self.shortdesc:
                # remove the shortdesc
                caller.db.shortdesc = ""
                caller.msg("Short description removed.")
                return

            caller.db.shortdesc = self.shortdesc
            caller.msg("Short description set to '|w%s|n'." % self.shortdesc)

class CmdEquipWeapon(Command):
    """
    Equip a weapon from your inventory.

    Usage:
      equip <weapon name>

    This command allows you to equip a weapon from your inventory.
    The equipped weapon will be used for attacks.
    """

    key = "equip"
    aliases = ["wield"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
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

class CmdUnequipWeapon(Command):
    """
    Unequip your currently equipped weapon.

    Usage:
      unequip

    This command removes your currently equipped weapon, if any.
    """

    key = "unequip"
    aliases = ["unwield"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
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

class CmdChargenDelete(Command):
    """
    Delete the character sheet for a character.

    Usage:
      chargen/delete

    This command deletes the character sheet associated with your character.
    """

    key = "chargen/delete"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        sheet = self.caller.character_sheet
        if sheet:
            sheet.delete()
            self.caller.msg("Your character sheet has been deleted.")
        else:
            self.caller.msg("You don't have a character sheet to delete.")

class CmdSetStat(Command):
    """
    Set a stat, skill, or topsheet attribute for your character.

    Usage:
      setstat <attribute>=<value>

    Examples:
      setstat INT=5
      setstat AUTO=3
      setstat HANDLE=CoolRunner
      setstat AGE=25
    """

    key = "setstat"
    locks = "cmd:all()"

    def func(self):
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("You can only use this command in a character generation room.")
            return

        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: setstat <attribute>=<value>")
            return

        attr, value = self.args.split("=", 1)
        attr = attr.strip()
        value = value.strip()

        full_attr_name = get_full_attribute_name(attr)
        if not full_attr_name:
            self.caller.msg(f"Invalid attribute name. Choose from: {', '.join(ALL_ATTRIBUTES.values())}")
            return

        sheet = self.caller.character_sheet
        if not sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        if full_attr_name in STAT_MAPPING.values():
            try:
                value = int(value)
                if value < 0 or value > 10:
                    self.caller.msg("Stat value must be between 0 and 10.")
                    return
            except ValueError:
                self.caller.msg("You must specify an integer value for stats.")
                return

            current_value = getattr(sheet, full_attr_name)
            points_needed = value - current_value
            remaining_stat_points, _ = sheet.get_remaining_points()

            if points_needed > remaining_stat_points:
                self.caller.msg(f"Not enough stat points. You need {points_needed} but only have {remaining_stat_points}.")
                return

        elif full_attr_name in SKILL_MAPPING.values():
            try:
                value = int(value)
                if value < 0 or value > 10:
                    self.caller.msg("Skill value must be between 0 and 10.")
                    return
            except ValueError:
                self.caller.msg("You must specify an integer value for skills.")
                return

            current_value = getattr(sheet, full_attr_name)
            points_needed = value - current_value
            is_double_cost = full_attr_name in ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics', 'paramedic']
            actual_points_needed = points_needed * 2 if is_double_cost else points_needed

            _, remaining_skill_points = sheet.get_remaining_points()

            if actual_points_needed > remaining_skill_points:
                self.caller.msg(f"Not enough skill points. You need {actual_points_needed} but only have {remaining_skill_points}.")
                return

        # For topsheet attributes, we don't need to check points
        setattr(sheet, full_attr_name, value)
        sheet.save()

        self.caller.msg(f"Set {full_attr_name} to {value}.")
        
        if full_attr_name in STAT_MAPPING.values() or full_attr_name in SKILL_MAPPING.values():
            new_remaining_stat_points, new_remaining_skill_points = sheet.get_remaining_points()
            self.caller.msg(f"You have {new_remaining_stat_points} stat points and {new_remaining_skill_points} skill points remaining to spend.")

        # Update the room's display
        if isinstance(self.caller.location, ChargenRoom):
            self.caller.location.update_remaining_points(self.caller)

    def get_derived_stats(self, sheet):
        return {
            "Max HP": sheet._max_hp,
            "Current HP": sheet._current_hp,
            "Death Save": sheet.death_save,
            "Serious Wounds": sheet.serious_wounds,
            "Humanity": sheet.humanity
        }

class CmdSetLanguage(MuxCommand):
    """
    Set a language skill for your character.

    Usage:
      setlanguage <language name> <level>
      setlanguage/remove <language name>
      setlanguage/list

    Examples:
      setlanguage Streetslang 3
      setlanguage/remove Streetslang
      setlanguage/list

    This command allows you to add, update, remove, or list language skills.
    The level should be between 1 and 10.
    """
    key = "setlanguage"
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet!")
            return

        sheet = self.caller.character_sheet

        if "list" in self.switches:
            languages = sheet.character_languages.all()
            if languages:
                self.caller.msg("Your languages:")
                for lang in languages:
                    self.caller.msg(f"{lang.language} (Level {lang.level})")
            else:
                self.caller.msg("You don't know any languages.")
            return

        if "remove" in self.switches:
            if not self.args:
                self.caller.msg("Usage: setlanguage/remove <language name>")
                return
            language_name = self.args.strip()
            sheet.remove_language(language_name)
            self.caller.msg(f"Removed {language_name} from your languages.")
            return

        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: setlanguage <language name> <level>")
            return

        try:
            language_name, level = self.args.rsplit(None, 1)
            level = int(level)
            if not 1 <= level <= 10:
                raise ValueError
        except ValueError:
            self.caller.msg("Please provide a valid language name and level (1-10).")
            return

        language_info = next((lang for lang in LANGUAGES if lang.name.lower() == language_name.lower()), None)

        if language_info:
            sheet.add_language(language_info.name, level)
            self.caller.msg(f"Added {language_info.name} at level {level} to your character sheet.")
        else:
            # If not found in LANGUAGES, try to get it from the database
            try:
                language_obj = Language.objects.get(name__iexact=language_name)
                sheet.add_language(language_obj.name, level)
                self.caller.msg(f"Added {language_obj.name} at level {level} to your character sheet.")
            except Language.DoesNotExist:
                self.caller.msg(f"Language '{language_name}' not found. Please check the spelling and try again.")

class CmdRoll(Command):
    """
    Roll a skill check.

    Usage:
      roll <attribute> <skill>

    This command rolls 1d10 and adds it to the specified attribute and skill.
    """
    key = "roll"
    aliases = ["check"]
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    def func(self):
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: roll <attribute> <skill>")
            return

        attr, skill = self.args.split()
        char = self.caller
        sheet = char.character_sheet

        full_attr_name = get_full_attribute_name(attr)
        full_skill_name = get_full_attribute_name(skill)

        if not full_attr_name or full_attr_name not in STAT_MAPPING.values():
            self.caller.msg(f"Invalid attribute. Choose from: {', '.join(STAT_MAPPING.values())}")
            return

        if not full_skill_name or full_skill_name not in SKILL_MAPPING.values():
            self.caller.msg(f"Invalid skill. Choose from: {', '.join(SKILL_MAPPING.values())}")
            return

        attr_value = getattr(sheet, full_attr_name, 0)
        skill_value = getattr(sheet, full_skill_name, 0)

        dice_roll = random.randint(1, 10)
        total = attr_value + skill_value + dice_roll

        self.caller.msg(f"Rolling {full_attr_name.capitalize()} + {full_skill_name.capitalize()} + 1d10")
        self.caller.msg(f"Result: {attr_value} + {skill_value} + {dice_roll} = {total}")

class CmdRole(Command):
    """
    Select your character's role.

    Usage:
      role <role>

    Available roles: Rockerboy, Solo, Netrunner, Tech, Medtech, Media, Exec, Lawman, Fixer, Nomad
    """
    locks = "cmd:all()"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: role <role>")
            return

        role = self.args.strip().capitalize()
        valid_roles = ['Rockerboy', 'Solo', 'Netrunner', 'Tech', 'Medtech', 'Media', 'Exec', 'Lawman', 'Fixer', 'Nomad']

        if role not in valid_roles:
            self.caller.msg(f"Invalid role. Choose from: {', '.join(valid_roles)}")
            return

        self.caller.character_sheet.role = role
        self.caller.character_sheet.save()
        self.caller.msg(f"Your role has been set to {role}.")

class CmdSpendLuck(Command):
    """
    Spend a luck point.

    Usage:
      luck

    This command spends one luck point if you have any available.
    """

    key = "luck"
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    def func(self):
        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet!")
            return

        sheet = self.caller.character_sheet
        
        def spend_luck(sheet):
            if sheet.current_luck > 0:
                sheet.current_luck -= 1
                sheet.save()
                return True
            return False
        
        if spend_luck(sheet):
            self.caller.msg(f"You spend a luck point. Remaining luck: {sheet.current_luck}/{sheet.luck}")
        else:
            self.caller.msg("You don't have any luck points to spend!")

class CmdGainLuck(Command):
    """
    Regain luck points.

    Usage:
      gainluck <amount>

    This command allows you to regain luck points up to your maximum.
    """

    key = "gainluck"
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: gainluck <amount>")
            return

        try:
            amount = int(self.args)
        except ValueError:
            self.caller.msg("Please provide a valid number.")
            return

        if amount <= 0:
            self.caller.msg("Please provide a positive number.")
            return

        if not hasattr(self.caller, 'character_sheet'):
            self.caller.msg("You don't have a character sheet!")
            return

        sheet = self.caller.character_sheet
        
        def gain_luck(sheet, amount):
            sheet.current_luck = min(sheet.current_luck + amount, sheet.luck)
            sheet.save()
            return sheet.current_luck
        
        new_luck = gain_luck(sheet, amount)
        self.caller.msg(f"You regained luck points. Current luck: {new_luck}/{sheet.luck}")