"""
Agent app loadout command (parallel to deck loadout command).
"""

from evennia.commands.default.muxcommand import MuxCommand

from world.agents.agent_loadout import (
    format_agent_sheet,
    install_agent_app,
    remove_agent_app,
)


class CmdAgent(MuxCommand):
    """
    Manage Agent app loadouts for your devices.

    Usage:
      agent                         - Show all agent devices and installed apps
      agent <name>                  - Show one specific agent
      agent/install <agent>=<app>   - Install an app to that agent
      agent/remove <agent>=<app>    - Remove an app back to inventory

    Notes:
      - Supports external Agent gear and installed Internal Agent cyberware.
      - App capacity is tied to device profile/quality.
    """

    key = "agent"
    aliases = ["agents"]
    locks = "cmd:all()"
    help_category = "Economy & Inventory"

    def func(self):
        subs = [switch.lower() for switch in (self.switches or [])]
        raw_args = (self.args or "").strip()

        if subs and subs[0] == "install":
            self._do_install(raw_args)
            return
        if subs and subs[0] == "remove":
            self._do_remove(raw_args)
            return

        self.caller.msg(format_agent_sheet(self.caller, device_filter=raw_args or None))

    def _do_install(self, raw: str):
        if "=" not in raw:
            self.caller.msg("Usage: agent/install <agent name>=<app>")
            return
        left, right = raw.split("=", 1)
        ok, msg = install_agent_app(self.caller, left.strip(), right.strip())
        self.caller.msg(msg if ok else f"|r{msg}|n")

    def _do_remove(self, raw: str):
        if "=" not in raw:
            self.caller.msg("Usage: agent/remove <agent name>=<installed app>")
            return
        left, right = raw.split("=", 1)
        ok, msg = remove_agent_app(self.caller, left.strip(), right.strip())
        self.caller.msg(msg if ok else f"|r{msg}|n")

