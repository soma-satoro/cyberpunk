"""
Improvement Points (IP) commands.

+ip - View your IP status (or +ip <name> for staff to view another player)
+ip/buy <stat> - Spend IP to raise a skill or attribute
+ip/refund - Refund your last purchase
+ip/log - View full IP history (or +ip/log <name> for staff)
+ip/award <name>=<amount> - Staff: Award IP to a player
+ip/remove <name>=<amount> - Staff: Remove IP from a player
"""
from evennia.commands.default.muxcommand import MuxCommand
from world.utils.formatting import header, footer, divider
from world.utils.character_utils import is_character_approved
from world.improvement_points import (
    get_character_ip,
    get_character_stat_value,
    set_character_stat_value,
    get_ip_cost,
    is_valid_stat,
    get_stat_display_name,
    add_ip_log_entry,
    get_recent_ip_changes,
    format_log_entry,
    normalize_stat_name,
    parse_skill_instance,
    SKILLS_REQUIRING_INSTANCE,
    IP_ATTRIBUTES,
    IP_ROLE_ABILITIES,
)


def get_target_character(caller, name):
    """Resolve name to a puppetable character (typeclass)."""
    if not name:
        return None
    target = caller.search(name, global_search=True)
    if not target:
        return None
    # We need the Character typeclass (puppetable)
    if hasattr(target, "db") and hasattr(target, "attributes"):
        return target
    if hasattr(target, "characters") and target.characters:
        return target.characters[0]
    if hasattr(target, "character") and target.character:
        return target.character
    return target


def format_ip_display(character, for_staff=False):
    """Format the IP status display (80 chars, sheet color scheme)."""
    width = 80
    current, spent, staff_awarded, _, _ = get_character_ip(character)
    lifetime = current + spent
    recent = get_recent_ip_changes(character, limit=5 if not for_staff else 10, exclude_votes=True)

    output = header("IMPROVEMENT POINTS", width=width, fillchar="|m=|n")
    output += "\n"
    output += f"|cCurrent IP:|n {current:<20} |cSpent IP:|n {spent}\n"
    output += f"|cLifetime IP:|n {lifetime:<18} |cStaff Awarded IP:|n {staff_awarded}\n"
    output += "\n"
    # RECENT CHANGES line: <---- RECENT CHANGES (Last 5) ----> (80 chars total)
    title = " RECENT CHANGES (Last 5) "
    dash_count = (width - len(title) - 2) // 2  # -2 for < and >
    output += "|m<|n" + "|m-|n" * dash_count + "|y" + title + "|n" + "|m-|n" * (width - len(title) - 2 - dash_count) + "|m>|n\n"
    for entry in recent:
        output += format_log_entry(entry) + "\n"
    if not recent:
        output += "(No recent changes)\n"
    output += "\n"
    output += "Use +ip/log to see full XP history\n"
    output += footer(width=width, fillchar="|m=|n")
    return output


class CmdIP(MuxCommand):
    """
    View and spend Improvement Points.

    Usage:
      +ip                    - View your IP status
      +ip <name>             - [Staff] View another player's IP
      +ip/buy <stat>         - Spend IP to raise a skill or attribute
      +ip/refund             - Refund your last purchase
      +ip/log                - View full IP history
      +ip/log <name>         - [Staff] View another player's full IP log
      +ip/award <name>=<amt> - [Staff] Award IP to a player
      +ip/remove <name>=<amt> - [Staff] Remove IP from a player

    Examples:
      +ip
      +ip/buy handgun
      +ip/buy athletics
      +ip/refund
      +ip/award Bob=25
      +ip/remove Jane=10
    """

    key = "+ip"
    aliases = ["ip"]
    locks = "cmd:all()"
    help_category = "Character"

    def func(self):
        caller = self.caller
        args = self.args.strip()
        switches = [s.lower() for s in self.switches] if self.switches else []

        # Staff viewing another player: +ip <name> or +ip/log <name>
        acct = getattr(caller, "account", caller)
        is_staff = acct.check_permstring("Builder") if hasattr(acct, "check_permstring") else False

        # +ip/award
        if "award" in switches:
            self.do_award()
            return

        # +ip/remove
        if "remove" in switches:
            self.do_remove()
            return

        # +ip/buy
        if "buy" in switches:
            self.do_buy()
            return

        # +ip/refund
        if "refund" in switches:
            self.do_refund()
            return

        # +ip/log [name]
        if "log" in switches:
            self.do_log(args, is_staff)
            return

        # +ip or +ip <name> (staff)
        if args and is_staff:
            target = get_target_character(caller, args)
            if not target:
                caller.msg("Could not find that character.")
                return
            caller.msg(format_ip_display(target, for_staff=True))
            caller.msg(f"\n|w(Viewing IP for {target.get_display_name(caller)})|n")
            return

        if args and not is_staff:
            caller.msg("Only staff can view another player's IP. Use +ip to see your own.")
            return

        # Default: show own IP (caller is Character when puppeted)
        char = self.get_self_character()
        if char:
            caller.msg(format_ip_display(char))
        else:
            caller.msg("You must be puppeting a character to view IP.")

    def get_self_character(self):
        """Get the caller's puppeted character."""
        caller = self.caller
        if hasattr(caller, "db") and hasattr(caller, "attributes"):
            return caller  # Already a Character (puppeted)
        if hasattr(caller, "character") and caller.character:
            return caller.character
        if hasattr(caller, "characters"):
            chars = caller.characters
            if callable(chars):
                chars = list(chars) if chars else []
            else:
                chars = list(chars) if chars else []
            return chars[0] if chars else None
        return None

    def do_award(self):
        """Staff: Award IP to a player."""
        acct = getattr(self.caller, "account", self.caller)
        if not (acct and acct.check_permstring("Admin")):
            self.caller.msg("Only staff can award IP.")
            return
        if not self.lhs or not self.rhs:
            self.caller.msg("Usage: +ip/award <name>=<amount>")
            return
        try:
            amount = float(self.rhs.strip())
        except ValueError:
            self.caller.msg("Amount must be a number.")
            return
        if amount <= 0:
            self.caller.msg("Amount must be positive.")
            return

        target = get_target_character(self.caller, self.lhs.strip())
        if not target:
            self.caller.msg("Could not find that character.")
            return

        current, spent, staff_awarded, _, _ = get_character_ip(target)
        new_current = current + amount
        target.attributes.add("improvement_points", new_current)
        target.attributes.add("ip_staff_awarded", staff_awarded + amount)
        awarder = self.caller.get_display_name(self.caller) if hasattr(self.caller, "get_display_name") else str(self.caller)
        add_ip_log_entry(target, amount, "Staff Award", f"Awarded by {awarder}")

        self.caller.msg(f"Awarded {amount} IP to {target.get_display_name(self.caller)}. New total: {new_current}")
        if target.sessions.all():
            target.msg(f"You have been awarded {amount} IP by staff. New total: {new_current}")

    def do_remove(self):
        """Staff: Remove IP from a player."""
        acct = getattr(self.caller, "account", self.caller)
        if not (acct and acct.check_permstring("Admin")):
            self.caller.msg("Only staff can remove IP.")
            return
        if not self.lhs or not self.rhs:
            self.caller.msg("Usage: +ip/remove <name>=<amount>")
            return
        try:
            amount = int(self.rhs.strip())
        except ValueError:
            self.caller.msg("Amount must be a number.")
            return
        if amount <= 0:
            self.caller.msg("Amount must be positive.")
            return

        target = get_target_character(self.caller, self.lhs.strip())
        if not target:
            self.caller.msg("Could not find that character.")
            return

        current, spent, staff_awarded, _, _ = get_character_ip(target)
        amount = min(amount, current)
        new_current = current - amount
        target.attributes.add("improvement_points", new_current)
        add_ip_log_entry(target, -amount, "Staff Removal", f"Removed by {self.caller.get_display_name(self.caller)}")

        self.caller.msg(f"Removed {amount} IP from {target.get_display_name(self.caller)}. New total: {new_current}")
        if target.sessions.all():
            target.msg(f"Staff has removed {amount} IP from you. New total: {new_current}")

    def do_buy(self):
        """Spend IP to raise a stat."""
        char = self.get_self_character()
        if not char:
            self.caller.msg("You must be puppeting a character to spend IP.")
            return
        if not is_character_approved(char):
            self.caller.msg("You must be approved by staff before spending IP.")
            return
        if not self.args:
            self.caller.msg("Usage: +ip/buy <stat>")
            return

        stat_name = self.args.strip()
        first_word = (stat_name.split() or [""])[0]
        stat_key = normalize_stat_name(first_word)
        base_skill, instance = parse_skill_instance(first_word)

        # Local Expert, Play Instrument, and Martial Arts require an instance (e.g. local_expert(Night City))
        if base_skill in SKILLS_REQUIRING_INSTANCE and not instance:
            examples = {
                "local_expert": "+ip/buy local_expert(Night City)",
                "play_instrument": "+ip/buy play_instrument(guitar)",
                "martial_arts": "+ip/buy martial_arts(Krav Maga)",
            }
            example = examples.get(base_skill, f"+ip/buy {base_skill}(instance)")
            self.caller.msg(
                f"{base_skill.replace('_', ' ').title()} requires an instance. "
                f"Use '+ip/buy {base_skill}(instance)', e.g. {example}"
            )
            return

        # Medicine requires specialty: +ip/buy medicine <surgery|pharma|cryo>
        medicine_specialty = None
        if stat_key == "medicine":
            parts = stat_name.split()
            if len(parts) >= 2:
                spec = parts[1].lower()
                if spec in ("surgery", "pharma", "cryo", "cryosystem"):
                    medicine_specialty = "cryo" if spec == "cryosystem" else spec
            if not medicine_specialty:
                self.caller.msg(
                    "Medicine requires a specialty. Use: +ip/buy medicine <surgery|pharma|cryo>\n"
                    "Surgery: 1 pt = 2 Surgery skill. Pharma/Cryo: 1 pt = 1 Medical Tech (max 5 each)."
                )
                return

        if not is_valid_stat(stat_name.split()[0] if stat_name else stat_name):
            self.caller.msg(f"'{stat_name}' is not a valid skill or attribute to purchase.")
            return

        current_val = get_character_stat_value(char, "medicine" if stat_key == "medicine" else stat_name)
        if current_val is None:
            self.caller.msg(f"Could not read current value for {stat_name}.")
            return

        if not medicine_specialty:
            stat_key = normalize_stat_name(stat_name)
        cost, next_level = get_ip_cost(
            "medicine" if stat_key == "medicine" else stat_name,
            current_val,
            is_attribute=stat_key in IP_ATTRIBUTES,
            is_role_ability=stat_key in IP_ROLE_ABILITIES)
        if cost is None:
            self.caller.msg(f"{get_stat_display_name(stat_name)} is already at maximum (10).")
            return

        ip_current, ip_spent, _, last_purchase, _ = get_character_ip(char)
        if ip_current < cost:
            self.caller.msg(f"You need {cost} IP to raise {get_stat_display_name(stat_name)} to {next_level}. You have {ip_current} IP.")
            return

        # Medicine: validate specialty limit (pharma/cryo max 5) before purchase
        if stat_key == "medicine" and medicine_specialty:
            from world.chargen_constants import MEDICINE_PHARMA_MAX, MEDICINE_CRYO_MAX
            s = getattr(char.db, "medicine_surgery", 0) or 0
            p = getattr(char.db, "medicine_pharma", 0) or 0
            c = getattr(char.db, "medicine_cryo", 0) or 0
            if medicine_specialty == "surgery":
                pass  # no cap
            elif medicine_specialty == "pharma":
                if p >= MEDICINE_PHARMA_MAX:
                    self.caller.msg(f"Pharmaceuticals is already at maximum ({MEDICINE_PHARMA_MAX}).")
                    return
            elif medicine_specialty == "cryo":
                if c >= MEDICINE_CRYO_MAX:
                    self.caller.msg(f"Cryosystem is already at maximum ({MEDICINE_CRYO_MAX}).")
                    return

        # Perform purchase
        set_character_stat_value(char, "medicine" if stat_key == "medicine" else stat_name, next_level)
        if stat_key == "medicine" and medicine_specialty and hasattr(char, "set_medicine_specialty"):
            key = f"medicine_{medicine_specialty}"
            current_spec = getattr(char.db, key, 0) or 0
            char.set_medicine_specialty(medicine_specialty, current_spec + 1)
        new_ip = ip_current - cost
        char.attributes.add("improvement_points", new_ip)
        char.attributes.add("ip_spent", ip_spent + cost)

        details = f"{current_val} > {next_level}"
        if stat_key == "medicine" and medicine_specialty:
            details += f" (+1 {medicine_specialty})"
        add_ip_log_entry(char, -cost, get_stat_display_name(stat_name), details)

        # Store for refund (use first_word for skill instances to preserve instance key)
        refund_stat = (
            "medicine" if stat_key == "medicine"
            else (first_word if base_skill in SKILLS_REQUIRING_INSTANCE and instance else stat_key)
        )
        refund_data = {
            "stat": refund_stat,
            "from_level": current_val,
            "to_level": next_level,
            "cost": cost,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
        if stat_key == "medicine" and medicine_specialty:
            refund_data["medicine_specialty"] = medicine_specialty
        char.attributes.add("ip_last_purchase", refund_data)

        msg = f"You spent {cost} IP to raise {get_stat_display_name(stat_name)} from {current_val} to {next_level}."
        if stat_key == "medicine" and medicine_specialty:
            msg += f" +1 {medicine_specialty.title()}."
        msg += f" You have {new_ip} IP remaining."
        self.caller.msg(msg)

    def do_refund(self):
        """Refund the last purchase."""
        char = self.get_self_character()
        if not char:
            self.caller.msg("You must be puppeting a character to refund IP.")
            return
        if not is_character_approved(char):
            self.caller.msg("You must be approved by staff before spending or refunding IP.")
            return

        last = char.attributes.get("ip_last_purchase", default=None)
        if not last:
            self.caller.msg("You have no recent purchase to refund.")
            return

        # Revert the stat
        stat_key = last.get("stat")
        from_level = last.get("from_level")
        cost = last.get("cost")
        if not stat_key or from_level is None or cost is None:
            self.caller.msg("Invalid refund data.")
            return

        set_character_stat_value(char, stat_key, from_level)

        # Medicine: also revert the specialty point that was added
        if stat_key == "medicine" and last.get("medicine_specialty"):
            spec = last["medicine_specialty"]
            key = f"medicine_{spec}"
            current = getattr(char.db, key, 0) or 0
            setattr(char.db, key, max(0, current - 1))
        ip_current, ip_spent, _, _, _ = get_character_ip(char)
        char.attributes.add("improvement_points", ip_current + cost)
        char.attributes.add("ip_spent", ip_spent - cost)
        char.attributes.add("ip_last_purchase", None)

        details = f"Refunded {get_stat_display_name(stat_key)}: {last.get('to_level')} > {from_level}"
        add_ip_log_entry(char, cost, "Refund", details)

        self.caller.msg(f"Refunded {cost} IP from {get_stat_display_name(stat_key)}. You have {ip_current + cost} IP again.")

    def do_log(self, args, is_staff):
        """View full IP log. Staff can append <name> to view another player."""
        if args and is_staff:
            target = get_target_character(self.caller, args)
            if not target:
                self.caller.msg("Could not find that character.")
                return
            char = target
        else:
            if args and not is_staff:
                self.caller.msg("Only staff can view another player's IP log.")
                return
            char = self.get_self_character()
            if not char:
                self.caller.msg("You must be puppeting a character to view IP log.")
                return

        log = char.attributes.get("ip_log", default=[]) or []
        if not log:
            self.caller.msg("No IP history recorded.")
            return

        output = header("FULL IP HISTORY", width=80, fillchar="|m=|n")
        output += "\n"
        for entry in log:
            output += format_log_entry(entry) + "\n"
        output += footer(width=80, fillchar="|m=|n")
        self.caller.msg(output)
