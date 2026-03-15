"""
Character notes and long-form narrative content.

Uses character.db.notes as a list of dicts (title, category, text, approved, etc.)
rather than the legacy model-based system.
"""
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import evtable
from datetime import datetime
from utils.text import process_special_characters
from world.utils.formatting import footer
from utils.search_helpers import search_character


def _get_notes(character):
    """
    Get notes for a character, migrating from old format if needed.
    Old format: attributes['notes'] as dict keyed by id.
    New format: db.notes as list of dicts with title, category, text, approved, etc.
    """
    raw = character.attributes.get("notes", default=None)
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    # Migrate from old dict format
    if isinstance(raw, dict):
        migrated = []
        for nid, data in raw.items():
            if not isinstance(data, dict):
                continue
            created = data.get("created_at") or data.get("created")
            updated = data.get("updated_at") or data.get("modified")
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elif hasattr(created, "strftime"):
                created = created.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(updated, str):
                try:
                    updated = datetime.fromisoformat(updated.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    updated = created
            elif hasattr(updated, "strftime"):
                updated = updated.strftime("%Y-%m-%d %H:%M:%S")
            else:
                updated = created
            approved_by = data.get("approved_by")
            if hasattr(approved_by, "username"):
                approved_by = approved_by.username
            approved_date = data.get("approved_at")
            if hasattr(approved_date, "strftime"):
                approved_date = approved_date.strftime("%Y-%m-%d %H:%M:%S")
            migrated.append({
                "title": data.get("name") or data.get("title") or f"Note {nid}",
                "category": data.get("category", "General"),
                "text": data.get("text", ""),
                "approved": bool(data.get("is_approved") or data.get("approved")),
                "created": created,
                "modified": updated,
                **({"approved_by": approved_by} if approved_by else {}),
                **({"approved_date": approved_date} if approved_date else {}),
            })
        character.db.notes = migrated
        return migrated
    return []


def _save_notes(character, notes):
    """Persist notes in the new list format."""
    character.db.notes = notes


class CmdNote(MuxCommand):
    """
    Manage character notes and long-form narrative content.

    Usage:
        +note [title]/[category]=[Note Text]     - Create a new note
        +note                                    - View all your notes
        +note [title]                            - View a specific note
        +note [player]                           - Staff: View all notes on a player
        +note [player]=[title]                   - Staff: View specific note on a player
        +note [player]/[title]/[category]=[text] - Staff: Create note for a player
        +note/edit [title]=[New text]           - Edit an existing note
        +note/delete [title]                    - Delete a note (player or staff)
        +note/approve [character]=[title]       - Approve a note (staff only, locks editing)
        +note/unapprove [character]=[title]     - Unapprove a note (staff only, unlocks editing)
        +note/show [title]                      - Show a note to everyone in the room
        +note/show [title]=[player name]        - Show a note privately to a specific player

    Notes are long-form narrative content that you can create on your character.
    Each note has a title, category, and text. Staff can approve notes to lock them
    from further editing.

    Examples:
        +note My Backstory/Background=I was born in a small town...
        +note
        +note My Backstory                       - View your "My Backstory" note
        +note Alice                              - Staff: View all of Alice's notes
        +note Alice=My Backstory                 - Staff: View Alice's "My Backstory" note
        +note Alice/New Note/Background=Text...  - Staff: Create note for Alice
        +note/edit My Backstory=I was actually born in a large city...
        +note/delete My Backstory
        +note/show My Backstory
        +note/show My Backstory=Bob
    """

    key = "+note"
    aliases = ["+notes"]
    help_category = "Chargen & Character Info"
    locks = "cmd:all()"

    def func(self):
        """Execute the command"""
        if not self.switches:
            if not self.args:
                self.view_notes()
            else:
                self.parse_no_switch_args()
        else:
            switch = self.switches[0].lower()
            if switch == "edit":
                self.edit_note()
            elif switch == "delete":
                self.delete_note()
            elif switch == "approve":
                self.approve_note()
            elif switch == "unapprove":
                self.unapprove_note()
            elif switch == "show":
                self.show_note()
            else:
                self.caller.msg("Invalid switch. See 'help +note' for usage.")

    def parse_no_switch_args(self):
        """Parse args when no switch is provided to determine action."""
        slash_count = self.args.count("/")
        has_equals = "=" in self.args

        if slash_count == 2 and has_equals:
            self.staff_create_note()
        elif slash_count == 1 and has_equals:
            self.create_note()
        elif has_equals and slash_count == 0:
            self.staff_view_specific_note()
        elif not has_equals and slash_count == 0:
            self.view_note_or_player()

    def create_note(self):
        """Create a new note: +note [title]/[category]=[Note Text]"""
        if "/" not in self.args or "=" not in self.args:
            self.caller.msg("Usage: +note [title]/[category]=[Note Text]")
            return

        try:
            lhs, rhs = self.args.split("=", 1)
            title, category = lhs.split("/", 1)
            title = title.strip()
            category = category.strip()
            text = rhs.strip()
        except ValueError:
            self.caller.msg("Usage: +note [title]/[category]=[Note Text]")
            return

        if not title or not category or not text:
            self.caller.msg("All fields (title, category, and text) must be provided.")
            return

        notes = _get_notes(self.caller)
        for note in notes:
            if note["title"].lower() == title.lower():
                self.caller.msg(f"A note with the title '{title}' already exists. Use +note/edit to modify it.")
                return

        new_note = {
            "title": title,
            "category": category,
            "text": text,
            "approved": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        notes.append(new_note)
        _save_notes(self.caller, notes)
        self.caller.msg(f"|gNote created:|n '{title}' in category '{category}'")

    def view_notes(self):
        """View all notes on the character"""
        notes = _get_notes(self.caller)
        if not notes:
            self.caller.msg("You have no notes.")
            return

        table = evtable.EvTable(
            "|wTitle|n",
            "|wCategory|n",
            "|wStatus|n",
            "|wCreated|n",
            border="cells",
            width=78,
        )
        for note in notes:
            status = "|gApproved|n" if note.get("approved") else "|yDraft|n"
            table.add_row(
                note["title"],
                note["category"],
                status,
                note.get("created", ""),
            )
        output = ["|wYour Notes|n", str(table)]
        output.append("\nUse '+note <title>' to view the full text of a note.")
        self.caller.msg("\n".join(output))

    def view_note_or_player(self):
        """View a specific note on self, or view all notes on a player (staff)."""
        search_term = self.args.strip()
        notes = _get_notes(self.caller)
        found_note = None
        for note in notes:
            if note["title"].lower() == search_term.lower():
                found_note = note
                break

        if found_note:
            self.display_single_note(found_note, self.caller)
            return

        if self.caller.check_permstring("builders"):
            self.staff_view_all_notes(search_term)
        else:
            self.caller.msg(f"You don't have a note titled '{search_term}'.")

    def display_single_note(self, note, character):
        """Display a single note."""
        output = []
        output.append(footer(78, fillchar="="))
        output.append(f"|wNote:|n {note['title']}")
        output.append(f"|wCategory:|n {note['category']}")
        output.append(f"|wCharacter:|n {character.name}")
        output.append(f"|wCreated:|n {note.get('created', '')}")
        output.append(f"|wLast Modified:|n {note.get('modified', '')}")

        if note.get("approved"):
            output.append(f"|wStatus:|n |gApproved|n")
            if "approved_by" in note:
                output.append(f"|wApproved by:|n {note['approved_by']} on {note.get('approved_date', 'Unknown')}")
        else:
            output.append(f"|wStatus:|n |yDraft|n")

        output.append(footer(78, fillchar="="))
        processed_text = process_special_characters(note.get("text", ""))
        output.append(processed_text)
        output.append(footer(78, fillchar="="))

        self.caller.msg("\n".join(output))

    def staff_view_all_notes(self, player_name):
        """Staff: View all notes on a player."""
        if not self.caller.check_permstring("builders"):
            self.caller.msg("Only staff can view other players' notes.")
            return

        character = search_character(self.caller, player_name)
        if not character:
            return
        if not character.has_account:
            self.caller.msg(f"'{player_name}' is not a character.")
            return

        notes = _get_notes(character)
        if not notes:
            self.caller.msg(f"{character.name} has no notes.")
            return

        table = evtable.EvTable(
            "|wTitle|n",
            "|wCategory|n",
            "|wStatus|n",
            "|wCreated|n",
            border="cells",
            width=78,
        )
        for note in notes:
            status = "|gApproved|n" if note.get("approved") else "|yDraft|n"
            table.add_row(
                note["title"],
                note["category"],
                status,
                note.get("created", ""),
            )
        output = [f"|w{character.name}'s Notes|n", str(table)]
        output.append(f"\nUse '+note {character.name}=<title>' to view the full text of a note.")
        self.caller.msg("\n".join(output))

    def staff_view_specific_note(self):
        """Staff: View a specific note on a player: +note [player]=[title]"""
        if not self.caller.check_permstring("builders"):
            self.caller.msg("Only staff can view other players' notes.")
            return

        if "=" not in self.args:
            self.caller.msg("Usage: +note [player]=[title]")
            return

        try:
            player_name, title = self.args.split("=", 1)
            player_name = player_name.strip()
            title = title.strip()
        except ValueError:
            self.caller.msg("Usage: +note [player]=[title]")
            return

        if not player_name or not title:
            self.caller.msg("Both player name and note title must be provided.")
            return

        character = search_character(self.caller, player_name)
        if not character:
            return
        if not character.has_account:
            self.caller.msg(f"'{player_name}' is not a character.")
            return

        notes = _get_notes(character)
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break

        if not found_note:
            self.caller.msg(f"{character.name} doesn't have a note titled '{title}'.")
            return

        self.display_single_note(found_note, character)

    def staff_create_note(self):
        """Staff: Create a note for a player: +note [player]/[title]/[category]=[text]"""
        if not self.caller.check_permstring("builders"):
            self.caller.msg("Only staff can create notes for other players.")
            return

        if self.args.count("/") != 2 or "=" not in self.args:
            self.caller.msg("Usage: +note [player]/[title]/[category]=[text]")
            return

        try:
            lhs, rhs = self.args.split("=", 1)
            parts = lhs.split("/")
            if len(parts) != 3:
                raise ValueError
            player_name = parts[0].strip()
            title = parts[1].strip()
            category = parts[2].strip()
            text = rhs.strip()
        except ValueError:
            self.caller.msg("Usage: +note [player]/[title]/[category]=[text]")
            return

        if not player_name or not title or not category or not text:
            self.caller.msg("All fields (player, title, category, and text) must be provided.")
            return

        character = search_character(self.caller, player_name)
        if not character:
            return
        if not character.has_account:
            self.caller.msg(f"'{player_name}' is not a character.")
            return

        notes = _get_notes(character)
        for note in notes:
            if note["title"].lower() == title.lower():
                self.caller.msg(f"{character.name} already has a note titled '{title}'. Use +note/approve to approve it or have them edit it.")
                return

        new_note = {
            "title": title,
            "category": category,
            "text": text,
            "approved": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_by_staff": self.caller.name,
        }
        notes.append(new_note)
        _save_notes(character, notes)
        self.caller.msg(f"|gNote created for {character.name}:|n '{title}' in category '{category}'")

        if character.sessions.all():
            character.msg(f"|gStaff member {self.caller.name} has created a note for you: '{title}'|n")

    def edit_note(self):
        """Edit an existing note: +note/edit [title]=[New text]"""
        if "=" not in self.args:
            self.caller.msg("Usage: +note/edit [title]=[New text]")
            return

        try:
            title, new_text = self.args.split("=", 1)
            title = title.strip()
            new_text = new_text.strip()
        except ValueError:
            self.caller.msg("Usage: +note/edit [title]=[New text]")
            return

        if not title or not new_text:
            self.caller.msg("Both title and new text must be provided.")
            return

        notes = _get_notes(self.caller)
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break

        if not found_note:
            self.caller.msg(f"You don't have a note titled '{title}'.")
            return

        if found_note.get("approved"):
            self.caller.msg(f"The note '{title}' is approved and cannot be edited. Contact staff to unapprove it first.")
            return

        found_note["text"] = new_text
        found_note["modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_notes(self.caller, notes)
        self.caller.msg(f"|gNote updated:|n '{title}'")

    def delete_note(self):
        """Delete a note: +note/delete [title]"""
        if not self.args:
            self.caller.msg("Usage: +note/delete [title]")
            return

        title = self.args.strip()
        notes = _get_notes(self.caller)
        found_index = None
        for i, note in enumerate(notes):
            if note["title"].lower() == title.lower():
                found_index = i
                break

        if found_index is None:
            self.caller.msg(f"You don't have a note titled '{title}'.")
            return

        found_note = notes[found_index]
        is_staff = self.caller.check_permstring("builders")

        if found_note.get("approved") and not is_staff:
            self.caller.msg(f"The note '{title}' is approved and cannot be deleted. Contact staff for assistance.")
            return

        del notes[found_index]
        _save_notes(self.caller, notes)
        self.caller.msg(f"|rNote deleted:|n '{title}'")

    def approve_note(self):
        """Approve a note (staff only): +note/approve [character]=[title]"""
        if not self.caller.check_permstring("builders"):
            self.caller.msg("Only staff can approve notes.")
            return

        if "=" not in self.args:
            self.caller.msg("Usage: +note/approve [character]=[title]")
            return

        try:
            character_name, title = self.args.split("=", 1)
            character_name = character_name.strip()
            title = title.strip()
        except ValueError:
            self.caller.msg("Usage: +note/approve [character]=[title]")
            return

        if not character_name or not title:
            self.caller.msg("Both character name and note title must be provided.")
            return

        character = search_character(self.caller, character_name)
        if not character:
            return
        if not character.has_account:
            self.caller.msg(f"'{character_name}' is not a character.")
            return

        notes = _get_notes(character)
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break

        if not found_note:
            self.caller.msg(f"Character '{character_name}' doesn't have a note titled '{title}'.")
            return

        if found_note.get("approved"):
            self.caller.msg(f"The note '{title}' is already approved.")
            return

        found_note["approved"] = True
        found_note["approved_by"] = self.caller.name
        found_note["approved_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_notes(character, notes)
        self.caller.msg(f"|gApproved note:|n '{title}' for {character.name}")

        if character.sessions.all():
            character.msg(f"|gYour note '{title}' has been approved by {self.caller.name}.|n")

    def unapprove_note(self):
        """Unapprove a note (staff only): +note/unapprove [character]=[title]"""
        if not self.caller.check_permstring("builders"):
            self.caller.msg("Only staff can unapprove notes.")
            return

        if "=" not in self.args:
            self.caller.msg("Usage: +note/unapprove [character]=[title]")
            return

        try:
            character_name, title = self.args.split("=", 1)
            character_name = character_name.strip()
            title = title.strip()
        except ValueError:
            self.caller.msg("Usage: +note/unapprove [character]=[title]")
            return

        if not character_name or not title:
            self.caller.msg("Both character name and note title must be provided.")
            return

        character = search_character(self.caller, character_name)
        if not character:
            return
        if not character.has_account:
            self.caller.msg(f"'{character_name}' is not a character.")
            return

        notes = _get_notes(character)
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break

        if not found_note:
            self.caller.msg(f"Character '{character_name}' doesn't have a note titled '{title}'.")
            return

        if not found_note.get("approved"):
            self.caller.msg(f"The note '{title}' is not approved.")
            return

        found_note["approved"] = False
        found_note.pop("approved_by", None)
        found_note.pop("approved_date", None)
        _save_notes(character, notes)
        self.caller.msg(f"|yUnapproved note:|n '{title}' for {character.name}")

        if character.sessions.all():
            character.msg(f"|yYour note '{title}' has been unapproved by {self.caller.name}. You can now edit it.|n")

    def show_note(self):
        """Show a note to the room or to a specific player"""
        if not self.args:
            self.caller.msg("Usage: +note/show [title] or +note/show [title]=[player name]")
            return

        if "=" in self.args:
            title, target_name = self.args.split("=", 1)
            title = title.strip()
            target_name = target_name.strip()
            show_to_room = False
        else:
            title = self.args.strip()
            target_name = None
            show_to_room = True

        notes = _get_notes(self.caller)
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break

        if not found_note:
            self.caller.msg(f"You don't have a note titled '{title}'.")
            return

        output = []
        output.append(footer(78, fillchar="="))
        output.append(f"|wNote:|n {found_note['title']}")
        output.append(f"|wCategory:|n {found_note['category']}")
        output.append(f"|wAuthor:|n {self.caller.name}")

        if found_note.get("approved"):
            output.append(f"|wStatus:|n |gApproved|n")
            if "approved_by" in found_note:
                output.append(f"|wApproved by:|n {found_note['approved_by']} on {found_note.get('approved_date', 'Unknown')}")
        else:
            output.append(f"|wStatus:|n |yDraft|n")

        output.append(footer(78, fillchar="="))
        processed_text = process_special_characters(found_note.get("text", ""))
        output.append(processed_text)
        output.append(footer(78, fillchar="="))

        note_display = "\n".join(output)

        if show_to_room:
            location = self.caller.location
            if not location:
                self.caller.msg("You are not in a room.")
                return
            location.msg_contents(f"{self.caller.name} shares a note:\n{note_display}", exclude=[self.caller])
            self.caller.msg(f"You show '{title}' to the room:\n{note_display}")
        else:
            target = search_character(self.caller, target_name)
            if not target:
                return
            if not target.sessions.all():
                self.caller.msg(f"{target.name} is not currently online.")
                return
            target.msg(f"{self.caller.name} shares a note with you:\n{note_display}")
            self.caller.msg(f"You show '{title}' to {target.name}.")
