"""
Tests for Cyberpunk RED netrunning system.

Run helper tests (no Evennia needed):
  python -m unittest world.netrunning.tests.TestRedNetrunningHelpers -v

Run all tests (includes CmdNet tests; requires CmdNet to import):
  python -m unittest world.netrunning.tests -v

With Evennia test runner (if project config allows):
  evennia test --settings server.conf.settings world.netrunning.tests
"""

import unittest
from unittest.mock import Mock, patch

try:
    from commands.netrun_commands import CmdNet
    CMD_NET_AVAILABLE = True
except Exception:
    CmdNet = None
    CMD_NET_AVAILABLE = False

from world.netrunning.red_netrunning import (
    generate_architecture,
    generate_paydata_entry,
    get_black_ice,
    get_interface_rank,
    get_program,
    interface_check,
    net_actions_for_rank,
    normalize_name,
    DIFFICULTY_DV,
)


class TestRedNetrunningHelpers(unittest.TestCase):
    """Tests for red_netrunning helper functions (no Evennia objects needed)."""

    def test_generate_architecture_produces_floors(self):
        """generate_architecture returns a list of floor dicts."""
        floors = generate_architecture("standard", floor_count=5)
        self.assertEqual(len(floors), 5)
        for i, floor in enumerate(floors):
            self.assertIn("floor", floor)
            self.assertIn("type", floor)
            self.assertIn("name", floor)
            self.assertEqual(floor["floor"], i + 1)

    def test_generate_architecture_valid_types(self):
        """Floor types match CPR rules."""
        floors = generate_architecture("basic", floor_count=10)
        valid_types = {"password", "file", "control", "black_ice", "black_ice_group", "misc"}
        for floor in floors:
            self.assertIn(floor["type"], valid_types)

    def test_get_program(self):
        """get_program finds programs by name."""
        sword = get_program("Sword")
        self.assertIsNotNone(sword)
        self.assertEqual(sword["name"], "Sword")
        self.assertIn("attacker", sword["class"].lower())

    def test_get_black_ice(self):
        """get_black_ice finds ICE by name."""
        wisp = get_black_ice("Wisp")
        self.assertIsNotNone(wisp)
        self.assertEqual(wisp["name"], "Wisp")

    def test_net_actions_for_rank(self):
        """NET actions scale with Interface rank."""
        self.assertEqual(net_actions_for_rank(0), 0)
        self.assertEqual(net_actions_for_rank(1), 2)
        self.assertEqual(net_actions_for_rank(4), 3)
        self.assertEqual(net_actions_for_rank(7), 4)
        self.assertEqual(net_actions_for_rank(10), 5)

    def test_generate_paydata_entry(self):
        """generate_paydata_entry produces valid paydata dict."""
        paydata = generate_paydata_entry("standard", 3)
        self.assertIn("label", paydata)
        self.assertIn("value", paydata)
        self.assertIn("dv", paydata)
        self.assertIn("claimed_by", paydata)


@unittest.skipUnless(CMD_NET_AVAILABLE, "CmdNet import failed (project env)")
class TestNetrunningJackInJackOut(unittest.TestCase):
    """
    Tests that the character stays in place and no body object is created/destroyed.

    Uses mocks to avoid full Evennia/Django setup dependencies.
    Requires CmdNet to be importable.
    """

    def setUp(self):
        """Create mock character and room."""
        self.room = Mock()
        self.room.id = 1001
        self.room.key = "Test Room"
        self.room.contents = []
        self.room.msg_contents = Mock()

        self.arch = Mock()
        self.arch.id = 2001
        self.arch.key = "TestArch"
        self.arch.location = self.room
        self.arch.db = {"floors": [{"floor": 1, "type": "file", "name": "File", "dv": 8}], "difficulty": "standard"}

        self.caller = Mock()
        self.caller.id = 3001
        self.caller.key = "NetRunner"
        self.caller.location = self.room
        self.caller.db = {"netrun_state": {}}
        self.caller.take_damage = Mock()
        self.caller.msg = Mock()

    def test_body_stays_in_room_on_jackin(self):
        """Character's location does NOT change when jacking in."""
        with patch("commands.netrun_commands.is_character_approved", return_value=True):
            with patch("commands.netrun_commands.check_builder_permission", return_value=True):
                with patch("commands.netrun_commands.get_interface_rank", return_value=4):
                    with patch("commands.netrun_commands.CmdNet._has_netrunning_gear", return_value=(True, [])):
                        with patch("commands.netrun_commands.CmdNet._find_architecture", return_value=self.arch):
                            with patch(
                                "commands.netrun_commands.CmdNet._get_floor",
                                return_value={"floor": 1, "type": "file", "name": "File", "dv": 8},
                            ):
                                cmd = CmdNet()
                                cmd.caller = self.caller
                                cmd.args = "TestArch"
                                cmd.switches = ["jackin"]

                                cmd.func()

        # Character never moved
        self.assertEqual(self.caller.location, self.room)

    def test_no_body_marker_created(self):
        """No NetrunBodyMarker or other body object is created when jacking in."""
        create_calls = []

        def capture_create(*args, **kwargs):
            create_calls.append((args, kwargs))
            return Mock(id=9999, db={}, delete=Mock())

        with patch("commands.netrun_commands.is_character_approved", return_value=True):
            with patch("commands.netrun_commands.check_builder_permission", return_value=True):
                with patch("commands.netrun_commands.get_interface_rank", return_value=4):
                    with patch("commands.netrun_commands.CmdNet._has_netrunning_gear", return_value=(True, [])):
                        with patch("commands.netrun_commands.CmdNet._find_architecture", return_value=self.arch):
                            with patch(
                                "commands.netrun_commands.CmdNet._get_floor",
                                return_value={"floor": 1, "type": "file", "name": "File", "dv": 8},
                            ):
                                with patch("commands.netrun_commands.evennia.create_object", side_effect=capture_create):
                                    cmd = CmdNet()
                                    cmd.caller = self.caller
                                    cmd.args = "TestArch"
                                    cmd.switches = ["jackin"]

                                    cmd.func()

        # No create_object was called during jackin (no body marker)
        self.assertEqual(len(create_calls), 0, "No objects should be created when jacking in")

    def test_jackout_clears_state(self):
        """Jacking out clears netrun_state; no body object exists to destroy."""
        self.caller.db["netrun_state"] = {
            "active": True,
            "architecture_id": self.arch.id,
            "floor": 1,
        }

        with patch("commands.netrun_commands.CmdNet._current_architecture", return_value=self.arch):
            cmd = CmdNet()
            cmd.caller = self.caller
            cmd.switches = ["jackout"]

            cmd.func()

        # State is cleared (no active netrun)
        state = self.caller.db.get("netrun_state") or {}
        self.assertFalse(state.get("active", False), "netrun_state should be cleared on jack out")
