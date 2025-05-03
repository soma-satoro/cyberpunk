# world/cyberpunk_sheets/services.py

import logging
from evennia.objects.models import ObjectDB
from evennia.utils import logger

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

# Keep old service for backward compatibility
class CharacterSheetMoneyService:
    @staticmethod
    def add_money(character_sheet, amount):
        logger.info(f"Adding {amount} to character sheet {character_sheet.id}")
        if not hasattr(character_sheet, 'eurodollars'):
            logger.warning(f"Character sheet {character_sheet.id} has no eurodollars attribute")
            character_sheet.eurodollars = 0
        character_sheet.eurodollars += amount
        character_sheet.save()
        logger.info(f"New balance for character sheet {character_sheet.id}: {character_sheet.eurodollars}")
        
        # Also update character object if it exists
        if hasattr(character_sheet, 'character') and character_sheet.character:
            character_sheet.character.db.eurodollars = character_sheet.eurodollars
            
        return character_sheet.eurodollars

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