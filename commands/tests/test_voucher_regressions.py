"""
Focused regression tests for voucher inventory integration.

Run with:
    evennia test commands.tests.test_voucher_regressions -v 2
"""

import unittest
from unittest.mock import patch

try:
    from evennia import create_object
    from evennia.utils.test_resources import EvenniaTest

    EVENNIA_AVAILABLE = True
except (ImportError, Exception):
    EVENNIA_AVAILABLE = False
    EvenniaTest = None


if EVENNIA_AVAILABLE and EvenniaTest:
    class TestVoucherRegressions(EvenniaTest):
        """Regression tests for claim/equip/attack/reload/cyberware install flows."""

        def setUp(self):
            super().setUp()
            self.char = self.char1
            self.char.key = "VoucherTester"
            self.char.save()

            from django.apps import apps
            from world.cyberpunk_sheets.models import CharacterSheet

            Inventory = apps.get_model("inventory", "Inventory")
            self.sheet, _ = CharacterSheet.objects.get_or_create(
                account=self.account1,
                character=self.char,
                defaults={"is_complete": True, "current_luck": 5},
            )
            self.char.db.character_sheet_id = self.sheet.id
            Inventory.objects.get_or_create(character=self.sheet)

            # Ensure clean equipment state for each test
            self.sheet.eqweapon = None
            self.sheet.eqarmor = None
            self.sheet.save()

        def _make_voucher(self, key="test voucher"):
            from typeclasses.vouchers import Voucher

            return create_object(Voucher, key=key, location=self.char)

        def test_claim_weapon_then_attack_consumes_ammo(self):
            """Claimed voucher weapon can be equipped and used by attack flow."""
            from world.voucher.utils import claim_voucher_item_to_inventory
            from world.inventory.models import Inventory
            from commands.attack_commands import execute_attack_roll

            voucher = self._make_voucher("weapon voucher")
            voucher.set_items(
                [
                    {
                        "name": "Test Pistol",
                        "description": "Voucher generated weapon",
                        "quantity": 1,
                        "item_type": "weapon",
                        "item_data": {
                            "name": "Test Pistol",
                            "description": "Voucher generated weapon",
                            "damage": "2d6",
                            "rof": "1",
                            "hands": 1,
                            "concealable": True,
                            "category": "handgun",
                            "weapon_type": "Heavy Pistol",
                            "quality": "standard",
                            "ammo_type": "Basic",
                            "current_ammo": 6,
                            "max_ammo": 12,
                            "clip": 12,
                            "weight": 1,
                            "value": 100,
                        },
                    }
                ]
            )

            ok, _msg = claim_voucher_item_to_inventory(self.char, voucher, 1, quantity=1)
            self.assertTrue(ok)

            inv, _ = Inventory.get_or_create_for_character(self.char)
            weapon = inv.weapons.filter(name__iexact="Test Pistol").first()
            self.assertIsNotNone(weapon)

            self.sheet.eqweapon = weapon
            self.sheet.save()

            before = weapon.current_ammo
            # One call for attack d10 (miss path); no damage rolls needed.
            with patch("commands.attack_commands.random.randint", return_value=5):
                execute_attack_roll(
                    attacker=self.char,
                    target=None,
                    dv=99,  # force miss while still firing a round
                    dv_name="high dv",
                    location=self.char.location,
                )
            weapon.refresh_from_db()
            self.assertEqual(weapon.current_ammo, before - 1)

        def test_attack_reload_consumes_voucher_ammo(self):
            """attack/reload loads from vouchers when inventory ammo is missing."""
            from commands.attack_commands import CmdAttack
            from world.inventory.models import Inventory, Weapon

            inv, _ = Inventory.get_or_create_for_character(self.char)
            weapon = Weapon.objects.create(
                name="Reload Pistol",
                description="Reload test weapon",
                damage="2d6",
                rof="1",
                hands=1,
                concealable=True,
                category="handgun",
                weapon_type="Heavy Pistol",
                quality="standard",
                ammo_type="Basic",
                current_ammo=0,
                max_ammo=10,
                clip=10,
                weight=1,
                value=100,
                range_dvs={},
            )
            inv.weapons.add(weapon)
            self.sheet.eqweapon = weapon
            self.sheet.save()

            voucher = self._make_voucher("ammo voucher")
            voucher.set_items(
                [
                    {
                        "name": "Basic Ammo",
                        "quantity": 15,
                        "item_type": "ammunition",
                        "item_data": {
                            "name": "Basic Ammo",
                            "ammo_type": "Basic",
                            "quantity": 15,
                            "cost": 10,
                            "weapon_type": "Handgun",
                            "damage_modifier": 0,
                            "armor_piercing": 0,
                            "description": "Standard ammunition",
                        },
                    }
                ]
            )

            cmd = CmdAttack()
            cmd.caller = self.char
            cmd._attack_reload(self.char, "Reload Pistol")

            weapon.refresh_from_db()
            self.assertEqual(weapon.current_ammo, 10)
            items = voucher.get_items()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].get("quantity"), 5)

        def test_claim_cyberware_then_install(self):
            """Claimed voucher cyberware is installable with cyberware/install flow."""
            from commands.cyberware_commands import CmdCyberware
            from world.voucher.utils import claim_voucher_item_to_inventory
            from world.inventory.models import Inventory

            voucher = self._make_voucher("cyber voucher")
            voucher.set_items(
                [
                    {
                        "name": "Test Reflex Booster",
                        "quantity": 1,
                        "item_type": "cyberware",
                        "item_data": {
                            "name": "Test Reflex Booster",
                            "description": "Voucher cyberware install test",
                            "cost": 500,
                            "humanity_loss": 2,
                            "type": "Neuralware",
                            "slots": 1,
                            "is_weapon": False,
                            "damage_dice": 0,
                            "damage_die_type": 6,
                            "rate_of_fire": 1,
                            "skill_chip_target": "",
                        },
                    }
                ]
            )

            ok, _msg = claim_voucher_item_to_inventory(self.char, voucher, 1, quantity=1)
            self.assertTrue(ok)

            inv, _ = Inventory.get_or_create_for_character(self.char)
            inst = inv.cyberware.filter(cyberware__name__iexact="Test Reflex Booster").first()
            self.assertIsNotNone(inst)
            self.assertFalse(inst.installed)

            cmd = CmdCyberware()
            cmd.caller = self.char
            cmd.install_cyberware(self.sheet, "Test Reflex Booster", None)

            inst.refresh_from_db()
            self.assertTrue(inst.installed)


else:
    class TestVoucherRegressions(unittest.TestCase):
        @unittest.skip("Run with: evennia test commands.tests.test_voucher_regressions")
        def test_placeholder(self):
            pass
