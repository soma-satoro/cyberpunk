"""
Server startstop hooks

This module contains functions called by Evennia at various
points during startup, reload and shutdown. It allows for
customization of these hooks.

"""

from evennia import AccountDB, create_script
from evennia.utils import logger
from evennia.utils.evmore import EvMore, CmdSetMore
from evennia.scripts.models import ScriptDB
from evennia.server.sessionhandler import SESSIONS
from world.world_scripts import WorldScript
from typeclasses.scripts import RentCollectionScript
from typeclasses.rental import RentableRoom
from world.equipment_data import (
    initialize_weapons,
    initialize_armor,
    initialize_gear,
    initialize_ammunition,
    initialize_vehicles,
    initialize_weapon_attachments,
)
from world.cyberware.cyberware_data import initialize_cyberware
from world.ip_config import IPConfigScript, get_ip_config
from world.ip_weekly_script import IPWeeklyScript
from world.mystery.focus_recovery_script import FocusRecoveryScript
from typeclasses.factions import Faction
from evennia.objects.models import ObjectDB


import traceback

def _patch_evmore_for_duplicate_pager_fix():
    """
    Patch EvMore.start() to remove any existing CmdSetMore before adding a new one.
    Fixes 'More than one match for next' when multiple sessions trigger help pagination
    (e.g. webclient + telnet both viewing help, or rapid double-invocation).
    """
    _original_start = EvMore.start

    def _patched_start(self):
        # Remove any orphaned CmdSetMore (from multiple sessions or rapid re-invocation)
        for obj in (self._caller, getattr(self._caller, "account", None)):
            if obj and hasattr(obj, "cmdset"):
                try:
                    obj.cmdset.remove(CmdSetMore)
                except Exception:
                    pass
        return _original_start(self)

    EvMore.start = _patched_start


def at_server_start():
    """
    This is called every time the server starts up, regardless of
    how it was shut down.
    """
    # Patch EvMore to prevent duplicate pagination commands (next/previous conflict)
    _patch_evmore_for_duplicate_pager_fix()

    # Initialize the faction system
    logger.log_info("Initializing the faction system...")
    
    storage = Faction.get_faction_storage()
    if not storage:
        logger.log_err("Failed to initialize faction system: Could not create faction storage room")
        return
        
    # Check if we have a master faction object
    master = ObjectDB.objects.filter(
        db_key="FactionMaster", db_typeclass_path="typeclasses.factions.Faction"
    ).first()
    if not master:
        from evennia import create_object
        master = create_object(
            "typeclasses.factions.Faction",
            key="FactionMaster",
            location=storage
        )
        logger.log_info("Created FactionMaster object")
    
    # Ensure default factions exist
    from typeclasses.factions import DEFAULT_FACTIONS, FactionModel
    created_count = 0
    
    for name, data in DEFAULT_FACTIONS.items():
        if not FactionModel.objects.filter(name=name).exists():
            try:
                faction_model = FactionModel.objects.create(
                    name=name,
                    description=data["description"],
                    ic_description=data["ic_description"],
                    influence=data["influence"]
                )
                
                faction_obj = create_object(
                    "typeclasses.factions.Faction",
                    key=name,
                    location=storage
                )
                
                faction_obj.db.faction_type = data["type"]
                faction_obj.link_to_model(faction_model.id)
                created_count += 1
                logger.log_info(f"Created default faction: {name}")
            except Exception as e:
                logger.log_err(f"Error creating default faction {name}: {e}")
    
    if created_count > 0:
        logger.log_info(f"Created {created_count} default factions")

    # Ensure all factions have channels (create missing, add aliases to existing)
    from world.factions.faction_utils import create_faction_channel
    for faction_model in FactionModel.objects.all():
        if not getattr(faction_model, "channel_id", None):
            channel = create_faction_channel(faction_model.name)
            if channel:
                faction_model.channel_id = channel.id
                faction_model.save()
                logger.log_info(f"Created channel for faction {faction_model.name}")
        else:
            create_faction_channel(faction_model.name)  # Ensure aliases on existing

    logger.log_info("Faction system initialization complete")

    # Start the WorldScript
    if not WorldScript.objects.filter(db_key="WorldScript").exists():
        create_script(WorldScript)
    
    # Start RentCollectionScripts for rented (non-purchased) apartments only
    processed = set()
    for room in RentableRoom.objects.all():
        main = room.get_main_room() if hasattr(room, 'get_main_room') else room
        if main.id in processed:
            continue
        processed.add(main.id)
        if main.db.owner and not getattr(main.db, 'purchased', False):
            if not main.scripts.get("rent_collection_" + str(main.id)):
                create_script(RentCollectionScript, obj=main)

    initialize_weapons()
    initialize_weapon_attachments()
    initialize_armor()
    initialize_gear()
    initialize_ammunition()
    initialize_vehicles()
    initialize_cyberware()

    # IP system: ensure config and weekly script exist
    try:
        if not ScriptDB.objects.filter(db_key="IPConfig").exists():
            create_script(IPConfigScript, key="IPConfig")
            logger.log_info("Created IPConfig script.")
        if not ScriptDB.objects.filter(db_key="IPWeeklyAllotment").exists():
            create_script(IPWeeklyScript, key="IPWeeklyAllotment")
            logger.log_info("Created IPWeeklyAllotment script.")
        if not ScriptDB.objects.filter(db_key="FocusRecovery").exists():
            create_script(FocusRecoveryScript, key="FocusRecovery")
            logger.log_info("Created FocusRecovery script.")
        # Ensure weekly script is running (it no-ops when allotment disabled)
        try:
            ws = ScriptDB.objects.filter(db_key="IPWeeklyAllotment").first()
            if ws and hasattr(ws, "start") and callable(ws.start):
                if not ws.is_active():
                    ws.start()
            fr = ScriptDB.objects.filter(db_key="FocusRecovery").first()
            if fr and hasattr(fr, "start") and callable(fr.start):
                if not fr.is_active():
                    fr.start()
        except Exception:
            pass
    except Exception as e:
        logger.log_err(f"IP system init: {e}")

    logger.log_info("Server startup scripts have been initialized.")


def at_server_stop():
    """
    This is called just before the server is shut down, regardless
    of it being for a reload, reset or shutdown.
    """
    logger.log_info("Custom server shutdown initiated")
    # Only process connected accounts - iterating all AccountDB can hang with large DBs
    seen = set()
    for session in SESSIONS.get_sessions():
        acc = getattr(session, "account", None)
        if acc and acc.id not in seen:
            seen.add(acc.id)
            try:
                if hasattr(acc, "at_server_shutdown"):
                    acc.at_server_shutdown()
            except Exception as e:
                logger.log_err(f"at_server_shutdown for Account {acc.id}: {e}")
    logger.log_info("Custom server shutdown complete")

def at_server_reload_start(account_sessions=None):
    """
    This is called only when server starts back up after a reload.

    account_sessions is a list of account sessions connected to the
    server before the reload. These will be reconnected unless they
    have been disconnected. It is not guaranteed that the Players in
    this list will be the same as the connected ones.

    """
    pass

def at_server_reload_stop():
    """
    This is called only when the server stops during a reload.
    """
    logger.log_info("Custom server reload initiated")
    seen = set()
    for session in SESSIONS.get_sessions():
        acc = getattr(session, "account", None)
        if acc and acc.id not in seen:
            seen.add(acc.id)
            try:
                if hasattr(acc, "at_server_reload"):
                    acc.at_server_reload()
            except Exception as e:
                logger.log_err(f"at_server_reload for Account {acc.id}: {e}")
    logger.log_info("Custom server reload complete")

def at_server_cold_start():
    """
    This is called only when the server starts "cold", i.e. after a
    shutdown or a reset.
    """
    at_server_start()  # Call the same initialization as for a regular start

def at_server_cold_stop():
    """
    This is called only when the server goes down due to a shutdown or
    reset.
    """
    pass
