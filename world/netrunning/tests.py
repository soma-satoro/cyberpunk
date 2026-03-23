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
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    from commands.netrun_commands import CmdNet
    CMD_NET_AVAILABLE = True
except Exception:
    CmdNet = None
    CMD_NET_AVAILABLE = False

from world.netrunning.red_netrunning import (
    get_active_defense_template,
    generate_architecture,
    generate_demon_for_architecture,
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
            self.assertIn("children", floor)
            self.assertIn("depth", floor)
            self.assertIn("branch", floor)
            self.assertIn("is_bottom", floor)

    def test_generate_architecture_valid_types(self):
        """Floor types match CPR rules."""
        floors = generate_architecture("basic", floor_count=10)
        valid_types = {"password", "file", "control", "black_ice", "black_ice_group", "misc"}
        for floor in floors:
            self.assertIn(floor["type"], valid_types)

    def test_generate_architecture_has_single_bottom(self):
        floors = generate_architecture("advanced", floor_count=12)
        bottoms = [f for f in floors if f.get("is_bottom")]
        self.assertEqual(len(bottoms), 1)
        bottom = bottoms[0]
        self.assertGreaterEqual(int(bottom.get("depth", 0) or 0), 1)

    def test_generate_demon_for_architecture(self):
        self.assertIsNone(generate_demon_for_architecture("standard", 5))
        demon = generate_demon_for_architecture("standard", 10)
        self.assertIsNotNone(demon)
        self.assertIn("name", demon)
        self.assertIn("interface", demon)
        self.assertIn("net_actions", demon)

    def test_active_defense_template_lookup(self):
        turret = get_active_defense_template("Automated Turret")
        self.assertIsNotNone(turret)
        self.assertEqual(turret["name"], "Automated Turret")
        self.assertIn("counter_dv", turret)

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
    Tests for jack in/jack out: body object is created on jack in, character moves into it,
    and body is destroyed on jack out with character returned to room.

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
        self.caller.account = Mock()
        self.caller.account.username = "TestUser"
        self.caller.db = {"netrun_state": {}}
        self.caller.take_damage = Mock()
        self.caller.msg = Mock()
        self.caller.move_to = Mock()

    def test_body_created_on_jackin(self):
        """A body object is created when jacking in, named '{username}'s Body'."""
        created_objects = []

        def capture_create(*args, **kwargs):
            obj = Mock(id=9999, db={}, delete=Mock(), location=self.room)
            created_objects.append((args, kwargs, obj))
            return obj

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

        self.assertEqual(len(created_objects), 1, "One body object should be created when jacking in")
        _, kwargs, _ = created_objects[0]
        self.assertEqual(kwargs.get("key"), "TestUser's Body", "Body should be named '{username}'s Body'")

    def test_character_moves_into_body_on_jackin(self):
        """Character moves into the body object when jacking in."""
        body = Mock(id=9999, db={}, delete=Mock(), location=self.room)

        def capture_create(*args, **kwargs):
            return body

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

        self.caller.move_to.assert_called_once_with(body, quiet=True)

    def test_jackout_clears_state(self):
        """Jacking out clears netrun_state."""
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

    def test_jackout_destroys_body_and_returns_character(self):
        """Jacking out destroys the body object and moves character back to room."""
        body = Mock(id=9999, db={}, location=self.room)

        self.caller.db["netrun_state"] = {
            "active": True,
            "architecture_id": self.arch.id,
            "body_id": body.id,
            "entry_location_id": self.room.id,
            "floor": 1,
        }
        self.caller.location = body

        with patch("commands.netrun_commands.CmdNet._current_architecture", return_value=self.arch):
            with patch("commands.netrun_commands.evennia.search_object", return_value=[body]):
                cmd = CmdNet()
                cmd.caller = self.caller
                cmd.switches = ["jackout"]

                cmd.func()

        self.caller.move_to.assert_called_once_with(self.room, quiet=True)
        body.delete.assert_called_once()


@unittest.skipUnless(CMD_NET_AVAILABLE, "CmdNet import failed (project env)")
class TestNetrunningCommandFlows(unittest.TestCase):
    """
    Integration-style command flow tests with lightweight mocks.
    Focuses on multi-system state transitions in CmdNet.
    """

    def setUp(self):
        self.room = Mock()
        self.room.id = 5001
        self.room.key = "Ops Room"
        self.room.msg_contents = Mock()
        self.room.db = SimpleNamespace(tags=[])
        self.room.tags = Mock()
        self.room.tags.get.return_value = []

        floors = [
            {"floor": 1, "type": "file", "name": "Entry", "parent": None, "children": [2], "branch": "main", "depth": 1, "is_bottom": False},
            {"floor": 2, "type": "control", "name": "Control Node 2", "dv": 8, "defense": "Automated Turret", "parent": 1, "children": [3, 4], "branch": "main", "depth": 2, "is_bottom": False},
            {"floor": 3, "type": "password", "name": "Password", "dv": 8, "parent": 2, "children": [], "branch": "branch_1", "depth": 3, "is_bottom": True},
            {"floor": 4, "type": "file", "name": "Branch File", "parent": 2, "children": [], "branch": "branch_2", "depth": 3, "is_bottom": False},
        ]
        self.arch = Mock()
        self.arch.id = 6001
        self.arch.key = "BranchArch"
        self.arch.location = self.room
        self.arch.db = SimpleNamespace(floors=floors, difficulty="standard", demon={"name": "Imp", "interface": 3, "net_actions": 2})

        self.caller = Mock()
        self.caller.id = 7001
        self.caller.key = "Runner"
        self.caller.location = self.room
        self.caller.account = Mock()
        self.caller.account.username = "RunnerAcc"
        self.caller.take_damage = Mock()
        self.caller.msg = Mock()
        self.caller.move_to = Mock()
        self.caller.character_sheet = SimpleNamespace(interface=6)
        self.caller.db = SimpleNamespace(
            netrun_state={
                "active": True,
                "architecture_id": self.arch.id,
                "entry_location_id": self.room.id,
                "floor": 2,
                "active_programs": {},
                "cleared_passwords": [1],
                "controlled_nodes": [2],
                "disabled_defenses": [],
                "ice_state": {},
                "enemy_runners": {},
                "enemy_runner_counter": 0,
                "alarm_level": 0,
                "net_actions_used": 0,
                "action_penalty": 0,
                "action_penalty_next": 0,
                "installed_programs": {"vrizzbolt": "Vrizzbolt", "sword": "Sword"},
                "destroyed_programs": [],
                "slide_penalty": 0,
                "attack_program_used": False,
                "slide_used_turn": False,
            }
        )

    def _make_cmd(self):
        cmd = CmdNet()
        cmd.caller = self.caller
        return cmd

    def test_branch_move_selector_down_by_branch_name(self):
        cmd = self._make_cmd()
        cmd.args = "down=branch_1"
        with patch.object(cmd, "_current_architecture", return_value=self.arch):
            with patch.object(cmd, "_encounter_ice", return_value=None):
                with patch.object(cmd, "_show_current_floor", return_value=None):
                    with patch.object(cmd, "_consume_net_action", return_value=None):
                        cmd.cmd_move()
        state = self.caller.db.netrun_state
        self.assertEqual(state.get("floor"), 3, "Expected branch selector to move into branch_1 child floor")

    def test_backdoor_failure_raises_alarm_and_spawns_runner(self):
        # Move to password branch floor first.
        self.caller.db.netrun_state["floor"] = 3
        self.caller.db.netrun_state["cleared_passwords"] = []
        cmd = self._make_cmd()
        with patch.object(cmd, "_current_architecture", return_value=self.arch):
            with patch("commands.netrun_commands.interface_check", return_value=(5, 6, 1, {"first_roll": 1, "extra_rolls": []})):
                with patch.object(cmd, "_consume_net_action", return_value=None):
                    cmd.cmd_backdoor()
        state = self.caller.db.netrun_state
        self.assertGreaterEqual(int(state.get("alarm_level", 0) or 0), 1)
        # Force threshold and verify spawn.
        with patch.object(cmd, "_current_architecture", return_value=self.arch):
            cmd._register_alarm(state, reason="test spike", amount=3)
        runners = state.get("enemy_runners", {}).get("3", [])
        self.assertTrue(len(runners) >= 1, "Expected enemy runner spawn at alarm threshold")

    def test_zap_can_target_enemy_runner(self):
        cmd = self._make_cmd()
        self.caller.db.netrun_state["floor"] = 2
        self.caller.db.netrun_state["enemy_runners"] = {
            "2": [{"id": 1, "name": "Enemy Netrunner 1", "interface": 4, "brain_hp": 18, "active": True, "programs": []}]
        }
        cmd.args = "Enemy Netrunner 1"
        with patch.object(cmd, "_current_architecture", return_value=self.arch):
            with patch.object(cmd, "_ensure_floor_ice_state", return_value=[]):
                with patch("commands.netrun_commands.interface_check", return_value=(20, 6, 10, {"first_roll": 10, "extra_rolls": []})):
                    with patch.object(cmd, "_consume_net_action", return_value=None):
                        cmd.cmd_zap()
        runner = self.caller.db.netrun_state["enemy_runners"]["2"][0]
        self.assertLess(int(runner.get("brain_hp", 99)), 18, "Expected Zap to damage enemy netrunner target")

    def test_demon_turn_triggers_control_node_defense(self):
        cmd = self._make_cmd()
        state = self.caller.db.netrun_state
        with patch.object(cmd, "_spawn_defense_mook", return_value=None) as spawn_mock:
            cmd._run_demon_turn(state, self.arch)
        self.assertTrue(spawn_mock.called, "Expected demon to trigger linked control-node defense")
