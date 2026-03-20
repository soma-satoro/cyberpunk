"""
Attack and Dodge commands for Cyberpunk Red combat.

Attack: Rolls attack (stat + skill vs DV) and damage. DV can be specified directly
or taken from a target's dodge roll.

Dodge: Rolls 1d10 + Dexterity + Evasion; result becomes the DV for attacks against you.
"""

import random
import time
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.utils import inherits_from
from world.utils.character_utils import is_character_approved, is_staff
from world.utils.difficulty_values import parse_dv
from world.equipment_data import get_weapon_damage_dice, get_weapon_by_name
from world.combat_rules import (
    get_dv_for_range,
    POINT_BLANK_RANGE,
    ARMOR_LOCATIONS,
    is_splash_weapon,
    is_shotgun_zone_weapon,
)
from world.wound_utils import (
    get_current_hp,
    get_max_hp,
    get_wound_state,
    get_action_penalty,
    get_armor_sp,
    get_cover_sp,
    apply_damage_to_character,
    apply_critical_injury_to_character,
    is_dead,
)
from world.wound_data import WOUND_MORTALLY, WOUND_DEAD
from world.utils.modifier_parser import parse_modifier_string
from typeclasses.npcs import is_npc

# Dodge result expires after 5 minutes
DODGE_EXPIRY_SECONDS = 300


# Weapon category -> (stat_field, skill_field, skill_display_name)
WEAPON_SKILL_MAP = {
    "melee": ("dexterity", "melee", "Melee"),
    "handgun": ("reflexes", "handgun", "Handgun"),
    "smg": ("reflexes", "handgun", "Handgun"),
    "shoulder_arms": ("reflexes", "shoulder_arms", "Shoulder Arms"),
    "heavy_weapons": ("reflexes", "heavy_weapons", "Heavy Weapons"),
    "archery": ("reflexes", "archery", "Archery"),
}


def _get_sheet(char):
    """Get CharacterSheet for character."""
    if not char:
        return None
    return getattr(char, "character_sheet", None)


def _get_equipped_weapon(char):
    """Get equipped weapon from character sheet, or None."""
    sheet = _get_sheet(char)
    if not sheet:
        return None
    return getattr(sheet, "eqweapon", None)


def _has_cyberarm_installed(char):
    """True if character has an actual Cyberarm limb (solo or paired) installed, not just options like Wolvers."""
    from django.db.models import Q
    from world.inventory.models import CyberwareInstance

    limb_filter = Q(cyberware__name__iexact="Cyberarm") | Q(cyberware__name__iexact="Neo-Soviet Cyberarm")
    sheet = _get_sheet(char)
    if sheet and getattr(sheet, "pk", None):
        if CyberwareInstance.objects.filter(
            character_sheet_id=sheet.pk, installed=True
        ).filter(limb_filter).exists():
            return True
    if hasattr(char, "pk") and char.pk:
        if CyberwareInstance.objects.filter(
            character_object_id=char.pk, installed=True
        ).filter(limb_filter).exists():
            return True
    return False


def _get_active_cyberware_weapon(char):
    """
    Get active cyberware weapon instance if any.
    Returns (CyberwareInstance, weapon_display_name, stat_field, skill_field, skill_display_name, num_damage_dice).
    """
    from world.inventory.models import CyberwareInstance

    sheet = _get_sheet(char)
    if not sheet:
        return None

    sheet_pk = getattr(sheet, "pk", None)
    if not sheet_pk:
        return None

    # Try character_sheet first, then character_object (Inventory may use either)
    active_inst = CyberwareInstance.objects.filter(
        character_sheet_id=sheet_pk, installed=True, active=True
    ).select_related("cyberware").first()

    if not active_inst and hasattr(char, "pk") and char.pk:
        active_inst = CyberwareInstance.objects.filter(
            character_object_id=char.pk, installed=True, active=True
        ).select_related("cyberware").first()

    if not active_inst:
        return None

    cw = active_inst.cyberware
    cw_name_lower = (cw.name or "").strip().lower()

    if cw_name_lower == "popup melee weapon":
        popup_name = (getattr(active_inst, "popup_weapon_name", None) or "").strip()
        if not popup_name:
            return None
        display = f"{cw.name} ({popup_name})"
        dice = get_weapon_damage_dice(popup_name)
        return (active_inst, display, "dexterity", "melee", "Melee", dice)
    elif cw_name_lower == "popup ranged weapon":
        popup_name = (getattr(active_inst, "popup_weapon_name", None) or "").strip()
        if not popup_name:
            return None
        display = f"{cw.name} ({popup_name})"
        dice = get_weapon_damage_dice(popup_name)
        return (active_inst, display, "reflexes", "handgun", "Handgun", dice)
    elif cw_name_lower == "popup grenade launcher":
        display = cw.name
        dice = get_weapon_damage_dice("Grenade Launcher")  # 6d6 per CPR
        return (active_inst, display, "reflexes", "heavy_weapons", "Heavy Weapons", dice)
    elif cw.is_weapon and cw.damage_dice:
        display = cw.name
        return (active_inst, display, "dexterity", "melee", "Melee", cw.damage_dice)
    return None


def _parse_damage_dice(damage_str):
    """Parse '2d6' or '4d6' format, return number of dice."""
    if not damage_str:
        return 0
    try:
        parts = str(damage_str).lower().split("d")
        return int(parts[0]) if parts else 0
    except (ValueError, IndexError):
        return 0


def _combat_weapon_name(weapon):
    """Range DV / splash detection: append weapon_type + generic so flavored names still match rules."""
    if not weapon:
        return ""
    from world.edgerunner_weapon_flavor import augmented_weapon_label_for_combat_rules

    return augmented_weapon_label_for_combat_rules(weapon)


def _weapon_supports_autofire(weapon):
    """SMG / Heavy SMG / Assault Rifle — uses weapon_type and generic template, not display name."""
    if not weapon:
        return False
    rw = _combat_weapon_name(weapon).lower()
    wt = (getattr(weapon, "weapon_type", None) or "").strip().lower()
    cat = (weapon.category or "").strip().lower()
    if "assault rifle" in rw or wt == "assault rifle":
        return True
    if "smg" in rw or "heavy smg" in rw or wt in ("smg", "heavy smg") or cat == "smg":
        return True
    return False


def _autofire_multiplier_for_weapon(weapon):
    """CPR: AR x4 max, SMG x3 max."""
    rw = _combat_weapon_name(weapon).lower()
    wt = (getattr(weapon, "weapon_type", None) or "").strip().lower()
    if "assault rifle" in rw or wt == "assault rifle":
        return 4
    return 3


def _get_weapon_quality_bonus(weapon):
    """Attack bonus from weapon quality: Excellent +1, Standard 0, Poor 0 (but can jam on 1)."""
    if not weapon:
        return 0
    from world.edgerunner_weapon_flavor import effective_weapon_quality_tier

    q = effective_weapon_quality_tier(weapon)
    return 1 if q == "excellent" else 0


def _is_weapon_poor_quality(weapon):
    """True if weapon is poor quality (can jam on natural 1)."""
    if not weapon:
        return False
    from world.edgerunner_weapon_flavor import effective_weapon_quality_tier

    return effective_weapon_quality_tier(weapon) == "poor"


def _is_weapon_jammed(weapon):
    """True if poor quality weapon is currently jammed."""
    return weapon and _is_weapon_poor_quality(weapon) and getattr(weapon, "jammed", False)


def _equipped_weapon_matches_name(caller, char, weapon, input_name: str) -> bool:
    """True if input matches equipped weapon by exact name, generic category, or flavor chart alias."""
    if not weapon or not (input_name or "").strip():
        return False
    if (weapon.name or "").strip().lower() == input_name.strip().lower():
        return True
    sheet = _get_sheet(char)
    inv = getattr(sheet, "inventory", None) if sheet else None
    if not inv:
        return False
    from commands.inventory_commands import _find_weapon_for_equip

    found = _find_weapon_for_equip(caller, inv, input_name.strip())
    return found is not None and found.pk == weapon.pk


def _get_cyberware_weapon_quality_bonus(cw_attack):
    """+1 for excellent quality cyberware weapons (Vampyres, Mantis Blade, Gorilla Arm, excellent popup)."""
    if not cw_attack:
        return 0
    inst, display_name, _, _, _, _ = cw_attack
    cw = inst.cyberware
    name_lower = (cw.name or "").strip().lower()
    if name_lower in ("vampyres", "mantis blade", "gorilla arm"):
        return 1
    if name_lower in ("popup melee weapon", "popup ranged weapon"):
        popup = (getattr(inst, "popup_weapon_name", None) or "").strip().lower()
        if popup and "excellent" in popup:
            return 1
        # Check equipment_data for popup weapon quality
        from world.equipment_data import get_weapon_by_name
        w_data = get_weapon_by_name(getattr(inst, "popup_weapon_name", None) or "")
        if w_data and (w_data.get("quality") or "").strip().lower() == "excellent":
            return 1
    return 0


def _get_weapon_attack_info(weapon):
    """Get (stat, skill, skill_display, num_dice) for a Weapon model."""
    from world.edgerunner_weapon_flavor import resolve_weapon_equipment_template

    cat = (weapon.category or "").strip().lower()
    mapping = WEAPON_SKILL_MAP.get(cat)
    if not mapping:
        mapping = WEAPON_SKILL_MAP.get("handgun")  # fallback
    stat_field, skill_field, skill_display = mapping
    tpl = resolve_weapon_equipment_template(weapon)
    num_dice = _parse_damage_dice(getattr(weapon, "damage", None))
    if not num_dice and tpl:
        num_dice = _parse_damage_dice(tpl.get("damage"))
    if not num_dice and tpl:
        num_dice = get_weapon_damage_dice(tpl.get("name") or "")
    if not num_dice:
        num_dice = get_weapon_damage_dice(weapon.name)
    return stat_field, skill_field, skill_display, num_dice


def _get_unarmed_attack_info(sheet):
    """Get (stat, skill, skill_display, num_dice) for unarmed. Favors Martial Arts over Brawling."""
    martial = getattr(sheet, "martial_arts", 0) or 0
    brawling = getattr(sheet, "brawling", 0) or 0
    if martial > 0:
        skill = martial
        skill_display = "Martial Arts"
    else:
        skill = brawling
        skill_display = "Brawling"
    num_dice = getattr(sheet, "unarmed_damage_dice", 1) or 1
    return "dexterity", skill, skill_display, num_dice


def _get_stat(sheet, stat_field):
    """Get stat value from sheet."""
    return getattr(sheet, stat_field, 0) or 0


def _get_skill(sheet, skill_field):
    """Get skill value from sheet."""
    return getattr(sheet, skill_field, 0) or 0


def _get_dex_and_evasion(target):
    """Get (dexterity, evasion) for a character or NPC."""
    sheet = _get_sheet(target)
    if sheet:
        dex = _get_stat(sheet, "dexterity")
        evasion = _get_skill(sheet, "evasion")
        return dex, evasion
    # NPC or character using db
    dex = getattr(target.db, "dexterity", 0) or 0
    skills = target.db.skills or {}
    evasion = skills.get("evasion", 0) or 0
    return dex, evasion


def _get_armor_ev_penalty(target):
    """Get EV penalty from worn armor (0 if none)."""
    sheet = _get_sheet(target)
    if sheet and getattr(sheet, "eqarmor", None):
        return getattr(sheet.eqarmor, "ev", 0) or 0
    # NPC with db.eqarmor (armor object or id)
    eqarmor = getattr(target.db, "eqarmor", None)
    if eqarmor and hasattr(eqarmor, "ev"):
        return eqarmor.ev or 0
    return 0


def _get_dodge_dv(target, modifier=0):
    """Roll dodge for target, return (d10, dex, evasion, total). Applies EV penalty from worn armor + modifier + wound penalty."""
    dex, evasion = _get_dex_and_evasion(target)
    d10 = random.randint(1, 10)
    ev_penalty = _get_armor_ev_penalty(target)
    action_penalty = get_action_penalty(target)
    total = d10 + dex + evasion - ev_penalty + modifier + action_penalty
    total = max(0, total)  # Dodge DV cannot go below 0
    return d10, dex, evasion, total


def _get_last_dodge_dv(target):
    """Get target's last dodge DV if valid (not expired). Returns (dv, timestamp) or (None, None)."""
    dv = getattr(target.db, "last_dodge_dv", None)
    ts = getattr(target.db, "last_dodge_timestamp", 0) or 0
    if dv is None:
        return None, None
    if time.time() - ts > DODGE_EXPIRY_SECONDS:
        return None, None
    return dv, ts


def _set_last_dodge_dv(target, dv):
    """Store dodge DV on target."""
    target.db.last_dodge_dv = dv
    target.db.last_dodge_timestamp = time.time()


def _clear_last_dodge_dv(target):
    """Clear stored dodge DV after use."""
    if hasattr(target.db, "last_dodge_dv"):
        del target.db.last_dodge_dv
    if hasattr(target.db, "last_dodge_timestamp"):
        del target.db.last_dodge_timestamp


def _can_roll_dodge_for(caller, target):
    """True if caller can roll dodge for target (self, owned NPC, or staff)."""
    if target == caller:
        return True
    if hasattr(caller, "check_permstring") and (caller.check_permstring("builders") or caller.check_permstring("wizards")):
        return True
    if is_npc(target):
        acc = getattr(caller, "account", None)
        if acc and getattr(target.db, "owner_account_id", None) == acc.id:
            return True
    return False


def _add_pending_attack(target, attacker, staff_override=None, modifier=0, luck_spend=0, aim_location=None, force_melee=False):
    """Add attacker to target's pending attacks list (target must dodge first).
    staff_override: optional dict with staff_stat, staff_skill, etc. for staff attacks.
    modifier, luck_spend, aim_location, force_melee: stored for execute_attack_roll when target dodges."""
    pending = list(getattr(target.db, "pending_attacks", []) or [])
    if attacker.id not in pending:
        pending.append(attacker.id)
    target.db.pending_attacks = pending
    overrides = dict(getattr(target.db, "pending_attack_overrides", {}) or {})
    data = dict(staff_override or {})
    data["modifier"] = modifier
    data["luck_spend"] = luck_spend
    if aim_location is not None:
        data["aim_location"] = aim_location
    if force_melee:
        data["force_melee"] = True
    overrides[attacker.id] = data
    target.db.pending_attack_overrides = overrides


def _resolve_pending_autofire(target, dodge_total):
    """If target has pending_autofire or pending_zone, resolve it. Returns True if resolved."""
    pending_af = getattr(target.db, "pending_autofire", None)
    if not pending_af:
        return False
    target.db.pending_autofire = None
    attack_roll = pending_af.get("attack_roll")
    if attack_roll is None:
        return True
    loc = target.location
    if not loc:
        return True
    zone_type = pending_af.get("zone_type", "autofire")
    zone_label = pending_af.get("zone_label", "autofire")

    if dodge_total > attack_roll:
        loc.msg_contents(
            f"|w{target.key}|n dodges! Roll {dodge_total} beats {zone_label} {attack_roll} - |gEVADED!|n"
        )
    else:
        if zone_type == "autofire":
            from world.inventory.models import Weapon
            try:
                weapon = Weapon.objects.get(pk=pending_af.get("weapon_id"))
            except (Weapon.DoesNotExist, TypeError):
                weapon = None
            dv = pending_af.get("dv", 17)
            beat = max(0, attack_roll - dv)
            mult = _autofire_multiplier_for_weapon(weapon) if weapon else 3
            mult = min(beat, mult)
            d1, d2 = random.randint(1, 6), random.randint(1, 6)
            dmg = (d1 + d2) * mult
            loc.msg_contents(
                f"|w{target.key}|n dodges! Roll {dodge_total} fails to beat {attack_roll} - |rHIT!|n "
                f"2d6 [{d1},{d2}] x {mult} = |r{dmg}|n"
            )
        else:
            # splash or shotgun: fixed dice
            num_dice = pending_af.get("num_dice", 3)
            rolls = [random.randint(1, 6) for _ in range(num_dice)]
            dmg = sum(rolls)
            rolls_str = ", ".join(str(r) for r in rolls)
            loc.msg_contents(
                f"|w{target.key}|n dodges! Roll {dodge_total} fails to beat {attack_roll} - |rHIT!|n "
                f"{num_dice}d6 [{rolls_str}] = |r{dmg}|n"
            )
    return True


def _clear_pending_attacks_on_leave(character, room_left):
    """When character leaves a room, clear their pending attacks (as target) and remove them
    from everyone else's pending attacks (as attacker). Prevents stale dodge prompts."""
    if not character or not hasattr(character, "db"):
        return
    # Clear this character's pending attacks (they were the target)
    character.db.pending_attacks = []
    character.db.pending_attack_overrides = {}
    # Remove this character from others' pending attacks (they were the attacker)
    if not room_left:
        return
    for obj in room_left.contents:
        if obj == character or not hasattr(obj, "db"):
            continue
        pending = list(getattr(obj.db, "pending_attacks", []) or [])
        if character.id in pending:
            pending.remove(character.id)
            obj.db.pending_attacks = pending
            overrides = dict(getattr(obj.db, "pending_attack_overrides", {}) or {})
            if character.id in overrides:
                del overrides[character.id]
                obj.db.pending_attack_overrides = overrides


def _get_pending_attacks_in_room(room):
    """Get all pending attacks in room as list of (attacker, target) pairs.
    Used for attack/pending display."""
    if not room:
        return []
    from evennia.utils.search import search_object
    result = []
    for obj in room.contents:
        if not hasattr(obj, "db"):
            continue
        pending_ids = list(getattr(obj.db, "pending_attacks", []) or [])
        for aid in pending_ids:
            found = search_object(f"#{aid}")
            if found and found[0].location == room:
                result.append((found[0], obj))
    return result


def _cancel_attacker_from_target(target, attacker):
    """Remove attacker from target's pending attacks. Returns True if removed."""
    pending = list(getattr(target.db, "pending_attacks", []) or [])
    if attacker.id not in pending:
        return False
    pending.remove(attacker.id)
    target.db.pending_attacks = pending
    overrides = dict(getattr(target.db, "pending_attack_overrides", {}) or {})
    if attacker.id in overrides:
        del overrides[attacker.id]
        target.db.pending_attack_overrides = overrides
    return True


def _clear_all_pending_attacks_in_room(room):
    """Staff: clear all pending attacks for everyone in the room."""
    if not room:
        return 0
    count = 0
    for obj in room.contents:
        if hasattr(obj, "db"):
            pending = getattr(obj.db, "pending_attacks", []) or []
            if pending:
                obj.db.pending_attacks = []
                obj.db.pending_attack_overrides = {}
                count += 1
    return count


def _get_and_clear_pending_attacks(target):
    """Get list of (attacker, staff_override) for pending attacks on target, and clear.
    staff_override is None or a dict for execute_attack_roll kwargs."""
    pending_ids = list(getattr(target.db, "pending_attacks", []) or [])
    overrides = dict(getattr(target.db, "pending_attack_overrides", {}) or {})
    if not pending_ids:
        return []
    target.db.pending_attacks = []
    target.db.pending_attack_overrides = {}
    from evennia.utils.search import search_object
    result = []
    for aid in pending_ids:
        found = search_object(f"#{aid}")
        if found and found[0].location and target.location and found[0].location == target.location:
            staff_override = overrides.get(aid)
            result.append((found[0], staff_override))
    return result


def _get_reflexes(target):
    """Get REF stat for target (PC or NPC)."""
    sheet = _get_sheet(target)
    if sheet:
        return _get_stat(sheet, "reflexes")
    return getattr(target.db, "reflexes", 0) or 0


def _apply_attack_damage(target, total_damage, aim_location, location, msg_lines):
    """
    Apply attack damage to target: armor SP, cover, then HP.
    Armor that stops damage loses 1 SP (ablation). Critical injuries deal 5 bonus damage (no armor ablation).
    If mortally wounded (already at 0 HP), apply critical injury. Death save penalty = base from injuries only.
    """
    from world.wound_utils import (
        get_armor_sp,
        get_cover_sp,
        apply_damage_to_character,
        apply_critical_injury_to_character,
        get_wound_state,
        get_current_hp,
    )
    from world.wound_data import WOUND_MORTALLY

    # Aimed shot to head: damage that gets through SP is multiplied by 2
    head_mult = 2 if aim_location == "head" else 1

    armor_sp = get_armor_sp(target, aim_location)
    damage_after_armor = max(0, total_damage - armor_sp) * head_mult

    # Armor ablation (CPR): every SP source that covers this location loses SP together
    if armor_sp > 0 and total_damage > 0:
        absorbed = min(armor_sp, total_damage)
        try:
            from world.cyberware.implanted_armor import (
                ablate_all_armor_for_location,
                get_total_armor_sp_for_location,
            )

            ablate_all_armor_for_location(target, aim_location, 1)
            new_total = get_total_armor_sp_for_location(target, aim_location)
            msg_lines.append(
                f"  |w{target.key}|n's armor absorbs |c{absorbed}|n damage "
                f"(location SP {armor_sp} -> {new_total})."
            )
        except Exception:
            msg_lines.append(f"  |w{target.key}|n's armor absorbs |c{absorbed}|n damage.")

    # Cover absorbs damage first
    cover_hp, cover_current = get_cover_sp(target)
    damage_to_char = damage_after_armor
    if cover_current > 0 and cover_hp > 0:
        cover_damage = min(damage_after_armor, cover_current)
        new_cover_hp = max(0, cover_current - cover_damage)
        target.db.cover = target.db.cover or {}
        target.db.cover["cover_current_hp"] = new_cover_hp
        damage_to_char = max(0, damage_after_armor - cover_damage)
        if cover_damage > 0:
            msg_lines.append(f"  Cover absorbs |r{cover_damage}|n damage ({new_cover_hp}/{cover_hp} HP remaining).")
        if new_cover_hp <= 0:
            msg_lines.append(f"  |rCover destroyed!|n")

    old_hp = get_current_hp(target)
    if damage_to_char > 0:
        apply_damage_to_character(target, damage_to_char)
        msg_lines.append(f"  |w{target.key}|n takes |r{damage_to_char}|n damage. HP: {old_hp} -> {get_current_hp(target)}")

    # Mortally wounded (was already at 0 or less): apply critical injury and +1 to death_save_penalty
    was_mortally = old_hp < 1
    if was_mortally:
        sheet = _get_sheet(target)
        if sheet:
            # Roll critical injury (head if aimed at head, else body)
            table = "head" if aim_location == "head" else "body"
            injury_name, _ = apply_critical_injury_to_character(target, table, aim_location)
            if injury_name:
                msg_lines.append(f"  |rCRITICAL INJURY: {injury_name}!|n (+5 bonus damage)")
            # +1 death_save_penalty for being hit at 0 HP
            from world.wound_utils import increase_death_save_penalty
            increase_death_save_penalty(target)

    # Check for death save prompt (HP <= 0, not dead yet); sync death_save_penalty = base (injuries only)
    if get_current_hp(target) <= 0 and not getattr(target.db, "dead", False):
        sheet = _get_sheet(target)
        if sheet:
            base = getattr(sheet, "base_death_save_penalty", 0) or 0
            sheet.death_save_penalty = base
            sheet.save(skip_recalculation=True)
            if hasattr(target, "db"):
                target.db.death_save_penalty = base
        msg_lines.append(f"  |r{target.key} is mortally wounded!|n Death Save required at start of next turn.")


def execute_attack_roll(attacker, target, dv, dv_name, location, aim_location=None, force_melee=False,
                       staff_stat=None, staff_skill=None, staff_skill_display=None, staff_weapon_name=None, staff_num_dice=None, staff_stat_field=None,
                       luck_spend=0, modifier=0):
    """
    Execute the attack roll and damage. Broadcasts to location.
    Caller must ensure attacker has character_sheet and target is valid.
    Staff override: pass staff_stat, staff_skill, etc.
    luck_spend: luck points to spend (+1 per point).
    modifier: additional modifier to attack roll (can be positive or negative).
    """
    sheet = _get_sheet(attacker)
    if not sheet and not (staff_stat is not None and staff_skill is not None):
        return

    weapon = _get_equipped_weapon(attacker)
    cw_attack = _get_active_cyberware_weapon(attacker)

    # Check jammed (poor quality weapon)
    if weapon and _is_weapon_jammed(weapon):
        if location:
            location.msg_contents(f"|w{attacker.key}|n's {weapon.name} is |rjammed|n! Use |wattack/unjam {weapon.name}|n to clear it.")
        return

    if staff_stat is not None and staff_skill is not None:
        stat_val = staff_stat
        skill_val = staff_skill
        skill_display = staff_skill_display or "Skill"
        weapon_name = staff_weapon_name or "weapon"
        num_dice = staff_num_dice or 2
        attack_type = "staff"
        stat_field = staff_stat_field or "reflexes"
    elif force_melee:
        _, unarmed_skill, unarmed_display, unarmed_dice = _get_unarmed_attack_info(sheet)
        stat_field, skill_field, skill_display = "dexterity", "melee", "Melee"
        skill_val = _get_skill(sheet, "melee")
        num_dice = max(2, unarmed_dice)  # Medium melee 2d6 or unarmed, whichever greater
        has_cyberarm = _has_cyberarm_installed(attacker)
        weapon_name = f"melee (Melee)" + (" |y(cyberarm)|n" if has_cyberarm else "")
        attack_type = "melee"
    elif weapon:
        stat_field, skill_field, skill_display, num_dice = _get_weapon_attack_info(weapon)
        weapon_name = f"{weapon.name} ({skill_display})"
        attack_type = "weapon"
    elif cw_attack:
        _, base_name, stat_field, skill_field, skill_display, num_dice = cw_attack
        weapon_name = f"{base_name} |y(cyberware)|n"
        attack_type = "cyberware"
    else:
        stat_field, skill_val, skill_display, num_dice = _get_unarmed_attack_info(sheet)
        skill_field = None
        has_cyberarm = _has_cyberarm_installed(attacker)
        weapon_name = "cyberarm brawling" if has_cyberarm else "unarmed strike"
        attack_type = "unarmed"

    if attack_type == "staff":
        pass  # stat_val, skill_val already set
    elif attack_type == "unarmed":
        stat_val = _get_stat(sheet, stat_field)
        skill_val = skill_val  # from _get_unarmed_attack_info
    else:
        stat_val = _get_stat(sheet, stat_field)
        skill_val = _get_skill(sheet, skill_field)

    d10 = random.randint(1, 10)

    # Quality bonus (Excellent +1)
    quality_bonus = 0
    if weapon:
        quality_bonus = _get_weapon_quality_bonus(weapon)
    elif cw_attack:
        quality_bonus = _get_cyberware_weapon_quality_bonus(cw_attack)

    # Luck (spend before roll - caller must have deducted)
    actual_luck = 0
    if luck_spend > 0:
        current = getattr(attacker.db, "current_luck", 0) or 0
        actual_luck = min(luck_spend, max(0, current))
        if actual_luck > 0:
            attacker.db.current_luck = current - actual_luck

    # Wound penalty to actions (-2 seriously, -4 mortally)
    action_penalty = get_action_penalty(attacker) if attacker else 0
    total = d10 + stat_val + skill_val + quality_bonus + actual_luck + modifier + action_penalty

    # Poor quality: natural 1 causes jam
    if weapon and _is_weapon_poor_quality(weapon) and d10 == 1:
        weapon.jammed = True
        weapon.save()
        if location:
            location.msg_contents(
                f"|w{attacker.key}|n attacks with |y{weapon.name}|n! "
                f"|rMALFUNCTION!|n Natural 1 - weapon jammed! Use |wattack/unjam {weapon.name}|n to clear."
            )
        return

    success = total > dv

    char_name = attacker.key
    dv_desc = f" ({dv_name})" if dv_name else ""
    stat_name = _stat_display(stat_field)
    roll_parts = [f"1d10 [{d10}]", stat_name, skill_display]
    if action_penalty:
        roll_parts.append(f"{action_penalty} (wound)")
    if quality_bonus:
        roll_parts.append(f"+{quality_bonus} (quality)")
    if actual_luck:
        roll_parts.append(f"+{actual_luck} (luck)")
    if modifier:
        roll_parts.append(f"{modifier:+d}")
    roll_result = " + ".join(roll_parts) + f" = {total} vs DV {dv}{dv_desc}"

    at_target = f" at |w{target.key}|n" if target else ""
    msg_lines = [
        f"|w{char_name}|n attacks{at_target} with |y{weapon_name}|n!",
        f"  Roll: {roll_result}",
    ]

    # Consume ammo for ranged weapons (1 round for single shot)
    if weapon and weapon.category not in ("archery", "melee"):
        from world.weapon_constants import get_effective_clip

        inv = getattr(sheet, "inventory", None) if sheet else None
        eff_clip = get_effective_clip(weapon, inv)
        if eff_clip:
            if (weapon.current_ammo or 0) < 1:
                if location:
                    location.msg_contents(
                        f"|w{attacker.key}|n's {weapon.name} is |rempty|n! "
                        f"Reload with |wattack/reload {weapon.name}|n."
                    )
                return
            weapon.current_ammo = (weapon.current_ammo or 0) - 1
            weapon.save()

    if success:
        damage_rolls = [random.randint(1, 6) for _ in range(num_dice)]
        total_damage = sum(damage_rolls)
        rolls_str = ", ".join(str(r) for r in damage_rolls)
        msg_lines.append(f"  |gHit!|n Damage: |r{total_damage}|n ({num_dice}d6: {rolls_str})")

        # Apply damage to target if present and not already dead
        if target and not is_dead(target):
            _apply_attack_damage(target, total_damage, aim_location, location, msg_lines)
    else:
        msg_lines.append(f"  |rMISS!|n (need to exceed {dv})")

    output = "\n".join(msg_lines)
    if location:
        location.msg_contents(output)


class CmdDodge(MuxCommand):
    """
    Roll a dodge check (1d10 + Dexterity + Evasion). The result becomes the DV
    for attacks against you until it expires or is used.

    Usage:
      dodge [modifier]     - Roll dodge (e.g. dodge +1, dodge -2, dodge +3-1-4)
      dodge as <name> [modifier] - Roll dodge for another (yourself, or an NPC you own)

    Modifiers: +1, -2, +3-1-4 (arithmetic sum). Armor EV penalty applies in addition.
    When someone attacks you, they'll use your last dodge result as the DV.
    """

    key = "dodge"
    help_category = "Combat"

    def func(self):
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before using the dodge command.")
            return

        args = (self.args or "").strip()
        modifier = 0
        if args.lower().startswith("as "):
            rest = args[3:].strip()
            # "as Soma" or "as Soma +1" - target name, optional modifier
            if rest:
                parts = rest.split(None, 1)
                target_name = parts[0]
                if len(parts) > 1 and parts[1] and (parts[1][0] in "+-" or parts[1][0].isdigit()):
                    modifier = parse_modifier_string(parts[1])
            else:
                target_name = ""
            if not target_name:
                self.caller.msg("Usage: dodge as <name> [modifier]")
                return
            target = self.caller.search(target_name, global_search=True)
            if not target:
                return
            if not _can_roll_dodge_for(self.caller, target):
                self.caller.msg(f"You cannot roll dodge for {target.key}.")
                return
        else:
            # "dodge", "dodge +1", "dodge -2", "dodge +3-1-4"
            if args and (args[0] in "+-" or args[0].isdigit()):
                modifier = parse_modifier_string(args)
            target = self.caller

        if is_dead(target):
            self.caller.msg(f"{target.key} is dead and cannot dodge.")
            return

        # NPCs and characters without sheet use db
        d10, dex, evasion, total = _get_dodge_dv(target, modifier=modifier)
        _set_last_dodge_dv(target, total)

        char_name = target.key
        ev_penalty = _get_armor_ev_penalty(target)
        action_penalty = get_action_penalty(target)
        roll_str = f"1d10 [{d10}] + Dexterity + Evasion"
        if ev_penalty:
            roll_str += f" - {ev_penalty} (armor EV)"
        if action_penalty:
            roll_str += f" {action_penalty} (wound)"
        if modifier:
            roll_str += f" {modifier:+d}"
        roll_str += f" = {total}"
        msg_lines = [
            f"|w{char_name}|n dodges!",
            f"  Roll: {roll_str} (DV for attacks)",
        ]
        output = "\n".join(msg_lines)
        self.caller.location.msg_contents(output)

        # Check for pending autofire (dodge must beat stored attack roll)
        if _resolve_pending_autofire(target, total):
            return

        # Check for pending attacks and auto-execute each
        pending = _get_and_clear_pending_attacks(target)
        if pending:
            _clear_last_dodge_dv(target)  # Consume dodge
            for attacker, override in pending:
                kwargs = {}
                if override and override.get("stat") is not None and override.get("skill") is not None:
                    kwargs = {
                        "staff_stat": override["stat"],
                        "staff_skill": override["skill"],
                        "staff_skill_display": override.get("skill_display"),
                        "staff_weapon_name": override.get("weapon_name"),
                        "staff_num_dice": override.get("num_dice"),
                        "staff_stat_field": override.get("stat_field"),
                    }
                aim_loc = override.get("aim_location") if override else None
                luck_spend = override.get("luck_spend", 0) if override else 0
                modifier = override.get("modifier", 0) if override else 0
                force_melee = override.get("force_melee", False) if override else False
                kwargs["luck_spend"] = luck_spend
                kwargs["modifier"] = modifier
                kwargs["force_melee"] = force_melee
                execute_attack_roll(attacker, target, total, f"{target.key}'s dodge", target.location,
                                   aim_location=aim_loc, **kwargs)


class CmdAttack(MuxCommand):
    """
    Make an attack roll (stat + skill vs DV) and roll damage if you exceed the DV.

    Usage:
      attack <dv> [=modifier]        - Use GM-specified DV (e.g. attack 13=+2)
      attack <target> [=modifier]    - Attack target; they must dodge first
      attack <target1,target2,...>   - Splash/shotgun zone (with grenade, rocket, flamethrower, or shotgun)
      attack/distance <meters> [target] [=modifier] - Ranged attack at distance
      attack/luck <N>=<dv or target> - Spend N luck (+1 per point) on attack
      attack/aim <target>=<head|body|arms|legs> - Aimed shot at body part
      attack/melee <target>          - Melee attack (medium melee or unarmed, whichever greater)
      attack/autofire <target1>, <target2>, ... - Autofire (10 bullets, REF 8+ can dodge)
      attack/suppressive <target1>, ... - Suppressive fire (10 bullets, WILL+Concentration vs REF+Autofire)
      attack/unjam <weapon name>     - Clear jam on poor quality weapon (Action)
      attack/reload <weapon> [=ammo type] - Reload from inventory (e.g. attack/reload smg=hollow point)
      attack/pending                 - List pending attacks (attacker -> target) in the room
      attack/cancel [target]         - Cancel your pending attack(s); omit target to cancel all

    Modifiers: =+2, =-3, =-2+3+1-1 (arithmetic sum). Excellent weapons +1; poor weapons jam on natural 1.

    Staff only:
      attack/clear                    - Clear all pending attacks in the room
      attack/staff <weapon>/[stat]+[skill]=<dv or target>
      attack/staff/autofire <weapon>/[stat]+[skill]=<target1,target2,...>
      attack/staff/aim <weapon>/[stat]+[skill]=<target or dv>=<location>
      attack/staff/distance <weapon>/[stat]+[skill]=<distance> <target>

    At point blank (0-6m), targets must dodge. Beyond that, use range chart DV.
    """

    key = "attack"
    aliases = ["atk"]
    help_category = "Combat"

    def func(self):
        args = (self.args or "").strip()
        switches = self.switches or []

        # attack/pending - show pending attacks (attacker -> target) for everyone
        if "pending" in switches:
            self._attack_pending()
            return

        # attack/cancel [target] - cancel pending attack(s) you have made
        if "cancel" in switches:
            self._attack_cancel(args)
            return

        # Staff: attack/clear - clear all pending attacks in the room
        if "clear" in switches:
            if not (hasattr(self.caller, "check_permstring") and (
                self.caller.check_permstring("builders") or self.caller.check_permstring("wizards")
            )):
                self.caller.msg("Only staff can use attack/clear.")
                return
            loc = self.caller.location
            if not loc:
                self.caller.msg("You are not in a room.")
                return
            count = _clear_all_pending_attacks_in_room(loc)
            self.caller.msg(f"Cleared pending attacks for {count} character(s) in the room.")
            return

        # Staff attack: attack/staff <weapon>/[stat] + [skill]=<dv or target>
        if "staff" in switches:
            if not (hasattr(self.caller, "check_permstring") and (
                self.caller.check_permstring("builders") or self.caller.check_permstring("wizards")
            )):
                self.caller.msg("Only staff can use attack/staff.")
                return
            self._attack_staff(args, switches)
            return

        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before using the attack command.")
            return

        char = self.caller
        if not hasattr(char, "character_sheet") or not char.character_sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        sheet = char.character_sheet

        if "autofire" in switches:
            self._attack_autofire(sheet, char, args)
            return
        if "suppressive" in switches:
            self._attack_suppressive(sheet, char, args)
            return
        if "unjam" in switches:
            self._attack_unjam(char, args)
            return
        if "reload" in switches:
            self._attack_reload(char, args)
            return

        # Parse luck: attack/luck N=... or attack/distance/luck N=... or attack/aim/luck N=target=head
        luck_spend = 0
        if "luck" in switches and "=" in args:
            luck_part, args = args.split("=", 1)
            luck_part = luck_part.strip()
            try:
                luck_spend = int(luck_part)
                if luck_spend < 1:
                    self.caller.msg("Luck amount must be at least 1.")
                    return
            except ValueError:
                self.caller.msg("Usage: attack/luck <amount>=<dv or target>")
                return
            args = args.strip()
            if luck_spend > 0:
                current = getattr(char.db, "current_luck", 0) or 0
                if current < luck_spend:
                    self.caller.msg(f"You only have {current} luck point(s). Cannot spend {luck_spend}.")
                    return

        # Parse modifier: attack 13=+2, attack target=-3, attack/mod 20=-2+3+1-1
        # For aim: target=head=+2 (parsed in _attack_aim). For melee: target=+2 parsed here.
        modifier = 0
        if "=" in args and "aim" not in switches:
            lhs, rhs = args.split("=", 1)
            rhs = rhs.strip()
            if rhs and (rhs[0] in "+-" or rhs[0].isdigit() or any(c.isdigit() for c in rhs)):
                mod_val = parse_modifier_string(rhs)
                args = lhs.strip()
                modifier = mod_val

        if "distance" in switches:
            self._attack_distance(sheet, char, args, luck_spend=luck_spend, modifier=modifier)
            return
        if "aim" in switches:
            self._attack_aim(sheet, char, args, luck_spend=luck_spend, modifier=modifier)
            return
        if "melee" in switches:
            self._attack_melee(sheet, char, args, luck_spend=luck_spend, modifier=modifier)
            return

        # Default: attack <dv> or attack <target> or attack <target1,target2,...> (splash/shotgun)
        if not args:
            self.caller.msg("Usage: attack <dv> or attack <target> (e.g. attack 13, attack Soma)")
            return

        parsed = parse_dv(args)
        if parsed:
            dv, dv_name, _ = parsed
            target = None
        else:
            names = [n.strip() for n in args.split(",") if n.strip()]
            if len(names) > 1:
                # Multiple targets - require splash or shotgun
                self._attack_zone_targets(sheet, char, names)
                return
            target = self.caller.search(names[0] if names else args)
            if not target:
                return
            if target == char:
                self.caller.msg("You can't attack yourself.")
                return

            dodge_dv, _ = _get_last_dodge_dv(target)
            if dodge_dv is None:
                target_name = target.key
                _add_pending_attack(target, char, modifier=modifier, luck_spend=luck_spend)
                self.caller.location.msg_contents(
                    f"|w{char.key}|n attacks |w{target_name}|n! |y{target_name} must dodge first.|n "
                    f"Use the |w'dodge'|n command (or |w+npc/dodge {target_name}|n for NPCs)."
                )
                target.msg(f"|yYou are being attacked by {char.key}!|n Use the |w'dodge'|n command to roll your evasion.")
                if is_npc(target):
                    owner_id = getattr(target.db, "owner_account_id", None)
                    if owner_id:
                        from evennia.accounts.models import AccountDB
                        try:
                            owner = AccountDB.objects.get(id=owner_id)
                            owner.msg(f"|yYour NPC {target_name} is being attacked by {char.key}!|n "
                                      f"Use |w+npc/dodge {target_name}|n to roll.")
                        except AccountDB.DoesNotExist:
                            pass
                return

            dv = dodge_dv
            dv_name = f"{target.key}'s dodge"
            _clear_last_dodge_dv(target)  # Consume dodge for this attack

        execute_attack_roll(char, target, dv, dv_name, self.caller.location,
                           luck_spend=luck_spend, modifier=modifier)

    def _attack_unjam(self, char, args):
        """attack/unjam <weapon name> - Clear jam on poor quality weapon (Action, no roll)."""
        if not args or not args.strip():
            self.caller.msg("Usage: attack/unjam <weapon name>")
            return
        weapon_name = args.strip()
        weapon = _get_equipped_weapon(char)
        if not weapon:
            self.caller.msg("You have no weapon equipped.")
            return
        if not _equipped_weapon_matches_name(self.caller, char, weapon, weapon_name):
            self.caller.msg(f"Your equipped weapon is {weapon.name}, not '{weapon_name}'.")
            return
        if not getattr(weapon, "jammed", False):
            self.caller.msg(f"Your {weapon.name} is not jammed.")
            return
        weapon.jammed = False
        weapon.save()
        loc = self.caller.location
        if loc:
            loc.msg_contents(f"|w{char.key}|n clears the jam on their |y{weapon.name}|n.")
        self.caller.msg(f"You have cleared the jam on your {weapon.name}.")

    def _attack_reload(self, char, args):
        """attack/reload <weapon> [=ammo type] - Reload weapon from inventory."""
        from world.inventory.models import Ammunition, AmmoType, Inventory
        from world.weapon_constants import get_effective_clip
        if not args or not args.strip():
            self.caller.msg("Usage: attack/reload <weapon> [=ammo type]")
            return
        weapon_name = args.strip()
        ammo_type_arg = None
        if "=" in weapon_name:
            weapon_name, ammo_type_arg = weapon_name.split("=", 1)
            weapon_name = weapon_name.strip()
            ammo_type_arg = ammo_type_arg.strip() if ammo_type_arg else None

        weapon = _get_equipped_weapon(char)
        if not weapon or (weapon.name or "").lower() != weapon_name.lower():
            inv = getattr(char.character_sheet, "inventory", None) if hasattr(char, "character_sheet") and char.character_sheet else None
            if inv:
                from commands.inventory_commands import _find_weapon_for_equip
                weapon = _find_weapon_for_equip(self.caller, inv, weapon_name)
            if not weapon:
                return

        inventory, _ = Inventory.get_or_create_for_character(char)
        effective_clip = get_effective_clip(weapon, inventory)
        room = effective_clip - (weapon.current_ammo or 0)
        if room <= 0:
            self.caller.msg(f"Your {weapon.name} is already full ({weapon.current_ammo}/{effective_clip}).")
            return

        target_ammo_type = (ammo_type_arg or getattr(weapon, "ammo_type", "Basic")).strip()
        ammo_type_val = "Basic"
        for choice, _ in AmmoType.choices:
            if target_ammo_type.lower() in str(choice).lower() or str(choice).lower().replace(" ", "") == target_ammo_type.lower().replace(" ", ""):
                ammo_type_val = choice
                break

        ammo_candidates = list(inventory.ammunition.filter(ammo_type=ammo_type_val, quantity__gt=0).order_by("-quantity"))
        if not ammo_candidates:
            self.caller.msg(f"You have no {target_ammo_type or 'matching'} ammunition in your inventory.")
            return

        ammo = ammo_candidates[0]
        to_load = min(room, ammo.quantity)
        weapon.current_ammo = (weapon.current_ammo or 0) + to_load
        ammo.quantity -= to_load
        if ammo.quantity <= 0:
            ammo.delete()
        else:
            ammo.save()
        weapon.save()
        if hasattr(weapon, "db"):
            weapon.db.loaded_ammo_type = ammo_type_val
        loc = self.caller.location
        if loc:
            loc.msg_contents(f"|w{char.key}|n reloads their |y{weapon.name}|n.")
        self.caller.msg(f"You reload your {weapon.name}. Loaded {to_load} rounds ({weapon.current_ammo}/{effective_clip} {ammo_type_val}).")

    def _attack_distance(self, sheet, char, args, luck_spend=0, modifier=0):
        """attack/distance <meters> [target] - Use range chart for DV. Target optional (e.g. suppressive fire)."""
        parts = args.split(None, 1)
        if not parts:
            self.caller.msg("Usage: attack/distance <meters> [target] or attack/distance/luck N=<meters> [target]")
            return
        try:
            distance = int(parts[0])
        except ValueError:
            self.caller.msg("Distance must be a number (meters).")
            return
        target_name = parts[1].strip() if len(parts) > 1 else None
        target = None
        if target_name:
            target = self.caller.search(target_name)
            if not target or target == char:
                return
        weapon = _get_equipped_weapon(char)
        cw_attack = _get_active_cyberware_weapon(char)
        if not weapon and not cw_attack:
            self.caller.msg("You need a ranged weapon equipped for attack/distance.")
            return
        w_name = _combat_weapon_name(weapon) if weapon else (cw_attack[1] if cw_attack else "")
        w_cat = weapon.category if weapon else ("handgun" if cw_attack and cw_attack[3] == "handgun" else "heavy_weapons")
        dv, dv_name = get_dv_for_range(w_name, w_cat, distance, autofire=False)
        if dv is None:
            self.caller.msg(f"Your weapon is out of range at {distance}m.")
            return
        if target and distance <= POINT_BLANK_RANGE:
            dodge_dv, _ = _get_last_dodge_dv(target)
            if dodge_dv is None:
                _add_pending_attack(target, char, modifier=modifier, luck_spend=luck_spend)
                self.caller.location.msg_contents(
                    f"|w{char.key}|n attacks |w{target.key}|n at point blank ({distance}m)! "
                    f"|y{target.key} must dodge first.|n Use the |w'dodge'|n command."
                )
                target.msg(f"|yYou are being attacked by {char.key} at point blank!|n Use the |w'dodge'|n command.")
                return
            dv = dodge_dv
            dv_name = f"{target.key}'s dodge"
            _clear_last_dodge_dv(target)
        else:
            dv_name = f"DV {dv} ({distance}m)"
        execute_attack_roll(char, target, dv, dv_name, self.caller.location,
                           luck_spend=luck_spend, modifier=modifier)

    def _attack_aim(self, sheet, char, args, luck_spend=0, modifier=0):
        """attack/aim <target>=<head|body|arms|legs> [=modifier]"""
        if not args or "=" not in args:
            self.caller.msg("Usage: attack/aim <target>=<head|body|arms|legs> [=modifier]")
            return
        parts = args.split("=")
        target_name = parts[0].strip()
        loc = parts[1].strip().lower() if len(parts) > 1 else ""
        # Optional modifier at end: target=head=+2
        if len(parts) >= 3 and parts[-1] and (parts[-1][0] in "+-" or parts[-1][0].isdigit()):
            modifier = parse_modifier_string(parts[-1])
            loc = parts[1].strip().lower() if len(parts) > 2 else loc
        if loc not in ARMOR_LOCATIONS:
            self.caller.msg(f"Aim location must be one of: {', '.join(ARMOR_LOCATIONS)}")
            return
        target = self.caller.search(target_name)
        if not target or target == char:
            return
        dodge_dv, _ = _get_last_dodge_dv(target)
        if dodge_dv is None:
            _add_pending_attack(target, char, modifier=modifier, luck_spend=luck_spend, aim_location=loc)
            self.caller.location.msg_contents(
                f"|w{char.key}|n aims at |w{target.key}|n's {loc}! |y{target.key} must dodge first.|n"
            )
            target.msg(f"|yYou are being targeted by {char.key}!|n Use the |w'dodge'|n command.")
            return
        dv = dodge_dv
        dv_name = f"{target.key}'s dodge"
        _clear_last_dodge_dv(target)
        execute_attack_roll(char, target, dv, dv_name, self.caller.location, aim_location=loc,
                           luck_spend=luck_spend, modifier=modifier)

    def _attack_melee(self, sheet, char, args, luck_spend=0, modifier=0):
        """attack/melee <target> [=modifier] - Use medium melee (2d6) or unarmed, whichever is greater."""
        if not args:
            self.caller.msg("Usage: attack/melee <target> [=modifier]")
            return
        # Parse optional modifier: target=+2 or target=-3
        target_name = args.strip()
        if "=" in args:
            lhs, rhs = args.split("=", 1)
            if rhs and (rhs[0] in "+-" or rhs[0].isdigit() or any(c.isdigit() for c in rhs)):
                modifier = parse_modifier_string(rhs)
                target_name = lhs.strip()
        target = self.caller.search(target_name)
        if not target or target == char:
            return
        dodge_dv, _ = _get_last_dodge_dv(target)
        if dodge_dv is None:
            _add_pending_attack(target, char, modifier=modifier, luck_spend=luck_spend, force_melee=True)
            self.caller.location.msg_contents(
                f"|w{char.key}|n attacks |w{target.key}|n in melee! |y{target.key} must dodge first.|n"
            )
            target.msg(f"|yYou are being attacked by {char.key}!|n Use the |w'dodge'|n command.")
            return
        dv = dodge_dv
        dv_name = f"{target.key}'s dodge"
        _clear_last_dodge_dv(target)
        execute_attack_roll(char, target, dv, dv_name, self.caller.location, force_melee=True,
                           luck_spend=luck_spend, modifier=modifier)

    def _attack_pending(self):
        """attack/pending - Show all pending attacks (attacker -> target) in the room."""
        from world.utils.formatting import header, footer, format_key_value
        loc = self.caller.location
        if not loc:
            self.caller.msg("You are not in a room.")
            return
        pending = _get_pending_attacks_in_room(loc)
        if not pending:
            self.caller.msg("No pending attacks in this room.")
            return
        out = header("Pending Attacks", width=78, color="|y", fillchar="-", bcolor="|b")
        for attacker, target in pending:
            out += format_key_value(f"  {attacker.key}", f"-> {target.key}", width=50) + "\n"
        out += footer(width=78, fillchar="-")
        self.caller.msg(out)

    def _attack_cancel(self, args):
        """attack/cancel [target] - Cancel pending attack(s) you have made."""
        char = self.caller
        loc = char.location
        if not loc:
            self.caller.msg("You are not in a room.")
            return
        target_name = (args or "").strip()
        if target_name:
            target = self.caller.search(target_name)
            if not target:
                return
            if _cancel_attacker_from_target(target, char):
                self.caller.msg(f"You cancel your pending attack on {target.key}.")
                loc.msg_contents(f"|w{char.key}|n cancels their attack on |w{target.key}|n.", exclude=char)
                target.msg(f"|w{char.key}|n has cancelled their attack on you.")
            else:
                self.caller.msg(f"You have no pending attack on {target.key}.")
        else:
            cancelled = 0
            for obj in loc.contents:
                if hasattr(obj, "db") and _cancel_attacker_from_target(obj, char):
                    cancelled += 1
                    obj.msg(f"|w{char.key}|n has cancelled their attack on you.")
            if cancelled:
                self.caller.msg(f"You cancel your pending attack(s) on {cancelled} target(s).")
                loc.msg_contents(f"|w{char.key}|n cancels their pending attack(s).", exclude=char)
            else:
                self.caller.msg("You have no pending attacks to cancel.")

    def _attack_zone_targets(self, sheet, char, names):
        """Splash or shotgun zone attack: attack <target1,target2,...>"""
        weapon = _get_equipped_weapon(char)
        cw_attack = _get_active_cyberware_weapon(char)
        w_name = ""
        w_cat = ""
        if weapon:
            w_name = _combat_weapon_name(weapon) or ""
            w_cat = weapon.category or ""
        elif cw_attack:
            w_name = cw_attack[1] or ""
            w_cat = "heavy_weapons" if "grenade" in w_name.lower() else ""

        if not weapon and not cw_attack:
            self.caller.msg("You need a weapon equipped for zone attacks.")
            return
        if not is_splash_weapon(w_name) and not is_shotgun_zone_weapon(w_name):
            self.caller.msg(
                "Multiple targets require a splash weapon (grenade launcher, rocket, flamethrower) "
                "or shotgun. Use attack/autofire for SMG/Assault Rifle."
            )
            return

        targets = []
        for n in names:
            t = self.caller.search(n)
            if t and t != char:
                targets.append(t)
        if not targets:
            self.caller.msg("No valid targets found.")
            return

        # Ammo check
        if weapon and hasattr(weapon, "current_ammo") and weapon.current_ammo < 1:
            self.caller.msg("Your weapon is out of ammo.")
            return

        if is_shotgun_zone_weapon(w_name):
            dv = 13
            dv_name = "DV 13 (shotgun shell)"
            stat_field, skill_field, skill_display = "reflexes", "shoulder_arms", "Shoulder Arms"
            num_dice = 3
            zone_type = "shotgun"
            zone_label = "shotgun"
        else:
            dv, _ = get_dv_for_range(w_name, w_cat, 0, autofire=False)
            dv = dv or 16
            dv_name = f"DV {dv} (splash)"
            stat_field, skill_field, skill_display = "reflexes", "heavy_weapons", "Heavy Weapons"
            # Resolve damage: "Grenade Launcher"=6d6, "Rocket Launcher"=8d6, "Flamethrower"=5d6
            base_name = w_name.split("(")[0].strip()
            for sub in ("Grenade Launcher", "Rocket Launcher", "Flamethrower"):
                if sub.lower() in base_name.lower():
                    num_dice = get_weapon_damage_dice(sub)
                    break
            else:
                num_dice = get_weapon_damage_dice(base_name)
            if not num_dice:
                num_dice = 6
            zone_type = "splash"
            zone_label = "blast"

        stat_val = _get_stat(sheet, stat_field)
        skill_val = _get_skill(sheet, skill_field)
        d10 = random.randint(1, 10)
        attack_roll = stat_val + skill_val + d10

        # Consume ammo
        if weapon and hasattr(weapon, "current_ammo"):
            weapon.current_ammo -= 1
            weapon.save()

        need_dodge = [t for t in targets if _get_reflexes(t) >= 8]
        no_dodge = [t for t in targets if _get_reflexes(t) < 8]

        if attack_roll <= dv:
            self.caller.location.msg_contents(
                f"|w{char.key}|n fires {zone_label} at the area! "
                f"Roll: 1d10 [{d10}] + {skill_display} = {attack_roll} vs {dv_name} - |rMISS!|n"
            )
            return

        if need_dodge:
            weapon_id = weapon.id if weapon and hasattr(weapon, "id") else None
            for t in need_dodge:
                t.db.pending_autofire = {
                    "attacker_id": char.id,
                    "attack_roll": attack_roll,
                    "dv": dv,
                    "weapon_id": weapon_id,
                    "zone_type": zone_type,
                    "zone_label": zone_label,
                    "num_dice": num_dice,
                }
            names_str = ", ".join(t.key for t in need_dodge)
            self.caller.location.msg_contents(
                f"|w{char.key}|n fires {zone_label}! Roll: 1d10 [{d10}] + {skill_display} = {attack_roll} vs {dv_name} - |gHit!|n "
                f"|y{names_str} (REF 8+) must dodge to beat {attack_roll}!|n"
            )
            for t in need_dodge:
                t.msg(f"|yYou are in the blast zone!|n Dodge to beat {attack_roll}.")
        if no_dodge:
            rolls = [random.randint(1, 6) for _ in range(num_dice)]
            dmg = sum(rolls)
            rolls_str = ", ".join(str(r) for r in rolls)
            for t in no_dodge:
                self.caller.location.msg_contents(
                    f"  |w{t.key}|n (REF<8) hit! {num_dice}d6 [{rolls_str}] = |r{dmg}|n"
                )

    def _attack_staff(self, args, switches):
        """Staff attack: weapon/stat + skill=dv or target. Staff can specify weapon without equipping."""
        if not args or "=" not in args:
            self.caller.msg(
                "Usage: attack/staff <weapon>/[stat] + [skill]=<dv or target>\n"
                "  attack/staff Very Heavy Pistol/4 + 6=17\n"
                "  attack/staff Medium Melee Weapon/5 + 3=John\n"
                "  attack/staff/autofire SMG/6 + 4=Alice,Bob,Carol\n"
                "  attack/staff/aim Very Heavy Pistol/4+6=John=body\n"
                "  attack/staff/distance Assault Rifle/5+5=25 John"
            )
            return

        lhs, rhs = args.split("=", 1)
        lhs, rhs = lhs.strip(), rhs.strip()

        # Parse weapon/stat + skill
        if "+" in lhs:
            left_part, skill_str = lhs.rsplit("+", 1)
            left_part, skill_str = left_part.strip(), skill_str.strip()
        else:
            self.caller.msg("Format: weapon/stat + skill=target (e.g. Very Heavy Pistol/4 + 6=17)")
            return

        if "/" not in left_part:
            self.caller.msg("Format: weapon/stat + skill (e.g. Very Heavy Pistol/4 + 6)")
            return

        weapon_str, stat_str = left_part.rsplit("/", 1)
        weapon_str, stat_str = weapon_str.strip(), stat_str.strip()

        try:
            stat_val = int(stat_str)
            skill_val = int(skill_str)
        except ValueError:
            self.caller.msg("Stat and skill must be numbers.")
            return

        # Look up weapon
        w_data = get_weapon_by_name(weapon_str)
        if not w_data and " melee" in weapon_str.lower():
            w_data = get_weapon_by_name(weapon_str + " Weapon")
        if not w_data:
            self.caller.msg(f"Unknown weapon: {weapon_str}. Use exact name from equipment (e.g. 'Medium Melee Weapon').")
            return

        w_name = w_data.get("name", weapon_str)
        w_cat = (w_data.get("category") or "").strip().lower()
        mapping = WEAPON_SKILL_MAP.get(w_cat, ("reflexes", "handgun", "Handgun"))
        stat_field, skill_field, skill_display = mapping
        num_dice = _parse_damage_dice(w_data.get("damage", "")) or 2
        weapon_display = f"{w_name} ({skill_display})"

        if "autofire" in switches:
            self._attack_staff_autofire(stat_val, skill_val, weapon_display, w_name, w_cat, rhs)
            return
        if "aim" in switches:
            self._attack_staff_aim(stat_val, skill_val, weapon_display, num_dice, stat_field, rhs)
            return
        if "distance" in switches:
            self._attack_staff_distance(stat_val, skill_val, weapon_display, num_dice, stat_field, w_name, w_cat, rhs)
            return

        # Default staff attack: rhs = DV or target
        parsed = parse_dv(rhs)
        if parsed:
            dv, dv_name, _ = parsed
            target = None
        else:
            names = [n.strip() for n in rhs.split(",") if n.strip()]
            if len(names) > 1:
                self.caller.msg("For multiple targets use attack/staff/autofire.")
                return
            target = self.caller.search(names[0] if names else rhs)
            if not target:
                return
            if target == self.caller:
                self.caller.msg("You can't attack yourself.")
                return
            dodge_dv, _ = _get_last_dodge_dv(target)
            if dodge_dv is None:
                staff_override = {
                    "stat": stat_val, "skill": skill_val, "skill_display": skill_display,
                    "weapon_name": weapon_display, "num_dice": num_dice, "stat_field": stat_field,
                }
                _add_pending_attack(target, self.caller, staff_override=staff_override)
                self.caller.location.msg_contents(
                    f"|w{self.caller.key}|n (staff) attacks |w{target.key}|n! |y{target.key} must dodge first.|n"
                )
                target.msg(f"|yYou are being attacked!|n Use the |w'dodge'|n command.")
                return
            dv = dodge_dv
            dv_name = f"{target.key}'s dodge"
            _clear_last_dodge_dv(target)

        execute_attack_roll(
            self.caller, target, dv, dv_name, self.caller.location,
            staff_stat=stat_val, staff_skill=skill_val, staff_skill_display=skill_display,
            staff_weapon_name=weapon_display, staff_num_dice=num_dice, staff_stat_field=stat_field
        )

    def _attack_staff_aim(self, stat_val, skill_val, weapon_display, num_dice, stat_field, rhs):
        """attack/staff/aim weapon/stat+skill=target=location or =dv"""
        if "=" in rhs:
            parts = rhs.split("=", 1)
            target_name = parts[0].strip()
            loc = parts[1].strip().lower() if len(parts) > 1 else "body"
        else:
            target_name = rhs
            loc = "body"
        if loc not in ARMOR_LOCATIONS:
            self.caller.msg(f"Aim location must be one of: {', '.join(ARMOR_LOCATIONS)}")
            return
        parsed = parse_dv(target_name)
        if parsed:
            dv, dv_name, _ = parsed
            target = None
        else:
            target = self.caller.search(target_name)
            if not target or target == self.caller:
                return
            dodge_dv, _ = _get_last_dodge_dv(target)
            if dodge_dv is None:
                staff_override = {
                    "stat": stat_val, "skill": skill_val, "skill_display": weapon_display.split("(")[-1].rstrip(")"),
                    "weapon_name": weapon_display, "num_dice": num_dice, "stat_field": stat_field,
                    "aim_location": loc,
                }
                _add_pending_attack(target, self.caller, staff_override=staff_override)
                self.caller.location.msg_contents(
                    f"|w{self.caller.key}|n (staff) aims at |w{target.key}|n's {loc}! |y{target.key} must dodge first.|n"
                )
                target.msg(f"|yYou are being targeted!|n Use the |w'dodge'|n command.")
                return
            dv = dodge_dv
            dv_name = f"{target.key}'s dodge"
            _clear_last_dodge_dv(target)
        execute_attack_roll(
            self.caller, target, dv, dv_name, self.caller.location, aim_location=loc,
            staff_stat=stat_val, staff_skill=skill_val, staff_skill_display=weapon_display.split("(")[-1].rstrip(")"),
            staff_weapon_name=weapon_display, staff_num_dice=num_dice, staff_stat_field=stat_field
        )

    def _attack_staff_distance(self, stat_val, skill_val, weapon_display, num_dice, stat_field, w_name, w_cat, rhs):
        """attack/staff/distance weapon/stat+skill=distance target"""
        parts = rhs.split(None, 1)
        if not parts:
            self.caller.msg("Usage: attack/staff/distance <weapon>/[stat]+[skill]=<distance> <target>")
            return
        try:
            distance = int(parts[0])
        except ValueError:
            self.caller.msg("Distance must be a number (meters).")
            return
        target_name = parts[1].strip() if len(parts) > 1 else None
        if not target_name:
            self.caller.msg("Usage: attack/staff/distance <weapon>/[stat]+[skill]=<distance> <target>")
            return
        target = self.caller.search(target_name)
        if not target or target == self.caller:
            return
        dv, _ = get_dv_for_range(w_name, w_cat, distance, autofire=False)
        if dv is None:
            self.caller.msg(f"Target out of range at {distance}m.")
            return
        if distance <= POINT_BLANK_RANGE:
            dodge_dv, _ = _get_last_dodge_dv(target)
            if dodge_dv is None:
                staff_override = {
                    "stat": stat_val, "skill": skill_val, "skill_display": weapon_display.split("(")[-1].rstrip(")"),
                    "weapon_name": weapon_display, "num_dice": num_dice, "stat_field": stat_field,
                }
                _add_pending_attack(target, self.caller, staff_override=staff_override)
                self.caller.location.msg_contents(
                    f"|w{self.caller.key}|n (staff) attacks at point blank ({distance}m)! |y{target.key} must dodge first.|n"
                )
                target.msg(f"|yYou are being attacked!|n Use the |w'dodge'|n command.")
                return
            dv = dodge_dv
            dv_name = f"{target.key}'s dodge"
            _clear_last_dodge_dv(target)
        else:
            dv_name = f"DV {dv} ({distance}m)"
        skill_display = weapon_display.split("(")[-1].rstrip(")")
        execute_attack_roll(
            self.caller, target, dv, dv_name, self.caller.location,
            staff_stat=stat_val, staff_skill=skill_val, staff_skill_display=skill_display,
            staff_weapon_name=weapon_display, staff_num_dice=num_dice, staff_stat_field=stat_field
        )

    def _attack_staff_autofire(self, stat_val, skill_val, weapon_display, w_name, w_cat, rhs):
        """attack/staff/autofire weapon/stat+skill=target1,target2,..."""
        w_lower = (w_name or "").lower()
        if "smg" not in w_lower and "assault rifle" not in w_lower:
            self.caller.msg("Autofire requires SMG or Assault Rifle.")
            return
        names = [n.strip() for n in rhs.split(",") if n.strip()]
        targets = []
        for n in names:
            t = self.caller.search(n)
            if t and t != self.caller:
                targets.append(t)
        if not targets:
            self.caller.msg("No valid targets found.")
            return
        dv, _ = get_dv_for_range(w_name, w_cat, 0, autofire=True)
        dv = dv or 17
        d10 = random.randint(1, 10)
        attack_roll = stat_val + skill_val + d10
        need_dodge = [t for t in targets if _get_reflexes(t) >= 8]
        no_dodge = [t for t in targets if _get_reflexes(t) < 8]
        if need_dodge:
            for t in need_dodge:
                t.db.pending_autofire = {
                    "attacker_id": self.caller.id,
                    "attack_roll": attack_roll,
                    "dv": dv,
                    "weapon_id": None,
                    "zone_type": "autofire",
                    "zone_label": "autofire",
                    "num_dice": 2,
                }
            names_str = ", ".join(t.key for t in need_dodge)
            self.caller.location.msg_contents(
                f"|w{self.caller.key}|n (staff) autofire! Roll: 1d10 [{d10}] + {stat_val} + {skill_val} = {attack_roll} vs DV {dv}. "
                f"|y{names_str} (REF 8+) must dodge to beat {attack_roll}!|n"
            )
            for t in need_dodge:
                t.msg(f"|yYou are in the line of autofire!|n Dodge to beat {attack_roll}.")
        if no_dodge:
            beat = max(0, attack_roll - dv)
            mult = 4 if "assault rifle" in w_lower else 3
            mult = min(beat, mult)
            for t in no_dodge:
                d1, d2 = random.randint(1, 6), random.randint(1, 6)
                dmg = (d1 + d2) * mult
                self.caller.location.msg_contents(
                    f"  |w{t.key}|n (REF<8) hit! 2d6 [{d1},{d2}] x {mult} = |r{dmg}|n"
                )

    def _attack_autofire(self, sheet, char, args):
        """attack/autofire <target1>, <target2>, ... - Costs 10 bullets, REF 8+ can dodge."""
        if not args:
            self.caller.msg("Usage: attack/autofire <target1>, <target2>, ...")
            return
        weapon = _get_equipped_weapon(char)
        if not weapon or weapon.current_ammo < 10:
            self.caller.msg("You need a weapon with at least 10 bullets for autofire.")
            return
        if not _weapon_supports_autofire(weapon):
            self.caller.msg("Autofire requires an SMG or Assault Rifle.")
            return
        names = [n.strip() for n in args.split(",") if n.strip()]
        targets = []
        for n in names:
            t = self.caller.search(n)
            if t and t != char:
                targets.append(t)
        if not targets:
            self.caller.msg("No valid targets found.")
            return
        dv, _ = get_dv_for_range(_combat_weapon_name(weapon), weapon.category, 0, autofire=True)
        dv = dv or 17
        ref = _get_stat(sheet, "reflexes")
        af = _get_skill(sheet, "autofire")
        d10 = random.randint(1, 10)
        attack_roll = ref + af + d10
        weapon.current_ammo -= 10
        weapon.save()
        need_dodge = [t for t in targets if _get_reflexes(t) >= 8]
        no_dodge = [t for t in targets if _get_reflexes(t) < 8]
        if need_dodge:
            for t in need_dodge:
                t.db.pending_autofire = {"attacker_id": char.id, "attack_roll": attack_roll, "dv": dv, "weapon_id": weapon.id}
            names_str = ", ".join(t.key for t in need_dodge)
            self.caller.location.msg_contents(
                f"|w{char.key}|n opens up with autofire! Roll: 1d10 [{d10}] + REF + Autofire = {attack_roll} vs DV {dv}. "
                f"|y{names_str} (REF 8+) must dodge to beat {attack_roll}!|n"
            )
            for t in need_dodge:
                t.msg(f"|yYou are in the line of autofire!|n Dodge to beat {attack_roll}.")
        if no_dodge:
            beat = max(0, attack_roll - dv)
            mult = _autofire_multiplier_for_weapon(weapon)
            mult = min(beat, mult)
            for t in no_dodge:
                d1, d2 = random.randint(1, 6), random.randint(1, 6)
                dmg = (d1 + d2) * mult
                self.caller.location.msg_contents(
                    f"  |w{t.key}|n (REF<8) hit! 2d6 [{d1},{d2}] x {mult} = |r{dmg}|n"
                )

    def _attack_suppressive(self, sheet, char, args):
        """attack/suppressive - Everyone within 25m, out of cover, rolls WILL+Concentration vs REF+Autofire."""
        weapon = _get_equipped_weapon(char)
        if not weapon or weapon.current_ammo < 10:
            self.caller.msg("You need a weapon with at least 10 bullets for suppressive fire.")
            return
        self.caller.location.msg_contents(
            f"|w{char.key}|n lays down suppressive fire! "
            f"Everyone on foot within 25m/yds, out of cover, must roll WILL + Concentration + 1d10 vs attacker's REF + Autofire + 1d10."
        )
        weapon.current_ammo -= 10
        weapon.save()


def _stat_display(stat_field):
    """Return display name for stat (without revealing value)."""
    names = {
        "dexterity": "Dexterity",
        "reflexes": "Reflexes",
    }
    return names.get(stat_field, stat_field.replace("_", " ").title())


class CmdDeathSave(MuxCommand):
    """
    Make a Death Save when mortally wounded (HP < 1).
    Roll d10 + death_save_penalty. If result < BODY, you live. Roll of 10 = auto-fail.
    Penalty = base (from injuries) + 1 per roll + 1 per hit at 0 HP. Stabilization resets to base.

    Usage:
      deathsave
      deathsave as <name>   - Staff/owner: roll for another
    """

    key = "deathsave"
    aliases = ["+deathsave", "ds"]
    help_category = "Combat"

    def func(self):
        from world.wound_utils import requires_death_save, make_death_save, get_death_save_penalty, is_dead

        args = (self.args or "").strip()
        if args.lower().startswith("as "):
            target_name = args[3:].strip()
            if not target_name:
                self.caller.msg("Usage: deathsave as <name>")
                return
            if not (hasattr(self.caller, "check_permstring") and (
                self.caller.check_permstring("builders") or self.caller.check_permstring("wizards")
            )):
                self.caller.msg("Only staff can roll death save for another.")
                return
            target = self.caller.search(target_name, global_search=True)
            if not target:
                return
        else:
            target = self.caller

        if is_dead(target):
            self.caller.msg(f"{target.key} is already dead.")
            return

        if not requires_death_save(target):
            self.caller.msg(f"{target.key} is not mortally wounded. Death saves only apply when HP < 1.")
            return

        success, roll, total, penalty = make_death_save(target)
        body = getattr(target.db, "death_save", 0) or 0
        if hasattr(target, "character_sheet") and target.character_sheet:
            body = getattr(target.character_sheet, "death_save", body) or body

        loc = self.caller.location
        if success:
            msg = f"|w{target.key}|n makes a Death Save! 1d10 [{roll}] + {penalty} = {total} < BODY {body} - |gSURVIVES!|n"
        else:
            msg = f"|w{target.key}|n makes a Death Save! 1d10 [{roll}] + {penalty} = {total} - |rFAILED!|n |r{target.key} is DEAD.|n"
        if loc:
            loc.msg_contents(msg)
        if target != self.caller:
            target.msg(f"You {'survive' if success else 'have failed'} the Death Save.")


class CmdCover(MuxCommand):
    """
    Take cover behind an object. Cover absorbs damage before it reaches you.
    Use 'cover' to see current cover, 'cover <item>' to take cover, 'cover none' to leave cover.

    Usage:
      cover              - Show current cover
      cover <item>       - Take cover (e.g. cover car door, cover overturned table)
      cover none         - Leave cover

    Cover examples: car door (25 HP), overturned table (5 HP), bar (20 HP), engine block (50 HP)
    """

    key = "cover"
    aliases = ["+cover"]
    help_category = "Combat"

    def func(self):
        from world.wound_data import get_cover_by_name, COVER_DATA

        args = (self.args or "").strip()
        char = self.caller

        if not args:
            cover = getattr(char.db, "cover", None)
            if not cover or not cover.get("cover_hp"):
                self.caller.msg("You are not in cover. Use 'cover <item>' to take cover (e.g. cover car door).")
                return
            hp = cover.get("cover_current_hp", 0)
            max_hp = cover.get("cover_hp", 0)
            name = cover.get("cover_name", "Unknown")
            self.caller.msg(f"You are behind {name}. Cover: {hp}/{max_hp} HP.")
            return

        if args.lower() in ("none", "off", "leave"):
            char.db.cover = None
            self.caller.msg("You leave cover.")
            if char.location:
                char.location.msg_contents(f"|w{char.key}|n leaves cover.", exclude=char)
            return

        cover_hp, material = get_cover_by_name(args)
        if cover_hp == 0 and args.lower() not in ("office cubicle", "windshield"):
            self.caller.msg(
                f"'{args}' is not valid cover. Examples: car door, overturned table, bar, engine block, metal door"
            )
            return

        char.db.cover = {
            "cover_hp": cover_hp,
            "cover_current_hp": cover_hp,
            "cover_name": args.strip(),
            "material": material or "Unknown",
        }
        self.caller.msg(f"You take cover behind {args.strip()} ({cover_hp} HP).")
        if char.location:
            char.location.msg_contents(f"|w{char.key}|n takes cover behind {args.strip()}.", exclude=char)


def _build_hud_for_char(char, include_header=False):
    """Build HUD string for a character. include_header: prefix with 'Name: '."""
    sheet = _get_sheet(char)
    if not sheet:
        return None
    parts = []
    # HP
    current_hp = get_current_hp(char)
    max_hp = get_max_hp(char)
    parts.append(f"{current_hp}/{max_hp} hp")
    # Armor (worn if strictly better than implants on body; else show implant SP)
    from world.cyberware.implanted_armor import get_hud_armor_display_line

    parts.append(get_hud_armor_display_line(char, sheet))
    # Weapon
    weapon = _get_equipped_weapon(char)
    if weapon:
        from world.edgerunner_weapon_flavor import effective_weapon_quality_tier, resolve_weapon_equipment_template

        quality = effective_weapon_quality_tier(weapon)
        tpl = resolve_weapon_equipment_template(weapon)
        damage = weapon.damage or (tpl.get("damage") if tpl else None) or "N/A"
        parts.append(f"{weapon.name} ({quality}): {damage}")
    else:
        parts.append("no weapon")
    # Ammo
    if weapon and getattr(weapon, "clip", 0) and weapon.category not in ("archery", "melee"):
        inv = getattr(sheet, "inventory", None)
        from world.weapon_constants import get_effective_clip
        eff_clip = get_effective_clip(weapon, inv)
        ammo_type = getattr(weapon, "db", None) and getattr(weapon.db, "loaded_ammo_type", None)
        if not ammo_type:
            ammo_type = getattr(weapon, "ammo_type", "Basic") or "Basic"
        ammo_str = (ammo_type or "Basic").lower()
        parts.append(f"{weapon.current_ammo or 0}/{eff_clip} {ammo_str}")
    else:
        parts.append("n/a")
    line = "; ".join(parts)
    if include_header:
        return f"|w{char.key}|n: {line}"
    return line


class CmdHud(MuxCommand):
    """
    Heads-up display: HP, armor, weapon, ammo.

    Usage:
      hud              - Your HUD
      hud/here         - Staff: HUD for everyone in the room
      hud <name>       - Staff: another character's HUD

    Shows: HP (current/max), armor name and SP (current/base), equipped weapon
    (name quality damage), and ammo (current/max_clip type).
    """

    key = "hud"
    help_category = "Combat"

    def func(self):
        # Staff: hud/here - room HUD
        if "here" in self.switches:
            if not is_staff(self.caller):
                self.caller.msg("Only staff can use hud/here.")
                return
            loc = self.caller.location
            if not loc:
                self.caller.msg("You are not in a location.")
                return
            chars = [
                obj for obj in loc.contents
                if inherits_from(obj, "typeclasses.characters.Character")
                and _get_sheet(obj)
            ]
            if not chars:
                self.caller.msg("No characters with sheets in this room.")
                return
            lines = ["Heads Up Display (room):"]
            for c in chars:
                hud = _build_hud_for_char(c, include_header=True)
                if hud:
                    lines.append(f"  {hud}")
            self.caller.msg("\n".join(lines))
            return

        # Staff: hud <name> - another character's HUD
        args = (self.args or "").strip()
        if args:
            if not is_staff(self.caller):
                self.caller.msg("Only staff can view another character's HUD.")
                return
            from world.utils.character_utils import get_staff_target_character
            target_char, _ = get_staff_target_character(self.caller, args, quiet=True)
            if not target_char:
                self.caller.msg(f"No character named '{args}' found.")
                return
            hud = _build_hud_for_char(target_char, include_header=True)
            if hud:
                self.caller.msg(f"Heads Up Display: {hud}")
            else:
                self.caller.msg(f"{target_char.key} doesn't have a character sheet.")
            return

        # Own HUD
        char = self.caller
        hud = _build_hud_for_char(char)
        if hud:
            self.caller.msg("Heads Up Display: " + hud)
        else:
            self.caller.msg("You don't have a character sheet.")
