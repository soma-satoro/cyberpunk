"""
Custom help command with /search switch for finding help topics by keyword.

CmdHelp overrides parse() and does not call MuxCommand.parse(), so switches
are never extracted. We override parse() to run MuxCommand.parse() first,
then CmdHelp.parse() when not using /search, so that help/search works.

Help text has ANSI stripped so that pipes (e.g. add|remove) in usage examples
display correctly instead of being interpreted as color codes.
"""
from evennia.commands.default.help import CmdHelp
from evennia.commands.default.syscommands import SystemNoMatch
from evennia.commands.cmdhandler import CMD_NOMATCH
from evennia.commands.cmdset import CmdSet
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.utils import string_suggestions


_HELP_PAGER_FOOTER = (
    "|n(|wHelp pager|n: |w+hpage next|n || |w+hpage prev|n || "
    "|w+hpage top|n || |w+hpage end|n || |w+hpage quit|n)"
)


def _get_help_pager_session(caller, session=None):
    """Resolve the session to use for help paging output."""
    if session:
        return session
    sessions = caller.sessions.get()
    if sessions:
        return sessions[0]
    return None


def _split_help_pages(text, session):
    """Split help text into pages based on session dimensions."""
    if text is None:
        text = ""
    lines = str(text).split("\n")

    screen_h = 25
    screen_w = 80
    if session:
        screen_h = session.protocol_flags.get("SCREENHEIGHT", {0: 25}).get(0, 25)
        screen_w = session.protocol_flags.get("SCREENWIDTH", {0: 80}).get(0, 80)

    height = max(4, int(screen_h) - 4)
    width = max(1, int(screen_w))
    height = min(10000 // width, height)

    pages = ["\n".join(lines[i : i + height]) for i in range(0, len(lines), height)]
    return pages or [""]


def _get_help_pager_state(caller):
    """Get active help pager state from caller or linked account."""
    state = getattr(caller.ndb, "_help_pager", None)
    if state:
        return state
    account = getattr(caller, "account", None)
    if account:
        return getattr(account.ndb, "_help_pager", None)
    return None


def _clear_help_pager_state(caller):
    """Clear active help pager state from caller and account."""
    try:
        del caller.ndb._help_pager
    except Exception:
        pass
    account = getattr(caller, "account", None)
    if account:
        try:
            del account.ndb._help_pager
        except Exception:
            pass


def _display_help_pager_page(caller, state, show_footer=True):
    """Render one page of help pager output."""
    pages = state["pages"]
    npos = max(0, min(state["npos"], len(pages) - 1))
    state["npos"] = npos
    text = pages[npos]
    if show_footer and len(pages) > 1:
        text = (
            f"{text}\n|n(|wPage|n [{npos + 1}/{len(pages)}] "
            f"|wn|next|n || |wprev|n || "
            f"|wtop|n || |wend|n || |w+hpage quit|n)"
        )
    text_outputfunc = (text, (), state.get("text_kwargs", {}))
    caller.msg(text=text_outputfunc, session=state.get("session"), **state.get("kwargs", {}))


def start_help_pager(caller, text, session=None, **kwargs):
    """
    Start a help pager using static command keys.

    This avoids dynamic pager cmdset insertion and one-letter alias multimatch.
    """
    session = _get_help_pager_session(caller, session=session)
    pages = _split_help_pages(text, session)

    # No pager state needed for single-page output.
    if len(pages) <= 1:
        text_outputfunc = (pages[0], (), kwargs.pop("text_kwargs", {}))
        caller.msg(text=text_outputfunc, session=session, **kwargs)
        return

    text_kwargs = kwargs.pop("text_kwargs", {})
    state = {
        "pages": pages,
        "npos": 0,
        "session": session,
        "text_kwargs": text_kwargs,
        "kwargs": kwargs,
        "exit_on_lastpage": True,
    }

    _clear_help_pager_state(caller)
    caller.ndb._help_pager = state
    account = getattr(caller, "account", None)
    if account:
        account.ndb._help_pager = state

    _display_help_pager_page(caller, state, show_footer=True)


class CmdHelpPage(MuxCommand):
    """
    Navigate the active help pager.

    Usage:
      +hpage <next|prev|top|end|quit>
    """

    key = "+hpage"
    aliases = ["hpage"]
    locks = "cmd:all()"
    help_category = "World & Information"

    def func(self):
        state = _get_help_pager_state(self.caller)
        if not state:
            self.caller.msg("No active help pager. Use |whelp|n to open one.")
            return

        action = (self.args or "next").strip().lower()
        pages = state["pages"]
        last = len(pages) - 1

        if action in ("quit", "q", "abort", "a", "stop", "endpager"):
            _clear_help_pager_state(self.caller)
            self.caller.msg("|xExited help pager.|n")
            return

        if action in ("prev", "previous", "p", "back"):
            state["npos"] = max(0, state["npos"] - 1)
            _display_help_pager_page(self.caller, state, show_footer=True)
            return

        if action in ("top", "start", "first"):
            state["npos"] = 0
            _display_help_pager_page(self.caller, state, show_footer=True)
            return

        if action in ("end", "last", "bottom"):
            state["npos"] = last
            _display_help_pager_page(self.caller, state, show_footer=True)
            return

        # default: next
        if state["npos"] >= last:
            _clear_help_pager_state(self.caller)
            self.caller.msg("|xExited help pager.|n")
            return

        state["npos"] += 1
        if state.get("exit_on_lastpage") and state["npos"] >= last:
            _display_help_pager_page(self.caller, state, show_footer=False)
            _clear_help_pager_state(self.caller)
            return
        _display_help_pager_page(self.caller, state, show_footer=True)


class CmdPagerNext(MuxCommand):
    """
    Advance an active pager one page.

    Works for both the custom help pager and Evennia's native EvMore pager.
    """

    key = "n"
    aliases = ["next"]
    locks = "cmd:all()"
    help_category = "World & Information"
    auto_help = False

    def _try_direction_fallback(self):
        """
        If no pager is active and user entered `n`, try room-exit traversal.
        """
        if self.cmdstring.lower() != "n":
            return False

        caller = self.caller
        location = getattr(caller, "location", None)
        if not location:
            return False

        try:
            exits = list(location.exits)
        except Exception:
            exits = []

        for ex in exits:
            key = str(getattr(ex, "key", "")).lower()
            aliases = []
            try:
                aliases = [alias.lower() for alias in ex.aliases.all()]
            except Exception:
                pass
            if "n" not in ([key] + aliases):
                continue

            if ex.access(caller, "traverse"):
                ex.at_traverse(caller, ex.destination)
            else:
                ex.at_failed_traverse(caller)
            return True

        return False

    def func(self):
        # 1) Custom help pager state.
        help_state = _get_help_pager_state(self.caller)
        if help_state:
            pages = help_state["pages"]
            last = len(pages) - 1
            if help_state["npos"] >= last:
                _clear_help_pager_state(self.caller)
                self.caller.msg("|xExited help pager.|n")
            else:
                help_state["npos"] += 1
                if help_state.get("exit_on_lastpage") and help_state["npos"] >= last:
                    _display_help_pager_page(self.caller, help_state, show_footer=False)
                    _clear_help_pager_state(self.caller)
                    return
                _display_help_pager_page(self.caller, help_state, show_footer=True)
            return

        # 2) Native Evennia pager state.
        more = getattr(self.caller.ndb, "_more", None)
        if not more and hasattr(self.caller, "account") and self.caller.account:
            more = getattr(self.caller.account.ndb, "_more", None)
        if more:
            try:
                more.page_next()
            except Exception:
                self.caller.msg("Error in loading the pager. Contact an admin.")
            return

        if self._try_direction_fallback():
            return

        # If no pager is active, let plain `n` fall through to the normal
        # directional command parser rather than swallowing it.
        if self.cmdstring.lower() == "n":
            self.caller.execute_cmd("north", session=self.session)
            return

        self.caller.msg("No active pager.")


class _PagerActionCommand(MuxCommand):
    """Base for global pager action commands."""

    action = None
    auto_help = False
    locks = "cmd:all()"
    help_category = "World & Information"

    def _get_more(self):
        more = getattr(self.caller.ndb, "_more", None)
        if not more and hasattr(self.caller, "account") and self.caller.account:
            more = getattr(self.caller.account.ndb, "_more", None)
        return more

    def _do_help_pager(self, state):
        pages = state["pages"]
        last = len(pages) - 1
        action = self.action

        if action == "quit":
            _clear_help_pager_state(self.caller)
            self.caller.msg("|xExited help pager.|n")
            return True
        if action == "prev":
            state["npos"] = max(0, state["npos"] - 1)
            _display_help_pager_page(self.caller, state, show_footer=True)
            return True
        if action == "top":
            state["npos"] = 0
            _display_help_pager_page(self.caller, state, show_footer=True)
            return True
        if action == "end":
            state["npos"] = last
            _display_help_pager_page(self.caller, state, show_footer=True)
            return True
        return False

    def _do_more_pager(self, more):
        action = self.action
        if action == "quit":
            more.page_quit()
            return True
        if action == "prev":
            more.page_back()
            return True
        if action == "top":
            more.page_top()
            return True
        if action == "end":
            more.page_end()
            return True
        return False

    def func(self):
        state = _get_help_pager_state(self.caller)
        if state:
            if self._do_help_pager(state):
                return

        more = self._get_more()
        if more:
            try:
                if self._do_more_pager(more):
                    return
            except Exception:
                self.caller.msg("Error in loading the pager. Contact an admin.")
                return

        self.caller.msg("No active pager.")


class CmdPagerTop(_PagerActionCommand):
    """Jump to top of active pager."""

    key = "top"
    aliases = ["start", "first"]
    action = "top"


class CmdPagerEnd(_PagerActionCommand):
    """Jump to end of active pager."""

    key = "end"
    aliases = ["last", "bottom"]
    action = "end"


class CmdPagerPrev(_PagerActionCommand):
    """Go to previous page of active pager (full word only)."""

    key = "prev"
    aliases = ["previous", "back"]
    action = "prev"


class PagerNavCmdSet(CmdSet):
    """
    High-priority pager navigation override.

    Lets `n`/`next` work even when native pager cmdsets collide.
    """

    key = "pager_nav_commands"
    priority = 120
    mergetype = "Union"
    # Keep local room/object commandsets (including ExitCmdSet) available.
    # Without explicit False, higher-priority cmdset merges can inherit
    # restrictive flags from other active cmdsets and hide exit aliases.
    no_exits = False
    no_objs = False

    def at_cmdset_creation(self):
        self.add(CmdPagerNext())
        self.add(CmdPagerTop())
        self.add(CmdPagerEnd())
        self.add(CmdPagerPrev())


class CmdPagerDebug(MuxCommand):
    """
    Debug active pager state on character/account/session.

    Usage:
      +pagerdebug
      pagerdebug
    """

    key = "+pagerdebug"
    aliases = ["pagerdebug"]
    locks = "cmd:perm(Developer) or perm(Admin)"
    help_category = "Admin"

    @staticmethod
    def _cmdset_debug_lines(holder_label, holder):
        """Build debug lines for a cmdset holder."""
        lines = [f"|w{holder_label}|n: {holder!r}"]
        if not holder:
            return lines

        try:
            cmdsets = list(holder.cmdset.all())
        except Exception as err:
            lines.append(f"  cmdset.all() failed: {err!r}")
            return lines

        lines.append(f"  stored_cmdsets={len(cmdsets)}")
        more_count = 0
        for cmdset_obj in cmdsets:
            key = str(getattr(cmdset_obj, "key", ""))
            path = str(getattr(cmdset_obj, "path", ""))
            if key.lower() == "more_commands" or path.lower().endswith(
                "evennia.utils.evmore.cmdsetmore"
            ):
                more_count += 1
            lines.append(f"    - key={key!r} path={path!r}")

        lines.append(f"  more_cmdset_count={more_count}")
        try:
            stack = list(getattr(holder.cmdset, "cmdset_stack", []) or [])
        except Exception as err:
            lines.append(f"  cmdset_stack read failed: {err!r}")
            stack = []
        if stack:
            lines.append(f"  live_stack_count={len(stack)}")
            stack_more_count = 0
            for cs in stack:
                skey = str(getattr(cs, "key", ""))
                spath = str(getattr(cs, "path", ""))
                sno_exits = getattr(cs, "no_exits", None)
                sno_objs = getattr(cs, "no_objs", None)
                sprio = getattr(cs, "priority", None)
                if skey.lower() == "more_commands" or spath.lower().endswith(
                    "evennia.utils.evmore.cmdsetmore"
                ):
                    stack_more_count += 1
                lines.append(
                    f"    * stack key={skey!r} path={spath!r} prio={sprio!r} "
                    f"no_exits={sno_exits!r} no_objs={sno_objs!r}"
                )
            lines.append(f"  live_stack_more_count={stack_more_count}")
        try:
            more_ref = holder.ndb._more
        except Exception as err:
            lines.append(f"  ndb._more read failed: {err!r}")
        else:
            lines.append(f"  ndb._more={more_ref!r}")
        return lines

    def func(self):
        caller = self.caller
        account = getattr(caller, "account", None)
        session = self.session
        puppet = getattr(session, "puppet", None) if session else None

        lines = [
            "|yPager Debug|n",
            f"caller={caller!r}",
            f"account={account!r}",
            f"session={session!r}",
            f"session.puppet={puppet!r}",
            "",
        ]
        lines.extend(self._cmdset_debug_lines("Caller", caller))
        lines.append("")
        lines.extend(self._cmdset_debug_lines("Session", session))
        lines.append("")
        lines.extend(self._cmdset_debug_lines("Account", account))
        if puppet is not None and puppet is not caller:
            lines.append("")
            lines.extend(self._cmdset_debug_lines("Session puppet", puppet))

        self.caller.msg("\n".join(lines))


class CmdNoMatchExitFallback(SystemNoMatch):
    """
    Fallback for unmatched input to support local exit aliases reliably.

    If no normal command matched, try exact single-token match against
    exits in caller's current room before reporting command-not-found.
    """

    key = CMD_NOMATCH
    locks = "cmd:all()"

    def func(self):
        raw = (self.args or "").strip()
        caller = self.caller

        if raw and " " not in raw and "/" not in raw:
            token = raw.lower()
            location = getattr(caller, "location", None)
            if location:
                try:
                    exits = list(location.exits)
                except Exception:
                    exits = []

                matches = []
                for ex in exits:
                    names = [str(getattr(ex, "key", "")).lower()]
                    try:
                        names.extend(alias.lower() for alias in ex.aliases.all())
                    except Exception:
                        pass
                    if token in names:
                        matches.append(ex)

                if len(matches) == 1:
                    ex = matches[0]
                    if ex.access(caller, "traverse"):
                        ex.at_traverse(caller, ex.destination)
                    else:
                        ex.at_failed_traverse(caller)
                    return

        # Friendly fallback text instead of stock "Huh?"
        msg = f"Command '{raw}' is not available."
        suggestions = []
        try:
            if raw and getattr(self, "cmdset", None):
                suggestions = string_suggestions(
                    raw,
                    self.cmdset.get_all_cmd_keys_and_aliases(caller),
                    cutoff=0.7,
                    maxnum=3,
                )
        except Exception:
            suggestions = []

        if suggestions:
            if len(suggestions) == 1:
                msg += f" Maybe you meant '{suggestions[0]}'?"
            elif len(suggestions) == 2:
                msg += f" Maybe you meant '{suggestions[0]}' or '{suggestions[1]}'?"
            else:
                msg += (
                    f" Maybe you meant '{suggestions[0]}', '{suggestions[1]}' or "
                    f"'{suggestions[2]}'?"
                )
        msg += " Type 'help' to browse commands."
        caller.msg(msg)


class CmdHelpSearch(CmdHelp):
    """
    Get help, with optional search across all help topics.

    Usage:
      help [topic[/subtopic]]
      help/search <string>

    Use |whelp|n alone to see the index. Use |whelp/search <string>|n to find
    help topics matching that string (searches keys, aliases, categories, and content).
    """

    # Allow "/" after "help" so help/search matches (parent uses r"\s|$" which rejects slash)
    arg_regex = r"[\s/]|$"

    # Consolidated category mapping for command help entries.
    HELP_CATEGORY_MAP = {
        "admin": "Administration",
        "admin commands": "Administration",
        "system": "Administration",
        "character": "Character & Identity",
        "chargen & character info": "Character & Identity",
        "combat": "Combat & Survival",
        "inventory": "Economy & Inventory",
        "economy": "Economy & Inventory",
        "crafting": "Economy & Inventory",
        "netrunning": "Netrunning & Matrix",
        "missions": "Missions & Jobs",
        "utility commands": "Missions & Jobs",
        "factions and groups": "Factions & Groups",
        "event & bulletin board": "Bulletin Board & Events",
        "building": "Building & Story",
        "building and housing": "Building & Story",
        "storyteller": "Building & Story",
        "storyteller commands": "Building & Story",
        "rp commands": "Roleplay & Communication",
        "roleplaying tools": "Roleplay & Communication",
        "roleplay utilities": "Roleplay & Communication",
        "communication": "Roleplay & Communication",
        "comms": "Roleplay & Communication",
        "ooc/ic movement": "Roleplay & Communication",
        "general": "World & Information",
        "game info": "World & Information",
        "elflines online": "World & Information",
    }

    def _normalize_help_category(self, category):
        """Consolidate legacy help categories into a smaller normalized set."""
        category = (category or "World & Information").strip()
        normalized = self.HELP_CATEGORY_MAP.get(category.lower(), category)
        return normalized

    def _normalize_entry_category(self, entry):
        """Apply category normalization on a help entry in-place."""
        if hasattr(entry, "help_category"):
            entry.help_category = self._normalize_help_category(entry.help_category)
        if hasattr(entry, "search_index_entry") and isinstance(entry.search_index_entry, dict):
            entry.search_index_entry["category"] = self._normalize_help_category(
                entry.search_index_entry.get("category", "World & Information")
            )

    def collect_topics(self, caller, mode="list"):
        """
        Collect help topics and normalize categories for consistent grouping.

        This prevents category names from colliding with command names
        (for example, category "Combat" vs command "combat").
        """
        cmd_help, db_help, file_help = super().collect_topics(caller, mode=mode)
        for collection in (cmd_help, db_help, file_help):
            for entry in collection.values():
                self._normalize_entry_category(entry)
        return cmd_help, db_help, file_help

    def format_help_entry(
        self,
        topic="",
        help_text="",
        aliases=None,
        suggested=None,
        subtopics=None,
        click_topics=True,
    ):
        """Format help entry with pipes escaped so pipes (e.g. add|remove) display correctly."""
        if help_text:
            help_text = help_text.replace("|", "||")
        return super().format_help_entry(
            topic=topic,
            help_text=help_text,
            aliases=aliases,
            suggested=suggested,
            subtopics=subtopics,
            click_topics=click_topics,
        )

    def parse(self):
        """Run MuxCommand parse first to extract switches, then CmdHelp parse for topic/subtopics."""
        MuxCommand.parse(self)
        if "search" not in (self.switches or []):
            CmdHelp.parse(self)

    def msg_help(self, text, **kwargs):
        """
        Send help output using game-local safe pager wrapper.

        Keeps the same client behavior as Evennia's default `CmdHelp.msg_help`
        while avoiding duplicate pager cmdset collisions.
        """
        if type(self).help_more:
            usemore = True

            if self.session and self.session.protocol_key in (
                "webclient/websocket",
                "webclient/ajax",
            ):
                try:
                    options = self.account.db._saved_webclient_options
                    if options and options["helppopup"]:
                        usemore = False
                except KeyError:
                    pass

            if usemore:
                start_help_pager(
                    self.caller,
                    text,
                    session=self.session,
                    text_kwargs={"type": "help"},
                    **kwargs,
                )
                return

        self.msg(text=(text, {"type": "help"}))

    def func(self):
        if "search" in (self.switches or []):
            search_str = (self.args or "").strip()
            if not search_str:
                self.caller.msg("Usage: help/search <string>")
                return
            self._search_help(search_str)
            return
        super().func()

    def _get_entry_key(self, entry):
        """Get display key for a help entry."""
        if hasattr(entry, "key"):
            return entry.key
        if hasattr(entry, "search_index_entry") and isinstance(entry.search_index_entry, dict):
            return entry.search_index_entry.get("key", "?")
        return "?"

    def _get_entry_category(self, entry):
        """Get category for a help entry."""
        if hasattr(entry, "help_category"):
            return self._normalize_help_category(entry.help_category)
        if hasattr(entry, "search_index_entry") and isinstance(entry.search_index_entry, dict):
            return self._normalize_help_category(
                entry.search_index_entry.get("category", "World & Information")
            )
        return "World & Information"

    def _search_help(self, search_str):
        """Search all help entries for the given string."""
        cmd_help, db_help, file_help = self.collect_topics(self.caller, mode="list")
        all_entries = []
        for d in (cmd_help, db_help, file_help):
            all_entries.extend(d.values())

        if not all_entries:
            self.caller.msg("No help entries available to search.")
            return

        # Default CmdHelp Lunr fields omit `text`; search_index_entry still carries
        # docstrings / entrytext. Index body text so mentions inside another topic
        # (e.g. related commands) rank in help/search, not only keys/aliases.
        search_fields = [
            {"field_name": "key", "boost": 10},
            {"field_name": "aliases", "boost": 7},
            {"field_name": "no_prefix", "boost": 6},
            {"field_name": "category", "boost": 5},
            {"field_name": "text", "boost": 3},
            {"field_name": "tags", "boost": 1},
        ]

        try:
            match, suggestions = self.do_search(
                search_str, all_entries, search_fields=search_fields
            )
            matches = [match] if match else []
            suggestions = suggestions or []
        except Exception:
            matches, suggestions = [], []

        if not matches and not suggestions:
            self._fallback_search(search_str, all_entries)
            return

        output = [f"|yHelp search: '{search_str}'|n", ""]
        if matches:
            output.append("|wMatches:|n")
            for entry in matches[:30]:
                key = self._get_entry_key(entry)
                category = self._get_entry_category(entry)
                output.append(f"  |w{key}|n ({category})")
            output.append("")
        if suggestions:
            output.append("|wSuggestions:|n")
            for s in suggestions[:15]:
                if isinstance(s, str):
                    output.append(f"  |w{s}|n")
                else:
                    output.append(f"  |w{self._get_entry_key(s)}|n")
            output.append("")
        output.append("Use |whelp <topic>|n to read a topic.")
        self.msg_help("\n".join(output))

    def _fallback_search(self, search_str, all_entries):
        """Simple substring search when Lunr is unavailable."""
        q = search_str.lower()
        matches = []
        for entry in all_entries:
            key = self._get_entry_key(entry).lower()
            category = self._get_entry_category(entry).lower()
            text = ""
            if hasattr(entry, "search_index_entry") and isinstance(entry.search_index_entry, dict):
                text = str(entry.search_index_entry.get("text", "")).lower()
            elif hasattr(entry, "entrytext"):
                text = (entry.entrytext or "").lower()
            if q in key or q in category or q in text:
                matches.append(entry)

        if not matches:
            self.caller.msg(f"No help topics found matching '{search_str}'.")
            return

        output = [f"|yHelp search: '{search_str}'|n", "", "|wMatches:|n"]
        for entry in matches[:30]:
            key = self._get_entry_key(entry)
            category = self._get_entry_category(entry)
            output.append(f"  |w{key}|n ({category})")
        output.append("")
        output.append("Use |whelp <topic>|n to read a topic.")
        self.msg_help("\n".join(output))
