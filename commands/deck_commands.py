"""
Cyberdeck loadout: programs, Black ICE, and hardware (inventory-style view + install/remove).
"""

from evennia.commands.default.muxcommand import MuxCommand

from world.netrunning.deck_loadout import (
    format_deck_sheet,
    install_deck_item,
    remove_deck_item,
)


class CmdDeck(MuxCommand):
    """
    Manage your cyberdeck program and hardware loadout.

    Usage:
      deck                          - All cyberdecks you carry (full sheet)
      deck <name>                   - Focus one deck (partial name ok)
      deck/install <deck>=<item>    - Load program, Black ICE, or hardware (fuzzy name)
      deck/remove <deck>=<item>    - Unload to inventory

    Items must be in your inventory or on a crafted voucher (program / deck option).
    Slots: total = program + hardware + flexible slots from equipment_data; all share one pool.
    """

    key = "deck"
    aliases = ["decks"]
    locks = "cmd:all()"
    help_category = "Netrunning"

    def func(self):
        subs = [s.lower() for s in (self.switches or [])]
        raw_args = (self.args or "").strip()

        if subs and subs[0] == "install":
            self._do_install(raw_args)
            return
        if subs and subs[0] == "remove":
            self._do_remove(raw_args)
            return

        # deck / deck <partial name>
        filt = raw_args if raw_args else None
        self.caller.msg(format_deck_sheet(self.caller, deck_name_filter=filt))

    def _do_install(self, raw: str):
        if "=" not in raw:
            self.caller.msg("Usage: deck/install <cyberdeck name>=<program, Black ICE, or hardware>")
            return
        left, right = raw.split("=", 1)
        ok, msg = install_deck_item(self.caller, left.strip(), right.strip())
        self.caller.msg(msg if ok else f"|r{msg}|n")

    def _do_remove(self, raw: str):
        if "=" not in raw:
            self.caller.msg("Usage: deck/remove <cyberdeck name>=<installed item>")
            return
        left, right = raw.split("=", 1)
        ok, msg = remove_deck_item(self.caller, left.strip(), right.strip())
        self.caller.msg(msg if ok else f"|r{msg}|n")
