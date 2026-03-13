"""
Legacy mission system - DEPRECATED. Superseded by world.mission_board.
This stub exists only to satisfy imports during Django startup.
No Evennia/Django imports at load time - use world.mission_board for missions.
"""


class Mission:
    """Deprecated placeholder. Use world.mission_board.models.Mission."""

    pass


class MissionBoard:
    """Deprecated placeholder. Use world.mission_board."""

    pass


def init_mission_system():
    """Deprecated. world.mission_board.services.init_mission_system is used instead."""
    pass


def get_or_create_mission_board():
    """Deprecated."""
    return None
