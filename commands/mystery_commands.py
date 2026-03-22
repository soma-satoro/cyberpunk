"""
Did Someone Say Murder? - Investigation system (Interface RED Vol 5)

Player: +investigate/* switches. Staff: +mystery/* and +clue/*.
"""

import random
from datetime import date
from django.db.models import Q
from evennia.commands.default.muxcommand import MuxCommand
from world.utils.formatting import header, footer, section_header
from world.mystery.models import (
    Mystery,
    MysteryClue,
    MysteryObstacle,
    CharacterFocus,
    ClueAttempt,
    ClueLocation,
    ObstacleAttempt,
    ClueExposure,
    MysteryFollower,
)
from world.mystery.services import (
    follow_mystery_for_character,
    unfollow_mystery_for_character,
    sync_followers_when_mystery_linked_to_mission,
)
from world.mystery.mystery_data import (
    get_max_focus,
    CLUE_TYPES,
    COMPLEXITY_TIERS,
)
from world.list_data import SKILL_TO_STAT_LOOKUP
from world.utils.character_utils import is_character_approved


def _get_character_for_caller(caller):
    if hasattr(caller, "is_puppet") and caller.is_puppet:
        return caller
    if hasattr(caller, "character") and caller.character:
        return caller.character
    return caller if hasattr(caller, "db") else None


def _get_or_create_focus(character):
    focus = CharacterFocus.objects.filter(character_object=character).first()
    if not focus and hasattr(character, "character_sheet") and character.character_sheet:
        focus = CharacterFocus.objects.filter(character_sheet=character.character_sheet).first()
    if not focus:
        int_val = getattr(character.db, "intelligence", 5) or 5
        will_val = getattr(character.db, "willpower", 5) or 5
        focus = CharacterFocus.objects.create(
            character_object=character,
            character_sheet=getattr(character, "character_sheet", None),
            current_focus=get_max_focus(int_val, will_val),
        )
    return focus


def _roll_dice(dice_str):
    try:
        n, d = dice_str.lower().replace("d", " ").split()
        n, d = int(n), int(d)
        return sum(random.randint(1, d) for _ in range(n))
    except Exception:
        return 0


def _normalize_element_key(s):
    if not s:
        return ""
    return " ".join(s.strip().lower().split())


def _parse_clue_and_element(rhs):
    rhs = (rhs or "").strip()
    if "/" in rhs:
        left, right = rhs.split("/", 1)
        clue_id = int(left.strip())
        element_key = _normalize_element_key(right)
    else:
        clue_id = int(rhs)
        element_key = ""
    return clue_id, element_key


def _exit_search(room, arg):
    if not room or not arg:
        return None
    want = _normalize_element_key(arg)
    for ex in room.exits:
        if ex.key and _normalize_element_key(ex.key) == want:
            return ex
        if hasattr(ex, "aliases") and ex.aliases:
            for al in ex.aliases.all():
                alias_text = getattr(al, "alias", None) or str(al)
                if _normalize_element_key(str(alias_text)) == want:
                    return ex
    return None


def _search_in_room(caller, char, arg):
    if not char.location:
        return None
    arg = arg.strip()
    hit = _exit_search(char.location, arg)
    if hit:
        return hit
    quiet = caller.search(arg, location=char.location, quiet=True)
    if quiet:
        if isinstance(quiet, list):
            return quiet[0] if quiet else None
        return quiet
    return None


def _locations_for_room_scan(room):
    if not room:
        return ClueLocation.objects.none()
    q = Q(location_object=room)
    try:
        for obj in room.contents:
            q |= Q(location_object=obj)
    except Exception:
        pass
    try:
        for ex in room.exits:
            q |= Q(location_object=ex)
    except Exception:
        pass
    return ClueLocation.objects.filter(q)


def _clue_prereqs_deciphered(clue, char):
    for req in clue.required_clues.all():
        if not ClueAttempt.objects.filter(clue=req, character=char, success=True).exists():
            return False
    return True


def _obstacle_gate_passed(char, clue):
    obs = clue.gating_obstacle
    if not obs:
        return True
    return ObstacleAttempt.objects.filter(obstacle=obs, character=char, success=True).exists()


def _obstacles_blocking_gated_clues_in_locs(char, locs):
    """
    Clues in this scan scope whose prereqs are met but gating obstacle is not overcome.
    Returns dict obstacle_id -> MysteryObstacle (deduped).
    """
    out = {}
    seen_clue = set()
    for loc in locs:
        c = loc.clue
        if c.id in seen_clue:
            continue
        seen_clue.add(c.id)
        if c.mystery.is_solved:
            continue
        if not _clue_prereqs_deciphered(c, char):
            continue
        if not c.gating_obstacle_id:
            continue
        if _obstacle_gate_passed(char, c):
            continue
        obs = c.gating_obstacle
        out[obs.id] = obs
    return out


def _format_obstacle_overcome_hint(obstacle):
    """One line: obstacle summary and exact +investigate/overcome command."""
    sk = _format_obstacle_skills_display(obstacle)
    desc = (obstacle.description or "").strip()
    tail = ""
    if desc:
        tail = f" -- {desc[:100]}{'...' if len(desc) > 100 else ''}"
    return (
        f"  |m#{obstacle.id}|n {obstacle.obstacle_type}|n |wDV{obstacle.dv}|n "
        f"({sk}){tail}  -> |c+investigate/overcome {obstacle.id}|n"
    )


def _pending_gating_obstacles_for_character(char):
    """
    Obstacles (deduped) that still block a clue in a mystery the character has started,
    where prereqs for that clue are met. Used for +mystery list and +investigate/leads.
    """
    mids = (
        ClueExposure.objects.filter(character=char)
        .values_list("clue__mystery_id", flat=True)
        .distinct()
    )
    if not mids:
        return []
    seen_obs = set()
    out = []
    for clue in (
        MysteryClue.objects.filter(mystery_id__in=mids, gating_obstacle__isnull=False)
        .select_related("gating_obstacle", "mystery")
        .order_by("mystery_id", "id")
    ):
        if clue.mystery.is_solved:
            continue
        if not _clue_prereqs_deciphered(clue, char):
            continue
        if _obstacle_gate_passed(char, clue):
            continue
        obs = clue.gating_obstacle
        if obs.id in seen_obs:
            continue
        seen_obs.add(obs.id)
        out.append(obs)
    return out


def _clue_eligible_for_exposure(char, clue):
    if clue.mystery.is_solved:
        return False
    if not _clue_prereqs_deciphered(clue, char):
        return False
    if not _obstacle_gate_passed(char, clue):
        return False
    return True


def _is_exposed(char, clue):
    return ClueExposure.objects.filter(character=char, clue=clue).exists()


def _expose_clue(char, clue):
    ClueExposure.objects.get_or_create(character=char, clue=clue)


def _loc_label_for_player(loc, room):
    if loc.element_key:
        if loc.location_object == room:
            return loc.element_key
        return f"{loc.location_object.key} ({loc.element_key})"
    if loc.location_object == room:
        return "the general area"
    return loc.location_object.key


def _default_player_hint(loc, room):
    label = _loc_label_for_player(loc, room)
    return f"Something draws your attention near {label}."


def _player_hint_for_clue(clue, loc, room):
    if clue.player_hint.strip():
        return clue.player_hint.strip()
    return _default_player_hint(loc, room)


def _format_clue_location_global(loc):
    """Short label for a clue placement (not necessarily the player's current room)."""
    obj = loc.location_object
    if not obj:
        return "Unknown"
    base = obj.key
    if getattr(obj, "destination", None):
        return f"Exit: {base}"
    if loc.element_key:
        return f"{base} ({loc.element_key})"
    return base


def _clue_deciphered(char, clue):
    return ClueAttempt.objects.filter(clue=clue, character=char, success=True).exists()


def _count_successful_decipher_clues(char):
    """How many distinct clues this character has successfully deciphered."""
    return (
        ClueAttempt.objects.filter(character=char, success=True)
        .values_list("clue_id", flat=True)
        .distinct()
        .count()
    )


def _find_pc_in_same_room(caller, arg):
    """Resolve a single character; must share caller's location."""
    if not arg or not caller.location:
        return None
    from evennia.utils.search import search_object

    arg = arg.strip()
    if arg.startswith("#"):
        try:
            dbref = int(arg[1:])
            from evennia.objects.models import ObjectDB

            obj = ObjectDB.objects.filter(id=dbref).first()
            if obj and getattr(obj, "location", None) == caller.location:
                return obj
        except ValueError:
            pass
        return None
    results = search_object(arg, typeclass="typeclasses.characters.Character")
    if not results:
        return None
    here = [r for r in results if getattr(r, "location", None) == caller.location]
    if len(here) == 1:
        return here[0]
    return None


def _sync_exposure_to_target(initiator, target):
    """
    Copy lead exposure from initiator to target for clues the target can legally see.
    Allowed only when target has deciphered at least as many clues as the initiator
    (they are not behind on successful investigations).
    """
    n_i = _count_successful_decipher_clues(initiator)
    n_t = _count_successful_decipher_clues(target)
    if n_t < n_i:
        return False, (
            "They have successfully deciphered fewer leads than you; "
            "they need to catch up on evidence checks before you can align their threads."
        )
    added = 0
    for exp in ClueExposure.objects.filter(character=initiator).select_related("clue"):
        clue = exp.clue
        if clue.mystery.is_solved:
            continue
        if not _clue_eligible_for_exposure(target, clue):
            continue
        _e, created = ClueExposure.objects.get_or_create(character=target, clue=clue)
        if created:
            added += 1
    return True, added


def _narrative_lines_for_successful_clues(character):
    """(mystery_name, text lines) for clues this character has successfully deciphered."""
    attempts = (
        ClueAttempt.objects.filter(character=character, success=True)
        .select_related("clue", "clue__mystery")
        .order_by("clue__mystery_id", "clue__discovery_priority", "clue_id")
    )
    by_mystery = []
    current_mid = None
    bucket = []
    mname = ""
    for a in attempts:
        clue = a.clue
        desc = (clue.description or "").strip()
        if not desc:
            continue
        mid = clue.mystery_id
        if current_mid is None:
            current_mid = mid
            mname = clue.mystery.name
        elif mid != current_mid:
            if bucket:
                by_mystery.append((mname, bucket))
            bucket = []
            current_mid = mid
            mname = clue.mystery.name
        bucket.append(f"  * {desc}")
    if bucket:
        by_mystery.append((mname, bucket))
    return by_mystery


def _max_scan_dv(clues):
    if not clues:
        return 13
    return max(c.mystery.scan_dv for c in clues)


def _unique_clues_from_locs(locs):
    seen = set()
    out = []
    for loc in locs:
        if loc.clue_id in seen:
            continue
        seen.add(loc.clue_id)
        out.append(loc.clue)
    return out


def _skill_to_stat(skill_name):
    """
    Stat key for CPR skill checks — must match world.list_data.SKILL_TO_STAT (sheet / rules).
    e.g. conversation -> empathy, persuasion -> cool, perception -> intelligence.
    """
    return SKILL_TO_STAT_LOOKUP.get(skill_name, "intelligence")


def _normalize_skill_key(token: str) -> str:
    """Normalize staff/player skill tokens to db keys (snake_case)."""
    s = (token or "").strip().lower().replace(" ", "_")
    return s


def _get_skill_value(char, skill_name: str) -> int:
    """Effective skill rank for mystery rolls."""
    v = getattr(char.db, skill_name, 0) or 0
    if hasattr(char, "get_skill"):
        v = char.get_skill(skill_name)
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _evidence_skill_candidates(clue):
    """
    Skills usable for an evidence check: CLUE_TYPES defaults for clue_type, plus any
    extras from skills_used (deduped). Lets gossip use conversation / persuasion /
    streetwise even if the clue row only listed one skill.
    """
    type_defaults = CLUE_TYPES.get(clue.clue_type, {}).get("skills") or []
    db_list = clue.get_skills_list()
    seen = set()
    out = []

    def add_many(items):
        for src in items:
            k = _normalize_skill_key(src)
            if k and k not in seen:
                seen.add(k)
                out.append(k)

    if type_defaults:
        add_many(type_defaults)
        add_many(db_list)
    else:
        add_many(db_list)

    return out if out else ["deduction"]


def _obstacle_skill_candidates(obstacle):
    """Parse obstacle.skill_used as comma-separated list; default streetwise."""
    raw = (obstacle.skill_used or "").strip()
    if not raw:
        return ["streetwise"]
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    keys = [_normalize_skill_key(p) for p in parts]
    return keys if keys else ["streetwise"]


def _pick_best_skill_for_roll(char, skill_names: list):
    """
    Choose the skill with the highest rank; ties keep the first listed candidate.
    Returns (skill_name, skill_val, stat_name, stat_val).
    """
    if not skill_names:
        skill_names = ["deduction"]
    best_sk = skill_names[0]
    best_val = _get_skill_value(char, best_sk)
    for sk in skill_names[1:]:
        val = _get_skill_value(char, sk)
        if val > best_val:
            best_val = val
            best_sk = sk
    stat_name = _skill_to_stat(best_sk)
    stat_val = getattr(char.db, stat_name, 5) or 5
    return (best_sk, best_val, stat_name, stat_val)


def _humanize_skill_stat_name(name: str) -> str:
    """Display label for db stat/skill keys (e.g. electronics_security_tech -> title case)."""
    return (name or "").replace("_", " ").strip().title()


def _format_obstacle_skills_display(obstacle):
    """Player-facing skill list for an obstacle (overcome uses best among these)."""
    cands = _obstacle_skill_candidates(obstacle)
    if len(cands) <= 1:
        return _humanize_skill_stat_name(cands[0] if cands else "streetwise")
    return " / ".join(_humanize_skill_stat_name(s) for s in cands)


def _collect_scan_locs(caller, char, arg):
    """Return (room, list of ClueLocation) for scan scope, or (None, error message)."""
    if not char.location:
        return None, "You are not in a location."
    room = char.location
    arg = (arg or "").strip()
    if not arg or arg.lower() in ("here", "room", "location"):
        return room, list(_locations_for_room_scan(room))
    target = _search_in_room(caller, char, arg)
    if target:
        return room, list(ClueLocation.objects.filter(location_object=target))
    ek = _normalize_element_key(arg)
    if ek:
        locs = list(ClueLocation.objects.filter(location_object=room, element_key=ek))
        if locs:
            return room, locs
    return None, "You find nothing to scan there."


def _filter_locs_eligible_for_exposure(char, locs):
    out = []
    for loc in locs:
        if _clue_eligible_for_exposure(char, loc.clue):
            out.append(loc)
    return out


def _filter_locs_exposed(char, locs):
    return [loc for loc in locs if _is_exposed(char, loc.clue)]


def _execute_evidence_check(caller, char, focus_obj, clue):
    if not _is_exposed(char, clue):
        caller.msg(
            "You have not noticed anything actionable there yet. "
            "Try |c+investigate/scan|n first, or investigate elsewhere."
        )
        return
    if not _obstacle_gate_passed(char, clue):
        obs = clue.gating_obstacle
        sk = _format_obstacle_skills_display(obs)
        caller.msg(
            f"|yA block is in the way of this lead.|n Overcome obstacle |m#{obs.id}|n "
            f"({obs.obstacle_type}, |wDV{obs.dv}|n, {sk}) with "
            f"|c+investigate/overcome {obs.id}|n, then you can push the evidence check."
        )
        return
    for req in clue.required_clues.all():
        if not ClueAttempt.objects.filter(clue=req, character=char, success=True).exists():
            caller.msg(
                f"You must decipher the earlier lead first (clue #{req.id})."
            )
            return

    today = date.today()
    existing = ClueAttempt.objects.filter(
        clue=clue, character=char, attempted_date=today
    ).first()
    if existing:
        caller.msg("You've already attempted this lead today. Try again tomorrow.")
        return

    candidates = _evidence_skill_candidates(clue)
    skill_name, skill_val, stat_name, stat_val = _pick_best_skill_for_roll(char, candidates)

    from world.utils.roll_utils import roll_skill_check, check_success, format_roll_vs_dv_message
    from world.wound_utils import get_action_penalty

    action_penalty = get_action_penalty(char)
    total, details = roll_skill_check(stat_val, skill_val, modifier=action_penalty)
    target = clue.dv
    success = check_success(total, target)
    fumble = details.get("is_crit_failure", False)

    caller.msg(
        format_roll_vs_dv_message(
            _humanize_skill_stat_name(stat_name),
            _humanize_skill_stat_name(skill_name),
            stat_val,
            skill_val,
            action_penalty,
            total,
            target,
            details,
        )
    )

    if success:
        damage = max(0, _roll_dice(clue.damage_dice) - clue.obfuscation)
        clue.mystery.current_complexity = max(
            0, clue.mystery.current_complexity - damage
        )
        clue.mystery.save()
        if clue.mystery.current_complexity <= 0:
            clue.mystery.solve()
        ClueAttempt.objects.create(
            clue=clue,
            character=char,
            attempted_date=today,
            success=True,
            damage_dealt=damage,
        )
        desc = (clue.description or "").strip()
        if desc:
            caller.msg(f"|gSuccess!|n {desc}")
        else:
            caller.msg("|gSuccess!|n You piece the lead together.")
        caller.msg(
            f"Dealt {damage} to the mystery. Remaining complexity: {clue.mystery.current_complexity}."
        )
        if clue.mystery.is_solved:
            caller.msg(f"|yMystery solved!|n {clue.mystery.goal}")
    else:
        focus_damage = _roll_dice(clue.focus_damage_dice)
        focus_obj.current_focus -= focus_damage
        focus_obj.save()
        ClueAttempt.objects.create(
            clue=clue,
            character=char,
            attempted_date=today,
            success=False,
            focus_lost=focus_damage,
        )
        msg = f"|rFailed.|n You lose {focus_damage} Focus. ({focus_obj.current_focus} remaining)"
        if fumble:
            fumble_effect = clue.fumble_effect or CLUE_TYPES.get(clue.clue_type, {}).get("fumble_effect")
            if fumble_effect:
                msg += f" |rFumble!|n {fumble_effect}"
            else:
                msg += " |rFumble!|n Additional complications may apply."
        caller.msg(msg)


def _resolve_evidence_target(caller, char, arg_orig):
    """Resolve a single clue for evidence check (must be exposed)."""
    arg_lower = arg_orig.strip().lower()
    if arg_orig.strip().isdigit():
        try:
            clue = MysteryClue.objects.get(id=int(arg_orig.strip()))
        except MysteryClue.DoesNotExist:
            return {"type": "error", "message": "Lead not found."}
        if not _is_exposed(char, clue):
            return {"type": "error", "message": "You have not noticed that lead yet. Use |c+investigate/scan|n."}
        return {"type": "single", "clue": clue}

    if not char.location:
        return {"type": "error", "message": "You are not in a location."}

    room = char.location

    if arg_lower in ("here", "room", "location"):
        locs = _filter_locs_exposed(
            char, _filter_clue_locations_for_chain_only(list(_locations_for_room_scan(room)), char)
        )
        if not locs:
            return {"type": "error", "message": "Nothing you can act on here yet. Try |c+investigate/scan|n."}
        dedup = []
        seen = set()
        for loc in locs:
            if loc.clue_id in seen:
                continue
            seen.add(loc.clue_id)
            dedup.append(loc)
        if len(dedup) == 1:
            return {"type": "single", "clue": dedup[0].clue}
        lines = ["|yLeads you are following up:|n"]
        for loc in dedup:
            c = loc.clue
            hint = _player_hint_for_clue(c, loc, room)
            lines.append(f"  {hint} (|c+investigate {c.id}|n)")
        lines.append("Use |c+investigate <id>|n or name the spot.")
        return {"type": "list", "message": "\n".join(lines)}

    target = _search_in_room(caller, char, arg_orig)
    if target:
        locs = _filter_locs_exposed(
            char,
            _filter_clue_locations_for_chain_only(
                list(ClueLocation.objects.filter(location_object=target)), char
            ),
        )
        if not locs:
            return {"type": "error", "message": f"Nothing actionable on {target.key} yet. Scan first."}
        if len(locs) == 1:
            return {"type": "single", "clue": locs[0].clue}
        lines = ["|ySeveral exposed leads on that target:|n"]
        for loc in locs:
            c = loc.clue
            lines.append(f"  {_player_hint_for_clue(c, loc, room)} -- |c+investigate {c.id}|n")
        return {"type": "list", "message": "\n".join(lines)}

    ek = _normalize_element_key(arg_orig)
    if ek:
        locs = _filter_locs_exposed(
            char,
            _filter_clue_locations_for_chain_only(
                list(ClueLocation.objects.filter(location_object=room, element_key=ek)), char
            ),
        )
        if locs:
            if len(locs) == 1:
                return {"type": "single", "clue": locs[0].clue}
            lines = ["|yWhich lead?|n"]
            for loc in locs:
                c = loc.clue
                lines.append(f"  |c+investigate {c.id}|n -- {_player_hint_for_clue(c, loc, room)}")
            return {"type": "list", "message": "\n".join(lines)}

    return {"type": "error", "message": "No exposed lead matches that. Use |c+investigate/scan|n or check +mystery."}


def _filter_clue_locations_for_chain_only(locs, char):
    """Locations whose clue chain allows attempting (prereqs); exposure handled separately."""
    out = []
    for loc in locs:
        if _clue_prereqs_deciphered(loc.clue, char):
            out.append(loc)
    return out


class CmdInvestigate(MuxCommand):
    """
    Investigation: scan to notice leads, then follow up with evidence checks.

    Usage:
      +investigate/scan [here|<name>]  - Roll Perception to notice leads in scope
      +investigate <id or spot>        - Evidence check on a lead you already noticed
      +investigate/hint                - Ask the GM for a nudge (costs Focus)
      +investigate/overcome <id>       - Push past an obstacle
      +investigate/sync <character>    - Align their uncovered threads to yours (IC, same room)
      +investigate/tell <character>    - Share narrative text of leads you deciphered (IC, same room)
    """

    key = "+investigate"
    aliases = ["investigate"]
    lock = "cmd:all()"
    help_category = "General"

    def func(self):
        char = _get_character_for_caller(self.caller)
        if not char:
            self.caller.msg("You must be playing a character.")
            return
        if not is_character_approved(char):
            self.caller.msg("You must be approved before using investigations.")
            return

        focus_obj = _get_or_create_focus(char)

        if "leads" in self.switches:
            self._do_leads(char)
            return
        if "hint" in self.switches:
            self._do_hint(focus_obj)
            return
        if "overcome" in self.switches:
            self._do_overcome(focus_obj)
            return
        if "scan" in self.switches:
            self._do_scan(focus_obj)
            return
        if "sync" in self.switches:
            self._do_sync_leads()
            return
        if "tell" in self.switches:
            self._do_tell_narrative()
            return

        if not self.args:
            self.caller.msg(
                "|c+investigate/scan|n [here|object|exit|element] -- look for leads.\n"
                "|c+investigate <id>|n or name -- evidence check on a lead you noticed.\n"
                "|c+investigate/leads|n -- uncovered leads, locations, and chains.\n"
                "|c+investigate/sync|n |c+investigate/tell|n (same room) |c+investigate/hint|n |c+investigate/overcome <id>|n"
            )
            return

        if focus_obj.current_focus <= 0:
            self.caller.msg("Your Focus is depleted. Rest before investigating further.")
            return

        res = _resolve_evidence_target(self.caller, char, self.args)
        if res["type"] == "error":
            self.caller.msg(res["message"])
            return
        if res["type"] == "list":
            self.caller.msg(res["message"])
            return
        _execute_evidence_check(self.caller, char, focus_obj, res["clue"])

    def _do_leads(self, char):
        exposures = (
            ClueExposure.objects.filter(character=char)
            .select_related("clue", "clue__mystery")
            .order_by("clue__mystery_id", "clue_id")
        )
        if not exposures.exists():
            self.caller.msg(
                "You have not uncovered any leads yet. Use |c+investigate/scan|n in play."
            )
            return
        lines = [header("Your uncovered leads"), ""]
        for exp in exposures:
            clue = exp.clue
            m = clue.mystery
            if m.is_solved:
                status = "|gMystery solved|n"
            elif _clue_deciphered(char, clue):
                status = "|gLead deciphered|n"
            else:
                status = "|yNot deciphered yet|n"
            locs = clue.locations.all()
            if locs:
                loc_str = ", ".join(_format_clue_location_global(loc) for loc in locs)
            else:
                loc_str = "(no fixed placement -- ask staff)"
            lines.append(f"|y#{clue.id}|n |w{m.name}|n -- {status}")
            lines.append(f"  Where: {loc_str}")
            reqs = clue.required_clues.all()
            if reqs:
                parts = []
                for r in reqs:
                    ok = _clue_deciphered(char, r)
                    tag = "|g(deciphered)|n" if ok else "|r(pending)|n"
                    parts.append(f"#{r.id} {tag}")
                lines.append(f"  Needs first: {', '.join(parts)}")
            dependents = clue.unlocks.all()
            if dependents:
                lines.append(
                    "  Other leads that need this one: "
                    + ", ".join(f"#{d.id}" for d in dependents)
                )
            hint = (clue.player_hint or "").strip()
            if hint:
                lines.append(f"  Thread: {hint}")
            lines.append("")
        pending_obs = _pending_gating_obstacles_for_character(char)
        if pending_obs:
            lines.append("|wStill in your way (clear to reveal more leads):|n")
            for obs in pending_obs:
                lines.append(_format_obstacle_overcome_hint(obs))
            lines.append("")
        lines.append(footer())
        self.caller.msg("\n".join(lines))

    def _do_scan(self, focus_obj):
        char = _get_character_for_caller(self.caller)
        if focus_obj.current_focus <= 0:
            self.caller.msg("Your Focus is depleted.")
            return

        arg = (self.args or "").strip()
        room, locs_or_err = _collect_scan_locs(self.caller, char, arg)
        if room is None:
            self.caller.msg(locs_or_err)
            return
        locs = locs_or_err

        if not locs:
            self.caller.msg("There are no investigation placements in this scope.")
            return

        gated_here = _obstacles_blocking_gated_clues_in_locs(char, locs)

        eligible_locs = _filter_locs_eligible_for_exposure(char, locs)
        if not eligible_locs:
            if gated_here:
                lines = [
                    "|ySomething is blocking new leads from surfacing here.|n "
                    "Push past the obstacle first, then scan again:",
                ]
                for obs in sorted(gated_here.values(), key=lambda o: o.id):
                    lines.append(_format_obstacle_overcome_hint(obs))
                self.caller.msg("\n".join(lines))
                return
            self.caller.msg(
                "You sweep the area but nothing new surfaces -- "
                "prerequisites may be missing (decipher earlier leads first)."
            )
            focus_damage = _roll_dice("1d6")
            focus_obj.current_focus -= focus_damage
            focus_obj.save()
            self.caller.msg(f"(Lost {focus_damage} Focus from the effort.)")
            return

        unexposed_eligible = [loc for loc in eligible_locs if not _is_exposed(char, loc.clue)]
        if not unexposed_eligible:
            if gated_here:
                lines = [
                    "|yYou already noticed every lead you can pick up here without a block.|n",
                    "|mTo open what is still locked away, clear this first:|n",
                ]
                for obs in sorted(gated_here.values(), key=lambda o: o.id):
                    lines.append(_format_obstacle_overcome_hint(obs))
                self.caller.msg("\n".join(lines))
                return
            self.caller.msg(
                "|yYou already noticed every lead you can find in this scope.|n "
                "No need to scan here again until you |wmove to another spot|n "
                "or |wdecipher a lead|n that unlocks more."
            )
            return

        clues = _unique_clues_from_locs(eligible_locs)
        scan_dv = _max_scan_dv(clues)

        skill_val = getattr(char.db, "perception", 0) or 0
        if hasattr(char, "get_skill"):
            skill_val = char.get_skill("perception")
        stat_val = getattr(char.db, "intelligence", 5) or 5
        from world.utils.roll_utils import roll_skill_check, check_success, format_roll_vs_dv_message
        from world.wound_utils import get_action_penalty

        action_penalty = get_action_penalty(char)
        total, details = roll_skill_check(stat_val, skill_val, modifier=action_penalty)
        success = check_success(total, scan_dv)

        focus_damage = _roll_dice("1d6")
        focus_obj.current_focus -= focus_damage
        focus_obj.save()

        self.caller.msg(
            format_roll_vs_dv_message(
                "Intelligence",
                "Perception",
                stat_val,
                skill_val,
                action_penalty,
                total,
                scan_dv,
                details,
            )
        )

        if not success:
            self.caller.msg(
                f"|rYou don't pick up anything useful.|n (Lost {focus_damage} Focus. "
                f"{focus_obj.current_focus} remaining.)"
            )
            return

        exposed = []
        for loc in sorted(
            unexposed_eligible,
            key=lambda x: (x.clue.discovery_priority, x.clue_id),
        ):
            clue = loc.clue
            if _is_exposed(char, clue):
                continue
            _expose_clue(char, clue)
            exposed.append((loc, clue))

        if not exposed:
            self.caller.msg(
                f"|yNothing new to notice.|n (Lost {focus_damage} Focus.) "
                "If this keeps happening, ask staff -- you should not reach this after a successful scan."
            )
            return

        lines = [
            f"|gYou pick up on something.|n (Lost {focus_damage} Focus. {focus_obj.current_focus} remaining.)",
            "",
            "|yThreads to follow:|n",
        ]
        for loc, clue in exposed:
            hint = _player_hint_for_clue(clue, loc, room)
            lines.append(f"  * {hint}")
        lines.append("")
        lines.append("Use |c+investigate <id>|n when you move in, or name the spot.")
        self.caller.msg("\n".join(lines))

    def _do_hint(self, focus_obj):
        char = _get_character_for_caller(self.caller)
        if focus_obj.current_focus <= 0:
            self.caller.msg("Your Focus is depleted.")
            return
        skill_val = getattr(char.db, "deduction", 0) or 0
        if hasattr(char, "get_skill"):
            skill_val = char.get_skill("deduction")
        stat_val = getattr(char.db, "intelligence", 5) or 5
        from world.utils.roll_utils import roll_skill_check, check_success, format_roll_vs_dv_message
        from world.wound_utils import get_action_penalty

        action_penalty = get_action_penalty(char)
        total, details = roll_skill_check(stat_val, skill_val, modifier=action_penalty)
        success = check_success(total, 15)
        focus_damage = _roll_dice("1d6")
        focus_obj.current_focus -= focus_damage
        focus_obj.save()
        self.caller.msg(
            format_roll_vs_dv_message(
                "Intelligence",
                "Deduction",
                stat_val,
                skill_val,
                action_penalty,
                total,
                15,
                details,
            )
        )
        if success:
            self.caller.msg(
                f"|gHint:|n The GM should provide a nudge. (Lost {focus_damage} Focus.)"
            )
        else:
            self.caller.msg(f"Nothing comes to mind. Lost {focus_damage} Focus.")

    def _do_overcome(self, focus_obj):
        char = _get_character_for_caller(self.caller)
        if not self.args:
            self.caller.msg("Usage: +investigate/overcome <obstacle id>")
            return
        if focus_obj.current_focus <= 0:
            self.caller.msg("Your Focus is depleted.")
            return
        try:
            obs_id = int(self.args.strip())
            obstacle = MysteryObstacle.objects.get(id=obs_id)
        except (ValueError, MysteryObstacle.DoesNotExist):
            self.caller.msg("Obstacle not found.")
            return

        today = date.today()
        existing = ObstacleAttempt.objects.filter(
            obstacle=obstacle, character=char, attempted_date=today
        ).first()
        if existing:
            self.caller.msg("You've already attempted this obstacle today.")
            return

        ocandidates = _obstacle_skill_candidates(obstacle)
        skill_name, skill_val, stat_name, stat_val = _pick_best_skill_for_roll(char, ocandidates)

        from world.utils.roll_utils import roll_skill_check, check_success, format_roll_vs_dv_message
        from world.wound_utils import get_action_penalty

        action_penalty = get_action_penalty(char)
        total, details = roll_skill_check(stat_val, skill_val, modifier=action_penalty)
        success = check_success(total, obstacle.dv)
        focus_damage = _roll_dice("1d6") if success else _roll_dice("2d6")

        focus_obj.current_focus = max(0, focus_obj.current_focus - focus_damage)
        focus_obj.save()
        ObstacleAttempt.objects.create(
            obstacle=obstacle,
            character=char,
            attempted_date=today,
            success=success,
            focus_lost=focus_damage,
        )
        self.caller.msg(
            format_roll_vs_dv_message(
                _humanize_skill_stat_name(stat_name),
                _humanize_skill_stat_name(skill_name),
                stat_val,
                skill_val,
                action_penalty,
                total,
                obstacle.dv,
                details,
            )
        )
        if success:
            self.caller.msg(
                f"|gYou overcome the obstacle!|n Lost {focus_damage} Focus. "
                f"({focus_obj.current_focus} remaining)"
            )
        else:
            self.caller.msg(
                f"|rYou fail to overcome the obstacle.|n Lost {focus_damage} Focus. "
                f"({focus_obj.current_focus} remaining)"
            )

    def _do_sync_leads(self):
        char = _get_character_for_caller(self.caller)
        if not self.args:
            self.caller.msg("Usage: +investigate/sync <character in the room>")
            return
        target = _find_pc_in_same_room(self.caller, self.args.strip())
        if not target:
            self.caller.msg("No single character by that name here.")
            return
        if target == char:
            self.caller.msg("Pick someone else.")
            return
        ok, result = _sync_exposure_to_target(char, target)
        if not ok:
            self.caller.msg(result)
            return
        added = result
        if added:
            self.caller.msg(
                f"|gYou bring them up to speed on what to look for.|n "
                f"{added} new lead(s) now line up for them (|c+investigate/leads|n)."
            )
            target.msg(
                f"|g{char.key}|n walks you through what they noticed; "
                f"{added} new lead(s) click into place for you."
            )
        else:
            self.caller.msg(
                "|yThey already had every lead you could pass along|n (or nothing new applies)."
            )

    def _do_tell_narrative(self):
        char = _get_character_for_caller(self.caller)
        if not self.args:
            self.caller.msg("Usage: +investigate/tell <character in the room>")
            return
        target = _find_pc_in_same_room(self.caller, self.args.strip())
        if not target:
            self.caller.msg("No single character by that name here.")
            return
        if target == char:
            self.caller.msg("Pick someone else.")
            return
        blocks = _narrative_lines_for_successful_clues(char)
        if not blocks:
            self.caller.msg("You have no deciphered lead narratives to share yet.")
            return
        lines = ["|wWhat you share:|n"]
        for mname, chunk in blocks:
            lines.append(f"|c{mname}|n")
            lines.extend(chunk)
        self.caller.msg("\n".join(lines))
        out = [f"|w{char.key} shares what they pieced together:|n"]
        for mname, chunk in blocks:
            out.append(f"|c{mname}|n")
            out.extend(chunk)
        target.msg("\n".join(out))


class CmdMystery(MuxCommand):
    """
    Mysteries: list, info, focus, and staff authoring (Builder).

    Usage:
      +mystery                    - Active mysteries and your Focus
      +mystery/focus              - Focus details
      +mystery/follow <id>       - Follow a mystery (highlights in list)
      +mystery/unfollow <id>     - Stop following
      +mystery/info <id>          - Mystery summary (no spoilers)
      +mystery/create ...         - Staff: create mystery (optional mission id at end of rhs)
      +mystery/public <id>=...    - Staff: player-facing description
      +mystery/start <id>=...     - Staff: where to start looking
      +mystery/scandv <id>=<n>    - Staff: scan DV for this mystery
      +mystery/obstacle ...       - Staff: add obstacle
      +mystery/link ...           - Staff: link to mission board mission (and its job if set)
      +mystery/unlink <id>        - Staff: unlink mission
    """

    key = "+mystery"
    aliases = ["mystery"]
    lock = "cmd:all()"
    help_category = "General"

    def func(self):
        char = _get_character_for_caller(self.caller)
        if not char:
            self.caller.msg("You must be playing a character.")
            return
        if not is_character_approved(char):
            self.caller.msg("You must be approved first.")
            return

        focus_obj = _get_or_create_focus(char)
        int_val = getattr(char.db, "intelligence", 5) or 5
        will_val = getattr(char.db, "willpower", 5) or 5
        max_focus = get_max_focus(int_val, will_val)
        current = focus_obj.current_focus

        if "create" in self.switches:
            return self._staff_create(char)
        if "public" in self.switches:
            return self._staff_set_public()
        if "start" in self.switches:
            return self._staff_set_start()
        if "scandv" in self.switches:
            return self._staff_set_scandv()
        if "obstacle" in self.switches:
            return self._staff_obstacle()
        if "link" in self.switches:
            return self._staff_link()
        if "unlink" in self.switches:
            return self._staff_unlink()

        if "follow" in self.switches:
            return self._do_follow(char)
        if "unfollow" in self.switches:
            return self._do_unfollow(char)

        if "info" in self.switches:
            return self._show_info()

        if "focus" in self.switches:
            out = [
                header("Focus"),
                f"  |gFocus:|n {current}/{max_focus}",
                "  Focus recovers INT + WILL every 24 hours. |c+rest|n for a concentration bonus.",
                footer(),
            ]
            self.caller.msg("\n".join(out))
            return

        self._list_mysteries(char, focus_obj, current, max_focus)

    def _list_mysteries(self, char, focus_obj, current, max_focus):
        broad = list(Mystery.objects.filter(is_solved=False))
        followed_ids = set(
            MysteryFollower.objects.filter(character=char).values_list("mystery_id", flat=True)
        )
        broad.sort(key=lambda m: (0 if m.id in followed_ids else 1, m.name.lower()))
        lines = [
            header("Mysteries & Investigation"),
            f"  |gFocus:|n {current}/{max_focus}",
            "",
            "  |wOpen investigations:|n  (|w★|n = you follow)",
        ]
        if not broad:
            lines.append("  (None listed -- ask staff or check the grid.)")
        else:
            for m in broad:
                pd = (m.public_description or "").strip()
                hint = (m.starting_location_hint or "").strip()
                if pd:
                    desc = pd[:120] + ("..." if len(pd) > 120 else "")
                else:
                    desc = (m.goal or "")[:120] + ("..." if len(m.goal or "") > 120 else "")
                loc = f" |cStart:|n {hint}" if hint else ""
                star = "|w★|n " if m.id in followed_ids else ""
                lines.append(f"  {star}|y#{m.id}|n {m.name} -- {desc}{loc}")
        pending_obs = _pending_gating_obstacles_for_character(char)
        if pending_obs:
            lines.append("")
            lines.append("  |yBlocks you can clear (then new leads may appear):|n")
            for obs in pending_obs[:6]:
                lines.append(_format_obstacle_overcome_hint(obs))
            if len(pending_obs) > 6:
                lines.append("  (see |c+investigate/leads|n for full list)")
        lines.append("")
        lines.append("  |c+mystery/info <id>|n |c+mystery/follow <id>|n  |c+investigate/scan|n")
        lines.append(footer())
        self.caller.msg("\n".join(lines))

    def _do_follow(self, char):
        if not self.args:
            self.caller.msg("Usage: +mystery/follow <mystery id>")
            return
        try:
            mid = int(self.args.strip())
            m = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        if m.is_solved:
            self.caller.msg("That mystery is already solved.")
            return
        follow_mystery_for_character(char, m)
        self.caller.msg(f"You are now following |y{m.name}|n (★ on +mystery).")

    def _do_unfollow(self, char):
        if not self.args:
            self.caller.msg("Usage: +mystery/unfollow <mystery id>")
            return
        try:
            mid = int(self.args.strip())
            m = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        unfollow_mystery_for_character(char, m)
        self.caller.msg(f"You stopped following |y{m.name}|n.")

    def _show_info(self):
        char = _get_character_for_caller(self.caller)
        if not self.args:
            self.caller.msg("Usage: +mystery/info <mystery id>")
            return
        try:
            mid = int(self.args.strip())
            m = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        nc = m.clues.count()
        no = m.obstacles.count()
        pd = (m.public_description or m.goal or "").strip()
        sh = (m.starting_location_hint or "").strip()
        lines = [
            header(f"Mystery #{m.id}: {m.name}"),
            f"  {pd}",
            "",
            f"  |wClues in play:|n {nc}  |wObstacles:|n {no}",
        ]
        if char and MysteryFollower.objects.filter(character=char, mystery=m).exists():
            lines.append("  |wYou are following this investigation.|n")
        if sh:
            lines.append(f"  |wWhere to start:|n {sh}")
        lines.append(f"  |wStatus:|n {'Solved' if m.is_solved else 'Open'}")
        if not m.is_solved and no > 0:
            lines.append("")
            lines.append("  |wObstacles (use when fiction hits a wall):|n")
            for o in m.obstacles.all().order_by("id"):
                sk = (o.skill_used or "any").replace("_", " ")
                lines.append(
                    f"    |m#{o.id}|n {o.obstacle_type} |wDV{o.dv}|n ({sk})  "
                    f"|c+investigate/overcome {o.id}|n"
                )
        lines.append(footer())
        self.caller.msg("\n".join(lines))

    def _check_builder(self):
        if not (
            self.caller.check_permstring("builders")
            or self.caller.check_permstring("admin")
            or self.caller.check_permstring("Admin")
        ):
            self.caller.msg("Builder permission required.")
            return False
        return True

    def _staff_create(self, char):
        if not self._check_builder():
            return
        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: +mystery/create <name>=<goal>,<complexity or tier>[,<mission id>]"
            )
            return
        name = self.lhs.strip()
        rhs = self.rhs.strip()
        mission_id = None
        if "," in rhs:
            left, right = rhs.rsplit(",", 1)
            if right.strip().isdigit():
                mission_id = int(right.strip())
                rhs = left
        parts = [p.strip() for p in rhs.split(",", 1)]
        goal = parts[0] if parts else ""
        complexity_arg = (parts[1] if len(parts) > 1 else "50").strip().lower()
        tier_data = COMPLEXITY_TIERS.get(complexity_arg)
        if tier_data:
            complexity = tier_data["value"]
            difficulty_level = complexity_arg
        else:
            try:
                complexity = int(complexity_arg)
                difficulty_level = "average"
            except ValueError:
                complexity = 50
                difficulty_level = "average"
        m = Mystery.objects.create(
            name=name,
            goal=goal,
            difficulty_level=difficulty_level,
            max_complexity=complexity,
            current_complexity=complexity,
            created_by=char,
            public_description=goal[:500],
        )
        tail = ""
        if mission_id is not None:
            from world.mission_board.models import Mission

            try:
                miss = Mission.objects.get(id=mission_id)
            except Mission.DoesNotExist:
                tail = f" |r(Mission #{mission_id} not found -- not linked.)|n"
            else:
                m.mission = miss
                m.save()
                sync_followers_when_mystery_linked_to_mission(m)
                if miss.job_id:
                    tail = (
                        f" |gLinked to mission #{miss.id}; job #{miss.job_id} "
                        f"gets investigation updates on solve.|n"
                    )
                else:
                    tail = (
                        f" |gLinked to mission #{miss.id}|n "
                        f"(that mission has no job yet; create one with mission acceptance flow)."
                    )
        self.caller.msg(
            f"Created Mystery #{m.id}: {m.name}. Set |c+mystery/public {m.id}=...|n and "
            f"|c+mystery/start {m.id}=...|n for players.{tail}"
        )

    def _staff_set_public(self):
        if not self._check_builder():
            return
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +mystery/public <id>=<player-facing description>")
            return
        try:
            mid = int(self.lhs.strip())
            m = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        m.public_description = self.rhs.strip()
        m.save()
        self.caller.msg(f"Updated public description for #{m.id}.")

    def _staff_set_start(self):
        if not self._check_builder():
            return
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +mystery/start <id>=<where to start looking>")
            return
        try:
            mid = int(self.lhs.strip())
            m = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        m.starting_location_hint = self.rhs.strip()
        m.save()
        self.caller.msg(f"Updated starting location hint for #{m.id}.")

    def _staff_set_scandv(self):
        if not self._check_builder():
            return
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +mystery/scandv <id>=<dv>")
            return
        try:
            mid = int(self.lhs.strip())
            dv = int(self.rhs.strip())
            m = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Invalid id or mystery.")
            return
        m.scan_dv = max(3, min(30, dv))
        m.save()
        self.caller.msg(f"Mystery #{m.id} scan DV set to {m.scan_dv}.")

    def _staff_obstacle(self):
        if not self._check_builder():
            return
        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: +mystery/obstacle <mystery id>=<type>,<skill>,<dv>[,description]"
            )
            return
        try:
            mid = int(self.lhs.strip())
            mystery = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        parts = [p.strip() for p in self.rhs.split(",", 3)]
        obs_type = parts[0] if parts else "Distraction"
        skill = parts[1] if len(parts) > 1 else "streetwise"
        try:
            dv = int(parts[2]) if len(parts) > 2 and parts[2] else 13
        except (ValueError, TypeError):
            dv = 13
        description = parts[3] if len(parts) > 3 else ""
        is_ticking = "ticking" in obs_type.lower() or "clock" in obs_type.lower()
        obs = MysteryObstacle.objects.create(
            mystery=mystery,
            obstacle_type=obs_type,
            skill_used=skill,
            dv=dv,
            description=description,
            is_ticking_clock=is_ticking,
        )
        self.caller.msg(
            f"Added Obstacle #{obs.id} to {mystery.name}. Players: |c+investigate/overcome {obs.id}|n"
        )

    def _staff_link(self):
        if not self._check_builder():
            return
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +mystery/link <mystery id>=<mission id>")
            return
        try:
            mid = int(self.lhs.strip())
            mystery = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        try:
            mission_id = int(self.rhs.strip())
            from world.mission_board.models import Mission
            mission = Mission.objects.get(id=mission_id)
        except (ValueError, Mission.DoesNotExist):
            self.caller.msg("Mission not found.")
            return
        mystery.mission = mission
        mystery.save()
        sync_followers_when_mystery_linked_to_mission(mystery)
        extra = ""
        if mission.job_id:
            extra = f" Job #{mission.job_id} will receive updates when this mystery is solved."
        self.caller.msg(
            f"Linked mystery to Mission #{mission.id}: {mission.name}.{extra}"
        )

    def _staff_unlink(self):
        if not self._check_builder():
            return
        if not self.args:
            self.caller.msg("Usage: +mystery/unlink <mystery id>")
            return
        try:
            mid = int(self.args.strip())
            mystery = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        mystery.mission = None
        mystery.save()
        self.caller.msg(f"Unlinked mission from '{mystery.name}'.")


class CmdClue(MuxCommand):
    """
    Staff: clues, placement, linking, listing.

    Usage:
      +clue/create <mid>=...
      +clue/add <target>=<clue id>[/element]
      +clue/remove ...
      +clue/list [mystery]
      +clue/destroy ...
      +clue/link / +clue/requires ...
      +clue/playerhint <id>=...
      +clue/gate <clue id>=<obstacle id>
      +clue/priority <id>=<n>
      +clue/resetattempts <character>[=<clue id>]  (add /all for full history)
      +clue/resetobstacle <character>[=<obstacle id>]  (add /all for full history)
    """

    key = "+clue"
    aliases = ["clue"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        if "create" in self.switches:
            return self._create()
        if "add" in self.switches:
            return self._add()
        if "remove" in self.switches:
            return self._remove()
        if "list" in self.switches:
            return self._list_all()
        if "destroy" in self.switches:
            return self._destroy()
        if "requires" in self.switches:
            return self._link(requires=True)
        if "link" in self.switches:
            return self._link(requires=False)
        if "playerhint" in self.switches:
            return self._playerhint()
        if "gate" in self.switches:
            return self._gate()
        if "priority" in self.switches:
            return self._priority()
        if "resetattempts" in self.switches:
            return self._reset_attempts()
        if "resetobstacle" in self.switches:
            return self._reset_obstacle()

        self.caller.msg(
            "Usage: |c+clue/create|n, |c+clue/add|n, |c+clue/list|n, |c+clue/requires|n, ..."
        )

    def _create(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +clue/create <mystery id>=<type>,<skills>,<dv>,<obfuscation>[,description]")
            return
        try:
            mid = int(self.lhs.strip())
            mystery = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        parts = [p.strip() for p in self.rhs.split(",")]
        clue_type = parts[0].lower() if parts else "deduction"
        skills = parts[1].replace(";", ", ") if len(parts) > 1 else "deduction"
        try:
            dv = int(parts[2]) if len(parts) > 2 else 13
        except (ValueError, IndexError):
            dv = 13
        try:
            obfuscation = int(parts[3]) if len(parts) > 3 else 0
        except (ValueError, IndexError):
            obfuscation = 0
        defaults = CLUE_TYPES.get(clue_type, {})
        damage_dice = defaults.get("damage_dice", "3d6")
        focus_damage_dice = defaults.get("focus_damage_dice", "2d6")
        fumble_effect = defaults.get("fumble_effect") or ""
        description = ", ".join(parts[4:]) if len(parts) > 4 else ""
        c = MysteryClue.objects.create(
            mystery=mystery,
            clue_type=clue_type,
            skills_used=skills,
            dv=dv,
            obfuscation=obfuscation,
            damage_dice=damage_dice,
            focus_damage_dice=focus_damage_dice,
            fumble_effect=fumble_effect,
            description=description,
        )
        self.caller.msg(
            f"Created Clue #{c.id}. |c+clue/add <room>={c.id}|n or |c={c.id}/element|n. "
            f"|c+clue/playerhint {c.id}=...|n"
        )

    def _add(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +clue/add <target>=<clue id>[/element]")
            return
        target_name = self.lhs.strip()
        clue_arg = self.rhs.strip()
        target = self.caller.search(target_name, global_search=True)
        if not target:
            return
        try:
            clue_id, element_key = _parse_clue_and_element(clue_arg)
            clue = MysteryClue.objects.get(id=clue_id)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Invalid clue id.")
            return
        elem = element_key or ""
        _, created = ClueLocation.objects.get_or_create(
            clue=clue,
            location_object=target,
            element_key=elem,
            defaults={},
        )
        if created:
            extra = f" (element '{elem}')" if elem else ""
            self.caller.msg(f"Attached clue #{clue_id} to {target.key}{extra}.")
        else:
            self.caller.msg("Already attached that way.")

    def _remove(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +clue/remove <target>=<id>[/element]")
            return
        target_name = self.lhs.strip()
        try:
            clue_id, element_key = _parse_clue_and_element(self.rhs.strip())
            clue = MysteryClue.objects.get(id=clue_id)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Clue not found.")
            return
        target = self.caller.search(target_name, global_search=True)
        if not target:
            return
        deleted, _ = ClueLocation.objects.filter(
            clue=clue,
            location_object=target,
            element_key=element_key or "",
        ).delete()
        if deleted:
            self.caller.msg("Removed.")
        else:
            self.caller.msg("Not found on that target.")

    def _list_all(self):
        mystery_arg = (self.args or "").strip()
        if mystery_arg:
            try:
                mid = int(mystery_arg)
                mysteries = Mystery.objects.filter(id=mid)
            except ValueError:
                mysteries = Mystery.objects.filter(name__icontains=mystery_arg)
            if not mysteries.exists():
                self.caller.msg("Mystery not found.")
                return
            mysteries = list(mysteries)
        else:
            mysteries = list(Mystery.objects.all().order_by("name"))

        lines = [header("Investigation Clues (staff)")]
        for m in mysteries:
            clues = m.clues.all().order_by("id")
            obstacles = m.obstacles.all().order_by("id")
            lines.append(section_header(m.name))
            lines.append(f"  Goal: {m.goal[:60]}{'...' if len(m.goal) > 60 else ''}")
            lines.append(
                f"  Difficulty: {m.difficulty_level} | "
                f"Complexity: {m.current_complexity}/{m.max_complexity} | Solved: {m.is_solved}"
            )
            if obstacles.exists():
                lines.append("  Obstacles:")
                for o in obstacles:
                    lines.append(f"    |y#{o.id}|n {o.obstacle_type} DV{o.dv} ({o.skill_used or 'any'})")
            for c in clues:
                reqs = list(c.required_clues.values_list("id", flat=True))
                locs = ClueLocation.objects.filter(clue=c)

                def _fmt_loc(loc):
                    if loc.element_key:
                        return f"{loc.location_object.key}<{loc.element_key}>"
                    return str(loc.location_object.key)

                loc_str = ", ".join(_fmt_loc(loc) for loc in locs[:3])
                if locs.count() > 3:
                    loc_str += f" (+{locs.count() - 3} more)"
                gate = ""
                if c.gating_obstacle_id:
                    gate = f" [gate obs#{c.gating_obstacle_id}]"
                lines.append(
                    f"    |y#{c.id}|n {c.clue_type} DV{c.dv} pri={c.discovery_priority}{gate} "
                    f"{'[requires: ' + ','.join(f'#{r}' for r in reqs) + ']' if reqs else ''}"
                )
                if loc_str:
                    lines.append(f"      @ {loc_str}")
            lines.append("")
        lines.append(footer())
        self.caller.msg("\n".join(lines))

    def _destroy(self):
        if not self.args:
            self.caller.msg("Usage: +clue/destroy <clue id> OR <target>=<id>[/element]")
            return
        if "=" in self.args:
            target_name = self.lhs.strip()
            try:
                clue_id, element_key = _parse_clue_and_element(self.rhs.strip())
                clue = MysteryClue.objects.get(id=clue_id)
            except (ValueError, MysteryClue.DoesNotExist):
                self.caller.msg("Clue not found.")
                return
            target = self.caller.search(target_name, global_search=True)
            if not target:
                return
            deleted, _ = ClueLocation.objects.filter(
                clue=clue,
                location_object=target,
                element_key=element_key or "",
            ).delete()
            self.caller.msg("Removed from location." if deleted else "Not found.")
            return
        try:
            clue_id = int(self.args.strip())
            clue = MysteryClue.objects.get(id=clue_id)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Clue not found.")
            return
        clue.delete()
        self.caller.msg(f"Destroyed clue #{clue_id}.")

    def _link(self, requires=False):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +clue/link <id>=<id> or +clue/requires <id>=<id>")
            return
        try:
            c1_id = int(self.lhs.strip())
            c1 = MysteryClue.objects.get(id=c1_id)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Clue not found (left).")
            return
        try:
            c2_id = int(self.rhs.strip())
            c2 = MysteryClue.objects.get(id=c2_id)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Clue not found (right).")
            return
        if c1.mystery_id != c2.mystery_id:
            self.caller.msg("Both clues must belong to the same mystery.")
            return
        if requires:
            c1.required_clues.add(c2)
            self.caller.msg(f"Clue #{c1_id} now requires #{c2_id} deciphered first.")
        else:
            c1.linked_clues.add(c2)
            self.caller.msg(f"Linked #{c1_id} <-> #{c2_id}.")

    def _playerhint(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +clue/playerhint <clue id>=<text for players when exposed>")
            return
        try:
            cid = int(self.lhs.strip())
            c = MysteryClue.objects.get(id=cid)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Clue not found.")
            return
        c.player_hint = self.rhs.strip()
        c.save()
        self.caller.msg(f"Player hint set for clue #{c.id}.")

    def _gate(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +clue/gate <clue id>=<obstacle id> (or 0 to clear)")
            return
        try:
            cid = int(self.lhs.strip())
            oid = int(self.rhs.strip())
            c = MysteryClue.objects.get(id=cid)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Invalid clue.")
            return
        if oid == 0:
            c.gating_obstacle = None
            c.save()
            self.caller.msg("Gating obstacle cleared.")
            return
        try:
            obs = MysteryObstacle.objects.get(id=oid)
        except MysteryObstacle.DoesNotExist:
            self.caller.msg("Obstacle not found.")
            return
        if obs.mystery_id != c.mystery_id:
            self.caller.msg("Obstacle must belong to the same mystery.")
            return
        c.gating_obstacle = obs
        c.save()
        self.caller.msg(f"Clue #{c.id} gated by obstacle #{obs.id}.")

    def _priority(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +clue/priority <clue id>=<number> (lower = found earlier on scan)")
            return
        try:
            cid = int(self.lhs.strip())
            pr = int(self.rhs.strip())
            c = MysteryClue.objects.get(id=cid)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Invalid.")
            return
        c.discovery_priority = max(0, pr)
        c.save()
        self.caller.msg(f"Discovery priority set to {c.discovery_priority}.")

    def _reset_attempts(self):
        """Clear ClueAttempt rows so a character can evidence-check again (today by default)."""
        today = date.today()
        mode_all = "all" in self.switches
        if not self.args:
            self.caller.msg(
                "Usage: |c+clue/resetattempts <character>[=<clue id>]|n clears |ytoday's|n evidence check "
                "for that lead (or all leads today if no clue id). "
                "|c+clue/resetattempts/all <character>[=<clue id>]|n removes |rall|n stored attempts "
                "(can break chains that depend on deciphered leads)."
            )
            return
        if "=" in self.args:
            char_name = self.lhs.strip()
            try:
                clue_id = int(self.rhs.strip())
            except ValueError:
                self.caller.msg("Clue id must be a number.")
                return
        else:
            char_name = self.args.strip()
            clue_id = None
        if not char_name:
            self.caller.msg("Specify a character.")
            return
        char, err = _staff_resolve_character(char_name)
        if err:
            self.caller.msg(err)
            return
        if mode_all:
            if clue_id is not None:
                n, _ = ClueAttempt.objects.filter(character=char, clue_id=clue_id).delete()
                self.caller.msg(
                    f"Removed {n} evidence-record(s) for {char.key} on clue #{clue_id}. "
                    "(Mystery complexity is unchanged.)"
                )
            else:
                n, _ = ClueAttempt.objects.filter(character=char).delete()
                self.caller.msg(
                    f"Removed {n} evidence-record(s) for {char.key} (all clues). "
                    "|yPrerequisite chains may be broken until they decipher again.|n"
                )
            return
        if clue_id is not None:
            n, _ = ClueAttempt.objects.filter(
                character=char, clue_id=clue_id, attempted_date=today
            ).delete()
        else:
            n, _ = ClueAttempt.objects.filter(character=char, attempted_date=today).delete()
        self.caller.msg(
            f"Cleared today's evidence attempt(s) for {char.key} ({n} row(s))."
        )

    def _reset_obstacle(self):
        """Clear ObstacleAttempt rows (overcome obstacle daily lock)."""
        today = date.today()
        mode_all = "all" in self.switches
        if not self.args:
            self.caller.msg(
                "Usage: |c+clue/resetobstacle <character>=<obstacle id>|n clears today's overcome try. "
                "|c+clue/resetobstacle <character>|n clears today's tries on all obstacles. "
                "|c+clue/resetobstacle/all ...|n wipes full history."
            )
            return
        if "=" in self.args:
            char_name = self.lhs.strip()
            try:
                obs_id = int(self.rhs.strip())
            except ValueError:
                self.caller.msg("Obstacle id must be a number.")
                return
        else:
            char_name = self.args.strip()
            obs_id = None
        if not char_name:
            self.caller.msg("Specify a character.")
            return
        char, err = _staff_resolve_character(char_name)
        if err:
            self.caller.msg(err)
            return
        if mode_all:
            if obs_id is not None:
                n, _ = ObstacleAttempt.objects.filter(character=char, obstacle_id=obs_id).delete()
                self.caller.msg(
                    f"Removed {n} obstacle-record(s) for {char.key} on obstacle #{obs_id}."
                )
            else:
                n, _ = ObstacleAttempt.objects.filter(character=char).delete()
                self.caller.msg(
                    f"Removed {n} obstacle-record(s) for {char.key} (all obstacles)."
                )
            return
        if obs_id is not None:
            n, _ = ObstacleAttempt.objects.filter(
                character=char, obstacle_id=obs_id, attempted_date=today
            ).delete()
        else:
            n, _ = ObstacleAttempt.objects.filter(character=char, attempted_date=today).delete()
        self.caller.msg(
            f"Cleared today's obstacle attempt(s) for {char.key} ({n} row(s))."
        )


class CmdCluesStaff(MuxCommand):
    """Alias for +clue/list (staff)."""

    key = "+clues"
    aliases = ["clues"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        proxy = CmdClue()
        proxy.caller = self.caller
        proxy.args = self.args
        proxy.switches = ["list"]
        proxy.session = self.session
        proxy.cmdset = self.cmdset
        CmdClue.func(proxy)


class CmdRest(MuxCommand):
    """Rest / concentration for Focus -- unchanged."""

    key = "+rest"
    aliases = ["rest"]
    lock = "cmd:all()"
    help_category = "General"

    def func(self):
        char = _get_character_for_caller(self.caller)
        if not char:
            self.caller.msg("You must be playing a character to rest.")
            return
        if not is_character_approved(char):
            self.caller.msg("You must be approved by staff before using the mystery system.")
            return

        focus_obj = _get_or_create_focus(char)
        today = date.today()
        if focus_obj.last_concentrate_date == today:
            self.caller.msg("You've already attempted to concentrate today. Try again tomorrow.")
            return

        max_focus = focus_obj.get_max_focus()
        room = max(0, max_focus - focus_obj.current_focus)
        if room == 0:
            self.caller.msg("Your Focus is already full.")
            focus_obj.last_concentrate_date = today
            focus_obj.save()
            return

        skill_val = getattr(char.db, "concentration", 0) or 0
        if hasattr(char, "get_skill"):
            skill_val = char.get_skill("concentration")
        stat_val = getattr(char.db, "willpower", 5) or 5
        from world.utils.roll_utils import roll_skill_check, check_success, format_roll_vs_dv_message
        from world.wound_utils import get_action_penalty

        action_penalty = get_action_penalty(char)
        total, details = roll_skill_check(stat_val, skill_val, modifier=action_penalty)
        success = check_success(total, 15)

        self.caller.msg(
            format_roll_vs_dv_message(
                "Willpower",
                "Concentration",
                stat_val,
                skill_val,
                action_penalty,
                total,
                15,
                details,
            )
        )

        focus_obj.last_concentrate_date = today
        if success:
            gain = min(5, room)
            focus_obj.current_focus = min(max_focus, focus_obj.current_focus + gain)
            focus_obj.save()
            self.caller.msg(
                f"|gSuccess!|n You focus your mind. Recovered {gain} Focus. "
                f"({focus_obj.current_focus}/{max_focus})"
            )
            if hasattr(char, "character_sheet") and char.character_sheet:
                try:
                    from world.cyberware.implanted_armor import apply_daily_natural_healing_implanted_armor

                    healed, hmsg = apply_daily_natural_healing_implanted_armor(char.character_sheet)
                    if healed and hmsg:
                        self.caller.msg(f"|cImplanted armor:|n {hmsg}")
                except Exception:
                    pass
        else:
            focus_obj.save()
            self.caller.msg(
                "You try to concentrate but can't quite clear your head. "
                "No bonus Focus this time."
            )


def _staff_resolve_character(arg):
    """Resolve a single Character from a name string. Returns (character, err_msg)."""
    from evennia.utils.search import search_object

    arg = (arg or "").strip()
    if not arg:
        return None, "Specify a character name."
    matches = search_object(arg, typeclass="typeclasses.characters.Character")
    if not matches:
        return None, f"No character matching '{arg}'."
    if len(matches) > 1:
        names = ", ".join(getattr(o, "key", str(o)) for o in matches[:6])
        return None, f"Ambiguous ({len(matches)} matches): {names}"
    return matches[0], None


class CmdStaffFocus(MuxCommand):
    """
    Staff: view or reset investigation Focus for a character (Builder).

    Usage:
      +focus/show <character>       - Current / max Focus
      +focus/refresh <character>     - Set Focus to maximum
      +focus/set <character>=<n>     - Set Focus (0 to max)
      +focus/resetrest <character>   - Clear +rest daily lock (can use +rest again today)
    """

    key = "+focus"
    aliases = ["stafffocus"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        if "refresh" in self.switches:
            return self._do_refresh()
        if "set" in self.switches:
            return self._do_set()
        if "resetrest" in self.switches:
            return self._do_resetrest()
        # default: show
        return self._do_show()

    def _get_focus(self, char):
        focus_obj = _get_or_create_focus(char)
        mx = focus_obj.get_max_focus()
        return focus_obj, mx

    def _do_show(self):
        name = (self.args or "").strip()
        if not name:
            self.caller.msg("Usage: +focus <character> or +focus/show <character>")
            return
        char, err = _staff_resolve_character(name)
        if err:
            self.caller.msg(err)
            self.caller.msg("Usage: +focus/show <character>")
            return
        focus_obj, mx = self._get_focus(char)
        self.caller.msg(
            f"|w{char.key}|n Focus: |g{focus_obj.current_focus}|n / |c{mx}|n"
        )

    def _do_refresh(self):
        name = (self.args or "").strip()
        char, err = _staff_resolve_character(name)
        if err:
            self.caller.msg(err)
            self.caller.msg("Usage: +focus/refresh <character>")
            return
        focus_obj, mx = self._get_focus(char)
        old = focus_obj.current_focus
        focus_obj.current_focus = mx
        focus_obj.save()
        self.caller.msg(
            f"|w{char.key}|n Focus refreshed: |y{old}|n -> |g{focus_obj.current_focus}|n / {mx}"
        )

    def _do_set(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +focus/set <character>=<amount>")
            return
        char, err = _staff_resolve_character(self.lhs.strip())
        if err:
            self.caller.msg(err)
            return
        try:
            n = int(self.rhs.strip())
        except ValueError:
            self.caller.msg("Amount must be an integer.")
            return
        focus_obj, mx = self._get_focus(char)
        n = max(0, min(mx, n))
        old = focus_obj.current_focus
        focus_obj.current_focus = n
        focus_obj.save()
        self.caller.msg(
            f"|w{char.key}|n Focus set: |y{old}|n -> |g{focus_obj.current_focus}|n / {mx}"
        )

    def _do_resetrest(self):
        name = (self.args or "").strip()
        char, err = _staff_resolve_character(name)
        if err:
            self.caller.msg(err)
            self.caller.msg("Usage: +focus/resetrest <character>")
            return
        focus_obj, _mx = self._get_focus(char)
        focus_obj.last_concentrate_date = None
        focus_obj.save()
        self.caller.msg(
            f"|w{char.key}|n +rest daily lock cleared. They may use |c+rest|n again today."
        )
