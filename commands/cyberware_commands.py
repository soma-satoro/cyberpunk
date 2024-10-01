from evennia import Command
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import CyberwareInstance
from world.cyberware.models import Cyberware
from evennia.commands.default.muxcommand import MuxCommand
from world.utils.formatting import header, footer, divider
from django.db.models import Q

class CmdCyberware(MuxCommand):
    """
    Show installed cyberware and its information.

    Usage:
      cyberware
      cyberware <name>

    Examples:
      cyberware
      cyberware Neural Link
    """

    key = "cyberware"
    aliases = ["cyber"]
    lock = "cmd:all()"
    help_category = "Character"

    def func(self):
        try:
            character_sheet = CharacterSheet.objects.get(character=self.caller)
        except CharacterSheet.DoesNotExist:
            self.caller.msg("You don't have a character sheet. Please create one using the 'chargen' command.")
            return

        if not character_sheet:
            self.caller.msg("You don't have a character sheet. Please create one using the 'chargen' command.")
            return

        if not self.args:
            self.list_cyberware(character_sheet)
        else:
            self.view_specific_cyberware(character_sheet, self.args.strip())

    def list_cyberware(self, character_sheet):
        installed_cyberware = CyberwareInstance.objects.filter(character=character_sheet, installed=True)

        if not installed_cyberware:
            self.caller.msg("You have no cyberware installed.")
            return

        output = header("Installed Cyberware", width=78, fillchar="|m-|n") + "\n"
        output += f"|c{'Name':<20}{'Type':<15}{'Humanity Loss':<15}{'Description':<25}|n\n"

        for instance in installed_cyberware:
            cyberware = instance.cyberware
            description = cyberware.description[:22] + "..." if len(cyberware.description) > 25 else cyberware.description
            output += f"{cyberware.name:<20}{cyberware.type:<15}{cyberware.humanity_loss:<15}{description:<25}\n"

        output += footer(width=78, fillchar="|m-|n")
        output += "\nUse 'cyberware <name>' to view full details of a specific piece of cyberware."
        self.caller.msg(output)

    def view_specific_cyberware(self, character_sheet, cyberware_name):
        cyberware_name = cyberware_name.strip()  # Remove leading/trailing whitespace
        try:
            cyberware_instance = CyberwareInstance.objects.get(
                character=character_sheet,
                cyberware__name__iexact=cyberware_name,
                installed=True
            )
        except CyberwareInstance.DoesNotExist:
            self.caller.msg(f"You don't have a piece of cyberware named '{cyberware_name}' installed.")
            return

        cyberware = cyberware_instance.cyberware
        
        output = header(cyberware.name, width=78, fillchar="|m-|n") + "\n"
        output += f"|cType:|n {cyberware.type}\n"
        output += f"|cSlots:|n {cyberware.slots}\n"
        output += f"|cHumanity Loss:|n {cyberware.humanity_loss}\n"
        output += f"|cCost:|n {cyberware.cost} eb\n"
        output += divider("Description", width=78, fillchar="|m-|n") + "\n"
        output += f"{cyberware.description}\n"
        output += footer(width=78, fillchar="|m-|n")
        
        self.caller.msg(output)

class CmdActivateCyberware(Command):
    """
    Activate a cyberware weapon.

    Usage:
      activate <cyberware_name>

    This command activates a cyberware weapon, modifying your unarmed strike damage.
    Only one cyberware weapon can be active at a time.
    """

    key = "activate"
    locks = "cmd:all()"
    help_category = "Cyberware"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: activate <cyberware_name>")
            return

        cyberware_name = self.args.strip().lower()

        try:
            character_sheet = self.caller.character_sheet
        except AttributeError:
            self.caller.msg("You don't have a character sheet.")
            return

        # Debug: Print all installed cyberware
        installed_cyberware = CyberwareInstance.objects.filter(
            character=character_sheet,
            installed=True
        )
        self.caller.msg("Installed cyberware:")
        for cw in installed_cyberware:
            self.caller.msg(f"- {cw.cyberware.name} (is_weapon: {cw.cyberware.is_weapon}, damage_dice: {cw.cyberware.damage_dice}, damage_die_type: {cw.cyberware.damage_die_type}, rate_of_fire: {cw.cyberware.rate_of_fire})")

        # Attempt to find the cyberware
        try:
            cyberware = CyberwareInstance.objects.filter(
                character=character_sheet,
                installed=True,
                cyberware__is_weapon=True
            ).filter(
                Q(cyberware__name__iexact=cyberware_name) |
                Q(cyberware__name__icontains=cyberware_name)
            ).first()

            if not cyberware:
                raise CyberwareInstance.DoesNotExist

        except CyberwareInstance.DoesNotExist:
            self.caller.msg(f"You don't have an installed cyberware weapon named '{cyberware_name}'.")
            return

        # Debug: Print found cyberware details
        self.caller.msg(f"Found cyberware: {cyberware.cyberware.name}")
        self.caller.msg(f"Is weapon: {cyberware.cyberware.is_weapon}")
        self.caller.msg(f"Damage: {cyberware.cyberware.damage_dice}d{cyberware.cyberware.damage_die_type}")
        self.caller.msg(f"Rate of fire: {cyberware.cyberware.rate_of_fire}")

        # Deactivate any previously activated cyberware
        CyberwareInstance.objects.filter(character=character_sheet, active=True).update(active=False)

        # Activate the selected cyberware
        cyberware.active = True
        cyberware.save()

        # Calculate base unarmed damage based on Body stat
        base_damage_dice = character_sheet.calculate_base_unarmed_damage()

        # Update the character's unarmed strike damage
        character_sheet.unarmed_damage_dice = max(base_damage_dice, cyberware.cyberware.damage_dice)
        character_sheet.unarmed_damage_die_type = 6  # Always d6 as per the rules
        character_sheet.save()

        self.caller.msg(f"You have activated {cyberware.cyberware.name}. Your unarmed strike now deals {character_sheet.unarmed_damage_dice}d6 damage.")

        # Check if the cyberware is a cyberarm and update the has_cyberarm flag
        if cyberware.cyberware.name.lower() == "cyberarm":
            character_sheet.has_cyberarm = True
            character_sheet.save()
            self.caller.msg("Your Cyberarm installation has been registered.")