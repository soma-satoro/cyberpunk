"""Mystery system services - mission/job updates on solve."""

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
