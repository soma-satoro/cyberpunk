import random
from evennia import Command
from evennia.utils.search import search_object
from evennia.utils import gametime
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.inventory.models import Weapon, Armor, Gear
from world.equipment_data import weapons, armors, gears
from evennia.utils.evmenu import get_input, EvMenu
from world.cyberpunk_sheets.merchants import Merchant

class Merchant:
    def __init__(self, merchant_type):
        self.merchant_type = merchant_type
        self.inventory = self._load_inventory()

    def _load_inventory(self):
        if self.merchant_type == "arms_dealer":
            return {item['name']: item for item in weapons}
        elif self.merchant_type == "clothier":
            return {item['name']: item for item in armors}
        elif self.merchant_type == "gear_merchant":
            return {item['name']: item for item in gears}
        else:
            return {}

    def get_item(self, item_name):
        return self.inventory.get(item_name)

    def list_items(self):
        return [f"{name} - {item['value']} eb" for name, item in self.inventory.items()]

class CmdBuy(Command):
    """
    Buy an item from a merchant.

    Usage:
      buy <item name> from <merchant>

    Purchase an item from a specific merchant in your current location.
    """

    key = "buy"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        if not self.args or " from " not in self.args:
            self.caller.msg("Usage: buy <item name> from <merchant>")
            return

        item_name, merchant_name = self.args.split(" from ")
        item_name = item_name.strip().lower()
        merchant_name = merchant_name.strip().lower()

        # Search for the merchant in the current location
        merchants = [obj for obj in self.caller.location.contents 
                     if obj.is_typeclass("world.cyberpunk_sheets.merchants.Merchant") 
                     and merchant_name in obj.name.lower()]
        
        if not merchants:
            self.caller.msg(f"There's no merchant named '{merchant_name}' here.")
            return
        merchant = merchants[0]

        item = merchant.get_item(item_name)
        if not item:
            self.caller.msg(f"Sorry, {item_name} is not available from this merchant.")
            return

        # Get character's inventory (checking typeclass first)
        inventory = self.get_character_inventory(self.caller)
        if not inventory:
            self.caller.msg("You don't have an inventory!")
            return

        # Check if the character already owns the item
        if self._item_exists_in_inventory(inventory, item):
            self.caller.msg(f"You already own {item['name']}.")
            return

        price = item['value']

        # Try to spend money
        if CharacterMoneyService.spend_money(self.caller, price):
            self._add_item_to_inventory(self.caller, item, merchant.db.merchant_type)
            self.caller.msg(f"You have purchased {item['name']} for {price} eb.")
        else:
            self.caller.msg(f"You don't have enough Eurodollars to buy {item['name']}. It costs {price} eb.")

    def get_character_inventory(self, character):
        """Get a character's inventory, checking typeclass first, then character sheet"""
        # Try to get inventory via typeclass attribute
        if hasattr(character, 'db') and hasattr(character.db, 'inventory'):
            return character.db.inventory
            
        # Try to get inventory via inventory_object relation
        if hasattr(character, 'inventory_object'):
            return character.inventory_object
            
        # Fall back to character sheet
        if hasattr(character, 'character_sheet') and character.character_sheet:
            return character.character_sheet.inventory
            
        return None

    def _item_exists_in_inventory(self, inventory, item):
        """Check if the item already exists in the character's inventory."""
        item_name = item['name'].lower()
        
        # Check weapons
        if inventory.weapons.filter(name__iexact=item_name).exists():
            return True
        
        # Check armor
        if inventory.armor.filter(name__iexact=item_name).exists():
            return True
        
        # Check gear
        if inventory.gear.filter(name__iexact=item_name).exists():
            return True
        
        return False

    def _add_item_to_inventory(self, character, item, merchant_type):
        # Get character's inventory (checking typeclass first)
        inventory = self.get_character_inventory(character)
        if not inventory:
            self.caller.msg("Error: Couldn't find your inventory.")
            return
        
        if merchant_type == "arms_dealer":
            weapon, created = Weapon.objects.get_or_create(
                name=item['name'],
                defaults={
                    'damage': item['damage'],
                    'rof': item['rof'],
                    'hands': item['hands'],
                    'concealable': item['concealable'],
                    'weight': item['weight'],
                    'value': item['value']
                }
            )
            inventory.weapons.add(weapon)
        elif merchant_type == "clothier":
            armor, created = Armor.objects.get_or_create(
                name=item['name'],
                defaults={
                    'sp': item['sp'],
                    'ev': item['ev'],
                    'locations': item['locations'],
                    'weight': item['weight'],
                    'value': item['value']
                }
            )
            inventory.armor.add(armor)
        elif merchant_type == "gear_merchant":
            gear, created = Gear.objects.get_or_create(
                name=item['name'],
                defaults={
                    'category': item['category'],
                    'description': item.get('description', ''),
                    'weight': item['weight'],
                    'value': item['value']
                }
            )
            inventory.gear.add(gear)

class CmdListItems(Command):
    """
    List items available from a merchant.

    Usage:
      list from <merchant>
      list items from <merchant>

    List all items available from a specific merchant in your current location.
    """

    key = "list"
    aliases = ["list items"]
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: list from <merchant> or list items from <merchant>")
            return

        args = self.args.strip().lower()
        
        if args.startswith("items from "):
            merchant_name = args[11:]
        elif args.startswith("from "):
            merchant_name = args[5:]
        else:
            self.caller.msg("Usage: list from <merchant> or list items from <merchant>")
            return

        # Debug: Print the merchant name being searched
        self.caller.msg(f"Debug: Searching for merchant named '{merchant_name}'")

        # Search for the merchant globally
        merchants = search_object(merchant_name)
        
        # Debug: Print all found objects
        self.caller.msg(f"Debug: Found objects: {merchants}")

        merchants = [obj for obj in merchants if obj.typeclass_path == "world.cyberpunk_sheets.merchants.Merchant"]

        # Debug: Print merchants after filtering
        self.caller.msg(f"Debug: Merchants after filtering: {merchants}")

        if not merchants:
            self.caller.msg(f"There's no merchant named '{merchant_name}' found.")
            return
        
        merchant = merchants[0]

        # Check if the merchant is in the same location as the character
        if merchant.location != self.caller.location:
            self.caller.msg(f"{merchant.name} is not here. They are located in {merchant.location}.")
            return

        items = merchant.list_items()

        if items:
            self.caller.msg(f"Items available from {merchant.name}:")
            for item in items:
                self.caller.msg(item)
        else:
            self.caller.msg(f"No items available from {merchant.name}.")

class CleanExitEvMenu(EvMenu):
    def close_menu(self):
        """Clean up and exit the menu without any additional output."""
        self.caller.cmdset.remove(self.cmdset_class)
        del self.caller.ndb._evmenu

def sell_node(caller, raw_string, **kwargs):
    context = caller.ndb._sell_item_context
    if not context:
        caller.msg("Error: Sell context not found.")
        return None

    text = f"{context['merchant'].name} offers {context['price']} eb for your {context['item'].name}.\nDo you want to sell it?"
    options = (
        {"key": ("y", "yes"), "desc": "Yes", "goto": "execute_sale"},
        {"key": ("n", "no"), "desc": "No", "goto": "cancel_sale"},
    )
    return text, options

def execute_sale(caller, raw_string, **kwargs):
    context = caller.ndb._sell_item_context
    merchant = context['merchant']
    item = context['item']
    price = context['price']

    # Remove the item from the character's inventory
    inventory = get_character_inventory(caller)
    category = 'weapons' if hasattr(item, 'damage') else 'armor' if hasattr(item, 'sp') else 'gear'
    getattr(inventory, category).remove(item)

    # Add money to the character
    CharacterMoneyService.add_money(caller, price)

    caller.msg(f"You sold {item.name} to {merchant.name} for {price} eb.")
    merchant.msg(f"{caller.name} sold you {item.name} for {price} eb.")

    del caller.ndb._sell_item_context
    
    # Update inventory display
    caller.execute_cmd('inventory')
    
    # Close the menu
    caller.ndb._evmenu.close_menu()

def cancel_sale(caller, raw_string, **kwargs):
    caller.msg("You decided not to sell the item.")
    del caller.ndb._sell_item_context
    
    # Close the menu
    caller.ndb._evmenu.close_menu()

def get_character_inventory(character):
    """Get a character's inventory, checking typeclass first, then character sheet"""
    # Try to get inventory via typeclass attribute
    if hasattr(character, 'db') and hasattr(character.db, 'inventory'):
        return character.db.inventory
        
    # Try to get inventory via inventory_object relation
    if hasattr(character, 'inventory_object'):
        return character.inventory_object
        
    # Fall back to character sheet
    if hasattr(character, 'character_sheet') and character.character_sheet:
        return character.character_sheet.inventory
        
    return None

class CmdSellItem(Command):
    """
    Sell an item to a merchant.

    Usage:
      sell <item name> to <merchant>

    This command allows you to sell items to merchants.
    """

    key = "sell"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        if not self.args or " to " not in self.args:
            self.caller.msg("Usage: sell <item name> to <merchant>")
            return

        item_name, merchant_name = self.args.split(" to ")
        item_name = item_name.strip().lower()
        merchant_name = merchant_name.strip().lower()

        # Search for the merchant in the current location
        merchants = [obj for obj in self.caller.location.contents 
                     if isinstance(obj, Merchant)  # Use isinstance instead of is_typeclass
                     and merchant_name in obj.name.lower()]
        
        if not merchants:
            self.caller.msg(f"There's no merchant named '{merchant_name}' here.")
            return
        merchant = merchants[0]

        # Find the item in the character's inventory
        inventory = get_character_inventory(self.caller)
        if not inventory:
            self.caller.msg("You don't have an inventory!")
            return
            
        item = None

        for category in ['weapons', 'armor', 'gear']:
            items = getattr(inventory, category).filter(name__iexact=item_name)
            if items.exists():
                item = items.first()
                break

        if not item:
            self.caller.msg(f"You don't have an item named '{item_name}' in your inventory.")
            return

        # Calculate the sell price
        sell_price = merchant.get_sell_price(item.__dict__)

        # Set up the context and start the menu
        self.caller.ndb._sell_item_context = {
            'merchant': merchant,
            'item': item,
            'price': sell_price
        }
        EvMenu(self.caller, "world.cyberpunk_sheets.commerce", 
               startnode="sell_node", auto_quit=True, cmd_on_exit=None)

class CmdHaggle(Command):
    """
    Haggle with a merchant over the price of an item.

    Usage:
      haggle <item name> with <merchant>

    This command allows you to haggle with merchants to get a better price for your items.
    """

    key = "haggle"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        if not self.args or " with " not in self.args:
            self.caller.msg("Usage: haggle <item name> with <merchant>")
            return

        item_name, merchant_name = self.args.split(" with ")
        item_name = item_name.strip().lower()
        merchant_name = merchant_name.strip().lower()

        # Search for the merchant in the current location
        merchants = [obj for obj in self.caller.location.contents 
                     if isinstance(obj, Merchant)  # Use isinstance instead of is_typeclass
                     and merchant_name in obj.name.lower()]
        
        if not merchants:
            self.caller.msg(f"There's no merchant named '{merchant_name}' here.")
            return
        merchant = merchants[0]

        # Check if the character can haggle
        if not merchant.can_haggle(self.caller):
            self.caller.msg(f"You can't haggle with {merchant.name} yet. Try again later.")
            return

        # Find the item in the character's inventory
        inventory = get_character_inventory(self.caller)
        if not inventory:
            self.caller.msg("You don't have an inventory!")
            return
            
        item = None

        for category in ['weapons', 'armor', 'gear']:
            items = getattr(inventory, category).filter(name__iexact=item_name)
            if items.exists():
                item = items.first()
                break

        if not item:
            self.caller.msg(f"You don't have an item named '{item_name}' in your inventory.")
            return

        # Get character's cool and trading skill values
        cool = merchant.get_character_cool(self.caller)
        trading = merchant.get_character_trading_skill(self.caller)
        
        # Perform the haggle check
        roll = random.randint(1, 10)
        total = cool + trading + roll

        # Determine the result
        base_price = merchant.get_sell_price(item.__dict__)
        if roll == 1:  # Critical failure
            price_multiplier = 0.50
            self.caller.msg("Critical failure! The merchant is offended by your low offer.")
            merchant.db.haggle_attempts[self.caller.id] = gametime.time() + 7 * 24 * 60 * 60  # 1 week cooldown
        elif roll == 10:  # Critical success
            price_multiplier = 1.75
            self.caller.msg("Critical success! The merchant is impressed by your negotiation skills.")
        elif total > 13:  # Success
            price_multiplier = 1.25
            self.caller.msg("Success! You've negotiated a better price.")
        else:  # Failure
            price_multiplier = 1.0
            self.caller.msg("Your attempt to haggle was unsuccessful.")

        final_price = int(base_price * price_multiplier)

        # Record the haggle attempt
        merchant.record_haggle_attempt(self.caller)

        self.caller.ndb._sell_item_context = {
            'merchant': merchant,
            'item': item,
            'price': final_price
        }
        EvMenu(self.caller, "world.cyberpunk_sheets.commerce", 
               startnode="sell_node", auto_quit=True, cmd_on_exit=None)

def handle_sell_confirmation(character, response):
    context = character.ndb._sell_item_context
    if not context:
        character.msg("Error: Sell context not found.")
        return

    if response.lower() in ["y", "yes"]:
        merchant = context['merchant']
        item = context['item']
        price = context['price']

        # Remove the item from the character's inventory
        inventory = get_character_inventory(character)
        category = 'weapons' if hasattr(item, 'damage') else 'armor' if hasattr(item, 'sp') else 'gear'
        getattr(inventory, category).remove(item)

        # Add money to the character
        CharacterMoneyService.add_money(character, price)

        character.msg(f"You sold {item.name} to {merchant.name} for {price} eb.")
        merchant.msg(f"{character.name} sold you {item.name} for {price} eb.")
        
        # Clean up
        del character.ndb._sell_item_context
    elif response.lower() in ["n", "no"]:
        character.msg("You decided not to sell the item.")
        
        # Clean up
        del character.ndb._sell_item_context
    else:
        character.msg("Invalid response. Please type 'y' or 'n'.")
        get_input(character, "Do you want to sell it? (y/n)", handle_sell_confirmation)

class CmdAddItem(Command):
    """
    Add an item to a merchant's inventory.

    Usage:
      additem <item name> to <merchant>

    This command allows administrators to add items to a merchant's inventory.
    The item must exist in the equipment data.
    """

    key = "additem"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or " to " not in self.args:
            self.caller.msg("Usage: additem <item name> to <merchant>")
            return

        item_name, merchant_name = self.args.split(" to ")
        item_name = item_name.strip()
        merchant_name = merchant_name.strip()

        # Search for the merchant
        merchants = search_object(merchant_name)
        if not merchants:
            self.caller.msg(f"No merchant named '{merchant_name}' found.")
            return
        merchant = merchants[0]

        if not merchant.is_typeclass("world.cyberpunk_sheets.merchants.Merchant"):
            self.caller.msg(f"{merchant_name} is not a valid merchant.")
            return

        # Find the item in the equipment data
        all_items = weapons + armors + gears
        item = next((item for item in all_items if item['name'].lower() == item_name.lower()), None)

        if not item:
            self.caller.msg(f"No item named '{item_name}' found in the equipment data.")
            return

        # Add the item to the merchant's inventory
        if not hasattr(merchant.db, 'inventory'):
            merchant.db.inventory = []
        
        if item not in merchant.db.inventory:
            merchant.db.inventory.append(item)
            self.caller.msg(f"Added {item_name} to {merchant_name}'s inventory.")
        else:
            self.caller.msg(f"{item_name} is already in {merchant_name}'s inventory.")

class CmdRemItem(Command):
    """
    Remove an item from a merchant's inventory.

    Usage:
      remitem <item name> from <merchant>

    This command allows administrators to remove items from a merchant's inventory.
    """

    key = "remitem"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or " from " not in self.args:
            self.caller.msg("Usage: remitem <item name> from <merchant>")
            return

        item_name, merchant_name = self.args.split(" from ")
        item_name = item_name.strip()
        merchant_name = merchant_name.strip()

        # Search for the merchant
        merchants = search_object(merchant_name)
        if not merchants:
            self.caller.msg(f"No merchant named '{merchant_name}' found.")
            return
        merchant = merchants[0]

        if not merchant.is_typeclass("world.cyberpunk_sheets.merchants.Merchant"):
            self.caller.msg(f"{merchant_name} is not a valid merchant.")
            return

        # Remove the item from the merchant's inventory
        if not hasattr(merchant.db, 'inventory'):
            self.caller.msg(f"{merchant_name} has no inventory.")
            return

        item = next((item for item in merchant.db.inventory if item['name'].lower() == item_name.lower()), None)
        if item:
            merchant.db.inventory.remove(item)
            self.caller.msg(f"Removed {item_name} from {merchant_name}'s inventory.")
        else:
            self.caller.msg(f"No item named '{item_name}' found in {merchant_name}'s inventory.")