"""
Rental service for apartment creation, management, and rent collection.

Handles eurodollar-based rental checks (threshold, not deduction),
purchase option, co-residents, partners, and room generation.
"""

import random
from evennia import create_object
from evennia.utils.search import search_object
from evennia.utils import create


def normalize_housing_data(hd):
    """
    Normalize legacy housing_data to current schema.
    Handles: list vs set for connected_rooms/apartment_numbers, missing keys,
    mixed dbref formats (int vs object id). Works with dict and Evennia _SaverDict.
    Returns a fresh dict; does not mutate input.
    """
    if not hd:
        return {}
    try:
        out = dict(hd)
    except (TypeError, ValueError):
        return {}
    if not isinstance(out, dict):
        return {}

    def to_id_set(val):
        """Convert to set of integer ids (dbrefs). Handles set, list, tuple, Evennia _SaverSet."""
        if val is None:
            return set()
        if isinstance(val, set):
            pass
        elif isinstance(val, (list, tuple)):
            val = set(val)
        elif hasattr(val, '__iter__') and not isinstance(val, (dict, str)):
            val = set(val)
        else:
            return set()
        result = set()
        for x in val:
            n = None
            if isinstance(x, int):
                n = x
            elif hasattr(x, 'id'):
                n = int(x.id)
            elif hasattr(x, 'dbref'):
                dr = x.dbref
                if isinstance(dr, str) and dr.startswith('#'):
                    try:
                        n = int(dr[1:])
                    except ValueError:
                        pass
                elif isinstance(dr, int):
                    n = dr
            elif isinstance(x, str) and x.startswith('#'):
                try:
                    n = int(x[1:])
                except ValueError:
                    pass
            if n is not None:
                result.add(n)
        return result

    if 'connected_rooms' in out:
        out['connected_rooms'] = to_id_set(out['connected_rooms'])
    else:
        out['connected_rooms'] = set()

    if 'apartment_numbers' in out:
        apt = out['apartment_numbers']
        if isinstance(apt, (list, tuple, set)):
            out['apartment_numbers'] = {str(x) for x in apt if x is not None}
        else:
            out['apartment_numbers'] = set()
    else:
        out['apartment_numbers'] = set()

    # Normalize building_zone to int (dbref)
    bz = out.get('building_zone')
    if bz is not None:
        if isinstance(bz, int):
            pass
        elif hasattr(bz, 'id'):
            out['building_zone'] = bz.id
        elif hasattr(bz, 'dbref'):
            out['building_zone'] = bz.dbref
        elif isinstance(bz, str) and bz.startswith('#'):
            try:
                out['building_zone'] = int(bz[1:])
            except ValueError:
                out['building_zone'] = None
    else:
        out['building_zone'] = None

    # Ensure expected keys exist
    out.setdefault('is_lobby', False)
    out.setdefault('is_housing', False)
    out.setdefault('available_types', [])
    if not isinstance(out['available_types'], list):
        out['available_types'] = list(out['available_types']) if out['available_types'] else []

    return out
from world.rental_data import (
    RENTAL_TYPES,
    ROOM_EXIT_ALIASES,
    OUT_EXIT_ALIAS,
    DEFAULT_MAX_UNITS_PER_FLOOR,
)
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from typeclasses.scripts import RentCollectionScript


def get_apartment_hierarchy(lobby, floor_room=None):
    """
    Get location hierarchy for apartment display. Uses lobby's hierarchy.
    Avoids using lobby.key as district (e.g. 'Lobby') - prefers lobby's location hierarchy.
    When hierarchy[1] is lobby.key, tries: lobby.location, then floor_room, for correct district.
    """
    hierarchy = getattr(lobby.db, 'location_hierarchy', None)
    if hierarchy and len(hierarchy) >= 2:
        # If second element is lobby's key (e.g. 'Lobby'), get district from elsewhere
        if str(hierarchy[1]).lower() == str(lobby.key).lower():
            # Try lobby's parent room first
            if lobby.location:
                parent_h = getattr(lobby.location.db, 'location_hierarchy', None)
                if parent_h and len(parent_h) >= 2:
                    return [hierarchy[0], parent_h[1]]
            # Fallback: use floor's hierarchy (floor shares building, has correct district)
            if floor_room:
                floor_h = getattr(floor_room.db, 'location_hierarchy', None)
                if floor_h and len(floor_h) >= 2 and str(floor_h[1]).lower() != str(lobby.key).lower():
                    return [hierarchy[0], floor_h[1]]
        return list(hierarchy)
    return [lobby.key, "Unknown"]


def is_lobby(obj):
    """Check if object is a rental building lobby (is_lobby, is_housing, or roomtype + no direct apt exit)."""
    if not obj or not hasattr(obj, 'db'):
        return False
    hd = normalize_housing_data(getattr(obj.db, 'housing_data', None))
    if hd.get('is_lobby'):
        return True
    if hd.get('is_housing'):
        return True
    roomtype = getattr(obj.db, 'roomtype', None)
    if roomtype not in ("Apartment Building", "Hotel", "Motel", "Splat Housing"):
        return False
    # Floors have direct exit to RentableRoom; lobbies do not
    for ex in getattr(obj, 'exits', []) or []:
        dest = getattr(ex, 'destination', None)
        if dest and getattr(dest, 'is_typeclass', lambda _: False)("typeclasses.rental.RentableRoom"):
            return False  # Has direct apt exit = floor
    return True  # roomtype matches and no direct apt exit = lobby


# Tag constants for rental discovery (set by +manage/setlobby and +manage/addroom)
RENTAL_LOBBY_TAG = "rental_lobby"
RENTAL_FLOOR_TAG = "rental_floor"


def get_lobby_for_rent(location):
    """
    Get the lobby for rental operations.
    - In lobby (rental_lobby tag): return location.
    - On floor (rental_floor tag): use building_zone -> lobby.
    """
    if not location or not hasattr(location, 'db'):
        return None
    if location.tags.has(RENTAL_LOBBY_TAG):
        return location
    if location.tags.has(RENTAL_FLOOR_TAG):
        hd = normalize_housing_data(getattr(location.db, 'housing_data', None)) or {}
        bz = hd.get('building_zone')
        if bz is not None:
            objs = search_object(f"#{int(bz)}")
            if objs:
                return objs[0]
    return None


def _to_int(val):
    """Convert dbref-like value to int (handles '#74', 74, object with .id)."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if hasattr(val, 'id'):
        return int(val.id)
    if isinstance(val, str) and val.startswith('#'):
        try:
            return int(val[1:])
        except ValueError:
            return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def get_floor_rooms(lobby):
    """
    Get floors for a lobby.
    1. Use lobby's connected_rooms (set by +manage/addroom) - most reliable.
    2. Fallback: rental_floor tag + building_zone.
    3. Fallback: iterate all objects with building_zone=lobby.
    """
    from evennia.objects.models import ObjectDB

    lobby_id = int(lobby.id)
    floors = []
    seen_ids = {lobby_id}

    # 1. connected_rooms from lobby's housing_data (primary - set by addroom)
    hd = normalize_housing_data(getattr(lobby.db, 'housing_data', None)) or {}
    connected = hd.get('connected_rooms') or set()
    for rid in connected:
        rid_int = _to_int(rid)
        if rid_int is None or rid_int in seen_ids:
            continue
        obj_db = ObjectDB.objects.filter(id=rid_int).first()
        if obj_db:
            room = obj_db.get() if hasattr(obj_db, 'get') else obj_db
            if room and room.id != lobby_id:
                floors.append(room)
                seen_ids.add(room.id)

    # 2. rental_floor tag + building_zone
    if not floors:
        floor_qs = ObjectDB.objects.filter(
            db_tags__db_key__iexact=RENTAL_FLOOR_TAG
        ).distinct()
        for obj_db in floor_qs:
            try:
                obj = obj_db.get() if hasattr(obj_db, 'get') else obj_db
                if not obj or obj.id in seen_ids:
                    continue
                fhd = normalize_housing_data(getattr(obj.db, 'housing_data', None)) or {}
                bz = _to_int(fhd.get('building_zone'))
                if bz == lobby_id:
                    floors.append(obj)
                    seen_ids.add(obj.id)
            except Exception:
                continue

    # 3. Iterate objects with building_zone=lobby (legacy)
    if not floors:
        for obj_db in ObjectDB.objects.all():
            try:
                obj = obj_db.get() if hasattr(obj_db, 'get') else obj_db
                if not obj or obj.id in seen_ids:
                    continue
                fhd = normalize_housing_data(getattr(obj.db, 'housing_data', None)) or {}
                bz = _to_int(fhd.get('building_zone'))
                if bz == lobby_id:
                    if not obj.tags.has(RENTAL_FLOOR_TAG):
                        obj.tags.add(RENTAL_FLOOR_TAG)
                    floors.append(obj)
                    seen_ids.add(obj.id)
            except Exception:
                continue

    return floors


def find_rental_lobbies():
    """
    Find all rental lobbies. Uses the same discovery logic as +manage/info:
    - Start from floors (rental_floor tag or housing_data.building_zone)
    - Each floor has building_zone pointing to its lobby
    - Collect unique lobbies from floors, same way manage/info finds lobby when you're on a floor
    """
    from evennia.objects.models import ObjectDB

    lobbies = []
    seen = set()

    def _add_lobby_from_floor(floor):
        """Get lobby from floor's building_zone (same as manage/info when on a floor)."""
        fhd = normalize_housing_data(getattr(floor.db, 'housing_data', None)) or {}
        lobby_id = _to_int(fhd.get('building_zone'))
        if lobby_id is None or lobby_id in seen:
            return
        obj_db = ObjectDB.objects.filter(id=lobby_id).first()
        if not obj_db:
            return
        lobby = obj_db.get() if hasattr(obj_db, 'get') else obj_db
        if not lobby or not hasattr(lobby, 'db'):
            return
        floors = get_floor_rooms(lobby)
        if floors:
            lobbies.append(lobby)
            seen.add(lobby_id)

    # 1. Floor-first via rental_floor tag (set by +manage/addroom)
    for obj_db in ObjectDB.objects.filter(db_tags__db_key__iexact=RENTAL_FLOOR_TAG).distinct():
        try:
            floor = obj_db.get() if hasattr(obj_db, 'get') else obj_db
            if floor and hasattr(floor, 'db'):
                _add_lobby_from_floor(floor)
        except Exception:
            continue

    # 2. Floor-first via housing_data.building_zone (buildings set up before rental_floor tag)
    if not lobbies:
        for obj_db in ObjectDB.objects.all():
            try:
                obj = obj_db.get() if hasattr(obj_db, 'get') else obj_db
                if not obj or not hasattr(obj, 'db'):
                    continue
                hd = getattr(obj.db, 'housing_data', None)
                if not hd or not isinstance(hd, dict):
                    continue
                if hd.get('is_lobby'):
                    continue  # Skip lobbies, we want floors
                if _to_int(hd.get('building_zone')) is None:
                    continue
                # This is a floor (has building_zone, not lobby)
                if hasattr(obj, 'tags') and not obj.tags.has(RENTAL_FLOOR_TAG):
                    obj.tags.add(RENTAL_FLOOR_TAG)
                _add_lobby_from_floor(obj)
            except Exception:
                continue

    def _has_floors(lobby):
        """Check if lobby has floors - use connected_rooms (same as manage/info) or get_floor_rooms."""
        hd = normalize_housing_data(getattr(lobby.db, 'housing_data', None)) or {}
        connected = hd.get('connected_rooms') or set()
        lobby_id = lobby.id
        other_ids = [c for c in connected if _to_int(c) and _to_int(c) != lobby_id]
        if other_ids:
            return True
        return len(get_floor_rooms(lobby)) > 0

    # 3. Lobby-first (rental_lobby tag or is_lobby)
    if not lobbies:
        for obj_db in ObjectDB.objects.filter(db_tags__db_key__iexact=RENTAL_LOBBY_TAG).distinct():
            try:
                obj = obj_db.get() if hasattr(obj_db, 'get') else obj_db
                if obj and obj.id not in seen and _has_floors(obj):
                    lobbies.append(obj)
                    seen.add(obj.id)
            except Exception:
                continue

    if not lobbies:
        for obj_db in ObjectDB.objects.all():
            try:
                obj = obj_db.get() if hasattr(obj_db, 'get') else obj_db
                if not obj or obj.id in seen:
                    continue
                hd = getattr(obj.db, 'housing_data', None)
                if hd and isinstance(hd, dict) and hd.get('is_lobby'):
                    if hasattr(obj, 'tags') and not obj.tags.has(RENTAL_LOBBY_TAG):
                        obj.tags.add(RENTAL_LOBBY_TAG)
                    if _has_floors(obj):
                        lobbies.append(obj)
                        seen.add(obj.id)
            except Exception:
                continue

    return lobbies


def get_building_rental_info(lobby, floor_room=None):
    """
    Get rental info for a building: hierarchy, area code, available slots, non-default costs.
    Returns dict with keys: hierarchy, area_code, available_count, floor_count, floors_available,
    cost_notes, types, building_name.
    building_name uses hierarchy[0] (e.g. "Test Apartment Building"), not lobby.key.
    """
    from world.rental_data import RENTAL_TYPES, DEFAULT_MAX_UNITS_PER_FLOOR

    hd = normalize_housing_data(getattr(lobby.db, 'housing_data', None)) or {}
    hierarchy = get_apartment_hierarchy(lobby, floor_room)
    hierarchy_str = " - ".join(hierarchy) if hierarchy else "Unknown"
    building_name = hierarchy[0] if hierarchy else lobby.key
    area_code = getattr(lobby.db, 'area_code', None) or ""

    # Use get_floor_rooms so we benefit from fallbacks (exits, building_zone)
    floors = get_floor_rooms(lobby)
    available_count = 0
    floor_count = len(floors)
    floors_available = []  # [(floor_name, available), ...]
    cost_notes = []
    seen_costs = set()

    for floor in floors:
        if not floor or not hasattr(floor, 'db'):
            continue
        floor_hd = normalize_housing_data(getattr(floor.db, 'housing_data', None)) or {}
        max_units = floor_hd.get('max_units_per_floor', DEFAULT_MAX_UNITS_PER_FLOOR)
        # Count only OCCUPIED apartments as used; vacant apartments count as available
        occupied_count = 0
        for ex in getattr(floor, 'exits', []) or []:
            dest = getattr(ex, 'destination', None)
            if dest and getattr(dest, 'is_typeclass', lambda _: False)("typeclasses.rental.RentableRoom"):
                try:
                    main = dest.get_main_room()
                    if main and main.db.owner:
                        occupied_count += 1
                except Exception:
                    pass
        floor_available = max(0, max_units - occupied_count)
        available_count += floor_available
        floors_available.append((floor.key, floor_available))

        # Check apartments on this floor for non-default costs
        for ex in getattr(floor, 'exits', []) or []:
            dest = getattr(ex, 'destination', None)
            if not dest:
                continue
            try:
                if dest.is_typeclass("typeclasses.rental.RentableRoom"):
                    main = dest.get_main_room()
                    rent_mod = main.db.rent_cost_modifier or 0
                    purch_mod = main.db.purchase_cost_modifier or 0
                    if rent_mod != 0 or purch_mod != 0:
                        r = f"+{rent_mod}" if rent_mod >= 0 else str(rent_mod)
                        p = f"+{purch_mod}" if purch_mod >= 0 else str(purch_mod)
                        note = f"{r}eb rent, {p}eb purchase"
                        if note not in seen_costs:
                            seen_costs.add(note)
                            cost_notes.append(note)
            except Exception:
                continue

    available_types = hd.get('available_types', []) or []
    types_str = ", ".join(t for t in available_types if t != "Custom") or "None"

    # Total capacity = sum of max_units_per_floor across all floors
    total_units = 0
    for floor in floors:
        if floor and hasattr(floor, 'db'):
            fhd = normalize_housing_data(getattr(floor.db, 'housing_data', None)) or {}
            total_units += fhd.get('max_units_per_floor', DEFAULT_MAX_UNITS_PER_FLOOR)

    return {
        "hierarchy": hierarchy_str,
        "area_code": area_code,
        "available_count": available_count,
        "total_units": total_units,
        "floor_count": floor_count,
        "floors_available": floors_available,
        "cost_notes": cost_notes,
        "types": types_str,
        "building_name": building_name,
    }


def get_used_apartment_numbers(floor_room):
    """Get set of used apartment numbers (strings) from housing_data and actual exits."""
    hd = normalize_housing_data(getattr(floor_room.db, 'housing_data', None)) or {}
    used = {str(x) for x in (hd.get('apartment_numbers', set()) or set()) if x is not None}
    for ex in getattr(floor_room, 'exits', []) or []:
        dest = getattr(ex, 'destination', None)
        if dest and getattr(dest, 'is_typeclass', lambda _: False)("typeclasses.rental.RentableRoom"):
            if ex.key:
                used.add(str(ex.key))
            for a in (ex.aliases.all() if hasattr(ex, 'aliases') else []) or []:
                used.add(str(a))
    return used


def get_available_apartment_number(floor_room):
    """Get next unused apartment number for this floor."""
    from world.rental_data import parse_floor_from_room_name
    hd = normalize_housing_data(getattr(floor_room.db, 'housing_data', None)) or {}
    floor_num = parse_floor_from_room_name(floor_room.key)
    if floor_num is None:
        floor_num = hd.get('floor_number', 1)
    used = get_used_apartment_numbers(floor_room)
    max_units = hd.get('max_units_per_floor', DEFAULT_MAX_UNITS_PER_FLOOR)
    for i in range(1, max_units + 1):
        num = f"{floor_num}{i:02d}"
        if num not in used:
            return num
    return None


def get_character_eurodollars(character):
    """Get character's eurodollar balance from character sheet."""
    if not hasattr(character, 'character_sheet') or not character.character_sheet:
        return 0
    return CharacterSheetMoneyService.get_balance(character.character_sheet)


def get_effective_rent_cost(room):
    """Get the effective monthly rent cost (base + modification)."""
    base = room.db.rent_cost or 0
    mod = room.db.rent_cost_modifier or 0
    return max(0, base + mod)


def get_effective_purchase_cost(room):
    """Get the effective purchase cost (base + modification)."""
    base = room.db.purchase_cost or 0
    mod = room.db.purchase_cost_modifier or 0
    return max(0, base + mod)


def create_apartment_rooms(main_room, rental_type, apartment_number, building_name, district, custom_layout=None):
    """
    Create child rooms for a multi-room apartment.
    Main room already exists. Creates child rooms and bidirectional exits.
    custom_layout: optional list of (room_name, exit_alias) - overrides rental_type lookup.
    """
    from world.rental_data import RENTAL_TYPES, get_custom_room_layout

    if custom_layout is not None:
        layout = custom_layout
    elif rental_type in RENTAL_TYPES:
        layout = RENTAL_TYPES[rental_type]["room_layout"]
    else:
        return []
    if len(layout) <= 1:
        return []

    child_rooms = []
    main_room.db.child_rooms = []

    for i, (room_name, exit_alias) in enumerate(layout[1:], 1):  # Skip main room
        full_name = f"{apartment_number} {room_name}"
        # Child room must be sibling of main (same parent), not inside main.
        child = create_object(
            "typeclasses.rental.RentableRoom",
            key=full_name,
            location=main_room.location,
        )
        child.db.parent_room = main_room
        child.db.rental_type = rental_type
        child.db.room_role = room_name  # e.g. "Bedroom 1", "Side Room"
        child.db.apartment_number = apartment_number
        child.db.building_name = building_name
        child.db.district = district
        child.db.is_child_room = True
        child.db.rent_cost = getattr(main_room.db, 'rent_cost', 0)
        child.db.purchase_cost = getattr(main_room.db, 'purchase_cost', 0)
        child.db.rent_cost_modifier = getattr(main_room.db, 'rent_cost_modifier', 0)
        child.db.purchase_cost_modifier = getattr(main_room.db, 'purchase_cost_modifier', 0)
        # Share references so updates to main room propagate to child rooms
        child.db.owner = getattr(main_room.db, 'owner', None)
        child.db.purchased = getattr(main_room.db, 'purchased', False)
        child.db.residents = getattr(main_room.db, 'residents', None) or []
        child.db.co_residents = getattr(main_room.db, 'co_residents', None) or {}
        child.db.partners = getattr(main_room.db, 'partners', None) or []
        child.db.room_owners = getattr(main_room.db, 'room_owners', None) or {}

        # Set hierarchy for display
        if main_room.db.location_hierarchy:
            child.db.location_hierarchy = list(main_room.db.location_hierarchy)
        child.db.area_name = building_name
        child.db.area_code = apartment_number

        main_room.db.child_rooms.append(child)
        child_rooms.append(child)

        # Create exit from main room to child (name + alias)
        exit_name = room_name
        exit_aliases = [exit_alias] if exit_alias else []
        create.create_object(
            typeclass="typeclasses.exits.Exit",
            key=exit_name,
            location=main_room,
            destination=child,
            aliases=exit_aliases,
        )

        # Create "Out" exit from child to main room
        create.create_object(
            typeclass="typeclasses.exits.Exit",
            key="Out",
            location=child,
            destination=main_room,
            aliases=[OUT_EXIT_ALIAS],
        )

    return child_rooms


def ensure_rent_collection_script(room):
    """Ensure rent collection script exists for a rented (non-purchased) room."""
    if room.db.purchased:
        return
    script_key = f"rent_collection_{room.id}"
    if not room.scripts.get(script_key):
        create.create_script(
            RentCollectionScript,
            key=script_key,
            obj=room,
            interval=2592000,  # 30 days
            persistent=True,
        )


def stop_rent_collection_script(room):
    """Stop rent collection script (e.g. when purchased or vacated)."""
    for script in room.scripts.all():
        if script.key and script.key.startswith("rent_collection_"):
            script.stop()
