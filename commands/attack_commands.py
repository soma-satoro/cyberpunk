"""
Attack and Dodge commands for Cyberpunk Red combat.

Attack: Rolls attack (stat + skill vs DV) and damage. DV can be specified directly
or taken from a target's dodge roll.

Dodge: Rolls 1d10 + Dexterity + Evasion; result becomes the DV for attacks against you.
"""

import random
import time
from evennia.commands.default.muxcommand import MuxCommand
from world.utils.character_utils import is_character_approved
from world.utils.difficulty_values import parse_dv
from world.equipment_data import get_weapon_damage_dice, get_weapon_by_name
from world.combat_rules import (
    get_dv_for_range,
    POINT_BLANK_RANGE,
    ARMOR_LOCATIONS,
    is_splash_weapon,
    is_shotgun_zone_weapon,
)
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


def _get_weapon_attack_info(weapon):
    """Get (stat, skill, skill_display, num_dice) for a Weapon model."""
    cat = (weapon.category or "").strip().lower()
    mapping = WEAPON_SKILL_MAP.get(cat)
    if not mapping:
        mapping = WEAPON_SKILL_MAP.get("handgun")  # fallback
    stat_field, skill_field, skill_display = mapping
    num_dice = _parse_damage_dice(getattr(weapon, "damage", None))
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


def _get_dodge_dv(target):
    """Roll dodge for target, return (d10, dex, evasion, total). Applies EV penalty from worn armor."""
    dex, evasion = _get_dex_and_evasion(target)
    d10 = random.randint(1, 10)
    ev_penalty = _get_armor_ev_penalty(target)
    total = d10 + dex + evasion - ev_penalty
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


def _add_pending_attack(target, attacker, staff_override=None):
    """Add attacker to target's pending attacks list (target must dodge first).
    staff_override: optional dict with staff_stat, staff_skill, etc. for staff attacks."""
    pending = list(getattr(target.db, "pending_attacks", []) or [])
    if attacker.id not in pending:
        pending.append(attacker.id)
    target.db.pending_attacks = pending
    if staff_override:
        overrides = dict(getattr(target.db, "pending_attack_overrides", {}) or {})
        overrides[attacker.id] = staff_override
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
            mult = 4 if weapon and "assault rifle" in (weapon.name or "").lower() else 3
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


def execute_attack_roll(attacker, target, dv, dv_name, location, aim_location=None, force_melee=False,
                       staff_stat=None, staff_skill=None, staff_skill_display=None, staff_weapon_name=None, staff_num_dice=None, staff_stat_field=None):
    """
    Execute the attack roll and damage. Broadcasts to location.
    Caller must ensure attacker has character_sheet and target is valid.
    Staff override: pass staff_stat, staff_skill, staff_skill_display, staff_weapon_name, staff_num_dice.
    """
    sheet = _get_sheet(attacker)
    if not sheet and not (staff_stat is not None and staff_skill is not None):
        return

    weapon = _get_equipped_weapon(attacker)
    cw_attack = _get_active_cyberware_weapon(attacker)

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
        has_cyberarm = getattr(sheet, "has_cyberarm", False) or False
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
        has_cyberarm = getattr(sheet, "has_cyberarm", False) or False
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
    total = d10 + stat_val + skill_val
    success = total > dv

    char_name = attacker.key
    dv_desc = f" ({dv_name})" if dv_name else ""
    stat_name = _stat_display(stat_field)
    roll_result = f"1d10 [{d10}] + {stat_name} + {skill_display} = {total} vs DV {dv}{dv_desc}"

    at_target = f" at |w{target.key}|n" if target else ""
    msg_lines = [
        f"|w{char_name}|n attacks{at_target} with |y{weapon_name}|n!",
        f"  Roll: {roll_result}",
    ]

    if success:
        damage_rolls = [random.randint(1, 6) for _ in range(num_dice)]
        total_damage = sum(damage_rolls)
        rolls_str = ", ".join(str(r) for r in damage_rolls)
        msg_lines.append(f"  |gHit!|n Damage: |r{total_damage}|n ({num_dice}d6: {rolls_str})")
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
      dodge
      dodge as <name>   - Roll dodge for another (yourself, or an NPC you own)

    When someone attacks you, they'll use your last dodge result as the DV.
    """

    key = "dodge"
    help_category = "Combat"

    def func(self):
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before using the dodge command.")
            return

        args = (self.args or "").strip()
        if args.lower().startswith("as "):
            target_name = args[3:].strip()
            if not target_name:
                self.caller.msg("Usage: dodge as <name>")
                return
            target = self.caller.search(target_name, global_search=True)
            if not target:
                return
            if not _can_roll_dodge_for(self.caller, target):
                self.caller.msg(f"You cannot roll dodge for {target.key}.")
                return
        else:
            target = self.caller

        # NPCs and characters without sheet use db
        d10, dex, evasion, total = _get_dodge_dv(target)
        _set_last_dodge_dv(target, total)

        char_name = target.key
        ev_penalty = _get_armor_ev_penalty(target)
        roll_str = f"1d10 [{d10}] + Dexterity + Evasion"
        if ev_penalty:
            roll_str += f" - {ev_penalty} (armor EV)"
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
            for attacker, staff_override in pending:
                kwargs = {}
                if staff_override and staff_override.get("stat") is not None and staff_override.get("skill") is not None:
                    kwargs = {
                        "staff_stat": staff_override["stat"],
                        "staff_skill": staff_override["skill"],
                        "staff_skill_display": staff_override.get("skill_display"),
                        "staff_weapon_name": staff_override.get("weapon_name"),
                        "staff_num_dice": staff_override.get("num_dice"),
                        "staff_stat_field": staff_override.get("stat_field"),
                    }
                aim_loc = staff_override.get("aim_location") if staff_override else None
                execute_attack_roll(attacker, target, total, f"{target.key}'s dodge", target.location,
                                   aim_location=aim_loc, **kwargs)


class CmdAttack(MuxCommand):
    """
    Make an attack roll (stat + skill vs DV) and roll damage if you exceed the DV.

    Usage:
      attack <dv>                    - Use a GM-specified DV
      attack <target>                - Attack target; they must dodge first
      attack <target1,target2,...>   - Splash/shotgun zone (with grenade, rocket, flamethrower, or shotgun)
      attack/distance <meters> <target> - Ranged attack at distance (range chart DV)
      attack/aim <target>=<head|body|arms|legs> - Aimed shot at body part
      attack/melee <target>          - Melee attack (medium melee or unarmed, whichever greater)
      attack/autofire <target1>, <target2>, ... - Autofire (10 bullets, REF 8+ can dodge)
      attack/suppressive <target1>, ... - Suppressive fire (10 bullets, WILL+Concentration vs REF+Autofire)

    Staff only:
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

        if "distance" in switches:
            self._attack_distance(sheet, char, args)
            return
        if "aim" in switches:
            self._attack_aim(sheet, char, args)
            return
        if "melee" in switches:
            self._attack_melee(sheet, char, args)
            return
        if "autofire" in switches:
            self._attack_autofire(sheet, char, args)
            return
        if "suppressive" in switches:
            self._attack_suppressive(sheet, char, args)
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
                _add_pending_attack(target, char)
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

        execute_attack_roll(char, target, dv, dv_name, self.caller.location)

    def _attack_distance(self, sheet, char, args):
        """attack/distance <meters> <target> - Use range chart for DV."""
        parts = args.split(None, 1)
        if not parts:
            self.caller.msg("Usage: attack/distance <meters> <target>")
            return
        try:
            distance = int(parts[0])
        except ValueError:
            self.caller.msg("Distance must be a number (meters).")
            return
        target_name = parts[1].strip() if len(parts) > 1 else None
        if not target_name:
            self.caller.msg("Usage: attack/distance <meters> <target>")
            return
        target = self.caller.search(target_name)
        if not target or target == char:
            return
        weapon = _get_equipped_weapon(char)
        cw_attack = _get_active_cyberware_weapon(char)
        if not weapon and not cw_attack:
            self.caller.msg("You need a ranged weapon equipped for attack/distance.")
            return
        w_name = weapon.name if weapon else (cw_attack[1] if cw_attack else "")
        w_cat = weapon.category if weapon else ("handgun" if cw_attack and cw_attack[3] == "handgun" else "heavy_weapons")
        dv, dv_name = get_dv_for_range(w_name, w_cat, distance, autofire=False)
        if dv is None:
            self.caller.msg(f"Target is out of range for your weapon at {distance}m.")
            return
        if distance <= POINT_BLANK_RANGE:
            dodge_dv, _ = _get_last_dodge_dv(target)
            if dodge_dv is None:
                _add_pending_attack(target, char)
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
        execute_attack_roll(char, target, dv, dv_name, self.caller.location)

    def _attack_aim(self, sheet, char, args):
        """attack/aim <target>=<head|body|arms|legs>"""
        if not args or "=" not in args:
            self.caller.msg("Usage: attack/aim <target>=<head|body|arms|legs>")
            return
        target_name, loc = args.split("=", 1)
        target_name = target_name.strip()
        loc = loc.strip().lower()
        if loc not in ARMOR_LOCATIONS:
            self.caller.msg(f"Aim location must be one of: {', '.join(ARMOR_LOCATIONS)}")
            return
        target = self.caller.search(target_name)
        if not target or target == char:
            return
        dodge_dv, _ = _get_last_dodge_dv(target)
        if dodge_dv is None:
            _add_pending_attack(target, char)
            self.caller.location.msg_contents(
                f"|w{char.key}|n aims at |w{target.key}|n's {loc}! |y{target.key} must dodge first.|n"
            )
            target.msg(f"|yYou are being targeted by {char.key}!|n Use the |w'dodge'|n command.")
            return
        dv = dodge_dv
        dv_name = f"{target.key}'s dodge"
        _clear_last_dodge_dv(target)
        execute_attack_roll(char, target, dv, dv_name, self.caller.location, aim_location=loc)

    def _attack_melee(self, sheet, char, args):
        """attack/melee <target> - Use medium melee (2d6) or unarmed, whichever is greater."""
        if not args:
            self.caller.msg("Usage: attack/melee <target>")
            return
        target = self.caller.search(args.strip())
        if not target or target == char:
            return
        dodge_dv, _ = _get_last_dodge_dv(target)
        if dodge_dv is None:
            _add_pending_attack(target, char)
            self.caller.location.msg_contents(
                f"|w{char.key}|n attacks |w{target.key}|n in melee! |y{target.key} must dodge first.|n"
            )
            target.msg(f"|yYou are being attacked by {char.key}!|n Use the |w'dodge'|n command.")
            return
        dv = dodge_dv
        dv_name = f"{target.key}'s dodge"
        _clear_last_dodge_dv(target)
        execute_attack_roll(char, target, dv, dv_name, self.caller.location, force_melee=True)

    def _attack_zone_targets(self, sheet, char, names):
        """Splash or shotgun zone attack: attack <target1,target2,...>"""
        weapon = _get_equipped_weapon(char)
        cw_attack = _get_active_cyberware_weapon(char)
        w_name = ""
        w_cat = ""
        if weapon:
            w_name = weapon.name or ""
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
        w_name = (weapon.name or "").lower()
        if "smg" not in w_name and "assault rifle" not in w_name:
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
        dv, _ = get_dv_for_range(weapon.name, weapon.category, 0, autofire=True)
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
            mult = 4 if "assault rifle" in (weapon.name or "").lower() else 3
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
