from evennia import DefaultScript
from evennia.utils import gametime, create
from evennia.scripts.models import ScriptDB
from evennia.utils import logger
from world.cyberpunk_sheets.services import CharacterMoneyService
import random

class Mission(DefaultScript):
    """
    This script represents a mission in the game.
    """
    def at_script_creation(self):
        self.key = "Mission"
        self.desc = "A mission script"
        self.interval = 3600  # Check mission status every hour
        self.persistent = True

        # Mission properties
        self.db.title = ""
        self.db.description = ""
        self.db.difficulty = 1
        self.db.reward = 0
        self.db.giver = None
        self.db.assigned_to = []
        self.db.max_players = 1
        self.db.status = "available"  # available, in_progress, completed, failed
        self.db.deadline = None
        self.db.reputation_requirement = 0
        self.db.associated_event = None

    def at_repeat(self):
        """
        Called every self.interval seconds.
        """
        if self.db.status == "in_progress" and self.db.deadline:
            if gametime.gametime(absolute=True) > self.db.deadline:
                self.fail_mission()

    def assign_to(self, character):
        """
        Assign the mission to a character.
        """
        if len(self.db.assigned_to) < self.db.max_players:
            self.db.assigned_to.append(character)
            if len(self.db.assigned_to) == self.db.max_players:
                self.db.status = "in_progress"
            character.msg(f"You have accepted the mission: {self.db.title}")
        else:
            character.msg("This mission is already full.")

    def complete_mission(self):
        """
        Mark the mission as completed and give rewards.
        """
        self.db.status = "completed"
        for character in self.db.assigned_to:
            character.msg(f"You have completed the mission: {self.db.title}")
            
            # Add money and reputation
            CharacterMoneyService.add_money(character, self.db.reward)
            self.add_character_reputation(character, self.db.difficulty * 10)

    def add_character_reputation(self, character, rep_amount):
        """Add reputation to a character, checking typeclass first then falling back to character sheet"""
        if hasattr(character, 'db'):
            # Check if reputation attributes exist, create if they don't
            if not hasattr(character.db, 'reputation_points'):
                character.db.reputation_points = 0
            if not hasattr(character.db, 'rep'):
                character.db.rep = 0
                
            # Add reputation points
            character.db.reputation_points += rep_amount
            
            # Update rep level (every 100 points = 1 level, max 10)
            new_rep = min(character.db.reputation_points // 100, 10)
            if new_rep != character.db.rep:
                character.db.rep = new_rep
                character.msg(f"Your reputation has increased to {new_rep}!")
                
            # Also update character sheet if it exists (for backwards compatibility)
            if hasattr(character, 'character_sheet') and character.character_sheet:
                character.character_sheet.reputation_points = character.db.reputation_points
                character.character_sheet.rep = character.db.rep
                character.character_sheet.save()
        # Fall back to character sheet if db attributes not found
        elif hasattr(character, 'character_sheet') and character.character_sheet:
            character.character_sheet.add_reputation(rep_amount)

    def fail_mission(self):
        """
        Mark the mission as failed.
        """
        self.db.status = "failed"
        for character in self.db.assigned_to:
            character.msg(f"You have failed the mission: {self.db.title}")

class MissionBoard(DefaultScript):
    """
    This script manages all missions in the game.
    """
    def at_script_creation(self):
        self.key = "MissionBoard"
        self.desc = "Manages all missions"
        self.persistent = True
        self.db.missions = []

    def create_mission(self, title, description, difficulty, reward, max_players, deadline, reputation_requirement, giver):
        """
        Create a new mission with given properties.
        """
        mission = Mission()
        mission.db.title = title
        mission.db.description = description
        mission.db.difficulty = difficulty
        mission.db.reward = reward
        mission.db.max_players = max_players
        mission.db.deadline = deadline
        mission.db.reputation_requirement = reputation_requirement
        mission.db.giver = giver
        self.db.missions.append(mission)
        return mission

    def get_available_missions(self, character):
        """
        Get all available missions for a character based on their reputation.
        """
        reputation = self.get_character_reputation(character)
        return [m for m in self.db.missions if m.db.status == "available" and m.db.reputation_requirement <= reputation]

    def get_character_reputation(self, character):
        """Get a character's reputation, checking typeclass first then character sheet"""
        # Check typeclass DB attributes
        if hasattr(character, 'db') and hasattr(character.db, 'rep'):
            return character.db.rep
        # Fall back to character sheet
        elif hasattr(character, 'character_sheet') and character.character_sheet:
            return character.character_sheet.rep
        # Default value
        return 0

    def get_mission_by_id(self, mission_id):
        """
        Get a mission by its ID.
        """
        return next((m for m in self.db.missions if m.id == mission_id), None)

# Function to initialize the mission system
def init_mission_system():
    try:
        board = ScriptDB.objects.get(db_key="MissionBoard")
        logger.log_info("Retrieved existing MissionBoard.")
    except ScriptDB.DoesNotExist:
        board = create.create_script(MissionBoard, key="MissionBoard")
        if isinstance(board, bool):
            # If create_script returned a boolean, try to fetch the script
            try:
                board = ScriptDB.objects.get(db_key="MissionBoard")
                logger.log_info("Created new MissionBoard and retrieved it.")
            except ScriptDB.DoesNotExist:
                logger.log_err("Failed to create MissionBoard script.")
                return None
        else:
            logger.log_info("Created new MissionBoard.")
    except ScriptDB.MultipleObjectsReturned:
        boards = ScriptDB.objects.filter(db_key="MissionBoard")
        board = boards.first()
        for extra in boards[1:]:
            extra.delete()
        logger.log_info(f"Multiple MissionBoards found. Kept one and deleted {len(boards) - 1} extra(s).")
    
    if board and hasattr(board, 'is_active') and callable(board.is_active):
        if not board.is_active():
            board.start()
            logger.log_info("Started inactive MissionBoard.")
    else:
        logger.log_warn("Retrieved board is not a proper MissionBoard instance.")
    
    return board

# Function to get or create the mission board
def get_or_create_mission_board():
    board = init_mission_system()
    if not board:
        logger.log_err("Failed to initialize or retrieve MissionBoard.")
    return board