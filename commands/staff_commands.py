"""
Staff commands for character management.

Provides staff with tools to:
- Add/remove Night City reputation (+rep/add, +rep/remove)
- Add/remove Night City notoriety (+notoriety/add, +notoriety/remove)
- Remove cyberware (normal or plot/retain humanity loss)
- Remove gear (weapons, armor, gear) - see CmdRemoveEquipment
- Remove money - see CmdAdminMoney
- Change or remove lifepath/bio information
- Configure game settings (+config) - developer only
"""
from evennia.commands.default.muxcommand import MuxCommand
from evennia import Command, create_script
from evennia.scripts.models import ScriptDB
from world.cyberware.models import Cyberware
from world.ip_config import (
    get_ip_config,
    get_vote_system_enabled,
    get_vote_ip_amount,
    get_vote_cooldown_hours,
    get_weekly_allotment_enabled,
    get_weekly_allotment_amount,
    IPConfigScript,
)
from world.inventory.models import CyberwareInstance, Inventory, Weapon, Armor, Gear
from world.cyberpunk_sheets.models import CharacterSheet
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from world.cyberpunk_sheets.edgerunner import EdgerunnerChargen


def get_character_and_sheet(caller, target_name):
    """
    Resolve a target name to (character, character_sheet).
    Works with character name or account name.
    Returns (None, None) if not found.
    """
    if not target_name:
        return None, None

    target = caller.search(target_name, global_search=True)
    if not target:
        return None, None

    # If we got a Character (typeclass) - has .db and often .character_sheet or .account
    if hasattr(target, 'db') and hasattr(target, 'attributes'):
        # Likely a Character/Object
        char_sheet = getattr(target, 'character_sheet', None)
        if char_sheet:
            return target, char_sheet
        try:
            sheet = CharacterSheet.objects.get(character=target)
            return target, sheet
        except CharacterSheet.DoesNotExist:
            pass

    # If we got an Account (has .characters, no .db like Object)
    if hasattr(target, 'characters'):
        try:
            sheet = CharacterSheet.objects.get(account=target)
            character = getattr(sheet, 'character', None)
            return character, sheet
        except CharacterSheet.DoesNotExist:
            caller.msg(f"No character sheet found for {target_name}.")
            return None, None

    # Fallback: try to get sheet by account (target might be Character with .account)
    account = getattr(target, 'account', None)
    if account:
        try:
            sheet = CharacterSheet.objects.get(account=account)
            character = getattr(sheet, 'character', target)
            return character, sheet
        except CharacterSheet.DoesNotExist:
            pass

    return None, None


# Lifepath field definitions - (display name, db attribute name)
LIFEPATH_PRESENT = [
    ("Cultural Origin", "cultural_origin"),
    ("Personality", "personality"),
    ("Clothing Style", "clothing_style"),
    ("Hairstyle", "hairstyle"),
    ("Affectation", "affectation"),
    ("Motivation", "motivation"),
    ("Life Goal", "life_goal"),
    ("Valued Person", "valued_person"),
]
LIFEPATH_PAST = [
    ("Valued Possession", "valued_possession"),
    ("Family Background", "family_background"),
    ("Environment", "environment"),
    ("Family Crisis", "family_crisis"),
]
LIFEPATH_ALL_FIELDS = {attr: label for label, attr in LIFEPATH_PRESENT + LIFEPATH_PAST}


class CmdRemoveCyberware(MuxCommand):
    """
    Remove cyberware from a character (staff only).

    Usage:
      removecyberware <character>=<cyberware name>
      removecyberware/plot <character>=<cyberware name>

    Switches:
      plot - Remove cyberware but retain humanity loss (e.g. cyberware destroyed
             in combat, trauma remains). Use for plot-driven removal.

    Without /plot: Humanity is recalculated; character regains humanity.
    With /plot: Cyberware is removed but humanity stays the same (trauma retained).
    """

    key = "removecyberware"
    aliases = ["rmcyberware", "stripcyberware"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: removecyberware [/plot] <character>=<cyberware name>"
            )
            return

        retain_humanity = "plot" in self.switches
        character_name = self.lhs.strip().strip('"')
        cyberware_name = self.rhs.strip().strip('"')

        character, char_sheet = get_character_and_sheet(self.caller, character_name)
        if not character and not char_sheet:
            self.caller.msg(f"Could not find character '{character_name}'.")
            return
        if not char_sheet:
            self.caller.msg(f"No character sheet for {character_name}.")
            return

        inv_target = character if character else getattr(char_sheet, 'character', None)
        if inv_target:
            inventory, _ = Inventory.get_or_create_for_character(inv_target)
        else:
            inventory, _ = Inventory.objects.get_or_create(character=char_sheet)
        if not inventory:
            self.caller.msg(f"No inventory found for {character_name}.")
            return

        # Find the cyberware instance (by character_object or character_sheet)
        cw_instances = inventory.cyberware.filter(
            cyberware__name__iexact=cyberware_name, installed=True
        )
        if not cw_instances.exists():
            # Also try direct query in case inventory link is stale
            char_obj = character if character else char_sheet.character
            if char_obj:
                cw_instances = CyberwareInstance.objects.filter(
                    character_object=char_obj,
                    cyberware__name__iexact=cyberware_name,
                    installed=True,
                )
            if not cw_instances.exists():
                cw_instances = CyberwareInstance.objects.filter(
                    character_sheet=char_sheet,
                    cyberware__name__iexact=cyberware_name,
                    installed=True,
                )
            if not cw_instances.exists():
                self.caller.msg(
                    f"'{cyberware_name}' not found in {character_name}'s installed cyberware."
                )
                return

        cw_instance = cw_instances.first()
        cyberware = cw_instance.cyberware
        humanity_loss = cyberware.humanity_loss

        # Remove from inventory M2M and delete instance
        inventory.cyberware.remove(cw_instance)
        cw_instance.delete()

        if retain_humanity:
            # Add the humanity loss to trauma (permanent) so it's retained
            char_obj = character if character else char_sheet.character
            if char_obj:
                trauma = getattr(char_obj.db, "trauma_humanity_loss", 0) or 0
                char_obj.db.trauma_humanity_loss = trauma + humanity_loss
            # Also store on sheet for sync (field may not exist pre-migration)
            if hasattr(char_sheet, "trauma_humanity_loss"):
                trauma = getattr(char_sheet, "trauma_humanity_loss", 0) or 0
                char_sheet.trauma_humanity_loss = trauma + humanity_loss
                char_sheet.save(skip_recalculation=True)

            self.caller.msg(
                f"Removed {cyberware.name} from {character_name} (plot removal). "
                f"Humanity loss ({humanity_loss}) retained as trauma."
            )
        else:
            # Recalculate humanity
            if char_sheet:
                char_sheet.calculate_humanity_loss()
            if character:
                EdgerunnerChargen.recalculate_humanity_for_typeclass(character)
            elif char_sheet.character:
                EdgerunnerChargen.recalculate_humanity_for_typeclass(char_sheet.character)

            self.caller.msg(
                f"Removed {cyberware.name} from {character_name}. Humanity recalculated."
            )

        # Notify the character if online
        target_char = character or (char_sheet.character if hasattr(char_sheet, "character") else None)
        if target_char and hasattr(target_char, "msg"):
            if retain_humanity:
                target_char.msg(
                    f"Your {cyberware.name} has been removed (plot). "
                    f"The trauma remains (-{humanity_loss} humanity)."
                )
            else:
                target_char.msg(f"Your {cyberware.name} has been removed.")


class CmdSetLifepath(MuxCommand):
    """
    Set or clear a character's lifepath/bio field (staff only).

    Usage:
      setlifepath <character>=<field> <value>
      setlifepath <character>=<field>  (clears the field)
      setlifepath <character>=/list    (list all fields and current values)

    Examples:
      setlifepath Bob=cultural_origin Street
      setlifepath Alice=motivation ""
      setlifepath Charlie=/list

    Fields: cultural_origin, personality, clothing_style, hairstyle,
            affectation, motivation, life_goal, valued_person,
            valued_possession, family_background, environment, family_crisis
    """

    key = "setlifepath"
    aliases = ["setbio", "editlifepath", "editbio"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: setlifepath <character>=<field> [value]\n"
                "       setlifepath <character>=/list"
            )
            return

        character_name = self.lhs.strip().strip('"')
        rhs = self.rhs.strip()

        character, char_sheet = get_character_and_sheet(self.caller, character_name)
        if not char_sheet:
            self.caller.msg(f"Could not find character '{character_name}'.")
            return

        # Prefer character typeclass; fall back to sheet
        target = character if character else getattr(char_sheet, 'character', None)
        sheet = char_sheet

        if rhs == "/list" or rhs.startswith("/list"):
            self.list_lifepath(target, sheet)
            return

        parts = rhs.split(None, 1)
        field_name = parts[0].lower().strip()
        value = parts[1].strip().strip('"') if len(parts) > 1 else ""

        # Check field exists on sheet (general + role-specific lifepath fields)
        if field_name not in LIFEPATH_ALL_FIELDS and not (sheet and hasattr(sheet, field_name)):
            self.caller.msg(
                f"Unknown field '{field_name}'. Use /list to see valid fields."
            )
            return

        # Set on character (typeclass) and sheet
        if target:
            target.attributes.add(field_name, value)
        if sheet and hasattr(sheet, field_name):
            setattr(sheet, field_name, value)
            sheet.save()

        display_name = LIFEPATH_ALL_FIELDS.get(field_name, field_name)
        if value:
            self.caller.msg(
                f"Set {display_name} for {character_name} to: {value}"
            )
        else:
            self.caller.msg(
                f"Cleared {display_name} for {character_name}."
            )

        # Notify character if online
        notify_target = target or (sheet.character if sheet else None)
        if notify_target and hasattr(notify_target, "msg"):
            if value:
                notify_target.msg(f"Staff has updated your {display_name}.")
            else:
                notify_target.msg(f"Staff has cleared your {display_name}.")

    def list_lifepath(self, target, sheet):
        """List all lifepath fields and their values."""
        output = []
        for label, attr in LIFEPATH_PRESENT + LIFEPATH_PAST:
            if target and hasattr(target, 'attributes'):
                val = target.attributes.get(attr, "")
            elif sheet:
                val = getattr(sheet, attr, "") or ""
            else:
                val = ""
            output.append(f"  {attr}: {val or '(empty)'}")
        self.caller.msg("Lifepath fields:\n" + "\n".join(output))


class CmdReputation(MuxCommand):
    """
    Add or remove Night City reputation from a character (staff only).

    Usage:
      +rep/add <name>=<amount>
      +rep/remove <name>=<amount>

    Switches:
      add    - Add reputation points to the character
      remove - Remove reputation points from the character

    Affects the Night City reputation shown on inventory and sheet displays.
    Rep level (0-10) is derived from reputation points (every 100 points = 1 rank).
    """

    key = "+rep"
    aliases = ["rep"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: +rep/add <name>=<amount>  or  +rep/remove <name>=<amount>"
            )
            return

        if "add" not in self.switches and "remove" not in self.switches:
            self.caller.msg(
                "Specify a switch: +rep/add or +rep/remove"
            )
            return

        if "add" in self.switches and "remove" in self.switches:
            self.caller.msg("Use only one switch: /add or /remove.")
            return

        character_name = self.lhs.strip().strip('"')
        try:
            amount = int(self.rhs.strip())
        except (ValueError, TypeError):
            self.caller.msg("Amount must be a whole number.")
            return

        if amount < 0:
            self.caller.msg("Amount must be non-negative.")
            return

        if amount == 0:
            self.caller.msg("Amount must be greater than zero.")
            return

        character, char_sheet = get_character_and_sheet(self.caller, character_name)
        if not char_sheet:
            self.caller.msg(f"Could not find character '{character_name}'.")
            return

        display_name = character.key if character else getattr(char_sheet, 'full_name', character_name) or character_name

        if "add" in self.switches:
            char_sheet.add_reputation(amount)
            self.caller.msg(
                f"Added {amount} reputation points to {display_name}. "
                f"Night City Rep is now Rank {char_sheet.rep} ({char_sheet.reputation_points} pts)."
            )
        else:
            # remove
            new_points = max(0, char_sheet.reputation_points - amount)
            char_sheet.reputation_points = new_points
            char_sheet.update_rep()
            char_sheet.save()
            self.caller.msg(
                f"Removed {amount} reputation points from {display_name}. "
                f"Night City Rep is now Rank {char_sheet.rep} ({char_sheet.reputation_points} pts)."
            )

        # Sync to character typeclass if present
        target_char = character or getattr(char_sheet, 'character', None)
        if target_char and hasattr(target_char, 'attributes'):
            target_char.attributes.add('reputation_points', char_sheet.reputation_points)
            target_char.attributes.add('rep', char_sheet.rep)

        # Notify the character if online
        if target_char and hasattr(target_char, 'msg'):
            if "add" in self.switches:
                target_char.msg(
                    f"Staff has added {amount} reputation points. "
                    f"Your Night City Rep is now Rank {char_sheet.rep}."
                )
            else:
                target_char.msg(
                    f"Staff has removed {amount} reputation points. "
                    f"Your Night City Rep is now Rank {char_sheet.rep}."
                )


class CmdNotoriety(MuxCommand):
    """
    Add or remove Night City notoriety from a character (staff only).

    Notoriety is negative reputation (cancels out rep bonuses). Award for
    failed jobs, cowardice, double-crossing, etc.

    Usage:
      +notoriety/add <name>=<amount>
      +notoriety/remove <name>=<amount>

    Switches:
      add    - Add notoriety points to the character
      remove - Remove notoriety points from the character

    Affects the Night City notoriety shown on inventory and sheet displays.
    Notoriety rank (0-10) is derived from points (every 100 points = 1 rank).
    """

    key = "+notoriety"
    aliases = ["notoriety"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: +notoriety/add <name>=<amount>  or  +notoriety/remove <name>=<amount>"
            )
            return

        if "add" not in self.switches and "remove" not in self.switches:
            self.caller.msg(
                "Specify a switch: +notoriety/add or +notoriety/remove"
            )
            return

        if "add" in self.switches and "remove" in self.switches:
            self.caller.msg("Use only one switch: /add or /remove.")
            return

        character_name = self.lhs.strip().strip('"')
        try:
            amount = int(self.rhs.strip())
        except (ValueError, TypeError):
            self.caller.msg("Amount must be a whole number.")
            return

        if amount < 0:
            self.caller.msg("Amount must be non-negative.")
            return

        if amount == 0:
            self.caller.msg("Amount must be greater than zero.")
            return

        character, char_sheet = get_character_and_sheet(self.caller, character_name)
        if not char_sheet:
            self.caller.msg(f"Could not find character '{character_name}'.")
            return

        display_name = character.key if character else getattr(char_sheet, 'full_name', character_name) or character_name

        if "add" in self.switches:
            char_sheet.add_notoriety(amount)
            self.caller.msg(
                f"Added {amount} notoriety points to {display_name}. "
                f"Night City Notoriety is now Rank {char_sheet.notoriety} ({char_sheet.notoriety_points} pts)."
            )
        else:
            new_points = max(0, char_sheet.notoriety_points - amount)
            char_sheet.notoriety_points = new_points
            char_sheet.update_notoriety()
            char_sheet.save()
            self.caller.msg(
                f"Removed {amount} notoriety points from {display_name}. "
                f"Night City Notoriety is now Rank {char_sheet.notoriety} ({char_sheet.notoriety_points} pts)."
            )

        # Sync to character typeclass if present
        target_char = character or getattr(char_sheet, 'character', None)
        if target_char and hasattr(target_char, 'attributes'):
            target_char.attributes.add('notoriety_points', char_sheet.notoriety_points)
            target_char.attributes.add('notoriety', char_sheet.notoriety)

        # Notify the character if online
        if target_char and hasattr(target_char, 'msg'):
            if "add" in self.switches:
                target_char.msg(
                    f"Staff has added {amount} notoriety points. "
                    f"Your Night City Notoriety is now Rank {char_sheet.notoriety}."
                )
            else:
                target_char.msg(
                    f"Staff has removed {amount} notoriety points. "
                    f"Your Night City Notoriety is now Rank {char_sheet.notoriety}."
                )


class CmdConfig(MuxCommand):
    """
    Configure game-specific settings (developer only).

    Usage:
      +config                       - List current IP settings
      +config vote on|off            - Enable/disable vote IP system
      +config vote <amount>          - Set IP per vote (default 0.5)
      +config vote cooldown <hours>  - Hours between votes per char (default 24)
      +config weekly on|off          - Enable/disable weekly IP allotment
      +config weekly <amount>        - Set IP per week (default 3)

    Examples:
      +config vote on
      +config vote 1.0
      +config vote cooldown 12
      +config weekly on
      +config weekly 5
    """

    key = "+config"
    aliases = ["config"]
    locks = "cmd:perm(Developer)"
    help_category = "Admin"

    def func(self):
        acct = getattr(self.caller, "account", self.caller)
        if not (acct and acct.check_permstring("Developer")):
            self.caller.msg("Only developers can modify game configuration.")
            return

        config = get_ip_config()
        if not config:
            # Create if missing
            config = create_script(IPConfigScript, key="IPConfig")
            if not config or (isinstance(config, bool) and not config):
                try:
                    config = ScriptDB.objects.get(db_key="IPConfig")
                except ScriptDB.DoesNotExist:
                    self.caller.msg("Could not create config. Contact an admin.")
                    return
            if isinstance(config, bool):
                self.caller.msg("Config script created but could not load.")
                return

        args = self.args.strip().lower().split()
        if not args:
            self._list_config(config)
            return

        setting = args[0]
        if setting == "vote":
            self._config_vote(config, args[1:])
        elif setting == "weekly":
            self._config_weekly(config, args[1:])
        else:
            self.caller.msg("Unknown setting. Use: vote, weekly. Type +config for list.")

    def _list_config(self, config):
        vote_on = config.db.vote_system_enabled or False
        vote_amt = config.db.vote_ip_amount if config.db.vote_ip_amount is not None else 0.5
        vote_cooldown = config.db.vote_cooldown_hours if config.db.vote_cooldown_hours is not None else 24
        week_on = config.db.weekly_allotment_enabled or False
        week_amt = config.db.weekly_allotment_amount if config.db.weekly_allotment_amount is not None else 3

        self.caller.msg(
            "|wIP Configuration|n\n"
            f"  Vote system: |{'g' if vote_on else 'r'}{'on' if vote_on else 'off'}|n "
            f"(IP per vote: {vote_amt}, cooldown: {vote_cooldown}h)\n"
            f"  Weekly allotment: |{'g' if week_on else 'r'}{'on' if week_on else 'off'}|n (IP per week: {week_amt})"
        )

    def _config_vote(self, config, rest):
        if not rest:
            self.caller.msg("Usage: +config vote on|off|<amount>|cooldown <hours>")
            return
        val = rest[0].lower()
        if val == "cooldown":
            if len(rest) < 2:
                self.caller.msg("Usage: +config vote cooldown <hours>")
                return
            try:
                hours = int(rest[1])
                if hours < 1:
                    self.caller.msg("Cooldown must be at least 1 hour.")
                    return
                config.db.vote_cooldown_hours = hours
                self.caller.msg(f"Vote cooldown set to {hours} hours per character.")
            except ValueError:
                self.caller.msg("Cooldown must be a whole number of hours.")
            return
        if val in ("on", "1", "true", "yes"):
            config.db.vote_system_enabled = True
            self.caller.msg("Vote IP system enabled.")
        elif val in ("off", "0", "false", "no"):
            config.db.vote_system_enabled = False
            self.caller.msg("Vote IP system disabled.")
        else:
            try:
                amt = float(val)
                if amt < 0:
                    self.caller.msg("IP amount must be non-negative.")
                    return
                config.db.vote_ip_amount = amt
                self.caller.msg(f"IP per vote set to {amt}.")
            except ValueError:
                self.caller.msg("For amount, use a number (e.g. 0.5 or 1.0).")

    def _config_weekly(self, config, rest):
        if not rest:
            self.caller.msg("Usage: +config weekly on|off|<amount>")
            return
        val = rest[0]
        if val in ("on", "1", "true", "yes"):
            config.db.weekly_allotment_enabled = True
            self.caller.msg("Weekly IP allotment enabled.")
        elif val in ("off", "0", "false", "no"):
            config.db.weekly_allotment_enabled = False
            self.caller.msg("Weekly IP allotment disabled.")
        else:
            try:
                amt = int(val)
                if amt < 0:
                    self.caller.msg("IP amount must be non-negative.")
                    return
                config.db.weekly_allotment_amount = amt
                self.caller.msg(f"Weekly IP allotment set to {amt} per week.")
            except ValueError:
                self.caller.msg("For amount, use a whole number (e.g. 3 or 5).")
