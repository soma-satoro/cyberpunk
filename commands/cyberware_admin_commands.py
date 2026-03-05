"""
Admin commands for cyberware management.
"""
from evennia.commands.default.muxcommand import MuxCommand
from world.cyberware.models import Cyberware
from world.inventory.models import CyberwareInstance, Inventory


class CmdAddCyberware(MuxCommand):
    """
    Add cyberware to a character (staff only).

    Usage:
      addcyberware <cyberware item>=<character name>

    Example:
      addcyberware Sandevistan=Soma

    Adds the specified cyberware to the character's inventory, installed.
    Cyberware must exist in the database (run populate_cyberware if needed).
    """

    key = "addcyberware"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: addcyberware <cyberware item>=<character name>")
            return

        cyberware_name = self.lhs.strip().strip('"')
        character_name = self.rhs.strip().strip('"')

        if not cyberware_name or not character_name:
            self.caller.msg("Usage: addcyberware <cyberware item>=<character name>")
            return

        # Find the cyberware
        try:
            cyberware = Cyberware.objects.get(name__iexact=cyberware_name)
        except Cyberware.DoesNotExist:
            self.caller.msg(
                f"Cyberware '{cyberware_name}' not found in database. "
                "Run 'populate_cyberware' to load cyberware from the data files."
            )
            return

        # Find the character
        character = self.caller.search(character_name, typeclass="typeclasses.characters.Character")
        if not character:
            character = self.caller.search(character_name)
        if not character:
            return

        # Get character sheet (required for inventory/humanity)
        char_sheet = getattr(character, "character_sheet", None)
        if not char_sheet:
            self.caller.msg(f"{character.key} does not have a character sheet.")
            return

        # Get or create inventory
        inventory, _ = Inventory.get_or_create_for_character(character)

        # Check if they already have this cyberware installed
        if inventory.cyberware.filter(
            cyberware__name__iexact=cyberware_name, installed=True
        ).exists():
            self.caller.msg(
                f"{character.key} already has {cyberware.name} installed."
            )
            return

        # Create CyberwareInstance (installed)
        cw_instance = CyberwareInstance.objects.create(
            cyberware=cyberware,
            character_object=character,
            character_sheet=char_sheet,
            installed=True,
            active=False,
        )
        inventory.cyberware.add(cw_instance)
        char_sheet.calculate_humanity_loss()

        self.caller.msg(
            f"Added {cyberware.name} (installed) to {character.key}. "
            f"Humanity loss: {cyberware.humanity_loss}."
        )
        character.msg(
            f"A {cyberware.name} has been added to your cyberware (installed)."
        )
