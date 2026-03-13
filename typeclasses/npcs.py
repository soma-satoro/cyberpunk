"""
NPCs

Non-Player Characters that can be generated and roleplayed by staff or player storytellers.
Supports two types: Major (full customization) and Minor (edgerunner-generated, temporary).
"""
from evennia import DefaultCharacter
from evennia.objects.models import ObjectDB
from world.cyberpunk_constants import ROLES, STATS, ROLE_SKILLS, ROLE_SKILL_NAME_MAP
from world.utils.ansi_utils import wrap_ansi
import re
import logging

logger = logging.getLogger('cyberpunk.npc')


def is_npc(obj):
    """Check if an object is an NPC typeclass."""
    if not obj:
        return False
    return obj.is_typeclass("typeclasses.npcs.NPC")


class NPC(DefaultCharacter):
    """
    Non-Player Character that can be created and controlled by staff or storytellers.
    
    Major NPCs: Full customization (chargen, stats, inventory, cyberware, notes).
    Minor NPCs: Edgerunner-generated mooks (gangers, security, etc.), temporary per scene.
    """

    def at_object_creation(self):
        super().at_object_creation()
        # NPC-specific
        self.db.npc_type = "minor"  # "major" or "minor"
        self.db.owner_account_id = None   # Account who created/owns this NPC
        self.db.owner_character_id = None  # Character who created (for display)
        self.db.role = ""
        self.db.improved_skills = []  # Skills raised via +npc/improve
        self.db.equipped_weapon_id = None  # PK of equipped Weapon (for NPCs, no CharacterSheet)
        self.db.selected_language = "None"
        self.db.desc = ""
        
        # No CharacterSheet - use db.* for all stats
        self.db.full_name = ""
        self.db.handle = ""
        self.db.gender = ""
        self.db.age = 0
        self.db.hometown = ""
        self.db.height = 0
        self.db.weight = 0
        self.db.faction = None
        self.db.faction_rep = {}
        
        # Core stats (matching Character)
        for stat in STATS:
            self.attributes.add(stat, 1)
        self.db.current_luck = 1
        self.db.max_hp = 10
        self.db.current_hp = 10
        self.db.humanity = 10
        self.db.humanity_loss = 0
        self.db.total_cyberware_humanity_loss = 0
        self.db.death_save = 1
        self.db.serious_wounds = 1
        
        # Economy - NPCs can have unlimited funds (for fixer missions)
        self.db.eurodollars = 0
        self.db.reputation_points = 0
        self.db.rep = 0
        self.db.notoriety_points = 0
        self.db.notoriety = 0
        
        # Skills - empty dict, populated by chargen
        self.db.skills = {}
        self.db.skill_instances = {}
        
        # Languages (db.languages dict for pose/say/emit)
        self.db.languages = {}
        
        # Notes (same structure as Character)
        self.db.notes = {}
        
        # NPCs have no account; they are controlled via +npc commands by their owner

    @property
    def character_sheet(self):
        """NPCs don't use CharacterSheet - return None."""
        return None

    def get_attribute(self, attr_name):
        """Get stat or skill value."""
        key = attr_name.lower().replace(' ', '_')
        if key in (self.db.skills or {}):
            return self.db.skills.get(key, 0)
        return self.attributes.get(key, 0)

    def set_attribute(self, attr_name, value):
        """Set stat or skill value."""
        key = attr_name.lower().replace(' ', '_')
        if key in (self.db.skills or {}):
            skills = dict(self.db.skills or {})
            skills[key] = int(value)
            self.db.skills = skills
        else:
            self.attributes.add(key, int(value))

    def get_skill(self, skill_name):
        """Get skill value by name."""
        key = skill_name.lower().replace(' ', '_')
        return (self.db.skills or {}).get(key, 0)

    def set_skill(self, skill_name, value):
        """Set skill value."""
        key = skill_name.lower().replace(' ', '_')
        skills = dict(self.db.skills or {})
        skills[key] = int(value)
        self.db.skills = skills

    def recalculate_derived_stats(self):
        """Recalculate max_hp, death_save, serious_wounds, humanity."""
        bod = self.attributes.get("body", 1)
        wil = self.attributes.get("willpower", 1)
        self.db.max_hp = 10 + (5 * ((bod + wil) // 2))
        self.db.current_hp = min(max(0, self.db.current_hp), self.db.max_hp)
        if self.db.current_hp == 0:
            self.db.current_hp = self.db.max_hp
        self.db.death_save = bod
        self.db.serious_wounds = bod
        self.calculate_humanity()

    def calculate_humanity(self):
        """Calculate humanity from empathy and cyberware."""
        from world.inventory.models import CyberwareInstance
        total_hl = 0
        char_pk = getattr(self, 'pk', None)
        if char_pk:
            instances = CyberwareInstance.objects.filter(
                character_object_id=char_pk, installed=True
            )
            total_hl = sum(cw.cyberware.humanity_loss for cw in instances)
        self.db.total_cyberware_humanity_loss = total_hl
        empathy = self.attributes.get("empathy", 1)
        trauma = getattr(self.db, "trauma_humanity_loss", 0) or 0
        self.db.humanity = max(0, empathy * 10 - total_hl - trauma)

    def add_language(self, language_name, level):
        """Add a language to the NPC. Required for Edgerunner chargen."""
        if not self.db.languages:
            self.db.languages = {}
        langs = dict(self.db.languages)
        langs[language_name] = int(level)
        self.db.languages = langs

    def get_languages(self):
        """Return list of language names the NPC knows."""
        langs = self.db.languages or {}
        return [k for k, v in langs.items() if v and v > 0]

    def get_speaking_language(self):
        """Get currently selected speaking language."""
        lang = self.attributes.get("selected_language", "None")
        if not lang or str(lang) == "None":
            return None
        return str(lang)

    def set_speaking_language(self, language):
        """Set speaking language. Must be one they know, or None."""
        if language is None:
            self.attributes.add("selected_language", "None")
            return
        langs = self.get_languages()
        for known in langs:
            if known.lower() == str(language).lower():
                self.attributes.add("selected_language", known)
                return
        raise ValueError(f"NPC doesn't know the language '{language}'.")

    def prepare_say(self, speech, viewer=None, language_only=False, skip_english=False):
        """Prepare say/pose/emit for language-tagged speech (matches Character)."""
        display_name = self.get_display_name(viewer or self)
        is_speaker = viewer is None or viewer == self
        if speech.strip().startswith("~"):
            text = speech.strip()[1:].strip()
            language = self.get_speaking_language()
            if not language:
                language = None
                text = speech
        else:
            language = None
            text = speech
        if language is None or (language and language.lower() == "english" and not skip_english):
            if language_only:
                return (text, text, text, None)
            if is_speaker:
                return (f'You say, "{text}"', f'{display_name} says, "{text}"', f'{display_name} says, "{text}"', None)
            return (f'You say, "{text}"', f'{display_name} says, "{text}"', f'{display_name} says, "{text}"', None)
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
        return (msg_self, msg_understand, msg_not_understand, language)

    def get_equipped_weapon(self):
        """Get the currently equipped weapon model or None."""
        wid = self.db.equipped_weapon_id
        if not wid:
            return None
        from world.inventory.models import Weapon
        try:
            return Weapon.objects.get(pk=wid)
        except Weapon.DoesNotExist:
            return None

    def set_equipped_weapon(self, weapon):
        """Set equipped weapon. Pass Weapon model or None."""
        if weapon is None:
            self.db.equipped_weapon_id = None
        else:
            self.db.equipped_weapon_id = weapon.pk

    def return_appearance(self, looker, **kwargs):
        """Format appearance when looked at."""
        if not looker:
            return ""
        desc = self.db.desc
        string = f"|c{self.get_display_name(looker)}|n\n"
        if desc:
            desc = desc.replace('%t', '|t').replace('|-', '|t')
            paragraphs = desc.split('%r')
            formatted_paragraphs = []
            for p in paragraphs:
                if not p.strip():
                    formatted_paragraphs.append('')
                    continue
                lines = p.split('|t')
                indented_lines = [line.strip() for line in lines]
                indented_text = '\n    '.join(indented_lines)
                wrapped_lines = [wrap_ansi(line, width=78) for line in indented_text.split('\n')]
                formatted_paragraphs.append('\n'.join(wrapped_lines))
            joined = '\n'.join(formatted_paragraphs)
            joined = re.sub(r'\n{3,}', '\n\n', joined)
            string += joined + "\n"
        return string
