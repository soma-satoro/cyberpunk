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
      addcyberware/pair <cyberware item>=<character name>

    Examples:
      addcyberware Sandevistan=Soma
      addcyberware/pair Cybereye=Soma

    Adds the specified cyberware to the character's inventory, installed.
    With /pair: adds a second Cybereye/Cyberarm/Cyberleg and pairs it to the existing one.
    Cyberware must exist in the database (run populate_cyberware if needed).
    """

    key = "addcyberware"
    switches = [("pair", "pair")]
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
        character = self.caller.search(character_name, typeclass="typeclasses.characters.Character", global_search=True)
        if not character:
            character = self.caller.search(character_name, global_search=True)
        if not character:
            return

        # Get character sheet (required for inventory/humanity)
        char_sheet = getattr(character, "character_sheet", None)
        if not char_sheet:
            self.caller.msg(f"{character.key} does not have a character sheet.")
            return

        # Get or create inventory
        inventory, _ = Inventory.get_or_create_for_character(character)

        use_pair = "pair" in (self.switches or [])

        if use_pair:
            # Find existing installed instance to pair with
            first_instance = inventory.cyberware.filter(
                cyberware__name__iexact=cyberware_name,
                installed=True,
                paired_with__isnull=True,
            ).first()
            if not first_instance:
                self.caller.msg(
                    f"{character.key} does not have an unpaired {cyberware.name} to pair with. "
                    "Add the first one with addcyberware (without /pair)."
                )
                return
            # Check they don't already have a paired second
            if inventory.cyberware.filter(
                cyberware__name__iexact=cyberware_name,
                installed=True,
                paired_with=first_instance,
            ).exists():
                self.caller.msg(f"{character.key} already has a paired {cyberware.name}.")
                return

            cw_instance = CyberwareInstance.objects.create(
                cyberware=cyberware,
                character_object=character,
                character_sheet=char_sheet,
                installed=True,
                active=False,
                paired_with=first_instance,
            )
        else:
            # Normal add: block if already installed
            if inventory.cyberware.filter(
                cyberware__name__iexact=cyberware_name, installed=True
            ).exists():
                self.caller.msg(
                    f"{character.key} already has {cyberware.name} installed. "
                    "Use addcyberware/pair to add a paired second."
                )
                return

            cw_instance = CyberwareInstance.objects.create(
                cyberware=cyberware,
                character_object=character,
                character_sheet=char_sheet,
                installed=True,
                active=False,
            )

        inventory.cyberware.add(cw_instance)
        char_sheet.calculate_humanity_loss()

        if cyberware.name.lower() == "cyberarm":
            char_sheet.has_cyberarm = True
            char_sheet.recalculate_derived_stats()

        pair_msg = " (paired)" if use_pair else ""
        self.caller.msg(
            f"Added {cyberware.name}{pair_msg} (installed) to {character.key}. "
            f"Humanity loss: {cyberware.humanity_loss}."
        )
        character.msg(
            f"A {cyberware.name}{pair_msg} has been added to your cyberware (installed)."
        )
