from world.lifepath_dictionary import CULTURAL_ORIGINS, PERSONALITIES, CLOTHING_STYLES, HAIRSTYLES, AFFECTATIONS, MOTIVATIONS, LIFE_GOALS, ROLE_SPECIFIC_LIFEPATHS, VALUED_PERSON, VALUED_POSSESSION, FAMILY_BACKGROUND, ENVIRONMENT, FAMILY_CRISIS
from world.cyberpunk_sheets.models import CharacterSheet
from django.db import IntegrityError

def start_lifepath(caller):
    cs = caller.account.character_sheet
    text = "Welcome to the Cyberpunk RED Lifepath creation process!\n"
    text += "This will guide you through creating your character's background.\n"
    if cs.role:
        text += f"\nCurrent Role: {cs.role}\n"
    else:
        text += "\nIMPORTANT: You haven't set a role yet. Choose 'Set Role' to define your character's role.\n"
    text += "Choose an aspect to define:"
    options = [
        {"key": "1", "desc": "Set Role", "goto": "set_role"},
        {"key": "2", "desc": "Cultural Origin", "goto": "cultural_origin"},
        {"key": "3", "desc": "Personality", "goto": "personality"},
        {"key": "4", "desc": "Clothing Style", "goto": "clothing_style"},
        {"key": "5", "desc": "Hairstyle", "goto": "hairstyle"},
        {"key": "6", "desc": "Affectation", "goto": "affectation"},
        {"key": "7", "desc": "Motivation", "goto": "motivation"},
        {"key": "8", "desc": "Life Goal", "goto": "life_goal"},
        {"key": "9", "desc": "Most Valued Person", "goto": "valued_person"},
        {"key": "10", "desc": "Valued Possession", "goto": "valued_possession"},
        {"key": "11", "desc": "Family Background", "goto": "family_background"},
        {"key": "12", "desc": "Origin Environment", "goto": "environment"},
        {"key": "13", "desc": "Family Crisis", "goto": "family_crisis"},
        {"key": "14", "desc": "Role-specific Lifepath", "goto": "role_specific"},
        {"key": "15", "desc": "Finish Lifepath", "goto": "finish_lifepath"},
        {"key": "q", "desc": "Quit", "goto": "exit_menu"}
    ]
    return text, options

def choose_cultural_origin(caller):
    text = "Choose your character's cultural origin:\n\n"
    options = []
    
    for i, origin in enumerate(CULTURAL_ORIGINS, 1):
        text += f"{i}. {origin}\n"
        options.append({"key": str(i), "desc": origin, "goto": ("set_cultural_origin", {"origin": origin})})
    
    options.append({"key": "b", "desc": "Back", "goto": "start_lifepath"})
    return text, options

def set_cultural_origin(caller, origin):
    cs = caller.account.character_sheet
    cs.cultural_origin = origin
    cs.save()
    
    text = f"Your cultural origin has been set to: {origin}\n"
    text += "Next, let's choose your personality."
    
    options = [
        {"key": "1", "desc": "Continue", "goto": "choose_personality"},
        {"key": "b", "desc": "Back", "goto": "choose_cultural_origin"}
    ]
    
    return text, options

# Add more functions for other lifepath steps...

def exit_menu(caller):
    text = "Exiting the Lifepath creation process. Your progress has been saved."
    return text, None

def cultural_origin(caller):
    return create_menu("Cultural Origin", CULTURAL_ORIGINS, "cultural_origin")

def personality(caller):
    return create_menu("Personality", PERSONALITIES, "personality")

def clothing_style(caller):
    return create_menu("Clothing Style", CLOTHING_STYLES, "clothing_style")

def hairstyle(caller):
    return create_menu("Hairstyle", HAIRSTYLES, "hairstyle")

def affectation(caller):
    return create_menu("Affectation", AFFECTATIONS, "affectation")

def motivation(caller):
    return create_menu("Motivation", MOTIVATIONS, "motivation")

def life_goal(caller):
    return create_menu("Life Goal", LIFE_GOALS, "life_goal")

def valued_person(caller):
    return create_menu("Most Valued Person", VALUED_PERSON, "valued_person")

def valued_possession(caller):
    return create_menu("Valued Possession", VALUED_POSSESSION, "valued_possession")

def family_background(caller):
    return create_menu("Family Background", FAMILY_BACKGROUND, "family_background")

def environment(caller):
    return create_menu("Origin Environment", ENVIRONMENT, "environment")

def family_crisis(caller):
    return create_menu("Family Crisis", FAMILY_CRISIS, "family_crisis")

def role_specific(caller):
    cs = caller.account.character_sheet
    if not cs.role:
        text = "You need to select a role first. Use the 'Set Role' option in the main menu to set your role."
        options = [{"key": "0", "desc": "Return to main menu", "goto": "start_lifepath"}]
        return text, options
    
    role_options = ROLE_SPECIFIC_LIFEPATHS.get(cs.role, [])
    if not role_options:
        text = f"No specific lifepath options for {cs.role}."
        options = [{"key": "0", "desc": "Return to main menu", "goto": "start_lifepath"}]
        return text, options
    
    text = f"Choose a {cs.role}-specific lifepath option:"
    options = []
    for i, (question, choices) in enumerate(role_options, 1):
        options.append({"key": str(i), "desc": question, "goto": ("role_specific_choice", {"question": question, "choices": choices})})
    options.append({"key": "0", "desc": "Go back", "goto": "start_lifepath"})
    return text, options

def role_specific_choice(caller, raw_string, **kwargs):
    question = kwargs['question']
    choices = kwargs['choices']
    field = question.lower().replace(' ', '_').replace('?', '').replace('/', '_').replace("'", '').strip()
    return create_menu(question, choices, field)

def create_menu(title, choices, field):
    text = f"Choose your {title}:"
    options = []
    for i, choice in enumerate(choices, 1):
        options.append({"key": str(i), "desc": choice, "goto": ("set_field", {"field": field, "value": choice})})
    options.append({"key": "0", "desc": "Go back", "goto": "start_lifepath"})
    return text, options

def set_field(caller, raw_string, **kwargs):
    field = kwargs['field']
    value = kwargs['value']
    
    cs = caller.account.character_sheet
    
    db_field = field.lower().replace(' ', '_').replace('?', '').replace('/', '_').strip()
    
    if hasattr(cs, db_field):
        setattr(cs, db_field, value)
        try:
            cs.save()
            caller.msg(f"Your {field.replace('_', ' ').title()} has been set to: {value}")
        except Exception as e:
            caller.msg(f"Error saving field: {str(e)}")
    else:
        caller.msg(f"Error: Field '{db_field}' does not exist on the character sheet. Please contact an admin.")
    
    return start_lifepath(caller)

def finish_lifepath(caller):
    """
    Finish the lifepath creation process.
    """
    caller.msg("Lifepath creation complete! Use 'sheet/lifepath' to view your lifepath details.")
    return None  # This will exit the menu system

def set_role(caller):
    text = "Choose your role:"
    options = [
        {"key": "1", "desc": "Rockerboy", "goto": ("set_role_helper", {"role": "Rockerboy"})},
        {"key": "2", "desc": "Solo", "goto": ("set_role_helper", {"role": "Solo"})},
        {"key": "3", "desc": "Netrunner", "goto": ("set_role_helper", {"role": "Netrunner"})},
        {"key": "4", "desc": "Tech", "goto": ("set_role_helper", {"role": "Tech"})},
        {"key": "5", "desc": "Medtech", "goto": ("set_role_helper", {"role": "Medtech"})},
        {"key": "6", "desc": "Media", "goto": ("set_role_helper", {"role": "Media"})},
        {"key": "7", "desc": "Exec", "goto": ("set_role_helper", {"role": "Exec"})},
        {"key": "8", "desc": "Lawman", "goto": ("set_role_helper", {"role": "Lawman"})},
        {"key": "9", "desc": "Fixer", "goto": ("set_role_helper", {"role": "Fixer"})},
        {"key": "10", "desc": "Nomad", "goto": ("set_role_helper", {"role": "Nomad"})},
        {"key": "0", "desc": "Go back", "goto": "start_lifepath"}
    ]
    return text, options

def set_role_helper(caller, raw_string, **kwargs):
    role = kwargs.get('role')
    if not role:
        caller.msg("Error: No role selected. Please try again.")
        return "set_role"
    
    cs = caller.account.character_sheet
    cs.role = role
    cs.save()
    caller.msg(f"Your role has been set to: {role}")
    
    # Return to the main menu
    return start_lifepath(caller)