# Lifepath data - re-exported from world.lifepath for backward compatibility
from world.lifepath import (
    CULTURAL_ORIGINS as _CULTURAL_ORIGINS,
    PERSONALITY_TRAITS,
    CLOTHING_STYLES,
    HAIRSTYLES,
    AFFECTATIONS,
    MOTIVATIONS,
    LIFE_GOALS,
    FAMILY_BACKGROUND,
    CHILDHOOD_ENVIRONMENT,
    FAMILY_CRISIS,
    ROLE_LIFEPATH,
)

# Legacy: list of region names (old format expected list of strings)
CULTURAL_ORIGINS = [o["region"] for o in _CULTURAL_ORIGINS]

# Mapping of cultural origin to languages (used by CharacterSheet.clear_cultural_languages)
CULTURAL_ORIGIN_LANGUAGES = {o["region"]: o["languages"] for o in _CULTURAL_ORIGINS}

# Legacy aliases
PERSONALITIES = PERSONALITY_TRAITS
ENVIRONMENT = CHILDHOOD_ENVIRONMENT

# Legacy: role-specific as (question, choices) for old lifepath_functions compat
ROLE_SPECIFIC_LIFEPATHS = {
    role: [("Role Event", events)] for role, events in ROLE_LIFEPATH.items()
}

# Not in new lifepath - kept for import compatibility (character_commands, etc.)
VALUED_PERSON = [
    "A parent", "A brother or sister", "A lover", "A friend", "Yourself",
    "A pet", "A teacher or mentor", "A public figure", "A personal hero", "No one"
]
VALUED_POSSESSION = [
    "A weapon", "A tool", "A piece of clothing", "A photograph", "A book or diary",
    "A recording", "A musical instrument", "A piece of jewelry", "A toy", "A letter"
]
