# world/cyberware/implanted_armor.py
"""
Track SP for Skin Weave, Subdermal Armor, and Sycust Fleshweave (per CharacterSheet).
CPR: effective SP in a hit location is the max of all sources that cover that location;
when ablated, all applicable sources in that location lose SP together.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

# State dict keys (must match ensure_implanted_armor_for_sheet)
KEY_SKIN_WEAVE = "skin_weave"
KEY_SUBDERMAL = "subdermal_armor"
KEY_SYCUST = "sycust_fleshweave"
LAST_REPAIR_CMD = "last_natural_implanted_repair_command_at"

# Display labels for HUD / inventory (must match state keys)
IMPLANT_KEY_LABELS = {
    KEY_SKIN_WEAVE: "Skin Weave",
    KEY_SUBDERMAL: "Subdermal Armor",
    KEY_SYCUST: "Sycust Fleshweave",
}

# Cyberware names (normalized) -> state key and max SP
_IMPLANT_SPECS = (
    ("skin weave", KEY_SKIN_WEAVE, 7),
    ("sycust fleshweave", KEY_SYCUST, 7),
    ("subdermal armor", KEY_SUBDERMAL, 11),
)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _get_sheet(character: Any):
    if character is None:
        return None
    sheet = getattr(character, "character_sheet", None)
    if sheet and getattr(sheet, "pk", None):
        return sheet
    try:
        from world.cyberpunk_sheets.models import CharacterSheet

        pk = getattr(character, "pk", None) or getattr(character, "id", None)
        if pk:
            return CharacterSheet.objects.filter(character_id=pk).first()
    except Exception:
        pass
    return None


def _installed_cyberware_names(sheet) -> set:
    if not sheet or not getattr(sheet, "pk", None):
        return set()
    from world.inventory.models import CyberwareInstance

    return {
        _norm(inst.cyberware.name)
        for inst in CyberwareInstance.objects.filter(
            character_sheet_id=sheet.pk, installed=True
        ).select_related("cyberware")
    }


def ensure_implanted_armor_for_sheet(sheet) -> Dict[str, Any]:
    """
    Sync implanted_armor_state JSON with installed cyberware.
    Adds missing layers at full SP; removes layers no longer installed.
    """
    if sheet is None or not getattr(sheet, "pk", None):
        return {}
    state = dict(getattr(sheet, "implanted_armor_state", None) or {})
    installed = _installed_cyberware_names(sheet)
    changed = False
    for cw_name, key, max_sp in _IMPLANT_SPECS:
        if cw_name in installed:
            if key not in state:
                state[key] = {"current": max_sp, "max": max_sp}
                changed = True
            else:
                ent = state[key]
                old_max = int(ent.get("max", max_sp) or max_sp)
                if old_max != max_sp:
                    ent["max"] = max_sp
                    ent["current"] = min(int(ent.get("current", max_sp) or max_sp), max_sp)
                    changed = True
        elif key in state:
            del state[key]
            changed = True
    if changed:
        sheet.implanted_armor_state = state
        sheet.save(skip_recalculation=True)
    return state


def armor_locations_cover_hit(locations_str: str, aim_location: Optional[str]) -> bool:
    """Whether worn armor's `locations` field protects this hit zone."""
    if not locations_str or not aim_location:
        return False
    al = str(aim_location).lower().strip()
    parts = [
        p.strip().lower()
        for p in str(locations_str).replace("/", ",").split(",")
        if p.strip()
    ]
    if al == "head":
        return "head" in parts or "eyes" in parts
    if al == "body":
        return "body" in parts
    if al == "leg":
        return "legs" in parts
    if al == "held_item":
        return False
    return False


def _implant_covers_hit(aim_location: Optional[str]) -> bool:
    """Skin weave / subdermal / sycust protect body and head (not leg-only rule per examples)."""
    al = str(aim_location or "body").lower().strip()
    return al in ("body", "head")


def get_implanted_layers_for_location(character: Any, aim_location: Optional[str]) -> List[Tuple[str, int]]:
    """Return [(state_key, current_sp), ...] for implants that apply to this hit location."""
    if not _implant_covers_hit(aim_location):
        return []
    sheet = _get_sheet(character)
    if not sheet:
        return []
    state = ensure_implanted_armor_for_sheet(sheet)
    out: List[Tuple[str, int]] = []
    for _, key, _ in _IMPLANT_SPECS:
        if key not in state:
            continue
        cur = int(state[key].get("current", 0) or 0)
        if cur > 0:
            out.append((key, cur))
    return out


def get_worn_layer_sp(character: Any, aim_location: Optional[str]) -> Tuple[int, Optional[Any], Optional[Any]]:
    """
    Return (effective_sp, Armor model or None, InventoryArmor inst or None) for equipped armor
    if it covers aim_location.
    """
    sheet = _get_sheet(character)
    if not sheet:
        return 0, None, None
    armor = getattr(sheet, "eqarmor", None)
    if not armor:
        return 0, None, None
    locs = getattr(armor, "locations", "") or ""
    if not armor_locations_cover_hit(locs, aim_location or "body"):
        return 0, None, None
    base_sp = getattr(armor, "sp", 0) or 0
    inv = getattr(sheet, "inventory", None)
    if not inv:
        return base_sp, armor, None
    try:
        from world.inventory.models import InventoryArmor

        inst = InventoryArmor.objects.filter(inventory=inv, armor=armor).first()
        if inst:
            return inst.get_effective_sp(), armor, inst
    except Exception:
        pass
    return base_sp, armor, None


def get_total_armor_sp_for_location(character: Any, aim_location: Optional[str]) -> int:
    """Max of all protective SP sources for this location."""
    worn_sp, _, _ = get_worn_layer_sp(character, aim_location)
    imp_layers = get_implanted_layers_for_location(character, aim_location)
    implant_sp = max((sp for _, sp in imp_layers), default=0)
    return max(worn_sp, implant_sp)


def ablate_all_armor_for_location(character: Any, aim_location: Optional[str], amount: int = 1) -> None:
    """Reduce every protective source for this location by `amount` (min 0)."""
    if amount <= 0:
        return
    al = aim_location or "body"
    sheet = _get_sheet(character)
    worn_sp, armor, inv_armor = get_worn_layer_sp(character, al)
    if sheet and armor and inv_armor and worn_sp > 0:
        try:
            base = inv_armor.original_sp if inv_armor.original_sp is not None else armor.sp
            current = inv_armor.current_sp if inv_armor.current_sp is not None else armor.sp
            inv_armor.current_sp = max(0, current - amount)
            if inv_armor.original_sp is None:
                inv_armor.original_sp = base
            inv_armor.save()
        except Exception:
            pass
    elif sheet and armor and worn_sp > 0 and inv_armor is None:
        try:
            from world.inventory.models import InventoryArmor

            inv = getattr(sheet, "inventory", None)
            if inv:
                inv_armor, _ = InventoryArmor.objects.get_or_create(
                    inventory=inv,
                    armor=armor,
                    defaults={"current_sp": armor.sp, "original_sp": armor.sp},
                )
                current = inv_armor.current_sp if inv_armor.current_sp is not None else armor.sp
                inv_armor.current_sp = max(0, current - amount)
                inv_armor.save()
        except Exception:
            pass

    if not _implant_covers_hit(al):
        return
    if not sheet:
        return
    state = dict(ensure_implanted_armor_for_sheet(sheet))
    changed = False
    for _, key, __ in _IMPLANT_SPECS:
        if key not in state:
            continue
        ent = state[key]
        cur = int(ent.get("current", 0) or 0)
        if cur <= 0:
            continue
        ent["current"] = max(0, cur - amount)
        changed = True
    if changed:
        sheet.implanted_armor_state = state
        sheet.save(skip_recalculation=True)


def repair_subdermal_command(caller) -> Tuple[bool, str]:
    """
    +repair/subdermal logic.
    Sycust Fleshweave: restore to full max (always, no shared cooldown).
    Skin Weave / Subdermal: +1 SP each (capped) if 24h elapsed since last use for those layers.
    """
    sheet = _get_sheet(caller)
    if not sheet:
        return False, "No character sheet."
    state = dict(ensure_implanted_armor_for_sheet(sheet))
    now = time.time()
    msgs = []
    changed = False

    if KEY_SYCUST in state:
        ent = state[KEY_SYCUST]
        mx = int(ent.get("max", 7) or 7)
        ent["current"] = mx
        state[KEY_SYCUST] = ent
        changed = True
        msgs.append("Sycust Fleshweave restored to full SP.")

    has_sq = KEY_SKIN_WEAVE in state or KEY_SUBDERMAL in state
    if not has_sq and not msgs:
        return False, "You have no Skin Weave, Subdermal Armor, or Sycust Fleshweave installed."

    if has_sq:
        last = state.get(LAST_REPAIR_CMD)
        if last is not None and (now - float(last)) < 86400:
            remaining = int(86400 - (now - float(last)))
            h = remaining // 3600
            m = (remaining % 3600) // 60
            wait_msg = f"Skin Weave / Subdermal repair on cooldown ({h}h {m}m)."
            if msgs:
                sheet.implanted_armor_state = state
                sheet.save(skip_recalculation=True)
                return True, " ".join(msgs) + f" ({wait_msg})"
            return False, wait_msg

        repaired_layers = []
        for key, label in ((KEY_SKIN_WEAVE, "Skin Weave"), (KEY_SUBDERMAL, "Subdermal Armor")):
            if key not in state:
                continue
            ent = state[key]
            cur = int(ent.get("current", 0) or 0)
            mx = int(ent.get("max", 0) or 0)
            if cur < mx:
                ent["current"] = cur + 1
                state[key] = ent
                changed = True
                repaired_layers.append(f"{label}: +1 SP ({ent['current']}/{mx})")
        if repaired_layers:
            state[LAST_REPAIR_CMD] = now
            msgs.extend(repaired_layers)
        elif not msgs:
            return False, "Your Skin Weave / Subdermal is already at full SP."

    if not changed:
        return False, "Nothing to repair."
    sheet.implanted_armor_state = state
    sheet.save(skip_recalculation=True)
    return True, " ".join(msgs)


def apply_daily_natural_healing_implanted_armor(sheet) -> Tuple[bool, str]:
    """
    After a full day of natural healing: +1 SP to Skin Weave and Subdermal (each), capped at max.
    Sycust Fleshweave is not restored by this (use passive / +repair/subdermal).
    """
    if sheet is None or not getattr(sheet, "pk", None):
        return False, ""
    state = dict(ensure_implanted_armor_for_sheet(sheet))
    changed = False
    msgs = []
    for key, label in ((KEY_SKIN_WEAVE, "Skin Weave"), (KEY_SUBDERMAL, "Subdermal Armor")):
        if key not in state:
            continue
        ent = state[key]
        cur = int(ent.get("current", 0) or 0)
        mx = int(ent.get("max", 0) or 0)
        if cur < mx:
            ent["current"] = cur + 1
            state[key] = ent
            changed = True
            msgs.append(f"{label} +1 SP ({ent['current']}/{mx})")
    if not changed:
        return False, ""
    sheet.implanted_armor_state = state
    sheet.save(skip_recalculation=True)
    return True, "; ".join(msgs)


def staff_set_implanted_sp(sheet, key: str, current: Optional[int] = None) -> Tuple[bool, str]:
    """Staff: set implanted layer SP. key = skin_weave | subdermal_armor | sycust_fleshweave"""
    ensure_implanted_armor_for_sheet(sheet)
    state = dict(sheet.implanted_armor_state or {})
    if key not in state:
        return False, f"No implanted layer '{key}' on this character."
    ent = state[key]
    mx = int(ent.get("max", 0) or 0)
    if current is None:
        ent["current"] = mx
    else:
        ent["current"] = max(0, min(int(current), mx))
    state[key] = ent
    sheet.implanted_armor_state = state
    sheet.save(skip_recalculation=True)
    return True, f"{key} SP set to {ent['current']}/{mx}."


def get_hud_armor_display_line(character: Any, sheet: Any = None) -> str:
    """
    Single armor summary for HUD.

    Shows **worn** armor only when its effective body SP is **strictly greater** than
    the best implanted layer for body; otherwise shows implanted protection when present
    (so fleshweave/subdermal still appears after removing an inferior jacket).
    """
    if sheet is None:
        sheet = _get_sheet(character)
    if not sheet:
        return "no armor"
    ensure_implanted_armor_for_sheet(sheet)
    aim = "body"
    worn_sp, armor, _inv_armor = get_worn_layer_sp(character, aim)
    layers = get_implanted_layers_for_location(character, aim)
    implant_max = max((s for _, s in layers), default=0)

    def _format_worn() -> str:
        if not armor or worn_sp <= 0:
            return ""
        inv = getattr(sheet, "inventory", None)
        current_sp = getattr(armor, "sp", 0) or 0
        base_sp = current_sp
        if inv:
            try:
                from world.inventory.models import InventoryArmor

                inst, _ = InventoryArmor.objects.get_or_create(
                    inventory=inv,
                    armor=armor,
                    defaults={"current_sp": armor.sp, "original_sp": armor.sp},
                )
                current_sp = inst.get_effective_sp()
                base_sp = inst.original_sp if inst.original_sp is not None else armor.sp
            except Exception:
                pass
        return f"{armor.name}, {current_sp}/{base_sp} SP"

    if implant_max > 0 and worn_sp <= implant_max:
        best = max(layers, key=lambda x: x[1])
        key, cur = best
        state = dict(getattr(sheet, "implanted_armor_state", None) or {})
        ent = state.get(key) or {}
        mx = int(ent.get("max", cur) or cur)
        label = IMPLANT_KEY_LABELS.get(key, key.replace("_", " ").title())
        return f"{label} (implanted), {cur}/{mx} SP"

    if worn_sp > implant_max and armor:
        return _format_worn()

    return "no armor"


def get_inventory_implanted_armor_rows(character_sheet) -> List[str]:
    """
    Lines for the Armor section of ``inv``: one row per active implant layer.
    Call after ``ensure_implanted_armor_for_sheet``.
    """
    from world.utils.formatting import inv_visible_cell

    if character_sheet is None or not getattr(character_sheet, "pk", None):
        return []
    ensure_implanted_armor_for_sheet(character_sheet)
    state = dict(getattr(character_sheet, "implanted_armor_state", None) or {})
    rows: List[str] = []
    for _cwname, key, default_max in _IMPLANT_SPECS:
        if key not in state:
            continue
        ent = state[key]
        cur = int(ent.get("current", 0) or 0)
        mx = int(ent.get("max", default_max) or default_max)
        label = IMPLANT_KEY_LABELS.get(key, key.replace("_", " ").title())
        # Match ``inv`` armor column widths (78-char layout)
        cw_name, cw_sp, cw_ev, cw_loc = 26, 12, 6, 31
        name_col = inv_visible_cell(f"{label} (implanted)", cw_name)
        sp_col = inv_visible_cell(f"{cur}/{mx}", cw_sp)
        ev_col = inv_visible_cell("—", cw_ev)
        loc_col = inv_visible_cell("body, head", cw_loc)
        rows.append(
            f"|w{name_col}|n |c{sp_col}|n |m{ev_col}|n|y{loc_col}|n\n"
        )
    return rows
