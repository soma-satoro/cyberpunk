# world/cyberware/stat_bonuses.py
"""
Cyberware-derived stat/skill bonuses, effective BODY (lace + linear frames),
natural armor SP from Skin Weave / Fleshweave / Subdermal, and initiative modifiers.

Rules follow game docs: duplicate installs usually grant no extra benefit unless noted.
"""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

if TYPE_CHECKING:
    pass

# Root limb instances for Extra-Jointed "one per limb" and global cap (4 limbs).
_CYBERLIMB_ROOT_NAMES = frozenset(
    name.lower()
    for name in (
        "Cyberarm",
        "Neo-Soviet Cyberarm",
        "Cyberleg",
        "Rocklin Augmentics Skydrivers",
        "Wyzard Technologies Romanova Cyberlegs",
    )
)


def _norm(name: str) -> str:
    return (name or "").strip().lower()


def _get_character_sheet(character: Any):
    if character is None:
        return None
    sheet = getattr(character, "character_sheet", None)
    if sheet and getattr(sheet, "pk", None):
        return sheet
    # Fallback: CharacterSheet by ObjectDB id
    try:
        from world.cyberpunk_sheets.models import CharacterSheet

        char_pk = getattr(character, "pk", None) or getattr(character, "id", None)
        if char_pk:
            return CharacterSheet.objects.filter(character_id=char_pk).first()
    except Exception:
        pass
    return None


def iter_installed_instances(character: Any) -> List[Any]:
    """Return installed CyberwareInstance rows for this character (or sheet)."""
    from world.inventory.models import CyberwareInstance

    out: List[Any] = []
    seen_ids = set()

    sheet = _get_character_sheet(character)
    if sheet and getattr(sheet, "pk", None):
        for inst in (
            CyberwareInstance.objects.filter(character_sheet_id=sheet.pk, installed=True)
            .select_related(
                "cyberware",
                "parent",
                "parent__cyberware",
                "parent__parent",
                "parent__parent__cyberware",
                "parent__parent__parent",
                "parent__parent__parent__cyberware",
            )
        ):
            if inst.id not in seen_ids:
                seen_ids.add(inst.id)
                out.append(inst)

    if character is not None:
        for inst in CyberwareInstance.objects.filter(
            character_object_id=getattr(character, "pk", None) or getattr(character, "id", None),
            installed=True,
        ).select_related(
            "cyberware",
            "parent",
            "parent__cyberware",
            "parent__parent",
            "parent__parent__cyberware",
            "parent__parent__parent",
            "parent__parent__parent__cyberware",
        ):
            if inst.id not in seen_ids:
                seen_ids.add(inst.id)
                out.append(inst)

    return out


def _name_counter(instances: Iterable[Any]) -> Counter:
    c: Counter = Counter()
    for inst in instances:
        c[_norm(getattr(inst.cyberware, "name", ""))] += 1
    return c


def _effective_body_from_counts(natural: int, counts: Counter) -> int:
    natural = max(1, int(natural))
    lace_n = counts.get("grafted muscle and bone lace", 0)
    without_frame = min(natural + 2 * lace_n, 10)
    if counts.get("implanted linear frame beta", 0) > 0:
        return 14
    if counts.get("implanted linear frame sigma", 0) > 0:
        return 12
    return without_frame


def get_natural_body(character: Any) -> int:
    """Unaugmented BODY from character db (or linked sheet)."""
    if character is None:
        return 1
    b = getattr(character.db, "body", None) if hasattr(character, "db") else None
    if b is not None:
        return max(1, int(b))
    sheet = _get_character_sheet(character)
    if sheet and sheet.body is not None:
        return max(1, int(sheet.body))
    return 1


def get_effective_body(character: Any) -> int:
    """
    BODY for mechanics (HP, death save threshold, serious wounds, rolls): lace cap at 10,
    Implanted Linear Frame Sigma -> 12, Beta -> 14 (Beta wins).
    """
    natural = get_natural_body(character)
    counts = _name_counter(iter_installed_instances(character))
    return _effective_body_from_counts(natural, counts)


def get_effective_body_for_sheet(sheet: Any) -> int:
    """Like get_effective_body but uses Django CharacterSheet + linked ObjectDB if any."""
    if sheet is None:
        return 1
    ch = getattr(sheet, "character", None)
    if ch:
        return get_effective_body(ch)
    natural = int(sheet.body or 1)
    from world.inventory.models import CyberwareInstance

    instances = list(
        CyberwareInstance.objects.filter(character_sheet_id=sheet.pk, installed=True).select_related(
            "cyberware", "parent", "parent__cyberware"
        )
    )
    return _effective_body_from_counts(natural, _name_counter(instances))


def get_cyberware_initiative_bonus(character: Any) -> int:
    """Flat initiative modifiers from cyberware (e.g. Kerenzikov +2)."""
    counts = _name_counter(iter_installed_instances(character))
    bonus = 0
    if counts.get("kerenzikov", 0) > 0:
        bonus += 2
    return bonus


def get_subdermal_armor_sp(character: Any, location: Optional[str] = None) -> int:
    """
    Highest *current* implanted body-armor SP for this hit location (Skin Weave / Sycust / Subdermal).
    Prefer get_total_armor_sp_for_location (worn + implants) for full protection.
    """
    try:
        from world.cyberware.implanted_armor import get_implanted_layers_for_location

        layers = get_implanted_layers_for_location(character, location)
        return max((sp for _, sp in layers), default=0)
    except Exception:
        pass
    counts = _name_counter(iter_installed_instances(character))
    sp = 0
    if counts.get("subdermal armor", 0) > 0:
        sp = max(sp, 11)
    if counts.get("skin weave", 0) > 0 or counts.get("sycust fleshweave", 0) > 0:
        sp = max(sp, 7)
    loc = str(location or "body").lower()
    if loc not in ("body", "head"):
        return 0
    return sp


def _fashion_style_bonus(instances: List[Any], counts: Counter) -> int:
    bonus = 0
    # 3+ Light Tattoos OR substitute one Lead's Turn-On Show-Off Nails for one tattoo
    tattoos = counts.get("light tattoo", 0)
    nails = counts.get("lead's turn-on show-off nails", 0)
    effective_tattoo_points = tattoos + (1 if nails > 0 else 0)
    if effective_tattoo_points >= 3:
        bonus += 2
    return bonus

def _fashion_personal_grooming_bonus(instances: List[Any], counts: Counter) -> int:
    bonus = 0
    if counts.get("chemskin", 0) > 0 and counts.get("techhair", 0) > 0:
        bonus += 2
    return bonus

def _superchrome_style_bonus(counts: Counter) -> int:
    if counts.get("superchrome covering", 0) > 0:
        return 2
    return 0


def _limb_root_for_instance(inst: Any) -> Optional[int]:
    """Walk parents to the owning cyberarm/cyberleg instance id."""
    seen = set()
    cur = inst
    while cur is not None:
        iid = getattr(cur, "id", None)
        if iid in seen:
            break
        if iid is not None:
            seen.add(iid)
        cwname = _norm(getattr(getattr(cur, "cyberware", None), "name", ""))
        if cwname in _CYBERLIMB_ROOT_NAMES:
            return iid
        cur = getattr(cur, "parent", None)
    return None


def _extra_jointed_contortion_bonus(instances: List[Any]) -> int:
    limb_roots: set = set()
    for inst in instances:
        if _norm(getattr(inst.cyberware, "name", "")) != "extra-jointed cyberlimb upgrade":
            continue
        root_id = _limb_root_for_instance(inst)
        if root_id is not None:
            limb_roots.add(root_id)
    n = min(4, len(limb_roots))
    return n * 2


def _parse_skill_key(skill_key: str) -> Tuple[str, Optional[str]]:
    sk = (skill_key or "").strip().lower()
    if "(" in sk and ")" in sk:
        idx = sk.index("(")
        base = sk[:idx].strip()
        inst = sk[idx + 1 : sk.rindex(")")].strip()
        return base, inst or None
    return sk, None


def get_cyberware_skill_bonus(character: Any, skill_key: str) -> int:
    """
    Total skill bonus from cyberware for this skill_key
    (e.g. 'human_perception', 'play_instrument(singing)').
    """
    if not character:
        return 0
    instances = iter_installed_instances(character)
    counts = _name_counter(instances)
    base, instance = _parse_skill_key(skill_key)
    bonus = 0

    # --- Once-only skill bundles ---
    if counts.get("voice stress analyzer", 0) > 0:
        if base == "human_perception":
            bonus += 2
        if base == "interrogation":
            bonus += 2

    if counts.get("toxin binders", 0) > 0 and base == "resist_torture_drugs":
        bonus += 2

    if counts.get("medscanner", 0) > 0:
        if base == "first_aid":
            bonus += 2
        if base == "paramedic":
            bonus += 2

    if counts.get("techscanner", 0) > 0:
        tech_skills = (
            "basic_tech",
            "cybertech",
            "land_vehicle_tech",
            "sea_vehicle_tech",
            "air_vehicle_tech",
            "electronics_security_tech",
            "weaponstech",
        )
        if base in tech_skills:
            bonus += 2

    if counts.get("audiovox", 0) > 0:
        if base == "play_instrument" and instance and instance.lower() in ("singing", "sing"):
            bonus += 2
    # Personal Grooming: Chemskin + Techhair +2
    if base == "personal_grooming":
        bonus += _fashion_personal_grooming_bonus(instances, counts)
    # Style: Fashion + Superchrome +2
    if base == "style":
        bonus += _fashion_style_bonus(instances, counts) + _superchrome_style_bonus(counts)
    # Contortionist: Extra-Jointed (+2 per qualifying limb, max 4 limbs); Sycust Cyberspine +1
    if base == "contortionist":
        bonus += _extra_jointed_contortion_bonus(instances)
        if counts.get("sycust cyberspine", 0) > 0:
            bonus += 1

    # Raven MicroWaldo: Surgery +1 (Medtech only)
    if counts.get("raven microcybernetics microwaldo", 0) > 0 and base == "surgery":
        if (getattr(character.db, "role", None) or "").strip() == "Medtech":
            bonus += 1

    return bonus
