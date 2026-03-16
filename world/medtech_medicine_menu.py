"""
EvMenu for Edgerunner Medtech Medicine specialty allocation at chargen.
Allocates Medicine rank points across Surgery, Pharmaceuticals, and Cryosystem.
One point at a time - select which specialty to add to.
"""

from evennia.utils.evmenu import EvMenu
from world.chargen_constants import (
    MEDICINE_PHARMA_MAX,
    MEDICINE_CRYO_MAX,
    get_medicine_surgery_skill,
    get_medical_tech_skill,
)

MEDICINE_RANK_EDGERUNNER = 4


def menunode_medicine_allocation(caller, raw_string, **kwargs):
    """
    Display Medicine specialty allocation. Add one point per choice (1: Surgery, 2: Pharma, 3: Cryo).
    """
    method = kwargs.get("method", "edgerunner")
    role = kwargs.get("role", "Medtech")
    full_name = kwargs.get("full_name", "")
    surgery = kwargs.get("surgery", 0)
    pharma = kwargs.get("pharma", 0)
    cryo = kwargs.get("cryo", 0)
    points_allocated = (surgery or 0) + (pharma or 0) + (cryo or 0)

    # Get from menu if first call
    if method is None and hasattr(caller, "ndb") and caller.ndb._evmenu:
        menu = caller.ndb._evmenu
        method = getattr(menu, "method", "edgerunner")
        role = getattr(menu, "role", "Medtech")
        full_name = getattr(menu, "full_name", "")

    medicine = MEDICINE_RANK_EDGERUNNER
    remaining = medicine - points_allocated
    surg_skill = get_medicine_surgery_skill(surgery)
    medtech_skill = get_medical_tech_skill(pharma, cryo)

    lines = [
        "|wMedtech - Medicine Specialty Allocation|n",
        "",
        f"You have |g{medicine}|n Medicine points to allocate across three specialties.",
        f"Points remaining: |g{remaining}|n",
        "",
        "|ySurgery|n: 1 pt = 2 Surgery skill (max 10). Critical injuries, cyberware, bodysculpting.",
        "|yPharmaceuticals|n: 1 pt = 1 Medical Tech (max 5 pts). Unlocks drug synthesis.",
        "|yCryosystem|n: 1 pt = 1 Medical Tech (max 5 pts). Unlocks cryopump/tank operation.",
        "",
        "Medical Tech skill = Pharma + Cryo (combined max 10).",
        "",
        f"|wCurrent allocation:|n Surgery {surgery} | Pharma {pharma} | Cryo {cryo}",
        f"  -> Surgery skill: {surg_skill} | Medical Tech skill: {medtech_skill}",
        "",
        "|wAdd 1 point to:|n",
    ]

    text = "\n".join(lines)

    def _add_point(choice):
        def _goto(caller, raw_string, **kw):
            ns = surgery + (1 if choice == "surgery" else 0)
            np = pharma + (1 if choice == "pharma" else 0)
            nc = cryo + (1 if choice == "cryo" else 0)
            new_total = ns + np + nc
            if new_total >= medicine:
                # All 4 points allocated - goto done node (returns None for options = exit)
                return (
                    "menunode_done",
                    {"method": method, "role": role, "full_name": full_name, "surgery": ns, "pharma": np, "cryo": nc},
                )
            return (
                "menunode_medicine_allocation",
                {"method": method, "role": role, "full_name": full_name, "surgery": ns, "pharma": np, "cryo": nc},
            )
        return _goto

    options = []

    # 1: Surgery (no max)
    options.append({"key": ("1", "surgery", "s"), "desc": "Surgery", "goto": _add_point("surgery")})

    # 2: Pharmaceuticals (max 5)
    if (pharma or 0) < MEDICINE_PHARMA_MAX:
        options.append({"key": ("2", "pharma", "pharmaceuticals", "p"), "desc": "Pharmaceuticals", "goto": _add_point("pharma")})

    # 3: Cryosystem (max 5)
    if (cryo or 0) < MEDICINE_CRYO_MAX:
        options.append({"key": ("3", "cryo", "cryosystem", "c"), "desc": "Cryosystem", "goto": _add_point("cryo")})

    options.append({"key": ("q", "quit", "b", "back"), "desc": "Cancel chargen", "goto": None})

    return text, tuple(options)


def menunode_done(caller, raw_string, **kwargs):
    """
    Final node when all 4 points are allocated. Store values and exit menu.
    Returning (text, None) for options exits the EvMenu.
    """
    surgery = kwargs.get("surgery", 0)
    pharma = kwargs.get("pharma", 0)
    cryo = kwargs.get("cryo", 0)
    method = kwargs.get("method", "edgerunner")
    role = kwargs.get("role", "Medtech")
    full_name = kwargs.get("full_name", "")

    caller.ndb._chargen_medicine_specialties = {"surgery": surgery, "pharma": pharma, "cryo": cryo}
    caller.ndb._chargen_params = (method, role, full_name)

    surg_skill = get_medicine_surgery_skill(surgery)
    medtech_skill = get_medical_tech_skill(pharma, cryo)
    text = (
        "|gMedicine specialty allocation complete!|n\n\n"
        f"Surgery {surgery} | Pharmaceuticals {pharma} | Cryosystem {cryo}\n"
        f"Surgery skill: {surg_skill} | Medical Tech skill: {medtech_skill}"
    )
    return text, None  # None options = exit menu


def start_medtech_medicine_menu(caller, method, role, full_name, on_complete):
    """
    Start the Medicine specialty allocation menu for Medtech Edgerunner chargen.
    When complete, calls on_complete(caller).
    Result is in caller.ndb._chargen_params and caller.ndb._chargen_medicine_specialties.
    """
    EvMenu(
        caller,
        "world.medtech_medicine_menu",
        startnode="menunode_medicine_allocation",
        method=method,
        role=role,
        full_name=full_name,
        cmdset_mergetype="Replace",
        cmd_on_exit=on_complete,
        auto_quit=True,
        auto_look=False,
    )
    return True
