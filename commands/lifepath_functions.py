from world.lifepath_dictionary import CULTURAL_ORIGINS, CULTURAL_ORIGIN_LANGUAGES, PERSONALITIES, CLOTHING_STYLES, HAIRSTYLES, AFFECTATIONS, MOTIVATIONS, LIFE_GOALS, ROLE_SPECIFIC_LIFEPATHS, VALUED_PERSON, VALUED_POSSESSION, FAMILY_BACKGROUND, ENVIRONMENT, FAMILY_CRISIS
from world.lifepath import undo_neuroport_choice
from world.cyberpunk_sheets.models import CharacterSheet
from django.db import IntegrityError

def start_lifepath(caller):
    try:
        cs = caller.character_sheet
    except AttributeError:
        caller.msg("Error: You don't have a character sheet. Please contact an admin.")
        return None, None

    if not cs:
        caller.msg("You don't have a character sheet. Please contact an admin.")
        return None, None

    text = "Welcome to the Cyberpunk RED Lifepath creation process!\n"
    text += "This will guide you through creating your character's background.\n"
    if cs.role:
        text += f"\nCurrent Role: {cs.role}\n"
    else:
        text += "\nIMPORTANT: You haven't set a role yet. Choose 'Set Role' to define your character's role.\n"
    text += "Choose an aspect to define:"
    options = [
        {"key": "1", "desc": "Set Role", "goto": "set_role"},
        {"key": "2", "desc": "Cultural Origin", "goto": "choose_cultural_origin"},
        {"key": "3", "desc": "Personality", "goto": "personality"},
        {"key": "4", "desc": "Clothing Style", "goto": "clothing_style"},
        {"key": "5", "desc": "Hairstyle", "goto": "hairstyle"},
        {"key": "6", "desc": "Affectation", "goto": "affectation"},
        {"key": "7", "desc": "Motivation", "goto": "motivation"},
        {"key": "8", "desc": "Life Goal", "goto": "life_goal"},
        {"key": "9", "desc": "Most Valued Person", "goto": "valued_person"},
        {"key": "10", "desc": "Valued Possession", "goto": "valued_possession"},
        {"key": "11", "desc": "Family Background", "goto": "family_background"},
        {"key": "12", "desc": "Neuroport (Yes/No)", "goto": "neuroport_option"},
        {"key": "13", "desc": "Origin Environment", "goto": "environment"},
        {"key": "14", "desc": "Family Crisis", "goto": "family_crisis"},
        {"key": "15", "desc": "Role-specific Lifepath", "goto": "role_specific"},
        {"key": "16", "desc": "Finish Lifepath", "goto": "finish_lifepath"},
        {"key": "q", "desc": "Quit", "goto": "exit_menu"}
    ]
    return text, options

def choose_cultural_origin(caller):
    text = "Choose your character's cultural origin:\n\n"
    options = []
    
    for i, origin in enumerate(CULTURAL_ORIGINS, 1):
        options.append({"key": str(i), "desc": origin, "goto": ("set_cultural_origin", {"origin": origin})})
    
    options.append({"key": "b", "desc": "Back", "goto": "start_lifepath"})
    return text, options

def set_cultural_origin(caller, raw_string, **kwargs):
    origin = kwargs.get('origin')
    cs = caller.character_sheet

    # Clear previous languages associated with old cultural origin (before overwriting)
    old_origin = getattr(cs, 'cultural_origin', '') or ''
    if old_origin:
        cs.clear_cultural_languages(old_origin)

    cs.cultural_origin = origin
    cs.save()
    
    caller.msg(f"Your Cultural Origin has been set to: {origin}")
    
    # Proceed directly to language selection
    return choose_language(caller, origin=origin)

def choose_language(caller, raw_string="", **kwargs):
    origin = kwargs.get("origin")
    languages = CULTURAL_ORIGIN_LANGUAGES.get(origin, [])
    
    text = f"Choose a language you know from your {origin} background:\n\n"
    options = []
    
    for i, lang in enumerate(languages, 1):
        options.append({"key": str(i), "desc": lang, "goto": ("set_language", {"language": lang})})
    
    options.append({"key": "b", "desc": "Back", "goto": "choose_cultural_origin"})
    return text, options

def set_language(caller, raw_string, **kwargs):
    language = kwargs.get("language")
    cs = caller.character_sheet
    
    cs.add_language(language, 4)
    
    caller.msg(f"You've gained full fluency in {language}.")
    
    # Return to the main menu
    return start_lifepath(caller)

# Add more functions for other lifepath steps...

def exit_menu(caller):
    text = "Exiting the Lifepath creation process. Your progress has been saved."
    return text, None

def cultural_origin(caller):
    return choose_cultural_origin(caller)

def choose_cultural_origin(caller):
    text = "Choose your character's cultural origin:\n\n"
    text += "(Note: Changing your cultural origin will reset your cultural language.)\n\n"
    options = []
    
    for i, origin in enumerate(CULTURAL_ORIGINS, 1):
        options.append({"key": str(i), "desc": origin, "goto": ("set_cultural_origin", {"origin": origin})})
    
    options.append({"key": "b", "desc": "Back", "goto": "start_lifepath"})
    return text, options

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


def neuroport_option(caller):
    """Neuroport choice: 1=Yes (free cyberware), 2=No (500 eb)."""
    desc = (
        "In the 2070s, most parents have done all they can to give their kids a Neuroport. "
        "This handy piece of cyberware is so ubiquitous that almost everyone has one. "
        "Do you have a neuroport?"
    )
    text = f"|c{desc}|n\n\n  |w1|n. Yes (free Neuroport)\n  |w2|n. No (500 eurodollars)\n\n  |w0|n. Back\n"
    options = [
        {"key": "1", "desc": "Yes", "goto": ("set_neuroport", {"has_neuroport": True})},
        {"key": "2", "desc": "No", "goto": ("set_neuroport", {"has_neuroport": False})},
        {"key": "0", "desc": "Back", "goto": "start_lifepath"},
    ]
    return text, options


def set_neuroport(caller, raw_string, has_neuroport=True, **kwargs):
    """Apply neuroport choice: grant cyberware or 500 eb. Store in db.lifepath.
    Undoes previous neuroport choice first (removes Neuroport or deducts 500 eb)."""
    lp = getattr(caller.db, "lifepath", None) or {}
    if not isinstance(lp, dict):
        lp = {}
    ok, blocked_msg = undo_neuroport_choice(caller, lp)
    if not ok:
        if blocked_msg:
            caller.msg(blocked_msg)
        return start_lifepath(caller)

    lp["neuroport_option"] = "yes" if has_neuroport else "no"
    caller.db.lifepath = lp

    char = getattr(caller, "character", caller) if hasattr(caller, "character") else caller
    sheet = getattr(char, "character_sheet", None) or getattr(caller, "character_sheet", None)

    if has_neuroport and sheet:
        try:
            from world.cyberware.models import Cyberware
            from world.inventory.models import Inventory, CyberwareInstance
            cw = Cyberware.objects.filter(name__iexact="Neuroport").first()
            if cw:
                inventory, _ = Inventory.get_or_create_for_character(char)
                if not inventory.cyberware.filter(cyberware__name__iexact="Neuroport", installed=True).exists():
                    inst = CyberwareInstance.objects.create(cyberware=cw, character_sheet=sheet, installed=True)
                    inventory.cyberware.add(inst)
                    if hasattr(sheet, "calculate_humanity_loss"):
                        sheet.calculate_humanity_loss()
                    sheet.save()
                    caller.msg("You received a free Neuroport!")
            else:
                caller.msg("Neuroport cyberware not found.")
        except Exception as e:
            caller.msg(f"Error granting Neuroport: {e}")
    elif not has_neuroport:
        from world.cyberpunk_sheets.services import CharacterMoneyService
        CharacterMoneyService.add_money(char, 500)
        caller.msg("You received 500 eurodollars (saved from not buying cyberware).")

    return start_lifepath(caller)


def environment(caller):
    return create_menu("Origin Environment", ENVIRONMENT, "environment")

def family_crisis(caller):
    return create_menu("Family Crisis", FAMILY_CRISIS, "family_crisis")

def role_specific(caller):
    try:
        cs = caller.character_sheet
    except AttributeError:
        caller.msg("Error: You don't have a character sheet. Please contact an admin.")
        return None, None

    if not cs:
        caller.msg("You don't have a character sheet. Please contact an admin.")
        return None, None

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
    
    try:
        cs = caller.character_sheet
    except AttributeError:
        # Create a new character sheet if one doesn't exist
        cs = CharacterSheet.objects.create(character=caller)
        caller.db.character_sheet_id = cs.id
        caller.msg("A new character sheet has been created for you.")

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
    
    try:
        cs = caller.character_sheet
    except AttributeError:
        # Create a new character sheet if one doesn't exist
        cs = CharacterSheet.objects.create(character=caller)
        caller.db.character_sheet_id = cs.id
        caller.msg("A new character sheet has been created for you.")

    cs.role = role
    cs.save()
    caller.msg(f"Your role has been set to: {role}")
    
    # Return to the main menu
    return start_lifepath(caller)

def save_lifepath_choice(caller, key, value):
    """Save a lifepath choice to the character's DB attributes."""
    caller.db[key] = value
    
    # For backward compatibility, also update character sheet
    if hasattr(caller, 'character_sheet') and caller.character_sheet:
        sheet = caller.character_sheet
        if hasattr(sheet, key):
            setattr(sheet, key, value)
            sheet.save(skip_recalculation=True)
    
    return f"You have chosen {value}."