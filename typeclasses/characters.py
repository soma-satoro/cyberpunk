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
class Character(DefaultCharacter):
    def at_object_creation(self):
        super().at_object_creation()
        self.db.combat_position = 0  # Default starting position
        self.cmdset.add("commands.default_cmdsets.CharacterCmdSet", permanent=True)
        
        # Initialize character attributes directly on the typeclass
        # Leave full_name empty - chargen will set it. Avoids false "already initialized" prompt.
        self.db.full_name = ""
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
        self.db.notoriety_points = 0
        self.db.notoriety = 0
        
        # Improvement Points (IP)
        self.db.improvement_points = 0
        self.db.ip_spent = 0
        self.db.ip_staff_awarded = 0
        self.db.ip_log = []
        self.db.ip_last_purchase = None  # For refund: {stat, from_level, to_level, cost, timestamp}
        
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

        # Do NOT create character sheet here - it is created when the player runs chargen
        # for the first time. This prevents new characters from being prompted to reset.

        # New characters start unapproved until staff approve them
        self.tags.add("unapproved", category="approval")
        
        # Initialize notification settings
        self.db.notifications = {
            "say": True,
            "pose": True,
            "emit": True,
            "page": True,
            "whisper": True,
            "new_page": True,
        }
        
        # Initialize notes storage (list of dicts: title, category, text, approved, etc.)
        self.db.notes = []

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

    def _subscribe_to_default_channels(self):
        """Subscribe this character's account to Public and Newbie channels."""
        if not self.account:
            return
        try:
            from evennia.comms.models import ChannelDB
            for channel_name in ("Public", "Newbie"):
                channels = ChannelDB.objects.channel_search(channel_name)
                if channels:
                    channel = channels[0]
                    if not channel.has_connection(self.account):
                        channel.connect(self.account)
                        logger.info(f"Subscribed {self.account.username} to {channel_name} channel")
        except Exception as e:
            logger.error(f"Error subscribing to default channels: {e}")

    def display_login_notifications(self):
        """Display notifications upon login."""
        from evennia.utils import logger
        logger.log_info(f"About to display login notifications for {self.key}")
        
        if self.account:
            # Check for first login notification
            if not self.attributes.has("first_login_complete"):
                # Subscribe new character's account to Public and Newbie channels
                self._subscribe_to_default_channels()
                
                self.msg("|g=========================== Welcome to Night City! ===========================|n")
                self.msg("|wYou have been automatically subscribed to the |cPublic|w and |cNewbie|w channels.|n")
                self.msg("|wYou can talk on Public using |cpublic <message>|w and on Newbie using |cnew <message>|w, for example:|n")
                self.msg("|c   public Hello everyone!|n")
                self.msg("|c   new I'm new here - any tips?|n")
                self.msg("|wYou can see all your available channels with the |cchannel/list|w command.|n")
                self.msg("|wFor help getting started, type |chelp|w or ask questions on the Newbie channel.|n")
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

    def get_display_name(self, looker, **kwargs):
        """Override: in Elflines rooms, show elfname instead of meat-world name."""
        if self.location and getattr(self.location, 'is_elflines_room', False):
            from world.elflines.services import get_elo_sheet_for_character
            sheet = get_elo_sheet_for_character(self)
            if sheet and sheet.elfname and sheet.elfname.strip():
                return sheet.elfname
        # Fallback: gradient_name (from +gradient) or default
        gradient = self.attributes.get('gradient_name', default=None)
        if gradient:
            return gradient
        return super().get_display_name(looker, **kwargs)

    def get_attribute(self, attr_name):
        """Get a character attribute value. Stats always come from attributes, never skills."""
        from world.cyberpunk_constants import STATS
        if attr_name in STATS:
            return self.attributes.get(attr_name)
        if attr_name in (self.db.skills or {}):
            return self.db.skills.get(attr_name, 0)
        return self.attributes.get(attr_name)
    
    def set_attribute(self, attr_name, value):
        """Set a character attribute value. Stats always go to attributes, never skills."""
        from world.cyberpunk_constants import STATS
        if attr_name in STATS:
            self.attributes.add(attr_name, value)
            return
        if attr_name in (self.db.skills or {}):
            skills = self.db.skills
            skills[attr_name] = value
            self.db.skills = skills
        else:
            self.attributes.add(attr_name, value)
    
    def get_skill(self, skill_name):
        """Get a skill value by name."""
        skill_key = skill_name.lower().replace(' ', '_')
        # Medtech: Surgery and Medical Tech are derived from Medicine specialties
        if (self.db.role or "").strip() == "Medtech":
            if skill_key == "surgery":
                from world.chargen_constants import get_medicine_surgery_skill
                return get_medicine_surgery_skill(self.db.medicine_surgery)
            if skill_key == "medical_tech":
                from world.chargen_constants import get_medical_tech_skill
                return get_medical_tech_skill(self.db.medicine_pharma, self.db.medicine_cryo)
        return self.db.skills.get(skill_key, 0)
    
    def get_medicine_specialties(self):
        """Return (surgery, pharma, cryo) allocation for Medtech."""
        return (
            getattr(self.db, 'medicine_surgery', 0) or 0,
            getattr(self.db, 'medicine_pharma', 0) or 0,
            getattr(self.db, 'medicine_cryo', 0) or 0
        )
    
    def set_medicine_specialty(self, specialty, value):
        """Set a Medicine specialty (surgery, pharma, or cryo). Medtech only."""
        key = f"medicine_{specialty}"
        setattr(self.db, key, int(value))

    def get_maker_specialties(self):
        """Return (field, upgrade, fabrication, invention) allocation for Tech."""
        return (
            getattr(self.db, 'maker_field', 0) or 0,
            getattr(self.db, 'maker_upgrade', 0) or 0,
            getattr(self.db, 'maker_fabrication', 0) or 0,
            getattr(self.db, 'maker_invention', 0) or 0,
        )

    def set_maker_specialty(self, specialty, value):
        """Set a Maker specialty (field, upgrade, fabrication, invention). Tech only."""
        key = f"maker_{specialty}"
        setattr(self.db, key, int(value))
    
    def set_skill(self, skill_name, value):
        """Set a skill value. Rejects core stat names (they belong in db.<stat>)."""
        from world.cyberpunk_constants import STATS
        skill_key = skill_name.lower().replace(' ', '_')
        if skill_key in STATS:
            # Don't allow stats to be stored in skills - would cause double-counting
            return
        skills = self.db.skills or {}
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
        trauma_loss = getattr(self.db, "trauma_humanity_loss", 0) or 0

        # Base humanity is empathy * 10
        base_humanity = self.db.empathy * 10

        # Current humanity is base minus losses (includes trauma from removed cyberware)
        self.db.humanity = max(0, base_humanity - total_humanity_loss - trauma_loss)
        
        # Only update empathy if it's been significantly reduced
        if base_humanity <= total_humanity_loss + trauma_loss:
            self.db.empathy = max(1, self.db.humanity // 10)
        
        # Store total loss for reference
        self.db.total_cyberware_humanity_loss = total_humanity_loss
    
    def calculate_cyberware_humanity_loss(self):
        """Calculate total humanity loss from installed cyberware."""
        from django.apps import apps
        CyberwareInstance = apps.get_model('inventory', 'CyberwareInstance')

        # Use pk to avoid "Model instances passed to related filters must be saved" error
        char_pk = getattr(self, 'pk', None) or getattr(self, 'id', None)

        if char_pk is not None:
            installed_cyberware = CyberwareInstance.objects.filter(
                character_object_id=char_pk, installed=True
            )
        else:
            installed_cyberware = CyberwareInstance.objects.none()

        if not installed_cyberware.exists():
            try:
                character_sheet = self.character_sheet
                if character_sheet and getattr(character_sheet, 'pk', None):
                    installed_cyberware = CyberwareInstance.objects.filter(
                        character_sheet_id=character_sheet.pk, installed=True
                    )
            except Exception:
                pass

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
                for cl in self.character_sheet.sheet_language_proficiencies.all()]

    def knows_language(self, language_name):
        if not self.character_sheet:
            return False
        return self.character_sheet.sheet_language_proficiencies.filter(
            language__name__iexact=language_name
        ).exists()

    # Language mixin methods for pose/emit/say system (binary: knows language or not)
    def get_languages(self):
        """Return list of language names the character knows. Binary check for pose/emit/say.
        Merges character_sheet (CharacterLanguage) and db.languages for chargen compatibility."""
        result = {}
        if self.character_sheet:
            for cl in self.character_sheet.sheet_language_proficiencies.all():
                if cl.level > 0:
                    result[cl.language.name] = True
        if hasattr(self.db, "languages") and self.db.languages:
            for name, level in self.db.languages.items():
                if level > 0:
                    result[name] = True
        return list(result.keys())

    def get_speaking_language(self):
        """Get the character's currently selected speaking language."""
        lang = self.attributes.get("selected_language", "None")
        if not lang or str(lang) == "None":
            return None
        return str(lang)

    def set_speaking_language(self, language):
        """Set the character's speaking language. Must be a language they know, or None."""
        if language is None:
            self.attributes.add("selected_language", "None")
            return
        languages = self.get_languages()
        for known in languages:
            if known.lower() == str(language).lower():
                self.attributes.add("selected_language", known)
                return
        raise ValueError(f"You don't know the language '{language}'.")

    def prepare_say(
        self, speech, viewer=None, language_only=False, skip_english=False
    ):
        """
        Prepare say/pose/emit messages for language-tagged speech.
        Speech with leading ~ is in the speaker's set language.
        Returns (msg_self, msg_understand, msg_not_understand, language).
        """
        display_name = self.get_display_name(viewer or self)
        is_speaker = viewer is None or viewer == self

        # Check for language-tagged speech (leading ~)
        if speech.strip().startswith("~"):
            text = speech.strip()[1:].strip()
            language = self.get_speaking_language()
            if not language:
                # No language set - treat as plain text
                language = None
                text = speech
        else:
            language = None
            text = speech

        # English / untagged - everyone understands. skip_english=True means process non-English languages properly.
        if language is None or (language and language.lower() == "english" and not skip_english):
            if language_only:
                return (text, text, text, None)
            if is_speaker:
                return (f'You say, "{text}"', f'{display_name} says, "{text}"', f'{display_name} says, "{text}"', None)
            return (f'You say, "{text}"', f'{display_name} says, "{text}"', f'{display_name} says, "{text}"', None)

        # Language-tagged: check if viewer understands
        understands = is_speaker
        if viewer and viewer != self:
            understands = language in viewer.get_languages()

        garbled = f"[speaks in {language}]"
        if language_only:
            msg_understand = text
            msg_not_understand = garbled
            msg_self = text
        else:
            msg_understand = f'{display_name} says, "{text}"'
            msg_not_understand = f'{display_name} says, "{garbled}"'
            msg_self = f'You say, "{text}"' if is_speaker else msg_understand

        if understands:
            return (msg_self, msg_understand, msg_not_understand, language)
        return (msg_self, msg_understand, msg_not_understand, language)

    def record_scene_activity(self):
        """Optional hook for scene/activity tracking. No-op for Cyberpunk by default."""
        pass

    def at_post_move(self, source_location, **kwargs):
        super().at_post_move(source_location, **kwargs)
        if self.character_sheet:
            self.character_sheet.refresh_from_db()

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        """When receiving a voucher, remove from our inventory any items that duplicate voucher contents."""
        super().at_object_receive(moved_obj, source_location, **kwargs)
        from typeclasses.vouchers import Voucher
        if moved_obj and moved_obj.is_typeclass(Voucher):
            from world.voucher.utils import remove_voucher_duplicates_from_inventory
            remove_voucher_duplicates_from_inventory(self, moved_obj)

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

        # Worn armor - visible when looking at the character
        if hasattr(self, 'character_sheet') and self.character_sheet:
            eqarmor = getattr(self.character_sheet, 'eqarmor', None)
            if eqarmor:
                string += f"\n|yThey are wearing {eqarmor.name}.|n\n"

        # Netrun indicator: show when character is jacked in (body vulnerable to attack)
        netrun_state = getattr(self.db, "netrun_state", None) or {}
        if netrun_state.get("active"):
            string += "\n|yThey sit motionless, chrome flickering in their eyes - jacked into the NET.|n\n"
            string += "|r(Their body is vulnerable to attack!)|n\n"

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
        self.db.notoriety_points = getattr(sheet, 'notoriety_points', 0) or 0
        self.db.notoriety = getattr(sheet, 'notoriety', 0) or 0
        
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
                                  'body', 'empathy', 'age', 'height', 'weight',
                                  'humanity', 'humanity_loss', 'total_cyberware_humanity_loss',
                                  'trauma_humanity_loss', 'death_save', 'serious_wounds',
                                  'notoriety_points', 'notoriety', 'is_complete',
                                  'unarmed_damage_dice', 'unarmed_damage_die_type', 'has_cyberarm']):
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
        if hasattr(sheet, 'notoriety_points'):
            sheet.notoriety_points = getattr(self.db, 'notoriety_points', 0) or 0
        if hasattr(sheet, 'notoriety'):
            sheet.notoriety = getattr(self.db, 'notoriety', 0) or 0
        
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
        """Brawling damage scales with BODY; Cyberarm grants minimum 2d6 (CPR p.169)."""
        body = getattr(self.db, 'body', 1) or 1
        has_cyberarm = getattr(self.db, 'has_cyberarm', False) or False
        if body >= 11:
            return 4
        elif body >= 7:
            return 3
        elif body >= 5 or (body >= 1 and has_cyberarm):
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
        """Remove a language from the character (db.languages, CharacterSheet, CharacterLanguage)."""
        # Update db.languages
        if hasattr(self.db, 'languages') and self.db.languages and language_name in self.db.languages:
            languages = dict(self.db.languages)
            del languages[language_name]
            self.db.languages = languages
        # Remove from CharacterSheet (and CharacterLanguage)
        if self.character_sheet and hasattr(self.character_sheet, 'remove_language'):
            try:
                self.character_sheet.remove_language(language_name)
            except Exception:
                pass
        # Also delete CharacterLanguage records (handles both character and sheet links)
        from django.db.models import Q
        from evennia.utils import logger as ev_logger
        try:
            language = Language.objects.get(name__iexact=language_name)
            q = Q(language=language)
            char_pk = getattr(self, 'pk', None) or getattr(self, 'id', None)
            sheet_pk = getattr(self.character_sheet, 'pk', None) if self.character_sheet else None
            if char_pk is not None or sheet_pk is not None:
                if char_pk is not None and sheet_pk is not None:
                    q &= Q(character_id=char_pk) | Q(character_sheet_id=sheet_pk)
                elif char_pk is not None:
                    q &= Q(character_id=char_pk)
                else:
                    q &= Q(character_sheet_id=sheet_pk)
                CharacterLanguage.objects.filter(q).delete()
                ev_logger.log_info(f"Removed language {language_name} from character")
        except Language.DoesNotExist:
            pass

    def update_language_level(self, language_name, new_level):
        from django.db.models import Q
        try:
            language = Language.objects.get(name=language_name)
            char_pk = getattr(self, 'pk', None) or getattr(self, 'id', None)
            sheet_pk = getattr(self.character_sheet, 'pk', None) if self.character_sheet else None
            q = Q(language=language)
            if char_pk is not None or sheet_pk is not None:
                if char_pk is not None and sheet_pk is not None:
                    q &= Q(character_id=char_pk) | Q(character_sheet_id=sheet_pk)
                elif char_pk is not None:
                    q &= Q(character_id=char_pk)
                else:
                    q &= Q(character_sheet_id=sheet_pk)
            else:
                return
            char_lang = CharacterLanguage.objects.filter(q).first()
            if char_lang:
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
        """Calculate spent character points.
        Role ability: first 4 points are free (not deducted from skill pool).
        Skills with instances (e.g. Martial Arts (Krav Maga)): count instances only, not base.
        """
        # Stats - use (x or 0) to handle None from uninitialized attributes
        stat_points = sum([
            self.db.intelligence or 0, self.db.reflexes or 0, self.db.dexterity or 0,
            self.db.technology or 0, self.db.cool or 0, self.db.willpower or 0,
            self.db.luck or 0, self.db.move or 0, self.db.body or 0, self.db.empathy or 0
        ])

        # Skills - get from skills dictionary; only count known skills (exclude junk from migration)
        from world.chargen_constants import ROLE_ABILITY_FREE_POINTS, ROLE_ABILITY_SKILLS
        from world.cyberpunk_constants import STATS
        from world.utils.calculation_utils import SKILL_MAPPING
        core_stats = frozenset(STATS)
        known_skills = frozenset(SKILL_MAPPING.values())
        skills = dict(self.db.skills or {})
        role = (self.db.role or "").strip()
        # Remove stats, non-skill keys, and role specialty allocations (they're not skills)
        medtech_specialty_keys = frozenset(("medicine_surgery", "medicine_pharma", "medicine_cryo"))
        maker_specialty_keys = frozenset(("maker_field", "maker_upgrade", "maker_fabrication", "maker_invention"))
        to_remove = [
            k for k in skills
            if k in core_stats or k not in known_skills
            or (role == "Medtech" and k in medtech_specialty_keys)
            or (role == "Tech" and k in maker_specialty_keys)
        ]
        if to_remove:
            for k in to_remove:
                del skills[k]
            self.db.skills = skills
        skills = {k: v for k, v in skills.items() if k in known_skills and k not in core_stats}
        double_cost_skills = ['autofire', 'martial_arts', 'pilot_air',
                             'heavy_weapons', 'demolitions', 'electronics', 'paramedic']
        # Base skills that have instances: don't count base (instance counts instead)
        skills_with_instances = set()
        if self.db.skill_instances:
            for skill_instance in self.db.skill_instances:
                if "(" in skill_instance:
                    skills_with_instances.add(skill_instance.split("(")[0])
        skill_points = 0
        role_ability_skill = ROLE_ABILITY_SKILLS.get(role) if role else None
        # Medtech: Surgery and Medical Tech are derived from Medicine specialties (medicine_surgery,
        # medicine_pharma, medicine_cryo). Never count paramedic, surgery, or medical_tech.
        medtech_derived_skills = frozenset(("paramedic", "surgery", "medical_tech"))
        for skill, value in skills.items():
            if skill in skills_with_instances:
                continue  # Instance counts instead; avoid double-count
            if role == "Medtech" and skill in medtech_derived_skills:
                continue  # Derived from Medicine allocation; avoid double-count
            try:
                val = int(value) if value is not None else 0
            except (TypeError, ValueError):
                val = 0
            multiplier = 2 if skill in double_cost_skills else 1
            if skill == role_ability_skill:
                billable = max(0, val - ROLE_ABILITY_FREE_POINTS)
                skill_points += billable * multiplier
            else:
                skill_points += val * multiplier

        # Skill instances - get from skill_instances dictionary
        if self.db.skill_instances:
            for skill_instance, value in self.db.skill_instances.items():
                if "(" not in skill_instance:
                    continue
                base_skill = skill_instance.split("(")[0]
                try:
                    val = int(value) if value is not None else 0
                except (TypeError, ValueError):
                    val = 0
                multiplier = 2 if base_skill in double_cost_skills else 1
                skill_points += val * multiplier

        # Languages: Streetslang 4 (automatic) and lifepath language are free
        from world.utils.calculation_utils import calculate_language_skill_points
        lifepath_lang = ""
        lp = getattr(self.db, "lifepath", None) or {}
        if isinstance(lp, dict):
            lifepath_lang = lp.get("cultural_language_picked", "") or ""
        # Fallback: lifepath may be on character_sheet (synced from account) or account when lifepath ran pre-puppet
        if not lifepath_lang and hasattr(self, "character_sheet") and self.character_sheet:
            lifepath_lang = (getattr(self.character_sheet, "lifepath_language", None) or "").strip()
        if not lifepath_lang and hasattr(self, "account") and self.account:
            acc_lp = getattr(self.account.db, "lifepath", None) or {}
            if isinstance(acc_lp, dict):
                lifepath_lang = acc_lp.get("cultural_language_picked", "") or ""
        lang_items = list(self.languages.items())
        language_points = calculate_language_skill_points(lang_items, lifepath_language=lifepath_lang)

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
        """Get remaining character points.
        Edgerunner: stats pre-assigned from table (0 remaining), skills use 86 pool.
        Complete Package: 62 stat points, 86 skill points (per book).
        """
        from world.chargen_constants import COMPLETE_PACKAGE_SKILL_POOL, EDGERUNNER_SKILL_POOL
        stat_points_spent, skill_points_spent = self.calculate_spent_points()
        method = (self.db.chargen_method or "").strip().lower()
        if method == "edgerunner":
            remaining_stat_points = 0
            remaining_skill_points = max(0, EDGERUNNER_SKILL_POOL - skill_points_spent)
        else:
            remaining_stat_points = max(0, 62 - stat_points_spent)
            remaining_skill_points = max(0, COMPLETE_PACKAGE_SKILL_POOL - skill_points_spent)
        return remaining_stat_points, remaining_skill_points

