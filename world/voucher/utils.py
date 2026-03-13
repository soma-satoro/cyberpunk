# -*- coding: utf-8 -*-
"""
Voucher item serialization and display utilities.
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
               "category", "ammo_type", "current_ammo", "max_ammo", "clip"],
    "armor": ["name", "description", "weight", "value", "sp", "ev", "locations"],
    "gear": ["name", "description", "weight", "value", "category", "sp", "ev", "locations"],
    "cyberware": ["name", "description", "cost", "humanity_loss", "type", "slots", "is_weapon",
                  "damage_dice", "damage_die_type", "rate_of_fire"],
    "ammunition": ["name", "ammo_type", "quantity", "cost", "weapon_type", "damage_modifier",
                   "armor_piercing", "description"],
    "vehicle": ["name", "description", "category", "sdp", "seats", "speed_combat", "speed_narrative", "value"],
}


def _blank_item_data_for_type(item_type, name):
    """Return default/empty item_data dict for staff-created custom items."""
    if item_type == "weapon":
        return {"name": name, "description": "", "weight": 0, "value": 0, "damage": "", "rof": "",
                "hands": 1, "concealable": False, "category": "", "ammo_type": "", "current_ammo": 0,
                "max_ammo": 0, "clip": 0, "range_dvs": {}}
    if item_type == "armor":
        return {"name": name, "description": "", "weight": 0, "value": 0, "sp": 0, "ev": 0, "locations": ""}
    if item_type == "gear":
        return {"name": name, "description": "", "weight": 0, "value": 0, "category": "",
                "sp": 0, "ev": 0, "locations": ""}
    if item_type == "cyberware":
        return {"name": name, "description": "", "cost": 0, "humanity_loss": 0, "type": "", "slots": 1,
                "is_weapon": False, "damage_dice": 0, "damage_die_type": 6, "rate_of_fire": 1}
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
        "ammo_type": weapon.ammo_type or "",
        "current_ammo": weapon.current_ammo,
        "max_ammo": weapon.max_ammo,
        "clip": weapon.clip,
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
    }


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
        out += f"  |gConcealable:|n {concealable:<5} |gWeight:|n {data.get('weight', 0):<5} |gValue:|n |y{data.get('value', 0):>4} eb|n\n"
        if data.get("current_ammo") is not None and data.get("max_ammo"):
            out += f"  |gAmmo:|n {data.get('current_ammo')}/{data.get('max_ammo')} |gCategory:|n {data.get('category', 'N/A')}\n"
        desc = data.get("description", "")
        if desc:
            out += sheet_section("Description", width=W)
            out += f"{desc}\n"

    elif item_type == "armor":
        out += f"|c{name}|n\n"
        out += f"  |gSP:|n {data.get('sp', 'N/A'):<5} |gEV:|n {data.get('ev', 'N/A'):<5} |gWeight:|n {data.get('weight', 0):<5} |gValue:|n |y{data.get('value', 0):>4} eb|n\n"
        out += f"  |gLocations:|n {data.get('locations', 'N/A')}\n"
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
