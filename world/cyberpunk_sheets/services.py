# world/cyberpunk_sheets/services.py

import logging
from django.db.models import F

from evennia.objects.models import ObjectDB
from evennia.utils import logger

from world.cyberpunk_sheets.models import CharacterSheet

logger = logging.getLogger('cyberpunk.economy')

class CharacterMoneyService:
    @staticmethod
    def add_money(character, amount):
        """Add money to a character (works with typeclass or character sheet)"""
        logger.info(f"Adding {amount} to character {character}")
        
        # Handle character typeclass
        if isinstance(character, ObjectDB) or hasattr(character, 'db'):
            if not hasattr(character.db, 'eurodollars'):
                character.db.eurodollars = 0
            character.db.eurodollars += amount
            logger.info(f"New balance for character {character.key}: {character.db.eurodollars}")
            
            # Also update character sheet if it exists (for backward compatibility)
            if hasattr(character, 'character_sheet') and character.character_sheet:
                character.character_sheet.eurodollars = character.db.eurodollars
                character.character_sheet.save()
                
            return character.db.eurodollars
        
        # Fall back to old character sheet method
        return CharacterSheetMoneyService.add_money(character, amount)

    @staticmethod
    def spend_money(character, amount):
        """Spend money from a character (works with typeclass or character sheet)"""
        logger.info(f"Attempting to spend {amount} from character {character}")
        
        # Handle character typeclass
        if isinstance(character, ObjectDB) or hasattr(character, 'db'):
            if not hasattr(character.db, 'eurodollars'):
                character.db.eurodollars = 0
                
            if character.db.eurodollars >= amount:
                character.db.eurodollars -= amount
                logger.info(f"New balance for character {character.key}: {character.db.eurodollars}")
                
                # Also update character sheet if it exists (for backward compatibility)
                if hasattr(character, 'character_sheet') and character.character_sheet:
                    character.character_sheet.eurodollars = character.db.eurodollars
                    character.character_sheet.save()
                    
                return True
            
            logger.info(f"Insufficient funds for character {character.key}")
            return False
        
        # Fall back to old character sheet method
        return CharacterSheetMoneyService.spend_money(character, amount)

    @staticmethod
    def get_balance(character):
        """Get a character's money balance (works with typeclass or character sheet)"""
        # Handle character typeclass
        if isinstance(character, ObjectDB) or hasattr(character, 'db'):
            balance = getattr(character.db, 'eurodollars', 0)
            logger.info(f"Retrieved balance for character {character.key}: {balance}")
            return balance
        
        # Fall back to old character sheet method
        return CharacterSheetMoneyService.get_balance(character)

    @staticmethod
    def get_fashion_budget(character):
        """Get fashion budget remaining (chargen only, use-it-or-lose-it 800 eb pool)."""
        char = character.character_sheet if hasattr(character, 'character_sheet') and character.character_sheet else character
        if hasattr(char, 'fashion_budget_remaining'):
            return getattr(char, 'fashion_budget_remaining', 0)
        return 0

    @staticmethod
    def spend_fashion_money(character, amount):
        """Spend from fashion budget during chargen. Returns True if successful."""
        char = character.character_sheet if hasattr(character, 'character_sheet') and character.character_sheet else character
        if not hasattr(char, 'fashion_budget_remaining'):
            return False
        budget = getattr(char, 'fashion_budget_remaining', 0)
        if budget >= amount:
            char.fashion_budget_remaining = budget - amount
            char.save(skip_recalculation=True)
            if hasattr(character, 'db') and character.character_sheet == char:
                character.db.fashion_budget_remaining = char.fashion_budget_remaining
            return True
        return False

    @staticmethod
    def add_fashion_budget(character, amount):
        """Add back to fashion budget (e.g. for refunds)."""
        char = character.character_sheet if hasattr(character, 'character_sheet') and character.character_sheet else character
        if not hasattr(char, 'fashion_budget_remaining'):
            return
        char.fashion_budget_remaining = getattr(char, 'fashion_budget_remaining', 0) + amount
        char.save(skip_recalculation=True)
        if hasattr(character, 'db') and character.character_sheet == char:
            character.db.fashion_budget_remaining = char.fashion_budget_remaining

# Keep old service for backward compatibility
class CharacterSheetMoneyService:
    @staticmethod
    def add_money(character_sheet, amount):
        logger.info(f"Adding {amount} to character sheet {character_sheet.id}")
        sheet_id = getattr(character_sheet, 'id', None) or getattr(character_sheet, 'pk', None)
        if not sheet_id:
            logger.warning("Character sheet has no id/pk, cannot add money")
            return 0

        # Use atomic F() update to add to existing balance (prevents overwriting)
        updated = CharacterSheet.objects.filter(pk=sheet_id).update(
            eurodollars=F('eurodollars') + amount
        )
        if not updated:
            logger.warning(f"No rows updated for character sheet {sheet_id}")
            return 0

        # Refresh from DB to get new value and sync to character object
        character_sheet.refresh_from_db()
        new_balance = character_sheet.eurodollars
        logger.info(f"New balance for character sheet {sheet_id}: {new_balance}")

        # Also update character object if it exists
        if hasattr(character_sheet, 'character') and character_sheet.character:
            character_sheet.character.db.eurodollars = new_balance

        return new_balance

    @staticmethod
    def spend_money(character_sheet, amount):
        logger.info(f"Attempting to spend {amount} from character sheet {character_sheet.id}")
        if not hasattr(character_sheet, 'eurodollars'):
            logger.warning(f"Character sheet {character_sheet.id} has no eurodollars attribute")
            return False
        if character_sheet.eurodollars >= amount:
            character_sheet.eurodollars -= amount
            character_sheet.save()
            logger.info(f"New balance for character sheet {character_sheet.id}: {character_sheet.eurodollars}")
            
            # Also update character object if it exists
            if hasattr(character_sheet, 'character') and character_sheet.character:
                character_sheet.character.db.eurodollars = character_sheet.eurodollars
                
            return True
        logger.info(f"Insufficient funds for character sheet {character_sheet.id}")
        return False

    @staticmethod
    def get_balance(character_sheet):
        balance = getattr(character_sheet, 'eurodollars', 0)
        logger.info(f"Retrieved balance for character sheet {character_sheet.id}: {balance}")
        return balance