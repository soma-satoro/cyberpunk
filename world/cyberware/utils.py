from evennia import Command, logger
from world.cyberware.models import Cyberware
from .cyberware_data import CYBERWARE_DATA_LIST

# Limb types that mount under borg ware (counted as "Cyberarm x3" etc.)
LIMB_TYPE_NAMES = frozenset({"cyberarm", "neo-soviet cyberarm", "cyberleg", "cybereye"})
# Borg ware that has child limbs or options (displayed as parent (child1, child2, ...))
BORG_WARE_NAMES = frozenset({"artificial shoulder mount", "multioptic mount", "sensor array", "cyberaudio suite", "discount cyberaudio suite"})


def format_cyberware_for_display(installed_instances, with_roots=False):
    """
    Build cyberware display from installed instances.

    If with_roots=False: returns compact list of strings for character sheet:
      "Cybereye (Paired, Anti-Dazzle, Color Shift)", "Light Tattoo", ...

    If with_roots=True: returns expanded table rows, list of (display_name, type, humanity_loss):
      ("Cyberaudio Suite", "Cyberaudio", 7),
      (" - Amplified Hearing", "Cyberaudio", 3),
      ("Cybereye", "Cyberoptics", 7),
      (" - Paired Cybereye", "Cyberoptics", 7),
      (" - Dartgun", "Cyberoptics", 3),
    Each piece on its own line; children indented with " - ".
    """
    if not installed_instances:
        return []
    installed = list(installed_instances)
    by_id = {i.id: i for i in installed}
    paired_second_ids = {i.id for i in installed if getattr(i, "paired_with_id", None)}
    roots = [i for i in installed if i.parent_id is None and i.id not in paired_second_ids]

    if not with_roots:
        # Compact format for character sheet
        result = []
        for root in roots:
            cw = root.cyberware
            name = (cw.name or "").strip()
            name_lower = name.lower()
            member_ids = {root.id}
            for inst in installed:
                if getattr(inst, "paired_with_id", None) == root.id:
                    member_ids.add(inst.id)
            to_process = list(member_ids)
            while to_process:
                pid = to_process.pop()
                for inst in installed:
                    if inst.parent_id == pid and inst.id not in member_ids:
                        member_ids.add(inst.id)
                        to_process.append(inst.id)
            members = [by_id[i] for i in member_ids if i in by_id]
            is_paired = any(getattr(m, "paired_with_id", None) for m in members)
            if name_lower in BORG_WARE_NAMES:
                limb_counts = {}
                options = []
                for m in members:
                    if m.id == root.id:
                        continue
                    cname = (m.cyberware.name or "").strip().lower()
                    if cname in LIMB_TYPE_NAMES:
                        limb_counts[m.cyberware.name] = limb_counts.get(m.cyberware.name, 0) + 1
                    else:
                        opt = m.cyberware.name
                        if getattr(m, "popup_weapon_name", None):
                            opt = f"{opt} ({m.popup_weapon_name})"
                        options.append(opt)
                parts = [f"{ln} x{c}" if c > 1 else ln for ln, c in sorted(limb_counts.items())]
                parts.extend(options)
            else:
                parts = ["Paired"] if is_paired else []
                for m in members:
                    if m.id == root.id:
                        continue
                    if m.parent_id in member_ids:
                        opt = m.cyberware.name
                        if getattr(m, "popup_weapon_name", None):
                            opt = f"{opt} ({m.popup_weapon_name})"
                        parts.append(opt)
            result.append(f"{name} ({', '.join(parts)})" if parts else name)
        return result

    # Expanded format: each piece on its own line with indentation
    result = []
    for root in roots:
        cw = root.cyberware
        name = (cw.name or "").strip()
        name_lower = name.lower()

        member_ids = {root.id}
        for inst in installed:
            if getattr(inst, "paired_with_id", None) == root.id:
                member_ids.add(inst.id)
        to_process = list(member_ids)
        while to_process:
            pid = to_process.pop()
            for inst in installed:
                if inst.parent_id == pid and inst.id not in member_ids:
                    member_ids.add(inst.id)
                    to_process.append(inst.id)

        members = [by_id[i] for i in member_ids if i in by_id]
        paired_second = next((m for m in members if getattr(m, "paired_with_id", None) == root.id), None)
        children = [m for m in members if m.id != root.id and m.id != (paired_second.id if paired_second else None)]

        # Root line
        result.append((name, cw.type, cw.humanity_loss))

        # Paired second (e.g. " - Paired Cybereye")
        if paired_second:
            pname = f"Paired {paired_second.cyberware.name}"
            result.append((f" - {pname}", paired_second.cyberware.type, paired_second.cyberware.humanity_loss))

        # Children: options, limbs under borg ware, etc.
        for m in children:
            opt_name = m.cyberware.name
            if getattr(m, "popup_weapon_name", None):
                opt_name = f"{opt_name} ({m.popup_weapon_name})"
            result.append((f" - {opt_name}", m.cyberware.type, m.cyberware.humanity_loss))

    return result

def populate_cyberware():
    existing_names = set(Cyberware.objects.values_list("name", flat=True))
    created = 0
    for cw_data in CYBERWARE_DATA_LIST:
        if cw_data["name"] in existing_names:
            continue
        defaults = {
            "type": cw_data["type"],
            "slots": cw_data["slots"],
            "humanity_loss": cw_data["humanity_loss"],
            "cost": cw_data["cost"],
            "is_weapon": cw_data.get("is_weapon", False),
            "description": cw_data["description"],
        }
        if defaults["is_weapon"]:
            defaults["rate_of_fire"] = cw_data.get("rate_of_fire", 1)
            defaults["damage_dice"] = cw_data.get("damage_dice", 0)
            defaults["damage_die_type"] = cw_data.get("damage_die_type", 6)
        Cyberware.objects.get_or_create(name=cw_data["name"], defaults=defaults)
        created += 1
        existing_names.add(cw_data["name"])
    print(f"Populated {len(CYBERWARE_DATA_LIST)} cyberware items ({created} new).")

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
    installed_cyberware = CyberwareInstance.objects.filter(character_sheet=sheet, installed=True)
    total_cyberware_hl = sum(cw.cyberware.humanity_loss for cw in installed_cyberware)
    trauma_hl = getattr(sheet, "trauma_humanity_loss", 0) or 0

    print(f"Debug: Total Cyberware Humanity Loss: {total_cyberware_hl}")
    print(f"Debug: Character's current Empathy: {sheet.empathy}")

    # Preserve staff-set humanity: use current humanity + old losses as base, then apply new losses
    old_total_hl = getattr(sheet, "total_cyberware_humanity_loss", 0) or 0
    humanity_base = sheet.humanity + old_total_hl + trauma_hl
    new_humanity = max(0, min(sheet.empathy * 10, humanity_base - total_cyberware_hl - trauma_hl))

    print(f"Debug: Calculated New Humanity: {new_humanity}")

    # Update humanity and empathy
    sheet.humanity = new_humanity
    sheet.empathy = max(1, new_humanity // 10)
    
    print(f"Debug: Updated Empathy: {sheet.empathy}")
    
    sheet.total_cyberware_humanity_loss = total_cyberware_hl
    sheet.save()

    return new_humanity