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
      sheet <character name>

    Switches:
      lifepath - Show detailed lifepath information

    Staff members can view the character sheet of other characters by specifying their name.
    """

    key = "sheet"
    aliases = ["char", "character"]
    lock = "cmd:all()"
    help_category = "Character"

    def safe_get_attr(self, obj, attr):
        """Safely get an attribute value, returning 'N/A' if it doesn't exist."""
        if hasattr(obj, "db") and obj.attributes.has(attr):
            return obj.db.get(attr, 'N/A')
        return getattr(obj, attr, 'N/A')

    def parse(self):
        """Parse command arguments."""
        super().parse()

        if not self.args or self.args in self.switches:
            self.target_name = None
        else:
            self.target_name = self.args.strip()

    def func(self):
        if "lifepath" in self.switches:
            self.view_lifepath()
        else:
            self.view_sheet()

    def get_target_character(self):
        """Get the target character based on user input."""
        caller = self.caller
        
        if not self.target_name:
            return caller
        
        # Check if the caller has staff permissions
        if not caller.check_permstring("builders") and not caller.check_permstring("wizards"):
            caller.msg("|rYou don't have permission to view other character sheets.|n")
            return None
        
        # Search for the target character
        target = caller.search(self.target_name)
        if not target:
            # caller.search already sends a message if no match found
            return None
            
        return target

    def view_lifepath(self):
        target = self.get_target_character()
        if not target:
            return
            
        # Use character object directly instead of character_sheet
        width = 80
        title_width = 30
        output = ""

        # Main header
        output += header(f"Lifepath for {target.db.full_name}", width=width, fillchar="|m-|n") + "\n"

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
            value = target.db.get(field, "Not set")
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
            value = target.db.get(field, "Not set")
            output += self.wrap_field(title, value, width, title_width)
        output += "\n"

        # Role Section
        if target.db.role:
            output += divider(f"|yRole: {target.db.role}|n", width=width, fillchar="|m=|n") + "\n"
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
            for field in role_specific_fields.get(target.db.role, []):
                value = target.db.get(field, None)
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
        target = self.get_target_character()
        if not target:
            return
            
        # Main header
        output = header(f"Character Sheet for {target.db.full_name}", width=80, fillchar="|m-|n") + "\n"

        # Basic Information
        output += divider("Basic Information", width=80, fillchar="|m-|n") + "\n"
        basic_info = [
            ("Full Name:", target.db.full_name, "Gender:", target.db.gender),
            ("Handle:", target.db.handle, "Age:", target.db.age),
            ("Hometown:", target.db.hometown, "Height:", f"{target.db.height} cm"),
            ("Night City Rep:", target.db.rep, "Weight:", f"{target.db.weight} kg"),
            ("Role:", target.db.role, "Luck:", f"{target.db.current_luck}/{target.db.luck}")
        ]
        for row in basic_info:
            output += f"|c{row[0]:<20}|n {row[1]:<20} |c{row[2]:<15}|n {row[3]:<20}\n"

        # Stats
        output += divider("STATS", width=80, fillchar="|m-|n") + "\n"
        stats = [
            ("Intelligence:", target.db.intelligence, "Technology:", target.db.technology, "Move:", target.db.move),
            ("Reflexes:", target.db.reflexes, "Cool:", target.db.cool, "Body:", target.db.body),
            ("Dexterity:", target.db.dexterity, "Willpower:", target.db.willpower, "Empathy:", target.db.empathy)
        ]
        for row in stats:
            output += "".join(f"|c{label:<13}|n {value:<8}" for label, value in zip(row[::2], row[1::2])) + "\n"
        output += "\n"

        # Skills
        output += divider("SKILLS", width=80, fillchar="|m-|n") + "\n"
        active_skills = self.get_active_skills(target)
        for i in range(0, len(active_skills), 3):
            row = active_skills[i:i+3]
            output += "".join(f"|c{skill:<20}|n {value:<5}" for skill, value in row).ljust(80) + "\n"
        output += "\n"

        # Derived Stats
        output += divider("Derived Statistics", width=80, fillchar="|m-|n") + "\n"
        derived_stats = [
            ("Hit Points:", f"{target.db.current_hp}/{target.db.max_hp}", "Death Save:", target.db.death_save),
            ("Serious Wounds:", target.db.serious_wounds, "Humanity:", target.db.humanity)
        ]
        for row in derived_stats:
            output += "".join(f"|c{label:<16}|n {value:<18}" for label, value in zip(row[::2], row[1::2])) + "\n"
        output += "\n"

        # Equipment
        output += divider("Equipment", width=80, fillchar="|m-|n") + "\n"
        try:
            # First try to get inventory directly from character if possible
            if hasattr(target, 'inventory') and target.inventory:
                inv = target.inventory
            else:
                # Fall back to model if needed
                from world.inventory.models import Inventory
                inv = Inventory.objects.get(character_object=target)
        except Exception as e:
            logger.log_err(f"Error retrieving inventory for {target}: {str(e)}")
            output += "Error retrieving inventory\n"
        else:
            weapons = inv.weapons.all() if hasattr(inv, 'weapons') else []
            if weapons:
                output += "|cWeapons:|n\n"
                for weapon in weapons:
                    if weapon.name and weapon.damage and weapon.rof:
                        output += f"- {weapon.name:<20} Damage: {weapon.damage:<10} ROF: {weapon.rof}\n"
                    else:
                        logger.log_warn(f"Incomplete weapon data found: {weapon.id}")
            else:
                output += "Weapons: None\n"

            armor = inv.armor.all() if hasattr(inv, 'armor') else []
            if armor:
                output += "|cArmor:|n\n"
                for piece in armor:
                    output += f"- {piece.name:<20} SP: {piece.sp}, EV: {piece.ev:<10} Locations: {piece.locations}\n"
            else:
                output += "Armor: None\n"

            gear = inv.gear.all() if hasattr(inv, 'gear') else []
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
        if hasattr(target, 'languages') and target.languages:
            for lang_name, level in target.languages.items():
                output += f"- {lang_name} (Level {level})\n"
        else:
            output += "None\n"

        output += footer(width=80, fillchar="|m-|n")
        self.caller.msg(output)

    def get_active_skills(self, char):
        """
        Get a list of active skills (skills with value > 0) directly from the character.
        """
        skill_list = []
        
        # Get skills from character's skills dictionary
        if hasattr(char, 'db') and char.db.skills:
            for skill_name, value in char.db.skills.items():
                if value > 0:
                    skill_name = skill_name.replace('_', ' ').title()
                    skill_list.append([skill_name, value])
        
        # Add role abilities
        role_abilities = {
            'charismatic_impact': 'Charismatic Impact',
            'combat_awareness': 'Combat Awareness',
            'interface': 'Interface',
            'maker': 'Maker',
            'medicine': 'Medicine',
            'credibility': 'Credibility',
            'teamwork': 'Teamwork',
            'backup': 'Backup',
            'operator': 'Operator',
            'moto': 'Moto'
        }
        
        for ability_key, ability_name in role_abilities.items():
            if char.db.skills and ability_key in char.db.skills:
                value = char.db.skills[ability_key]
                if value > 0:
                    skill_list.append([ability_name, value])
        
        # Add skill instances from character typeclass
        if hasattr(char, 'db') and char.db.skill_instances:
            for skill_key, value in char.db.skill_instances.items():
                if value > 0 and "(" in skill_key and ")" in skill_key:
                    # Extract the base name and instance from the key (format: "base_skill(instance)")
                    base_name, instance = skill_key.split("(", 1)
                    instance = instance.rstrip(")")
                    # Format as "Base Skill (Instance)"
                    formatted_name = f"{base_name.replace('_', ' ').title()} ({instance})"
                    skill_list.append([formatted_name, value])
        
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

        full_attr_name = get_full_attribute_name(attr)
        full_skill_name = get_full_attribute_name(skill)

        if not full_attr_name or full_attr_name not in STAT_MAPPING.values():
            self.caller.msg(f"Invalid attribute. Choose from: {', '.join(STAT_MAPPING.values())}")
            return

        if not full_skill_name or full_skill_name not in SKILL_MAPPING.values():
            self.caller.msg(f"Invalid skill. Choose from: {', '.join(SKILL_MAPPING.values())}")
            return

        # Get attribute value directly from character
        attr_value = char.db.get(full_attr_name, 0)
        
        # Get skill value from character's skills dictionary
        skill_key = full_skill_name.lower().replace(' ', '_')
        skill_value = char.db.skills.get(skill_key, 0) if char.db.skills else 0

        dice_roll = random.randint(1, 10)
        total = attr_value + skill_value + dice_roll

        self.caller.msg(f"Rolling {full_attr_name.capitalize()} + {full_skill_name.capitalize()} + 1d10")
        self.caller.msg(f"Result: {attr_value} + {skill_value} + {dice_roll} = {total}")

class CmdLuck(Command):
    """
    Spend a luck point.

    Usage:
      luck        - Spend one luck point if you have any available.
      luck/gain <amount> - Regain luck points up to your maximum.
    """

    key = "luck"
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    def func(self):
        char = self.caller
        
        # Handle the gain switch
        if "gain" in self.switches:
            self.gain_luck()
            return
        
        # Handle spending luck
        current_luck = char.db.current_luck
        max_luck = char.db.luck
        
        if current_luck is None or max_luck is None:
            self.caller.msg("Your luck attributes aren't properly set up.")
            return
            
        if current_luck > 0:
            char.db.current_luck = current_luck - 1
            self.caller.msg(f"You spend a luck point. Remaining luck: {char.db.current_luck}/{max_luck}")
        else:
            self.caller.msg("You don't have any luck points to spend!")
        
    def gain_luck(self):
        """Handle gaining luck points."""
        if not self.args:
            self.caller.msg("Usage: luck/gain <amount>")
            return

        try:
            amount = int(self.args)
        except ValueError:
            self.caller.msg("Please provide a valid number.")
            return
        
        if amount <= 0:
            self.caller.msg("Please provide a positive number.")
            return

        char = self.caller
        current_luck = char.db.current_luck
        max_luck = char.db.luck
        
        if current_luck is None or max_luck is None:
            self.caller.msg("Your luck attributes aren't properly set up.")
            return

        if current_luck >= max_luck:
            self.caller.msg("You already have the maximum number of luck points.")
            return

        new_luck = min(current_luck + amount, max_luck)
        char.db.current_luck = new_luck
        self.caller.msg(f"You regained {amount} luck points. Current luck: {new_luck}/{max_luck}")

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
            self_message = f"<|mOOC|n> You say, \"{ooc_message}\""
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
