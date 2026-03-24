"""
Game-side safe wrapper around Evennia's EvMore pager.

This avoids duplicate pager command collisions by cleaning up any existing
pager cmdset/state on caller/account before attaching a new pager.
"""

from evennia.utils.evmore import CmdSetMore, EvMore


class SafeEvMore(EvMore):
    """EvMore variant that safely replaces any existing pager state."""

    def _collect_targets(self):
        """
        Collect all likely holders of pager state for this interaction.

        Depending on which cmdset the active help command came from, caller may
        be Character or Account. We include both plus current session puppet.
        """
        targets = []

        def _add(obj):
            if obj and obj not in targets:
                targets.append(obj)

        _add(self._caller)
        _add(getattr(self._caller, "account", None))
        _add(getattr(self._session, "puppet", None))
        return targets

    @staticmethod
    def _is_more_cmdset(cmdset_obj):
        """Identify Evennia's pager cmdset by key/path."""
        key = str(getattr(cmdset_obj, "key", "")).lower()
        path = str(getattr(cmdset_obj, "path", "")).lower()
        return key == "more_commands" or path.endswith("evennia.utils.evmore.cmdsetmore")

    def _anchor_target(self):
        """Use account as pager anchor when available."""
        return getattr(self._caller, "account", None) or self._caller

    def _remove_more_cmdsets(self, target):
        """Remove all pager cmdset instances from a target."""
        # Fast path: remove by key/class repeatedly.
        for _ in range(10):
            removed_any = False
            for ref in ("more_commands", CmdSetMore):
                try:
                    target.cmdset.remove(ref)
                    removed_any = True
                except Exception:
                    pass
            if not removed_any:
                break

        # Fallback: iterate actual stack and remove matching objects.
        for _ in range(10):
            removed_any = False
            try:
                active_sets = list(target.cmdset.all())
            except Exception:
                active_sets = []

            for cmdset_obj in active_sets:
                if self._is_more_cmdset(cmdset_obj):
                    try:
                        target.cmdset.remove(cmdset_obj)
                        removed_any = True
                    except Exception:
                        pass

            if not removed_any:
                break

    def _clear_existing_pager(self):
        """Remove stale pager state from caller and linked account."""
        for target in self._collect_targets():
            self._remove_more_cmdsets(target)

            try:
                del target.ndb._more
            except Exception:
                pass

    def start(self):
        """
        Starts pagination.

        Mirrors Evennia behavior but first clears old pager state to avoid
        duplicate `CmdMore` commands in merged cmdsets.
        """
        if self._npages <= 1 and not self._always_page:
            self.display(show_footer=False)
            return

        self._clear_existing_pager()
        # Store reference on all likely holders so CmdMore/CmdMoreExit can
        # resolve pager state regardless of which object handled the command.
        for target in self._collect_targets():
            try:
                target.ndb._more = self
            except Exception:
                pass

        # Add pager cmdset on a single anchor only to avoid duplicate matches.
        self._anchor_target().cmdset.add(CmdSetMore)
        self.page_top()

    def page_quit(self, quiet=False):
        """
        Quit pager and clear pager state from all likely holders.

        This mirrors EvMore.page_quit but prevents stale pager state from
        lingering on account/character/session-puppet combinations.
        """
        for target in self._collect_targets():
            self._remove_more_cmdsets(target)
            try:
                del target.ndb._more
            except Exception:
                pass

        if not quiet:
            self._caller.msg(text=self._exit_msg, **self._kwargs)
        if self.exit_cmd:
            self._caller.execute_cmd(self.exit_cmd, session=self._session)


def msg(
    caller,
    text="",
    always_page=False,
    session=None,
    justify=False,
    justify_kwargs=None,
    exit_on_lastpage=True,
    **kwargs,
):
    """Safe EvMore-backed message helper with EvMore-compatible signature."""
    SafeEvMore(
        caller,
        text,
        always_page=always_page,
        session=session,
        justify=justify,
        justify_kwargs=justify_kwargs,
        exit_on_lastpage=exit_on_lastpage,
        **kwargs,
    )
