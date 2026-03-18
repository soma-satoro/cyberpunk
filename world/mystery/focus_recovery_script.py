"""
Focus recovery script - every 24 hours, characters recover INT + WILL Focus (Interface RED).

Per Interface RED: "Whenever you recover Hit Points from resting, you also recover
an amount of Focus equal to your INT + WILL." This script runs daily and applies
that recovery. Use +rest for optional DV15 Concentration check (+5 Focus on success).
"""

from evennia import DefaultScript
from evennia.utils import logger
from world.mystery.models import CharacterFocus


class FocusRecoveryScript(DefaultScript):
    """Recovers INT + WILL Focus for all characters every 24 hours (Interface RED)."""

    def at_script_creation(self):
        self.key = "FocusRecovery"
        self.desc = "Recovers INT + WILL Focus every 24 hours (Interface RED)"
        self.interval = 86400  # 24 hours in seconds
        self.persistent = True

    def at_repeat(self):
        recovered_count = 0
        for focus in CharacterFocus.objects.all():
            char = focus.character_object or (
                focus.character_sheet.character if focus.character_sheet else None
            )
            if not char and not focus.character_sheet:
                continue
            if focus.character_object:
                int_val = getattr(focus.character_object.db, "intelligence", 5) or 5
                will_val = getattr(focus.character_object.db, "willpower", 5) or 5
            elif focus.character_sheet:
                int_val = getattr(focus.character_sheet, "intelligence", 5) or 5
                will_val = getattr(focus.character_sheet, "willpower", 5) or 5
            else:
                continue
            recovery = int_val + will_val
            max_focus = focus.get_max_focus()
            room = max(0, max_focus - focus.current_focus)
            gain = min(recovery, room)
            if gain > 0:
                focus.current_focus = min(max_focus, focus.current_focus + gain)
                focus.save()
                recovered_count += 1
        logger.log_info(f"FocusRecovery: Restored Focus for {recovered_count} characters.")
