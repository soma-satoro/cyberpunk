"""
Commands for handling data migrations and system transitions.
"""
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils import logger
from world.scripts import run_migration, add_global_migration_script

class CmdMigrateCharacterSheets(MuxCommand):
    """
    Migrate character data from Django models to typeclass attributes.

    Usage:
      @migratecharsheets [/options]

    Options:
      /all         - Migrate all character sheets
      /single <character> - Migrate only the specified character
      /test        - Run in test mode without saving changes

    This command moves character data from the CharacterSheet Django model
    to the Character typeclass's attributes directly. This provides a more
    native Evennia approach to character data and eliminates circular
    dependencies between apps.
    
    This is an admin-only command.
    """

    key = "@migratecharsheets"
    aliases = ["@migratesheets"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        """Execute the command."""
        caller = self.caller
        args = self.args.strip()
        switches = self.switches

        if not switches:
            caller.msg("Please specify an option. See help @migratecharsheets for details.")
            return

        # Handle migration of all character sheets
        if "all" in switches:
            caller.msg("Starting migration of all character sheets...")
            success_count, error_count = run_migration()
            caller.msg(f"Migration complete. {success_count} successful, {error_count} failed.")
            return

        # Handle migration of a single character
        if "single" in switches:
            if not args:
                caller.msg("You must specify a character name.")
                return
                
            # Find the character
            char = caller.search(args)
            if not char:
                return
                
            # Check if this is a character with a character sheet
            if not hasattr(char, "migrate_sheet_to_typeclass"):
                caller.msg(f"{char.name} is not a character or doesn't support migration.")
                return
                
            # Attempt the migration
            try:
                result = char.migrate_sheet_to_typeclass()
                if result:
                    caller.msg(f"Successfully migrated {char.name}'s character sheet.")
                else:
                    caller.msg(f"Failed to migrate {char.name}'s character sheet (no sheet found).")
            except Exception as e:
                caller.msg(f"Error migrating {char.name}'s sheet: {e}")
                logger.log_trace(f"Error in single character migration for {char.name}")
            return
            
        # Test mode
        if "test" in switches:
            caller.msg("Test mode is not fully implemented yet. Use /all to perform the migration.")
            return
            
        caller.msg("Invalid option. See help @migratecharsheets for usage.")


class CmdToggleMigrationMode(MuxCommand):
    """
    Toggle between model-based and typeclass-based character data.

    Usage:
      @migrationmode <mode>

    Options:
      legacy - Use the legacy Django model for character data
      native - Use the native Evennia typeclass attributes
      status - Show current mode

    This admin command controls whether character data is primarily stored
    in the Django models or in typeclass attributes. During the transition
    period, both systems can work together, but one should be designated
    as primary.
    
    This is an admin-only command.
    """

    key = "@migrationmode"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        """Execute the command."""
        caller = self.caller
        args = self.args.strip().lower()
        
        # Get the migration script
        script = add_global_migration_script()
        current_mode = script.attributes.get("data_mode", "legacy")
        
        if not args or args == "status":
            caller.msg(f"Current character data mode: {current_mode}")
            return
            
        if args == "legacy":
            script.attributes.add("data_mode", "legacy")
            caller.msg("Character data mode set to LEGACY (Django model-based).")
            return
            
        if args == "native":
            script.attributes.add("data_mode", "native")
            caller.msg("Character data mode set to NATIVE (Typeclass-based).")
            return
            
        caller.msg("Invalid mode. Use 'legacy', 'native', or 'status'.") 