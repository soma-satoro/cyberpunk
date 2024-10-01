from evennia import create_object
from evennia.objects.objects import DefaultObject
from .merchants import CyberwareMerchantCmdSet

class CyberwareMerchantNPC(DefaultObject):
    def at_object_creation(self):
        self.cmdset.add(CyberwareMerchantCmdSet, permanent=True)
        self.db.desc = "A grizzled ripperdoc with cybernetic arms, ready to enhance your body with the latest tech."
        self.db.name_list = ["ripperdoc", "doc", "surgeon"]

    def at_say(self, message, receivers=None, msg_self=None, **kwargs):
        """Customize the Ripperdoc's speech."""
        return f"|c{self.key} says, '{message}'|n"

def create_cyberware_merchant(location):
    merchant = create_object(
        CyberwareMerchantNPC,
        key="Doc Chrome",
        location=location
    )
    merchant.db.desc = "A grizzled street surgeon with cybernetic arms, known for quick and (mostly) reliable cyberware installations."
    return merchant