from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.evtable import EvTable
from world.missions import get_or_create_mission_board
from world.events import get_or_create_event_scheduler
from evennia.utils import gametime, logger
from datetime import datetime

class CmdMission(MuxCommand):
    """
    Base command for missions and events.
    Usage:
      mission -
      mission/list -
      mission/accept <mission_id> -
      mission/complete <mission_id> -
      mission/status -
      mission/create <title> = <description>/<difficulty>/<reward>/<max_players>/<deadline>/<reputation_requirement> -
      mission/events -
      mission/createevent <title> = <description>/<date_time>/<associated_mission_id> -
      mission/eventinfo <event_id> -
      mission/joinevent <event_id> -
      mission/leaveevent <event_id> -
      mission/startevent <event_id> -
      mission/completeevent <event_id> -
    """
    key = "mission"
    aliases = ["missions", "event", "events"]
    locks = "cmd:all()"

    def func(self):
        pass

        if self.args == "list":
            return CmdListMissions().func(self)
        elif self.args == "accept":
            return CmdAcceptMission().func(self)
        elif self.args == "complete":
            return CmdCompleteMission().func(self)
        elif self.args == "status":
            return CmdMissionStatus().func(self)
        elif self.args == "create":
            return CmdCreateMission().func(self)
        elif self.args == "events":
            return CmdListEvents().func(self)
        elif self.args == "createevent":
            return CmdCreateEvent().func(self)
            

class CmdListMissions(Command):
    """
    List available missions.

    Usage:
      missions

    This command shows all available missions that you qualify for based on your reputation.
    """
    key = "missions"
    aliases = ["listmissions"]
    locks = "cmd:all()"
    help_category = "Missions and Events"

    def func(self):
        if not self.caller.character_sheet:
            self.caller.msg("You need a character sheet to view missions.")
            return

        mission_board = get_or_create_mission_board()
        if not mission_board:
            self.caller.msg("Error: Unable to access the mission board. Please contact an admin.")
            return

        available_missions = mission_board.get_available_missions(self.caller)

        if not available_missions:
            self.caller.msg("There are no missions available for you at the moment.")
            return

        table = EvTable("ID", "Title", "Difficulty", "Reward", "Players", "Deadline", border="cells")
        for mission in available_missions:
            table.add_row(
                mission.id,
                mission.db.title,
                mission.db.difficulty,
                f"{mission.db.reward} eb",
                f"{len(mission.db.assigned_to)}/{mission.db.max_players}",
                mission.db.deadline.strftime("%Y-%m-%d %H:%M:%S")
            )

        self.caller.msg(table)

class CmdAcceptMission(Command):
    """
    Accept a mission.

    Usage:
      accept <mission_id>

    This command allows you to accept a mission from the mission board.
    """
    key = "accept"
    locks = "cmd:all()"
    help_category = "Missions and Events"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: accept <mission_id>")
            return

        try:
            mission_id = int(self.args)
        except ValueError:
            self.caller.msg("Invalid mission ID. Please use a number.")
            return

        mission_board = get_or_create_mission_board()
        if not mission_board:
            self.caller.msg("Error: Unable to access the mission board. Please contact an admin.")
            return

        mission = mission_board.get_mission_by_id(mission_id)

        if not mission:
            self.caller.msg("Mission not found.")
            return

        if mission.db.status != "available":
            self.caller.msg("This mission is not available.")
            return

        if mission.db.reputation_requirement > self.caller.character_sheet.rep:
            self.caller.msg("You don't have enough reputation to accept this mission.")
            return

        mission.assign_to(self.caller)

class CmdCompleteMission(Command):
    """
    Complete a mission.

    Usage:
      complete <mission_id>

    This command allows you to complete a mission you've accepted.
    """
    key = "complete"
    locks = "cmd:all()"
    help_category = "Missions and Events"

    def func(self):
        if not self.args:
            self.caller.msg("You must specify a mission ID.")
            return

        try:
            mission_id = int(self.args)
        except ValueError:
            self.caller.msg("Invalid mission ID. Please use a number.")
            return

        mission_board = self.caller.search("MissionBoard", global_search=True)
        if not mission_board:
            self.caller.msg("The mission board is not available.")
            return

        mission = mission_board.get_mission_by_id(mission_id)

        if not mission:
            self.caller.msg("Mission not found.")
            return

        if self.caller not in mission.db.assigned_to:
            self.caller.msg("This mission is not assigned to you.")
            return

        if mission.db.status != "in_progress":
            self.caller.msg("This mission is not in progress.")
            return

        if mission.db.associated_event and mission.db.associated_event.db.status != "completed":
            self.caller.msg("The associated event for this mission has not been completed yet.")
            return

        mission.complete_mission()

class CmdMissionStatus(Command):
    """
    Check the status of your current missions.

    Usage:
      missionstatus

    This command shows the status of all missions you have accepted.
    """
    key = "missionstatus"
    locks = "cmd:all()"
    help_category = "Missions and Events"

    def func(self):
        mission_board = self.caller.search("MissionBoard", global_search=True)
        if not mission_board:
            self.caller.msg("The mission board is not available.")
            return

        current_missions = [m for m in mission_board.db.missions if self.caller in m.db.assigned_to]

        if not current_missions:
            self.caller.msg("You have no active missions.")
            return

        table = EvTable("ID", "Title", "Status", "Players", "Deadline", border="cells")
        for mission in current_missions:
            table.add_row(
                mission.id,
                mission.db.title,
                mission.db.status,
                f"{len(mission.db.assigned_to)}/{mission.db.max_players}",
                mission.db.deadline.strftime("%Y-%m-%d %H:%M:%S")
            )

        self.caller.msg(table)

class CmdCreateMission(Command):
    """
    Create a new mission (Fixer only).

    Usage:
      createmission <title> = <description>/<difficulty>/<reward>/<max_players>/<deadline>/<reputation_requirement>

    This command allows Fixers to create new missions for the mission board.
    """
    key = "createmission"
    locks = "cmd:role(Fixer)"
    help_category = "Missions and Events"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: createmission <title> = <description>/<difficulty>/<reward>/<max_players>/<deadline>/<reputation_requirement>")
            return

        title, args = self.args.split("=", 1)
        title = title.strip()
        args = args.strip().split("/")

        if len(args) != 6:
            self.caller.msg("You must provide all required information.")
            return

        description, difficulty, reward, max_players, deadline, reputation_requirement = args

        try:
            difficulty = int(difficulty)
            reward = int(reward)
            max_players = int(max_players)
            deadline = gametime.gametime(absolute=True) + int(deadline) * 3600  # Convert hours to seconds
            reputation_requirement = int(reputation_requirement)
        except ValueError:
            self.caller.msg("Invalid input. Make sure all numeric values are correct.")
            return

        mission_board = self.caller.search("MissionBoard", global_search=True)
        if not mission_board:
            mission_board = get_or_create_mission_board()

        new_mission = mission_board.create_mission(
            title, description, difficulty, reward, max_players, deadline, reputation_requirement, self)

        new_mission = mission_board.create_mission(
            title, description, difficulty, reward, max_players, deadline, reputation_requirement, self.caller
        )

        self.caller.msg(f"Created new mission: {new_mission.db.title}")

class CmdListEvents(Command):
    """
    List all upcoming events.

    Usage:
      events

    This command shows all upcoming events.
    """
    key = "events"
    aliases = ["listevents"]
    locks = "cmd:all()"
    help_category = "Missions and Events"

    def func(self):
        try:
            event_scheduler = get_or_create_event_scheduler()
            if not event_scheduler:
                self.caller.msg("Error: Unable to access the event scheduler. Please contact an admin.")
                return

            upcoming_events = event_scheduler.get_upcoming_events()

            logger.log_info(f"Retrieved {len(upcoming_events)} upcoming events for {self.caller.name}")

            if not upcoming_events:
                self.caller.msg("There are no upcoming events.")
                return

            table = EvTable("ID", "Title", "Organizer", "Date/Time", border="cells")
            for event in upcoming_events:
                table.add_row(
                    event.id,
                    event.db.title,
                    event.db.organizer,
                    event.db.date_time.strftime("%Y-%m-%d %H:%M:%S")
                )

            self.caller.msg(table)
        except Exception as e:
            logger.log_trace(f"Error in CmdListEvents for {self.caller.name}: {str(e)}")
            self.caller.msg(f"An error occurred while retrieving events: {str(e)}. Please try again later or contact an admin.")

class CmdCreateEvent(Command):
    """
    Create a new event.

    Usage:
      createevent <title> = <description>/<date_time>/<associated_mission_id>

    This command allows you to create a new event. The date_time should be in the format YYYY-MM-DD HH:MM:SS.
    The associated_mission_id is optional.
    """
    key = "createevent"
    locks = "cmd:perm(Builders)"
    help_category = "Missions and Events"

    def func(self):
        try:
            if not self.args or "=" not in self.args:
                self.caller.msg("Usage: createevent <title> = <description>/<date_time>/<associated_mission_id>")
                return

            title, args = self.args.split("=", 1)
            title = title.strip()
            args = args.strip().split("/")

            if len(args) < 2 or len(args) > 3:
                self.caller.msg("You must provide a description and date_time, and optionally an associated mission ID.")
                return

            description = args[0].strip()
            date_time_str = args[1].strip()
            associated_mission_id = args[2].strip() if len(args) == 3 else None

            try:
                date_time = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
                logger.log_info(f"Parsed date_time: {date_time}")
            except ValueError:
                self.caller.msg("Invalid date/time format. Use YYYY-MM-DD HH:MM:SS.")
                return

            event_scheduler = get_or_create_event_scheduler()
            if not event_scheduler:
                self.caller.msg("Error: Unable to access the event scheduler. Please contact an admin.")
                return

            associated_mission = None
            if associated_mission_id:
                mission_board = get_or_create_mission_board()
                if mission_board:
                    associated_mission = mission_board.get_mission_by_id(int(associated_mission_id))
                    if not associated_mission:
                        self.caller.msg(f"Mission with ID {associated_mission_id} not found.")
                        return

            new_event = event_scheduler.create_event(title, description, self.caller, date_time, associated_mission)
            if new_event:
                self.caller.msg(f"Created new event: {new_event.db.title}")
                logger.log_info(f"Event created: {title} by {self.caller.name}, Date: {date_time}")
            else:
                self.caller.msg("Failed to create the event. Please try again or contact an admin.")

        except Exception as e:
            logger.log_trace(f"Error in CmdCreateEvent: {str(e)}")
            self.caller.msg(f"An error occurred while creating the event: {str(e)}. Please try again or contact an admin.")

class CmdEventInfo(Command):
    """
    Get detailed information about an event.

    Usage:
      eventinfo <event_id>

    This command shows detailed information about a specific event.
    """
    key = "eventinfo"
    locks = "cmd:all()"
    help_category = "Missions and Events"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: eventinfo <event_id>")
            return

        try:
            event_id = int(self.args)
        except ValueError:
            self.caller.msg("Invalid event ID. Please use a number.")
            return

        event_scheduler = get_or_create_event_scheduler()
        if not event_scheduler:
            self.caller.msg("Error: Unable to access the event system. Please contact an admin.")
            return

        event = event_scheduler.get_event_by_id(event_id)

        if not event:
            self.caller.msg(f"Event with ID {event_id} not found.")
            return

        info = f"|cEvent Information:|n\n"
        info += f"Title: {event.db.title}\n"
        info += f"Organizer: {event.db.organizer}\n"
        info += f"Date/Time: {event.db.date_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        info += f"Status: {event.db.status}\n"
        info += f"Description: {event.db.description}\n"
        if event.db.associated_mission:
            info += f"Associated Mission: {event.db.associated_mission.db.title} (ID: {event.db.associated_mission.id})\n"
        info += f"Participants: {', '.join([str(p) for p in event.db.participants])}\n"

        self.caller.msg(info)

class CmdJoinEvent(Command):
    """
    Join an event.

    Usage:
      joinevent <event_id>

    This command allows you to join a specific event.
    """
    key = "joinevent"
    locks = "cmd:all()"
    help_category = "Missions and Events"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: joinevent <event_id>")
            return

        try:
            event_id = int(self.args)
        except ValueError:
            self.caller.msg("Invalid event ID. Please use a number.")
            return

        event_scheduler = get_or_create_event_scheduler()
        if not event_scheduler:
            self.caller.msg("Error: Unable to access the event system. Please contact an admin.")
            return

        success = event_scheduler.join_event(event_id, self.caller)

        if success:
            self.caller.msg(f"You have joined the event with ID {event_id}.")
        else:
            self.caller.msg(f"Unable to join the event with ID {event_id}. The event may not exist or you may already be a participant.")


class CmdLeaveEvent(Command):
    """
    Leave an event.

    Usage:
      leaveevent <event_id>

    This command allows you to leave a specific event you've joined.
    """
    key = "leaveevent"
    locks = "cmd:all()"
    help_category = "Missions and Events"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: leaveevent <event_id>")
            return

        try:
            event_id = int(self.args)
        except ValueError:
            self.caller.msg("Invalid event ID. Please use a number.")
            return

        event_scheduler = get_or_create_event_scheduler()
        if not event_scheduler:
            self.caller.msg("The event system is not available.")
            return

        event = event_scheduler.get_event_by_id(event_id)

        if not event:
            self.caller.msg(f"Event with ID {event_id} not found.")
            return

        if self.caller not in event.db.participants:
            self.caller.msg("You are not participating in this event.")
            return

        event.db.participants.remove(self.caller)
        self.caller.msg(f"You have left the event: {event.db.title}")

class CmdStartEvent(Command):
    """
    Start an event.

    Usage:
      startevent <event_id>

    This command allows event organizers or admins to start a specific event.
    """
    key = "startevent"
    locks = "cmd:perm(Builders)"
    help_category = "Missions and Events"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: startevent <event_id>")
            return

        try:
            event_id = int(self.args)
        except ValueError:
            self.caller.msg("Invalid event ID. Please use a number.")
            return

        event_scheduler = get_or_create_event_scheduler()
        if not event_scheduler:
            self.caller.msg("The event system is not available.")
            return

        event = event_scheduler.get_event_by_id(event_id)

        if not event:
            self.caller.msg(f"Event with ID {event_id} not found.")
            return

        if event.db.organizer != self.caller and not self.caller.check_permstring("Admin"):
            self.caller.msg("You don't have permission to start this event.")
            return

        event.start_event()
        self.caller.msg(f"Event '{event.db.title}' has been started.")

class CmdCompleteEvent(Command):
    """
    Complete an event.

    Usage:
      completeevent <event_id>

    This command allows event organizers or admins to mark a specific event as completed.
    """
    key = "completeevent"
    locks = "cmd:perm(Builders)"
    help_category = "Missions and Events"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: completeevent <event_id>")
            return

        try:
            event_id = int(self.args)
        except ValueError:
            self.caller.msg("Invalid event ID. Please use a number.")
            return

        event_scheduler = get_or_create_event_scheduler()
        if not event_scheduler:
            self.caller.msg("The event system is not available.")
            return

        event = event_scheduler.get_event_by_id(event_id)

        if not event:
            self.caller.msg(f"Event with ID {event_id} not found.")
            return

        if event.db.organizer != self.caller and not self.caller.check_permstring("Admin"):
            self.caller.msg("You don't have permission to complete this event.")
            return

        event.complete_event()
        self.caller.msg(f"Event '{event.db.title}' has been marked as completed.")