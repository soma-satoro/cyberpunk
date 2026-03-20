# world/cyberware/validation.py
"""
Cyberpunk RED cyberware parenting and slot validation.

Only certain cyberware can act as parents. Invalid parent-child combinations
are rejected with clear error messages.
"""

from world.cyberware.cyberware_data import CYBERWARE_DATA
from world.inventory.models import CyberwareInstance


# Limbs that accept generic cyberlimb options (covering, reinforced, extra-jointed, etc.)
_CYBERLIMB_OPTION_PARENTS = (
    "cyberarm",
    "neo-soviet cyberarm",
    "cyberleg",
    "rocklin augmentics skydrivers",
    "wyzard technologies romanova cyberlegs",
)

# Host instances for Cyberarm / Cyberleg Options display & balancing (includes alt legs).
ARM_LIMB_HOST_LOWERS = frozenset({"cyberarm", "neo-soviet cyberarm"})
LEG_LIMB_HOST_LOWERS = frozenset(
    {
        "cyberleg",
        "rocklin augmentics skydrivers",
        "wyzard technologies romanova cyberlegs",
    }
)

# Foundation cybereye catalog names (options + coverings may use these as parents).
_CYBEROPTIC_FOUNDATION_LOWERS = (
    "cybereye",
    "sponsored cybereye",
    "kiroshi monovision",
    "cyclops international bug eye",
)
FOUNDATION_EYE_NAME_LOWERS = frozenset(_CYBEROPTIC_FOUNDATION_LOWERS)

# Cosmetic coverings can mount on cybereyes too (house rule). RAW Reinforced/Hardened Shielding = limbs only (below).
_CYBERLIMB_AND_EYE_DECOR_PARENTS = _CYBERLIMB_OPTION_PARENTS + _CYBEROPTIC_FOUNDATION_LOWERS

# --- Valid parent types (can have children) ---

# Parents that provide option slots. Format: name_lower -> (base_slots, accepts_extra_from_borgware)
# Neuroport provides Neural Link (5 slots) + other features
VALID_PARENT_NAMES = frozenset({
    *_CYBEROPTIC_FOUNDATION_LOWERS,
    "cyberarm",
    "neo-soviet cyberarm",
    "cyberaudio suite",
    "discount cyberaudio suite",
    "cyberleg",
    "rocklin augmentics skydrivers",
    "wyzard technologies romanova cyberlegs",
    "chipware socket",
    "budget chipware socket",
    "neural link",
    "neuroport",
    # Borgware that parents limbs/suites:
    "multioptic mount",      # up to 5 additional cybereyes
    "sensor array",          # +5 cyberaudio options, parents cyberaudio suite
    "artificial shoulder mount",  # up to 2 additional cyberarms
})

# Which parent types can have which child types. Child name -> allowed parent name patterns.
# A child can only be parented to a valid parent that matches its requirements.
CHILD_REQUIRES_PARENT = {
    # Neuralware options -> Neural Link or Neuroport
    "kerenzikov": ["neural link", "neuroport"],
    "braindance recorder": ["neural link", "neuroport"],
    "interface plugs": ["neural link", "neuroport"],
    "sandevistan": ["neural link", "neuroport"],
    "reflex co-processor": ["neural link", "neuroport"],
    "berserk implant": ["neural link", "neuroport"],
    # Chipware Socket is child of Neural Link
    "chipware socket": ["neural link", "neuroport"],
    "budget chipware socket": ["neural link", "neuroport"],
    # Chipware -> Chipware Socket
    "chemical analyzer": ["chipware socket", "budget chipware socket"],
    "memory chip": ["chipware socket", "budget chipware socket"],
    "olfactory boost": ["chipware socket", "budget chipware socket"],
    "pain editor": ["chipware socket", "budget chipware socket"],
    "basic skill chip": ["chipware socket", "budget chipware socket"],
    "advanced skill chip": ["chipware socket", "budget chipware socket"],
    "tactile boost": ["chipware socket", "budget chipware socket"],
    "explicit memory stimulator": ["chipware socket", "budget chipware socket"],
    "poser chip": ["chipware socket", "budget chipware socket"],
    # Subdermal Grip takes Neural Link slot (special case)
    "subdermal grip": ["neural link", "neuroport"],
    # Cybereye options (any foundation eye type may host options)
    "chyron": _CYBEROPTIC_FOUNDATION_LOWERS,
    "anti-dazzle": _CYBEROPTIC_FOUNDATION_LOWERS,
    "color shift": _CYBEROPTIC_FOUNDATION_LOWERS,
    "dartgun": _CYBEROPTIC_FOUNDATION_LOWERS,
    "image enhance": _CYBEROPTIC_FOUNDATION_LOWERS,
    "low light-ir-uv": _CYBEROPTIC_FOUNDATION_LOWERS,
    "microoptics": _CYBEROPTIC_FOUNDATION_LOWERS,
    "microvideo": _CYBEROPTIC_FOUNDATION_LOWERS,
    "radiation detector": _CYBEROPTIC_FOUNDATION_LOWERS,
    "targeting scope": _CYBEROPTIC_FOUNDATION_LOWERS,
    "teleoptics": _CYBEROPTIC_FOUNDATION_LOWERS,
    "virtuality": _CYBEROPTIC_FOUNDATION_LOWERS,
    "hardened cybereye casing": _CYBEROPTIC_FOUNDATION_LOWERS,
    # Cyberaudio options (can parent to suite or sensor array when suite is full)
    "amplified hearing": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "audio recorder": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "bug detector": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "homing tracer": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "internal agent": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "level damper": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "radio communicator": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "radio scanner and music player": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "radar detector": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "scrambler descrambler": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    "voice stress analyzer": ["cyberaudio suite", "discount cyberaudio suite", "sensor array"],
    # Sensor Array is child of Cyberaudio Suite
    "sensor array": ["cyberaudio suite", "discount cyberaudio suite"],
    # Cyberarm options
    "big knucks": ["cyberarm", "neo-soviet cyberarm"],
    "cyberdeck": ["cyberarm", "neo-soviet cyberarm"],
    "grapple hand": ["cyberarm", "neo-soviet cyberarm"],
    "medscanner": ["cyberarm", "neo-soviet cyberarm"],
    "popup grenade launcher": ["cyberarm", "neo-soviet cyberarm"],
    "popup melee weapon": ["cyberarm", "neo-soviet cyberarm"],
    "popup shield": ["cyberarm", "neo-soviet cyberarm"],
    "popup ranged weapon": ["cyberarm", "neo-soviet cyberarm"],
    "quick change mount": ["cyberarm", "neo-soviet cyberarm"],
    "shoulder cam": ["cyberarm", "neo-soviet cyberarm"],
    "techscanner": ["cyberarm", "neo-soviet cyberarm"],
    "wolvers": ["cyberarm", "neo-soviet cyberarm"],
    "flashbulb": ["cyberarm", "neo-soviet cyberarm"],
    "integrated cyberdeck upgrade": ["cyberarm", "neo-soviet cyberarm"],
    "popup net launcher": ["cyberarm", "neo-soviet cyberarm"],
    "popup shotgun": ["cyberarm", "neo-soviet cyberarm"],
    "standard hand": ["cyberarm", "neo-soviet cyberarm"],
    "standard foot": ["cyberleg"],
    "modular finger cyberhand": ["cyberarm", "neo-soviet cyberarm"],
    "dynalar modular finger enthusiast cyberhand": ["cyberarm", "neo-soviet cyberarm"],
    "gorilla arm": ["cyberarm", "neo-soviet cyberarm"],
    "mantis blade": ["cyberarm", "neo-soviet cyberarm"],
    "monowire": ["cyberarm", "neo-soviet cyberarm"],
    "projectile launch system": ["cyberarm", "neo-soviet cyberarm"],
    "cyberpillow": ["cyberarm", "neo-soviet cyberarm"],
    "holo projector palm": ["cyberarm", "neo-soviet cyberarm"],
    "personalpak kibblewarmer": ["cyberarm", "neo-soviet cyberarm"],
    "pursuit security inc. personal shredder": ["cyberarm", "neo-soviet cyberarm"],
    "chainripp": ["cyberarm", "neo-soviet cyberarm"],
    "cybermatrix gang jazzler": ["cyberarm", "neo-soviet cyberarm"],
    "psiberstuff watch-man": ["cyberarm", "neo-soviet cyberarm"],
    "raven microcybernetics microwaldo": ["cyberarm", "neo-soviet cyberarm"],
    "pursuit security inc gas jet": ["cyberarm", "neo-soviet cyberarm"],
    "cyberscanner, integrated": ["cyberarm", "neo-soviet cyberarm"],
    # Cyberleg options
    "grip foot": ["cyberleg"],
    "jump booster": ["cyberleg"],
    "skate foot": ["cyberleg"],
    "talon foot": ["cyberleg"],
    "web foot": ["cyberleg"],
    "rocklin augmentics skydrivers": ["cyberleg"],
    "perfectfit cyberfoot": ["cyberleg"],
    # Cyberlimb options (RAW: Reinforced + Hardened Shielding = arms/legs only)
    "hardened shielding": _CYBERLIMB_OPTION_PARENTS,
    "reinforced cyberlimb upgrade": _CYBERLIMB_OPTION_PARENTS,
    # Cosmetic coverings: still allowed on cybereyes (house)
    "plastic covering": _CYBERLIMB_AND_EYE_DECOR_PARENTS,
    "realskinn covering": _CYBERLIMB_AND_EYE_DECOR_PARENTS,
    "superchrome covering": _CYBERLIMB_AND_EYE_DECOR_PARENTS,
    "extra-jointed cyberlimb upgrade": _CYBERLIMB_OPTION_PARENTS,
    "sponsored covering": _CYBERLIMB_AND_EYE_DECOR_PARENTS,
    # Cybereye/arm/leg as children of borgware
    "cybereye": ["multioptic mount"],
    "sponsored cybereye": ["multioptic mount"],
    "cyberarm": ["artificial shoulder mount"],
    "neo-soviet cyberarm": ["artificial shoulder mount"],
    "cyberaudio suite": ["sensor array"],
    "discount cyberaudio suite": ["sensor array"],
}

# Slots per parent (base capacity). Borgware adds more.
PARENT_SLOTS = {
    "cybereye": 3,
    "cyberarm": 4,
    "neo-soviet cyberarm": 3,
    "cyberaudio suite": 3,
    "discount cyberaudio suite": 1,
    "cyberleg": 3,
    "rocklin augmentics skydrivers": 2,
    "wyzard technologies romanova cyberlegs": 3,
    "chipware socket": 1,
    "budget chipware socket": 1,
    "neural link": 5,
    "neuroport": 5,
    "multioptic mount": 5,   # additional cybereyes
    "sensor array": 5,       # additional cyberaudio options
    "artificial shoulder mount": 2,  # additional cyberarms
}

# Items that use 0 slots (coverings, etc.)
ZERO_SLOT_ITEMS = frozenset({
    "plastic covering", "realskinn covering", "superchrome covering", "sponsored covering",
    "standard hand", "standard foot",
})

# Bodyware: 7 slots total for Internal Body + External Body (excluding fashion, cyberarm, cyberleg, etc.)
BODYWARE_LIMIT = 7
BODYWARE_TYPES = frozenset({"internal body", "external body"})

# Pairable foundational items (Cybereye, Cyberarm, Cyberleg)
PAIRABLE_NAMES = frozenset(
    {"cybereye", "sponsored cybereye", "cyberarm", "neo-soviet cyberarm", "cyberleg"}
)

# Items that can be purchased multiple times (slot limits enforced by category)
# Chipware sockets, fashionware (7 slots total), Interface Plugs, Self-ICE (max 3)
MULTIPLE_ALLOWED = frozenset({
    "chipware socket",
    "budget chipware socket",
    "interface plugs",
    "self-ice",
    "grafted muscle and bone lace",
    # One per cyberlimb; slot/validation limits apply (max 4 limbs, 1 per limb).
    "extra-jointed cyberlimb upgrade",
    # Paired cyberarms: max two installs, must parent to paired Cyberarms (see validate_parent_child).
    "gorilla arm",
    "mantis blade",
    # At most one per eligible parent (limb-only for shielding/reinforced; see check_limb_decor_capacity).
    "hardened shielding",
    "plastic covering",
    "realskinn covering",
    "superchrome covering",
    "reinforced cyberlimb upgrade",
    "hardened cybereye casing",
    "color shift",
    # One per appropriate limb; per-parent limits apply.
    "standard hand",
    "standard foot",
    "modular finger cyberhand",
})

# Fashionware type - all share 7 slots; allow multiples
FASHIONWARE_TYPE = "fashionware"

# Self-ICE limit per character (Neural Link/Neuroport)
SELF_ICE_LIMIT = 3

# Paired Cyberarm weapons: buy two max; must parent to paired Cyberarms (same model both sides).
PAIRED_CYBERARM_WEAPON_OPTIONS = frozenset({"gorilla arm", "mantis blade"})

# Coverings: at most one per eligible parent (each Cyberarm, Cyberleg, or Cybereye counts).
LIMB_AND_EYE_DECOR_NAMES = frozenset({
    "superchrome covering",
    "realskinn covering",
    "plastic covering",
})
# RAW: Reinforced + Hardened Shielding = cyberlimb only (one per arm/leg).
LIMB_ONLY_DECOR_NAMES = frozenset({"hardened shielding", "reinforced cyberlimb upgrade"})
# Eye-only cosmetics / casings: cap install count to foundation eye count (one per eye in practice).
EYE_ONLY_DECOR_NAMES = frozenset({"hardened cybereye casing", "color shift"})

_CYBEREYE_INSTANCE_NAMES = [
    "Cybereye",
    "Sponsored Cybereye",
    "Kiroshi MonoVision",
    "Cyclops International Bug Eye",
]

# Installed limb rows that count as cyberleg hosts (for decor / optional cap math)
_CYBERLEG_INSTANCE_NAMES = [
    "Cyberleg",
    "Rocklin Augmentics Skydrivers",
    "Wyzard Technologies Romanova Cyberlegs",
]

# Cyberarm/leg options that "can be the only cyberware in a meat arm/leg".
# ONE such item can be installed without a Cyberarm/Cyberleg. For a second,
# you must purchase the limb first, then parent the existing option to it.
# Meat-arm rules: check_has_required_parent / check_cyberlimb_exclusive_option_capacity.
# If parented, get_valid_parents_for_child uses CHILD_REQUIRES_PARENT when present
# (e.g. Subdermal Grip); otherwise arm-only solo options resolve to Cyberarm hosts.
SOLO_ARM_OPTIONS = frozenset({
    "big knucks",
    "rippers",
    "scratchers",
    "slice n dice",
    "wolvers",
    "rocklin augmentics quick digits",
    "subdermal grip",
    "holo projector palm",
    "cybermatrix gang jazzler",
})

SOLO_LEG_OPTIONS = frozenset({
    "talon foot",
    "perfectfit cyberfoot",
})


def allows_multiples(cyberware):
    """Return True if this cyberware can be purchased multiple times (slot limits enforced)."""
    name = _norm(getattr(cyberware, "name", ""))
    cw_type = _norm(getattr(cyberware, "type", ""))
    if name in MULTIPLE_ALLOWED:
        return True
    if cw_type == FASHIONWARE_TYPE:
        return True
    return False


def select_child_instance_for_parenting(child_queryset, parent_inst, *, allow_uninstalled=False):
    """
    When several instances share the same cyberware name (e.g. Extra-Jointed),
    choose which row to attach to parent_inst.

    Preference:
      1) Unparented + installed (player flow).
      2) If allow_uninstalled, unparented + not installed (e.g. staff parentcyberware).
      3) None if every instance is already parented to another limb (do not steal).

    If something is already linked to parent_inst, returns that instance with status
    'already'.

    Returns:
        (CyberwareInstance | None, status: 'assign' | 'already' | 'all_busy')
    """
    qs = child_queryset.order_by("id")
    on_target = qs.filter(parent_id=parent_inst.id).first()

    def _first_free_installed():
        return qs.filter(installed=True, parent__isnull=True).first()

    free = _first_free_installed()
    if not free and allow_uninstalled:
        free = qs.filter(installed=False, parent__isnull=True).first()
    if free:
        return free, "assign"
    if on_target:
        return on_target, "already"
    return None, "all_busy"


def is_solo_arm_option(cyberware):
    """Return True if this cyberware can be the only cyberware in a meat arm."""
    return _norm(getattr(cyberware, "name", "")) in SOLO_ARM_OPTIONS


def is_solo_leg_option(cyberware):
    """Return True if this cyberware can be the only cyberware in a meat leg."""
    return _norm(getattr(cyberware, "name", "")) in SOLO_LEG_OPTIONS


def _count_solo_arm_options_unparented(character_sheet):
    """Count installed solo arm options that have no parent (installed as only cyberware in meat arm)."""
    count = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        parent__isnull=True,
    ).select_related("cyberware"):
        if _norm(inst.cyberware.name) in SOLO_ARM_OPTIONS:
            count += 1
    return count


def _count_solo_leg_options_unparented(character_sheet):
    """Count installed solo leg options that have no parent (installed as only cyberware in meat leg)."""
    count = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        parent__isnull=True,
    ).select_related("cyberware"):
        if _norm(inst.cyberware.name) in SOLO_LEG_OPTIONS:
            count += 1
    return count


def check_foundation_eye_exclusive_option_capacity(character_sheet, cyberware):
    """
    For catalog items whose valid parents are *only* foundation Cybereyes, require
    that at least one installed eye can accept this option (per-eye option slots).
    Covers buy/cyberware when not using parent=.../Cybereye.
    """
    name = _norm(getattr(cyberware, "name", ""))
    if name in FOUNDATION_EYE_NAME_LOWERS:
        return True, ""
    vp = get_valid_parents_for_child(cyberware)
    if not vp:
        return True, ""
    eye_hosts = frozenset(_CYBEROPTIC_FOUNDATION_LOWERS)
    if not all(p in eye_hosts for p in vp):
        return True, ""
    candidates = list(
        CyberwareInstance.objects.filter(
            character_sheet=character_sheet,
            installed=True,
            cyberware__name__in=_CYBEREYE_INSTANCE_NAMES,
        ).select_related("cyberware")
    )
    if not candidates:
        return False, (
            f"You need an installed Cybereye (or compatible eye) before buying {cyberware.name}."
        )
    for inst in candidates:
        ok, _ = validate_parent_for_new_child(inst, cyberware)
        if ok:
            return True, ""
    _, err = validate_parent_for_new_child(candidates[0], cyberware)
    return False, err or (
        f"No Cybereye has enough free option slots for {cyberware.name}. "
        "Remove an option, add another eye, or free a slot before buying more."
    )


def check_cyberlimb_exclusive_option_capacity(character_sheet, cyberware):
    """
    For items whose valid parents are *only* cyberlimb hosts (arms/legs from
    _CYBERLIMB_OPTION_PARENTS — no cybereyes), ensure at least one installed
    limb can accept this option (per-limb slots). Covers coverings, shielding,
    reinforced, Extra-Jointed, Standard Hand/Foot, Modular Finger, etc. when
    bought without a disambiguated parent.
    """
    name = _norm(getattr(cyberware, "name", ""))
    if name in ARM_LIMB_HOST_LOWERS or name in LEG_LIMB_HOST_LOWERS:
        return True, ""
    vp = get_valid_parents_for_child(cyberware)
    if not vp:
        return True, ""
    limb_hosts = frozenset(_CYBERLIMB_OPTION_PARENTS)
    if not all(p in limb_hosts for p in vp):
        return True, ""

    # Meat arm: one solo arm option may install with no Cyberarm (see SOLO_ARM_OPTIONS).
    if name in SOLO_ARM_OPTIONS:
        has_arm = CyberwareInstance.objects.filter(
            character_sheet=character_sheet,
            installed=True,
            cyberware__name__in=["Cyberarm", "Neo-Soviet Cyberarm"],
        ).exists()
        if not has_arm and _count_solo_arm_options_unparented(character_sheet) == 0:
            return True, ""

    tried = []
    for inst in CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
    ).select_related("cyberware"):
        if not is_valid_parent(inst.cyberware):
            continue
        if get_parent_instance_slot_usage(inst) is None:
            continue
        pn = _norm(inst.cyberware.name)
        if not parent_name_matches_child_valid_hosts(pn, vp):
            continue
        tried.append(inst)
        ok, _ = validate_parent_for_new_child(inst, cyberware)
        if ok:
            return True, ""
    if not tried:
        return False, (
            f"You need an installed Cyberarm or Cyberleg (or compatible limb) "
            f"before buying {cyberware.name}."
        )
    _, err = validate_parent_for_new_child(tried[0], cyberware)
    return False, err or (
        f"No limb has enough free option slots for {cyberware.name}. "
        "Remove an option or add a limb before buying more."
    )


def check_self_ice_limit(character_sheet):
    """Check Self-ICE limit (max 3). Returns (success, error_message)."""
    count = CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        cyberware__name__iexact="Self-ICE",
    ).count()
    if count >= SELF_ICE_LIMIT:
        return False, (
            f"You can only install up to {SELF_ICE_LIMIT} Self-ICE. "
            f"You currently have {count} installed."
        )
    return True, ""


def _norm(s):
    return (s or "").strip().lower()


def get_cyberware_data(cyberware):
    """Get entry from CYBERWARE_DATA by name."""
    name = getattr(cyberware, "name", None) or ""
    return CYBERWARE_DATA.get(name, {})


def get_required_parents(cyberware):
    """
    Get list of valid parent names from cyberware data.
    Returns list of parent name alternatives (any one satisfies).
    """
    data = get_cyberware_data(cyberware)
    req = data.get("requirements")
    if not req:
        return []
    # Handle "X or Y" or "X, Y" or "Cyberarm or Cyberleg"
    req_str = (req or "").strip()
    if not req_str:
        return []
    # Split on " or " or ", "
    parts = req_str.replace(" or ", "|").replace(", ", "|").split("|")
    return [_norm(p) for p in parts if p.strip()]


def get_child_slot_cost(child_cyberware):
    """
    Get slot cost for a child item. Uses 'slots' from cyberware model or data.
    0 for zero-slot items.
    """
    name = _norm(getattr(child_cyberware, "name", ""))
    if name in ZERO_SLOT_ITEMS:
        return 0
    return max(1, getattr(child_cyberware, "slots", 1))


def get_parent_instance_slot_usage(parent_inst):
    """
    Get (used_slots, total_slots) for a single parent instance.
    Used for per-parent display in cyberware list.
    Returns (used, total) or None if parent type has no slot limits.
    """
    parent_cw = parent_inst.cyberware
    parent_name = _norm(parent_cw.name)

    # Total slots for this parent
    if parent_name in ("chipware socket", "budget chipware socket"):
        total = 1
    elif parent_name == "cyclops international bug eye":
        total = 5
    elif parent_name == "kiroshi monovision":
        total = 3
    elif parent_name == "sponsored cybereye":
        total = 2
    elif parent_name in (
        "cybereye",
        "cyberarm",
        "neo-soviet cyberarm",
        "cyberleg",
        "rocklin augmentics skydrivers",
        "wyzard technologies romanova cyberlegs",
        "cyberaudio suite",
        "discount cyberaudio suite",
        "neural link",
        "neuroport",
        "multioptic mount",
        "sensor array",
        "artificial shoulder mount",
    ):
        total = PARENT_SLOTS.get(parent_name, 4)
    else:
        return None

    # Used slots: sum of child costs for this parent
    used = 0
    for c in parent_inst.children.all():
        used += get_child_slot_cost(c.cyberware)
    return used, total


def is_valid_parent(parent_cyberware):
    """Return True if this cyberware can be a parent."""
    name = _norm(getattr(parent_cyberware, "name", ""))
    return name in VALID_PARENT_NAMES


def get_valid_parents_for_child(child_cyberware):
    """
    Get allowed parent names for a child. Uses CHILD_REQUIRES_PARENT and
    requirements from data.

    Solo arm options (SOLO_ARM_OPTIONS) may install with no Cyberarm (meat arm);
    if they are parented, hosts are still only Cyberarm / Neo-Soviet Cyberarm.
    Entries also in CHILD_REQUIRES_PARENT (e.g. Subdermal Grip -> Neural Link) keep
    their explicit rule set.
    """
    name = _norm(getattr(child_cyberware, "name", ""))
    if name in CHILD_REQUIRES_PARENT:
        return CHILD_REQUIRES_PARENT[name]
    if name in SOLO_ARM_OPTIONS:
        return ["cyberarm", "neo-soviet cyberarm"]
    # Fallback to requirements from data
    data = get_cyberware_data(child_cyberware)
    req = data.get("requirements")
    if req:
        parts = req.replace(" or ", "|").replace(", ", "|").split("|")
        return [_norm(p) for p in parts if p.strip()]
    return []


def parent_name_matches_child_valid_hosts(parent_name_norm, valid_parents):
    """
    True if an installed parent's catalog name (normalized) may host this child
    per CHILD_REQUIRES_PARENT / data requirements.

    Expands generic ``cyberleg`` to all cyberleg host types (standard + Rocklin /
    Wyzard legs) and treats arm-only option lists as matching any arm host, so
    capacity checks do not probe irrelevant parents (e.g. Neural Link) and alt
    legs accept leg options like Jump Booster.
    """
    if not valid_parents:
        return True
    if any(
        p in parent_name_norm or parent_name_norm in p
        for p in valid_parents
    ) or parent_name_norm in valid_parents:
        return True
    if "cyberleg" in valid_parents and parent_name_norm in LEG_LIMB_HOST_LOWERS:
        return True
    vp_set = frozenset(valid_parents)
    if vp_set <= ARM_LIMB_HOST_LOWERS and parent_name_norm in ARM_LIMB_HOST_LOWERS:
        return True
    return False


def find_best_cyberaudio_parent(character_sheet, child_cyberware, character=None):
    """
    Find best parent for a cyberaudio option. Tries main Cyberaudio Suite(s) first,
    then Sensor Array if main suite(s) are full. Returns (parent_inst, error_msg).
    """
    from django.db.models import Q
    from world.inventory.models import CyberwareInstance

    char_sheet = getattr(character_sheet, "character_sheet", character_sheet) or character_sheet
    if not char_sheet and not character:
        return None, "No character sheet."

    # Filter installed suites (support both character_sheet and character_object links)
    char_q = Q()
    if char_sheet:
        char_q |= Q(character_sheet=char_sheet)
    if character:
        char_q |= Q(character_object=character)
    if not char_q:
        return None, "No character sheet."
    suite_q = Q(installed=True, cyberware__name__in=["Cyberaudio Suite", "Discount Cyberaudio Suite"]) & char_q
    all_suites = list(CyberwareInstance.objects.filter(suite_q).select_related("cyberware", "parent"))
    main_suites = [s for s in all_suites if not s.parent or _norm(s.parent.cyberware.name) != "sensor array"]

    for cand in main_suites:
        ok, _ = validate_parent_for_new_child(cand, child_cyberware)
        if ok:
            return cand, None

    # 2. Sensor Array (if main suite(s) full)
    sensor_array = CyberwareInstance.objects.filter(
        char_q,
        installed=True,
        cyberware__name__iexact="Sensor Array",
    ).select_related("cyberware").first()
    if sensor_array:
        ok, err = validate_parent_for_new_child(sensor_array, child_cyberware)
        if ok:
            return sensor_array, None
        return None, err

    return None, (
        "No Cyberaudio Suite or Sensor Array with available slots. "
        "Install a Cyberaudio Suite first; Sensor Array adds 5 more option slots when the main suite is full."
    )


def validate_parent_for_new_child(parent_inst, child_cyberware):
    """
    Validate that a new child (not yet instantiated) can be parented to parent.
    Used when buying with parent= or installing. Returns (success, error_message).
    """
    # Create a minimal mock instance for slot validation (we only need .cyberware)
    class _MockChild:
        def __init__(self, cw):
            self.cyberware = cw
    mock_child = _MockChild(child_cyberware)
    return validate_parent_child(parent_inst, mock_child)


def select_balanced_parent_instance(parent_candidates, child_cyberware):
    """
    Pick a parent when multiple installed instances share the same catalog name
    (e.g. several Cybereyes). ``buy/cyberware parent=Option/Cybereye`` used to
    always take ``parent_candidates[0]`` (first DB row), so nothing ever attached
    to MultiOptic or other eyes.

    Chooses a candidate that passes ``validate_parent_for_new_child``, preferring
    fewer installed children, then lower slot usage, then stable pk — so repeated
    purchases spread across eyes/arms/legs instead of stacking on one instance.
    """
    if not parent_candidates:
        return None, "No parent candidates."
    valid = []
    for cand in parent_candidates:
        ok, _ = validate_parent_for_new_child(cand, child_cyberware)
        if ok:
            valid.append(cand)
    if not valid:
        _, err = validate_parent_for_new_child(parent_candidates[0], child_cyberware)
        return None, err or "No parent can accept this option."

    def _sort_key(c):
        n_children = c.children.filter(installed=True).count()
        su = get_parent_instance_slot_usage(c)
        used = su[0] if su else 0
        return (n_children, used, c.pk)

    return min(valid, key=_sort_key), None


def validate_parent_child(parent_inst, child_inst):
    """
    Validate that child can be parented to parent.
    Returns (success: bool, error_message: str)
    """
    parent_cw = parent_inst.cyberware
    child_cw = child_inst.cyberware
    parent_name = _norm(parent_cw.name)
    child_name = _norm(child_cw.name)

    # 1. Parent must be a valid parent type
    if not is_valid_parent(parent_cw):
        return False, (
            f"{parent_cw.name} cannot be a parent. Only foundational slot providers and borg mounts "
            "(Cybereye and variants, Cyberarm, Neo-Soviet Cyberarm, Cyberleg, suites, neural links, chipware sockets, "
            "MultiOptic Mount, Sensor Array, Artificial Shoulder Mount, etc.) can have options attached."
        )

    # 2. Child must list this parent as valid
    valid_parents = get_valid_parents_for_child(child_cw)
    if valid_parents:
        if not parent_name_matches_child_valid_hosts(parent_name, valid_parents):
            return False, (
                f"{child_cw.name} cannot be attached to {parent_cw.name}. "
                f"{child_cw.name} requires: {', or '.join(p.title() for p in valid_parents)}."
            )

    # 2b. Extra-Jointed: at most one per limb instance (RAW: one per cyberlimb)
    if child_name == "extra-jointed cyberlimb upgrade":
        sib_q = parent_inst.children.all()
        child_pk = getattr(child_inst, "id", None)
        if child_pk:
            sib_q = sib_q.exclude(pk=child_pk)
        if sib_q.filter(cyberware__name__iexact="Extra-Jointed Cyberlimb Upgrade").exists():
            return False, (
                f"{parent_cw.name} already has Extra-Jointed Cyberlimb Upgrade. Only one per cyberlimb."
            )

    # 2c. Gorilla Arm / Mantis Blade: paired Cyberarms only, matching weapon on both sides
    ok, msg = validate_paired_cyberarm_weapon_parent(parent_inst, child_inst)
    if not ok:
        return False, msg

    # 3. Slot availability
    ok, msg = validate_slot_availability_for_parent(parent_inst, child_inst)
    if not ok:
        return False, msg

    return True, ""


def find_best_parent_for_cyberaudio_option(character_sheet, child_cyberware):
    """
    Find a parent with available slots for a cyberaudio option.
    Tries main Cyberaudio Suite(s) first (fill to capacity), then Sensor Array.
    Returns (parent_inst, display_name) or (None, None) if no room.
    """
    from world.inventory.models import Inventory
    try:
        inv = character_sheet.inventory
    except (Inventory.DoesNotExist, AttributeError):
        inv = None
    if not inv:
        return None, None
    installed = inv.cyberware.filter(installed=True).select_related("cyberware", "parent", "parent__cyberware")
    # Main Cyberaudio Suites (not under Sensor Array) - try first
    main_suites = [
        i for i in installed
        if _norm(i.cyberware.name) in ("cyberaudio suite", "discount cyberaudio suite")
        and (not i.parent or _norm(i.parent.cyberware.name) != "sensor array")
    ]
    for suite in main_suites:
        ok, _ = validate_parent_for_new_child(suite, child_cyberware)
        if ok:
            return suite, suite.cyberware.name
    # Sensor Array - try if main suites are full
    sensor_arrays = [
        i for i in installed
        if _norm(i.cyberware.name) == "sensor array"
    ]
    for sa in sensor_arrays:
        ok, _ = validate_parent_for_new_child(sa, child_cyberware)
        if ok:
            return sa, sa.cyberware.name
    return None, None


def validate_slot_availability_for_parent(parent_inst, child_inst):
    """
    Check that parent has enough free slots for the child.
    Returns (success, error_message).
    """
    parent_cw = parent_inst.cyberware
    child_cw = child_inst.cyberware
    parent_name = _norm(parent_cw.name)
    child_name = _norm(child_cw.name)
    child_slots = get_child_slot_cost(child_cw)

    if child_slots == 0:
        return True, ""

    # Per-parent limits. (Legacy bug: Cybereye used character-wide totals so a full eye could
    # still accept options while the global pool had room.)
    char_sheet = parent_inst.character_sheet

    if parent_name in FOUNDATION_EYE_NAME_LOWERS:
        slot_info = get_parent_instance_slot_usage(parent_inst)
        if not slot_info:
            return True, ""
        total_slots, used_slots = slot_info[1], slot_info[0]
    elif parent_name in ARM_LIMB_HOST_LOWERS:
        slot_info = get_parent_instance_slot_usage(parent_inst)
        if not slot_info:
            return True, ""
        total_slots, used_slots = slot_info[1], slot_info[0]
    elif parent_name in LEG_LIMB_HOST_LOWERS:
        slot_info = get_parent_instance_slot_usage(parent_inst)
        if not slot_info:
            return True, ""
        total_slots, used_slots = slot_info[1], slot_info[0]
    elif parent_name == "artificial shoulder mount":
        if child_name in ARM_LIMB_HOST_LOWERS:
            max_limbs = PARENT_SLOTS.get("artificial shoulder mount", 2)
            n_arms = sum(
                1
                for c in parent_inst.children.filter(installed=True)
                if _norm(c.cyberware.name) in ARM_LIMB_HOST_LOWERS
            )
            if n_arms >= max_limbs:
                return False, (
                    f"This Artificial Shoulder Mount already holds {max_limbs} additional Cyberarm(s). "
                    "Uninstall one before installing another."
                )
            return True, ""
        slot_info = get_parent_instance_slot_usage(parent_inst)
        if not slot_info:
            return True, ""
        total_slots, used_slots = slot_info[1], slot_info[0]
    elif parent_name == "multioptic mount":
        # Child is almost always a new Cybereye limb under this mount (not an optic option).
        if child_name in FOUNDATION_EYE_NAME_LOWERS:
            max_limbs = PARENT_SLOTS.get("multioptic mount", 5)
            n_eyes = sum(
                1
                for c in parent_inst.children.filter(installed=True)
                if _norm(c.cyberware.name) in FOUNDATION_EYE_NAME_LOWERS
            )
            if n_eyes >= max_limbs:
                return False, (
                    f"This MultiOptic Mount already holds {max_limbs} Cybereyes. "
                    "Uninstall one before installing another."
                )
            return True, ""
        slot_info = get_parent_instance_slot_usage(parent_inst)
        if not slot_info:
            return True, ""
        total_slots, used_slots = slot_info[1], slot_info[0]
    elif parent_name in ("cyberaudio suite", "discount cyberaudio suite", "sensor array"):
        # Per-parent slots: each suite has 3 (or 1 for discount), Sensor Array has 5
        slot_info = get_parent_instance_slot_usage(parent_inst)
        if slot_info:
            total_slots, used_slots = slot_info[1], slot_info[0]
        else:
            total_slots = _count_cyberaudio_slots(char_sheet)
            used_slots = _count_used_cyberaudio_slots(char_sheet)
    elif parent_name in ("neural link", "neuroport"):
        total_slots = _count_neural_slots(char_sheet)
        used_slots = _count_used_neural_slots(char_sheet)
    elif parent_name in ("chipware socket", "budget chipware socket"):
        # Each socket has 1 slot; we're assigning to a specific parent instance
        total_slots = 1
        used_slots = parent_inst.children.count()  # each child uses 1 (except 0-slot)
        for c in parent_inst.children.all():
            if _norm(c.cyberware.name) in ZERO_SLOT_ITEMS:
                used_slots -= 1
    else:
        return True, ""

    available = total_slots - used_slots
    if child_slots > available:
        return False, (
            f"Not enough slots on {parent_cw.name}. Available: {available}, required: {child_slots}. "
            f"Use cyberware command to check your current cyberware and slot usage."
        )
    return True, ""


def _count_cybereye_slots(char_sheet):
    total = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True,
        cyberware__name__in=["Cybereye", "Sponsored Cybereye", "Kiroshi MonoVision", "Cyclops International Bug Eye"]
    ).select_related("cyberware"):
        name = _norm(inst.cyberware.name)
        if name == "cyclops international bug eye":
            total += 5
        elif name == "kiroshi monovision":
            total += 3
        elif name == "sponsored cybereye":
            total += 2
        else:
            total += 3
    # MultiOptic Mount adds 5 cybereyes (15 slots)
    if CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True,
        cyberware__name__iexact="MultiOptic Mount"
    ).exists():
        total += 15  # 5 cybereyes * 3 slots
    return total


def _count_used_cybereye_slots(char_sheet):
    used = 0
    from world.cyberware.cyberware_data import CYBERWARE_DATA
    option_types = {"Cyberoptics", "Cyberarm", "Cyberleg"}  # options can be in different types
    for inst in CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True, parent__isnull=False
    ).select_related("cyberware", "parent"):
        if not inst.parent:
            continue
        pname = _norm(inst.parent.cyberware.name)
        if pname in ("cybereye", "sponsored cybereye", "kiroshi monovision", "cyclops international bug eye") or "multioptic" in pname:
            cost = get_child_slot_cost(inst.cyberware)
            used += cost
    return used


def _count_cyberarm_slots(char_sheet):
    """Count slots from all installed Cyberarms (including those under Artificial Shoulder Mount)."""
    total = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True,
        cyberware__name__in=["Cyberarm", "Neo-Soviet Cyberarm"]
    ).select_related("cyberware"):
        name = _norm(inst.cyberware.name)
        total += PARENT_SLOTS.get(name, 4)
    return total


def _count_used_cyberarm_slots(char_sheet):
    used = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True, parent__isnull=False
    ).select_related("cyberware", "parent"):
        if not inst.parent:
            continue
        pname = _norm(inst.parent.cyberware.name)
        if pname in ("cyberarm", "neo-soviet cyberarm") or "artificial shoulder" in pname:
            cost = get_child_slot_cost(inst.cyberware)
            used += cost
    return used


def _count_cyberaudio_slots(char_sheet):
    total = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True,
        cyberware__name__in=["Cyberaudio Suite", "Discount Cyberaudio Suite"]
    ).select_related("cyberware"):
        name = _norm(inst.cyberware.name)
        total += PARENT_SLOTS.get(name, 3)
    if CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True,
        cyberware__name__iexact="Sensor Array"
    ).exists():
        total += 5
    return total


def _count_used_cyberaudio_slots(char_sheet):
    used = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True, parent__isnull=False
    ).select_related("cyberware", "parent"):
        if not inst.parent:
            continue
        pname = _norm(inst.parent.cyberware.name)
        if pname in ("cyberaudio suite", "discount cyberaudio suite") or "sensor array" in pname:
            cost = get_child_slot_cost(inst.cyberware)
            used += cost
    return used


def _count_cyberleg_slots(char_sheet):
    total = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=char_sheet,
        installed=True,
        cyberware__name__in=_CYBERLEG_INSTANCE_NAMES,
    ).select_related("cyberware"):
        name = _norm(inst.cyberware.name)
        total += PARENT_SLOTS.get(name, 3)
    return total


def _count_used_cyberleg_slots(char_sheet):
    used = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True, parent__isnull=False
    ).select_related("cyberware", "parent"):
        if not inst.parent:
            continue
        pname = _norm(inst.parent.cyberware.name)
        if pname in LEG_LIMB_HOST_LOWERS:
            cost = get_child_slot_cost(inst.cyberware)
            used += cost
    return used


def _count_neural_slots(char_sheet):
    total = 0
    if CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True,
        cyberware__name__iexact="Neural Link"
    ).exists():
        total += 5
    if CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True,
        cyberware__name__iexact="Neuroport"
    ).exists():
        total += 5
    return total


def _count_used_neural_slots(char_sheet):
    used = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=char_sheet, installed=True, parent__isnull=False
    ).select_related("cyberware", "parent"):
        if not inst.parent:
            continue
        pname = _norm(inst.parent.cyberware.name)
        if pname in ("neural link", "neuroport"):
            cost = get_child_slot_cost(inst.cyberware)
            used += cost
    return used


def get_paired_limb_instance(limb_inst):
    """
    Return the other Cybereye / Cyberarm / Cyberleg in a pair, or None.
    Convention: second instance has paired_with -> first; first has related paired_instances.
    """
    if getattr(limb_inst, "paired_with_id", None):
        return limb_inst.paired_with
    paired = list(limb_inst.paired_instances.all())
    return paired[0] if paired else None


def count_installed_cybereyes(character_sheet):
    return CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        cyberware__name__in=_CYBEREYE_INSTANCE_NAMES,
    ).count()


def count_limb_only_decor_capacity(character_sheet):
    """Cyberarms + cyberleg hosts only (for Reinforced / Hardened Shielding caps)."""
    arms = CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        cyberware__name__in=["Cyberarm", "Neo-Soviet Cyberarm"],
    ).count()
    legs = CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        cyberware__name__in=_CYBERLEG_INSTANCE_NAMES,
    ).count()
    return arms + legs


def count_limb_and_eye_decor_capacity(character_sheet):
    """Parents that can take cosmetic coverings (limbs + cybereyes)."""
    arms = CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        cyberware__name__in=["Cyberarm", "Neo-Soviet Cyberarm"],
    ).count()
    legs = CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        cyberware__name__in=_CYBERLEG_INSTANCE_NAMES,
    ).count()
    return arms + legs + count_installed_cybereyes(character_sheet)


def check_limb_decor_capacity(character_sheet, cyberware, *, installing: bool = True):
    """
    Limit cosmetic / shielding installs: at most one installed copy of this catalog item
    per eligible parent (limb or eye). Hardened Cybereye Casing and Color Shift use cybereye count only.
    Returns (success, error_message).
    """
    cw_name = _norm(getattr(cyberware, "name", ""))
    if cw_name in EYE_ONLY_DECOR_NAMES:
        cap = count_installed_cybereyes(character_sheet)
    elif cw_name in LIMB_ONLY_DECOR_NAMES:
        cap = count_limb_only_decor_capacity(character_sheet)
    elif cw_name in LIMB_AND_EYE_DECOR_NAMES:
        cap = count_limb_and_eye_decor_capacity(character_sheet)
    else:
        return True, ""

    have = CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        cyberware_id=getattr(cyberware, "id", None),
    ).count()
    if installing:
        have += 1
    if cap <= 0:
        if cw_name in EYE_ONLY_DECOR_NAMES:
            msg = (
                f"You need at least one installed Cybereye-type implant before installing "
                f"{cyberware.name}."
            )
        elif cw_name in LIMB_ONLY_DECOR_NAMES:
            msg = (
                f"You need at least one installed Cyberarm or Cyberleg before installing "
                f"{cyberware.name}."
            )
        else:
            msg = (
                f"You need at least one installed Cyberarm, Cyberleg, or Cybereye before installing "
                f"{cyberware.name}."
            )
        return False, msg
    if have > cap:
        if cw_name in EYE_ONLY_DECOR_NAMES:
            per = "Cybereye-type implant"
        elif cw_name in LIMB_ONLY_DECOR_NAMES:
            per = "Cyberarm or Cyberleg"
        else:
            per = "Cyberarm, Cyberleg, or Cybereye"
        return False, (
            f"{cyberware.name} can be installed at most once per {per} "
            f"({cap} eligible socket(s); you would exceed that)."
        )
    return True, ""


def check_paired_arm_weapon_install_limit(character_sheet, cyberware):
    """Gorilla Arm / Mantis Blade: max two installed total (one per arm after pairing)."""
    cw_name = _norm(getattr(cyberware, "name", ""))
    if cw_name not in PAIRED_CYBERARM_WEAPON_OPTIONS:
        return True, ""

    count = CyberwareInstance.objects.filter(
        character_sheet=character_sheet,
        installed=True,
        cyberware__name__iexact=getattr(cyberware, "name", ""),
    ).count()
    if count >= 2:
        return False, (
            f"You can only install two {cyberware.name} (one on each paired Cyberarm). "
            f"Use |wcyberware/parent|n to attach them to each arm."
        )
    return True, ""


def validate_paired_cyberarm_weapon_parent(parent_inst, child_inst):
    """
    Gorilla Arm / Mantis Blade must mount on Cyberarms.

    Left/right Cyberarms created as a pair must install the same weapon on both.
    Extra Cyberarms parented to Artificial Shoulder Mount are not part of that
    pair (no ``paired_with``); they only obey one paired-weapon option per arm.
    """
    child_name = _norm(getattr(child_inst, "cyberware", None) and child_inst.cyberware.name)
    if child_name not in PAIRED_CYBERARM_WEAPON_OPTIONS:
        return True, ""

    parent_name = _norm(parent_inst.cyberware.name)
    if parent_name not in ("cyberarm", "neo-soviet cyberarm"):
        return False, f"{getattr(child_inst, 'cyberware', None) and child_inst.cyberware.name} requires a Cyberarm parent."

    # Mount-hosted arms are not mirrored with the other side; skip L/R match rule.
    ppar = getattr(parent_inst, "parent", None)
    ppar_cw = getattr(ppar, "cyberware", None) if ppar else None
    ppar_name = _norm(getattr(ppar_cw, "name", "") if ppar_cw else "")
    if ppar_name == "artificial shoulder mount":
        child_pk = getattr(child_inst, "id", None)
        for c in parent_inst.children.all():
            cn = _norm(c.cyberware.name)
            if cn in PAIRED_CYBERARM_WEAPON_OPTIONS and c.pk != child_pk:
                return False, (
                    f"{parent_inst.cyberware.name} already has {c.cyberware.name}. "
                    f"Only one paired weapon option per arm."
                )
        return True, ""

    other = get_paired_limb_instance(parent_inst)
    if not other:
        return False, (
            f"{child_inst.cyberware.name} must be installed on |wpaired|n Cyberarms. "
            f"Install a second Cyberarm and link it with |waddcyberware/pair Cyberarm=<char>|n (staff) "
            f"or complete chargen pairing, then use |wcyberware/parent|n on each arm."
        )

    child_pk = getattr(child_inst, "id", None)
    for c in parent_inst.children.all():
        cn = _norm(c.cyberware.name)
        if cn in PAIRED_CYBERARM_WEAPON_OPTIONS and c.pk != child_pk:
            return False, (
                f"{parent_inst.cyberware.name} already has {c.cyberware.name}. "
                f"Only one paired weapon option per arm."
            )

    other_weapon_display_names = []
    for c in other.children.all():
        cn = _norm(c.cyberware.name)
        if cn in PAIRED_CYBERARM_WEAPON_OPTIONS:
            other_weapon_display_names.append(c.cyberware.name)

    if len(other_weapon_display_names) > 1:
        return False, (
            f"{other.cyberware.name} has multiple paired weapon options; fix staff-side state before continuing."
        )

    if other_weapon_display_names:
        other_n = _norm(other_weapon_display_names[0])
        if other_n != child_name:
            return False, (
                f"Your other Cyberarm has {other_weapon_display_names[0]} installed; "
                f"this arm must use the same paired weapon ({child_inst.cyberware.name})."
            )

    return True, ""


def check_has_required_parent(character_sheet, cyberware):
    """
    For cyberware that requires a parent (e.g. Kerenzikov needs Neural Link),
    verify the character has that parent installed.
    Returns (success, error_message).

    Solo-limb override: Options that "can be the only cyberware in a meat arm/leg"
    (e.g. Rippers, Wolvers) may be installed ONCE without a Cyberarm/Cyberleg.
    For a second such option, the character must have the limb and parent it.
    """
    cw_name = _norm(getattr(cyberware, "name", ""))

    # Solo-limb override: allow first install without parent
    if cw_name in SOLO_ARM_OPTIONS:
        has_arm = CyberwareInstance.objects.filter(
            character_sheet=character_sheet, installed=True,
            cyberware__name__in=["Cyberarm", "Neo-Soviet Cyberarm"],
        ).exists()
        solo_count = _count_solo_arm_options_unparented(character_sheet)
        if has_arm or solo_count == 0:
            return True, ""
        return False, (
            f"You already have a solo arm option (e.g. Rippers, Wolvers) installed without a Cyberarm. "
            f"To install another, purchase a Cyberarm first, then use |wcyberware/parent {cyberware.name}=Cyberarm|n "
            f"to parent your existing option, then install the new one."
        )
    if cw_name in SOLO_LEG_OPTIONS:
        has_leg = CyberwareInstance.objects.filter(
            character_sheet=character_sheet, installed=True,
            cyberware__name__iexact="Cyberleg",
        ).exists()
        solo_count = _count_solo_leg_options_unparented(character_sheet)
        if has_leg or solo_count == 0:
            return True, ""
        return False, (
            f"You already have a solo leg option (e.g. Talon Foot, PerfectFit Cyberfoot) installed without a Cyberleg. "
            f"To install another, purchase a Cyberleg first, then use |wcyberware/parent {cyberware.name}=Cyberleg|n."
        )

    required = get_required_parents(cyberware)
    if not required:
        return True, ""

    qs = CyberwareInstance.objects.filter(character_sheet=character_sheet, installed=True)
    installed_names = {_norm(inst.cyberware.name) for inst in qs.select_related("cyberware")}

    for req in required:
        # "cyberlimb" means Cyberarm or Cyberleg
        if req == "cyberlimb":
            parts = ["cyberarm", "neo-soviet cyberarm", "cyberleg"]
        else:
            parts = [req]
        for p in parts:
            if p in installed_names:
                return True, ""
            if any(p in iname or iname in p for iname in installed_names):
                return True, ""

    parent_display = ", or ".join(r.title() for r in required)
    return False, (
        f"You need {parent_display} installed before you can install {cyberware.name}. "
        f"Purchase and install the required cyberware first."
    )


def count_bodyware_slots_used(character_sheet):
    """Count used bodyware slots (Internal Body + External Body, 7 max total)."""
    used = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=character_sheet, installed=True
    ).select_related("cyberware"):
        cw_type = _norm(getattr(inst.cyberware, "type", ""))
        if cw_type in BODYWARE_TYPES or cw_type.startswith("internal body") or cw_type.startswith("external body"):
            used += max(1, getattr(inst.cyberware, "slots", 1))
    return used


def check_bodyware_slots(character_sheet, cyberware):
    """
    Verify bodyware slot limit (7). Returns (success, error_message).
    """
    cw_type = _norm(getattr(cyberware, "type", ""))
    if cw_type not in BODYWARE_TYPES:
        return True, ""

    used = count_bodyware_slots_used(character_sheet)
    cost = max(1, getattr(cyberware, "slots", 1))
    if used + cost > BODYWARE_LIMIT:
        return False, (
            f"Bodyware limit reached. You have {used} of {BODYWARE_LIMIT} Internal/External Body slots used. "
            f"{cyberware.name} requires {cost} slot(s). You cannot install more bodyware without removing some."
        )
    return True, ""


# Fashionware slot limit (7)
FASHIONWARE_LIMIT = 7


def _count_fashionware_slots_used(character_sheet):
    """Count Fashionware slots used (7 max)."""
    used = 0
    for inst in CyberwareInstance.objects.filter(
        character_sheet=character_sheet, installed=True
    ).select_related("cyberware"):
        cw_type = _norm(getattr(inst.cyberware, "type", ""))
        if cw_type == "fashionware":
            used += max(1, getattr(inst.cyberware, "slots", 1))
    return used


def _count_chipware_sockets(character_sheet):
    """Count Chipware Sockets and their used slots."""
    sockets = list(
        CyberwareInstance.objects.filter(
            character_sheet=character_sheet,
            installed=True,
            cyberware__name__in=["Chipware Socket", "Budget Chipware Socket"],
        ).select_related("cyberware")
    )
    total = len(sockets)
    used = 0
    for s in sockets:
        for c in s.children.all():
            if _norm(c.cyberware.name) not in ZERO_SLOT_ITEMS:
                used += 1
    return used, total


def get_slot_summaries(character_sheet):
    """
    Return slot usage for each cyberware category.
    Returns: dict of category_label -> {"used": N, "total": N, "remaining": N}
    """
    summaries = {}
    # Fashionware
    fw_used = _count_fashionware_slots_used(character_sheet)
    summaries["Fashionware"] = {"used": fw_used, "total": FASHIONWARE_LIMIT, "remaining": max(0, FASHIONWARE_LIMIT - fw_used)}
    # Neural Link / Neuroport
    nl_total = _count_neural_slots(character_sheet)
    nl_used = _count_used_neural_slots(character_sheet)
    summaries["Neural Link Options"] = {"used": nl_used, "total": nl_total, "remaining": max(0, nl_total - nl_used)}
    # Chipware
    cw_used, cw_total = _count_chipware_sockets(character_sheet)
    summaries["Chipware"] = {"used": cw_used, "total": cw_total, "remaining": max(0, cw_total - cw_used)}
    # Cybereye
    ce_total = _count_cybereye_slots(character_sheet)
    ce_used = _count_used_cybereye_slots(character_sheet)
    summaries["Cybereye Options"] = {"used": ce_used, "total": ce_total, "remaining": max(0, ce_total - ce_used)}
    # Cyberaudio
    ca_total = _count_cyberaudio_slots(character_sheet)
    ca_used = _count_used_cyberaudio_slots(character_sheet)
    summaries["Cyberaudio Options"] = {"used": ca_used, "total": ca_total, "remaining": max(0, ca_total - ca_used)}
    # Cyberarm
    carm_total = _count_cyberarm_slots(character_sheet)
    carm_used = _count_used_cyberarm_slots(character_sheet)
    summaries["Cyberarm Options"] = {"used": carm_used, "total": carm_total, "remaining": max(0, carm_total - carm_used)}
    # Cyberleg
    cleg_total = _count_cyberleg_slots(character_sheet)
    cleg_used = _count_used_cyberleg_slots(character_sheet)
    summaries["Cyberleg Options"] = {"used": cleg_used, "total": cleg_total, "remaining": max(0, cleg_total - cleg_used)}
    # Bodyware
    bw_used = count_bodyware_slots_used(character_sheet)
    summaries["Bodyware"] = {"used": bw_used, "total": BODYWARE_LIMIT, "remaining": max(0, BODYWARE_LIMIT - bw_used)}
    return summaries
