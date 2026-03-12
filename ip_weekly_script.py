"""
Weekly IP allotment script.

Awards configured IP to all characters with sheets each week.
"""
from evennia import DefaultScript
from evennia.utils import logger
from world.cyberpunk_sheets.models import CharacterSheet
from world.improvement_points import get_character_ip, add_ip_log_entry
from world.ip_config import get_weekly_allotment_enabled, get_weekly_allotment_amount
from world.ip_config import get_ip_config


class IPWeeklyScript(DefaultScript):
    """Script that runs weekly to award IP to all characters."""

    def at_script_creation(self):
        self.key = "IPWeeklyAllotment"
        self.desc = "Weekly IP allotment for characters"
        self.interval = 604800  # 1 week in seconds
        self.persistent = True

    def at_repeat(self):
        if not get_weekly_allotment_enabled():
            logger.log_info("IPWeeklyAllotment: Weekly allotment disabled, skipping.")
            return

        amount = get_weekly_allotment_amount()
        if amount <= 0:
            return

        count = 0
        for sheet in CharacterSheet.objects.filter(character__isnull=False):
            char = sheet.character
            if not char:
                continue
            if not hasattr(char, "attributes"):
                continue

            current, spent, _, _, _ = get_character_ip(char)
            new_current = current + amount
            char.attributes.add("improvement_points", new_current)
            add_ip_log_entry(char, amount, "Weekly Allotment", f"+{amount} IP")
            count += 1

        logger.log_info(f"IPWeeklyAllotment: Awarded {amount} IP to {count} characters.")
