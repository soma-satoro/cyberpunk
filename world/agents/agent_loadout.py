"""
Agent loadout: install/remove apps on carried Agents and installed Internal Agents.

Stored on ``character.db.agent_app_loadout``::
    {
        "<device_key>": {"apps": ["BabelChat App", ...]},
    }

Device keys are stable per source:
    - Gear Agent: ``gear:<Gear.name>``
    - Installed Internal Agent cyberware: ``cyberware:<CyberwareInstance.id>``
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from world.cyberware.cyberware_data import CYBERWARE_DATA
from world.equipment_data import gears
from world.inventory.models import CyberwareInstance, Gear, Inventory
from world.utils.name_fuzzy import pick_named_candidate

LOADOUT_ATTR = "agent_app_loadout"
AGENT_APP_CATEGORY = "Agent App"

DEFAULT_APP_SLOTS_BY_QUALITY = {
    "poor": 4,
    "standard": 6,
    "excellent": 8,
}

VOUCHER_TYPECLASS = "typeclasses.vouchers.Voucher"


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _empty_entry() -> Dict[str, List[str]]:
    return {"apps": []}


def _normalize_entry(raw) -> Dict[str, List[str]]:
    if isinstance(raw, dict):
        apps = raw.get("apps") if isinstance(raw.get("apps"), list) else []
        return {"apps": [str(x) for x in apps]}
    if isinstance(raw, list):
        return {"apps": [str(x) for x in raw]}
    return _empty_entry()


def _persist(character, data: Dict[str, Dict[str, List[str]]]) -> None:
    character.db.agent_app_loadout = {k: {"apps": list(v["apps"])} for k, v in data.items()}


def app_data_by_name(name: str) -> Optional[dict]:
    if not name:
        return None
    n = _norm(name)
    for item in gears:
        if _norm(item.get("category")) != _norm(AGENT_APP_CATEGORY):
            continue
        if _norm(item.get("name")) == n:
            return item
    return None


def _agent_gear_data_by_name(name: str) -> Optional[dict]:
    if not name:
        return None
    n = _norm(name)
    for item in gears:
        item_name = item.get("name")
        if _norm(item_name) != n:
            continue
        category = _norm(item.get("category"))
        if category == "agent" or _norm(item_name) == "agent":
            return item
    return None


def _internal_agent_data_by_name(name: str) -> Optional[dict]:
    data = CYBERWARE_DATA.get(name)
    if not data:
        return None
    if _norm(data.get("type")) != "cyberaudio":
        return None
    name_l = _norm(data.get("name"))
    desc_l = _norm(data.get("description"))
    if "agent" not in name_l and "internal agent" not in desc_l:
        return None
    return data


def _app_slots_from_quality(quality: str) -> int:
    return DEFAULT_APP_SLOTS_BY_QUALITY.get(_norm(quality), DEFAULT_APP_SLOTS_BY_QUALITY["standard"])


def _app_slots_for_device(device_data: dict) -> int:
    explicit_slots = _to_int(device_data.get("app_slots"), 0)
    if explicit_slots > 0:
        return explicit_slots
    return _app_slots_from_quality(device_data.get("quality", "standard"))


def get_agent_loadouts(character) -> Dict[str, Dict[str, List[str]]]:
    raw = getattr(character.db, LOADOUT_ATTR, None)
    out: Dict[str, Dict[str, List[str]]] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            out[str(key)] = _normalize_entry(value)
    return out


def _get_agent_devices(character) -> List[dict]:
    devices: List[dict] = []
    inv, _ = Inventory.get_or_create_for_character(character)

    # External agent devices from inventory gear.
    for gear in inv.gear.all():
        data = _agent_gear_data_by_name(gear.name)
        if not data:
            continue
        quality = data.get("quality", "standard")
        devices.append(
            {
                "key": f"gear:{gear.name}",
                "name": gear.name,
                "label": f"{gear.name} (External)",
                "source": "External",
                "quality": quality,
                "app_slots": _app_slots_for_device(data),
            }
        )

    # Internal agent devices from installed cyberware.
    installed = CyberwareInstance.get_installed_for_character(character).select_related("cyberware")
    for inst in installed:
        name = inst.cyberware.name
        data = _internal_agent_data_by_name(name)
        if not data:
            continue
        quality = data.get("quality", "standard")
        devices.append(
            {
                "key": f"cyberware:{inst.id}",
                "name": name,
                "label": f"{name} (Internal)",
                "source": "Internal",
                "quality": quality,
                "app_slots": _app_slots_for_device(data),
            }
        )

    # Keep order deterministic for display and fuzzy matching.
    devices.sort(key=lambda d: (_norm(d.get("name")), _norm(d.get("source"))))
    return devices


def _resolve_agent_device(character, device_query: str) -> Tuple[Optional[dict], Optional[str]]:
    devices = _get_agent_devices(character)
    if not devices:
        return None, "You do not currently have an Agent device available."

    query = (device_query or "").strip()
    if not query:
        if len(devices) == 1:
            return devices[0], None
        return None, "Multiple Agents found. Specify one: agent <name>."

    candidates = [(d["label"], d) for d in devices]
    picked, err = pick_named_candidate(query, candidates)
    if err:
        return None, err
    if not picked:
        return None, f"No Agent found matching '{device_query}'."
    return picked, None


def _consume_app_from_vouchers(character, app_name: str) -> bool:
    if not app_name or not getattr(character, "contents", None):
        return False
    target = _norm(app_name)
    for obj in list(character.contents):
        if not obj.is_typeclass(VOUCHER_TYPECLASS):
            continue
        get_items = getattr(obj, "get_items", None)
        if not callable(get_items):
            continue
        items = get_items()
        for i, item in enumerate(items):
            if _norm(item.get("item_type")) != "gear":
                continue
            data = item.get("item_data") or {}
            if _norm(data.get("category")) != _norm(AGENT_APP_CATEGORY):
                continue
            if _norm(item.get("name")) != target:
                continue
            obj.set_items(items[:i] + items[i + 1 :])
            if hasattr(obj, "is_empty") and obj.is_empty():
                obj.delete()
            return True
    return False


def ensure_agent_app_gear(app_name: str) -> Optional[Gear]:
    app_data = app_data_by_name(app_name)
    if not app_data:
        return None
    gear, _ = Gear.objects.get_or_create(
        name=app_data["name"],
        defaults={
            "category": AGENT_APP_CATEGORY,
            "description": app_data.get("description", ""),
            "weight": app_data.get("weight", 0),
            "value": _to_int(app_data.get("value"), 0),
        },
    )
    return gear


def install_agent_app(character, device_query: str, app_query: str) -> Tuple[bool, str]:
    device, err = _resolve_agent_device(character, device_query)
    if err:
        return False, err

    app_query = (app_query or "").strip()
    if not app_query:
        return False, "Specify an app name to install."

    app_candidates = [(item.get("name"), item.get("name")) for item in gears if _norm(item.get("category")) == _norm(AGENT_APP_CATEGORY)]
    canonical_name, err = pick_named_candidate(app_query, app_candidates)
    if err:
        return False, err
    if not canonical_name:
        return False, f"'{app_query}' is not a recognized Agent app."

    app_data = app_data_by_name(canonical_name)
    if not app_data:
        return False, f"No app data found for '{canonical_name}'."

    loadouts = get_agent_loadouts(character)
    entry = loadouts.get(device["key"]) or _empty_entry()
    apps = list(entry["apps"])

    if any(_norm(name) == _norm(canonical_name) for name in apps):
        return False, f"{canonical_name} is already installed on {device['label']}."

    used = len(apps)
    capacity = int(device.get("app_slots") or 0)
    if capacity and used >= capacity:
        return False, f"{device['label']} has no free app slots ({used}/{capacity} used)."

    inv, _ = Inventory.get_or_create_for_character(character)
    app_gear = inv.gear.filter(name__iexact=canonical_name, category=AGENT_APP_CATEGORY).first()
    if app_gear:
        inv.remove_gear(app_gear)
    elif not _consume_app_from_vouchers(character, canonical_name):
        return False, f"You need a '{canonical_name}' app in inventory (or voucher) to install it."

    apps.append(canonical_name)
    entry["apps"] = apps
    loadouts[device["key"]] = entry
    _persist(character, loadouts)
    return True, f"Installed {canonical_name} on {device['label']} ({len(apps)}/{capacity} slots used)."


def remove_agent_app(character, device_query: str, app_query: str) -> Tuple[bool, str]:
    device, err = _resolve_agent_device(character, device_query)
    if err:
        return False, err

    app_query = (app_query or "").strip()
    if not app_query:
        return False, "Specify an app name to remove."

    loadouts = get_agent_loadouts(character)
    entry = loadouts.get(device["key"]) or _empty_entry()
    apps = list(entry["apps"])
    matched_name = next((name for name in apps if _norm(name) == _norm(app_query)), None)
    if not matched_name:
        return False, f"{app_query} is not installed on {device['label']}."

    apps = [name for name in apps if _norm(name) != _norm(matched_name)]
    entry["apps"] = apps
    loadouts[device["key"]] = entry
    _persist(character, loadouts)

    app_gear = ensure_agent_app_gear(matched_name)
    if app_gear:
        inv, _ = Inventory.get_or_create_for_character(character)
        inv.add_gear(app_gear)

    capacity = int(device.get("app_slots") or 0)
    return True, f"Removed {matched_name} from {device['label']} ({len(apps)}/{capacity} slots used)."


def format_agent_sheet(character, device_filter: Optional[str] = None, width: int = 78) -> str:
    from world.utils.formatting import footer, inv_visible_cell, sheet_header, sheet_section

    display_name = getattr(character.db, "full_name", None) or character.key
    lines = [sheet_header(f"Agents -- {display_name}", width=width)]

    devices = _get_agent_devices(character)
    if device_filter:
        picked, err = _resolve_agent_device(character, device_filter)
        if err:
            return err
        devices = [picked]

    if not devices:
        lines.append("|wYou do not have any Agent devices available.|n")
        lines.append(footer(width=width, fillchar="-"))
        return "\n".join(lines)

    loadouts = get_agent_loadouts(character)
    an, av = 58, 8
    for device in devices:
        entry = loadouts.get(device["key"]) or _empty_entry()
        apps = list(entry["apps"])
        capacity = int(device.get("app_slots") or 0)
        used = len(apps)
        free = max(0, capacity - used) if capacity else 0

        lines.append(sheet_section(device["label"][:44], width=width))
        lines.append(
            f"|ySource:|n |w{device['source']}|n  |yQuality:|n |w{device['quality']}|n  "
            f"|ySlots:|n |w{used}/{capacity}|n  |yFree:|n |w{free}|n\n"
        )

        lines.append(sheet_section("Installed Apps", width=width))
        if not apps:
            lines.append("|wNo apps installed.|n")
        else:
            lines.append(
                f"|y{inv_visible_cell('App', an)} {inv_visible_cell('Cost', av)}|n"
            )
            for app_name in apps:
                app_data = app_data_by_name(app_name) or {}
                value = _to_int(app_data.get("value"), 0)
                lines.append(
                    f"|w{inv_visible_cell(app_name, an)}|n |w{inv_visible_cell(str(value), av)}|n"
                )
        lines.append("")

    lines.append(
        "|yInstall:|n |wagent/install <agent>=<app>|n  "
        "|yRemove:|n |wagent/remove <agent>=<app>|n  "
        "|yDetail:|n |wagent <name>|n\n"
    )
    lines.append(footer(width=width, fillchar="-"))
    return "\n".join(lines)

