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
from evennia.commands.default.muxcommand import MuxCommand
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.utils.evtable import EvTable
from evennia.utils.search import search_account
from evennia.utils import logger, crop
from django.core.exceptions import ObjectDoesNotExist
from world.factions.models import Group, Faction as FactionModel
from world.factions.models import FactionReputation, GroupRole, GroupMembership, GroupJoinRequest, GroupInfo
from world.factions.faction_types import FACTION_TYPES
from world.factions.default_faction_dictionary import default_faction_dictionary
from typeclasses.factions import Faction
import random, textwrap


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
      
    Admin commands:
      faction/create <n> - Create a new faction (admin only)
      faction/create/type <n>=<type> - Create a faction of specific type
      faction/type <n>=<type> - Change a faction's type
      faction/type/add <n>=<type> - Add another type to a faction
      faction/desc <n>=<description> - Set a description on a faction
      faction/desc/ic <n>=<description> - Set IC description on a faction
      faction/modify <character> <faction> <amount> - Modify reputation
      faction/init - Initialize default factions
      
    Note: Factions can have multiple types (e.g., both 'nomad' and 'gang'),
    which allows them to represent complex entities in the game world.
    """
    key = "faction"
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
        admin_commands = ["create", "type", "desc", "modify", "init"]
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
            self.caller.msg("You cannot directly join major factions. Gain reputation with them through missions and roleplay.")
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
        else:
            self.caller.msg(f"Unknown switch: /{switch}")

    def cmd_list(self):
        """List all factions."""
        from typeclasses.factions import Faction as FactionTypeclass
        factions = FactionModel.objects.all().order_by('-influence')

        if not factions:
            self.caller.msg("There are no factions in the game yet.")
            return

        table = EvTable("Faction", "Type", "Influence", "Members", border="cells")
        
        for faction in factions:
            faction_obj = FactionTypeclass.get_faction(faction.name)
            
            # Handle multiple faction types
            if faction_obj and faction_obj.db.faction_type:
                if isinstance(faction_obj.db.faction_type, list):
                    faction_type = ", ".join(faction_obj.db.faction_type)
                else:
                    faction_type = str(faction_obj.db.faction_type)
            else:
                faction_type = "Unknown"
                
            member_count = faction.factionreputation_set.count()
            table.add_row(faction.name, faction_type, faction.influence, member_count)

        self.caller.msg(table)

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

        # Get faction type and member count
        if faction_obj and faction_obj.db.faction_type:
            if isinstance(faction_obj.db.faction_type, list):
                faction_type = ", ".join(faction_obj.db.faction_type)
            else:
                faction_type = str(faction_obj.db.faction_type)
        else:
            faction_type = "Unknown"
            
        member_count = faction.factionreputation_set.count()
        
        # Create a table for display
        table = EvTable(border="table", width=78)
        table.add_row("|cFaction Name|n", faction.name)
        table.add_row("|cType|n", faction_type)
        table.add_row("|cOOC Description|n", crop(faction.description or 'Not set', width=58))
        table.add_row("|cInfluence|n", faction.influence)
        table.add_row("|cMembers|n", member_count)
        table.add_row("|cCreated|n", faction.created_at.strftime('%Y-%m-%d %H:%M:%S'))
        
        self.caller.msg(table)

        # IC Description
        ic_description = faction.ic_description or 'Not set'
        wrapped_description = textwrap.wrap(ic_description, width=76)
        
        ic_table = EvTable(border="table", width=78)
        ic_table.add_row("|cIC Description|n")
        for line in wrapped_description:
            ic_table.add_row(line)
        
        self.caller.msg(ic_table)
        
        # If player is a member or has reputation with this faction, show it
        character_sheet = self.caller.character_sheet
        if character_sheet:
            try:
                rep = FactionReputation.objects.get(
                    character=character_sheet,
                    faction=faction
                )
                self.caller.msg(f"Your reputation with {faction.name}: {rep.reputation}")
            except FactionReputation.DoesNotExist:
                pass

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
        else:
            self.caller.msg("Error creating faction. Check logs for details.")

    def cmd_join(self):
        """Join a faction."""
        if not self.args:
            self.caller.msg("Usage: faction/join <name>")
            return
            
        # Request to join a faction
        faction_name = self.args.strip()
        faction_obj = Faction.get_faction(faction_name)
        
        if not faction_obj:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return
            
        # Check if they're already a member
        if hasattr(self.caller, 'db') and self.caller.db.faction == faction_name:
            self.caller.msg(f"You are already a member of '{faction_name}'.")
            return
            
        # Only allow joining edgerunner factions directly
        if faction_obj.db.faction_type != "edgerunner":
            self.caller.msg(f"{faction_name} is a {faction_obj.db.faction_type} faction and cannot be joined directly. "
                         f"You must gain reputation with them through roleplay.")
            return
            
        # Add them to the faction
        if faction_obj.add_member(self.caller):
            self.caller.msg(f"You have joined the {faction_name} faction.")
            
            # Create reputation entry
            faction_model = faction_obj.model
            if faction_model and self.caller.character_sheet:
                FactionReputation.objects.get_or_create(
                    character=self.caller.character_sheet,
                    faction=faction_model,
                    defaults={"reputation": 0}
                )
        else:
            self.caller.msg(f"Failed to join {faction_name}. Please contact an admin.")

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
        """Check your reputation with a faction."""
        if not self.args:
            # If no faction specified, check current faction
            if not hasattr(self.caller, 'db') or not self.caller.db.faction:
                self.caller.msg("You are not currently affiliated with any faction.")
                return
            faction_name = self.caller.db.faction
        else:
            faction_name = self.args.strip()

        character_sheet = self.caller.character_sheet
        if not character_sheet:
            self.caller.msg("You need a character sheet to check faction reputation.")
            return

        try:
            faction = FactionModel.objects.get(name__iexact=faction_name)
        except FactionModel.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        reputation, created = FactionReputation.objects.get_or_create(
            character=character_sheet,
            faction=faction
        )

        self.caller.msg(f"Your reputation with {faction.name}: {reputation.reputation}")

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
                character=character_sheet,
                faction=faction
            )
            reputation.reputation += reputation_gain
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
        """Modify a character's reputation with a faction (admin only)."""
        if not self.args or len(self.args.split()) != 3:
            self.caller.msg("Usage: faction/modify <character> <faction> <amount>")
            return

        # Check permissions
        if not self.caller.check_permstring("Admin"):
            self.caller.msg("Only admins can modify faction reputation.")
            return

        char_name, faction_name, amount = self.args.split()

        try:
            character = CharacterSheet.objects.get(full_name__iexact=char_name)
            faction = FactionModel.objects.get(name__iexact=faction_name)
            amount = int(amount)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"Character '{char_name}' not found.")
            return
        except FactionModel.DoesNotExist:
            self.caller.msg(f"Faction '{faction_name}' not found.")
            return
        except ValueError:
            self.caller.msg("Amount must be a number.")
            return

        reputation, created = FactionReputation.objects.get_or_create(
            character=character,
            faction=faction
        )

        reputation.reputation += amount
        reputation.save()

        self.caller.msg(f"Modified {character.full_name}'s reputation with {faction.name} by {amount}. New reputation: {reputation.reputation}")

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
        master = Faction.objects.filter(db_key="FactionMaster").first()
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
                
        if created_count:
            self.caller.msg(f"Created {created_count} default factions.")
        else:
            self.caller.msg("All default factions already exist.")
            
        # List all factions for verification
        all_factions = Faction.objects.filter(db_typeclass_path="typeclasses.factions.Faction")
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
        master = Faction.objects.filter(db_key="FactionMaster").first()
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
                
        if created_count:
            self.caller.msg(f"Created {created_count} default factions.")
        else:
            self.caller.msg("All default factions already exist.")
            
        # List all factions for verification
        all_factions = Faction.objects.filter(db_typeclass_path="typeclasses.factions.Faction")
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
