"""
+lookup command - Player-facing lookup for equipment, skills, stats, roles.
"""

from django.db.models import Q
from django.db.models.functions import Length

from evennia.commands.default.muxcommand import MuxCommand
from world.utils.formatting import header, footer, divider, section_header
from world.utils.ansi_utils import wrap_ansi
from world.cyberpunk_constants import ROLES, STATS
from world.list_data import STAT_DESCRIPTIONS, SKILL_DESCRIPTIONS, ROLE_ABILITIES
from world.inventory.models import (
    Weapon, Armor, Gear, Vehicle, Ammunition, Cyberdeck,
    WeaponAttachment,
)
from world.cyberware.models import Cyberware
from world.netrunning.deckoptions import programs, hardware, black_ice, quickhacks


def _match_item_by_words(model, name_field, words):
    """Filter model where all words appear in name_field. Returns first match, preferring shorter names."""
    if not words:
        return None
    q = Q()
    for word in words:
        q &= Q(**{f"{name_field}__icontains": word})
    return model.objects.filter(q).annotate(name_len=Length(name_field)).order_by("name_len", "name").first()


def _match_list_item_by_words(items, name_key="name", words=None):
    """Find item in list where all words appear in name. Returns best match (shortest name) or None."""
    if not words:
        return None
    matches = []
    for item in items:
        item_name = (item.get(name_key) or "").lower()
        if all(w in item_name for w in words):
            matches.append(item)
    if not matches:
        return None
    return min(matches, key=lambda m: len(m.get(name_key, "")))


def _find_item_info(name):
    """Search equipment, cyberware, and netrunning data for item. Returns (source, data) or (None, None).
    Supports exact match and partial string match (e.g. 'constitutional arms multi' finds 'Constitutional Arms Multi-Ammo Pistol').
    """
    name_lower = name.strip().lower()
    name_clean = name.strip()
    words = [w for w in name_lower.split() if w]

    # Weapons
    w = Weapon.objects.filter(name__iexact=name_clean).first()
    if not w:
        w = _match_item_by_words(Weapon, "name", words)
    if w:
        return ("Weapon", {
            "name": w.name, "description": getattr(w, "description", ""), "damage": w.damage,
            "rof": w.rof, "hands": w.hands, "concealable": w.concealable, "category": w.category,
            "value": w.value, "weight": w.weight, "clip": getattr(w, "clip", 0),
        })

    # Armor
    a = Armor.objects.filter(name__iexact=name_clean).first()
    if not a:
        a = _match_item_by_words(Armor, "name", words)
    if a:
        return ("Armor", {
            "name": a.name, "description": getattr(a, "description", ""),
            "sp": a.sp, "ev": a.ev, "locations": a.locations, "value": a.value, "weight": a.weight,
        })

    # Gear
    g = Gear.objects.filter(name__iexact=name_clean).first()
    if not g:
        g = _match_item_by_words(Gear, "name", words)
    if g:
        return ("Gear", {
            "name": g.name, "description": g.description, "category": g.category,
            "value": g.value, "weight": g.weight,
        })

    # Vehicle
    v = Vehicle.objects.filter(name__iexact=name_clean).first()
    if not v:
        v = _match_item_by_words(Vehicle, "name", words)
    if v:
        return ("Vehicle", {
            "name": v.name, "description": getattr(v, "description", ""), "category": v.category,
            "sdp": v.sdp, "seats": v.seats, "speed_combat": v.speed_combat,
            "speed_narrative": v.speed_narrative, "value": v.value,
        })

    # Ammunition
    am = Ammunition.objects.filter(name__iexact=name_clean).first()
    if not am:
        am = _match_item_by_words(Ammunition, "name", words)
    if am:
        return ("Ammunition", {
            "name": am.name, "description": am.description, "ammo_type": am.ammo_type,
            "cost": am.cost, "weapon_type": am.weapon_type,
        })

    # Cyberdeck
    cd = Cyberdeck.objects.filter(name__iexact=name_clean).first()
    if not cd:
        cd = _match_item_by_words(Cyberdeck, "name", words)
    if cd:
        return ("Cyberdeck", {
            "name": cd.name, "description": getattr(cd, "description", ""),
            "hardware_slots": cd.hardware_slots, "program_slots": cd.program_slots,
            "any_slots": cd.any_slots, "value": cd.value,
        })

    # Weapon attachment
    wa = WeaponAttachment.objects.filter(name__iexact=name_clean).first()
    if not wa:
        wa = _match_item_by_words(WeaponAttachment, "name", words)
    if wa:
        return ("Weapon Attachment", {
            "name": wa.name, "description": wa.description, "value": wa.value,
            "effect_description": wa.effect_description, "install_dv": wa.install_dv,
            "install_skill": wa.install_skill,
        })

    # Cyberware
    cw = Cyberware.objects.filter(name__iexact=name_clean).first()
    if not cw:
        cw = _match_item_by_words(Cyberware, "name", words)
    if cw:
        return ("Cyberware", {
            "name": cw.name, "description": cw.description, "type": cw.type,
            "slots": cw.slots, "humanity_loss": cw.humanity_loss, "cost": cw.cost,
        })

    # Netrunning: programs
    p = next((x for x in programs if (x.get("name") or "").lower() == name_lower), None)
    if not p:
        p = _match_list_item_by_words(programs, "name", words)
    if p:
        return ("Netrunning Program", {
            "name": p["name"], "type": p.get("type", ""), "atk": p.get("atk", 0),
            "dfv": p.get("dfv", 0), "rez": p.get("rez", 0),
            "effect": p.get("effect", ""), "cost": p.get("cost", 0),
            "icon": p.get("icon", ""),
        })

    # Netrunning: hardware
    h = next((x for x in hardware if (x.get("name") or "").lower() == name_lower), None)
    if not h:
        h = _match_list_item_by_words(hardware, "name", words)
    if h:
        return ("Netrunning Hardware", {
            "name": h["name"], "description": h.get("description", ""),
            "slots": h.get("slots", 0), "cost": h.get("cost", 0),
        })

    # Netrunning: black ICE
    b = next((x for x in black_ice if (x.get("name") or "").lower() == name_lower), None)
    if not b:
        b = _match_list_item_by_words(black_ice, "name", words)
    if b:
        return ("Black ICE", {
            "name": b["name"], "effect": b.get("effect", ""), "atk": b.get("atk", 0),
            "dfv": b.get("dfv", 0), "rez": b.get("rez", 0),
            "cost": b.get("cost", 0), "icon": b.get("icon", ""),
        })

    # Netrunning: quickhack
    q = next((x for x in quickhacks if (x.get("name") or "").lower() == name_lower), None)
    if not q:
        q = _match_list_item_by_words(quickhacks, "name", words)
    if q:
        return ("Quickhack", {
            "name": q["name"], "dv": q.get("dv", 0), "tier": q.get("tier", ""),
            "effect": q.get("effect", ""),
        })

    return (None, None)


def format_item_info(source, data):
    """Format item info for display. Returns list of output lines."""
    out = [section_header(f"{source}: {data.get('name', '')}", width=78)]

    if source == "Weapon":
        out.append(f"  |gDamage:|n {data.get('damage', '—')}  |gROF:|n {data.get('rof', '—')}  |gHands:|n {data.get('hands', '—')}")
        out.append(f"  |gCategory:|n {data.get('category', '—')}  |gValue:|n {data.get('value', 0)} eb  |gConceal:|n {'Yes' if data.get('concealable') else 'No'}")
        if data.get("description"):
            out.append(f"  {wrap_ansi(data['description'], 74)}")
    elif source == "Armor":
        out.append(f"  |gSP:|n {data.get('sp', 0)}  |gEV:|n {data.get('ev', 0)}  |gLocations:|n {data.get('locations', '—')}")
        out.append(f"  |gValue:|n {data.get('value', 0)} eb")
        if data.get("description"):
            out.append(f"  {wrap_ansi(data['description'], 74)}")
    elif source == "Gear":
        out.append(f"  |gCategory:|n {data.get('category', '—')}  |gValue:|n {data.get('value', 0)} eb")
        if data.get("description"):
            out.append(f"  {wrap_ansi(data['description'], 74)}")
    elif source == "Vehicle":
        out.append(f"  |gCategory:|n {data.get('category', '—')}  |gSDP:|n {data.get('sdp', 0)}  |gSeats:|n {data.get('seats', 0)}")
        out.append(f"  |gSpeed:|n {data.get('speed_narrative', '—')}  |gValue:|n {data.get('value', 0)} eb")
        if data.get("description"):
            out.append(f"  {wrap_ansi(data['description'], 74)}")
    elif source == "Ammunition":
        out.append(f"  |gType:|n {data.get('ammo_type', '—')}  |gCost:|n {data.get('cost', 0)} eb")
        if data.get("description"):
            out.append(f"  {wrap_ansi(data['description'], 74)}")
    elif source == "Cyberdeck":
        out.append(f"  |gHW:|n {data.get('hardware_slots', 0)}  |gProgram:|n {data.get('program_slots', 0)}  |gAny:|n {data.get('any_slots', 0)}  |gValue:|n {data.get('value', 0)} eb")
        if data.get("description"):
            out.append(f"  {wrap_ansi(data['description'], 74)}")
    elif source == "Weapon Attachment":
        out.append(f"  |gValue:|n {data.get('value', 0)} eb  DV{data.get('install_dv', 17)} {data.get('install_skill', 'Weaponstech')}")
        out.append(f"  {wrap_ansi(data.get('effect_description') or data.get('description', '—'), 74)}")
    elif source == "Cyberware":
        out.append(f"  |gType:|n {data.get('type', '—')}  |gSlots:|n {data.get('slots', 0)}  |gHL:|n {data.get('humanity_loss', 0)}  |gCost:|n {data.get('cost', 0)} eb")
        if data.get("description"):
            out.append(f"  {wrap_ansi(data['description'], 74)}")
    elif source == "Netrunning Program":
        out.append(f"  |gType:|n {data.get('type', '—')}  |gATK/DFV/Rez:|n {data.get('atk', 0)}/{data.get('dfv', 0)}/{data.get('rez', 0)}  |gCost:|n {data.get('cost', 0)} eb")
        out.append(f"  |gEffect:|n {wrap_ansi(data.get('effect', '—'), 74)}")
        if data.get("icon"):
            out.append(f"  |gIcon:|n {data['icon']}")
    elif source == "Netrunning Hardware":
        out.append(f"  |gSlots:|n {data.get('slots', 0)}  |gCost:|n {data.get('cost', 0)} eb")
        if data.get("description"):
            out.append(f"  {wrap_ansi(data['description'], 74)}")
    elif source == "Black ICE":
        out.append(f"  |gATK/DFV/Rez:|n {data.get('atk', 0)}/{data.get('dfv', 0)}/{data.get('rez', 0)}  |gCost:|n {data.get('cost', 0)} eb")
        out.append(f"  |gEffect:|n {wrap_ansi(data.get('effect', '—'), 74)}")
    elif source == "Quickhack":
        out.append(f"  |gDV:|n {data.get('dv', 0)}  |gTier:|n {data.get('tier', '—')}")
        out.append(f"  |gEffect:|n {wrap_ansi(data.get('effect', '—'), 74)}")

    out.append(divider("", width=78))
    return out


class CmdLookup(MuxCommand):
    """
    Look up game system information.

    Usage:
      +lookup                   - Show available categories
      +lookup equipment [cat]   - List equipment (weapons, armor, gear, etc.)
      +lookup skills [skill]    - List skills with descriptions
      +lookup stats [stat]      - List stats with descriptions
      +lookup roles [role]      - List roles and role abilities
      +lookup/info <item>       - Detailed info on a specific item

    Equipment categories: weapons, armor, gear, vehicles, ammo, cyberdecks, attachments, cyberware
    """

    key = "+lookup"
    aliases = ["lookup"]
    lock = "cmd:all()"
    help_category = "General"

    def func(self):
        if self.switches and "info" in self.switches:
            self.do_info()
            return

        if not self.args:
            self.do_main_menu()
            return

        parts = self.args.strip().split(None, 1)
        category = parts[0].lower()
        sub = parts[1] if len(parts) > 1 else None

        if category == "equipment":
            self.do_equipment(sub)
        elif category in ("skills", "skill"):
            self.do_skills(sub)
        elif category in ("stats", "stat"):
            self.do_stats(sub)
        elif category in ("roles", "role"):
            self.do_roles(sub)
        elif category in ("mystery", "mysteries", "investigation"):
            self.do_mystery()
        else:
            self.caller.msg(f"Unknown category '{category}'. Use: equipment, skills, stats, roles, mystery")

    def do_main_menu(self):
        out = [
            header("Lookup - Game Reference"),
            "  |w+lookup equipment|n [cat]   - Weapons, armor, gear, vehicles, ammo, cyberdecks, attachments, cyberware",
            "  |w+lookup skills|n [name]    - Skill descriptions",
            "  |w+lookup stats|n [name]     - Stat descriptions",
            "  |w+lookup roles|n [name]     - Roles and role abilities",
            "  |w+lookup mystery|n          - Investigation system (Focus, clues)",
            "  |w+lookup/info <item>|n      - Detailed info on equipment, cyberware, or netrunning items",
            "",
            "Example: |w+lookup equipment weapons|n  |w+lookup/info Medium Pistol|n",
            footer(),
        ]
        self.caller.msg("\n".join(out))

    def do_equipment(self, subcategory=None):
        if not subcategory:
            out = [
                section_header("Equipment Categories", width=78),
                "  |wweapons|n      |warmor|n       |wgear|n        |wvehicles|n    |wammo|n",
                "  |wcyberdecks|n   |wattachments|n  |wcyberware|n",
                "",
                "Use: |w+lookup equipment <category>|n  e.g. +lookup equipment gear",
                divider("", width=78),
            ]
            self.caller.msg("\n".join(out))
            return

        sub = subcategory.lower()
        out = []
        if sub in ("weapons", "weapon"):
            qs = Weapon.objects.all().order_by("category", "name")[:50]
            out.append(section_header("Weapons", width=78))
            for w in qs:
                out.append(f"  |c{w.name}|n - {w.damage} |g{w.value}eb|n")
        elif sub in ("armor",):
            for a in Armor.objects.all().order_by("name")[:50]:
                out.append(f"  |c{a.name}|n SP{a.sp} |g{a.value}eb|n")
            out.insert(0, section_header("Armor", width=78))
        elif sub in ("gear",):
            qs = Gear.objects.all().order_by("category", "name")[:80]
            out.append(section_header("Gear", width=78))
            for g in qs:
                out.append(f"  |c{g.name}|n ({g.category}) |g{g.value}eb|n")
        elif sub in ("vehicles", "vehicle"):
            for v in Vehicle.objects.all().order_by("category", "name")[:40]:
                out.append(f"  |c{v.name}|n ({v.category}) |g{v.value}eb|n")
            out.insert(0, section_header("Vehicles", width=78))
        elif sub in ("ammo", "ammunition"):
            for a in Ammunition.objects.all().order_by("ammo_type", "name")[:40]:
                out.append(f"  |c{a.name}|n |g{a.cost}eb|n")
            out.insert(0, section_header("Ammunition", width=78))
        elif sub in ("cyberdecks", "deck"):
            for d in Cyberdeck.objects.all().order_by("name")[:30]:
                out.append(f"  |c{d.name}|n |g{d.value}eb|n")
            out.insert(0, section_header("Cyberdecks", width=78))
        elif sub in ("attachments", "attachment"):
            for a in WeaponAttachment.objects.all().order_by("name")[:30]:
                out.append(f"  |c{a.name}|n |g{a.value}eb|n")
            out.insert(0, section_header("Weapon Attachments", width=78))
        elif sub in ("cyberware",):
            for c in Cyberware.objects.all().order_by("type", "name")[:80]:
                out.append(f"  |c{c.name}|n ({c.type}) |g{c.cost}eb|n")
            out.insert(0, section_header("Cyberware", width=78))
        else:
            self.caller.msg(f"Unknown equipment category: {subcategory}")
            return

        out.append(divider("", width=78))
        out.append("Use |w+lookup/info <name>|n for details on any item.")
        self.caller.msg("\n".join(out))

    def do_skills(self, skill_name=None):
        if not skill_name:
            out = [section_header("Skills by Category", width=78)]
            cats = {}
            for skill, (cat, _) in SKILL_DESCRIPTIONS.items():
                cats.setdefault(cat, []).append(skill)
            for cat in sorted(cats):
                out.append(f"\n  |y{cat}|n: {', '.join(sorted(cats[cat])[:12])}{'...' if len(cats[cat]) > 12 else ''}")
            out.append("\n  Use |w+lookup skills <name>|n for description.")
            out.append(divider("", width=78))
            self.caller.msg("\n".join(out))
            return

        key = skill_name.lower().replace(" ", "_").replace("-", "_")
        for k, (cat, desc) in SKILL_DESCRIPTIONS.items():
            if key in k or k in key:
                out = [
                    section_header(f"Skill: {k.title().replace('_', ' ')}", width=78),
                    f"  |gCategory:|n {cat}",
                    f"  |gDescription:|n {desc}",
                    divider("", width=78),
                ]
                self.caller.msg("\n".join(out))
                return
        self.caller.msg(f"Skill '{skill_name}' not found.")

    def do_stats(self, stat_name=None):
        if not stat_name:
            out = [section_header("Stats", width=78)]
            for s in STATS:
                info = STAT_DESCRIPTIONS.get(s, {})
                abbrev = info.get("abbrev", s[:3].upper())
                out.append(f"  |c{abbrev}|n - {info.get('name', s)}")
            out.append("\n  Use |w+lookup stats <name>|n for full description.")
            out.append(divider("", width=78))
            self.caller.msg("\n".join(out))
            return

        key = stat_name.lower().strip()
        for k, info in STAT_DESCRIPTIONS.items():
            if key in k or key == info.get("abbrev", "").lower():
                out = [
                    section_header(f"Stat: {info.get('name', k)} ({info.get('abbrev', '')})", width=78),
                    f"  {info.get('description', '')}",
                    divider("", width=78),
                ]
                self.caller.msg("\n".join(out))
                return
        self.caller.msg(f"Stat '{stat_name}' not found.")

    def do_roles(self, role_name=None):
        if not role_name:
            out = [section_header("Roles", width=78)]
            for r in ROLES:
                ab = ROLE_ABILITIES.get(r, {})
                out.append(f"  |c{r}|n - {ab.get('ability', '—')}")
            out.append("\n  Use |w+lookup roles <name>|n for role ability details.")
            out.append(divider("", width=78))
            self.caller.msg("\n".join(out))
            return

        key = role_name.strip().capitalize()
        if key not in ROLES:
            for r in ROLES:
                if role_name.lower() in r.lower():
                    key = r
                    break
        if key in ROLES and key in ROLE_ABILITIES:
            ab = ROLE_ABILITIES[key]
            out = [
                section_header(f"Role: {key}", width=78),
                f"  |gPrimary Ability:|n {ab.get('ability', '—')}",
                f"  {ab.get('description', '')}",
                divider("", width=78),
            ]
            self.caller.msg("\n".join(out))
            return
        self.caller.msg(f"Role '{role_name}' not found.")

    def do_mystery(self):
        """Show investigation system overview."""
        from world.mystery.mystery_data import (
            CLUE_TYPES,
            COMPLEXITY_TIERS,
            OBFUSCATION_LEVELS,
            get_max_focus,
        )
        out = [
            section_header("Investigation System (Did Someone Say Murder?)", width=78),
            "",
            "  |gFocus|n: 10 + 5[(INT+WILL)/2]. Depletes on failed Evidence Checks.",
            "  |gMystery Complexity|n: Reduced by clue damage. At 0 = solved.",
            "  |gClue Types|n: " + ", ".join(CLUE_TYPES.keys()),
            "",
            "  Use |w+mystery|n for your Focus. |w+investigate <clue>|n to gather clues.",
            divider("", width=78),
        ]
        self.caller.msg("\n".join(out))

    def do_info(self):
        if not self.args or not self.args.strip():
            self.caller.msg("Usage: +lookup/info <item name>")
            return

        source, data = _find_item_info(self.args)
        if not data:
            self.caller.msg(f"Item '{self.args.strip()}' not found. Try +lookup equipment to browse.")
            return

        self.caller.msg("\n".join(format_item_info(source, data)))
