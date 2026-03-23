"""
EvMenu for Edgerunner chargen skill instance prompts.
Collects Local Expert area, Play Instrument (Rockerboy), and Science choice (Tech/Medtech)
before proceeding with character creation.
"""

from evennia.utils.evmenu import EvMenu, EvMenuGotoAbortMessage
from world.chargen_constants import SCIENCE_SKILLS
from world.cyberware.cyberware_data import LOCAL_EXPERT_AREAS


def _get_menu_params(caller, kwargs):
    """Get method, role, full_name from kwargs or menu."""
    method = kwargs.get("method")
    role = kwargs.get("role")
    full_name = kwargs.get("full_name")
    if method is None and hasattr(caller, "ndb") and caller.ndb._evmenu:
        menu = caller.ndb._evmenu
        method = getattr(menu, "method", "edgerunner")
        role = getattr(menu, "role", "")
        full_name = getattr(menu, "full_name", "")
    return method or "edgerunner", role or "", full_name or ""


def _get_choices_from_menu_or_kw(caller, kw):
    """EvMenu does not pass current kwargs to _default goto callables - get from menu."""
    menu = getattr(caller.ndb, "_evmenu", None)
    if menu and hasattr(menu, "node_kwargs"):
        return menu.node_kwargs.get("choices", {}) or kw.get("choices", {})
    return kw.get("choices", {})


def _normalize_area_name(area):
    """Normalize Local Expert area names for matching."""
    normalized = " ".join(str(area or "").strip().lower().split())
    if normalized.startswith("the "):
        normalized = normalized[4:]
    return normalized


def _coerce_suggested_local_expert_options(value):
    """
    Convert a suggestion payload into a clean list of option strings.
    Supports string, list/tuple/set, and dict payloads.
    """
    if not value:
        return []
    if isinstance(value, str):
        # Accept either a single string or comma/pipe-separated values.
        parts = value.replace("|", ",").split(",")
        return [p.strip() for p in parts if p and p.strip()]
    if isinstance(value, dict):
        # Prefer explicit keys; fallback to dict values.
        if "options" in value:
            return _coerce_suggested_local_expert_options(value.get("options"))
        if "local_expert" in value:
            return _coerce_suggested_local_expert_options(value.get("local_expert"))
        return [str(v).strip() for v in value.values() if str(v).strip()]
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            out.extend(_coerce_suggested_local_expert_options(item))
        return out
    return [str(value).strip()] if str(value).strip() else []


def _get_suggested_local_expert_options(caller, kwargs):
    """Resolve suggested Local Expert options from kwargs/menu/caller attrs."""
    # 1) Explicit kwargs from start call
    explicit = kwargs.get("suggested_local_expert_options")
    opts = _coerce_suggested_local_expert_options(explicit)
    if opts:
        return opts

    # 2) Menu-persisted value
    menu = getattr(caller.ndb, "_evmenu", None)
    if menu and hasattr(menu, "node_kwargs"):
        menu_value = menu.node_kwargs.get("suggested_local_expert_options")
        opts = _coerce_suggested_local_expert_options(menu_value)
        if opts:
            return opts

    # 3) Character attrs set by upstream chargen/lifepath flow
    for attr_name in (
        "suggested_local_expert_options",
        "suggested_local_expert",
        "chargen_suggested_local_expert_options",
        "_chargen_suggested_local_expert_options",
    ):
        try:
            ndb_value = getattr(caller.ndb, attr_name, None)
        except Exception:
            ndb_value = None
        opts = _coerce_suggested_local_expert_options(ndb_value)
        if opts:
            return opts
        db_value = getattr(caller.db, attr_name, None)
        opts = _coerce_suggested_local_expert_options(db_value)
        if opts:
            return opts
    return []


def menunode_local_expert(caller, raw_string, **kwargs):
    """Prompt for Local Expert area - everyone has this skill."""
    method, role, full_name = _get_menu_params(caller, kwargs)
    choices = kwargs.get("choices", {})
    method_label = "Complete Package" if (method or "").strip().lower() == "complete_package" else "Edgerunner"

    suggested_options = _get_suggested_local_expert_options(caller, kwargs)
    chip_map = {_normalize_area_name(area): area for area in LOCAL_EXPERT_AREAS}
    chip_map.setdefault("combat zones", "Combat Zone")
    suggested_chip_matches = []
    for option in suggested_options:
        normalized = _normalize_area_name(option)
        if normalized in chip_map:
            suggested_chip_matches.append(chip_map[normalized])
    if suggested_chip_matches:
        # Keep output stable and easy to scan.
        suggested_chip_matches = list(dict.fromkeys(suggested_chip_matches))

    suggested_lines = ""
    if suggested_options:
        suggested_lines = (
            f"|wSuggested option(s):|n {', '.join(suggested_options)}\n"
        )
        if suggested_chip_matches:
            suggested_lines += (
                f"|wBasic Skill Chip options available:|n {', '.join(suggested_chip_matches)}\n"
            )

    text = (
        f"|w{method_label} - Skill Details|n\n\n"
        "|yLocal Expert|n: Knowledge of a specific area.\n"
        "Everyone has Local Expert at rank 2. What area is your character an expert in?\n\n"
        f"{suggested_lines}"
        "|wExamples:|n Night City, Corporate Zones, The Badlands, Pacifica, Watson, "
        "Combat Zones, the Net, etc.\n\n"
        "Enter the area name (e.g., 'Night City'):"
    )
    options = [
        {
            "key": "_default",
            "desc": "Enter your Local Expert area",
            "goto": (
                "menunode_play_instrument" if role == "Rockerboy" else
                "menunode_science" if role in ("Tech", "Medtech") else
                "menunode_done"
            ),
        },
    ]

    def _process_input(caller, raw_string, **kw):
        area = (raw_string or "").strip()
        if not area:
            raise EvMenuGotoAbortMessage(
                "|rPlease enter an area name (e.g., 'Night City').|n"
            )
        cur_choices = _get_choices_from_menu_or_kw(caller, kw)
        new_choices = dict(cur_choices)
        new_choices["local_expert"] = area[:80]  # Cap length
        next_node = "menunode_play_instrument" if role == "Rockerboy" else "menunode_science" if role in ("Tech", "Medtech") else "menunode_done"
        return (next_node, {
            "method": kw.get("method") or method,
            "role": kw.get("role") or role,
            "full_name": kw.get("full_name") or full_name,
            "choices": new_choices,
        })

    options[0]["goto"] = _process_input
    return text, tuple(options)


def menunode_play_instrument(caller, raw_string, **kwargs):
    """Prompt for Play Instrument - Rockerboy only."""
    method, role, full_name = _get_menu_params(caller, kwargs)
    choices = kwargs.get("choices", {})
    method_label = "Complete Package" if (method or "").strip().lower() == "complete_package" else "Edgerunner"

    text = (
        f"|w{method_label} - Skill Details|n\n\n"
        "|yPlay Instrument|n: Rockerboys have this skill at rank 2.\n"
        "What instrument does your character play?\n\n"
        "|wExamples:|n guitar, electric guitar, synth, piano, drums, bass, violin, etc.\n\n"
        "Enter the instrument name:"
    )
    options = [
        {
            "key": "_default",
            "desc": "Enter your instrument",
            "goto": "menunode_science" if role in ("Tech", "Medtech") else "menunode_done",
        },
    ]

    def _process_input(caller, raw_string, **kw):
        inst = (raw_string or "").strip() or "guitar"
        cur_choices = _get_choices_from_menu_or_kw(caller, kw)
        new_choices = dict(cur_choices)
        new_choices["play_instrument"] = inst[:80]
        next_node = "menunode_science" if role in ("Tech", "Medtech") else "menunode_done"
        return (next_node, {
            "method": kw.get("method") or method,
            "role": kw.get("role") or role,
            "full_name": kw.get("full_name") or full_name,
            "choices": new_choices,
        })

    options[0]["goto"] = _process_input
    return text, tuple(options)


def menunode_science(caller, raw_string, **kwargs):
    """Prompt for Science skill choice - Tech and Medtech pick one."""
    method, role, full_name = _get_menu_params(caller, kwargs)
    choices = kwargs.get("choices", {})
    method_label = "Complete Package" if (method or "").strip().lower() == "complete_package" else "Edgerunner"

    lines = [
        f"|w{method_label} - Science Skill Selection|n",
        "",
        f"|y{role}|n: Choose one Science skill at rank 2.",
        "",
        "|wAvailable Science skills:|n",
        "",
    ]
    for i, skill in enumerate(SCIENCE_SKILLS, 1):
        display = skill.replace("_", " ").title()
        lines.append(f"  |w{i}|n. {display}")
    lines.append("")
    lines.append("Enter the number of your choice:")

    text = "\n".join(lines)

    def _make_goto(idx):
        def _goto(caller, raw_string, **kw):
            skill = SCIENCE_SKILLS[idx]
            cur_choices = _get_choices_from_menu_or_kw(caller, kw)
            new_choices = dict(cur_choices)
            new_choices["science"] = skill
            return ("menunode_done", {
                "method": kw.get("method") or method,
                "role": kw.get("role") or role,
                "full_name": kw.get("full_name") or full_name,
                "choices": new_choices,
            })
        return _goto

    options = []
    for i, skill in enumerate(SCIENCE_SKILLS):
        display = skill.replace("_", " ").title()
        options.append({
            "key": (str(i + 1), display.lower().replace(" ", "_")),
            "desc": display,
            "goto": _make_goto(i),
        })
    options.append({"key": ("q", "quit", "b", "back"), "desc": "Cancel chargen", "goto": None})

    return text, tuple(options)


def menunode_done(caller, raw_string, **kwargs):
    """Store choices and exit menu."""
    method = kwargs.get("method", "edgerunner")
    role = kwargs.get("role", "")
    full_name = kwargs.get("full_name", "")
    choices = kwargs.get("choices", {})

    # Ensure local_expert is set (everyone)
    if "local_expert" not in choices:
        choices["local_expert"] = "Unknown"

    caller.ndb._chargen_skill_instances = choices
    caller.ndb._chargen_params = (method, role, full_name)

    summary = "|gSkill details saved:|n\n"
    summary += f"  Local Expert: {choices.get('local_expert', 'Unknown')}\n"
    if "play_instrument" in choices:
        summary += f"  Play Instrument: {choices.get('play_instrument')}\n"
    if "science" in choices:
        summary += f"  Science: {choices.get('science', '').replace('_', ' ').title()}\n"
    summary += "\nProceeding with character creation..."

    return summary, None  # None = exit menu


def start_edgerunner_skill_instances_menu(
    caller,
    method,
    role,
    full_name,
    on_complete,
    suggested_local_expert_options=None,
):
    """
    Start the skill instances menu for Edgerunner chargen.
    Prompts for: Local Expert (all), Play Instrument (Rockerboy), Science (Tech/Medtech).
    When complete, calls on_complete(caller).
    Result in caller.ndb._chargen_skill_instances and caller.ndb._chargen_params.
    """
    EvMenu(
        caller,
        "world.edgerunner_skill_instances_menu",
        startnode="menunode_local_expert",
        method=method,
        role=role,
        full_name=full_name,
        suggested_local_expert_options=suggested_local_expert_options,
        choices={},
        cmdset_mergetype="Replace",
        cmd_on_exit=on_complete,
        auto_quit=True,
        auto_look=False,
    )
    return True
