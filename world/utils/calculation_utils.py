# /root/cyberpunk/cyberpunk/world/utils/calculation_utils.py


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
    'ES': 'electronics',
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
    stat_points = sum(getattr(character, attr, 0) for attr in STAT_MAPPING.values())
    double_cost_skills = ['autofire', 'martial_arts', 'pilot_air', 'heavy_weapons', 'demolitions', 'electronics', 'paramedic']
    from world.chargen_constants import ROLE_ABILITY_FREE_POINTS, ROLE_ABILITY_SKILLS
    role = (getattr(character, 'role', None) or "").strip()
    role_ability_skill = ROLE_ABILITY_SKILLS.get(role) if role else None
    skill_points = 0
    for skill in SKILL_MAPPING.values():
        val = getattr(character, skill, 0) or 0
        mult = 2 if skill in double_cost_skills else 1
        if skill == role_ability_skill:
            billable = max(0, int(val) - ROLE_ABILITY_FREE_POINTS)
            skill_points += billable * mult
        else:
            skill_points += int(val) * mult

    # Add points from languages (CharacterSheet uses sheet_language_proficiencies)
    if hasattr(character, 'sheet_language_proficiencies'):
        skill_points += sum(lang.level for lang in character.sheet_language_proficiencies.all())
    
    return stat_points, skill_points

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