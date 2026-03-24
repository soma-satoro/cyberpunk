# -*- coding: utf-8 -*-
"""
Maker Upgrade Expertise rules and upgrade application helpers.

This module defines:
- Core Upgrade Expertise options (CP:R p.148)
- Selected Invented Tech Upgrades with Cost #2 presets
- Validation and mutation helpers for turning existing inventory items into custom upgraded items
"""

from copy import deepcopy


MAKER_REPAIR_HALF_TAG = "[maker_repair_x0.5]"


# Cost #2 bands (Invented Tech Upgrade Thermometer)
INVENTED_TUP_COSTS = {
    "mild": 100,
    "medium": 500,
    "hot": 1000,
    "extra_hot": 5000,
    "diablo": 5000,  # 5000+ in source material; 5000 is minimum baseline here.
}


UPGRADE_DEFINITIONS = {
    # --- Core Upgrade Expertise ---
    "reduce_cyberware_hl": {
        "name": "Reduce Cyberware Humanity Loss",
        "source": "core",
        "eligible_types": ("cyberware",),
        "description": "Lower Humanity Loss of non-borgware cyberware by 1d6 (modeled as -3).",
    },
    "add_existing_slot": {
        "name": "Add Existing Slot Type",
        "source": "core",
        "eligible_types": ("weapon", "cyberware"),
        "description": "Increase an existing slot type by +1 (attachments/options/program/hardware style slots).",
    },
    "simplify_repairs": {
        "name": "Simplify Repairs",
        "source": "core",
        "eligible_types": ("weapon", "armor", "gear", "cyberware"),
        "description": "Halves future full-repair time on the item.",
    },
    "concealable_one_handed_weapon": {
        "name": "Concealable One-Handed Weapon",
        "source": "core",
        "eligible_types": ("weapon",),
        "description": "Grant a typically non-concealable one-handed weapon concealability.",
    },
    "average_to_excellent_weapon": {
        "name": "Average to Excellent Weapon",
        "source": "core",
        "eligible_types": ("weapon",),
        "description": "Upgrade an Average/Standard quality weapon to Excellent quality.",
    },
    "exotic_attachment_slot": {
        "name": "Exotic Weapon Attachment Slot",
        "source": "core",
        "eligible_types": ("weapon",),
        "description": "Grant an attachment slot to an Exotic weapon.",
    },
    "exotic_non_basic_ammo": {
        "name": "Exotic Non-Basic Ammo Compatibility",
        "source": "core",
        "eligible_types": ("weapon",),
        "description": "Allow an Exotic weapon to fire one non-Basic ammo variety of its ammo type.",
    },
    "increase_sp": {
        "name": "Increase SP",
        "source": "core",
        "eligible_types": ("armor",),
        "description": "Increase item's SP by +1 (must already have SP).",
    },
    # --- Invented Upgrade examples ---
    "foundational_tuning": {
        "name": "Foundational Tuning",
        "source": "invented",
        "cost2": 1000,
        "eligible_types": ("cyberware",),
        "description": "Options installed into this cyberware reduce Humanity Depression by 1.",
    },
    "rocket_runner": {
        "name": "Rocket Runner",
        "source": "invented",
        "cost2": 500,
        "eligible_types": ("cyberware",),
        "description": "Skate Foot movement tech; grants +1 MOVE for move actions when paired.",
    },
    "counterweight_system": {
        "name": "Counterweight System",
        "source": "invented",
        "cost2": 500,
        "eligible_types": ("weapon",),
        "description": "Lowers BODY requirement to use weapon/functions by 3.",
    },
    "optimized_popup": {
        "name": "Optimized Popup",
        "source": "invented",
        "cost2": 1000,
        "eligible_types": ("cyberware",),
        "description": "Cyberarm popup optimization; popup can avoid option slot cost (with constraints).",
    },
    "combined_underbarrel": {
        "name": "Combined Underbarrel",
        "source": "invented",
        "cost2": 500,
        "eligible_types": ("weapon",),
        "description": "Combines two compatible underbarrel attachments into one slot profile.",
    },
    "vorpal_coating": {
        "name": "Vorpal Coating",
        "source": "invented",
        "cost2": 1000,
        "eligible_types": ("weapon",),
        "description": "On random Critical Injury, roll twice and keep favored result.",
    },
    "superscanner": {
        "name": "Superscanner",
        "source": "invented",
        "cost2": 500,
        "eligible_types": ("cyberware",),
        "description": "Enhanced scanner behavior (situational flexibility upgrade).",
    },
    "calibrated_medscanner": {
        "name": "Calibrated Medscanner",
        "source": "invented",
        "cost2": 500,
        "eligible_types": ("cyberware",),
        "description": "When guiding Speedheal, treat patient BODY as +3 for HP recovery.",
    },
    "netsuit_insulation": {
        "name": "Netsuit Insulation",
        "source": "invented",
        "cost2": 500,
        "eligible_types": ("armor", "gear"),
        "description": "Provides Insulated Wiring-like protection on suitable suit gear.",
    },
    "super_slide": {
        "name": "Super Slide",
        "source": "invented",
        "cost2": 1000,
        "eligible_types": ("gear",),
        "description": "Upgraded Speedy Gonzalvez/Worm program allows Slide twice per turn.",
    },
    "stun_bunny": {
        "name": "Stun Bunny",
        "source": "invented",
        "cost2": 1000,
        "eligible_types": ("weapon",),
        "description": "Firearm can also function as a Microwaver or Stun Gun mode.",
    },
    "flashbulb_beacon": {
        "name": "Flashbulb Beacon",
        "source": "invented",
        "cost2": 500,
        "eligible_types": ("vehicle",),
        "description": "Vehicle-mounted dazzler effect at tactical range.",
    },
    "metalgear_coating": {
        "name": "MetalGear Coating",
        "source": "invented",
        "cost2": 1000,
        "eligible_types": ("vehicle",),
        "description": "Vehicle armor upgrade: +3 SP-equivalent, -5 combat MOVE.",
    },
    "self_driving_vehicle": {
        "name": "Self-Driving Vehicle",
        "source": "invented",
        "cost2": 1000,
        "eligible_types": ("vehicle",),
        "description": "Vehicle gains onboard autonomous driving capability (Skill Base 10).",
    },
    "function_driver": {
        "name": "Function Driver",
        "source": "invented",
        "cost2": 500,
        "eligible_types": ("gear",),
        "description": "Cyberdeck gains one protected free 1-slot non-Black ICE program slot.",
    },
}


def list_upgrade_keys():
    return sorted(UPGRADE_DEFINITIONS.keys())


def get_upgrade_definition(key_or_name):
    """Resolve an upgrade by key or fuzzy name. Returns dict with 'key' or None."""
    query = (key_or_name or "").strip().lower()
    if not query:
        return None
    if query in UPGRADE_DEFINITIONS:
        d = dict(UPGRADE_DEFINITIONS[query])
        d["key"] = query
        return d
    for key, data in UPGRADE_DEFINITIONS.items():
        nm = (data.get("name") or "").strip().lower()
        if nm == query:
            d = dict(data)
            d["key"] = key
            return d
    for key, data in UPGRADE_DEFINITIONS.items():
        nm = (data.get("name") or "").strip().lower()
        if query in key or query in nm:
            d = dict(data)
            d["key"] = key
            return d
    return None


def is_exotic_weapon(item_data):
    """Heuristic check for exotic weapon tagging in data."""
    blob = " ".join(
        str(item_data.get(k) or "")
        for k in ("name", "description", "weapon_type", "category")
    ).lower()
    return "exotic" in blob


def _append_marker_to_description(item_data, marker):
    desc = (item_data.get("description") or "").strip()
    if marker in desc:
        return
    if not desc:
        item_data["description"] = marker
    else:
        item_data["description"] = f"{desc} {marker}"


def extract_repair_time_multiplier_from_description(description):
    """Read repair multiplier marker from string description."""
    desc = (description or "").lower()
    if MAKER_REPAIR_HALF_TAG in desc:
        return 0.5
    return 1.0


def extract_repair_time_multiplier(item_data):
    """Read repair multiplier from item payload metadata/description."""
    val = item_data.get("repair_time_multiplier")
    try:
        if val:
            return max(0.1, float(val))
    except (TypeError, ValueError):
        pass
    return extract_repair_time_multiplier_from_description(item_data.get("description", ""))


def _has_existing_upgrade(item_data):
    upgrades = item_data.get("maker_upgrades") or []
    return bool(upgrades)


def _ensure_custom_name(item_data):
    name = (item_data.get("name") or "Item").strip()
    if name.lower().startswith("custom "):
        return
    item_data["name"] = f"Custom {name}"


def _append_upgrade(item_data, upgrade_key):
    upgrades = list(item_data.get("maker_upgrades") or [])
    if upgrade_key not in upgrades:
        upgrades.append(upgrade_key)
    item_data["maker_upgrades"] = upgrades
    item_data["custom_item"] = True


def _validate_upgrade_rules(item_type, item_data, upgrade):
    key = upgrade["key"]
    elig = tuple(upgrade.get("eligible_types") or ())
    if elig and item_type not in elig:
        return f"{upgrade['name']} cannot be applied to {item_type} items."
    if _has_existing_upgrade(item_data):
        return "That item already has a Maker upgrade. Each item can only have one Maker upgrade."

    if key == "reduce_cyberware_hl":
        hl = int(item_data.get("humanity_loss", 0) or 0)
        if hl < 7:
            return "Cyberware Humanity Loss must be at least 2d6-equivalent (7+) for this upgrade."
        item_name = (item_data.get("name") or "").lower()
        if "borgware" in item_name:
            return "This upgrade cannot be applied to borgware."
    elif key == "concealable_one_handed_weapon":
        if int(item_data.get("hands", 0) or 0) != 1:
            return "Only one-handed weapons can be made concealable by this upgrade."
        if bool(item_data.get("concealable")):
            return "That weapon is already concealable."
    elif key == "average_to_excellent_weapon":
        quality = (item_data.get("quality") or "standard").strip().lower()
        if quality not in ("standard", "average"):
            return "Only Average/Standard quality weapons can be upgraded this way."
    elif key in ("exotic_attachment_slot", "exotic_non_basic_ammo"):
        if not is_exotic_weapon(item_data):
            return "That upgrade requires an Exotic weapon."
    elif key == "increase_sp":
        if int(item_data.get("sp", 0) or 0) < 1:
            return "This item does not have SP to increase."
    elif key == "rocket_runner":
        if "skate foot" not in (item_data.get("name") or "").lower():
            return "Rocket Runner must be installed on Skate Foot cyberware."
    elif key == "optimized_popup":
        if "cyberarm" not in (item_data.get("name") or "").lower():
            return "Optimized Popup must be installed on a Cyberarm."
    elif key == "superscanner":
        if "techscanner" not in (item_data.get("name") or "").lower():
            return "Superscanner must be installed on Techscanner cyberware."
    elif key == "calibrated_medscanner":
        if "medscanner" not in (item_data.get("name") or "").lower():
            return "Calibrated Medscanner must be installed on a Medscanner."
    elif key == "netsuit_insulation":
        blob = " ".join(
            str(item_data.get(k) or "")
            for k in ("name", "description", "category")
        ).lower()
        if not any(token in blob for token in ("bodyweight suit", "netsuit", "armor")):
            return "Netsuit Insulation must be installed on a Bodyweight Suit or similar armor/suit item."
    elif key == "super_slide":
        blob = " ".join(
            str(item_data.get(k) or "")
            for k in ("name", "description")
        ).lower()
        if not any(token in blob for token in ("speedy gonzalvez", "worm")):
            return "Super Slide must be installed on a Speedy Gonzalvez or Worm program."
    elif key == "function_driver":
        blob = " ".join(
            str(item_data.get(k) or "")
            for k in ("name", "description", "category")
        ).lower()
        if "cyberdeck" not in blob:
            return "Function Driver must be installed on a cyberdeck."
    return None


def _apply_upgrade_mutation(item_type, item_data, upgrade):
    key = upgrade["key"]
    if key == "reduce_cyberware_hl":
        item_data["humanity_loss"] = max(0, int(item_data.get("humanity_loss", 0) or 0) - 3)
    elif key == "add_existing_slot":
        if item_type == "weapon":
            item_data["attachment_slots"] = int(item_data.get("attachment_slots", 0) or 0) + 1
        elif item_type == "cyberware":
            item_data["slots"] = max(1, int(item_data.get("slots", 1) or 1) + 1)
    elif key == "simplify_repairs":
        item_data["repair_time_multiplier"] = 0.5
        _append_marker_to_description(item_data, MAKER_REPAIR_HALF_TAG)
    elif key == "concealable_one_handed_weapon":
        item_data["concealable"] = True
    elif key == "average_to_excellent_weapon":
        item_data["quality"] = "excellent"
    elif key == "exotic_attachment_slot":
        item_data["attachment_slots"] = int(item_data.get("attachment_slots", 0) or 0) + 1
    elif key == "exotic_non_basic_ammo":
        item_data["non_basic_ammo_compatibility"] = True
    elif key == "increase_sp":
        item_data["sp"] = int(item_data.get("sp", 0) or 0) + 1
    elif key == "foundational_tuning":
        item_data["foundational_tuning"] = True
    elif key == "rocket_runner":
        item_data["move_bonus_on_move_action"] = 1
        item_data["requires_paired_rocket_runner"] = True
    elif key == "counterweight_system":
        item_data["body_requirement_reduction"] = 3
    elif key == "optimized_popup":
        item_data["optimized_popup"] = True
    elif key == "combined_underbarrel":
        item_data["combined_underbarrel"] = True
    elif key == "vorpal_coating":
        item_data["vorpal_coating"] = True
    elif key == "superscanner":
        item_data["superscanner"] = True
    elif key == "calibrated_medscanner":
        item_data["calibrated_medscanner"] = True
        item_data["speedheal_body_bonus"] = 3
    elif key == "netsuit_insulation":
        item_data["netsuit_insulation"] = True
        item_data["insulated_wiring_effect"] = True
    elif key == "super_slide":
        item_data["super_slide"] = True
        item_data["slide_actions_per_turn"] = 2
    elif key == "stun_bunny":
        item_data["stun_bunny"] = True
        item_data["alt_fire_modes"] = ["microwaver", "stun_gun"]
        item_data["alt_mode_battery_capacity"] = 8
    elif key == "flashbulb_beacon":
        item_data["flashbulb_beacon"] = True
        item_data["flashbulb_beacon_range"] = 50
        item_data["flashbulb_beacon_resist_dv"] = 15
    elif key == "metalgear_coating":
        item_data["metalgear_coating"] = True
        item_data["vehicle_armor_sp_bonus"] = 3
        item_data["speed_combat_modifier"] = -5
    elif key == "self_driving_vehicle":
        item_data["self_driving_vehicle"] = True
        item_data["self_driving_skill_base"] = 10
    elif key == "function_driver":
        item_data["function_driver"] = True
        item_data["free_program_slots"] = int(item_data.get("free_program_slots", 0) or 0) + 1


def apply_upgrade_to_item(item_type, base_item_data, upgrade):
    """
    Apply an upgrade definition to item data.
    Returns (upgraded_item_data, error_message_or_None).
    """
    data = deepcopy(base_item_data or {})
    err = _validate_upgrade_rules(item_type, data, upgrade)
    if err:
        return None, err

    _apply_upgrade_mutation(item_type, data, upgrade)
    _append_upgrade(data, upgrade["key"])
    _ensure_custom_name(data)
    data["upgrade_source"] = upgrade.get("source", "core")
    data["upgrade_name"] = upgrade.get("name", upgrade["key"])
    return data, None


def get_upgrade_cost2(upgrade):
    """Cost #2 for invented upgrades; core upgrades have Cost #2 = 0."""
    if not upgrade:
        return 0
    if upgrade.get("source") != "invented":
        return 0
    return int(upgrade.get("cost2", 0) or 0)


def get_item_value_for_upgrade(item_type, item_data):
    """Resolve base item value/cost for Maker upgrade Cost #1 calculations."""
    if item_type == "cyberware":
        return int(item_data.get("cost", 0) or 0)
    return int(item_data.get("value", 0) or 0)


def get_upgrade_listing_rows():
    """Rows for +make/upgrade list UI."""
    rows = []
    for key in list_upgrade_keys():
        d = UPGRADE_DEFINITIONS[key]
        source = d.get("source", "core")
        cost2 = get_upgrade_cost2(d)
        rows.append({
            "key": key,
            "name": d.get("name", key),
            "source": source,
            "cost2": cost2,
            "types": ", ".join(d.get("eligible_types") or ()),
            "description": d.get("description", ""),
        })
    return rows
