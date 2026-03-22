"""Mystery system services - mission/job updates, followers, room display."""

from django.db.models import Q
from django.utils import timezone


def update_mission_on_mystery_solve(mystery):
    """
    When a mystery is solved, update the linked mission and its job.
    """
    mission = mystery.mission
    if not mission:
        return

    update_text = f"[Mystery Solved] {mystery.name}: {mystery.goal}"
    mission.updates = mission.updates or []
    mission.updates.append({
        "date": timezone.now().isoformat(),
        "author": "Investigation System",
        "text": update_text,
    })
    mission.save()

    if mission.job:
        mission.job.comments = mission.job.comments or []
        mission.job.comments.append({
            "author": "Investigation System",
            "created_at": timezone.now().isoformat(),
            "text": update_text,
        })
        mission.job.save()


def clue_locations_for_room(room):
    """ClueLocation rows tied to this room, its contents, or its exits (same scope as scan)."""
    from world.mystery.models import ClueLocation

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
    return ClueLocation.objects.filter(q).select_related("clue", "clue__mystery")


def get_deciphered_clue_display_lines(looker, room):
    """
    Lines for room description: clues in this room's scope the looker has successfully deciphered.
    """
    from world.mystery.models import ClueAttempt

    if not looker or not room:
        return []
    locs = clue_locations_for_room(room)
    seen = set()
    rows = []
    for loc in locs:
        cid = loc.clue_id
        if cid in seen:
            continue
        seen.add(cid)
        clue = loc.clue
        if not ClueAttempt.objects.filter(clue=clue, character=looker, success=True).exists():
            continue
        m = clue.mystery
        label = (clue.player_hint or "").strip() or (clue.description or "").strip()
        if not label:
            label = f"{clue.clue_type} lead"
        if len(label) > 220:
            label = label[:217] + "..."
        loc_note = ""
        if loc.element_key:
            loc_note = f" ({loc.element_key})"
        elif loc.location_object_id and loc.location_object_id != room.id:
            lo = loc.location_object
            if lo:
                loc_note = f" ({lo.key})"
        rows.append((clue.discovery_priority, clue.id, m.name, label, loc_note))
    rows.sort(key=lambda x: (x[0], x[1]))
    out = []
    for _pri, _cid, mname, label, loc_note in rows:
        out.append(f"  |c{mname}|n{loc_note}: {label}")
    return out


def follow_mystery_for_character(character, mystery):
    from world.mystery.models import MysteryFollower

    if not character or not mystery:
        return
    MysteryFollower.objects.get_or_create(character=character, mystery=mystery)


def unfollow_mystery_for_character(character, mystery):
    from world.mystery.models import MysteryFollower

    MysteryFollower.objects.filter(character=character, mystery=mystery).delete()


def follow_mysteries_for_mission_character(character, mission):
    """Auto-follow all open mysteries linked to this mission."""
    from world.mystery.models import Mystery

    if not character or not mission:
        return
    for mystery in Mystery.objects.filter(mission=mission, is_solved=False):
        follow_mystery_for_character(character, mystery)


def sync_followers_when_mystery_linked_to_mission(mystery):
    """When staff links a mystery to a mission, team members auto-follow the mystery."""
    if not mystery or not mystery.mission_id:
        return
    mission = mystery.mission
    for mtm in mission.team_members.all():
        follow_mystery_for_character(mtm.character, mystery)
