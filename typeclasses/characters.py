"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.
"""
from evennia import DefaultCharacter
from world.cyberpunk_sheets.models import CharacterSheet
from evennia.utils.ansi import ANSIString
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider
import logging, re
from datetime import datetime
logger = logging.getLogger('cyberpunk.character')
from evennia.utils.utils import lazy_property

class Character(DefaultCharacter):
    def at_object_creation(self):
        super().at_object_creation()
        self.db.combat_position = 0  # Default starting position
        self.cmdset.add("commands.default_cmdsets.CharacterCmdSet", permanent=True)
        self.create_character_sheet()

        # Initialize notification settings
        self.db.notifications = {
            "say": True,
            "pose": True,
            "emit": True,
            "page": True,
            "whisper": True,
            "new_page": True,
        }
        
        # Initialize notes storage
        self.db.notes = {}
        self.db.notes_public = {}  # For public notes that others can view

    def create_character_sheet(self):
        try:
            sheet = CharacterSheet.objects.get(character=self)
            logger.info(f"Found existing character sheet for {self.name}")
        except CharacterSheet.DoesNotExist:
            sheet = CharacterSheet(character=self, account=self.account)
            sheet.save()
            logger.info(f"Created new character sheet for {self.name}")
        
        self.db.character_sheet_id = sheet.id
        return sheet

    def initialize_character_sheet(self, sheet):
        sheet.full_name = self.name  # Set the full name to the puppet object's name
        sheet.gender = ""
        sheet.intelligence = 1
        sheet.reflexes = 1
        sheet.dexterity = 1
        sheet.technology = 1
        sheet.cool = 1
        sheet.willpower = 1
        sheet.luck = 1
        sheet.move = 1
        sheet.empathy = 1
        sheet.body = 1
        sheet.save()

    def at_post_unpuppet(self, account=None, session=None, **kwargs):
        """
        Called just after the Character was unpuppeted.
        """
        if not self.sessions.count():
            # only remove this char from grid if no sessions control it anymore.
            if self.location:
                def message(obj, from_obj):
                    obj.msg(
                        "{name} has disconnected{reason}.".format(
                            name=self.get_display_name(obj),
                            reason=kwargs.get("reason", ""),
                        ),
                        from_obj=from_obj,
                    )
                self.location.for_contents(message, exclude=[self], from_obj=self)
                self.db.prelogout_location = self.location
                self.location = None
                
            # Store the current time as the last disconnect time
            from time import time
            self.attributes.add("last_disconnect", time())
            
            # Store the last IP address used
            if session and hasattr(session, 'address'):
                ip_addr = isinstance(session.address, tuple) and session.address[0] or session.address
                self.attributes.add("last_ip", ip_addr)

            # Notification now handled by signal system
            # from commands.CmdWatch import notify_watchers
            # notify_watchers(self, False)

    def at_post_puppet(self, **kwargs):
        """
        Called just after puppeting has been completed and all
        Account<->Object links have been established.
        """
        from evennia.utils import logger
        logger.log_info(f"at_post_puppet called for {self.key}")

        super().at_post_puppet(**kwargs)
        if not hasattr(self, 'character_sheet'):
            self.create_character_sheet()

        # Send connection message to room
        if self.location:
            def message(obj, from_obj):
                obj.msg(
                    "{name} has connected.".format(
                        name=self.get_display_name(obj),
                    ),
                    from_obj=from_obj,
                )
            self.location.for_contents(message, exclude=[self], from_obj=self)

            # Show room description
            self.msg((self.at_look(self.location)))

        # Display login notifications
        logger.log_info(f"About to call display_login_notifications for {self.key}")
        self.display_login_notifications()
        logger.log_info(f"Finished display_login_notifications for {self.key}")

        # Notification now handled by signal system
        # from commands.CmdWatch import notify_watchers
        # notify_watchers(self, True)

    @property
    def notification_settings(self):
        """Get character's notification preferences."""
        if not self.db.notification_settings:
            # Default settings - everything enabled
            self.db.notification_settings = {
                "mail": True,
                "jobs": True,
                "bbs": True,
                "all": False  # Master switch - when True, all notifications are off
            }
        return self.db.notification_settings

    def set_notification_pref(self, notification_type, enabled):
        """Set notification preference for a specific type."""
        if notification_type not in ["mail", "jobs", "bbs", "all"]:
            raise ValueError("Invalid notification type")
        
        settings = self.notification_settings
        
        # Special handling for the "all" switch
        if notification_type == "all":
            # When all=True, notifications are off
            # When all=False, notifications are on
            settings["all"] = enabled
            settings["mail"] = not enabled
            settings["jobs"] = not enabled
            settings["bbs"] = not enabled
        else:
            # For individual switches
            settings[notification_type] = enabled
            # If enabling any individual switch, make sure master "all" is off
            if enabled:
                settings["all"] = False
                
        # Explicitly save the settings back to the database
        self.db.notification_settings = settings

    def should_show_notification(self, notification_type):
        """Check if a notification type should be shown."""
        settings = self.notification_settings
        # If master switch is on (all notifications off), return False
        if settings["all"]:
            return False
        # Otherwise check individual setting
        return settings.get(notification_type, True)

    def display_login_notifications(self):
        """Display notifications upon login."""
        from evennia.utils import logger
        logger.log_info(f"About to display login notifications for {self.key}")
        
        if self.account:
            # Check for first login notification
            if not self.attributes.has("first_login_complete"):
                self.msg("|g=========================== Welcome to Your WoD Game! ===========================|n")
                self.msg("|wYou have been automatically subscribed to the |cNewbie|w channel.|n")
                self.msg("|wYou can talk on this channel using the |cnewb|w command, for example:|n")
                self.msg("|c   newb Hello everyone! I'm new here.|n")
                self.msg("|wYou can see all your available channels with the |cchannel/list|w command.|n")
                self.msg("|wFor help getting started, type |chelp|w or ask questions on the Newbie channel.|n")
                self.msg("                                                                                  ")
                self.msg("|bJust as a note: if you've logged in before and you're seeing this, it's because|n")
                self.msg("|bthe typeclass has been updated. Don't worry, your character data is still here!|n")
                self.msg("|bYou also haven't been added to the newbie channel. This will only show up once.|n")
                self.msg("|g==============================================================================|n")
                
                # Mark first login as complete
                self.attributes.add("first_login_complete", True)
            
            # Check for unread mail
            if self.should_show_notification("mail"):
                from evennia.comms.models import Msg
                from evennia.utils.utils import inherits_from
                from django.db.models import Q

                # Check if caller is account (same check as mail command)
                caller_is_account = bool(
                    inherits_from(self.account, "evennia.accounts.accounts.DefaultAccount")
                )
                
                # Get messages for this account/character using Q objects for OR condition
                messages = Msg.objects.filter(
                    Q(db_receivers_accounts=self.account) | 
                    Q(db_receivers_objects=self)
                )
                
                unread_count = sum(1 for msg in messages if "new" in [str(tag) for tag in msg.tags.all()])
                
                if unread_count > 0:
                    self.msg("|wYou have %i unread @mail message%s.|n" % (unread_count, "s" if unread_count > 1 else ""))

            # Check for job updates
            if self.should_show_notification("jobs"):
                try:
                    from world.jobs.models import Job
                    from django.db.models import Q
                    if self.account:
                        # Get jobs where the character is requester or participant
                        jobs = Job.objects.filter(
                            Q(requester=self.account) |
                            Q(participants=self.account),
                            status__in=['open', 'claimed']
                        )
                        
                        # Count jobs with updates since last view
                        updated_jobs = sum(1 for job in jobs if job.is_updated_since_last_view(self.account))

                        if updated_jobs > 0:
                            self.msg(f"|wYou have {updated_jobs} job{'s' if updated_jobs != 1 else ''} with new activity.|n")
                except (ImportError, ModuleNotFoundError):
                    # Jobs module not available or not properly installed
                    from evennia.utils import logger
                    logger.log_info(f"Jobs module not available during login notification for {self.key}")
                except Exception as e:
                    # Log any other errors but don't crash the login process
                    from evennia.utils import logger
                    logger.log_err(f"Error checking job notifications for {self.key}: {str(e)}")

    @property
    def character_sheet(self):
        sheet_id = self.db.character_sheet_id
        if sheet_id is not None:
            try:
                sheet = CharacterSheet.objects.get(id=sheet_id)
                if not sheet.full_name:
                    self.initialize_character_sheet(sheet)
                return sheet
            except CharacterSheet.DoesNotExist:
                logger.warning(f"Character sheet with ID {sheet_id} not found for {self.name}")
        return None

    @property
    def humanity(self):
        """Calculate and return the character's humanity."""
        return self.character_sheet.current_humanity if self.character_sheet else None

    def adjust_humanity(self, amount):
        """Adjust the character's humanity."""
        if self.character_sheet:
            self.character_sheet.reduce_humanity(amount)

    def get_attribute(self, attr_name):
        """Get the value of a character attribute."""
        return getattr(self.character_sheet, attr_name, None) if self.character_sheet else None

    def set_attribute(self, attr_name, value):
        """Set the value of a character attribute."""
        if self.character_sheet and hasattr(self.character_sheet, attr_name):
            setattr(self.character_sheet, attr_name, value)
            self.character_sheet.save()
        else:
            raise AttributeError(f"CharacterSheet has no attribute '{attr_name}'")

    @property
    def language_list(self):
        if not self.character_sheet:
            return []
        return [f"{cl.language.name} (Level {cl.level})" 
                for cl in self.character_sheet.character_languages.all()]

    def knows_language(self, language_name):
        if not self.character_sheet:
            return False
        return self.character_sheet.character_languages.filter(
            language__name__iexact=language_name
        ).exists()

    def at_post_move(self, source_location, **kwargs):
        super().at_post_move(source_location, **kwargs)
        if self.character_sheet:
            self.character_sheet.refresh_from_db()

    def return_appearance(self, looker, **kwargs):
        """
        This formats a description for any object looking at this object.
        """
        if not looker:
            return ""
        
        # Get the description
        desc = self.db.desc

        # Start with the name
        string = f"|c{self.get_display_name(looker)}|n\n"

        # Process character description
        if desc:
            # Replace both %t and |- with a consistent tab marker
            desc = desc.replace('%t', '|t').replace('|-', '|t')
            
            paragraphs = desc.split('%r')
            formatted_paragraphs = []
            for p in paragraphs:
                if not p.strip():
                    formatted_paragraphs.append('')  # Add blank line for empty paragraph
                    continue
                
                # Handle tabs manually
                lines = p.split('|t')
                indented_lines = [line.strip() for line in lines]
                indented_text = '\n    '.join(indented_lines)
                
                # Wrap each line individually
                wrapped_lines = [wrap_ansi(line, width=78) for line in indented_text.split('\n')]
                formatted_paragraphs.append('\n'.join(wrapped_lines))
            
            # Join paragraphs with a single newline, and remove any consecutive newlines
            joined_paragraphs = '\n'.join(formatted_paragraphs)
            joined_paragraphs = re.sub(r'\n{3,}', '\n\n', joined_paragraphs)
            
            string += joined_paragraphs + "\n"

        # Add any other details you want to include in the character's appearance
        # For example, you might want to add information about their equipment, stats, etc.

        return string

    def execute_cmd(self, raw_string, session=None, **kwargs):
        # Use regex to match ':' followed immediately by any non-space character
        if re.match(r'^:\S', raw_string):
            # Treat it as a pose command, inserting a space after the colon
            raw_string = "pose " + raw_string[1:]
        return super().execute_cmd(raw_string, session=session, **kwargs)
    
class Note:
    def __init__(self, name, text, category="General", is_public=False, is_approved=False, 
                 approved_by=None, approved_at=None, created_at=None, updated_at=None, note_id=None):
        self.name = name
        self.text = text
        self.category = category
        self.is_public = is_public
        self.is_approved = is_approved
        self.approved_by = approved_by
        self.approved_at = approved_at
        self.created_at = created_at if isinstance(created_at, datetime) else datetime.now()
        self.updated_at = updated_at if isinstance(updated_at, datetime) else datetime.now()
        self.note_id = note_id

    @property
    def id(self):
        """For backwards compatibility"""
        return self.note_id

    def to_dict(self):
        return {
            'name': self.name,
            'text': self.text,
            'category': self.category,
            'is_public': self.is_public,
            'is_approved': self.is_approved,
            'approved_by': self.approved_by,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'note_id': self.note_id
        }

    @classmethod
    def from_dict(cls, data):
        # Handle SaverDict by creating a new dict with its items
        note_data = {k: v for k, v in data.items()}
        
        # Convert datetime strings back to datetime objects
        for field in ['created_at', 'updated_at', 'approved_at']:
            if note_data.get(field):
                try:
                    if isinstance(note_data[field], str):
                        note_data[field] = datetime.fromisoformat(note_data[field])
                except (ValueError, TypeError):
                    note_data[field] = None
            else:
                note_data[field] = None
                
        return cls(**note_data)
    
    @lazy_property
    def notes(self):
        return Note.objects.filter(character=self)

    def add_note(self, name, text, category="General"):
        """Add a new note to the character."""
        notes = self.attributes.get('notes', {})
        
        # Find the first available ID by checking for gaps
        used_ids = set(int(id_) for id_ in notes.keys())
        note_id = 1
        while note_id in used_ids:
            note_id += 1
        
        # Create the new note
        note_data = {
            'name': name,
            'text': text,
            'category': category,
            'is_public': False,
            'is_approved': False,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        notes[str(note_id)] = note_data
        self.attributes.add('notes', notes)
        
        return Note(
            name=name,
            text=text,
            category=category,
            is_public=False,
            is_approved=False,
            created_at=note_data['created_at'],
            updated_at=note_data['updated_at'],
            note_id=str(note_id)
        )

    def get_note(self, note_id):
        """Get a specific note by ID."""
        notes = self.attributes.get('notes', default={})
        note_data = notes.get(str(note_id))
        return Note.from_dict(note_data) if note_data else None

    def get_all_notes(self):
        """Get all notes for this character."""
        notes = self.attributes.get('notes', default={})
        return [Note.from_dict(note_data) for note_data in notes.values()]

    def update_note(self, note_id, text=None, category=None, **kwargs):
        """Update an existing note."""
        notes = self.attributes.get('notes', default={})
        if str(note_id) in notes:
            note_data = notes[str(note_id)]
            if text is not None:
                note_data['text'] = text
            if category is not None:
                note_data['category'] = category
            note_data.update(kwargs)
            note_data['updated_at'] = datetime.now().isoformat()
            notes[str(note_id)] = note_data
            self.attributes.add('notes', notes)
            return True
        return False

    def change_note_status(self, note_name, is_public):
        """Change the visibility status of a note."""
        try:
            note = self.get_note(note_name)
            if note:
                note.is_public = is_public
                note.save()
                return True
            return False
        except Exception as e:
            return False

    def delete_note(self, note_id):
        """Delete a note."""
        notes = self.attributes.get('notes', default={})
        if str(note_id) in notes:
            del notes[str(note_id)]
            self.attributes.add('notes', notes)
            return True
        return False

    def get_notes_by_category(self, category):
        """Get all notes in a specific category."""
        return [note for note in self.get_all_notes() 
                if note.category.lower() == category.lower()]

    def get_public_notes(self):
        """Get all public notes."""
        return [note for note in self.get_all_notes() if note.is_public]

    def get_approved_notes(self):
        """Get all approved notes."""
        return [note for note in self.get_all_notes() if note.is_approved]

    def search_notes(self, search_term):
        """Search notes by name or content."""
        search_term = search_term.lower()
        return [
            note for note in self.get_all_notes()
            if search_term in note.name.lower() or search_term in note.text.lower()
        ]