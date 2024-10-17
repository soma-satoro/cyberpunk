"""
Server startstop hooks

This module contains functions called by Evennia at various
points during startup, reload and shutdown. It allows for
customization of these hooks.

"""

from evennia import AccountDB, create_script
from evennia.utils import logger
from evennia.server.sessionhandler import SESSIONS
from world.world_scripts import WorldScript
from typeclasses.scripts import RentCollectionScript
from typeclasses.rental import RentableRoom
from world.equipment_data import initialize_weapons, initialize_armor, initialize_gear, initialize_ammunition
from world.cyberware.cyberware_data import initialize_cyberware


import traceback

def at_server_start():
    """
    This is called every time the server starts up, regardless of
    how it was shut down.
    """
    # Start the WorldScript
    if not WorldScript.objects.filter(db_key="WorldScript").exists():
        create_script(WorldScript)
    
    # Start RentCollectionScripts for all rentable rooms
    for room in RentableRoom.objects.all():
        if not room.scripts.get("rent_collection_" + str(room.id)):
            create_script(RentCollectionScript, obj=room)

    initialize_weapons()
    initialize_armor()
    initialize_gear()
    initialize_ammunition()
    initialize_cyberware()

    logger.log_info("Server startup scripts have been initialized.")


def at_server_stop():
    """
    This is called just before the server is shut down, regardless
    of it being for a reload, reset or shutdown.
    """
    logger.log_info("Custom server shutdown initiated")
    
    for p in AccountDB.objects.all():
        logger.log_info(f"Processing account: {p.id}, class: {p.__class__}, is custom: {isinstance(p, AccountDB)}")
        
        if hasattr(p, 'at_server_shutdown'):
            logger.log_info(f"Calling at_server_shutdown for Account {p.id}")
            p.at_server_shutdown()
        else:
            logger.log_warn(f"Account {p.id} does not have at_server_shutdown method")

    # Remove the SESSIONS.disconnect_all_sessions call

    logger.log_info("Custom server shutdown complete")

def at_server_reload_start():
    """
    This is called only when server starts back up after a reload.
    """
    pass

def at_server_reload_stop():
    """
    This is called only time the server stops during a reload.
    """
    logger.log_info("Custom server reload initiated")
    for p in AccountDB.objects.all():
        logger.log_info(f"Processing account: {p.id}, class: {p.__class__}, is custom: {isinstance(p, AccountDB)}")
        
        if hasattr(p, 'at_server_reload'):
            p.at_server_reload()
        else:
            logger.log_warn(f"Account {p.id} does not have at_server_reload method")

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
