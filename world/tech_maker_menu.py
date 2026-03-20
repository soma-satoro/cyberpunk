"""
EvMenu for Tech Maker specialty allocation at chargen.
Allocates Maker rank x 2 points across Field, Upgrade, Fabrication, and Invention expertise.
One point at a time - select which specialty to add to.
"""

from evennia.utils.evmenu import EvMenu
from world.chargen_constants import MAKER_ALLOCATION_PER_RANK

MAKER_RANK_EDGERUNNER = 4
MAKER_RANK_COMPLETE_PACKAGE = 4


def _get_menu_params(caller, kwargs):
    """Get method, role, full_name from kwargs or EvMenu."""
    method = kwargs.get("method")
    role = kwargs.get("role")
    full_name = kwargs.get("full_name", "")
    if method is None and hasattr(caller, "ndb") and getattr(caller.ndb, "_evmenu", None):
        menu = caller.ndb._evmenu
        method = getattr(menu, "method", "edgerunner")
        role = role or getattr(menu, "role", "Tech")
        full_name = full_name or getattr(menu, "full_name", "")
    return method or "edgerunner", role or "Tech", full_name or ""


def menunode_maker_allocation(caller, raw_string, **kwargs):
    """
    Display Maker specialty allocation. Add one point per choice.
    """
    method, role, full_name = _get_menu_params(caller, kwargs)
    field = kwargs.get("field", 0)
    upgrade = kwargs.get("upgrade", 0)
    fabrication = kwargs.get("fabrication", 0)
    invention = kwargs.get("invention", 0)
    points_allocated = (field or 0) + (upgrade or 0) + (fabrication or 0) + (invention or 0)

    maker = MAKER_RANK_EDGERUNNER if method == "edgerunner" else MAKER_RANK_COMPLETE_PACKAGE
    total_points = maker * MAKER_ALLOCATION_PER_RANK
    remaining = total_points - points_allocated

    lines = [
        "|wTech - Maker Specialty Allocation|n",
        "",
        f"You have |g{total_points}|n points to allocate (Maker {maker} x {MAKER_ALLOCATION_PER_RANK}).",
        f"Points remaining: |g{remaining}|n",
        "",
        "|yField Expertise|n: Repair, maintain, jury-rig. (max per specialty = Maker rank)",
        "|yUpgrade Expertise|n: Improve items beyond base stats.",
        "|yFabrication Expertise|n: Build from scratch.",
        "|yInvention Expertise|n: Create new designs.",
        "",
        f"|wCurrent allocation:|n Field {field} | Upgrade {upgrade} | Fabrication {fabrication} | Invention {invention}",
        "",
        "|wAdd 1 point to:|n",
    ]

    text = "\n".join(lines)

    def _add_point(choice):
        def _goto(caller, raw_string, **kw):
            nf = field + (1 if choice == "field" else 0)
            nu = upgrade + (1 if choice == "upgrade" else 0)
            nfab = fabrication + (1 if choice == "fabrication" else 0)
            ninv = invention + (1 if choice == "invention" else 0)
            new_total = nf + nu + nfab + ninv
            if new_total >= total_points:
                return (
                    "menunode_done",
                    {
                        "method": method,
                        "role": role,
                        "full_name": full_name,
                        "field": nf,
                        "upgrade": nu,
                        "fabrication": nfab,
                        "invention": ninv,
                    },
                )
            return (
                "menunode_maker_allocation",
                {
                    "method": method,
                    "role": role,
                    "full_name": full_name,
                    "field": nf,
                    "upgrade": nu,
                    "fabrication": nfab,
                    "invention": ninv,
                },
            )
        return _goto

    options = []
    if (field or 0) < maker:
        options.append({"key": ("1", "field", "f"), "desc": "Field Expertise", "goto": _add_point("field")})
    if (upgrade or 0) < maker:
        options.append({"key": ("2", "upgrade", "u"), "desc": "Upgrade Expertise", "goto": _add_point("upgrade")})
    if (fabrication or 0) < maker:
        options.append({"key": ("3", "fabrication", "fab"), "desc": "Fabrication Expertise", "goto": _add_point("fabrication")})
    if (invention or 0) < maker:
        options.append({"key": ("4", "invention", "i"), "desc": "Invention Expertise", "goto": _add_point("invention")})
    options.append({"key": ("q", "quit", "b", "back"), "desc": "Cancel chargen", "goto": None})

    return text, tuple(options)


def menunode_done(caller, raw_string, **kwargs):
    """Final node when all points are allocated. Store values and exit menu."""
    field = kwargs.get("field", 0)
    upgrade = kwargs.get("upgrade", 0)
    fabrication = kwargs.get("fabrication", 0)
    invention = kwargs.get("invention", 0)
    method, role, full_name = _get_menu_params(caller, kwargs)

    caller.ndb._chargen_maker_specialties = {
        "field": field,
        "upgrade": upgrade,
        "fabrication": fabrication,
        "invention": invention,
    }
    caller.ndb._chargen_params = (method, role, full_name)

    text = (
        "|gMaker specialty allocation complete!|n\n\n"
        f"Field {field} | Upgrade {upgrade} | Fabrication {fabrication} | Invention {invention}"
    )
    return text, None


def start_tech_maker_menu(caller, method, role, full_name, on_complete):
    """
    Start the Maker specialty allocation menu for Tech chargen.
    When complete, calls on_complete(caller).
    Result is in caller.ndb._chargen_params and caller.ndb._chargen_maker_specialties.
    """
    EvMenu(
        caller,
        "world.tech_maker_menu",
        startnode="menunode_maker_allocation",
        method=method,
        role=role,
        full_name=full_name,
        cmdset_mergetype="Replace",
        cmd_on_exit=on_complete,
        auto_quit=True,
        auto_look=False,
    )
    return True
