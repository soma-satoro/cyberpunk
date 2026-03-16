# Sell Your Soul chargen EvMenu - 1500 eb + Neural Link in exchange for employer control

from evennia.utils.evmenu import EvMenu
from world.chargen_constants import (
    SELL_YOUR_SOUL_EBOOST,
    SELL_YOUR_SOUL_CATCHES,
    SELL_YOUR_SOUL_MILITARY_OPTIONS,
    SELL_YOUR_SOUL_CRIME_OPTIONS,
    SELL_YOUR_SOUL_CORPORATION_OPTIONS,
    SELL_YOUR_SOUL_GANG_OPTIONS,
)
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.cyberware.models import Cyberware
from world.inventory.models import Inventory, CyberwareInstance

_NDB_KEY = "_sellyoursoul_context"


def _get_sheet(caller):
    return getattr(caller, 'character_sheet', None)


def _get_context(caller):
    ctx = getattr(caller.ndb, _NDB_KEY, None)
    if ctx is None:
        setattr(caller.ndb, _NDB_KEY, {})
        ctx = getattr(caller.ndb, _NDB_KEY)
    return ctx


def _clear_context(caller):
    try:
        delattr(caller.ndb, _NDB_KEY)
    except AttributeError:
        pass


def _set_employer_type(caller, raw_string, employer_type=None, **kwargs):
    ctx = _get_context(caller)
    ctx["employer_type"] = employer_type
    return "menunode_employer"


def _set_employer(caller, raw_string, employer=None, employer_type=None, **kwargs):
    ctx = _get_context(caller)
    ctx["employer"] = employer
    ctx["employer_type"] = employer_type or ctx.get("employer_type")
    return "menunode_catch"


def _set_catch(caller, raw_string, catch=None, employer=None, employer_type=None, **kwargs):
    ctx = _get_context(caller)
    ctx["catch"] = catch
    ctx["employer"] = employer or ctx.get("employer")
    ctx["employer_type"] = employer_type or ctx.get("employer_type")
    return "menunode_confirm"


def menunode_start(caller, raw_string, **kwargs):
    sheet = _get_sheet(caller)
    if not sheet:
        caller.msg("No character sheet found. Complete chargen first.")
        return None, None

    if getattr(sheet, 'sell_your_soul', False):
        employer = getattr(sheet, 'sell_your_soul_employer', '') or "Unknown"
        catch = getattr(sheet, 'sell_your_soul_catch', '') or "Unknown"
        text = (
            "You have already chosen to Sell Your Soul.\n"
            f"|yEmployer:|n {employer}\n"
            f"|yCatch:|n {catch}\n"
            "\nThis cannot be changed. Use |wsellyoursoul/clear|n to remove it (admin only)."
        )
        return text, None

    text = (
        "|rSell Your Soul|n\n\n"
        "Hire yourself out to someone who can afford to buy your cybernetics for you. "
        "Selecting this option provides:\n"
        f"- |g{SELL_YOUR_SOUL_EBOOST} eurodollars|n\n"
        "- Free |gNeural Link|n cyberware (installed)\n\n"
        "In exchange, you pledge service to an employer who may hold one of several 'catches' over you.\n\n"
        "|y1|n - Choose Employer Type (Military / Crime / Corporation)\n"
        "|y2|n - Cancel"
    )
    options = [
        {"key": "1", "desc": "Choose employer type", "goto": "menunode_employer_type"},
        {"key": "2", "desc": "Cancel", "goto": "menunode_exit"},
    ]
    return text, options


def menunode_employer_type(caller, raw_string, **kwargs):
    text = (
        "|yEmployer Type|n\n\n"
        "|y1|n - Military (Covert forces, national armies)\n"
        "|y2|n - Organized Crime (Mob, Yakuza, Triads, Cartels)\n"
        "|y3|n - Corporation (Mega-corps from 2077)\n"
        "|y4|n - Gang (Street gangs, nomad clans, crews)\n"
        "|y0|n - Back"
    )
    options = [
        {"key": "1", "desc": "Military", "goto": (_set_employer_type, {"employer_type": "military"})},
        {"key": "2", "desc": "Organized Crime", "goto": (_set_employer_type, {"employer_type": "crime"})},
        {"key": "3", "desc": "Corporation", "goto": (_set_employer_type, {"employer_type": "corporation"})},
        {"key": "4", "desc": "Gang", "goto": (_set_employer_type, {"employer_type": "gang"})},
        {"key": "0", "desc": "Back", "goto": "menunode_start"},
    ]
    return text, options


def menunode_employer(caller, raw_string, **kwargs):
    ctx = _get_context(caller)
    employer_type = ctx.get("employer_type", "military")
    if employer_type == "military":
        opts = SELL_YOUR_SOUL_MILITARY_OPTIONS
    elif employer_type == "crime":
        opts = SELL_YOUR_SOUL_CRIME_OPTIONS
    elif employer_type == "corporation":
        opts = SELL_YOUR_SOUL_CORPORATION_OPTIONS
    else:
        opts = SELL_YOUR_SOUL_GANG_OPTIONS  # gang

    text = f"|ySelect Employer ({employer_type.title()})|n\n\n"
    options = []
    for i, emp in enumerate(opts, 1):
        options.append({
            "key": str(i),
            "desc": emp,
            "goto": (_set_employer, {"employer": emp, "employer_type": employer_type}),
        })
    options.append({"key": "0", "desc": "Back", "goto": "menunode_employer_type"})
    text += "\n".join(f"|y{i}|n - {e}" for i, e in enumerate(opts, 1))
    text += "\n|y0|n - Back"
    return text, options


def menunode_catch(caller, raw_string, **kwargs):
    ctx = _get_context(caller)
    employer = ctx.get("employer", "")
    employer_type = ctx.get("employer_type", "military")

    text = (
        "|ySelect Your Catch|n\n\n"
        "The controlling agency holds one of these over you:\n\n"
    )
    options = []
    for i, catch in enumerate(SELL_YOUR_SOUL_CATCHES, 1):
        options.append({
            "key": str(i),
            "desc": catch,
            "goto": (_set_catch, {"catch": catch, "employer": employer, "employer_type": employer_type}),
        })
    options.append({"key": "0", "desc": "Back", "goto": "menunode_employer"})
    text += "\n".join(f"|y{i}|n - {c}" for i, c in enumerate(SELL_YOUR_SOUL_CATCHES, 1))
    text += "\n|y0|n - Back"
    return text, options


def menunode_confirm(caller, raw_string, **kwargs):
    ctx = _get_context(caller)
    employer = ctx.get("employer", "")
    catch = ctx.get("catch", "")

    text = (
        f"|yConfirm Sell Your Soul|n\n\n"
        f"|yEmployer:|n {employer}\n"
        f"|yCatch:|n {catch}\n\n"
        f"You will receive |g{SELL_YOUR_SOUL_EBOOST} eurodollars|n and a free |gNeural Link|n.\n\n"
        "|y1|n - Confirm\n"
        "|y0|n - Cancel"
    )
    options = [
        {"key": "1", "desc": "Confirm", "goto": "menunode_do_confirm"},
        {"key": "0", "desc": "Cancel", "goto": "menunode_exit"},
    ]
    return text, options


def menunode_do_confirm(caller, raw_string, **kwargs):
    """Apply Sell Your Soul: add 1500 eb, Neural Link, save to sheet."""
    sheet = _get_sheet(caller)
    if not sheet:
        caller.msg("No character sheet found.")
        return None, None

    ctx = _get_context(caller)
    employer = ctx.get("employer", "")
    employer_type = ctx.get("employer_type", "")
    catch = ctx.get("catch", "")

    # Save to sheet
    sheet.sell_your_soul = True
    sheet.sell_your_soul_employer_type = employer_type
    sheet.sell_your_soul_employer = employer
    sheet.sell_your_soul_catch = catch
    sheet.save(skip_recalculation=True)

    # Add 1500 eb
    CharacterMoneyService.add_money(caller, SELL_YOUR_SOUL_EBOOST)

    # Install Neural Link if not already present
    try:
        neural_link = Cyberware.objects.get(name="Neural Link")
        inventory, _ = Inventory.get_or_create_for_character(caller)
        if not inventory.cyberware.filter(cyberware=neural_link, installed=True).exists():
            instance = CyberwareInstance.objects.create(
                cyberware=neural_link,
                character_sheet=sheet,
                character_object=caller,
                installed=True,
            )
            inventory.cyberware.add(instance)
            sheet.calculate_humanity_loss()
            sheet.save()
            caller.msg("Neural Link installed (free).")
    except Cyberware.DoesNotExist:
        pass  # Neural Link not in DB - skip
    except Exception as e:
        caller.msg(f"Warning: Could not install Neural Link: {e}")

    caller.msg(
        f"You have Sold Your Soul to {employer}. "
        f"Your catch: {catch}. +{SELL_YOUR_SOUL_EBOOST} eb added."
    )
    _clear_context(caller)
    return None, None


def menunode_exit(caller, raw_string, **kwargs):
    _clear_context(caller)
    caller.msg("Sell Your Soul cancelled.")
    return None, None


def start_sellyoursoul_menu(caller):
    EvMenu(caller, "world.sellyoursoul_menu", startnode="menunode_start")
