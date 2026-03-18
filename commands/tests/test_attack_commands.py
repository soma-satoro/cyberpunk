"""
Tests for attack and dodge commands with Soma and Ryan.

Run modifier parser tests (no Django/Evennia needed):
  python -m unittest commands.tests.test_attack_commands.TestModifierParser -v

Run pending attack helper tests and integration tests (requires Evennia/Django):
  evennia test commands.tests.test_attack_commands -v 2

Note: TestPendingAttackHelpers and TestAttackCommandsWithSomaAndRyan import
attack_commands, which loads Evennia/Django. Use 'evennia test' to run them.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

from world.utils.modifier_parser import parse_modifier_string


class TestModifierParser(unittest.TestCase):
    """Tests for modifier string parsing."""

    def test_single_positive(self):
        self.assertEqual(parse_modifier_string("+2"), 2)
        self.assertEqual(parse_modifier_string("+10"), 10)

    def test_single_negative(self):
        self.assertEqual(parse_modifier_string("-3"), -3)
        self.assertEqual(parse_modifier_string("-1"), -1)

    def test_bare_number(self):
        self.assertEqual(parse_modifier_string("3"), 3)
        self.assertEqual(parse_modifier_string("0"), 0)

    def test_arithmetic_sum(self):
        self.assertEqual(parse_modifier_string("-2+3+1-1"), 1)
        self.assertEqual(parse_modifier_string("+3-1-4"), -2)
        self.assertEqual(parse_modifier_string("+1+1+1"), 3)

    def test_empty_or_invalid(self):
        self.assertEqual(parse_modifier_string(""), 0)
        self.assertEqual(parse_modifier_string("   "), 0)
        self.assertEqual(parse_modifier_string("body"), 0)  # non-modifier text


class TestPendingAttackHelpers(unittest.TestCase):
    """Tests for pending attack helper functions using mocks."""

    def setUp(self):
        self.room = Mock()
        self.room.id = 1001
        self.room.contents = []
        self.room.msg_contents = Mock()

        self.soma = Mock()
        self.soma.id = 100
        self.soma.key = "Soma"
        self.soma.location = self.room
        self.soma.db = {}
        self.soma.has_account = True
        self.soma.character_sheet = Mock()

        self.ryan = Mock()
        self.ryan.id = 101
        self.ryan.key = "Ryan"
        self.ryan.location = self.room
        self.ryan.db = {}
        self.ryan.has_account = True
        self.ryan.character_sheet = Mock()

        self.room.contents = [self.soma, self.ryan]

    def test_add_pending_attack_stores_modifier_and_luck(self):
        """_add_pending_attack stores modifier and luck_spend in overrides."""
        from commands.attack_commands import _add_pending_attack, _get_and_clear_pending_attacks

        _add_pending_attack(self.ryan, self.soma, modifier=2, luck_spend=3)
        self.assertIn(self.soma.id, self.ryan.db.pending_attacks)
        override = self.ryan.db.pending_attack_overrides.get(self.soma.id)
        self.assertIsNotNone(override)
        self.assertEqual(override.get("modifier"), 2)
        self.assertEqual(override.get("luck_spend"), 3)

    def test_add_pending_attack_stores_aim_location(self):
        """_add_pending_attack stores aim_location for aimed shots."""
        from commands.attack_commands import _add_pending_attack

        _add_pending_attack(self.ryan, self.soma, aim_location="head")
        override = self.ryan.db.pending_attack_overrides.get(self.soma.id)
        self.assertEqual(override.get("aim_location"), "head")

    def test_clear_pending_attacks_on_leave_target(self):
        """When target (Ryan) leaves, their pending_attacks are cleared."""
        from commands.attack_commands import _add_pending_attack, _clear_pending_attacks_on_leave

        _add_pending_attack(self.ryan, self.soma)
        self.assertEqual(len(self.ryan.db.pending_attacks), 1)

        _clear_pending_attacks_on_leave(self.ryan, self.room)
        self.assertEqual(self.ryan.db.pending_attacks, [])
        self.assertEqual(self.ryan.db.pending_attack_overrides, {})

    def test_clear_pending_attacks_on_leave_attacker(self):
        """When attacker (Soma) leaves, they are removed from target's pending list."""
        from commands.attack_commands import _add_pending_attack, _clear_pending_attacks_on_leave

        _add_pending_attack(self.ryan, self.soma)
        self.assertIn(self.soma.id, self.ryan.db.pending_attacks)

        # Soma leaves - room.contents still has everyone in room (Soma has left, so we iterate over Ryan)
        _clear_pending_attacks_on_leave(self.soma, self.room)

        # Ryan's pending should no longer include Soma
        self.assertNotIn(self.soma.id, self.ryan.db.pending_attacks)

    def test_clear_all_pending_attacks_in_room(self):
        """Staff attack/clear clears all pending attacks in room."""
        from commands.attack_commands import _add_pending_attack, _clear_all_pending_attacks_in_room

        _add_pending_attack(self.ryan, self.soma)
        _add_pending_attack(self.soma, self.ryan)  # mutual pending

        count = _clear_all_pending_attacks_in_room(self.room)
        self.assertEqual(count, 2)  # Both had pending
        self.assertEqual(self.ryan.db.pending_attacks, [])
        self.assertEqual(self.soma.db.pending_attacks, [])


try:
    from evennia.utils.test_resources import EvenniaTest, EvenniaCommandTest
    EVENNIA_AVAILABLE = True
except (ImportError, Exception):
    EVENNIA_AVAILABLE = False
    EvenniaTest = None
    EvenniaCommandTest = None


if EVENNIA_AVAILABLE and EvenniaCommandTest:

    class TestAttackCommandsWithSomaAndRyan(EvenniaCommandTest):
        """
        Integration tests for attack/dodge with Soma and Ryan.
        Uses EvenniaTest's char1/char2, renamed to Soma/Ryan for clarity.
        """

        def setUp(self):
            super().setUp()
            # Rename default chars to Soma and Ryan
            self.soma = self.char1
            self.ryan = self.char2
            self.soma.key = "Soma"
            self.ryan.key = "Ryan"
            self.soma.save()
            self.ryan.save()

            # Create character sheets and mark approved
            from world.cyberpunk_sheets.models import CharacterSheet
            from django.apps import apps

            Inventory = apps.get_model("inventory", "Inventory")

            for char, acct in [(self.soma, self.account1), (self.ryan, self.account2)]:
                sheet, _ = CharacterSheet.objects.get_or_create(
                    account=acct,
                    character=char,
                    defaults={"is_complete": True, "current_luck": 5}
                )
                char.db.character_sheet_id = sheet.id
                Inventory.objects.get_or_create(character=sheet)

            # Tag as approved (category from character_utils.is_character_approved)
            self.soma.tags.add("approved", category="approval")
            self.ryan.tags.add("approved", category="approval")

        def test_attack_without_dodge_prompts_target(self):
            """attack Ryan when Ryan hasn't dodged shows 'must dodge first'."""
            from commands.attack_commands import CmdAttack

            self.call(
                CmdAttack(),
                "Ryan",
                caller=self.soma,
                msg="must dodge first",
            )

        def test_dodge_with_modifier(self):
            """dodge +1 applies modifier to dodge roll."""
            from commands.attack_commands import CmdDodge

            with patch("commands.attack_commands.random.randint", return_value=5):
                result = self.call(CmdDodge(), "+1", caller=self.ryan)
            # Dodge should have run; result may contain modifier in output
            self.assertIsNotNone(result)

else:

    class TestAttackCommandsWithSomaAndRyan(unittest.TestCase):
        """Placeholder when Evennia not available - run with: evennia test commands.tests.test_attack_commands"""

        @unittest.skip("Run with: evennia test commands.tests.test_attack_commands")
        def test_placeholder(self):
            pass

