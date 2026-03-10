"""
EvMenu-based interactive lifepath builder for Cyberpunk RED.
Players step through each lifepath section and can handpick or roll randomly.
Launched via the 'lifepath' command.
"""

import random
from evennia.utils.evmenu import EvMenu
from world.lifepath import (
    CULTURAL_ORIGINS, PERSONALITY_TRAITS, CLOTHING_STYLES, HAIRSTYLES,
    AFFECTATIONS, MOTIVATIONS, LIFE_GOALS, FAMILY_BACKGROUND,
    CHILDHOOD_ENVIRONMENT, FAMILY_CRISIS, FRIEND_RELATIONSHIPS,
    ENEMY_CAUSES, ENEMY_TYPES, ENEMY_THREATS, ROMANTIC_COMPLICATIONS,
    ROLE_LIFEPATH, format_lifepath, roll_table,
)


def _header(text):
    w = 78
    pad = w - len(text) - 4
    left = pad // 2
    right = pad - left
    return f"|c{'-' * left}[ {text} ]{'-' * right}|n"


def _wrap(text, width=74, indent=2):
    """Wrap text to width, preserving paragraph breaks (\\n\\n)."""
    prefix = " " * indent
    paragraphs = text.split("\n\n")
    result = []
    for para in paragraphs:
        words = para.split()
        lines = []
        current = []
        current_len = 0
        for w in words:
            add_len = len(w) + (1 if current else 0)
            if current_len + add_len <= width - indent:
                current.append(w)
                current_len += add_len
            else:
                if current:
                    lines.append(prefix + " ".join(current))
                current = [w]
                current_len = len(w)
        if current:
            lines.append(prefix + " ".join(current))
        if lines:
            result.append("\n".join(lines))
    return "\n\n".join(result) if result else ""


# Corebook descriptive text for each lifepath section
COREBOOK_DESCRIPTIONS = {
    "cultural_origin": (
        "The Cyberpunk world is multicultural and multinational. You either learn to "
        "deal with all kinds of people from all over a fractured and chaotic world, "
        "or you die the first time you look side-eye at the wrong person. Where you "
        "come from determines your native language. In RED, we assume everyone speaks "
        "Streetslang, but you probably also have another primary tongue you learned at "
        "your mother's knee. After rolling to determine your general cultural region, "
        "choose one of the languages from the list for that region. You begin with 4 "
        "points in that Language Skill. If you want your Character to speak a language "
        "that isn't represented, you can choose that language instead.\n\n"
        "Roll 1d10 or choose one:"
    ),
    "native_language": (
        "Choose one language from your cultural background. This will be added to your "
        "skills at level 4. There are hundreds of languages spoken around the world "
        "but we've listed the most commonly spoken in each region during the Time of "
        "the Red."
    ),
    "personality": (
        "This is what you're like as a person. Are you the kind of Character that "
        "stands away from the pack, aloof and calculating? A party animal who loves "
        "to get messed up? The stable and competent professional who always has a plan?\n\n"
        "Roll 1d10 or choose one:"
    ),
    "clothing_style": (
        "In Cyberpunk, what you look like is (to The Street) a snapshot of who you are. "
        "Your clothes, hairstyles and even personal touches can determine how people "
        "will relate to you, for good or for bad. Your clothing style is more about the "
        "style of clothes you favor, not the individual items.\n\n"
        "Roll 1d10 or choose one:"
    ),
    "hairstyle": (
        "How do you wear your hair? From mohawks to wild colors, your hairstyle says "
        "something about who you are in the Dark Future.\n\n"
        "Roll 1d10 or choose one:"
    ),
    "affectation": (
        "The personal touch you're never without. Tattoos, mirrorshades, ritual scars, "
        "or something stranger?\n\n"
        "Roll 1d10 or choose one:"
    ),
    "motivation": (
        "What do you value most? Money, honor, your word, honesty, knowledge, vengeance, "
        "love, power, family, or friendship? This drives your character's choices.\n\n"
        "Roll 1d10 or choose one:"
    ),
    "life_goal": (
        "You know your history, your personal style, and your turbulent love life. "
        "It's time to wrap all this up by determining what you want out of life.\n\n"
        "Roll 1d10 or choose one:"
    ),
    "family_background": (
        "Who are you and where did you originally come from? Were you born with a "
        "silver spoon in your mouth or were you using it to stab your brother so you "
        "could steal that extra bite of dead rat you both found?\n\n"
        "Roll 1d10 or choose one:"
    ),
    "childhood_environment": (
        "How did you grow up? What kind of places did you and your sibs hang out in? "
        "Safe and calm? Crazy dangerous? Massively oppressive? It's possible that "
        "something happened in your background and your environment turns out drastically "
        "different from your original family background.\n\n"
        "Roll 1d10 or choose one:"
    ),
    "family_crisis": (
        "In the Time of the Red, the world is still recovering from a world war and "
        "other disasters. Chances are, something happened to you and your family along "
        "the way. What's the story there?\n\n"
        "Roll 1d10 or choose one:"
    ),
    "friends": (
        "It's not all grim. Sometimes you link up with people who have your back. "
        "Roll 1d10 and subtract 7 (minimum 0) to see just how many friends you've "
        "made so far in your life. For each friend, choose their relationship to you."
    ),
    "friend_relationship": (
        "How is this person connected to you? Like a sibling, a mentor, a former "
        "lover, or someone from The Street?"
    ),
    "enemies": (
        "Enemies are a big part of life in the Cyberpunk world. You're going to get "
        "in someone's face sooner or later, so you might as well find out who they "
        "are, why there's a beef, and what they can do to you to even a score. "
        "Roll 1d10 and subtract 7 (minimum 0) to determine how many enemies you've made."
    ),
    "enemy_who": (
        "Who is this enemy? An ex-friend, ex-lover, estranged relative, childhood enemy, "
        "someone you work with, or something worse?"
    ),
    "enemy_cause": (
        "What caused the bad blood between you? Who was the injured party?"
    ),
    "enemy_threat": (
        "What can they throw at you when you meet again? Just themselves, a few "
        "friends, or something much bigger?"
    ),
    "romantic": (
        "It wouldn't be Cyberpunk if there was a happily ever-after, now would it? "
        "You've probably been involved with someone by now. We don't care about the "
        "ones that worked—we want to know about the ugly ones that ripped out your "
        "heart. Roll 1d10 and subtract 7 (minimum 0) to see how many tragic love "
        "affairs you've had, then choose how each ended.\n\n"
        "Roll 1d10 or choose one:"
    ),
    "role_event": (
        "Some things about life are universal. Other things are pretty specific to "
        "your role. The things a hard-bitten Lawman faces are way different from the "
        "glittering club life of a Rockerboy. This is your role-specific lifepath event.\n\n"
        "Roll 1d10 or choose one:"
    ),
}


def _build_descriptive_menu(title, description_key, options, key_field=None, show_random=True):
    """Build a menu with corebook description and numbered options."""
    desc = COREBOOK_DESCRIPTIONS.get(description_key, "")
    lines = [_header(title), ""]
    if desc:
        lines.append(_wrap(desc))
        lines.append("")
    for i, opt in enumerate(options, 1):
        if key_field and isinstance(opt, dict):
            label = opt[key_field]
        else:
            label = str(opt)
        lines.append(f"  |w{i:>2}|n. {label}")
    lines.append("")
    if show_random:
        lines.append("  |wR|n. Roll randomly")
    lines.append("  |wQ|n. Quit lifepath builder")
    lines.append("")
    return "\n".join(lines)


def _build_choice_text(title, options, key_field=None, show_random=True):
    """Build a numbered menu from a list of options (legacy, no description)."""
    return _build_descriptive_menu(title, "", options, key_field, show_random)


def _sync_lifepath_to_sheet(caller):
    """Sync caller.db.lifepath to CharacterSheet when it exists."""
    sheet = getattr(caller, 'character_sheet', None)
    if not sheet:
        return
    lp = caller.db.lifepath or {}
    # Map new lifepath fields to CharacterSheet columns
    if lp.get("cultural_region"):
        sheet.cultural_origin = lp["cultural_region"]
    if lp.get("personality"):
        sheet.personality = lp["personality"]
    if lp.get("clothing_style"):
        sheet.clothing_style = lp["clothing_style"]
    if lp.get("hairstyle"):
        sheet.hairstyle = lp["hairstyle"]
    if lp.get("affectation"):
        sheet.affectation = lp["affectation"]
    if lp.get("motivation"):
        sheet.motivation = lp["motivation"]
    if lp.get("life_goal"):
        sheet.life_goal = lp["life_goal"]
    if lp.get("family_background"):
        sheet.family_background = lp["family_background"]
    if lp.get("childhood_environment"):
        sheet.environment = lp["childhood_environment"]
    if lp.get("family_crisis"):
        sheet.family_crisis = lp["family_crisis"]
    # Store friends, enemies, romantic, role_event in db.lifepath (sheet has no columns)
    sheet.save()


# ---------------------------------------------------------------------------
# Menu nodes
# ---------------------------------------------------------------------------

def menunode_welcome(caller, raw_string, **kwargs):
    text = (
        _header("Lifepath Builder") + "\n\n"
        "  Welcome to the interactive Lifepath Builder.\n"
        "  You'll walk through each section of your character's\n"
        "  background and can either |wpick|n from a list or |wroll|n randomly.\n\n"
        "  Your choices are saved as you go. You can quit at any\n"
        "  time and your progress will be kept.\n"
    )
    options = (
        {"key": ("1", "start", "begin"), "desc": "Begin lifepath", "goto": (_begin_lifepath, {})},
        {"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"},
    )
    return text, options


def _begin_lifepath(caller, raw_string, **kwargs):
    """Clear previous lifepath data and remove old cultural language before starting fresh."""
    lp = caller.db.lifepath or {}
    old_lang = lp.get("cultural_language_picked")
    if old_lang and hasattr(caller, "remove_language"):
        try:
            caller.remove_language(old_lang)
        except Exception:
            pass
    caller.db.lifepath = {}
    return "menunode_cultural_origin"


def menunode_cultural_origin(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Cultural Origin", "cultural_origin", CULTURAL_ORIGINS, key_field="region")

    options = []
    for i, origin in enumerate(CULTURAL_ORIGINS):
        idx = str(i + 1)
        options.append({
            "key": idx,
            "desc": origin["region"],
            "goto": (_set_cultural_origin, {"index": i}),
        })
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_cultural_origin, {"index": None})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def _set_cultural_origin(caller, raw_string, index=None, **kwargs):
    if index is None:
        origin = roll_table(CULTURAL_ORIGINS)
    else:
        origin = CULTURAL_ORIGINS[index]

    lp = caller.db.lifepath or {}
    # Remove old lifepath language when changing cultural origin (redundant with _begin_lifepath but safe)
    old_lang = lp.get("cultural_language_picked")
    if old_lang and hasattr(caller, "remove_language"):
        try:
            caller.remove_language(old_lang)
        except Exception:
            pass
        lp.pop("cultural_language_picked", None)

    lp["cultural_region"] = origin["region"]
    lp["cultural_languages"] = origin["languages"]
    caller.db.lifepath = lp

    _sync_lifepath_to_sheet(caller)
    caller.msg(f"|g  >> Cultural Origin: {origin['region']}|n")
    caller.msg(f"|g  >> Languages: {', '.join(origin['languages'])}|n")
    if origin["languages"]:
        return "menunode_pick_language"
    return "menunode_personality"


def menunode_pick_language(caller, raw_string, **kwargs):
    """Let player pick one cultural language to add to skills."""
    lp = caller.db.lifepath or {}
    languages = lp.get("cultural_languages", [])
    if not languages:
        return "menunode_personality"

    desc = COREBOOK_DESCRIPTIONS.get("native_language", "")
    text = _header("Pick Your Native Language") + "\n\n"
    if desc:
        text += _wrap(desc) + "\n\n"
    for i, lang in enumerate(languages, 1):
        text += f"  |w{i:>2}|n. {lang}\n"
    text += "\n  |wR|n. Roll randomly\n  |wQ|n. Quit lifepath builder\n"
    options = []
    for i, lang in enumerate(languages):
        options.append({
            "key": str(i + 1),
            "desc": lang,
            "goto": (_set_language, {"language": lang}),
        })
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_language, {"language": None})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def _set_language(caller, raw_string, language=None, **kwargs):
    """Add picked language to skills and store in lifepath."""
    lp = caller.db.lifepath or {}
    languages = lp.get("cultural_languages", [])
    if not languages:
        return "menunode_personality"

    if language is None:
        language = roll_table(languages)

    # Remove old lifepath language if changing (e.g. from partial redo)
    old_lang = lp.get("cultural_language_picked")
    if old_lang and old_lang != language and hasattr(caller, "remove_language"):
        caller.remove_language(old_lang)

    lp["cultural_language_picked"] = language
    caller.db.lifepath = lp
    if hasattr(caller, "add_language"):
        caller.add_language(language, 4)

    _sync_lifepath_to_sheet(caller)
    caller.msg(f"|g  >> Native language: {language} (added to skills at level 4)|n")
    return "menunode_personality"


def menunode_personality(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Personality", "personality", PERSONALITY_TRAITS)
    options = []
    for i, trait in enumerate(PERSONALITY_TRAITS):
        options.append({"key": str(i + 1), "desc": trait, "goto": (_set_simple, {"field": "personality", "value": trait, "next_node": "menunode_clothing"})})
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "personality", "value": None, "table": PERSONALITY_TRAITS, "next_node": "menunode_clothing"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def menunode_clothing(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Clothing Style", "clothing_style", CLOTHING_STYLES)
    options = []
    for i, style in enumerate(CLOTHING_STYLES):
        options.append({"key": str(i + 1), "desc": style, "goto": (_set_simple, {"field": "clothing_style", "value": style, "next_node": "menunode_hairstyle"})})
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "clothing_style", "value": None, "table": CLOTHING_STYLES, "next_node": "menunode_hairstyle"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def menunode_hairstyle(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Hairstyle", "hairstyle", HAIRSTYLES)
    options = []
    for i, style in enumerate(HAIRSTYLES):
        options.append({"key": str(i + 1), "desc": style, "goto": (_set_simple, {"field": "hairstyle", "value": style, "next_node": "menunode_affectation"})})
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "hairstyle", "value": None, "table": HAIRSTYLES, "next_node": "menunode_affectation"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def menunode_affectation(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Affectation", "affectation", AFFECTATIONS)
    options = []
    for i, aff in enumerate(AFFECTATIONS):
        options.append({"key": str(i + 1), "desc": aff, "goto": (_set_simple, {"field": "affectation", "value": aff, "next_node": "menunode_motivation"})})
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "affectation", "value": None, "table": AFFECTATIONS, "next_node": "menunode_motivation"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def menunode_motivation(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("What Do You Value Most?", "motivation", MOTIVATIONS)
    options = []
    for i, mot in enumerate(MOTIVATIONS):
        options.append({"key": str(i + 1), "desc": mot, "goto": (_set_simple, {"field": "motivation", "value": mot, "next_node": "menunode_life_goal"})})
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "motivation", "value": None, "table": MOTIVATIONS, "next_node": "menunode_life_goal"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def menunode_life_goal(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Life Goal", "life_goal", LIFE_GOALS)
    options = []
    for i, goal in enumerate(LIFE_GOALS):
        options.append({"key": str(i + 1), "desc": goal, "goto": (_set_simple, {"field": "life_goal", "value": goal, "next_node": "menunode_family_background"})})
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "life_goal", "value": None, "table": LIFE_GOALS, "next_node": "menunode_family_background"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def menunode_family_background(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Family Background", "family_background", FAMILY_BACKGROUND)
    options = []
    for i, bg in enumerate(FAMILY_BACKGROUND):
        options.append({"key": str(i + 1), "desc": bg, "goto": (_set_simple, {"field": "family_background", "value": bg, "next_node": "menunode_childhood"})})
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "family_background", "value": None, "table": FAMILY_BACKGROUND, "next_node": "menunode_childhood"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def menunode_childhood(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Childhood Environment", "childhood_environment", CHILDHOOD_ENVIRONMENT)
    options = []
    for i, env in enumerate(CHILDHOOD_ENVIRONMENT):
        options.append({"key": str(i + 1), "desc": env, "goto": (_set_simple, {"field": "childhood_environment", "value": env, "next_node": "menunode_family_crisis"})})
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "childhood_environment", "value": None, "table": CHILDHOOD_ENVIRONMENT, "next_node": "menunode_family_crisis"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def menunode_family_crisis(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Family Crisis", "family_crisis", FAMILY_CRISIS)
    options = []
    for i, crisis in enumerate(FAMILY_CRISIS):
        options.append({"key": str(i + 1), "desc": crisis, "goto": (_set_simple, {"field": "family_crisis", "value": crisis, "next_node": "menunode_friends_count"})})
    options.append({"key": ("r", "random", "roll"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "family_crisis", "value": None, "table": FAMILY_CRISIS, "next_node": "menunode_friends_count"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


# --- Friends ---

def menunode_friends_count(caller, raw_string, **kwargs):
    desc = COREBOOK_DESCRIPTIONS.get("friends", "")
    text = _header("Friends") + "\n\n"
    if desc:
        text += _wrap(desc) + "\n\n"
    text += (
        "  |w0|n. No close friends\n"
        "  |w1|n. 1 friend\n"
        "  |w2|n. 2 friends\n"
        "  |w3|n. 3 friends\n"
        "  |w4|n. 4 friends\n\n"
        "  |wR|n. Roll randomly (1d10 - 7, min 0)\n"
        "  |wQ|n. Quit\n"
    )
    options = []
    for i in range(5):
        options.append({
            "key": str(i),
            "desc": f"{i} friend{'s' if i != 1 else ''}",
            "goto": (_set_friends_count, {"count": i}),
        })
    options.append({"key": ("r", "random"), "desc": "Random", "goto": (_set_friends_count, {"count": None})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def _set_friends_count(caller, raw_string, count=None, **kwargs):
    if count is None:
        count = random.randint(1, 4)
    lp = caller.db.lifepath or {}
    lp["friends"] = []
    caller.db.lifepath = lp
    caller.ndb._lifepath_friend_count = count
    caller.ndb._lifepath_friend_index = 0
    if count == 0:
        caller.msg("|g  >> No close friends.|n")
        return "menunode_enemies_count"
    return "menunode_pick_friend"


def menunode_pick_friend(caller, raw_string, **kwargs):
    idx = caller.ndb._lifepath_friend_index or 0
    total = caller.ndb._lifepath_friend_count or 1
    text = _build_descriptive_menu(
        f"Friend {idx + 1} of {total} - Relationship",
        "friend_relationship",
        FRIEND_RELATIONSHIPS,
    )
    options = []
    for i, rel in enumerate(FRIEND_RELATIONSHIPS):
        options.append({"key": str(i + 1), "desc": rel, "goto": (_add_friend, {"value": rel})})
    options.append({"key": ("r", "random"), "desc": "Roll randomly", "goto": (_add_friend, {"value": None})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def _add_friend(caller, raw_string, value=None, **kwargs):
    if value is None:
        value = roll_table(FRIEND_RELATIONSHIPS)
    lp = caller.db.lifepath or {}
    friends = lp.get("friends", [])
    friends.append(value)
    lp["friends"] = friends
    caller.db.lifepath = lp
    caller.msg(f"|g  >> Friend: {value}|n")

    idx = (caller.ndb._lifepath_friend_index or 0) + 1
    caller.ndb._lifepath_friend_index = idx
    total = caller.ndb._lifepath_friend_count or 1
    if idx >= total:
        return "menunode_enemies_count"
    return "menunode_pick_friend"


# --- Enemies ---

def menunode_enemies_count(caller, raw_string, **kwargs):
    desc = COREBOOK_DESCRIPTIONS.get("enemies", "")
    text = _header("Enemies") + "\n\n"
    if desc:
        text += _wrap(desc) + "\n\n"
    text += (
        "  |w0|n. No enemies\n"
        "  |w1|n. 1 enemy\n"
        "  |w2|n. 2 enemies\n"
        "  |w3|n. 3 enemies\n\n"
        "  |wR|n. Roll randomly (1d10 - 7, min 0)\n"
        "  |wQ|n. Quit\n"
    )
    options = []
    for i in range(4):
        options.append({
            "key": str(i),
            "desc": f"{i} enem{'ies' if i != 1 else 'y'}",
            "goto": (_set_enemies_count, {"count": i}),
        })
    options.append({"key": ("r", "random"), "desc": "Random", "goto": (_set_enemies_count, {"count": None})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def _set_enemies_count(caller, raw_string, count=None, **kwargs):
    if count is None:
        count = random.randint(0, 3)
    lp = caller.db.lifepath or {}
    lp["enemies"] = []
    caller.db.lifepath = lp
    caller.ndb._lifepath_enemy_count = count
    caller.ndb._lifepath_enemy_index = 0
    if count == 0:
        caller.msg("|g  >> No enemies.|n")
        return "menunode_romance"
    return "menunode_pick_enemy_type"


def menunode_pick_enemy_type(caller, raw_string, **kwargs):
    idx = caller.ndb._lifepath_enemy_index or 0
    total = caller.ndb._lifepath_enemy_count or 1
    text = _build_descriptive_menu(
        f"Enemy {idx + 1} of {total} - Who Are They?",
        "enemy_who",
        ENEMY_TYPES,
    )
    options = []
    for i, et in enumerate(ENEMY_TYPES):
        options.append({"key": str(i + 1), "desc": et, "goto": (_set_enemy_type, {"value": et})})
    options.append({"key": ("r", "random"), "desc": "Roll randomly", "goto": (_set_enemy_type, {"value": None})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def _set_enemy_type(caller, raw_string, value=None, **kwargs):
    if value is None:
        value = roll_table(ENEMY_TYPES)
    caller.ndb._current_enemy = {"who": value}
    caller.msg(f"|r  >> Enemy: {value}|n")
    return "menunode_pick_enemy_cause"


def menunode_pick_enemy_cause(caller, raw_string, **kwargs):
    idx = caller.ndb._lifepath_enemy_index or 0
    total = caller.ndb._lifepath_enemy_count or 1
    text = _build_descriptive_menu(
        f"Enemy {idx + 1} of {total} - What Happened?",
        "enemy_cause",
        ENEMY_CAUSES,
    )
    options = []
    for i, cause in enumerate(ENEMY_CAUSES):
        options.append({"key": str(i + 1), "desc": cause, "goto": (_set_enemy_cause, {"value": cause})})
    options.append({"key": ("r", "random"), "desc": "Roll randomly", "goto": (_set_enemy_cause, {"value": None})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def _set_enemy_cause(caller, raw_string, value=None, **kwargs):
    if value is None:
        value = roll_table(ENEMY_CAUSES)
    enemy = caller.ndb._current_enemy or {}
    enemy["cause"] = value
    caller.ndb._current_enemy = enemy
    caller.msg(f"|r  >> Cause: {value}|n")
    return "menunode_pick_enemy_threat"


def menunode_pick_enemy_threat(caller, raw_string, **kwargs):
    idx = caller.ndb._lifepath_enemy_index or 0
    total = caller.ndb._lifepath_enemy_count or 1
    text = _build_descriptive_menu(
        f"Enemy {idx + 1} of {total} - What Do They Want?",
        "enemy_threat",
        ENEMY_THREATS,
    )
    options = []
    for i, threat in enumerate(ENEMY_THREATS):
        options.append({"key": str(i + 1), "desc": threat, "goto": (_finish_enemy, {"value": threat})})
    options.append({"key": ("r", "random"), "desc": "Roll randomly", "goto": (_finish_enemy, {"value": None})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


def _finish_enemy(caller, raw_string, value=None, **kwargs):
    if value is None:
        value = roll_table(ENEMY_THREATS)
    enemy = caller.ndb._current_enemy or {}
    enemy["threat"] = value
    caller.msg(f"|r  >> Threat: {value}|n")

    lp = caller.db.lifepath or {}
    enemies = lp.get("enemies", [])
    enemies.append(enemy)
    lp["enemies"] = enemies
    caller.db.lifepath = lp

    idx = (caller.ndb._lifepath_enemy_index or 0) + 1
    caller.ndb._lifepath_enemy_index = idx
    total = caller.ndb._lifepath_enemy_count or 1
    if idx >= total:
        return "menunode_romance"
    return "menunode_pick_enemy_type"


# --- Romance ---

def menunode_romance(caller, raw_string, **kwargs):
    text = _build_descriptive_menu("Your Tragic Love Affair(s)", "romantic", ROMANTIC_COMPLICATIONS)
    options = []
    for i, rom in enumerate(ROMANTIC_COMPLICATIONS):
        options.append({"key": str(i + 1), "desc": rom, "goto": (_set_simple, {"field": "romantic", "value": rom, "next_node": "menunode_role_event"})})
    options.append({"key": ("r", "random"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "romantic", "value": None, "table": ROMANTIC_COMPLICATIONS, "next_node": "menunode_role_event"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


# --- Role Event ---

def menunode_role_event(caller, raw_string, **kwargs):
    role = getattr(caller.db, 'role', None) or (getattr(caller, 'character_sheet', None) and getattr(caller.character_sheet, 'role', None))
    if not role or role not in ROLE_LIFEPATH:
        return "menunode_summary"

    events = ROLE_LIFEPATH[role]
    text = _build_descriptive_menu(f"Role Event ({role})", "role_event", events)
    options = []
    for i, event in enumerate(events):
        options.append({"key": str(i + 1), "desc": event, "goto": (_set_simple, {"field": "role_event", "value": event, "next_node": "menunode_summary"})})
    options.append({"key": ("r", "random"), "desc": "Roll randomly", "goto": (_set_simple, {"field": "role_event", "value": None, "table": events, "next_node": "menunode_summary"})})
    options.append({"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"})
    return text, options


# --- Summary ---

def menunode_summary(caller, raw_string, **kwargs):
    lp = caller.db.lifepath or {}
    text = (
        _header("Lifepath Complete") + "\n\n"
        + format_lifepath(lp) + "\n\n"
        "  |w1|n. Accept and finish\n"
        "  |w2|n. Start lifepath over\n"
        "  |wQ|n. Quit (progress is saved)\n"
    )
    options = (
        {"key": ("1", "accept", "done"), "desc": "Accept lifepath", "goto": "menunode_finish"},
        {"key": ("2", "redo", "restart"), "desc": "Start over", "goto": (_begin_lifepath, {})},
        {"key": ("q", "quit"), "desc": "Quit", "goto": "menunode_quit"},
    )
    return text, options


def menunode_finish(caller, raw_string, **kwargs):
    _sync_lifepath_to_sheet(caller)
    caller.msg("|gLifepath accepted!|n Use |wsheet/lifepath|n to view your lifepath.")

    # If using +chargen flow (from newcommands CmdChargen), advance step
    if hasattr(caller, 'set_chargen'):
        cg = caller.db.chargen or {}
        method = cg.get("method")
        if method == "streetrat":
            caller.set_chargen(step="finish")
            caller.msg("Next: |w+chargen/finish|n to finalize.")
        elif method in ("edgerunner", "complete"):
            caller.set_chargen(step="stats")
            caller.msg("Next: |w+chargen/stats|n to roll/allocate your stats.")

    return None


def menunode_quit(caller, raw_string, **kwargs):
    _sync_lifepath_to_sheet(caller)
    caller.msg("|yLifepath builder closed. Your progress has been saved.|n")
    caller.msg("Use |wlifepath|n to continue building, or |wsheet/lifepath|n to view.")
    return None


# --- Sync to CharacterSheet ---

def _sync_lifepath_to_sheet(caller):
    """Sync caller.db.lifepath to CharacterSheet when it exists."""
    lp = caller.db.lifepath or {}
    sheet = getattr(caller, "character_sheet", None)
    if not sheet:
        return
    # Map new lifepath fields to sheet columns
    if lp.get("cultural_region"):
        sheet.cultural_origin = lp["cultural_region"]
    if lp.get("personality"):
        sheet.personality = lp["personality"]
    if lp.get("clothing_style"):
        sheet.clothing_style = lp["clothing_style"]
    if lp.get("hairstyle"):
        sheet.hairstyle = lp["hairstyle"]
    if lp.get("affectation"):
        sheet.affectation = lp["affectation"]
    if lp.get("motivation"):
        sheet.motivation = lp["motivation"]
    if lp.get("life_goal"):
        sheet.life_goal = lp["life_goal"]
    if lp.get("family_background"):
        sheet.family_background = lp["family_background"]
    if lp.get("childhood_environment"):
        sheet.environment = lp["childhood_environment"]
    if lp.get("family_crisis"):
        sheet.family_crisis = lp["family_crisis"]
    try:
        sheet.save()
    except Exception:
        pass


# --- Shared setter callback ---

def _set_simple(caller, raw_string, field=None, value=None, table=None, next_node=None, **kwargs):
    if value is None and table:
        value = roll_table(table)
    lp = caller.db.lifepath or {}
    lp[field] = value
    caller.db.lifepath = lp
    _sync_lifepath_to_sheet(caller)
    caller.msg(f"|g  >> {field.replace('_', ' ').title()}: {value}|n")
    return next_node


# --- Launcher ---

def start_lifepath_menu(caller):
    """Launch the EvMenu lifepath builder on a caller."""
    EvMenu(
        caller,
        "commands.lifepath_menu",
        startnode="menunode_welcome",
        cmdset_mergetype="Replace",
        cmd_on_exit=None,
        auto_quit=True,
        auto_look=False,
    )
