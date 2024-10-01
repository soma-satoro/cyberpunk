from evennia import default_cmds, CmdSet
"""
Command sets

All commands in the game must be grouped in a cmdset.  A given command
can be part of any number of cmdsets and cmdsets can be added/removed
and merged onto entities at runtime.

To create new commands to populate the cmdset, see
`commands/command.py`.

This module wraps the default command sets of Evennia; overloads them
to add/remove commands from the default lineup. You can create your
own cmdsets by inheriting from them or directly from `evennia.CmdSet`.

"""

from evennia import default_cmds, CmdSet
from .character_commands import CmdSheet, CmdSetStat, CmdRoll, CmdRole, CmdSpendLuck, CmdGainLuck, CmdEquipWeapon, CmdUnequipWeapon, CmdShortDesc, CmdSetLanguage
from .chargen import CmdChargen, CmdChargenFinish, CmdClearSheet, CmdListCharacterSheets
from .lifepath import CmdViewLifepath, CmdLifepath  
from .admin_commands import CmdStat, CmdHeal, CmdApprove, CmdUnapprove, CmdAdminViewSheet, CmdAdminViewLifepath, CmdFixSheet, CmdSpawnRipperdoc, CmdGradientName, CmdClearAllStates, CmdCleanupDuplicateGear, CmdClearRental, CmdCleanupDuplicates
from .inventory_commands import CmdInventory, CmdEquipment
from .equipment_commands import CmdAddWeapon, CmdAddArmor, CmdAddGear, CmdPopulateWeapons, CmdPopulateArmor, CmdPopulateGear, CmdViewEquipment, CmdPopulateAllEquipment, CmdRemoveEquipment, CmdPopulateCyberware, CmdDepopulateAllEquipment, CmdYes
from .economy import CmdAdminMoney, CmdGiveMoney, CmdBalance, CmdRentRoom, CmdLeaveRental
from world.cyberpunk_sheets.commerce import CmdBuy, CmdSellItem, CmdHaggle, CmdAddItem, CmdRemItem, CmdListItems
from .mission_commands import CmdListMissions, CmdAcceptMission, CmdCompleteMission, CmdMissionStatus, CmdCreateMission, CmdListEvents, CmdCreateEvent, CmdEventInfo, CmdJoinEvent, CmdLeaveEvent, CmdStartEvent, CmdCompleteEvent
from .bulletin_commands import CmdBoardList, CmdBoardRead, CmdBoardPost, CmdBoardDelete, CmdBoardEdit
from .hustle_commands import CmdHustle, CmdDebugHustle, CmdClearHustleAttempt, CmdRegenerateHustles
from .faction_commands import CmdCreateFaction, CmdFactionInfo, CmdFactionRep, CmdModifyFactionRep, CmdCreateGroup, CmdJoinGroup, CmdLeaveGroup, CmdGroupInfo, CmdFactionInfluence, CmdCreateGroupRole, CmdAssignGroupRole, CmdGroupChat, CmdFactionMission, CmdListGroupsAndFactions, CmdApproveJoin, CmdFactionDesc, CmdGroupDesc, CmdSetGroupLeader
from world.mail.commands import CmdMail, CmdMailbox, CmdMailDelete
from .request_commands import CmdRequests, CmdStaffRequest, CmdStaffRequestView, CmdStaffRequestAssign, CmdStaffRequestComment, CmdStaffRequestClose
from .cyberware_commands import CmdCyberware, CmdActivateCyberware
from .netrun_commands import CmdNetrun, CmdInstallProgram, CmdListPrograms, CmdListNetArchitectures
from .netrun_admin_commands import CmdCreateNetArchitecture
from .combat_system import CombatStartCommand, CombatCommand, CmdReload, CmdJoinCombat
from .language_commands import CmdLanguage, CmdMaskedSay, CmdMaskedPose, CmdMaskedEmit
from .building import CmdCreateRentableRoom
from evennia import default_cmds
# from typeclasses.characters import CharacterCmdSet as BaseCharacterCmdSet

class CharacterCmdSet(default_cmds.CharacterCmdSet):
    """
    The `CharacterCmdSet` contains general in-game commands like `look`,
    `get`, etc available on in-game Character objects. It is merged with
    the `AccountCmdSet` when an Account puppets a Character.
    """

    key = "DefaultCharacter"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        
        self.add(CmdSheet())
        self.add(CmdSetStat())
        self.add(CmdRoll())
        self.add(CmdRole())
        self.add(CmdViewLifepath())
        self.add(CmdLifepath())
        self.add(CmdSpendLuck())
        self.add(CmdGainLuck())
        self.add(CmdInventory())
        self.add(CmdEquipment())
        self.add(CmdViewEquipment())
        self.add(CmdEquipWeapon())
        self.add(CmdChargen())
        self.add(CmdClearSheet())
        self.add(CmdChargenFinish())
        self.add(CombatStartCommand())
        self.add(CombatCommand())
        self.add(CmdReload())
        self.add(CmdJoinCombat())
        self.add(CmdBalance())
        self.add(CmdGiveMoney())
        self.add(CmdBuy())
        self.add(CmdSellItem())
        self.add(CmdListItems())
        self.add(CmdHaggle())
        self.add(CmdUnequipWeapon())
        self.add(CmdListMissions())
        self.add(CmdAcceptMission())
        self.add(CmdCompleteMission())
        self.add(CmdMissionStatus())
        self.add(CmdCreateMission())
        self.add(CmdListEvents())
        self.add(CmdCreateEvent())
        self.add(CmdEventInfo())
        self.add(CmdJoinEvent())
        self.add(CmdLeaveEvent())
        self.add(CmdStartEvent())
        self.add(CmdCompleteEvent())
        self.add(CmdBoardList())
        self.add(CmdBoardRead())
        self.add(CmdBoardPost())
        self.add(CmdBoardDelete())
        self.add(CmdBoardEdit())
        self.add(CmdHustle())
        self.add(CmdFactionInfo())
        self.add(CmdGroupInfo())
        self.add(CmdJoinGroup())
        self.add(CmdLeaveGroup())
        self.add(CmdFactionInfo())
        self.add(CmdFactionRep())
        self.add(CmdFactionInfluence())
        self.add(CmdFactionMission())
        self.add(CmdAssignGroupRole())
        self.add(CmdCreateGroupRole())
        self.add(CmdGroupChat())
        self.add(CmdListGroupsAndFactions())
        self.add(CmdApproveJoin())
        self.add(CmdMail())
        self.add(CmdMailbox())
        self.add(CmdMailDelete())
        self.add(CmdGroupDesc())
        self.add(CmdRequests())
        self.add(CmdShortDesc())
        self.add(CmdSetLanguage())
        self.add(CmdCyberware())
        self.add(CmdActivateCyberware())
        self.add(CmdNetrun())
        self.add(CmdInstallProgram())
        self.add(CmdListPrograms())
        self.add(CmdListNetArchitectures())
        self.add(CmdLanguage())
        self.add(CmdMaskedSay())
        self.add(CmdMaskedPose())
        self.add(CmdMaskedEmit())
        self.add(CmdRentRoom())
        self.add(CmdLeaveRental())

class AccountCmdSet(default_cmds.AccountCmdSet):
    """
    This is the cmdset available to the Account at all times. It is
    combined with the `CharacterCmdSet` when the Account puppets a
    Character. It holds game-account-specific commands, channel
    commands, etc.
    """

    key = "DefaultAccount"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
        self.add(CmdStat())
        self.add(CmdAddWeapon())
        self.add(CmdAddArmor())
        self.add(CmdAddGear())
        self.add(CmdPopulateWeapons())
        self.add(CmdPopulateArmor())
        self.add(CmdPopulateGear())
        self.add(CmdPopulateAllEquipment())
        self.add(CmdDepopulateAllEquipment())
        self.add(CmdYes())
        self.add(CmdRemoveEquipment())
        self.add(CmdApprove())
        self.add(CmdUnapprove())
        self.add(CmdAdminViewSheet())
        self.add(CmdAdminViewLifepath())
        self.add(CmdFixSheet())
        self.add(CmdPopulateCyberware())
        self.add(CmdAdminMoney())
        self.add(CmdAddItem())
        self.add(CmdRemItem())
        self.add(CmdSpawnRipperdoc())
        self.add(CmdClearHustleAttempt())
        self.add(CmdDebugHustle())
        self.add(CmdRegenerateHustles())
        self.add(CmdCreateFaction())
        self.add(CmdCreateGroup())
        self.add(CmdModifyFactionRep())
        self.add(CmdFactionDesc())
        self.add(CmdSetGroupLeader())
        self.add(CmdStaffRequest())
        self.add(CmdStaffRequestView())
        self.add(CmdStaffRequestAssign())
        self.add(CmdStaffRequestComment())
        self.add(CmdStaffRequestClose())
        self.add(CmdGradientName())
        self.add(CmdCreateNetArchitecture())
        self.add(CmdClearAllStates())
        self.add(CmdListCharacterSheets())
        self.add(CmdCleanupDuplicateGear())
        self.add(CmdHeal())
        self.add(CmdCreateRentableRoom())
        self.add(CmdClearRental())
        self.add(CmdCleanupDuplicates())

class EquipmentAdminCmdSet(CmdSet): # type: ignore
    """
    Cmdset for admin-level equipment management commands.
    """
    key = "EquipmentAdmin"
    
    def at_cmdset_creation(self):
        self.add(CmdAddWeapon())
        self.add(CmdAddArmor())
        self.add(CmdAddGear())

class UnloggedinCmdSet(default_cmds.UnloggedinCmdSet):
    """
    Command set available to the Session before being logged in.  This
    holds commands like creating a new account, logging in, etc.
    """

    key = "DefaultUnloggedin"

    def at_cmdset_creation(self):
        """
        Populates the cmdset
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #


class SessionCmdSet(default_cmds.SessionCmdSet):
    """
    This cmdset is made available on Session level once logged in. It
    is empty by default.
    """

    key = "DefaultSession"

    def at_cmdset_creation(self):
        """
        This is the only method defined in a cmdset, called during
        its creation. It should populate the set with command instances.

        As and example we just add the empty base `Command` object.
        It prints some info.
        """
        super().at_cmdset_creation()
        #
        # any commands you add below will overload the default ones.
        #
