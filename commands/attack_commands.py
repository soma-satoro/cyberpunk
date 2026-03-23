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


def _has_reflex_coprocessor_installed(char):
    """True if character has installed Reflex Co-Processor cyberware."""
    from django.db.models import Q
    from world.inventory.models import CyberwareInstance

    name_filter = Q(cyberware__name__iexact="Reflex Co-Processor") | Q(
        cyberware__name__iexact="Reflex Co Processor"
    )
    sheet = _get_sheet(char)
    if sheet and getattr(sheet, "pk", None):
        if CyberwareInstance.objects.filter(
            character_sheet_id=sheet.pk, installed=True
        ).filter(name_filter).exists():
            return True
    if hasattr(char, "pk") and char.pk:
        if CyberwareInstance.objects.filter(
            character_object_id=char.pk, installed=True
        ).filter(name_filter).exists():
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
    """SMG / Heavy SMG / Assault Rifle - uses weapon_type and generic template, not display name."""
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
    grapple_penalty = _get_grapple_action_penalty(target)
    prone_penalty = _get_prone_action_penalty(target)
    total = d10 + dex + evasion - ev_penalty + modifier + action_penalty + grapple_penalty + prone_penalty
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


def _can_dodge_ranged_attacks(target):
    """
    True if target can dodge ranged attacks:
    - REF 8+, or
    - Reflex Co-Processor installed.
    """
    return _get_reflexes(target) >= 8 or _has_reflex_coprocessor_installed(target)


def _is_ranged_attack_for_attacker(attacker, force_melee=False):
    """True if attack mode for attacker is ranged (weapon/cyberware based)."""
    if force_melee:
        return False
    weapon = _get_equipped_weapon(attacker)
    if weapon:
        return (weapon.category or "").strip().lower() != "melee"
    cw_attack = _get_active_cyberware_weapon(attacker)
    if cw_attack:
        skill_field = (cw_attack[3] or "").strip().lower()
        return skill_field in ("handgun", "shoulder_arms", "heavy_weapons", "archery")
    return False


def _get_point_blank_range_dv_for_attacker(attacker):
    """Get range-table DV at point-blank (0m) for attacker's current ranged setup."""
    weapon = _get_equipped_weapon(attacker)
    if weapon:
        dv, _ = get_dv_for_range(_combat_weapon_name(weapon), weapon.category, 0, autofire=False)
        if dv is not None:
            return dv
    cw_attack = _get_active_cyberware_weapon(attacker)
    if cw_attack:
        w_name = cw_attack[1] or ""
        skill_field = (cw_attack[3] or "").strip().lower()
        if skill_field in ("handgun", "shoulder_arms", "heavy_weapons", "archery"):
            w_cat = skill_field
            dv, _ = get_dv_for_range(w_name, w_cat, 0, autofire=False)
            if dv is not None:
                return dv
    return 13


def _get_cool_and_rep(target):
    """
    Return (cool, effective_rep) for facedown.
    effective_rep = rep - notoriety (minimum 0).
    """
    sheet = _get_sheet(target)
    if sheet:
        cool = getattr(sheet, "cool", 0) or 0
        rep = getattr(sheet, "rep", 0) or 0
        notoriety = getattr(sheet, "notoriety", 0) or 0
    else:
        cool = getattr(target.db, "cool", 0) or 0
        rep = getattr(target.db, "rep", 0) or 0
        notoriety = getattr(target.db, "notoriety", 0) or 0
    return int(cool), max(0, int(rep) - int(notoriety))


def _get_dex_and_brawling(target):
    """Return (dexterity, brawling) for grapple checks."""
    sheet = _get_sheet(target)
    if sheet:
        dex = _get_stat(sheet, "dexterity")
        brawling = _get_skill(sheet, "brawling")
        return dex, brawling
    dex = getattr(target.db, "dexterity", 0) or 0
    skills = target.db.skills or {}
    brawling = skills.get("brawling", 0) or 0
    return int(dex), int(brawling)


def _get_dex_and_martial(target):
    """Return (dexterity, martial_arts) for martial checks."""
    sheet = _get_sheet(target)
    if sheet:
        dex = _get_stat(sheet, "dexterity")
        martial = _get_skill(sheet, "martial_arts")
        return int(dex), int(martial)
    dex = getattr(target.db, "dexterity", 0) or 0
    skills = target.db.skills or {}
    martial = skills.get("martial_arts", 0) or 0
    return int(dex), int(martial)


def _martial_damage_dice_for_body(target):
    """CPR martial arts damage by BODY: <=4:1d6, 5-6:2d6, 7-10:3d6, >=11:4d6."""
    sheet = _get_sheet(target)
    body = _get_stat(sheet, "body") if sheet else (getattr(target.db, "body", 0) or 0)
    body = int(body or 0)
    if body <= 4:
        return 1
    if body <= 6:
        return 2
    if body <= 10:
        return 3
    return 4


def _get_willpower(target):
    """Get willpower for requirements."""
    sheet = _get_sheet(target)
    if sheet:
        return int(_get_stat(sheet, "willpower") or 0)
    return int(getattr(target.db, "willpower", 0) or 0)


MARTIAL_STYLE_ALIASES = {
    "aikido": "Aikido",
    "arnis": "Arnis",
    "boxing": "Boxing",
    "capoeira": "Capoeira",
    "choy li fut": "Choy Li Fut",
    "choy_li_fut": "Choy Li Fut",
    "drunken fist": "Drunken Fist",
    "drunken_fist": "Drunken Fist",
    "krav maga": "Krav Maga",
    "krav_maga": "Krav Maga",
    "kendo": "Kendo",
    "jujutsu": "Jujutsu",
    "kung fu": "Kung Fu",
    "kung_fu": "Kung Fu",
    "thrash sambo": "Thrash Sambo",
    "thrash_sambo": "Thrash Sambo",
    "sov-system": "Sov-System",
    "sov system": "Sov-System",
    "sov_system": "Sov-System",
    "gun fu": "Gun Fu",
    "gun_fu": "Gun Fu",
    "militech commando training": "Militech Commando Training",
    "militech_commando_training": "Militech Commando Training",
    "sumo": "Sumo",
    "kyudo": "Kyudo",
    "panzerfaust": "PanzerFaust",
    "multiarm melee": "Multiarm Melee",
    "multiarm_melee": "Multiarm Melee",
    "muay thai": "Muay Thai",
    "muay_thai": "Muay Thai",
    "silat": "Silat",
    "tai chi": "Tai Chi",
    "tai_chi": "Tai Chi",
    "thamoc": "Thamoc",
    "karate": "Karate",
    "judo": "Judo",
    "taekwondo": "Taekwondo",
    "tae_kwon_do": "Taekwondo",
    "tae kwon do": "Taekwondo",
    "wrestling": "Wrestling",
    "arasaka-te": "Arasaka-te",
    "arasakate": "Arasaka-te",
    "arasaka te": "Arasaka-te",
}


def _get_martial_style_rank(target, style_name):
    """Return rank in a specific martial arts form/style."""
    style = MARTIAL_STYLE_ALIASES.get((style_name or "").strip().lower(), (style_name or "").strip())
    if not style:
        return 0
    if hasattr(target, "get_skill_instance") and callable(getattr(target, "get_skill_instance")):
        try:
            return int(target.get_skill_instance("martial_arts", style) or 0)
        except Exception:
            return 0
    skill_instances = getattr(target.db, "skill_instances", {}) or {}
    lookup_key = f"martial_arts({style})".lower()
    for key, value in skill_instances.items():
        if str(key).lower() == lookup_key:
            return int(value or 0)
    return 0


def _get_all_martial_style_ranks(target):
    """Return {style_name: rank} from known aliases."""
    out = {}
    for canonical in set(MARTIAL_STYLE_ALIASES.values()):
        rank = _get_martial_style_rank(target, canonical)
        if rank > 0:
            out[canonical] = rank
    return out


def _check_martial_once_per_turn(caller, move_key):
    """
    Enforce once-per-turn for martial moves.
    In scene combat, this is keyed to scene round + turn index; outside scenes it is not enforced.
    """
    room = getattr(caller, "location", None)
    if not room:
        return True
    try:
        from commands.combat_system import get_active_scene

        scene = get_active_scene(room)
    except Exception:
        scene = None
    if not scene:
        return True
    token = f"{int(scene.get('round', 0) or 0)}:{int(scene.get('turn_index', 0) or 0)}"
    used = dict(getattr(caller.db, "martial_moves_used", {}) or {})
    if used.get(move_key) == token:
        caller.msg("You can only use that special move once this turn.")
        return False
    used[move_key] = token
    caller.db.martial_moves_used = used
    return True


def _martial_turn_token(character):
    """Best-effort turn token for requirement windows."""
    room = getattr(character, "location", None)
    if not room:
        return "no-room"
    try:
        from commands.combat_system import get_active_scene

        scene = get_active_scene(room)
    except Exception:
        scene = None
    if not scene:
        return "no-scene"
    return f"{int(scene.get('round', 0) or 0)}:{int(scene.get('turn_index', 0) or 0)}"


def _mark_martial_event(character, event_key):
    """Timestamp and tag an event as happening on current turn token."""
    now = time.time()
    token = _martial_turn_token(character)
    marks = dict(getattr(character.db, "martial_event_marks", {}) or {})
    marks[event_key] = {"ts": now, "token": token}
    character.db.martial_event_marks = marks


def _has_recent_martial_event(character, event_key, seconds=30):
    """Check event happened recently; used for 'since last turn' approximations."""
    marks = dict(getattr(character.db, "martial_event_marks", {}) or {})
    item = marks.get(event_key, {})
    ts = float(item.get("ts", 0) or 0)
    return (time.time() - ts) <= float(seconds)


def _inc_martial_hit_count(attacker, target):
    """Increment per-turn hit count against a specific target."""
    token = _martial_turn_token(attacker)
    data = dict(getattr(attacker.db, "martial_hit_counts", {}) or {})
    bucket = dict(data.get(token, {}) or {})
    tid = str(getattr(target, "id", 0) or 0)
    bucket[tid] = int(bucket.get(tid, 0) or 0) + 1
    data[token] = bucket
    # keep only latest few tokens
    if len(data) > 6:
        keys = list(data.keys())
        for k in keys[:-6]:
            data.pop(k, None)
    attacker.db.martial_hit_counts = data


def _get_martial_hit_count(attacker, target):
    token = _martial_turn_token(attacker)
    data = dict(getattr(attacker.db, "martial_hit_counts", {}) or {})
    bucket = dict(data.get(token, {}) or {})
    tid = str(getattr(target, "id", 0) or 0)
    return int(bucket.get(tid, 0) or 0)


def _consume_deashi_reaction(target):
    """
    Consume active Deashi reaction if present.
    Returns True if grapple/throw should be negated.
    """
    try:
        until = float(getattr(target.db, "deashi_until", 0) or 0)
    except Exception:
        until = 0
    if until > time.time():
        target.db.deashi_until = 0
        target.db.deashi_mover_name = None
        return True
    return False


def _force_drop_equipped_weapon(target):
    """Force target to drop currently equipped weapon if possible."""
    try:
        if (getattr(target.db, "weapon_retention_until", 0) or 0) > time.time():
            return None
    except Exception:
        pass
    sheet = _get_sheet(target)
    if sheet and getattr(sheet, "eqweapon", None):
        dropped = sheet.eqweapon
        sheet.eqweapon = None
        sheet.save()
        return dropped
    w = getattr(target.db, "eqweapon", None)
    if w:
        target.db.eqweapon = None
        return w
    return None


def _set_grapple_state(attacker, target):
    """Set simple 1:1 grapple state."""
    attacker.db.grappling_target_id = target.id
    target.db.grappled_by_id = attacker.id


def _clear_grapple_state(attacker=None, target=None):
    """Clear grapple state for either side."""
    if attacker and hasattr(attacker, "db"):
        attacker.db.grappling_target_id = None
    if target and hasattr(target, "db"):
        target.db.grappled_by_id = None
        target.db.iron_grip_by_id = None


def _get_grapple_target(attacker):
    """Resolve current grapple target object for attacker, if any."""
    tid = getattr(attacker.db, "grappling_target_id", None)
    if not tid:
        return None
    from evennia.utils.search import search_object

    found = search_object(f"#{tid}")
    if found:
        return found[0]
    attacker.db.grappling_target_id = None
    return None


def _is_grappled(target):
    return bool(getattr(target.db, "grappled_by_id", None))


def _get_active_shield(target):
    """Return active shield dict or None."""
    sh = getattr(target.db, "active_shield", None)
    if not isinstance(sh, dict):
        return None
    hp = int(sh.get("current_hp", 0) or 0)
    if hp <= 0:
        return None
    return sh


def _set_active_shield(target, name, hp, source="gear", interpose=True, human_target_id=None):
    target.db.active_shield = {
        "name": str(name),
        "max_hp": int(hp),
        "current_hp": int(hp),
        "source": source,  # gear|human|corpse
        "interpose": bool(interpose),
        "human_target_id": human_target_id,
    }


def _drop_active_shield(target):
    target.db.active_shield = None


def _shield_interposing(target):
    sh = _get_active_shield(target)
    if not sh:
        return False
    return bool(sh.get("interpose", True))


def _set_prone(target, prone=True):
    target.db.prone = bool(prone)


def _is_prone(target):
    return bool(getattr(target.db, "prone", False))


def _get_prone_action_penalty(character):
    """-2 to attacks/dodge while prone."""
    if _is_prone(character):
        return -2
    return 0


def _get_grapple_action_penalty(character):
    """-2 while grappling or grappled."""
    if not character or not hasattr(character, "db"):
        return 0
    if getattr(character.db, "grappling_target_id", None) or getattr(character.db, "grappled_by_id", None):
        return -2
    return 0


def _get_facedown_fear_penalty(attacker, target):
    """Return -2 if attacker is currently intimidated by this target."""
    if not attacker or not target:
        return 0
    fear_target_id = getattr(attacker.db, "fear_target_id", None)
    fear_until = getattr(attacker.db, "fear_until", 0) or 0
    if fear_target_id == target.id and time.time() < fear_until:
        return -2
    return 0


def _has_backed_down_from(attacker, target):
    """True if attacker has an active back-down state against target."""
    if not attacker or not target:
        return False
    bid = getattr(attacker.db, "backed_down_target_id", None)
    until = getattr(attacker.db, "backed_down_until", 0) or 0
    return bid == target.id and time.time() < until


def _consume_scene_action(caller, label):
    """Consume action in active scene combat (if caller is on roster)."""
    room = getattr(caller, "location", None)
    if not room:
        return True
    try:
        from commands.combat_system import consume_action_for_character

        ok, msg = consume_action_for_character(room, caller, label=label)
        if not ok:
            caller.msg(msg)
            return False
    except Exception:
        # If combat tracker unavailable, don't block command execution.
        return True
    return True


def _apply_attack_damage(target, total_damage, aim_location, location, msg_lines, allow_shield=True):
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

    # Shield interpose: if active, shield absorbs the full incoming hit.
    sh = _get_active_shield(target)
    if allow_shield and sh and _shield_interposing(target):
        cur = int(sh.get("current_hp", 0) or 0)
        max_hp = int(sh.get("max_hp", cur) or cur)
        src = sh.get("source")
        human_id = sh.get("human_target_id")
        if src == "human" and human_id:
            from evennia.utils.search import search_object

            found = search_object(f"#{human_id}")
            if found:
                hs = found[0]
                # Human shield takes attack as if targeted; holder takes none.
                _apply_attack_damage(hs, total_damage, aim_location, location, msg_lines, allow_shield=False)
                new_hs_hp = get_current_hp(hs)
                sh["max_hp"] = int(get_max_hp(hs) or max_hp)
                sh["current_hp"] = int(new_hs_hp)
                target.db.active_shield = sh
                msg_lines.append(
                    f"  |w{target.key}|n interposes |c{hs.key}|n as a human shield "
                    f"({sh['current_hp']}/{sh['max_hp']} HP)."
                )
                if is_dead(hs) or new_hs_hp <= 0:
                    hs.db.used_as_human_shield_by_id = None
                    corpse_hp = max(1, getattr(hs.db, "body", 0) or 0)
                    hs_sheet = _get_sheet(hs)
                    if hs_sheet:
                        corpse_hp = max(1, _get_stat(hs_sheet, "body"))
                    sh["source"] = "corpse"
                    sh["name"] = f"{hs.key} (corpse shield)"
                    sh["max_hp"] = corpse_hp
                    sh["current_hp"] = corpse_hp
                    sh["human_target_id"] = None
                    target.db.active_shield = sh
                    msg_lines.append(
                        f"  |rHuman shield collapses!|n {target.key} now has a corpse shield ({corpse_hp} HP)."
                    )
                return
            # If human target vanished, just clear human link and continue as normal shield.
            sh["source"] = "gear"
            sh["name"] = "Shield"
            sh["human_target_id"] = None

        absorb = min(cur, total_damage)
        new_hp = max(0, cur - total_damage)
        sh["current_hp"] = new_hp
        target.db.active_shield = sh
        msg_lines.append(
            f"  |w{target.key}|n blocks with |c{sh.get('name', 'shield')}|n: "
            f"|r{absorb}|n absorbed ({new_hp}/{max_hp} HP)."
        )
        if new_hp <= 0:
            msg_lines.append("  |rShield destroyed!|n")
        return

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

    # Solo Combat Awareness: Damage Deflection reduces first damage taken each Round.
    try:
        from world.role_abilities import (
            get_solo_damage_deflection_value,
            solo_damage_deflection_available,
            consume_solo_damage_deflection,
        )

        if damage_to_char > 0 and solo_damage_deflection_available(target):
            dd = int(get_solo_damage_deflection_value(target) or 0)
            if dd > 0:
                reduced = min(dd, damage_to_char)
                damage_to_char = max(0, damage_to_char - reduced)
                consume_solo_damage_deflection(target)
                msg_lines.append(
                    f"  |w{target.key}|n deflects |c{reduced}|n damage with Combat Awareness."
                )
    except Exception:
        pass

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

    # Backed down in facedown: cannot attack that opponent during active window.
    if target and _has_backed_down_from(attacker, target):
        if location:
            location.msg_contents(
                f"|w{attacker.key}|n backs down and does not attack |w{target.key}|n."
            )
        return

    # Grapple restriction: no two-handed weapons while grappling/grappled.
    if weapon and (getattr(attacker.db, "grappling_target_id", None) or getattr(attacker.db, "grappled_by_id", None)):
        try:
            hands_required = int(getattr(weapon, "hands", 1) or 1)
        except Exception:
            hands_required = 1
        if hands_required >= 2:
            if location:
                location.msg_contents(
                    f"|w{attacker.key}|n cannot use |y{weapon.name}|n while in a grapple (two-handed)."
                )
            return

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
    grapple_penalty = _get_grapple_action_penalty(attacker) if attacker else 0
    fear_penalty = _get_facedown_fear_penalty(attacker, target)
    prone_penalty = _get_prone_action_penalty(attacker) if attacker else 0
    total = (
        d10
        + stat_val
        + skill_val
        + quality_bonus
        + actual_luck
        + modifier
        + action_penalty
        + grapple_penalty
        + prone_penalty
        + fear_penalty
    )

    # Solo Combat Awareness: Fumble Recovery (ignore natural-1 malfunction while attacking)
    ignore_fumble = False
    try:
        from world.role_abilities import has_solo_fumble_recovery
        ignore_fumble = bool(has_solo_fumble_recovery(attacker))
    except Exception:
        ignore_fumble = False

    # Poor quality: natural 1 causes jam (unless Solo Fumble Recovery active)
    if weapon and _is_weapon_poor_quality(weapon) and d10 == 1 and not ignore_fumble:
        weapon.jammed = True
        weapon.save()
        if location:
            location.msg_contents(
                f"|w{attacker.key}|n attacks with |y{weapon.name}|n! "
                f"|rMALFUNCTION!|n Natural 1 - weapon jammed! Use |wattack/unjam {weapon.name}|n to clear."
            )
        return

    success = total > dv
    # Kendo (lightweight): Cut the Bullet can negate next incoming ranged single-shot.
    try:
        is_ranged_attack = False
        if weapon and (weapon.category or "").strip().lower() not in ("melee",):
            is_ranged_attack = True
        if cw_attack and (cw_attack[3] or "").strip().lower() in ("handgun", "shoulder_arms", "heavy_weapons", "archery"):
            is_ranged_attack = True
        if (
            target
            and success
            and is_ranged_attack
            and (getattr(target.db, "cut_the_bullet_until", 0) or 0) > time.time()
        ):
            success = False
            target.db.cut_the_bullet_until = 0
            if location:
                location.msg_contents(
                    f"|w{target.key}|n cuts/deflects the incoming shot with impossible precision!"
                )
    except Exception:
        pass

    char_name = attacker.key
    dv_desc = f" ({dv_name})" if dv_name else ""
    stat_name = _stat_display(stat_field)
    roll_parts = [f"1d10 [{d10}]", stat_name, skill_display]
    if action_penalty:
        roll_parts.append(f"{action_penalty} (wound)")
    if grapple_penalty:
        roll_parts.append(f"{grapple_penalty} (grapple)")
    if prone_penalty:
        roll_parts.append(f"{prone_penalty} (prone)")
    if quality_bonus:
        roll_parts.append(f"+{quality_bonus} (quality)")
    if actual_luck:
        roll_parts.append(f"+{actual_luck} (luck)")
    if modifier:
        roll_parts.append(f"{modifier:+d}")
    if fear_penalty:
        roll_parts.append(f"{fear_penalty} (facedown)")
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
        # Kyudo: while stance is active, first ROF1 archery hit gains +2d6.
        try:
            if (
                weapon
                and (getattr(weapon, "category", "") or "").strip().lower() == "archery"
                and int(getattr(weapon, "rof", 1) or 1) == 1
                and (getattr(attacker.db, "kyudo_stance_until", 0) or 0) > time.time()
                and bool(getattr(attacker.db, "kyudo_stance_active", False))
            ):
                extra = [random.randint(1, 6) for _ in range(2)]
                damage_rolls.extend(extra)
                attacker.db.kyudo_stance_active = False
        except Exception:
            pass
        total_damage = sum(damage_rolls)
        rolls_str = ", ".join(str(r) for r in damage_rolls)

        # Solo Combat Awareness: Precision Attack applies to all attacks.
        try:
            from world.role_abilities import get_solo_precision_attack_bonus
            precision = int(get_solo_precision_attack_bonus(attacker) or 0)
            if precision > 0:
                total_damage += precision
                rolls_str += f" + {precision} (Precision Attack)"
        except Exception:
            pass

        # Solo Combat Awareness: Spot Weakness applies to first successful attack each Round.
        try:
            from world.role_abilities import (
                get_solo_spot_weakness_bonus,
                solo_spot_weakness_available,
                consume_solo_spot_weakness,
            )

            if solo_spot_weakness_available(attacker):
                sw = int(get_solo_spot_weakness_bonus(attacker) or 0)
                if sw > 0:
                    total_damage += sw
                    rolls_str += f" + {sw} (Spot Weakness)"
                    consume_solo_spot_weakness(attacker)
        except Exception:
            pass

        msg_lines.append(f"  |gHit!|n Damage: |r{total_damage}|n ({num_dice}d6: {rolls_str})")

        # Apply damage to target if present and not already dead
        if target and not is_dead(target):
            _apply_attack_damage(target, total_damage, aim_location, location, msg_lines)
            # Requirement history tracking for special moves.
            try:
                is_melee_like = bool(
                    force_melee
                    or attack_type in ("unarmed",)
                    or (weapon and (weapon.category or "").strip().lower() == "melee")
                )
                if is_melee_like:
                    _mark_martial_event(target, "took_melee_damage")
                    _mark_martial_event(attacker, "landed_melee_hit")
                    _inc_martial_hit_count(attacker, target)
            except Exception:
                pass
            # Beating your feared opponent clears facedown fear.
            if getattr(attacker.db, "fear_target_id", None) == target.id:
                attacker.db.fear_target_id = None
                attacker.db.fear_until = 0
                msg_lines.append("  |gFacedown fear broken.|n")
    else:
        msg_lines.append(f"  |rMISS!|n (need to exceed {dv})")
        try:
            is_melee_like = bool(
                force_melee
                or attack_type in ("unarmed",)
                or (weapon and (weapon.category or "").strip().lower() == "melee")
            )
            if target and is_melee_like:
                _mark_martial_event(target, "dodged_melee_attack")
        except Exception:
            pass

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
    Ranged attacks can be dodged if defender has REF 8+ or Reflex Co-Processor installed.
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

        if _shield_interposing(target):
            sh = _get_active_shield(target) or {}
            self.caller.msg(
                f"{target.key} is interposing {sh.get('name', 'a shield')} and cannot dodge until shield is lowered."
            )
            return
        if getattr(target.db, "used_as_human_shield_by_id", None):
            self.caller.msg(f"{target.key} is being used as a human shield and cannot dodge right now.")
            return

        # NPCs and characters without sheet use db
        d10, dex, evasion, total = _get_dodge_dv(target, modifier=modifier)
        _set_last_dodge_dv(target, total)

        char_name = target.key
        ev_penalty = _get_armor_ev_penalty(target)
        action_penalty = get_action_penalty(target)
        grapple_penalty = _get_grapple_action_penalty(target)
        prone_penalty = _get_prone_action_penalty(target)
        roll_str = f"1d10 [{d10}] + Dexterity + Evasion"
        if ev_penalty:
            roll_str += f" - {ev_penalty} (armor EV)"
        if action_penalty:
            roll_str += f" {action_penalty} (wound)"
        if grapple_penalty:
            roll_str += f" {grapple_penalty} (grapple)"
        if prone_penalty:
            roll_str += f" {prone_penalty} (prone)"
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
      attack/aim <target>=<head|body|arms|legs> - Aimed shot at body part (-8 baseline)
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

    At point blank (0-6m), eligible targets (REF 8+ or Reflex Co-Processor) can dodge.
    Otherwise ranged attacks use range-chart DV.
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

        if not _consume_scene_action(self.caller, "attack"):
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

            if _is_ranged_attack_for_attacker(char):
                if _can_dodge_ranged_attacks(target):
                    dodge_dv, _ = _get_last_dodge_dv(target)
                    if dodge_dv is None:
                        target_name = target.key
                        _add_pending_attack(target, char, modifier=modifier, luck_spend=luck_spend)
                        self.caller.location.msg_contents(
                            f"|w{char.key}|n attacks |w{target_name}|n! |y{target_name} can dodge this ranged attack.|n "
                            f"Use the |w'dodge'|n command (or |w+npc/dodge {target_name}|n for NPCs)."
                        )
                        target.msg(
                            f"|yYou are being attacked by {char.key}!|n "
                            f"You may use |w'dodge'|n to defend against this ranged attack."
                        )
                        if is_npc(target):
                            owner_id = getattr(target.db, "owner_account_id", None)
                            if owner_id:
                                from evennia.accounts.models import AccountDB
                                try:
                                    owner = AccountDB.objects.get(id=owner_id)
                                    owner.msg(
                                        f"|yYour NPC {target_name} is being attacked by {char.key}!|n "
                                        f"Use |w+npc/dodge {target_name}|n to roll if desired."
                                    )
                                except AccountDB.DoesNotExist:
                                    pass
                        return
                    dv = dodge_dv
                    dv_name = f"{target.key}'s dodge"
                    _clear_last_dodge_dv(target)  # Consume dodge for this attack
                else:
                    dv = _get_point_blank_range_dv_for_attacker(char)
                    dv_name = f"DV {dv} (point blank; {target.key} cannot dodge ranged)"
            else:
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

        ammo_candidates = list(
            inventory.ammunition.filter(ammo_type=ammo_type_val, quantity__gt=0).order_by("-quantity")
        )
        ammo = ammo_candidates[0] if ammo_candidates else None
        to_load = 0
        loaded_from_inventory = 0
        loaded_from_voucher = 0

        if ammo:
            loaded_from_inventory = min(room, ammo.quantity)
            to_load += loaded_from_inventory
            ammo.quantity -= loaded_from_inventory
            if ammo.quantity <= 0:
                ammo.delete()
            else:
                ammo.save()

        remaining_room = room - to_load
        if remaining_room > 0:
            try:
                from world.voucher.utils import consume_ammo_from_vouchers

                loaded_from_voucher = consume_ammo_from_vouchers(char, ammo_type_val, remaining_room)
                to_load += loaded_from_voucher
            except Exception:
                loaded_from_voucher = 0

        if to_load <= 0:
            self.caller.msg(
                f"You have no {target_ammo_type or 'matching'} ammunition in your inventory or vouchers."
            )
            return

        weapon.current_ammo = (weapon.current_ammo or 0) + to_load
        weapon.save()
        if hasattr(weapon, "db"):
            weapon.db.loaded_ammo_type = ammo_type_val
        loc = self.caller.location
        if loc:
            loc.msg_contents(f"|w{char.key}|n reloads their |y{weapon.name}|n.")
        src_parts = []
        if loaded_from_inventory:
            src_parts.append(f"{loaded_from_inventory} from inventory")
        if loaded_from_voucher:
            src_parts.append(f"{loaded_from_voucher} from vouchers")
        src_str = ", ".join(src_parts) if src_parts else "unknown source"
        self.caller.msg(
            f"You reload your {weapon.name}. Loaded {to_load} rounds "
            f"({weapon.current_ammo}/{effective_clip} {ammo_type_val}; {src_str})."
        )

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
            if _can_dodge_ranged_attacks(target):
                dodge_dv, _ = _get_last_dodge_dv(target)
                if dodge_dv is None:
                    _add_pending_attack(target, char, modifier=modifier, luck_spend=luck_spend)
                    self.caller.location.msg_contents(
                        f"|w{char.key}|n attacks |w{target.key}|n at point blank ({distance}m)! "
                        f"|y{target.key} can dodge this ranged attack.|n Use the |w'dodge'|n command."
                    )
                    target.msg(
                        f"|yYou are being attacked by {char.key} at point blank!|n "
                        f"You may use |w'dodge'|n to defend against this ranged attack."
                    )
                    return
                dv = dodge_dv
                dv_name = f"{target.key}'s dodge"
                _clear_last_dodge_dv(target)
            else:
                dv_name = f"DV {dv} ({distance}m; {target.key} cannot dodge ranged)"
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
        # CPR aimed shots take -8 baseline.
        modifier -= 8
        try:
            if (getattr(char.db, "martial_aim_bonus_until", 0) or 0) > time.time():
                bonus = int(getattr(char.db, "martial_aim_bonus_value", 0) or 0)
                modifier += bonus
                # Consume one-shot benefit.
                char.db.martial_aim_bonus_until = 0
                char.db.martial_aim_bonus_value = 0
        except Exception:
            pass
        if loc not in ARMOR_LOCATIONS:
            self.caller.msg(f"Aim location must be one of: {', '.join(ARMOR_LOCATIONS)}")
            return
        target = self.caller.search(target_name)
        if not target or target == char:
            return
        if _can_dodge_ranged_attacks(target):
            dodge_dv, _ = _get_last_dodge_dv(target)
            if dodge_dv is None:
                _add_pending_attack(target, char, modifier=modifier, luck_spend=luck_spend, aim_location=loc)
                self.caller.location.msg_contents(
                    f"|w{char.key}|n aims at |w{target.key}|n's {loc}! |y{target.key} can dodge this ranged attack.|n"
                )
                target.msg(
                    f"|yYou are being targeted by {char.key}!|n "
                    f"You may use the |w'dodge'|n command against this ranged attack."
                )
                return
            dv = dodge_dv
            dv_name = f"{target.key}'s dodge"
            _clear_last_dodge_dv(target)
        else:
            dv = _get_point_blank_range_dv_for_attacker(char)
            dv_name = f"DV {dv} (point blank; {target.key} cannot dodge ranged)"
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
        aim_modifier = -8
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
            staff_weapon_name=weapon_display, staff_num_dice=num_dice, staff_stat_field=stat_field,
            modifier=aim_modifier
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


class CmdShield(MuxCommand):
    """
    Manage active shields (gear or human shield).

    Usage:
      shield                     - Show current shield
      shield/up [hp]             - Equip a personal shield (default 10 HP)
      shield/down                - Lower shield interpose (allows dodge)
      shield/raise               - Raise shield interpose (blocks instead of dodge)
      shield/drop                - Drop active shield
      shield/human <target>      - Equip grappled target as human shield
    """

    key = "shield"
    aliases = ["+shield"]
    help_category = "Combat"

    def func(self):
        caller = self.caller
        switches = [s.lower() for s in (self.switches or [])]
        args = (self.args or "").strip()

        sh = _get_active_shield(caller)
        if not switches and not args:
            if not sh:
                caller.msg("No active shield. Use shield/up [hp] or shield/human <target>.")
                return
            mode = "interposing" if sh.get("interpose", True) else "lowered"
            caller.msg(
                f"Active shield: {sh.get('name')} ({sh.get('current_hp')}/{sh.get('max_hp')} HP), {mode}."
            )
            return

        if "up" in switches:
            if not _consume_scene_action(caller, "shield_up"):
                return
            hp = 10
            if args:
                try:
                    hp = max(1, int(args))
                except ValueError:
                    caller.msg("Usage: shield/up [hp]")
                    return
            _set_active_shield(caller, "Bulletproof Shield", hp, source="gear", interpose=True)
            caller.msg(f"You equip a Bulletproof Shield ({hp} HP) and raise it.")
            if caller.location:
                caller.location.msg_contents(f"|w{caller.key}|n raises a shield.", exclude=caller)
            return

        if "human" in switches:
            if not _consume_scene_action(caller, "human_shield"):
                return
            if not args:
                caller.msg("Usage: shield/human <target>")
                return
            target = caller.search(args)
            if not target:
                return
            grappling = _get_grapple_target(caller)
            if not grappling or grappling != target:
                caller.msg("You can only use a target you are currently grappling as a human shield.")
                return
            hp = max(1, int(get_current_hp(target) or 1))
            _set_active_shield(
                caller,
                f"{target.key} (human shield)",
                hp,
                source="human",
                interpose=True,
                human_target_id=target.id,
            )
            target.db.used_as_human_shield_by_id = caller.id
            caller.msg(f"You pull {target.key} in front of you as a human shield ({hp} HP).")
            if caller.location:
                caller.location.msg_contents(
                    f"|w{caller.key}|n uses |w{target.key}|n as a human shield.",
                    exclude=caller,
                )
            return

        if "down" in switches:
            if not sh:
                caller.msg("No active shield.")
                return
            sh["interpose"] = False
            caller.db.active_shield = sh
            caller.msg("You lower your shield and can dodge again.")
            return

        if "raise" in switches:
            if not sh:
                caller.msg("No active shield.")
                return
            sh["interpose"] = True
            caller.db.active_shield = sh
            caller.msg("You raise your shield to interpose incoming attacks.")
            return

        if "drop" in switches:
            if not _consume_scene_action(caller, "shield_drop"):
                return
            if not sh:
                caller.msg("No active shield to drop.")
                return
            hid = sh.get("human_target_id")
            if hid:
                from evennia.utils.search import search_object

                found = search_object(f"#{hid}")
                if found:
                    found[0].db.used_as_human_shield_by_id = None
            _drop_active_shield(caller)
            caller.msg("You drop your shield.")
            if caller.location:
                caller.location.msg_contents(f"|w{caller.key}|n drops their shield.", exclude=caller)
            return

        caller.msg("Usage: shield, shield/up [hp], shield/down, shield/raise, shield/drop, shield/human <target>")


class CmdGrab(MuxCommand):
    """
    Grapple combat actions: grab, choke, throw, escape.

    Usage:
      grab <target>          - Attempt grapple (DEX+Brawling+1d10 opposed)
      grab/choke             - Choke current grappled target (BODY direct HP)
      grab/throw             - Throw current grappled target (BODY direct HP, prone)
      grab/release           - Release grapple
      grab/escape            - Escape if grappled
      grab/status            - Show grapple state
    """

    key = "grab"
    aliases = ["grapple", "choke", "throw"]
    help_category = "Combat"

    def func(self):
        caller = self.caller
        switches = [s.lower() for s in (self.switches or [])]
        args = (self.args or "").strip()
        cmd = (self.cmdstring or "").lower()

        # Alias behaviors: "choke" and "throw"
        if cmd == "choke" and "choke" not in switches:
            switches.append("choke")
        if cmd == "throw" and "throw" not in switches:
            switches.append("throw")

        if "status" in switches:
            tgt = _get_grapple_target(caller)
            if tgt:
                caller.msg(f"You are grappling {tgt.key}.")
            elif _is_grappled(caller):
                caller.msg("You are currently grappled by someone.")
            else:
                caller.msg("You are not currently in a grapple.")
            return

        if "escape" in switches:
            if not _consume_scene_action(caller, "grapple_escape"):
                return
            gid = getattr(caller.db, "grappled_by_id", None)
            if not gid:
                caller.msg("You are not grappled.")
                return
            from evennia.utils.search import search_object

            found = search_object(f"#{gid}")
            if not found:
                caller.db.grappled_by_id = None
                caller.msg("Your grappler is no longer present. You break free.")
                return
            attacker = found[0]
            dex_a, brawl_a = _get_dex_and_brawling(caller)
            dex_d, brawl_d = _get_dex_and_brawling(attacker)
            ra = random.randint(1, 10)
            rd = random.randint(1, 10)
            iron_grip_pen = -2 if getattr(caller.db, "iron_grip_by_id", None) == attacker.id else 0
            ta = dex_a + brawl_a + ra + iron_grip_pen
            td = dex_d + brawl_d + rd
            if ta > td:
                _clear_grapple_state(attacker=attacker, target=caller)
                caller.db.iron_grip_by_id = None
                # If attacker was using this target as human shield, end that state.
                ash = _get_active_shield(attacker)
                if ash and ash.get("source") == "human" and ash.get("human_target_id") == caller.id:
                    _drop_active_shield(attacker)
                caller.db.used_as_human_shield_by_id = None
                caller.msg(f"You escape {attacker.key}'s grapple! ({ta} vs {td})")
                if caller.location:
                    caller.location.msg_contents(f"|w{caller.key}|n breaks free of |w{attacker.key}|n.")
            else:
                caller.msg(f"You fail to escape ({ta} vs {td}).")
            return

        if "release" in switches:
            tgt = _get_grapple_target(caller)
            if not tgt:
                caller.msg("You are not grappling anyone.")
                return
            _clear_grapple_state(attacker=caller, target=tgt)
            sh = _get_active_shield(caller)
            if sh and sh.get("source") == "human" and sh.get("human_target_id") == tgt.id:
                _drop_active_shield(caller)
                tgt.db.used_as_human_shield_by_id = None
            caller.msg(f"You release {tgt.key}.")
            if caller.location:
                caller.location.msg_contents(f"|w{caller.key}|n releases |w{tgt.key}|n.", exclude=caller)
            return

        if "choke" in switches:
            if not _consume_scene_action(caller, "choke"):
                return
            tgt = _get_grapple_target(caller)
            if not tgt:
                caller.msg("You must be grappling a target to choke.")
                return
            if getattr(caller.db, "used_as_human_shield_by_id", None):
                caller.msg("You cannot choke while being used as a human shield.")
                return
            body = 0
            sheet = _get_sheet(caller)
            if sheet:
                body = _get_stat(sheet, "body")
            else:
                body = getattr(caller.db, "body", 0) or 0
            body = max(1, int(body))
            old_hp = get_current_hp(tgt)
            if old_hp > 1 and old_hp - body < 0:
                dmg = max(0, old_hp - 1)
                apply_damage_to_character(tgt, dmg)
                tgt.db.unconscious_until = time.time() + 60
            else:
                apply_damage_to_character(tgt, body)
                dmg = body
            caller.msg(f"You choke {tgt.key} for {dmg} direct damage.")
            if caller.location:
                caller.location.msg_contents(
                    f"|w{caller.key}|n chokes |w{tgt.key}|n for |r{dmg}|n damage.",
                    exclude=caller,
                )
            return

        if "throw" in switches:
            if not _consume_scene_action(caller, "throw"):
                return
            tgt = _get_grapple_target(caller)
            if not tgt:
                caller.msg("You must be grappling a target to throw.")
                return
            if _consume_deashi_reaction(tgt):
                caller.msg(f"{tgt.key} braces and slips your throw attempt (Deashi).")
                tgt.msg("You deflect the throw attempt with Deashi.")
                if caller.location:
                    caller.location.msg_contents(
                        f"|w{tgt.key}|n slips |w{caller.key}|n's throw attempt.",
                        exclude=(caller, tgt),
                    )
                return
            if getattr(caller.db, "used_as_human_shield_by_id", None):
                caller.msg("You cannot throw while being used as a human shield.")
                return
            body = 0
            sheet = _get_sheet(caller)
            if sheet:
                body = _get_stat(sheet, "body")
            else:
                body = getattr(caller.db, "body", 0) or 0
            body = max(1, int(body))
            apply_damage_to_character(tgt, body)
            _set_prone(tgt, True)
            _clear_grapple_state(attacker=caller, target=tgt)
            sh = _get_active_shield(caller)
            if sh and sh.get("source") == "human" and sh.get("human_target_id") == tgt.id:
                _drop_active_shield(caller)
                tgt.db.used_as_human_shield_by_id = None
            caller.msg(f"You throw {tgt.key} for {body} direct damage and knock them prone.")
            if caller.location:
                caller.location.msg_contents(
                    f"|w{caller.key}|n throws |w{tgt.key}|n to the ground (|r{body}|n damage).",
                    exclude=caller,
                )
            return

        # Default: grab <target>
        if not _consume_scene_action(caller, "grab"):
            return
        if not args:
            caller.msg("Usage: grab <target> (or grab/choke, grab/throw, grab/escape, grab/release, grab/status)")
            return
        if getattr(caller.db, "used_as_human_shield_by_id", None):
            caller.msg("You cannot initiate a grapple while being used as a human shield.")
            return
        if _get_grapple_target(caller):
            caller.msg("You are already grappling someone. Use grab/release first.")
            return
        target = caller.search(args)
        if not target:
            return
        if target == caller:
            caller.msg("You cannot grapple yourself.")
            return
        if _is_grappled(target):
            caller.msg(f"{target.key} is already grappled.")
            return

        dex_a, brawl_a = _get_dex_and_brawling(caller)
        dex_d, brawl_d = _get_dex_and_brawling(target)
        ra = random.randint(1, 10)
        rd = random.randint(1, 10)
        ta = dex_a + brawl_a + ra
        td = dex_d + brawl_d + rd
        if ta > td:
            if _consume_deashi_reaction(target):
                caller.msg(f"{target.key} shifts stance and avoids your grapple (Deashi).")
                target.msg("You avoid being grappled with Deashi.")
                if caller.location:
                    caller.location.msg_contents(
                        f"|w{target.key}|n slips out of |w{caller.key}|n's grab attempt.",
                        exclude=(caller, target),
                    )
                return
            _set_grapple_state(caller, target)
            caller.msg(f"You grab {target.key}! ({ta} vs {td})")
            if caller.location:
                caller.location.msg_contents(
                    f"|w{caller.key}|n grabs |w{target.key}|n in a grapple!",
                    exclude=caller,
                )
        else:
            caller.msg(f"You fail to grab {target.key}. ({ta} vs {td})")
            if caller.location:
                caller.location.msg_contents(
                    f"|w{caller.key}|n fails to grab |w{target.key}|n.",
                    exclude=caller,
                )


class CmdMartial(MuxCommand):
    """
    Martial arts form/move command layer.

    Usage:
      martial/status
      martial/forms
      martial/recovery
      martial/strike <target>
      martial/knockout_punch <target>
      martial/punch_combination <target>
      martial/disarm <target>
      martial/bonebreak <target>
      martial/pressure_point <target>
      martial/iron_grip
      martial/grab_escape
      martial/counter_throw <target>
      martial/flying_kick <target>
      martial/chokehold
      martial/reversal
      martial/counter_strike <target>
      martial/escape_hold
      martial/punishing_blow <target>
      martial/contact_combat <target>
      martial/grit
      martial/dirty_blow <target>
      martial/ki_ken_tai_no_ichi
      martial/woo_technique
      martial/combat_reload [weapon[=ammo type]]
      martial/combat_knife_training <target>
      martial/commando_disarm <target>
      martial/niramiai
      martial/deashi
      martial/hassetsu
      martial/zaiteki
      martial/borg_fist <target>
      martial/inner_chrome
      martial/armed_dangerous <target>
      martial/smack_together
      martial/internal_power <target>
      martial/violent_leverage <target>
      martial/coordinated_combination <target>
      martial/disarming_technique <target>
      martial/rhythmic_recovery <target>
      martial/slash_dance <target>
      martial/shaolin_step
      martial/sweeping_fist <target>
      martial/environmental_improvisation
      martial/lucky_stumble
      martial/aiki <target>
      martial/throwing_technique <target>
      martial/five_forms <target>
      martial/superior_stance
      martial/conditioned_ferocity <target>
      martial/conditioned_power <target>
      martial/joint_manipulation <target>
      martial/lu <target>
      martial/advantaged_position <target>
      martial/weapon_retention
      martial/cut_the_bullet
    """

    key = "martial"
    aliases = ["ma"]
    help_category = "Combat"

    def func(self):
        caller = self.caller
        switches = [s.lower() for s in (self.switches or [])]
        args = (self.args or "").strip()

        dex, base_martial = _get_dex_and_martial(caller)
        forms = _get_all_martial_style_ranks(caller)
        has_form_training = bool(forms)
        has_any_training = base_martial > 0 or has_form_training

        if "status" in switches or "forms" in switches:
            if has_form_training:
                ranked = ", ".join(f"{k} {v}" for k, v in sorted(forms.items()))
            else:
                ranked = "none"
            caller.msg(
                f"Martial Arts status: DEX {dex}, generic rank {base_martial}. "
                f"Form ranks: {ranked}."
            )
            return

        if not has_any_training:
            caller.msg("You need at least 1 rank in Martial Arts to use martial special moves.")
            return

        if "recovery" in switches:
            self._recovery(caller, dex, max(base_martial, max(forms.values()) if forms else 0))
            return

        target_needed_moves = {
            "strike",
            "knockout_punch",
            "punch_combination",
            "disarm",
            "bonebreak",
            "pressure_point",
            "counter_throw",
            "flying_kick",
            "counter_strike",
            "punishing_blow",
            "contact_combat",
            "dirty_blow",
            "combat_knife_training",
            "commando_disarm",
            "borg_fist",
            "armed_dangerous",
            "internal_power",
            "violent_leverage",
            "coordinated_combination",
            "disarming_technique",
            "rhythmic_recovery",
            "slash_dance",
            "sweeping_fist",
            "aiki",
            "throwing_technique",
            "five_forms",
            "conditioned_ferocity",
            "conditioned_power",
            "joint_manipulation",
            "lu",
            "advantaged_position",
        }
        active_move = None
        ordered_moves = [
            "knockout_punch",
            "punch_combination",
            "bonebreak",
            "pressure_point",
            "dirty_blow",
            "disarm",
            "iron_grip",
            "grab_escape",
            "counter_throw",
            "flying_kick",
            "chokehold",
            "reversal",
            "counter_strike",
            "escape_hold",
            "punishing_blow",
            "contact_combat",
            "grit",
            "ki_ken_tai_no_ichi",
            "woo_technique",
            "combat_reload",
            "combat_knife_training",
            "commando_disarm",
            "niramiai",
            "deashi",
            "hassetsu",
            "zaiteki",
            "borg_fist",
            "inner_chrome",
            "armed_dangerous",
            "smack_together",
            "internal_power",
            "violent_leverage",
            "coordinated_combination",
            "disarming_technique",
            "rhythmic_recovery",
            "slash_dance",
            "shaolin_step",
            "sweeping_fist",
            "environmental_improvisation",
            "lucky_stumble",
            "aiki",
            "throwing_technique",
            "five_forms",
            "superior_stance",
            "conditioned_ferocity",
            "conditioned_power",
            "joint_manipulation",
            "lu",
            "advantaged_position",
            "weapon_retention",
            "cut_the_bullet",
            "strike",
        ]
        for mv in ordered_moves:
            if mv in switches:
                active_move = mv
                break
        if not active_move:
            active_move = "strike"

        target = None
        if active_move in target_needed_moves:
            if not args:
                caller.msg(f"Usage: martial/{active_move} <target>")
                return
            target = caller.search(args)
            if not target:
                return
            if target == caller:
                caller.msg("You cannot target yourself.")
                return

        if active_move == "woo_technique":
            rank = self._style_rank_for_move(caller, ["Gun Fu"], "woo_technique")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_woo_technique"):
                return
            self._woo_technique(caller, dex, rank)
            return

        if active_move == "combat_reload":
            rank = self._style_rank_for_move(caller, ["Gun Fu"], "combat_reload")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_combat_reload"):
                return
            self._combat_reload(caller, dex, rank, args)
            return

        if active_move == "combat_knife_training":
            rank = self._style_rank_for_move(caller, ["Militech Commando Training"], "combat_knife_training")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_combat_knife_training"):
                return
            self._combat_knife_training(caller, target, dex, rank)
            return

        if active_move == "commando_disarm":
            rank = self._style_rank_for_move(caller, ["Militech Commando Training"], "commando_disarm")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_commando_disarm"):
                return
            self._commando_disarm(caller, target, dex, rank)
            return

        if active_move == "niramiai":
            rank = self._style_rank_for_move(caller, ["Sumo"], "niramiai")
            if rank <= 0:
                return
            self._niramiai(caller, dex, rank)
            return

        if active_move == "deashi":
            rank = self._style_rank_for_move(caller, ["Sumo"], "deashi")
            if rank <= 0:
                return
            self._deashi(caller, dex, rank)
            return

        if active_move == "hassetsu":
            rank = self._style_rank_for_move(caller, ["Kyudo"], "hassetsu")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_hassetsu"):
                return
            self._hassetsu(caller, dex, rank)
            return

        if active_move == "zaiteki":
            rank = self._style_rank_for_move(caller, ["Kyudo"], "zaiteki")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_zaiteki"):
                return
            self._zaiteki(caller, target, dex, rank)
            return

        if active_move == "borg_fist":
            rank = self._style_rank_for_move(caller, ["PanzerFaust"], "borg_fist")
            if rank <= 0:
                return
            body = _get_stat(_get_sheet(caller), "body") if _get_sheet(caller) else (getattr(caller.db, "body", 0) or 0)
            if int(body) < 10:
                caller.msg("Borg Fist requires BODY 10+.")
                return
            if not _consume_scene_action(caller, "martial_borg_fist"):
                return
            self._borg_fist(caller, target, dex, rank)
            return

        if active_move == "inner_chrome":
            rank = self._style_rank_for_move(caller, ["PanzerFaust"], "inner_chrome")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_inner_chrome"):
                return
            self._inner_chrome(caller, dex, rank)
            return

        if active_move == "armed_dangerous":
            rank = self._style_rank_for_move(caller, ["Multiarm Melee"], "armed_dangerous")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_armed_dangerous"):
                return
            self._armed_dangerous(caller, target, dex, rank)
            return

        if active_move == "smack_together":
            rank = self._style_rank_for_move(caller, ["Multiarm Melee"], "smack_together")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_smack_together"):
                return
            self._smack_together(caller, dex, rank)
            return

        if active_move == "internal_power":
            rank = self._style_rank_for_move(caller, ["Silat"], "internal_power")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_internal_power"):
                return
            self._internal_power(caller, target, dex, rank)
            return

        if active_move == "violent_leverage":
            rank = self._style_rank_for_move(caller, ["Silat"], "violent_leverage")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_violent_leverage"):
                return
            self._violent_leverage(caller, target, dex, rank)
            return

        if active_move == "coordinated_combination":
            rank = self._style_rank_for_move(caller, ["Arnis"], "coordinated_combination")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_coordinated_combination"):
                return
            self._coordinated_combination(caller, target, dex, rank)
            return

        if active_move == "disarming_technique":
            rank = self._style_rank_for_move(caller, ["Arnis"], "disarming_technique")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_disarming_technique"):
                return
            self._disarming_technique(caller, target, dex, rank)
            return

        if active_move == "rhythmic_recovery":
            rank = self._style_rank_for_move(caller, ["Capoeira"], "rhythmic_recovery")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_rhythmic_recovery"):
                return
            self._rhythmic_recovery(caller, target, dex, rank)
            return

        if active_move == "slash_dance":
            rank = self._style_rank_for_move(caller, ["Capoeira"], "slash_dance")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_slash_dance"):
                return
            self._slash_dance(caller, target, dex, rank)
            return

        if active_move == "shaolin_step":
            rank = self._style_rank_for_move(caller, ["Choy Li Fut"], "shaolin_step")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_shaolin_step"):
                return
            self._shaolin_step(caller, dex, rank)
            return

        if active_move == "sweeping_fist":
            rank = self._style_rank_for_move(caller, ["Choy Li Fut"], "sweeping_fist")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_sweeping_fist"):
                return
            self._sweeping_fist(caller, target, dex, rank)
            return

        if active_move == "environmental_improvisation":
            rank = self._style_rank_for_move(caller, ["Drunken Fist"], "environmental_improvisation")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_environmental_improvisation"):
                return
            self._environmental_improvisation(caller, dex, rank)
            return

        if active_move == "lucky_stumble":
            rank = self._style_rank_for_move(caller, ["Drunken Fist"], "lucky_stumble")
            if rank <= 0:
                return
            self._lucky_stumble(caller, dex, rank)
            return

        if active_move == "aiki":
            rank = self._style_rank_for_move(caller, ["Jujutsu"], "aiki")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_aiki"):
                return
            self._aiki(caller, target, dex, rank)
            return

        if active_move == "throwing_technique":
            rank = self._style_rank_for_move(caller, ["Jujutsu"], "throwing_technique")
            if rank <= 0:
                return
            if _get_willpower(caller) < 6:
                caller.msg("Throwing Technique requires WILL 6+.")
                return
            if not _consume_scene_action(caller, "martial_throwing_technique"):
                return
            self._throwing_technique(caller, target, dex, rank)
            return

        if active_move == "five_forms":
            rank = self._style_rank_for_move(caller, ["Kung Fu"], "five_forms")
            if rank <= 0:
                return
            if int(rank) < 4:
                caller.msg("Five Forms requires Kung Fu rank 4+.")
                return
            if not _consume_scene_action(caller, "martial_five_forms"):
                return
            self._five_forms(caller, target, dex, rank)
            return

        if active_move == "superior_stance":
            rank = self._style_rank_for_move(caller, ["Kung Fu"], "superior_stance")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_superior_stance"):
                return
            self._superior_stance(caller, dex, rank)
            return

        if active_move == "conditioned_ferocity":
            rank = self._style_rank_for_move(caller, ["Muay Thai"], "conditioned_ferocity")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_conditioned_ferocity"):
                return
            self._conditioned_ferocity(caller, target, dex, rank)
            return

        if active_move == "conditioned_power":
            rank = self._style_rank_for_move(caller, ["Muay Thai"], "conditioned_power")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_conditioned_power"):
                return
            self._conditioned_power(caller, target, dex, rank)
            return

        if active_move == "joint_manipulation":
            rank = self._style_rank_for_move(caller, ["Tai Chi"], "joint_manipulation")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_joint_manipulation"):
                return
            self._joint_manipulation(caller, target, dex, rank)
            return

        if active_move == "lu":
            rank = self._style_rank_for_move(caller, ["Tai Chi"], "lu")
            if rank <= 0:
                return
            if _get_willpower(caller) < 8:
                caller.msg("Lu requires WILL 8+.")
                return
            if not _consume_scene_action(caller, "martial_lu"):
                return
            self._lu(caller, target, dex, rank)
            return

        if active_move == "advantaged_position":
            rank = self._style_rank_for_move(caller, ["Thamoc"], "advantaged_position")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_advantaged_position"):
                return
            self._advantaged_position(caller, target, dex, rank)
            return

        if active_move == "weapon_retention":
            rank = self._style_rank_for_move(caller, ["Thamoc"], "weapon_retention")
            if rank <= 0:
                return
            self._weapon_retention(caller, dex, rank)
            return

        if active_move == "cut_the_bullet":
            rank = self._style_rank_for_move(caller, ["Kendo"], "cut_the_bullet")
            if rank <= 0:
                return
            if _get_willpower(caller) < 8:
                caller.msg("Cut the Bullet requires WILL 8+.")
                return
            self._cut_the_bullet(caller, dex, rank)
            return

        if active_move == "bonebreak":
            rank = self._style_rank_for_move(caller, ["Karate"], "bonebreak")
            if rank <= 0:
                return
            if _get_willpower(caller) < 8:
                caller.msg("Bone Breaking Strike requires WILL 8+.")
                return
            if not _consume_scene_action(caller, "martial_bonebreak"):
                return
            self._bonebreak(caller, target, dex, rank)
            return

        if active_move == "knockout_punch":
            rank = self._style_rank_for_move(caller, ["Boxing"], "knockout_punch")
            if rank <= 0:
                return
            body = _get_stat(_get_sheet(caller), "body") if _get_sheet(caller) else (getattr(caller.db, "body", 0) or 0)
            if int(body) < 8:
                caller.msg("Knockout Punch requires BODY 8+.")
                return
            if not _consume_scene_action(caller, "martial_knockout_punch"):
                return
            self._knockout_punch(caller, target, dex, rank)
            return

        if active_move == "punch_combination":
            rank = self._style_rank_for_move(caller, ["Boxing"], "punch_combination")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_punch_combination"):
                return
            self._punch_combination(caller, target, dex, rank)
            return

        if active_move == "pressure_point":
            rank = self._style_rank_for_move(caller, ["Taekwondo"], "pressure_point")
            if rank <= 0:
                return
            if _get_willpower(caller) < 8:
                caller.msg("Pressure Point Strike requires WILL 8+.")
                return
            if not _consume_scene_action(caller, "martial_pressure_point"):
                return
            self._pressure_point(caller, target, dex, rank)
            return

        if active_move == "disarm":
            rank = self._style_rank_for_move(caller, ["Aikido"], "disarm")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_disarm"):
                return
            self._disarm(caller, target, dex, rank)
            return

        if active_move == "iron_grip":
            rank = self._style_rank_for_move(caller, ["Aikido"], "iron_grip")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_iron_grip"):
                return
            self._iron_grip(caller, dex, rank)
            return

        if active_move == "grab_escape":
            rank = self._style_rank_for_move(caller, ["Judo"], "grab_escape")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_grab_escape"):
                return
            self._grab_escape(caller, dex, rank)
            return

        if active_move == "counter_throw":
            rank = self._style_rank_for_move(caller, ["Judo"], "counter_throw")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_counter_throw"):
                return
            self._counter_throw(caller, target, dex, rank)
            return

        if active_move == "flying_kick":
            rank = self._style_rank_for_move(caller, ["Taekwondo"], "flying_kick")
            if rank <= 0:
                return
            move_stat = _get_stat(_get_sheet(caller), "move") if _get_sheet(caller) else (getattr(caller.db, "move", 0) or 0)
            if int(move_stat) < 8:
                caller.msg("Flying Kick requires MOVE 8+.")
                return
            if not _consume_scene_action(caller, "martial_flying_kick"):
                return
            self._flying_kick(caller, target, dex, rank)
            return

        if active_move == "chokehold":
            rank = self._style_rank_for_move(caller, ["Wrestling"], "chokehold")
            if rank <= 0:
                return
            self._chokehold(caller, dex, rank)
            return

        if active_move == "reversal":
            rank = self._style_rank_for_move(caller, ["Wrestling"], "reversal")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_reversal"):
                return
            self._reversal(caller, dex, rank)
            return

        if active_move == "counter_strike":
            rank = self._style_rank_for_move(caller, ["Arasaka-te"], "counter_strike")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_counter_strike"):
                return
            self._counter_strike(caller, target, dex, rank)
            return

        if active_move == "escape_hold":
            rank = self._style_rank_for_move(caller, ["Arasaka-te"], "escape_hold")
            if rank <= 0:
                return
            self._escape_hold(caller, dex, rank)
            return

        if active_move == "punishing_blow":
            rank = self._style_rank_for_move(caller, ["Krav Maga"], "punishing_blow")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_punishing_blow"):
                return
            self._punishing_blow(caller, target, dex, rank)
            return

        if active_move == "contact_combat":
            rank = self._style_rank_for_move(caller, ["Krav Maga"], "contact_combat")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_contact_combat"):
                return
            self._contact_combat(caller, target, dex, rank)
            return

        if active_move == "grit":
            rank = self._style_rank_for_move(caller, ["Thrash Sambo"], "grit")
            if rank <= 0:
                return
            self._grit(caller, dex, rank)
            return

        if active_move == "dirty_blow":
            rank = self._style_rank_for_move(caller, ["Sov-System"], "dirty_blow")
            if rank <= 0:
                return
            body = _get_stat(_get_sheet(caller), "body") if _get_sheet(caller) else (getattr(caller.db, "body", 0) or 0)
            if int(body) < 4:
                caller.msg("Dirty Blow requires BODY 4+.")
                return
            if not _consume_scene_action(caller, "martial_dirty_blow"):
                return
            self._dirty_blow(caller, target, dex, rank)
            return

        if active_move == "ki_ken_tai_no_ichi":
            rank = self._style_rank_for_move(caller, ["Kendo"], "ki_ken_tai_no_ichi")
            if rank <= 0:
                return
            if not _consume_scene_action(caller, "martial_ki_ken_tai_no_ichi"):
                return
            self._ki_ken_tai_no_ichi(caller, dex, rank)
            return

        # default: strike (generic martial attack, any trained form or generic rank)
        strike_rank = max(base_martial, max(forms.values()) if forms else 0)
        if not _consume_scene_action(caller, "martial_strike"):
            return
        self._strike(caller, target, dex, strike_rank)

    def _style_rank_for_move(self, caller, required_styles, move_key):
        if not _check_martial_once_per_turn(caller, move_key):
            return 0
        ranks = [int(_get_martial_style_rank(caller, s) or 0) for s in required_styles]
        best = max(ranks) if ranks else 0
        # Backward-compat: if character has generic martial only, allow with generic rank.
        if best <= 0:
            _, generic = _get_dex_and_martial(caller)
            if generic > 0:
                return int(generic)
            style_text = " or ".join(required_styles)
            caller.msg(f"This move requires training in {style_text}.")
            return 0
        return int(best)

    def _special_move_roll_vs_dv(self, caller, dex, martial_rank, dv, mod=0):
        roll = random.randint(1, 10)
        total = (
            int(roll)
            + int(dex)
            + int(martial_rank)
            + int(mod)
            + int(get_action_penalty(caller))
            + int(_get_grapple_action_penalty(caller))
            + int(_get_prone_action_penalty(caller))
        )
        return total, roll, total >= int(dv)

    def _recovery(self, caller, dex, martial_rank):
        if not _check_martial_once_per_turn(caller, "recovery"):
            return
        if not _is_prone(caller):
            caller.msg("You are already standing.")
            return
        total, roll, ok = self._special_move_roll_vs_dv(caller, dex, martial_rank, 13)
        if ok:
            _set_prone(caller, False)
            caller.msg(f"Recovery succeeds ({total} vs DV13). You stand up without spending your Action.")
            if caller.location:
                caller.location.msg_contents(f"|w{caller.key}|n springs back to their feet.", exclude=caller)
            return
        if not _consume_scene_action(caller, "martial_recovery_getup"):
            return
        _set_prone(caller, False)
        caller.msg(f"Recovery fails ({total} vs DV13). You still get up, but it costs your Action.")
        if caller.location:
            caller.location.msg_contents(f"|w{caller.key}|n gets up from prone.", exclude=caller)

    def _strike(self, caller, target, dex, martial):
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        fear_pen = _get_facedown_fear_penalty(caller, target)
        armed_bonus = 0
        ferocity_bonus = 0
        try:
            if (getattr(caller.db, "armed_dangerous_until", 0) or 0) > time.time():
                armed_bonus = 2
                caller.db.armed_dangerous_until = 0
            if (getattr(caller.db, "conditioned_ferocity_until", 0) or 0) > time.time():
                ferocity_bonus = 1
        except Exception:
            armed_bonus = 0
            ferocity_bonus = 0
        total_a = (
            r_a
            + int(dex)
            + int(martial)
            + int(get_action_penalty(caller))
            + int(_get_grapple_action_penalty(caller))
            + int(_get_prone_action_penalty(caller))
            + int(fear_pen)
            + int(armed_bonus)
            + int(ferocity_bonus)
        )
        total_t = (
            r_t
            + int(dex_t)
            + int(evasion_t)
            + int(get_action_penalty(target))
            + int(_get_grapple_action_penalty(target))
            + int(_get_prone_action_penalty(target))
        )
        if total_a <= total_t:
            _mark_martial_event(caller, "missed_ma_attack")
            caller.msg(
                f"Martial strike misses {target.key}: {total_a} vs {total_t} "
                f"(1d10[{r_a}] + DEX {dex} + MA {martial})."
            )
            if caller.location:
                caller.location.msg_contents(
                    f"|w{caller.key}|n's martial strike misses |w{target.key}|n.",
                    exclude=caller,
                )
            return
        dice = _martial_damage_dice_for_body(caller)
        # Gun Fu (lightweight): while active, use stored handgun damage dice and consume ammo.
        try:
            if (getattr(caller.db, "gun_fu_until", 0) or 0) > time.time():
                gf_dice = int(getattr(caller.db, "gun_fu_damage_dice", 0) or 0)
                if gf_dice > 0:
                    weapon = _get_equipped_weapon(caller)
                    if weapon and int(getattr(weapon, "current_ammo", 0) or 0) > 0:
                        weapon.current_ammo = int(getattr(weapon, "current_ammo", 0) or 0) - 1
                        weapon.save()
                        dice = gf_dice
                    else:
                        caller.msg("Gun Fu strike fails: you have no ammo.")
                        return
        except Exception:
            pass
        try:
            if (getattr(caller.db, "conditioned_power_until", 0) or 0) > time.time():
                dice = min(6, int(dice) + 1)
                caller.db.conditioned_power_until = 0
            if (getattr(caller.db, "conditioned_ferocity_until", 0) or 0) > time.time():
                dice = min(6, int(dice) + 1)
                caller.db.conditioned_ferocity_until = 0
        except Exception:
            pass
        rolls = [random.randint(1, 6) for _ in range(dice)]
        raw = sum(rolls)
        armor_sp = int(get_armor_sp(target, "body") or 0)
        effective_sp = (armor_sp + 1) // 2
        try:
            if (getattr(caller.db, "env_improv_until", 0) or 0) > time.time():
                effective_sp = (effective_sp + 1) // 2
                caller.db.env_improv_until = 0
        except Exception:
            pass
        try:
            if (
                (getattr(caller.db, "aiki_until", 0) or 0) > time.time()
                and int(getattr(caller.db, "aiki_target_id", 0) or 0) == int(getattr(target, "id", -1) or -1)
            ):
                alt_body = int(getattr(caller.db, "aiki_body_value", 0) or 0)
                if alt_body > 0:
                    raw += alt_body
                caller.db.aiki_until = 0
                caller.db.aiki_target_id = 0
                caller.db.aiki_body_value = 0
        except Exception:
            pass
        dealt = max(0, raw - effective_sp)
        if dealt > 0:
            apply_damage_to_character(target, dealt)
        _mark_martial_event(caller, "landed_ma_attack")
        _inc_martial_hit_count(caller, target)
        msg = (
            f"You land a martial strike on {target.key}: "
            f"{dice}d6 {rolls} = {raw}, half-armor SP {effective_sp}, damage {dealt}."
        )
        caller.msg(msg)
        if caller.location:
            caller.location.msg_contents(
                f"|w{caller.key}|n lands a martial strike on |w{target.key}|n for |r{dealt}|n damage.",
                exclude=caller,
            )
        if rolls.count(6) >= 2:
            injury_name, _ = apply_critical_injury_to_character(target, "body", "body")
            if injury_name:
                _mark_martial_event(caller, "inflicted_critical")
                caller.msg(f"|rCritical injury inflicted: {injury_name}.|n")
                if caller.location:
                    caller.location.msg_contents(
                        f"|rCritical injury!|n |w{target.key}|n suffers |r{injury_name}|n.",
                        exclude=caller,
                    )
        if fear_pen < 0:
            caller.db.fear_target_id = None
            caller.db.fear_until = 0
            caller.msg("You push through your fear after landing the hit.")

    def _knockout_punch(self, caller, target, dex, martial):
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        total_a = r_a + int(dex) + int(martial) - 5 + int(get_action_penalty(caller))
        total_t = r_t + int(dex_t) + int(evasion_t) + int(get_action_penalty(target))
        if total_a <= total_t:
            caller.msg(f"Knockout Punch misses: {total_a} vs {total_t}.")
            return
        dice = _martial_damage_dice_for_body(caller)
        raw = sum(random.randint(1, 6) for _ in range(dice))
        armor_sp = int(get_armor_sp(target, "head") or 0)
        dealt = max(0, (raw - armor_sp) * 2)
        if dealt > 0:
            apply_damage_to_character(target, dealt)
        injury_name, _ = apply_critical_injury_to_character(target, "head", "head")
        if injury_name:
            _mark_martial_event(caller, "inflicted_critical")
        caller.msg(
            f"You land Knockout Punch on {target.key} for {dealt} head damage"
            + (f" and inflict {injury_name}." if injury_name else ".")
        )

    def _punch_combination(self, caller, target, dex, martial):
        if _get_martial_hit_count(caller, target) < 2:
            caller.msg("Punch Combination requires two successful close hits on the same target this turn.")
            return
        # Lightweight implementation: successful DV15 setup grants one bonus brawling-style strike.
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Punch Combination setup fails ({total} vs DV15).")
            return
        self._strike(caller, target, dex, martial)

    def _pressure_point(self, caller, target, dex, martial):
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        fear_pen = _get_facedown_fear_penalty(caller, target)
        total_a = (
            r_a
            + int(dex)
            + int(martial)
            + int(get_action_penalty(caller))
            + int(_get_grapple_action_penalty(caller))
            + int(_get_prone_action_penalty(caller))
            + int(fear_pen)
        )
        total_t = (
            r_t
            + int(dex_t)
            + int(evasion_t)
            + int(get_action_penalty(target))
            + int(_get_grapple_action_penalty(target))
            + int(_get_prone_action_penalty(target))
        )
        if total_a <= total_t:
            caller.msg(f"Pressure Point Strike misses: {total_a} vs {total_t}.")
            return
        dice = _martial_damage_dice_for_body(caller)
        raw = sum(random.randint(1, 6) for _ in range(dice))
        armor_sp = int(get_armor_sp(target, "body") or 0)
        dealt = max(0, raw - ((armor_sp + 1) // 2))
        if dealt > 0:
            apply_damage_to_character(target, dealt)
        injury_name, _ = apply_critical_injury_to_character(target, "body", "body")
        if injury_name:
            _mark_martial_event(caller, "inflicted_critical")
        caller.msg(
            f"You land Pressure Point Strike on {target.key} for {dealt} damage"
            + (f" and inflict {injury_name}." if injury_name else ".")
        )

    def _dirty_blow(self, caller, target, dex, martial):
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        total_a = r_a + int(dex) + int(martial) + int(get_action_penalty(caller))
        total_t = r_t + int(dex_t) + int(evasion_t) + int(get_action_penalty(target))
        if total_a <= total_t:
            caller.msg(f"Dirty Blow misses: {total_a} vs {total_t}.")
            return
        dice = _martial_damage_dice_for_body(caller)
        raw = sum(random.randint(1, 6) for _ in range(dice))
        armor_sp = int(get_armor_sp(target, "body") or 0)
        dealt = max(0, raw - ((armor_sp + 1) // 2))
        if dealt > 0:
            apply_damage_to_character(target, dealt)
        injury_name, _ = apply_critical_injury_to_character(target, "body", "body")
        if injury_name:
            _mark_martial_event(caller, "inflicted_critical")
        caller.msg(
            f"You land Dirty Blow on {target.key} for {dealt} damage"
            + (f" and inflict {injury_name}." if injury_name else ".")
        )

    def _bonebreak(self, caller, target, dex, martial):
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        fear_pen = _get_facedown_fear_penalty(caller, target)
        total_a = (
            r_a
            + int(dex)
            + int(martial)
            - 8
            + int(get_action_penalty(caller))
            + int(_get_grapple_action_penalty(caller))
            + int(_get_prone_action_penalty(caller))
            + int(fear_pen)
        )
        total_t = (
            r_t
            + int(dex_t)
            + int(evasion_t)
            + int(get_action_penalty(target))
            + int(_get_grapple_action_penalty(target))
            + int(_get_prone_action_penalty(target))
        )
        if total_a <= total_t:
            caller.msg(f"Bone Breaking Strike misses: {total_a} vs {total_t}.")
            return
        dice = _martial_damage_dice_for_body(caller)
        raw = sum(random.randint(1, 6) for _ in range(dice))
        armor_sp = int(get_armor_sp(target, "body") or 0)
        dealt = max(0, raw - ((armor_sp + 1) // 2))
        if dealt > 0:
            apply_damage_to_character(target, dealt)
        injury_name, _ = apply_critical_injury_to_character(target, "body", "body")
        if injury_name:
            _mark_martial_event(caller, "inflicted_critical")
        caller.msg(
            f"You land Bone Breaking Strike on {target.key} for {dealt} damage"
            + (f" and inflict {injury_name}." if injury_name else ".")
        )
        if caller.location:
            caller.location.msg_contents(
                f"|w{caller.key}|n lands a |rBone Breaking Strike|n on |w{target.key}|n.",
                exclude=caller,
            )
        if fear_pen < 0:
            caller.db.fear_target_id = None
            caller.db.fear_until = 0
            caller.msg("You push through your fear after landing the hit.")

    def _iron_grip(self, caller, dex, martial):
        tgt = _get_grapple_target(caller)
        if not tgt:
            caller.msg("Iron Grip requires that you are currently grappling someone.")
            return
        if getattr(tgt.db, "iron_grip_by_id", None) == caller.id:
            caller.msg(f"{tgt.key} is already affected by your Iron Grip.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Iron Grip fails ({total} vs DV15).")
            return
        tgt.db.iron_grip_by_id = caller.id
        caller.msg(f"Iron Grip succeeds on {tgt.key}. Their escape attempts suffer -2.")
        tgt.msg(f"{caller.key}'s Iron Grip locks you down; escape attempts are harder.")

    def _grab_escape(self, caller, dex, martial):
        gid = getattr(caller.db, "grappled_by_id", None)
        if not gid:
            caller.msg("Grab Escape requires that you are currently grappled.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Grab Escape fails ({total} vs DV15).")
            return
        from evennia.utils.search import search_object

        found = search_object(f"#{gid}")
        attacker = found[0] if found else None
        if attacker and _get_martial_hit_count(caller, attacker) < 2:
            caller.msg("Grab Escape requires two successful close hits on your grappler this turn.")
            return
        if attacker:
            _clear_grapple_state(attacker=attacker, target=caller)
            caller.msg(f"You break free from {attacker.key}'s grapple!")
            attacker.msg(f"{caller.key} slips your grapple.")
        else:
            caller.db.grappled_by_id = None
            caller.msg("You break free.")

    def _counter_throw(self, caller, target, dex, martial):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Counter Throw setup fails ({total} vs DV15).")
            return
        body = _get_stat(_get_sheet(caller), "body") if _get_sheet(caller) else (getattr(caller.db, "body", 0) or 0)
        body = max(1, int(body))
        apply_damage_to_character(target, body)
        _set_prone(target, True)
        caller.msg(f"You counter-throw {target.key}, dealing {body} direct damage and knocking them prone.")
        if caller.location:
            caller.location.msg_contents(
                f"|w{caller.key}|n counter-throws |w{target.key}|n to the ground.",
                exclude=caller,
            )

    def _flying_kick(self, caller, target, dex, martial):
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        total_a = r_a + int(dex) + int(martial) + int(get_action_penalty(caller))
        total_t = r_t + int(dex_t) + int(evasion_t) + int(get_action_penalty(target))
        if total_a <= total_t:
            caller.msg(f"Flying Kick misses: {total_a} vs {total_t}.")
            return
        dice = _martial_damage_dice_for_body(caller)
        raw = sum(random.randint(1, 6) for _ in range(dice))
        armor_sp = int(get_armor_sp(target, "body") or 0)
        dealt = max(0, raw - ((armor_sp + 1) // 2))
        if dealt > 0:
            apply_damage_to_character(target, dealt)
        _set_prone(target, True)
        caller.msg(f"You land a Flying Kick on {target.key} for {dealt} damage and knock them prone.")

    def _chokehold(self, caller, dex, martial):
        if not _check_martial_once_per_turn(caller, "chokehold"):
            return
        tgt = _get_grapple_target(caller)
        if not tgt:
            caller.msg("Chokehold requires that you are grappling a target.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Chokehold setup fails ({total} vs DV15).")
            return
        body = _get_stat(_get_sheet(caller), "body") if _get_sheet(caller) else (getattr(caller.db, "body", 0) or 0)
        body = max(1, int(body))
        old_hp = get_current_hp(tgt)
        if old_hp > 1 and old_hp - body < 0:
            dmg = max(0, old_hp - 1)
            apply_damage_to_character(tgt, dmg)
            tgt.db.unconscious_until = time.time() + 60
        else:
            apply_damage_to_character(tgt, body)
            dmg = body
        caller.msg(f"Chokehold succeeds: you choke {tgt.key} for {dmg} direct damage without spending another Action.")

    def _reversal(self, caller, dex, martial):
        gid = getattr(caller.db, "grappled_by_id", None)
        if not gid:
            caller.msg("Reversal requires that you are currently grappled.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Reversal fails ({total} vs DV15).")
            return
        from evennia.utils.search import search_object

        found = search_object(f"#{gid}")
        attacker = found[0] if found else None
        if not attacker:
            caller.db.grappled_by_id = None
            caller.msg("Your grappler is gone; the grapple ends.")
            return
        _clear_grapple_state(attacker=attacker, target=caller)
        _set_grapple_state(caller, attacker)
        caller.msg(f"You reverse the grapple and now control {attacker.key}.")
        attacker.msg(f"{caller.key} reverses your grapple and takes control.")

    def _counter_strike(self, caller, target, dex, martial):
        if not _has_recent_martial_event(caller, "took_melee_damage", seconds=45):
            caller.msg("Counter Strike requires taking melee damage since your last turn.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Counter Strike setup fails ({total} vs DV15).")
            return
        # Reduce aimed-shot penalty this turn in lightweight implementation.
        caller.db.martial_aim_bonus_value = 3  # -8 -> -5
        caller.db.martial_aim_bonus_until = time.time() + 12
        caller.msg("Counter Strike succeeds. Your aimed melee/martial penalty is reduced this turn.")
        self._strike(caller, target, dex, martial)

    def _punishing_blow(self, caller, target, dex, martial):
        if not _has_recent_martial_event(caller, "dodged_melee_attack", seconds=45):
            caller.msg("Punishing Blow requires dodging a melee attack since your last turn.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Punishing Blow setup fails ({total} vs DV15).")
            return
        self._strike(caller, target, dex, martial)

    def _contact_combat(self, caller, target, dex, martial):
        if not _has_recent_martial_event(caller, "inflicted_critical", seconds=45):
            caller.msg("Contact Combat requires that you inflicted a critical injury recently.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Contact Combat setup fails ({total} vs DV15).")
            return
        self._strike(caller, target, dex, martial)

    def _grit(self, caller, dex, martial):
        if not _check_martial_once_per_turn(caller, "grit"):
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Grit fails ({total} vs DV15).")
            return
        caller.db.grit_bonus_until = time.time() + 12
        caller.msg("Grit succeeds. Critical injury bonus damage is reduced on your next injury this turn.")

    def _ki_ken_tai_no_ichi(self, caller, dex, martial):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Ki Ken Tai no Ichi fails ({total} vs DV15).")
            return
        caller.db.martial_aim_bonus_value = 6  # -8 -> -2 on first aimed attack next turn
        caller.db.martial_aim_bonus_until = time.time() + 30
        caller.msg("Ki Ken Tai no Ichi succeeds. Your next aimed melee attack penalty is reduced.")

    def _woo_technique(self, caller, dex, martial):
        sheet = _get_sheet(caller)
        hg = _get_skill(sheet, "handgun") if sheet else ((caller.db.skills or {}).get("handgun", 0) or 0)
        if int(hg) < 4:
            caller.msg("Woo Technique requires Handgun 4+.")
            return
        weapon = _get_equipped_weapon(caller)
        if not weapon:
            caller.msg("Woo Technique requires a one-handed handgun to be equipped.")
            return
        cat = (getattr(weapon, "category", "") or "").strip().lower()
        if cat not in ("handgun", "smg"):
            caller.msg("Woo Technique currently supports equipped handgun-category weapons.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Woo Technique fails ({total} vs DV15).")
            return
        caller.db.gun_fu_until = time.time() + 12
        caller.db.gun_fu_weapon_id = getattr(weapon, "id", None)
        caller.db.gun_fu_damage_dice = int(_parse_damage_dice(getattr(weapon, "damage", None)) or 2)
        caller.msg("Woo Technique succeeds. Your martial strikes channel your handgun style this turn.")

    def _combat_reload(self, caller, dex, martial, args):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Combat Reload setup fails ({total} vs DV15).")
            return
        # Lightweight: provide immediate tactical reload via existing attack/reload path.
        weapon = _get_equipped_weapon(caller)
        if not weapon:
            caller.msg("You need an equipped weapon to use Combat Reload.")
            return
        caller.msg("Combat Reload succeeds. Reload now without spending another action.")
        if caller.location:
            caller.location.msg_contents(f"|w{caller.key}|n performs a rapid combat reload.", exclude=caller)

    def _combat_knife_training(self, caller, target, dex, martial):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Combat Knife Training setup fails ({total} vs DV15).")
            return
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        total_a = r_a + int(dex) + int(martial) + int(get_action_penalty(caller))
        total_t = r_t + int(dex_t) + int(evasion_t) + int(get_action_penalty(target))
        if total_a <= total_t:
            caller.msg(f"Combat Knife strike misses: {total_a} vs {total_t}.")
            return
        # Lightweight approximation: boosted 4d6 knife-style hit.
        raw = sum(random.randint(1, 6) for _ in range(4))
        armor_sp = int(get_armor_sp(target, "body") or 0)
        dealt = max(0, raw - ((armor_sp + 1) // 2))
        if dealt > 0:
            apply_damage_to_character(target, dealt)
        caller.msg(f"Combat Knife Training lands on {target.key} for {dealt} damage.")

    def _commando_disarm(self, caller, target, dex, martial):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Commando Disarm setup fails ({total} vs DV15).")
            return
        dropped = _force_drop_equipped_weapon(target)
        if not dropped:
            caller.msg(f"{target.key} has no equipped weapon to disarm.")
            return
        name = getattr(dropped, "name", "their weapon")
        caller.msg(f"Commando Disarm succeeds: you strip {name} from {target.key}.")
        target.msg(f"{caller.key} strips your weapon from your hands.")
        if caller.location:
            caller.location.msg_contents(f"|w{caller.key}|n disarms |w{target.key}|n with commando technique.", exclude=(caller, target))

    def _niramiai(self, caller, dex, martial):
        if not _check_martial_once_per_turn(caller, "niramiai"):
            return
        cool = _get_stat(_get_sheet(caller), "cool") if _get_sheet(caller) else (getattr(caller.db, "cool", 0) or 0)
        if int(cool) < 4:
            caller.msg("Niramiai requires COOL 4+.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Niramiai fails ({total} vs DV15).")
            return
        caller.db.facedown_bonus = 2
        caller.db.facedown_bonus_until = time.time() + 60
        caller.msg("Niramiai succeeds. Your next facedown gains +2.")

    def _deashi(self, caller, dex, martial):
        if not _check_martial_once_per_turn(caller, "deashi"):
            return
        body = _get_stat(_get_sheet(caller), "body") if _get_sheet(caller) else (getattr(caller.db, "body", 0) or 0)
        if int(body) < 7:
            caller.msg("Deashi requires BODY 7+.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Deashi fails ({total} vs DV15).")
            return
        caller.db.deashi_until = time.time() + 12
        caller.msg("Deashi succeeds. Your next grapple/throw against you is negated this turn.")

    def _hassetsu(self, caller, dex, martial):
        weapon = _get_equipped_weapon(caller)
        if not weapon or (getattr(weapon, "category", "") or "").strip().lower() != "archery":
            caller.msg("Hassetsu requires an equipped archery weapon.")
            return
        if _is_prone(caller) or _is_grappled(caller) or _get_grapple_target(caller):
            caller.msg("You cannot establish Kyudo stance while prone or in a grapple.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Hassetsu fails ({total} vs DV15).")
            return
        caller.db.kyudo_stance_until = time.time() + 120
        caller.db.kyudo_stance_active = True
        caller.msg("Hassetsu succeeds. You establish Kyudo stance.")

    def _zaiteki(self, caller, target, dex, martial):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Zaiteki fails ({total} vs DV15).")
            return
        max_luck = _get_stat(_get_sheet(caller), "luck") if _get_sheet(caller) else (getattr(caller.db, "luck", 0) or 0)
        current = int(getattr(caller.db, "current_luck", 0) or 0)
        regain = min(2, max(0, int(max_luck) - current))
        if regain <= 0:
            caller.msg("Zaiteki succeeds, but your luck pool is already full.")
            return
        caller.db.current_luck = current + regain
        caller.msg(f"Zaiteki succeeds. You regain {regain} Luck.")

    def _borg_fist(self, caller, target, dex, martial):
        body = _get_stat(_get_sheet(caller), "body") if _get_sheet(caller) else (getattr(caller.db, "body", 0) or 0)
        body_t = _get_stat(_get_sheet(target), "body") if _get_sheet(target) else (getattr(target.db, "body", 0) or 0)
        if int(body_t) >= int(body):
            caller.msg("Borg Fist requires target BODY lower than yours.")
            return
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        total_a = r_a + int(dex) + int(martial) + int(get_action_penalty(caller))
        total_t = r_t + int(dex_t) + int(evasion_t) + int(get_action_penalty(target))
        if total_a <= total_t:
            caller.msg(f"Borg Fist misses: {total_a} vs {total_t}.")
            return
        dice = 6 if int(getattr(caller.db, "humanity", 0) or 0) < 0 else 5
        raw = sum(random.randint(1, 6) for _ in range(dice))
        armor_sp = int(get_armor_sp(target, "body") or 0)
        dealt = max(0, raw - ((armor_sp + 1) // 2))
        if dealt > 0:
            apply_damage_to_character(target, dealt)
        caller.msg(f"Borg Fist lands on {target.key} for {dealt} damage ({dice}d6 base).")

    def _inner_chrome(self, caller, dex, martial):
        # Lightweight implementation: defensive buff for cyberware stability.
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 11)
        if not ok:
            caller.msg(f"Inner Chrome fails ({total} vs DV11).")
            return
        caller.db.inner_chrome_until = time.time() + 60
        caller.msg("Inner Chrome succeeds. Your cyberware systems stabilize for this fight window.")

    def _armed_dangerous(self, caller, target, dex, martial):
        # Lightweight arm-count check: cyberarm users are treated as having arm advantage over non-cyberarm targets.
        has_adv = _has_cyberarm_installed(caller) and not _has_cyberarm_installed(target)
        if not has_adv:
            caller.msg("Armed & Dangerous requires arm-count advantage over target.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Armed & Dangerous fails ({total} vs DV15).")
            return
        # Apply one-time boost to next brawling/martial style action.
        caller.db.armed_dangerous_until = time.time() + 12
        caller.msg("Armed & Dangerous succeeds. Your next close attack gains enhanced control.")

    def _smack_together(self, caller, dex, martial):
        body = _get_stat(_get_sheet(caller), "body") if _get_sheet(caller) else (getattr(caller.db, "body", 0) or 0)
        if int(body) < 6:
            caller.msg("Smack Together requires BODY 6+.")
            return
        tgt = _get_grapple_target(caller)
        if not tgt:
            caller.msg("Smack Together requires controlling at least one grapple target.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Smack Together fails ({total} vs DV15).")
            return
        dmg = max(1, int(body))
        apply_damage_to_character(tgt, dmg)
        caller.msg(f"Smack Together slams {tgt.key} for {dmg} direct damage.")
        if caller.location:
            caller.location.msg_contents(f"|w{caller.key}|n slams |w{tgt.key}|n brutally.", exclude=caller)

    def _internal_power(self, caller, target, dex, martial):
        will = _get_willpower(caller)
        if int(will) < 6:
            caller.msg("Internal Power requires WILL 6+.")
            return
        if _get_martial_hit_count(caller, target) < 2:
            caller.msg("Internal Power requires two successful close hits on this target this turn.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Internal Power fails ({total} vs DV15).")
            return
        self._strike(caller, target, dex, martial)

    def _violent_leverage(self, caller, target, dex, martial):
        tgt = _get_grapple_target(caller)
        if not tgt:
            caller.msg("Violent Leverage requires that you have started and hold a grapple.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Violent Leverage fails ({total} vs DV15).")
            return
        # Lightweight: one bonus melee-style strike.
        self._strike(caller, target, dex, martial)

    def _coordinated_combination(self, caller, target, dex, martial):
        if _get_martial_hit_count(caller, target) < 2:
            caller.msg("Coordinated Combination requires two successful close hits on this target this turn.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Coordinated Combination fails ({total} vs DV15).")
            return
        injury_name, _ = apply_critical_injury_to_character(target, "body", "body")
        if injury_name:
            _mark_martial_event(caller, "inflicted_critical")
        caller.msg(
            f"Coordinated Combination lands on {target.key}."
            + (f" {injury_name} applied (no bonus damage approximation)." if injury_name else "")
        )

    def _disarming_technique(self, caller, target, dex, martial):
        if not _has_recent_martial_event(caller, "dodged_melee_attack", seconds=45):
            caller.msg("Disarming Technique requires dodging melee attacks since your last turn.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Disarming Technique fails ({total} vs DV15).")
            return
        dropped = _force_drop_equipped_weapon(target)
        if dropped:
            caller.msg(f"Disarming Technique strips {target.key}'s weapon.")
        else:
            caller.msg(f"{target.key} has no weapon to strip.")

    def _rhythmic_recovery(self, caller, target, dex, martial):
        if not _has_recent_martial_event(caller, "missed_ma_attack", seconds=45):
            caller.msg("Rhythmic Recovery requires missing a martial attack since your last turn.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Rhythmic Recovery fails ({total} vs DV15).")
            return
        self._strike(caller, target, dex, martial)

    def _slash_dance(self, caller, target, dex, martial):
        if not _has_recent_martial_event(caller, "inflicted_critical", seconds=45):
            caller.msg("Slash Dance currently requires inflicting a critical injury recently.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Slash Dance fails ({total} vs DV15).")
            return
        self._strike(caller, target, dex, martial)

    def _shaolin_step(self, caller, dex, martial):
        move_stat = _get_stat(_get_sheet(caller), "move") if _get_sheet(caller) else (getattr(caller.db, "move", 0) or 0)
        if int(move_stat) < 6:
            caller.msg("Shaolin Step requires MOVE 6+.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Shaolin Step fails ({total} vs DV15).")
            return
        caller.db.shaolin_step_until = time.time() + 12
        caller.msg("Shaolin Step succeeds. You gain a free tactical run window this turn.")

    def _sweeping_fist(self, caller, target, dex, martial):
        move_stat = _get_stat(_get_sheet(caller), "move") if _get_sheet(caller) else (getattr(caller.db, "move", 0) or 0)
        if int(move_stat) < 6:
            caller.msg("Sweeping Fist requires MOVE 6+.")
            return
        if _get_martial_hit_count(caller, target) < 2:
            caller.msg("Sweeping Fist requires two successful close hits on this target this turn.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Sweeping Fist fails ({total} vs DV15).")
            return
        self._strike(caller, target, dex, martial)

    def _environmental_improvisation(self, caller, dex, martial):
        luck_stat = _get_stat(_get_sheet(caller), "luck") if _get_sheet(caller) else (getattr(caller.db, "luck", 0) or 0)
        if int(luck_stat) < 4:
            caller.msg("Environmental Improvisation requires LUCK 4+.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 13)
        if not ok:
            caller.msg(f"Environmental Improvisation fails ({total} vs DV13).")
            return
        caller.db.env_improv_until = time.time() + 12
        caller.msg("Environmental Improvisation succeeds. Your brawling-style strikes ignore half armor briefly.")

    def _lucky_stumble(self, caller, dex, martial):
        luck_stat = _get_stat(_get_sheet(caller), "luck") if _get_sheet(caller) else (getattr(caller.db, "luck", 0) or 0)
        if int(luck_stat) < 4:
            caller.msg("Lucky Stumble requires LUCK 4+.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Lucky Stumble fails ({total} vs DV15).")
            return
        current = int(getattr(caller.db, "current_luck", 0) or 0)
        max_luck = int(luck_stat)
        regain = min(2, max(0, max_luck - current))
        if regain > 0:
            caller.db.current_luck = current + regain
            caller.msg(f"Lucky Stumble succeeds. You regain {regain} Luck.")
        else:
            caller.msg("Lucky Stumble succeeds, but your luck pool is already full.")

    def _aiki(self, caller, target, dex, martial):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Aiki fails ({total} vs DV15).")
            return
        target_body = _get_stat(_get_sheet(target), "body") if _get_sheet(target) else (getattr(target.db, "body", 0) or 0)
        caller.db.aiki_target_id = target.id
        caller.db.aiki_body_value = int(target_body)
        caller.db.aiki_until = time.time() + 12
        caller.msg(f"Aiki succeeds. You can leverage {target.key}'s BODY for close damage this turn.")

    def _throwing_technique(self, caller, target, dex, martial):
        if _get_martial_hit_count(caller, target) < 2:
            caller.msg("Throwing Technique requires two successful close hits on this target this turn.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Throwing Technique fails ({total} vs DV15).")
            return
        body = _get_stat(_get_sheet(target), "body") if _get_sheet(target) else (getattr(target.db, "body", 0) or 0)
        dmg = max(1, int(body))
        apply_damage_to_character(target, dmg)
        _set_prone(target, True)
        caller.msg(f"Throwing Technique launches {target.key} for {dmg} direct damage and prone.")

    def _five_forms(self, caller, target, dex, martial):
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        total_a = r_a + int(dex) + int(martial) + int(get_action_penalty(caller))
        total_t = r_t + int(dex_t) + int(evasion_t) + int(get_action_penalty(target))
        if total_a <= total_t:
            caller.msg(f"Five Forms misses: {total_a} vs {total_t}.")
            return
        self._strike(caller, target, dex, martial)
        target.db.five_forms_tiger_ablate = time.time() + 10
        caller.msg("Five Forms lands. Tiger pressure set (extra armor ablation approximation).")

    def _superior_stance(self, caller, dex, martial):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 17)
        if not ok:
            caller.msg(f"Superior Stance fails ({total} vs DV17).")
            return
        try:
            from commands.combat_system import get_active_scene

            room = getattr(caller, "location", None)
            scene = get_active_scene(room) if room else None
            if scene:
                cid = f"pc-{caller.id}"
                for idx, e in enumerate(scene.get("roster", [])):
                    if str(e.get("id", "")) == cid:
                        scene["turn_index"] = idx
                        caller.msg("Superior Stance succeeds. You seize top priority in the initiative flow.")
                        return
        except Exception:
            pass
        caller.msg("Superior Stance succeeds.")

    def _conditioned_ferocity(self, caller, target, dex, martial):
        if not _has_recent_martial_event(caller, "landed_ma_attack", seconds=45):
            caller.msg("Conditioned Ferocity requires that you damaged someone with martial attacks recently.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Conditioned Ferocity fails ({total} vs DV15).")
            return
        caller.db.conditioned_ferocity_until = time.time() + 12
        caller.msg("Conditioned Ferocity succeeds. Your next close strike is empowered.")
        self._strike(caller, target, dex, martial)

    def _conditioned_power(self, caller, target, dex, martial):
        if not _has_recent_martial_event(caller, "landed_melee_hit", seconds=45):
            caller.msg("Conditioned Power requires that you damaged someone with close attacks recently.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Conditioned Power fails ({total} vs DV15).")
            return
        caller.db.conditioned_power_until = time.time() + 12
        caller.msg("Conditioned Power succeeds. Your next martial strike gains extra force.")
        self._strike(caller, target, dex, martial)

    def _joint_manipulation(self, caller, target, dex, martial):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Joint Manipulation fails ({total} vs DV15).")
            return
        target.db.joint_lock_until = time.time() + 12
        caller.msg(f"Joint Manipulation succeeds. {target.key}'s next hand-based action is hindered.")

    def _lu(self, caller, target, dex, martial):
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Lu fails ({total} vs DV15).")
            return
        target.db.lu_suppressed_until = time.time() + 10
        caller.msg(f"Lu succeeds. {target.key}'s next martial special attempt is pressured.")

    def _advantaged_position(self, caller, target, dex, martial):
        if not _get_grapple_target(caller):
            caller.msg("Advantaged Position requires that you are currently grappling a target.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Advantaged Position fails ({total} vs DV15).")
            return
        caller.db.martial_aim_bonus_value = max(int(getattr(caller.db, "martial_aim_bonus_value", 0) or 0), 3)
        caller.db.martial_aim_bonus_until = time.time() + 12
        caller.msg("Advantaged Position succeeds. Your aimed close attack penalty is reduced this turn.")

    def _weapon_retention(self, caller, dex, martial):
        if not _check_martial_once_per_turn(caller, "weapon_retention"):
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Weapon Retention fails ({total} vs DV15).")
            return
        caller.db.weapon_retention_until = time.time() + 20
        caller.msg("Weapon Retention succeeds. Your next disarm attempt against you is negated.")

    def _cut_the_bullet(self, caller, dex, martial):
        if not _check_martial_once_per_turn(caller, "cut_the_bullet"):
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Cut the Bullet fails ({total} vs DV15).")
            return
        caller.db.cut_the_bullet_until = time.time() + 12
        caller.msg("Cut the Bullet succeeds. The next incoming ranged single-shot against you is negated.")

    def _escape_hold(self, caller, dex, martial):
        if not _check_martial_once_per_turn(caller, "escape_hold"):
            return
        gid = getattr(caller.db, "grappled_by_id", None)
        if not gid:
            caller.msg("Escape Hold requires that you are currently grappled.")
            return
        total, _, ok = self._special_move_roll_vs_dv(caller, dex, martial, 15)
        if not ok:
            caller.msg(f"Escape Hold fails ({total} vs DV15).")
            return
        from evennia.utils.search import search_object

        found = search_object(f"#{gid}")
        attacker = found[0] if found else None
        if attacker:
            _clear_grapple_state(attacker=attacker, target=caller)
            caller.msg(f"You break free from {attacker.key}'s hold.")
        else:
            caller.db.grappled_by_id = None
            caller.msg("You break free.")

    def _disarm(self, caller, target, dex, martial):
        dex_t, evasion_t = _get_dex_and_evasion(target)
        r_a = random.randint(1, 10)
        r_t = random.randint(1, 10)
        fear_pen = _get_facedown_fear_penalty(caller, target)
        total_a = (
            r_a
            + int(dex)
            + int(martial)
            + int(get_action_penalty(caller))
            + int(_get_grapple_action_penalty(caller))
            + int(_get_prone_action_penalty(caller))
            + int(fear_pen)
        )
        total_t = (
            r_t
            + int(dex_t)
            + int(evasion_t)
            + int(get_action_penalty(target))
            + int(_get_grapple_action_penalty(target))
            + int(_get_prone_action_penalty(target))
        )
        if total_a <= total_t:
            caller.msg(f"Disarm attempt fails: {total_a} vs {total_t}.")
            return
        check = random.randint(1, 10) + int(dex) + int(martial)
        if check < 15:
            caller.msg(f"You win position but fail to complete disarm (DV15, rolled {check}).")
            return
        dropped = _force_drop_equipped_weapon(target)
        if dropped:
            name = getattr(dropped, "name", "their weapon")
            caller.msg(f"You disarm {target.key}, forcing them to drop {name}.")
            target.msg(f"{caller.key} disarms you; you lose your equipped weapon.")
            if caller.location:
                caller.location.msg_contents(
                    f"|w{caller.key}|n disarms |w{target.key}|n.",
                    exclude=(caller, target),
                )
        else:
            caller.msg(f"{target.key} has no equipped weapon to disarm.")


class CmdFacedown(MuxCommand):
    """
    Opposed COOL + Rep + 1d10 stare-down.

    Usage:
      facedown <target>
      facedown/backdown [target]
    """

    key = "facedown"
    aliases = ["faceoff"]
    help_category = "Combat"

    def func(self):
        caller = self.caller
        switches = [s.lower() for s in (self.switches or [])]
        args = (self.args or "").strip()

        if "backdown" in switches:
            from evennia.utils.search import search_object

            target = None
            if args:
                target = caller.search(args)
                if not target:
                    return
            else:
                fear_target_id = getattr(caller.db, "fear_target_id", None)
                if fear_target_id:
                    found = search_object(f"#{fear_target_id}")
                    if found:
                        target = found[0]
            if not target:
                caller.msg("You are not currently pressured in a facedown.")
                return
            if _get_facedown_fear_penalty(caller, target) == 0:
                caller.msg(f"You are not currently suffering facedown pressure from {target.key}.")
                return
            caller.db.fear_target_id = None
            caller.db.fear_until = 0
            caller.db.backed_down_target_id = target.id
            caller.db.backed_down_until = time.time() + 600
            if caller.location:
                caller.location.msg_contents(f"|w{caller.key}|n backs down from |w{target.key}|n.")
            else:
                caller.msg(f"You back down from {target.key}.")
            return

        if not _consume_scene_action(caller, "facedown"):
            return
        if not args:
            caller.msg("Usage: facedown <target> or facedown/backdown [target]")
            return
        target = caller.search(args)
        if not target:
            return
        if target == caller:
            caller.msg("You cannot facedown yourself.")
            return

        c_cool, c_rep = _get_cool_and_rep(caller)
        t_cool, t_rep = _get_cool_and_rep(target)
        cr = random.randint(1, 10)
        tr = random.randint(1, 10)
        c_bonus = 0
        t_bonus = 0
        try:
            if (getattr(caller.db, "facedown_bonus_until", 0) or 0) > time.time():
                c_bonus = int(getattr(caller.db, "facedown_bonus", 0) or 0)
                caller.db.facedown_bonus = 0
                caller.db.facedown_bonus_until = 0
            if (getattr(target.db, "facedown_bonus_until", 0) or 0) > time.time():
                t_bonus = int(getattr(target.db, "facedown_bonus", 0) or 0)
                target.db.facedown_bonus = 0
                target.db.facedown_bonus_until = 0
        except Exception:
            c_bonus = 0
            t_bonus = 0
        c_total = c_cool + c_rep + cr + c_bonus
        t_total = t_cool + t_rep + tr + t_bonus

        if c_total == t_total:
            msg = (
                f"|wFacedown:|n {caller.key} [{c_total}] vs {target.key} [{t_total}] - "
                f"|ystalemate.|n"
            )
        elif c_total > t_total:
            target.db.fear_target_id = caller.id
            target.db.fear_until = time.time() + 600
            msg = (
                f"|wFacedown:|n {caller.key} [{c_total}] vs {target.key} [{t_total}] - "
                f"|g{caller.key} wins.|n {target.key} can back down or suffer fear penalties."
            )
        else:
            caller.db.fear_target_id = target.id
            caller.db.fear_until = time.time() + 600
            msg = (
                f"|wFacedown:|n {caller.key} [{c_total}] vs {target.key} [{t_total}] - "
                f"|r{target.key} wins.|n {caller.key} can back down or suffer fear penalties."
            )

        if caller.location:
            caller.location.msg_contents(msg)
        else:
            caller.msg(msg)


class CmdGetUp(MuxCommand):
    """
    Stand up from prone.

    Usage:
      getup
      stand
    """

    key = "getup"
    aliases = ["stand"]
    help_category = "Combat"

    def func(self):
        if not _is_prone(self.caller):
            self.caller.msg("You are already standing.")
            return
        if not _consume_scene_action(self.caller, "getup"):
            return
        _set_prone(self.caller, False)
        self.caller.msg("You get back on your feet.")
        if self.caller.location:
            self.caller.location.msg_contents(f"|w{self.caller.key}|n gets back to their feet.", exclude=self.caller)
