"""
Cyberpunk RED Lifepath tables for character background generation.
2077 tables: roll 2d6 (cultural region 2-12), 1d10, or 1d6 depending on table.
Legacy (2020/RED) options kept commented for posterity.
"""

import ast
import json
import re
import random

# 2077: Roll 2d6 (2-12) for cultural region. Index 0-10 map to rolls 2-12.
CULTURAL_ORIGINS = [
    {"region": "North American", "languages": ["English", "Streetslang"]},           # 2
    {"region": "Central American", "languages": ["Spanish", "Streetslang"]},         # 3
    {"region": "South American", "languages": ["Spanish", "Portuguese", "Streetslang"]},  # 4
    {"region": "Western European", "languages": ["English", "French", "German", "Italian", "Spanish"]},  # 5
    {"region": "Eastern European", "languages": ["Russian", "Ukrainian", "Polish", "Greek"]},  # 6
    {"region": "Middle Eastern/North African", "languages": ["Arabic", "Farsi", "Turkish", "Hebrew"]},  # 7
    {"region": "Sub-Saharan African", "languages": ["Swahili", "Hausa", "Yoruba", "Zulu", "Amharic"]},  # 8
    {"region": "South Asian", "languages": ["Hindi", "Bengali", "Punjabi", "Tamil", "Telugu"]},  # 9
    {"region": "South East Asian", "languages": ["Vietnamese", "Thai", "Burmese", "Lao", "Khmer", "Tagalog", "Malay"]},  # 10
    {"region": "East Asian", "languages": ["Mandarin", "Cantonese", "Japanese", "Korean"]},  # 11
    {"region": "Oceania/Pacific Islander", "languages": ["English", "Maori"]},      # 12
]
# Legacy CULTURAL_ORIGINS (1d10): South/Central American combined, Oceanian vs Oceania

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

# 2077: Personal Style - Roll 1d6, pick one from each column (wardrobe, length/style, color)
PERSONAL_STYLE = [
    {
        "wardrobe": "Entropism. Functional but haphazard, putting necessity over style.",
        "length_style": "Classic mohawk",
        "color": "Multi-hued",
    },
    {
        "wardrobe": "Kitsch. A throwback, putting style over substance with bright colors and flashy fashion.",
        "length_style": "Short and styled",
        "color": "One bright color",
    },
    {
        "wardrobe": "Neo-Militarism. Utilitarian and harsh, putting substance over style.",
        "length_style": "Short and unkempt",
        "color": "Natural color",
    },
    {
        "wardrobe": "Neo-Kitsch. A return to classic fashions, mixing the old with the new to include substance and style.",
        "length_style": "Shaved close or bald",
        "color": "Subtly shaded",
    },
    {
        "wardrobe": "Nomad Leathers. Rarely actual leather but rough and rugged, inspired by the wandering life.",
        "length_style": "Long and styled",
        "color": "Festooned with decorations",
    },
    {
        "wardrobe": "High Fashion. Keeping up with the current trends and expensive labels, no matter what they are.",
        "length_style": "Long and unkempt",
        "color": "Different every day",
    },
    {
        "wardrobe": "Bohemian. Artsy, eclectic, mixing cultural influences and thrift finds.",
        "length_style": "Long and ratty",
        "color": "Striped or patterned",
    },
    {
        "wardrobe": "Gang Colors. You wear your crew or gang's colors and style. Family first.",
        "length_style": "Wild and all over",
        "color": "Gang colors",
    },
]
# Legacy (1d10 each)
# CLOTHING_STYLES = ["Generic Chic", "Leisurewear", "Urban Flash", "Businesswear", "High Fashion", "Bohemian", "Bag Lady Chic", "Gang Colors", "Nomad Leathers", "Asia Pop"]
# HAIRSTYLES = ["Mohawk", "Long and ratty", "Short and spiked", "Wild and all over", "Bald", "Striped", "Wild colors", "Neat and short", "Short and curly", "Long and straight"]
# Backward compat: combine 2077 color-based affectations with legacy tattoo/piercing options
AFFECTATIONS = (
    [p["color"] for p in PERSONAL_STYLE]
    + [
        "Tattoos",
        "Mirrorshades",
        "Nose rings",
        "Tongue or other piercings",
        "Ritual scars",
        "Ear or facial piercings",
        "Unusual contacts",
    ]
)
CLOTHING_STYLES = [p["wardrobe"] for p in PERSONAL_STYLE]
HAIRSTYLES = [p["length_style"] for p in PERSONAL_STYLE]

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

# 2077: Your Life Goal - Roll 1d6 or choose one
LIFE_GOALS = [
    "You need to fix a mistake you made.",
    "You want power and control.",
    "You're looking to score big and get out of the game.",
    "There's shame in your past, and you want to correct it.",
    "Fame and money, choomba!",
    "Protect the people you love in any way you can.",
    "Get rid of a bad reputation.",
    "Prove yourself to someone who doubted you.",
    "Find a place to belong.",
]
# Legacy LIFE_GOALS (1d10): ["Get rid of a bad reputation", "Gain power and control", ...]

# 2077: How do you feel about people? Roll 1d10 or choose one
FEELINGS_ABOUT_PEOPLE = [
    "You're neutral towards almost everyone.",
    "You like almost everyone.",
    "You hate almost everyone.",
    "People are tools to be used.",
    "People are obstacles in your way.",
    "Everyone is unique. Judge accordingly.",
    "Most people are trash. Judge accordingly.",
    "Forming deep connections is hard.",
    "You fall in love too quickly.",
    "All life has meaning. Cherish it.",
]

# --- Background / Family ---

# 2077: Your Original Family Background - Roll 1d10 or choose one
FAMILY_BACKGROUND = [
    "Corporate Execs. Wealthy, powerful, with servants and luxury homes. How did you end up edgerunning?",
    "Corporate Managers. Middle management still meant a decent home and a safe life. Looks like you didn't follow in their footsteps.",
    "Corporate Worker. Long hours and harsh working conditions meant you rarely saw your guardian(s) but at least you had a roof over your head and food in your belly.",
    "Nomad Pack. You grew up on the road, living in trailers and tents. You learned to drive and fight at an early age but your family was always there to care for you.",
    "Gangers. Depending on the gang, you were either part of the family or a resource to be exploited. Either way, it was a rough life.",
    "Combat Zoners. You grew up in a place completely abandoned by the rest of society. Life was a constant struggle.",
    "Urban Homeless. You lived in shanty towns, tent villages, abandoned shipping containers, and wherever else you could. Since you're still alive, you obviously learned how to survive.",
    "Megabuilding Rat. Like so many kids, you grew up in one of the megabuildings. Probably not the top floors, either. A small apartment and two meals of scop a day.",
    "Edgerunners. Your home always changed depending on the employment of the person or persons taking care of you. A luxury apartment one day, the back of someone's car the next. Now you're following in their footsteps.",
    "Everyone Else. Not everyone fits neatly into one of the above categories. You could be the kid of shopkeepers, cab drivers, joytoys, or any of a thousand others.",
    "Military family. Bases, deployments, and rigid structure shaped your childhood.",
]
# Legacy FAMILY_BACKGROUND (1d10): ["Corporate Executives", "Corporate Managers", "Corporate Technicians", ...]

# 2077: Your Environment - Roll 1d6 or choose one
CHILDHOOD_ENVIRONMENT = [
    "Ran on the street with little adult supervision",
    "In a mansion, high up in a skyscraper, or in an otherwise secure place.",
    "In a nomad pack, moving from place to place.",
    "In the heart of the combat zone, living in a wrecked building or other squat.",
    "In a megabuilding, controlled by a megacorp or the government.",
    "In an average, small dwelling or apartment in the city.",
    "In a corporate compound or company town.",
    "In an enclave of immigrants or outcasts.",
]
# Legacy CHILDHOOD_ENVIRONMENT (1d10): ["Ran on The Street...", "Spent in a safe Corp...", ...]

# 2077: Your Crisis - Roll 1d6 or choose one
FAMILY_CRISIS = [
    "Someone betrayed you or your family and you lost everything.",
    "You or your family was exiled or driven from their original home by politics or circumstances.",
    "You're all that's left of your family. The rest died or vanished.",
    "You've inherited a feud, either because of your actions or your heritage.",
    "You're in debt. Either because of your own actions or your family's.",
    "You're wanted by the law. Maybe you did it. Maybe you didn't. Either way, be careful.",
    "Major public embarrassment or scandal rocked your family.",
    "Mental or physical disability affected someone you love.",
]
# Legacy FAMILY_CRISIS (1d10): ["Your family lost everything through betrayal", ...]

# --- Friends and Enemies (2077) ---
# Friends: Roll 1d6. 1=0, 2-5=1, 6=2. For each: relationship (1d6), role (1d10), circle (1d10)
# Enemies: Roll 1d6. 1=0, 2-5=1, 6=2. For each: relationship (1d6), role (1d10), circle (1d10)

FRIEND_RELATIONSHIPS = [
    "An ex-lover you're on good terms with.",
    "Someone you grew up with.",
    "A mentor or parental figure.",
    "A former boss who remembers you fondly.",
    "An old enemy/rival you've made peace with.",
    "Someone you share a hobby with. You geek out together.",
    "Like an older sibling to you.",
    "Like a younger sibling to you.",
    "Someone you served with or went through hell with.",
]
# Legacy FRIEND_RELATIONSHIPS (1d10): ["Like an older sibling to you", ...]

# 2077: Enemy relationship (who they are to you) - Roll 1d6 or choose one
ENEMY_RELATIONSHIPS = [
    "A former friend or lover.",
    "An enemy from your childhood.",
    "An old boss who betrayed you.",
    "One of your relatives.",
    "A former partner or coworker.",
    "A mysterious figure. You don't even know they exist.",
    "Someone you wronged who hasn't forgotten.",
    "A rival in your line of work.",
]

# 2077: Role and Circle - roll 1d10 for Role, 1d10 for Circle (for friends and enemies)
ROLE_AND_CIRCLE_ROLES = [
    "None", "Fixer", "Medtech", "Tech", "Media", "Nomad", "Rocker", "Solo", "Netrunner", "Lawman", "Exec",
]
ROLE_AND_CIRCLE_CIRCLES = [
    "Combat zone resident",
    "Corporate ladder climber",
    "Edgerunning crew",
    "Emergency response/medical personnel",
    "Gang member",
    "Government employee",
    "Police or law enforcement employee",
    "News and entertainment professional",
    "Nomad pack member",
    "Retail employee",
    "Academic or researcher",
    "Street hustler or black market",
]

# Legacy enemy tables (1d10 each: who, cause, threat) - kept for _parse_enemy and old lifepath data
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
# Legacy ENEMY_TYPES
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

# 2077: Your Tragic Love Affair - Roll 1d6 or choose one
ROMANTIC_COMPLICATIONS = [
    "Your lover died, either via accident or murder.",
    "Your lover mysteriously vanished.",
    "A personal goal or vendetta came between you and your lover.",
    "Your lover was imprisoned or exiled.",
    "Your lover left you for someone else.",
    "You didn't have a lover. Maybe you're just not into it.",
    "Your lover's friends or family hate you.",
    "Distance or circumstance kept you apart.",
]
# Legacy ROMANTIC_COMPLICATIONS (1d10): ["Your lover's friends hate you", ...]

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
        "You fought in a corporate war or major conflict",
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
        "You served in an elite police or tactical unit",
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


def undo_neuroport_choice(caller, lp):
    """Undo a previous neuroport choice: remove Neuroport cyberware or deduct 500 eb.
    Returns (success, blocked_message). success=True means proceed; False means blocked.
    When blocked, caller took 500 eb and has balance < 500 (need refund to recover)."""
    neuroport = lp.get("neuroport_option") or lp.get("neuroport")
    if not neuroport:
        return True, None

    char = getattr(caller, "character", caller) if hasattr(caller, "character") else caller
    sheet = getattr(char, "character_sheet", None) or getattr(caller, "character_sheet", None)

    had_yes = str(neuroport).lower() in ("yes", "1", "true")
    had_no = str(neuroport).lower() in ("no", "2", "false")

    if had_yes and sheet:
        try:
            from world.inventory.models import Inventory
            inventory, _ = Inventory.get_or_create_for_character(char)
            inst = inventory.cyberware.filter(cyberware__name__iexact="Neuroport", installed=True).first()
            if inst:
                inst.delete()
                if hasattr(sheet, "calculate_humanity_loss"):
                    sheet.calculate_humanity_loss()
                sheet.save()
                if hasattr(caller, "msg"):
                    caller.msg("|y  >> Previous Neuroport removed (lifepath redo).|n")
        except Exception as e:
            if hasattr(caller, "msg"):
                caller.msg(f"|r  >> Error removing Neuroport: {e}|n")
        return True, None

    if had_no:
        from world.cyberpunk_sheets.services import CharacterMoneyService
        balance = CharacterMoneyService.get_balance(char)
        if balance < 500:
            return False, (
                "You previously chose not to take a Neuroport and received 500 eurodollars. "
                "To redo your lifepath, you must have at least 500 eb to 'return' that choice. "
                "Your current balance is {} eb. Use the |wrefund|n command (in chargen) "
                "to sell items back and recover eurodollars, then try again."
            ).format(balance)
        if not CharacterMoneyService.spend_money(char, 500):
            return False, "Unable to deduct 500 eb. Try again later."
        return True, None

    return True, None


def roll_d10():
    """Roll 1d10 (returns 1-10)."""
    return random.randint(1, 10)


def roll_2d6():
    """Roll 2d6 (returns 2-12)."""
    return random.randint(1, 6) + random.randint(1, 6)


def roll_table(table):
    """Roll on a table. Returns the selected item (random index)."""
    index = random.randint(0, len(table) - 1)
    return table[index]


def roll_cultural_origin():
    """Roll 2d6 for 2077 cultural region (2-12). Index = roll - 2."""
    roll = roll_2d6()
    index = roll - 2
    return CULTURAL_ORIGINS[index]


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
    """Extract enemy data. Supports 2077 format (relationship, role, circle) and legacy (who, cause, threat)."""
    who = cause = threat = None
    key_map = None
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
    # 2077 format: relationship, role, circle
    if key_map is not None:
        rel = key_map.get("relationship")
        role = key_map.get("role")
        circle = key_map.get("circle")
        if rel is not None or role is not None or circle is not None:
            return ("_2077", str(rel or "").strip(), str(role or "").strip(), str(circle or "").strip())

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
    feelings = lifepath_data.get('feelings_about_people')
    if feelings:
        lines.append(_field("Feelings About People:", feelings))
    lines.append(_field("Life Goal:", lifepath_data.get('life_goal', 'Unknown')))
    lines.append("")
    lines.append(sheet_section("Past", width=80))
    lines.append(_field("Family Background:", lifepath_data.get('family_background', 'Unknown')))
    neuroport = lifepath_data.get('neuroport_option') or lifepath_data.get('neuroport')
    if neuroport:
        neuroport_str = "Yes (free Neuroport)" if str(neuroport).lower() == "yes" else "No (+500 eb)"
        lines.append(_field("Neuroport:", neuroport_str))
    lines.append(_field("Childhood:", lifepath_data.get('childhood_environment', 'Unknown')))
    lines.append(_field("Family Crisis:", lifepath_data.get('family_crisis', 'Unknown')))
    lines.append("")
    lines.append(sheet_section("Connections", width=80))
    friends = lifepath_data.get("friends", [])
    if friends:
        lines.append(_field("Friends:", f"{len(friends)} total"))
        for i, f in enumerate(friends, 1):
            if isinstance(f, dict):
                rel = f.get("relationship", "")
                role = f.get("role", "")
                circle = f.get("circle", "")
                if role or circle:
                    lines.append(_list_item(i, f"{rel or '?'} | Role: {role or '?'} | Circle: {circle or '?'}"))
                else:
                    lines.append(_list_item(i, rel or str(f)))
            else:
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
            parsed = _parse_enemy(e)
            if parsed and parsed[0] == "_2077":
                _, rel, role, circle = parsed
                lines.append(_list_item(i, f"{rel or '?'} | Role: {role or '?'} | Circle: {circle or '?'}"))
            elif len(parsed) >= 3:
                who, cause, threat = parsed
                if who is not None or cause is not None or threat is not None:
                    lines.append(_list_item(i, f"{who or '?'} - {cause or '?'}"))
                    lines.append(_list_field("Threat", threat or '?'))
                else:
                    lines.append(_list_item(i, e))
            else:
                lines.append(_list_item(i, e))

    lines.append(_field("Romantic Life:", lifepath_data.get('romantic', 'Unknown')))

    role_event = lifepath_data.get("role_event")
    if role_event:
        lines.append(_field("Role Event:", role_event))

    return "\n".join(lines)
