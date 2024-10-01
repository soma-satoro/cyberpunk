# world/cyberpunk_sheets/services.py

import logging

logger = logging.getLogger('cyberpunk.economy')

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
            return True
        logger.info(f"Insufficient funds for character sheet {character_sheet.id}")
        return False

    @staticmethod
    def get_balance(character_sheet):
        balance = getattr(character_sheet, 'eurodollars', 0)
        logger.info(f"Retrieved balance for character sheet {character_sheet.id}: {balance}")
        return balance