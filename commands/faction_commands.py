from evennia import Command
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.utils.evtable import EvTable
from evennia.utils.search import search_account
from evennia.utils import logger, crop
from django.core.exceptions import ObjectDoesNotExist
from world.factions.models import Group, Faction, FactionReputation, GroupRole, GroupMembership, GroupJoinRequest, GroupInfo
import random, textwrap

class CmdCreateGroup(Command):
    """
    Create a new group or gang.

    Usage:
      creategroup <name>

    Creates a new group with you as the leader.
    """
    key = "creategroup"
    locks = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args:
            self.caller.msg("Usage: creategroup <name>")
            return

        name = self.args.strip()
        character_sheet = self.caller.character_sheet

        if Group.objects.filter(name__iexact=name).exists():
            self.caller.msg(f"A group named '{name}' already exists.")
            return

        new_group = Group.objects.create(name=name, leader=character_sheet)
        
        # Create a GroupMembership for the leader
        GroupMembership.objects.create(character=character_sheet, group=new_group)
        
        self.caller.msg(f"You have created the group '{name}' and are now its leader.")

class CmdJoinGroup(Command):
    """
    Request to join an existing group.

    Usage:
      joingroup <name>

    Sends a request to join the specified group.
    """
    key = "joingroup"
    locks = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args:
            self.caller.msg("Usage: joingroup <name>")
            return

        name = self.args.strip()
        character_sheet = self.caller.character_sheet

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
            group.leader.db_object.msg(f"{self.caller.name} has requested to join your group '{name}'. Use 'approvejoin <character_name> <group_name>' to approve.")

class CmdLeaveGroup(Command):
    """
    Leave a group you're currently in.

    Usage:
      leavegroup <name>

    Removes you from the specified group.
    """
    key = "leavegroup"
    locks = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args:
            self.caller.msg("Usage: leavegroup <name>")
            return

        name = self.args.strip()
        character_sheet = self.caller.character_sheet

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
        group.leader.db_object.msg(f"{self.caller.name} has left your group '{name}'.")


class CmdGroupDesc(Command):
    """
    Set or update the description of a group.

    Usage:
      groupdesc <group_name> <type> = <description>

    Where <type> is either 'general' or 'ic' (in-character).

    Examples:
      groupdesc Samurai general = A legendary rockerboy band from Night City.
      groupdesc Samurai ic = Known for their anti-corp anthems and electrifying performances.
    """

    key = "groupdesc"
    aliases = ["group_description"]
    locks = "cmd:all()"
    help_category = "Factions and Groups"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: groupdesc <group_name> <type> = <description>")
            return

        args, description = self.args.split("=", 1)
        args = args.strip().split()
        
        if len(args) != 2:
            self.caller.msg("Usage: groupdesc <group_name> <type> = <description>")
            return

        group_name, desc_type = args
        description = description.strip()

        if desc_type not in ['general', 'ic']:
            self.caller.msg("Description type must be either 'general' or 'ic'.")
            return

        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return

        # Debug information
        self.caller.msg(f"Debug: Group ID: {group.id}")
        self.caller.msg(f"Debug: Group leader: {group.leader}")
        if group.leader:
            self.caller.msg(f"Debug: Group leader ID: {group.leader.id}")
            self.caller.msg(f"Debug: Group leader full name: {group.leader.full_name}")
        else:
            self.caller.msg("Debug: Group leader is not set.")
        self.caller.msg(f"Debug: Your character sheet: {self.caller.character_sheet}")
        self.caller.msg(f"Debug: Your character sheet ID: {self.caller.character_sheet.id}")

        # Check if the caller is the group leader or has permission to edit info
        is_leader = group.leader == self.caller.character_sheet if group.leader else False
        has_edit_permission = GroupMembership.objects.filter(
            character=self.caller.character_sheet,
            group=group,
            role__can_edit_info=True
        ).exists()

        self.caller.msg(f"Debug: Is leader: {is_leader}")
        self.caller.msg(f"Debug: Has edit permission: {has_edit_permission}")

        if is_leader:
            self.caller.msg("You have permission to edit as the group leader.")
        elif has_edit_permission:
            self.caller.msg("You have permission to edit based on your role.")
        else:
            self.caller.msg("You don't have permission to edit this group's description.")
            return

        # Update the description
        if desc_type == 'general':
            group.description = description
        else:  # ic
            group.ic_description = description

        group.save()

        self.caller.msg(f"Updated the {desc_type} description for group '{group_name}'.")
        logger.log_info(f"{self.caller.name} updated the {desc_type} description for group '{group_name}'.")

        # Display the updated group info
        info = f"Group: {group.name}\n"
        info += f"General Description: {group.description or 'Not set'}\n"
        info += f"IC Description: {group.ic_description or 'Not set'}\n"
        info += f"Leader: {group.leader.full_name if group.leader else 'None'}\n"
        members = GroupMembership.objects.filter(group=group)
        member_names = [member.character.full_name for member in members]
        info += f"Members ({len(member_names)}): {', '.join(member_names)}\n"
        info += f"Created: {group.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

        self.caller.msg(info)

class CmdGroupInfo(Command):
    """
    Display information about a group.
    Usage:
      groupinfo <name>
    Shows details about the specified group.
    """
    key = "groupinfo"
    locks = "cmd:all()"
    help_category = "Factions and Groups"
 
    def func(self):
        if not self.args:
            self.caller.msg("Usage: groupinfo <name>")
            return
        name = self.args.strip()
        try:
            group = Group.objects.get(name__iexact=name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{name}' exists.")
            return
        memberships = GroupMembership.objects.filter(group=group)
        members = [membership.character.full_name for membership in memberships]
        # Basic Group Info
        table = EvTable(border="table", width=78)
        table.add_row("|cGroup Name|n", group.name)
        table.add_row("|cOOC Description|n", crop(group.description or 'Not set', width=58))
        table.add_row("|cLeader|n", group.leader.full_name if group.leader else 'None')
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

class CmdGroupChat(Command):
    """
    Send a message to all members of your group.

    Usage:
      gchat <group_name> <message>

    Sends a message to all online members of the specified group.
    """
    key = "gchat"
    aliases = ["groupchat"]
    locks = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args or len(self.args.split()) < 2:
            self.caller.msg("Usage: gchat <group_name> <message>")
            return

        group_name, message = self.args.split(None, 1)
        character_sheet = self.caller.character_sheet

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

        # Debug information
        self.caller.msg("Debug: Online accounts in this group:")
        for membership in GroupMembership.objects.filter(group=group):
            member = membership.character
            account = search_account(member.full_name)
            if account:
                self.caller.msg(f"- {member.full_name}: {'Online' if account[0].sessions.count() > 0 else 'Offline'}")
            else:
                self.caller.msg(f"- {member.full_name}: No associated account found")

class CmdSetGroupLeader(Command):
    """
    Set the leader of a group.

    Usage:
      setgroupleader <group_name> = <character_name>

    This command allows you to set or change the leader of a group.
    Only admins can use this command.

    Example:
      setgroupleader Samurai = Johnny Silverhand
    """

    key = "setgroupleader"
    aliases = ["set_group_leader"]
    locks = "cmd:perm(Admin)"
    help_category = "Factions and Groups"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: setgroupleader <group_name> = <character_name>")
            return

        group_name, character_name = [part.strip() for part in self.args.split("=")]

        self.caller.msg(f"Debug: Attempting to set leader for group '{group_name}' to '{character_name}'")

        try:
            group = Group.objects.get(name__iexact=group_name)
            self.caller.msg(f"Debug: Found group: {group}")
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return

        try:
            character_sheet = CharacterSheet.objects.get(full_name__iexact=character_name)
            self.caller.msg(f"Debug: Found character sheet: {character_sheet}")
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"No character named '{character_name}' exists.")
            return

        # Set the new leader
        self.caller.msg(f"Debug: Current group leader: {group.leader}")
        group.leader = character_sheet
        self.caller.msg(f"Debug: Setting new leader: {group.leader}")
        group.save()
        self.caller.msg("Debug: Group saved")

        # Ensure the leader is a member of the group and has edit permissions
        membership, created = GroupMembership.objects.get_or_create(character=character_sheet, group=group)
        self.caller.msg(f"Debug: Group membership created: {created}")

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
        self.caller.msg(f"Debug: Leader role created: {role_created}")

        # Assign the leader role to the new leader
        membership.role = leader_role
        membership.save()
        self.caller.msg("Debug: Leader role assigned to membership")

        # Verify the leader was set
        try:
            updated_group = Group.objects.get(id=group.id)
            self.caller.msg(f"Debug: Retrieved updated group: {updated_group}")
            self.caller.msg(f"Debug: Updated group leader: {updated_group.leader}")
            if updated_group.leader == character_sheet:
                self.caller.msg(f"{character_name} has been set as the leader of {group_name}.")
                self.caller.msg(f"Debug: Group ID: {updated_group.id}")
                self.caller.msg(f"Debug: Leader ID: {updated_group.leader.id}")
                self.caller.msg(f"Debug: Leader full name: {updated_group.leader.full_name}")
            else:
                self.caller.msg(f"Error: Failed to set {character_name} as the leader of {group_name}.")
                self.caller.msg(f"Debug: Updated group leader: {updated_group.leader}")
        except ObjectDoesNotExist:
            self.caller.msg(f"Error: Unable to retrieve the updated group.")

        logger.log_info(f"{self.caller.name} set {character_name} as the leader of {group_name}.")

class CmdApproveJoin(Command):
    """
    Approve a join request for your group.

    Usage:
      approvejoin <character_name> <group_name>

    Approves a character's request to join a group you lead.
    """
    key = "approvejoin"
    locks = "cmd:all()"
    help_category = "Factions and Groups"

    def func(self):
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: approvejoin <character_name> <group_name>")
            return

        character_name, group_name = self.args.split()
        leader_sheet = self.caller.character_sheet

        try:
            group = Group.objects.get(name__iexact=group_name, leader=leader_sheet)
        except Group.DoesNotExist:
            self.caller.msg(f"You are not the leader of a group named '{group_name}'.")
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
        if character_sheet.db_object:
            character_sheet.db_object.msg(f"Your request to join '{group_name}' has been approved.")

class CmdCreateGroupRole(Command):
    """
    Create a new role for a group.

    Usage:
      creategrouprole <group_name> <role_name> = <permissions>

    Permissions are comma-separated and can include:
    invite, kick, promote, edit_info

    Example:
      creategrouprole MyGang Officer = invite,kick
    """
    key = "creategrouprole"
    locks = "cmd:all()"
    help_category = "Factions and Groups"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: creategrouprole <group_name> <role_name> = <permissions>")
            return

        group_and_role, permissions = self.args.split("=", 1)
        group_name, role_name = group_and_role.rsplit(None, 1)
        
        group_name = group_name.strip()
        role_name = role_name.strip()
        permissions = [p.strip() for p in permissions.split(",")]

        character_sheet = self.caller.character_sheet

        try:
            group = Group.objects.get(name__iexact=group_name)
        except Group.DoesNotExist:
            self.caller.msg(f"No group named '{group_name}' exists.")
            return

        if group.leader != character_sheet:
            self.caller.msg("Only the group leader can create new roles.")
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

class CmdAssignGroupRole(Command):
    """
    Assign a role to a group member.

    Usage:
      assigngrouprole <group_name> <character_name> = <role_name>

    Example:
      assigngrouprole MyGang Alice = Officer
    """
    key = "assigngrouprole"
    locks = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: assigngrouprole <group_name> <character_name> = <role_name>")
            return

        group_and_character, role_name = self.args.split("=", 1)
        group_name, character_name = group_and_character.rsplit(None, 1)
        
        group_name = group_name.strip()
        character_name = character_name.strip()
        role_name = role_name.strip()

        character_sheet = self.caller.character_sheet

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

        if group.leader != character_sheet and not GroupMembership.objects.filter(
            character=character_sheet, group=group, role__can_promote=True
        ).exists():
            self.caller.msg("You don't have permission to assign roles in this group.")
            return

        membership, created = GroupMembership.objects.get_or_create(character=target_character, group=group)
        membership.role = role
        membership.save()

        self.caller.msg(f"Assigned role '{role_name}' to {character_name} in group '{group_name}'.")


class CmdCreateFaction(Command):
    """
    Create a new faction.

    Usage:
      createfaction <name>

    Creates a new faction. This command should be restricted to admins.
    """
    key = "createfaction"
    locks = "cmd:perm(Admin)"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args:
            self.caller.msg("Usage: createfaction <name>")
            return

        name = self.args.strip()

        if Faction.objects.filter(name__iexact=name).exists():
            self.caller.msg(f"A faction named '{name}' already exists.")
            return

        new_faction = Faction.objects.create(name=name)
        self.caller.msg(f"You have created the faction '{name}'.")

class CmdFactionDesc(Command):
    """
    Set or update the description of a faction.

    Usage:
      factiondesc <faction_name> <type> = <description>

    Where <type> is either 'general' or 'ic' (in-character).

    Examples:
      factiondesc Arasaka general = A powerful megacorporation specializing in security and technology.
      factiondesc Arasaka ic = Known for their ruthless business practices and cutting-edge cyberware.
    """

    key = "factiondesc"
    aliases = ["faction_description"]
    locks = "cmd:perm(Admin)"  
    help_category = "Factions and Groups"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: factiondesc <faction_name> <type> = <description>")
            return

        args, description = self.args.split("=", 1)
        args = args.strip().split()
        
        if len(args) != 2:
            self.caller.msg("Usage: factiondesc <faction_name> <type> = <description>")
            return

        faction_name, desc_type = args
        description = description.strip()

        if desc_type not in ['general', 'ic']:
            self.caller.msg("Description type must be either 'general' or 'ic'.")
            return

        try:
            faction = Faction.objects.get(name__iexact=faction_name)
        except Faction.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        if desc_type == 'general':
            faction.description = description
        else:  # ic
            faction.ic_description = description

        faction.save()

        self.caller.msg(f"Updated the {desc_type} description for faction '{faction_name}'.")
        logger.log_info(f"{self.caller.name} updated the {desc_type} description for faction '{faction_name}'.")

class CmdFactionInfo(Command):
    """
    Display information about a faction.

    Usage:
      factioninfo <name>

    Shows details about the specified faction.
    """
    key = "factioninfo"
    locks = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args:
            self.caller.msg("Usage: factioninfo <name>")
            return

        name = self.args.strip()

        try:
            faction = Faction.objects.get(name__iexact=name)
        except Faction.DoesNotExist:
            self.caller.msg(f"No faction named '{name}' exists.")
            return

        info = f"Faction: {faction.name}\n"
        info += f"General Description: {faction.description or 'Not set'}\n"
        info += f"IC Description: {faction.ic_description or 'Not set'}\n"
        info += f"Influence: {faction.influence}\n"
        info += f"Created: {faction.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

        self.caller.msg(info)


class CmdFactionRep(Command):
    """
    Check your reputation with a faction.

    Usage:
      factionrep <faction_name>

    Displays your current reputation with the specified faction.
    """
    key = "factionrep"
    locks = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args:
            self.caller.msg("Usage: factionrep <faction_name>")
            return

        faction_name = self.args.strip()
        character_sheet = self.caller.character_sheet

        try:
            faction = Faction.objects.get(name__iexact=faction_name)
        except Faction.DoesNotExist:
            self.caller.msg(f"No faction named '{faction_name}' exists.")
            return

        reputation, created = FactionReputation.objects.get_or_create(
            character=character_sheet,
            faction=faction
        )

        self.caller.msg(f"Your reputation with {faction.name}: {reputation.reputation}")

class CmdModifyFactionRep(Command):
    """
    Modify a character's reputation with a faction.

    Usage:
      modifyfactionrep <character> <faction> <amount>

    This command should be restricted to admins or specific roles.
    """
    key = "modifyfactionrep"
    locks = "cmd:perm(Admin)"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args or len(self.args.split()) != 3:
            self.caller.msg("Usage: modifyfactionrep <character> <faction> <amount>")
            return

        char_name, faction_name, amount = self.args.split()

        try:
            character = CharacterSheet.objects.get(full_name__iexact=char_name)
            faction = Faction.objects.get(name__iexact=faction_name)
            amount = int(amount)
        except CharacterSheet.DoesNotExist:
            self.caller.msg(f"Character '{char_name}' not found.")
            return
        except Faction.DoesNotExist:
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

class CmdFactionMission(Command):
    """
    Attempt a mission for a faction to gain reputation and influence.

    Usage:
      factionmission <faction_name>

    Attempt a mission for the specified faction. Success is based on your
    skills and a bit of luck. Successful missions increase your reputation
    with the faction and the faction's overall influence.
    """
    key = "factionmission"
    locks = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        if not self.args:
            self.caller.msg("Usage: factionmission <faction_name>")
            return

        faction_name = self.args.strip()
        character_sheet = self.caller.character_sheet

        try:
            faction = Faction.objects.get(name__iexact=faction_name)
        except Faction.DoesNotExist:
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

class CmdFactionInfluence(Command):
    """
    Check the current influence of all factions.

    Usage:
      factioninfluence

    Displays a list of all factions and their current influence levels.
    """
    key = "factioninfluence"
    locks = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        factions = Faction.objects.all().order_by('-influence')

        if not factions:
            self.caller.msg("There are no factions in the game yet.")
            return

        table = self.styled_table("Faction", "Influence")
        for faction in factions:
            table.add_row(faction.name, faction.influence)

        self.caller.msg(table)

class CmdListGroupsAndFactions(Command):
    """
    List all existing groups and factions.

    Usage:
      listgf

    This command displays a table of all groups and factions,
    showing their name, type, and number of members.
    """

    key = "listgf"
    aliases = ["listgroupsandfactions"]
    lock = "cmd:all()"
    help_category = "Factions and Groups"
  
    def func(self):
        groups = Group.objects.all()
        factions = Faction.objects.all()

        table = EvTable("Name", "Type", "Members", border="cells")

        for group in groups:
            member_count = GroupMembership.objects.filter(group=group).count()
            table.add_row(group.name, "Group", member_count)

        for faction in factions:
            member_count = faction.factionreputation_set.count()
            table.add_row(faction.name, "Faction", member_count)

        if not groups and not factions:
            self.caller.msg("There are no groups or factions in the game yet.")
        else:
            self.caller.msg(table)