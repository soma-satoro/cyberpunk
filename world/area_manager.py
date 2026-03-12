"""
Area Manager for Cyberpunk MUD

Manages game areas, room codes, and coordinates for mapping.
Uses ServerConfig for persistent storage.
"""

import json
from evennia.server.models import ServerConfig


# Default Cyberpunk-themed areas (2-char codes for room format XX00)
DEFAULT_AREAS = {
    "NC": {"name": "Night City", "description": "The megacity of the future", "rooms": {}, "next_room": 1},
    "WB": {"name": "Westbrook", "description": "Corporate and entertainment district", "rooms": {}, "next_room": 1},
    "WA": {"name": "Watson", "description": "Industrial and immigrant district", "rooms": {}, "next_room": 1},
    "HE": {"name": "Heywood", "description": "Working class district", "rooms": {}, "next_room": 1},
    "SD": {"name": "Santo Domingo", "description": "Industrial and power district", "rooms": {}, "next_room": 1},
    "PA": {"name": "Pacifico", "description": "Coastal and combat zone", "rooms": {}, "next_room": 1},
    "BL": {"name": "Badlands", "description": "Wasteland outside the city", "rooms": {}, "next_room": 1},
    "OO": {"name": "OOC Area", "description": "Out of character areas", "rooms": {}, "next_room": 1},
}


class AreaManager:
    """Manages area codes and room assignments."""

    CONFIG_KEY = "area_manager_data"

    def _get_data(self):
        """Get persisted area data."""
        try:
            data = ServerConfig.objects.conf(key=self.CONFIG_KEY, default="{}")
            if isinstance(data, str):
                return json.loads(data)
            return data
        except (json.JSONDecodeError, TypeError):
            return {}

    def _save_data(self, data):
        """Persist area data."""
        ServerConfig.objects.conf(key=self.CONFIG_KEY, value=json.dumps(data))

    def get_areas(self):
        """Return all areas. Format: {code: {name, description, rooms: {num: room_id}, next_room}}"""
        data = self._get_data()
        if not data.get("areas"):
            self._init_default_areas()
            return self._get_data().get("areas", DEFAULT_AREAS)
        return data["areas"]

    def _init_default_areas(self):
        """Initialize with default Cyberpunk areas."""
        data = self._get_data()
        data["areas"] = dict(DEFAULT_AREAS)
        data["coordinates"] = data.get("coordinates", {})
        self._save_data(data)

    def validate_area_code(self, code):
        """Check if area code exists. Supports 2-4 char codes (NC, WB, WAT, etc.)."""
        areas = self.get_areas()
        return code.upper() in areas

    def get_area_info(self, code):
        """Get info dict for an area."""
        areas = self.get_areas()
        return areas.get(code.upper())

    def get_next_room_number(self, code):
        """Get next room number as full code string (e.g., NC01, WB03)."""
        info = self.get_area_info(code)
        if not info:
            return None
        num = info["next_room"]
        return f"{code.upper()}{num:02d}"

    def get_area_rooms(self, code):
        """Get {room_number: room_id} for an area."""
        info = self.get_area_info(code)
        if not info:
            return {}
        return info.get("rooms", {})

    def register_room(self, area_code, room_number, room_id):
        """Register a room in an area."""
        data = self._get_data()
        areas = data.get("areas", {})
        code = area_code.upper()

        if code not in areas:
            areas[code] = {"name": code, "description": "", "rooms": {}, "next_room": 1}

        areas[code]["rooms"][room_number] = room_id
        if room_number >= areas[code]["next_room"]:
            areas[code]["next_room"] = room_number + 1

        data["areas"] = areas
        self._save_data(data)

    def add_area(self, code, name, description=""):
        """Add a new area. Code must be 2-4 characters."""
        code = code.upper()
        if len(code) < 2 or len(code) > 4:
            return False, "Area code must be 2-4 characters."

        data = self._get_data()
        areas = data.get("areas", {})

        if code in areas:
            return False, f"Area {code} already exists."

        areas[code] = {"name": name, "description": description, "rooms": {}, "next_room": 1}
        data["areas"] = areas
        self._save_data(data)
        return True, f"Area {code} ({name}) added."

    def remove_area(self, code):
        """Remove an area if it has no rooms."""
        code = code.upper()
        data = self._get_data()
        areas = data.get("areas", {})

        if code not in areas:
            return False, f"Area {code} not found."

        if areas[code].get("rooms"):
            return False, f"Cannot remove {code}: it has {len(areas[code]['rooms'])} rooms. Remove rooms first."

        del areas[code]
        data["areas"] = areas
        self._save_data(data)
        return True, f"Area {code} removed."

    def set_room_coordinates(self, room_id, x, y):
        """Store room coordinates for mapping."""
        data = self._get_data()
        coords = data.get("coordinates", {})
        coords[str(room_id)] = (int(x), int(y))
        data["coordinates"] = coords
        self._save_data(data)
        return True

    def get_room_coordinates(self, room_id):
        """Get (x, y) for a room or None."""
        data = self._get_data()
        coords = data.get("coordinates", {})
        return coords.get(str(room_id))


# Singleton instance
_area_manager = None


def get_area_manager():
    """Return the global AreaManager instance."""
    global _area_manager
    if _area_manager is None:
        _area_manager = AreaManager()
    return _area_manager
