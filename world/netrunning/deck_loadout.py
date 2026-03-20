"""
Cyberdeck loadout: programs, Black ICE, and hardware share the deck's total slot pool
(``hardware_slots + program_slots + any_slots`` from ``equipment_data.cyberdecks``).

Stored on ``character.db.cyberdeck_loadout``::
    { "<Cyberdeck Gear.name>": {"programs": [...], "hardware": [...]}, }

Legacy ``cyberdeck_hardware`` (map of deck -> list of hardware only) is migrated on read.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from world.equipment_data import cyberdecks as cyberdecks_data
from world.netrunning import deckoptions

VOUCHER_TYPECLASS = "typeclasses.vouchers.Voucher"

LOADOUT_ATTR = "cyberdeck_loadout"
LEGACY_HW_ATTR = "cyberdeck_hardware"


def hardware_data_by_name(name: str) -> Optional[dict]:
    if not name:
        return None
    n = name.strip().lower()
    for h in deckoptions.hardware:
        if (h.get("name") or "").strip().lower() == n:
            return h
    return None


def program_data_by_name(name: str) -> Optional[dict]:
    if not name:
        return None
    n = name.strip().lower()
    for p in deckoptions.programs:
        if (p.get("name") or "").strip().lower() == n:
            return p
    return None


def black_ice_data_by_name(name: str) -> Optional[dict]:
    if not name:
        return None
    n = name.strip().lower()
    for b in deckoptions.black_ice:
        if (b.get("name") or "").strip().lower() == n:
            return b
    return None


def installable_program_or_ice(name: str) -> Optional[dict]:
    """First matching program, else Black ICE entry."""
    return program_data_by_name(name) or black_ice_data_by_name(name)


def program_slot_cost(name: str) -> int:
    """Each program / Black ICE counts as one slot toward the shared pool."""
    if installable_program_or_ice(name):
        return 1
    return 0


def get_deck_slots_total(deck_gear_name: str) -> Optional[int]:
    if not deck_gear_name:
        return None
    for cd in cyberdecks_data:
        if cd.get("name") == deck_gear_name:
            return int(cd.get("hardware_slots") or 0) + int(
                cd.get("program_slots") or 0
            ) + int(cd.get("any_slots") or 0)
    return None


def count_hardware_slots_used(installed_names: List[str]) -> int:
    total = 0
    for nm in installed_names:
        d = hardware_data_by_name(nm)
        if d:
            total += int(d.get("slots") or 0)
    return total


def count_program_slots_used(installed_names: List[str]) -> int:
    return sum(program_slot_cost(n) for n in installed_names)


def _empty_entry() -> Dict[str, List[str]]:
    return {"hardware": [], "programs": []}


def _normalize_entry(raw) -> Dict[str, List[str]]:
    if isinstance(raw, dict):
        hw = raw.get("hardware") if isinstance(raw.get("hardware"), list) else []
        pr = raw.get("programs") if isinstance(raw.get("programs"), list) else []
        return {"hardware": [str(x) for x in hw], "programs": [str(x) for x in pr]}
    if isinstance(raw, list):
        return {"hardware": [str(x) for x in raw], "programs": []}
    return _empty_entry()


def get_deck_loadouts(character) -> Dict[str, Dict[str, List[str]]]:
    modern = getattr(character.db, LOADOUT_ATTR, None)
    legacy = getattr(character.db, LEGACY_HW_ATTR, None)
    out: Dict[str, Dict[str, List[str]]] = {}

    if isinstance(modern, dict):
        for k, v in modern.items():
            out[str(k)] = _normalize_entry(v)

    if isinstance(legacy, dict):
        for k, v in legacy.items():
            key = str(k)
            if key not in out:
                out[key] = _normalize_entry(v)
            elif not out[key]["hardware"] and isinstance(v, list):
                out[key]["hardware"] = [str(x) for x in v]

    return out


def _persist(character, data: Dict[str, Dict[str, List[str]]]) -> None:
    character.db.cyberdeck_loadout = {
        k: {"hardware": list(v["hardware"]), "programs": list(v["programs"])}
        for k, v in data.items()
    }
    if hasattr(character.db, LEGACY_HW_ATTR):
        character.db.cyberdeck_hardware = None


def resolve_deck_gear(character, deck_name_query: str):
    from world.inventory.models import Inventory
    from world.utils.character_utils import get_character_sheet
    from world.utils.name_fuzzy import pick_named_candidate

    deck_name_query = (deck_name_query or "").strip()
    if not deck_name_query:
        return None, "No cyberdeck name given.", None

    sheet = get_character_sheet(character)
    if not sheet:
        return None, "No character sheet.", None

    inv, _ = Inventory.get_or_create_for_character(character)
    deck_candidates = [(g.name, g) for g in inv.gear.all() if getattr(g, "is_cyberdeck", False)]
    deck_gear, err = pick_named_candidate(deck_name_query, deck_candidates)
    if err:
        return None, err, None
    if not deck_gear:
        return None, f"No cyberdeck in your inventory matching '{deck_name_query}'.", None

    deck_key = deck_gear.name
    total = get_deck_slots_total(deck_key)
    if total is None or total < 1:
        return (
            None,
            f"No slot configuration found for '{deck_key}'. Add it to equipment_data cyberdecks.",
            None,
        )
    return deck_key, None, total


def consume_deck_option_from_vouchers(character, hw_name: str) -> bool:
    return _consume_voucher_gear(
        character, hw_name, category="Deck Option",
    )


def consume_program_from_vouchers(character, prog_name: str) -> bool:
    return _consume_voucher_gear(
        character, prog_name, category="Program",
    )


def _consume_voucher_gear(character, item_name: str, *, category: str) -> bool:
    if not item_name or not getattr(character, "contents", None):
        return False
    target = item_name.strip().lower()
    for obj in list(character.contents):
        if not obj.is_typeclass(VOUCHER_TYPECLASS):
            continue
        get_items = getattr(obj, "get_items", None)
        if not callable(get_items):
            continue
        items = get_items()
        for i, it in enumerate(items):
            if (it.get("item_type") or "").lower() != "gear":
                continue
            data = it.get("item_data") or {}
            if (data.get("category") or "") != category:
                continue
            if (it.get("name") or "").strip().lower() != target:
                continue
            new_items = items[:i] + items[i + 1 :]
            obj.set_items(new_items)
            if hasattr(obj, "is_empty") and obj.is_empty():
                obj.delete()
            return True
    return False


def ensure_deck_option_gear(hw_name: str):
    from world.inventory.models import Gear

    data = hardware_data_by_name(hw_name)
    if not data:
        return None
    name = data["name"]
    gear, _ = Gear.objects.get_or_create(
        name=name,
        defaults={
            "category": "Deck Option",
            "description": data.get("description", ""),
            "weight": 0,
            "value": int(data.get("cost") or 0),
        },
    )
    return gear


def ensure_program_gear(prog_name: str):
    """Return Gear for a program or Black ICE instance going to inventory."""
    from world.inventory.models import Gear

    pdata = program_data_by_name(prog_name)
    if pdata:
        name = pdata["name"]
        gear, _ = Gear.objects.get_or_create(
            name=name,
            defaults={
                "category": "Program",
                "description": (pdata.get("effect") or pdata.get("description", ""))[:2000],
                "weight": 0,
                "value": int(pdata.get("cost") or 0),
            },
        )
        return gear
    bdata = black_ice_data_by_name(prog_name)
    if bdata:
        name = bdata["name"]
        gear, _ = Gear.objects.get_or_create(
            name=name,
            defaults={
                "category": "Black ICE",
                "description": (bdata.get("effect") or "")[:2000],
                "weight": 0,
                "value": int(bdata.get("cost") or 0),
            },
        )
        return gear
    return None


def install_deck_hardware(
    character, deck_name_query: str, hw_name_query: str
) -> Tuple[bool, str]:
    from world.inventory.models import Inventory
    from world.utils.name_fuzzy import pick_named_candidate

    deck_key, err, total = resolve_deck_gear(character, deck_name_query)
    if err:
        return False, err

    hw_name_query = (hw_name_query or "").strip()
    if not hw_name_query:
        return False, "Specify hardware to install."

    inv, _ = Inventory.get_or_create_for_character(character)
    hw_data = hardware_data_by_name(hw_name_query)
    if not hw_data:
        hw_pick = [(h["name"], h["name"]) for h in deckoptions.hardware if h.get("name")]
        canonical, err = pick_named_candidate(hw_name_query, hw_pick)
        if err:
            return False, err
        if not canonical:
            return False, f"'{hw_name_query}' is not valid cyberdeck hardware."
        hw_data = hardware_data_by_name(canonical)
    hw_name = hw_data["name"]

    loadouts = get_deck_loadouts(character)
    ent = loadouts.get(deck_key) or _empty_entry()
    hw_list = list(ent["hardware"])
    pr_list = list(ent["programs"])

    if hw_name in hw_list:
        return False, f"{hw_name} is already installed on {deck_key}."

    slot_cost = int(hw_data.get("slots") or 0)
    used = count_hardware_slots_used(hw_list) + count_program_slots_used(pr_list)
    if used + slot_cost > total:
        return False, (
            f"Not enough slots on {deck_key}: {hw_name} needs {slot_cost} but only "
            f"{total - used} of {total} remain (programs + hardware share this pool)."
        )

    inv_gear = inv.gear.filter(name__iexact=hw_name).first()
    if inv_gear:
        if not hardware_data_by_name(inv_gear.name):
            return False, f"'{inv_gear.name}' is not installable cyberdeck hardware."
        inv.remove_gear(inv_gear)
    elif not consume_deck_option_from_vouchers(character, hw_name):
        return False, (
            f"You need '{hw_name}' in your inventory or on a crafted deck-option voucher."
        )

    hw_list.append(hw_name)
    loadouts[deck_key] = {"hardware": hw_list, "programs": pr_list}
    _persist(character, loadouts)

    used_after = count_hardware_slots_used(hw_list) + count_program_slots_used(pr_list)
    return (
        True,
        f"Installed |w{hw_name}|n on |c{deck_key}|n ({used_after}/{total} slots used).",
    )


def install_deck_program(
    character, deck_name_query: str, prog_name_query: str
) -> Tuple[bool, str]:
    from world.inventory.models import Inventory
    from world.utils.name_fuzzy import pick_named_candidate

    deck_key, err, total = resolve_deck_gear(character, deck_name_query)
    if err:
        return False, err

    prog_name_query = (prog_name_query or "").strip()
    if not prog_name_query:
        return False, "Specify a program or Black ICE name to install."

    pdata = installable_program_or_ice(prog_name_query)
    if not pdata:
        prog_pool = [(p["name"], p["name"]) for p in deckoptions.programs if p.get("name")]
        prog_pool += [(b["name"], b["name"]) for b in deckoptions.black_ice if b.get("name")]
        canonical, err = pick_named_candidate(prog_name_query, prog_pool)
        if err:
            return False, err
        if not canonical:
            return False, f"'{prog_name_query}' is not a known program or Black ICE."
        pdata = installable_program_or_ice(canonical)
    prog_name = pdata["name"]

    inv, _ = Inventory.get_or_create_for_character(character)
    loadouts = get_deck_loadouts(character)
    ent = loadouts.get(deck_key) or _empty_entry()
    hw_list = list(ent["hardware"])
    pr_list = list(ent["programs"])

    if prog_name in pr_list:
        return False, f"{prog_name} is already loaded on {deck_key}."

    cost = program_slot_cost(prog_name)
    used = count_hardware_slots_used(hw_list) + count_program_slots_used(pr_list)
    if used + cost > total:
        return False, (
            f"Not enough slots on {deck_key}: need {cost} for {prog_name} but only {total - used} of {total} remain."
        )

    inv_gear = inv.gear.filter(name__iexact=prog_name).first()
    cat_ok = inv_gear and (
        (inv_gear.category or "") in ("Program", "Black ICE")
        or program_data_by_name(inv_gear.name)
        or black_ice_data_by_name(inv_gear.name)
    )
    if inv_gear and cat_ok:
        inv.remove_gear(inv_gear)
    elif not consume_program_from_vouchers(character, prog_name):
        return False, (
            f"You need '{prog_name}' in your inventory (Program / Black ICE gear) or on a crafted program voucher."
        )

    pr_list.append(prog_name)
    loadouts[deck_key] = {"hardware": hw_list, "programs": pr_list}
    _persist(character, loadouts)

    used_after = count_hardware_slots_used(hw_list) + count_program_slots_used(pr_list)
    return (
        True,
        f"Loaded |w{prog_name}|n on |c{deck_key}|n ({used_after}/{total} slots used).",
    )


def install_deck_item(
    character, deck_name_query: str, item_query: str
) -> Tuple[bool, str]:
    """Fuzzy-resolve item as deck hardware or program / Black ICE, then install."""
    from world.utils.name_fuzzy import pick_named_candidate

    item_query = (item_query or "").strip()
    if not item_query:
        return False, "Specify a program, Black ICE, or hardware option to install."

    candidates = []
    for h in deckoptions.hardware:
        if h.get("name"):
            candidates.append((h["name"], ("h", h["name"])))
    for p in deckoptions.programs:
        if p.get("name"):
            candidates.append((p["name"], ("p", p["name"])))
    for b in deckoptions.black_ice:
        if b.get("name"):
            candidates.append((b["name"], ("p", b["name"])))

    picked, err = pick_named_candidate(item_query, candidates)
    if err:
        return False, err
    if not picked:
        return False, f"Unknown deck item '{item_query}'."

    kind, canonical = picked
    if kind == "h":
        return install_deck_hardware(character, deck_name_query, canonical)
    return install_deck_program(character, deck_name_query, canonical)


def remove_deck_hardware(
    character, deck_name_query: str, hw_name_query: str
) -> Tuple[bool, str]:
    from world.inventory.models import Inventory
    from world.utils.name_fuzzy import pick_named_candidate

    deck_key, err, _total = resolve_deck_gear(character, deck_name_query)
    if err:
        return False, err

    inv, _ = Inventory.get_or_create_for_character(character)
    loadouts = get_deck_loadouts(character)
    ent = loadouts.get(deck_key) or _empty_entry()
    hw_list = list(ent["hardware"])
    pr_list = list(ent["programs"])

    pick = [(n, n) for n in hw_list]
    hw_name, err = pick_named_candidate(hw_name_query, pick)
    if err:
        return False, err
    if not hw_name or hw_name not in hw_list:
        return False, f"'{hw_name_query}' is not installed as hardware on {deck_key}."

    hw_list.remove(hw_name)
    loadouts[deck_key] = {"hardware": hw_list, "programs": pr_list}
    _persist(character, loadouts)

    gear = ensure_deck_option_gear(hw_name)
    if gear:
        inv.add_gear(gear)

    return True, f"Removed |w{hw_name}|n from |c{deck_key}|n; returned to inventory."


def remove_deck_program(
    character, deck_name_query: str, prog_name_query: str
) -> Tuple[bool, str]:
    from world.inventory.models import Inventory
    from world.utils.name_fuzzy import pick_named_candidate

    deck_key, err, _total = resolve_deck_gear(character, deck_name_query)
    if err:
        return False, err

    inv, _ = Inventory.get_or_create_for_character(character)
    loadouts = get_deck_loadouts(character)
    ent = loadouts.get(deck_key) or _empty_entry()
    hw_list = list(ent["hardware"])
    pr_list = list(ent["programs"])

    pick = [(n, n) for n in pr_list]
    prog_name, err = pick_named_candidate(prog_name_query, pick)
    if err:
        return False, err
    if not prog_name or prog_name not in pr_list:
        return False, f"'{prog_name_query}' is not loaded on {deck_key}."

    pr_list.remove(prog_name)
    loadouts[deck_key] = {"hardware": hw_list, "programs": pr_list}
    _persist(character, loadouts)

    gear = ensure_program_gear(prog_name)
    if gear:
        inv.add_gear(gear)

    return True, f"Unloaded |w{prog_name}|n from |c{deck_key}|n; returned to inventory."


def remove_deck_item(
    character, deck_name_query: str, item_query: str
) -> Tuple[bool, str]:
    loadouts = get_deck_loadouts(character)
    deck_key, err, _ = resolve_deck_gear(character, deck_name_query)
    if err:
        return False, err
    ent = loadouts.get(deck_key) or _empty_entry()
    iq = (item_query or "").strip().lower()
    if any(iq == (p or "").lower() for p in ent["programs"]):
        return remove_deck_program(character, deck_name_query, item_query)
    if any(iq == (h or "").lower() for h in ent["hardware"]):
        return remove_deck_hardware(character, deck_name_query, item_query)
    return False, f"'{item_query}' is not installed on {deck_key}."


def format_deck_sheet(character, deck_name_filter: Optional[str] = None, width: int = 78) -> str:
    from world.inventory.models import Inventory
    from world.utils.character_utils import get_character_sheet
    from world.utils.formatting import (
        footer,
        inv_visible_cell,
        sheet_header,
        sheet_section,
    )

    sheet = get_character_sheet(character)
    if not sheet:
        return "No character sheet."

    inv, _ = Inventory.get_or_create_for_character(character)
    decks = [g for g in inv.gear.all() if getattr(g, "is_cyberdeck", False)]
    loadouts = get_deck_loadouts(character)

    if deck_name_filter:
        from world.utils.name_fuzzy import pick_named_candidate

        cand = [(g.name, g) for g in decks]
        match, err = pick_named_candidate(deck_name_filter, cand)
        if err:
            return err
        if not match:
            return f"No cyberdeck in your inventory matching '{deck_name_filter}'."
        decks = [g for g in decks if g.name == match.name]

    display_name = getattr(character.db, "full_name", None) or character.key
    lines = [sheet_header(f"Cyberdecks -- {display_name}", width=width)]

    if not decks:
        lines.append("|wYou are not carrying a cyberdeck.|n")
        lines.append(footer(width=width, fillchar="-"))
        return "\n".join(lines)

    pn, pt, pz = 28, 22, 10
    hn, hs = 52, 6

    for deck in decks:
        key = deck.name
        total = get_deck_slots_total(key)
        ent = loadouts.get(key) or _empty_entry()
        progs = list(ent["programs"])
        hws = list(ent["hardware"])
        hw_used = count_hardware_slots_used(hws)
        pr_used = count_program_slots_used(progs)
        used = hw_used + pr_used
        free = max(0, (total - used)) if total is not None else None

        lines.append(sheet_section(key[:44], width=width))
        if total is None:
            lines.append("|rNo template in equipment_data -- slot total unknown.|n\n")
        else:
            lines.append(
                f"|yTotal slots:|n |w{total}|n  |yIn use:|n |w{used}|n  |yFree:|n |w{free}|n  "
                f"|m({pr_used} program, {hw_used} hardware)|n\n"
            )

        lines.append(sheet_section("Programs & Black ICE", width=width))
        if not progs:
            lines.append("|wNo programs loaded.|n")
        else:
            lines.append(
                f"|y{inv_visible_cell('Program', pn)} {inv_visible_cell('Type', pt)} "
                f"{inv_visible_cell('REZ', pz)}|n"
            )
            for nm in progs:
                pdata = program_data_by_name(nm)
                bdata = black_ice_data_by_name(nm) if not pdata else None
                typ = (pdata.get("type") if pdata else None) or "Black ICE"
                rez = pdata.get("rez") if pdata else (bdata.get("rez") if bdata else "--")
                lines.append(
                    f"|w{inv_visible_cell(nm, pn)}|n |w{inv_visible_cell(str(typ), pt)}|n "
                    f"|w{inv_visible_cell(str(rez), pz)}|n"
                )
        lines.append("")

        lines.append(sheet_section("Hardware options", width=width))
        if not hws:
            lines.append("|wNo hardware installed.|n")
        else:
            lines.append(
                f"|y{inv_visible_cell('Hardware', hn)} {inv_visible_cell('Slots', hs)}|n"
            )
            for nm in hws:
                d = hardware_data_by_name(nm) or {}
                sc = int(d.get("slots") or 0)
                lines.append(
                    f"|w{inv_visible_cell(nm, hn)}|n |w{inv_visible_cell(str(sc), hs)}|n"
                )
        lines.append("")

    lines.append(
        "|yInstall:|n |wdeck/install <deck>=<item>|n  |yRemove:|n |wdeck/remove <deck>=<item>|n "
        "|y(detail one deck)|n |wdeck <name>|n\n"
    )
    lines.append(footer(width=width, fillchar="-"))
    return "\n".join(lines)


# Back-compat alias used by older imports
def format_deck_loadout_summary(character, width: int = 78) -> str:
    return format_deck_sheet(character, deck_name_filter=None, width=width)
