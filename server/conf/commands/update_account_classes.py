from evennia.accounts.models import AccountDB
from evennia.utils import logger
from typeclasses.accounts import Account

def update_account_classes():
    updated_count = 0
    for account in AccountDB.objects.all():
        if not isinstance(account, Account):
            account.swap_typeclass("typeclasses.accounts.Account", clean_attributes=False)
            logger.log_info(f'Updated account {account.id} to use custom Account class')
            updated_count += 1
    logger.log_info(f"Finished updating account classes. Updated {updated_count} accounts.")
    return updated_count

if __name__ == "__main__":
    update_account_classes()