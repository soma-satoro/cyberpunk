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
from .character_commands import CmdSheet, CmdRoll, CmdLuck, CmdShortDesc, CmdOOC, CmdPlusOoc, CmdPlusIc, CmdMeet
from .chargen import CmdChargen, CmdListCharacterSheets, CmdLifepath, CmdSelfStat, CmdSetLanguage
from .admin_commands import CmdStat, CmdHeal, CmdApprove, CmdUnapprove, CmdSpawnRipperdoc, CmdGradientName, CmdClearAllStates, CmdClearRental, CmdCleanupDuplicates, CmdExamine, CmdAssociateAllCharacterSheets, CmdViewCharacterSheetID, CmdSetCharacterSheetID, CmdAllSheets, CmdViewSheetAttributes, CmdSyncLanguages, CmdJoin, CmdSummon
from .inventory_commands import CmdInventory
from .equipment_commands import CmdAddWeapon, CmdAddArmor, CmdAddGear, CmdPopulateWeapons, CmdPopulateArmor, CmdPopulateGear, CmdViewEquipment, CmdPopulateAllEquipment, CmdRemoveEquipment, CmdPopulateCyberware, CmdDepopulateAllEquipment, CmdYes
from .economy import CmdAdminMoney, CmdGiveMoney, CmdBalance, CmdRentRoom, CmdLeaveRental
from .mission_commands import CmdListMissions, CmdAcceptMission, CmdCompleteMission, CmdMissionStatus, CmdCreateMission, CmdListEvents, CmdCreateEvent, CmdEventInfo, CmdJoinEvent, CmdLeaveEvent, CmdStartEvent, CmdCompleteEvent
from .bbs.bbs_all_commands import CmdBBS, CmdBBPost, CmdBBRead
from .hustle_commands import CmdHustle, CmdDebugHustle, CmdClearHustleAttempt, CmdRegenerateHustles
from .faction_commands import (
    CmdFaction, CmdGroup, CmdInitFactions
)
from world.mail.commands import CmdMail, CmdMailbox, CmdMailDelete
from .jobs.jobs_commands import CmdJobs
from .cyberware_commands import CmdCyberware
from .netrun_commands import CmdNet
from .netrun_admin_commands import CmdArchitecture
from .combat_system import CmdCombat
from .language_commands import CmdLanguage, CmdMaskedSay, CmdMaskedEmit, CmdMaskedPose
from .building import CmdManageBuilding
from .notes import CmdNotes
from evennia.contrib.base_systems.mux_comms_cmds import CmdSetLegacyComms
from evennia import default_cmds
from .CmdAlts import CmdAlts
from .CmdEmit import CmdEmit
from .CmdPose import CmdPose
from .CmdSay import CmdSay
from .CmdHangouts import CmdHangout
from .CmdPlots import CmdPlots
from .CmdWatch import CmdWatch
from .CmdWeather import CmdWeather
from .CmdMultidesc import CmdMultidesc
from .CmdFinger import CmdFinger
from .CmdGradient import CmdGradientName
from .where import CmdWhere
from .CmdWho import CmdWho

from commands.bbs.bbs_admin_commands import CmdResetBBS

from commands.bbs.bbs_all_commands import (
    CmdBBS
)

from commands.bbs.bbs_builder_commands import (
    CmdCreateBoard,CmdDeleteBoard, CmdRevokeAccess, CmdListAccess, 
    CmdLockBoard, CmdPinPost, CmdUnpinPost, CmdEditBoard, CmdGrantAccess
)
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
        
        self.add(CmdSetLegacyComms())
        self.add(CmdSheet())
        self.add(CmdSelfStat())
        self.add(CmdRoll())
        self.add(CmdLifepath())
        self.add(CmdLuck())
        self.add(CmdInventory())
        self.add(CmdViewEquipment())
        self.add(CmdChargen())
        self.add(CmdManageBuilding())
        self.add(CmdCombat())
        self.add(CmdAlts())
        self.add(CmdEmit())
        self.add(CmdPose())
        self.add(CmdSay())
        self.add(CmdHangout())
        self.add(CmdWho())
        self.add(CmdWhere())
        self.add(CmdPlots())
        self.add(CmdWatch())
        self.add(CmdWeather())
        self.add(CmdMultidesc())
        self.add(CmdFinger())
        self.add(CmdGradientName())
        self.add(CmdBalance())
        self.add(CmdGiveMoney())
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
        self.add(CmdHustle())
        
        # Add faction and group commands
        self.add(CmdFaction())
        self.add(CmdGroup())
        
        # Continue with other commands
        self.add(CmdMail())
        self.add(CmdMailbox())
        self.add(CmdMailDelete())
        self.add(CmdJobs())
        self.add(CmdShortDesc())
        self.add(CmdSetLanguage())
        self.add(CmdCyberware())
        self.add(CmdNet())
        self.add(CmdArchitecture())
        self.add(CmdLanguage())
        self.add(CmdMaskedSay())
        self.add(CmdMaskedPose())
        self.add(CmdMaskedEmit())
        self.add(CmdRentRoom())
        self.add(CmdLeaveRental())
        self.add(CmdOOC())
        self.add(CmdPlusOoc())
        self.add(CmdPlusIc())
        self.add(CmdMeet())
        self.add(CmdNotes())
        self.add(CmdBBS())
        self.add(CmdResetBBS())
        self.add(CmdCreateBoard())
        self.add(CmdDeleteBoard())
        self.add(CmdRevokeAccess())
        self.add(CmdListAccess())
        self.add(CmdLockBoard())
        self.add(CmdPinPost())
        self.add(CmdUnpinPost())
        self.add(CmdEditBoard())
        self.add(CmdGrantAccess())

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
        self.add(CmdPopulateCyberware())
        self.add(CmdAdminMoney())
        self.add(CmdSpawnRipperdoc())
        self.add(CmdClearHustleAttempt())
        self.add(CmdDebugHustle())
        self.add(CmdRegenerateHustles())
        
        # Add admin faction commands
        self.add(CmdInitFactions())
        
        self.add(CmdGradientName())
        self.add(CmdClearAllStates())
        self.add(CmdListCharacterSheets())
        self.add(CmdHeal())
        self.add(CmdClearRental())
        self.add(CmdCleanupDuplicates())
        self.add(CmdExamine())
        self.add(CmdAssociateAllCharacterSheets())
        self.add(CmdAllSheets())
        self.add(CmdSetCharacterSheetID())
        self.add(CmdViewCharacterSheetID())
        self.add(CmdViewSheetAttributes())
        self.add(CmdSyncLanguages())
        self.add(CmdJoin())
        self.add(CmdSummon())

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
