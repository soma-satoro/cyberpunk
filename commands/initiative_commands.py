"""Room initiative: 1d10 + Reflex (+ cyberware / role modifiers), sorted high to low."""

import random
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import ansi

from world.utils.formatting import sheet_header, sheet_section, footer


def _living_characters_in_room(room, looker=None):
    if not room:
        return []
    try:
        from typeclasses.characters import Character
    except Exception:
        Character = None

    out = []
    for obj in room.contents:
        if Character is not None and not isinstance(obj, Character):
            continue
        if looker and not obj.access(looker, "view", default=True):
            continue
        if not getattr(obj, "db", None):
            continue
        ref = getattr(obj.db, "reflexes", None)
        if ref is None:
            continue
        out.append(obj)
    return out


def _initiative_modifier(character):
    """Cyberware (e.g. Kerenzikov +2) + Solo Combat Awareness (+1 when rank > 0)."""
    mod = 0
    try:
        from world.cyberware.stat_bonuses import get_cyberware_initiative_bonus

        mod += get_cyberware_initiative_bonus(character)
    except Exception:
        pass
    try:
        from world.improvement_points import get_character_stat_value

        ca = get_character_stat_value(character, "combat_awareness")
        if ca and int(ca) > 0:
            mod += 1
    except Exception:
        pass
    return mod


class CmdInitiative(MuxCommand):
    """
    Roll initiative for combat order in your current room.

    Usage:
      initiative
      init

    Each eligible character gets 1d10 + Reflex + modifiers (Kerenzikov +2,
    Combat Awareness +1 if you have the Role Ability at rank 1+).
    Results are shown highest first. GM resolves ties.
    """

    key = "initiative"
    aliases = ["init"]
    locks = "cmd:all()"
    help_category = "Combat"

    def func(self):
        room = self.caller.location
        if not room:
            self.caller.msg("You are nowhere.")
            return
        chars = _living_characters_in_room(room, looker=self.caller)
        if not chars:
            self.caller.msg("No characters here to roll initiative.")
            return

        rows = []
        for char in chars:
            d10 = random.randint(1, 10)
            ref = int(char.db.reflexes or 0)
            extra = _initiative_modifier(char)
            total = d10 + ref + extra
            rows.append((total, d10, ref, extra, char))

        rows.sort(key=lambda r: r[0], reverse=True)

        W = 80
        room_title = room.get_display_name(self.caller)
        clean = ansi.strip_ansi(room_title)
        if len(clean) > 60:
            clean = clean[:57] + "..."

        out = sheet_header("Initiative", width=W)
        out += sheet_section(clean or "Current room", width=W)
        out += (
            f"  |y{'#':>2}|n  |w{'Character':<32}|n  |w{'Tot':>3}|n  "
            f"|x{'1d10 + REF + mods':<22}|n\n"
        )

        for idx, (total, d10, ref, extra, char) in enumerate(rows, start=1):
            name = char.get_display_name(self.caller)
            name_plain = ansi.strip_ansi(name)
            if len(name_plain) > 32:
                name_plain = name_plain[:29] + "..."
            detail = f"{d10}+{ref}+{extra}"
            out += f"  |y{idx:>2}|n  |w{name_plain:<32}|n  |c{total:>3}|n  |x{detail:<22}|n\n"

        out += "|x  Highest total acts first. Ties: GM call.|n\n"
        out += footer(width=W, fillchar="-")

        self.caller.msg(out)
        room.msg_contents(out, exclude=[self.caller])
