import random
from evennia import Command, logger, search_object, default_cmds
from world.utils.character_utils import get_full_attribute_name, ALL_ATTRIBUTES, TOPSHEET_MAPPING
from world.utils.calculation_utils import get_remaining_points, STAT_MAPPING, SKILL_MAPPING
from typeclasses.chargen import ChargenRoom
from evennia.utils import evtable
from evennia.utils.utils import list_to_string, inherits_from
from evennia.utils.create import create_object
from evennia.utils import create
from world.cyberpunk_sheets.models import CharacterSheet
from world.languages.models import Language
from evennia.utils.evtable import EvTable
from world.utils.formatting import header, footer, divider
from world.utils.ansi_utils import wrap_ansi
from world.inventory.models import Weapon, Armor, Gear, Inventory
from evennia.commands.default.muxcommand import MuxCommand
from world.lifepath_dictionary import CULTURAL_ORIGINS, PERSONALITIES, CLOTHING_STYLES, HAIRSTYLES, AFFECTATIONS, MOTIVATIONS, LIFE_GOALS, ROLE_SPECIFIC_LIFEPATHS, VALUED_PERSON, VALUED_POSSESSION, FAMILY_BACKGROUND, ENVIRONMENT, FAMILY_CRISIS
from math import ceil

class CmdSheet(MuxCommand):
    """
    Show character sheet or lifepath details

    Usage:
      sheet
      sheet/lifepath

    Switches:
      lifepath - Show detailed lifepath information
    """

    key = "sheet"
    aliases = ["char", "character"]
    lock = "cmd:all()"
    help_category = "Character"

    def safe_get_attr(self, obj, attr):
        """Safely get an attribute value, returning 'N/A' if it doesn't exist."""
        return getattr(obj, attr, 'N/A')

    def func(self):
        if "lifepath" in self.switches:
            self.view_lifepath()
        else:
            self.view_sheet()

    def view_lifepath(self):
        try:
            cs = self.caller.character_sheet
        except AttributeError:
            self.caller.msg("You don't have a character sheet yet. Use the 'lifepath' command to create one.")
            return

        if not cs:
            self.caller.msg("You don't have a character sheet yet. Use the 'lifepath' command to create one.")
            return

        width = 80
        title_width = 30
        output = ""

        # Main header
        output += header(f"Lifepath for {cs.full_name}", width=width, fillchar="|m-|n") + "\n"

        # Present Section
        output += divider("|yPresent|n", width=width, fillchar="|m=|n") + "\n"
        present_fields = [
            ("Cultural Origin", "cultural_origin"),
            ("Personality", "personality"),
            ("Clothing Style", "clothing_style"),
            ("Hairstyle", "hairstyle"),
            ("Affectation", "affectation"),
            ("Motivation", "motivation"),
            ("Life Goal", "life_goal"),
            ("Most Valued Person", "valued_person"),
        ]
        for title, field in present_fields:
            value = getattr(cs, field, "Not set")
            output += self.wrap_field(title, value, width, title_width)
        output += "\n"

        # Past Section
        output += divider("|yPast|n", width=width, fillchar="|m=|n") + "\n"
        past_fields = [
            ("Valued Possession", "valued_possession"),
            ("Family Background", "family_background"),
            ("Origin Environment", "environment"),
            ("Family Crisis", "family_crisis")
        ]
        for title, field in past_fields:
            value = getattr(cs, field, "Not set")
            output += self.wrap_field(title, value, width, title_width)
        output += "\n"

        # Role Section
        if cs.role:
            output += divider(f"|yRole: {cs.role}|n", width=width, fillchar="|m=|n") + "\n"
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
                    output += self.wrap_field(title, value, width, title_width)
            output += "\n"

        output += footer(width=width, fillchar="|m-|n")
        
        # Send the formatted output to the caller
        self.caller.msg(output)

    def wrap_field(self, title, value, width=80, title_width=30):
        wrapped_title = wrap_ansi(title, width=title_width)
        wrapped_value = wrap_ansi(value, width=width-title_width-1)
        
        title_lines = wrapped_title.split('\n')
        value_lines = wrapped_value.split('\n')
        
        output = ""
        for i in range(max(len(title_lines), len(value_lines))):
            title_line = title_lines[i] if i < len(title_lines) else ""
            value_line = value_lines[i] if i < len(value_lines) else ""
            
            if i == 0:
                output += f"|c{title_line:<{title_width}}|n {value_line}\n"
            else:
                output += f"|c{title_line:<{title_width}}|n {value_line}\n"
        
        return output
    
    def view_sheet(self):
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
            ("Night City Rep:", self.safe_get_attr(cs, 'reputation'), "Weight:", f"{self.safe_get_attr(cs, 'weight')} kg"),
            ("Role:", self.safe_get_attr(cs, 'role'), "Luck:", f"{self.safe_get_attr(cs, 'current_luck')}/{self.safe_get_attr(cs, 'luck')}")
        ]
        for row in basic_info:
            output += f"|c{row[0]:<20}|n {row[1]:<20} |c{row[2]:<15}|n {row[3]:<20}\n"

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
        excluded_fields = ['id', 'age', 'height', 'weight', 'hometown', 'account', 'total_cyberware_humanity_loss', 
                        'rep', 'full_name', 'handle', 'gender', 'unarmed_damage_die_type', 'unarmed_damage_dice', 
                        'current_luck', '_max_hp', '_current_hp', 'humanity', 'death_save', 'serious_wounds', 
                        'eurodollars', 'role', 'eqweapon', 'eqarmor', 'humanity_loss', 'is_complete']
        excluded_prefixes = ('intelligence', 'reflexes', 'dexterity', 'technology', 'cool', 
                            'willpower', 'luck', 'move', 'body', 'empathy')
        
        added_skills = set()
        
        for field in cs._meta.get_fields():
            if (field.name not in excluded_fields and 
                not field.name.startswith(excluded_prefixes) and
                not field.is_relation):  # This line excludes relation fields
                value = getattr(cs, field.name, 0)
                if isinstance(value, int) and value > 0:
                    skill_name = field.name.replace('_', ' ').title()
                    if skill_name not in added_skills:
                        skill_list.append([skill_name, value])
                        added_skills.add(skill_name)
        
        # Add role abilities
        role_abilities = ['charismatic_impact', 'combat_awareness', 'interface', 'maker', 
                        'medicine', 'credibility', 'teamwork', 'backup', 'operator', 'moto']
        for ability in role_abilities:
            value = getattr(cs, ability, 0)
            if value > 0:
                ability_name = ability.replace('_', ' ').title()
                if ability_name not in added_skills:
                    skill_list.append([ability_name, value])
                    added_skills.add(ability_name)
        
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

class CmdOOC(MuxCommand):
    """
    Speak or pose out-of-character in your current location.

    Usage:
      ooc <message>
      ooc :<pose>

    Examples:
      ooc Hello everyone!
      ooc :waves to the group.
    """
    key = "ooc"
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        if not self.args:
            self.caller.msg("Say or pose what?")
            return

        location = self.caller.location
        if not location:
            self.caller.msg("You are not in any location.")
            return

        # Strip leading and trailing whitespace from the message
        ooc_message = self.args.strip()

        # Check if it's a pose (starts with ':')
        if ooc_message.startswith(':'):
            pose = ooc_message[1:].strip()  # Remove the ':' and any following space
            message = f"<|mOOC|n> {self.caller.name} {pose}"
            self_message = f"<|mOOC|n> {self.caller.name} {pose}"
        else:
            message = f"<|mOOC|n> {self.caller.name} says, \"{ooc_message}\""
            self_message = f"<|mOOC|n> You say, \"{ooc_message}\""

        location.msg_contents(message, exclude=self.caller)
        self.caller.msg(self_message)

class CmdPlusIc(MuxCommand):
    """
    Return to the IC area from OOC.

    Usage:
      +ic

    This command moves you back to your previous IC location if available,
    or to the default IC starting room if not. You must be approved to use this command.
    """

    key = "+ic"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller

        # Check if the character is approved
        if not caller.tags.has("approved", category="approval"):
            caller.msg("You must be approved to enter IC areas.")
            return

        # Get the stored pre_ooc_location, or use the default room #30
        target_location = caller.db.pre_ooc_location or search_object("#30")[0]

        if not target_location:
            caller.msg("Error: Unable to find a valid IC location.")
            return

        # Move the caller to the target location
        caller.move_to(target_location, quiet=True)
        caller.msg(f"You return to the IC area ({target_location.name}).")
        target_location.msg_contents(f"{caller.name} has returned to the IC area.", exclude=caller)

        # Clear the pre_ooc_location attribute
        caller.attributes.remove("pre_ooc_location")

class CmdPlusOoc(MuxCommand):
    """
    Move to the OOC area (Limbo).

    Usage:
      +ooc

    This command moves you to the OOC area (Limbo) and stores your
    previous location so you can return later.
    """

    key = "+ooc"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        current_location = caller.location

        # Store the current location as an attribute
        caller.db.pre_ooc_location = current_location

        # Find Limbo (object #2)
        limbo = search_object("#2")[0]

        if not limbo:
            caller.msg("Error: Limbo not found.")
            return

        # Move the caller to Limbo
        caller.move_to(limbo, quiet=True)
        caller.msg(f"You move to the OOC area ({limbo.name}).")
        limbo.msg_contents(f"{caller.name} has entered the OOC area.", exclude=caller)

class CmdMeet(MuxCommand):
    """
    Send a meet request to another player or respond to one.

    Usage:
      +meet <player>
      +meet/accept
      +meet/reject

    Sends a meet request to another player. If accepted, they'll be
    teleported to your location.
    """

    key = "+meet"
    locks = "cmd:all()"
    help_category = "General"

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

    def func(self):
        caller = self.caller

        if not self.args and not self.switches:
            caller.msg("Usage: +meet <player> or +meet/accept or +meet/reject")
            return

        if "accept" in self.switches:
            if not caller.ndb.meet_request:
                caller.msg("You have no pending meet requests.")
                return
            requester = caller.ndb.meet_request
            old_location = caller.location
            caller.move_to(requester.location, quiet=True)
            caller.msg(f"You accept the meet request from {requester.name} and join them.")
            requester.msg(f"{caller.name} has accepted your meet request and joined you.")
            old_location.msg_contents(f"{caller.name} has left to meet {requester.name}.", exclude=caller)
            requester.location.msg_contents(f"{caller.name} appears, joining {requester.name}.", exclude=[caller, requester])
            caller.ndb.meet_request = None
            return

        if "reject" in self.switches:
            if not caller.ndb.meet_request:
                caller.msg("You have no pending meet requests.")
                return
            requester = caller.ndb.meet_request
            caller.msg(f"You reject the meet request from {requester.name}.")
            requester.msg(f"{caller.name} has rejected your meet request.")
            caller.ndb.meet_request = None
            return

        target = self.search_for_character(self.args)
        if not target:
            caller.msg(f"Could not find character '{self.args}'.")
            return

        if target == caller:
            caller.msg("You can't send a meet request to yourself.")
            return

        if target.ndb.meet_request:
            caller.msg(f"{target.name} already has a pending meet request.")
            return

        target.ndb.meet_request = caller
        caller.msg(f"You sent a meet request to {target.name}.")
        target.msg(f"{caller.name} has sent you a meet request. Use +meet/accept to accept or +meet/reject to decline.")
