"""
Faction and Group commands module for Cyberpunk Evennia.

This module contains commands for interacting with two distinct systems:

1. Factions: Staff-created and managed major entities in the game world
   - Represents corporations, gangs, nomad families, etc.
   - Players can't create them directly but can gain reputation
   - Only admins can manage factions (create, modify, set descriptions)
   - Examples: Arasaka, Militech, Maelstrom, Valentinos, etc.

2. Groups: Player-created and managed organizations
   - Represents player crews, teams, and smaller organizations
   - Players can freely create and manage membership
   - Group leaders can set descriptions, roles, approve members, etc.
   - Examples: Edgerunner crews, player-formed gangs, etc.

These systems use both database models and typeclasses to manage data and
provide in-game functionality.
"""

from evennia import Command, CmdSet, create_object
from evennia.objects.models import ObjectDB
from evennia.commands.default.muxcommand import MuxCommand
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.utils.evtable import EvTable
from evennia.utils.search import search_account
from evennia.utils import logger, crop
from django.core.exceptions import ObjectDoesNotExist
from world.factions.models import Group, Faction as FactionModel, FactionItem
from world.mission_board.models import FactionMissionPoster
from world.factions.models import FactionReputation, GroupRole, GroupMembership, GroupJoinRequest, GroupInfo
from world.factions.faction_types import FACTION_TYPES
from world.factions.default_faction_dictionary import default_faction_dictionary
from world.factions.faction_utils import (
    create_faction_channel,
    get_default_staff_sponsor,
    set_default_staff_sponsor,
    room_has_faction_vendor_tags,
    character_has_faction_rep,
    subscribe_character_to_faction_channel,
)
from world.utils.formatting import sheet_header, sheet_section, footer
from typeclasses.factions import Faction
import random, textwrap

WIDTH = 80

# Abbreviations for faction types (long types truncated for 80-char table)
FACTION_TYPE_ABBREV = {
    "corporation": "corp",
    "service": "svc",
    "gang": "gang",
    "nomad": "nomad",
    "zoner": "zone",
    "edgerunner": "edge",
    "band": "band",
    "reclaimer": "recl",
    "reclaimers": "recl",
}


def _abbreviate_faction_types(ft_list):
    """Convert faction type list to abbreviated string (e.g. ['corporation','service'] -> 'corp/svc')."""
    if not ft_list:
        return "?"
    if isinstance(ft_list, str):
        if ft_list.strip().startswith("["):
            try:
                import ast
                ft_list = ast.literal_eval(ft_list)
            except (ValueError, SyntaxError):
                ft_list = [ft_list]
        else:
            ft_list = [ft_list]
    if not isinstance(ft_list, (list, tuple)):
        ft_list = [ft_list]
    abbrevs = [FACTION_TYPE_ABBREV.get(str(t).lower(), str(t)[:4]) for t in ft_list]
    result = "/".join(abbrevs)
    return result[:10] if len(result) > 10 else result


class CmdFaction(MuxCommand):
    """
    Faction commands. These commands allow for interaction with the major 
    world factions such as corporations, gangs, and nomad families.
    
    Factions are managed by staff and represent major entities in the game world.
    Players can gain reputation with factions through missions and roleplay.

    Usage:
      faction - List all factions
      faction <n> - Display info about a faction
      faction/info <n> - Display information about a faction
      faction/list - List all factions
      faction/rep <n> - Check your reputation with a faction
      faction/influence - Check the current influence of all factions
      faction/mission <n> - Attempt a mission for a faction
    faction/join <faction> - Request to join (creates job for staff sponsor and faction head)
      
    Staff/Faction head commands:
      faction/add <faction>=<character> - Add a character to a faction
      faction/remove <faction>=<character> - Remove a character from a faction
      faction/missionposter <faction>=<add|remove|list> [character] - Designate who can post missions
      
    Admin commands:
      faction/create <n> - Create a new faction (admin only)
      faction/create/type <n>=<type> - Create a faction of specific type
      faction/type <n>=<type> - Change a faction's type
      faction/type/add <n>=<type> - Add another type to a faction
      faction/desc <n>=<description> - Set a description on a faction
      faction/desc/ic <n>=<description> - Set IC description on a faction
      faction/modify <character>/<faction>=<amount> - Modify reputation
      faction/modify/notoriety <character>/<faction>=<amount> - Modify notoriety
      faction/sponsor <faction>=<staff> - Set staff sponsor
      faction/head <faction>=<character> - Set faction head (IC leader)
      faction/init - Initialize default factions
      
    Note: Factions can have multiple types (e.g., both 'nomad' and 'gang'),
    which allows them to represent complex entities in the game world.
    """
    key = "faction"
    aliases = ["+faction"]
    locks = "cmd:all()"
    help_category = "Factions and Groups"

    def func(self):
        if not self.switches and not self.args:
            # Default: List all factions if no switch or arguments
            self.cmd_list()
            return
            
        if not self.switches:
            # If there are args but no switch, interpret as /info
            self.cmd_info(self.args.strip())
            return
            
        # Handle switches
        switch = self.switches[0]  # Use the first switch if multiple provided
        
        # Admin-only commands
        admin_commands = ["create", "type", "desc", "modify", "init", "sponsor", "head", "public", "defaultsponsor", "item"]
        if switch in admin_commands and not self.caller.check_permstring("Admin"):
            self.caller.msg("This faction command is only available to administrators.")
            return
        
        if switch == "create":
            if "type" in self.switches:
                self.cmd_create_type()
            else:
                self.cmd_create()
        elif switch == "info":
            self.cmd_info()
        elif switch == "list":
            self.cmd_list()
        elif switch == "join":
            self.cmd_join()
        elif switch == "leave":
            self.caller.msg("You cannot directly leave major factions. Your reputation with them can change through your actions.")
        elif switch == "rep":
            self.cmd_rep()
        elif switch == "influence":
            self.cmd_influence()
        elif switch == "mission":
            self.cmd_mission()
        elif switch == "type":
            if "add" in self.switches:
                self.cmd_type_add()
            else:
                self.cmd_type()
        elif switch == "desc":
            if "ic" in self.switches:
                self.cmd_desc_ic()
            else:
                self.cmd_desc()
        elif switch == "modify":
            self.cmd_modify()
        elif switch == "init":
            self.cmd_init()
        elif switch == "replist":
            self.cmd_replist()
        elif switch == "sponsor":
            self.cmd_sponsor()
        elif switch == "head":
            self.cmd_head()
        elif switch == "public":
            self.cmd_public()
        elif switch == "defaultsponsor":
            self.cmd_defaultsponsor()
        elif switch == "item":
            self.cmd_item()
        elif switch == "buy":
            self.cmd_buy()
        elif switch == "sell":
            self.cmd_sell()
        elif switch == "items":
            self.cmd_items()
        elif switch == "missionposter":
            self.cmd_missionposter()
        elif switch == "add":
            self.cmd_add_member()
        elif switch == "remove":
            self.cmd_remove_member()
        else:
            self.caller.msg(f"Unknown switch: /{switch}")

    def cmd_list(self):
        """List all factions."""
        factions = FactionModel.objects.all().order_by('-influence')

        if not factions:
            self.caller.msg("There are no factions in the game yet.")
            return

        default_sponsor = get_default_staff_sponsor()
        default_sponsor_name = default_sponsor.username if default_sponsor else None

        output = sheet_header("Faction List", width=WIDTH)
        output += sheet_section("All Factions", width=WIDTH)

        # Column widths (total 80): Faction 22 | Type 10 | Infl 5 | Mem 4 | Head 15 | Sponsor 24
        col = {"faction": 22, "type": 10, "infl": 5, "mem": 4, "head": 15, "sponsor": 24}
        output += f"|y{'Faction':<22}{'Type':<10}{'Infl':<5}{'Mem':<4}{'Head':<15}{'Sponsor':<24}|n\n"

        for faction in factions:
            # Use model's faction_type (list); abbreviate for display
            ft_raw = getattr(faction, "faction_type", None) or []
            faction_type = _abbreviate_faction_types(ft_raw)

            member_count = faction.factionreputation_set.count()

            # Truncate names to column width
            faction_name = faction.name
            if len(faction_name) > col["faction"]:
                faction_name = faction_name[: col["faction"] - 2] + ".."

            head_name = "-"
            if getattr(faction, "faction_head", None):
                head_name = faction.get_character_display_name(faction.faction_head)
            if len(head_name) > col["head"]:
                head_name = head_name[: col["head"] - 2] + ".."

            sponsor_name = "-"
            if getattr(faction, "staff_sponsor", None):
                sponsor_name = faction.staff_sponsor.username
            elif default_sponsor_name:
                sponsor_name = f"Default ({default_sponsor_name})"
            if len(sponsor_name) > col["sponsor"]:
                sponsor_name = sponsor_name[: col["sponsor"] - 2] + ".."

            row_fmt = f"|w{{0:<{col['faction']}}}{{1:<{col['type']}}}{{2:<{col['infl']}}}{{3:<{col['mem']}}}{{4:<{col['head']}}}{{5:<{col['sponsor']}}}|n\n"
            output += row_fmt.format(
                faction_name, faction_type, faction.influence, member_count, head_name, sponsor_name
            )

        output += footer(width=WIDTH, fillchar="-")
        self.caller.msg(output)

    def cmd_info(self, faction_name=None):
        """Display information about a faction."""
        if not faction_name:
            faction_name = self.args.strip()
            
        if not faction_name:
            self.caller.msg("Usage: faction/info <name>")
            return
            
        # Try to get the faction object
        from typeclasses.factions import Faction as FactionTypeclass
        faction_obj = FactionTypeclass.get_faction(faction_name)
        
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        # Get faction type (model stores list) and member count
        ft = getattr(faction, "faction_type", None) or []
        if isinstance(ft, list):
            faction_type = ", ".join(ft) if ft else "Unknown"
        else:
            faction_type = str(ft) if ft else "Unknown"

        member_count = faction.factionreputation_set.count()
        
        # Build output with sheet-style UI
        output = sheet_header(f"Faction: {faction.name}", width=WIDTH)
        output += sheet_section("Overview", width=WIDTH)
        output += f"|y{'Faction Name':<25}|n {faction.name}\n"
        output += f"|y{'Type':<25}|n {faction_type}\n"
        output += f"|y{'Influence':<25}|n {faction.influence}\n"
        output += f"|y{'Members':<25}|n {member_count}\n"
        output += f"|y{'Created':<25}|n {faction.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        output += f"|y{'Membership':<25}|n {'Public' if getattr(faction, 'members_public', True) else 'Private'}\n\n"

        # Leadership: staff sponsor always visible; faction head only when members public
        output += sheet_section("Leadership", width=WIDTH)
        staff_sponsor = getattr(faction, 'staff_sponsor', None)
        if staff_sponsor:
            output += f"|y{'Staff Sponsor':<25}|n {staff_sponsor.username}\n"
        else:
            output += f"|y{'Staff Sponsor':<25}|n Not set\n"
        if getattr(faction, 'members_public', True):
            faction_head = getattr(faction, 'faction_head', None)
            if faction_head:
                head_name = faction.get_character_display_name(faction_head) if hasattr(faction, 'get_character_display_name') else (getattr(faction_head.db, 'full_name', None) or faction_head.key)
                output += f"|y{'Faction Head':<25}|n {head_name}\n"
            else:
                output += f"|y{'Faction Head':<25}|n Not set\n"
        output += "\n"

        # Members list - only when public
        if getattr(faction, 'members_public', True) and member_count > 0:
            output += sheet_section("Members", width=WIDTH)
            reps = faction.factionreputation_set.all()[:20]  # Limit display
            for fr in reps:
                name = faction.get_character_display_name(fr.character) if hasattr(faction, 'get_character_display_name') else (getattr(fr.character.db, 'full_name', None) or fr.character.key)
                output += f"  |w{name}|n - Rep {fr.rep} ({fr.reputation_points} pts)"
                if fr.notoriety_points > 0:
                    output += f", Notoriety {fr.notoriety}"
                output += "\n"
            if member_count > 20:
                output += f"  ... and {member_count - 20} more\n"
            output += "\n"

        output += sheet_section("OOC Description", width=WIDTH)
        output += (crop(faction.description or 'Not set', width=76) + "\n\n")
        output += sheet_section("IC Description", width=WIDTH)
        ic_description = faction.ic_description or 'Not set'
        for line in textwrap.wrap(ic_description, width=76):
            output += line + "\n"
        output += "\n"

        # Player's standing
        char_obj = self.caller
        if char_obj:
            try:
                fr = FactionReputation.objects.get(character=char_obj, faction=faction)
                output += sheet_section("Your Standing", width=WIDTH)
                rep_str = f"Rep: Rank {fr.rep} ({fr.reputation_points} pts)"
                if fr.notoriety_points > 0:
                    rep_str += f" | Notoriety: Rank {fr.notoriety} ({fr.notoriety_points} pts)"
                output += rep_str + "\n"
            except FactionReputation.DoesNotExist:
                pass

        output += footer(width=WIDTH, fillchar="|m-|n")
        self.caller.msg(output)

    def cmd_create(self):
        """Create a new faction (admin only)."""
        from typeclasses.factions import Faction, FACTION_TYPES
        
        if not self.args:
            self.caller.msg("Usage: faction/create <name>")
            self.caller.msg(f"Available types: {', '.join(FACTION_TYPES.keys())}")
            return

        name = self.args.strip()
        # Default to corporation if not specified
        faction_type = "corporation"

        # Check if faction already exists
        if FactionModel.objects.filter(name__iexact=name).exists():
            self.caller.msg(f"A faction named '{name}' already exists.")
            return

        # Create the faction object through our typeclass
        faction = Faction.create_player_faction(
            name=name,
            description=f"A {faction_type} faction",
            ic_description=f"A major {faction_type} in Night City",
            creator=None  # No player creator for staff-created factions
        )
        
        if faction:
            # Set the appropriate faction type
            faction.db.faction_type = faction_type
            faction.update_from_model()
            
            self.caller.msg(f"You have created the {faction_type} faction '{name}'.")
            self.caller.msg("Use faction/type and faction/desc to set more details.")
            self.caller.msg("|yRemember:|n Set the staff sponsor (faction/sponsor) and faction head (faction/head) for this faction.")
            self.caller.msg("|yReminder:|n Set the staff sponsor (faction/sponsor {}=<staff>) and faction head (faction/head {}=<character>).".format(name, name))
        else:
            self.caller.msg("Error creating faction. Check logs for details.")

    def cmd_create_type(self):
        """Create a new faction with specific type (admin only)."""
        from typeclasses.factions import Faction, FACTION_TYPES
        
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/create/type <name>=<type>")
            self.caller.msg(f"Available types: {', '.join(FACTION_TYPES.keys())}")
            return

        name, faction_type = [part.strip() for part in self.args.split("=", 1)]

        # Check permissions
        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can create non-edgerunner factions.")
            return

        # Validate faction type
        if faction_type not in FACTION_TYPES:
            self.caller.msg(f"Invalid faction type. Available types: {', '.join(FACTION_TYPES.keys())}")
            return

        # Check if faction already exists
        if FactionModel.objects.filter(name__iexact=name).exists():
            self.caller.msg(f"A faction named '{name}' already exists.")
            return

        # Create the faction with the specified type
        faction = Faction.create_player_faction(
            name=name,
            description=f"A {faction_type} faction",
            ic_description=f"A {faction_type} in Night City",
            creator=None
        )
        
        if faction:
            faction.db.faction_type = faction_type
            faction.update_from_model()
            
            self.caller.msg(f"You have created the {faction_type} faction '{name}'.")
            self.caller.msg("|yRemember:|n Set the staff sponsor (faction/sponsor) and faction head (faction/head) for this faction.")
        else:
            self.caller.msg("Error creating faction. Check logs for details.")

    def cmd_join(self):
        """Request to join a faction by creating a job for the staff sponsor and faction head."""
        if not self.args:
            self.caller.msg("Usage: faction/join <faction>")
            return

        faction_name = self.args.strip()
        try:
            faction_model = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        faction_obj = Faction.get_faction(faction_name)
        if not faction_obj:
            self.caller.msg(f"Faction object for '{faction_name}' not found.")
            return

        # Check if already a member
        if hasattr(self.caller, 'db') and self.caller.db.faction == faction_obj.key:
            self.caller.msg(f"You are already a member of '{faction_model.name}'.")
            return

        # Get requester account (player)
        requester = getattr(self.caller, 'account', self.caller)
        if not requester or not hasattr(requester, 'username'):
            self.caller.msg("You need to be logged in to request faction membership.")
            return

        # Assignee: faction's staff sponsor, or default sponsor
        assignee = faction_model.staff_sponsor
        if not assignee:
            assignee = get_default_staff_sponsor()
        if not assignee:
            self.caller.msg(f"Faction {faction_model.name} has no staff sponsor. Contact staff.")
            return

        # Build description
        char_display = getattr(self.caller.db, 'full_name', None) or self.caller.key
        description = (
            f"{char_display} ({self.caller.key}) wishes to join the {faction_model.name} faction.\n\n"
            f"Staff sponsor: {assignee.username}\n"
            f"Faction head: {faction_model.get_character_display_name(faction_model.faction_head) if faction_model.faction_head else 'Not set'}\n\n"
            f"When approved, use faction/add {faction_model.name}={char_display} to add them."
        )

        # Create job
        from world.jobs.models import Job, Queue

        queue, _ = Queue.objects.get_or_create(
            name="FACTION",
            defaults={"automatic_assignee": None}
        )

        job = Job.objects.create(
            title=f"Faction Join: {faction_model.name}",
            description=description,
            requester=requester,
            assignee=assignee,
            queue=queue,
            status="claimed",
        )
        job.participants.add(requester)

        # Add faction head as participant if set
        faction_head = faction_model.faction_head
        if faction_head:
            head_account = getattr(faction_head, 'account', None) or getattr(faction_head, 'db_account', None)
            if head_account and head_account != requester:
                job.participants.add(head_account)

        # Notify assignee
        if assignee != requester:
            self.caller.execute_cmd(
                f"@mail {assignee.username}=Faction Join Request: {faction_model.name}/"
                f"{char_display} has submitted a request to join {faction_model.name}. "
                f"Job #{job.id} has been assigned to you."
            )

        # Post to jobs channel
        try:
            from evennia.comms.models import ChannelDB
            channel_names = ["Jobs", "Requests", "Req"]
            channel = None
            for name in channel_names:
                found = ChannelDB.objects.channel_search(name)
                if found:
                    channel = found[0]
                    break
            if channel:
                channel.msg(f"[Job System] {requester.username} created Job #{job.id} (Faction Join: {faction_model.name})")
        except Exception:
            pass

        self.caller.msg(
            f"|gFaction join request submitted.|n Job #{job.id} has been created and assigned to {assignee.username}. "
            f"The faction head has been added as a participant. Staff will process your request."
        )

    def cmd_leave(self):
        """Leave your current faction."""
        if not hasattr(self.caller, 'db') or not self.caller.db.faction:
            self.caller.msg("You are not currently affiliated with any faction.")
            return
            
        faction_name = self.caller.db.faction
        faction_obj = Faction.get_faction(faction_name)
        
        if not faction_obj:
            # If faction object doesn't exist, just clear the attribute
            self.caller.db.faction = None
            self.caller.msg(f"You are no longer affiliated with {faction_name}.")
            return
            
        if faction_obj.remove_member(self.caller):
            self.caller.msg(f"You have left the faction '{faction_name}'.")
        else:
            self.caller.msg(f"Failed to leave {faction_name}. Please contact an admin.")

    def cmd_rep(self):
        """Check your reputation and notoriety with a faction."""
        if not self.args:
            if not hasattr(self.caller, 'db') or not self.caller.db.faction:
                self.caller.msg("You are not currently affiliated with any faction.")
                return
            faction_name = self.caller.db.faction
        else:
            faction_name = self.args.strip()

        if not self.caller.character_sheet:
            self.caller.msg("You need a character sheet to check faction standing.")
            return

        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        fr, created = FactionReputation.objects.get_or_create(
            character=self.caller,
            faction=faction,
            defaults={"reputation_points": 0, "rep": 0, "notoriety_points": 0, "notoriety": 0}
        )
        rep_str = f"Rep: Rank {fr.rep} ({fr.reputation_points} pts)"
        if fr.notoriety_points > 0:
            rep_str += f" | Notoriety: Rank {fr.notoriety} ({fr.notoriety_points} pts)"
        self.caller.msg(f"Your standing with {faction.name}: {rep_str}")

    def cmd_influence(self):
        """Check the influence of all factions."""
        factions = FactionModel.objects.all().order_by('-influence')

        if not factions:
            self.caller.msg("There are no factions in the game yet.")
            return

        table = EvTable("Faction", "Type", "Influence", border="cells")
        
        for faction in factions:
            faction_obj = Faction.get_faction(faction.name)
            faction_type = faction_obj.db.faction_type if faction_obj else "Unknown"
            table.add_row(faction.name, faction_type, faction.influence)

        self.caller.msg(table)

    def cmd_mission(self):
        """Attempt a mission for a faction to gain reputation."""
        if not self.args:
            self.caller.msg("Usage: faction/mission <faction_name>")
            return

        faction_name = self.args.strip()
        character_sheet = self.caller.character_sheet
        if not character_sheet:
            self.caller.msg("You need a character sheet to attempt faction missions.")
            return

        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        # Simple mission success calculation
        success_chance = 50 + character_sheet.cool + character_sheet.streetwise
        roll = random.randint(1, 100)

        if roll <= success_chance:
            reputation_gain = random.randint(1, 5)
            influence_gain = random.randint(1, 3)

            reputation, created = FactionReputation.objects.get_or_create(
                character=self.caller,
                faction=faction
            )
            reputation.reputation_points += reputation_gain
            reputation.update_rep()
            reputation.save()

            faction.influence += influence_gain
            faction.save()

            self.caller.msg(f"Mission successful! You gained {reputation_gain} reputation with {faction.name}.")
            self.caller.msg(f"{faction.name}'s influence increased by {influence_gain}.")
        else:
            self.caller.msg(f"Mission failed. Better luck next time, {self.caller.name}.")

    def cmd_desc(self):
        """Set a faction's general description."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/desc <faction_name> = <description>")
            return

        faction_name, description = [part.strip() for part in self.args.split("=", 1)]

        # Check permissions - only admins can modify faction descriptions
        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can modify faction descriptions.")
            return

        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        # Update the description
        faction.description = description
        faction.save()

        self.caller.msg(f"Updated the general description for faction '{faction_name}'.")
        logger.log_info(f"{self.caller.name} updated the general description for faction '{faction_name}'.")

    def cmd_desc_ic(self):
        """Set a faction's in-character description."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/desc/ic <faction_name> = <description>")
            return

        faction_name, description = [part.strip() for part in self.args.split("=", 1)]

        # Check permissions - only admins can modify faction descriptions
        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can modify faction IC descriptions.")
            return

        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        # Update the IC description
        faction.ic_description = description
        faction.save()

        self.caller.msg(f"Updated the IC description for faction '{faction_name}'.")
        logger.log_info(f"{self.caller.name} updated the IC description for faction '{faction_name}'.")

    def cmd_type(self):
        """Change a faction's type (admin only)."""
        from typeclasses.factions import FACTION_TYPES
        
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/type <faction_name> = <type>")
            self.caller.msg(f"Available types: {', '.join(FACTION_TYPES.keys())}")
            return

        faction_name, faction_type = [part.strip() for part in self.args.split("=", 1)]

        # Check permissions
        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can change faction types.")
            return

        # Validate faction type
        if faction_type not in FACTION_TYPES:
            self.caller.msg(f"Invalid faction type. Available types: {', '.join(FACTION_TYPES.keys())}")
            return

        # Get the faction
        faction_obj = Faction.get_faction(faction_name)
        if not faction_obj:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        # Update the faction type (replacing any existing types)
        faction_obj.db.faction_type = [faction_type]
        
        # Update the model if it exists
        if faction_obj.model:
            faction_obj.model.faction_type = [faction_type]
            faction_obj.model.save()
            
        self.caller.msg(f"Changed {faction_name}'s type to {faction_type}.")
        logger.log_info(f"{self.caller.name} changed {faction_name}'s type to {faction_type}.")

    def cmd_type_add(self):
        """Add an additional type to a faction."""
        from typeclasses.factions import FACTION_TYPES
        
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/type/add <faction_name> = <type>")
            self.caller.msg(f"Available types: {', '.join(FACTION_TYPES.keys())}")
            return

        faction_name, faction_type = [part.strip() for part in self.args.split("=", 1)]

        # Check permissions
        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can add faction types.")
            return

        # Validate faction type
        if faction_type not in FACTION_TYPES:
            self.caller.msg(f"Invalid faction type. Available types: {', '.join(FACTION_TYPES.keys())}")
            return

        # Get the faction
        faction_obj = Faction.get_faction(faction_name)
        if not faction_obj:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        # Add the type to existing types
        current_types = faction_obj.db.faction_type
        if isinstance(current_types, str):
            current_types = [current_types]
        elif not isinstance(current_types, list):
            current_types = []
            
        # Check if type already exists
        if faction_type in current_types:
            self.caller.msg(f"{faction_name} already has the type '{faction_type}'.")
            return
            
        current_types.append(faction_type)
        faction_obj.db.faction_type = current_types
        
        # Update the model if it exists
        if faction_obj.model:
            faction_obj.model.faction_type = current_types
            faction_obj.model.save()
            
        self.caller.msg(f"Added type '{faction_type}' to {faction_name}. Current types: {', '.join(current_types)}")
        logger.log_info(f"{self.caller.name} added type '{faction_type}' to {faction_name}")

    def cmd_modify(self):
        """Modify a character's reputation or notoriety with a faction (admin only)."""
        from commands.staff_commands import get_character_and_sheet

        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: faction/modify <character>/<faction>=<amount>\n"
                "       faction/modify/notoriety <character>/<faction>=<amount>"
            )
            return

        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can modify faction standing.")
            return

        lhs, rhs = self.args.split("=", 1)
        lhs = lhs.strip()
        rhs = rhs.strip()
        if "/" not in lhs:
            self.caller.msg("Usage: faction/modify <character>/<faction>=<amount>")
            return
        char_name, faction_name = [p.strip() for p in lhs.split("/", 1)]
        try:
            amount = int(rhs)
        except ValueError:
            self.caller.msg("Amount must be a number.")
            return
        is_notoriety = "notoriety" in self.switches

        character, char_sheet = get_character_and_sheet(self.caller, char_name)
        if not character and not char_sheet:
            self.caller.msg(f"Character '{char_name}' not found.")
            return
        char_obj = character or (getattr(char_sheet, 'character', None) if char_sheet else None)
        if not char_obj:
            self.caller.msg(f"Character '{char_name}' has no linked object.")
            return

        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"Faction '{faction_name}' not found.")
            return
        except ValueError:
            self.caller.msg("Amount must be a number.")
            return

        fr, created = FactionReputation.objects.get_or_create(
            character=char_obj,
            faction=faction,
            defaults={"reputation_points": 0, "rep": 0, "notoriety_points": 0, "notoriety": 0}
        )
        display_name = getattr(char_obj.db, 'full_name', None) or char_obj.key

        if is_notoriety:
            fr.notoriety_points = max(0, fr.notoriety_points + amount)
            fr.update_notoriety()
            fr.save()
            self.caller.msg(
                f"Modified {display_name}'s notoriety with {faction.name} by {amount}. "
                f"Notoriety: Rank {fr.notoriety} ({fr.notoriety_points} pts)"
            )
        else:
            fr.reputation_points = max(0, fr.reputation_points + amount)
            fr.update_rep()
            fr.save()
            self.caller.msg(
                f"Modified {display_name}'s reputation with {faction.name} by {amount}. "
                f"Rep: Rank {fr.rep} ({fr.reputation_points} pts)"
            )
        # Subscribe character to faction channel when they have standing
        subscribe_character_to_faction_channel(char_obj, faction)

    def cmd_replist(self):
        """Show all faction members and their rep/notoriety. Faction members only."""
        faction_name = self.args.strip() if self.args else None
        if not faction_name:
            self.caller.msg("Usage: faction/replist <faction_name>")
            return
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        # Must have rep with this faction to view
        if not character_has_faction_rep(self.caller, faction):
            self.caller.msg("You must have standing with this faction to view its reputation list.")
            return
        reputations = FactionReputation.objects.filter(faction=faction).order_by('-rep', '-notoriety')
        output = sheet_header(f"Reputation List: {faction.name}", width=WIDTH)
        output += sheet_section("Members and Standing", width=WIDTH)
        output += f"|y{'Character':<30}{'Rep':<8}{'Pts':<8}{'Notoriety':<10}{'Pts':<8}|n\n"
        for fr in reputations:
            name = faction.get_character_display_name(fr.character) if hasattr(faction, 'get_character_display_name') else (getattr(fr.character.db, 'full_name', None) or fr.character.key)
            name = (name or "?")[:29]
            output += f"|w{name:<30}{fr.rep:<8}{fr.reputation_points:<8}{fr.notoriety:<10}{fr.notoriety_points:<8}|n\n"
        output += footer(width=WIDTH, fillchar="|m-|n")
        self.caller.msg(output)

    def cmd_sponsor(self):
        """Set staff sponsor for a faction. Usage: faction/sponsor <faction>=<staff_username>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/sponsor <faction>=<staff_username>")
            return
        faction_name, username = [p.strip() for p in self.args.split("=", 1)]
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        from evennia.accounts.models import AccountDB
        if username.lower() in ("none", "clear", ""):
            faction.staff_sponsor = None
            faction.save()
            self.caller.msg(f"Cleared staff sponsor for {faction.name}.")
            return
        try:
            account = AccountDB.objects.get(username__iexact=username)
        except AccountDB.DoesNotExist:
            self.caller.msg(f"Account '{username}' not found.")
            return
        faction.staff_sponsor = account
        faction.save()
        self.caller.msg(f"Set {username} as staff sponsor for {faction.name}.")

    def cmd_head(self):
        """Set faction head (player character). Usage: faction/head <faction>=<character>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/head <faction>=<character>")
            return
        faction_name, char_name = [p.strip() for p in self.args.split("=", 1)]
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        if char_name.lower() in ("none", "clear", ""):
            faction.faction_head = None
            faction.save()
            self.caller.msg(f"Cleared faction head for {faction.name}.")
            return
        from commands.staff_commands import get_character_and_sheet
        character, _ = get_character_and_sheet(self.caller, char_name)
        if not character:
            self.caller.msg(f"Character '{char_name}' not found.")
            return
        faction.faction_head = character
        faction.save()
        display = getattr(character.db, 'full_name', None) or character.key
        self.caller.msg(f"Set {display} as faction head for {faction.name}.")

    def cmd_public(self):
        """Set whether faction membership is public. Usage: faction/public <faction>=<on|off>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/public <faction>=<on|off>")
            return
        faction_name, val = [p.strip() for p in self.args.split("=", 1)]
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        faction.members_public = val.lower() in ("on", "yes", "1", "true")
        faction.save()
        status = "public" if faction.members_public else "private"
        self.caller.msg(f"Faction {faction.name} membership is now {status}.")

    def cmd_missionposter(self):
        """Faction head: designate who can post missions. Usage: faction/missionposter <faction>=<add|remove|list> [character]"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/missionposter <faction>=<add|remove|list> [character]")
            return
        faction_name, rest = [p.strip() for p in self.args.split("=", 1)]
        parts = rest.split(None, 1)
        subcmd = parts[0].lower() if parts else ""
        char_name = parts[1].strip() if len(parts) > 1 else None
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        faction_obj = Faction.get_faction(faction_name)
        if not faction_obj:
            self.caller.msg("Faction object not found.")
            return
        is_head = faction.faction_head == self.caller
        is_staff = self.caller.check_permstring("Builder")
        if not (is_head or is_staff):
            self.caller.msg("Only the faction head or staff can manage mission posters.")
            return
        if subcmd == "list":
            posters = FactionMissionPoster.objects.filter(faction=faction)
            if not posters:
                self.caller.msg(f"No designated mission posters for {faction.name}.")
                return
            names = []
            for p in posters:
                d = getattr(p.character.db, 'full_name', None) or p.character.key
                names.append(d)
            self.caller.msg(f"Mission posters for {faction.name}: {', '.join(names)}")
        elif subcmd == "add":
            if not char_name:
                self.caller.msg("Usage: faction/missionposter <faction>=add <character>")
                return
            from commands.staff_commands import get_character_and_sheet
            character, _ = get_character_and_sheet(self.caller, char_name)
            if not character:
                self.caller.msg(f"Character '{char_name}' not found.")
                return
            _, created = FactionMissionPoster.objects.get_or_create(faction=faction, character=character)
            if created:
                self.caller.msg(f"Added {character.key} as mission poster for {faction.name}.")
            else:
                self.caller.msg(f"{character.key} is already a mission poster for {faction.name}.")
        elif subcmd == "remove":
            if not char_name:
                self.caller.msg("Usage: faction/missionposter <faction>=remove <character>")
                return
            from commands.staff_commands import get_character_and_sheet
            character, _ = get_character_and_sheet(self.caller, char_name)
            if not character:
                self.caller.msg(f"Character '{char_name}' not found.")
                return
            deleted, _ = FactionMissionPoster.objects.filter(faction=faction, character=character).delete()
            if deleted:
                self.caller.msg(f"Removed {character.key} from mission posters for {faction.name}.")
            else:
                self.caller.msg(f"{character.key} was not a mission poster for {faction.name}.")
        else:
            self.caller.msg("Use add, remove, or list.")

    def cmd_add_member(self):
        """Staff or faction head: Add a character to a faction. Usage: faction/add <faction>=<character>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/add <faction>=<character>")
            return
        faction_name, char_name = [p.strip() for p in self.args.split("=", 1)]
        try:
            faction_model = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        faction_obj = Faction.get_faction(faction_name)
        if not faction_obj:
            self.caller.msg("Faction object not found.")
            return
        is_head = faction_model.faction_head == self.caller
        is_staff = self.caller.check_permstring("Builder")
        if not (is_head or is_staff):
            self.caller.msg("Only the faction head or staff can add members to a faction.")
            return
        from commands.staff_commands import get_character_and_sheet
        character, _ = get_character_and_sheet(self.caller, char_name)
        if not character:
            self.caller.msg(f"Character '{char_name}' not found.")
            return
        if character.id in (faction_obj.db.members or []):
            display = getattr(character.db, 'full_name', None) or character.key
            self.caller.msg(f"{display} is already a member of {faction_model.name}.")
            return
        if faction_obj.add_member(character):
            display = getattr(character.db, 'full_name', None) or character.key
            # Ensure reputation entry exists for the character (ObjectDB)
            FactionReputation.objects.get_or_create(
                character=character,
                faction=faction_model,
                defaults={"reputation_points": 0, "rep": 0, "notoriety_points": 0, "notoriety": 0}
            )
            self.caller.msg(f"Added {display} to {faction_model.name}.")
            logger.log_info(f"{self.caller.key} added {character.key} to faction {faction_model.name}")
        else:
            self.caller.msg("Failed to add member.")

    def cmd_remove_member(self):
        """Staff or faction head: Remove a character from a faction. Usage: faction/remove <faction>=<character>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/remove <faction>=<character>")
            return
        faction_name, char_name = [p.strip() for p in self.args.split("=", 1)]
        try:
            faction_model = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        faction_obj = Faction.get_faction(faction_name)
        if not faction_obj:
            self.caller.msg("Faction object not found.")
            return
        is_head = faction_model.faction_head == self.caller
        is_staff = self.caller.check_permstring("Builder")
        if not (is_head or is_staff):
            self.caller.msg("Only the faction head or staff can remove members from a faction.")
            return
        from commands.staff_commands import get_character_and_sheet
        character, _ = get_character_and_sheet(self.caller, char_name)
        if not character:
            self.caller.msg(f"Character '{char_name}' not found.")
            return
        if character.id not in (faction_obj.db.members or []):
            display = getattr(character.db, 'full_name', None) or character.key
            self.caller.msg(f"{display} is not a member of {faction_model.name}.")
            return
        if faction_obj.remove_member(character):
            display = getattr(character.db, 'full_name', None) or character.key
            self.caller.msg(f"Removed {display} from {faction_model.name}.")
            logger.log_info(f"{self.caller.key} removed {character.key} from faction {faction_model.name}")
        else:
            self.caller.msg("Failed to remove member.")

    def cmd_defaultsponsor(self):
        """Set default staff sponsor for new factions. Usage: faction/defaultsponsor [=username]"""
        if self.rhs:
            username = self.rhs.strip()
            from evennia.accounts.models import AccountDB
            try:
                account = AccountDB.objects.get(username__iexact=username)
            except AccountDB.DoesNotExist:
                self.caller.msg(f"Account '{username}' not found.")
                return
            if set_default_staff_sponsor(account):
                self.caller.msg(f"Default staff sponsor set to {username}.")
            else:
                self.caller.msg("Failed to set default sponsor.")
        else:
            sponsor = get_default_staff_sponsor()
            if sponsor:
                self.caller.msg(f"Current default staff sponsor: {sponsor.username}")
            else:
                self.caller.msg("No default staff sponsor set. Use faction/defaultsponsor=<username> to set one.")

    def cmd_item(self):
        """Staff: Add a faction-exclusive item. Usage: faction/item <faction>=<type>/<item_key>/<display_name>/<price>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/item <faction>=<type>/<item_key>/<display_name>/<price>")
            self.caller.msg("Types: weapon, armor, gear, cyberware, vehicle")
            return
        from world.factions.models import FactionItem
        faction_name, rest = [p.strip() for p in self.args.split("=", 1)]
        parts = [p.strip() for p in rest.split("/")]
        if len(parts) != 4:
            self.caller.msg("Usage: faction/item <faction>=<type>/<item_key>/<display_name>/<price>")
            return
        item_type, item_key, display_name, price_str = parts
        try:
            price = int(price_str)
        except ValueError:
            self.caller.msg("Price must be a number.")
            return
        if item_type not in [c[0] for c in FactionItem.ITEM_TYPES]:
            self.caller.msg(f"Invalid type. Use: {', '.join(c[0] for c in FactionItem.ITEM_TYPES)}")
            return
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        fi, created = FactionItem.objects.get_or_create(
            faction=faction, item_type=item_type, item_key=item_key,
            defaults={"display_name": display_name, "price": price}
        )
        if not created:
            fi.display_name = display_name
            fi.price = price
            fi.save()
        self.caller.msg(f"{'Created' if created else 'Updated'} faction item: {display_name} ({price} eb) for {faction.name}. Use +voucher to create the voucher template, then faction/item/setvoucher to link it.")

    def cmd_buy(self):
        """Buy a faction item (faction members only, in faction vendor rooms). Usage: faction/buy <faction>=<item_name>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/buy <faction>=<item_name>")
            return
        faction_name, item_name = [p.strip() for p in self.args.split("=", 1)]
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        if not character_has_faction_rep(self.caller, faction):
            self.caller.msg("You must have standing with this faction to buy their items.")
            return
        if not self.caller.location:
            self.caller.msg("You must be in a room to buy.")
            return
        if not room_has_faction_vendor_tags(self.caller.location, faction.name):
            self.caller.msg(f"You must be in a room tagged with '{faction.name}' and 'Vendor' to buy faction items.")
            return
        from world.factions.models import FactionItem
        from world.cyberpunk_sheets.services import CharacterSheetMoneyService
        item = FactionItem.objects.filter(
            faction=faction,
            display_name__icontains=item_name
        ).first()
        if not item:
            self.caller.msg(f"No faction item matching '{item_name}' found for {faction.name}. Use faction/items {faction.name} to list.")
            return
        char_sheet = getattr(self.caller, 'character_sheet', None)
        if not char_sheet:
            self.caller.msg("You need a character sheet to buy.")
            return
        balance = CharacterSheetMoneyService.get_balance(char_sheet)
        if balance < item.price:
            self.caller.msg(f"You need {item.price} eb but only have {balance} eb.")
            return
        if not item.voucher_id:
            self.caller.msg(f"Faction item '{item.display_name}' has no voucher template yet. Staff must set it with faction/item/setvoucher.")
            return
        from evennia import search_object
        voucher = search_object(f"#{item.voucher_id}")
        if not voucher:
            self.caller.msg("The faction item voucher template could not be found.")
            return
        voucher = voucher[0]
        from typeclasses.vouchers import Voucher
        if not voucher.is_typeclass(Voucher):
            self.caller.msg("Invalid voucher template.")
            return
        # Clone voucher and give to player; deduct money
        new_voucher = voucher.copy()
        if new_voucher:
            new_voucher.location = self.caller
        if new_voucher:
            CharacterSheetMoneyService.deduct_money(char_sheet, item.price)
            self.caller.msg(f"You bought {item.display_name} for {item.price} eb.")
        else:
            self.caller.msg("Failed to create the item. Contact staff.")

    def cmd_sell(self):
        """Sell a faction voucher back (faction members only, in faction vendor rooms). Usage: faction/sell <faction>=<voucher>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: faction/sell <faction>=<voucher>")
            return
        faction_name, voucher_arg = [p.strip() for p in self.args.split("=", 1)]
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        if not character_has_faction_rep(self.caller, faction):
            self.caller.msg("You must have standing with this faction to sell to them.")
            return
        if not self.caller.location:
            self.caller.msg("You must be in a room to sell.")
            return
        if not room_has_faction_vendor_tags(self.caller.location, faction.name):
            self.caller.msg(f"You must be in a room tagged with '{faction.name}' and 'Vendor' to sell faction items.")
            return
        from commands.voucher_commands import find_voucher
        voucher = find_voucher(self.caller, voucher_arg)
        if not voucher:
            self.caller.msg("Voucher not found.")
            return
        if voucher.location != self.caller:
            self.caller.msg("You must be holding the voucher to sell it.")
            return
        from world.factions.models import FactionItem
        from world.cyberpunk_sheets.services import CharacterSheetMoneyService
        # Find matching faction item (by voucher contents or we'd need to track which FactionItem this came from)
        # For now, we'll match by checking if any FactionItem has this voucher_id - or we accept any voucher and pay a fraction
        # Simplified: match FactionItems by voucher_id, pay back half price
        items = FactionItem.objects.filter(faction=faction, voucher_id=voucher.id)
        if not items.exists():
            items = FactionItem.objects.filter(faction=faction)
            if not items:
                self.caller.msg(f"{faction.name} has no items configured for buyback.")
                return
            refund = min(i.price // 2 for i in items)  # Default half of cheapest
        else:
            item = items.first()
            refund = item.price // 2
        char_sheet = getattr(self.caller, 'character_sheet', None)
        if not char_sheet:
            self.caller.msg("You need a character sheet.")
            return
        voucher.delete()
        CharacterSheetMoneyService.add_money(char_sheet, refund)
        self.caller.msg(f"You sold the item for {refund} eb.")

    def cmd_items(self):
        """List faction-exclusive items. Usage: faction/items <faction>"""
        faction_name = self.args.strip() if self.args else None
        if not faction_name:
            self.caller.msg("Usage: faction/items <faction_name>")
            return
        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
        from world.factions.models import FactionItem
        items = FactionItem.objects.filter(faction=faction)
        if not items:
            self.caller.msg(f"{faction.name} has no faction-exclusive items.")
            return
        output = sheet_header(f"Faction Items: {faction.name}", width=WIDTH)
        output += sheet_section("Available Items", width=WIDTH)
        output += f"|y{'Item':<30}{'Type':<12}{'Price':<12}|n\n"
        for fi in items:
            output += f"|w{fi.display_name:<30}{fi.item_type:<12}{fi.price:<12}|n\n"
        output += footer(width=WIDTH, fillchar="|m-|n")
        self.caller.msg(output)

    def cmd_init(self):
        """Initialize default factions (admin only)."""
        # Check permissions
        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can initialize factions.")
            return

        from typeclasses.factions import Faction
        
        # First, make sure we have a faction storage room
        storage = Faction.get_faction_storage()
        if not storage:
            self.caller.msg("Error: Could not create or find Faction Storage room.")
            return
            
        self.caller.msg("Creating default factions...")
        
        # Create a master faction object to handle initialization
        master = ObjectDB.objects.filter(
            db_key="FactionMaster", db_typeclass_path="typeclasses.factions.Faction"
        ).first()
        if not master:
            master = create_object(
                "typeclasses.factions.Faction",
                key="FactionMaster",
                location=storage
            )
            self.caller.msg("Created FactionMaster object.")
        
        # Create all the default factions
        created_count = 0
        for faction_data in default_faction_dictionary:
            name = faction_data.get("name")
            if not FactionModel.objects.filter(name=name).exists():
                # Get faction type(s)
                faction_type = faction_data.get("faction_type")
                if isinstance(faction_type, str):
                    faction_type = [faction_type]
                    
                faction_model = FactionModel.objects.create(
                    name=name,
                    description=faction_data.get("description", ""),
                    ic_description=faction_data.get("ic_description", ""),
                    influence=faction_data.get("influence", 50),
                    faction_type=faction_type
                )
                
                faction_obj = create_object(
                    "typeclasses.factions.Faction",
                    key=name,
                    location=storage
                )
                
                faction_obj.db.faction_type = faction_type
                faction_obj.link_to_model(faction_model.id)
                created_count += 1

        # Ensure all factions have channels (create missing, add aliases to existing)
        channel_count = 0
        for faction_model in FactionModel.objects.all():
            needs_channel = not getattr(faction_model, "channel_id", None)
            if needs_channel:
                channel = create_faction_channel(faction_model.name)
                if channel:
                    faction_model.channel_id = channel.id
                    faction_model.save()
                    channel_count += 1
            else:
                create_faction_channel(faction_model.name)  # Ensure aliases on existing

        if channel_count:
            self.caller.msg(f"Created {channel_count} faction channels.")
                
        if created_count:
            self.caller.msg(f"Created {created_count} default factions.")
        else:
            self.caller.msg("All default factions already exist.")
            
        # List all factions for verification
        all_factions = ObjectDB.objects.filter(
            db_typeclass_path="typeclasses.factions.Faction"
        )
        self.caller.msg(f"Total faction objects: {all_factions.count()}")
        for faction in all_factions:
            model_id = faction.db.model_id if hasattr(faction.db, 'model_id') else "None"
            faction_type = faction.db.faction_type if hasattr(faction.db, 'faction_type') else "Unknown"
            
            # Format faction type for display
            if isinstance(faction_type, list):
                faction_type_display = ", ".join(faction_type)
            else:
                faction_type_display = str(faction_type)
                
            self.caller.msg(f"- {faction.key} (Type: {faction_type_display}, Model ID: {model_id})")


class CmdGroup(MuxCommand):
    """
    Group commands. These commands allow players to create and manage their own
    groups and crews (edgerunner groups).
    
    Groups are player-created and player-managed organizations. Unlike factions,
    which represent major world entities managed by staff, groups are for player
    teams, crews, and smaller organizations in the game world.

    Basic usage:
      group - Show details of your current group(s)
      group <name> - Display info about a group
      group/create <name> - Create a new group with you as leader
      group/join <name> - Request to join an existing group
      group/leave <name> - Leave a group you're in
      group/info <name> - Display information about a group
      group/list - List all groups
      
    Group management (for leaders/officers):
      group/desc <name> = <description> - Set the description of your group
      group/desc/ic <name> = <description> - Set the IC description
      group/members <name> - List the members of your group
      group/kick <name> <member> - Kick a member from your group
      group/approve <name> <member> - Approve a join request
      group/role <name> <role>=<permissions> - Create a role for your group
      group/promote <group> <character>=<role> - Assign a role to a member
      group/demote <name> <member> - Remove a role from a member
      group/chat <name> <message> - Send a message to all group members
      
    Admin commands:
      group/type <name>=<type> - Set the type of a group
      group/leader <name>=<character> - Set the leader of a group
    """
    key = "group"
    locks = "cmd:all()"
    help_category = "Factions and Groups"

    def func(self):
        if not self.switches and not self.args:
            # Display info about current group if no args or switches
            self.cmd_group()
            return
            
        if not self.switches:
            # If there are args but no switch, interpret as /info
            self.cmd_info(self.args.strip())
            return

        switch = self.switches[0]  # Use the first switch if multiple provided
        
        # Admin-only commands
        admin_commands = ["type", "leader"]
        if switch in admin_commands and not self.caller.check_permstring("Admin"):
            self.caller.msg("This group command is only available to administrators.")
            return
        
        if switch == "create":
            self.cmd_create()
        elif switch == "join":
            self.cmd_join()
        elif switch == "leave":
            self.cmd_leave()
        elif switch == "info":
            self.cmd_info()
        elif switch == "list":
            self.cmd_list()
        elif switch == "desc":
            if "ic" in self.switches:
                self.cmd_desc_ic()
            else:
                self.cmd_desc()
        elif switch == "type":
            self.cmd_type()
        elif switch == "leader":
            self.cmd_leader()
        elif switch == "members":
            self.cmd_members()
        elif switch == "kick":
            self.cmd_kick()
        elif switch == "promote":
            self.cmd_promote()
        elif switch == "demote":
            self.cmd_demote()
        elif switch == "role":
            self.cmd_role()
        elif switch == "chat":
            self.cmd_chat()
        elif switch == "approve":
            self.cmd_approve()
        else:
            self.caller.msg(f"Unknown switch: /{switch}")

    def cmd_group(self):
        """Show the details of your current group."""
        character_sheet = self.caller.character_sheet
        if not character_sheet:
            self.caller.msg("You do not have a character sheet.")
            return

        # Find groups where this character is a member
        memberships = GroupMembership.objects.filter(character=character_sheet)
        
        if not memberships.exists():
            self.caller.msg("You are not a member of any group.")
            return

        if memberships.count() == 1:
            # If only in one group, show that group's details
            group = memberships.first().group
            self.cmd_info(group.name)
        else:
            # If in multiple groups, list them
            self.caller.msg("You are a member of the following groups:")
            table = EvTable("Group Name", "Role", border="table")
            for membership in memberships:
                role_name = membership.role.name if membership.role else "No Role"
                table.add_row(membership.group.name, role_name)
            self.caller.msg(table)

    def cmd_create(self):
        """Create a new edgerunner group."""
        if not self.args:
            self.caller.msg("Usage: group/create <name>")
            return

        name = self.args.strip()
        character_sheet = self.caller.character_sheet
        
        if not character_sheet:
            self.caller.msg("You do not have a character sheet.")
            return

        if Group.objects.filter(name__iexact=name).exists():
            self.caller.msg(f"A group named '{name}' already exists.")
            return

        new_group = Group.objects.create(name=name, leader=character_sheet)
        
        # Create a GroupMembership for the leader
        GroupMembership.objects.create(character=character_sheet, group=new_group)
        
        # Create default leader role with all permissions
        leader_role = GroupRole.objects.create(
            name="Leader",
            group=new_group,
            can_invite=True,
            can_kick=True,
            can_promote=True,
            can_edit_info=True
        )
        
        # Assign leader role to the creator's membership
        membership = GroupMembership.objects.get(character=character_sheet, group=new_group)
        membership.role = leader_role
        membership.save()
        
        self.caller.msg(f"You have created the edgerunner group '{name}' and are now its leader.")
        self.caller.msg("Use group/desc to set a description for your group.")

    def cmd_join(self):
        """Request to join an existing group."""
        if not self.args:
            self.caller.msg("Usage: group/join <name>")
            return

        name = self.args.strip()
        character_sheet = self.caller.character_sheet
        
        if not character_sheet:
            self.caller.msg("You do not have a character sheet.")
            return

        try:
            group = Group.objects.get(name__iexact=name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{name}' exists.")
            return

        if GroupMembership.objects.filter(character=character_sheet, group=group).exists():
            self.caller.msg(f"You are already a member of '{name}'.")
            return

        if GroupJoinRequest.objects.filter(character=character_sheet, group=group).exists():
            self.caller.msg(f"You have already requested to join '{name}'. Please wait for approval.")
            return

        GroupJoinRequest.objects.create(character=character_sheet, group=group)
        self.caller.msg(f"You have requested to join the group '{name}'. Please wait for approval from the group leader.")
        
        if group.leader and group.leader.db_object:
            group.leader.db_object.msg(f"{self.caller.name} has requested to join your group '{name}'. Use 'group/approve {name} {self.caller.name}' to approve.")

    def cmd_leave(self):
        """Leave a group you're currently in."""
        if not self.args:
            # If no group specified and only in one group, leave that group
            character_sheet = self.caller.character_sheet
            if not character_sheet:
                self.caller.msg("You do not have a character sheet.")
                return
                
            memberships = GroupMembership.objects.filter(character=character_sheet)
            if memberships.count() == 0:
                self.caller.msg("You are not a member of any group.")
                return
            elif memberships.count() == 1:
                group = memberships.first().group
                name = group.name
            else:
                self.caller.msg("You are a member of multiple groups. Please specify which one to leave.")
                table = EvTable("Group Name", border="table")
                for membership in memberships:
                    table.add_row(membership.group.name)
                self.caller.msg(table)
                return
        else:
            # Leave the specified group
            name = self.args.strip()
            character_sheet = self.caller.character_sheet
            
            if not character_sheet:
                self.caller.msg("You do not have a character sheet.")
                return
            
            try:
                group = Group.objects.get(name__iexact=name)
            except Group.DoesNotExist:
                self.caller.msg(f"No group named '{name}' exists.")
                return

        membership = GroupMembership.objects.filter(character=character_sheet, group=group).first()
        if not membership:
            self.caller.msg(f"You are not a member of '{name}'.")
            return

        if group.leader == character_sheet:
            self.caller.msg(f"You are the leader of '{name}'. You must transfer leadership before leaving.")
            return

        membership.delete()
        self.caller.msg(f"You have left the group '{name}'.")
        
        # Notify the leader
        if group.leader and group.leader.db_object:
            group.leader.db_object.msg(f"{self.caller.name} has left your group '{name}'.")

    def cmd_info(self, group_name=None):
        """Display information about a group."""
        if not group_name:
            group_name = self.args.strip()
            
        if not group_name:
            # If no group specified and only in one group, show that group's info
            character_sheet = self.caller.character_sheet
            if not character_sheet:
                self.caller.msg("You do not have a character sheet.")
                return
                
            memberships = GroupMembership.objects.filter(character=character_sheet)
            if memberships.count() == 0:
                self.caller.msg("You are not a member of any group.")
                return
            elif memberships.count() == 1:
                group_name = memberships.first().group.name
            else:
                self.caller.msg("You are a member of multiple groups. Please specify which one to view.")
                table = EvTable("Group Name", border="table")
                for membership in memberships:
                    table.add_row(membership.group.name)
                self.caller.msg(table)
                return
        
        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return
            
        memberships = GroupMembership.objects.filter(group=group)
        members = [membership.character.full_name for membership in memberships]
        
        # Basic Group Info
        table = EvTable(border="table", width=78)
        table.add_row("|cGroup Name|n", group.name)
        table.add_row("|cOOC Description|n", crop(group.description or 'Not set', width=58))
        table.add_row("|cLeader|n", group.leader_display_name)
        table.add_row("|cMembers|n", f"{len(members)}: {', '.join(members)}")
        table.add_row("|cCreated|n", group.created_at.strftime('%Y-%m-%d %H:%M:%S'))
        
        self.caller.msg(table)

        # IC Description (modified by group leader or admin)
        ic_description = group.ic_description or 'Not set'
        wrapped_description = textwrap.wrap(ic_description, width=76)  # Adjust width as needed
        
        ic_table = EvTable(border="table", width=78)
        ic_table.add_row("|cIC Description|n")
        for line in wrapped_description:
            ic_table.add_row(line)
        
        self.caller.msg(ic_table)

    def cmd_list(self):
        """List all existing groups."""
        groups = Group.objects.all()

        if not groups:
            self.caller.msg("There are no groups in the game yet.")
            return

        table = EvTable("Name", "Leader", "Members", border="cells")
        for group in groups:
            member_count = GroupMembership.objects.filter(group=group).count()
            leader_name = group.leader_display_name if group.leader else "None"
            table.add_row(group.name, leader_name, member_count)

        self.caller.msg(table)

    def cmd_desc(self):
        """Set or update the description of a group."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: group/desc <group_name> = <description>")
            return

        args, description = self.args.split("=", 1)
        group_name = args.strip()
        description = description.strip()

        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return

        # Check if the caller is the group leader or has permission to edit info
        character_sheet = self.caller.character_sheet
        is_leader = group.leader == character_sheet if group.leader else False
        has_edit_permission = GroupMembership.objects.filter(
            character=character_sheet,
            group=group,
            role__can_edit_info=True
        ).exists()

        if is_leader or has_edit_permission or self.caller.check_permstring("Admin"):
            # Update the description
            group.description = description
            group.save()
            self.caller.msg(f"Updated the general description for group '{group_name}'.")
            logger.log_info(f"{self.caller.name} updated the general description for group '{group_name}'.")
        else:
            self.caller.msg("You don't have permission to edit this group's description.")

    def cmd_desc_ic(self):
        """Set or update the in-character description of a group."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: group/desc/ic <group_name> = <description>")
            return

        args, description = self.args.split("=", 1)
        group_name = args.strip()
        description = description.strip()

        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return

        # Check if the caller is the group leader or has permission to edit info
        character_sheet = self.caller.character_sheet
        is_leader = group.leader == character_sheet if group.leader else False
        has_edit_permission = GroupMembership.objects.filter(
            character=character_sheet,
            group=group,
            role__can_edit_info=True
        ).exists()

        if is_leader or has_edit_permission or self.caller.check_permstring("Admin"):
            # Update the IC description
            group.ic_description = description
            group.save()
            self.caller.msg(f"Updated the IC description for group '{group_name}'.")
            logger.log_info(f"{self.caller.name} updated the IC description for group '{group_name}'.")
        else:
            self.caller.msg("You don't have permission to edit this group's IC description.")

    def cmd_leader(self):
        """Set the leader of a group (admin only)."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: group/leader <group_name> = <character_name>")
            return

        group_name, character_name = [part.strip() for part in self.args.split("=")]

        # Check if the caller is an admin
        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can set group leaders.")
            return

        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(full_name__iexact=character_name)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"No character named '{character_name}' exists.")
            return

        # Set the new leader
        group.leader = character_sheet
        group.save()

        # Ensure the leader is a member of the group and has edit permissions
        membership, created = GroupMembership.objects.get_or_create(character=character_sheet, group=group)

        # Create or get a role for the leader with all permissions
        leader_role, role_created = GroupRole.objects.get_or_create(
            name="Leader",
            group=group,
            defaults={
                "can_invite": True,
                "can_kick": True,
                "can_promote": True,
                "can_edit_info": True
            }
        )

        # Assign the leader role to the new leader
        membership.role = leader_role
        membership.save()

        self.caller.msg(f"{character_name} has been set as the leader of {group_name}.")
        logger.log_info(f"{self.caller.name} set {character_name} as the leader of {group_name}.")

    def cmd_members(self):
        """List the members of a group."""
        if not self.args:
            self.caller.msg("Usage: group/members <group_name>")
            return

        group_name = self.args.strip()
        
        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return
            
        memberships = GroupMembership.objects.filter(group=group)
        
        if not memberships.exists():
            self.caller.msg(f"The group '{group_name}' has no members.")
            return
            
        table = EvTable("Member", "Role", border="table")
        for membership in memberships:
            member_name = membership.character.full_name
            role_name = membership.role.name if membership.role else "None"
            
            # Mark the leader
            if group.leader and group.leader.id == membership.character.id:
                member_name = f"{member_name} (Leader)"
                
            table.add_row(member_name, role_name)
            
        self.caller.msg(f"Members of group '{group_name}':")
        self.caller.msg(table)

    def cmd_kick(self):
        """Kick a member from a group."""
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: group/kick <group_name> <character_name>")
            return

        group_name, character_name = self.args.split()
        
        character_sheet = self.caller.character_sheet
        if not character_sheet:
            self.caller.msg("You do not have a character sheet.")
            return
            
        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return
            
        # Check if the caller is the group leader or has permission to kick
        is_leader = group.leader == character_sheet if group.leader else False
        has_kick_permission = GroupMembership.objects.filter(
            character=character_sheet,
            group=group,
            role__can_kick=True
        ).exists()
        
        if not (is_leader or has_kick_permission or self.caller.check_permstring("Admin")):
            self.caller.msg("You don't have permission to kick members from this group.")
            return
            
        try:
            target_character = CharacterSheet.objects.get(full_name__iexact=character_name)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"No character named '{character_name}' exists.")
            return
            
        # Make sure we're not trying to kick the leader
        if group.leader and group.leader.id == target_character.id:
            self.caller.msg("You cannot kick the group leader.")
            return
            
        membership = GroupMembership.objects.filter(character=target_character, group=group).first()
        if not membership:
            self.caller.msg(f"{character_name} is not a member of '{group_name}'.")
            return
            
        membership.delete()
        self.caller.msg(f"You have kicked {character_name} from the group '{group_name}'.")
        
        # Notify the kicked member
        if target_character.db_object:
            target_character.db_object.msg(f"You have been kicked from the group '{group_name}' by {self.caller.name}.")

    def cmd_promote(self):
        """Assign a role to a group member."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: group/promote <group_name> <character_name> = <role_name>")
            return

        args, role_name = self.args.split("=", 1)
        args = args.strip().split()
        
        if len(args) != 2:
            self.caller.msg("Usage: group/promote <group_name> <character_name> = <role_name>")
            return
            
        group_name, character_name = args
        role_name = role_name.strip()

        character_sheet = self.caller.character_sheet
        if not character_sheet:
            self.caller.msg("You do not have a character sheet.")
            return
            
        try:
            group = Group.objects.get(name__iexact=group_name)
            target_character = CharacterSheet.objects.get(full_name__iexact=character_name)
            role = GroupRole.objects.get(group=group, name__iexact=role_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"No character named '{character_name}' exists.")
            return
        except GroupRole.DoesNotExist:
            self.caller.msg(f"No role named '{role_name}' exists in this group.")
            return

        # Check if the caller can promote members
        if not (group.leader == character_sheet or 
                GroupMembership.objects.filter(
                    character=character_sheet, 
                    group=group, 
                    role__can_promote=True
                ).exists() or
                self.caller.check_permstring("Admin")):
            self.caller.msg("You don't have permission to assign roles in this group.")
            return

        membership, created = GroupMembership.objects.get_or_create(character=target_character, group=group)
        membership.role = role
        membership.save()

        self.caller.msg(f"Assigned role '{role_name}' to {character_name} in group '{group_name}'.")
        
        # Notify the promoted member
        if target_character.db_object:
            target_character.db_object.msg(f"You have been assigned the role '{role_name}' in the group '{group_name}' by {self.caller.name}.")

    def cmd_demote(self):
        """Remove a role from a group member."""
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: group/demote <group_name> <character_name>")
            return

        group_name, character_name = self.args.split()
        
        character_sheet = self.caller.character_sheet
        if not character_sheet:
            self.caller.msg("You do not have a character sheet.")
            return
            
        try:
            group = Group.objects.get(name__iexact=group_name)
            target_character = CharacterSheet.objects.get(full_name__iexact=character_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"No character named '{character_name}' exists.")
            return

        # Check if the caller can promote/demote members
        if not (group.leader == character_sheet or 
                GroupMembership.objects.filter(
                    character=character_sheet, 
                    group=group, 
                    role__can_promote=True
                ).exists() or
                self.caller.check_permstring("Admin")):
            self.caller.msg("You don't have permission to modify roles in this group.")
            return
            
        membership = GroupMembership.objects.filter(character=target_character, group=group).first()
        if not membership:
            self.caller.msg(f"{character_name} is not a member of '{group_name}'.")
            return
            
        # Make sure we're not trying to demote the leader
        if group.leader and group.leader.id == target_character.id:
            self.caller.msg("You cannot remove the role from the group leader.")
            return
            
        old_role = membership.role.name if membership.role else "No Role"
        membership.role = None
        membership.save()

        self.caller.msg(f"Removed role '{old_role}' from {character_name} in group '{group_name}'.")
        
        # Notify the demoted member
        if target_character.db_object:
            target_character.db_object.msg(f"Your role '{old_role}' in the group '{group_name}' has been removed by {self.caller.name}.")

    def cmd_role(self):
        """Create a new role for a group."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: group/role <group_name> <role_name> = <permissions>")
            self.caller.msg("Permissions are comma-separated and can include: invite, kick, promote, edit_info")
            return

        group_and_role, permissions = self.args.split("=", 1)
        group_name, role_name = group_and_role.rsplit(None, 1)
        
        group_name = group_name.strip()
        role_name = role_name.strip()
        permissions = [p.strip() for p in permissions.split(",")]

        character_sheet = self.caller.character_sheet
        if not character_sheet:
            self.caller.msg("You do not have a character sheet.")
            return
            
        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return

        # Check if the caller is the group leader or an admin
        if not (group.leader == character_sheet or self.caller.check_permstring("Admin")):
            self.caller.msg("Only the group leader can create new roles.")
            return
            
        # Check if role already exists
        if GroupRole.objects.filter(group=group, name__iexact=role_name).exists():
            self.caller.msg(f"A role named '{role_name}' already exists in this group.")
            return

        role = GroupRole.objects.create(
            name=role_name,
            group=group,
            can_invite="invite" in permissions,
            can_kick="kick" in permissions,
            can_promote="promote" in permissions,
            can_edit_info="edit_info" in permissions
        )

        self.caller.msg(f"Created role '{role_name}' for group '{group_name}' with permissions: {', '.join(permissions)}")

    def cmd_chat(self):
        """Send a message to all members of a group."""
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: group/chat <group_name> <message>")
            return

        group_name, message = self.args.split(None, 1)
        character_sheet = self.caller.character_sheet

        if not character_sheet:
            self.caller.msg("You do not have a character sheet.")
            return
            
        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return

        # Check if the character is a member of the group
        if not GroupMembership.objects.filter(character=character_sheet, group=group).exists():
            self.caller.msg(f"You are not a member of '{group_name}'.")
            return

        # Prepare the formatted message
        formatted_message = f"|w[{group.name}] {self.caller.name}: {message}|n"

        # Send message to all online group members, including the sender
        members_notified = 0
        for membership in GroupMembership.objects.filter(group=group):
            member = membership.character
            # Find the online account associated with this character
            account = search_account(member.full_name)
            if account and account[0].sessions.count() > 0:
                account[0].msg(formatted_message)
                members_notified += 1

        # Always show the message to the sender, even if they're the only one online
        if members_notified == 0:
            self.caller.msg(formatted_message)
            self.caller.msg("You were the only one online to receive the message.")
        else:
            self.caller.msg(f"You sent a message to '{group.name}'. {members_notified} member(s) received it.")

    def cmd_approve(self):
        """Approve a join request for your group."""
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: group/approve <group_name> <character_name>")
            return

        group_name, character_name = self.args.split()
        leader_sheet = self.caller.character_sheet
        
        if not leader_sheet:
            self.caller.msg("You do not have a character sheet.")
            return

        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return
            
        # Check if the caller can approve join requests
        is_leader = group.leader == leader_sheet if group.leader else False
        has_invite_permission = GroupMembership.objects.filter(
            character=leader_sheet,
            group=group,
            role__can_invite=True
        ).exists()
        
        if not (is_leader or has_invite_permission or self.caller.check_permstring("Admin")):
            self.caller.msg("You don't have permission to approve join requests for this group.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(full_name__iexact=character_name)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"No character named '{character_name}' found.")
            return

        try:
            join_request = GroupJoinRequest.objects.get(character=character_sheet, group=group)
        except GroupJoinRequest.DoesNotExist:
            self.caller.msg(f"{character_name} has not requested to join '{group_name}'.")
            return

        GroupMembership.objects.create(character=character_sheet, group=group)
        join_request.delete()

        self.caller.msg(f"You have approved {character_name}'s request to join '{group_name}'.")
        
        # Notify the approved member
        if character_sheet.db_object:
            character_sheet.db_object.msg(f"Your request to join '{group_name}' has been approved by {self.caller.name}.")

    def cmd_type(self):
        """Set the type of a group (admin only)."""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: group/type <group_name>=<type>")
            return
            
        group_name, group_type = [part.strip() for part in self.args.split("=", 1)]
        
        # Check if the caller is an admin
        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can set group types.")
            return
            
        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return
            
        # There's no GROUP_TYPES constant, but we can add one later if needed
        # For now, just set the type without validation
        group.group_type = group_type
        group.save()
        
        self.caller.msg(f"Set the type of group '{group_name}' to '{group_type}'.")


class CmdInitFactions(Command):
    """
    Initialize the default factions in the game.

    Usage:
      initfactions

    This command creates the default factions defined in the faction typeclass.
    It should be run once during game setup or after a database reset.
    """
    key = "initfactions"
    locks = "cmd:perm(Admin)"
    help_category = "System"

    def func(self):
        from typeclasses.factions import Faction
        
        # First, make sure we have a faction storage room
        storage = Faction.get_faction_storage()
        if not storage:
            self.caller.msg("Error: Could not create or find Faction Storage room.")
            return
            
        self.caller.msg("Creating default factions...")
        
        # Create a master faction object to handle initialization
        master = ObjectDB.objects.filter(
            db_key="FactionMaster", db_typeclass_path="typeclasses.factions.Faction"
        ).first()
        if not master:
            master = create_object(
                "typeclasses.factions.Faction",
                key="FactionMaster",
                location=storage
            )
            self.caller.msg("Created FactionMaster object.")
        
        # Create all the default factions
        created_count = 0
        for faction_data in default_faction_dictionary:
            name = faction_data.get("name")
            if not FactionModel.objects.filter(name=name).exists():
                # Get faction type(s)
                faction_type = faction_data.get("faction_type")
                if isinstance(faction_type, str):
                    faction_type = [faction_type]
                    
                faction_model = FactionModel.objects.create(
                    name=name,
                    description=faction_data.get("description", ""),
                    ic_description=faction_data.get("ic_description", ""),
                    influence=faction_data.get("influence", 50),
                    faction_type=faction_type
                )
                
                faction_obj = create_object(
                    "typeclasses.factions.Faction",
                    key=name,
                    location=storage
                )
                
                faction_obj.db.faction_type = faction_type
                faction_obj.link_to_model(faction_model.id)
                created_count += 1

        # Ensure all factions have channels (create missing, add aliases to existing)
        channel_count = 0
        for faction_model in FactionModel.objects.all():
            needs_channel = not getattr(faction_model, "channel_id", None)
            if needs_channel:
                channel = create_faction_channel(faction_model.name)
                if channel:
                    faction_model.channel_id = channel.id
                    faction_model.save()
                    channel_count += 1
            else:
                create_faction_channel(faction_model.name)  # Ensure aliases on existing

        if channel_count:
            self.caller.msg(f"Created {channel_count} faction channels.")
                
        if created_count:
            self.caller.msg(f"Created {created_count} default factions.")
        else:
            self.caller.msg("All default factions already exist.")
            
        # List all factions for verification
        all_factions = ObjectDB.objects.filter(
            db_typeclass_path="typeclasses.factions.Faction"
        )
        self.caller.msg(f"Total faction objects: {all_factions.count()}")
        for faction in all_factions:
            model_id = faction.db.model_id if hasattr(faction.db, 'model_id') else "None"
            faction_type = faction.db.faction_type if hasattr(faction.db, 'faction_type') else "Unknown"
            
            # Format faction type for display
            if isinstance(faction_type, list):
                faction_type_display = ", ".join(faction_type)
            else:
                faction_type_display = str(faction_type)
                
            self.caller.msg(f"- {faction.key} (Type: {faction_type_display}, Model ID: {model_id})")

# Command set for adding all faction commands to the default command set
class FactionCommands(CmdSet):
    """
    Command set for all faction and group commands.
    
    This command set contains both the consolidated commands:
    - CmdFaction: For staff-managed major world factions (corps, gangs, etc.)
    - CmdGroup: For player-created groups and edgerunner crews
    - CmdInitFactions: Admin command to initialize default factions
    
    This command set should be added to the default command set to make
    these commands available to players.
    """
    
    key = "FactionCommands"
    
    def at_cmdset_creation(self):
        """Add all faction and group commands."""
        # Add the consolidated commands
        self.add(CmdFaction())
        self.add(CmdGroup())
        
        # Add the initialization command (admin-only)
        self.add(CmdInitFactions())
