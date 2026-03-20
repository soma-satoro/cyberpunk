# Sell Your Soul chargen EvMenu - 1500 eb + Neural Link or Neuroport in exchange for employer control

from evennia.utils.evmenu import EvMenu
from world.chargen_constants import (
    SELL_YOUR_SOUL_EBOOST,
    SELL_YOUR_SOUL_CATCHES,
    SELL_YOUR_SOUL_MILITARY_OPTIONS,
    SELL_YOUR_SOUL_CRIME_OPTIONS,
    SELL_YOUR_SOUL_CORPORATION_OPTIONS,
    SELL_YOUR_SOUL_GANG_OPTIONS,
)
from world.chargen_neural_helpers import (
    resolve_chargen_character,
    installed_neural_status,
    install_cyberware_chargen,
    install_neural_link_replacing_neuroport,
    install_neuroport_replacing_neural_link,
)
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.cyberware.models import Cyberware

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
    return "menunode_neural_choice"


def _set_neural_choice(caller, raw_string, pick=None, **kwargs):
    ctx = _get_context(caller)
    ctx["neural_pick"] = pick
    char = resolve_chargen_character(caller)
    ctx["neural_snapshot"] = installed_neural_status(char)
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

    char = resolve_chargen_character(caller)
    has_nl, has_np = installed_neural_status(char)

    cyber_bullet = (
        "- Free |gNeural Link|n or |gNeuroport|n (you choose after employer and catch)\n"
    )
    if has_nl and has_np:
        cyber_bullet = (
            "- |yNeural install:|n You already have both platforms; this offer adds eurodollars only\n"
        )
    elif has_nl or has_np:
        have = " and ".join(
            x for x, ok in (("Neural Link", has_nl), ("Neuroport", has_np)) if ok
        )
        cyber_bullet = (
            f"- |yNeural install:|n You already have |g{have}|n; adding the other is optional (next step)\n"
        )

    text = (
        "|rSell Your Soul|n\n\n"
        "Hire yourself out to someone who can afford to buy your cybernetics for you. "
        "Selecting this option provides:\n"
        f"- |g{SELL_YOUR_SOUL_EBOOST} eurodollars|n\n"
        f"{cyber_bullet}"
        "\nIn exchange, you pledge service to an employer who may hold one of several 'catches' over you.\n\n"
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


def menunode_neural_choice(caller, raw_string, **kwargs):
    char = resolve_chargen_character(caller)
    has_nl, has_np = installed_neural_status(char)

    text = "|yNeural install (Sell Your Soul)|n\n\n"
    options = []

    if has_nl and has_np:
        text += (
            "You already have a |gNeural Link|n and a |gNeuroport|n. "
            "No additional neural cyberware will be installed.\n\n"
            "|y1|n - Continue to confirmation\n"
            "|y0|n - Back"
        )
        options = [
            {"key": "1", "desc": "Continue", "goto": (_set_neural_choice, {"pick": "none"})},
            {"key": "0", "desc": "Back", "goto": "menunode_catch"},
        ]
        return text, options

    if not has_nl and not has_np:
        text += (
            "Choose your free neural platform (required):\n\n"
            "|y1|n - Neural Link\n"
            "|y2|n - Neuroport\n"
            "|y0|n - Back"
        )
        options = [
            {"key": "1", "desc": "Neural Link", "goto": (_set_neural_choice, {"pick": "neural_link"})},
            {"key": "2", "desc": "Neuroport", "goto": (_set_neural_choice, {"pick": "neuroport"})},
            {"key": "0", "desc": "Back", "goto": "menunode_catch"},
        ]
        return text, options

    if has_nl and not has_np:
        text += (
            "You already have a |gNeural Link|n. "
            "You may keep it, or replace it with a |gNeuroport|n (free).\n\n"
            "|y1|n - Add Neuroport (Neural Link removed)\n"
            "|y2|n - Keep Neural Link only\n"
            "|y0|n - Back"
        )
        options = [
            {"key": "1", "desc": "Neuroport", "goto": (_set_neural_choice, {"pick": "neuroport"})},
            {"key": "2", "desc": "Keep Neural Link", "goto": (_set_neural_choice, {"pick": "skip"})},
            {"key": "0", "desc": "Back", "goto": "menunode_catch"},
        ]
        return text, options

    # has_np and not has_nl
    text += (
        "You already have a |gNeuroport|n. "
        "You may keep it, or swap to a standalone |gNeural Link|n instead (free).\n\n"
        "|y1|n - Add Neural Link (Neuroport removed)\n"
        "|y2|n - Keep Neuroport only\n"
        "|y0|n - Back"
    )
    options = [
        {"key": "1", "desc": "Neural Link", "goto": (_set_neural_choice, {"pick": "neural_link"})},
        {"key": "2", "desc": "Keep Neuroport", "goto": (_set_neural_choice, {"pick": "skip"})},
        {"key": "0", "desc": "Back", "goto": "menunode_catch"},
    ]
    return text, options


def _describe_confirm_cyber(pick, had_nl, had_np):
    if pick == "none" or (had_nl and had_np):
        return "No neural install (you already have both platforms)."
    if pick == "skip":
        return "No change to neural cyberware."
    if pick == "neural_link":
        if had_np and not had_nl:
            return "Neuroport will be removed and Neural Link installed (free)."
        return "Neural Link will be installed (free)."
    if pick == "neuroport":
        if had_nl and not had_np:
            return "Neural Link will be removed and Neuroport installed (free)."
        return "Neuroport will be installed (free)."
    return "Neural install as chosen."


def menunode_confirm(caller, raw_string, **kwargs):
    ctx = _get_context(caller)
    employer = ctx.get("employer", "")
    catch = ctx.get("catch", "")
    pick = ctx.get("neural_pick")
    snap = ctx.get("neural_snapshot")
    if snap is None:
        char = resolve_chargen_character(caller)
        snap = installed_neural_status(char)
    had_nl, had_np = snap

    cyber_line = _describe_confirm_cyber(pick, had_nl, had_np)

    text = (
        f"|yConfirm Sell Your Soul|n\n\n"
        f"|yEmployer:|n {employer}\n"
        f"|yCatch:|n {catch}\n\n"
        f"You will receive |g{SELL_YOUR_SOUL_EBOOST} eurodollars|n.\n"
        f"{cyber_line}\n\n"
        "|y1|n - Confirm\n"
        "|y0|n - Cancel"
    )
    options = [
        {"key": "1", "desc": "Confirm", "goto": "menunode_do_confirm"},
        {"key": "0", "desc": "Cancel", "goto": "menunode_exit"},
    ]
    return text, options


def _apply_sell_your_soul_cyber(caller, pick, had_nl, had_np):
    char = resolve_chargen_character(caller)
    sheet = _get_sheet(caller)
    if not sheet:
        return

    if pick in (None, "none", "skip"):
        return

    nl = Cyberware.objects.filter(name__iexact="Neural Link").first()
    np_ = Cyberware.objects.filter(name__iexact="Neuroport").first()

    if pick == "neural_link":
        if not nl:
            caller.msg("|yNeural Link not found in database; skipped.|n")
            return
        if had_np and not had_nl:
            if install_neural_link_replacing_neuroport(char):
                caller.msg("|gNeural Link installed (Neuroport removed; options kept).|n")
            return
        if not had_nl:
            if install_cyberware_chargen(char, nl):
                caller.msg("|gNeural Link installed (free).|n")
        return

    if pick == "neuroport":
        if not np_:
            caller.msg("|yNeuroport not found in database; skipped.|n")
            return
        if had_nl and not had_np:
            if install_neuroport_replacing_neural_link(char):
                caller.msg("|gNeuroport installed (Neural Link removed; options kept).|n")
            return
        if not had_np:
            if install_cyberware_chargen(char, np_):
                caller.msg("|gNeuroport installed (free).|n")
        return


def menunode_do_confirm(caller, raw_string, **kwargs):
    """Apply Sell Your Soul: add eurodollars, neural cyber per choice, save to sheet."""
    sheet = _get_sheet(caller)
    if not sheet:
        caller.msg("No character sheet found.")
        return None, None

    ctx = _get_context(caller)
    employer = ctx.get("employer", "")
    employer_type = ctx.get("employer_type", "")
    catch = ctx.get("catch", "")
    pick = ctx.get("neural_pick")
    snap = ctx.get("neural_snapshot")
    if snap is None:
        snap = installed_neural_status(resolve_chargen_character(caller))
    had_nl, had_np = snap

    sheet.sell_your_soul = True
    sheet.sell_your_soul_employer_type = employer_type
    sheet.sell_your_soul_employer = employer
    sheet.sell_your_soul_catch = catch
    sheet.save(skip_recalculation=True)

    CharacterMoneyService.add_money(caller, SELL_YOUR_SOUL_EBOOST)

    try:
        _apply_sell_your_soul_cyber(caller, pick, had_nl, had_np)
    except Exception as e:
        caller.msg(f"Warning: neural install issue: {e}")

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
