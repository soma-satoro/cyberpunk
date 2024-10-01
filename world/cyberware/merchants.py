# world/cyberware/merchants.py

import inspect
from evennia import Command
from world.cyberware.models import CYBERWARE_HUMANITY_LOSS
from world.inventory.models import CyberwareInstance
from world.cyberpunk_sheets.models import CharacterSheet
from .models import Cyberware
from evennia import CmdSet

def check_cyberware_requirements(character, cyberware):
    print(f"Debug: Entering check_cyberware_requirements for {cyberware.name}")
    
    # Specific checks for main cyberware
    if cyberware.name.lower() == "cybereye":
        cybereye_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cybereye", installed=True).count()
        print(f"Debug: Current Cybereye count: {cybereye_count}")
        
        if cybereye_count >= 2:
            multioptic_mount = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="MultiOptic Mount", installed=True).exists()
            print(f"Debug: MultiOptic Mount exists: {multioptic_mount}")
            
            if not multioptic_mount:
                print("Debug: MultiOptic Mount required but not found")
                return False, "You need to install a MultiOptic Mount to have more than two Cybereyes."
            elif cybereye_count >= 7:
                print("Debug: Maximum number of Cybereyes (7) reached")
                return False, "You cannot install more than seven Cybereyes, even with a MultiOptic Mount."
    
    elif cyberware.name.lower() == "cyberarm":
        cyberarm_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cyberarm", installed=True).count()
        print(f"Debug: Current Cyberarm count: {cyberarm_count}")
        
        if cyberarm_count >= 4:
            print("Debug: Maximum number of Cyberarms (4) reached")
            return False, "You cannot install more than four Cyberarms, even with an Artificial Shoulder Mount."
        
        if cyberarm_count >= 2:
            artificial_shoulder_mount = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Artificial Shoulder Mount", installed=True).exists()
            print(f"Debug: Artificial Shoulder Mount exists: {artificial_shoulder_mount}")
            
            if not artificial_shoulder_mount:
                print("Debug: Artificial Shoulder Mount required but not found")
                return False, "You need to install an Artificial Shoulder Mount to have more than two Cyberarms."
    
    elif cyberware.name.lower() == "cyberaudio suite":
        cyberaudio_suite_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cyberaudio Suite", installed=True).count()
        print(f"Debug: Current Cyberaudio Suite count: {cyberaudio_suite_count}")
        
        if cyberaudio_suite_count >= 1:
            sensor_array = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Sensor Array", installed=True).exists()
            print(f"Debug: Sensor Array exists: {sensor_array}")
            
            if not sensor_array:
                print("Debug: Sensor Array required but not found")
                return False, "You need to install a Sensor Array to have more than one Cyberaudio Suite."
    
    elif cyberware.name.lower() == "cyberleg":
        cyberleg_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cyberleg", installed=True).count()
        print(f"Debug: Current Cyberleg count: {cyberleg_count}")
        if cyberleg_count >= 2:
            print("Debug: Maximum number of Cyberlegs (2) reached")
            return False, "You cannot install more than two Cyberlegs."
    
    # Check slot availability for cyberware options
    elif cyberware.type.lower() in ["cybereye", "cyberaudio", "cyberarm", "cyberleg"]:
        main_cyberware_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact=cyberware.type, installed=True).count()
        if main_cyberware_count == 0:
            print(f"Debug: No {cyberware.type} installed")
            return False, f"You need to install a {cyberware.type} before installing {cyberware.name}."
        
        total_slots, used_slots = count_available_slots(character, cyberware.type.lower())
        if used_slots + cyberware.slots > total_slots:
            print(f"Debug: Not enough slots available for {cyberware.name}")
            return False, f"Not enough slots available to install {cyberware.name}. Available slots: {total_slots - used_slots}, Required slots: {cyberware.slots}"

    # Check for cyberlimb options
    elif cyberware.type.lower() == "cyberlimb":
        cyberarm_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cyberarm", installed=True).count()
        cyberleg_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cyberleg", installed=True).count()
        
        # Special checks for Grip Foot and Jump Booster
        if cyberware.name.lower() in ["grip foot", "jump booster"]:
            if cyberleg_count < 2:
                print(f"Debug: Not enough Cyberlegs for {cyberware.name}")
                return False, f"You need to install two Cyberlegs before installing {cyberware.name}."
        else:
            if cyberarm_count == 0 and cyberleg_count == 0:
                print("Debug: No Cyberarm or Cyberleg installed")
                return False, "You need to install at least one Cyberarm or Cyberleg before installing cyberlimb options."

    print("Debug: All checks passed")
    return True, ""

def count_available_slots(character, slot_type):
    if slot_type == "cybereye":
        cybereye_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cybereye", installed=True).count()
        total_slots = cybereye_count * 3
    elif slot_type == "cyberaudio":
        cyberaudio_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cyberaudio Suite", installed=True).count()
        total_slots = cyberaudio_count * 3
    elif slot_type == "cyberarm":
        cyberarm_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cyberarm", installed=True).count()
        total_slots = cyberarm_count * 4
    elif slot_type == "cyberleg":
        cyberleg_count = CyberwareInstance.objects.filter(character=character, cyberware__name__iexact="Cyberleg", installed=True).count()
        total_slots = cyberleg_count * 3
    else:
        return 0, 0

    used_slots = CyberwareInstance.objects.filter(
        character=character,
        cyberware__type__iexact=slot_type,
        installed=True
    ).exclude(cyberware__name__in=["Cybereye", "Cyberaudio Suite", "Cyberarm", "Cyberleg"]).count()

    return total_slots, used_slots

class CyberwareMerchantCmdSet(CmdSet):
    key = "cyberware_merchant"

    def at_cmdset_creation(self):
        self.add(CyberwareMerchant())
        self.add(CmdImplantCyberware())
        self.add(CmdListCyberware())

    # Prevent installation of more than two Cybereyes or Cyberarms without Multioptic Mount or Artificial Shoulder Mount

class CmdImplantCyberware(Command):
    """
    Buy and install cyberware from the merchant.

    Usage:
      cyberimplant <cyberware_name>
    """

    key = "cyberimplant"
    aliases = ["implant_cyberware"]
    locks = "cmd:all()"
    help_category = "Cyberware"

    def __init__(self):
        super().__init__()
        self.type_slots = {
            "Fashionware": 7,
            "Neuralware": 5,
            "Cyberoptics": 3,
            "Cyberaudio": 3,
            "Internal Body Cyberware": 7,
            "External Body Cyberware": 7,
        }

    def func(self):
        self.caller.msg("Debug: CmdImplantCyberware executed")
        
        if not self.args:
            self.caller.msg("Debug: No arguments provided")
            self.caller.msg("Usage: cyberimplant <cyberware_name>")
            return

        cyberware_name = self.args.strip()
        self.caller.msg(f"Debug: Attempting to implant {cyberware_name}")
        
        try:
            cyberware = Cyberware.objects.get(name__iexact=cyberware_name)
            self.caller.msg(f"Debug: Found cyberware: {cyberware.name}")
        except Cyberware.DoesNotExist:
            self.caller.msg(f"Debug: Cyberware '{cyberware_name}' not found.")
            return
        
        try:
            character_sheet = self.caller.character_sheet
            self.caller.msg("Debug: Retrieved character sheet")
        except AttributeError:
            self.caller.msg("Debug: Error: No character sheet found for your character.")
            return

        self.caller.msg(f"Debug: Character's current money: {character_sheet.eurodollars}")
        self.caller.msg(f"Debug: Cyberware cost: {cyberware.cost}")

        if character_sheet.eurodollars < cyberware.cost:
            self.caller.msg(f"Debug: Not enough money to buy {cyberware.name}.")
            return

        # Call the check_cyberware_requirements function
        self.caller.msg("Debug: About to call check_cyberware_requirements")
        requirements_met, error_message = check_cyberware_requirements(character_sheet, cyberware)
        self.caller.msg(f"Debug: Result from check_cyberware_requirements: {requirements_met}, {error_message}")

        if not requirements_met:
            self.caller.msg(f"Debug: Requirements not met: {error_message}")
            self.caller.msg(error_message)
            return

        # Check available slots
        if cyberware.type in self.type_slots:
            installed_cyberware = character_sheet.inventory.cyberware.filter(installed=True, cyberware__type=cyberware.type)
            used_slots = sum(cw.cyberware.slots for cw in installed_cyberware)
            if used_slots + cyberware.slots > self.type_slots[cyberware.type]:
                self.caller.msg(f"Not enough slots available for {cyberware.type}.")
                return

        # If we've passed all checks, proceed with installation
        self.caller.msg("Debug: Creating CyberwareInstance")
        try:
            cyberware_instance = CyberwareInstance.objects.create(
                cyberware=cyberware,
                character=character_sheet,
                installed=True
            )
            self.caller.msg(f"Debug: CyberwareInstance created with ID: {cyberware_instance.id}")

            # Check if the cyberware is a cyberarm and update the has_cyberarm flag
            if cyberware.name.lower() == "cyberarm":
                character_sheet.has_cyberarm = True
                character_sheet.save()
                self.caller.msg("Your Cyberarm installation has been registered.")

        except Exception as e:
            self.caller.msg(f"Debug: Error creating CyberwareInstance: {str(e)}")
            return

        self.caller.msg("Debug: Updating character sheet")
        character_sheet.eurodollars -= cyberware.cost
        character_sheet.calculate_humanity_loss()
        character_sheet.save()

        self.caller.msg(f"Debug: Implant process completed for {cyberware.name}")
        self.caller.msg(f"You have purchased and installed {cyberware.name}.")
        self.caller.msg(f"Your new humanity is {character_sheet.humanity}.")

        if cyberware.is_weapon:
            self.caller.msg(f"Weapon stats: {cyberware.damage_dice}d{cyberware.damage_die_type} damage, {cyberware.rate_of_fire} ROF")

        # Display updated installed cyberware list
        self.caller.msg("Installed Cyberware:")
        try:
            installed_cyberware = CyberwareInstance.objects.filter(character=character_sheet, installed=True)
            self.caller.msg(f"Debug: Found {installed_cyberware.count()} installed cyberware items")
            
            for cw in installed_cyberware:
                self.caller.msg(f"- {cw.cyberware.name} ({cw.cyberware.type})")
                if cw.cyberware.is_weapon:
                    self.caller.msg(f"  Weapon stats: {cw.cyberware.damage_dice}d{cw.cyberware.damage_die_type} damage, {cw.cyberware.rate_of_fire} ROF")
        except Exception as e:
            self.caller.msg(f"Debug: Error retrieving installed cyberware: {str(e)}")

        # Display all cyberware in inventory (including not installed)
        self.caller.msg("\nAll Cyberware in Inventory:")
        try:
            all_cyberware = CyberwareInstance.objects.filter(character=character_sheet)
            self.caller.msg(f"Debug: Found {all_cyberware.count()} total cyberware items")
            
            for cw in all_cyberware:
                status = "Installed" if cw.installed else "Not Installed"
                self.caller.msg(f"- {cw.cyberware.name} ({cw.cyberware.type}) - {status}")
                if cw.cyberware.is_weapon:
                    self.caller.msg(f"  Weapon stats: {cw.cyberware.damage_dice}d{cw.cyberware.damage_die_type} damage, {cw.cyberware.rate_of_fire} ROF")
        except Exception as e:
            self.caller.msg(f"Debug: Error retrieving all cyberware: {str(e)}")

        character_sheet.recalculate_derived_stats()
        character_sheet.save()


class CyberwareMerchant(Command):
    """
    Interact with the cyberware merchant.

    Usage:
      ripperdoc
    """

    key = "ripperdoc"
    locks = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        self.caller.msg("|cThe ripperdoc grins, revealing a row of metallic teeth.|n")
        self.caller.msg("|cThe ripperdoc says, 'Welcome to the clinic, choomba! Ready to get chromed up?'|n")
        self.caller.msg("Available commands:")
        self.caller.msg("  |mcyberimplant <cyberware_name>|n - Purchase and install cyberware")
        self.caller.msg("  |mcyberlist|n - List available cyberware")

class CmdListCyberware(Command):
    """
    List available cyberware.

    Usage:
      list_cyberware
    """

    key = "cyberlist"
    locks = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        cyberware_list = Cyberware.objects.all().order_by('type', 'name')
        
        self.caller.msg("Available Cyberware:")
        current_type = ""
        for cw in cyberware_list:
            if cw.type != current_type:
                current_type = cw.type
                self.caller.msg(f"\n{current_type}:")
            self.caller.msg(f"  {cw.name} - Cost: {cw.cost}eb, Humanity Loss: {cw.humanity_loss}")
            if cw.is_weapon:
                self.caller.msg(f"Weapon stats: {cw.damage_dice}d{cw.damage_die_type} damage, {cw.rate_of_fire} ROF")