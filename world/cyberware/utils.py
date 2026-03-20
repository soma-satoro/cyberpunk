from evennia import Command, logger
from world.cyberware.models import Cyberware
from .cyberware_data import CYBERWARE_DATA_LIST

# Limb types that mount under borg ware (counted as "Cyberarm x3" etc.)
LIMB_TYPE_NAMES = frozenset({"cyberarm", "neo-soviet cyberarm", "cyberleg", "cybereye"})
# Borg ware that has child limbs or options (displayed as parent (child1, child2, ...))
BORG_WARE_NAMES = frozenset({"artificial shoulder mount", "multioptic mount", "sensor array", "cyberaudio suite", "discount cyberaudio suite"})


def format_cyberware_for_display(installed_instances, with_roots=False):
    """
    Build cyberware display from installed instances.

    If with_roots=False: returns compact list of strings for character sheet:
      "Cybereye (Paired, Anti-Dazzle, Color Shift)", "Light Tattoo", ...

    If with_roots=True: returns expanded table rows, list of (display_name, type, humanity_loss):
      ("Cyberaudio Suite", "Cyberaudio", 7),
      (" - Amplified Hearing", "Cyberaudio", 3),
      ("Cybereye", "Cyberoptics", 7),
      (" - Paired Cybereye", "Cyberoptics", 7),
      (" - Dartgun", "Cyberoptics", 3),
    Each piece on its own line; children indented with " - ".
    """
    if not installed_instances:
        return []
    installed = list(installed_instances)
    by_id = {i.id: i for i in installed}
    paired_second_ids = {i.id for i in installed if getattr(i, "paired_with_id", None)}
    roots = [i for i in installed if i.parent_id is None and i.id not in paired_second_ids]

    if not with_roots:
        # Compact format for character sheet
        result = []
        for root in roots:
            cw = root.cyberware
            name = (cw.name or "").strip()
            name_lower = name.lower()
            member_ids = {root.id}
            for inst in installed:
                if getattr(inst, "paired_with_id", None) == root.id:
                    member_ids.add(inst.id)
            to_process = list(member_ids)
            while to_process:
                pid = to_process.pop()
                for inst in installed:
                    if inst.parent_id == pid and inst.id not in member_ids:
                        member_ids.add(inst.id)
                        to_process.append(inst.id)
            members = [by_id[i] for i in member_ids if i in by_id]
            is_paired = any(getattr(m, "paired_with_id", None) for m in members)
            if name_lower in BORG_WARE_NAMES:
                limb_counts = {}
                options = []
                for m in members:
                    if m.id == root.id:
                        continue
                    cname = (m.cyberware.name or "").strip().lower()
                    if cname in LIMB_TYPE_NAMES:
                        limb_counts[m.cyberware.name] = limb_counts.get(m.cyberware.name, 0) + 1
                    else:
                        opt = m.cyberware.name
                        if getattr(m, "popup_weapon_name", None):
                            opt = f"{opt} ({m.popup_weapon_name})"
                        options.append(opt)
                parts = [f"{ln} x{c}" if c > 1 else ln for ln, c in sorted(limb_counts.items())]
                parts.extend(options)
            else:
                # Count duplicate options (like Chipware Socket x4, Advanced Skill Chip x3)
                opt_counts = {}
                for m in members:
                    if m.id == root.id:
                        continue
                    if m.parent_id not in member_ids:
                        continue
                    opt = m.cyberware.name
                    if getattr(m, "popup_weapon_name", None):
                        opt = f"{opt} ({m.popup_weapon_name})"
                    opt_counts[opt] = opt_counts.get(opt, 0) + 1
                parts = ["Paired"] if is_paired else []
                parts.extend(f"{opt} x{c}" if c > 1 else opt for opt, c in sorted(opt_counts.items()))
            result.append(f"{name} ({', '.join(parts)})" if parts else name)
        # Consolidate duplicate root entries (e.g. Light Tattoo x6)
        counts = {}
        for item in result:
            counts[item] = counts.get(item, 0) + 1
        seen = set()
        final = []
        for item in result:
            if item in seen:
                continue
            seen.add(item)
            n = counts[item]
            final.append(f"{item} x{n}" if n > 1 else item)
        return final

    # Expanded format: each piece on its own line with indentation
    result = []
    for root in roots:
        cw = root.cyberware
        name = (cw.name or "").strip()
        name_lower = name.lower()

        member_ids = {root.id}
        for inst in installed:
            if getattr(inst, "paired_with_id", None) == root.id:
                member_ids.add(inst.id)
        to_process = list(member_ids)
        while to_process:
            pid = to_process.pop()
            for inst in installed:
                if inst.parent_id == pid and inst.id not in member_ids:
                    member_ids.add(inst.id)
                    to_process.append(inst.id)

        members = [by_id[i] for i in member_ids if i in by_id]
        paired_second = next((m for m in members if getattr(m, "paired_with_id", None) == root.id), None)
        children = [m for m in members if m.id != root.id and m.id != (paired_second.id if paired_second else None)]

        # Root line
        result.append((name, cw.type, cw.humanity_loss))

        # Paired second (e.g. " - Cybereye" at same indent as other options)
        if paired_second:
            pname = paired_second.cyberware.name or ""
            if pname.lower().startswith("paired "):
                pname = pname[7:].strip()
            result.append((f" - {pname}", paired_second.cyberware.type, paired_second.cyberware.humanity_loss))

        # Children: options, limbs under borg ware, etc.
        for m in children:
            opt_name = m.cyberware.name
            if getattr(m, "popup_weapon_name", None):
                opt_name = f"{opt_name} ({m.popup_weapon_name})"
            result.append((f" - {opt_name}", m.cyberware.type, m.cyberware.humanity_loss))

    return result


# Category order for display (matches get_slot_summaries keys)
CYBERWARE_DISPLAY_CATEGORIES = [
    "Fashionware",
    "Neural Link Options",
    "Chipware",
    "Cybereye Options",
    "Cyberaudio Options",
    "Cyberarm Options",
    "Cyberleg Options",
    "Bodyware",
]

# Foundational roots (parents) processed first so they appear before their options.
# Order matches category flow: Neural, Cybereye, Cyberaudio, Cyberarm, Cyberleg, etc.
_FOUNDATIONAL_ROOT_ORDER = (
    "neural link", "neuroport",
    "cybereye", "sponsored cybereye", "kiroshi monovision", "cyclops international bug eye",
    "cyberaudio suite", "discount cyberaudio suite",
    "cyberarm", "neo-soviet cyberarm",
    "cyberleg",
    "chipware socket", "budget chipware socket",
    "multioptic mount", "sensor array", "artificial shoulder mount",
)

# Foundational roots processed first (so parents appear before options in each category)
_FOUNDATIONAL_ROOT_ORDER = (
    "neural link", "neuroport",
    "cybereye", "sponsored cybereye", "kiroshi monovision", "cyclops international bug eye",
    "cyberaudio suite", "discount cyberaudio suite",
    "cyberarm", "neo-soviet cyberarm",
    "cyberleg",
    "chipware socket", "budget chipware socket",
    "multioptic mount", "sensor array", "artificial shoulder mount",
)

# Foundational roots (parents) processed first so they appear before their options in each category.
# Order matches category flow; options/children get higher index (processed later).
_ROOT_DISPLAY_PRIORITY = {
    "neural link": 0,
    "neuroport": 0,
    "chipware socket": 1,
    "budget chipware socket": 1,
    "cybereye": 2,
    "sponsored cybereye": 2,
    "kiroshi monovision": 2,
    "cyclops international bug eye": 2,
    "cyberaudio suite": 3,
    "discount cyberaudio suite": 3,
    "cyberarm": 4,
    "neo-soviet cyberarm": 4,
    "cyberleg": 5,
    "multioptic mount": 6,
    "sensor array": 7,
    "artificial shoulder mount": 8,
}

# Foundational roots processed first so parents appear before options in each category.
# Lower index = earlier. Options (not in this set) are processed last.
_FOUNDATIONAL_ROOT_ORDER = [
    "neural link", "neuroport",
    "cybereye", "sponsored cybereye", "kiroshi monovision", "cyclops international bug eye",
    "cyberaudio suite", "discount cyberaudio suite",
    "cyberarm", "neo-soviet cyberarm",
    "cyberleg",
    "chipware socket", "budget chipware socket",
    "multioptic mount", "sensor array", "artificial shoulder mount",
]

# Foundational roots: process before options so parents appear before children in each category
FOUNDATIONAL_ROOT_NAMES = frozenset({
    "neural link", "neuroport", "cybereye", "sponsored cybereye",
    "kiroshi monovision", "cyclops international bug eye",
    "cyberarm", "neo-soviet cyberarm", "cyberleg",
    "cyberaudio suite", "discount cyberaudio suite",
    "chipware socket", "budget chipware socket",
    "multioptic mount", "sensor array", "artificial shoulder mount",
})


def _rebuild_cybereye_option_parent_groups(installed, roots, root_sort_key_fn):
    """
    Build Cybereye Options parent_groups from DB parent_id (no first-fit redistribution).

    The main loop can miss nested mount eyes or attach inconsistently; this pass is
    authoritative: every foundation eye instance gets exactly the option rows for
    children where parent_id == that eye.
    """
    from world.cyberware.validation import (
        get_child_slot_cost,
        _CYBEROPTIC_FOUNDATION_LOWERS,
    )

    def norm(s):
        return (s or "").strip().lower()

    foundation = frozenset(_CYBEROPTIC_FOUNDATION_LOWERS)
    result = []

    def opt_row(m):
        opt_name = m.cyberware.name or ""
        if getattr(m, "popup_weapon_name", None):
            opt_name = f"{opt_name} ({m.popup_weapon_name})"
        row = (opt_name, m.cyberware.type, m.cyberware.humanity_loss)
        cost = get_child_slot_cost(m.cyberware)
        if cost:
            row = row + (cost,)
        return row

    def options_for_eye(eye_id):
        rows = []
        for m in installed:
            if m.parent_id != eye_id:
                continue
            rows.append(opt_row(m))
        return rows

    for root in sorted(roots, key=root_sort_key_fn):
        rname = norm(root.cyberware.name)
        if rname == "multioptic mount":
            child_eyes = [
                m
                for m in installed
                if m.parent_id == root.id and norm(m.cyberware.name) in foundation
            ]
            child_eyes.sort(key=lambda x: x.id)
            result.append((root, [(e, options_for_eye(e.id)) for e in child_eyes]))
        elif rname in foundation:
            result.append((root, options_for_eye(root.id)))
            paired = next(
                (i for i in installed if getattr(i, "paired_with_id", None) == root.id),
                None,
            )
            if paired and norm(paired.cyberware.name) in foundation:
                result.append((paired, options_for_eye(paired.id)))
    return result


def _rebuild_cyberarm_option_parent_groups(installed, roots, root_sort_key_fn):
    """
    Build Cyberarm Options from DB parent_id (each arm / mount-hosted arm shows its own children).
    """
    from world.cyberware.validation import (
        get_child_slot_cost,
        ARM_LIMB_HOST_LOWERS,
    )

    def norm(s):
        return (s or "").strip().lower()

    result = []

    def opt_row(m):
        opt_name = m.cyberware.name or ""
        if getattr(m, "popup_weapon_name", None):
            opt_name = f"{opt_name} ({m.popup_weapon_name})"
        row = (opt_name, m.cyberware.type, m.cyberware.humanity_loss)
        cost = get_child_slot_cost(m.cyberware)
        if cost:
            row = row + (cost,)
        return row

    def options_for_limb(limb_id):
        rows = []
        for m in installed:
            if m.parent_id != limb_id:
                continue
            rows.append(opt_row(m))
        return rows

    hosts = frozenset(ARM_LIMB_HOST_LOWERS)
    for root in sorted(roots, key=root_sort_key_fn):
        rname = norm(root.cyberware.name)
        if rname == "artificial shoulder mount":
            child_limbs = [
                m
                for m in installed
                if m.parent_id == root.id and norm(m.cyberware.name) in hosts
            ]
            child_limbs.sort(key=lambda x: x.id)
            result.append((root, [(e, options_for_limb(e.id)) for e in child_limbs]))
        elif rname in hosts:
            result.append((root, options_for_limb(root.id)))
            paired = next(
                (i for i in installed if getattr(i, "paired_with_id", None) == root.id),
                None,
            )
            if paired and norm(paired.cyberware.name) in hosts:
                result.append((paired, options_for_limb(paired.id)))
    return result


def _rebuild_cyberleg_option_parent_groups(installed, roots, root_sort_key_fn):
    """
    Build Cyberleg Options from DB parent_id (standard legs, Rocklin, Romanova, etc.).
    """
    from world.cyberware.validation import (
        get_child_slot_cost,
        LEG_LIMB_HOST_LOWERS,
    )

    def norm(s):
        return (s or "").strip().lower()

    result = []

    def opt_row(m):
        opt_name = m.cyberware.name or ""
        if getattr(m, "popup_weapon_name", None):
            opt_name = f"{opt_name} ({m.popup_weapon_name})"
        row = (opt_name, m.cyberware.type, m.cyberware.humanity_loss)
        cost = get_child_slot_cost(m.cyberware)
        if cost:
            row = row + (cost,)
        return row

    def options_for_limb(limb_id):
        rows = []
        for m in installed:
            if m.parent_id != limb_id:
                continue
            rows.append(opt_row(m))
        return rows

    hosts = frozenset(LEG_LIMB_HOST_LOWERS)
    for root in sorted(roots, key=root_sort_key_fn):
        rname = norm(root.cyberware.name)
        if rname in hosts:
            result.append((root, options_for_limb(root.id)))
            paired = next(
                (i for i in installed if getattr(i, "paired_with_id", None) == root.id),
                None,
            )
            if paired and norm(paired.cyberware.name) in hosts:
                result.append((paired, options_for_limb(paired.id)))
    return result


def cascade_uninstall_installed_descendants(root_instance, char_sheet):
    """
    Uninstall every *installed* descendant of ``root_instance`` (not ``root`` itself).

    Used when staff (or systems) uninstall a parent piece (Cybereye, MultiOptic Mount,
    Cyberarm, suite, etc.) so options and nested limbs are not left pointing at the
    uninstalled parent with ``installed=True``.

    - Sets ``installed=False``, ``active=False``, ``parent=None`` on each descendant.
    - Merges humanity into ``char_sheet.uninstalled_cyberware_hl`` when present (same
      policy as ``uninstallcyberware``).

    Returns the number of descendant instances uninstalled.
    """
    from world.inventory.models import CyberwareInstance

    # Collect all descendant PKs (breadth-first over parent_id links)
    frontier = [root_instance.id]
    desc_pks = []
    seen = {root_instance.id}
    idx = 0
    while idx < len(frontier):
        pid = frontier[idx]
        idx += 1
        for cid in CyberwareInstance.objects.filter(parent_id=pid).values_list(
            "pk", flat=True
        ):
            if cid not in seen:
                seen.add(cid)
                desc_pks.append(cid)
                frontier.append(cid)

    if not desc_pks:
        return 0

    uhl_delta = {}
    count = 0
    qs = CyberwareInstance.objects.filter(
        pk__in=desc_pks, installed=True
    ).select_related("cyberware")
    for inst in qs:
        cw = inst.cyberware
        hl = int(getattr(cw, "humanity_loss", 0) or 0)
        if hl > 0:
            uhl_delta[cw.name] = uhl_delta.get(cw.name, 0) + hl
        inst.installed = False
        inst.active = False
        inst.parent = None
        inst.save()
        count += 1

    if uhl_delta and char_sheet is not None and hasattr(
        char_sheet, "uninstalled_cyberware_hl"
    ):
        uhl = getattr(char_sheet, "uninstalled_cyberware_hl", None) or {}
        if not isinstance(uhl, dict):
            uhl = {}
        for name, amt in uhl_delta.items():
            uhl[name] = uhl.get(name, 0) + amt
        char_sheet.uninstalled_cyberware_hl = uhl
        char_sheet.save(skip_recalculation=True)

    return count


def _get_instance_category(inst, parent_name=None):
    """
    Assign a CyberwareInstance to a display category based on its type and parent.
    Returns category label or None for "Borgware/Other".
    """
    def _norm(s):
        return (s or "").strip().lower()

    cw = inst.cyberware
    name = _norm(cw.name)
    cw_type = _norm(getattr(cw, "type", ""))

    if cw_type == "fashionware":
        return "Fashionware"
    if name in ("neural link", "neuroport"):
        return "Neural Link Options"
    if parent_name and parent_name in ("neural link", "neuroport"):
        return "Neural Link Options"
    if name in ("chipware socket", "budget chipware socket"):
        return "Chipware"
    if parent_name and parent_name in ("chipware socket", "budget chipware socket"):
        return "Chipware"
    if name in ("cybereye", "sponsored cybereye", "kiroshi monovision", "cyclops international bug eye"):
        return "Cybereye Options"
    if parent_name and (parent_name in ("cybereye", "sponsored cybereye", "kiroshi monovision", "cyclops international bug eye") or "multioptic" in (parent_name or "")):
        return "Cybereye Options"
    if name in ("cyberaudio suite", "discount cyberaudio suite"):
        return "Cyberaudio Options"
    if parent_name and (parent_name in ("cyberaudio suite", "discount cyberaudio suite") or "sensor array" in (parent_name or "")):
        return "Cyberaudio Options"
    if name in ("cyberarm", "neo-soviet cyberarm"):
        return "Cyberarm Options"
    if name == "artificial shoulder mount":
        return "Cyberarm Options"
    if parent_name and (parent_name in ("cyberarm", "neo-soviet cyberarm") or "artificial shoulder" in (parent_name or "")):
        return "Cyberarm Options"
    if name == "multioptic mount":
        return "Cybereye Options"
    if name == "sensor array":
        return "Cyberaudio Options"
    from world.cyberware.validation import LEG_LIMB_HOST_LOWERS

    if name in LEG_LIMB_HOST_LOWERS:
        return "Cyberleg Options"
    if parent_name and parent_name in LEG_LIMB_HOST_LOWERS:
        return "Cyberleg Options"
    if cw_type in ("internal body", "external body") or cw_type.startswith("internal body") or cw_type.startswith("external body"):
        return "Bodyware"
    return "Borgware/Other"


def format_cyberware_by_category(installed_instances, character_sheet):
    """
    Build cyberware display grouped by category with slots used/remaining.
    For limb/socket categories (Cybereye, Cyberarm, Cyberleg, Chipware, Neural Link, Cyberaudio),
    groups items under each parent with per-parent slot usage [used/total].
    """
    from world.cyberware.validation import (
        get_slot_summaries,
        get_parent_instance_slot_usage,
        get_child_slot_cost,
    )

    if not installed_instances:
        return ""

    installed = list(installed_instances)
    by_id = {i.id: i for i in installed}
    paired_second_ids = {i.id for i in installed if getattr(i, "paired_with_id", None)}
    roots = [i for i in installed if i.parent_id is None and i.id not in paired_second_ids]

    # Process foundational roots first so parents appear before options in each category
    _foundational_order = (
        "neural link", "neuroport", "chipware socket", "budget chipware socket",
        "cybereye", "sponsored cybereye", "kiroshi monovision", "cyclops international bug eye",
        "cyberaudio suite", "discount cyberaudio suite",
        "cyberarm", "neo-soviet cyberarm",
        "cyberleg",
        "multioptic mount", "sensor array", "artificial shoulder mount",
    )

    def _root_sort_key(r):
        name = _norm(getattr(r.cyberware, "name", ""))
        try:
            return _foundational_order.index(name)
        except ValueError:
            return 999

    roots = sorted(roots, key=_root_sort_key)

    # Categories that show per-parent slot usage (group items under each limb/eye/socket)
    PARENT_GROUPED_CATEGORIES = frozenset({
        "Neural Link Options", "Chipware", "Cybereye Options",
        "Cyberaudio Options", "Cyberarm Options", "Cyberleg Options",
    })

    # Build structure: for parent-grouped categories, group by parent instance.
    # rows_by_category[cat] = list of (parent_inst or None, list of (display, type, hl))
    # For flat categories, parent_inst is None and we have a single list.
    rows_by_category = {cat: [] for cat in CYBERWARE_DISPLAY_CATEGORIES}
    rows_by_category["Borgware/Other"] = []
    # For parent-grouped: {cat: [(parent_inst, children_list), ...]}
    parent_groups = {cat: [] for cat in PARENT_GROUPED_CATEGORIES}

    def _parent_display_name(inst, paired_second=None):
        name = inst.cyberware.name or ""
        if name.lower().startswith("paired "):
            name = name[7:].strip()
        return name

    def _child_display_name(m):
        opt_name = m.cyberware.name
        if getattr(m, "popup_weapon_name", None):
            opt_name = f"{opt_name} ({m.popup_weapon_name})"
        return opt_name

    # Collect parent instances per category for limb/socket grouping
    # Include borgware (Artificial Shoulder Mount, MultiOptic Mount, Sensor Array) so they're added as parents
    limb_parent_names = {
        "Neural Link Options": ("neural link", "neuroport"),
        "Chipware": ("chipware socket", "budget chipware socket"),
        "Cybereye Options": ("cybereye", "sponsored cybereye", "kiroshi monovision", "cyclops international bug eye", "multioptic mount"),
        "Cyberaudio Options": ("cyberaudio suite", "discount cyberaudio suite", "sensor array"),
        "Cyberarm Options": ("cyberarm", "neo-soviet cyberarm", "artificial shoulder mount"),
        "Cyberleg Options": (
            "cyberleg",
            "rocklin augmentics skydrivers",
            "wyzard technologies romanova cyberlegs",
        ),
    }
    # Limbs that are children of borgware - don't add as top-level parents (they're shown nested under the borgware)
    BORGWARE_PARENT_NAMES = frozenset({"artificial shoulder mount", "multioptic mount", "sensor array"})
    # Limb types that mount under borgware (for secondary parenting: show options nested under each limb)
    BORGWARE_LIMB_NAMES = frozenset({
        "cybereye", "sponsored cybereye", "kiroshi monovision", "cyclops international bug eye",
        "cyberarm", "neo-soviet cyberarm", "cyberleg",
        "cyberaudio suite", "discount cyberaudio suite",
    })

    for root in roots:
        member_ids = {root.id}
        for inst in installed:
            if getattr(inst, "paired_with_id", None) == root.id:
                member_ids.add(inst.id)
        to_process = list(member_ids)
        while to_process:
            pid = to_process.pop()
            for inst in installed:
                if inst.parent_id == pid and inst.id not in member_ids:
                    member_ids.add(inst.id)
                    to_process.append(inst.id)

        members = [by_id[i] for i in member_ids if i in by_id]
        paired_second = next((m for m in members if getattr(m, "paired_with_id", None) == root.id), None)

        # Order: root first, paired second, then children
        ordered_members = [m for m in members if m.id == root.id]
        if paired_second:
            ordered_members.append(paired_second)
        children = [m for m in members if m.id != root.id and (not paired_second or m.id != paired_second.id)]
        child_order = ["cybereye", "sponsored cybereye", "cyberarm", "neo-soviet cyberarm", "cyberleg"]
        children.sort(key=lambda m: (
            0 if _norm(getattr(m.cyberware, "name", "")) in child_order else 1,
            getattr(m.cyberware, "name", ""),
        ))
        ordered_members.extend(children)

        for m in ordered_members:
            parent_inst = getattr(m, "parent", None)
            pname = _norm(parent_inst.cyberware.name) if parent_inst and getattr(parent_inst, "cyberware", None) else None
            cat = _get_instance_category(m, pname)

            if m.id == root.id:
                opt_name = m.cyberware.name
                is_parent = True
            elif paired_second and m.id == paired_second.id:
                opt_name = _parent_display_name(m, paired_second)
                is_parent = True
            else:
                opt_name = _child_display_name(m)
                is_parent = False

            if cat in PARENT_GROUPED_CATEGORIES:
                m_name = _norm(m.cyberware.name)
                # Chipware Socket is a display parent in Chipware (even though it's a child of Neural Link)
                if cat == "Chipware" and m_name in ("chipware socket", "budget chipware socket"):
                    slot_info = get_parent_instance_slot_usage(m)
                    if slot_info and not any(p.id == m.id for p, _ in parent_groups[cat]):
                        parent_groups[cat].append((m, []))
                elif is_parent:
                    # This instance is a display parent (Cybereye, Cyberarm, etc.)
                    if any(m_name == p for p in limb_parent_names.get(cat, ())):
                        slot_info = get_parent_instance_slot_usage(m)
                        if slot_info and not any(p.id == m.id for p, _ in parent_groups[cat]):
                            parent_groups[cat].append((m, []))
                else:
                    # Child: attach to its parent
                    if parent_inst and parent_inst.id in by_id:
                        pname_lower = _norm(parent_inst.cyberware.name)
                        m_name_lower = _norm(m.cyberware.name)
                        # Limb under borgware: store (instance, []) for nested display + add as option container
                        is_limb_under_borgware = (
                            pname_lower in BORGWARE_PARENT_NAMES
                            and m_name_lower in BORGWARE_LIMB_NAMES
                            and cat in ("Cybereye Options", "Cyberarm Options", "Cyberleg Options", "Cyberaudio Options")
                        )
                        if is_limb_under_borgware:
                            for i, (p, ch_list) in enumerate(parent_groups[cat]):
                                if p.id == parent_inst.id:
                                    ch_list.append((m, []))  # limb instance, options attach to nested sub_list
                                    break
                            else:
                                parent_groups[cat].append((parent_inst, [(m, [])]))
                            # Do not add (m, []) as a top-level row — that duplicates the limb (e.g. Neo-Soviet
                            # under Artificial Shoulder Mount). Options must attach under the nested tuple only.
                        else:
                            # Regular option child
                            slot_cost = get_child_slot_cost(m.cyberware) if cat in ("Cybereye Options", "Cyberleg Options", "Cyberarm Options", "Cyberaudio Options") else 0
                            row = (opt_name, m.cyberware.type, m.cyberware.humanity_loss)
                            if slot_cost:
                                row = row + (slot_cost,)
                            placed = False
                            for i, (p, ch_list) in enumerate(parent_groups[cat]):
                                if p.id == parent_inst.id:
                                    ch_list.append(row)
                                    placed = True
                                    break
                            if not placed:
                                # Parent limb may only exist nested under borgware (no duplicate parent row).
                                for p, ch_list in parent_groups[cat]:
                                    if _norm(p.cyberware.name) not in BORGWARE_PARENT_NAMES:
                                        continue
                                    for item in ch_list:
                                        if not (
                                            isinstance(item, tuple)
                                            and len(item) == 2
                                            and hasattr(item[0], "id")
                                        ):
                                            continue
                                        limb_inst, sub_list = item
                                        if limb_inst.id == parent_inst.id:
                                            sub_list.append(row)
                                            placed = True
                                            break
                                    if placed:
                                        break
                            if not placed:
                                parent_groups[cat].append((parent_inst, [row]))
            else:
                # Flat category
                indent = "" if is_parent else " - "
                display = f"{indent}{opt_name}"
                if cat not in rows_by_category:
                    rows_by_category[cat] = []
                rows_by_category[cat].append((display, m.cyberware.type, m.cyberware.humanity_loss))

    # Second pass: for Chipware, parents (sockets) may appear as Neural Link children.
    # Ensure all Chipware Socket instances that have chips are in parent_groups["Chipware"]
    # and that sockets without chips also appear (empty)
    chipware_sockets = [i for i in installed if _norm(i.cyberware.name) in ("chipware socket", "budget chipware socket")]
    existing_socket_ids = {p.id for p, _ in parent_groups["Chipware"]}
    for s in chipware_sockets:
        if s.id not in existing_socket_ids:
            parent_groups["Chipware"].append((s, []))
    # Sort Chipware by socket order (keep insertion order; sockets from Neural Link iteration come first)
    parent_groups["Chipware"].sort(key=lambda x: (x[0].id,))

    # Ensure Neural Link Options, Cybereye, Cyberarm, Cyberleg, Cyberaudio have parents
    # when we have children but parent came from a different root
    def _ensure_parents_have_entries(cat, parent_names):
        seen = {(p.id, p.cyberware_id) for p, _ in parent_groups[cat]}
        for inst in installed:
            # Skip limbs that are children of borgware (shown under Mount/etc, not as top-level parents)
            parent_inst = getattr(inst, "parent", None)
            if parent_inst and _norm(parent_inst.cyberware.name) in BORGWARE_PARENT_NAMES:
                continue
            if _norm(inst.cyberware.name) in parent_names and inst.id not in {x[0].id for x in parent_groups[cat]}:
                slot_info = get_parent_instance_slot_usage(inst)
                if slot_info and inst.id not in seen:
                    parent_groups[cat].append((inst, []))
                    seen.add((inst.id, inst.cyberware_id))

    for cat, names in limb_parent_names.items():
        if cat == "Chipware":
            continue
        _ensure_parents_have_entries(cat, names)

    # Cybereye Options: rebuild from DB parenting so MultiOptic eyes and paired eyes
    # all show their real children (first pass + _ensure_parents skips mount-hosted eyes).
    parent_groups["Cybereye Options"] = _rebuild_cybereye_option_parent_groups(
        installed, roots, _root_sort_key
    )
    parent_groups["Cyberarm Options"] = _rebuild_cyberarm_option_parent_groups(
        installed, roots, _root_sort_key
    )
    parent_groups["Cyberleg Options"] = _rebuild_cyberleg_option_parent_groups(
        installed, roots, _root_sort_key
    )

    # Redistribute options across available parents (Cyberaudio only; limbs/eyes use DB parents)
    # so each eye/leg/arm/suite shows at most its capacity, not all options under one
    OPTION_CONTAINER_NAMES = {
        "Cyberaudio Options": frozenset({"cyberaudio suite", "discount cyberaudio suite", "sensor array"}),
    }

    # Limb instances that are children of borgware (for nested display)
    BORGWARE_LIMB_IDS = {}

    def _redistribute_options(cat):
        if cat not in OPTION_CONTAINER_NAMES:
            return
        container_names = OPTION_CONTAINER_NAMES[cat]
        borgware_parent_names = BORGWARE_PARENT_NAMES
        entries = parent_groups[cat]
        option_containers = []
        borgware_nested_containers = []  # (limb_inst, ch_list, total) - shown under borgware
        borgware_entries = []
        all_options = []
        for p, ch_list in entries:
            pname = _norm(p.cyberware.name)
            # Skip limbs under borgware - they're handled via borgware's ch_list
            parent_inst = getattr(p, "parent", None)
            is_limb_under_borgware = (
                parent_inst
                and _norm(parent_inst.cyberware.name) in borgware_parent_names
                and pname in container_names
            )
            if pname in container_names and not is_limb_under_borgware:
                slot_info = get_parent_instance_slot_usage(p)
                total = slot_info[1] if slot_info else 4
                option_containers.append((p, [], total))
                for row in ch_list:
                    # Skip Sensor Array hardware (parent, not an option) when redistributing
                    if cat == "Cyberaudio Options" and isinstance(row, (tuple, list)) and len(row) >= 1:
                        if _norm(str(row[0])) == "sensor array":
                            continue
                    all_options.append(row)
            elif pname in container_names and is_limb_under_borgware:
                # Duplicate list row should not appear after nested-only attachment; if present, feed
                # options into redistribution only — limb displays under borgware, not as a root.
                for row in ch_list:
                    if isinstance(row, tuple) and len(row) == 2 and hasattr(row[0], "cyberware"):
                        continue
                    if cat == "Cyberaudio Options" and isinstance(row, (tuple, list)) and len(row) >= 1:
                        if _norm(str(row[0])) == "sensor array":
                            continue
                    all_options.append(row)
            elif pname in borgware_parent_names:
                # Borgware - ch_list has (limb_inst, []) or legacy rows
                limb_children = []
                for item in ch_list:
                    if isinstance(item, tuple) and len(item) == 2:
                        limb_inst, sub_list = item
                        if hasattr(limb_inst, "cyberware") and hasattr(limb_inst, "id"):
                            limb_name = _norm(limb_inst.cyberware.name)
                            if limb_name in container_names:
                                slot_info = get_parent_instance_slot_usage(limb_inst)
                                total = slot_info[1] if slot_info else 4
                                borgware_nested_containers.append((limb_inst, [], total))
                                BORGWARE_LIMB_IDS[limb_inst.id] = limb_inst
                                for row in sub_list:
                                    if isinstance(row, (list, tuple)) and len(row) >= 3:
                                        all_options.append(row)
                            limb_children.append((limb_inst, sub_list))
                        else:
                            limb_children.append(item)
                    else:
                        limb_children.append(item)
                borgware_entries.append((p, limb_children))
            else:
                borgware_entries.append((p, ch_list))

        # For Cyberaudio, ensure suite(s) are filled before Sensor Array
        if cat == "Cyberaudio Options" and option_containers:
            def _cyberaudio_container_order(item):
                p, _, _ = item
                return 1 if _norm(p.cyberware.name) == "sensor array" else 0
            option_containers.sort(key=_cyberaudio_container_order)

        # Distribute options across ALL containers (top-level + borgware-nested limbs)
        all_containers = option_containers + borgware_nested_containers
        container_used = [0] * len(all_containers)
        for row in all_options:
            cost = row[3] if len(row) == 4 else 1
            placed = False
            for i, (p, ch_list, total) in enumerate(all_containers):
                if container_used[i] + cost <= total:
                    ch_list.append(row)
                    container_used[i] += cost
                    placed = True
                    break
            if not placed and all_containers:
                best_i = min(range(len(all_containers)), key=lambda i: container_used[i])
                all_containers[best_i][1].append(row)
                container_used[best_i] += cost

        # Build borgware entries with redistributed opts for each limb
        limb_id_to_opts = {p.id: ch_list for p, ch_list, _ in borgware_nested_containers}
        borgware_with_opts = []
        for p, limb_children in borgware_entries:
            updated_children = []
            for item in limb_children:
                if isinstance(item, tuple) and len(item) == 2:
                    limb_inst, _ = item
                    if hasattr(limb_inst, "id"):
                        opts = limb_id_to_opts.get(limb_inst.id, [])
                        updated_children.append((limb_inst, opts))
                    else:
                        updated_children.append(item)
                else:
                    updated_children.append(item)
            borgware_with_opts.append((p, updated_children))

        rebuilt = [(p, ch_list) for p, ch_list, _ in option_containers]
        parent_groups[cat] = rebuilt + borgware_with_opts

    for cat in ("Cyberaudio Options",):
        _redistribute_options(cat)

    slot_summaries = get_slot_summaries(character_sheet)

    lines = []
    for cat in CYBERWARE_DISPLAY_CATEGORIES + ["Borgware/Other"]:
        slot_info = slot_summaries.get(cat, {})
        used = slot_info.get("used", 0)
        total = slot_info.get("total", 0)
        if total > 0:
            rem = slot_info.get("remaining", total - used)
            header_line = f"|y{cat}|n [{used}/{total}, {rem} left]"
        else:
            header_line = f"|y{cat}|n"

        # Consistent column layout (~80 char): name 36, type 14, hl 3, slots 7
        NAME_W, TYPE_W, HL_W, SLOT_W = 36, 14, 3, 7
        if cat in PARENT_GROUPED_CATEGORIES and parent_groups[cat]:
            lines.append(header_line)
            for parent_inst, children in parent_groups[cat]:
                pname_norm = _norm(parent_inst.cyberware.name)
                is_borgware = pname_norm in BORGWARE_PARENT_NAMES
                slot_usage = get_parent_instance_slot_usage(parent_inst)
                pname = _parent_display_name(parent_inst) or parent_inst.cyberware.name
                cw_type = str(parent_inst.cyberware.type or "")[:TYPE_W]
                hl = parent_inst.cyberware.humanity_loss or 0
                if slot_usage:
                    u, t = slot_usage
                    # Use displayed children for slot count - options may be redistributed across containers
                    # so DB parent_id can differ from displayed placement (e.g. Sensor Array)
                    if cat in ("Cybereye Options", "Cyberleg Options", "Cyberarm Options", "Cyberaudio Options"):
                        disp_used = sum(
                            (row[3] if len(row) == 4 else 1) for row in children
                            if not (isinstance(row, tuple) and len(row) == 2 and hasattr(row[0], "cyberware"))
                        )
                        # Show real option slot sum (can exceed capacity if DB is wrong or legacy data)
                        u = disp_used if disp_used else u
                    else:
                        u = min(u, t)
                    sc = "|r" if u > t else "|c"
                    slot_str = f"  {sc}[{u}/{t}]|n"  # 7 visible chars to match SLOT_W
                else:
                    slot_str = " " * SLOT_W
                lines.append(f"  |w{pname[:NAME_W]:<{NAME_W}}|n {cw_type:<{TYPE_W}} {hl:>{HL_W}}{slot_str}")
                CHILD_NAME_W = 33  # 5 ("   - ") + 33 = 38, matches parent 2 + 36
                for item in children:
                    if isinstance(item, tuple) and len(item) == 2 and hasattr(item[0], "cyberware"):
                        # Limb under borgware: (limb_inst, opts) - secondary parenting
                        limb_inst, opts = item
                        limb_name = limb_inst.cyberware.name or ""
                        limb_type = str(limb_inst.cyberware.type or "")[:TYPE_W]
                        limb_hl = limb_inst.cyberware.humanity_loss or 0
                        limb_slot = get_parent_instance_slot_usage(limb_inst)
                        if limb_slot:
                            lu, lt = limb_slot
                            disp_used = sum(
                                (r[3] if len(r) == 4 else 1) for r in opts
                            )
                            lu = disp_used
                            lsc = "|r" if lu > lt else "|c"
                            limb_slot_str = f"  {lsc}[{lu}/{lt}]|n"
                        else:
                            limb_slot_str = " " * SLOT_W
                        lines.append(f"   |w- {limb_name[:CHILD_NAME_W]:<{CHILD_NAME_W}}|n {limb_type:<{TYPE_W}} {limb_hl:>{HL_W}}{limb_slot_str}")
                        for row in opts:
                            disp, rt, rhl = row[0], row[1], row[2]
                            rt = str(rt)[:TYPE_W]
                            lines.append(f"      |w- {disp[:CHILD_NAME_W]:<{CHILD_NAME_W}}|n {rt:<{TYPE_W}} {rhl:>{HL_W}}")
                    else:
                        # Regular option row
                        disp, rt, rhl = item[0], item[1], item[2]
                        rt = str(rt)[:TYPE_W]
                        lines.append(f"   |w- {disp[:CHILD_NAME_W]:<{CHILD_NAME_W}}|n {rt:<{TYPE_W}} {rhl:>{HL_W}}")
            lines.append("")
        else:
            rows = rows_by_category.get(cat, [])
            if not rows:
                continue
            lines.append(header_line)
            for display_name, cw_type, humanity_loss in rows:
                cw_type = str(cw_type)[:TYPE_W]
                slot_str = " " * SLOT_W  # Reserve space for alignment (no slots on flat rows)
                lines.append(f"  |w{display_name[:NAME_W]:<{NAME_W}}|n {cw_type:<{TYPE_W}} {humanity_loss or 0:>{HL_W}}{slot_str}")
            lines.append("")

    return "\n".join(lines)


def _norm(s):
    """Normalize for category lookup."""
    return (s or "").strip().lower()


def populate_cyberware():
    existing_names = set(Cyberware.objects.values_list("name", flat=True))
    created = 0
    for cw_data in CYBERWARE_DATA_LIST:
        if cw_data["name"] in existing_names:
            continue
        defaults = {
            "type": cw_data["type"],
            "slots": cw_data["slots"],
            "humanity_loss": cw_data["humanity_loss"],
            "cost": cw_data["cost"],
            "is_weapon": cw_data.get("is_weapon", False),
            "description": cw_data["description"],
        }
        if defaults["is_weapon"]:
            defaults["rate_of_fire"] = cw_data.get("rate_of_fire", 1)
            defaults["damage_dice"] = cw_data.get("damage_dice", 0)
            defaults["damage_die_type"] = cw_data.get("damage_die_type", 6)
        if cw_data.get("skill_chip_target"):
            defaults["skill_chip_target"] = cw_data["skill_chip_target"]
        obj, _ = Cyberware.objects.get_or_create(name=cw_data["name"], defaults=defaults)
        created += 1
        existing_names.add(cw_data["name"])
    print(f"Populated {len(CYBERWARE_DATA_LIST)} cyberware items ({created} new).")

def check_cyberware_requirements(character, cyberware):
    print("DEBUG: This is the modified check_cyberware_requirements function")
    
    try:
        cybereye_count = character.inventory.cyberware.filter(cyberware__name__iexact="Cybereye", installed=True).count()
        logger.msg(f"Debug: Current Cybereye count: {cybereye_count}")
    except Exception as e:
        logger.msg(f"Debug: Error counting Cybereyes: {str(e)}")
        return False, f"Error checking Cybereye count: {str(e)}"

    # Check for MultiOptic Mount requirement
    if cyberware.name.lower() == "cybereye":
        logger.msg(f"Debug: Checking Cybereye installation. Current count: {cybereye_count}")
        if cybereye_count >= 2:
            logger.msg("Debug: Checking for MultiOptic Mount")
            try:
                multioptic_mount = character.inventory.cyberware.filter(cyberware__name__iexact="MultiOptic Mount", installed=True).exists()
                logger.msg(f"Debug: MultiOptic Mount exists: {multioptic_mount}")
            except Exception as e:
                logger.msg(f"Debug: Error checking MultiOptic Mount: {str(e)}")
                return False, f"Error checking MultiOptic Mount: {str(e)}"
            
            if not multioptic_mount:
                logger.msg("Debug: MultiOptic Mount required but not found")
                return False, "You need to install a MultiOptic Mount to have more than two Cybereyes."
        else:
            logger.msg(f"Debug: Installing Cybereye {cybereye_count + 1}")

    # Check other requirements
    if cyberware.requirements:
        logger.msg(f"Debug: Checking requirements: {cyberware.requirements}")
        requirements = cyberware.requirements.split(',')
        for req in requirements:
            req = req.strip().lower()
            logger.msg(f"Debug: Checking requirement: {req}")
            if req == "cybereye":
                if cybereye_count < 2:
                    logger.msg("Debug: Not enough Cybereyes for requirement")
                    return False, f"You need to install two Cybereyes for {cyberware.name}. You currently have {cybereye_count}."

    if cyberware.name.lower() in ["image enhance", "low light-ir-uv", "virtuality"]:
        logger.msg(f"Debug: Checking special case for {cyberware.name}")
        if cybereye_count < 2:
            logger.msg("Debug: Not enough Cybereyes for special case")
            return False, f"You need to install two Cybereyes for {cyberware.name}. You currently have {cybereye_count}."

    logger.msg("Debug: All checks passed")
    return True, ""

def calculate_humanity_loss(sheet):
    from world.inventory.models import CyberwareInstance
    installed_cyberware = CyberwareInstance.objects.filter(character_sheet=sheet, installed=True)
    total_cyberware_hl = sum(cw.cyberware.humanity_loss for cw in installed_cyberware)
    trauma_hl = getattr(sheet, "trauma_humanity_loss", 0) or 0

    # Preserve staff-set humanity: use current humanity + old losses as base, then apply new losses
    old_total_hl = getattr(sheet, "total_cyberware_humanity_loss", 0) or 0
    humanity_base = sheet.humanity + old_total_hl + trauma_hl
    new_humanity = max(0, min(sheet.empathy * 10, humanity_base - total_cyberware_hl - trauma_hl))

    # Update humanity and empathy (only reduce empathy when humanity is overwhelmed by cyberware)
    sheet.humanity = new_humanity
    if sheet.empathy * 10 <= total_cyberware_hl + trauma_hl:
        sheet.empathy = max(1, new_humanity // 10)
    
    sheet.total_cyberware_humanity_loss = total_cyberware_hl
    sheet.save()

    return new_humanity