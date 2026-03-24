"""
Custom help command with /search switch for finding help topics by keyword.

CmdHelp overrides parse() and does not call MuxCommand.parse(), so switches
are never extracted. We override parse() to run MuxCommand.parse() first,
then CmdHelp.parse() when not using /search, so that help/search works.

Help text has ANSI stripped so that pipes (e.g. add|remove) in usage examples
display correctly instead of being interpreted as color codes.
"""
from evennia.commands.default.help import CmdHelp
from evennia.commands.default.muxcommand import MuxCommand
from utils import evmore_safe


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
                if skey.lower() == "more_commands" or spath.lower().endswith(
                    "evennia.utils.evmore.cmdsetmore"
                ):
                    stack_more_count += 1
                lines.append(f"    * stack key={skey!r} path={spath!r}")
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
        lines.extend(self._cmdset_debug_lines("Account", account))
        if puppet is not None and puppet is not caller:
            lines.append("")
            lines.extend(self._cmdset_debug_lines("Session puppet", puppet))

        self.caller.msg("\n".join(lines))


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
                evmore_safe.msg(
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
