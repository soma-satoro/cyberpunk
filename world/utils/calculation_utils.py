# /root/cyberpunk/cyberpunk/world/utils/calculation_utils.py


STAT_MAPPING = {
    'INT': 'intelligence',
    'REF': 'reflexes',
    'DEX': 'dexterity',
    'TECH': 'technique',
    'COOL': 'cool',
    'WILL': 'willpower',
    'LUCK': 'luck',
    'MOVE': 'move',
    'BOD': 'body',
    'EMP': 'empathy'
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

def calculate_points_spent(character):
    def _get_stat(char, attr):
        if attr == 'technique':
            from world.utils.character_utils import get_technique_value
            return get_technique_value(char) or 0
        return getattr(char, attr, 0) or 0
    stat_points = sum(_get_stat(character, attr) for attr in STAT_MAPPING.values())
    double_cost_skills = ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics_security_tech', 'paramedic']
    from world.chargen_constants import ROLE_ABILITY_FREE_POINTS, ROLE_ABILITY_SKILLS
    from world.cyberpunk_constants import STATS
    core_stats = frozenset(STATS)
    role = (getattr(character, 'role', None) or "").strip()
    role_ability_skill = ROLE_ABILITY_SKILLS.get(role) if role else None
    skill_points = 0
    # Medtech: Surgery and Medical Tech are derived from Medicine specialties. 
    medtech_derived_skills = frozenset(("surgery", "medical_tech"))
    for skill in SKILL_MAPPING.values():
        if skill in core_stats:
            continue  # Never count stats as skills (e.g. technique)
        if role == "Medtech" and skill in medtech_derived_skills:
            continue  # Derived from Medicine allocation; avoid double-count
        val = int(getattr(character, skill, 0) or 0)
        mult = 2 if skill in double_cost_skills else 1
        if skill == role_ability_skill:
            billable = max(0, val - ROLE_ABILITY_FREE_POINTS)
            skill_points += billable * mult
        else:
            skill_points += val * mult

    # Add points from languages. Streetslang 4 (automatic) and lifepath language are free.
    if hasattr(character, 'sheet_language_proficiencies'):
        lifepath_lang = getattr(character, 'lifepath_language', None) or ""
        # Sheet may link to character; character has db.lifepath
        if not lifepath_lang and getattr(character, 'character', None):
            try:
                lp = getattr(character.character.db, 'lifepath', None) or {}
                lifepath_lang = lp.get("cultural_language_picked", "") or ""
            except Exception:
                pass
        skill_points += calculate_language_skill_points(
            character.sheet_language_proficiencies.all(),
            lifepath_language=lifepath_lang,
        )
    
    return stat_points, skill_points


def calculate_language_skill_points(language_items, lifepath_language=""):
    """
    Calculate skill points spent on languages during chargen.
    Streetslang 4 (automatic from chargen) and the lifepath language are free.
    All other languages cost 1 skill point per rank.
    language_items: iterable of (name, level) or objects with .language.name and .level
    lifepath_language: name of language added by lifepath (free)
    """
    lifepath_lang = (lifepath_language or "").strip().lower()
    points = 0
    for item in language_items:
        if hasattr(item, "language") and hasattr(item, "level"):
            name = (item.language.name or "").strip().lower()
            level = int(item.level or 0)
        else:
            name, level = item[0], int(item[1] or 0)
            name = (name or "").strip().lower()
        if level <= 0:
            continue
        # Streetslang at 4 or less: free (automatic from chargen)
        if name == "streetslang" and level <= 4:
            continue
        # Lifepath language: free
        if lifepath_lang and name == lifepath_lang:
            continue
        points += level
    return points


def get_remaining_points(character, is_edgerunner=False):
    stat_points_spent, skill_points_spent = calculate_points_spent(character)
    
    stat_points_limit = 62
    skill_points_limit = 86
    
    remaining_stat_points = max(0, stat_points_limit - stat_points_spent)
    remaining_skill_points = max(0, skill_points_limit - skill_points_spent)
    
    if is_edgerunner:
        # For Edgerunners, add any unspent points to the remaining points
        total_remaining = (remaining_stat_points + remaining_skill_points)
        remaining_stat_points = total_remaining
        remaining_skill_points = total_remaining
    
    return remaining_stat_points, remaining_skill_points