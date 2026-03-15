"""Dice rolling command."""
import random
import re
from evennia import Command
from world.utils.difficulty_values import parse_dv

DICE = {"d4": 4,"d6": 6, "d8": 8, "d10": 10, "d12": 12, "d20": 20, "d100": 100}


class CmdDice(Command):
    """Roll dice. Usage: dice [NdX] [+/- modifier] [vs N or difficulty name]"""
    key = "dice"
    aliases = ["d"]
    locks = "cmd:all()"
    help_category = "Roleplay Utilities"

    def func(self):
        args = (self.args or "").strip()
        vs_info = None
        vs_match = re.search(r'\s+vs\s+', args, re.IGNORECASE)
        if vs_match:
            vs_str = args[vs_match.end():].strip()
            args = args[:vs_match.start()].strip()
            vs_info = parse_dv(vs_str)
            if vs_info is None:
                self.caller.msg("Invalid difficulty. Use a number (e.g. 9) or a name (Simple, Everyday, Difficult, etc.).")
                return

        # Parse modifier (+N or -N) at end of dice expression
        modifier = 0
        mod_match = re.search(r'\s*([+-])\s*(\d+)\s*$', args)
        if mod_match:
            sign, num = mod_match.group(1), int(mod_match.group(2))
            modifier = num if sign == '+' else -num
            args = args[:mod_match.start()].strip()

        args_lower = args.lower()
        # Parse NdX or dX
        count = 1
        for key in sorted(DICE.keys(), key=len, reverse=True):
            if key in args_lower:
                idx = args_lower.find(key)
                prefix = args_lower[:idx].strip()
                count = int(prefix) if prefix else 1
                sides = DICE[key]
                break
        else:
            # Check if they used roll syntax (stat + skill vs difficulty) - suggest +roll instead
            if " + " in args:
                self.caller.msg("Syntax: +dice <number of dice><die size>, e.g., 3d10. To roll for a skill check, use +roll.")
                return
            self.caller.msg("Usage: dice [NdX] [+/- modifier] [vs N]  (X: 4,6,8,10,12,20,100)")
            return

        rolls = [random.randint(1, sides) for _ in range(count)]
        dice_total = sum(rolls)
        total = dice_total + modifier
        roll_str = " + ".join(str(r) for r in rolls)
        label = f"{count}d{sides}"
        if count > 1:
            out = f"You roll {label}: {roll_str}"
        else:
            out = f"You roll {label}: {roll_str}"
        if modifier != 0:
            mod_str = f"+ {modifier}" if modifier > 0 else f"- {-modifier}"
            out += f" {mod_str}"
        out += f" = |g{total}|n"

        if vs_info is not None:
            dv, diff_name, _ = vs_info
            if count == 1:
                success = total >= dv  # Success = meet or exceed DV
                result = "Success" if success else "Failure"
                color = "g" if success else "r"
                out += f" vs {dv}"
                if diff_name:
                    out += f" ({diff_name})"
                out += f" - |{color}{result}|n"
            else:
                successes = sum(1 for r in rolls if r >= dv)
                failures = count - successes
                out += f" vs {dv}"
                if diff_name:
                    out += f" ({diff_name})"
                out += f" - |g{successes} success|n, |r{failures} failure|n"

        self.caller.msg(out)
