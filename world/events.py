from evennia import DefaultScript, create_script
from evennia.utils import gametime
from evennia.scripts.models import ScriptDB
from datetime import datetime

class Event(DefaultScript):
    """
    This script represents a scheduled event in the game.
    """
    def at_script_creation(self):
        self.key = "Event"
        self.desc = "A scheduled event"
        self.interval = 3600  # Check event status every hour
        self.persistent = True

        # Event properties will be set after creation

    def setup(self, title, description, organizer, date_time, associated_mission=None):
        """
        Set up the event properties after creation.
        """
        self.db.title = title
        self.db.description = description
        self.db.organizer = organizer
        self.db.participants = []
        self.db.date_time = date_time
        self.db.status = "scheduled"
        self.db.associated_mission = associated_mission


    def at_repeat(self):
        """
        Called every self.interval seconds.
        """
        if self.db.status == "scheduled" and self.db.date_time:
            if gametime.gametime(absolute=True) > self.db.date_time:
                self.start_event()

    def start_event(self):
        """
        Start the event.
        """
        self.db.status = "in_progress"
        for participant in self.db.participants:
            participant.msg(f"The event '{self.db.title}' has started!")

    def complete_event(self):
        """
        Complete the event.
        """
        self.db.status = "completed"
        for participant in self.db.participants:
            participant.msg(f"The event '{self.db.title}' has been completed!")
        
        if self.db.associated_mission:
            self.db.associated_mission.complete_mission()

    def cancel_event(self):
        """
        Cancel the event.
        """
        self.db.status = "cancelled"
        for participant in self.db.participants:
            participant.msg(f"The event '{self.db.title}' has been cancelled.")

    def join_event(self, character):
        """
        Add a character to the event's participants.
        """
        if character not in self.db.participants:
            self.db.participants.append(character)
            self.save()
            return True
        return False


class EventScheduler(DefaultScript):
    """
    This script manages all scheduled events in the game.
    """
    def at_script_creation(self):
        self.key = "EventScheduler"
        self.desc = "Manages all scheduled events"
        self.persistent = True
        self.db.events = []

    def create_event(self, title, description, organizer, date_time, associated_mission=None):
        """
        Create a new event with given properties.
        """
        event = create_script(Event, key=f"Event_{title}")
        event.setup(title, description, organizer, date_time, associated_mission)
        if event not in self.db.events:
            self.db.events.append(event)
        self.save()
        return event

    def get_upcoming_events(self):
        """
        Get all upcoming events.
        """
        current_time = datetime.fromtimestamp(gametime.gametime(absolute=True))
        return [
            e for e in (self.db.events or [])
            if e.db.status == "scheduled" and e.db.date_time > current_time
        ]
    
    def get_event_by_id(self, event_id):
        """
        Get a specific event by its ID.
        """
        for event in self.db.events:
            if event.id == event_id:
                return event
        return None

    def join_event(self, event_id, character):
        """
        Join a character to an event.
        """
        event = self.get_event_by_id(event_id)
        if event:
            return event.join_event(character)
        return False

# Function to initialize the event scheduling system
def init_event_system():
    try:
        scheduler = ScriptDB.objects.get(db_key="EventScheduler")
    except ScriptDB.DoesNotExist:
        scheduler = create_script(EventScheduler, key="EventScheduler")
    except ScriptDB.MultipleObjectsReturned:
        schedulers = ScriptDB.objects.filter(db_key="EventScheduler")
        scheduler = schedulers.first()
        for extra in schedulers[1:]:
            extra.delete()

    if scheduler and isinstance(scheduler, EventScheduler):
        if not scheduler.is_active:
            scheduler.start()
    else:
        return None

    return scheduler


def get_or_create_event_scheduler():
    return init_event_system()
