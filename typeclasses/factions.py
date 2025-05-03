# this is a typeclass for factions

from .objects import ObjectParent
from evennia import search_object, create_object
from world.factions.models import Faction as FactionModel, Group as GroupModel
from world.factions.faction_types import FACTION_TYPES
from evennia.utils import logger
import random

class Faction(ObjectParent):
    """
    Typeclass for faction objects.
    
    This represents an in-game faction entity, separate from but linked to
    the database model. The faction object lives in a storage room and can
    listen for faction-related commands.
    """
    
    def at_object_creation(self):
        """Set up the faction object when first created."""
        # Core attributes
        self.db.faction_types = FACTION_TYPES
        self.db.model_id = None  # Will link to database model
        self.db.faction_type = None
        self.db.player_created = False
        self.db.members = []  # List of objectdb IDs of members
        
        # Set locks to prevent players from manipulating the faction object directly
        self.locks.add("control:perm(Admin);delete:perm(Admin);edit:perm(Admin)")
        
        # Make this object a global script that can be accessed anywhere
        self.cmdset.add_default("commands.faction_commands.FactionCmdSet")
        
    def link_to_model(self, model_id):
        """Link this typeclass to a database model."""
        self.db.model_id = model_id
        try:
            model = FactionModel.objects.get(id=model_id)
            self.key = model.name
            self.db.description = model.description
            self.db.ic_description = model.ic_description
            self.db.influence = model.influence
            self.db.faction_type = model.faction_type  # This will now get a list if multiple types
            logger.log_info(f"Linked faction typeclass {self.key} to model ID {model_id}")
            return True
        except FactionModel.DoesNotExist:
            logger.log_err(f"Failed to link faction typeclass to non-existent model ID {model_id}")
            return False
    
    @property
    def model(self):
        """Get the database model linked to this typeclass."""
        if self.db.model_id:
            try:
                return FactionModel.objects.get(id=self.db.model_id)
            except FactionModel.DoesNotExist:
                logger.log_err(f"Faction model with ID {self.db.model_id} no longer exists")
        return None
    
    def add_member(self, character):
        """Add a character as a member of this faction."""
        if not character:
            return False
            
        # Set faction affiliation on the character
        character.db.faction = self.key
        
        # Add to our tracking list if not already there
        if character.id not in self.db.members:
            self.db.members.append(character.id)
            logger.log_info(f"Added {character.key} to faction {self.key}")
        
        return True
    
    def remove_member(self, character):
        """Remove a character from this faction."""
        if not character:
            return False
            
        # Remove faction affiliation
        if character.db.faction == self.key:
            character.db.faction = None
        
        # Remove from tracking list
        if character.id in self.db.members:
            self.db.members.remove(character.id)
            logger.log_info(f"Removed {character.key} from faction {self.key}")
        
        return True
    
    def get_members(self):
        """Get all member characters of this faction."""
        members = []
        for member_id in self.db.members:
            try:
                character = ObjectParent.objects.get(id=member_id)
                members.append(character)
            except ObjectParent.DoesNotExist:
                # Clean up stale references
                self.db.members.remove(member_id)
        return members
        
    def update_from_model(self):
        """Update this typeclass from its database model."""
        model = self.model
        if not model:
            return False
            
        self.key = model.name
        self.db.description = model.description
        self.db.ic_description = model.ic_description
        self.db.influence = model.influence
        return True
    
    def create_database_factions(self):
        """Create the default factions in the database if they don't exist."""
        from world.factions.default_faction_dictionary import default_faction_dictionary
        
        for faction_data in default_faction_dictionary:
            name = faction_data.get("name")
            if not FactionModel.objects.filter(name=name).exists():
                # Get faction type(s)
                faction_type = faction_data.get("faction_type")
                if isinstance(faction_type, str):
                    faction_type = [faction_type]
                    
                faction = FactionModel.objects.create(
                    name=name,
                    description=faction_data.get("description", ""),
                    ic_description=faction_data.get("ic_description", ""),
                    influence=faction_data.get("influence", 50),
                    faction_type=faction_type
                )
                logger.log_info(f"Created default faction: {name}")
                
                # Create a faction object for each default faction
                storage = self.get_faction_storage()
                if storage:
                    faction_obj = create_object(
                        "typeclasses.factions.Faction",
                        key=name,
                        location=storage
                    )
                    faction_obj.db.faction_type = faction_type
                    faction_obj.link_to_model(faction.id)
    
    @classmethod
    def get_faction_storage(cls):
        """Get or create the faction storage room."""
        storage = search_object("Faction Storage", exact=True)
        if storage:
            return storage[0]
        
        # If not found, create it
        from typeclasses.rooms import Room
        try:
            storage = create_object(
                "typeclasses.rooms.Room",
                key="Faction Storage"
            )
            storage.db.desc = "This room stores faction objects. Do not delete."
            logger.log_info("Created Faction Storage room")
            return storage
        except Exception as e:
            logger.log_err(f"Failed to create Faction Storage: {e}")
            return None
    
    @classmethod
    def create_player_faction(cls, name, description="", ic_description="", creator=None, faction_type=None):
        """Create a new player faction."""
        # First, create the database model
        try:
            # Set default faction type if none provided
            if faction_type is None:
                faction_type = ["edgerunner"]
            elif isinstance(faction_type, str):
                faction_type = [faction_type]
                
            faction_model = FactionModel.objects.create(
                name=name,
                description=description,
                ic_description=ic_description,
                influence=FACTION_TYPES["edgerunner"]["influence_base"],
                faction_type=faction_type
            )
            
            # Then create the typeclass object
            storage = cls.get_faction_storage()
            if not storage:
                logger.log_err("Could not create faction - no storage room found")
                return None
                
            faction_obj = create_object(
                "typeclasses.factions.Faction",
                key=name,
                location=storage
            )
            
            faction_obj.db.faction_type = faction_type
            faction_obj.db.player_created = True
            faction_obj.link_to_model(faction_model.id)
            
            # Add creator as first member if provided
            if creator:
                faction_obj.add_member(creator)
                
            logger.log_info(f"Created player faction: {name}")
            return faction_obj
            
        except Exception as e:
            logger.log_err(f"Failed to create faction {name}: {e}")
            return None
    
    @classmethod
    def get_faction(cls, faction_name):
        """Get a faction object by name."""
        factions = search_object(faction_name, typeclass="typeclasses.factions.Faction")
        if factions:
            return factions[0]
        return None
        
    def at_pre_delete(self):
        """Clean up related data when this object is deleted."""
        # Remove faction affiliation from all members
        for member_id in self.db.members:
            try:
                character = ObjectParent.objects.get(id=member_id)
                character.db.faction = None
            except ObjectParent.DoesNotExist:
                pass
                
        # Delete the database model if it exists
        if self.model:
            self.model.delete()
