"""Chargen helpers: Neural Link / Neuroport detection, removal, and installs."""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

from world.cyberware.models import Cyberware


def resolve_chargen_character(caller: Any) -> Any:
    """Resolve ObjectDB character (caller may be Account with .character)."""
    if getattr(caller, "character", None):
        return caller.character
    return caller


def _inventory_and_sheet(character: Any) -> Tuple[Optional[Any], Optional[Any]]:
    from world.inventory.models import Inventory

    sheet = getattr(character, "character_sheet", None)
    if not sheet:
        return None, None
    inventory, _ = Inventory.get_or_create_for_character(character)
    return inventory, sheet


def installed_neural_status(character: Any) -> Tuple[bool, bool]:
    """Return (has_neural_link, has_neuroport) among installed cyberware."""
    inventory, _ = _inventory_and_sheet(character)
    if not inventory:
        return False, False
    has_nl = inventory.cyberware.filter(
        cyberware__name__iexact="Neural Link", installed=True
    ).exists()
    has_np = inventory.cyberware.filter(
        cyberware__name__iexact="Neuroport", installed=True
    ).exists()
    return has_nl, has_np


def delete_installed_cyberware_by_name(character: Any, name_iexact: str) -> int:
    """Delete installed instances; CASCADE removes children. Refreshes HL. Returns count."""
    inventory, sheet = _inventory_and_sheet(character)
    if not inventory or not sheet:
        return 0
    qs = list(
        inventory.cyberware.filter(cyberware__name__iexact=name_iexact, installed=True)
    )
    n = len(qs)
    for inst in qs:
        inst.delete()
    if n:
        if hasattr(sheet, "calculate_humanity_loss"):
            sheet.calculate_humanity_loss()
        sheet.save()
    return n


def remove_installed_neural_link(character: Any) -> int:
    return delete_installed_cyberware_by_name(character, "Neural Link")


def remove_installed_neuroport(character: Any) -> int:
    return delete_installed_cyberware_by_name(character, "Neuroport")


def install_cyberware_chargen(character: Any, cyberware: Cyberware) -> bool:
    """
    Grant one installed instance (chargen / free): inventory link + HL hooks.
    Returns True if a new row was created.
    """
    from world.inventory.models import CyberwareInstance

    inventory, sheet = _inventory_and_sheet(character)
    if not inventory or not sheet:
        return False
    if inventory.cyberware.filter(cyberware=cyberware, installed=True).exists():
        return False
    char_obj = character if getattr(character, "pk", None) else None
    instance = CyberwareInstance.objects.create(
        cyberware=cyberware,
        character_sheet=sheet,
        character_object=char_obj,
        installed=True,
    )
    inventory.cyberware.add(instance)
    if hasattr(sheet, "consume_uninstalled_hl_for_cyberware"):
        sheet.consume_uninstalled_hl_for_cyberware(cyberware)
    if hasattr(sheet, "calculate_humanity_loss"):
        sheet.calculate_humanity_loss()
    sheet.save()
    return True


def replace_neural_platform(
    character: Any,
    *,
    old_base_name_iexact: str,
    new_cyberware: Cyberware,
) -> bool:
    """
    Replace installed base row(s) (Neural Link or Neuroport) with a new base instance.

    Direct children in inventory that pointed at the old base are re-parented to the new
    base so they are not lost to CASCADE when the old base row is deleted. Deeper trees
    (option -> sub-option) keep their own parent links unchanged.
    """
    from world.inventory.models import CyberwareInstance

    inventory, sheet = _inventory_and_sheet(character)
    if not inventory or not sheet:
        return False
    if inventory.cyberware.filter(cyberware=new_cyberware, installed=True).exists():
        return False

    old_bases = list(
        inventory.cyberware.filter(
            cyberware__name__iexact=old_base_name_iexact, installed=True
        )
    )
    if not old_bases:
        return False

    char_obj = character if getattr(character, "pk", None) else None
    new_inst = CyberwareInstance.objects.create(
        cyberware=new_cyberware,
        character_sheet=sheet,
        character_object=char_obj,
        installed=True,
    )
    inventory.cyberware.add(new_inst)
    if hasattr(sheet, "consume_uninstalled_hl_for_cyberware"):
        sheet.consume_uninstalled_hl_for_cyberware(new_cyberware)

    for old in old_bases:
        for child in inventory.cyberware.filter(parent_id=old.id):
            child.parent = new_inst
            child.save(update_fields=["parent"])
        old.delete()

    if hasattr(sheet, "calculate_humanity_loss"):
        sheet.calculate_humanity_loss()
    sheet.save()
    return True


def install_neuroport_replacing_neural_link(character: Any) -> bool:
    """Install Neuroport, re-parenting Neural Link children then removing Neural Link."""
    has_nl, has_np = installed_neural_status(character)
    if has_np:
        return False
    np_cw = Cyberware.objects.filter(name__iexact="Neuroport").first()
    if not np_cw:
        return False
    if not has_nl:
        return install_cyberware_chargen(character, np_cw)
    return replace_neural_platform(
        character, old_base_name_iexact="Neural Link", new_cyberware=np_cw
    )


def install_neural_link_replacing_neuroport(character: Any) -> bool:
    """Install Neural Link, re-parenting Neuroport children then removing Neuroport."""
    has_nl, has_np = installed_neural_status(character)
    if has_nl:
        return False
    nl_cw = Cyberware.objects.filter(name__iexact="Neural Link").first()
    if not nl_cw:
        return False
    if not has_np:
        return install_cyberware_chargen(character, nl_cw)
    return replace_neural_platform(
        character, old_base_name_iexact="Neuroport", new_cyberware=nl_cw
    )


def grant_neuroport_for_lifepath_yes(character: Any, msg: Optional[Callable] = None) -> None:
    """
    Lifepath 'Yes' to Neuroport: install Neuroport, removing Neural Link first if present.
    If Neuroport is already installed, caller should use the already-owned stipend path instead.
    """
    has_nl, has_np = installed_neural_status(character)
    if has_np:
        if msg:
            msg("|y  >> You already have a Neuroport.|n")
        return
    np_cw = Cyberware.objects.filter(name__iexact="Neuroport").first()
    if not np_cw:
        if msg:
            msg("|y  >> Neuroport cyberware not found in database.|n")
        return
    if install_neuroport_replacing_neural_link(character):
        if msg:
            if has_nl:
                msg("|g  >> Neuroport installed (Neural Link removed; options kept).|n")
            else:
                msg("|g  >> You received a free Neuroport!|n")
    elif msg:
        msg("|r  >> Could not install Neuroport.|n")
