"""
Cyberpunk RED Lifepath tables for character background generation.
Each table is a list indexed 0-9 (roll 1d10, subtract 1 for index).
"""

import ast
import json
import re
import random

CULTURAL_ORIGINS = [
    {"region": "North American", "languages": ["English", "Streetslang"]},
    {"region": "South/Central American", "languages": ["Spanish", "Portuguese"]},
    {"region": "Western European", "languages": ["English", "French", "German", "Italian", "Spanish"]},
    {"region": "Eastern European", "languages": ["Russian", "Ukrainian", "Polish", "Greek"]},
    {"region": "Middle Eastern/North African", "languages": ["Arabic", "Farsi", "Turkish", "Hebrew"]},
    {"region": "Sub-Saharan African", "languages": ["Swahili", "Hausa", "Yoruba", "Zulu", "Amharic"]},
    {"region": "South Asian", "languages": ["Hindi", "Bengali", "Punjabi", "Tamil", "Telugu"]},
    {"region": "South East Asian", "languages": ["Vietnamese", "Thai", "Burmese", "Lao", "Khmer", "Tagalog", "Malay"]},
    {"region": "East Asian", "languages": ["Mandarin", "Cantonese", "Japanese", "Korean"]},
    {"region": "Oceanian/Pacific Islander", "languages": ["English", "Maori"]},
]

PERSONALITY_TRAITS = [
    "Shy and secretive",
    "Rebellious, antisocial, and violent",
    "Arrogant, proud, and aloof",
    "Moody, rash, and headstrong",
    "Picky, fussy, and nervous",
    "Stable and serious",
    "Silly and fluffheaded",
    "Sneaky and deceptive",
    "Intellectual and detached",
    "Friendly and outgoing",
]

CLOTHING_STYLES = [
    "Generic Chic",
    "Leisurewear",
    "Urban Flash",
    "Businesswear",
    "High Fashion",
    "Bohemian",
    "Bag Lady Chic",
    "Gang Colors",
    "Nomad Leathers",
    "Asia Pop",
]

HAIRSTYLES = [
    "Mohawk",
    "Long and ratty",
    "Short and spiked",
    "Wild and all over",
    "Bald",
    "Striped",
    "Wild colors",
    "Neat and short",
    "Short and curly",
    "Long and straight",
]

AFFECTATIONS = [
    "Tattoos",
    "Mirrorshades",
    "Ritual scars",
    "Spiked gloves",
    "Nose rings",
    "Tongue or other piercings",
    "Strange fingernail implants",
    "Unusual contacts",
    "Fingerless gloves",
    "Strange haircolor",
]

MOTIVATIONS = [
    "Money",
    "Honor",
    "Your word",
    "Honesty",
    "Knowledge",
    "Vengeance",
    "Love",
    "Power",
    "Family",
    "Friendship",
]

LIFE_GOALS = [
    "Get rid of a bad reputation",
    "Gain power and control",
    "Get off The Street no matter what it takes",
    "Cause pain and suffering to anyone who crosses you",
    "Live down your past life and try to forget it",
    "Hunt down those responsible for your misfortune and make them pay",
    "Get what's rightfully yours",
    "Save, if possible, parsecs who are important to you",
    "Get to the top, no matter what",
    "Control everything around you",
]

# --- Background / Family ---

FAMILY_BACKGROUND = [
    "Corporate Executives",
    "Corporate Managers",
    "Corporate Technicians",
    "Nomad Pack",
    "Ganger Family",
    "Combat Zoners",
    "Urban Homeless",
    "Megabuilding Warren Rats",
    "Reclaimers",
    "Edgerunners",
]

CHILDHOOD_ENVIRONMENT = [
    "Ran on The Street, with no adult supervision",
    "Spent in a safe Corp Suburban Housing",
    "In a Nomad Pack moving from place to place",
    "In a decaying, once upscale neighborhood",
    "In a defended Corporate Zone in the pointed center of the City",
    "In the heart of the Combat Zone",
    "In a huge megabuilding controlled by a Corp or a gang",
    "In the ruins of a deserted town or city",
    "In a rebuilt, post-War city area",
    "On a Nomad pack 'pirate ship' sailing the seas",
]

FAMILY_CRISIS = [
    "Your family lost everything through betrayal",
    "Your family lost everything through bad management",
    "Your family was exiled or otherwise driven from their original home/nation/corporation",
    "Your family is imprisoned, and you alone escaped",
    "Your family vanished. You are the only remaining member",
    "Your family was killed, and you were the only survivor",
    "Your family is involved in a long-term conspiracy, and you have been recruited",
    "Your family was scattered to the winds due to misfortune",
    "Your family is cursed with a hereditary feud that has lasted for generations",
    "You are the inheritor of a family debt; you must pay it off before moving on with your life",
]

# --- Friends and Enemies ---

FRIEND_RELATIONSHIPS = [
    "Like an older sibling to you",
    "Like a younger sibling to you",
    "A teacher or mentor",
    "A partner or coworker",
    "A former lover",
    "An old enemy who is now a friend",
    "A childhood friend reconnected",
    "A relative you trust completely",
    "Someone you saved (or who saved you)",
    "Connected through a shared experience",
]

ENEMY_CAUSES = [
    "Caused the loss of a friend, lover, or relative",
    "Caused a major public humiliation",
    "Caused a physical disability or disfigurement",
    "Deserted or betrayed you",
    "Turned down your offer of friendship or romance",
    "You caused the death of a friend, lover, or relative of theirs",
    "You turned down their offer of friendship or romance",
    "You caused a major public humiliation for them",
    "You deserted or betrayed them",
    "You caused a physical disability or disfigurement to them",
]

ENEMY_TYPES = [
    "An ex-friend",
    "An ex-lover",
    "A relative",
    "A childhood enemy",
    "A person working for you",
    "A person you work for",
    "A partner or coworker",
    "A boosterganger",
    "A corporate exec",
    "A government official",
]

ENEMY_THREATS = [
    "They'll go out of their way to ruin your reputation",
    "They'll go out of their way to trash your possessions",
    "They want to physically harm you",
    "They want to kill you",
    "They want to sabotage your work or relationships",
    "They want to humiliate you in public",
    "They plan a long-term vendetta against you",
    "They want to see you impoverished",
    "They want to destroy what you care about most",
    "They want revenge at any cost",
]

ROMANTIC_COMPLICATIONS = [
    "Your lover's friends hate you",
    "Your lover's family hates you",
    "Your lover has a rival who hates you",
    "You are separated by distance",
    "You are separated by a conflict",
    "You fight constantly",
    "A professional rival broke you up",
    "Your lover was kidnapped",
    "Your lover went missing",
    "Your lover died in an accident or was killed",
]

# --- Role-specific lifepath (simplified) ---

ROLE_LIFEPATH = {
    "Rockerboy": [
        "You were part of a band that broke up",
        "You were a solo act on the streets",
        "You were signed to a label that screwed you over",
        "You played backup for a big name rocker",
        "You were part of a protest movement",
        "You played clubs in the Combat Zone",
        "You recorded a viral hit on the NET",
        "You performed at corporate events",
        "You busked your way across the continent",
        "You were part of a revolutionary art collective",
    ],
    "Solo": [
        "You served in a corporate military unit",
        "You were a freelance bodyguard",
        "You worked as an assassin",
        "You were a combat instructor",
        "You served in the military and went AWOL",
        "You were a prizefighter in underground arenas",
        "You were a security consultant",
        "You protected a high-profile client",
        "You fought in the Fourth Corporate War",
        "You were part of a mercenary unit",
    ],
    "Netrunner": [
        "You hacked a corporate database for fun",
        "You were trained by a legendary netrunner",
        "You worked for a data brokerage",
        "You barely survived a run through a hostile architecture",
        "You wrote a famous program",
        "You were part of an underground hacker collective",
        "You hacked your school records",
        "You ran data for a fixer",
        "You cracked corporate ICE for a living",
        "You accidentally unleashed something from the old NET",
    ],
    "Tech": [
        "You built your first device as a kid",
        "You apprenticed under a master tech",
        "You worked in a corpo R&D lab",
        "You ran a repair shop in the Combat Zone",
        "You designed custom cyberware",
        "You built weapons for a gang",
        "You maintained vehicles for a Nomad pack",
        "You reverse-engineered corporate tech",
        "You invented something that changed your life",
        "You worked the assembly lines and dreamed bigger",
    ],
    "Medtech": [
        "You learned medicine in a war zone",
        "You were a corporate medical researcher",
        "You ran a ripperdoc clinic",
        "You worked trauma team",
        "You were a military medic",
        "You treated patients no one else would",
        "You developed a new pharmaceutical",
        "You worked in a hospital before it was bombed",
        "You patched up edgerunners for a living",
        "You studied under a brilliant but unorthodox doctor",
    ],
    "Media": [
        "You exposed a corporate conspiracy",
        "You were an investigative reporter",
        "You ran an underground news feed",
        "You were a war correspondent",
        "You exposed gang activity in your neighborhood",
        "You were a popular NET blogger",
        "You worked for a major screamsheet",
        "You documented life in the Combat Zone",
        "You uncovered government corruption",
        "You were a talk show host who asked the wrong questions",
    ],
    "Lawman": [
        "You joined the force to make a difference",
        "You were a corporate security officer",
        "You served in the NCPD MAXTAC unit",
        "You investigated organized crime",
        "You were an undercover agent",
        "You worked the beat in the Combat Zone",
        "You were a private investigator",
        "You served as a detective",
        "You were assigned to a special task force",
        "You lost a partner and it changed you",
    ],
    "Exec": [
        "You climbed the corporate ladder ruthlessly",
        "You inherited a position through family connections",
        "You survived a hostile corporate takeover",
        "You managed a corporate division",
        "You negotiated major corporate deals",
        "You were part of a corporate espionage division",
        "You managed corporate assets in a war zone",
        "You built a department from nothing",
        "You were a rising star before a scandal",
        "You played corporate politics and won (mostly)",
    ],
    "Fixer": [
        "You started as a small-time fence",
        "You ran deals in the Combat Zone",
        "You built a network of contacts across the city",
        "You brokered a deal that made your reputation",
        "You worked as a talent scout for edgerunners",
        "You ran a nightclub as a front",
        "You smuggled goods across borders",
        "You were the go-to person for impossible requests",
        "You managed a stable of freelancers",
        "You played every side and somehow survived",
    ],
    "Nomad": [
        "You grew up in a Nomad pack on the road",
        "You left your pack to find your own way",
        "You served as a pack scout and outrider",
        "You drove convoys through dangerous territory",
        "You were part of a pack that was destroyed",
        "You maintained the pack's vehicles",
        "You traded with other packs across the badlands",
        "You fought off raiders attacking your family",
        "You were exiled from your pack",
        "You led a migration to new territory",
    ],
}


def roll_d10():
    """Roll 1d10 (returns 1-10)."""
    return random.randint(1, 10)


def roll_table(table):
    """Roll on a d10 table (list of 10 items). Returns the selected item."""
    index = random.randint(0, len(table) - 1)
    return table[index]


def generate_lifepath(role_name=None, num_friends=None, num_enemies=None):
    """Generate a complete random lifepath.

    Args:
        role_name: If provided, includes role-specific lifepath event.
        num_friends: Number of friends to generate (random 1-4 if None).
        num_enemies: Number of enemies to generate (random 0-3 if None).

    Returns:
        Dict with all lifepath sections.
    """
    if num_friends is None:
        num_friends = random.randint(1, 4)
    if num_enemies is None:
        num_enemies = random.randint(0, 3)

    cultural = roll_table(CULTURAL_ORIGINS)

    lifepath = {
        "cultural_region": cultural["region"],
        "cultural_languages": cultural["languages"],
        "personality": roll_table(PERSONALITY_TRAITS),
        "clothing_style": roll_table(CLOTHING_STYLES),
        "hairstyle": roll_table(HAIRSTYLES),
        "affectation": roll_table(AFFECTATIONS),
        "motivation": roll_table(MOTIVATIONS),
        "life_goal": roll_table(LIFE_GOALS),
        "family_background": roll_table(FAMILY_BACKGROUND),
        "childhood_environment": roll_table(CHILDHOOD_ENVIRONMENT),
        "family_crisis": roll_table(FAMILY_CRISIS),
        "friends": [],
        "enemies": [],
        "romantic": roll_table(ROMANTIC_COMPLICATIONS),
    }

    for _ in range(num_friends):
        lifepath["friends"].append(roll_table(FRIEND_RELATIONSHIPS))

    for _ in range(num_enemies):
        lifepath["enemies"].append({
            "who": roll_table(ENEMY_TYPES),
            "cause": roll_table(ENEMY_CAUSES),
            "threat": roll_table(ENEMY_THREATS),
        })

    if role_name and role_name in ROLE_LIFEPATH:
        lifepath["role_event"] = roll_table(ROLE_LIFEPATH[role_name])

    return lifepath


def _to_plain_python(obj):
    """Convert Evennia SaverDict/SaverList to plain dict/list for reliable access."""
    if obj is None:
        return None
    if hasattr(obj, "items") and hasattr(obj, "keys") and not isinstance(obj, (str, bytes)):
        return {str(k): _to_plain_python(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)) or (hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, dict))):
        try:
            return [_to_plain_python(item) for item in obj]
        except (TypeError, ValueError):
            return list(obj) if not isinstance(obj, list) else obj
    return obj


def _parse_enemy(e):
    """Extract (who, cause, threat) from an enemy in any supported format."""
    who = cause = threat = None
    # 1. Dict or dict-like (SaverDict, etc.)
    if isinstance(e, dict):
        key_map = {str(k).strip().lower(): v for k, v in e.items()}
        who = key_map.get("who")
        cause = key_map.get("cause")
        threat = key_map.get("threat")
    elif hasattr(e, "items") and hasattr(e, "keys"):
        try:
            d = dict(e)
            key_map = {str(k).strip().lower(): v for k, v in d.items()}
            who = key_map.get("who")
            cause = key_map.get("cause")
            threat = key_map.get("threat")
        except (TypeError, ValueError):
            pass
    # 2. Tuple/list (who, cause, threat)
    elif isinstance(e, (list, tuple)) and len(e) >= 3:
        who, cause, threat = e[0], e[1], e[2]
    # 3. String: try ast.literal_eval, then json.loads
    elif isinstance(e, str):
        s = e.strip()
        for parse_fn in (ast.literal_eval, json.loads):
            try:
                parsed = parse_fn(s)
                if isinstance(parsed, dict):
                    who = parsed.get("who")
                    cause = parsed.get("cause")
                    threat = parsed.get("threat")
                    break
                if isinstance(parsed, (list, tuple)) and len(parsed) >= 3:
                    who, cause, threat = parsed[0], parsed[1], parsed[2]
                    break
            except (SyntaxError, ValueError, TypeError):
                continue
    # 4. Object with dict-like repr (e.g. SaverDict that didn't convert)
    if who is None and cause is None and threat is None:
        s = str(e)
        for parse_fn in (ast.literal_eval, json.loads):
            try:
                parsed = parse_fn(s)
                if isinstance(parsed, dict):
                    who = parsed.get("who")
                    cause = parsed.get("cause")
                    threat = parsed.get("threat")
                    break
            except (SyntaxError, ValueError, TypeError):
                continue
        # 5. Regex for Python repr when ast fails (apostrophes in values)
        if who is None and cause is None and threat is None and "'who'" in s:
            try:
                who_m = re.search(r"'who'\s*:\s*'((?:[^'\\]|\\.)*)'", s)
                cause_m = re.search(r"'cause'\s*:\s*'((?:[^'\\]|\\.)*)'", s)
                threat_m = re.search(r"'threat'\s*:\s*'((?:[^'\\]|\\.)*)'", s)
                if who_m:
                    who = who_m.group(1).replace("\\'", "'")
                if cause_m:
                    cause = cause_m.group(1).replace("\\'", "'")
                if threat_m:
                    threat = threat_m.group(1).replace("\\'", "'")
            except Exception:
                pass
    # Ensure string values for display (handles non-string from DB/serialization)
    if who is not None:
        who = str(who).strip() or None
    if cause is not None:
        cause = str(cause).strip() or None
    if threat is not None:
        threat = str(threat).strip() or None
    return (who, cause, threat)


def format_lifepath(lifepath_data):
    """Format lifepath data into display text (sheet-style formatting)."""
    if not lifepath_data:
        return "No lifepath generated."

    # Normalize to plain Python (handles Evennia SaverDict/SaverList from db attributes)
    try:
        lifepath_data = _to_plain_python(lifepath_data)
    except Exception:
        pass  # Use original if conversion fails
    if not lifepath_data:
        return "No lifepath generated."

    from world.utils.formatting import sheet_section
    from world.utils.ansi_utils import wrap_ansi

    LABEL_WIDTH = 20
    VALUE_WIDTH = 80 - LABEL_WIDTH - 1  # 59
    LIST_INDENT = 2
    LIST_LABEL_WIDTH = 20
    LIST_VALUE_WIDTH = 80 - LIST_INDENT - LIST_LABEL_WIDTH - 1  # 57

    def _field(label, value):
        """Format label-value pair with wrapped, indented continuation lines."""
        wrapped = wrap_ansi(str(value), width=VALUE_WIDTH)
        value_lines = wrapped.split('\n')
        out = [f"|y{label:<{LABEL_WIDTH}}|n {value_lines[0]}"]
        for line in value_lines[1:]:
            out.append(f"{' ' * (LABEL_WIDTH + 1)}{line}")
        return "\n".join(out)

    def _list_item(num, value):
        """Format numbered list item with wrapped, indented continuation lines."""
        label = f"{num}."
        wrapped = wrap_ansi(str(value), width=LIST_VALUE_WIDTH)
        value_lines = wrapped.split('\n')
        out = [f"  |y{label:<{LIST_LABEL_WIDTH}}|n {value_lines[0]}"]
        for line in value_lines[1:]:
            out.append(f"  {' ' * LIST_LABEL_WIDTH} {line}")
        return "\n".join(out)

    def _list_field(label, value):
        """Format label: value at list indent level (left-aligned), with wrapped continuation."""
        label_str = f"{label}:"
        wrapped = wrap_ansi(str(value), width=LIST_VALUE_WIDTH)
        value_lines = wrapped.split('\n')
        out = [f"  |y{label_str:<{LIST_LABEL_WIDTH}}|n {value_lines[0]}"]
        for line in value_lines[1:]:
            out.append(f"  {' ' * LIST_LABEL_WIDTH} {line}")
        return "\n".join(out)

    lines = []
    lines.append(sheet_section("Present", width=80))
    lines.append(_field("Cultural Region:", lifepath_data.get('cultural_region', 'Unknown')))

    langs = lifepath_data.get("cultural_languages", [])
    if langs:
        lines.append(_field("Cultural Languages:", ', '.join(langs)))
    picked = lifepath_data.get("cultural_language_picked")
    if picked:
        lines.append(_field("Native Language:", f"{picked} (in skills)"))

    lines.append(_field("Personality:", lifepath_data.get('personality', 'Unknown')))
    lines.append(_field("Clothing Style:", lifepath_data.get('clothing_style', 'Unknown')))
    lines.append(_field("Hairstyle:", lifepath_data.get('hairstyle', 'Unknown')))
    lines.append(_field("Affectation:", lifepath_data.get('affectation', 'Unknown')))
    lines.append(_field("Motivation:", lifepath_data.get('motivation', 'Unknown')))
    lines.append(_field("Life Goal:", lifepath_data.get('life_goal', 'Unknown')))
    lines.append("")
    lines.append(sheet_section("Past", width=80))
    lines.append(_field("Family Background:", lifepath_data.get('family_background', 'Unknown')))
    lines.append(_field("Childhood:", lifepath_data.get('childhood_environment', 'Unknown')))
    lines.append(_field("Family Crisis:", lifepath_data.get('family_crisis', 'Unknown')))
    lines.append("")
    lines.append(sheet_section("Connections", width=80))
    friends = lifepath_data.get("friends", [])
    if friends:
        lines.append(_field("Friends:", f"{len(friends)} total"))
        for i, f in enumerate(friends, 1):
            lines.append(_list_item(i, f))

    enemies = lifepath_data.get("enemies", [])
    if enemies:
        lines.append(_field("Enemies:", f"{len(enemies)} total"))
        # Ensure plain Python types (Evennia SaverList/SaverDict may not fully convert)
        try:
            enemies = list(enemies)
            enemies = [dict(x) if hasattr(x, "items") else x for x in enemies]
        except (TypeError, ValueError):
            pass
        for i, e in enumerate(enemies, 1):
            who, cause, threat = _parse_enemy(e)
            if who is not None or cause is not None or threat is not None:
                lines.append(_list_item(i, f"{who or '?'} - {cause or '?'}"))
                # Threat line: left-aligned like list items
                lines.append(_list_field("Threat", threat or '?'))
            else:
                lines.append(_list_item(i, e))

    lines.append(_field("Romantic Life:", lifepath_data.get('romantic', 'Unknown')))

    role_event = lifepath_data.get("role_event")
    if role_event:
        lines.append(_field("Role Event:", role_event))

    return "\n".join(lines)
