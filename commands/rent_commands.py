"""
Comprehensive +rent command for apartment rental system.

Usage:
  +rent <type>        - Rent at current location (type required, e.g. +rent here "Studio Apartment")
  +rent/search            - List all buildings with available apartments (location, area, costs)
  +rent/desc [=text]      - Set/change room description
  +rent/exit <exit>=<name> - Change exit display name (not alias)
  +rent/home              - Set this apartment as your IC home
  +rent/name [=name]      - Change room name
  +rent/add <character>   - Add co-resident (assigns to next available room)
  +rent/remove <character> - Remove co-resident
  +rent/partner <character> - Invite romantic partner to move in
  +rent/partner confirm   - Confirm partner move-in (when invited)
  +rent/purchase         - Purchase apartment (no more monthly rent)
  +rent/lock [<exit>]    - Lock door (default: main exit)
  +rent/unlock [<exit>]  - Unlock door
  +rent/info             - Show rental information (in apartment)
  +rent/status           - Show rental/building status (apartment or lobby/floor)
  +rent/leave            - Leave your rental
"""

import random
from evennia import Command, CmdSet
from evennia.utils import create
from evennia.utils.search import search_object
from evennia.commands.default.muxcommand import MuxCommand
from typeclasses.rental import RentableRoom
from world.utils.formatting import header, footer, section_header, divider, format_key_value
from world.rental_data import RENTAL_TYPES, DEFAULT_MAX_UNITS_PER_FLOOR
from world.rental_service import (
    get_character_eurodollars,
    get_effective_rent_cost,
    get_effective_purchase_cost,
    create_apartment_rooms,
    ensure_rent_collection_script,
    get_apartment_hierarchy,
    find_rental_lobbies,
    get_building_rental_info,
    get_floor_rooms,
    get_available_apartment_number,
    get_used_apartment_numbers,
    is_lobby as rental_is_lobby,
    normalize_housing_data,
    get_lobby_for_rent,
    RENTAL_LOBBY_TAG,
    RENTAL_FLOOR_TAG,
)
from world.cyberpunk_sheets.services import CharacterSheetMoneyService


# Apartment types for building commands (backward compatibility)
APARTMENT_TYPES = {k: {"rooms": v["rooms"], "resource_modifier": 0, "desc": f"Rent: {v['rent']}eb/mo" if v.get('rent') else "Corp housing"} for k, v in RENTAL_TYPES.items() if v.get("rent") is not None or v.get("purchase") is not None}
RESIDENTIAL_TYPES = {"Encampment": {"rooms": 1, "resource_modifier": 0, "desc": "Free encampment"}}


class CmdHome(Command):
    """
    Return to your IC home (apartment).

    Usage:
      home

    Teleports you to your set home location. Use +rent/home in your apartment first.
    """

    key = "home"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        home = getattr(self.caller.db, 'home_location', None)
        if not home:
            self.caller.msg("You don't have a home set. Use +rent/home in your apartment to set it.")
            return
        self.caller.move_to(home)
        self.caller.msg(f"You head home to {home.key}.")


def find_lobby(location):
    """Find building lobby from current location."""
    if not location or not hasattr(location, 'db'):
        return None
    if rental_is_lobby(location):
        return location
    for ex in getattr(location, 'exits', []) or []:
        dest = getattr(ex, 'destination', None)
        if dest and rental_is_lobby(dest):
            return dest
    return None


class CmdRent(MuxCommand):
    """
    Apartment rental and management.

    Usage:
      +rent <type>       - Rent at current location (type required; use +rent/status to see available types)
      +rent/search            - List buildings with available apartments
      +rent/desc [=text]      - Set room description
      +rent/exit <exit>=<name> - Change exit name
      +rent/home              - Set as IC home
      +rent/name [=name]       - Change room name
      +rent/add <character>   - Add co-resident
      +rent/remove <character> - Remove co-resident
      +rent/partner <character> - Invite partner
      +rent/partner confirm   - Confirm partner move-in
      +rent/purchase          - Purchase apartment
      +rent/lock [<exit>]     - Lock door
      +rent/unlock [<exit>]   - Unlock door
      +rent/info              - Show rental info (in apartment)
      +rent/status            - Show rental/building status (apartment or lobby/floor)
      +rent/leave             - Leave rental
    """

    key = "+rent"
    aliases = ["rent"]
    locks = "cmd:all()"
    help_category = "Economy"

    def get_apartment_main(self, location):
        """Get main room if location is part of apartment."""
        if not location:
            return None
        if isinstance(location, RentableRoom):
            return location.get_main_room()
        return None

    def func(self):
        caller = self.caller
        location = caller.location
        switches = self.switches or []
        switch = switches[0].lower() if switches else None

        # +rent/leave
        if switch == "leave":
            rented = caller.attributes.get('rented_room')
            if not rented:
                caller.msg("You are not renting anywhere.")
                return
            success, msg = rented.leave_rental(caller)
            caller.msg(msg)
            if success and rented.location:
                caller.move_to(rented.location, quiet=True)
            return

        # +rent here - rent at current location
        if not switch or switch == "here":
            self.do_rent_here(location)
            return

        # +rent/search - global search for buildings with available apartments
        if switch == "search":
            self.do_rent_search()
            return

        # +rent/debug - diagnose rental search (Builder only)
        if switch == "debug":
            self.do_rent_debug()
            return

        # +rent/status works in apartment OR lobby/floor
        if switch == "status":
            self.do_rent_status(location)
            return

        # All other switches require being in a rentable room
        main = self.get_apartment_main(location)
        if not main:
            caller.msg("You must be in an apartment to use that command.")
            return

        if switch == "desc":
            self.do_desc(main, location)
        elif switch == "exit":
            self.do_exit(location)
        elif switch == "home":
            self.do_home(main)
        elif switch == "name":
            self.do_name(location)
        elif switch == "add":
            self.do_add(main)
        elif switch == "remove":
            self.do_remove(main)
        elif switch == "partner":
            self.do_partner(main)
        elif switch == "purchase":
            self.do_purchase(main)
        elif switch == "lock":
            self.do_lock(location)
        elif switch == "unlock":
            self.do_unlock(location)
        elif switch == "info":
            self.do_info(main)
        else:
            caller.msg("Unknown switch. Try +rent here, +rent/search, +rent/desc, +rent/home, etc.")

    def do_rent_here(self, location):
        """Handle +rent here - in lobby, on floor, or vacant apartment."""
        # Case 1: In a vacant RentableRoom
        if isinstance(location, RentableRoom):
            main = location.get_main_room()
            if not main.db.owner:
                # Vacant - rent it (use existing rental_type or get from building)
                rental_type = main.db.rental_type
                if not rental_type and main.location:
                    floor_hd = getattr(main.location.db, 'housing_data', None) or {}
                    available = floor_hd.get('available_types', [])
                    rental_type = available[0] if available else None
                if not rental_type:
                    self.caller.msg("No rental type set for this apartment.")
                    return
                success, msg = main.rent_to(self.caller, rental_type)
                self.caller.msg(msg)
                return

        # Case 2: In lobby or on floor - create new apartment
        lobby = get_lobby_for_rent(location)
        if not lobby:
            self.caller.msg("You must be in a building lobby, on a rental floor, or in a vacant apartment to rent.")
            return

        hd = lobby.db.housing_data or {}
        available = [t for t in (hd.get('available_types', []) or []) if t != "Custom"]
        if not available:
            self.caller.msg("No apartment types are available in this building. (Custom types must be created by staff with +manage/createapt)")
            return

        # Parse requested type: +rent here Studio Apartment or +rent here "One-Bedroom Apartment"
        rental_type = None
        if self.args and self.args.strip():
            requested = self.args.strip()
            if requested and requested[0] == requested[-1] and requested[0] in '"\'':
                requested = requested[1:-1].strip()
            requested_lower = requested.lower()
            for t in available:
                if t.lower() == requested_lower:
                    rental_type = t
                    break
            if not rental_type:
                self.caller.msg(
                    f"'{requested}' is not available here. Use |w+rent/status|n to see available types: {', '.join(available)}."
                )
                return
        if not rental_type:
            self.caller.msg(
                "You must specify an apartment type. Use |w+rent/status|n in the lobby or on a floor to see available types, "
                "then |w+rent here <type>|n (e.g. |w+rent here \"Studio Apartment\"|n)."
            )
            return

        # Determine floor
        floor_room = None
        if location.id == lobby.id:
            # In lobby - pick random floor
            floors = get_floor_rooms(lobby)
            if not floors:
                self.caller.msg("No floors are set up for rentals. Contact staff.")
                return
            floor_room = random.choice(floors)
        else:
            # On a floor - building_zone identifies which lobby this floor belongs to
            floor_hd = normalize_housing_data(getattr(location.db, 'housing_data', None)) or {}
            bz = floor_hd.get('building_zone')
            lobby_ids = {int(lobby.id), getattr(lobby, 'dbref', lobby.id)}
            if bz is not None and int(bz) in lobby_ids:
                floor_room = location
            if not floor_room:
                floors = get_floor_rooms(lobby)
                for f in floors:
                    if f.id == location.id:
                        floor_room = f
                        break
            if not floor_room:
                self.caller.msg("You must be in the lobby, on a rental floor, or in a vacant apartment.")
                return

        # Prefer vacant apartments over creating new ones
        main = None
        apt_num = None
        for ex in getattr(floor_room, 'exits', []) or []:
            dest = getattr(ex, 'destination', None)
            if not dest or not getattr(dest, 'is_typeclass', lambda _: False)("typeclasses.rental.RentableRoom"):
                continue
            try:
                room_main = dest.get_main_room()
                if room_main and not room_main.db.owner and room_main.db.rental_type == rental_type:
                    main = room_main
                    apt_num = room_main.db.apartment_number
                    break
            except Exception:
                continue

        if not main:
            apt_num = get_available_apartment_number(floor_room)
            if not apt_num:
                self.caller.msg("No apartments available on this floor.")
                return

        main_hierarchy = get_apartment_hierarchy(lobby, floor_room=floor_room)
        building_name = main_hierarchy[0] if (main_hierarchy and main_hierarchy[0]) else lobby.key
        district = main_hierarchy[1] if len(main_hierarchy) >= 2 else "Unknown"

        if not main:
            # Create new apartment
            data = RENTAL_TYPES[rental_type]
            main = create.create_object(
                RentableRoom,
                key=f"{apt_num} Main Room",
                location=floor_room.location,
            )
            main.db.rental_type = rental_type
            main.db.apartment_number = apt_num
            main.db.building_name = building_name
            main.db.location_hierarchy = main_hierarchy
            main.db.area_name = main_hierarchy[0] if main_hierarchy else building_name
            main.db.area_code = apt_num
            main.db.rent_cost = data.get("rent") or 0
            main.db.purchase_cost = data.get("purchase") or 0

            # Create exit from floor to apartment
            create.create_object(
                typeclass="typeclasses.exits.Exit",
                key=apt_num,
                location=floor_room,
                destination=main,
                aliases=[apt_num],
            )
            # Create exit from main to floor
            create.create_object(
                typeclass="typeclasses.exits.Exit",
                key="Out",
                location=main,
                destination=floor_room,
                aliases=["O"],
            )

            # Register apartment number on floor
            floor_hd = normalize_housing_data(getattr(floor_room.db, 'housing_data', None)) or {}
            used = get_used_apartment_numbers(floor_room)
            used.add(str(apt_num))
            floor_hd['apartment_numbers'] = used
            floor_room.db.housing_data = floor_hd

            # Create child rooms if multi-room
            if data.get("rooms", 1) > 1:
                create_apartment_rooms(main, rental_type, apt_num, building_name, district)

        # Rent to caller
        success, msg = main.rent_to(self.caller, rental_type)
        self.caller.msg(msg)
        if not success:
            return

        self.caller.msg(f"Your apartment is ready. Use the exit '{apt_num}' to enter.")
        self.caller.move_to(main, quiet=True)

    def do_rent_debug(self):
        """+rent/debug - Diagnose rental search (Builder only)."""
        acct = getattr(self.caller, 'account', self.caller)
        if not (acct and hasattr(acct, 'check_permstring') and acct.check_permstring("Builder")):
            self.caller.msg("You need Builder permission.")
            return
        from evennia.objects.models import ObjectDB
        from world.rental_service import find_rental_lobbies, get_floor_rooms, get_building_rental_info
        lines = []
        lines.append("=== +rent/debug ===")
        # Count ObjectDB
        total = ObjectDB.objects.count()
        lines.append(f"ObjectDB total: {total}")
        # Check current lobby
        loc = self.caller.location
        if loc:
            hd = getattr(loc.db, 'housing_data', None)
            lines.append(f"Your location: {loc.key} (#{loc.id})")
            lines.append(f"  housing_data.is_lobby: {hd.get('is_lobby') if hd else 'N/A'}")
            lines.append(f"  tags.has(rental_lobby): {loc.tags.has('rental_lobby') if hasattr(loc, 'tags') else 'N/A'}")
            if hd:
                lines.append(f"  connected_rooms: {hd.get('connected_rooms')}")
        # Floor discovery
        from evennia.objects.models import ObjectDB
        floor_by_tag = list(ObjectDB.objects.filter(db_tags__db_key__iexact=RENTAL_FLOOR_TAG).distinct())
        lines.append(f"Floors (tag '{RENTAL_FLOOR_TAG}'): {len(floor_by_tag)}")
        if loc:
            hd = getattr(loc.db, 'housing_data', None) or {}
            bz = hd.get('building_zone')
            lines.append(f"  Your room building_zone: {bz}")
        # Lobbies found
        lobbies = find_rental_lobbies()
        lines.append(f"find_rental_lobbies() returned: {len(lobbies)} lobbies")
        for i, lobby in enumerate(lobbies):
            floors = get_floor_rooms(lobby)
            info = get_building_rental_info(lobby)
            lines.append(f"  Lobby {i+1}: {lobby.key} (#{lobby.id})")
            lines.append(f"    floors: {len(floors)} - {[f.key for f in floors]}")
            lines.append(f"    floor_count: {info['floor_count']}, available: {info['available_count']}")
        self.caller.msg("\n".join(lines))

    def do_rent_search(self):
        """+rent/search - List all buildings with available apartments."""
        lobbies = find_rental_lobbies()
        if not lobbies:
            self.caller.msg("No rental buildings found with available apartments.")
            return

        # Filter to buildings that have floors and (available types or available units)
        buildings = []
        for lobby in lobbies:
            info = get_building_rental_info(lobby)
            if info["floor_count"] > 0 and (info["types"] != "None" or info["available_count"] > 0):
                buildings.append((lobby, info))

        if not buildings:
            self.caller.msg("No rental buildings currently have available apartments.")
            return

        out = [header("Buildings with Available Apartments", width=78)]
        out.append(section_header("Rental Buildings", width=78))
        for lobby, info in buildings:
            cost_str = "; ".join(info["cost_notes"]) if info["cost_notes"] else "-"
            bname = info["building_name"]
            out.append(f"|c{bname}|n")
            out.append(f"  |gLocation:|n {info['hierarchy']}")
            out.append(f"  |gFloors:|n {info['floor_count']} |gTypes:|n {info['types']}")
            out.append(f"  |gUnits Available:|n {info['available_count']}")
            if info.get("floors_available"):
                parts = [f"{name}: {n}" for name, n in info["floors_available"] if n > 0]
                if parts:
                    out.append(f"  |gPer floor:|n {', '.join(parts)}")
            if cost_str and cost_str != "-":
                out.append(f"  |gCost Notes:|n {cost_str}")
            out.append("")
        out.append(divider("", width=78))
        out.append(footer(width=78))
        out.append("Go to a building's lobby or floor and use |w+rent here|n to rent.")
        self.caller.msg("\n".join(out))

    def do_desc(self, main, room):
        """+rent/desc [=text]"""
        if not main.can_modify_room(self.caller):
            self.caller.msg("You can't modify this room.")
            return
        if self.rhs is not None:
            room.db.desc = self.rhs
            self.caller.msg("Description updated.")
        else:
            self.caller.msg("Usage: +rent/desc =<description>")

    def do_exit(self, room):
        """+rent/exit <exit>=<name>"""
        if not room.can_modify_room(self.caller):
            self.caller.msg("You can't modify this room.")
            return
        if not self.lhs or not self.rhs:
            self.caller.msg("Usage: +rent/exit <exit>=<new name>")
            return
        exit_name = self.lhs.strip()
        new_name = self.rhs.strip()
        for ex in room.exits:
            if ex.key.lower() == exit_name.lower() or (ex.aliases and exit_name.lower() in [a.lower() for a in ex.aliases.all()]):
                ex.key = new_name
                self.caller.msg(f"Exit renamed to '{new_name}'.")
                return
        self.caller.msg(f"No exit named '{exit_name}' found.")

    def do_home(self, main):
        """+rent/home"""
        if not main.is_resident(self.caller):
            self.caller.msg("You must be a resident to set this as home.")
            return
        self.caller.db.home_location = main
        self.caller.msg("This apartment is now your IC home. Use your home command to return.")

    def do_name(self, room):
        """+rent/name [=name]"""
        if not room.can_modify_room(self.caller):
            self.caller.msg("You can't modify this room.")
            return
        if self.rhs is not None:
            room.key = self.rhs.strip()
            self.caller.msg(f"Room renamed to '{room.key}'.")
        else:
            self.caller.msg("Usage: +rent/name =<new name>")

    def do_add(self, main):
        """+rent/add <character>"""
        if not main.is_primary_owner(self.caller):
            self.caller.msg("Only the primary renter can add co-residents.")
            return
        target = self.caller.search(self.args)
        if not target:
            return
        if not target.has_account:
            self.caller.msg("You can only add player characters.")
            return
        data = RENTAL_TYPES.get(main.db.rental_type, {})
        max_co = data.get("max_co_residents", 0)
        current = len(main.db.co_residents or {})
        if current >= max_co:
            self.caller.msg(f"This apartment type allows at most {max_co} co-residents.")
            return
        if main.is_resident(target):
            self.caller.msg(f"{target.name} is already a resident.")
            return
        # Assign to next available room (child rooms only for multi-room)
        children = main.db.child_rooms or []
        assigned = False
        for child in children:
            if child and child.id not in (main.db.room_owners or {}):
                main.db.co_residents = main.db.co_residents or {}
                main.db.co_residents[child.id] = target
                main.db.room_owners = main.db.room_owners or {}
                main.db.room_owners[child.id] = target.id
                main.db.residents = main.db.residents or []
                if target not in main.db.residents:
                    main.db.residents.append(target)
                target.attributes.add('rented_room', main)
                target.db.home_location = main
                self.caller.msg(f"{target.name} has been added as a co-resident (assigned to {child.key}).")
                target.msg(f"You have been added as a co-resident of {main.db.owner.name}'s apartment.")
                assigned = True
                break
        if not assigned:
            self.caller.msg("No available rooms for co-residents.")

    def do_remove(self, main):
        """+rent/remove <character>"""
        if not main.is_primary_owner(self.caller):
            self.caller.msg("Only the primary renter can remove co-residents.")
            return
        target = self.caller.search(self.args)
        if not target:
            return
        if main.db.owner == target:
            self.caller.msg("The primary renter must use +rent/leave to leave.")
            return
        co = dict(main.db.co_residents or {})
        for rid, c in list(co.items()):
            if c and c.id == target.id:
                del co[rid]
                main.db.co_residents = co
                ro = dict(main.db.room_owners or {})
                if rid in ro:
                    del ro[rid]
                    main.db.room_owners = ro
                if main.db.residents:
                    main.db.residents = [r for r in main.db.residents if r and r.id != target.id]
                target.attributes.remove('rented_room')
                if target.db.home_location == main:
                    target.db.home_location = None
                self.caller.msg(f"{target.name} has been removed.")
                target.msg(f"You have been removed from the apartment.")
                return
        self.caller.msg(f"{target.name} is not a co-resident.")

    def do_partner(self, main):
        """+rent/partner <character> or +rent/partner confirm"""
        if "confirm" in self.switches or self.args.lower() == "confirm":
            if main.db.partner_pending and main.db.partner_pending.id == self.caller.id:
                main.db.partners = main.db.partners or []
                main.db.partners.append(self.caller)
                main.db.residents = main.db.residents or []
                if self.caller not in main.db.residents:
                    main.db.residents.append(self.caller)
                self.caller.attributes.add('rented_room', main)
                self.caller.db.home_location = main
                inviter = main.db.owner
                main.db.partner_pending = None
                self.caller.msg("You have moved in as a partner.")
                if inviter:
                    inviter.msg(f"{self.caller.name} has confirmed and moved in.")
            else:
                self.caller.msg("You have no pending partner invitation.")
            return
        if not main.is_resident(self.caller):
            self.caller.msg("You must be a resident to invite a partner.")
            return
        target = self.caller.search(self.args)
        if not target:
            return
        if not target.has_account:
            self.caller.msg("You can only invite player characters.")
            return
        if main.is_resident(target):
            self.caller.msg(f"{target.name} is already a resident.")
            return
        main.db.partner_pending = target
        self.caller.msg(f"{target.name} has been invited. They must type +rent/partner confirm in the apartment to accept.")
        target.msg(f"{self.caller.name} has invited you to move in as their partner. Go to their apartment and type +rent/partner confirm to accept.")

    def do_purchase(self, main):
        """+rent/purchase"""
        if not main.is_primary_owner(self.caller):
            self.caller.msg("Only the primary renter can purchase the apartment.")
            return
        success, msg = main.purchase_by(self.caller)
        self.caller.msg(msg)

    def do_lock(self, room):
        """+rent/lock [<exit>]"""
        if not room.can_lock_door(self.caller):
            self.caller.msg("You can't lock doors here.")
            return
        main = room.get_main_room()
        keyholders = list(main.db.residents or []) + (main.db.partners or [])
        keyholder_ids = [c.id for c in keyholders if c]
        lock_def = f"id({','.join(map(str, keyholder_ids))}) or perm(Admin)"
        exit_name = self.args.strip() if self.args else None
        for ex in room.exits:
            if exit_name and ex.key.lower() != exit_name.lower():
                continue
            ex.locks.add(f"traverse:{lock_def}")
            self.caller.msg(f"Locked {ex.key}.")
            return
        self.caller.msg("No matching exit found.")

    def do_unlock(self, room):
        """+rent/unlock [<exit>]"""
        if not room.can_lock_door(self.caller):
            self.caller.msg("You can't unlock doors here.")
            return
        exit_name = self.args.strip() if self.args else None
        for ex in room.exits:
            if exit_name and ex.key.lower() != exit_name.lower():
                continue
            ex.locks.add("traverse:all()")
            self.caller.msg(f"Unlocked {ex.key}.")
            return
        self.caller.msg("No matching exit found.")

    def do_rent_status(self, location):
        """+rent/status - Show rental info in apartment, or building status in lobby/floor."""
        main = self.get_apartment_main(location)
        if main:
            self.do_info(main)
            return
        # In lobby or floor - show building status
        lobby = get_lobby_for_rent(location)
        if not lobby:
            self.caller.msg("You must be in an apartment, building lobby, or rental floor to use +rent/status.")
            return
        floor_room = location if location and location.id != lobby.id else None
        info = get_building_rental_info(lobby, floor_room)
        out = [section_header(f"Rental Status - {info['building_name']}", width=78)]
        out.append(f"|gLocation:|n {info['hierarchy']}")
        out.append(f"|gFloors:|n {info['floor_count']}")
        out.append(f"|gTypes:|n {info['types']}")
        out.append(f"|gUnits Available:|n {info['available_count']}")
        if info.get("floors_available"):
            parts = [f"{name}: {n}" for name, n in info["floors_available"]]
            out.append(f"|gPer floor:|n {', '.join(parts)}")
        out.append(f" - Use |w+rent <type>|n to rent an apartment")
        out.append(divider("", width=78))
        self.caller.msg("\n".join(out))

    def do_info(self, main):
        """+rent/info"""
        out = [section_header("Rental Info", width=78)]
        out.append(format_key_value("Type", main.db.rental_type or "None", width=40))
        out.append(format_key_value("Rent", f"{get_effective_rent_cost(main)}eb/month", width=40))
        purch = f"{get_effective_purchase_cost(main)}eb" if get_effective_purchase_cost(main) else "N/A"
        out.append(format_key_value("Purchase", purch, width=40))
        status = "Owned" if main.db.purchased else ("Vacant" if not main.db.owner else "Rented")
        out.append(format_key_value("Status", status, width=40))
        out.append(format_key_value("Primary", main.db.owner.name if main.db.owner else "None", width=40))
        residents = ", ".join(r.name for r in (main.db.residents or []) if r)
        out.append(format_key_value("Residents", residents or "None", width=40))
        out.append(divider("", width=78))
        out.append(footer(width=78))
        self.caller.msg("\n".join(out))
