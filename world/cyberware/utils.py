from evennia import Command
from world.cyberware.models import Cyberware
from .cyberware_data import CYBERWARE_DATA_LIST

def get_all_cyberware():
    """
    Return all cyberware items in a format suitable for merchant inventory.
    Each item includes 'name' and 'value' (cost) for compatibility with
    merchant list_items and get_item methods.
    """
    return [
        {
            **cw_data,
            "value": cw_data["cost"],
        }
        for cw_data in CYBERWARE_DATA_LIST
    ]

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

        if defaults['is_weapon']:
            defaults['rate_of_fire'] = cw_data.get('rate_of_fire', 1)
            defaults['damage_dice'] = cw_data.get('damage_dice', 0)
            defaults['damage_die_type'] = cw_data.get('damage_die_type', 6)

        cyberware, created = Cyberware.objects.get_or_create(
            name=cw_data['name'],
            defaults=defaults
        )

        if not created:
            for key, value in defaults.items():
                setattr(cyberware, key, value)
            cyberware.save()


def check_cyberware_requirements(character, cyberware):
    try:
        cybereye_count = character.inventory.cyberware.filter(cyberware__name__iexact="Cybereye", installed=True).count()
    except Exception:
        return False, "Error checking cyberware requirements."

    if cyberware.name.lower() == "cybereye":
        if cybereye_count >= 2:
            try:
                multioptic_mount = character.inventory.cyberware.filter(cyberware__name__iexact="MultiOptic Mount", installed=True).exists()
            except Exception:
                return False, "Error checking MultiOptic Mount."

            if not multioptic_mount:
                return False, "You need to install a MultiOptic Mount to have more than two Cybereyes."

    if cyberware.requirements:
        requirements = cyberware.requirements.split(',')
        for req in requirements:
            req = req.strip().lower()
            if req == "cybereye":
                if cybereye_count < 2:
                    return False, f"You need to install two Cybereyes for {cyberware.name}. You currently have {cybereye_count}."

    if cyberware.name.lower() in ["image enhance", "low light-ir-uv", "virtuality"]:
        if cybereye_count < 2:
            return False, f"You need to install two Cybereyes for {cyberware.name}. You currently have {cybereye_count}."

    return True, ""


def calculate_humanity_loss(sheet):
    from world.inventory.models import CyberwareInstance
    installed_cyberware = CyberwareInstance.objects.filter(character=sheet, installed=True)
    total_cyberware_hl = sum(cw.cyberware.humanity_loss for cw in installed_cyberware)

    new_humanity = max(0, sheet.empathy * 10 - total_cyberware_hl)

    sheet.humanity = new_humanity
    sheet.empathy = max(1, new_humanity // 10)
    sheet.total_cyberware_humanity_loss = total_cyberware_hl
    sheet.save()

    return new_humanity
