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