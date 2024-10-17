from evennia import Command, logger
from world.cyberware.models import Cyberware
from .cyberware_data import CYBERWARE_DATA_LIST

def populate_cyberware():
    for cw_data in CYBERWARE_DATA_LIST:
        defaults = {
            'type': cw_data['type'],
            'slots': cw_data['slots'],
            'humanity_loss': cw_data['humanity_loss'],
            'cost': cw_data['cost'],
            'is_weapon': cw_data.get('is_weapon', False),
            'description': cw_data['description']
        }
        
        # Only add weapon-specific fields if it's a weapon
        if defaults['is_weapon']:
            defaults['rate_of_fire'] = cw_data.get('rate_of_fire', 1)
            defaults['damage_dice'] = cw_data.get('damage_dice', 0)
            defaults['damage_die_type'] = cw_data.get('damage_die_type', 6)
        
        cyberware, created = Cyberware.objects.get_or_create(
            name=cw_data['name'],
            defaults=defaults
        )
        
        if not created:
            # Update existing cyberware
            for key, value in defaults.items():
                setattr(cyberware, key, value)
            cyberware.save()

    print(f"Populated {len(CYBERWARE_DATA_LIST)} cyberware items.")

def check_cyberware_requirements(character, cyberware):
    print("DEBUG: This is the modified check_cyberware_requirements function")
    
    try:
        cybereye_count = character.inventory.cyberware.filter(cyberware__name__iexact="Cybereye", installed=True).count()
        logger.msg(f"Debug: Current Cybereye count: {cybereye_count}")
    except Exception as e:
        logger.msg(f"Debug: Error counting Cybereyes: {str(e)}")
        return False, f"Error checking Cybereye count: {str(e)}"

    # Check for MultiOptic Mount requirement
    if cyberware.name.lower() == "cybereye":
        logger.msg(f"Debug: Checking Cybereye installation. Current count: {cybereye_count}")
        if cybereye_count >= 2:
            logger.msg("Debug: Checking for MultiOptic Mount")
            try:
                multioptic_mount = character.inventory.cyberware.filter(cyberware__name__iexact="MultiOptic Mount", installed=True).exists()
                logger.msg(f"Debug: MultiOptic Mount exists: {multioptic_mount}")
            except Exception as e:
                logger.msg(f"Debug: Error checking MultiOptic Mount: {str(e)}")
                return False, f"Error checking MultiOptic Mount: {str(e)}"
            
            if not multioptic_mount:
                logger.msg("Debug: MultiOptic Mount required but not found")
                return False, "You need to install a MultiOptic Mount to have more than two Cybereyes."
        else:
            logger.msg(f"Debug: Installing Cybereye {cybereye_count + 1}")

    # Check other requirements
    if cyberware.requirements:
        logger.msg(f"Debug: Checking requirements: {cyberware.requirements}")
        requirements = cyberware.requirements.split(',')
        for req in requirements:
            req = req.strip().lower()
            logger.msg(f"Debug: Checking requirement: {req}")
            if req == "cybereye":
                if cybereye_count < 2:
                    logger.msg("Debug: Not enough Cybereyes for requirement")
                    return False, f"You need to install two Cybereyes for {cyberware.name}. You currently have {cybereye_count}."

    if cyberware.name.lower() in ["image enhance", "low light-ir-uv", "virtuality"]:
        logger.msg(f"Debug: Checking special case for {cyberware.name}")
        if cybereye_count < 2:
            logger.msg("Debug: Not enough Cybereyes for special case")
            return False, f"You need to install two Cybereyes for {cyberware.name}. You currently have {cybereye_count}."

    logger.msg("Debug: All checks passed")
    return True, ""

def calculate_humanity_loss(sheet):
    from world.inventory.models import CyberwareInstance
    installed_cyberware = CyberwareInstance.objects.filter(character=sheet, installed=True)
    total_cyberware_hl = sum(cw.cyberware.humanity_loss for cw in installed_cyberware)
    
    print(f"Debug: Total Cyberware Humanity Loss: {total_cyberware_hl}")
    print(f"Debug: Character's current Empathy: {sheet.empathy}")
    
    # Calculate new humanity
    new_humanity = max(0, sheet.empathy * 10 - total_cyberware_hl)
    
    print(f"Debug: Calculated New Humanity: {new_humanity}")
    
    # Update humanity and empathy
    sheet.humanity = new_humanity
    sheet.empathy = max(1, new_humanity // 10)
    
    print(f"Debug: Updated Empathy: {sheet.empathy}")
    
    sheet.total_cyberware_humanity_loss = total_cyberware_hl
    sheet.save()

    return new_humanity