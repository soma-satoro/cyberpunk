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
from .character_commands import CmdSheet, CmdRoll, CmdLuck, CmdShortDesc, CmdPlusOoc, CmdPlusIc, CmdMeet
from .chargen import CmdChargen, CmdListCharacterSheets, CmdLifepath, CmdSelfStat, CmdSetLanguage, CmdSellYourSoul
from .admin_commands import CmdStat, CmdHeal, CmdHarm, CmdApprove, CmdUnapprove, CmdSpawnRipperdoc, CmdGradientName, CmdClearAllStates, CmdClearRental, CmdCleanupDuplicates, CmdExamine, CmdAssociateAllCharacterSheets, CmdViewCharacterSheetID, CmdSetCharacterSheetID, CmdAllSheets, CmdViewSheetAttributes, CmdSyncLanguages, CmdJoin, CmdSummon, CmdClearDb
from .inventory_commands import CmdInventory, CmdWear, CmdEquipWeapon
from .voucher_commands import CmdVoucher, CmdConceal, CmdOwner
from .equipment_commands import CmdAddItem, CmdAddVehicle, CmdRemoveVehicle, CmdPopulateWeapons, CmdPopulateArmor, CmdPopulateGear, CmdPopulateVehicles, CmdViewEquipment, CmdPopulateAllEquipment, CmdRemoveEquipment, CmdPopulateCyberware, CmdDepopulateAllEquipment
from .list_commands import CmdLookup
from .mystery_commands import (
    CmdMystery,
    CmdInvestigate,
    CmdRest,
    CmdOvercome,
    CmdAddClue,
    CmdAddObstacle,
    CmdClues,
    CmdCreateMystery,
    CmdCreateClue,
    CmdDestroyClue,
    CmdLinkClue,
    CmdMysteryLink,
)
from .cyberware_admin_commands import CmdAddCyberware, CmdParentCyberware, CmdUnparentCyberware
from .staff_commands import CmdRemoveCyberware, CmdSetLifepath, CmdReputation, CmdNotoriety, CmdConfig
from .economy import CmdAdminMoney, CmdGiveMoney, CmdBalance, CmdLeaveRental
from .rent_commands import CmdRent, CmdHome
from world.cyberpunk_sheets.commerce import CmdBuy, CmdRefund, CmdListItems, CmdGive, CmdSellItem, CmdHaggle
from .ip_commands import CmdIP
from .vote_commands import CmdVote
from .mission_commands import CmdMission
from .bbs.bbs_all_commands import CmdBBS, CmdBBPost, CmdBBRead
from .hustle_commands import CmdHustle, CmdDebugHustle, CmdClearHustleAttempt, CmdResetHustles
from .faction_commands import (
    CmdFaction, CmdGroup, CmdInitFactions
)
from world.mail.commands import CmdMail, CmdMailbox, CmdMailDelete
from .jobs.jobs_commands import CmdJobs
from .cyberware_commands import CmdCyberware
from .netrun_commands import CmdNet
from .netrun_admin_commands import CmdArchitecture
from .combat_system import CmdCombat
from .attack_commands import CmdAttack, CmdDodge, CmdDeathSave, CmdCover, CmdHud
from .repair_commands import CmdRepair, CmdJuryrig
from .treat_commands import CmdTreat
from .health_commands import CmdHealth
from .maker_commands import CmdMake
from .language_commands import CmdLanguage
from .building import CmdManageBuilding, CmdRoom, CmdAreaManage
from .notes import CmdNote
from evennia.contrib.base_systems.mux_comms_cmds import CmdSetLegacyComms
from commands.commonmux.CmdOOCChat import CmdOOCChat

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
from .CmdWho import CmdWho, CmdLfrp
from .coords_commands import CmdCoords, CmdGo
from .commonmux.CmdPage import CmdPage
#from .vehicle_commands import CmdEnterVehicle, CmdExitVehicle
from .dice_commands import CmdDice
from .npc_commands import CmdNpc
from .elflines_commands import CmdElo, CmdElfline, CmdEloSetup
from .help_commands import CmdHelpSearch

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
        self.add(CmdHelpSearch())
        self.add(CmdSetLegacyComms())
        self.add(CmdSheet())
        self.add(CmdSelfStat())
        self.add(CmdRoll())
        self.add(CmdLifepath())
        self.add(CmdLuck())
        self.add(CmdInventory())
        self.add(CmdWear())
        self.add(CmdRepair())
        self.add(CmdJuryrig())
        self.add(CmdTreat())
        self.add(CmdHealth())
        self.add(CmdMake())
        self.add(CmdVoucher())
        self.add(CmdConceal())
        self.add(CmdOwner())
        self.add(CmdViewEquipment())
        self.add(CmdLookup())
        self.add(CmdMystery())
        self.add(CmdInvestigate())
        self.add(CmdRest())
        self.add(CmdOvercome())
        self.add(CmdChargen())
        self.add(CmdSellYourSoul())
        self.add(CmdManageBuilding())
        self.add(CmdRoom())
        self.add(CmdAreaManage())
        self.add(CmdCombat())
        self.add(CmdAttack())
        self.add(CmdDodge())
        self.add(CmdDeathSave())
        self.add(CmdCover())
        self.add(CmdHud())
        self.add(CmdEquipWeapon())
        self.add(CmdAlts())
        self.add(CmdEmit())
        self.add(CmdPose())
        self.add(CmdSay())
        self.add(CmdHangout())
        self.add(CmdWho())
        self.add(CmdLfrp())
        self.add(CmdWhere())
        self.add(CmdCoords())
        self.add(CmdGo())
        self.add(CmdPlots())
        self.add(CmdWatch())
        self.add(CmdWeather())
        self.add(CmdMultidesc())
        self.add(CmdFinger())
        self.add(CmdGradientName())
        self.add(CmdBalance())
        self.add(CmdGiveMoney())
        self.add(CmdBuy())
        self.add(CmdRefund())
        self.add(CmdListItems())
        self.add(CmdGive())
        self.add(CmdSellItem())
        self.add(CmdHaggle())
        self.add(CmdMission())
        self.add(CmdHustle())
        self.add(CmdDice())
        self.add(CmdNpc())
        self.add(CmdElo())
        self.add(CmdElfline())

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
        # CmdSay, CmdPose, CmdEmit (added above) handle say/pose/emit with pose breaks and ~language
        # CmdMaskedSay/Pose/Emit removed - they overrode with wrong format ("says:" vs "says, \"\"")
        #self.add(CmdEnterVehicle())
        #self.add(CmdExitVehicle())
        self.add(CmdRent())
        self.add(CmdHome())
        self.add(CmdLeaveRental())
        self.add(CmdOOCChat())
        self.add(CmdPlusOoc())
        self.add(CmdPlusIc())
        self.add(CmdMeet())
        self.add(CmdNote())
        self.add(CmdIP())
        self.add(CmdVote())
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
        self.add(CmdPage())

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
        self.add(CmdAddItem())
        self.add(CmdAddVehicle())
        self.add(CmdRemoveVehicle())
        self.add(CmdPopulateWeapons())
        self.add(CmdPopulateArmor())
        self.add(CmdPopulateGear())
        self.add(CmdPopulateVehicles())
        self.add(CmdPopulateAllEquipment())
        self.add(CmdDepopulateAllEquipment())
        self.add(CmdRemoveEquipment())
        self.add(CmdAddCyberware())
        self.add(CmdParentCyberware())
        self.add(CmdUnparentCyberware())
        self.add(CmdRemoveCyberware())
        self.add(CmdAddClue())
        self.add(CmdAddObstacle())
        self.add(CmdClues())
        self.add(CmdCreateMystery())
        self.add(CmdCreateClue())
        self.add(CmdDestroyClue())
        self.add(CmdLinkClue())
        self.add(CmdMysteryLink())
        self.add(CmdSetLifepath())
        self.add(CmdReputation())
        self.add(CmdNotoriety())
        self.add(CmdConfig())
        self.add(CmdApprove())
        self.add(CmdUnapprove())
        self.add(CmdPopulateCyberware())
        self.add(CmdAdminMoney())
        self.add(CmdSpawnRipperdoc())
        self.add(CmdClearHustleAttempt())
        self.add(CmdDebugHustle())
        self.add(CmdResetHustles())
        
        # Add admin faction commands
        self.add(CmdInitFactions())
        self.add(CmdEloSetup())

        self.add(CmdGradientName())
        self.add(CmdClearAllStates())
        self.add(CmdListCharacterSheets())
        self.add(CmdHeal())
        self.add(CmdHarm())
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
        self.add(CmdClearDb())

class EquipmentAdminCmdSet(CmdSet): # type: ignore
    """
    Cmdset for admin-level equipment management commands.
    """
    key = "EquipmentAdmin"
    
    def at_cmdset_creation(self):
        self.add(CmdAddItem())

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
