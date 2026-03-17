import random
import re
from evennia import Command, logger, search_object, default_cmds
from typeclasses.rental import CharacterSheetMoneyService
from world.utils.character_utils import get_full_attribute_name, ALL_ATTRIBUTES, TOPSHEET_MAPPING, is_staff
from world.list_data import STAT_DESCRIPTIONS, SKILL_TO_STAT_LOOKUP, SKILL_DISPLAY_OVERRIDES
from world.utils.calculation_utils import get_remaining_points, STAT_MAPPING, SKILL_MAPPING
from typeclasses.chargen import ChargenRoom
from evennia.utils import evtable
from evennia.utils.utils import list_to_string, inherits_from
from evennia.utils.create import create_object
from evennia.utils import create
from world.cyberpunk_sheets.models import CharacterSheet
from world.languages.models import Language
from evennia.utils.evtable import EvTable
from world.utils.formatting import footer, sheet_header, sheet_section
from world.utils.ansi_utils import wrap_ansi, wrap_labeled_comma_list
from world.inventory.models import Weapon, Armor, Gear, Inventory
from evennia.commands.default.muxcommand import MuxCommand
from world.lifepath_dictionary import CULTURAL_ORIGINS, PERSONALITIES, CLOTHING_STYLES, HAIRSTYLES, AFFECTATIONS, MOTIVATIONS, LIFE_GOALS, ROLE_SPECIFIC_LIFEPATHS, VALUED_PERSON, VALUED_POSSESSION, FAMILY_BACKGROUND, ENVIRONMENT, FAMILY_CRISIS
from world.utils.difficulty_values import parse_dv
from math import ceil

class CmdSheet(MuxCommand):
    """
    Show character sheet or lifepath details

    Usage:
      sheet
      sheet/lifepath
      sheet/elo
      sheet <character name>

    Switches:
      lifepath - Show detailed lifepath information
      elo      - Elflines Online character generation (stats, skills, elfname, equipment)

    Staff members can view the character sheet of other characters by specifying their name.
    """

    key = "sheet"
    aliases = ["char", "character"]
    lock = "cmd:all()"
    help_category = "Character"

    def safe_get_attr(self, obj, attr):
        """Safely get an attribute value, returning 'N/A' if it doesn't exist."""
        if hasattr(obj, "attributes") and obj.attributes.has(attr):
            return obj.attributes.get(attr, 'N/A')
        return getattr(obj, attr, 'N/A')

    def _safe_fmt(self, val, default=''):
        """Return value for formatting; use default if value is None to avoid TypeErrors."""
        return val if val is not None else default

    def parse(self):
        """Parse command arguments."""
        super().parse()

        if not self.args or self.args in self.switches:
            self.target_name = None
        else:
            self.target_name = self.args.strip()

    def func(self):
        if "lifepath" in self.switches:
            self.view_lifepath()
        elif "elo" in self.switches:
            self.view_elo_chargen()
        else:
            self.view_sheet()

    def get_target_character(self):
        """Get the target character based on user input."""
        caller = self.caller
        
        if not self.target_name:
            # Resolve account -> character when viewing own sheet (caller may be account in some session modes)
            if not inherits_from(caller, "typeclasses.characters.Character"):
                if hasattr(caller, "character") and caller.character:
                    return caller.character
                if hasattr(caller, "characters") and caller.characters:
                    chars = list(caller.characters) if not callable(caller.characters) else list(caller.characters())
                    if chars:
                        return chars[0]
            return caller
        
        # Check if the caller has staff permissions
        if not is_staff(caller):
            caller.msg("|rYou don't have permission to view other character sheets.|n")
            return None
        
        # Search for the target character
        target = caller.search(self.target_name, global_search=True)
        if not target:
            # caller.search already sends a message if no match found
            return None
            
        return target

    def view_elo_chargen(self):
        """Launch Elflines Online character generation EvMenu."""
        from world.elflines.chargen_menu import start_elo_chargen
        start_elo_chargen(self.caller)

    def view_lifepath(self):
        target = self.get_target_character()
        if not target:
            return

        # Check for new lifepath format (db.lifepath dict with cultural_region, friends, etc.)
        lp = target.db.lifepath or {}
        if lp.get("cultural_region") or lp.get("friends") is not None or lp.get("enemies") is not None:
            from world.lifepath import format_lifepath
            display_name = getattr(target.db, 'full_name', None) or target.key
            sheet = getattr(target, 'character_sheet', None)
            if sheet and getattr(sheet, 'full_name', None):
                display_name = sheet.full_name
            output = sheet_header(f"Lifepath for {display_name}", width=80)
            output += format_lifepath(lp) + "\n"
            output += footer(width=80, fillchar="-")
            self.caller.msg(output)
            return

        # Legacy: lifepath data on CharacterSheet
        sheet = getattr(target, 'character_sheet', None)
        if not sheet:
            self.caller.msg("No character sheet found. Create one with the chargen command first.")
            return

        width = 80
        output = ""

        # Main header - use sheet full_name or fall back to target
        display_name = getattr(sheet, 'full_name', None) or getattr(target.db, 'full_name', None) or target.key
        output += sheet_header(f"Lifepath for {display_name}", width=width)

        def get_sheet_value(field):
            val = getattr(sheet, field, None)
            return (val or "").strip() or "Not set"

        # Present Section
        output += sheet_section("Present", width=width)
        present_fields = [
            ("Cultural Origin", "cultural_origin"),
            ("Personality", "personality"),
            ("Clothing Style", "clothing_style"),
            ("Hairstyle", "hairstyle"),
            ("Affectation", "affectation"),
            ("Motivation", "motivation"),
            ("Life Goal", "life_goal"),
            ("Most Valued Person", "valued_person"),
        ]
        for title, field in present_fields:
            value = get_sheet_value(field)
            output += self._sheet_field(title, value, width)
        output += "\n"

        # Past Section
        output += sheet_section("Past", width=width)
        past_fields = [
            ("Valued Possession", "valued_possession"),
            ("Family Background", "family_background"),
            ("Origin Environment", "environment"),
            ("Family Crisis", "family_crisis")
        ]
        for title, field in past_fields:
            value = get_sheet_value(field)
            output += self._sheet_field(title, value, width)
        output += "\n"

        # Role Section - read role from sheet
        role = getattr(sheet, 'role', None) or ""
        if role:
            output += sheet_section(f"Role: {role}", width=width)
            role_specific_fields = {
                "Rockerboy": [
                    "what_kind_of_rockerboy_are_you",
                    "whos_gunning_for_you_your_group",
                    "where_do_you_perform"
                ],
                "Solo": [
                    "what_kind_of_solo_are_you",
                    "whats_your_moral_compass_like",
                    "whos_gunning_for_you",
                    "whats_your_operational_territory"
                ],
                "Netrunner": [
                    "what_kind_of_runner_are_you",
                    "who_are_some_of_your_other_clients",
                    "where_do_you_get_your_programs",
                    "whos_gunning_for_you"
                ],
                "Tech": [
                    "what_kind_of_tech_are_you",
                    "whats_your_workspace_like",
                    "who_are_your_main_clients",
                    "where_do_you_get_your_supplies"
                ],
                "Medtech": [
                    "what_kind_of_medtech_are_you",
                    "who_are_your_main_clients",
                    "where_do_you_get_your_supplies"
                ],
                "Media": [
                    "what_kind_of_media_are_you",
                    "how_does_your_work_reach_the_public",
                    "how_ethical_are_you",
                    "what_types_of_stories_do_you_want_to_tell"
                ],
                "Exec": [
                    "what_kind_of_corp_do_you_work_for",
                    "what_division_do_you_work_in",
                    "how_good_bad_is_your_corp",
                    "where_is_your_corp_based",
                    "current_state_with_your_boss"
                ],
                "Lawman": [
                    "what_is_your_position_on_the_force",
                    "how_wide_is_your_groups_jurisdiction",
                    "how_corrupt_is_your_group",
                    "who_is_your_groups_major_target"
                ],
                "Fixer": [
                    "what_kind_of_fixer_are_you",
                    "who_are_your_side_clients",
                    "whos_gunning_for_you"
                ],
                "Nomad": [
                    "how_big_is_your_pack",
                    "what_do_you_do_for_your_pack",
                    "whats_your_packs_overall_philosophy",
                    "is_your_pack_based_on_land_air_or_sea"
                ]
            }
            for field in role_specific_fields.get(role, []):
                value = get_sheet_value(field)
                if value and value != "Not set":
                    title = field.replace('_', ' ').title()
                    output += self._sheet_field(title, value, width)
            output += "\n"

        output += footer(width=width, fillchar="-")
        
        # Send the formatted output to the caller
        self.caller.msg(output)

    def _sheet_field(self, title, value, width=80, label_width=20):
        """Format a label-value pair like the main sheet (|yLabel:|n value)."""
        wrapped_value = wrap_ansi(value, width=width - label_width - 1)
        value_lines = wrapped_value.split('\n')
        output = ""
        label = f"{title}:"
        for i, value_line in enumerate(value_lines):
            if i == 0:
                output += f"|y{label:<{label_width}}|n {value_line}\n"
            else:
                output += f"{' ' * label_width} {value_line}\n"
        return output
    
    def view_sheet(self):
        # Check for voucher first (anyone can +sheet a voucher they have or that's in the room)
        if self.target_name:
            from commands.voucher_commands import find_voucher
            v = find_voucher(self.caller, self.target_name, quiet=True)
            if v and (v.location == self.caller or v.location == self.caller.location):
                self.caller.msg(v.format_sheet())
                return

        target = self.get_target_character()
        if not target:
            return

        # New players without a character sheet should be directed to chargen
        sheet = getattr(target, 'character_sheet', None) if hasattr(target, 'character_sheet') else None
        if not sheet:
            # Fallback: find sheet by character relation (fixes chargen->sheet link if character_sheet_id wasn't set)
            target_pk = getattr(target, 'pk', None) or getattr(target, 'id', None)
            if target_pk:
                sheet = CharacterSheet.objects.filter(character_id=target_pk).first()
                if sheet:
                    target.db.character_sheet_id = sheet.id
        if not sheet:
            if target == self.caller:
                self.caller.msg(
                    "You don't have a character sheet yet. Proceed to the chargen room to create your character."
                )
            else:
                self.caller.msg(f"{target.name} doesn't have a character sheet yet.")
            return

        # Recalculate humanity from cyberware before display (CharacterSheet is source of truth)
        if sheet:
            sheet.calculate_humanity_loss(quiet=True)
            target.db.humanity = sheet.humanity
            target.db.total_cyberware_humanity_loss = sheet.total_cyberware_humanity_loss
            
        W = 80
        full_name = target.db.full_name or "Unknown"

        # Main header (80 chars, blue/magenta/yellow - no pipes)
        output = sheet_header(f"Character Sheet for {full_name}", width=W)

        # Basic Information
        output += sheet_section("Basic Information", width=W)
        basic_info = [
            ("Full Name:", full_name, "Gender:", target.db.gender or ""),
            ("Handle:", target.db.handle or "", "Age:", target.db.age or 0),
            ("Hometown:", target.db.hometown or "", "Height:", f"{target.db.height or 0} cm"),
            ("Night City Rep:", target.db.rep or 0, "Notoriety:", target.db.notoriety or 0),
            ("Weight:", f"{target.db.weight or 0} kg", "Luck:", f"{target.db.current_luck or 1}/{target.db.luck or 1}"),
        ]
        for row in basic_info:
            v1, v3 = str(row[1])[:18], str(row[3])[:18]
            output += f"|y{row[0]:<18}|n {v1:<18} |y{row[2]:<15}|n {v3:<18}\n"
        # Role on its own line (full width) - includes secondary roles from role abilities
        display_roles = self.get_display_roles(target)
        output += f"|yRole:|n {display_roles}\n"

        # Stats
        output += sheet_section("STATS", width=W)
        stats = [
            ("Intelligence:", target.db.intelligence, "Technology:", target.db.technology, "Move:", target.db.move),
            ("Reflexes:", target.db.reflexes, "Cool:", target.db.cool, "Body:", target.db.body),
            ("Dexterity:", target.db.dexterity, "Willpower:", target.db.willpower, "Empathy:", target.db.empathy)
        ]
        for row in stats:
            output += "".join(
                f"|y{label:<13}|n {(v if v is not None else ''):<8}"
                for label, v in zip(row[::2], row[1::2])
            ) + "\n"

        # Skills (2 columns, 30+1+5=36 per column = 72 total, under 80)
        output += sheet_section("SKILLS", width=W)
        active_skills = self.get_active_skills(target)
        for i in range(0, len(active_skills), 2):
            row = active_skills[i:i+2]
            output += "".join(
                f"|y{(s or ''):<30}|n {(v if v is not None else ''):<5}"
                for s, v in row
            ) + "\n"

        # Role Abilities (primary role + any bought with IP)
        output += sheet_section("Role Abilities", width=W)
        role_abilities = self.get_role_abilities(target)
        if role_abilities:
            for i in range(0, len(role_abilities), 2):
                row = role_abilities[i:i+2]
                output += "".join(
                    f"|y{(s or ''):<30}|n {(v if v is not None else ''):<5}"
                    for s, v in row
                ) + "\n"
        else:
            output += "|wNone|n\n"

        # Derived Stats
        output += sheet_section("Derived Statistics", width=W)
        sheet = target.character_sheet if hasattr(target, 'character_sheet') and target.character_sheet else None
        unarmed_die = getattr(sheet, 'unarmed_damage_die_type', None) if sheet else None
        unarmed_dice = getattr(sheet, 'unarmed_damage_dice', None) if sheet else None
        if unarmed_die is None:
            unarmed_die = getattr(target.db, 'unarmed_damage_die_type', 6)
        if unarmed_dice is None:
            unarmed_dice = getattr(target.db, 'unarmed_damage_dice', 1)
        unarmed_die_display = f"d{unarmed_die}"
        hp_str = f"{target.db.current_hp or 0}/{target.db.max_hp or 0}"
        derived_stats = [
            ("Hit Points:", hp_str, "Death Save:", target.db.death_save),
            ("Serious Wounds:", target.db.serious_wounds, "Humanity:", target.db.humanity),
            ("Unarmed Damage:", unarmed_die_display, "Unarmed Dice:", unarmed_dice)
        ]
        for row in derived_stats:
            output += "".join(
                f"|y{label:<16}|n {(v if v is not None else ''):<18}"
                for label, v in zip(row[::2], row[1::2])
            ) + "\n"
        output += "\n"

        # Equipment (use same inventory source as +inventory: character_sheet.inventory)
        output += sheet_section("Equipment", width=W)
        try:
            from world.inventory.models import Inventory
            inv = None
            sheet = target.character_sheet if hasattr(target, 'character_sheet') and target.character_sheet else None
            if sheet:
                try:
                    inv = sheet.inventory
                except Inventory.DoesNotExist:
                    sheet_pk = getattr(sheet, 'pk', None)
                    if sheet_pk:
                        inv, _ = Inventory.objects.get_or_create(character_id=sheet_pk)
            if inv:
                EQUIP_WIDTH = 78
                weapons = list(inv.weapons.all()) if hasattr(inv, 'weapons') else []
                w_items = [w.name for w in weapons] if weapons else ["None"]
                output += wrap_labeled_comma_list("|yWeapons:|n ", w_items, "|w", "|n", width=EQUIP_WIDTH, separator=",")

                armor = list(inv.armor.all()) if hasattr(inv, 'armor') else []
                a_items = [p.name for p in armor] if armor else ["None"]
                output += wrap_labeled_comma_list("|yArmor:|n ", a_items, "|w", "|n", width=EQUIP_WIDTH, separator=",")

                # Use get_gear_with_quantities (same as +inventory) - avoids M2M-through issues
                try:
                    gear_items = inv.get_gear_with_quantities() if hasattr(inv, 'get_gear_with_quantities') else [(g, 1) for g in inv.gear.all()]
                    gear_names = [f"{g.name} (x{qty})" if qty > 1 else g.name for g, qty in gear_items]
                    g_items = gear_names if gear_names else ["None"]
                    output += wrap_labeled_comma_list("|yGear:|n ", g_items, "|w", "|n", width=EQUIP_WIDTH, separator=",")
                except Exception as gear_err:
                    logger.log_err(f"Error retrieving gear for {target}: {gear_err}", exc_info=True)
                    output += "|yGear:|n |wError retrieving gear|n\n"

                try:
                    cyberware = list(inv.cyberware.filter(installed=True)) if hasattr(inv, 'cyberware') else []
                    cw_names = [c.cyberware.name for c in cyberware]
                    cw_items = cw_names if cw_names else ["None"]
                    output += wrap_labeled_comma_list("|yCyberware:|n ", cw_items, "|w", "|n", width=EQUIP_WIDTH, separator=",")
                except Exception as cw_err:
                    logger.log_err(f"Error retrieving cyberware for {target}: {cw_err}", exc_info=True)
                    output += "|yCyberware:|n |wError retrieving cyberware|n\n"
                eurodollars = CharacterSheetMoneyService.get_balance(sheet)
                output += f"|yBalance:|n |w{eurodollars} Eurodollars|n\n"
            else:
                output += "|yWeapons:|n |wNone|n\n|yArmor:|n |wNone|n\n|yGear:|n |wNone|n\n|yCyberware:|n |wNone|n\n"
        except Exception as e:
            logger.log_err(f"Error retrieving inventory for {target}: {str(e)}", exc_info=True)
            output += "|wError retrieving inventory|n\n"
        output += "\n"

        # Languages (three-column format, alphabetical order - like skills)
        output += sheet_section("Languages", width=W)
        if hasattr(target, 'languages') and target.languages:
            lang_list = [(name, level) for name, level in target.languages.items()]
            lang_list.sort(key=lambda x: x[0].lower())
            for i in range(0, len(lang_list), 3):
                row = lang_list[i:i+3]
                output += "".join(f"|y{name:<20}|n {level:<5}" for name, level in row).ljust(80) + "\n"
        else:
            output += "|wNone|n\n"

        # Sell Your Soul (if chosen during chargen)
        sheet = target.character_sheet if hasattr(target, 'character_sheet') and target.character_sheet else None
        if sheet and getattr(sheet, 'sell_your_soul', False):
            output += sheet_section("Sell Your Soul", width=W)
            employer = getattr(sheet, 'sell_your_soul_employer', '') or "Unknown"
            catch = getattr(sheet, 'sell_your_soul_catch', '') or "Unknown"
            output += f"|yEmployer:|n {employer}\n"
            output += f"|yCatch:|n {catch}\n"

        output += footer(width=W, fillchar="-")
        self.caller.msg(output)

    # Role ability key -> Role name (for detecting secondary roles from taken abilities)
    ROLE_ABILITY_TO_ROLE = {
        'charismatic_impact': 'Rockerboy',
        'combat_awareness': 'Solo',
        'interface': 'Netrunner',
        'maker': 'Tech',
        'medicine': 'Medtech',
        'credibility': 'Media',
        'teamwork': 'Exec',
        'backup': 'Lawman',
        'operator': 'Fixer',
        'moto': 'Nomad',
    }

    def get_display_roles(self, char):
        """
        Build role display string: primary role + any secondary roles from role abilities.
        E.g. "Solo / Rockerboy / Medtech" if primary is Solo but they also have Charismatic Impact and Medicine.
        """
        primary = (char.db.role or "").strip()
        roles_seen = set()
        roles_ordered = []

        # Primary role first
        if primary:
            roles_seen.add(primary)
            roles_ordered.append(primary)

        # Add secondary roles from role abilities with value > 0
        if hasattr(char, 'db') and char.db.skills:
            for ability_key, role_name in self.ROLE_ABILITY_TO_ROLE.items():
                if role_name in roles_seen:
                    continue
                val = char.db.skills.get(ability_key, 0)
                if val > 0:
                    roles_seen.add(role_name)
                    roles_ordered.append(role_name)

        return " / ".join(roles_ordered) if roles_ordered else "None"

    # Keys in db.skills that are derived stats, not actual skills (exclude from SKILLS section)
    NON_SKILL_KEYS = frozenset({
        'total_cyberware_humanity_loss', 'humanity', 'death_save', 'serious_wounds',
        'unarmed_damage_die_type', 'unarmed_damage_dice',
    })

    # Role ability keys - displayed in Role Abilities section, excluded from SKILLS
    ROLE_ABILITY_KEYS = frozenset(ROLE_ABILITY_TO_ROLE.keys())

    # Max width for skill names (2 cols: 30+1+5=36 each = 72 total, under 80)
    SKILL_NAME_WIDTH = 30

    def _format_skill_for_sheet(self, name, skill_key=None, base_skill=None):
        """
        Format skill name for sheet display.
        - Instanced skills (Local Expert, Martial Arts, Play Instrument): "Skill Name: Instance (STAT)"
        - Regular skills: "Skill Name (STAT)"
        - Applies display overrides (Resist Torture/Drugs, Electronics/Security Tech, etc.)
        """
        base = (base_skill or "").lower().strip()
        instance = None
        if skill_key and "(" in skill_key and ")" in skill_key:
            base, instance = skill_key.split("(", 1)
            base = base.strip().lower()
            instance = instance.rstrip(")").strip()

        # Get display name: override or title-case
        display_name = SKILL_DISPLAY_OVERRIDES.get(base)
        if not display_name:
            display_name = base.replace("_", " ").title() if base else name

        # Instanced format: "SKILL NAME: INSTANCE" (not parens)
        if instance:
            formatted = f"{display_name}: {instance}"
        else:
            formatted = display_name

        # Add stat abbreviation
        stat_key = SKILL_TO_STAT_LOOKUP.get(base)
        if stat_key and stat_key in STAT_DESCRIPTIONS:
            stat_abbrev = STAT_DESCRIPTIONS[stat_key]["abbrev"]
            formatted = f"{formatted} ({stat_abbrev})"

        if len(formatted) > self.SKILL_NAME_WIDTH:
            formatted = formatted[: self.SKILL_NAME_WIDTH - 3] + "..."
        return formatted

    def get_active_skills(self, char):
        """
        Get a list of active skills (skills with value > 0) directly from the character.
        Excludes derived stats that may be stored in db.skills.
        """
        skill_list = []

        # Get skills from character's skills dictionary (exclude role abilities)
        if hasattr(char, 'db') and char.db.skills:
            for skill_name, value in char.db.skills.items():
                if value > 0 and skill_name not in self.NON_SKILL_KEYS and skill_name not in self.ROLE_ABILITY_KEYS:
                    display_name = self._format_skill_for_sheet(
                        skill_name.replace('_', ' ').title(),
                        base_skill=skill_name,
                    )
                    skill_list.append([display_name, value])

        # Add skill instances from character typeclass
        if hasattr(char, 'db') and char.db.skill_instances:
            for skill_key, value in char.db.skill_instances.items():
                if value > 0 and "(" in skill_key and ")" in skill_key:
                    # Extract the base name and instance from the key (format: "base_skill(instance)")
                    base_name, instance = skill_key.split("(", 1)
                    instance = instance.rstrip(")")
                    # Format for sheet (abbreviated + truncated)
                    formatted_name = self._format_skill_for_sheet(
                        f"{base_name.replace('_', ' ').title()} ({instance})",
                        skill_key=skill_key,
                    )
                    skill_list.append([formatted_name, value])

        skill_list.sort(key=lambda x: (x[0].lower(), -x[1]))  # Alphabetical by name, then by value desc
        return skill_list

    def get_role_abilities(self, char):
        """
        Get a list of role abilities (primary + any bought with IP) for the Role Abilities section.
        Includes Medicine specialty breakdown for Medtechs.
        Returns [(display_name, value), ...] sorted alphabetically.
        """
        ability_list = []

        if not hasattr(char, 'db') or not char.db.skills:
            return ability_list

        # Standard role abilities (from db.skills)
        for ability_key in self.ROLE_ABILITY_KEYS:
            value = char.db.skills.get(ability_key, 0)
            if value <= 0:
                continue
            if ability_key in ('medicine', 'maker'):
                # Medicine/Maker: add base rank plus specialty breakdown (handled below)
                continue
            display_name = ability_key.replace('_', ' ').title()
            display_name = self._format_skill_for_sheet(display_name)
            ability_list.append([display_name, value])

        # Medicine (Medtech): add base Medicine + specialty breakdown when available
        medicine = char.db.skills.get('medicine', 0)
        if medicine > 0:
            if hasattr(char, 'get_medicine_specialties'):
                from world.chargen_constants import get_medicine_surgery_skill, get_medical_tech_skill
                s, p, c = char.get_medicine_specialties()
                surg_skill = get_medicine_surgery_skill(s)
                medtech_skill = get_medical_tech_skill(p, c)
                if surg_skill > 0:
                    ability_list.append(["Surgery", surg_skill])
                if p > 0:
                    ability_list.append(["Med Tech (Pharma)", p])
                if c > 0:
                    ability_list.append(["Med Tech (Cryo)", c])
                if medtech_skill > 0:
                    ability_list.append(["Medical Tech", medtech_skill])
            ability_list.append(["Medicine", medicine])

        # Maker (Tech): add base Maker + specialty breakdown when available
        maker = char.db.skills.get('maker', 0)
        if maker > 0:
            if hasattr(char, 'get_maker_specialties'):
                f, u, fab, inv = char.get_maker_specialties()
                if f > 0:
                    ability_list.append(["Field Expertise", f])
                if u > 0:
                    ability_list.append(["Upgrade Expertise", u])
                if fab > 0:
                    ability_list.append(["Fabrication Expertise", fab])
                if inv > 0:
                    ability_list.append(["Invention Expertise", inv])
            ability_list.append(["Maker", maker])

        ability_list.sort(key=lambda x: (x[0].lower(), -x[1]))
        return ability_list

class CmdShortDesc(Command):
    """
    shortdesc <text>

    Usage:
      shortdesc <text>
      shortdesc <character>=<text>

    Create or set a short description for your character. Builders+ can set the short description for others.

    Examples:
      shortdesc Tall and muscular
      shortdesc Bob=Short and stocky
    """
    key = "shortdesc"
    help_category = "Roleplay Utilities"

    def parse(self):
        """
        Custom parser to handle the possibility of targeting another character.
        """
        args = self.args.strip()
        if "=" in args:
            self.target_name, self.shortdesc = [part.strip() for part in args.split("=", 1)]
        else:
            self.target_name = None
            self.shortdesc = args

    def func(self):
        "Implement the command"
        caller = self.caller

        if self.target_name:
            # Check if the caller has permission to set short descriptions for others
            if not caller.check_permstring("builders"):
                caller.msg("|rYou don't have permission to set short descriptions for others.|n")
                return

            # Find the target character
            target = caller.search(self.target_name, global_search=True)
            if not target:
                caller.msg(f"|rCharacter '{self.target_name}' not found.|n")
                return

            # Set the short description for the target
            target.db.shortdesc = self.shortdesc
            caller.msg(f"Short description for {target.name} set to '|w{self.shortdesc}|n'.")
            target.msg(f"Your short description has been set to '|w{self.shortdesc}|n' by {caller.name}.")
        else:
            # Set the short description for the caller
            if not self.shortdesc:
                # remove the shortdesc
                caller.db.shortdesc = ""
                caller.msg("Short description removed.")
                return

            caller.db.shortdesc = self.shortdesc
            caller.msg("Short description set to '|w%s|n'." % self.shortdesc)


class CmdRoll(MuxCommand):
    """
    Roll a skill check.

    Usage:
      roll <attribute> + <skill> [<+/- modifier>]
      roll <attribute> + <skill> [<+/- modifier>] vs <DV or difficulty name>
      roll/luck <amount>=<attribute> + <skill> [<+/- modifier>] [vs <DV>]

    Rolls 1d10 + attribute + skill + modifier (or raw values). Supports critical success
    (natural 10: add another d10) and critical failure (natural 1: subtract another d10).
    With 'vs', shows success (total exceeds DV) or failure. Hitting the DV exactly fails.

    Use roll/luck <N>= to spend N luck points before rolling (+1 per point).
    Use roll/job <#>=<stat> + <skill> [vs <DV>] to roll and post result to a job (e.g. repair).

    Difficulty names: Simple (9), Everyday (13), Difficult (15), Professional (17),
    Heroic (21), Incredible (24), Legendary (29).

    Examples:
      roll Reflexes + Handgun
      roll Intelligence + Interface +1 vs 13
      roll Reflexes + Shoulder Arms -3 vs Legendary
      roll/luck 3=intelligence + interface + 2 vs 20
    """
    key = "roll"
    aliases = ["check"]
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    def _get_stat_value(self, char, field_name, is_stat):
        """Get stat or skill value from character sheet or fallback to char attributes/db."""
        sheet = getattr(char, 'character_sheet', None)
        if sheet and hasattr(sheet, field_name):
            return getattr(sheet, field_name, 0)
        if is_stat:
            return char.attributes.get(field_name, 0)
        skill_key = field_name.lower().replace(' ', '_')
        return char.db.skills.get(skill_key, 0) if char.db.skills else 0

    def _parse_modifier(self, s):
        """Extract trailing modifier (+1, -3, + 1, - 3) from string. Returns (stripped_string, modifier)."""
        mod_match = re.search(r'\s*([+-])\s*(\d+)\s*$', s)
        if mod_match:
            sign, num = mod_match.group(1), int(mod_match.group(2))
            mod = num if sign == '+' else -num
            return s[:mod_match.start()].strip(), mod
        return s.strip(), 0

    def func(self):
        args = (self.args or "").strip()

        # Parse roll/job <#>=<roll> - post roll result as job comment
        if "job" in self.switches:
            self._roll_into_job(args)
            return

        # Parse roll/luck N=... syntax
        luck_spend = 0
        if "luck" in self.switches:
            if "=" not in args:
                self.caller.msg("Usage: roll/luck <amount>=<attribute> + <skill> [<+/- modifier>] [vs <DV>]")
                return
            luck_part, args = args.split("=", 1)
            luck_part = luck_part.strip()
            try:
                luck_spend = int(luck_part)
                if luck_spend < 1:
                    self.caller.msg("Luck amount must be at least 1.")
                    return
            except ValueError:
                self.caller.msg("Usage: roll/luck <amount>=<attribute> + <skill> [vs <DV>]")
                return
            args = args.strip()

        if not args:
            self.caller.msg("Usage: roll <attribute> + <skill> [<+/- modifier>] [vs <DV or difficulty>]")
            return

        # Parse "vs" part (case-insensitive)
        vs_info = None
        vs_match = re.search(r'\s+vs\s+', args, re.IGNORECASE)
        if vs_match:
            vs_str = args[vs_match.end():].strip()
            args = args[:vs_match.start()].strip()
            vs_info = parse_dv(vs_str)
            if vs_info is None:
                self.caller.msg("Invalid difficulty. Use a number (e.g. 9) or a name (Simple, Everyday, Difficult, Professional, Heroic, Incredible, Legendary).")
                return

        # Parse "Stat + Skill" part (with optional modifier on skill)
        if " + " not in args:
            if re.match(r'^\s*\d*d\d+', args, re.IGNORECASE):
                self.caller.msg("Syntax: roll <stat> + <skill> vs <difficulty>. To roll dice without a skill check, use the +dice command.")
                return
            self.caller.msg("Usage: roll <attribute> + <skill> [<+/- modifier>] [vs <DV or difficulty>]")
            return

        parts = args.split(" + ", 1)
        attr_input = parts[0].strip()
        skill_input, modifier = self._parse_modifier(parts[1])

        attr_value = None
        skill_value = None
        attr_display = None
        skill_display = None

        # Try parsing as raw numeric values (for NPCs / ad-hoc rolls)
        try:
            a, s = int(attr_input), int(skill_input)
            if 0 <= a <= 10 and 0 <= s <= 10:
                attr_value, skill_value = a, s
                attr_display, skill_display = str(a), str(s)
        except ValueError:
            pass

        # Fall back to character sheet lookup
        if attr_value is None:
            full_attr_name = get_full_attribute_name(attr_input)
            full_skill_name = get_full_attribute_name(skill_input)

            if not full_attr_name or full_attr_name not in STAT_MAPPING.values():
                self.caller.msg(f"Invalid attribute. Choose from: {', '.join(STAT_MAPPING.values())}, or use raw values 0-10.")
                return

            if not full_skill_name or full_skill_name not in SKILL_MAPPING.values():
                self.caller.msg(f"Invalid skill. Choose from: {', '.join(SKILL_MAPPING.values())}, or use raw values 0-10.")
                return

            char = self.caller
            attr_value = self._get_stat_value(char, full_attr_name, is_stat=True)
            skill_value = self._get_stat_value(char, full_skill_name, is_stat=False)
            attr_display = full_attr_name.replace('_', ' ').title()
            skill_display = full_skill_name.replace('_', ' ').title()

        # Luck check
        if luck_spend > 0:
            char = self.caller
            current = getattr(char.db, "current_luck", 0) or 0
            if current < luck_spend:
                self.caller.msg(f"You only have {current} luck point(s) remaining. Cannot spend {luck_spend}.")
                return

        from world.utils.roll_utils import roll_skill_check, check_success, format_roll_details

        total, details = roll_skill_check(
            attr_value, skill_value,
            modifier=modifier,
            luck_spend=luck_spend,
            character=self.caller if luck_spend else None,
        )

        breakdown = format_roll_details(details, attr_value, skill_value, modifier)
        out = f"Rolling {attr_display} + {skill_display} + 1d10: {breakdown} = |w{total}|n"

        if details.get("is_crit_success"):
            out += " |g(Critical Success!)|n"
        elif details.get("is_crit_failure"):
            out += " |r(Critical Failure!)|n"

        if vs_info is not None:
            dv, diff_name, _ = vs_info
            success = check_success(total, dv)
            color = "g" if success else "r"
            result = "Success" if success else "Failure"
            out += f" vs {dv}"
            if diff_name:
                out += f" ({diff_name})"
            out += f" - |{color}{result}|n"

        self.caller.msg(out)

    def _roll_into_job(self, args):
        """roll/job <job#>=<attribute> + <skill> [vs <DV>] - Roll and post result to job."""
        if not args or "=" not in args:
            self.caller.msg("Usage: roll/job <job#>=<attribute> + <skill> [vs <DV>]")
            return

        job_part, roll_part = args.split("=", 1)
        job_part = job_part.strip()
        roll_part = roll_part.strip()

        try:
            job_id = int(job_part)
        except ValueError:
            self.caller.msg("Job number must be a number.")
            return

        from world.jobs.models import Job

        try:
            job = Job.objects.get(id=job_id, archive_id__isnull=True)
        except Job.DoesNotExist:
            self.caller.msg(f"Job #{job_id} not found.")
            return

        if not (
            job.requester == self.caller.account
            or job.participants.filter(id=self.caller.account.id).exists()
            or self.caller.check_permstring("builders")
            or self.caller.check_permstring("wizards")
        ):
            self.caller.msg("You don't have permission to roll into this job.")
            return

        # Parse roll: "Stat + Skill" or "Stat + Skill vs DV"
        vs_info = None
        vs_match = re.search(r'\s+vs\s+', roll_part, re.IGNORECASE)
        if vs_match:
            vs_str = roll_part[vs_match.end():].strip()
            roll_part = roll_part[:vs_match.start()].strip()
            vs_info = parse_dv(vs_str)

        if " + " not in roll_part:
            self.caller.msg("Roll format: <stat> + <skill> [vs <DV>]")
            return

        parts = roll_part.split(" + ", 1)
        attr_input = parts[0].strip()
        skill_input, modifier = self._parse_modifier(parts[1])

        full_attr_name = get_full_attribute_name(attr_input)
        full_skill_name = get_full_attribute_name(skill_input)
        if not full_attr_name or full_attr_name not in STAT_MAPPING.values():
            self.caller.msg(f"Invalid attribute: {attr_input}")
            return
        if not full_skill_name or full_skill_name not in SKILL_MAPPING.values():
            self.caller.msg(f"Invalid skill: {skill_input}")
            return

        char = self.caller
        attr_value = self._get_stat_value(char, full_attr_name, is_stat=True)
        skill_value = self._get_stat_value(char, full_skill_name, is_stat=False)
        attr_display = full_attr_name.replace("_", " ").title()
        skill_display = full_skill_name.replace("_", " ").title()

        from world.utils.roll_utils import roll_skill_check, check_success, format_roll_details

        total, details = roll_skill_check(attr_value, skill_value, modifier=modifier)
        breakdown = format_roll_details(details, attr_value, skill_value, modifier)
        out = f"Roll: {attr_display} + {skill_display} + 1d10: {breakdown} = {total}"
        if details.get("is_crit_success"):
            out += " (Critical Success!)"
        elif details.get("is_crit_failure"):
            out += " (Critical Failure!)"
        if vs_info is not None:
            dv, diff_name, _ = vs_info
            success = check_success(total, dv)
            result = "Success" if success else "Failure"
            out += f" vs {dv}"
            if diff_name:
                out += f" ({diff_name})"
            out += f" - {result}"

        from django.utils import timezone

        comment = {
            "author": self.caller.account.username,
            "text": out,
            "created_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if not job.comments:
            job.comments = []
        job.comments.append(comment)
        job.save()

        self.caller.msg(f"|gRoll posted to Job #{job_id}:|n {out}")
        self.caller.msg("Staff will review and process the repair.")


class CmdLuck(MuxCommand):
    """
    Spend a luck point.

    Usage:
      luck        - Spend one luck point if you have any available.
      luck/gain <amount> - Regain luck points up to your maximum.
    """

    key = "luck"
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    def func(self):
        char = self.caller
        
        # Handle the gain switch
        if "gain" in self.switches:
            self.gain_luck()
            return
        
        # Handle spending luck
        current_luck = char.db.current_luck
        max_luck = char.db.luck
        
        if current_luck is None or max_luck is None:
            self.caller.msg("Your luck attributes aren't properly set up.")
            return
            
        if current_luck > 0:
            char.db.current_luck = current_luck - 1
            self.caller.msg(f"You spend a luck point. Remaining luck: {char.db.current_luck}/{max_luck}")
        else:
            self.caller.msg("You don't have any luck points to spend!")
        
    def gain_luck(self):
        """Handle gaining luck points."""
        if not self.args:
            self.caller.msg("Usage: luck/gain <amount>")
            return

        try:
            amount = int(self.args)
        except ValueError:
            self.caller.msg("Please provide a valid number.")
            return
        
        if amount <= 0:
            self.caller.msg("Please provide a positive number.")
            return

        char = self.caller
        current_luck = char.db.current_luck
        max_luck = char.db.luck
        
        if current_luck is None or max_luck is None:
            self.caller.msg("Your luck attributes aren't properly set up.")
            return

        if current_luck >= max_luck:
            self.caller.msg("You already have the maximum number of luck points.")
            return

        new_luck = min(current_luck + amount, max_luck)
        char.db.current_luck = new_luck
        self.caller.msg(f"You regained {amount} luck points. Current luck: {new_luck}/{max_luck}")

class CmdOOC(MuxCommand):
    """
    Speak or pose out-of-character in your current location.

    Usage:
      ooc <message>
      ooc :<pose>

    Examples:
      ooc Hello everyone!
      ooc :waves to the group.
    """
    key = "ooc"
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        if not self.args:
            self.caller.msg("Say or pose what?")
            return

        location = self.caller.location
        if not location:
            self.caller.msg("You are not in any location.")
            return

        # Strip leading and trailing whitespace from the message
        ooc_message = self.args.strip()

        # Check if it's a pose (starts with ':')
        if ooc_message.startswith(':'):
            pose = ooc_message[1:].strip()  # Remove the ':' and any following space
            message = f"<|mOOC|n> {self.caller.name} {pose}"
            self_message = f"<|mOOC|n> You say, \"{ooc_message}\""
        else:
            message = f"<|mOOC|n> {self.caller.name} says, \"{ooc_message}\""
            self_message = f"<|mOOC|n> You say, \"{ooc_message}\""

        location.msg_contents(message, exclude=self.caller)
        self.caller.msg(self_message)

class CmdPlusIc(MuxCommand):
    """
    Return to the IC area from OOC.

    Usage:
      +ic

    This command moves you back to your previous IC location if available,
    or to the default IC starting room if not. You must be approved to use this command.
    """

    key = "+ic"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller

        # Check if the character is approved
        if not caller.tags.has("approved", category="approval"):
            caller.msg("You must be approved to enter IC areas.")
            return

        # Get the stored pre_ooc_location, or use the default room #30
        target_location = caller.db.pre_ooc_location or search_object("#30")[0]

        if not target_location:
            caller.msg("Error: Unable to find a valid IC location.")
            return

        # Move the caller to the target location
        caller.move_to(target_location, quiet=True)
        caller.msg(f"You return to the IC area ({target_location.name}).")
        target_location.msg_contents(f"{caller.name} has returned to the IC area.", exclude=caller)

        # Clear the pre_ooc_location attribute
        caller.attributes.remove("pre_ooc_location")

class CmdPlusOoc(MuxCommand):
    """
    Move to the OOC area (Limbo).

    Usage:
      +ooc

    This command moves you to the OOC area (Limbo) and stores your
    previous location so you can return later.
    """

    key = "+ooc"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        current_location = caller.location

        # Store the current location as an attribute
        caller.db.pre_ooc_location = current_location

        # Find Limbo (object #2)
        limbo = search_object("#2")[0]

        if not limbo:
            caller.msg("Error: Limbo not found.")
            return

        # Move the caller to Limbo
        caller.move_to(limbo, quiet=True)
        caller.msg(f"You move to the OOC area ({limbo.name}).")
        limbo.msg_contents(f"{caller.name} has entered the OOC area.", exclude=caller)

class CmdMeet(MuxCommand):
    """
    Send a meet request to another player or respond to one.

    Usage:
      +meet <player>
      +meet/accept
      +meet/reject

    Sends a meet request to another player. If accepted, they'll be
    teleported to your location.
    """

    key = "+meet"
    locks = "cmd:all()"
    help_category = "General"

    def search_for_character(self, search_string):
        # First, try to find by exact name match
        results = search_object(search_string, typeclass="typeclasses.characters.Character")
        if results:
            return results[0]
        
        # If not found, try to find by dbref
        if search_string.startswith("#") and search_string[1:].isdigit():
            results = search_object(search_string, typeclass="typeclasses.characters.Character")
            if results:
                return results[0]
        
        # If still not found, return None
        return None

    def func(self):
        caller = self.caller

        if not self.args and not self.switches:
            caller.msg("Usage: +meet <player> or +meet/accept or +meet/reject")
            return

        if "accept" in self.switches:
            if not caller.ndb.meet_request:
                caller.msg("You have no pending meet requests.")
                return
            requester = caller.ndb.meet_request
            # Capture locations before move - avoids desync if move_to triggers DB write
            old_location = caller.location
            destination = requester.location
            caller.move_to(destination, quiet=True)
            caller.msg(f"You accept the meet request from {requester.name} and join them.")
            requester.msg(f"{caller.name} has accepted your meet request and joined you.")
            old_location.msg_contents(f"{caller.name} has left to meet {requester.name}.", exclude=caller)
            destination.msg_contents(f"{caller.name} appears, joining {requester.name}.", exclude=[caller, requester])
            caller.ndb.meet_request = None
            return

        if "reject" in self.switches:
            if not caller.ndb.meet_request:
                caller.msg("You have no pending meet requests.")
                return
            requester = caller.ndb.meet_request
            caller.msg(f"You reject the meet request from {requester.name}.")
            requester.msg(f"{caller.name} has rejected your meet request.")
            caller.ndb.meet_request = None
            return

        target = self.search_for_character(self.args)
        if not target:
            caller.msg(f"Could not find character '{self.args}'.")
            return

        if target == caller:
            caller.msg("You can't send a meet request to yourself.")
            return

        if target.ndb.meet_request:
            caller.msg(f"{target.name} already has a pending meet request.")
            return

        target.ndb.meet_request = caller
        caller.msg(f"You sent a meet request to {target.name}.")
        target.msg(f"{caller.name} has sent you a meet request. Use +meet/accept to accept or +meet/reject to decline.")
