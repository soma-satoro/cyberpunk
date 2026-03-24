"""
Game-side safe wrapper around Evennia's EvMore pager.

This avoids duplicate pager command collisions by cleaning up any existing
pager cmdset/state on caller/account before attaching a new pager.
"""

from evennia.utils.evmore import CmdSetMore, EvMore


class SafeEvMore(EvMore):
    """EvMore variant that safely replaces any existing pager state."""

    def _clear_existing_pager(self):
        """Remove stale pager state from caller and linked account."""
        targets = [self._caller]
        account = getattr(self._caller, "account", None)
        if account and account is not self._caller:
            targets.append(account)

        for target in targets:
            # remove any stacked pager cmdsets, not just one instance
            for _ in range(10):
                removed = False
                for cmdset_ref in (CmdSetMore, "more_commands"):
                    try:
                        target.cmdset.remove(cmdset_ref)
                        removed = True
                    except Exception:
                        pass
                if not removed:
                    break

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
        self._caller.ndb._more = self
        self._caller.cmdset.add(CmdSetMore)
        self.page_top()


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
