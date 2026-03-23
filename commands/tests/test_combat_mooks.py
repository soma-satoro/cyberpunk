"""Unit tests for combat mook profile helpers."""

import unittest

try:
    from commands.combat_system import (
        ENCOUNTER_PRESETS,
        NAMED_ARCHETYPES,
        MOOK_PROFILES,
        _apply_level_scaling,
        _count_active_pcs,
        _lookup_profile,
        _normalize_team_name,
        _normalize_level_name,
        _normalize_preset_name,
        _pick_from_pool,
        _randomize_mook_from_profile,
        _resolve_profile_and_level,
        _sort_roster,
    )

    COMBAT_IMPORT_OK = True
except Exception:
    COMBAT_IMPORT_OK = False


if COMBAT_IMPORT_OK:
    class TestCombatMookProfiles(unittest.TestCase):
        def test_all_requested_profiles_exist(self):
            expected = {
                "melee",
                "ranged",
                "tank",
                "martial artist",
                "gang member",
                "bareknuckle boxer",
                "security guard",
                "corporate security",
                "ncpd beat cop",
                "combat medic",
                "paramedic",
                "doctor",
                "engineer",
                "grenadier",
                "sapper",
                "hacker",
                "punk",
                "getaway driver",
                "combat gunner",
                "militech soldier",
                "arasaka ninja",
            }
            self.assertTrue(expected.issubset(set(MOOK_PROFILES.keys())))

        def test_lookup_profile_supports_exact_and_alias(self):
            key, profile = _lookup_profile("corporate security")
            self.assertEqual(key, "corporate security")
            self.assertIsNotNone(profile)

            key2, profile2 = _lookup_profile("ncpd")
            self.assertEqual(key2, "ncpd beat cop")
            self.assertIsNotNone(profile2)
            self.assertIn("pyro", NAMED_ARCHETYPES)

        def test_randomized_mook_entry_has_required_fields(self):
            key, profile = _lookup_profile("grenadier")
            self.assertIsNotNone(profile)
            entry = _randomize_mook_from_profile(key, profile, 7)
            self.assertEqual(entry["kind"], "mook")
            self.assertIn("stats", entry)
            self.assertIn("skills", entry)
            self.assertIn("weapon_name", entry)
            self.assertIn("armor_sp", entry)
            self.assertGreater(entry["max_hp"], 0)
            self.assertEqual(entry["current_hp"], entry["max_hp"])
            self.assertEqual(entry["team"], "neutral")
            self.assertEqual(entry["level"], "mook")

        def test_team_name_normalization(self):
            self.assertEqual(_normalize_team_name("Red Team"), "red-team")
            self.assertEqual(_normalize_team_name(""), "neutral")
            self.assertEqual(_normalize_team_name("  BLUE_ops  "), "blue_ops")

        def test_level_name_normalization(self):
            self.assertEqual(_normalize_level_name("lt"), "lieutenant")
            self.assertEqual(_normalize_level_name("mini"), "mini-boss")
            self.assertEqual(_normalize_level_name("unknown"), "mook")

        def test_named_archetype_level_resolution(self):
            key, profile, level = _resolve_profile_and_level("pyro")
            self.assertEqual(key, "grenadier")
            self.assertIsNotNone(profile)
            self.assertEqual(level, "mini-boss")

        def test_preset_resolution(self):
            self.assertIn("street-ambush", ENCOUNTER_PRESETS)
            self.assertEqual(_normalize_preset_name("street-ambush"), "street-ambush")
            self.assertEqual(_normalize_preset_name("corp"), "corp-response")
            self.assertEqual(_normalize_preset_name("not-a-preset"), "")

        def test_count_active_pcs(self):
            scene = {
                "roster": [
                    {"kind": "pc", "active": True, "current_hp": 25},
                    {"kind": "pc", "active": False, "current_hp": 0},
                    {"kind": "npc", "active": True, "current_hp": 20},
                ]
            }
            self.assertEqual(_count_active_pcs(scene), 1)

        def test_pick_from_pool_returns_member(self):
            pool = ["punk", "gang member", "road ganger"]
            picked = _pick_from_pool(pool)
            self.assertIn(picked, pool)

        def test_level_scaling_increases_survivability(self):
            stats = {"reflexes": 6, "dexterity": 6, "body": 6, "willpower": 6, "move": 6}
            skills = {"handgun": 6, "evasion": 6}
            _, _, hp_mook, armor_mook, dmg_mook = _apply_level_scaling(
                dict(stats), dict(skills), 30, 7, "3d6", "mook"
            )
            _, _, hp_lt, armor_lt, dmg_lt = _apply_level_scaling(
                dict(stats), dict(skills), 30, 7, "3d6", "lieutenant"
            )
            _, _, hp_boss, armor_boss, dmg_boss = _apply_level_scaling(
                dict(stats), dict(skills), 30, 7, "3d6", "mini-boss"
            )
            self.assertGreater(hp_lt, hp_mook)
            self.assertGreater(hp_boss, hp_lt)
            self.assertGreater(armor_lt, armor_mook)
            self.assertGreater(armor_boss, armor_lt)
            self.assertNotEqual(dmg_mook, dmg_lt)
            self.assertNotEqual(dmg_lt, dmg_boss)

        def test_initiative_sorting_high_to_low(self):
            a = {"name": "A", "stats": {"reflexes": 5}, "initiative": 12}
            b = {"name": "B", "stats": {"reflexes": 7}, "initiative": 16}
            c = {"name": "C", "stats": {"reflexes": 6}, "initiative": 14}
            sorted_roster = _sort_roster([a, b, c])
            self.assertEqual([r["name"] for r in sorted_roster], ["B", "C", "A"])
else:
    class TestCombatMookProfiles(unittest.TestCase):
        @unittest.skip("Requires Evennia/Django settings (run with evennia test).")
        def test_placeholder(self):
            pass
