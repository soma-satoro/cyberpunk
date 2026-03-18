# Define a mapping of abbreviated stat names to full stat names
from world.cyberpunk_sheets.models import CharacterSheet


def is_character_approved(obj):
    """
    Check if a character is approved by staff. Unapproved characters cannot use
    certain in-character systems (missions, hangouts, combat, mysteries, IP spending,
    voting, Elflines, netrunning, NPC creation, hustles).

    Staff (Builder+) bypass this check - they can use any command regardless of
    approval status.

    Args:
        obj: A Character (or Account with character) to check.

    Returns:
        bool: True if the character is staff or has the 'approved' tag; False otherwise.
    """
    if not obj:
        return False
    char = obj
    if hasattr(obj, "character") and obj.character:
        char = obj.character
    # Staff bypass: Builder, Admin, Developer can do anything
    acct = getattr(char, "account", None)
    if acct and (
        getattr(acct, "is_superuser", False)
        or (hasattr(acct, "check_permstring") and acct.check_permstring("Builder"))
    ):
        return True
    if not hasattr(char, "tags"):
        return False
    return char.tags.has("approved", category="approval")


def is_staff(obj):
    """
    Check if a character/account is staff (Builder+ or superuser).
    Staff bypass approval for using commands but cannot receive IP from vote or weekly allotment.
    """
    if not obj:
        return False
    char = obj
    if hasattr(obj, "character") and obj.character:
        char = obj.character
    acct = getattr(char, "account", None)
    if not acct:
        return False
    return (
        getattr(acct, "is_superuser", False)
        or (hasattr(acct, "check_permstring") and acct.check_permstring("Builder"))
    )


def can_receive_ip(obj):
    """
    Check if a character can receive IP from vote or weekly allotment.
    Must be approved and NOT staff. Staff do not receive IP from these sources.
    """
    if not obj or is_staff(obj):
        return False
    return is_character_approved(obj)


STAT_MAPPING = {
    'INT': 'intelligence',
    'REF': 'reflexes',
    'DEX': 'dexterity',
    'TECH': 'technology',
    'COOL': 'cool',
    'WILL': 'willpower',
    'LUCK': 'luck',
    'MOVE': 'move',
    'BOD': 'body',
    'EMP': 'empathy',
    'HUM': 'humanity',
}

SKILL_MAPPING = {
    'CONC': 'concentration',
    'CO': 'conceal_object',
    'LR': 'lip_reading',
    'PER': 'perception',
    'TRACK': 'tracking',
    'ATH': 'athletics',
    'CONT': 'contortionist',
    'DANCE': 'dance',
    'END': 'endurance',
    'RTD': 'resist_torture_drugs',
    'STEALTH': 'stealth',
    'DLV': 'drive_land',
    'PAV': 'pilot_air',
    'PSV': 'pilot_sea',
    'RIDE': 'riding',
    'ACC': 'accounting',
    'AH': 'animal_handling',
    'BUR': 'bureaucracy',
    'BUS': 'business',
    'COMP': 'composition',
    'CRIM': 'criminology',
    'CRYPT': 'cryptography',
    'DED': 'deduction',
    'EDU': 'education',
    'GAMB': 'gamble',
    'LS': 'library_search',
    'LE': 'local_expert',
    'TAC': 'tactics',
    'WS': 'wilderness_survival',
    'ZOO': 'zoology',
    'SM': 'stock_market',
    'PHY': 'physics',
    'BIO': 'biology',
    'CHEM': 'chemistry',
    'NEURO': 'neuroscience',
    'DS': 'data_science',
    'ECON': 'economics',
    'SOC': 'sociology',
    'PS': 'political_science',
    'GEN': 'genetics',
    'ANAT': 'anatomy',
    'ROB': 'robotics',
    'NANO': 'nanotechnology',
    'BRAW': 'brawling',
    'EVA': 'evasion',
    'MA': 'martial_arts',
    'MEL': 'melee',
    'ACT': 'acting',
    'PI': 'play_instrument',
    'PG': 'personal_grooming',
    'ARCH': 'archery',
    'AUTO': 'autofire',
    'HG': 'handgun',
    'HW': 'heavy_weapons',
    'SA': 'shoulder_arms',
    'BRIB': 'bribery',
    'CONV': 'conversation',
    'HP': 'human_perception',
    'INT': 'interrogation',
    'PERS': 'persuasion',
    'SW': 'streetwise',
    'TRAD': 'trading',
    'STYLE': 'style',
    'AVT': 'air_vehicle_tech',
    'BT': 'basic_tech',
    'CT': 'cybertech',
    'DEM': 'demolitions',
    'ES': 'electronics_security_tech',
    'FA': 'first_aid',
    'FORG': 'forgery',
    'LVT': 'land_vehicle_tech',
    'ART': 'artistry',
    'PARA': 'paramedic',
    'PF': 'photography',
    'PL': 'pick_lock',
    'PP': 'pick_pocket',
    'SVT': 'sea_vehicle_tech',
    'WT': 'weaponstech',
    'CI': 'charismatic_impact',
    'CA': 'combat_awareness',
    'IF': 'interface',
    'MAK': 'maker',
    'MED': 'medicine',
    'CRED': 'credibility',
    'TW': 'teamwork',
    'BU': 'backup',
    'OP': 'operator',
    'MOTO': 'moto'
}

# Medicine (Medtech) specialties - allocate Medicine rank: surgery, pharma, cryo
MEDICINE_SPECIALTY_MAPPING = {
    'MEDSUG': 'medicine_surgery',
    'MEDPHA': 'medicine_pharma',
    'MEDCRY': 'medicine_cryo',
}
MEDICINE_SPECIALTY_ATTRIBUTES = frozenset(MEDICINE_SPECIALTY_MAPPING.values())

# Maker (Tech) specialties - allocate Maker rank × 2: field, upgrade, fabrication, invention
MAKER_SPECIALTY_MAPPING = {
    'MAKF': 'maker_field',
    'MAKU': 'maker_upgrade',
    'MAKFAB': 'maker_fabrication',
    'MAKINV': 'maker_invention',
}
MAKER_SPECIALTY_ATTRIBUTES = frozenset(MAKER_SPECIALTY_MAPPING.values())

TOPSHEET_MAPPING = {
    'FN': 'full_name',
    'HANDLE': 'handle',
    'HOME': 'hometown',
    'AGE': 'age',
    'HEIGHT': 'height',
    'WEIGHT': 'weight',
    'GENDER': 'gender'
}

# Wound system: staff can modify via stat command
WOUND_STAT_MAPPING = {
    'DSP': 'death_save_penalty',
    'DEATH_SAVE_PENALTY': 'death_save_penalty',
    'BASE_DSP': 'base_death_save_penalty',
    'BASE_DEATH_SAVE_PENALTY': 'base_death_save_penalty',
    'DEAD': 'dead',
}

ALL_ATTRIBUTES = {**STAT_MAPPING, **SKILL_MAPPING, **TOPSHEET_MAPPING}

# Create a reverse mapping with multiple options
REVERSE_MAPPING = {}
for mapping in [STAT_MAPPING, SKILL_MAPPING, TOPSHEET_MAPPING, MEDICINE_SPECIALTY_MAPPING, MAKER_SPECIALTY_MAPPING]:
    for abbr, full in mapping.items():
        REVERSE_MAPPING[abbr] = full
        REVERSE_MAPPING[full.upper()] = full
        # Add space-separated form (e.g. "SHOULDER ARMS" -> shoulder_arms)
        if '_' in full:
            REVERSE_MAPPING[full.replace('_', ' ').upper()] = full
        # Add plural form for skills (e.g. HANDGUNS -> handgun)
        if mapping is SKILL_MAPPING and not full.endswith('s') and full not in MEDICINE_SPECIALTY_MAPPING.values() and full not in MAKER_SPECIALTY_MAPPING.values():
            REVERSE_MAPPING[(full + 's').upper()] = full
        # Add partial matches
        for i in range(1, len(abbr)):
            REVERSE_MAPPING[abbr[:i]] = full
        for i in range(3, len(full)):  # Start from 3 to avoid very short matches
            REVERSE_MAPPING[full[:i].upper()] = full
# Wound stats: full keys only (no short abbrevs to avoid conflicts)
for abbr, full in WOUND_STAT_MAPPING.items():
    REVERSE_MAPPING[abbr] = full
    REVERSE_MAPPING[full.upper()] = full
    if '_' in full:
        REVERSE_MAPPING[full.replace('_', ' ').upper()] = full

def format_skill_display(name):
    """Convert internal skill/stat name (e.g. shoulder_arms) to display form (Shoulder Arms)."""
    if not name:
        return ""
    return name.replace('_', ' ').title()

def get_full_attribute_name(input_str):
    """
    Get the full attribute name from various input options.
    Accepts underscores or spaces: "Shoulder Arms" and "shoulder_arms" both resolve to shoulder_arms.
    """
    if not input_str:
        return None
    normalized = input_str.strip().upper()
    result = REVERSE_MAPPING.get(normalized)
    if result is None and ' ' in normalized:
        # Try with spaces replaced by underscores
        result = REVERSE_MAPPING.get(normalized.replace(' ', '_'))
    return result


def _fuzzy_match_from_pool(input_str, pool):
    """
    Fuzzy match input against a pool of full names (e.g. stat or skill names).
    Input is matched as a prefix (case-insensitive) of the full name.
    Returns (single_match, None) if exactly one match, or (None, [display_names]) if multiple.
    Returns (None, []) if no matches.
    """
    if not input_str or not pool:
        return None, []
    inp = input_str.strip().lower().replace(' ', '_')
    if not inp:
        return None, []

    def norm(name):
        return (name or "").lower().replace(" ", "_")

    matches = []
    for full in pool:
        n = norm(full)
        display = format_skill_display(full)
        # Exact match
        if n == inp:
            return full, None
        # Prefix match: full name starts with input (require at least 2 chars)
        if len(inp) >= 2 and n.startswith(inp):
            matches.append((full, display))

    if len(matches) == 1:
        return matches[0][0], None
    if len(matches) > 1:
        return None, [m[1] for m in matches]
    return None, []


def fuzzy_match_stat(input_str):
    """
    Fuzzy match input to a stat. Returns (full_name, None) if unique match,
    or (None, [display_names]) if multiple matches. (None, []) if no match.
    Falls back to get_full_attribute_name for abbreviations (e.g. REF, DEX).
    """
    single, multi = _fuzzy_match_from_pool(input_str, list(STAT_MAPPING.values()))
    if single:
        return single, None
    if multi:
        return None, multi
    # Fallback: try abbreviation mapping (e.g. REF -> reflexes)
    legacy = get_full_attribute_name(input_str)
    if legacy and legacy in STAT_MAPPING.values():
        return legacy, None
    return None, []


def fuzzy_match_skill(input_str):
    """
    Fuzzy match input to a skill. Returns (full_name, None) if unique match,
    or (None, [display_names]) if multiple matches. (None, []) if no match.
    Falls back to get_full_attribute_name for abbreviations (e.g. HG, IF).
    """
    pool = list(SKILL_MAPPING.values()) + list(MEDICINE_SPECIALTY_MAPPING.values()) + list(MAKER_SPECIALTY_MAPPING.values())
    single, multi = _fuzzy_match_from_pool(input_str, pool)
    if single:
        return single, None
    if multi:
        return None, multi
    # Fallback: try abbreviation mapping
    legacy = get_full_attribute_name(input_str)
    if legacy and legacy in pool:
        return legacy, None
    return None, []


# Skills that require an instance for rolls (e.g. local_expert(The Net), play_instrument(Guitar))
SKILLS_REQUIRING_INSTANCE = frozenset(["local_expert", "play_instrument", "martial_arts"])


def fuzzy_match_stat_or_skill(input_str):
    """
    Fuzzy match input to a stat or skill (interchangeable for roll).
    Tries stat first, then skill. Returns (full_name, None) if unique match,
    or (None, [display_names]) if multiple matches. (None, []) if no match.
    Supports skill instances: "local expert (The Net)" -> local_expert(The Net).
    """
    base_input = input_str
    instance_part = None
    if input_str and "(" in input_str and ")" in input_str:
        idx = input_str.index("(")
        base_input = input_str[:idx].strip()
        instance_part = input_str[idx + 1 : input_str.rindex(")")].strip()

    stat_match, stat_ambiguous = fuzzy_match_stat(base_input)
    if stat_match:
        return stat_match, None
    skill_match, skill_ambiguous = fuzzy_match_skill(base_input)
    if skill_match:
        if skill_match in SKILLS_REQUIRING_INSTANCE and instance_part:
            return f"{skill_match}({instance_part})", None
        return skill_match, None
    if stat_ambiguous or skill_ambiguous:
        combined = list(dict.fromkeys((stat_ambiguous or []) + (skill_ambiguous or [])))
        return None, combined
    return None, []


def get_character_sheet(character):
    if isinstance(character, (list, tuple)) and character:
        character = character[0]
    try:
        return CharacterSheet.objects.get(character=character)
    except CharacterSheet.DoesNotExist:
        return None


def get_staff_target_character(caller, target_name, quiet=False):
    """
    Resolve a target name to a character for staff commands. Works for offline characters
    (global search). Returns (character, sheet) or (None, None) if not found or not staff.

    Staff = Builder+ (Builder, Admin, Developer).
    quiet: If True, suppress search "not found" message (caller handles messaging).
    """
    if not target_name or not str(target_name).strip():
        return None, None
    if not is_staff(caller):
        return None, None
    target = caller.search(str(target_name).strip(), global_search=True, quiet=quiet)
    if not target:
        return None, None
    # search() may return a list when multiple matches; take first
    if isinstance(target, (list, tuple)):
        target = target[0] if target else None
    if not target:
        return None, None
    # Resolve to character and sheet
    char = target
    sheet = None
    if hasattr(target, "character_sheet") and target.character_sheet:
        sheet = target.character_sheet
        char = getattr(sheet, "character", None) or target
    elif hasattr(target, "characters"):
        chars = list(target.characters) if not callable(target.characters) else list(target.characters())
        if chars:
            char = chars[0]
            if isinstance(char, (list, tuple)) and char:
                char = char[0]
            sheet = get_character_sheet(char)
    else:
        sheet = get_character_sheet(target)
    if not sheet:
        return None, None
    return char, sheet

def get_pronouns(gender):
    if gender == "male":
        return "he", "him", "his"
    elif gender == "female":
        return "she", "her", "her"
    else:
        return "they", "them", "their"
