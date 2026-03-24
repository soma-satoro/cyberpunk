# -*- coding: utf-8 -*-
"""
Voucher item serialization, validation, and inventory integration utilities.
Formats voucher items to match +inventory, +cyberware, and +equipdb displays.
"""
from world.utils.formatting import sheet_header, sheet_section, footer
from world.utils.ansi_utils import wrap_ansi
from evennia.utils.ansi import ANSIString

ITEM_TYPES = ("weapon", "armor", "gear", "cyberware", "ammunition", "vehicle")

# Fields staff can set per item type (for +voucher/setstat)
# Gear includes optional armor-like fields (sp, ev, locations) for armor items added as gear
ITEM_TYPE_FIELDS = {
    "weapon": ["name", "description", "weight", "value", "damage", "rof", "hands", "concealable",
               "category", "weapon_type", "quality", "ammo_type", "current_ammo", "max_ammo", "clip", "jammed", "range_dvs",
               "attachment_slots", "custom_item", "maker_upgrades", "upgrade_name", "upgrade_source", "repair_time_multiplier",
               "non_basic_ammo_compatibility", "foundational_tuning", "move_bonus_on_move_action", "requires_paired_rocket_runner",
               "body_requirement_reduction", "optimized_popup", "combined_underbarrel", "vorpal_coating", "superscanner"],
    "armor": ["name", "description", "weight", "value", "sp", "ev", "locations",
              "custom_item", "maker_upgrades", "upgrade_name", "upgrade_source", "repair_time_multiplier"],
    "gear": ["name", "description", "weight", "value", "category", "sp", "ev", "locations",
             "custom_item", "maker_upgrades", "upgrade_name", "upgrade_source", "repair_time_multiplier"],
    "cyberware": ["name", "description", "cost", "humanity_loss", "type", "slots", "is_weapon",
                  "damage_dice", "damage_die_type", "rate_of_fire", "skill_chip_target",
                  "custom_item", "maker_upgrades", "upgrade_name", "upgrade_source", "repair_time_multiplier",
                  "foundational_tuning", "move_bonus_on_move_action", "requires_paired_rocket_runner",
                  "body_requirement_reduction", "optimized_popup", "superscanner"],
    "ammunition": ["name", "ammo_type", "quantity", "cost", "weapon_type", "damage_modifier",
                   "armor_piercing", "description"],
    "vehicle": ["name", "description", "category", "sdp", "seats", "speed_combat", "speed_narrative", "value",
                "custom_item", "maker_upgrades", "upgrade_name", "upgrade_source", "repair_time_multiplier",
                "vehicle_armor_sp_bonus", "speed_combat_modifier", "self_driving_vehicle", "self_driving_skill_base",
                "flashbulb_beacon", "flashbulb_beacon_range", "flashbulb_beacon_resist_dv"],
}

INT_FIELDS = {
    "quantity", "weight", "value", "sp", "ev", "cost", "humanity_loss", "slots", "hands",
    "current_ammo", "max_ammo", "clip", "damage_dice", "damage_die_type", "rate_of_fire",
    "damage_modifier", "armor_piercing", "sdp", "seats", "speed_combat",
    "attachment_slots", "move_bonus_on_move_action", "body_requirement_reduction",
    "vehicle_armor_sp_bonus", "speed_combat_modifier", "self_driving_skill_base",
    "flashbulb_beacon_range", "flashbulb_beacon_resist_dv",
}
BOOL_FIELDS = {
    "concealable", "is_weapon", "jammed", "custom_item", "non_basic_ammo_compatibility",
    "foundational_tuning", "requires_paired_rocket_runner", "optimized_popup",
    "combined_underbarrel", "vorpal_coating", "superscanner",
}
STRING_FIELDS = {
    "name", "description", "category", "weapon_type", "quality", "ammo_type", "locations",
    "type", "speed_narrative", "skill_chip_target", "upgrade_name", "upgrade_source",
}


def _blank_item_data_for_type(item_type, name):
    """Return default/empty item_data dict for staff-created custom items."""
    if item_type == "weapon":
        return {"name": name, "description": "", "weight": 0, "value": 0, "damage": "", "rof": "",
                "hands": 1, "concealable": False, "category": "", "weapon_type": "", "quality": "standard",
                "ammo_type": "", "current_ammo": 0, "max_ammo": 0, "clip": 0, "jammed": False, "range_dvs": {}}
    if item_type == "armor":
        return {"name": name, "description": "", "weight": 0, "value": 0, "sp": 0, "ev": 0, "locations": ""}
    if item_type == "gear":
        return {"name": name, "description": "", "weight": 0, "value": 0, "category": "",
                "sp": 0, "ev": 0, "locations": ""}
    if item_type == "cyberware":
        return {"name": name, "description": "", "cost": 0, "humanity_loss": 0, "type": "", "slots": 1,
                "is_weapon": False, "damage_dice": 0, "damage_die_type": 6, "rate_of_fire": 1, "skill_chip_target": ""}
    if item_type == "ammunition":
        return {"name": name, "ammo_type": "", "quantity": 1, "cost": 0, "weapon_type": "",
                "damage_modifier": 0, "armor_piercing": 0, "description": ""}
    if item_type == "vehicle":
        return {"name": name, "description": "", "category": "", "sdp": 35, "seats": 2,
                "speed_combat": 20, "speed_narrative": "", "value": 0}
    return {"name": name}


def serialize_weapon(weapon):
    """Serialize a Weapon model to voucher item_data dict."""
    return {
        "name": weapon.name,
        "description": getattr(weapon, "description", "") or "",
        "weight": getattr(weapon, "weight", 0) or 0,
        "value": getattr(weapon, "value", 0) or 0,
        "damage": weapon.damage or "",
        "rof": weapon.rof or "",
        "hands": weapon.hands,
        "concealable": weapon.concealable,
        "category": weapon.category or "",
        "weapon_type": getattr(weapon, "weapon_type", "") or "",
        "quality": getattr(weapon, "quality", "standard") or "standard",
        "ammo_type": weapon.ammo_type or "",
        "current_ammo": weapon.current_ammo,
        "max_ammo": weapon.max_ammo,
        "clip": weapon.clip,
        "attachment_slots": getattr(weapon, "attachment_slots", 0) or 0,
        "jammed": getattr(weapon, "jammed", False),
        "range_dvs": getattr(weapon, "range_dvs", None) or {},
    }


def serialize_armor(armor):
    """Serialize an Armor model to voucher item_data dict."""
    return {
        "name": armor.name,
        "description": getattr(armor, "description", "") or "",
        "weight": getattr(armor, "weight", 0) or 0,
        "value": getattr(armor, "value", 0) or 0,
        "sp": armor.sp,
        "ev": armor.ev,
        "locations": armor.locations or "",
    }


def serialize_gear(gear):
    """Serialize a Gear model to voucher item_data dict."""
    return {
        "name": gear.name,
        "description": gear.description or "",
        "weight": gear.weight or 0,
        "value": gear.value or 0,
        "category": gear.category or "",
    }


def serialize_cyberware(cyberware):
    """Serialize a Cyberware model to voucher item_data dict."""
    return {
        "name": cyberware.name,
        "description": cyberware.description or "",
        "cost": cyberware.cost,
        "humanity_loss": cyberware.humanity_loss,
        "type": cyberware.type or "",
        "slots": cyberware.slots,
        "is_weapon": cyberware.is_weapon,
        "damage_dice": getattr(cyberware, "damage_dice", 0) or 0,
        "damage_die_type": getattr(cyberware, "damage_die_type", 6) or 6,
        "rate_of_fire": getattr(cyberware, "rate_of_fire", 1) or 1,
        "skill_chip_target": getattr(cyberware, "skill_chip_target", "") or "",
    }


def _coerce_field(field, value):
    """Coerce voucher field values to stable scalar types."""
    if value is None:
        if field in INT_FIELDS:
            return 0
        if field in BOOL_FIELDS:
            return False
        return ""
    if field in BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")
    if field in INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if field in STRING_FIELDS:
        return str(value)
    return value


def normalize_voucher_item(item):
    """
    Normalize a voucher item dict to the canonical voucher schema.
    Returns a new dict safe to persist.
    """
    item = dict(item or {})
    item_type = (item.get("item_type") or "").strip().lower()
    if item_type not in ITEM_TYPES:
        item_type = ""
    name = (item.get("name") or "").strip() or "item"
    desc = item.get("description", "")
    item_data = dict(item.get("item_data") or {})
    quantity = _coerce_field("quantity", item.get("quantity", 1))
    if quantity < 1:
        quantity = 1

    if item_type:
        defaults = _blank_item_data_for_type(item_type, name)
        allowed = ITEM_TYPE_FIELDS.get(item_type, [])
        normalized_data = {}
        for field in allowed:
            raw = item_data.get(field, defaults.get(field))
            normalized_data[field] = _coerce_field(field, raw)
        normalized_data["name"] = normalized_data.get("name") or name
        if "description" in defaults:
            normalized_data["description"] = normalized_data.get("description", desc or "")
        # Keep quantity mirrored in ammo payload for compatibility with old views/consumers
        if item_type == "ammunition":
            normalized_data["quantity"] = max(1, _coerce_field("quantity", normalized_data.get("quantity", quantity)))
            quantity = normalized_data["quantity"]
        if item_type == "weapon":
            # Keep clip/max/current coherent
            clip = max(0, normalized_data.get("clip", 0))
            max_ammo = max(clip, normalized_data.get("max_ammo", 0))
            current = max(0, normalized_data.get("current_ammo", 0))
            normalized_data["clip"] = clip
            normalized_data["max_ammo"] = max_ammo
            normalized_data["current_ammo"] = min(current, max_ammo) if max_ammo else current
            quality = (normalized_data.get("quality") or "standard").strip().lower()
            if quality not in ("poor", "standard", "excellent"):
                quality = "standard"
            normalized_data["quality"] = quality
        item_data = normalized_data
        name = item_data.get("name", name)
        desc = item_data.get("description", desc)

    return {
        "name": name,
        "description": desc or "",
        "quantity": quantity,
        "ic_location": (item.get("ic_location") or "")[:20],
        "cloneable": bool(item.get("cloneable", False)),
        "item_type": item_type,
        "item_data": item_data,
    }


def normalize_voucher_items(items):
    """Normalize a list of voucher item dicts."""
    return [normalize_voucher_item(it) for it in (items or []) if isinstance(it, dict)]


def serialize_ammunition(ammo):
    """Serialize an Ammunition model to voucher item_data dict."""
    return {
        "name": ammo.name,
        "ammo_type": ammo.ammo_type or "",
        "quantity": ammo.quantity,
        "cost": ammo.cost,
        "weapon_type": ammo.weapon_type or "",
        "damage_modifier": ammo.damage_modifier,
        "armor_piercing": ammo.armor_piercing,
        "description": ammo.description or "",
    }


def serialize_vehicle(vehicle):
    """Serialize a Vehicle model to voucher item_data dict."""
    return {
        "name": vehicle.name,
        "description": vehicle.description or "",
        "category": vehicle.category or "",
        "sdp": vehicle.sdp,
        "seats": vehicle.seats,
        "speed_combat": getattr(vehicle, "speed_combat", 0) or 0,
        "speed_narrative": vehicle.speed_narrative or "",
        "value": vehicle.value or 0,
    }


def format_voucher_item(item, item_num=None):
    """
    Format a voucher item for display, matching +cyberware, +inventory, +equipdb.
    Returns a string suitable for +voucher/info <voucher>/<item#>.
    """
    item_type = (item.get("item_type") or "").lower()
    data = item.get("item_data") or {}
    name = item.get("name") or data.get("name") or "?"
    qty = item.get("quantity", 1)
    ic_loc = item.get("ic_location") or ""
    cloneable = item.get("cloneable", False)

    W = 80
    title = name
    if item_num is not None:
        title = f"Item #{item_num}: {name}"
    out = sheet_header(title, width=W)
    out += sheet_section("Details", width=W)

    if item_type == "weapon":
        out += f"|c{name}|n\n"
        out += f"  |gDamage:|n {data.get('damage', 'N/A'):<10} |gROF:|n {data.get('rof', 'N/A'):<5} |gHands:|n {data.get('hands', 'N/A')}\n"
        concealable = "Yes" if data.get("concealable") else "No"
        out += (
            f"  |gConcealable:|n {concealable:<5} |gQuality:|n {(data.get('quality', 'standard') or 'standard'):<10}"
            f" |gSlots:|n {data.get('attachment_slots', 0):<3} |gWeight:|n {data.get('weight', 0):<5}"
            f" |gValue:|n |y{data.get('value', 0):>4} eb|n\n"
        )
        if data.get("current_ammo") is not None and data.get("max_ammo"):
            out += f"  |gAmmo:|n {data.get('current_ammo')}/{data.get('max_ammo')} |gCategory:|n {data.get('category', 'N/A')}\n"
        if data.get("custom_item"):
            out += f"  |gCustom:|n Yes  |gUpgrade:|n {data.get('upgrade_name', 'Maker Upgrade')}\n"
        desc = data.get("description", "")
        if desc:
            out += sheet_section("Description", width=W)
            out += f"{desc}\n"

    elif item_type == "armor":
        out += f"|c{name}|n\n"
        out += f"  |gSP:|n {data.get('sp', 'N/A'):<5} |gEV:|n {data.get('ev', 'N/A'):<5} |gWeight:|n {data.get('weight', 0):<5} |gValue:|n |y{data.get('value', 0):>4} eb|n\n"
        out += f"  |gLocations:|n {data.get('locations', 'N/A')}\n"
        if data.get("custom_item"):
            out += f"  |gCustom:|n Yes  |gUpgrade:|n {data.get('upgrade_name', 'Maker Upgrade')}\n"
        desc = data.get("description", "")
        if desc:
            out += sheet_section("Description", width=W)
            out += f"{desc}\n"

    elif item_type == "gear":
        out += f"|c{name}|n\n"
        out += f"  |gCategory:|n {data.get('category', 'N/A'):<15} |gWeight:|n {data.get('weight', 0):<5} |gValue:|n |y{data.get('value', 0):>4} eb|n\n"
        desc = data.get("description", "")
        if desc:
            out += sheet_section("Description", width=W)
            wrapped = wrap_ansi(desc, 76, left_padding=2)
            out += f"  {wrapped}\n"

    elif item_type == "cyberware":
        out += f"|cType:|n {data.get('type', 'N/A')}\n"
        out += f"|cSlots:|n {data.get('slots', 'N/A')}\n"
        out += f"|cHumanity Loss:|n {data.get('humanity_loss', 'N/A')}\n"
        out += f"|cCost:|n {data.get('cost', 0)} eb\n"
        if data.get("custom_item"):
            out += f"|cCustom:|n Yes ({data.get('upgrade_name', 'Maker Upgrade')})\n"
        out += sheet_section("Description", width=W)
        out += f"{data.get('description', '')}\n"

    elif item_type == "ammunition":
        out += f"|c{name}|n\n"
        out += f"  |gType:|n {data.get('ammo_type', 'N/A'):<15} |gWeapon Type:|n {data.get('weapon_type', 'N/A')}\n"
        out += f"  |gQuantity:|n {data.get('quantity', 0):<5} |gDamage Mod:|n {data.get('damage_modifier', 0):<5} |gAP:|n {data.get('armor_piercing', 0):<5} |gCost:|n |y{data.get('cost', 0):>4} eb|n\n"
        desc = data.get("description", "")
        if desc:
            out += sheet_section("Description", width=W)
            out += f"{desc}\n"

    elif item_type == "vehicle":
        out += f"|c{name}|n\n"
        out += f"  |gCategory:|n {data.get('category', 'N/A'):<10} |gSeats:|n {data.get('seats', 'N/A'):<5} |gSpeed:|n {data.get('speed_narrative', 'N/A')}\n"
        out += f"  |gSDP:|n {data.get('sdp', 'N/A'):<5} |gValue:|n |y{data.get('value', 0):>6} eb|n\n"
        if data.get("custom_item"):
            out += f"  |gCustom:|n Yes  |gUpgrade:|n {data.get('upgrade_name', 'Maker Upgrade')}\n"
        desc = data.get("description", "")
        if desc:
            out += sheet_section("Description", width=W)
            out += f"{desc}\n"

    else:
        # Simple/legacy item
        out += f"  Quantity: {qty}\n"
        out += f"  IC Location: {ic_loc or '(none)'}\n"
        out += f"  Cloneable: {'Yes' if cloneable else 'No'}\n"
        desc = item.get("description") or data.get("description", "")
        if desc:
            out += sheet_section("Description", width=W)
            out += f"{desc}\n"

    out += footer(width=W, fillchar="-")
    return out


def find_inventory_item(character, name):
    """
    Search character's inventory for an item by name.
    Returns (item_type, obj, serializer, removal_obj) or (None, None, None, None).
    obj: the model to serialize (e.g. Weapon, Cyberware).
    removal_obj: the object to remove from inventory (same as obj except for cyberware,
        where it's the CyberwareInstance).
    """
    from world.utils.character_utils import get_character_sheet
    from world.inventory.models import Inventory

    sheet = get_character_sheet(character)
    if not sheet:
        return None, None, None, None

    try:
        inv, _ = Inventory.get_or_create_for_character(character)
    except (ValueError, AttributeError):
        return None, None, None, None

    name_lower = (name or "").strip().lower()
    if not name_lower:
        return None, None, None, None

    # Weapons - exact match first
    w = inv.weapons.filter(name__iexact=name_lower).first()
    if not w:
        w = inv.weapons.filter(name__icontains=name_lower).first()
    if w:
        return "weapon", w, serialize_weapon, w

    # Armor
    a = inv.armor.filter(name__iexact=name_lower).first()
    if not a:
        a = inv.armor.filter(name__icontains=name_lower).first()
    if a:
        return "armor", a, serialize_armor, a

    # Gear
    g = inv.gear.filter(name__iexact=name_lower).first()
    if not g:
        g = inv.gear.filter(name__icontains=name_lower).first()
    if g:
        return "gear", g, serialize_gear, g

    # Cyberware (uninstalled only) - return instance for removal
    for cw_instance in inv.cyberware.filter(installed=False).select_related("cyberware"):
        c = cw_instance.cyberware
        if c.name.lower() == name_lower or name_lower in c.name.lower():
            return "cyberware", c, serialize_cyberware, cw_instance

    # Ammunition
    ammo = inv.ammunition.filter(name__iexact=name_lower).first()
    if not ammo:
        ammo = inv.ammunition.filter(name__icontains=name_lower).first()
    if ammo:
        return "ammunition", ammo, serialize_ammunition, ammo

    # Vehicles
    v = inv.vehicles.filter(name__iexact=name_lower).first()
    if not v:
        v = inv.vehicles.filter(name__icontains=name_lower).first()
    if v:
        return "vehicle", v, serialize_vehicle, v

    return None, None, None, None


def remove_voucher_duplicates_from_inventory(character, voucher):
    """
    When a character receives a voucher, remove from their inventory any items
    that match the voucher's contents. Items in a voucher are the canonical
    storage; the character shouldn't have duplicates in both places.
    """
    from world.utils.character_utils import get_character_sheet
    from world.inventory.models import Inventory

    sheet = get_character_sheet(character)
    if not sheet:
        return

    try:
        inv, _ = Inventory.get_or_create_for_character(character)
    except (ValueError, AttributeError):
        return

    items = voucher.get_items() if hasattr(voucher, 'get_items') else []
    removed = []

    for it in items:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        name_lower = name.lower()
        item_type = (it.get("item_type") or "").lower()

        if item_type == "weapon":
            for w in list(inv.weapons.filter(name__iexact=name_lower)):
                inv.weapons.remove(w)
                removed.append(name)
        elif item_type == "armor":
            for a in list(inv.armor.filter(name__iexact=name_lower)):
                inv.armor.remove(a)
                removed.append(name)
        elif item_type == "gear":
            for g in list(inv.gear.filter(name__iexact=name_lower)):
                inv.remove_gear(g)
                removed.append(name)
        elif item_type == "cyberware":
            for cw in list(inv.cyberware.filter(installed=False, cyberware__name__iexact=name_lower)):
                inv.cyberware.remove(cw)
                cw.delete()
                removed.append(name)
        elif item_type == "ammunition":
            for ammo in list(inv.ammunition.filter(name__iexact=name_lower)):
                inv.ammunition.remove(ammo)
                removed.append(name)
        elif item_type == "vehicle":
            for v in list(inv.vehicles.filter(name__iexact=name_lower)):
                inv.vehicles.remove(v)
                removed.append(name)
        # Simple/legacy items have no inventory equivalent; skip

    if removed:
        character.msg(
            f"Removed from your inventory (now in voucher): {', '.join(set(removed))}"
        )


def _get_inventory_for_character(character):
    """Return (sheet, inventory) or (None, None)."""
    from world.utils.character_utils import get_character_sheet
    from world.inventory.models import Inventory

    sheet = get_character_sheet(character)
    if not sheet:
        return None, None
    try:
        inventory, _ = Inventory.get_or_create_for_character(character)
    except (ValueError, AttributeError):
        return None, None
    return sheet, inventory


def _withdraw_one_typed_item(character, voucher_item):
    """
    Create one concrete inventory item from a voucher entry.
    Returns (ok: bool, message: str).
    """
    from world.inventory.models import Weapon, Armor, Gear, Ammunition, Vehicle, CyberwareInstance
    from world.cyberware.models import Cyberware

    voucher_item = normalize_voucher_item(voucher_item)
    item_type = (voucher_item.get("item_type") or "").lower()
    data = voucher_item.get("item_data") or {}
    name = voucher_item.get("name", "item")

    if not item_type:
        return False, "That item is not typed and cannot be claimed into inventory."

    sheet, inv = _get_inventory_for_character(character)
    if not sheet or not inv:
        return False, "You do not have a valid character inventory."

    if item_type == "weapon":
        weapon = Weapon.objects.create(
            name=data.get("name") or name,
            description=data.get("description", ""),
            weight=data.get("weight", 0),
            value=data.get("value", 0),
            damage=data.get("damage", ""),
            rof=data.get("rof", ""),
            hands=max(1, data.get("hands", 1)),
            concealable=bool(data.get("concealable", False)),
            category=(data.get("category") or "handgun"),
            weapon_type=data.get("weapon_type", "") or "",
            quality=(data.get("quality") or "standard"),
            ammo_type=(data.get("ammo_type") or "Basic"),
            current_ammo=max(0, data.get("current_ammo", 0)),
            max_ammo=max(0, data.get("max_ammo", 0)),
            clip=max(0, data.get("clip", 0)),
            attachment_slots=max(0, data.get("attachment_slots", 0)),
            range_dvs=data.get("range_dvs") or {},
            jammed=bool(data.get("jammed", False)),
        )
        inv.weapons.add(weapon)
        return True, f"Claimed weapon: {weapon.name}."

    if item_type == "armor":
        armor = Armor.objects.create(
            name=data.get("name") or name,
            description=data.get("description", ""),
            weight=data.get("weight", 0),
            value=data.get("value", 0),
            sp=data.get("sp", 0),
            ev=data.get("ev", 0),
            locations=data.get("locations", ""),
        )
        inv.armor.add(armor)
        return True, f"Claimed armor: {armor.name}."

    if item_type == "gear":
        gear = Gear.objects.create(
            name=data.get("name") or name,
            description=data.get("description", ""),
            weight=data.get("weight", 0),
            value=data.get("value", 0),
            category=data.get("category", "") or "Misc",
        )
        inv.add_gear(gear)
        return True, f"Claimed gear: {gear.name}."

    if item_type == "ammunition":
        ammo_name = data.get("name") or name
        ammo_type = data.get("ammo_type") or "Basic"
        weapon_type = data.get("weapon_type") or "Generic"
        ammo = inv.ammunition.filter(
            name__iexact=ammo_name,
            ammo_type=ammo_type,
            weapon_type=weapon_type,
            damage_modifier=data.get("damage_modifier", 0),
            armor_piercing=data.get("armor_piercing", 0),
        ).first()
        if ammo:
            ammo.quantity += 1
            ammo.save()
        else:
            ammo = Ammunition.objects.create(
                name=ammo_name,
                ammo_type=ammo_type,
                quantity=1,
                cost=data.get("cost", 0),
                weapon_type=weapon_type,
                damage_modifier=data.get("damage_modifier", 0),
                armor_piercing=data.get("armor_piercing", 0),
                description=data.get("description", "") or "Standard ammunition",
            )
            inv.ammunition.add(ammo)
        return True, f"Claimed ammunition: {ammo.name} ({ammo.ammo_type})."

    if item_type == "vehicle":
        vehicle = Vehicle.objects.create(
            name=data.get("name") or name,
            description=data.get("description", ""),
            category=(data.get("category") or "land"),
            sdp=max(0, data.get("sdp", 35)),
            seats=max(1, data.get("seats", 1)),
            speed_combat=max(0, data.get("speed_combat", 0)),
            speed_narrative=data.get("speed_narrative", ""),
            value=data.get("value", 0),
        )
        inv.vehicles.add(vehicle)
        return True, f"Claimed vehicle: {vehicle.name}."

    if item_type == "cyberware":
        cyberware_name = data.get("name") or name
        cyberware, _ = Cyberware.objects.get_or_create(
            name=cyberware_name,
            defaults={
                "description": data.get("description", "") or "",
                "cost": data.get("cost", 0),
                "humanity_loss": data.get("humanity_loss", 0),
                "type": data.get("type", "") or "Neuralware",
                "slots": max(1, data.get("slots", 1)),
                "is_weapon": bool(data.get("is_weapon", False)),
                "damage_dice": max(0, data.get("damage_dice", 0)),
                "damage_die_type": max(1, data.get("damage_die_type", 6)),
                "rate_of_fire": max(1, data.get("rate_of_fire", 1)),
                "skill_chip_target": data.get("skill_chip_target", "") or "",
            },
        )
        char_obj_id = getattr(character, "id", None) or getattr(character, "pk", None)
        instance = CyberwareInstance.objects.create(
            cyberware=cyberware,
            character_sheet=sheet,
            character_object_id=char_obj_id,
            installed=False,
            active=False,
        )
        inv.cyberware.add(instance)
        return True, f"Claimed cyberware: {cyberware.name} (uninstalled)."

    return False, f"Unsupported voucher item type: {item_type}."


def claim_voucher_item_to_inventory(character, voucher, item_number, quantity=1):
    """
    Claim voucher item(s) into character inventory as concrete models.
    Returns (ok: bool, message: str).
    """
    if not voucher or not hasattr(voucher, "get_item_by_num"):
        return False, "Invalid voucher."
    item, idx = voucher.get_item_by_num(item_number)
    if not item:
        return False, f"No such item #{item_number}."

    item = normalize_voucher_item(item)
    item_type = (item.get("item_type") or "").lower()
    if not item_type:
        return False, "That item is not typed and cannot be claimed into inventory."

    have = max(1, int(item.get("quantity", 1)))
    take = max(1, int(quantity or 1))
    take = min(take, have)

    claimed = 0
    last_msg = ""
    for _ in range(take):
        ok, msg = _withdraw_one_typed_item(character, item)
        if not ok:
            if claimed == 0:
                return False, msg
            break
        claimed += 1
        last_msg = msg

    if claimed == 0:
        return False, "Could not claim that voucher item."

    items = voucher.get_items()
    if claimed >= have:
        items.pop(idx - 1)
    else:
        updated = dict(item)
        updated["quantity"] = have - claimed
        if item_type == "ammunition":
            data = dict(updated.get("item_data") or {})
            data["quantity"] = updated["quantity"]
            updated["item_data"] = data
        items[idx - 1] = updated
    voucher.set_items(normalize_voucher_items(items))

    base = item.get("name", "?")
    if claimed == 1:
        return True, last_msg or f"Claimed {base}."
    return True, f"Claimed {claimed} x {base} into your inventory."


def consume_ammo_from_vouchers(character, ammo_type, amount):
    """
    Consume matching ammunition directly from carried vouchers.
    Returns integer rounds consumed.
    """
    if not character or amount <= 0:
        return 0
    ammo_type = (ammo_type or "Basic").strip().lower()
    remaining = amount
    consumed = 0

    for obj in list(getattr(character, "contents", []) or []):
        if remaining <= 0:
            break
        if not obj.is_typeclass("typeclasses.vouchers.Voucher"):
            continue
        if not hasattr(obj, "get_items"):
            continue
        changed = False
        items = normalize_voucher_items(obj.get_items())
        i = 0
        while i < len(items):
            if remaining <= 0:
                break
            it = items[i]
            if (it.get("item_type") or "").lower() != "ammunition":
                i += 1
                continue
            data = it.get("item_data") or {}
            it_ammo_type = (data.get("ammo_type") or "").strip().lower()
            if it_ammo_type != ammo_type:
                i += 1
                continue
            qty = max(1, int(it.get("quantity", 1)))
            take = min(qty, remaining)
            remaining -= take
            consumed += take
            changed = True
            if take >= qty:
                items.pop(i)
            else:
                it["quantity"] = qty - take
                data = dict(data)
                data["quantity"] = it["quantity"]
                it["item_data"] = data
                items[i] = it
                i += 1
        if changed:
            obj.set_items(normalize_voucher_items(items))
            if hasattr(obj, "is_empty") and obj.is_empty():
                obj.delete()
    return consumed
