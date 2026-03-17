# world/cyberware/merchants.py

import inspect
from evennia import Command
from world.cyberware.models import CYBERWARE_HUMANITY_LOSS
from world.inventory.models import CyberwareInstance
from world.cyberpunk_sheets.models import CharacterSheet
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.commerce.pricing import get_purchase_discount_percent, calculate_final_price
from .models import Cyberware
from .cyberware_data import BODYCULPT_PACKAGES
from evennia import CmdSet

# Main cyberware that provide option slots. Include both standard and discount variants.
# Add new discount versions here when they are added to cyberware_data.
MAIN_CYBERWARE_NAMES = {
    "cybereye": ["Cybereye"],
    "cyberaudio": ["Cyberaudio Suite", "Discount Cyberaudio Suite"],
    "cyberarm": ["Cyberarm"],
    "cyberleg": ["Cyberleg"],
}
# Slots provided by each main piece (discount variants often have fewer)
MAIN_CYBERWARE_SLOTS = {
    "Cybereye": 3,
    "Cyberaudio Suite": 3,
    "Discount Cyberaudio Suite": 1,
    "Cyberarm": 4,
    "Cyberleg": 3,
}
# Names to exclude when counting "used" slots (main pieces provide slots; options use them)
MAIN_CYBERWARE_EXCLUDE = ["Cybereye", "Cyberaudio Suite", "Discount Cyberaudio Suite", "Cyberarm", "Cyberleg"]

def check_cyberware_requirements(character, cyberware):
    print(f"Debug: Entering check_cyberware_requirements for {cyberware.name}")
    
    # Specific checks for main cyberware
    if cyberware.name.lower() == "cybereye":
        cybereye_count = CyberwareInstance.objects.filter(character_sheet=character, cyberware__name__iexact="Cybereye", installed=True).count()
        print(f"Debug: Current Cybereye count: {cybereye_count}")
        
        if cybereye_count >= 2:
            multioptic_mount = CyberwareInstance.objects.filter(character_sheet=character, cyberware__name__iexact="MultiOptic Mount", installed=True).exists()
            print(f"Debug: MultiOptic Mount exists: {multioptic_mount}")
            
            if not multioptic_mount:
                print("Debug: MultiOptic Mount required but not found")
                return False, "You need to install a MultiOptic Mount to have more than two Cybereyes."
            elif cybereye_count >= 7:
                print("Debug: Maximum number of Cybereyes (7) reached")
                return False, "You cannot install more than seven Cybereyes, even with a MultiOptic Mount."
    
    elif cyberware.name.lower() == "cyberarm":
        cyberarm_count = CyberwareInstance.objects.filter(character_sheet=character, cyberware__name__iexact="Cyberarm", installed=True).count()
        print(f"Debug: Current Cyberarm count: {cyberarm_count}")
        
        if cyberarm_count >= 4:
            print("Debug: Maximum number of Cyberarms (4) reached")
            return False, "You cannot install more than four Cyberarms, even with an Artificial Shoulder Mount."
        
        if cyberarm_count >= 2:
            artificial_shoulder_mount = CyberwareInstance.objects.filter(character_sheet=character, cyberware__name__iexact="Artificial Shoulder Mount", installed=True).exists()
            print(f"Debug: Artificial Shoulder Mount exists: {artificial_shoulder_mount}")
            
            if not artificial_shoulder_mount:
                print("Debug: Artificial Shoulder Mount required but not found")
                return False, "You need to install an Artificial Shoulder Mount to have more than two Cyberarms."
    
    elif cyberware.name.lower() in [n.lower() for n in MAIN_CYBERWARE_NAMES["cyberaudio"]]:
        # Count both standard and discount - you can only have one total without Sensor Array
        cyberaudio_suite_count = CyberwareInstance.objects.filter(
            character_sheet=character,
            cyberware__name__in=MAIN_CYBERWARE_NAMES["cyberaudio"],
            installed=True
        ).count()
        print(f"Debug: Current Cyberaudio Suite count: {cyberaudio_suite_count}")
        
        if cyberaudio_suite_count >= 1:
            sensor_array = CyberwareInstance.objects.filter(character_sheet=character, cyberware__name__iexact="Sensor Array", installed=True).exists()
            print(f"Debug: Sensor Array exists: {sensor_array}")
            
            if not sensor_array:
                print("Debug: Sensor Array required but not found")
                return False, "You need to install a Sensor Array to have more than one Cyberaudio Suite."
    
    elif cyberware.name.lower() == "cyberleg":
        cyberleg_count = CyberwareInstance.objects.filter(character_sheet=character, cyberware__name__iexact="Cyberleg", installed=True).count()
        print(f"Debug: Current Cyberleg count: {cyberleg_count}")
        if cyberleg_count >= 2:
            print("Debug: Maximum number of Cyberlegs (2) reached")
            return False, "You cannot install more than two Cyberlegs."
    
    # Check slot availability for cyberware options
    elif cyberware.type.lower() in ["cybereye", "cyberaudio", "cyberarm", "cyberleg"]:
        names_to_check = MAIN_CYBERWARE_NAMES.get(cyberware.type.lower(), [cyberware.type])
        main_cyberware_count = CyberwareInstance.objects.filter(
            character_sheet=character, cyberware__name__in=names_to_check, installed=True
        ).count()
        if main_cyberware_count == 0:
            display_name = "Cyberaudio Suite" if cyberware.type.lower() == "cyberaudio" else cyberware.type
            print(f"Debug: No {display_name} installed")
            return False, f"You need to install a {display_name} before installing {cyberware.name}."
        
        total_slots, used_slots = count_available_slots(character, cyberware.type.lower())
        if used_slots + cyberware.slots > total_slots:
            print(f"Debug: Not enough slots available for {cyberware.name}")
            return False, f"Not enough slots available to install {cyberware.name}. Available slots: {total_slots - used_slots}, Required slots: {cyberware.slots}"

    # Check for cyberlimb options
    elif cyberware.type.lower() == "cyberlimb":
        cyberarm_count = CyberwareInstance.objects.filter(character_sheet=character, cyberware__name__iexact="Cyberarm", installed=True).count()
        cyberleg_count = CyberwareInstance.objects.filter(character_sheet=character, cyberware__name__iexact="Cyberleg", installed=True).count()
        
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
    """Sum slots from all installed main cyberware (standard and discount variants)."""
    if slot_type == "cybereye":
        main_names = MAIN_CYBERWARE_NAMES["cybereye"]
    elif slot_type == "cyberaudio":
        main_names = MAIN_CYBERWARE_NAMES["cyberaudio"]
    elif slot_type == "cyberarm":
        main_names = MAIN_CYBERWARE_NAMES["cyberarm"]
    elif slot_type == "cyberleg":
        main_names = MAIN_CYBERWARE_NAMES["cyberleg"]
    else:
        return 0, 0

    # Sum slots from each installed main piece (discount variants have fewer slots)
    total_slots = 0
    for cw_instance in CyberwareInstance.objects.filter(
        character_sheet=character,
        cyberware__name__in=main_names,
        installed=True
    ).select_related("cyberware"):
        total_slots += MAIN_CYBERWARE_SLOTS.get(cw_instance.cyberware.name, 0)

    used_slots = CyberwareInstance.objects.filter(
        character_sheet=character,
        cyberware__type__iexact=slot_type,
        installed=True
    ).exclude(cyberware__name__in=MAIN_CYBERWARE_EXCLUDE).count()

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
      cyberimplant <cyberware_name>      - Buy and install
      cyberimplant/stash <cyberware_name> - Buy without installing (for resale)

    Use /stash to purchase cyberware without installing it. Useful for Medtechs
    who plan to resell it to other players.
    """

    key = "cyberimplant"
    aliases = ["implant_cyberware"]
    switches = [("stash", "stash")]
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
        if not self.args:
            self.caller.msg("Usage: cyberimplant <cyberware_name> [or cyberimplant/stash for no install]")
            return

        stash = "stash" in self.switches
        cyberware_name = self.args.strip()
        try:
            cyberware = Cyberware.objects.get(name__iexact=cyberware_name)
        except Cyberware.DoesNotExist:
            self.caller.msg(f"Cyberware '{cyberware_name}' not found.")
            return

        # Bodysculpt packages: add all package cyberware (cannot stash)
        if getattr(cyberware, "type", "") == "Bodysculpt Package":
            if stash:
                self.caller.msg("Bodysculpt packages cannot be stashed; they are always installed.")
                return
            self._install_bodysculpt_package(cyberware)
            return

        try:
            character_sheet = self.caller.character_sheet
        except AttributeError:
            self.caller.msg("No character sheet found for your character.")
            return

        base_cost = cyberware.cost
        discount = get_purchase_discount_percent(self.caller, "cyberware", None)
        final_cost = calculate_final_price(base_cost, discount)

        if not CharacterMoneyService.spend_money(self.caller, final_cost):
            self.caller.msg(
                f"Not enough money to buy {cyberware.name}. "
                f"It costs {final_cost} eb."
            )
            return

        # Popup Melee/Ranged require weapon selection at install - must stash, then cyberware/install with weapon
        cw_lower = cyberware.name.lower()
        if not stash and cw_lower in ("popup melee weapon", "popup ranged weapon"):
            stash = True
            self.caller.msg(
                f"{cyberware.name} requires selecting a weapon when installing. "
                f"Use: cyberware/install \"{cyberware.name}\" = \"<weapon>\" (e.g. Light Melee Weapon, Heavy Pistol)"
            )

        if not stash:
            requirements_met, error_message = check_cyberware_requirements(character_sheet, cyberware)
            if not requirements_met:
                CharacterMoneyService.add_money(self.caller, final_cost)
                self.caller.msg(error_message)
                return

            # Check available slots
            if cyberware.type in self.type_slots:
                installed_cyberware = character_sheet.inventory.cyberware.filter(installed=True, cyberware__type=cyberware.type)
                used_slots = sum(cw.cyberware.slots for cw in installed_cyberware)
                if used_slots + cyberware.slots > self.type_slots[cyberware.type]:
                    CharacterMoneyService.add_money(self.caller, final_cost)
                    self.caller.msg(f"Not enough slots available for {cyberware.type}.")
                    return

        try:
            cyberware_instance = CyberwareInstance.objects.create(
                cyberware=cyberware,
                character_sheet=character_sheet,
                installed=not stash,
            )

            character_sheet.inventory.cyberware.add(cyberware_instance)
            # Check if the cyberware is a cyberarm and update the has_cyberarm flag (only when installing)
            if not stash and cyberware.name.lower() == "cyberarm":
                character_sheet.has_cyberarm = True
                character_sheet.save()
                self.caller.msg("Your Cyberarm installation has been registered.")

        except Exception as e:
            CharacterMoneyService.add_money(self.caller, final_cost)
            self.caller.msg(f"Error creating cyberware instance: {str(e)}")
            return

        character_sheet.refresh_from_db()
        if not stash:
            character_sheet.calculate_humanity_loss()
        character_sheet.save()

        if stash:
            if discount > 0:
                self.caller.msg(
                    f"You have purchased {cyberware.name} (not installed) for {final_cost} eb "
                    f"(base {base_cost} eb, {discount}% Medtech discount applied)."
                )
            else:
                self.caller.msg(f"You have purchased {cyberware.name} (not installed) for {final_cost} eb.")
        else:
            if discount > 0:
                self.caller.msg(
                    f"You have purchased and installed {cyberware.name} for {final_cost} eb "
                    f"(base {base_cost} eb, {discount}% Medtech discount applied)."
                )
            else:
                self.caller.msg(f"You have purchased and installed {cyberware.name} for {final_cost} eb.")
            self.caller.msg(f"Your new humanity is {character_sheet.humanity}.")

        if cyberware.is_weapon:
            self.caller.msg(f"Weapon stats: {cyberware.damage_dice}d{cyberware.damage_die_type} damage, {cyberware.rate_of_fire} ROF")

        # Display updated installed cyberware list
        self.caller.msg("Installed Cyberware:")
        try:
            for cw in CyberwareInstance.objects.filter(character_sheet=character_sheet, installed=True):
                self.caller.msg(f"- {cw.cyberware.name} ({cw.cyberware.type})")
                if cw.cyberware.is_weapon:
                    self.caller.msg(f"  Weapon: {cw.cyberware.damage_dice}d{cw.cyberware.damage_die_type} damage, {cw.cyberware.rate_of_fire} ROF")
        except Exception as e:
            self.caller.msg(f"Error retrieving cyberware: {str(e)}")

    def _install_bodysculpt_package(self, package_cyberware):
        """Install a bodysculpt package; add all contained cyberware to character."""
        pkg_data = BODYCULPT_PACKAGES.get(package_cyberware.name)
        if not pkg_data:
            self.caller.msg(f"Unknown bodysculpt package: {package_cyberware.name}.")
            return
        try:
            character_sheet = self.caller.character_sheet
        except AttributeError:
            self.caller.msg("No character sheet found for your character.")
            return
        base_cost = pkg_data["cost"]
        discount = get_purchase_discount_percent(self.caller, "cyberware", None)
        final_cost = calculate_final_price(base_cost, discount)
        if not CharacterMoneyService.spend_money(self.caller, final_cost):
            self.caller.msg(
                f"Not enough money for {package_cyberware.name}. It costs {final_cost} eb."
            )
            return
        inventory = character_sheet.inventory
        added = []
        missing = []
        for cw_name in pkg_data["package_contains"]:
            try:
                cw = Cyberware.objects.get(name__iexact=cw_name)
            except Cyberware.DoesNotExist:
                missing.append(cw_name)
                continue
            instance = CyberwareInstance.objects.create(
                cyberware=cw,
                character_sheet=character_sheet,
                installed=True,
            )
            inventory.cyberware.add(instance)
            added.append(cw_name)
            if cw.name.lower() == "cyberarm":
                character_sheet.has_cyberarm = True
                character_sheet.save()
        if missing:
            self.caller.msg(
                f"Warning: some package items not found: {', '.join(missing)}. "
                f"Added {len(added)} items."
            )
        character_sheet.refresh_from_db()
        character_sheet.calculate_humanity_loss()
        character_sheet.save()
        if discount > 0:
            self.caller.msg(
                f"You have purchased and installed {package_cyberware.name} for {final_cost} eb "
                f"(base {base_cost} eb, {discount}% discount). Package: {len(added)} cyberware items."
            )
        else:
            self.caller.msg(
                f"You have purchased and installed {package_cyberware.name} for {final_cost} eb. "
                f"Package: {len(added)} cyberware items."
            )
        self.caller.msg(f"Your new humanity is {character_sheet.humanity}.")

        # Display updated installed cyberware list
        self.caller.msg("Installed Cyberware:")
        try:
            for cw in CyberwareInstance.objects.filter(character_sheet=character_sheet, installed=True):
                self.caller.msg(f"- {cw.cyberware.name} ({cw.cyberware.type})")
                if cw.cyberware.is_weapon:
                    self.caller.msg(f"  Weapon: {cw.cyberware.damage_dice}d{cw.cyberware.damage_die_type} damage, {cw.cyberware.rate_of_fire} ROF")
        except Exception as e:
            self.caller.msg(f"Error retrieving cyberware: {str(e)}")


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