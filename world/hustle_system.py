from evennia import DefaultScript
from evennia.utils import gametime, create
from evennia.scripts.models import ScriptDB
from evennia.utils import logger
from world.cyberpunk_sheets.services import CharacterMoneyService, CharacterSheetMoneyService
import random



class HustleSystem(DefaultScript):
    """
    This script manages the hustle side missions for characters.
    """
    def at_script_creation(self):
        self.key = "HustleSystem"
        self.desc = "Manages hustle side missions"
        self.interval = 604800  # 1 week in seconds
        self.persistent = True
        self.db.available_hustles = {}
        self.db.last_attempt = {}  # Track last attempt for each character
        self.generate_hustles()  # Generate initial hustles

    def at_start(self):
        """
        Called when the script is started.
        """
        self.generate_hustles()

    def at_repeat(self):
        """
        Called every week to generate new hustles and reset attempt tracking.
        """
        self.generate_hustles()
        self.db.last_attempt = {}  # Reset attempt tracking
        logger.log_info("HustleSystem: Weekly reset completed. New hustles generated.")

    def generate_hustles(self):
        """
        Generate new hustles for each role.
        """
        roles = ["Rockerboy", "Solo", "Netrunner", "Tech", "Medtech", "Media", "Exec", "Lawman", "Fixer", "Nomad"]
        self.db.available_hustles = {}
        
        for role in roles:
            hustle = self.generate_hustle_for_role(role)
            self.db.available_hustles[role] = hustle
        
        logger.log_info(f"HustleSystem: Generated hustles for roles: {', '.join(roles)}")

    def generate_hustle_for_role(self, role):
        """
        Generate a hustle for a specific role.
        """
        d6 = random.randint(1, 6)
        
        if role == "Rockerboy":
            if d6 <= 3:
                return {"name": "Street Performance", "difficulty": 13, "payout": 100}
            elif d6 <= 5:
                return {"name": "Club Gig", "difficulty": 15, "payout": 200}
            else:
                return {"name": "Corporate Event", "difficulty": 17, "payout": 500}
        elif role == "Solo":
            if d6 <= 3:
                return {"name": "Bodyguard Duty", "difficulty": 13, "payout": 100}
            elif d6 <= 5:
                return {"name": "Security Consultant", "difficulty": 15, "payout": 200}
            else:
                return {"name": "High-Risk Escort", "difficulty": 17, "payout": 500}
        # Add similar logic for other roles
        else:
            return {"name": "Generic Hustle", "difficulty": 15, "payout": 200}

    def get_available_hustle(self, character):
        """
        Get the available hustle for a character based on their role.
        """
        # Get character role - first check typeclass attributes, then fall back to character sheet
        role = None
        
        # Check if character has a db attribute
        if hasattr(character, 'db') and hasattr(character.db, 'role') and character.db.role:
            role = character.db.role
            logger.log_info(f"HustleSystem: Found role {role} in character typeclass attributes")
        # Fall back to character sheet
        elif hasattr(character, 'character_sheet') and character.character_sheet and character.character_sheet.role:
            role = character.character_sheet.role
            logger.log_info(f"HustleSystem: Found role {role} in character sheet")
        else:
            logger.log_warn(f"HustleSystem: Character {character.name} has no role.")
            return None
            
        hustle = self.db.available_hustles.get(role)
        if not hustle:
            logger.log_warn(f"HustleSystem: No hustle found for role {role}. Available hustles: {self.db.available_hustles}")
        return hustle

    def can_attempt_hustle(self, character):
        """
        Check if the character can attempt a hustle this week.
        """
        last_attempt = self.db.last_attempt.get(character.id, 0)
        current_time = gametime.gametime(absolute=True)
        return (current_time - last_attempt) >= self.interval

    def attempt_hustle(self, character, hustle):
        """
        Attempt a hustle for a character.
        """
        logger.log_info(f"Attempting hustle for {character.name}")
        try:
            if not self.can_attempt_hustle(character):
                logger.log_info(f"{character.name} has already attempted a hustle this week.")
                return False, "You have already attempted your hustle this week.", 0, 0, 0

            # Define a mapping of roles to their corresponding abilities
            role_abilities = {
                "Rockerboy": "charismatic_impact",
                "Solo": "combat_awareness",
                "Netrunner": "interface",
                "Tech": "maker",
                "Medtech": "medicine",
                "Media": "credibility",
                "Exec": "teamwork",
                "Lawman": "backup",
                "Fixer": "operator",
                "Nomad": "moto"
            }
            
            # Get character role and abilities from character or character sheet
            role = None
            role_ability_value = 0
            cool_value = 0
            
            # First try to get from character typeclass
            if hasattr(character, 'db'):
                if hasattr(character.db, 'role'):
                    role = character.db.role
                
                # Get the role-specific ability or default to cool
                role_ability = role_abilities.get(role, 'cool') if role else 'cool'
                
                # Check if ability is in character's skills dictionary
                if hasattr(character.db, 'skills') and character.db.skills:
                    role_ability_value = character.db.skills.get(role_ability, 0)
                    cool_value = character.db.skills.get('cool', 0)
                # Otherwise, check direct attributes
                else:
                    role_ability_value = getattr(character.db, role_ability, 0)
                    cool_value = getattr(character.db, 'cool', 0)
            
            # Fall back to character sheet if values weren't found
            if role is None and hasattr(character, 'character_sheet') and character.character_sheet:
                cs = character.character_sheet
                role = cs.role
                
                # Get the role-specific ability or default to cool
                role_ability = role_abilities.get(role, 'cool') if role else 'cool'
                role_ability_value = getattr(cs, role_ability, 0)
                cool_value = getattr(cs, 'cool', 0)
            
            if role is None:
                logger.log_warn(f"HustleSystem: Couldn't determine role for {character.name}")
                return False, "You need to have a defined role to attempt a hustle.", 0, 0, 0
            
            logger.log_info(f"{character.name} - Role: {role}, Role Ability: {role_ability}, Value: {role_ability_value}, Cool: {cool_value}")

            dice_roll = random.randint(1, 10)
            total_roll = cool_value + role_ability_value + dice_roll
            
            logger.log_info(f"{character.name} - Dice Roll: {dice_roll}, Total Roll: {total_roll}, Difficulty: {hustle['difficulty']}")

            # Record the attempt
            self.db.last_attempt[character.id] = gametime.gametime(absolute=True)
            
            if total_roll >= hustle['difficulty']:
                logger.log_info(f"{character.name} succeeded in the hustle.")
                CharacterMoneyService.add_money(character, hustle['payout'])
                return True, f"Success! You earned {hustle['payout']} eb from your {hustle['name']} hustle.", total_roll, cool_value, role_ability_value
            else:
                logger.log_info(f"{character.name} failed the hustle.")
                return False, f"You failed your {hustle['name']} hustle. Better luck next time!", total_roll, cool_value, role_ability_value
        except Exception as e:
            logger.log_trace(f"Error in attempt_hustle for {character.name}: {str(e)}")
            return False, f"An error occurred: {str(e)}", 0, 0, 0

# Function to get or create the hustle system
def get_or_create_hustle_system():
    try:
        script = ScriptDB.objects.get(db_key="HustleSystem")
        logger.log_info("Retrieved existing HustleSystem.")
    except ScriptDB.DoesNotExist:
        script = create.create_script(HustleSystem, key="HustleSystem")
        if isinstance(script, bool):
            # If create_script returned a boolean, try to fetch the script
            try:
                script = ScriptDB.objects.get(db_key="HustleSystem")
                logger.log_info("Created new HustleSystem and retrieved it.")
            except ScriptDB.DoesNotExist:
                logger.log_err("Failed to create HustleSystem script.")
                return None
        else:
            logger.log_info("Created new HustleSystem.")
    except ScriptDB.MultipleObjectsReturned:
        scripts = ScriptDB.objects.filter(db_key="HustleSystem")
        script = scripts.first()
        for extra in scripts[1:]:
            extra.delete()
        logger.log_info(f"Multiple HustleSystems found. Kept one and deleted {len(scripts) - 1} extra(s).")
    
    if script and hasattr(script, 'is_active') and callable(script.is_active):
        if not script.is_active():
            script.start()
            logger.log_info("Started inactive HustleSystem.")
    else:
        logger.log_warn("Retrieved script is not a proper HustleSystem instance.")
    
    return script