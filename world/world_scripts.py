from evennia import DefaultScript
from world.missions import init_mission_system
from world.bulletin_boards import init_bulletin_board_system
from world.hustle_system import init_hustle_system
from evennia.utils.logger import log_err

class WorldScript(DefaultScript):
    """
    This script is responsible for initializing various world systems.
    """

    def at_script_creation(self):
        self.key = "WorldScript"
        self.desc = "Initializes world systems"
        self.persistent = True

    def at_start(self):
        """
        This is called when the script is started.
        """
        self.initialize_systems()

    def initialize_systems(self):
        """
        Initialize all world systems.
        """
        systems = [
            ("Mission System", init_mission_system),
            ("Bulletin Board System", init_bulletin_board_system),
            ("Hustle System", init_hustle_system)
        ]

        for system_name, init_func in systems:
            try:
                init_func()
                self.db.initialized_systems = self.db.initialized_systems or {}
                self.db.initialized_systems[system_name] = True
            except Exception as e:
                log_err(f"Error initializing {system_name}: {str(e)}")
                self.db.initialized_systems = self.db.initialized_systems or {}
                self.db.initialized_systems[system_name] = False

# Function to start the world script
def start_world_script():
    WorldScript().start()