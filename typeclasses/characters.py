"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.
"""
from evennia import DefaultCharacter
from django.apps import apps
from world.cyberpunk_constants import LANGUAGES
from world.languages.models import CharacterLanguage, Language
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
        
        # Initialize character attributes directly on the typeclass
        self.db.full_name = self.name
        self.db.handle = ""
        self.db.role = ""
        self.db.gender = ""
        self.db.age = 0
        self.db.hometown = ""
        self.db.height = 0
        self.db.weight = 0
        
        # Faction-related attributes
        self.db.faction = None  # Name of the character's faction
        self.db.faction_rep = {}  # Dictionary of faction name : reputation value
        
        # Core attributes
        self.db.intelligence = 1
        self.db.reflexes = 1
        self.db.dexterity = 1
        self.db.technology = 1
        self.db.cool = 1
        self.db.willpower = 1
        self.db.luck = 1
        self.db.current_luck = 1
        self.db.move = 1
        self.db.body = 1
        self.db.empathy = 1
        
        # Derived stats
        self.db.max_hp = 10 + (5 * ((self.db.body + self.db.willpower) // 2))
        self.db.current_hp = self.db.max_hp
        self.db.humanity = self.db.empathy * 10
        self.db.humanity_loss = 0
        self.db.total_cyberware_humanity_loss = 0
        self.db.serious_wounds = self.db.body
        self.db.death_save = self.db.body
        
        # Economy
        self.db.eurodollars = 0
        self.db.reputation_points = 0
        self.db.rep = 0
        
        # Status flags
        self.db.is_complete = False
        self.db.has_cyberarm = False
        
        # Lifepath - General
        self.db.cultural_origin = ""
        self.db.personality = ""
        self.db.clothing_style = ""
        self.db.hairstyle = ""
        self.db.affectation = ""
        self.db.motivation = ""
        self.db.life_goal = ""
        self.db.valued_person = ""
        self.db.valued_possession = ""
        self.db.family_background = ""
        self.db.environment = ""
        self.db.family_crisis = ""
        
        # Role-specific lifepath attributes (initialized when role is set)
        self.db.role_lifepath = {}
        
        # Skills - initialize all to 0 (this can be extended with all skills from the model)
        self.db.skills = {
            # Awareness Skills
            "concentration": 0,
            "conceal_object": 0,
            "lip_reading": 0,
            "perception": 0,
            "tracking": 0,
            # Body Skills
            "athletics": 0,
            "contortionist": 0,
            "dance": 0,
            "endurance": 0,
            "resist_torture_drugs": 0,
            "stealth": 0,
            # Control Skills
            "drive_land": 0,
            "pilot_air": 0,
            "pilot_sea": 0,
            "riding": 0,
            # Education Skills
            "accounting": 0,
            "animal_handling": 0,
            "bureaucracy": 0,
            "business": 0,
            "composition": 0,   
            "criminology": 0,
            "cryptography": 0,
            "deduction": 0,
            "education": 0,
            "gamble": 0,
            "library_search": 0,    
            "local_expert": 0,
            "zoology": 0,
            "physics": 0,
            "stock_market": 0,
            "biology": 0,
            "chemistry": 0,
            "neuroscience": 0,
            "data_science": 0,
            "economics": 0,
            "sociology": 0,
            "political_science": 0,
            "genetics": 0,
            "anatomy": 0,
            "robotics": 0,
            "nanotechnology": 0,
            "tactics": 0,
            "wilderness_survival": 0,
            # Fighting Skills
            "brawling": 0,
            "evasion": 0,
            "martial_arts": 0,
            "melee": 0,
            # Performance Skills
            "acting": 0,
            "dance": 0,
            "singing": 0,
            "theater": 0,
            # Ranged Weapon Skills
            "archery": 0,
            "autofire": 0,
            "handgun": 0,
            "heavy_weapons": 0,
            "shoulder_arms": 0,
            # Social Skills
            "bribery": 0,
            "conversation": 0,
            "human_perception": 0,
            "interrogation": 0,
            "persuasion": 0,
            "play_instrument": 0,
            "personal_grooming": 0,
            "streetwise": 0,
            "trading": 0,
            "style": 0,
            # Technique Skills
            "air_vehicle_tech": 0,
            "basic_tech": 0,
            "cybertech": 0,
            "demolitions": 0,
            "electronics": 0,
            "first_aid": 0,
            "forgery": 0,
            "land_vehicle_tech": 0,
            "artistry": 0,
            "paramedic": 0,
            "photography": 0,
            "pick_lock": 0,
            "pick_pocket": 0,
            "sea_vehicle_tech": 0,
            "weaponstech": 0,
            # Role abilities
            "charismatic_impact": 0,
            "combat_awareness": 0,
            "interface": 0,
            "maker": 0,
            "medicine": 0,
            "credibility": 0,
            "teamwork": 0,
            "backup": 0,
            "operator": 0,
            "moto": 0
        }
     
        # Initialize skill instances dictionary
        self.db.skill_instances = {}

        # Only create a character sheet if we have an account
        if self.account:
            self.create_character_sheet(self.account)
        # Skip character sheet creation during initial setup - it will be created when a player connects
        
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

    @classmethod
    def create_character_sheet(cls, account=None):
        """Create a character sheet and initialize required related objects."""
        # Get models via lazy loading
        from django.apps import apps
        CharacterSheet = apps.get_model('cyberpunk_sheets', 'CharacterSheet')
        Inventory = apps.get_model('inventory', 'Inventory')
        
        # If no account is provided (during server initialization), create a placeholder sheet
        if account is None:
            # During initial setup, we just return the character without creating a sheet
            # The sheet will be created later when a real account is available
            return None
        
        # Create character object if needed
        if not cls.objects.filter(account=account).exists():
            # Create new character object
            character = cls.create(key=f"{account.username}'s Character", account=account)
        else:
            character = cls.objects.get(account=account)
        
        # Create character sheet
        sheet = CharacterSheet.objects.create(account=account, character=character)
        character.db.character_sheet_id = sheet.id
        
        # Create inventory
        inventory, _ = Inventory.objects.get_or_create(
            character=sheet,
            character_object=character
        )
        
        return character

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
        
        # Automatically migrate character sheet data to typeclass if needed
        if not self.attributes.has("db_migrated_character_sheet"):
            logger.log_info(f"Attempting to migrate character sheet data for {self.key}")
            try:
                if self.migrate_sheet_to_typeclass():
                    logger.log_info(f"Successfully migrated character sheet data for {self.key}")
                    self.attributes.add("db_migrated_character_sheet", True)
            except Exception as e:
                logger.log_err(f"Error migrating character sheet data for {self.key}: {str(e)}")

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
        """Get a character attribute value."""
        if attr_name in self.db.skills:
            return self.db.skills.get(attr_name, 0)
        return self.attributes.get(attr_name)
    
    def set_attribute(self, attr_name, value):
        """Set a character attribute value."""
        if attr_name in self.db.skills:
            skills = self.db.skills
            skills[attr_name] = value
            self.db.skills = skills
        else:
            self.attributes.add(attr_name, value)
    
    def get_skill(self, skill_name):
        """Get a skill value by name."""
        return self.db.skills.get(skill_name.lower().replace(' ', '_'), 0)
    
    def set_skill(self, skill_name, value):
        """Set a skill value."""
        skill_key = skill_name.lower().replace(' ', '_')
        skills = self.db.skills
        skills[skill_key] = value
        self.db.skills = skills
    
    def recalculate_derived_stats(self):
        """Recalculate all derived statistics."""
        # Calculate max HP
        self.db.max_hp = 10 + (5 * ((self.db.body + self.db.willpower) // 2))
        
        # Ensure current HP doesn't exceed max HP
        if self.db.current_hp > self.db.max_hp:
            self.db.current_hp = self.db.max_hp
        
        # If current HP is 0 and this is initialization, set to max
        if self.db.current_hp == 0:
            self.db.current_hp = self.db.max_hp
        
        # Ensure current HP is never negative
        self.db.current_hp = max(0, self.db.current_hp)
        
        # Death save and serious wounds based on body
        self.db.death_save = self.db.body
        self.db.serious_wounds = self.db.body
        
        # Calculate humanity based on empathy and cyberware
        self.calculate_humanity()
    
    def calculate_humanity(self):
        """Calculate character's humanity based on empathy and installed cyberware."""
        # Get total humanity loss from cyberware
        total_humanity_loss = self.calculate_cyberware_humanity_loss()
        
        # Base humanity is empathy * 10
        base_humanity = self.db.empathy * 10
        
        # Current humanity is base minus losses
        self.db.humanity = max(0, base_humanity - total_humanity_loss)
        
        # Only update empathy if it's been significantly reduced
        if base_humanity <= total_humanity_loss:
            self.db.empathy = max(1, self.db.humanity // 10)
        
        # Store total loss for reference
        self.db.total_cyberware_humanity_loss = total_humanity_loss
    
    def calculate_cyberware_humanity_loss(self):
        """Calculate total humanity loss from installed cyberware."""
        from django.apps import apps
        CyberwareInstance = apps.get_model('inventory', 'CyberwareInstance')
        
        # Get character sheet for backward compatibility during transition
        try:
            character_sheet = self.character_sheet
            if character_sheet:
                installed_cyberware = CyberwareInstance.objects.filter(
                    character=character_sheet, installed=True
                )
            else:
                return 0  # No character sheet, no cyberware
        except Exception:
            return 0  # Error accessing character sheet
            
        # Sum humanity loss from all installed cyberware
        return sum(cw.cyberware.humanity_loss for cw in installed_cyberware)
    
    def take_damage(self, amount):
        """Inflict damage on the character."""
        self.db.current_hp = max(0, self.db.current_hp - amount)
    
    def heal(self, amount):
        """Heal the character by the specified amount."""
        self.db.current_hp = min(self.db.current_hp + amount, self.db.max_hp)
    
    def spend_luck(self):
        """Spend a luck point if available."""
        if self.db.current_luck > 0:
            self.db.current_luck -= 1
            return True
        return False
    
    def gain_luck(self, amount=1):
        """Regain luck points, up to the maximum."""
        self.db.current_luck = min(self.db.current_luck + amount, self.db.luck)
        return self.db.current_luck
    
    def add_reputation(self, amount):
        """Add reputation points and update rep level if necessary."""
        self.db.reputation_points += amount
        self.update_rep()
    
    def update_rep(self):
        """Update the rep level based on reputation points."""
        new_rep = min(self.db.reputation_points // 100, 10)
        if new_rep != self.db.rep:
            self.db.rep = new_rep
    
    def get_active_skills(self):
        """Return a dictionary of skills with values greater than 0."""
        return {name: value for name, value in self.db.skills.items() if value > 0}
    
    @property
    def active_skills(self):
        """Property that returns active skills with formatted names."""
        raw_skills = self.get_active_skills()
        return {name.replace('_', ' ').title(): value for name, value in raw_skills.items()}
    
    @property
    def role_ability(self):
        """Get the character's role ability value based on role."""
        role_ability_mapping = {
            'Rockerboy': 'charismatic_impact',
            'Solo': 'combat_awareness',
            'Netrunner': 'interface',
            'Tech': 'maker',
            'Medtech': 'medicine',
            'Media': 'credibility',
            'Exec': 'teamwork',
            'Lawman': 'backup',
            'Fixer': 'operator',
            'Nomad': 'moto'
        }
        role_skill = role_ability_mapping.get(self.db.role)
        return self.db.skills.get(role_skill, 0) if role_skill else 0

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
    
    def migrate_sheet_to_typeclass(self):
        """
        Migrate data from CharacterSheet model to Character typeclass attributes.
        This allows for a smooth transition from the model-based approach to typeclass-based.
        """
        if not self.character_sheet:
            return False
        
        sheet = self.character_sheet
        
        # Basic character info
        self.db.full_name = sheet.full_name
        self.db.handle = sheet.handle
        self.db.role = sheet.role
        self.db.gender = sheet.gender
        self.db.age = sheet.age
        self.db.hometown = sheet.hometown
        self.db.height = sheet.height
        self.db.weight = sheet.weight
        
        # Attributes
        self.db.intelligence = sheet.intelligence
        self.db.reflexes = sheet.reflexes
        self.db.dexterity = sheet.dexterity
        self.db.technology = sheet.technology
        self.db.cool = sheet.cool
        self.db.willpower = sheet.willpower
        self.db.luck = sheet.luck
        self.db.current_luck = sheet.current_luck
        self.db.move = sheet.move
        self.db.body = sheet.body
        self.db.empathy = sheet.empathy
        
        # Economy and reputation
        self.db.eurodollars = sheet.eurodollars
        self.db.reputation_points = sheet.reputation_points
        self.db.rep = sheet.rep
        
        # Character status
        self.db.is_complete = sheet.is_complete
        self.db.has_cyberarm = sheet.has_cyberarm
        
        # Derived stats
        self.db.max_hp = sheet._max_hp
        self.db.current_hp = sheet._current_hp
        self.db.humanity = sheet.humanity
        self.db.humanity_loss = sheet.humanity_loss
        self.db.total_cyberware_humanity_loss = sheet.total_cyberware_humanity_loss
        
        # Skills
        skills = self.db.skills or {}
        for field in sheet._meta.get_fields():
            field_name = field.name
            # Only process skill fields (those that are integers and not system fields)
            if (isinstance(getattr(sheet, field_name, None), int) and 
                not field_name.startswith('_') and 
                field_name not in ['id', 'eurodollars', 'reputation_points', 'rep', 
                                  'intelligence', 'reflexes', 'dexterity', 'technology',
                                  'cool', 'willpower', 'luck', 'current_luck', 'move', 
                                  'body', 'empathy', 'age', 'height', 'weight']):
                skills[field_name] = getattr(sheet, field_name)
        
        self.db.skills = skills
        
        # Migrate lifepath data
        self.migrate_lifepath_from_sheet()
        
        return True
    
    def migrate_typeclass_to_sheet(self):
        """
        Migrate data from Character typeclass attributes to CharacterSheet model.
        This allows keeping the model updated during the transition period.
        """
        sheet = self.character_sheet
        if not sheet:
            return False
        
        # Basic character info
        sheet.full_name = self.db.full_name
        sheet.handle = self.db.handle
        sheet.role = self.db.role
        sheet.gender = self.db.gender
        sheet.age = self.db.age
        sheet.hometown = self.db.hometown
        sheet.height = self.db.height
        sheet.weight = self.db.weight
        
        # Attributes
        sheet.intelligence = self.db.intelligence
        sheet.reflexes = self.db.reflexes
        sheet.dexterity = self.db.dexterity
        sheet.technology = self.db.technology
        sheet.cool = self.db.cool
        sheet.willpower = self.db.willpower
        sheet.luck = self.db.luck
        sheet.current_luck = self.db.current_luck
        sheet.move = self.db.move
        sheet.body = self.db.body
        sheet.empathy = self.db.empathy
        
        # Economy and reputation
        sheet.eurodollars = self.db.eurodollars
        sheet.reputation_points = self.db.reputation_points
        sheet.rep = self.db.rep
        
        # Character status
        sheet.is_complete = self.db.is_complete
        sheet.has_cyberarm = self.db.has_cyberarm
        
        # Derived stats
        sheet._max_hp = self.db.max_hp
        sheet._current_hp = self.db.current_hp
        sheet.humanity = self.db.humanity
        sheet.humanity_loss = self.db.humanity_loss
        sheet.total_cyberware_humanity_loss = self.db.total_cyberware_humanity_loss
        
        # Skills
        skills = self.db.skills or {}
        for skill_name, value in skills.items():
            if hasattr(sheet, skill_name):
                setattr(sheet, skill_name, value)
        
        # Save the sheet with skip_recalculation flag to prevent circular updates
        sheet.save(skip_recalculation=True)
        return True

    # Language-related methods
    def add_language(self, language_name, level):
        """Add a language to the character."""
        # Initialize languages dict if not exists
        if not hasattr(self.db, 'languages'):
            self.db.languages = {}
        
        # Add the language with its level
        languages = self.db.languages
        languages[language_name] = level
        self.db.languages = languages
        
        # For backward compatibility, also update CharacterSheet if it exists
        if self.character_sheet:
            self.character_sheet.add_language(language_name, level)
    
    def remove_language(self, language_name):
        """Remove a language from the character."""
        if not hasattr(self.db, 'languages'):
            return
        
        # Remove the language if it exists
        languages = self.db.languages
        if language_name in languages:
            del languages[language_name]
            self.db.languages = languages
        
        # For backward compatibility, also update CharacterSheet
        if self.character_sheet:
            self.character_sheet.remove_language(language_name)
    
    def get_language_level(self, language_name):
        """Get the character's level in a specific language."""
        if not hasattr(self.db, 'languages'):
            return 0
        
        return self.db.languages.get(language_name, 0)
    
    def update_language_level(self, language_name, new_level):
        """Update the level of a language the character knows."""
        if not hasattr(self.db, 'languages'):
            self.db.languages = {}
        
        languages = self.db.languages
        languages[language_name] = new_level
        self.db.languages = languages
        
        # For backward compatibility
        if self.character_sheet:
            self.character_sheet.update_language_level(language_name, new_level)
    
    @property
    def languages(self):
        """Get a dictionary of all languages the character knows."""
        if not hasattr(self.db, 'languages'):
            self.db.languages = {}
            
            # If we have a character sheet, initialize from it
            if self.character_sheet:
                for lang_data in self.character_sheet.language_list:
                    self.db.languages[lang_data['name']] = lang_data['level']
                    
        return self.db.languages
    
    @property
    def language_list(self):
        """Get a formatted list of languages for display."""
        return [f"{name} (Level {level})" for name, level in self.languages.items()]
    
    def knows_language(self, language_name):
        """Check if the character knows a specific language."""
        return language_name in self.languages

    def set_default_language(self, language_name="English", level=4):
        """Set a default language for the character."""
        # Add the language directly using the typeclass method
        self.add_language(language_name, level)
        
        # For compatibility with the CharacterSheet model
        if self.character_sheet:
            # Use lazy loading with string references
            from django.apps import apps
            Language = apps.get_model('languages', 'Language')
            CharacterLanguage = apps.get_model('languages', 'CharacterLanguage')
            
            try:
                language = Language.objects.get(name=language_name)
                CharacterLanguage.objects.get_or_create(
                    character_sheet=self.character_sheet,
                    language=language,
                    defaults={'level': level}
                )
            except Exception:
                pass  # Fail silently if language doesn't exist

    def calculate_base_unarmed_damage(self):
        if self.body >= 11:
            return 4
        elif self.body >= 7:
            return 3
        elif self.body >= 5 or (self.body >= 1 and self.has_cyberarm):
            return 2
        else:
            return 1

    # Language-related methods
    def add_language(self, language_name, level):
        """Add a language to the character."""
        # Initialize languages dict if not exists
        if not hasattr(self.db, 'languages'):
            self.db.languages = {}
        
        # Add the language with its level
        languages = self.db.languages
        languages[language_name] = level
        self.db.languages = languages
        
        # For backward compatibility, also update CharacterSheet if it exists
        if self.character_sheet:
            self.character_sheet.add_language(language_name, level)

    def remove_language(self, language_name):
        try:
            language = Language.objects.get(name__iexact=language_name)
            CharacterLanguage.objects.filter(character_sheet=self, language=language).delete()
            logger.log_info(f"Removed language {language_name} from character sheet")
        except Language.DoesNotExist:
            logger.log_warn(f"Language {language_name} not found, nothing to remove")

    def update_language_level(self, language_name, new_level):
        try:
            language = Language.objects.get(name=language_name)
            char_lang = CharacterLanguage.objects.get(character_sheet=self, language=language)
            char_lang.level = new_level
            char_lang.save()
        except (Language.DoesNotExist, CharacterLanguage.DoesNotExist):
            pass  # Language or character-language relationship not found

    def get_skill_instance(self, skill_name, instance):
        """Get a skill instance value by name and instance."""
        if not self.db.skill_instances:
            return 0
        skill_key = f"{skill_name.lower().replace(' ', '_')}({instance})"
        return self.db.skill_instances.get(skill_key, 0)
    
    def set_skill_instance(self, skill_name, instance, value):
        """Set a skill instance value."""
        if not self.db.skill_instances:
            self.db.skill_instances = {}
        skill_key = f"{skill_name.lower().replace(' ', '_')}({instance})"
        skill_instances = self.db.skill_instances
        skill_instances[skill_key] = value
        self.db.skill_instances = skill_instances
    
    def get_all_skill_instances(self):
        """Get all skill instances as a dictionary."""
        return self.db.skill_instances or {}
    
    def calculate_spent_points(self):
        """Calculate spent character points"""
        # Stats
        stat_points = sum([
            self.db.intelligence, self.db.reflexes, self.db.dexterity, 
            self.db.technology, self.db.cool, self.db.willpower,
            self.db.luck, self.db.move, self.db.body, self.db.empathy
        ])
        
        # Skills - get from skills dictionary
        skills = self.db.skills
        double_cost_skills = ['autofire', 'martial_arts', 'pilot_air', 
                            'heavy_weapons', 'demolitions', 'electronics', 'paramedic']
        skill_points = 0
        for skill, value in skills.items():
            multiplier = 2 if skill in double_cost_skills else 1
            skill_points += value * multiplier
        
        # Skill instances - get from skill_instances dictionary
        if self.db.skill_instances:
            for skill_instance, value in self.db.skill_instances.items():
                # Extract base skill name from instance key (format: "skill(instance)")
                if "(" in skill_instance:
                    base_skill = skill_instance.split("(")[0]
                    multiplier = 2 if base_skill in double_cost_skills else 1
                    skill_points += value * multiplier
        
        # Languages
        language_points = sum(level for _, level in self.languages.items())
        
        total_skill_points = skill_points + language_points
        return stat_points, total_skill_points
        
    @property
    def active_skills_with_instances(self):
        """Property that returns active skills and skill instances with formatted names."""
        # Get regular skills
        raw_skills = self.get_active_skills()
        formatted_skills = {name.replace('_', ' ').title(): value for name, value in raw_skills.items()}
        
        # Get skill instances
        if self.db.skill_instances:
            for key, value in self.db.skill_instances.items():
                if value > 0:
                    # Parse the key to get the readable name
                    if "(" in key and ")" in key:
                        base_name, instance = key.split("(", 1)
                        instance = instance.rstrip(")")
                        formatted_name = f"{base_name.replace('_', ' ').title()} ({instance})"
                        formatted_skills[formatted_name] = value
                    
        return formatted_skills

    def set_role(self, role):
        """
        Set the character's role and initialize role-specific lifepath fields.
        
        Args:
            role (str): The role name (Rockerboy, Solo, Netrunner, etc.)
        """
        # Make sure role is properly capitalized
        role = role.capitalize()
        
        # Validate role
        valid_roles = ['Rockerboy', 'Solo', 'Netrunner', 'Tech', 'Medtech', 
                       'Media', 'Exec', 'Lawman', 'Fixer', 'Nomad']
        
        if role not in valid_roles:
            logger.log_err(f"Invalid role '{role}' for character {self.name}")
            return False
        
        # Set the role
        self.db.role = role
        
        # Initialize role-specific lifepath fields based on role
        role_fields = {}
        
        if role == "Rockerboy":
            role_fields = {
                "what_kind_of_rockerboy_are_you": "",
                "whos_gunning_for_you_your_group": "",
                "where_do_you_perform": ""
            }
        elif role == "Solo":
            role_fields = {
                "what_kind_of_solo_are_you": "",
                "whats_your_moral_compass_like": "",
                "whos_gunning_for_you": "",
                "whats_your_operational_territory": ""
            }
        elif role == "Netrunner":
            role_fields = {
                "what_kind_of_runner_are_you": "",
                "who_are_some_of_your_other_clients": "",
                "where_do_you_get_your_programs": "",
                "whos_gunning_for_you": ""
            }
        elif role == "Tech":
            role_fields = {
                "what_kind_of_tech_are_you": "",
                "whats_your_workspace_like": "",
                "who_are_your_main_clients": "",
                "where_do_you_get_your_supplies": "",
                "whos_gunning_for_you": ""
            }
        elif role == "Medtech":
            role_fields = {
                "what_kind_of_medtech_are_you": "",
                "who_are_your_main_clients": "",
                "where_do_you_get_your_supplies": ""
            }
        elif role == "Media":
            role_fields = {
                "what_kind_of_media_are_you": "",
                "how_does_your_work_reach_the_public": "",
                "how_ethical_are_you": "",
                "what_types_of_stories_do_you_want_to_tell": ""
            }
        elif role == "Exec":
            role_fields = {
                "what_kind_of_corp_do_you_work_for": "",
                "what_division_do_you_work_in": "",
                "how_good_bad_is_your_corp": "",
                "where_is_your_corp_based": "",
                "current_state_with_your_boss": ""
            }
        elif role == "Lawman":
            role_fields = {
                "what_is_your_position_on_the_force": "",
                "how_wide_is_your_groups_jurisdiction": "",
                "how_corrupt_is_your_group": "",
                "whos_gunning_for_your_group": "",
                "who_is_your_groups_major_target": ""
            }
        elif role == "Fixer":
            role_fields = {
                "what_kind_of_fixer_are_you": "",
                "who_are_your_side_clients": "",
                "whos_gunning_for_you": ""
            }
        elif role == "Nomad":
            role_fields = {
                "how_big_is_your_pack": "",
                "what_do_you_do_for_your_pack": "",
                "whats_your_packs_overall_philosophy": "",
                "whos_gunning_for_your_pack": "",
                "is_your_pack_based_on_land_air_or_sea": "",
                "land_sea_air_specialization": ""  # This will store the appropriate land/sea/air role based on previous answer
            }
            
        # Set the role-specific fields
        self.db.role_lifepath = role_fields
        
        return True

    def set_lifepath_attribute(self, attribute, value):
        """
        Set a general lifepath attribute.
        
        Args:
            attribute (str): The attribute name
            value (str): The attribute value
        """
        general_lifepath_attributes = [
            "cultural_origin", "personality", "clothing_style", "hairstyle",
            "affectation", "motivation", "life_goal", "valued_person",
            "valued_possession", "family_background", "environment", 
            "family_crisis"
        ]
        
        if attribute in general_lifepath_attributes:
            self.attributes.add(attribute, value)
            return True
        else:
            logger.log_err(f"Invalid lifepath attribute '{attribute}' for character {self.name}")
            return False
    
    def set_role_lifepath_attribute(self, attribute, value):
        """
        Set a role-specific lifepath attribute.
        
        Args:
            attribute (str): The attribute name
            value (str): The attribute value
        """
        if not self.db.role:
            logger.log_err(f"Cannot set role lifepath attribute - no role set for character {self.name}")
            return False
            
        if attribute in self.db.role_lifepath:
            role_lifepath = self.db.role_lifepath
            role_lifepath[attribute] = value
            self.db.role_lifepath = role_lifepath
            return True
        else:
            logger.log_err(f"Invalid role lifepath attribute '{attribute}' for role {self.db.role}")
            return False
            
    def get_lifepath_attribute(self, attribute):
        """
        Get a lifepath attribute (either general or role-specific).
        
        Args:
            attribute (str): The attribute name
            
        Returns:
            The attribute value or empty string if not found
        """
        # First check general lifepath attributes
        if hasattr(self.db, attribute):
            return getattr(self.db, attribute, "")
            
        # Then check role-specific attributes
        if self.db.role_lifepath and attribute in self.db.role_lifepath:
            return self.db.role_lifepath.get(attribute, "")
            
        return ""
    
    def migrate_lifepath_from_sheet(self):
        """Migrate lifepath data from CharacterSheet model to typeclass attributes."""
        if not self.character_sheet:
            logger.log_err(f"No character sheet found for {self.name}")
            return False
            
        cs = self.character_sheet
        
        # General lifepath
        self.db.cultural_origin = getattr(cs, 'cultural_origin', "")
        self.db.personality = getattr(cs, 'personality', "")
        self.db.clothing_style = getattr(cs, 'clothing_style', "")
        self.db.hairstyle = getattr(cs, 'hairstyle', "")
        self.db.affectation = getattr(cs, 'affectation', "")
        self.db.motivation = getattr(cs, 'motivation', "")
        self.db.life_goal = getattr(cs, 'life_goal', "")
        self.db.valued_person = getattr(cs, 'valued_person', "")
        self.db.valued_possession = getattr(cs, 'valued_possession', "")
        self.db.family_background = getattr(cs, 'family_background', "")
        self.db.environment = getattr(cs, 'environment', "")
        self.db.family_crisis = getattr(cs, 'family_crisis', "")
        
        # Role needs to be set first for role-specific fields
        role = getattr(cs, 'role', None)
        if role:
            self.set_role(role)
            
            # Role-specific fields
            role_fields = {}
            
            if role == "Rockerboy":
                role_fields = {
                    "what_kind_of_rockerboy_are_you": getattr(cs, 'what_kind_of_rockerboy_are_you', ""),
                    "whos_gunning_for_you_your_group": getattr(cs, 'whos_gunning_for_you_your_group', ""),
                    "where_do_you_perform": getattr(cs, 'where_do_you_perform', "")
                }
            elif role == "Solo":
                role_fields = {
                    "what_kind_of_solo_are_you": getattr(cs, 'what_kind_of_solo_are_you', ""),
                    "whats_your_moral_compass_like": getattr(cs, 'whats_your_moral_compass_like', ""),
                    "whos_gunning_for_you": getattr(cs, 'whos_gunning_for_you', ""),
                    "whats_your_operational_territory": getattr(cs, 'whats_your_operational_territory', "")
                }
            elif role == "Netrunner":
                role_fields = {
                    "what_kind_of_runner_are_you": getattr(cs, 'what_kind_of_runner_are_you', ""),
                    "who_are_some_of_your_other_clients": getattr(cs, 'who_are_some_of_your_other_clients', ""),
                    "where_do_you_get_your_programs": getattr(cs, 'where_do_you_get_your_programs', ""),
                    "whos_gunning_for_you": getattr(cs, 'whos_gunning_for_you', "")
                }
            elif role == "Tech":
                role_fields = {
                    "what_kind_of_tech_are_you": getattr(cs, 'what_kind_of_tech_are_you', ""),
                    "whats_your_workspace_like": getattr(cs, 'whats_your_workspace_like', ""),
                    "who_are_your_main_clients": getattr(cs, 'who_are_your_main_clients', ""),
                    "where_do_you_get_your_supplies": getattr(cs, 'where_do_you_get_your_supplies', ""),
                    "whos_gunning_for_you": getattr(cs, 'whos_gunning_for_you', "")
                }
            elif role == "Medtech":
                role_fields = {
                    "what_kind_of_medtech_are_you": getattr(cs, 'what_kind_of_medtech_are_you', ""),
                    "who_are_your_main_clients": getattr(cs, 'who_are_your_main_clients', ""),
                    "where_do_you_get_your_supplies": getattr(cs, 'where_do_you_get_your_supplies', "")
                }
            elif role == "Media":
                role_fields = {
                    "what_kind_of_media_are_you": getattr(cs, 'what_kind_of_media_are_you', ""),
                    "how_does_your_work_reach_the_public": getattr(cs, 'how_does_your_work_reach_the_public', ""),
                    "how_ethical_are_you": getattr(cs, 'how_ethical_are_you', ""),
                    "what_types_of_stories_do_you_want_to_tell": getattr(cs, 'what_types_of_stories_do_you_want_to_tell', "")
                }
            elif role == "Exec":
                role_fields = {
                    "what_kind_of_corp_do_you_work_for": getattr(cs, 'what_kind_of_corp_do_you_work_for', ""),
                    "what_division_do_you_work_in": getattr(cs, 'what_division_do_you_work_in', ""),
                    "how_good_bad_is_your_corp": getattr(cs, 'how_good_bad_is_your_corp', ""),
                    "where_is_your_corp_based": getattr(cs, 'where_is_your_corp_based', ""),
                    "current_state_with_your_boss": getattr(cs, 'current_state_with_your_boss', "")
                }
            elif role == "Lawman":
                role_fields = {
                    "what_is_your_position_on_the_force": getattr(cs, 'what_is_your_position_on_the_force', ""),
                    "how_wide_is_your_groups_jurisdiction": getattr(cs, 'how_wide_is_your_groups_jurisdiction', ""),
                    "how_corrupt_is_your_group": getattr(cs, 'how_corrupt_is_your_group', ""),
                    "whos_gunning_for_your_group": getattr(cs, 'whos_gunning_for_your_group', ""),
                    "who_is_your_groups_major_target": getattr(cs, 'who_is_your_groups_major_target', "")
                }
            elif role == "Fixer":
                role_fields = {
                    "what_kind_of_fixer_are_you": getattr(cs, 'what_kind_of_fixer_are_you', ""),
                    "who_are_your_side_clients": getattr(cs, 'who_are_your_side_clients', ""),
                    "whos_gunning_for_you": getattr(cs, 'whos_gunning_for_you', "")
                }
            elif role == "Nomad":
                role_fields = {
                    "how_big_is_your_pack": getattr(cs, 'how_big_is_your_pack', ""),
                    "what_do_you_do_for_your_pack": getattr(cs, 'what_do_you_do_for_your_pack', ""),
                    "whats_your_packs_overall_philosophy": getattr(cs, 'whats_your_packs_overall_philosophy', ""),
                    "whos_gunning_for_your_pack": getattr(cs, 'whos_gunning_for_your_pack', ""),
                    "is_your_pack_based_on_land_air_or_sea": getattr(cs, 'is_your_pack_based_on_land_air_or_sea', "")
                }
                
                # Handle the land/sea/air specialization
                if hasattr(cs, 'land_specialization') and cs.land_specialization:
                    role_fields["land_sea_air_specialization"] = cs.land_specialization
                elif hasattr(cs, 'air_specialization') and cs.air_specialization:
                    role_fields["land_sea_air_specialization"] = cs.air_specialization
                elif hasattr(cs, 'sea_specialization') and cs.sea_specialization:
                    role_fields["land_sea_air_specialization"] = cs.sea_specialization
                
            self.db.role_lifepath = role_fields
        
        return True

@classmethod
def create_sheet(cls, account, character, **kwargs):
    """Create a sheet for the character"""
    # Get the CharacterSheet model
    CharacterSheet = apps.get_model('cyberpunk_sheets', 'CharacterSheet')
    sheet = CharacterSheet.objects.create(account=account, character=character, **kwargs)
    if character:
        character.db.character_sheet_id = sheet.id
    return sheet

def get_remaining_points(self):
    """Get remaining character points"""
    stat_points_spent, skill_points_spent = self.calculate_spent_points()
    remaining_stat_points = max(0, 62 - stat_points_spent)
    remaining_skill_points = max(0, 86 - skill_points_spent)
    return remaining_stat_points, remaining_skill_points

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
    def initialize_humanity(self):
        self.humanity = self.empathy * 10
        self.total_cyberware_humanity_loss = 0

    def calculate_humanity_loss(self):
        logger.info("Starting calculate_humanity_loss in CharacterSheet")
        # Use lazy loading
        CyberwareInstance = apps.get_model('inventory', 'CyberwareInstance')
        installed_cyberware = CyberwareInstance.objects.filter(character=self, installed=True)
        total_cyberware_hl = sum(cw.cyberware.humanity_loss for cw in installed_cyberware)
        
        logger.info(f"Total cyberware humanity loss: {total_cyberware_hl}")
        
        # Calculate new humanity
        new_humanity = max(0, self.empathy * 10 - total_cyberware_hl)
        
        logger.info(f"New calculated humanity: {new_humanity}")
        
        # Update humanity
        self.humanity = new_humanity
        
        # Only update empathy if it's been reduced to 0
        if self.empathy * 10 <= total_cyberware_hl:
            self.empathy = max(1, new_humanity // 10)
        
        self.total_cyberware_humanity_loss = total_cyberware_hl
        logger.info("About to recalculate derived stats")
        self.recalculate_derived_stats()
        logger.info("Derived stats recalculated")
        self.save()
        logger.info("CharacterSheet saved")

    def recalculate_derived_stats(self):
        self._max_hp = 10 + (5 * ((self.body + self.willpower) // 2))
        self.death_save = self.body
        self.serious_wounds = self.body
        
        total_cyberware_hl = self.calculate_total_cyberware_hl()
        
        # Calculate current humanity
        self.humanity = max(0, self.empathy * 10 - total_cyberware_hl)
        
        # Ensure _current_hp doesn't exceed _max_hp
        if self._current_hp > self._max_hp:
            self._current_hp = self._max_hp
        # If _current_hp is 0, set it to _max_hp
        if self._current_hp == 0:
            self._current_hp = self._max_hp
        # Ensure _current_hp is never negative   
        self._current_hp = max(0, self._current_hp)

        # Save without triggering another recalculation
        self.save(skip_recalculation=True)

    def calculate_total_cyberware_hl(self):
        # Use lazy loading
        CyberwareInstance = apps.get_model('inventory', 'CyberwareInstance')
        installed_cyberware = CyberwareInstance.objects.filter(character=self, installed=True)
        return sum(cw.cyberware.humanity_loss for cw in installed_cyberware)

    def save(self, *args, **kwargs):
        # Add a flag to prevent recursive calls
        if not kwargs.get('skip_recalculation'):
            self.recalculate_derived_stats()
        super().save(*args, **kwargs)

    def clean(self):
                if self._current_hp < 0:
                 self._current_hp = 0
                elif self._current_hp > self._max_hp:
                                  self._current_hp = self._max_hp

    def take_damage(self, amount):
                """
                Inflict damage on the character.
                """
                self._current_hp = max(0, self._current_hp - amount)
                self.save()

    def heal(self, amount):
                """
                Heal the character by the specified amount.
                """
                self._current_hp = min(self._current_hp + amount, self._max_hp)
                self.save()
    def spend_luck(self):
                if self.current_luck > 0:
                 self.current_luck -= 1
                self.save()
                return True

    def gain_luck(self, amount):
                self.current_luck = min(self.current_luck + amount, self.luck)
                self.save()
                return self.current_luck

    def add_reputation(self, amount):
                """
                Add reputation points and update rep level if necessary.
                """
                self.reputation_points += amount
                self.update_rep()
                self.save()

    def update_rep(self):
                """
                Update the rep level based on reputation points.
                """
                new_rep = min(self.reputation_points // 100, 10)
                if new_rep != self.rep:
                 self.rep = new_rep
                 self.save()

    def refresh_from_db(self, using=None, fields=None):
        """
        Reload field values from the database.
        """
        super().refresh_from_db(using=using, fields=fields)

    def save(self, *args, **kwargs):
        skip_recalculation = kwargs.pop('skip_recalculation', False)
        if not skip_recalculation:
            self.recalculate_derived_stats()
        if self.character:
            # Check if this character is already associated with another sheet
            existing_sheet = CharacterSheet.objects.filter(character=self.character).exclude(id=self.id).first()
            if existing_sheet:
                # If so, remove the association from the old sheet
                existing_sheet.character = None
                existing_sheet.save(skip_recalculation=True)
        super().save(*args, **kwargs)

    def recalculate_derived_stats(self):
        self._max_hp = 10 + (5 * ((self.body + self.willpower) // 2))
        self.death_save = self.body
        self.serious_wounds = self.body
        
        total_cyberware_hl = self.calculate_total_cyberware_hl()
        
        # Calculate current humanity
        self.humanity = max(0, self.empathy * 10 - total_cyberware_hl)
        
        # Ensure _current_hp doesn't exceed _max_hp
        if self._current_hp > self._max_hp:
            self._current_hp = self._max_hp
        # If _current_hp is 0, set it to _max_hp
        if self._current_hp == 0:
            self._current_hp = self._max_hp
        # Ensure _current_hp is never negative   
        self._current_hp = max(0, self._current_hp)

        # Save without triggering another recalculation
        self.save(skip_recalculation=True)

@property
def max_hp(self):
        return self._max_hp

@max_hp.setter
def max_hp(self, value):
        self._max_hp = value

@property
def current_hp(self):
        return self._current_hp

@current_hp.setter
def current_hp(self, value):
    self._current_hp = max(0, min(value, self.max_hp))

@property
def death_save(self):
        return self.body

@property
def serious_wounds(self):
        return self.body

@property
def rep_level(self):
        """
        Return the current rep level as a string for display.
        """
        return f"{self.rep} level"
