from evennia import DefaultObject
from evennia.utils import gametime
from world.equipment_data import weapons, armors, gears

class Merchant(DefaultObject):
    """
    This is a typeclass for merchant NPCs in the game.
    """

    def at_object_creation(self):
        """
        Called when the object is first created.
        """
        super().at_object_creation()
        
        # Set default attributes
        self.db.merchant_type = "general"
        self.db.description = "A merchant ready to trade goods."
        self.db.inventory = []
        self.db.haggle_attempts = {}

    def setup_merchant(self, merchant_type):
        """
        Set up the merchant with a specific type and initialize inventory.
        """
        merchant_type = str(merchant_type).lower()  # Ensure merchant_type is a lowercase string
        valid_types = ["arms_dealer", "clothier", "gear_merchant"]
        if merchant_type not in valid_types:
            raise ValueError(f"Invalid merchant type. Choose from: {', '.join(valid_types)}")
        
        self.db.merchant_type = merchant_type
        self.db.description = f"A {merchant_type.replace('_', ' ')} ready to trade goods."
        
        # Initialize inventory based on merchant type
        if merchant_type == "arms_dealer":
            self.db.inventory = weapons.copy()
        elif merchant_type == "clothier":
            self.db.inventory = armors.copy()
        elif merchant_type == "gear_merchant":
            self.db.inventory = gears.copy()

    def can_haggle(self, character):
        """Check if a character can haggle with this merchant."""
        if not self.db.haggle_attempts:
            self.db.haggle_attempts = {}
        last_attempt = self.db.haggle_attempts.get(character.id, 0)
        time_since_last_attempt = gametime.gametime(absolute=True) - last_attempt
        return time_since_last_attempt >= 24 * 60 * 60  # 24 hours in seconds

    def record_haggle_attempt(self, character):
        """Record a haggling attempt for a character."""
        if not self.db.haggle_attempts:
            self.db.haggle_attempts = {}
        self.db.haggle_attempts[character.id] = gametime.gametime(absolute=True)

    def get_sell_price(self, item):
        """Get the sell price for an item."""
        return int(item.get('value', 0) * 0.5)  # 50% of original value

    def list_items(self):
        """List all items available from this merchant."""
        if not self.db.inventory:
            return []
        return [f"{item['name']} - {item['value']} eb" for item in self.db.inventory]

    def get_item(self, item_name):
        """Get a specific item from the merchant's inventory."""
        return next((item for item in self.db.inventory if item['name'].lower() == item_name.lower()), None)
    
    def at_post_puppet(self):
        """
        Called just after puppeting has been completed and all
        Account<->Object links have been established.
        """
        super().at_post_puppet()
        # If the merchant type hasn't been set up, set it up now
        if self.db.merchant_type == "general":
            self.setup_merchant(self.db.merchant_type)
        self.msg(f"\nYou are now puppeting {self.name}, a {self.db.merchant_type.replace('_', ' ')}.")

    def at_pre_puppet(self):
        """
        Called just before puppeting is about to begin.
        """
        super().at_pre_puppet()
        # Ensure the merchant is properly set up
        if not hasattr(self.db, 'merchant_type') or self.db.merchant_type == "general":
            self.setup_merchant("general")
    
    def get_character_trading_skill(self, character):
        """
        Get a character's trading skill level, checking typeclass first, then sheet.
        
        Args:
            character: The character to check
            
        Returns:
            int: The trading skill level
        """
        # First check typeclass attributes
        if hasattr(character, 'db'):
            # Check skills dictionary if it exists
            if hasattr(character.db, 'skills') and character.db.skills:
                return character.db.skills.get('trading', 0)
            # Check for direct attribute
            if hasattr(character.db, 'trading'):
                return character.db.trading
                
        # Fall back to character sheet
        if hasattr(character, 'character_sheet') and character.character_sheet:
            return getattr(character.character_sheet, 'trading', 0)
            
        # Default value if not found
        return 0
    
    def get_character_cool(self, character):
        """
        Get a character's cool stat, checking typeclass first, then sheet.
        
        Args:
            character: The character to check
            
        Returns:
            int: The cool stat value
        """
        # First check typeclass attributes
        if hasattr(character, 'db') and hasattr(character.db, 'cool'):
            return character.db.cool
                
        # Fall back to character sheet
        if hasattr(character, 'character_sheet') and character.character_sheet:
            return getattr(character.character_sheet, 'cool', 0)
            
        # Default value if not found
        return 0

def create_cyberware_merchant(location):
    """
    Create a Ripperdoc (cyberware merchant) at the specified location.
    
    Args:
        location: The location where the Ripperdoc should be created
        
    Returns:
        Merchant: The created Ripperdoc merchant object
    """
    from evennia import create_object
    from world.cyberware.utils import get_all_cyberware
    
    # Create the merchant object
    ripperdoc = create_object(
        "world.cyberpunk_sheets.merchants.Merchant",
        key="Ripperdoc",
        location=location
    )
    
    # Set up custom attributes for the Ripperdoc
    ripperdoc.db.merchant_type = "ripperdoc"
    ripperdoc.db.description = "A skilled cyberware surgeon who sells and installs various cybernetic enhancements."
    
    # Get cyberware inventory from cyberware utils
    try:
        ripperdoc.db.inventory = get_all_cyberware()
    except Exception as e:
        # Fall back to empty inventory if there's an error
        ripperdoc.db.inventory = []
        ripperdoc.db.error_msg = str(e)
    
    # Add additional attributes specific to Ripperdoc
    ripperdoc.db.surgery_fee = 100  # Base fee for cyberware installation
    ripperdoc.db.reputation = 3     # On a scale of 1-10
    
    return ripperdoc