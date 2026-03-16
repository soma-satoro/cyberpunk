"""
Did Someone Say Murder? - Investigation System commands (Interface RED Vol 5)
"""

import random
from datetime import date
from evennia.commands.default.muxcommand import MuxCommand
from evennia import Command
from world.utils.formatting import header, footer, divider, section_header
from world.mystery.models import Mystery, MysteryClue, CharacterFocus, ClueAttempt, ClueLocation
from world.mystery.mystery_data import (
    get_max_focus,
    CLUE_TYPES,
    COMPLEXITY_TIERS,
    OBFUSCATION_LEVELS,
)
from world.utils.character_utils import is_character_approved


def _get_character_for_caller(caller):
    """Resolve character (ObjectDB) from caller - puppeted character or caller if Account."""
    if hasattr(caller, "is_puppet") and caller.is_puppet:
        return caller
    if hasattr(caller, "character") and caller.character:
        return caller.character
    return caller if hasattr(caller, "db") else None


def _get_or_create_focus(character):
    """Get or create CharacterFocus for character. Initializes current_focus to max."""
    focus = CharacterFocus.objects.filter(character_object=character).first()
    if not focus and hasattr(character, "character_sheet") and character.character_sheet:
        focus = CharacterFocus.objects.filter(character_sheet=character.character_sheet).first()
    if not focus:
        int_val = getattr(character.db, "intelligence", 5) or 5
        will_val = getattr(character.db, "willpower", 5) or 5
        focus = CharacterFocus.objects.create(
            character_object=character,
            character_sheet=getattr(character, "character_sheet", None),
            current_focus=get_max_focus(int_val, will_val),
        )
    return focus


def _roll_dice(dice_str):
    """Parse '3d6' and return sum of rolls."""
    try:
        n, d = dice_str.lower().replace("d", " ").split()
        n, d = int(n), int(d)
        return sum(random.randint(1, d) for _ in range(n))
    except Exception:
        return 0


class CmdMystery(MuxCommand):
    """
    View investigation system status: Focus and active mysteries.

    Usage:
      +mystery              - Your Focus and active mysteries
      +mystery/focus        - Detailed Focus info
    """

    key = "+mystery"
    aliases = ["mystery"]
    lock = "cmd:all()"
    help_category = "General"

    def func(self):
        char = _get_character_for_caller(self.caller)
        if not char:
            self.caller.msg("You must be playing a character to view mysteries.")
            return
        if not is_character_approved(char):
            self.caller.msg("You must be approved by staff before using the mystery system.")
            return

        focus_obj = CharacterFocus.objects.filter(character_object=char).first()
        if not focus_obj:
            focus_obj = _get_or_create_focus(char)

        int_val = getattr(char.db, "intelligence", 5) or 5
        will_val = getattr(char.db, "willpower", 5) or 5
        max_focus = get_max_focus(int_val, will_val)
        current = focus_obj.current_focus

        out = [
            header("Investigation System"),
            f"  |gFocus:|n {current}/{max_focus}",
        ]
        if current <= 0:
            out.append("  |rYou cannot make Evidence Checks until Focus recovers.|n")
        out.append("")
        out.append("  Focus recovers every 24 hours (half your max).")
        out.append(footer())
        self.caller.msg("\n".join(out))


def _resolve_clue_from_arg(caller, char, arg):
    """
    Resolve clue from arg: either a location (here, room, NPC, object) or clue id/name.
    Returns (clue, None) or (None, error_msg).
    """
    arg = arg.strip().lower()
    # First try location-based: "here" or object/NPC in room
    if char and hasattr(char, "location") and char.location:
        if arg in ("here", "room", "location"):
            target = char.location
        else:
            # Search in room and its contents (NPCs, objects)
            target = char.search(arg, location=char.location)
        if target:
            locs = ClueLocation.objects.filter(location_object=target)
            if locs.exists():
                # Use first clue if multiple
                clue = locs.first().clue
                return clue, None
            if arg in ("here", "room", "location"):
                return None, "Nothing to investigate here."
            return None, f"Nothing to investigate on {target.key}."

    # Fall back to clue id or name
    try:
        clue_id = int(arg)
        clue = MysteryClue.objects.get(id=clue_id)
        return clue, None
    except (ValueError, MysteryClue.DoesNotExist):
        clue = MysteryClue.objects.filter(
            mystery__name__icontains=arg
        ).first() or MysteryClue.objects.filter(
            clue_type__iexact=arg
        ).first()
        if clue:
            return clue, None
    return None, "Clue not found."


class CmdInvestigate(MuxCommand):
    """
    Make an Evidence Check to gather a clue (investigation system).

    Usage:
      +investigate <target>     - Investigate a room, NPC, or object (e.g. +investigate here, +investigate corpse)
      +investigate <clue id>    - Investigate a clue by ID (abstract clues)
      +investigate/hint         - DV15 Deduction for a hint (costs 1d6 Focus)

    Targets: 'here' for current room, or any NPC/object in the room.
    Staff use +addclue to attach clues to rooms, NPCs, and objects.
    """

    key = "+investigate"
    aliases = ["investigate"]
    lock = "cmd:all()"
    help_category = "General"

    def func(self):
        if "hint" in self.switches:
            self.do_hint()
            return

        if not self.args:
            self.caller.msg("Usage: +investigate <target or clue id>")
            return

        char = _get_character_for_caller(self.caller)
        if not char:
            self.caller.msg("You must be playing a character to investigate.")
            return
        if not is_character_approved(char):
            self.caller.msg("You must be approved by staff before using the mystery system.")
            return

        focus_obj = _get_or_create_focus(char)
        if focus_obj.current_focus <= 0:
            self.caller.msg("Your Focus is depleted. Rest before making more Evidence Checks.")
            return

        clue, err = _resolve_clue_from_arg(self.caller, char, self.args)
        if err:
            self.caller.msg(err)
            return

        # Check required clues - must have succeeded on all before attempting this one
        for req in clue.required_clues.all():
            if not ClueAttempt.objects.filter(clue=req, character=char, success=True).exists():
                self.caller.msg(
                    f"You must decipher clue #{req.id} ({req.clue_type}) before this one."
                )
                return

        today = date.today()
        existing = ClueAttempt.objects.filter(
            clue=clue, character=char, attempted_date=today
        ).first()
        if existing:
            self.caller.msg(
                f"You've already attempted this clue today. Try again tomorrow."
            )
            return

        # Resolve skill + stat for check
        skill_name = clue.get_skills_list()[0] if clue.get_skills_list() else "deduction"
        skill_val = getattr(char.db, skill_name, 0) or 0
        stat_name = _skill_to_stat(skill_name)
        stat_val = getattr(char.db, stat_name, 5) or 5

        from world.utils.roll_utils import roll_skill_check, check_success

        total, details = roll_skill_check(stat_val, skill_val)
        target = clue.dv
        success = check_success(total, target)
        fumble = details.get("is_crit_failure", False)

        if success:
            damage = max(0, _roll_dice(clue.damage_dice) - clue.obfuscation)
            clue.mystery.current_complexity = max(
                0, clue.mystery.current_complexity - damage
            )
            clue.mystery.save()
            if clue.mystery.current_complexity <= 0:
                clue.mystery.solve()
            ClueAttempt.objects.create(
                clue=clue,
                character=char,
                attempted_date=today,
                success=True,
                damage_dealt=damage,
            )
            self.caller.msg(
                f"|gSuccess!|n You decipher the clue. "
                f"Dealt {damage} to the mystery. "
                f"Remaining complexity: {clue.mystery.current_complexity}."
            )
            if clue.mystery.is_solved:
                self.caller.msg(f"|yMystery solved!|n {clue.mystery.goal}")
        else:
            focus_damage = _roll_dice(clue.focus_damage_dice)
            focus_obj.current_focus -= focus_damage
            focus_obj.save()
            ClueAttempt.objects.create(
                clue=clue,
                character=char,
                attempted_date=today,
                success=False,
                focus_lost=focus_damage,
            )
            msg = f"|rFailed.|n You lose {focus_damage} Focus. ({focus_obj.current_focus} remaining)"
            if fumble:
                msg += " |rCritical Failure!|n Additional complications may apply."
            self.caller.msg(msg)

    def do_hint(self):
        char = _get_character_for_caller(self.caller)
        if not char:
            return
        if not is_character_approved(char):
            self.caller.msg("You must be approved by staff before using the mystery system.")
            return
        focus_obj = _get_or_create_focus(char)
        if focus_obj.current_focus <= 0:
            self.caller.msg("Your Focus is depleted.")
            return
        # DV15 Deduction
        skill_val = getattr(char.db, "deduction", 0) or 0
        stat_val = getattr(char.db, "intelligence", 5) or 5
        from world.utils.roll_utils import roll_skill_check, check_success
        total, details = roll_skill_check(stat_val, skill_val)
        success = check_success(total, 15)
        focus_damage = _roll_dice("1d6")
        focus_obj.current_focus -= focus_damage
        focus_obj.save()
        if success:
            self.caller.msg(
                f"|gHint:|n The GM should provide a nudge. (Lost {focus_damage} Focus.)"
            )
        else:
            self.caller.msg(f"Nothing comes to mind. Lost {focus_damage} Focus.")


class CmdClues(MuxCommand):
    """
    List all clues in the investigation system (staff).

    Usage:
      +clues                - List all clues
      +clues <mystery>      - List clues for a mystery
    """

    key = "+clues"
    aliases = ["clues"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        mystery_arg = (self.args or "").strip()
        if mystery_arg:
            try:
                mid = int(mystery_arg)
                mysteries = Mystery.objects.filter(id=mid)
            except ValueError:
                mysteries = Mystery.objects.filter(name__icontains=mystery_arg)
            if not mysteries.exists():
                self.caller.msg("Mystery not found.")
                return
            mysteries = list(mysteries)
        else:
            mysteries = list(Mystery.objects.all().order_by("name"))

        lines = [header("Investigation Clues")]
        for m in mysteries:
            clues = m.clues.all().order_by("id")
            lines.append(section_header(m.name))
            lines.append(f"  Goal: {m.goal[:60]}{'...' if len(m.goal) > 60 else ''}")
            lines.append(f"  Complexity: {m.current_complexity}/{m.max_complexity}  Solved: {m.is_solved}")
            for c in clues:
                reqs = list(c.required_clues.values_list("id", flat=True))
                locs = ClueLocation.objects.filter(clue=c)
                loc_str = ", ".join(str(loc.location_object.key) for loc in locs[:3])
                if locs.count() > 3:
                    loc_str += f" (+{locs.count() - 3} more)"
                lines.append(
                    f"    |y#{c.id}|n {c.clue_type} DV{c.dv} "
                    f"(skills: {c.skills_used[:30]}...) "
                    f"{'[requires: ' + ','.join(f'#{r}' for r in reqs) + ']' if reqs else ''}"
                )
                if loc_str:
                    lines.append(f"      @ {loc_str}")
            lines.append("")
        lines.append(footer())
        self.caller.msg("\n".join(lines))


class CmdCreateMystery(MuxCommand):
    """
    Create a new mystery (staff).

    Usage:
      +createmystery <name>=<goal>,<complexity>
    """

    key = "+createmystery"
    aliases = ["createmystery"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +createmystery <name>=<goal>,<complexity>")
            return
        name = self.lhs.strip()
        rhs = self.rhs.strip()
        parts = [p.strip() for p in rhs.split(",", 1)]
        goal = parts[0] if parts else ""
        try:
            complexity = int(parts[1]) if len(parts) > 1 else 50
        except (ValueError, IndexError):
            complexity = 50
        char = _get_character_for_caller(self.caller)
        m = Mystery.objects.create(
            name=name,
            goal=goal,
            max_complexity=complexity,
            current_complexity=complexity,
            created_by=char,
        )
        self.caller.msg(f"Created Mystery #{m.id}: {m.name} (complexity {complexity})")


class CmdCreateClue(MuxCommand):
    """
    Create a new clue and add it to a mystery (staff).

    Usage:
      +createclue <mystery id>=<clue_type>,<skills>,<dv>,<obfuscation>
    Example:
      +createclue 1=forensics,criminology;deduction,13,2
    """

    key = "+createclue"
    aliases = ["createclue"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: +createclue <mystery id>=<type>,<skills>,<dv>,<obfuscation>"
            )
            return
        try:
            mid = int(self.lhs.strip())
            mystery = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        parts = [p.strip() for p in self.rhs.split(",")]
        clue_type = parts[0].lower() if parts else "deduction"
        skills = parts[1].replace(";", ", ") if len(parts) > 1 else "deduction"
        try:
            dv = int(parts[2]) if len(parts) > 2 else 13
        except (ValueError, IndexError):
            dv = 13
        try:
            obfuscation = int(parts[3]) if len(parts) > 3 else 0
        except (ValueError, IndexError):
            obfuscation = 0
        defaults = CLUE_TYPES.get(clue_type, {})
        damage_dice = defaults.get("damage_dice", "3d6")
        focus_damage_dice = defaults.get("focus_damage_dice", "2d6")
        c = MysteryClue.objects.create(
            mystery=mystery,
            clue_type=clue_type,
            skills_used=skills,
            dv=dv,
            obfuscation=obfuscation,
            damage_dice=damage_dice,
            focus_damage_dice=focus_damage_dice,
        )
        self.caller.msg(
            f"Created Clue #{c.id} ({c.clue_type}) for {mystery.name}. "
            f"Use +addclue <target>={c.id} to attach to a location."
        )


class CmdDestroyClue(MuxCommand):
    """
    Remove a clue from an object, or delete it from the system entirely (staff).

    Usage:
      +destroyclue <clue id>              - Delete clue from system (removes from all locations)
      +destroyclue <target>=<clue id>      - Remove clue from target only (same as +addclue/remove)
    """

    key = "+destroyclue"
    aliases = ["destroyclue"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: +destroyclue <clue id> or +destroyclue <target>=<clue id>")
            return
        if "=" in self.args:
            # Remove from target only
            target_name = self.lhs.strip()
            try:
                clue_id = int(self.rhs.strip())
                clue = MysteryClue.objects.get(id=clue_id)
            except (ValueError, MysteryClue.DoesNotExist):
                self.caller.msg("Clue not found.")
                return
            target = self.caller.search(target_name, global_search=True)
            if not target:
                return
            deleted, _ = ClueLocation.objects.filter(
                clue=clue,
                location_object=target,
            ).delete()
            if deleted:
                self.caller.msg(f"Removed clue #{clue_id} from {target.key}.")
            else:
                self.caller.msg(f"Clue #{clue_id} was not attached to {target.key}.")
            return
        try:
            clue_id = int(self.args.strip())
            clue = MysteryClue.objects.get(id=clue_id)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Clue not found.")
            return
        name = str(clue)
        clue.delete()
        self.caller.msg(f"Destroyed clue #{clue_id} ({name}). Removed from all locations.")


class CmdLinkClue(MuxCommand):
    """
    Link clues: set required_clues or linked_clues (staff).

    Usage:
      +linkclue <clue>=<clue id>              - Add to linked_clues (bidirectional)
      +linkclue/requires <clue>=<clue id>      - Add as required (must decipher before this clue)
    """

    key = "+linkclue"
    aliases = ["linkclue"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg(
                "Usage: +linkclue <clue>=<id> or +linkclue/requires <clue>=<id>"
            )
            return
        try:
            c1_id = int(self.lhs.strip())
            c1 = MysteryClue.objects.get(id=c1_id)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Clue not found (left side).")
            return
        try:
            c2_id = int(self.rhs.strip())
            c2 = MysteryClue.objects.get(id=c2_id)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Clue not found (right side).")
            return
        if c1.mystery_id != c2.mystery_id:
            self.caller.msg("Both clues must belong to the same mystery.")
            return
        if "requires" in self.switches:
            c1.required_clues.add(c2)
            self.caller.msg(f"Clue #{c1_id} now requires clue #{c2_id} to be deciphered first.")
        else:
            c1.linked_clues.add(c2)
            self.caller.msg(f"Linked clue #{c1_id} to clue #{c2_id}.")


class CmdMysteryLink(MuxCommand):
    """
    Link a mystery to a mission. When solved, mission and job are updated (staff).

    Usage:
      +mysterylink <mystery id>=<mission id>
      +mysterylink/unlink <mystery id>   - Remove mission link
    """

    key = "+mysterylink"
    aliases = ["mysterylink"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: +mysterylink <mystery id>=<mission id>")
            return
        try:
            mid = int((self.lhs or self.args).strip())
            mystery = Mystery.objects.get(id=mid)
        except (ValueError, Mystery.DoesNotExist):
            self.caller.msg("Mystery not found.")
            return
        if "unlink" in self.switches:
            mystery.mission = None
            mystery.save()
            self.caller.msg(f"Unlinked mystery '{mystery.name}' from mission.")
            return
        try:
            mission_id = int(self.rhs.strip())
            from world.mission_board.models import Mission
            mission = Mission.objects.get(id=mission_id)
        except (ValueError, Mission.DoesNotExist):
            self.caller.msg("Mission not found.")
            return
        mystery.mission = mission
        mystery.save()
        self.caller.msg(f"Linked mystery '{mystery.name}' to Mission #{mission.id}: {mission.name}")


class CmdAddClue(MuxCommand):
    """
    Attach or remove investigation clues from rooms, NPCs, and objects.

    Usage:
      +addclue <target>=<clue id>    - Attach clue to room/NPC/object
      +addclue/remove <target>=<clue id>  - Remove clue from target
      +addclue/list <target>          - List clues attached to target
    """

    key = "+addclue"
    aliases = ["addclue"]
    lock = "cmd:perm(builders)"
    help_category = "Building"

    def func(self):
        if "list" in self.switches:
            target_name = (self.lhs or self.args or "").strip()
            if target_name:
                self.do_list(target_name)
            else:
                self.caller.msg("Usage: +addclue/list <target>")
            return

        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +addclue <target>=<clue id>")
            return

        target_name = self.lhs.strip()
        clue_arg = self.rhs.strip()

        target = self.caller.search(target_name, global_search=True)
        if not target:
            return

        try:
            clue_id = int(clue_arg)
            clue = MysteryClue.objects.get(id=clue_id)
        except (ValueError, MysteryClue.DoesNotExist):
            self.caller.msg("Clue not found. Use a numeric clue ID.")
            return

        if "remove" in self.switches:
            deleted, _ = ClueLocation.objects.filter(
                clue=clue,
                location_object=target,
            ).delete()
            if deleted:
                self.caller.msg(f"Removed clue #{clue_id} from {target.key}.")
            else:
                self.caller.msg(f"Clue #{clue_id} was not attached to {target.key}.")
            return

        _, created = ClueLocation.objects.get_or_create(
            clue=clue,
            location_object=target,
        )
        if created:
            self.caller.msg(f"Attached clue #{clue_id} ({clue.clue_type}) to {target.key}.")
        else:
            self.caller.msg(f"Clue #{clue_id} is already attached to {target.key}.")

    def do_list(self, target_name):
        target = self.caller.search(target_name.strip(), global_search=True)
        if not target:
            return
        locs = ClueLocation.objects.filter(location_object=target)
        if not locs.exists():
            self.caller.msg(f"No clues attached to {target.key}.")
            return
        lines = [f"Clues on {target.key}:"]
        for loc in locs:
            c = loc.clue
            lines.append(f"  #{c.id} {c.clue_type} (Mystery: {c.mystery.name})")
        self.caller.msg("\n".join(lines))


def _skill_to_stat(skill_name):
    """Map skill to primary stat for Evidence Checks."""
    stat_map = {
        "intelligence": ["concentration", "conceal_object", "lip_reading", "perception", "tracking",
                        "accounting", "animal_handling", "bureaucracy", "business", "composition",
                        "criminology", "cryptography", "deduction", "education", "library_search",
                        "local_expert", "tactics", "wilderness_survival"],
        "reflexes": ["drive_land", "pilot_air", "pilot_sea", "riding", "archery", "autofire",
                    "handgun", "heavy_weapons", "shoulder_arms"],
        "dexterity": ["athletics", "contortionist", "dance", "endurance", "resist_torture_drugs",
                     "stealth", "brawling", "evasion", "martial_arts", "melee"],
        "technology": ["basic_tech", "cybertech", "demolitions", "electronics", "first_aid",
                      "forgery", "paramedic", "medicine", "surgery", "pick_lock", "weaponstech",
                      "air_vehicle_tech", "land_vehicle_tech", "sea_vehicle_tech"],
        "cool": ["acting", "play_instrument", "style", "bribery", "conversation", "human_perception",
                "interrogation", "persuasion", "streetwise", "trading"],
    }
    for stat, skills in stat_map.items():
        if skill_name in skills:
            return stat
    return "intelligence"
