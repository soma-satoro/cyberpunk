"""
NET floor leads: delve (notice) and trace (resolve) using Interface checks only — no Focus.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from world.inventory.models import Inventory
from world.netrunning.deck_loadout import ensure_program_gear
from world.netrunning.models import NetFloorLead, NetLeadExposure, NetLeadResolution
from world.netrunning.red_netrunning import _format_interface_dice, interface_check


def _rumor_intel_for_floor(character, architecture, floor_number: int) -> List[dict]:
    intel = list(getattr(character.db, "net_rumor_intel", []) or [])
    out = []
    for row in intel:
        if row.get("consumed"):
            continue
        if int(row.get("architecture_id", 0) or 0) != int(getattr(architecture, "id", 0) or 0):
            continue
        if int(row.get("floor", 0) or 0) != int(floor_number):
            continue
        out.append(row)
    return out


def _select_rumor_target(candidates: List[NetFloorLead], rumor_intel: List[dict]) -> Tuple[Optional[NetFloorLead], int]:
    """
    Prefer a candidate lead that rumor intel points to. Returns (lead, bonus).
    """
    if not candidates or not rumor_intel:
        return None, 0
    by_id = {int(lead.id): lead for lead in candidates}
    for row in rumor_intel:
        lid = int(row.get("lead_id", 0) or 0)
        if lid in by_id:
            bonus = int(row.get("bonus", 0) or 0)
            return by_id[lid], max(0, bonus)
    return None, 0


def _consume_rumor_intel(character, architecture, floor_number: int, lead: NetFloorLead):
    intel = list(getattr(character.db, "net_rumor_intel", []) or [])
    changed = False
    for row in intel:
        if row.get("consumed"):
            continue
        if int(row.get("architecture_id", 0) or 0) != int(getattr(architecture, "id", 0) or 0):
            continue
        if int(row.get("floor", 0) or 0) != int(floor_number):
            continue
        if int(row.get("lead_id", 0) or 0) != int(getattr(lead, "id", 0) or 0):
            continue
        row["consumed"] = True
        changed = True
        break
    if changed:
        character.db.net_rumor_intel = intel[-80:]


def _prereqs_met(lead: NetFloorLead, character) -> bool:
    pre_ids = list(lead.prerequisite_leads.values_list("pk", flat=True))
    if not pre_ids:
        return True
    done = set(
        NetLeadResolution.objects.filter(character=character, lead_id__in=pre_ids).values_list(
            "lead_id", flat=True
        )
    )
    return set(pre_ids) == done


def eligible_leads_for_floor(architecture, floor_number: int, character) -> List[NetFloorLead]:
    """Leads that exist on this floor and have prerequisites satisfied; not yet exposed."""
    if not architecture:
        return []
    qs = (
        NetFloorLead.objects.filter(architecture_object_id=architecture.id, floor_number=floor_number)
        .prefetch_related("prerequisite_leads")
        .order_by("discovery_priority", "id")
    )
    out = []
    for lead in qs:
        if not _prereqs_met(lead, character):
            continue
        if NetLeadExposure.objects.filter(lead=lead, character=character).exists():
            continue
        out.append(lead)
    return out


def exposed_unresolved_leads(architecture, floor_number: int, character) -> List[NetFloorLead]:
    """Exposed but not yet traced (excluding flavor, which auto-resolves on delve)."""
    if not architecture:
        return []
    exposed_ids = NetLeadExposure.objects.filter(character=character).values_list("lead_id", flat=True)
    qs = (
        NetFloorLead.objects.filter(
            architecture_object_id=architecture.id,
            floor_number=floor_number,
            id__in=exposed_ids,
        )
        .exclude(lead_type=NetFloorLead.LEAD_FLAVOR)
        .order_by("discovery_priority", "id")
    )
    out = []
    for lead in qs:
        if NetLeadResolution.objects.filter(lead=lead, character=character).exists():
            continue
        out.append(lead)
    return out


def delve_next_lead(character, architecture, floor_number: int) -> Tuple[Optional[NetFloorLead], str]:
    """
    Try to expose the next eligible lead. One Interface check vs that lead's scan_dv.
    Returns (lead_or_none, message).
    """
    all_floor_leads = list(
        NetFloorLead.objects.filter(
            architecture_object_id=architecture.id,
            floor_number=floor_number,
        )
        .prefetch_related("prerequisite_leads")
        .order_by("discovery_priority", "id")
    )
    if not all_floor_leads:
        return None, "|yNo custom trails are seeded on this floor.|n"

    candidates = eligible_leads_for_floor(architecture, floor_number, character)
    if not candidates:
        resolved_ids = set(
            NetLeadResolution.objects.filter(character=character).values_list("lead_id", flat=True)
        )
        blocked = []
        for lead in all_floor_leads:
            if NetLeadExposure.objects.filter(lead=lead, character=character).exists():
                continue
            missing = [pre for pre in lead.prerequisite_leads.all() if pre.pk not in resolved_ids]
            if missing:
                blocked.append((lead, missing))
        if blocked:
            lines = ["|yNo new signatures surface yet; some trails are chained behind earlier clues:|n"]
            for lead, missing in blocked[:5]:
                req = ", ".join(f"#{m.pk} {m.label}" for m in missing[:3])
                if len(missing) > 3:
                    req += ", ..."
                lines.append(f"  |w{lead.label}|n needs {req}")
            lines.append("Resolve those leads, then run |w+net/delve|n again.")
            return None, "\n".join(lines)
        return None, "|yNo hidden data signatures left to sweep on this floor.|n"

    rumor_intel = _rumor_intel_for_floor(character, architecture, floor_number)
    rumor_target, rumor_bonus = _select_rumor_target(candidates, rumor_intel)
    lead = rumor_target or candidates[0]
    total, rank, _die, details = interface_check(character, bonus=rumor_bonus)
    dice_str = _format_interface_dice(details, rumor_bonus)
    dv = int(lead.scan_dv)
    msg0 = f"|cNET sweep|n Interface {rank} + {dice_str} = |w{total}|n vs DV |w{dv}|n ({lead.label})"
    if rumor_bonus > 0 and rumor_target:
        msg0 += "\n|mRumor intel aligns with this signature, tightening your search pattern.|n"
    if total <= dv:
        return None, msg0 + "\n|rThe noise swallows the pattern. Nothing new surfaces.|n"

    NetLeadExposure.objects.get_or_create(lead=lead, character=character)
    if rumor_bonus > 0 and rumor_target:
        _consume_rumor_intel(character, architecture, floor_number, lead)

    if lead.lead_type == NetFloorLead.LEAD_FLAVOR:
        NetLeadResolution.objects.get_or_create(lead=lead, character=character)
        body = (lead.teaser or lead.success_text or "").strip() or "You skim a fragment of story in the static."
        return lead, msg0 + f"\n|gPulled from the noise:|n\n{body}"

    teaser = (lead.teaser or "").strip() or f"A trace tagged |w{lead.label}|n resolves in your overlay."
    return lead, msg0 + f"\n|gSignal acquired:|n {teaser}\nUse |w+net/trace {lead.pk}|n to crack it."


def trace_lead(character, architecture, floor_number: int, lead_id: int) -> Tuple[bool, str]:
    """Resolve an exposed lead. Returns (success, message)."""
    try:
        lead = NetFloorLead.objects.get(
            pk=lead_id,
            architecture_object_id=architecture.id,
            floor_number=floor_number,
        )
    except NetFloorLead.DoesNotExist:
        return False, "No such lead on this floor."

    if not NetLeadExposure.objects.filter(lead=lead, character=character).exists():
        return False, "You have not swept that signature yet. Use |w+net/delve|n first."

    if lead.lead_type == NetFloorLead.LEAD_FLAVOR:
        return True, "Flavor text was already absorbed when you swept it."

    if NetLeadResolution.objects.filter(lead=lead, character=character).exists():
        return True, "You already extracted everything from this lead."

    total, rank, _die, details = interface_check(character, bonus=0)
    dice_str = _format_interface_dice(details, 0)
    dv = int(lead.investigate_dv)
    head = f"|cTrace|n Interface {rank} + {dice_str} = |w{total}|n vs DV |w{dv}|n\n"

    if total <= dv:
        return False, head + "|rThe structure shifts; you lose the thread.|n"

    NetLeadResolution.objects.get_or_create(lead=lead, character=character)

    parts = [head + "|gAccessed.|n"]

    st = (lead.success_text or "").strip()
    if st:
        parts.append(st)

    if lead.lead_type == NetFloorLead.LEAD_NARRATIVE:
        return True, "\n".join(parts)

    if lead.lead_type == NetFloorLead.LEAD_PAYDATA:
        label = (lead.paydata_label or lead.label).strip()
        value = int(lead.paydata_value or 0)
        stash = character.db.net_paydata or []
        stash.append(
            {
                "architecture": getattr(architecture, "key", "NET"),
                "label": label,
                "value": value,
                "floor": floor_number,
                "source": "net_lead",
                "lead_id": lead.pk,
            }
        )
        character.db.net_paydata = stash
        parts.append(f"|gPaydata secured:|n {label} (|y{value} eb|n street value)")
        return True, "\n".join(parts)

    if lead.lead_type == NetFloorLead.LEAD_PROGRAM:
        pname = (lead.program_name or "").strip()
        if not pname:
            return True, "\n".join(parts) + "\n|y(Staff: set program_name on this lead.)|n"
        gear = ensure_program_gear(pname)
        if not gear:
            return True, "\n".join(parts) + f"\n|yUnknown program '{pname}' — staff must use a valid deck program name.|n"
        inv, _ = Inventory.get_or_create_for_character(character)
        inv.add_gear(gear)
        parts.append(
            f"|gRipped to offline buffer:|n {gear.name} (|yin inventory|n — load with |w+deck/install|n)"
        )
        return True, "\n".join(parts)

    return True, "\n".join(parts)


def format_leads_notebook(character, architecture, floor_number: int) -> str:
    """Exposed leads on this floor with linkage hints."""
    qs = (
        NetFloorLead.objects.filter(architecture_object_id=architecture.id, floor_number=floor_number)
        .prefetch_related("linked_leads", "prerequisite_leads")
        .order_by("discovery_priority", "id")
    )
    resolved_ids = set(
        NetLeadResolution.objects.filter(character=character).values_list("lead_id", flat=True)
    )
    lines = []
    for lead in qs:
        if not NetLeadExposure.objects.filter(lead=lead, character=character).exists():
            continue
        resolved = NetLeadResolution.objects.filter(lead=lead, character=character).exists()
        status = "|gdone|n" if resolved else "|yopen|n"
        extra = ""
        linked = [x for x in lead.linked_leads.all() if x.pk != lead.pk]
        if linked:
            bits = ", ".join(f"{x.label} (#{x.pk})" for x in linked[:6])
            if len(linked) > 6:
                bits += "…"
            extra = f"  |cLinked:|n {bits}"
        needs = [p for p in lead.prerequisite_leads.all() if p.pk not in resolved_ids]
        req_txt = ""
        if needs:
            need_bits = ", ".join(f"#{p.pk}" for p in needs[:6])
            if len(needs) > 6:
                need_bits += ", ..."
            req_txt = f"  |mNeeds:|n {need_bits}"
        lines.append(f"  |w#{lead.pk}|n {lead.label} [{status}]{extra}{req_txt}")
    if not lines:
        return "|yNo swept signatures logged for this floor.|n"
    return "|cNET notebook (this floor)|n\n" + "\n".join(lines)
