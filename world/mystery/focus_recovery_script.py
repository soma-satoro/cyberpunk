"""
Focus recovery script - every 24 hours, characters recover half their max Focus.
"""

from evennia import DefaultScript
from evennia.utils import logger
from world.mystery.models import CharacterFocus
from world.mystery.mystery_data import get_max_focus


class FocusRecoveryScript(DefaultScript):
    """Recovers half of max Focus for all characters every 24 hours."""

    def at_script_creation(self):
        self.key = "FocusRecovery"
        self.desc = "Recovers half of max Focus every 24 hours"
        self.interval = 86400  # 24 hours in seconds
        self.persistent = True

    def at_repeat(self):
        recovered_count = 0
        for focus in CharacterFocus.objects.all():
            char = focus.character_object or (
                focus.character_sheet.character if focus.character_sheet else None
            )
            if not char:
                continue
            max_focus = focus.get_max_focus()
            half = max_focus // 2
            room = max(0, max_focus - focus.current_focus)
            gain = min(half, room)
            if gain > 0:
                focus.current_focus = min(max_focus, focus.current_focus + gain)
                focus.save()
                recovered_count += 1
        logger.log_info(f"FocusRecovery: Restored Focus for {recovered_count} characters.")
