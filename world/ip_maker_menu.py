"""
EvMenu for allocating 2 Maker points when spending IP to raise Maker.
Tech only - add 1 point at a time to Field, Upgrade, Fabrication, or Invention.
Each specialty is capped by the new Maker rank.
"""

from evennia.utils.evmenu import EvMenu


def menunode_maker_ip_allocation(caller, raw_string, **kwargs):
    """Allocate 2 points (one at a time) to Maker specialties."""
    field = kwargs.get("field", 0)
    upgrade = kwargs.get("upgrade", 0)
    fabrication = kwargs.get("fabrication", 0)
    invention = kwargs.get("invention", 0)
    points_allocated = field + upgrade + fabrication + invention

    # Base values = character's current specialties (before this +1 Maker)
    base_field = kwargs.get("base_field")
    base_upgrade = kwargs.get("base_upgrade")
    base_fabrication = kwargs.get("base_fabrication")
    base_invention = kwargs.get("base_invention")
    maker_cap = kwargs.get("maker_cap")
    if base_field is None:
        base_field = getattr(caller.db, "maker_field", 0) or 0
        base_upgrade = getattr(caller.db, "maker_upgrade", 0) or 0
        base_fabrication = getattr(caller.db, "maker_fabrication", 0) or 0
        base_invention = getattr(caller.db, "maker_invention", 0) or 0
        purchase = getattr(caller.ndb, "_ip_purchase", None) or {}
        maker_cap = purchase.get("next_level", (getattr(caller, "get_skill", lambda x: 0)("maker") or 0) + 1)

    # Need to allocate 2 points total for +1 Maker rank
    points_to_allocate = 2
    remaining = points_to_allocate - points_allocated

    if remaining <= 0:
        # Done - store and exit
        caller.ndb._ip_maker_specialties = {
            "field": field,
            "upgrade": upgrade,
            "fabrication": fabrication,
            "invention": invention,
        }
        return "|gMaker allocation complete.|n", None

    lines = [
        "|wMaker +1 - Allocate 2 Points to Specialties|n",
        "",
        f"You are raising Maker by 1 rank. Add 2 points total (1 at a time).",
        f"Each specialty max = new Maker rank ({maker_cap}).",
        f"Points remaining: |g{remaining}|n",
        "",
        "|yField Expertise|n |yUpgrade Expertise|n |yFabrication Expertise|n |yInvention Expertise|n",
        "",
        f"|wCurrent (after allocation):|n Field {base_field + field} | Upgrade {base_upgrade + upgrade} | Fabrication {base_fabrication + fabrication} | Invention {base_invention + invention}",
        "",
        "|wAdd 1 point to:|n",
    ]

    def _add_point(choice):
        def _goto(caller, raw_string, **kw):
            nf = field + (1 if choice == "field" else 0)
            nu = upgrade + (1 if choice == "upgrade" else 0)
            nfab = fabrication + (1 if choice == "fabrication" else 0)
            ninv = invention + (1 if choice == "invention" else 0)
            new_total = nf + nu + nfab + ninv
            if new_total >= points_to_allocate:
                caller.ndb._ip_maker_specialties = {
                    "field": nf,
                    "upgrade": nu,
                    "fabrication": nfab,
                    "invention": ninv,
                }
                return "|gMaker allocation complete.|n", None
            return (
                "menunode_maker_ip_allocation",
                {
                    "field": nf, "upgrade": nu, "fabrication": nfab, "invention": ninv,
                    "base_field": base_field, "base_upgrade": base_upgrade,
                    "base_fabrication": base_fabrication, "base_invention": base_invention,
                    "maker_cap": maker_cap,
                },
            )
        return _goto

    options = []
    if base_field + (field or 0) < maker_cap:
        options.append({"key": ("1", "field", "f"), "desc": "Field Expertise", "goto": _add_point("field")})
    if base_upgrade + (upgrade or 0) < maker_cap:
        options.append({"key": ("2", "upgrade", "u"), "desc": "Upgrade Expertise", "goto": _add_point("upgrade")})
    if base_fabrication + (fabrication or 0) < maker_cap:
        options.append({"key": ("3", "fabrication", "fab"), "desc": "Fabrication Expertise", "goto": _add_point("fabrication")})
    if base_invention + (invention or 0) < maker_cap:
        options.append({"key": ("4", "invention", "i"), "desc": "Invention Expertise", "goto": _add_point("invention")})
    options.append({"key": ("q", "quit"), "desc": "Cancel", "goto": None})

    text = "\n".join(lines)
    return text, tuple(options)


def start_ip_maker_menu(caller, on_complete):
    """
    Start the Maker specialty allocation menu for IP purchase.
    When complete, caller.ndb._ip_maker_specialties has {field, upgrade, fabrication, invention}.
    Calls on_complete(caller) when done.
    """
    caller.ndb._ip_maker_specialties = None
    EvMenu(
        caller,
        "world.ip_maker_menu",
        startnode="menunode_maker_ip_allocation",
        cmdset_mergetype="Replace",
        cmd_on_exit=on_complete,
        auto_quit=True,
        auto_look=False,
    )
    return True
