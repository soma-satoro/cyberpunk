"""
CommonMux Command Set

This cmdset includes all CommonMux-specific custom commands.
"""

from evennia.commands.cmdset import CmdSet

from commands.commonmux.CmdAlias import CmdAlias
from commands.commonmux.CmdAlts import CmdAlts
from commands.commonmux.CmdEmit import CmdEmit
from commands.commonmux.CmdLanguage import CmdLanguage
from commands.commonmux.CmdOOCChat import CmdOOCChat, CmdUnpuppet
from commands.commonmux.CmdPage import CmdPage
from commands.commonmux.CmdPool import CmdPool, CmdGain, CmdSpend
from commands.commonmux.CmdPose import CmdPose
from commands.commonmux.CmdSay import CmdSay
from commands.commonmux.CmdShortDesc import CmdShortDesc
from commands.commonmux.CmdStaff import CmdStaff
from commands.commonmux.CmdTableTalk import CmdTableTalk
from commands.commonmux.CmdTxt import CmdText
from commands.commonmux.CmdWatch import CmdWatch
from commands.commonmux.CmdWeather import CmdWeather
from commands.commonmux.CmdWho import CmdWho  # CmdCensus removed - see commands.census instead
from commands.commonmux.notes import CmdNote
from commands.commonmux.CmdFinger import CmdFinger


class CommonMuxCmdSet(CmdSet):
    """
    This cmdset includes all CommonMux custom commands.
    """
    key = "CommonMux"
    priority = 1

    def at_cmdset_creation(self):
        """
        Populates the cmdset with all CommonMux commands.
        """
        # Character and roleplay commands
        self.add(CmdAlias())
        self.add(CmdAlts())
        self.add(CmdEmit())
        self.add(CmdFinger())
        self.add(CmdOOCChat())
        self.add(CmdPose())
        self.add(CmdSay())
        self.add(CmdShortDesc())
        self.add(CmdTableTalk())
        
        # Communication commands
        self.add(CmdPage())
        self.add(CmdText())
        
        # Information and social commands
        self.add(CmdStaff())
        self.add(CmdUnpuppet())
        self.add(CmdWatch())
        self.add(CmdWeather())
        self.add(CmdWho())
        # self.add(CmdCensus())  # Commented out - replaced by commands.census.CmdCensus
        self.add(CmdNote())
        
        # Game mechanics commands
        self.add(CmdPool())
        self.add(CmdSpend())
        self.add(CmdGain())
        self.add(CmdLanguage())

