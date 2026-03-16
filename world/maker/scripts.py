# -*- coding: utf-8 -*-
"""
Maker craft queue processor script.
Runs periodically to process completed fabrication orders.
"""
from evennia import DefaultScript
from evennia.scripts.models import ScriptDB
from evennia import create_script

from world.maker.services import process_due_orders

MAKER_SCRIPT_KEY = "MakerCraftProcessor"


class MakerCraftScript(DefaultScript):
    """
    Script that runs every 15 minutes to process due Maker craft orders.
    When a Tech's fabrication time elapses, we auto-roll and deliver voucher or refund.
    """

    def at_script_creation(self):
        self.key = MAKER_SCRIPT_KEY
        self.desc = "Processes Tech Maker fabrication queue"
        self.interval = 900  # 15 minutes
        self.persistent = True
        self.repeats = -1  # Run indefinitely

    def at_repeat(self):
        process_due_orders()


def get_or_create_maker_script():
    """Get or create the Maker craft processor script."""
    try:
        script = ScriptDB.objects.get(db_key=MAKER_SCRIPT_KEY)
    except ScriptDB.DoesNotExist:
        script = create_script(MakerCraftScript, key=MAKER_SCRIPT_KEY)
    except ScriptDB.MultipleObjectsReturned:
        scripts = ScriptDB.objects.filter(db_key=MAKER_SCRIPT_KEY)
        script = scripts.first()
        for extra in scripts[1:]:
            extra.delete()
    if script and not script.is_active:
        script.start()
    return script
