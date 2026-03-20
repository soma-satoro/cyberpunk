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
            return entry.help_category
        if hasattr(entry, "search_index_entry") and isinstance(entry.search_index_entry, dict):
            return entry.search_index_entry.get("category", "General")
        return "General"

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
