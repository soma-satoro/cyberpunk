# -*- coding: utf-8 -*-
"""
Maker (Tech Role Ability) craft services.
Handles fabrication queue, roll resolution, and voucher delivery.
"""
import random
from datetime import datetime, timedelta

from django.utils import timezone
from evennia import create_object
from evennia.utils import logger

from world.maker.models import CraftOrder
from world.maker_constants import (
    value_to_price_category,
    get_maker_dv,
    get_maker_time_hours,
    get_materials_cost_fabrication,
    get_tech_skill_for_item,
)
from world.voucher.utils import (
    serialize_weapon,
    serialize_armor,
    serialize_gear,
    serialize_vehicle,
    serialize_ammunition,
    serialize_cyberware,
)
from world.cyberpunk_sheets.services import CharacterMoneyService

VOUCHER_TYPECLASS = "typeclasses.vouchers.Voucher"


def find_item_for_fabrication(name):
    """
    Find a fabricatable item by name in the equipment DB.
    Returns (item_type, obj, item_data_dict) or (None, None, None).
    """
    from world.inventory.models import Weapon, Armor, Gear, Vehicle, Ammunition
    from world.cyberware.models import Cyberware

    name_lower = (name or "").strip().lower()
    if not name_lower:
        return None, None, None

    # Weapon
    w = Weapon.objects.filter(name__iexact=name_lower).first()
    if not w:
        w = Weapon.objects.filter(name__icontains=name_lower).first()
    if w:
        return "weapon", w, serialize_weapon(w)

    # Armor
    a = Armor.objects.filter(name__iexact=name_lower).first()
    if not a:
        a = Armor.objects.filter(name__icontains=name_lower).first()
    if a:
        return "armor", a, serialize_armor(a)

    # Gear
    g = Gear.objects.filter(name__iexact=name_lower).first()
    if not g:
        g = Gear.objects.filter(name__icontains=name_lower).first()
    if g:
        return "gear", g, serialize_gear(g)

    # Vehicle
    v = Vehicle.objects.filter(name__iexact=name_lower).first()
    if not v:
        v = Vehicle.objects.filter(name__icontains=name_lower).first()
    if v:
        return "vehicle", v, serialize_vehicle(v)

    # Ammunition (fabricatable)
    ammo = Ammunition.objects.filter(name__iexact=name_lower).first()
    if not ammo:
        ammo = Ammunition.objects.filter(name__icontains=name_lower).first()
    if ammo:
        return "ammunition", ammo, serialize_ammunition(ammo)

    # Cyberware (Tech can fabricate)
    cw = Cyberware.objects.filter(name__iexact=name_lower).first()
    if not cw:
        cw = Cyberware.objects.filter(name__icontains=name_lower).first()
    if cw:
        return "cyberware", cw, serialize_cyberware(cw)

    return None, None, None


# Medical Tech (Pharmaceuticals) - Medtech-only, not street drugs. DV13, 200eb materials, 1hr, doses = Medical Tech.
PHARMA_ITEMS = {
    "antibiotic": {
        "name": "Antibiotic",
        "description": "When injected, a target who has started natural healing heals an extra 2 HP every day for a week. One use at a time.",
    },
    "rapidetox": {
        "name": "Rapidetox",
        "description": "When injected, a target affected by a drug, poison, or intoxicant is immediately purged of that substance's effects.",
    },
    "speedheal": {
        "name": "Speedheal",
        "description": "When injected, a target not Mortally Wounded heals HP equal to BODY + WILL. One use per day.",
    },
    "stim": {
        "name": "Stim",
        "description": "When injected, a target ignores all penalties from Seriously Wounded for an hour. One use per day.",
    },
    "surge": {
        "name": "Surge",
        "description": "When injected, a target can function unimpaired without sleep for 24 hours. One use per week.",
    },
}


def find_pharma_for_craft(name):
    """Find a pharmaceutical by name. Returns (data_dict, None) or (None, None). Not street drugs."""
    name_lower = (name or "").strip().lower()
    if not name_lower:
        return None, None
    for key, data in PHARMA_ITEMS.items():
        if key == name_lower or (data["name"].lower() == name_lower):
            return data, None
    for key, data in PHARMA_ITEMS.items():
        if name_lower in data["name"].lower():
            return data, None
    return None, None


def find_program_for_craft(name):
    """Find a program by name from deckoptions. Returns (data_dict, None) - data is dict, no DB obj."""
    from world.netrunning.deckoptions import programs
    name_lower = (name or "").strip().lower()
    for p in programs:
        if (p.get("name") or "").strip().lower() == name_lower:
            return p, None
    for p in programs:
        if name_lower in (p.get("name") or "").strip().lower():
            return p, None
    return None, None


def find_deckoption_for_craft(name):
    """Find a deck option (hardware) by name from deckoptions. Returns (data_dict, None)."""
    from world.netrunning.deckoptions import hardware
    name_lower = (name or "").strip().lower()
    for h in hardware:
        if (h.get("name") or "").strip().lower() == name_lower:
            return h, None
    for h in hardware:
        if name_lower in (h.get("name") or "").strip().lower():
            return h, None
    return None, None


def get_item_value(item_type, obj):
    """Get value (eb) for an item."""
    if item_type == "weapon":
        return getattr(obj, "value", 0) or 0
    if item_type == "armor":
        return getattr(obj, "value", 0) or 0
    if item_type == "gear":
        return getattr(obj, "value", 0) or 0
    if item_type == "vehicle":
        return getattr(obj, "value", 0) or 0
    if item_type == "ammunition":
        return getattr(obj, "cost", 0) or 0
    if item_type == "cyberware":
        return getattr(obj, "cost", 0) or 0
    return 0


def get_item_category(item_type, obj):
    """Get category for tech skill resolution."""
    if item_type == "gear":
        return getattr(obj, "category", "") or ""
    if item_type == "vehicle":
        return getattr(obj, "category", "land") or "land"
    return ""


def create_fabrication_order(character, item_name, recipient=None):
    """
    Create a fabrication craft order. Tech pays materials cost; order is queued.
    Returns (order, error_msg). If error_msg is set, order is None.
    """
    role = (getattr(character.db, "role", None) or "").strip()
    if role != "Tech":
        return None, "Only Tech characters can fabricate items."

    fabrication = getattr(character.db, "maker_fabrication", 0) or 0
    if fabrication < 1:
        return None, "You need at least 1 rank in Fabrication Expertise to fabricate items."

    item_type, obj, item_data = find_item_for_fabrication(item_name)
    if not obj:
        return None, f"No fabricatable item found named '{item_name}'."

    value = get_item_value(item_type, obj)
    category = get_item_category(item_type, obj)
    price_category = value_to_price_category(value)
    dv = get_maker_dv(price_category)
    time_hours = get_maker_time_hours(price_category, value)
    materials_cost = get_materials_cost_fabrication(value, price_category)
    tech_skill = get_tech_skill_for_item(item_type, category)

    # Check balance
    balance = CharacterMoneyService.get_balance(character)
    if balance < materials_cost:
        return None, f"You need {materials_cost} eb for materials (you have {balance} eb)."

    # Deduct materials cost
    if not CharacterMoneyService.spend_money(character, materials_cost):
        return None, "Failed to deduct materials cost."

    # Calculate completed_at
    now = timezone.now()
    completed_at = now + timedelta(hours=time_hours)

    order = CraftOrder.objects.create(
        crafter=character,
        craft_type=CraftOrder.CRAFT_TYPE_FABRICATION,
        status=CraftOrder.STATUS_IN_PROGRESS,
        item_type=item_type,
        item_name=obj.name,
        item_category=category,
        item_data=item_data,
        materials_cost=materials_cost,
        price_category=price_category,
        dv=dv,
        time_hours=time_hours,
        tech_skill=tech_skill,
        specialty_rank=fabrication,
        started_at=now,
        completed_at=completed_at,
        recipient=recipient or character,
    )
    return order, None


def create_pharma_order(character, item_name, recipient=None):
    """
    Create a pharmaceutical craft order. MedTech only.
    Per rulebook: DV13 Medical Tech Check, 200eb materials, 1 hour, doses = Medical Tech Skill.
    On failure: materials wasted (no refund).
    """
    from world.chargen_constants import get_medical_tech_skill

    role = (getattr(character.db, "role", None) or "").strip()
    if role != "Medtech":
        return None, "Only Medtech characters can craft pharmaceuticals."

    pharma = getattr(character.db, "medicine_pharma", 0) or 0
    if pharma < 1:
        return None, "You need at least 1 rank in Pharmaceuticals to craft pharmaceuticals."

    data, _ = find_pharma_for_craft(item_name)
    if not data:
        return None, f"No pharmaceutical found named '{item_name}'. (Street drugs cannot be synthesized.)"

    materials_cost = 200  # Fixed per rulebook
    dv = 13  # Fixed DV13 Medical Tech Check
    time_hours = 1

    item_data = {
        "name": data["name"],
        "description": data["description"],
        "weight": 0.5,
        "value": 0,  # Medical pharmaceuticals, not sold
        "category": "Pharmaceutical",
    }

    balance = CharacterMoneyService.get_balance(character)
    if balance < materials_cost:
        return None, f"You need {materials_cost} eb for materials (you have {balance} eb)."

    if not CharacterMoneyService.spend_money(character, materials_cost):
        return None, "Failed to deduct materials cost."

    now = timezone.now()
    completed_at = now + timedelta(hours=time_hours)

    order = CraftOrder.objects.create(
        crafter=character,
        craft_type=CraftOrder.CRAFT_TYPE_PHARMA,
        status=CraftOrder.STATUS_IN_PROGRESS,
        item_type="gear",
        item_name=data["name"],
        item_category="Pharmaceutical",
        item_data=item_data,
        materials_cost=materials_cost,
        price_category="Pharma",
        dv=dv,
        time_hours=time_hours,
        tech_skill="medical_tech",
        specialty_rank=0,
        started_at=now,
        completed_at=completed_at,
        recipient=recipient or character,
    )
    return order, None


def create_program_order(character, item_name, recipient=None):
    """Create a program craft order. Netrunner only. Uses Interface."""
    role = (getattr(character.db, "role", None) or "").strip()
    if role != "Netrunner":
        return None, "Only Netrunner characters can craft programs."

    interface = character.get_skill("interface") if hasattr(character, "get_skill") else 0
    if not interface:
        interface = (getattr(character.db, "skills", None) or {}).get("interface", 0)
    if interface < 1:
        return None, "You need at least 1 rank in Interface to craft programs."

    data = find_program_for_craft(item_name)
    if not data:
        return None, f"No program found named '{item_name}'."

    value = data.get("cost", 0) or 0
    price_category = value_to_price_category(value)
    dv = get_maker_dv(price_category)
    time_hours = get_maker_time_hours(price_category, value)
    materials_cost = get_materials_cost_fabrication(value, price_category)

    item_data = {
        "name": data.get("name", ""),
        "description": data.get("effect", ""),
        "weight": 0,
        "value": value,
        "category": "Program",
        "program_type": data.get("type", ""),
        "atk": data.get("atk", 0),
        "dfv": data.get("dfv", 0),
        "rez": data.get("rez", 0),
    }

    balance = CharacterMoneyService.get_balance(character)
    if balance < materials_cost:
        return None, f"You need {materials_cost} eb for materials (you have {balance} eb)."

    if not CharacterMoneyService.spend_money(character, materials_cost):
        return None, "Failed to deduct materials cost."

    now = timezone.now()
    completed_at = now + timedelta(hours=time_hours)

    order = CraftOrder.objects.create(
        crafter=character,
        craft_type=CraftOrder.CRAFT_TYPE_PROGRAM,
        status=CraftOrder.STATUS_IN_PROGRESS,
        item_type="gear",
        item_name=data.get("name", ""),
        item_category="Program",
        item_data=item_data,
        materials_cost=materials_cost,
        price_category=price_category,
        dv=dv,
        time_hours=time_hours,
        tech_skill="interface",
        specialty_rank=interface,
        started_at=now,
        completed_at=completed_at,
        recipient=recipient or character,
    )
    return order, None


def create_deckoption_order(character, item_name, recipient=None):
    """Create a deck option (hardware) craft order. Netrunner only. Uses Interface."""
    role = (getattr(character.db, "role", None) or "").strip()
    if role != "Netrunner":
        return None, "Only Netrunner characters can craft deck options."

    interface = character.get_skill("interface") if hasattr(character, "get_skill") else 0
    if not interface:
        interface = (getattr(character.db, "skills", None) or {}).get("interface", 0)
    if interface < 1:
        return None, "You need at least 1 rank in Interface to craft deck options."

    data = find_deckoption_for_craft(item_name)
    if not data:
        return None, f"No deck option found named '{item_name}'."

    value = data.get("cost", 0) or 0
    price_category = value_to_price_category(value)
    dv = get_maker_dv(price_category)
    time_hours = get_maker_time_hours(price_category, value)
    materials_cost = get_materials_cost_fabrication(value, price_category)

    item_data = {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "weight": 0,
        "value": value,
        "category": "Deck Option",
        "slots": data.get("slots", 0),
    }

    balance = CharacterMoneyService.get_balance(character)
    if balance < materials_cost:
        return None, f"You need {materials_cost} eb for materials (you have {balance} eb)."

    if not CharacterMoneyService.spend_money(character, materials_cost):
        return None, "Failed to deduct materials cost."

    now = timezone.now()
    completed_at = now + timedelta(hours=time_hours)

    order = CraftOrder.objects.create(
        crafter=character,
        craft_type=CraftOrder.CRAFT_TYPE_DECKOPTION,
        status=CraftOrder.STATUS_IN_PROGRESS,
        item_type="gear",
        item_name=data.get("name", ""),
        item_category="Deck Option",
        item_data=item_data,
        materials_cost=materials_cost,
        price_category=price_category,
        dv=dv,
        time_hours=time_hours,
        tech_skill="interface",
        specialty_rank=interface,
        started_at=now,
        completed_at=completed_at,
        recipient=recipient or character,
    )
    return order, None


def _roll_maker_check(character, tech_skill, specialty_rank):
    """
    Roll TECH + tech_skill + specialty_rank + 1d10.
    Returns (total, d10_roll).
    """
    from world.utils.character_utils import get_technique_value
    tech = get_technique_value(character) or 0
    skill = 0
    if tech_skill == "medical_tech":
        from world.chargen_constants import get_medical_tech_skill
        skill = get_medical_tech_skill(
            getattr(character.db, "medicine_pharma", 0),
            getattr(character.db, "medicine_cryo", 0),
        )
    elif hasattr(character, "get_skill"):
        skill = character.get_skill(tech_skill) or 0
    else:
        skills = getattr(character.db, "skills", None) or {}
        skill = skills.get(tech_skill.lower().replace(" ", "_"), 0)
    d10 = random.randint(1, 10)
    total = tech + skill + specialty_rank + d10
    return total, d10


def process_craft_order(order):
    """
    Process a completed craft order: roll, create voucher on success, refund on failure.
    """
    if order.status not in (CraftOrder.STATUS_IN_PROGRESS, CraftOrder.STATUS_QUEUED):
        return

    crafter = order.crafter
    if not crafter:
        order.status = CraftOrder.STATUS_CANCELLED
        order.save()
        return

    total, d10 = _roll_maker_check(crafter, order.tech_skill, order.specialty_rank)
    order.roll_result = total
    order.success = total >= order.dv
    order.status = CraftOrder.STATUS_COMPLETED if order.success else CraftOrder.STATUS_FAILED
    order.save()

    recipient = order.recipient or crafter
    recipient_obj = recipient  # May be ObjectDB

    if order.success:
        # Create voucher with the crafted item
        voucher = create_object(
            "typeclasses.vouchers.Voucher",
            key=f"Crafted: {order.item_name}",
            location=recipient_obj,
        )
        voucher_item = {
            "name": order.item_name,
            "description": order.item_data.get("description", ""),
            "quantity": 1,
            "ic_location": "",
            "cloneable": False,
            "item_type": order.item_type,
            "item_data": dict(order.item_data),
        }
        if order.item_type == "ammunition":
            voucher_item["quantity"] = order.item_data.get("quantity", 10)
        elif order.craft_type == CraftOrder.CRAFT_TYPE_PHARMA:
            # Doses = Medical Tech Skill at process time
            from world.chargen_constants import get_medical_tech_skill
            medtech = get_medical_tech_skill(
                getattr(crafter.db, "medicine_pharma", 0),
                getattr(crafter.db, "medicine_cryo", 0),
            )
            voucher_item["quantity"] = max(1, medtech)
            voucher_item["item_data"]["quantity"] = voucher_item["quantity"]
        voucher.set_items([voucher_item])
        order.voucher = voucher
        order.save()

        craft_label = dict(CraftOrder.CRAFT_TYPE_CHOICES).get(order.craft_type, "Craft")
        if order.craft_type == CraftOrder.CRAFT_TYPE_PHARMA:
            doses = voucher_item.get("quantity", 1)
            msg = (
                f"|g{craft_label} complete!|n You synthesized {order.item_name} ({doses} dose{'s' if doses != 1 else ''}). "
                f"Roll: TECH+Medical Tech+1d10 = {total} (d10={d10}) vs DV{order.dv}. Voucher created."
            )
        else:
            msg = (
                f"|g{craft_label} complete!|n You successfully crafted {order.item_name}. "
                f"Roll: TECH+{order.tech_skill}+{order.specialty_rank}+1d10 = {total} (d10={d10}) vs DV{order.dv}. "
                f"Voucher created."
            )
        crafter.msg(msg)
        if recipient_obj != crafter and hasattr(recipient_obj, "msg"):
            recipient_obj.msg(f"You received a voucher for {order.item_name} from {crafter.key}.")
    else:
        # Refund materials (except pharma: materials wasted on failure per rulebook)
        if order.craft_type != CraftOrder.CRAFT_TYPE_PHARMA:
            CharacterMoneyService.add_money(crafter, order.materials_cost)
        craft_label = dict(CraftOrder.CRAFT_TYPE_CHOICES).get(order.craft_type, "Craft")
        if order.craft_type == CraftOrder.CRAFT_TYPE_PHARMA:
            msg = (
                f"|r{craft_label} failed.|n You couldn't synthesize {order.item_name}. "
                f"Roll: TECH+Medical Tech+1d10 = {total} (d10={d10}) vs DV{order.dv}. "
                f"Materials ({order.materials_cost} eb) wasted."
            )
        else:
            msg = (
                f"|r{craft_label} failed.|n You couldn't complete {order.item_name}. "
                f"Roll: TECH+{order.tech_skill}+{order.specialty_rank}+1d10 = {total} (d10={d10}) vs DV{order.dv}. "
                f"Materials ({order.materials_cost} eb) refunded."
            )
        crafter.msg(msg)


def process_due_orders():
    """Process all craft orders whose completed_at has passed."""
    now = timezone.now()
    due = CraftOrder.objects.filter(
        status__in=(CraftOrder.STATUS_IN_PROGRESS, CraftOrder.STATUS_QUEUED),
        completed_at__lte=now,
    )
    for order in due:
        try:
            process_craft_order(order)
        except Exception as e:
            logger.log_err(f"Maker process_craft_order failed for #{order.id}: {e}")
