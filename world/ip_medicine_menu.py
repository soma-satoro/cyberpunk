"""
EvMenu for allocating 1 Medicine point when spending IP to raise Medicine.
Used for Medtechs and for any character buying Medicine with IP (multi-role).
Pick Surgery, Pharmaceuticals, or Cryosystem.
"""

from evennia.utils.evmenu import EvMenu
from world.chargen_constants import get_medicine_surgery_skill, get_medical_tech_skill, MEDICINE_PHARMA_MAX, MEDICINE_CRYO_MAX


def menunode_medicine_ip_allocation(caller, raw_string, **kwargs):
    """Single point: pick Surgery, Pharma, or Cryo."""
    choice = kwargs.get("choice")
    if choice:
        # Store choice and exit
        caller.ndb._ip_medicine_specialty_choice = choice
        return "|gAllocated +1 to " + choice.title() + ".|n", None

    s = getattr(caller.db, "medicine_surgery", 0) or 0
    p = getattr(caller.db, "medicine_pharma", 0) or 0
    c = getattr(caller.db, "medicine_cryo", 0) or 0
    surg_skill = get_medicine_surgery_skill(s)
    medtech_skill = get_medical_tech_skill(p, c)

    lines = [
        "|wMedicine +1 - Allocate to Specialty|n",
        "",
        "You are raising Medicine by 1 rank. Add 1 point to one specialty:",
        "",
        f"|wCurrent:|n Surgery {s} | Pharma {p} | Cryo {c}",
        f"  -> Surgery skill: {surg_skill} | Medical Tech skill: {medtech_skill}",
        "",
        "|wChoose:|n",
    ]

    options = []
    options.append({"key": ("1", "surgery", "s"), "desc": "Surgery (1 pt = 2 Surgery skill)", "goto": ("menunode_medicine_ip_allocation", {"choice": "surgery"})})
    if p < MEDICINE_PHARMA_MAX:
        options.append({"key": ("2", "pharma", "pharmaceuticals", "p"), "desc": "Pharmaceuticals (+1 Medical Tech, max 5)", "goto": ("menunode_medicine_ip_allocation", {"choice": "pharma"})})
    if c < MEDICINE_CRYO_MAX:
        options.append({"key": ("3", "cryo", "cryosystem", "c"), "desc": "Cryosystem (+1 Medical Tech, max 5)", "goto": ("menunode_medicine_ip_allocation", {"choice": "cryo"})})
    options.append({"key": ("q", "quit"), "desc": "Cancel", "goto": None})

    text = "\n".join(lines)
    return text, tuple(options)


def start_ip_medicine_menu(caller, on_complete):
    """
    Start the Medicine specialty allocation menu for IP purchase.
    When complete, caller.ndb._ip_medicine_specialty_choice has the choice (surgery/pharma/cryo).
    Calls on_complete(caller) when done.
    """
    caller.ndb._ip_medicine_specialty_choice = None
    EvMenu(
        caller,
        "world.ip_medicine_menu",
        startnode="menunode_medicine_ip_allocation",
        cmdset_mergetype="Replace",
        cmd_on_exit=on_complete,
        auto_quit=True,
        auto_look=False,
    )
    return True
