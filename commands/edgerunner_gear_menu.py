"""
EvMenu for Edgerunner chargen gear OR choices (e.g. Rockerboy: Bug Detector or Electric Guitar).
Collects player choices before proceeding with character creation.
"""

from evennia.utils.evmenu import EvMenu
from world.cyberpunk_constants import EQUIPMENT_OR_CHOICES


def _format_option(opt):
    """Format a gear option for display - handles (name, qty) and plain name."""
    if isinstance(opt, (list, tuple)) and len(opt) >= 2:
        return f"{opt[0]} x{opt[1]}"
    return str(opt)


def menunode_gear_choices(caller, raw_string, **kwargs):
    """
    Present gear OR choices for the role. If multiple OR groups, we iterate.
    kwargs: method, role, full_name, choices_so_far (list), or_index (int)
    First call gets method/role/full_name from EvMenu kwargs (caller.ndb._evmenu).
    """
    # Get from kwargs (when returning from goto) or from menu (first call)
    method = kwargs.get("method")
    role = kwargs.get("role")
    full_name = kwargs.get("full_name")
    if method is None and hasattr(caller, "ndb") and caller.ndb._evmenu:
        menu = caller.ndb._evmenu
        method = getattr(menu, "method", "edgerunner")
        role = getattr(menu, "role", "")
        full_name = getattr(menu, "full_name", "")
    method = method or "edgerunner"
    role = role or ""
    full_name = full_name or ""
    choices_so_far = kwargs.get("choices_so_far", [])
    or_index = kwargs.get("or_index", 0)

    or_groups = EQUIPMENT_OR_CHOICES.get(role, [])
    if or_index >= len(or_groups):
        # All choices collected - proceed to chargen
        caller.ndb._chargen_gear_choices = {f"{role}_{i}": c for i, c in enumerate(choices_so_far)}
        caller.ndb._chargen_params = (method, role, full_name)
        return None  # Exit menu - caller will detect and run create_character

    group = or_groups[or_index]
    prompt = group.get("prompt", "Choose one:")
    options = group.get("options", [])

    lines = [
        f"|w{role} Starting Gear - Choice {or_index + 1} of {len(or_groups)}|n",
        "",
        f"|y{prompt}|n",
        "",
    ]
    for i, opt in enumerate(options, 1):
        display = _format_option(opt)
        lines.append(f"  |w{i}|n. {display}")
    lines.append("")
    lines.append("Enter the number of your choice:")

    text = "\n".join(lines)

    def _make_goto(idx):
        def _goto(caller, raw_string, **kw):
            choice = options[idx]
            new_choices = choices_so_far + [choice]
            return ("menunode_gear_choices", {
                "method": method,
                "role": role,
                "full_name": full_name,
                "choices_so_far": new_choices,
                "or_index": or_index + 1,
            })
        return _goto

    ev_options = []
    for i, opt in enumerate(options):
        ev_options.append({
            "key": (str(i + 1), str(opt) if not isinstance(opt, (list, tuple)) else str(opt[0])),
            "desc": _format_option(opt),
            "goto": _make_goto(i),
        })

    return text, tuple(ev_options)


def start_edgerunner_gear_menu(caller, method, role, full_name, on_complete):
    """
    Start the gear choices menu. When complete, calls on_complete(caller).
    on_complete should run create_character with gear_choices from caller.ndb._chargen_gear_choices.
    """
    or_groups = EQUIPMENT_OR_CHOICES.get(role, [])
    if not or_groups:
        return False

    EvMenu(
        caller,
        "commands.edgerunner_gear_menu",
        startnode="menunode_gear_choices",
        method=method,
        role=role,
        full_name=full_name,
        cmdset_mergetype="Replace",
        cmd_on_exit=on_complete,
        auto_quit=True,
        auto_look=False,
    )
    return True
