"""
Treat command - Stabilization and critical injury healing (First Aid, Paramedic, Surgery).

treat/stabilize [target] - Stabilize wound state (TECH + First Aid or Paramedic vs DV)
treat/diagnose <character> - List injuries on character
treat/quick <name>=<injury> - Quick Fix (removes effect for rest of day)
treat/injury <name>=<injury> - Treatment with Paramedic (permanent)
treat/surgery <name> - Treatment with Surgery (Medtech only, permanent)
"""

import random
import time
from evennia.commands.default.muxcommand import MuxCommand
from world.utils.character_utils import get_character_sheet, is_character_approved, is_staff
from world.wound_utils import (
    get_current_hp,
    get_max_hp,
    get_wound_state,
    is_dead,
    stabilize_character,
    is_unconscious,
)
from world.wound_data import (
    WOUND_SLIGHTLY,
    WOUND_SERIOUSLY,
    WOUND_MORTALLY,
    WOUND_DEAD,
    STABILIZATION_DV,
    get_injury_data_by_name,
    get_hospital_cost_for_injuries,
    CRITICAL_INJURIES_BODY,
    CRITICAL_INJURIES_HEAD,
    INJURY_CYBERWARE_REPLACEMENT,
    get_installed_cyberware_counts,
    injury_requires_cybertech_for_replacement,
    can_replace_injury_with_cyberware,
)


def _get_sheet(char):
    if not char:
        return None
    return getattr(char, "character_sheet", None)


def _get_tech(char):
    from world.utils.character_utils import get_technique_value
    sheet = _get_sheet(char)
    if sheet:
        return get_technique_value(sheet) or 0
    return get_technique_value(char) or 0


def _get_first_aid(char):
    sheet = _get_sheet(char)
    if sheet:
        return getattr(sheet, "first_aid", 0) or 0
    return (char.db.skills or {}).get("first_aid", 0) or 0


def _get_paramedic(char):
    sheet = _get_sheet(char)
    if sheet:
        return getattr(sheet, "paramedic", 0) or 0
    return (char.db.skills or {}).get("paramedic", 0) or 0


def _get_surgery(char):
    if hasattr(char, "get_skill"):
        return char.get_skill("surgery") or 0
    return (char.db.skills or {}).get("surgery", 0) or 0


def _is_medtech(char):
    return (getattr(char.db, "role", None) or "").strip() == "Medtech"


def _get_injuries(char):
    sheet = _get_sheet(char)
    if not sheet:
        return []
    return list(getattr(sheet, "critical_injuries", []) or [])


def _is_injury_quick_fixed(sheet, injury_name):
    fixes = getattr(sheet, "critical_injury_quick_fixes", {}) or {}
    expiry = fixes.get(injury_name, 0)
    return expiry > 0 and time.time() < expiry


def _apply_quick_fix(sheet, injury_name):
    """Record quick fix - effect suppressed for 24 hours."""
    fixes = dict(getattr(sheet, "critical_injury_quick_fixes", {}) or {})
    fixes[injury_name] = time.time() + 86400
    sheet.critical_injury_quick_fixes = fixes
    sheet.save(skip_recalculation=True)


MEDICAL_ROOM_TAGS = ("ripperdoc", "clinic", "hospital", "medical", "medtech")


def _is_medical_room(room):
    """True if room has ripperdoc, clinic, hospital, medical, or medtech tag."""
    if not room or not hasattr(room, "tags"):
        return False
    for tag in MEDICAL_ROOM_TAGS:
        if room.tags.has(tag):
            return True
    db_tags = getattr(room.db, "tags", None) or []
    for t in db_tags:
        if t and str(t).strip().lower() in MEDICAL_ROOM_TAGS:
            return True
    return False


def _is_ripperdoc_room(room):
    """True if room has ripperdoc tag - has Cybertech for limb-loss repairs when at 2x cyberware."""
    if not room or not hasattr(room, "tags"):
        return False
    if room.tags.has("ripperdoc"):
        return True
    db_tags = getattr(room.db, "tags", None) or []
    for t in db_tags:
        if t and str(t).strip().lower() == "ripperdoc":
            return True
    return False


def _get_medical_debt_total(sheet):
    """Total medical debt from entries."""
    entries = getattr(sheet, "medical_debt_entries", None) or []
    return sum((e.get("amount") or 0) for e in entries)


def _add_medical_debt(sheet, amount, injuries, cyberware=None):
    """Add a medical debt entry. cyberware: list of cyberware names installed with this debt."""
    from datetime import date
    entries = list(getattr(sheet, "medical_debt_entries", None) or [])
    entry = {
        "amount": amount,
        "injuries": list(injuries) if injuries else [],
        "date": str(date.today()),
    }
    if cyberware:
        entry["cyberware"] = list(cyberware)
    entries.append(entry)
    sheet.medical_debt_entries = entries
    sheet.save(skip_recalculation=True)


def _pay_medical_debt(sheet, amount):
    """
    Pay toward medical debt. Returns (amount_applied, remaining_debt).
    Applies to oldest entries first.
    """
    entries = list(getattr(sheet, "medical_debt_entries", None) or [])
    if not entries or amount <= 0:
        return 0, _get_medical_debt_total(sheet)
    remaining = amount
    new_entries = []
    for entry in entries:
        if remaining <= 0:
            new_entries.append(entry)
            continue
        entry_amount = entry.get("amount") or 0
        if entry_amount <= 0:
            continue
        pay_this = min(remaining, entry_amount)
        remaining -= pay_this
        new_amount = entry_amount - pay_this
        if new_amount > 0:
            new_entries.append({**entry, "amount": new_amount})
    sheet.medical_debt_entries = new_entries
    sheet.save(skip_recalculation=True)
    applied = amount - remaining
    return applied, _get_medical_debt_total(sheet)


def _install_cyberware_for_injury(sheet, character, cyberware_name):
    """Install cyberware (replacement limb) for character. Returns True on success."""
    from world.inventory.models import Inventory, CyberwareInstance
    from world.cyberware.models import Cyberware

    try:
        cw = Cyberware.objects.get(name__iexact=cyberware_name)
    except Cyberware.DoesNotExist:
        return False
    inventory, _ = Inventory.get_or_create_for_character(character)
    inst = CyberwareInstance.objects.create(
        cyberware=cw,
        character_sheet=sheet,
        character_object=character,
        installed=True,
    )
    inventory.cyberware.add(inst)
    if cw.name.lower() in ("cyberarm", "neo-soviet cyberarm"):
        sheet.has_cyberarm = True
        sheet.save(skip_recalculation=True)
    if hasattr(sheet, "calculate_humanity_loss"):
        sheet.calculate_humanity_loss()
    return True


def _remove_injury(sheet, injury_name):
    """Permanently remove injury from list. Reduces base_death_save_penalty if injury had one."""
    injuries = list(getattr(sheet, "critical_injuries", []) or [])
    if injury_name in injuries:
        data, _ = get_injury_data_by_name(injury_name)
        dsp = (data or {}).get("death_save_penalty", 0) or 0
        if dsp > 0:
            base = getattr(sheet, "base_death_save_penalty", 0) or 0
            sheet.base_death_save_penalty = max(0, base - dsp)
            new_base = getattr(sheet, "base_death_save_penalty", 0) or 0
            current_penalty = getattr(sheet, "death_save_penalty", 0) or 0
            sheet.death_save_penalty = max(new_base, current_penalty - dsp)
            char = getattr(sheet, "character", None)
            if char and hasattr(char, "db"):
                char.db.death_save_penalty = sheet.death_save_penalty
        injuries.remove(injury_name)
        sheet.critical_injuries = injuries
        fixes = dict(getattr(sheet, "critical_injury_quick_fixes", {}) or {})
        fixes.pop(injury_name, None)
        sheet.critical_injury_quick_fixes = fixes
        sheet.save(skip_recalculation=True)


class CmdTreat(MuxCommand):
    """
    Stabilize wound states and heal critical injuries.

    Usage:
      treat/stabilize [target]   - Stabilize (TECH + First Aid or Paramedic vs DV)
      treat/diagnose <character> - List injuries
      treat/quick <name>=<injury> - Quick Fix (1 min, removes effect for rest of day)
      treat/injury <name>=<injury> - Treatment with Paramedic (4 hrs, permanent)
      treat/surgery <name> [=injury] - Treatment with Surgery (Medtech only)
      treat/hospital [yes|no|accept] - Surgical restoration; /yes=all, /accept leg,eye=some, /no=cancel
      treat/pay <amount>         - Pay medical debt (in medical room)
      treat/cleardebt [name]     - Staff: clear medical debt (self or target)
    """

    key = "treat"
    aliases = ["+treat"]
    help_category = "Combat"

    def func(self):
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved to use the treat command.")
            return

        switches = self.switches or []
        args = (self.args or "").strip()

        if "stabilize" in switches:
            self._do_stabilize(args)
            return
        if "diagnose" in switches:
            self._do_diagnose(args)
            return
        if "quick" in switches:
            self._do_quick(args)
            return
        if "injury" in switches:
            self._do_injury(args)
            return
        if "surgery" in switches:
            self._do_surgery(args)
            return
        if "hospital" in switches:
            self._do_hospital(args, switches)
            return
        if "pay" in switches:
            self._do_pay_debt(args)
            return
        if "cleardebt" in switches:
            self._do_clear_debt(args)
            return

        self.caller.msg(
            "Usage: treat/stabilize [target] | treat/diagnose <char> | "
            "treat/quick <name>=<injury> | treat/injury <name>=<injury> | treat/surgery <name> | "
            "treat/hospital | treat/pay <amount> | treat/cleardebt [name]"
        )

    def _do_stabilize(self, args):
        target = self.caller.search(args.strip()) if args else self.caller
        if not target:
            return

        if is_dead(target):
            self.caller.msg(f"{target.key} is dead. Stabilization cannot help.")
            return

        sheet = _get_sheet(target)
        if not sheet:
            self.caller.msg(f"{target.key} has no character sheet.")
            return

        state = get_wound_state(target)
        if state is None:
            self.caller.msg(f"{target.key} is unwounded. No stabilization needed.")
            return
        if state == WOUND_DEAD:
            self.caller.msg(f"{target.key} is dead.")
            return

        dv = STABILIZATION_DV.get(state)
        if dv is None:
            self.caller.msg("Cannot stabilize in this wound state.")
            return

        tech = _get_tech(self.caller)
        paramedic = _get_paramedic(self.caller)
        first_aid = _get_first_aid(self.caller)

        if paramedic >= first_aid and paramedic > 0:
            skill_val = paramedic
            skill_name = "Paramedic"
        elif first_aid > 0:
            skill_val = first_aid
            skill_name = "First Aid"
        else:
            self.caller.msg("You need First Aid or Paramedic skill to stabilize.")
            return

        d10 = random.randint(1, 10)
        total = tech + skill_val + d10
        success = total > dv

        state_names = {WOUND_SLIGHTLY: "Lightly", WOUND_SERIOUSLY: "Seriously", WOUND_MORTALLY: "Mortally"}
        state_str = state_names.get(state, "wounded")

        msg = (
            f"|w{self.caller.key}|n attempts to stabilize |w{target.key}|n ({state_str} Wounded). "
            f"Roll: TECH {tech} + {skill_name} {skill_val} + 1d10 [{d10}] = {total} vs DV {dv}. "
        )
        if success:
            msg += f"|gSuccess!|n "
            if state == WOUND_MORTALLY:
                stabilize_character(target)
                msg += f"{target.key} is stabilized to 1 HP and |yunconscious|n for 1 minute."
            else:
                msg += f"{target.key} is stabilized."
        else:
            msg += f"|rFailed.|n"

        loc = self.caller.location
        if loc:
            loc.msg_contents(msg)
        if target != self.caller:
            target.msg(f"You {'are stabilized' if success else 'remain unstable'}.")

    def _do_diagnose(self, args):
        if not args:
            self.caller.msg("Usage: treat/diagnose <character>")
            return
        target = self.caller.search(args.strip())
        if not target:
            return

        sheet = _get_sheet(target)
        if not sheet:
            self.caller.msg(f"{target.key} has no character sheet.")
            return

        injuries = _get_injuries(target)
        if not injuries:
            self.caller.msg(f"{target.key} has no critical injuries.")
            return

        lines = [f"|yCritical injuries on {target.key}:|n"]
        for name in injuries:
            data, _ = get_injury_data_by_name(name)
            qf = " |g(quick-fixed)|n" if _is_injury_quick_fixed(sheet, name) else ""
            effect = data.get("effect", "-") if data else "-"
            lines.append(f"  * {name}{qf} [{effect}]")
        self.caller.msg("\n".join(lines))

    def _do_quick(self, args):
        if not args or "=" not in args:
            self.caller.msg("Usage: treat/quick <name>=<injury>")
            return
        name_part, injury_part = args.split("=", 1)
        name_part = name_part.strip()
        injury_part = injury_part.strip().strip('"')

        target = self.caller.search(name_part)
        if not target:
            return

        sheet = _get_sheet(target)
        if not sheet:
            return

        injuries = _get_injuries(target)
        injury_match = None
        for inv_name in injuries:
            if injury_part.lower() in (inv_name or "").lower():
                injury_match = inv_name
                break
        if not injury_match:
            verb = "don't" if target == self.caller else "doesn't"
            who = "You" if target == self.caller else target.key
            self.caller.msg(f"{who} {verb} have an injury matching '{injury_part}'.")
            return

        data, _ = get_injury_data_by_name(injury_match)
        if not data:
            self.caller.msg(f"Unknown injury: {injury_match}")
            return

        qf = data.get("quick_fix")
        if not qf:
            self.caller.msg(f"{injury_match} cannot be Quick Fixed.")
            return

        skill_req = qf.get("skill", "paramedic")
        dv = qf.get("dv", 13)
        tech = _get_tech(self.caller)
        skill_val = 0
        skill_name = ""
        if skill_req == "first_aid":
            fa = _get_first_aid(self.caller)
            para = _get_paramedic(self.caller)
            if para >= fa and para > 0:
                skill_val = para
                skill_name = "Paramedic"
            elif fa > 0:
                skill_val = fa
                skill_name = "First Aid"
        else:
            skill_val = _get_paramedic(self.caller)
            skill_name = "Paramedic"

        if skill_val <= 0:
            self.caller.msg(f"Quick Fix for {injury_match} requires {skill_name}.")
            return

        d10 = random.randint(1, 10)
        total = tech + skill_val + d10
        success = total > dv

        msg = (
            f"|w{self.caller.key}|n attempts Quick Fix on {injury_match}. "
            f"TECH {tech} + {skill_name} {skill_val} + 1d10 [{d10}] = {total} vs DV {dv}. "
        )
        if success:
            _apply_quick_fix(sheet, injury_match)
            msg += f"|gSuccess!|n Injury effect suppressed for the rest of the day."
        else:
            msg += f"|rFailed.|n"

        loc = self.caller.location
        if loc:
            loc.msg_contents(msg)

    def _do_injury(self, args):
        if not args or "=" not in args:
            self.caller.msg("Usage: treat/injury <name>=<injury>")
            return
        name_part, injury_part = args.split("=", 1)
        name_part = name_part.strip()
        injury_part = injury_part.strip().strip('"')

        target = self.caller.search(name_part)
        if not target:
            return

        if target == self.caller:
            self.caller.msg("You cannot perform Treatment on yourself.")
            return

        sheet = _get_sheet(target)
        if not sheet:
            return

        injuries = _get_injuries(target)
        injury_match = None
        for inv_name in injuries:
            if injury_part.lower() in (inv_name or "").lower():
                injury_match = inv_name
                break
        if not injury_match:
            self.caller.msg(f"{target.key} doesn't have an injury matching '{injury_part}'.")
            return

        data, _ = get_injury_data_by_name(injury_match)
        if not data:
            return

        treatment = data.get("treatment", {})
        paramedic_dv = treatment.get("paramedic")
        if paramedic_dv is None:
            self.caller.msg(f"{injury_match} cannot be treated with Paramedic. Use treat/surgery (Medtech).")
            return

        tech = _get_tech(self.caller)
        skill_val = _get_paramedic(self.caller)
        if skill_val <= 0:
            self.caller.msg("Treatment with Paramedic requires the Paramedic skill.")
            return

        d10 = random.randint(1, 10)
        total = tech + skill_val + d10
        success = total > paramedic_dv

        msg = (
            f"|w{self.caller.key}|n attempts Treatment on |w{target.key}|n's {injury_match}. "
            f"TECH {tech} + Paramedic {skill_val} + 1d10 [{d10}] = {total} vs DV {paramedic_dv}. "
        )
        if success:
            _remove_injury(sheet, injury_match)
            msg += f"|gSuccess!|n {injury_match} permanently healed."
        else:
            msg += f"|rFailed.|n"

        loc = self.caller.location
        if loc:
            loc.msg_contents(msg)
        target.msg(f"Your {injury_match} has been {'permanently healed' if success else 'left untreated'}.")

    def _do_surgery(self, args):
        if not args:
            self.caller.msg("Usage: treat/surgery <name> [=injury]")
            return

        if not _is_medtech(self.caller):
            self.caller.msg("Surgery requires the Medtech role (Medicine + Surgery specialty).")
            return

        name_part = args.strip()
        injury_part = None
        if "=" in args:
            name_part, injury_part = args.split("=", 1)
            name_part = name_part.strip()
            injury_part = injury_part.strip().strip('"')

        target = self.caller.search(name_part)
        if not target:
            return

        if target == self.caller:
            self.caller.msg("You cannot perform Surgery on yourself.")
            return

        sheet = _get_sheet(target)
        if not sheet:
            return

        injuries = _get_injuries(target)
        if not injuries:
            self.caller.msg(f"{target.key} has no critical injuries to treat.")
            return

        if injury_part:
            injury_match = None
            for inv_name in injuries:
                if injury_part.lower() in (inv_name or "").lower():
                    injury_match = inv_name
                    break
            if not injury_match:
                self.caller.msg(f"{target.key} doesn't have an injury matching '{injury_part}'.")
                return
            best_injury = injury_match
        else:
            best_injury = None
            best_dv = 99
            for inv_name in injuries:
                data, _ = get_injury_data_by_name(inv_name)
                if not data:
                    continue
                treatment = data.get("treatment", {})
                surg_dv = treatment.get("surgery")
                if surg_dv is not None and surg_dv < best_dv:
                    best_dv = surg_dv
                    best_injury = inv_name

        if not best_injury:
            self.caller.msg(f"None of {target.key}'s injuries require Surgery.")
            return

        data, _ = get_injury_data_by_name(best_injury)
        treatment = (data or {}).get("treatment", {})
        best_dv = treatment.get("surgery")
        if best_dv is None:
            self.caller.msg(f"{best_injury} cannot be treated with Surgery.")
            return

        tech = _get_tech(self.caller)
        skill_val = _get_surgery(self.caller)
        if skill_val <= 0:
            self.caller.msg("You need Surgery skill (Medicine + Surgery specialty) to perform surgery.")
            return

        d10 = random.randint(1, 10)
        total = tech + skill_val + d10
        success = total > best_dv

        msg = (
            f"|w{self.caller.key}|n performs Surgery on |w{target.key}|n's {best_injury}. "
            f"TECH {tech} + Surgery {skill_val} + 1d10 [{d10}] = {total} vs DV {best_dv}. "
        )
        if success:
            _remove_injury(sheet, best_injury)
            msg += f"|gSuccess!|n {best_injury} permanently healed."
        else:
            msg += f"|rFailed.|n"

        loc = self.caller.location
        if loc:
            loc.msg_contents(msg)
        target.msg(f"Your {best_injury} has been {'permanently healed' if success else 'left untreated'}.")

    def _do_hospital(self, args, switches):
        """Surgical restoration at ripperdoc/clinic/hospital. Offers cyberware replacement for limb-loss."""
        loc = self.caller.location
        if not _is_medical_room(loc):
            self.caller.msg(
                "You must be at a ripperdoc, clinic, hospital, or medical facility. "
                "Look for rooms tagged ripperdoc, clinic, hospital, medical, or medtech."
            )
            return

        target = self.caller
        sheet = _get_sheet(target)
        if not sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        injuries = _get_injuries(target)
        if not injuries:
            self.caller.msg("You have no critical injuries to heal.")
            return

        from world.cyberpunk_sheets.services import CharacterMoneyService
        balance = CharacterMoneyService.get_balance(target)
        counts = get_installed_cyberware_counts(sheet)
        is_ripperdoc = _is_ripperdoc_room(loc)

        # Split injuries: regular (no cyberware option) vs limb-loss
        regular_injuries = []
        limb_loss_injuries = []
        for inj in injuries:
            if inj in INJURY_CYBERWARE_REPLACEMENT:
                limb_loss_injuries.append(inj)
            else:
                regular_injuries.append(inj)

        # Build eligible cyberware options for limb-loss
        eligible = []
        cannot_replace = []
        needs_cybertech = []
        for inj in limb_loss_injuries:
            repl = INJURY_CYBERWARE_REPLACEMENT.get(inj)
            if not repl:
                continue
            cw_list = repl.get("cyberware") or []
            cw_name = cw_list[0] if cw_list else ""
            cost_eb = repl.get("cost", 0)
            can_replace = can_replace_injury_with_cyberware(inj, counts)
            need_tech = injury_requires_cybertech_for_replacement(inj, counts)
            if not can_replace:
                cannot_replace.append((inj, cw_name))
                continue
            if need_tech and not is_ripperdoc:
                needs_cybertech.append((inj, cw_name))
                continue
            eligible.append({"injury": inj, "cyberware": cw_name, "cost": cost_eb})

        base_cost, highest_dc = get_hospital_cost_for_injuries(injuries)
        cyberware_total = sum(e["cost"] for e in eligible)
        max_total = base_cost + cyberware_total

        # Parse treat/hospital/accept <list>
        accept_switch = "accept" in switches
        if accept_switch and args and args.strip():
            # Parse injury names from args: "leg,eye,ear" -> Dismembered Leg, Lost Eye, Lost Ear
            _MAP = {
                "leg": "Dismembered Leg", "arm": "Dismembered Arm", "hand": "Dismembered Hand",
                "eye": "Lost Eye", "ear": "Lost Ear",
            }
            parts = [p.strip().lower() for p in args.split(",") if p.strip()]
            accepted_injuries = set()
            for p in parts:
                if p in _MAP:
                    accepted_injuries.add(_MAP[p])
                else:
                    for inv in eligible:
                        if p in (inv["injury"] or "").lower():
                            accepted_injuries.add(inv["injury"])
                            break
            accepted = [e for e in eligible if e["injury"] in accepted_injuries]
        elif "yes" in switches:
            accepted = eligible
        else:
            accepted = None

        # treat/hospital/no - cancel pending
        if "no" in switches:
            if getattr(target.ndb, "treat_hospital_pending", None):
                target.ndb.treat_hospital_pending = None
                self.caller.msg("Surgical restoration cancelled.")
            else:
                self.caller.msg("No pending surgical restoration to cancel.")
            return

        # Confirm: treat/hospital/yes or treat/hospital/accept
        if accepted is not None:
            injuries_to_remove = regular_injuries + [a["injury"] for a in accepted]
            cyber_cost = sum(a["cost"] for a in accepted)
            total_cost = base_cost + cyber_cost

            # Validate: don't charge for nothing
            if not injuries_to_remove and not accepted:
                target.ndb.treat_hospital_pending = None
                if accept_switch and args and args.strip():
                    _MAP = {
                        "leg": "Dismembered Leg", "arm": "Dismembered Arm", "hand": "Dismembered Hand",
                        "eye": "Lost Eye", "ear": "Lost Ear",
                    }
                    parts = [p.strip().lower() for p in args.split(",") if p.strip()]
                    invalid = []
                    for p in parts:
                        inj_name = _MAP.get(p)
                        if inj_name and inj_name not in injuries:
                            invalid.append(inj_name)
                        elif inj_name is None and p:
                            invalid.append(p)
                    if invalid:
                        self.caller.msg(
                            f"|rYou don't have these injuries:|n {', '.join(invalid)}. "
                            f"No treatment performed. Use |wtreat/hospital|n to see your current options."
                        )
                    else:
                        self.caller.msg(
                            "|rNone of those options apply to your current injuries.|n "
                            "Use |wtreat/hospital|n to see your current options."
                        )
                else:
                    self.caller.msg("No treatment to perform.")
                return

            target.ndb.treat_hospital_pending = None
            if balance >= total_cost:
                CharacterMoneyService.spend_money(target, total_cost)
                for inj in injuries_to_remove:
                    _remove_injury(sheet, inj)
                for a in accepted:
                    _install_cyberware_for_injury(sheet, target, a["cyberware"])
                cw_str = ", ".join(a["cyberware"] for a in accepted) if accepted else ""
                self.caller.msg(
                    f"|gSurgical restoration complete.|n Injuries healed. "
                    f"Cost: {total_cost} eb. " + (f"Cyberware installed: {cw_str}. " if cw_str else "")
                    + f"Balance: {balance - total_cost} eb."
                )
                loc.msg_contents(
                    f"|w{target.key}|n receives surgical restoration.",
                    exclude=target,
                )
            else:
                cw_names = [a["cyberware"] for a in accepted] if accepted else []
                _add_medical_debt(sheet, total_cost, injuries_to_remove, cyberware=cw_names)
                for inj in injuries_to_remove:
                    _remove_injury(sheet, inj)
                for a in accepted:
                    _install_cyberware_for_injury(sheet, target, a["cyberware"])
                self.caller.msg(
                    f"|gSurgical restoration complete.|n Medical debt: |r{total_cost} eb|n "
                    f"(pay with |wtreat/pay <amount>|n in a medical facility)."
                )
                loc.msg_contents(
                    f"|w{target.key}|n receives surgical restoration.",
                    exclude=target,
                )
            return

        # Initial treat/hospital - show breakdown
        lines = [f"|ySurgical restoration at {loc.key if loc else 'medical facility'}|n"]
        lines.append(f"Injuries: {', '.join(injuries)}")
        if regular_injuries:
            lines.append(f"  Regular (surgery): {', '.join(regular_injuries)}")
        if cannot_replace:
            for inj, cw in cannot_replace:
                lines.append(f"  |r{inj}|n: Cannot replace (already have 2x {cw})")
        if needs_cybertech:
            for inj, cw in needs_cybertech:
                lines.append(f"  |r{inj}|n: Requires Cybertech (visit a |wripperdoc|n)")
        if eligible:
            lines.append("  Cyberware replacement available:")
            for e in eligible:
                lines.append(f"    * {e['injury']}: {e['cyberware']} ({e['cost']} eb)")
        lines.append(f"Base cost: {base_cost} eb (highest DC {highest_dc})")
        if eligible:
            lines.append(f"With all cyberware: {max_total} eb")
        lines.append(f"Your balance: {balance} eb")
        self.caller.msg("\n".join(lines))

        total_cost = base_cost + cyberware_total
        if balance >= total_cost:
            target.ndb.treat_hospital_pending = {
                "base_cost": base_cost,
                "highest_dc": highest_dc,
                "regular_injuries": regular_injuries,
                "eligible": eligible,
                "accepted": eligible,
            }
            self.caller.msg(
                f"Use |wtreat/hospital/yes|n to proceed ({total_cost} eb), "
                f"or |wtreat/hospital/accept leg,eye|n to accept only some (e.g. leg, eye, ear, arm, hand)."
            )
        else:
            target.ndb.treat_hospital_pending = {
                "base_cost": base_cost,
                "highest_dc": highest_dc,
                "regular_injuries": regular_injuries,
                "eligible": eligible,
                "accepted": eligible,
            }
            self.caller.msg(
                f"Use |wtreat/hospital/yes|n to go into debt ({total_cost} eb), "
                f"|wtreat/hospital/accept leg,eye|n to accept only some, or |wtreat/hospital/no|n to cancel."
            )

    def _do_pay_debt(self, args):
        """Pay medical debt. Must be in a medical room."""
        loc = self.caller.location
        if not _is_medical_room(loc):
            self.caller.msg(
                "You must be at a ripperdoc, clinic, hospital, or medical facility to pay medical debt."
            )
            return

        if not args or not args.strip().isdigit():
            self.caller.msg("Usage: treat/pay <amount>")
            return

        amount = int(args.strip())
        if amount <= 0:
            self.caller.msg("Amount must be positive.")
            return

        target = self.caller
        sheet = _get_sheet(target)
        if not sheet:
            self.caller.msg("You don't have a character sheet.")
            return

        total_debt = _get_medical_debt_total(sheet)
        if total_debt <= 0:
            self.caller.msg("You have no medical debt.")
            return

        from world.cyberpunk_sheets.services import CharacterMoneyService
        balance = CharacterMoneyService.get_balance(target)
        if balance < amount:
            self.caller.msg(f"You only have {balance} eb. You tried to pay {amount} eb.")
            return

        applied, remaining = _pay_medical_debt(sheet, amount)
        CharacterMoneyService.spend_money(target, applied)
        self.caller.msg(
            f"Paid |g{applied} eb|n toward medical debt. "
            f"Remaining debt: |y{remaining} eb|n" + (" (cleared!)" if remaining <= 0 else ".")
        )

    def _do_clear_debt(self, args):
        """Staff: clear medical debt for self or target."""
        if not is_staff(self.caller):
            self.caller.msg("Only staff can clear medical debt.")
            return
        target = self.caller.search(args.strip()) if args else self.caller
        if not target:
            return
        sheet = _get_sheet(target)
        if not sheet:
            self.caller.msg(f"{target.key} has no character sheet.")
            return
        total = _get_medical_debt_total(sheet)
        if total <= 0:
            self.caller.msg(f"{target.key} has no medical debt.")
            return
        sheet.medical_debt_entries = []
        sheet.save(skip_recalculation=True)
        self.caller.msg(f"|gCleared|n {total} eb medical debt for {target.key}.")
        if target != self.caller:
            target.msg(f"Staff cleared your medical debt ({total} eb).")
