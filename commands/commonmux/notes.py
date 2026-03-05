from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import evtable
from evennia import search_object
from datetime import datetime
from utils.text import process_special_characters
from world.utils.formatting import footer
from utils.search_helpers import search_character


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
                # View all your notes
                self.view_notes()
            else:
                # Parse args to determine what action to take
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
        # Count slashes to help determine format
        slash_count = self.args.count("/")
        has_equals = "=" in self.args
        
        if slash_count == 2 and has_equals:
            # Format: player/title/category=text (staff creating note for player)
            self.staff_create_note()
        elif slash_count == 1 and has_equals:
            # Format: title/category=text (player creating note)
            self.create_note()
        elif has_equals and slash_count == 0:
            # Format: player=title (staff viewing specific note)
            self.staff_view_specific_note()
        elif not has_equals and slash_count == 0:
            # Format: [title or player name]
            # Try to find as note title first, then as player name if staff
            self.view_note_or_player()
    
    def create_note(self):
        """Create a new note: +note [title]/[category]=[Note Text]"""
        if "/" not in self.args or "=" not in self.args:
            self.caller.msg("Usage: +note [title]/[category]=[Note Text]")
            return
        
        try:
            # Split the args to get title/category and text
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
        
        # Initialize notes if not exists
        if not self.caller.db.notes:
            self.caller.db.notes = []
        
        # Check if a note with this title already exists
        existing_note = None
        for note in self.caller.db.notes:
            if note["title"].lower() == title.lower():
                existing_note = note
                break
        
        if existing_note:
            self.caller.msg(f"A note with the title '{title}' already exists. Use +note/edit to modify it.")
            return
        
        # Create the note
        new_note = {
            "title": title,
            "category": category,
            "text": text,
            "approved": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self.caller.db.notes.append(new_note)
        self.caller.msg(f"|gNote created:|n '{title}' in category '{category}'")
    
    def view_notes(self):
        """View all notes on the character"""
        notes = self.caller.db.notes or []
        
        if not notes:
            self.caller.msg("You have no notes.")
            return
        
        # Create a table for displaying notes
        table = evtable.EvTable(
            "|wTitle|n",
            "|wCategory|n",
            "|wStatus|n",
            "|wCreated|n",
            border="cells",
            width=78
        )
        
        for note in notes:
            status = "|gApproved|n" if note["approved"] else "|yDraft|n"
            table.add_row(
                note["title"],
                note["category"],
                status,
                note["created"]
            )
        
        output = ["|wYour Notes|n", str(table)]
        output.append("\nUse '+note <title>' to view the full text of a note.")
        self.caller.msg("\n".join(output))
    
    def view_note_or_player(self):
        """View a specific note on self, or view all notes on a player (staff)."""
        search_term = self.args.strip()
        
        # First, try to find as a note on the caller
        notes = self.caller.db.notes or []
        found_note = None
        for note in notes:
            if note["title"].lower() == search_term.lower():
                found_note = note
                break
        
        if found_note:
            # Found a note with this title on caller
            self.display_single_note(found_note, self.caller)
            return
        
        # Not found as a note title - if staff, try as player name
        if self.caller.check_permstring("builders"):
            self.staff_view_all_notes(search_term)
        else:
            self.caller.msg(f"You don't have a note titled '{search_term}'.")
    
    def display_single_note(self, note, character):
        """Display a single note."""
        output = []
        output.append(footer(78, char="="))
        output.append(f"|wNote:|n {note['title']}")
        output.append(f"|wCategory:|n {note['category']}")
        output.append(f"|wCharacter:|n {character.name}")
        output.append(f"|wCreated:|n {note['created']}")
        output.append(f"|wLast Modified:|n {note['modified']}")
        
        if note["approved"]:
            output.append(f"|wStatus:|n |gApproved|n")
            if "approved_by" in note:
                output.append(f"|wApproved by:|n {note['approved_by']} on {note.get('approved_date', 'Unknown')}")
        else:
            output.append(f"|wStatus:|n |yDraft|n")
        
        output.append(footer(78, char="="))
        processed_text = process_special_characters(note["text"])
        output.append(processed_text)
        output.append(footer(78, char="="))
        
        self.caller.msg("\n".join(output))
    
    def staff_view_all_notes(self, player_name):
        """Staff: View all notes on a player."""
        if not self.caller.check_permstring("builders"):
            self.caller.msg("Only staff can view other players' notes.")
            return
        
        # Search for the character
        character = search_character(self.caller, player_name)
        if not character:
            return
        
        # Check if it's a character object
        if not character.has_account:
            self.caller.msg(f"'{player_name}' is not a character.")
            return
        
        notes = character.db.notes or []
        
        if not notes:
            self.caller.msg(f"{character.name} has no notes.")
            return
        
        # Create a table for displaying notes
        table = evtable.EvTable(
            "|wTitle|n",
            "|wCategory|n",
            "|wStatus|n",
            "|wCreated|n",
            border="cells",
            width=78
        )
        
        for note in notes:
            status = "|gApproved|n" if note["approved"] else "|yDraft|n"
            table.add_row(
                note["title"],
                note["category"],
                status,
                note["created"]
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
        
        # Search for the character
        character = search_character(self.caller, player_name)
        if not character:
            return
        
        # Check if it's a character object
        if not character.has_account:
            self.caller.msg(f"'{player_name}' is not a character.")
            return
        
        notes = character.db.notes or []
        
        # Find the note
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break
        
        if not found_note:
            self.caller.msg(f"{character.name} doesn't have a note titled '{title}'.")
            return
        
        # Display the note
        self.display_single_note(found_note, character)
    
    def staff_create_note(self):
        """Staff: Create a note for a player: +note [player]/[title]/[category]=[text]"""
        if not self.caller.check_permstring("builders"):
            self.caller.msg("Only staff can create notes for other players.")
            return
        
        # Should have format: player/title/category=text
        if self.args.count("/") != 2 or "=" not in self.args:
            self.caller.msg("Usage: +note [player]/[title]/[category]=[text]")
            return
        
        try:
            # Split on = first
            lhs, rhs = self.args.split("=", 1)
            # Then split lhs on /
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
        
        # Search for the character
        character = search_character(self.caller, player_name)
        if not character:
            return
        
        # Check if it's a character object
        if not character.has_account:
            self.caller.msg(f"'{player_name}' is not a character.")
            return
        
        # Initialize notes if not exists
        if not character.db.notes:
            character.db.notes = []
        
        # Check if a note with this title already exists
        existing_note = None
        for note in character.db.notes:
            if note["title"].lower() == title.lower():
                existing_note = note
                break
        
        if existing_note:
            self.caller.msg(f"{character.name} already has a note titled '{title}'. Use +note/approve to approve it or have them edit it.")
            return
        
        # Create the note
        new_note = {
            "title": title,
            "category": category,
            "text": text,
            "approved": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "created_by_staff": self.caller.name
        }
        
        character.db.notes.append(new_note)
        self.caller.msg(f"|gNote created for {character.name}:|n '{title}' in category '{category}'")
        
        # Notify the character owner if they're online
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
        
        notes = self.caller.db.notes or []
        
        # Find the note
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break
        
        if not found_note:
            self.caller.msg(f"You don't have a note titled '{title}'.")
            return
        
        # Check if the note is approved
        if found_note["approved"]:
            self.caller.msg(f"The note '{title}' is approved and cannot be edited. Contact staff to unapprove it first.")
            return
        
        # Update the note
        found_note["text"] = new_text
        found_note["modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.caller.msg(f"|gNote updated:|n '{title}'")
    
    def delete_note(self):
        """Delete a note: +note/delete [title]"""
        if not self.args:
            self.caller.msg("Usage: +note/delete [title]")
            return
        
        title = self.args.strip()
        notes = self.caller.db.notes or []
        
        # Find and remove the note
        found_note = None
        for i, note in enumerate(notes):
            if note["title"].lower() == title.lower():
                found_note = note
                found_index = i
                break
        
        if not found_note:
            self.caller.msg(f"You don't have a note titled '{title}'.")
            return
        
        # Check permissions - staff can always delete
        is_staff = self.caller.check_permstring("builders")
        
        if found_note["approved"] and not is_staff:
            self.caller.msg(f"The note '{title}' is approved and cannot be deleted. Contact staff for assistance.")
            return
        
        # Remove the note
        del notes[found_index]
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
        
        # Search for the character
        character = search_character(self.caller, character_name)
        if not character:
            return
        
        # Check if it's a character object
        if not character.has_account:
            self.caller.msg(f"'{character_name}' is not a character.")
            return
        
        notes = character.db.notes or []
        
        # Find the note
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break
        
        if not found_note:
            self.caller.msg(f"Character '{character_name}' doesn't have a note titled '{title}'.")
            return
        
        if found_note["approved"]:
            self.caller.msg(f"The note '{title}' is already approved.")
            return
        
        # Approve the note
        found_note["approved"] = True
        found_note["approved_by"] = self.caller.name
        found_note["approved_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.caller.msg(f"|gApproved note:|n '{title}' for {character.name}")
        
        # Notify the character owner if they're online
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
        
        # Search for the character
        character = search_character(self.caller, character_name)
        if not character:
            return
        
        # Check if it's a character object
        if not character.has_account:
            self.caller.msg(f"'{character_name}' is not a character.")
            return
        
        notes = character.db.notes or []
        
        # Find the note
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break
        
        if not found_note:
            self.caller.msg(f"Character '{character_name}' doesn't have a note titled '{title}'.")
            return
        
        if not found_note["approved"]:
            self.caller.msg(f"The note '{title}' is not approved.")
            return
        
        # Unapprove the note
        found_note["approved"] = False
        if "approved_by" in found_note:
            del found_note["approved_by"]
        if "approved_date" in found_note:
            del found_note["approved_date"]
        
        self.caller.msg(f"|yUnapproved note:|n '{title}' for {character.name}")
        
        # Notify the character owner if they're online
        if character.sessions.all():
            character.msg(f"|yYour note '{title}' has been unapproved by {self.caller.name}. You can now edit it.|n")
    
    def show_note(self):
        """Show a note to the room or to a specific player"""
        if not self.args:
            self.caller.msg("Usage: +note/show [title] or +note/show [title]=[player name]")
            return
        
        # Check if showing to a specific player
        if "=" in self.args:
            title, target_name = self.args.split("=", 1)
            title = title.strip()
            target_name = target_name.strip()
            show_to_room = False
        else:
            title = self.args.strip()
            target_name = None
            show_to_room = True
        
        notes = self.caller.db.notes or []
        
        # Find the note
        found_note = None
        for note in notes:
            if note["title"].lower() == title.lower():
                found_note = note
                break
        
        if not found_note:
            self.caller.msg(f"You don't have a note titled '{title}'.")
            return
        
        # Format the note for display
        output = []
        output.append(footer(78, char="="))
        output.append(f"|wNote:|n {found_note['title']}")
        output.append(f"|wCategory:|n {found_note['category']}")
        output.append(f"|wAuthor:|n {self.caller.name}")
        
        if found_note["approved"]:
            output.append(f"|wStatus:|n |gApproved|n")
            if "approved_by" in found_note:
                output.append(f"|wApproved by:|n {found_note['approved_by']} on {found_note.get('approved_date', 'Unknown')}")
        else:
            output.append(f"|wStatus:|n |yDraft|n")
        
        output.append(footer(78, char="="))
        processed_text = process_special_characters(found_note["text"])
        output.append(processed_text)
        output.append(footer(78, char="="))
        
        note_display = "\n".join(output)
        
        if show_to_room:
            # Show to everyone in the room
            location = self.caller.location
            if not location:
                self.caller.msg("You are not in a room.")
                return
            
            # Send to everyone in the room
            location.msg_contents(f"{self.caller.name} shares a note:\n{note_display}", exclude=[self.caller])
            self.caller.msg(f"You show '{title}' to the room:\n{note_display}")
        else:
            # Show to a specific player
            target = search_character(self.caller, target_name)
            if not target:
                return
            
            # Check if target is online
            if not target.sessions.all():
                self.caller.msg(f"{target.name} is not currently online.")
                return
            
            # Send to target
            target.msg(f"{self.caller.name} shares a note with you:\n{note_display}")
            self.caller.msg(f"You show '{title}' to {target.name}.")

