"""
Cyberpunk RED netrunning command.

Floor-based NET architectures per the core rulebook. Uses +net/scan, +net/jackin, etc.
"""

import random
from collections import Counter
from datetime import datetime, timezone

import evennia
from evennia.commands.default.muxcommand import MuxCommand

from world.netrunning.red_netrunning import (
    ALL_PROGRAMS,
    DIFFICULTY_DV,
    _format_interface_dice,
    get_active_defense_template,
    generate_demon_for_architecture,
    generate_architecture,
    generate_paydata_entry,
    get_black_ice,
    get_demon,
    get_interface_rank,
    get_program,
    interface_check,
    net_actions_for_rank,
    normalize_name,
)
from world.utils.permission_utils import check_builder_permission
from world.utils.character_utils import is_character_approved
from world.inventory.models import CyberwareInstance
from world.netrunning.deck_loadout import (
    format_deck_sheet,
    get_deck_loadouts,
    installable_program_or_ice,
    install_deck_item,
    ensure_program_gear,
    remove_deck_item,
)
from world.netrunning.models import NetFloorLead
from world.netrunning import net_discovery as net_disc
from world.netrunning import deckoptions
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.inventory.models import Inventory
from world.utils.name_fuzzy import pick_named_candidate
from world.maker.services import create_program_order
from world.maker.scripts import get_or_create_maker_script


def _roll_dice(dice: str) -> int:
    num, die = dice.lower().split("d", 1)
    return sum(random.randint(1, int(die)) for _ in range(int(num)))


class CmdNet(MuxCommand):
    """
    Create and run Cyberpunk RED net architectures.

    Player usage:
        +net/scan
        +net/jackin <architecture>
        +net/jackout
        +net/status
        +net/move <down|up|floor#>[=<child floor#|branch>]  - branch selector for split paths
        +net/pathfinder
        +net/cloak
        +net/backdoor
        +net/eyedee
        +net/control
        +net/grab
        +net/programs
        +net/activate <program>
        +net/deactivate <program>
        +net/zap [=target]              - target: ICE name or index when multiple
        +net/attack <program> [=target] - target: ICE name or index when multiple
        +net/slide <up|floor#>[=<target>] - disengage + move upward, target by ICE name/index
        +net/virus [status|start <dv>/<actions>=<description>|work|abort|list]
        +net/buy <program or Black ICE>  - Purchase to inventory (for deck install later)
        +net/craft <program>             - Queue program crafting job (same as +make/program/add)
        +net/deck                        - Same as |wdeck|n (full cyberdeck sheet)
        +net/deck/install <deck>=<item> - Install program, Black ICE, or hardware
        +net/deck/remove <deck>=<item> - Unload to inventory (|wdeck/...|n also works)
        +net/delve                        - Sweep current floor for hidden staff-placed leads (Interface)
        +net/trace [lead id]              - Crack a swept lead (Interface); grants paydata / program / text
        +net/leads                        - Notebook: swept leads on this floor and links
        +net/hostiles [all]               - Show hostile ICE/runners on current floor or entire architecture
        +net/extinguish                   - Spend Meat Action to put out Hellhound fire
        +net/counter [status|start|work|abort] - Counter linked defense workflow
        +net/demon [status|pause|resume|on|off] - Demon controls (staff for on/off)

    Staff/Storyteller usage:
        +net/create <name>=<difficulty>[,<floors>]
        +net/generate <arch>=<difficulty>[,<floors>]
        +net/show <arch>
        +net/setfloor <arch>=<floor>/<type>[/<value>]
        +net/autopaydata <arch>=<on|off>
        +net/refreshpaydata
        +net/intruder <novice|professional|expert|master>[,<count>]
        +net/lead/create|list|destroy|requires|link|paydata|program|text|teaser|priority|notes
            - Floor narrative leads (Builder)
    """

    key = "+net"
    aliases = ["net", "netrun", "+netrun"]
    locks = "cmd:all()"
    help_category = "Netrunning"

    STAFF_SWITCHES = {"create", "generate", "setfloor", "autopaydata", "refreshpaydata", "intruder"}

    def func(self):
        if not self.switches:
            self.cmd_status()
            return

        switch = self.switches[0].lower()
        if switch == "lead":
            if not check_builder_permission(self.caller):
                self.caller.msg("Only staff/storytellers can manage NET floor leads.")
                return
            self._cmd_net_lead()
            return
        if switch == "deck":
            self._cmd_deck()
            return
        if switch in self.STAFF_SWITCHES and not check_builder_permission(self.caller):
            self.caller.msg("Only staff/storytellers can use that switch.")
            return

        dispatch = {
            "scan": self.cmd_scan,
            "jackin": self.cmd_jackin,
            "jackout": self.cmd_jackout,
            "status": self.cmd_status,
            "move": self.cmd_move,
            "pathfinder": self.cmd_pathfinder,
            "cloak": self.cmd_cloak,
            "backdoor": self.cmd_backdoor,
            "bypass": self.cmd_backdoor,
            "eyedee": self.cmd_eyedee,
            "control": self.cmd_control,
            "grab": self.cmd_grab,
            "programs": self.cmd_programs,
            "activate": self.cmd_activate,
            "deactivate": self.cmd_deactivate,
            "zap": self.cmd_zap,
            "attack": self.cmd_attack_program,
            "slide": self.cmd_slide,
            "virus": self.cmd_virus,
            "buy": self.cmd_buy_program,
            "craft": self.cmd_craft_program,
            "create": self.cmd_create_architecture,
            "generate": self.cmd_generate_architecture,
            "show": self.cmd_show_architecture,
            "setfloor": self.cmd_setfloor,
            "autopaydata": self.cmd_autopaydata,
            "refreshpaydata": self.cmd_refresh_paydata,
            "intruder": self.cmd_intruder,
            "delve": self.cmd_delve,
            "trace": self.cmd_trace,
            "leads": self.cmd_leads,
            "hostiles": self.cmd_hostiles,
            "extinguish": self.cmd_extinguish,
            "counter": self.cmd_counter,
            "demon": self.cmd_demon,
        }
        handler = dispatch.get(switch)
        if not handler:
            self.caller.msg(f"Unknown switch '{switch}'. See help +net.")
            return
        handler()

    def _cmd_deck(self):
        """Cyberdeck loadout (delegates to same logic as |wdeck|n)."""
        subs = [s.lower() for s in (self.switches or [])[1:]]
        if not subs:
            self.caller.msg(format_deck_sheet(self.caller))
            return
        sub = subs[0]
        raw = (self.args or "").strip()
        if sub == "install":
            if "=" not in raw:
                self.caller.msg(
                    "Usage: +net/deck/install <cyberdeck name>=<program, Black ICE, or hardware>"
                )
                return
            left, right = raw.split("=", 1)
            ok, msg = install_deck_item(self.caller, left.strip(), right.strip())
            self.caller.msg(msg if ok else f"|r{msg}|n")
            return
        if sub == "remove":
            if "=" not in raw:
                self.caller.msg("Usage: +net/deck/remove <cyberdeck name>=<installed item>")
                return
            left, right = raw.split("=", 1)
            ok, msg = remove_deck_item(self.caller, left.strip(), right.strip())
            self.caller.msg(msg if ok else f"|r{msg}|n")
            return
        self.caller.msg(
            "Use |wdeck|n or |w+net/deck|n for your sheet; |wdeck/install|n or |w+net/deck/install|n to load."
        )

    def _get_state(self):
        return self.caller.db.netrun_state or {}

    def _set_state(self, state):
        self.caller.db.netrun_state = state

    def _clear_state(self):
        self.caller.db.netrun_state = {}

    def _is_jacked_in(self):
        return bool(self._get_state().get("active"))

    def _find_architecture(self, name):
        if not name:
            return None
        local = self.caller.search(name, location=self.caller.location, quiet=True)
        if local:
            for obj in local:
                if hasattr(obj, "db") and getattr(obj.db, "is_net_architecture", False):
                    return obj
        global_matches = evennia.search_object(name)
        for obj in global_matches:
            if hasattr(obj, "db") and getattr(obj.db, "is_net_architecture", False):
                return obj
        return None

    def _current_architecture(self):
        state = self._get_state()
        arch_id = state.get("architecture_id")
        if not arch_id:
            return None
        match = evennia.search_object(f"#{arch_id}")
        if not match:
            return None
        arch = match[0]
        if not getattr(arch.db, "is_net_architecture", False):
            return None
        return arch

    def _require_netrun(self):
        if not self._is_jacked_in():
            self.caller.msg("You are not jacked in. Use +net/jackin <architecture>.")
            return False
        return True

    def _interface_bonus(self, state, check_type):
        active = state.get("active_programs", {})
        bonus = 0
        if check_type == "backdoor" and "worm" in active:
            bonus += 2
        if check_type == "pathfinder" and "see_ya" in active:
            bonus += 2
        if check_type == "cloak" and "eraser" in active:
            bonus += 2
        if check_type == "speed" and "speedy_gonzalvez" in active:
            bonus += 2
        return bonus

    def _installed_cyberware_names(self):
        """
        Return normalized installed cyberware names for this character.
        """
        sheet = getattr(self.caller, "character_sheet", None)
        if not sheet:
            return []
        try:
            installed = CyberwareInstance.objects.filter(character_sheet=sheet, installed=True).select_related("cyberware")
        except Exception:
            return []
        return [normalize_name((cw.cyberware.name or "").strip()) for cw in installed if getattr(cw, "cyberware", None)]

    def _net_action_modifiers(self, state):
        """
        Compute additive NET Action modifiers from deck/cyberware effects.
        Returns (bonus_int, [reason strings]).
        """
        bonus = 0
        reasons = []
        deck_name = str(state.get("deck_name", "") or "")
        deck_key = normalize_name(deck_name)

        # Deck passive: Raven Microcyb Hummingbird grants +1 NET Action/turn.
        if deck_key == "raven_microcyb_hummingbird":
            bonus += 1
            reasons.append("+1 Raven Microcyb Hummingbird")

        # Ex-Disk: 2+ installed + physically connected through Interface Plugs.
        installed_names = self._installed_cyberware_names()
        exdisk_count = sum(1 for name in installed_names if name in {"ex-disk", "ex_disk"})
        has_interface_plugs = "interface_plugs" in set(installed_names)
        if exdisk_count >= 2 and has_interface_plugs:
            bonus += 1
            reasons.append("+1 Ex-Disk x2 (Interface Plug link)")

        return bonus, reasons

    def _get_floor(self, arch, state):
        floors = arch.db.floors or []
        idx = int(state.get("floor", 1)) - 1
        if idx < 0 or idx >= len(floors):
            return None
        return floors[idx]

    def _get_floor_by_num(self, arch, floor_num):
        floors = arch.db.floors or []
        idx = int(floor_num) - 1
        if idx < 0 or idx >= len(floors):
            return None
        return floors[idx]

    def _entry_room(self, state):
        room_id = state.get("entry_location_id")
        if not room_id:
            return None
        found = evennia.search_object(f"#{room_id}")
        return found[0] if found else None

    def _room_tag_set(self, room):
        tags = set()
        if not room:
            return tags
        db_tags = getattr(room.db, "tags", None) or []
        for t in db_tags:
            if t:
                tags.add(str(t).strip().lower().replace(" ", "_"))
        try:
            for tag in (room.tags.get() or []):
                tags.add(str(tag).strip().lower().replace(" ", "_"))
        except Exception:
            pass
        return tags

    def _children_for_floor(self, floor):
        data = floor.get("children")
        if isinstance(data, list):
            return [int(x) for x in data if str(x).isdigit() or isinstance(x, int)]
        return []

    def _parent_for_floor(self, floor):
        parent = floor.get("parent")
        if parent is None:
            return None
        try:
            return int(parent)
        except (TypeError, ValueError):
            return None

    def _record_trace_action(self, state, label):
        """
        Record runner actions that would appear in architecture forensic logs.
        """
        if not self._is_jacked_in():
            return
        if state.get("trace_sealed", False):
            # Cloak already sealed this run's trail.
            return
        if normalize_name(label or "") in {"status"}:
            return
        actions = list(state.get("trace_actions", []) or [])
        actions.append(
            {
                "turn": int(state.get("trace_turn", 1) or 1),
                "floor": int(state.get("floor", 1) or 1),
                "label": str(label or "NET Action")[:120],
            }
        )
        # Keep reasonable bound.
        if len(actions) > 300:
            actions = actions[-300:]
        state["trace_actions"] = actions

    def _archive_trace_if_exposed(self, state, arch, unsafe=False):
        """
        Persist a run trace if runner jacks out without successful Cloak.
        """
        if state.get("trace_sealed", False):
            self.caller.msg("|gCloak scrub completes. Your run leaves no useful forensic trail.|n")
            return
        actions = list(state.get("trace_actions", []) or [])
        if not actions:
            return
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "architecture_id": getattr(arch, "id", None),
            "architecture": getattr(arch, "key", "Unknown"),
            "unsafe": bool(unsafe),
            "actions": actions,
        }
        exposed = list(self.caller.db.netrun_exposed_traces or [])
        exposed.append(record)
        self.caller.db.netrun_exposed_traces = exposed[-50:]
        self.caller.msg(
            "|rYou jack out without a successful Cloak. Enemy netrunners can automatically reconstruct your actions in this architecture.|n"
        )

    def _electronics_security_skill(self):
        sheet = getattr(self.caller, "character_sheet", None)
        if sheet and hasattr(sheet, "electronics_security_tech"):
            return int(getattr(sheet, "electronics_security_tech") or 0)
        skills = getattr(self.caller.db, "skills", None) or {}
        for key in ("electronics_security_tech", "electronics/security_tech"):
            if key in skills:
                return int(skills.get(key) or 0)
        return 0

    def _brain_damage(self, amount, reason):
        state = self._get_state()
        active = state.get("active_programs", {})
        if "armor" in active:
            reduced = max(0, int(amount) - 4)
            if reduced != amount:
                self.caller.msg(f"|xArmor absorbs 4 brain damage ({amount} -> {reduced}).|n")
            amount = reduced
        if amount <= 0:
            return
        self.caller.take_damage(amount)
        self.caller.msg(f"|rBrain burn: {amount} damage ({reason}).|n")
        hp = getattr(self.caller.db, "current_hp", None)
        if hp is not None and hp <= 0:
            # During unsafe jack-out backlash resolution, avoid recursively
            # calling jack-out again for each individual damage packet.
            if state.get("_jackout_in_progress"):
                return
            self.caller.msg("|rYou flatline from neural feedback!|n")
            self._do_jackout(unsafe=True)

    def _choose_jackin_deck(self):
        """
        Pick the deck used for this run:
        - first deck carrying at least one installed program/ICE
        - else first carried cyberdeck
        """
        inv, _ = Inventory.get_or_create_for_character(self.caller)
        decks = [g.name for g in inv.gear.all() if getattr(g, "is_cyberdeck", False)]
        if not decks:
            return None
        loadouts = get_deck_loadouts(self.caller)
        for deck_name in decks:
            programs = (loadouts.get(deck_name) or {}).get("programs", [])
            if programs:
                return deck_name
        return decks[0]

    def _installed_programs_for_deck(self, deck_name):
        """
        Return map(normalized_name -> display_name) for deck-installed programs/Black ICE.
        """
        if not deck_name:
            return {}
        loadouts = get_deck_loadouts(self.caller)
        names = (loadouts.get(deck_name) or {}).get("programs", [])
        out = {}
        for name in names:
            key = normalize_name(name or "")
            if key:
                out[key] = name
        return out

    def _apply_jackin_deck_automation(self, state):
        """
        Apply immediate-on-jackin deck effects that grant free setup actions.
        """
        deck_key = normalize_name(str(state.get("deck_name", "") or ""))
        installed = state.get("installed_programs", {}) or {}
        destroyed = set(state.get("destroyed_programs", []) or [])
        active = state.get("active_programs", {}) or {}
        notes = []

        if deck_key == "microtech_scout":
            state["free_pathfinder_uses"] = int(state.get("free_pathfinder_uses", 0) or 0) + 1
            notes.append("Microtech Scout grants one free Pathfinder use.")

        if deck_key == "microtech_warrior":
            pkey = "armor"
            if pkey in installed and pkey not in destroyed and pkey not in active:
                prog = get_program("armor")
                if prog:
                    active[pkey] = {
                        "name": prog["name"],
                        "rez": int(prog.get("rez", 0) or 0),
                        "def": int(prog.get("def", 0) or 0),
                    }
                    notes.append("Microtech Warrior auto-activates Armor (no NET Action).")

        if deck_key == "raven_microcyb_kestrel_2":
            pkey = "speedy_gonzalvez"
            if pkey in installed and pkey not in destroyed and pkey not in active:
                prog = get_program("speedy gonzalvez")
                if prog:
                    active[pkey] = {
                        "name": prog["name"],
                        "rez": int(prog.get("rez", 0) or 0),
                        "def": int(prog.get("def", 0) or 0),
                    }
                    notes.append("Kestrel 2 auto-activates Speedy Gonzalvez (no NET Action).")

        state["active_programs"] = active
        return notes

    def _get_active_ice_on_floor(self, state, floor_num):
        ice_state = state.get("ice_state", {})
        return ice_state.get(str(floor_num), [])

    def _set_active_ice_on_floor(self, state, floor_num, data):
        ice_state = state.get("ice_state", {})
        ice_state[str(floor_num)] = data
        state["ice_state"] = ice_state

    def _next_ice_uid(self, state):
        uid = int(state.get("ice_uid_counter", 0) or 0) + 1
        state["ice_uid_counter"] = uid
        return uid

    def _ice_display_names(self, ice_list):
        """
        Returns list of per-instance display names with numbered suffixes for duplicates.
        """
        counts = Counter(normalize_name(i.get("name", "")) for i in ice_list)
        seen = Counter()
        labels = []
        for ice in ice_list:
            key = normalize_name(ice.get("name", ""))
            seen[key] += 1
            if counts[key] > 1:
                labels.append(f"{ice.get('name', 'ICE')}{seen[key]}")
            else:
                labels.append(ice.get("name", "ICE"))
        return labels

    def _move_pursuing_ice(self, state, from_floor, to_floor):
        """
        Move all active, pursuing ICE from one floor to another.
        """
        if from_floor == to_floor:
            return
        source = list(self._get_active_ice_on_floor(state, from_floor))
        if not source:
            return
        staying = []
        chasing = []
        for ice in source:
            if ice.get("active") and ice.get("pursuing", True):
                ice["current_floor"] = int(to_floor)
                ice["encountered"] = True
                chasing.append(ice)
            else:
                staying.append(ice)
        if not chasing:
            return
        dest = list(self._get_active_ice_on_floor(state, to_floor))
        dest.extend(chasing)
        self._set_active_ice_on_floor(state, from_floor, staying)
        self._set_active_ice_on_floor(state, to_floor, dest)

    def _enemy_runners_on_floor(self, state, floor_num):
        return (state.get("enemy_runners", {}) or {}).get(str(int(floor_num)), [])

    def _set_enemy_runners_on_floor(self, state, floor_num, runners):
        all_runners = state.get("enemy_runners", {}) or {}
        all_runners[str(int(floor_num))] = runners
        state["enemy_runners"] = all_runners

    def _iter_enemy_runners(self, state):
        all_runners = state.get("enemy_runners", {}) or {}
        for floor_key, runners in all_runners.items():
            try:
                floor_num = int(floor_key)
            except (TypeError, ValueError):
                continue
            for runner in list(runners or []):
                yield floor_num, runner

    def _enemy_runner_display_names(self, runner_list):
        counts = Counter(normalize_name(r.get("name", "")) for r in runner_list)
        seen = Counter()
        labels = []
        for runner in runner_list:
            key = normalize_name(runner.get("name", ""))
            seen[key] += 1
            if counts[key] > 1:
                labels.append(f"{runner.get('name', 'Runner')}#{seen[key]}")
            else:
                labels.append(runner.get("name", "Runner"))
        return labels

    def _pick_runner_target(self, runner_list, target_arg):
        if not runner_list:
            return None, -1
        if not target_arg or not target_arg.strip():
            return runner_list[0], 0
        arg = target_arg.strip()
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(runner_list):
                return runner_list[idx], idx
            return None, -1
        arg_key = normalize_name(arg)
        labels = self._enemy_runner_display_names(runner_list)
        for idx, runner in enumerate(runner_list):
            if normalize_name(runner.get("name", "")) == arg_key or normalize_name(labels[idx]) == arg_key:
                return runner, idx
        return None, -1

    def _move_enemy_runner_between_floors(self, state, runner, from_floor, to_floor):
        if int(from_floor) == int(to_floor):
            return
        source = list(self._enemy_runners_on_floor(state, from_floor))
        dest = list(self._enemy_runners_on_floor(state, to_floor))
        if runner in source:
            source.remove(runner)
        runner["floor"] = int(to_floor)
        dest.append(runner)
        self._set_enemy_runners_on_floor(state, from_floor, source)
        self._set_enemy_runners_on_floor(state, to_floor, dest)

    def _adjacent_floors(self, arch, floor_num):
        floor = self._get_floor_by_num(arch, floor_num)
        if not floor:
            return []
        children = self._children_for_floor(floor)
        parent = self._parent_for_floor(floor)
        out = list(children)
        if parent:
            out.append(parent)
        if not out:
            # Legacy linear fallback.
            if floor_num > 1:
                out.append(floor_num - 1)
            floors = arch.db.floors or []
            if floor_num < len(floors):
                out.append(floor_num + 1)
        return sorted(set(int(x) for x in out if int(x) > 0))

    def _next_floor_toward(self, arch, start_floor, goal_floor):
        start = int(start_floor)
        goal = int(goal_floor)
        if start == goal:
            return start
        queue = [start]
        parents = {start: None}
        while queue:
            cur = queue.pop(0)
            if cur == goal:
                break
            for nxt in self._adjacent_floors(arch, cur):
                if nxt in parents:
                    continue
                parents[nxt] = cur
                queue.append(nxt)
        if goal not in parents:
            # Unreachable graph edge case: stay put.
            return start
        # Walk backward from goal to first hop after start.
        hop = goal
        while parents.get(hop) is not None and parents.get(hop) != start:
            hop = parents[hop]
        return hop if parents.get(hop) == start else goal

    def _enemy_runner_brain_hp_for_interface(self, iface):
        return max(8, 10 + int(iface) * 2)

    def _enemy_runner_use_program(self, runner, prog_name):
        used = set(runner.get("used_programs", []) or [])
        if prog_name:
            used.add(normalize_name(prog_name))
        runner["used_programs"] = list(used)

    def _enemy_runner_program_used(self, runner, prog_name):
        return normalize_name(prog_name) in set(runner.get("used_programs", []) or [])

    def _spawn_enemy_runner(self, state, floor_num, tier="professional"):
        tier = (tier or "professional").strip().lower()
        ranges = {
            "novice": (1, 3),
            "professional": (4, 6),
            "expert": (7, 9),
            "master": (10, 10),
        }
        lo, hi = ranges.get(tier, ranges["professional"])
        iface = random.randint(lo, hi)
        state["enemy_runner_counter"] = int(state.get("enemy_runner_counter", 0) or 0) + 1
        idx = state["enemy_runner_counter"]
        candidate_programs = ["Vrizzbolt", "Superglue", "Nervescrub", "Poison Flatline", "Hellbolt", "DeckKRASH"]
        random.shuffle(candidate_programs)
        runner = {
            "id": idx,
            "name": f"Enemy Netrunner {idx}",
            "tier": tier,
            "interface": iface,
            "floor": int(floor_num),
            "active": True,
            "programs": candidate_programs[:3],
            "used_programs": [],
            "brain_hp": self._enemy_runner_brain_hp_for_interface(iface),
            "lock_deeper_rounds": 0,
            "lock_safe_jackout_rounds": 0,
            "action_penalty_next": 0,
        }
        current = list(self._enemy_runners_on_floor(state, floor_num))
        current.append(runner)
        self._set_enemy_runners_on_floor(state, floor_num, current)
        self.caller.msg(
            f"|rALERT: {runner['name']} ({tier}, Interface {iface}) has entered this architecture level.|n"
        )

    def _register_alarm(self, state, reason="intrusion activity", amount=1):
        new_alarm = int(state.get("alarm_level", 0) or 0) + int(amount or 1)
        state["alarm_level"] = new_alarm
        self.caller.msg(f"|yAlarm level rises to {new_alarm}:|n {reason}.")
        floor_num = int(state.get("floor", 1) or 1)
        active_runners = [
            r for _, r in self._iter_enemy_runners(state)
            if r.get("active")
        ]
        if new_alarm >= 3 and not active_runners:
            tier = "professional"
            if new_alarm >= 8:
                tier = "master"
            elif new_alarm >= 6:
                tier = "expert"
            self._spawn_enemy_runner(state, floor_num, tier=tier)

    def _run_enemy_runner_turn(self, state):
        arch = self._current_architecture()
        if not arch:
            return
        active = [(f, r) for f, r in self._iter_enemy_runners(state) if r.get("active")]
        if not active:
            return
        runner_floor = int(state.get("floor", 1) or 1)
        self.caller.msg("|rENEMY NETRUNNER TURN: hostile operators execute routines.|n")
        for floor_num, runner in active:
            if not self._is_jacked_in():
                return
            iface = int(runner.get("interface", 4) or 4)
            penalty = int(runner.get("action_penalty", 0) or 0)
            actions = max(2, int(net_actions_for_rank(iface)) - penalty)
            if int(runner.get("lock_deeper_rounds", 0) or 0) > 0:
                runner["lock_deeper_rounds"] = int(runner.get("lock_deeper_rounds", 0)) - 1
            if int(runner.get("lock_safe_jackout_rounds", 0) or 0) > 0:
                runner["lock_safe_jackout_rounds"] = int(runner.get("lock_safe_jackout_rounds", 0)) - 1
            # Runner moves toward target floor when separated.
            if int(floor_num) != runner_floor:
                step = self._next_floor_toward(arch, floor_num, runner_floor)
                if int(step) != int(floor_num):
                    self._move_enemy_runner_between_floors(state, runner, floor_num, step)
                    self.caller.msg(
                        f"  {runner['name']} shifts position through the architecture (F{floor_num} -> F{step})."
                    )
                    floor_num = step
            if int(floor_num) != runner_floor:
                continue
            # Same floor: execute actions with simple priorities.
            for _ in range(actions):
                if not self._is_jacked_in():
                    return
                program_pool = list(runner.get("programs") or [])
                active_programs = state.get("active_programs", {}) or {}
                caller_hp = int(getattr(self.caller.db, "current_hp", 999) or 999)
                choice = None
                if active_programs and "Poison Flatline" in program_pool and not self._enemy_runner_program_used(runner, "Poison Flatline"):
                    choice = "Poison Flatline"
                elif int(state.get("lock_deeper_rounds", 0) or 0) <= 0 and "Superglue" in program_pool and not self._enemy_runner_program_used(runner, "Superglue"):
                    choice = "Superglue"
                elif caller_hp <= 10 and any(p in program_pool for p in ("DeckKRASH", "Hellbolt")):
                    lethal = "DeckKRASH" if "DeckKRASH" in program_pool else "Hellbolt"
                    if not self._enemy_runner_program_used(runner, lethal):
                        choice = lethal
                elif "Vrizzbolt" in program_pool:
                    choice = "Vrizzbolt"
                elif "Nervescrub" in program_pool and not self._enemy_runner_program_used(runner, "Nervescrub"):
                    choice = "Nervescrub"

                atk = iface + random.randint(1, 10)
                defense = max(1, get_interface_rank(self.caller)) + random.randint(1, 10)
                self.caller.msg(f"  {runner['name']} attack: {atk} vs Interface defense {defense}")
                if atk < defense:
                    self.caller.msg(f"  |g{runner['name']} misses.|n")
                    continue
                if not choice:
                    self._brain_damage(_roll_dice("1d6"), f"{runner['name']} / Zap")
                    continue
                pkey = normalize_name(choice)
                self._enemy_runner_use_program(runner, choice)
                if pkey == "vrizzbolt":
                    self._brain_damage(_roll_dice("1d6"), f"{runner['name']} / Vrizzbolt")
                    state["action_penalty_next"] = max(1, int(state.get("action_penalty_next", 0) or 0))
                elif pkey in {"deckkrash", "hellbolt"}:
                    self.caller.msg(f"  |r{runner['name']} runs {choice}: forced unsafe jack out!|n")
                    self._do_jackout(unsafe=True)
                    return
                elif pkey == "superglue":
                    rounds = random.randint(1, 6)
                    state["lock_deeper_rounds"] = max(rounds, int(state.get("lock_deeper_rounds", 0) or 0))
                    state["lock_safe_jackout_rounds"] = max(rounds, int(state.get("lock_safe_jackout_rounds", 0) or 0))
                    self.caller.msg(f"  |ySuperglue lock holds you for {rounds} rounds.|n")
                elif pkey == "poison_flatline":
                    self._destroy_random_installed_program(state, f"{runner['name']} / Poison Flatline")
                elif pkey == "nervescrub":
                    self.caller.msg("  |yNervescrub effect: psychosomatic stat penalty (INT/REF/DEX) applied narratively.|n")
                else:
                    self._brain_damage(_roll_dice("1d6"), f"{runner['name']} / Zap")
            runner["action_penalty"] = int(runner.get("action_penalty_next", 0) or 0)
            runner["action_penalty_next"] = 0

    def _net_actions_available(self, state):
        """
        Effective NET actions this turn.
        Interface sets baseline, with a minimum of 2 and optional penalties.
        """
        rank = max(1, get_interface_rank(self.caller))
        base_actions = int(net_actions_for_rank(rank))
        action_bonus, _reasons = self._net_action_modifiers(state)
        penalty = int(state.get("action_penalty", 0) or 0)
        return max(2, base_actions + int(action_bonus or 0) - penalty)

    def _ice_program_damage_dice(self, ice_name):
        key = normalize_name(ice_name or "")
        if key in {"dragon", "sabertooth"}:
            return "6d6"
        if key == "killer":
            return "4d6"
        return "3d6"

    def _ice_brain_damage_dice(self, ice_name):
        key = normalize_name(ice_name or "")
        if key in {"giant", "kraken"}:
            return "3d6"
        if key == "hellhound":
            return "2d6"
        if key in {"raven", "wisp"}:
            return "1d6"
        return None

    def _run_ice_turn(self, state):
        """Run one ICE attack pass after the runner spends their turn."""
        if not self._is_jacked_in():
            return
        arch = self._current_architecture()
        if not arch:
            return
        floor = self._get_floor(arch, state)
        if not floor:
            return
        floor_ice = [i for i in self._ensure_floor_ice_state(state, floor) if i.get("active")]
        if not floor_ice:
            self.caller.msg("|xNo active ICE takes a turn this round.|n")
            return

        active_programs = state.get("active_programs", {})
        runner_rank = max(1, get_interface_rank(self.caller))
        self.caller.msg("|rICE TURN: Hostile routines execute.|n")
        for ice_instance in floor_ice:
            if not self._is_jacked_in():
                return
            if not ice_instance.get("active"):
                continue
            ice = get_black_ice(normalize_name(ice_instance.get("name", "")))
            if not ice:
                continue

            ice_class = (ice.get("class") or "").lower()
            ice_key = normalize_name(ice.get("name", ""))
            if "anti-program" in ice_class:
                if not active_programs:
                    self.caller.msg(f"  |y{ice['name']} finds no active programs to shred.|n")
                    continue
                target_key = random.choice(list(active_programs.keys()))
                target = active_programs.get(target_key) or {}
                atk_total = int(ice.get("atk", 0)) + random.randint(1, 10)
                def_total = int(target.get("def", 0) or 0) + random.randint(1, 10)
                self.caller.msg(
                    f"  {ice['name']} attack: {atk_total} vs {target.get('name', target_key)} defense {def_total}"
                )
                if atk_total < def_total:
                    self.caller.msg(f"  |g{ice['name']} misses.|n")
                    continue
                damage = _roll_dice(self._ice_program_damage_dice(ice.get("name")))
                target["rez"] = int(target.get("rez", 0)) - damage
                target_name = target.get("name", target_key.replace("_", " ").title())
                self.caller.msg(f"  |r{ice['name']} hits {target_name} for {damage} REZ.|n")
                if target["rez"] <= 0:
                    active_programs.pop(target_key, None)
                    if ice_key in {"dragon", "killer", "sabertooth"}:
                        destroyed = set(state.get("destroyed_programs", []) or [])
                        destroyed.add(target_key)
                        state["destroyed_programs"] = list(destroyed)
                        self.caller.msg(f"  |r{target_name} is Destroyed by {ice['name']}.|n")
                    else:
                        self.caller.msg(f"  |y{target_name} is Derezzed by {ice['name']}.|n")
                else:
                    active_programs[target_key] = target
                continue

            # Anti-personnel and special attacks.
            atk_total = int(ice.get("atk", 0)) + random.randint(1, 10)
            def_total = runner_rank + random.randint(1, 10)
            self.caller.msg(
                f"  {ice['name']} attack: {atk_total} vs Interface defense {def_total}"
            )
            if atk_total < def_total:
                self.caller.msg(f"  |g{ice['name']} misses.|n")
                continue
            damage_dice = self._ice_brain_damage_dice(ice.get("name"))
            if damage_dice:
                damage = _roll_dice(damage_dice)
                self._brain_damage(damage, ice["name"])

            if ice_key == "asp":
                self._destroy_random_installed_program(state, "Asp")
            elif ice_key == "wisp":
                state["action_penalty_next"] = max(1, int(state.get("action_penalty_next", 0) or 0))
                self.caller.msg("  |yWisp static will reduce your next turn's NET actions by 1 (minimum 2).|n")
            elif ice_key == "giant":
                self.caller.msg("  |rGiant slams your connection out of the Architecture!|n")
                self._do_jackout(unsafe=True, exclude_backlash_uid=ice_instance.get("uid"))
                return
            elif ice_key == "hellhound" and not state.get("on_fire", False):
                state["on_fire"] = True
                self.caller.msg("  |rHellhound sets your deck and clothing ablaze!|n")
            elif ice_key == "kraken":
                state["lock_deeper_rounds"] = max(1, int(state.get("lock_deeper_rounds", 0) or 0))
                state["lock_safe_jackout_rounds"] = max(1, int(state.get("lock_safe_jackout_rounds", 0) or 0))
                self.caller.msg("  |rKraken lock: you cannot move deeper or jack out safely until end of next turn.|n")
            elif ice_key == "skunk":
                affected = set(state.get("skunk_effect_uids", []) or [])
                uid = int(ice_instance.get("uid", 0) or 0)
                if uid not in affected:
                    affected.add(uid)
                    state["skunk_effect_uids"] = list(affected)
                    state["slide_penalty"] = int(state.get("slide_penalty", 0) or 0) + 2
                    self.caller.msg("  |ySkunk stench imposes -2 to Slide checks (stacks).|n")
            elif ice_key == "raven":
                defenders = [
                    k for k, pdata in active_programs.items()
                    if "defender" in (get_program(k) or {}).get("class", "").lower()
                ]
                if defenders:
                    dk = random.choice(defenders)
                    dname = active_programs.get(dk, {}).get("name", dk.replace("_", " ").title())
                    active_programs.pop(dk, None)
                    self.caller.msg(f"  |yRaven derezzes defender {dname}.|n")
            elif ice.get("effect"):
                self.caller.msg(f"  |xEffect: {ice['effect']}|n")

        state["active_programs"] = active_programs
        if self._is_jacked_in():
            self._run_demon_turn(state, arch)
        if self._is_jacked_in():
            self._run_enemy_runner_turn(state)

    def _spawn_defense_mook(self, state, defense_name, demon_name):
        """
        Best-effort bridge into scene combat for control-node defenses.
        """
        room = self._entry_room(state)
        if not room:
            return
        try:
            from commands import combat_system as cbt
        except Exception:
            return
        scene = cbt.get_active_scene(room)
        if not scene:
            return
        template = get_active_defense_template(defense_name) or {}
        prof_name = template.get("profile", "security guard")
        level = template.get("level", "mook")
        key, profile, resolved_level = cbt._resolve_profile_and_level(prof_name, level)
        if not profile:
            return
        room_tags = self._room_tag_set(room)
        if "no_net_defense" in room_tags:
            return
        team = "security"
        if "gang" in room_tags or "booster" in room_tags:
            team = "gang"
        elif "corporate" in room_tags or "corpsec" in room_tags:
            team = "corpsec"
        elif "arasaka" in room_tags:
            team = "arasaka"
        elif "militech" in room_tags:
            team = "militech"

        # Avoid duplicate same-named defense mooks alive at once.
        for existing in scene.get("roster", []):
            if existing.get("kind") == "mook" and existing.get("active", True):
                if str(existing.get("name", "")).startswith(f"{defense_name} [{demon_name}]"):
                    return
        scene["mook_counter"] = int(scene.get("mook_counter", 0) or 0) + 1
        mook = cbt._randomize_mook_from_profile(key, profile, scene["mook_counter"], level=resolved_level)
        mook["name"] = f"{defense_name} [{demon_name}]"
        mook["team"] = team
        if template.get("hp") is not None and int(template.get("hp") or 0) > 0:
            mook["max_hp"] = int(template.get("hp"))
            mook["current_hp"] = int(template.get("hp"))
        if template.get("weapon_name"):
            mook["weapon_name"] = template.get("weapon_name")
        if template.get("weapon_damage"):
            mook["weapon_damage"] = template.get("weapon_damage")
        if template.get("move"):
            mook_stats = dict(mook.get("stats", {}) or {})
            mook_stats["move"] = int(template.get("move"))
            mook["stats"] = mook_stats
        mook["defense_template"] = template
        cbt._roll_initiative_for_entry(mook)
        scene["roster"].append(mook)
        scene["roster"] = cbt._sort_roster(scene["roster"])
        scene["turn_index"] = 0
        effect_note = template.get("trigger")
        if effect_note:
            room.msg_contents(f"|rControl-node defense joins combat:|n {mook['name']} |x({effect_note})|n")
        else:
            room.msg_contents(f"|rControl-node defense joins combat:|n {mook['name']}.")

    def _run_demon_turn(self, state, arch):
        demon_data = getattr(arch.db, "demon", None) or {}
        if not demon_data:
            return
        if not bool(getattr(arch.db, "demon_enabled", True)):
            return
        if bool(state.get("demon_paused", False)):
            return
        demon = get_demon(demon_data.get("name", "")) or demon_data
        actions = int(demon.get("net_actions", 0) or 0)
        if actions <= 0:
            return
        floors = arch.db.floors or []
        room = self._entry_room(state)
        room_tags = self._room_tag_set(room)
        if "no_demon_autotrigger" in room_tags:
            return
        controlled = state.get("controlled_nodes", []) or []
        disabled = set(state.get("disabled_defenses", []) or [])
        countered = set(state.get("countered_defenses", []) or [])
        defense_nodes = []
        for fnum in controlled:
            if fnum in disabled or fnum in countered:
                continue
            floor = floors[int(fnum) - 1] if 0 < int(fnum) <= len(floors) else None
            if floor and floor.get("type") == "control" and floor.get("defense"):
                defense_nodes.append(floor)

        if not defense_nodes:
            # No controlled nodes: demon spends actions on Zap.
            for _ in range(actions):
                atk_total = int(demon.get("interface", 3) or 3) + random.randint(1, 10)
                def_total = max(1, get_interface_rank(self.caller)) + random.randint(1, 10)
                self.caller.msg(
                    f"|rDEMON {demon.get('name', 'Imp')} zaps: {atk_total} vs {def_total}|n"
                )
                if atk_total >= def_total:
                    self._brain_damage(_roll_dice("1d6"), f"Demon {demon.get('name', 'Imp')}")
            return

        # Prioritize control-node trigger, then Zap leftovers.
        # Optional room-tag control over how many node triggers demon prioritizes.
        max_node_triggers = actions
        if "demon_trigger_single" in room_tags:
            max_node_triggers = 1
        used = 0
        for floor in defense_nodes:
            if used >= actions or used >= max_node_triggers:
                break
            defense = floor.get("defense")
            self.caller.msg(
                f"|rDEMON {demon.get('name', 'Imp')} triggers Control Node {floor.get('floor')} "
                f"({defense}).|n"
            )
            self._spawn_defense_mook(state, defense, demon.get("name", "Imp"))
            used += 1
        while used < actions:
            atk_total = int(demon.get("interface", 3) or 3) + random.randint(1, 10)
            def_total = max(1, get_interface_rank(self.caller)) + random.randint(1, 10)
            self.caller.msg(
                f"|rDEMON {demon.get('name', 'Imp')} zaps: {atk_total} vs {def_total}|n"
            )
            if atk_total >= def_total:
                self._brain_damage(_roll_dice("1d6"), f"Demon {demon.get('name', 'Imp')}")
            used += 1

    def _consume_net_action(self, state, label="NET Action"):
        """Spend one NET action; trigger ICE turn when the turn budget is exhausted."""
        if not self._is_jacked_in():
            return
        self._record_trace_action(state, label)
        max_actions = self._net_actions_available(state)
        used = int(state.get("net_actions_used", 0) or 0) + 1
        state["net_actions_used"] = used
        remaining = max_actions - used
        if remaining > 0:
            self.caller.msg(f"|x{label} used. NET Actions left: {remaining}/{max_actions}.|n")
            self._set_state(state)
            return

        self.caller.msg(f"|x{label} used. NET action budget spent ({max_actions}/{max_actions}).|n")
        self._run_ice_turn(state)
        if not self._is_jacked_in():
            return
        state["net_actions_used"] = 0
        state["trace_turn"] = int(state.get("trace_turn", 1) or 1) + 1
        state["action_penalty"] = int(state.pop("action_penalty_next", 0) or 0)
        if state.get("on_fire", False):
            self.caller.take_damage(2)
            self.caller.msg("|rHellhound fire burns you for 2 HP at end of turn. Use a Meat Action in scene to extinguish.|n")
        state["slide_used_turn"] = False
        state["attack_program_used"] = False
        # Programs must be re-activated each turn.
        state["active_programs"] = {}
        if int(state.get("lock_deeper_rounds", 0) or 0) > 0:
            state["lock_deeper_rounds"] = int(state.get("lock_deeper_rounds", 0)) - 1
        if int(state.get("lock_safe_jackout_rounds", 0) or 0) > 0:
            state["lock_safe_jackout_rounds"] = int(state.get("lock_safe_jackout_rounds", 0)) - 1
        self._set_state(state)

    def _pick_ice_target(self, floor_ice, target_arg):
        """Resolve ICE target from optional name or 1-based index. Returns (ice_dict, index) or (None, -1)."""
        if not floor_ice:
            return None, -1
        if not target_arg or not target_arg.strip():
            return floor_ice[0], 0
        arg = target_arg.strip()
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(floor_ice):
                return floor_ice[idx], idx
            return None, -1
        arg_lower = normalize_name(arg)
        labels = self._ice_display_names(floor_ice)
        for i, ice_dict in enumerate(floor_ice):
            if normalize_name(ice_dict.get("name", "")) == arg_lower or normalize_name(labels[i]) == arg_lower:
                return ice_dict, i
        return None, -1

    def _resolve_program_or_ice(self, query):
        """Resolve player input to canonical Program/Black ICE data row."""
        text = (query or "").strip()
        if not text:
            return None, "Specify a program or Black ICE name."
        direct = installable_program_or_ice(text)
        if direct:
            return direct, None

        candidates = []
        for p in deckoptions.programs:
            nm = p.get("name")
            if nm:
                candidates.append((nm, nm))
        for b in deckoptions.black_ice:
            nm = b.get("name")
            if nm:
                candidates.append((nm, nm))
        picked, err = pick_named_candidate(text, candidates)
        if err:
            return None, err
        if not picked:
            return None, f"Unknown program or Black ICE: '{text}'."
        resolved = installable_program_or_ice(picked)
        if not resolved:
            return None, f"Unable to resolve '{picked}'."
        return resolved, None

    def _net_vendor_tag_status(self):
        """
        Return room net-vendor tag status tuple:
        (room_tags, has_role_tag, has_stock_tag).
        Role tags: netrunner/hacker
        Stock tags: program/deck
        """
        room = getattr(self.caller, "location", None)
        if not room:
            return set(), False, False
        room_tags = self._room_tag_set(room)
        has_role_tag = bool({"netrunner", "hacker"} & room_tags)
        has_stock_tag = bool({"program", "deck"} & room_tags)
        return room_tags, has_role_tag, has_stock_tag

    def _can_buy_programs_here(self):
        """
        Gate +net/buy to tagged rooms.
        Requires at least one role tag and one stock tag:
          role: netrunner or hacker
          stock: program or deck
        """
        _tags, has_role_tag, has_stock_tag = self._net_vendor_tag_status()
        return has_role_tag and has_stock_tag

    def _parse_ice_names(self, floor):
        ftype = floor.get("type")
        if ftype == "black_ice":
            return [floor.get("name")]
        if ftype == "black_ice_group":
            return [n.strip() for n in (floor.get("name") or "").split(",") if n.strip()]
        return []

    def _ensure_floor_ice_state(self, state, floor):
        floor_num = int(floor.get("floor", 1))
        existing = self._get_active_ice_on_floor(state, floor_num)
        if existing:
            return existing
        names = self._parse_ice_names(floor)
        generated = []
        for name in names:
            ice = get_black_ice(normalize_name(name))
            if not ice:
                continue
            generated.append(
                {
                    "uid": self._next_ice_uid(state),
                    "name": ice["name"],
                    "rez": ice["rez"],
                    "active": True,
                    "pursuing": True,
                    "home_floor": floor_num,
                    "current_floor": floor_num,
                    "encountered": False,
                }
            )
        self._set_active_ice_on_floor(state, floor_num, generated)
        return generated

    def _destroy_random_installed_program(self, state, reason):
        installed = state.get("installed_programs", {}) or {}
        destroyed = set(state.get("destroyed_programs", []) or [])
        # Asp/Poison Flatline target regular Programs, not Black ICE packages.
        candidates = [k for k in installed.keys() if k not in destroyed and get_program(k)]
        if not candidates:
            self.caller.msg(f"  |y{reason} finds no installed Program to destroy.|n")
            return
        victim = random.choice(candidates)
        destroyed.add(victim)
        state["destroyed_programs"] = list(destroyed)
        active = state.get("active_programs", {})
        active.pop(victim, None)
        state["active_programs"] = active
        self.caller.msg(f"  |r{reason} destroys installed Program {installed[victim]}.|n")

    def _send_ice_to_home_floor(self, state, ice_instance):
        cur = int(ice_instance.get("current_floor", 0) or 0)
        home = int(ice_instance.get("home_floor", cur) or cur)
        ice_instance["pursuing"] = False
        ice_instance["current_floor"] = home
        if cur == home:
            return
        cur_list = list(self._get_active_ice_on_floor(state, cur))
        home_list = list(self._get_active_ice_on_floor(state, home))
        if ice_instance in cur_list:
            cur_list.remove(ice_instance)
        home_list.append(ice_instance)
        self._set_active_ice_on_floor(state, cur, cur_list)
        self._set_active_ice_on_floor(state, home, home_list)

    def _remove_skunk_penalty_for_ice(self, state, ice_instance):
        if normalize_name(ice_instance.get("name", "")) != "skunk":
            return
        uid = int(ice_instance.get("uid", 0) or 0)
        affected = set(state.get("skunk_effect_uids", []) or [])
        if uid in affected:
            affected.remove(uid)
            state["skunk_effect_uids"] = list(affected)
            state["slide_penalty"] = max(0, int(state.get("slide_penalty", 0) or 0) - 2)

    def _encounter_ice(self, state, floor):
        ice_list = self._ensure_floor_ice_state(state, floor)
        if not ice_list:
            return
        speed_bonus = self._interface_bonus(state, "speed")
        for ice_instance in ice_list:
            if not ice_instance.get("active"):
                continue
            ice = get_black_ice(normalize_name(ice_instance["name"]))
            if not ice:
                continue
            ice_instance["encountered"] = True
            net_total, _, _, _ = interface_check(self.caller, bonus=speed_bonus)
            ice_total = int(ice["spd"]) + random.randint(1, 10)
            if ice_total > net_total:
                self.caller.msg(
                    f"|r{ice['name']} gets a free hit on encounter! ({ice_total} vs {net_total})|n"
                )
                ice_class = (ice.get("class") or "").lower()
                if "anti-program" in ice_class:
                    active_programs = state.get("active_programs", {})
                    if active_programs:
                        tkey = random.choice(list(active_programs.keys()))
                        tdata = active_programs.get(tkey) or {}
                        dmg = _roll_dice(self._ice_program_damage_dice(ice.get("name")))
                        tdata["rez"] = int(tdata.get("rez", 0)) - dmg
                        tname = tdata.get("name", tkey.replace("_", " ").title())
                        self.caller.msg(f"|r{ice['name']} shreds {tname} for {dmg} REZ.|n")
                        if tdata["rez"] <= 0:
                            active_programs.pop(tkey, None)
                            if normalize_name(ice.get("name", "")) in {"dragon", "killer", "sabertooth"}:
                                destroyed = set(state.get("destroyed_programs", []) or [])
                                destroyed.add(tkey)
                                state["destroyed_programs"] = list(destroyed)
                                self.caller.msg(f"|r{tname} is Destroyed by {ice['name']}.|n")
                            else:
                                self.caller.msg(f"|y{tname} is Derezzed by {ice['name']}.|n")
                        else:
                            active_programs[tkey] = tdata
                        state["active_programs"] = active_programs
                    else:
                        self.caller.msg(f"|y{ice['name']} finds no active programs to strike.|n")
                else:
                    dmg = self._ice_brain_damage_dice(ice.get("name"))
                    if dmg:
                        self._brain_damage(_roll_dice(dmg), ice["name"])
                    key = normalize_name(ice.get("name", ""))
                    if key == "asp":
                        self._destroy_random_installed_program(state, "Asp")
                    elif key == "wisp":
                        state["action_penalty_next"] = max(1, int(state.get("action_penalty_next", 0) or 0))
                    elif key == "giant":
                        self.caller.msg("|rGiant slams your connection out of the Architecture!|n")
                        self._do_jackout(unsafe=True, exclude_backlash_uid=ice_instance.get("uid"))
                        return
                    elif key == "hellhound" and not state.get("on_fire", False):
                        state["on_fire"] = True
                        self.caller.msg("|rHellhound sets your deck and clothing ablaze!|n")
                    elif key == "kraken":
                        state["lock_deeper_rounds"] = max(1, int(state.get("lock_deeper_rounds", 0) or 0))
                        state["lock_safe_jackout_rounds"] = max(1, int(state.get("lock_safe_jackout_rounds", 0) or 0))
                    elif key == "skunk":
                        affected = set(state.get("skunk_effect_uids", []) or [])
                        uid = int(ice_instance.get("uid", 0) or 0)
                        if uid not in affected:
                            affected.add(uid)
                            state["skunk_effect_uids"] = list(affected)
                            state["slide_penalty"] = int(state.get("slide_penalty", 0) or 0) + 2

    def _show_current_floor(self, arch, state):
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("Your NET position is invalid. Jacking out for safety.")
            self._do_jackout(unsafe=False)
            return
        floor_num = int(floor.get("floor", state.get("floor", 1)))
        self.caller.msg(
            f"|cNET Floor {floor_num}/{len(arch.db.floors or [])}|n: "
            f"|w{floor.get('name', 'Unknown')}|n ({floor.get('type')})"
        )
        if floor.get("branch") and floor.get("branch") != "main":
            self.caller.msg(f"  |xBranch:|n {floor.get('branch')} (depth {floor.get('depth', '?')})")
        if floor.get("type") == "password":
            cleared = state.get("cleared_passwords", [])
            if floor_num not in cleared:
                self.caller.msg(f"  |yBlocked by Password DV {floor.get('dv', '?')}|n")
                self.caller.msg("  |xSuggested:|n |w+net/backdoor|n (alias: |w+net/bypass|n)")
            else:
                self.caller.msg("  |gPassword on this floor is already bypassed.|n")
                self.caller.msg("  |xSuggested:|n |w+net/move down|n")
        if floor.get("type") in ("file", "paydata"):
            paydata = floor.get("paydata")
            if paydata:
                self.caller.msg("  |yData cache detected. Use +net/eyedee or +net/grab.|n")
            self.caller.msg("  |xSuggested:|n |w+net/eyedee|n -> |w+net/grab|n -> |w+net/move down|n")
        if floor.get("type") in ("black_ice", "black_ice_group"):
            active = [i for i in self._ensure_floor_ice_state(state, floor) if i.get("active")]
            if active:
                labels = self._ice_display_names(active)
                self.caller.msg(
                    "  |rHostile ICE:|n "
                    + ", ".join(f"{labels[idx]}({ice['rez']} REZ)" for idx, ice in enumerate(active))
                )
                self.caller.msg("  |xSuggested:|n |w+net/zap|n, |w+net/attack <program>|n, or |w+net/slide up[=<ICE>] |n")
        hostile_runners = [r for r in self._enemy_runners_on_floor(state, floor_num) if r.get("active")]
        if hostile_runners:
            self.caller.msg(
                "  |rHostile Netrunners:|n "
                + ", ".join(f"{r.get('name')} (Interface {r.get('interface', '?')})" for r in hostile_runners)
            )
        if floor.get("type") == "control" and floor.get("defense"):
            defense_name = floor.get("defense")
            self.caller.msg(f"  |mLinked defense:|n {defense_name}")
            dtemp = get_active_defense_template(defense_name) or {}
            if dtemp:
                self.caller.msg(
                    f"    Trigger: {dtemp.get('trigger', 'n/a')} | "
                    f"Counter DV {dtemp.get('counter_dv', '?')} / "
                    f"{dtemp.get('counter_time_min', '?')} min"
                )
            if int(floor_num) in set(state.get("countered_defenses", []) or []):
                self.caller.msg("    |gStatus: COUNTERED (meatspace disable complete).|n")
            elif int(floor_num) in set(state.get("disabled_defenses", []) or []):
                self.caller.msg("    |yStatus: Toggled OFF via control node.|n")
            self.caller.msg("  |xSuggested:|n |w+net/control|n, then |w+net/control off|n / |w+net/control on|n")
        children = self._children_for_floor(floor)
        parent = self._parent_for_floor(floor)
        if children:
            child_labels = []
            for x in children:
                cf = self._get_floor_by_num(arch, x) or {}
                b = cf.get("branch")
                if b and b != "main":
                    child_labels.append(f"F{x} ({b})")
                else:
                    child_labels.append(f"F{x}")
            self.caller.msg("  |xConnected deeper floors:|n " + ", ".join(child_labels))
            self.caller.msg("  |xMove:|n |w+net/move down|n or |w+net/move down=<floor#|branch>|n")
        if parent:
            self.caller.msg(f"  |xConnected upper floor:|n F{parent}")
            self.caller.msg("  |xRetreat:|n |w+net/move up|n or |w+net/slide up|n")
        if floor.get("is_bottom"):
            self.caller.msg("  |gLowest node reached: you can place a persistent virus here.|n")
            self.caller.msg("  Use |w+net/virus start <dv>/<actions>=<description>|n")
        if NetFloorLead.objects.filter(architecture_object_id=arch.id, floor_number=floor_num).exists():
            self.caller.msg("  |cConcealed data trails may exist on this floor.|n |w+net/delve|n  |w+net/leads|n")

    def _has_netrunner_access_role(self, interface_rank=None):
        """
        Gate NET access to characters with Netrunner as a primary role, or as a
        secondary role represented by bought Interface ranks.
        """
        sheet = getattr(self.caller, "character_sheet", None)
        primary_role = ""
        if sheet:
            primary_role = str(getattr(sheet, "role", "") or "").strip().lower()
        if primary_role == "netrunner":
            return True
        role_db = str(getattr(self.caller.db, "role", "") or "").strip().lower()
        if role_db == "netrunner":
            return True
        if interface_rank is None:
            interface_rank = get_interface_rank(self.caller)
        return int(interface_rank or 0) > 0

    def _has_netrunning_gear(self):
        sheet = getattr(self.caller, "character_sheet", None)
        if not sheet:
            return False, ["a character sheet"]
        inv = getattr(sheet, "inventory", None)
        if not inv:
            return False, ["an inventory"]
        installed_cyberware = list(
            CyberwareInstance.objects.filter(character_sheet=sheet, installed=True).select_related("cyberware")
        )
        has_deck = False
        for gear in inv.gear.all():
            if getattr(gear, "is_cyberdeck", False):
                has_deck = True
                break
        for cw in installed_cyberware:
            if "cyberdeck" in (cw.cyberware.name or "").lower():
                has_deck = True
                break
        cyber_names = set()
        for cw in installed_cyberware:
            cyber_names.add(normalize_name(cw.cyberware.name or ""))
        inv_gear_names = {normalize_name(getattr(g, "name", "") or "") for g in inv.gear.all()}
        inv_armor_names = {normalize_name(getattr(a, "name", "") or "") for a in inv.armor.all()}
        equipped_armor = getattr(sheet, "eqarmor", None)
        if equipped_armor and getattr(equipped_armor, "name", None):
            inv_armor_names.add(normalize_name(equipped_armor.name))

        has_neuroport = "neuroport" in cyber_names
        has_neural_link = "neural_link" in cyber_names
        has_virtuality_cyberware = "virtuality" in cyber_names
        has_virtuality_goggles = "virtuality_goggles" in inv_gear_names or "virtuality_goggles" in inv_armor_names

        needs = []
        if not has_deck:
            needs.append("a Cyberdeck")
        if not has_neuroport:
            if not has_neural_link:
                needs.append("Neural Link cyberware (or Neuroport)")
            if not (has_virtuality_goggles or has_virtuality_cyberware):
                needs.append("Virtuality Goggles or Virtuality cyberware")
        if needs:
            return False, needs
        return True, []

    def _do_jackout(self, unsafe=False, exclude_backlash_uid=None):
        state = self._get_state()
        if not state.get("active"):
            return
        if state.get("_jackout_in_progress"):
            return
        state["_jackout_in_progress"] = True
        self._set_state(state)
        arch = self._current_architecture()
        try:
            if unsafe:
                for floor_ice in (state.get("ice_state", {}) or {}).values():
                    for ice_instance in floor_ice or []:
                        if not ice_instance.get("active") or not ice_instance.get("encountered"):
                            continue
                        if exclude_backlash_uid and int(ice_instance.get("uid", 0) or 0) == int(exclude_backlash_uid):
                            continue
                        ice = get_black_ice(normalize_name(ice_instance.get("name", "")))
                        if not ice:
                            continue
                        damage_dice = self._ice_brain_damage_dice(ice.get("name"))
                        if damage_dice:
                            self._brain_damage(_roll_dice(damage_dice), f"{ice['name']} (jack-out backlash)")
                        key = normalize_name(ice.get("name", ""))
                        if key == "asp":
                            self._destroy_random_installed_program(state, "Asp")
                        elif key == "wisp":
                            state["action_penalty_next"] = max(1, int(state.get("action_penalty_next", 0) or 0))
                        elif key == "kraken":
                            state["lock_deeper_rounds"] = max(1, int(state.get("lock_deeper_rounds", 0) or 0))
                            state["lock_safe_jackout_rounds"] = max(1, int(state.get("lock_safe_jackout_rounds", 0) or 0))
                        elif key == "hellhound":
                            if not state.get("on_fire", False):
                                state["on_fire"] = True
                                self.caller.msg("|rHellhound flames cling to your body and gear!|n")
            self._archive_trace_if_exposed(state, arch, unsafe=unsafe)
            # Move character back to room and destroy body object
            body_id = state.get("body_id")
            entry_loc_id = state.get("entry_location_id")
            if body_id:
                body = evennia.search_object(f"#{body_id}")
                if body:
                    body = body[0]
                    # Move character back to room (body's location) before destroying body
                    room = body.location
                    if not room and entry_loc_id:
                        room_match = evennia.search_object(f"#{entry_loc_id}")
                        room = room_match[0] if room_match else None
                    if room:
                        self.caller.move_to(room, quiet=True)
                    body.delete()
            self._clear_state()
            if unsafe:
                self.caller.msg("|rUnsafe jack out! Neural backlash tears through your nervous system.|n")
            else:
                self.caller.msg("|gYou safely jack out of the Architecture.|n")
            if self.caller.location:
                arch_name = arch.key if arch else "the NET"
                self.caller.location.msg_contents(
                    f"{self.caller.key} blinks rapidly as their focus returns from {arch_name}.",
                    exclude=self.caller,
                )
        finally:
            # If jack-out aborted due to an unexpected exception, clear
            # re-entrancy guard so the character is not stuck.
            current = self._get_state()
            if current.get("active") and current.get("_jackout_in_progress"):
                current["_jackout_in_progress"] = False
                self._set_state(current)

    def cmd_scan(self):
        room = self.caller.location
        if not room:
            self.caller.msg("You have no location to scan.")
            return
        arches = [obj for obj in room.contents if hasattr(obj, "db") and getattr(obj.db, "is_net_architecture", False)]
        if not arches:
            self.caller.msg("No NET access points detected here.")
            return
        lines = ["|cAccess Points in range:|n"]
        for arch in arches:
            lines.append(
                f"  {arch.key} - {(arch.db.difficulty or 'standard').title()} ({len(arch.db.floors or [])} floors)"
            )
        self.caller.msg("\n".join(lines))

    def cmd_jackin(self):
        if not is_character_approved(self.caller):
            self.caller.msg("You must be approved by staff before using netrunning.")
            return
        if self._is_jacked_in():
            self.caller.msg("You are already jacked in.")
            return
        if not self.args:
            self.caller.msg("Usage: +net/jackin <architecture>")
            return
        arch = self._find_architecture(self.args.strip())
        if not arch or arch.location != self.caller.location:
            self.caller.msg("You need to be next to that access point to jack in.")
            return

        interface_rank = get_interface_rank(self.caller)
        if not self._has_netrunner_access_role(interface_rank):
            self.caller.msg("NET access is restricted to Netrunners (primary role or secondary Interface role).")
            return
        if interface_rank <= 0:
            self.caller.msg("You need Interface rank to netrun.")
            return
        ok, missing = self._has_netrunning_gear()
        if not ok:
            self.caller.msg("Missing required netrunning gear: " + ", ".join(missing))
            return

        # Create body object in room (physical body left behind while in the net)
        room = self.caller.location
        body_key = f"{self.caller.account.username}'s Body" if self.caller.account else "Body"
        body = evennia.create_object(
            "typeclasses.objects.Object",
            key=body_key,
            location=room,
        )
        body.db.desc = "Sits motionless, eyes glazed, chrome light flickering in their gaze as they're jacked into the NET."
        # Move character into body so room shows body, not character
        self.caller.move_to(body, quiet=True)

        deck_name = self._choose_jackin_deck()
        installed = self._installed_programs_for_deck(deck_name)

        state = {
            "active": True,
            "architecture_id": arch.id,
            "entry_location_id": room.id if room else None,
            "body_id": body.id,
            "deck_name": deck_name,
            "installed_programs": installed,
            "destroyed_programs": [],
            "floor": 1,
            "active_programs": {},
            "cleared_passwords": [],
            "controlled_nodes": [],
            "disabled_defenses": [],
            "countered_defenses": [],
            "ice_state": {},
            "ice_uid_counter": 0,
            "net_actions_used": 0,
            "action_penalty": 0,
            "action_penalty_next": 0,
            "slide_used_turn": False,
            "attack_program_used": False,
            "lock_deeper_rounds": 0,
            "lock_safe_jackout_rounds": 0,
            "slide_penalty": 0,
            "skunk_effect_uids": [],
            "on_fire": False,
            "trace_turn": 1,
            "trace_actions": [],
            "trace_sealed": False,
            "trace_cloak_roll": None,
            "virus_job": None,
            "alarm_level": 0,
            "enemy_runners": {},
            "enemy_runner_counter": 0,
            "counter_job": None,
            "demon_paused": False,
        }
        setup_notes = self._apply_jackin_deck_automation(state)
        self._set_state(state)

        self.caller.msg(f"|gYou jack into {arch.key}. The world resolves into META geometry.|n")
        for note in setup_notes:
            self.caller.msg(f"|xDeck Effect:|n {note}")
        if self.caller.location:
            self.caller.location.msg_contents(
                f"{self.caller.key} goes still as chrome light flickers in their eyes.",
                exclude=self.caller,
            )
        floor = self._get_floor(arch, state)
        if floor:
            self._encounter_ice(state, floor)
            self._set_state(state)
            self._show_current_floor(arch, state)

    def cmd_jackout(self):
        if not self._require_netrun():
            return
        state = self._get_state()
        if int(state.get("lock_safe_jackout_rounds", 0) or 0) > 0:
            self.caller.msg("|rYou are locked out of safe jack-out and must pull unsafely!|n")
            self._do_jackout(unsafe=True)
            return
        self._do_jackout(unsafe=False)

    def cmd_status(self):
        if not self._is_jacked_in():
            self.caller.msg("Not jacked in. Use +net/scan then +net/jackin <architecture>.")
            return
        arch = self._current_architecture()
        if not arch:
            self.caller.msg("Architecture no longer exists. Forcing jack out.")
            self._do_jackout(unsafe=True)
            return
        state = self._get_state()
        rank = get_interface_rank(self.caller)
        actions = self._net_actions_available(state)
        _action_bonus, action_bonus_reasons = self._net_action_modifiers(state)
        used = int(state.get("net_actions_used", 0) or 0)
        remaining = max(0, actions - used)
        active_programs = state.get("active_programs", {})
        self.caller.msg(
            f"|cNetrun Status|n  Arch: |w{arch.key}|n  Interface: {rank}  "
            f"NET Actions: {remaining}/{actions} this turn"
        )
        if action_bonus_reasons:
            self.caller.msg("NET Action modifiers: " + ", ".join(action_bonus_reasons))
        self.caller.msg(f"Alarm level: {int(state.get('alarm_level', 0) or 0)}")
        demon = getattr(arch.db, "demon", None) or {}
        if demon:
            demon_enabled = bool(getattr(arch.db, "demon_enabled", True))
            demon_local = "paused" if state.get("demon_paused", False) else "active"
            self.caller.msg(
                f"Demon present: {demon.get('name', 'Imp')} "
                f"(Interface {demon.get('interface', '?')}, NET actions {demon.get('net_actions', '?')}, "
                f"global={'on' if demon_enabled else 'off'}, local={demon_local})"
            )
        if active_programs:
            self.caller.msg("Active programs: " + ", ".join(p.get("name", k) for k, p in active_programs.items()))
        else:
            self.caller.msg("Active programs: none")
        installed = state.get("installed_programs", {}) or {}
        destroyed = set(state.get("destroyed_programs", []) or [])
        if installed:
            labels = []
            for key, label in sorted(installed.items(), key=lambda item: item[1]):
                if key in destroyed:
                    labels.append(f"{label} [DESTROYED]")
                else:
                    labels.append(label)
            self.caller.msg("Installed deck payloads: " + ", ".join(labels))
        trace_count = len(state.get("trace_actions", []) or [])
        if state.get("trace_sealed", False):
            self.caller.msg("Forensics: |gCloaked|n (trace scrubbed for this run).")
        else:
            self.caller.msg(f"Forensics: |yExposed|n ({trace_count} logged action entries so far).")
        if state.get("on_fire", False):
            self.caller.msg("|rYou are on fire in meatspace (Hellhound effect). Use +net/extinguish.|n")
        if state.get("counter_job"):
            job = state.get("counter_job") or {}
            self.caller.msg(
                f"Defense counter job: F{job.get('floor')} {job.get('spent_actions', 0)}/{job.get('total_actions', 0)}"
            )
        self._show_current_floor(arch, state)

    def cmd_move(self):
        if not self._require_netrun():
            return
        if not self.args:
            self.caller.msg("Usage: +net/move <down|up|floor#>[=<child floor#|branch>]")
            return
        arch = self._current_architecture()
        state = self._get_state()
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        floors = arch.db.floors or []
        cur = int(state.get("floor", 1))
        current_floor = self._get_floor(arch, state)
        if not current_floor:
            self.caller.msg("Current floor data is invalid.")
            return

        if current_floor and current_floor.get("type") == "password":
            cleared = state.get("cleared_passwords", [])
            if cur not in cleared:
                self.caller.msg("A Password blocks your descent. Use +net/backdoor.")
                return

        raw_arg = self.args.strip()
        selector = ""
        if "=" in raw_arg:
            left, right = raw_arg.split("=", 1)
            arg = left.strip().lower()
            selector = right.strip().lower()
        else:
            arg = raw_arg.lower()
        if int(state.get("lock_deeper_rounds", 0) or 0) > 0:
            # Deeper means descending to higher floor index.
            if (arg == "down") or (arg.isdigit() and int(arg) > cur):
                self.caller.msg("|rKraken/Superglue lock prevents deeper movement this turn.|n")
                return

        graph_mode = "children" in current_floor or "parent" in current_floor
        if arg == "down":
            if graph_mode:
                kids = self._children_for_floor(current_floor)
                if not kids:
                    self.caller.msg("No deeper branch from here.")
                    return
                if selector:
                    chosen = None
                    if selector.isdigit():
                        s_floor = int(selector)
                        if s_floor in kids:
                            chosen = s_floor
                    if chosen is None:
                        # Allow selecting by branch label.
                        branch_map = {}
                        for k in kids:
                            kfloor = self._get_floor_by_num(arch, k)
                            if not kfloor:
                                continue
                            bname = str(kfloor.get("branch", "") or "").strip().lower()
                            if bname:
                                branch_map[bname] = k
                        chosen = branch_map.get(selector)
                    if chosen is None:
                        hints = []
                        for k in kids:
                            kfloor = self._get_floor_by_num(arch, k)
                            bname = (kfloor or {}).get("branch", "")
                            if bname and bname != "main":
                                hints.append(f"F{k} ({bname})")
                            else:
                                hints.append(f"F{k}")
                        self.caller.msg(
                            "Unknown branch selector. Valid children: " + ", ".join(hints)
                        )
                        return
                    new_floor = chosen
                elif len(kids) > 1:
                    self.caller.msg(
                        "Multiple deeper branches available: "
                        + ", ".join(
                            f"F{k} ({(self._get_floor_by_num(arch, k) or {}).get('branch', 'main')})"
                            for k in kids
                        )
                        + ". Use +net/move down=<floor#|branch>."
                    )
                    return
                else:
                    new_floor = kids[0]
            else:
                new_floor = cur + 1
        elif arg == "up":
            if graph_mode:
                parent = self._parent_for_floor(current_floor)
                if not parent:
                    self.caller.msg("You are already at the entry node.")
                    return
                new_floor = parent
            else:
                new_floor = cur - 1
        else:
            try:
                new_floor = int(arg)
            except ValueError:
                self.caller.msg("Move target must be down, up, or a floor number.")
                return
            if graph_mode:
                kids = self._children_for_floor(current_floor)
                parent = self._parent_for_floor(current_floor)
                allowed = set(kids)
                if parent:
                    allowed.add(parent)
                if new_floor not in allowed:
                    self.caller.msg(
                        "That floor is not directly connected from here. Connected: "
                        + ", ".join(f"F{x}" for x in sorted(allowed))
                    )
                    return
        if new_floor < 1 or new_floor > len(floors):
            self.caller.msg("That floor is out of range.")
            return

        old_floor = cur
        state["floor"] = new_floor
        self._move_pursuing_ice(state, old_floor, new_floor)
        floor = floors[new_floor - 1]
        self._encounter_ice(state, floor)
        self._set_state(state)
        self._show_current_floor(arch, state)
        self._consume_net_action(state, "Move")

    def cmd_pathfinder(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        bonus = self._interface_bonus(state, "pathfinder")
        total, rank, die, details = interface_check(self.caller, bonus=bonus)
        floors = arch.db.floors or []
        current = self._get_floor(arch, state)
        graph_mode = bool(current and ("children" in current or "parent" in current))
        visible = []
        if graph_mode and current:
            by_num = {int(f.get("floor", 0)): f for f in floors}
            queue = [int(current.get("floor", 1))]
            seen = set()
            while queue and len(visible) < total:
                fnum = queue.pop(0)
                if fnum in seen:
                    continue
                seen.add(fnum)
                floor = by_num.get(fnum)
                if not floor:
                    continue
                visible.append(floor)
                blocked = floor.get("type") == "password" and int(floor.get("dv", 0) or 0) >= total
                if blocked:
                    continue
                for child in self._children_for_floor(floor):
                    if child not in seen:
                        queue.append(child)
        else:
            for floor in floors:
                visible.append(floor)
                if floor.get("type") == "password" and int(floor.get("dv", 0)) > total:
                    break
                if len(visible) >= total:
                    break
        dice_str = _format_interface_dice(details, bonus)
        self.caller.msg(f"|cPathfinder|n Interface {rank} + {dice_str} = |w{total}|n")
        for floor in visible:
            extras = []
            if floor.get("branch") and floor.get("branch") != "main":
                extras.append(str(floor.get("branch")))
            if floor.get("is_bottom"):
                extras.append("BOTTOM")
            extra = f" [{' | '.join(extras)}]" if extras else ""
            self.caller.msg(
                f"  F{floor['floor']}: {floor.get('name', '?')} ({floor.get('type')}){extra}"
            )
        free_uses = int(state.get("free_pathfinder_uses", 0) or 0)
        if free_uses > 0:
            state["free_pathfinder_uses"] = free_uses - 1
            self._set_state(state)
            self.caller.msg("|gPathfinder used for free (Microtech Scout jack-in effect).|n")
            return
        self._consume_net_action(state, "Pathfinder")

    def cmd_cloak(self):
        """
        Scrub run activity logs before jack-out.
        """
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        if state.get("trace_sealed", False):
            self.caller.msg("|gYou already sealed this run's trace with Cloak.|n")
            return
        dv = int(DIFFICULTY_DV.get(getattr(arch.db, "difficulty", "standard"), 8))
        bonus = self._interface_bonus(state, "cloak")
        total, rank, die, details = interface_check(self.caller, bonus=bonus)
        dice_str = _format_interface_dice(details, bonus)
        self.caller.msg(f"|cCloak|n Interface {rank} + {dice_str} = {total} vs DV {dv}")
        state["trace_cloak_roll"] = total
        if total > dv:
            state["trace_sealed"] = True
            state["trace_actions"] = []
            self.caller.msg("|gCloak succeeds. Active forensic trail is scrubbed.|n")
        else:
            self.caller.msg("|rCloak fails. Trace residue remains in the architecture.|n")
            self._register_alarm(state, reason="Cloak routine failed to scrub activity")
        self._set_state(state)
        self._consume_net_action(state, "Cloak")

    def cmd_backdoor(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        floor = self._get_floor(arch, state)
        if not floor or floor.get("type") != "password":
            self.caller.msg("You are not on a Password floor.")
            return
        dv = int(floor.get("dv", 8))
        bonus = self._interface_bonus(state, "backdoor")
        total, rank, die, details = interface_check(self.caller, bonus=bonus)
        dice_str = _format_interface_dice(details, bonus)
        self.caller.msg(f"|cBackdoor|n Interface {rank} + {dice_str} = {total} vs DV {dv}")
        if total > dv:
            cleared = state.get("cleared_passwords", [])
            floor_num = int(floor["floor"])
            if floor_num not in cleared:
                cleared.append(floor_num)
            state["cleared_passwords"] = cleared
            self._set_state(state)
            self.caller.msg("|gPassword bypassed.|n")
            self.caller.msg("|xPath is open:|n use |w+net/move down|n to continue.")
        else:
            self.caller.msg("|rAccess denied.|n")
            self._register_alarm(state, reason=f"Backdoor failure on Floor {floor.get('floor')}")
        self._consume_net_action(state, "Backdoor")

    def cmd_eyedee(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        floor = self._get_floor(arch, state)
        if not floor or floor.get("type") not in ("file", "paydata"):
            self.caller.msg("There is no file/paydata target on this floor.")
            return
        dv = int(floor.get("dv", DIFFICULTY_DV.get(arch.db.difficulty, 8)))
        total, rank, die, details = interface_check(self.caller)
        dice_str = _format_interface_dice(details, 0)
        self.caller.msg(f"|cEye-Dee|n Interface {rank} + {dice_str} = {total} vs DV {dv}")
        if total <= dv:
            self.caller.msg("|rYou cannot decode this payload yet.|n")
            self._register_alarm(state, reason="Failed Eye-Dee against secured file node")
            self._consume_net_action(state, "Eye-Dee")
            return
        paydata = floor.get("paydata")
        if paydata:
            self.caller.msg(
                f"|gIdentified:|n {paydata.get('label')}  "
                f"(Estimated value: {paydata.get('value', 0)} eb)"
            )
        else:
            self.caller.msg("|gYou identify a file node. It appears valuable.|n")
        self._consume_net_action(state, "Eye-Dee")

    def cmd_control(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        floor = self._get_floor(arch, state)
        if not floor or floor.get("type") != "control":
            self.caller.msg("No control node on this floor.")
            return
        fnum = int(floor["floor"])
        controlled = state.get("controlled_nodes", [])
        verb = (self.args or "").strip().lower()
        if fnum in controlled and floor.get("defense") and verb in {"on", "off"}:
            disabled = set(state.get("disabled_defenses", []) or [])
            countered = set(state.get("countered_defenses", []) or [])
            if verb == "off":
                disabled.add(fnum)
                self.caller.msg(f"|yControl Node {fnum}: {floor.get('defense')} toggled OFF.|n")
            else:
                if fnum in countered:
                    self.caller.msg("|rThat defense is physically countered and cannot be toggled back on from NET control.|n")
                    return
                if fnum in disabled:
                    disabled.remove(fnum)
                self.caller.msg(f"|gControl Node {fnum}: {floor.get('defense')} toggled ON.|n")
            state["disabled_defenses"] = list(disabled)
            self._set_state(state)
            self._consume_net_action(state, "Control")
            return
        dv = int(floor.get("dv", DIFFICULTY_DV.get(arch.db.difficulty, 8)))
        total, rank, die, details = interface_check(self.caller)
        dice_str = _format_interface_dice(details, 0)
        self.caller.msg(f"|cControl|n Interface {rank} + {dice_str} = {total} vs DV {dv}")
        if total > dv:
            if fnum not in controlled:
                controlled.append(fnum)
            state["controlled_nodes"] = controlled
            self._set_state(state)
            self.caller.msg("|gControl node seized. You can now issue remote operations in-scene.|n")
            if floor.get("defense"):
                self.caller.msg(
                    f"|xLinked defense available:|n {floor.get('defense')} "
                    f"(use |w+net/control off|n or |w+net/control on|n here)."
                )
        else:
            self.caller.msg("|rControl node resists your command.|n")
            self._register_alarm(state, reason=f"Failed Control attempt on node {floor.get('floor')}")
        self._consume_net_action(state, "Control")

    def cmd_grab(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        self._record_trace_action(state, "Grab")
        floor = self._get_floor(arch, state)
        if not floor or floor.get("type") not in ("file", "paydata"):
            self.caller.msg("No file/paydata to copy on this floor.")
            return
        paydata = floor.get("paydata")
        if not paydata:
            paydata = generate_paydata_entry(arch.db.difficulty, int(floor["floor"]))
            floor["paydata"] = paydata
            floors = arch.db.floors or []
            floors[int(floor["floor"]) - 1] = floor
            arch.db.floors = floors

        claimed = paydata.get("claimed_by", [])
        if self.caller.id in claimed:
            self.caller.msg("You already copied this paydata package this cycle.")
            return

        dv = int(paydata.get("dv", floor.get("dv", DIFFICULTY_DV.get(arch.db.difficulty, 8))))
        total, rank, die, details = interface_check(self.caller)
        dice_str = _format_interface_dice(details, 0)
        self.caller.msg(f"|cExfiltrate|n Interface {rank} + {dice_str} = {total} vs DV {dv}")
        if total <= dv:
            self.caller.msg("|rTransfer failed. ICE chatter spikes as your access is denied.|n")
            self._register_alarm(state, reason="Failed Grab/Exfiltrate on protected data")
            return

        claimed.append(self.caller.id)
        paydata["claimed_by"] = claimed
        floor["paydata"] = paydata
        floors = arch.db.floors or []
        floors[int(floor["floor"]) - 1] = floor
        arch.db.floors = floors

        stash = self.caller.db.net_paydata or []
        stash.append(
            {
                "architecture": arch.key,
                "label": paydata.get("label"),
                "value": paydata.get("value", 0),
                "floor": floor.get("floor"),
            }
        )
        self.caller.db.net_paydata = stash
        self.caller.msg(
            f"|gPaydata copied:|n {paydata.get('label')} "
            f"(Street value {paydata.get('value', 0)} eb)"
        )
        self.caller.msg("|xNext step:|n |w+net/move down|n for deeper nodes or |w+net/jackout|n when done.")

    def cmd_programs(self):
        subs = [s.lower() for s in (self.switches or [])[1:]]
        if "shop" in subs:
            return self._show_program_shop()
        active = (self._get_state().get("active_programs", {}) if self._is_jacked_in() else {})
        state = self._get_state() if self._is_jacked_in() else {}
        installed = state.get("installed_programs", {}) or {}
        destroyed = set(state.get("destroyed_programs", []) or [])
        lines = ["|cProgram Catalog|n"]
        if not installed:
            lines.append("  No installed Programs/Black ICE found on your active cyberdeck.")
        for key, display_name in sorted(installed.items(), key=lambda item: item[1]):
            data = ALL_PROGRAMS.get(key) or get_black_ice(key)
            if not data:
                continue
            marker = " |g[ON]|n" if key in active else ""
            broken = " |r[DESTROYED]|n" if key in destroyed else ""
            lines.append(
                f"  {data['name']}{marker}{broken} - {data['class']} "
                f"(ATK {data['atk']} DEF {data['def']} REZ {data['rez']})"
            )
        lines.append("")
        lines.append("Acquire: |w+net/programs/shop|n  |w+net/buy <name>|n  |w+net/craft <name>|n")
        self.caller.msg("\n".join(lines))

    def _show_program_shop(self):
        """Display all purchasable programs and Black ICE with prices."""
        from world.utils.formatting import header, footer

        lines = [header("Netrunner Program Market"), "  |wPrograms|n"]
        for p in sorted(deckoptions.programs, key=lambda row: (row.get("type", ""), row.get("name", ""))):
            nm = p.get("name", "?")
            typ = p.get("type", "program")
            cost = int(p.get("cost", 0) or 0)
            lines.append(f"  - {nm} ({typ}) |y{cost} eb|n")
        lines.append("")
        lines.append("  |wBlack ICE (deployable package)|n")
        for b in sorted(deckoptions.black_ice, key=lambda row: row.get("name", "")):
            nm = b.get("name", "?")
            cost = int(b.get("cost", 0) or 0)
            lines.append(f"  - {nm} |y{cost} eb|n")
        lines.append("")
        lines.append("Buy now: |w+net/buy <program or black ice>|n")
        lines.append("Craft as Netrunner: |w+net/craft <program>|n or |w+make/program/add <name>|n")
        lines.append(footer())
        self.caller.msg("\n".join(lines))

    def cmd_buy_program(self):
        """Buy a program/Black ICE and add as gear to inventory."""
        room_tags, has_role_tag, has_stock_tag = self._net_vendor_tag_status()
        if not (has_role_tag and has_stock_tag):
            missing = []
            if not has_role_tag:
                missing.append("role tag (netrunner or hacker)")
            if not has_stock_tag:
                missing.append("stock tag (program or deck)")
            missing_text = ", ".join(missing) if missing else "required vendor tags"
            tags_text = ", ".join(sorted(room_tags)) if room_tags else "(none)"
            self.caller.msg(
                "You need to be in a tagged netrunner vendor room to buy programs. "
                f"Missing: {missing_text}. Current room tags: {tags_text}. "
                "Note: +room/tag replaces tags, so set all needed tags in one command "
                "(example: +room/tag here=netrunner,deck)."
            )
            return
        if not self.args:
            self.caller.msg("Usage: +net/buy <program or Black ICE name>")
            return
        data, err = self._resolve_program_or_ice(self.args)
        if err:
            self.caller.msg(err)
            return
        name = data.get("name", "").strip()
        if not name:
            self.caller.msg("Unable to resolve that item.")
            return
        cost = int(data.get("cost", 0) or 0)
        balance = CharacterMoneyService.get_balance(self.caller)
        if balance < cost:
            self.caller.msg(f"You need {cost} eb, but only have {balance} eb.")
            return
        if not CharacterMoneyService.spend_money(self.caller, cost):
            self.caller.msg("Purchase failed; funds could not be deducted.")
            return
        gear = ensure_program_gear(name)
        if not gear:
            CharacterMoneyService.add_money(self.caller, cost)
            self.caller.msg("Purchase failed; item could not be materialized.")
            return
        inv, _ = Inventory.get_or_create_for_character(self.caller)
        inv.add_gear(gear)
        self.caller.msg(
            f"|gPurchased|n {name} for |y{cost} eb|n. "
            f"It is in your inventory (use |wdeck/install <deck>={name}|n)."
        )

    def cmd_craft_program(self):
        """Queue a Netrunner program craft order (same backend as +make/program/add)."""
        if not self.args:
            self.caller.msg("Usage: +net/craft <program name>")
            return
        raw = self.args.strip()
        data, err = self._resolve_program_or_ice(raw)
        if err:
            self.caller.msg(err)
            return
        # Program crafting currently covers standard Programs, not Black ICE packages.
        if not any((p.get("name") or "").lower() == (data.get("name") or "").lower() for p in deckoptions.programs):
            self.caller.msg("Only standard Programs can be crafted with +net/craft right now.")
            return
        order, create_err = create_program_order(self.caller, data.get("name", raw))
        if create_err:
            self.caller.msg(f"|r{create_err}|n")
            return
        self.caller.msg(
            f"|gQueued program craft: {order.item_name}.|n "
            f"Materials: {order.materials_cost} eb. DV{order.dv}, ~{order.time_hours}h."
        )
        get_or_create_maker_script()

    def cmd_activate(self):
        if not self._require_netrun():
            return
        if not self.args:
            self.caller.msg("Usage: +net/activate <program>")
            return
        prog = get_program(self.args.strip())
        if not prog:
            self.caller.msg("Unknown program.")
            return
        state = self._get_state()
        installed = state.get("installed_programs", {}) or {}
        destroyed = set(state.get("destroyed_programs", []) or [])
        active = state.get("active_programs", {})
        key = normalize_name(prog["name"])
        if key not in installed:
            self.caller.msg("That program is not installed on your active cyberdeck.")
            return
        if key in destroyed:
            self.caller.msg("That program has been destroyed and cannot be activated this run.")
            return
        if key in active:
            self.caller.msg(f"{prog['name']} is already active.")
            return
        active[key] = {"name": prog["name"], "rez": prog["rez"], "def": int(prog.get("def", 0))}
        state["active_programs"] = active
        self._set_state(state)
        self.caller.msg(f"|gActivated {prog['name']}.|n")
        self._consume_net_action(state, "Activate Program")

    def cmd_deactivate(self):
        if not self._require_netrun():
            return
        if not self.args:
            self.caller.msg("Usage: +net/deactivate <program>")
            return
        key = normalize_name(self.args.strip())
        state = self._get_state()
        active = state.get("active_programs", {})
        if key not in active:
            self.caller.msg("That program is not active.")
            return
        name = active[key].get("name", key.replace("_", " ").title())
        del active[key]
        state["active_programs"] = active
        self._set_state(state)
        self.caller.msg(f"|yDeactivated {name}.|n")
        self._consume_net_action(state, "Deactivate Program")

    def cmd_zap(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("No valid floor.")
            return
        floor_ice = [i for i in self._ensure_floor_ice_state(state, floor) if i.get("active")]
        floor_num = int(floor.get("floor", state.get("floor", 1)))
        floor_runners = [r for r in self._enemy_runners_on_floor(state, floor_num) if r.get("active")]
        if not floor_ice and not floor_runners:
            self.caller.msg("No hostile ICE or netrunner targets on this floor.")
            return
        target_arg = (self.args or "").strip().lstrip("=").strip()
        if not target_arg and len(floor_ice) + len(floor_runners) > 1:
            options = self._ice_display_names(floor_ice) + self._enemy_runner_display_names(floor_runners)
            self.caller.msg(
                "Multiple hostile targets on this floor. Specify target: +net/zap <name or #>  "
                f"(e.g. {', '.join(options)})"
            )
            return
        ice_target, _ = self._pick_ice_target(floor_ice, target_arg)
        runner_target, _ = self._pick_runner_target(floor_runners, target_arg)
        target_is_runner = bool(runner_target) and (not ice_target or not target_arg or normalize_name(target_arg) == normalize_name(runner_target.get("name", "")))
        if target_is_runner:
            atk_total, rank, die, details = interface_check(self.caller)
            def_total = int(runner_target.get("interface", 4) or 4) + random.randint(1, 10)
            dice_str = _format_interface_dice(details, 0)
            self.caller.msg(
                f"|cZap|n Interface {rank}+{dice_str} = {atk_total} vs "
                f"{runner_target.get('name')} defense {def_total}"
            )
            if atk_total < def_total:
                self.caller.msg("|rZap misses.|n")
                self._consume_net_action(state, "Zap")
                return
            dmg = _roll_dice("1d6")
            runner_target["brain_hp"] = int(runner_target.get("brain_hp", 10) or 10) - dmg
            self.caller.msg(
                f"|gHit!|n {runner_target.get('name')} takes {dmg} brain damage "
                f"({max(0, int(runner_target.get('brain_hp', 0) or 0))} HP left)."
            )
            if int(runner_target.get("brain_hp", 0) or 0) <= 0:
                runner_target["active"] = False
                self.caller.msg(f"|y{runner_target.get('name')} is forced out and drops from the architecture.|n")
            self._set_enemy_runners_on_floor(state, floor_num, floor_runners)
            self._set_state(state)
            self._consume_net_action(state, "Zap")
            return
        target = ice_target
        if not target:
            self.caller.msg("Target not found. Use an ICE/runner name or 1-based index.")
            return
        ice = get_black_ice(normalize_name(target["name"]))
        atk_total, rank, die, details = interface_check(self.caller)
        def_total = int(ice["def"]) + random.randint(1, 10)
        dice_str = _format_interface_dice(details, 0)
        self.caller.msg(
            f"|cZap|n Interface {rank}+{dice_str} = {atk_total} vs "
            f"{ice['name']} DEF {ice['def']}+d10 = {def_total}"
        )
        if atk_total < def_total:
            self.caller.msg("|rZap misses.|n")
            self._consume_net_action(state, "Zap")
            return
        dmg = _roll_dice("1d6")
        target["rez"] -= dmg
        self.caller.msg(f"|gHit!|n {ice['name']} takes {dmg} REZ damage.")
        if target["rez"] <= 0:
            target["active"] = False
            self._remove_skunk_penalty_for_ice(state, target)
            self.caller.msg(f"|y{ice['name']} is Derezzed.|n")
        self._set_active_ice_on_floor(state, floor["floor"], floor_ice)
        self._set_state(state)
        self._consume_net_action(state, "Zap")

    def cmd_attack_program(self):
        if not self._require_netrun():
            return
        if not self.args:
            self.caller.msg("Usage: +net/attack <program> [=target]  (target needed if multiple ICE)")
            return
        if "=" in self.args:
            prog_arg, target_arg = self.args.split("=", 1)
        else:
            parts = self.args.strip().split(None, 1)
            prog_arg = parts[0] if parts else ""
            target_arg = parts[1] if len(parts) > 1 else ""
        prog = get_program(prog_arg.strip())
        if not prog:
            self.caller.msg("Unknown program.")
            return
        state = self._get_state()
        installed = state.get("installed_programs", {}) or {}
        destroyed = set(state.get("destroyed_programs", []) or [])
        pkey = normalize_name(prog["name"])
        if pkey not in installed:
            self.caller.msg("That program is not installed on your active cyberdeck.")
            return
        if pkey in destroyed:
            self.caller.msg("That program was destroyed and cannot be used this run.")
            return
        active = state.get("active_programs", {})
        if pkey not in active:
            self.caller.msg("Activate that program first with +net/activate.")
            return
        if "attacker" not in prog["class"].lower():
            self.caller.msg("That is not an attacker program.")
            return
        if state.get("attack_program_used", False):
            self.caller.msg("You can only run one attack Program per turn.")
            return
        arch = self._current_architecture()
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("No valid floor.")
            return
        floor_ice = [i for i in self._ensure_floor_ice_state(state, floor) if i.get("active")]
        floor_num = int(floor.get("floor", state.get("floor", 1)))
        floor_runners = [r for r in self._enemy_runners_on_floor(state, floor_num) if r.get("active")]
        if not floor_ice and not floor_runners:
            self.caller.msg("No valid target for that program on this floor.")
            return
        if not target_arg and len(floor_ice) + len(floor_runners) > 1:
            labels = self._ice_display_names(floor_ice) + self._enemy_runner_display_names(floor_runners)
            self.caller.msg(
                f"Multiple hostiles on this floor. Specify target: +net/attack {prog['name']}=<name or #>  "
                f"(e.g. {', '.join(labels)})"
            )
            return
        ice_target, _ = self._pick_ice_target(floor_ice, target_arg)
        runner_target, _ = self._pick_runner_target(floor_runners, target_arg)
        target_is_runner = bool(runner_target) and (not ice_target or not target_arg or normalize_name(target_arg) == normalize_name(runner_target.get("name", "")))
        atk_total = get_interface_rank(self.caller) + int(prog["atk"]) + random.randint(1, 10)
        if target_is_runner:
            if "anti-personnel" not in prog["class"].lower():
                self.caller.msg("That Program cannot target enemy Netrunners directly.")
                return
            def_total = int(runner_target.get("interface", 4) or 4) + random.randint(1, 10)
            self.caller.msg(
                f"|c{prog['name']}|n attack: {atk_total} vs {runner_target.get('name')} defense {def_total}"
            )
            if atk_total < def_total:
                self.caller.msg("|rProgram attack misses.|n")
            else:
                pkey = normalize_name(prog["name"])
                if pkey == "vrizzbolt":
                    dmg = _roll_dice("1d6")
                    runner_target["brain_hp"] = int(runner_target.get("brain_hp", 10) or 10) - dmg
                    runner_target["action_penalty_next"] = max(1, int(runner_target.get("action_penalty_next", 0) or 0))
                    self.caller.msg(f"|gVrizzbolt hits for {dmg} brain damage.|n")
                elif pkey == "superglue":
                    rounds = random.randint(1, 6)
                    runner_target["lock_deeper_rounds"] = max(rounds, int(runner_target.get("lock_deeper_rounds", 0) or 0))
                    runner_target["lock_safe_jackout_rounds"] = max(rounds, int(runner_target.get("lock_safe_jackout_rounds", 0) or 0))
                    self.caller.msg(f"|gSuperglue binds target NET movement for {rounds} rounds.|n")
                elif pkey in {"deckkrash", "hellbolt"}:
                    runner_target["active"] = False
                    self.caller.msg(f"|g{runner_target.get('name')} is forcibly and unsafely jacked out!|n")
                elif pkey == "poison_flatline":
                    programs = [nm for nm in (runner_target.get("programs") or []) if normalize_name(nm) not in {"asp","giant","hellhound","kraken","liche","raven","scorpion","skunk","wisp","dragon","killer","sabertooth"}]
                    if programs:
                        destroyed = random.choice(programs)
                        runner_target["programs"] = [nm for nm in (runner_target.get("programs") or []) if nm != destroyed]
                        self.caller.msg(f"|gPoison Flatline destroys {runner_target.get('name')}'s {destroyed}.|n")
                    else:
                        self.caller.msg("|yTarget has no non-Black ICE programs left to destroy.|n")
                elif pkey == "nervescrub":
                    self.caller.msg("|gNervescrub lands: target suffers temporary psychosomatic stat penalties.|n")
                else:
                    dmg = _roll_dice("1d6")
                    runner_target["brain_hp"] = int(runner_target.get("brain_hp", 10) or 10) - dmg
                    self.caller.msg(f"|gProgram effect lands for {dmg} brain damage.|n")
                if int(runner_target.get("brain_hp", 0) or 0) <= 0:
                    runner_target["active"] = False
                    self.caller.msg(f"|y{runner_target.get('name')} drops out of the architecture.|n")
            self._set_enemy_runners_on_floor(state, floor_num, floor_runners)
            self._set_state(state)
        else:
            target = ice_target
            if not target:
                self.caller.msg("Target not found. Use an ICE/runner name or 1-based index.")
                return
            ice = get_black_ice(normalize_name(target["name"]))
            def_total = int(ice["def"]) + random.randint(1, 10)
            self.caller.msg(
                f"|c{prog['name']}|n attack: {atk_total} vs {ice['name']} defense {def_total}"
            )
            if atk_total >= def_total:
                dmg = _roll_dice("3d6") if "anti-program" in prog["class"].lower() else _roll_dice("1d6")
                target["rez"] -= dmg
                self.caller.msg(f"|g{prog['name']} hits for {dmg} REZ.|n")
                if target["rez"] <= 0:
                    target["active"] = False
                    self._remove_skunk_penalty_for_ice(state, target)
                    self.caller.msg(f"|y{ice['name']} is Derezzed.|n")
            else:
                self.caller.msg("|rProgram attack misses.|n")
            self._set_active_ice_on_floor(state, floor["floor"], floor_ice)
        # Attack Programs are one-shot and auto-deactivate after use.
        active.pop(pkey, None)
        state["attack_program_used"] = True
        state["active_programs"] = active
        self._set_state(state)
        self._consume_net_action(state, f"{prog['name']} attack")

    def cmd_slide(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        if state.get("slide_used_turn", False):
            self.caller.msg("You can only Slide once per turn.")
            return
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("No valid floor.")
            return
        floor_ice = [i for i in self._ensure_floor_ice_state(state, floor) if i.get("active")]
        if not floor_ice:
            self.caller.msg("No ICE is currently engaging you on this floor.")
            return
        raw = (self.args or "").strip()
        if "=" in raw:
            move_arg, target_arg = raw.split("=", 1)
        else:
            move_arg, target_arg = raw, ""
        move_arg = move_arg.strip().lower()
        target_arg = target_arg.strip()
        if not move_arg:
            move_arg = "up"
        if len(floor_ice) > 1 and not target_arg:
            labels = self._ice_display_names(floor_ice)
            self.caller.msg(
                f"Multiple ICE on this floor. Specify target: +net/slide <up|floor#>=<name or #>  "
                f"(e.g. {', '.join(labels)})"
            )
            return
        target, _ = self._pick_ice_target(floor_ice, target_arg)
        if not target:
            self.caller.msg("ICE target not found. Use a name or 1-based index.")
            return
        floors = arch.db.floors or []
        cur = int(state.get("floor", 1))
        if move_arg == "up":
            new_floor = cur - 1
        else:
            try:
                new_floor = int(move_arg)
            except ValueError:
                self.caller.msg("Slide movement target must be up or a floor number.")
                return
        if new_floor >= cur:
            self.caller.msg("Slide can only disengage upward toward safer floors.")
            return
        if new_floor < 1 or new_floor > len(floors):
            self.caller.msg("That floor is out of range.")
            return
        ice = get_black_ice(normalize_name(target["name"]))
        slide_penalty = int(state.get("slide_penalty", 0) or 0)
        runner_total, rank, die, details = interface_check(self.caller, bonus=-slide_penalty)
        ice_total = int(ice["per"]) + random.randint(1, 10)
        dice_str = _format_interface_dice(details, -slide_penalty)
        self.caller.msg(
            f"|cSlide|n Interface {rank}+{dice_str} = {runner_total} vs "
            f"{ice['name']} PER {ice['per']}+d10 = {ice_total}"
        )
        state["slide_used_turn"] = True
        if runner_total > ice_total:
            self._send_ice_to_home_floor(state, target)
            state["floor"] = new_floor
            self._move_pursuing_ice(state, cur, new_floor)
            self._set_state(state)
            self.caller.msg(f"|gYou evade {ice['name']}; it loses you and falls back to its home floor.|n")
            self._show_current_floor(arch, state)
        else:
            self.caller.msg("|rSlide fails; the ICE stays on you.|n")
        self._consume_net_action(state, "Slide")

    def cmd_hostiles(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        state = self._get_state()
        mode = (self.args or "").strip().lower()
        floors = arch.db.floors or []
        if mode == "all":
            lines = ["|cHostile Presence: Full Architecture Sweep|n"]
            for floor in floors:
                fnum = int(floor.get("floor", 0) or 0)
                if fnum <= 0:
                    continue
                ice = [i for i in self._get_active_ice_on_floor(state, fnum) if i.get("active")]
                runners = [r for r in self._enemy_runners_on_floor(state, fnum) if r.get("active")]
                if not ice and not runners:
                    continue
                lines.append(f"  |wF{fnum}|n {floor.get('name', '?')}:")
                if ice:
                    ice_labels = self._ice_display_names(ice)
                    lines.append("    ICE: " + ", ".join(f"{ice_labels[idx]}({obj.get('rez', '?')} REZ)" for idx, obj in enumerate(ice)))
                if runners:
                    runner_labels = self._enemy_runner_display_names(runners)
                    lines.append("    Runners: " + ", ".join(f"{runner_labels[idx]}(IF {obj.get('interface', '?')})" for idx, obj in enumerate(runners)))
            if len(lines) == 1:
                lines.append("  No active hostile ICE or netrunners detected.")
            self.caller.msg("\n".join(lines))
            return
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("No valid floor.")
            return
        fnum = int(floor.get("floor", state.get("floor", 1)) or 1)
        ice = [i for i in self._get_active_ice_on_floor(state, fnum) if i.get("active")]
        runners = [r for r in self._enemy_runners_on_floor(state, fnum) if r.get("active")]
        if not ice and not runners:
            self.caller.msg("No active hostile ICE or netrunners on this floor.")
            return
        lines = [f"|cHostiles on F{fnum}|n"]
        if ice:
            labels = self._ice_display_names(ice)
            lines.append("  ICE: " + ", ".join(f"{labels[idx]}({obj.get('rez', '?')} REZ)" for idx, obj in enumerate(ice)))
        if runners:
            labels = self._enemy_runner_display_names(runners)
            lines.append("  Netrunners: " + ", ".join(f"{labels[idx]}(Interface {obj.get('interface', '?')}, HP {obj.get('brain_hp', '?')})" for idx, obj in enumerate(runners)))
        self.caller.msg("\n".join(lines))

    def cmd_extinguish(self):
        if not self._require_netrun():
            return
        state = self._get_state()
        if not state.get("on_fire", False):
            self.caller.msg("You are not currently burning.")
            return
        room = self._entry_room(state)
        try:
            from commands import combat_system as cbt
            ok, msg = cbt.consume_action_for_character(room, self.caller, label="extinguish fire")
        except Exception:
            ok, msg = True, ""
        if not ok:
            self.caller.msg(msg or "You cannot spend a Meat Action to extinguish right now.")
            return
        state["on_fire"] = False
        self._set_state(state)
        self.caller.msg("|gYou spend your Meat Action patting out flames and securing your deck.|n")

    def cmd_counter(self):
        """
        Counter linked defense workflow on current control node.
          +net/counter
          +net/counter status
          +net/counter start
          +net/counter work
          +net/counter abort
        """
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("No valid floor.")
            return
        raw = (self.args or "").strip().lower()
        sub = raw or "status"
        job = state.get("counter_job")
        floor_num = int(floor.get("floor", state.get("floor", 1)) or 1)
        if floor.get("type") != "control" or not floor.get("defense"):
            self.caller.msg("Counter workflow is only available on control nodes with linked defenses.")
            return
        defense = floor.get("defense")
        template = get_active_defense_template(defense) or {}
        countered = set(state.get("countered_defenses", []) or [])
        if sub in {"status", ""}:
            if floor_num in countered:
                self.caller.msg(f"|g{defense} is already COUNTERED on this floor.|n")
                return
            if job:
                self.caller.msg(
                    f"|mCounter job|n F{job.get('floor')} {job.get('spent_actions', 0)}/{job.get('total_actions', 0)} "
                    f"(DV {job.get('dv', '?')})"
                )
            else:
                self.caller.msg(
                    f"No active counter job. Start with |w+net/counter start|n "
                    f"(DV {template.get('counter_dv', '?')}, ~{template.get('counter_time_min', '?')} actions)."
                )
            return
        if sub == "abort":
            if not job:
                self.caller.msg("No active counter job.")
                return
            state["counter_job"] = None
            self._set_state(state)
            self.caller.msg("|yCounter job aborted.|n")
            return
        if sub == "start":
            if floor_num in countered:
                self.caller.msg(f"{defense} is already physically countered.")
                return
            if job:
                self.caller.msg("Counter job already in progress. Use +net/counter work or +net/counter abort.")
                return
            total_actions = max(1, int(template.get("counter_time_min", 1) or 1))
            dv = int(template.get("counter_dv", DIFFICULTY_DV.get(getattr(arch.db, "difficulty", "standard"), 8)))
            state["counter_job"] = {
                "floor": floor_num,
                "defense": defense,
                "dv": dv,
                "total_actions": total_actions,
                "spent_actions": 0,
            }
            self._set_state(state)
            self.caller.msg(f"|gCounter job started|n for {defense}: DV {dv}, {total_actions} actions.")
            return
        if sub == "work":
            if not job:
                self.caller.msg("No active counter job. Use +net/counter start.")
                return
            if int(job.get("floor", -1) or -1) != floor_num:
                self.caller.msg("Return to the originating control node floor to continue this counter job.")
                return
            job["spent_actions"] = int(job.get("spent_actions", 0) or 0) + 1
            state["counter_job"] = job
            self._set_state(state)
            self.caller.msg(
                f"|mCounter progress:|n {job['spent_actions']}/{job['total_actions']} actions."
            )
            self._consume_net_action(state, "Counter")
            if not self._is_jacked_in():
                return
            state = self._get_state()
            job = state.get("counter_job") or {}
            if int(job.get("spent_actions", 0) or 0) < int(job.get("total_actions", 0) or 0):
                return
            bonus = self._electronics_security_skill()
            total, rank, die, details = interface_check(self.caller, bonus=bonus)
            dice_str = _format_interface_dice(details, bonus)
            dv = int(job.get("dv", 13) or 13)
            self.caller.msg(f"|cCounter Check|n Interface {rank} + {dice_str} = {total} vs DV {dv}")
            if total > dv:
                countered = set(state.get("countered_defenses", []) or [])
                disabled = set(state.get("disabled_defenses", []) or [])
                countered.add(floor_num)
                disabled.add(floor_num)
                state["countered_defenses"] = list(countered)
                state["disabled_defenses"] = list(disabled)
                self.caller.msg(f"|gCounter successful: {defense} is physically disabled.|n")
            else:
                self.caller.msg("|rCounter attempt fails; defense remains active.|n")
            state["counter_job"] = None
            self._set_state(state)
            return
        self.caller.msg("Usage: +net/counter [status|start|work|abort]")

    def cmd_demon(self):
        """
        Demon controls.
          +net/demon
          +net/demon status
          +net/demon pause
          +net/demon resume
          +net/demon on   (staff)
          +net/demon off  (staff)
        """
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        demon = getattr(arch.db, "demon", None) or {}
        if not demon:
            self.caller.msg("No demon is loaded on this architecture.")
            return
        state = self._get_state()
        sub = (self.args or "").strip().lower() or "status"
        if sub in {"", "status"}:
            self.caller.msg(
                f"Demon {demon.get('name', 'Imp')}: "
                f"global={'on' if bool(getattr(arch.db, 'demon_enabled', True)) else 'off'}, "
                f"local={'paused' if state.get('demon_paused', False) else 'active'}."
            )
            return
        if sub in {"pause", "resume"}:
            state["demon_paused"] = sub == "pause"
            self._set_state(state)
            self.caller.msg(
                f"|yDemon local state set to {'paused' if state['demon_paused'] else 'active'} for your run.|n"
            )
            return
        if sub in {"on", "off"}:
            if not check_builder_permission(self.caller):
                self.caller.msg("Only staff/storytellers can toggle architecture-wide demon power.")
                return
            arch.db.demon_enabled = sub == "on"
            self.caller.msg(f"|gDemon global power is now {'on' if arch.db.demon_enabled else 'off'}.|n")
            return
        self.caller.msg("Usage: +net/demon [status|pause|resume|on|off]")

    def cmd_virus(self):
        """
        Virus workflow at architecture bottom.
          +net/virus
          +net/virus status
          +net/virus start <dv>/<actions>=<description>
          +net/virus work
          +net/virus abort
          +net/virus list
        """
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("No valid floor.")
            return
        raw = (self.args or "").strip()
        sub = raw.split(None, 1)[0].lower() if raw else "status"
        job = state.get("virus_job")

        if sub in {"", "status"}:
            if job:
                self.caller.msg(
                    f"|mVirus job:|n DV {job.get('dv')} | "
                    f"Progress {job.get('spent_actions', 0)}/{job.get('total_actions', 0)} | "
                    f"{job.get('description', '')}"
                )
            else:
                self.caller.msg("No active virus job.")
            if floor.get("is_bottom"):
                self.caller.msg(
                    "Bottom node confirmed. Start with |w+net/virus start <dv>/<actions>=<description>|n"
                )
            return

        if sub == "list":
            viruses = getattr(arch.db, "viruses", None) or []
            if not viruses:
                self.caller.msg("No persistent viruses are currently installed in this architecture.")
                return
            lines = ["|mPersistent Viruses|n"]
            for idx, v in enumerate(viruses, start=1):
                lines.append(
                    f"  #{idx}: DV {v.get('dv', '?')} by {v.get('author', 'unknown')} "
                    f"(F{v.get('floor', '?')}) - {v.get('description', '')}"
                )
            self.caller.msg("\n".join(lines))
            return

        if sub == "abort":
            if not job:
                self.caller.msg("No active virus job to abort.")
                return
            state["virus_job"] = None
            self._set_state(state)
            self.caller.msg("|yVirus job aborted.|n")
            return

        if sub == "start":
            if not floor.get("is_bottom"):
                self.caller.msg("Viruses can only be authored from the architecture's bottom node.")
                return
            if job:
                self.caller.msg("A virus job is already in progress. Use +net/virus work or +net/virus abort.")
                return
            payload = raw[len("start"):].strip()
            if "=" not in payload or "/" not in payload:
                self.caller.msg("Usage: +net/virus start <dv>/<actions>=<description>")
                return
            left, desc = payload.split("=", 1)
            left = left.strip()
            desc = desc.strip()
            if not desc:
                self.caller.msg("Virus description cannot be blank.")
                return
            dv_s, actions_s = [x.strip() for x in left.split("/", 1)]
            if not dv_s.isdigit() or not actions_s.isdigit():
                self.caller.msg("DV and actions must be numeric.")
                return
            dv = int(dv_s)
            total_actions = max(1, int(actions_s))
            state["virus_job"] = {
                "dv": dv,
                "total_actions": total_actions,
                "spent_actions": 0,
                "description": desc[:500],
                "floor": int(floor.get("floor", 1)),
            }
            self._set_state(state)
            self.caller.msg(
                f"|gVirus job started.|n DV {dv}, {total_actions} NET actions required."
            )
            return

        if sub == "work":
            if not job:
                self.caller.msg("No active virus job. Start one with +net/virus start ...")
                return
            if int(floor.get("floor", 0) or 0) != int(job.get("floor", -1) or -1):
                self.caller.msg("You must return to the original floor where this virus job started.")
                return
            job["spent_actions"] = int(job.get("spent_actions", 0) or 0) + 1
            state["virus_job"] = job
            self._set_state(state)
            self.caller.msg(
                f"|mVirus coding progress:|n {job['spent_actions']}/{job['total_actions']} actions."
            )
            self._consume_net_action(state, "Virus")
            if not self._is_jacked_in():
                return
            state = self._get_state()
            job = state.get("virus_job")
            if not job:
                return
            if int(job.get("spent_actions", 0)) < int(job.get("total_actions", 0)):
                return
            total, rank, die, details = interface_check(self.caller)
            dice_str = _format_interface_dice(details, 0)
            dv = int(job.get("dv", 13) or 13)
            self.caller.msg(f"|cVirus Check|n Interface {rank} + {dice_str} = {total} vs DV {dv}")
            if total > dv:
                viruses = getattr(arch.db, "viruses", None) or []
                viruses.append(
                    {
                        "author_id": self.caller.id,
                        "author": self.caller.key,
                        "description": job.get("description", ""),
                        "dv": total,
                        "actions": int(job.get("total_actions", 1) or 1),
                        "floor": int(job.get("floor", 1) or 1),
                    }
                )
                arch.db.viruses = viruses
                self.caller.msg("|gVirus seeded successfully; it persists after jack out.|n")
            else:
                self.caller.msg("|rVirus check fails. The code collapses; restart from scratch.|n")
            state["virus_job"] = None
            self._set_state(state)
            return

        self.caller.msg("Usage: +net/virus [status|start <dv>/<actions>=<description>|work|abort|list]")

    def cmd_delve(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        state = self._get_state()
        floor_num = int(state.get("floor", 1))
        _lead, msg = net_disc.delve_next_lead(self.caller, arch, floor_num)
        self.caller.msg(msg)
        self._consume_net_action(state, "Delve")

    def cmd_trace(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        state = self._get_state()
        floor_num = int(state.get("floor", 1))
        if self.args and str(self.args).strip():
            if not str(self.args).strip().isdigit():
                self.caller.msg("Usage: +net/trace <lead id>")
                return
            lead_id = int(str(self.args).strip())
        else:
            unresolved = net_disc.exposed_unresolved_leads(self.caller, arch, floor_num)
            if not unresolved:
                self.caller.msg(
                    "No open swept leads to trace on this floor. Use |w+net/delve|n first."
                )
                return
            if len(unresolved) > 1:
                lines = ["Multiple open leads. Use |w+net/trace <id>|n:"]
                for lead in unresolved:
                    lines.append(f"  |w#{lead.pk}|n {lead.label}")
                self.caller.msg("\n".join(lines))
                return
            lead_id = unresolved[0].pk
        _ok, msg = net_disc.trace_lead(self.caller, arch, floor_num, lead_id)
        self.caller.msg(msg)
        if not _ok:
            self._register_alarm(state, reason="Trace pattern destabilized and raised architecture alerts")
        self._consume_net_action(state, "Trace")

    def cmd_leads(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        state = self._get_state()
        floor_num = int(state.get("floor", 1))
        self.caller.msg(net_disc.format_leads_notebook(self.caller, arch, floor_num))

    def _cmd_net_lead(self):
        subs = [s.lower() for s in (self.switches or [])[1:]]
        if not subs:
            self.caller.msg(
                "Staff NET leads: |w+net/lead/create|n, |w+net/lead/list|n, |w+net/lead/destroy|n, "
                "|w+net/lead/requires|n, |w+net/lead/link|n, |w+net/lead/paydata|n, "
                "|w+net/lead/program|n, |w+net/lead/text|n, |w+net/lead/teaser|n, "
                "|w+net/lead/priority|n, |w+net/lead/notes|n"
            )
            return
        sub = subs[0]
        if sub == "create":
            self._net_lead_create()
        elif sub == "list":
            self._net_lead_list()
        elif sub == "destroy":
            self._net_lead_destroy()
        elif sub == "requires":
            self._net_lead_requires()
        elif sub == "link":
            self._net_lead_link()
        elif sub == "paydata":
            self._net_lead_paydata()
        elif sub == "program":
            self._net_lead_program()
        elif sub == "text":
            self._net_lead_text()
        elif sub == "teaser":
            self._net_lead_teaser()
        elif sub == "priority":
            self._net_lead_priority()
        elif sub == "notes":
            self._net_lead_notes()
        else:
            self.caller.msg("Unknown +net/lead subcommand.")

    def _parse_lead_id(self, raw):
        """Parse a lead id token, allowing optional leading #."""
        token = (raw or "").strip()
        if token.startswith("#"):
            token = token[1:]
        if not token.isdigit():
            return None
        return int(token)

    def _net_lead_create(self):
        raw = (self.args or "").strip()
        if "=" not in raw:
            self.caller.msg(
                "Usage: +net/lead/create <architecture>=<floor>/<slug>/<type>/<scan>/<inv>/<label>[|<extra>]"
            )
            self.caller.msg(
                "   or: +net/lead/create <architecture>=<floor>|<slug>|<type>|<scan>|<inv>|<label>[|<extra>]"
            )
            self.caller.msg(
                "Types: |wpaydata|n, |wprogram|n, |wnarrative|n, |wflavor|n. "
                "Extra after |: paydata eb value, program name, or flavor/narrative text."
            )
            return
        arch_part, rhs = raw.split("=", 1)
        arch = self._find_architecture(arch_part.strip())
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        rhs = rhs.strip()
        floor_s = slug = ltype = scan_s = inv_s = label = ""
        extra = ""

        valid_types = {"paydata", "program", "narrative", "flavor"}

        # Supported forms:
        #   floor/slug/type/scan/inv/label[|extra]
        #   floor|slug|type|scan|inv|label[|extra]
        if "/" in rhs:
            if "|" in rhs:
                rhs, extra = rhs.rsplit("|", 1)
                extra = extra.strip()
            parts = rhs.split("/")
            if len(parts) < 6:
                self.caller.msg("Need |wfloor/slug/type/scan_dv/investigate_dv/label|n")
                return
            floor_s, slug, ltype, scan_s, inv_s = parts[:5]
            label = "/".join(parts[5:])
        else:
            parts = [p.strip() for p in rhs.split("|")]
            if len(parts) < 6:
                self.caller.msg("Need |wfloor|slug|type|scan_dv|investigate_dv|label|n")
                return
            floor_s, slug, ltype, scan_s, inv_s, label = parts[:6]
            if len(parts) > 6:
                extra = "|".join(parts[6:]).strip()

        # Backward-compatible rescue for accidentally swapped pipe order:
        # floor|slug|label|scan|inv|type
        if ltype.strip().lower() not in valid_types and label.strip().lower() in valid_types:
            ltype, label = label, ltype
        try:
            floor_num = int(floor_s)
            scan_dv = int(scan_s)
            inv_dv = int(inv_s)
        except ValueError:
            self.caller.msg("Floor and DVs must be integers.")
            return
        floors = arch.db.floors or []
        if floor_num < 1 or floor_num > len(floors):
            self.caller.msg(f"Floor must be between 1 and {len(floors)} for this architecture.")
            return
        if not slug.strip():
            self.caller.msg("Slug is required.")
            return
        ltype = ltype.strip().lower()
        if ltype not in valid_types:
            self.caller.msg(
                "Type must be paydata, program, narrative, or flavor. "
                "Expected: floor|slug|type|scan_dv|investigate_dv|label"
            )
            return

        lead = NetFloorLead(
            architecture_object_id=arch.id,
            floor_number=floor_num,
            slug=slug.strip().lower()[:80],
            label=label.strip()[:200],
            scan_dv=scan_dv,
            investigate_dv=inv_dv,
            lead_type=ltype,
        )
        if ltype == "paydata":
            lead.paydata_label = lead.label
            if extra:
                try:
                    lead.paydata_value = int(extra)
                except ValueError:
                    # Allow descriptive paydata teaser text in create flow.
                    # Monetary value can still be set explicitly via +net/lead/paydata.
                    lead.teaser = extra
        elif ltype == "program" and extra:
            lead.program_name = extra.strip()[:200]
        elif ltype in ("narrative", "flavor") and extra:
            lead.teaser = extra
            if ltype == "flavor":
                lead.success_text = extra
        lead.save()
        self.caller.msg(f"|gCreated lead|n id |w{lead.pk}|n ({lead.slug}) on |c{arch.key}|n floor {floor_num}.")

    def _net_lead_list(self):
        name = (self.args or "").strip()
        arch = None
        if name:
            arch = self._find_architecture(name)
        elif self._is_jacked_in():
            arch = self._current_architecture()
        if not arch:
            self.caller.msg("Usage: +net/lead/list <architecture> (or jack in and omit name)")
            return
        qs = NetFloorLead.objects.filter(architecture_object_id=arch.id).order_by("floor_number", "discovery_priority", "id")
        if not qs.exists():
            self.caller.msg("No leads on that architecture.")
            return
        lines = [f"|c{arch.key}|n — NET floor leads"]
        for lead in qs:
            pre_ids = list(lead.prerequisite_leads.values_list("id", flat=True))
            linked_ids = list(lead.linked_leads.values_list("id", flat=True))
            meta = []
            if pre_ids:
                meta.append("requires: " + ",".join(f"#{x}" for x in pre_ids[:6]))
            if linked_ids:
                meta.append("links: " + ",".join(f"#{x}" for x in linked_ids[:6]))
            lines.append(
                f"  |wF{lead.floor_number}|n #{lead.pk} |y{lead.lead_type}|n {lead.slug} DV {lead.scan_dv}/{lead.investigate_dv} — {lead.label}"
                + (f" |c({' | '.join(meta)})|n" if meta else "")
            )
        self.caller.msg("\n".join(lines))

    def _net_lead_destroy(self):
        lead_id = self._parse_lead_id(self.args)
        if lead_id is None:
            self.caller.msg("Usage: +net/lead/destroy <lead id>")
            return
        lead = NetFloorLead.objects.filter(pk=lead_id).first()
        if not lead:
            self.caller.msg("No such lead.")
            return
        lead.delete()
        self.caller.msg("|gDeleted.|n")

    def _net_lead_requires(self):
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: +net/lead/requires <dependent id>=<prerequisite id>")
            return
        left, right = self.args.split("=", 1)
        child_id = self._parse_lead_id(left)
        parent_id = self._parse_lead_id(right)
        if child_id is None or parent_id is None:
            self.caller.msg("Ids must be numbers.")
            return
        child = NetFloorLead.objects.filter(pk=child_id).first()
        parent = NetFloorLead.objects.filter(pk=parent_id).first()
        if not child or not parent:
            self.caller.msg("Lead id not found.")
            return
        if child.pk == parent.pk:
            self.caller.msg("A lead cannot require itself.")
            return
        if child.architecture_object_id != parent.architecture_object_id:
            self.caller.msg("Both leads must belong to the same architecture.")
            return
        child.prerequisite_leads.add(parent)
        self.caller.msg(f"|gLead #{child.pk} now requires #{parent.pk} resolved first.|n")

    def _net_lead_link(self):
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: +net/lead/link <lead id>=<related lead id>")
            return
        left, right = self.args.split("=", 1)
        a_id = self._parse_lead_id(left)
        b_id = self._parse_lead_id(right)
        if a_id is None or b_id is None:
            self.caller.msg("Ids must be numbers.")
            return
        a = NetFloorLead.objects.filter(pk=a_id).first()
        b = NetFloorLead.objects.filter(pk=b_id).first()
        if not a or not b:
            self.caller.msg("Lead id not found.")
            return
        if a.pk == b.pk:
            self.caller.msg("A lead cannot be linked to itself.")
            return
        if a.architecture_object_id != b.architecture_object_id:
            self.caller.msg("Both leads must belong to the same architecture.")
            return
        a.linked_leads.add(b)
        self.caller.msg(f"|gLinked leads #{a.pk} and #{b.pk} (notebook cross-reference).|n")

    def _net_lead_paydata(self):
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: +net/lead/paydata <id>=<eb value>[/<label>]")
            return
        left, right = self.args.split("=", 1)
        lead_id = self._parse_lead_id(left)
        if lead_id is None:
            self.caller.msg("Lead id must be a number.")
            return
        lead = NetFloorLead.objects.filter(pk=lead_id).first()
        if not lead:
            self.caller.msg("No such lead.")
            return
        right = right.strip()
        if "/" in right:
            val_s, lab = right.split("/", 1)
            try:
                lead.paydata_value = int(val_s.strip())
            except ValueError:
                self.caller.msg("Value must be numeric.")
                return
            lead.paydata_label = lab.strip()[:200]
        else:
            try:
                lead.paydata_value = int(right)
            except ValueError:
                self.caller.msg("Value must be numeric.")
                return
        lead.lead_type = NetFloorLead.LEAD_PAYDATA
        lead.save()
        self.caller.msg("|gUpdated paydata fields.|n")

    def _net_lead_program(self):
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: +net/lead/program <id>=<program name>")
            return
        left, right = self.args.split("=", 1)
        lead_id = self._parse_lead_id(left)
        if lead_id is None:
            self.caller.msg("Lead id must be a number.")
            return
        lead = NetFloorLead.objects.filter(pk=lead_id).first()
        if not lead:
            self.caller.msg("No such lead.")
            return
        lead.program_name = right.strip()[:200]
        lead.lead_type = NetFloorLead.LEAD_PROGRAM
        lead.save()
        self.caller.msg("|gUpdated program name.|n")

    def _net_lead_text(self):
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: +net/lead/text <id>=<success / narrative text>")
            return
        left, right = self.args.split("=", 1)
        lead_id = self._parse_lead_id(left)
        if lead_id is None:
            self.caller.msg("Lead id must be a number.")
            return
        lead = NetFloorLead.objects.filter(pk=lead_id).first()
        if not lead:
            self.caller.msg("No such lead.")
            return
        lead.success_text = right.strip()
        lead.save()
        self.caller.msg("|gUpdated success text.|n")

    def _net_lead_teaser(self):
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: +net/lead/teaser <id>=<scan-time teaser text>")
            return
        left, right = self.args.split("=", 1)
        lead_id = self._parse_lead_id(left)
        if lead_id is None:
            self.caller.msg("Lead id must be a number.")
            return
        lead = NetFloorLead.objects.filter(pk=lead_id).first()
        if not lead:
            self.caller.msg("No such lead.")
            return
        lead.teaser = right.strip()
        lead.save()
        self.caller.msg("|gUpdated teaser text.|n")

    def _net_lead_priority(self):
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: +net/lead/priority <id>=<number> (lower appears first)")
            return
        left, right = self.args.split("=", 1)
        lead_id = self._parse_lead_id(left)
        try:
            pri = int(right.strip())
        except ValueError:
            self.caller.msg("Lead id and priority must be numbers.")
            return
        if lead_id is None:
            self.caller.msg("Lead id and priority must be numbers.")
            return
        lead = NetFloorLead.objects.filter(pk=lead_id).first()
        if not lead:
            self.caller.msg("No such lead.")
            return
        lead.discovery_priority = max(0, pri)
        lead.save()
        self.caller.msg(f"|gUpdated discovery priority to {lead.discovery_priority}.|n")

    def _net_lead_notes(self):
        if "=" not in (self.args or ""):
            self.caller.msg("Usage: +net/lead/notes <id>=<staff notes>")
            return
        left, right = self.args.split("=", 1)
        lead_id = self._parse_lead_id(left)
        if lead_id is None:
            self.caller.msg("Lead id must be a number.")
            return
        lead = NetFloorLead.objects.filter(pk=lead_id).first()
        if not lead:
            self.caller.msg("No such lead.")
            return
        lead.staff_notes = right.strip()
        lead.save()
        self.caller.msg("|gUpdated staff notes.|n")

    # ---- Staff switches ----

    def cmd_intruder(self):
        """
        Staff: inject hostile netrunners into current floor.
        Usage: +net/intruder <novice|professional|expert|master>[,<count>]
        """
        if not self._require_netrun():
            return
        raw = (self.args or "").strip().lower()
        if not raw:
            self.caller.msg("Usage: +net/intruder <novice|professional|expert|master>[,<count>]")
            return
        if "," in raw:
            tier_s, count_s = [x.strip() for x in raw.split(",", 1)]
        else:
            tier_s, count_s = raw, "1"
        if tier_s not in {"novice", "professional", "expert", "master"}:
            self.caller.msg("Tier must be novice, professional, expert, or master.")
            return
        if not count_s.isdigit():
            self.caller.msg("Count must be numeric.")
            return
        count = max(1, min(10, int(count_s)))
        state = self._get_state()
        floor_num = int(state.get("floor", 1) or 1)
        for _ in range(count):
            self._spawn_enemy_runner(state, floor_num, tier=tier_s)
        self._set_state(state)

    def cmd_create_architecture(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +net/create <name>=<difficulty>[,<floors>]")
            return
        name, rhs = self.args.split("=", 1)
        name = name.strip()
        parts = [p.strip().lower() for p in rhs.split(",") if p.strip()]
        difficulty = parts[0] if parts else "standard"
        floors = None
        if len(parts) > 1:
            try:
                floors = int(parts[1])
            except ValueError:
                self.caller.msg("Floor count must be a number.")
                return
        if difficulty not in DIFFICULTY_DV:
            self.caller.msg("Difficulty must be basic, standard, uncommon, or advanced.")
            return
        arch = evennia.create_object(
            "typeclasses.netrunning.NetArchitecture",
            key=name,
            location=self.caller.location,
        )
        arch.db.difficulty = difficulty
        generated_floors = generate_architecture(difficulty, floor_count=floors)
        arch.db.floors = generated_floors
        arch.db.demon = generate_demon_for_architecture(difficulty, len(generated_floors))
        arch.db.demon_enabled = True
        arch.db.viruses = []
        self.caller.msg(
            f"|gCreated architecture {arch.key}|n "
            f"({difficulty}, {len(arch.db.floors or [])} floors)."
        )
        if arch.db.demon:
            self.caller.msg(f"|mDemon loaded:|n {arch.db.demon.get('name')} ({arch.db.demon.get('net_actions')} NET actions)")

    def cmd_generate_architecture(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +net/generate <arch>=<difficulty>[,<floors>]")
            return
        arch_name, rhs = self.args.split("=", 1)
        arch = self._find_architecture(arch_name.strip())
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        parts = [p.strip().lower() for p in rhs.split(",") if p.strip()]
        difficulty = parts[0] if parts else "standard"
        floors = None
        if len(parts) > 1:
            try:
                floors = int(parts[1])
            except ValueError:
                self.caller.msg("Floor count must be numeric.")
                return
        if difficulty not in DIFFICULTY_DV:
            self.caller.msg("Difficulty must be basic, standard, uncommon, or advanced.")
            return
        arch.db.difficulty = difficulty
        generated_floors = generate_architecture(difficulty, floor_count=floors)
        arch.db.floors = generated_floors
        arch.db.demon = generate_demon_for_architecture(difficulty, len(generated_floors))
        arch.db.demon_enabled = True
        arch.db.viruses = []
        self.caller.msg(f"|gRegenerated {arch.key}|n: {difficulty}, {len(arch.db.floors or [])} floors.")
        if arch.db.demon:
            self.caller.msg(f"|mDemon loaded:|n {arch.db.demon.get('name')} ({arch.db.demon.get('net_actions')} NET actions)")

    def cmd_show_architecture(self):
        if not self.args:
            if self._is_jacked_in():
                arch = self._current_architecture()
            else:
                self.caller.msg("Usage: +net/show <architecture>")
                return
        else:
            arch = self._find_architecture(self.args.strip())
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        lines = [f"|c{arch.key}|n  Difficulty: {(arch.db.difficulty or 'standard').title()}"]
        demon = getattr(arch.db, "demon", None)
        if demon:
            lines.append(
                f"  Demon: {demon.get('name', 'Imp')} "
                f"(Interface {demon.get('interface', '?')}, NET actions {demon.get('net_actions', '?')}, "
                f"global={'on' if bool(getattr(arch.db, 'demon_enabled', True)) else 'off'})"
            )
        for floor in arch.db.floors or []:
            line = f"  F{floor['floor']:>2}: {floor.get('name', '?')} ({floor.get('type', '?')})"
            if floor.get("dv") is not None:
                line += f" DV {floor['dv']}"
            if floor.get("branch") and floor.get("branch") != "main":
                line += f" [{floor.get('branch')}]"
            if floor.get("is_bottom"):
                line += " |g[BOTTOM]|n"
            if floor.get("defense"):
                line += f" |m[{floor.get('defense')}]|n"
            if floor.get("paydata"):
                line += f" |y[Paydata {floor['paydata'].get('value', 0)}eb]|n"
            lines.append(line)
        viruses = getattr(arch.db, "viruses", None) or []
        if viruses:
            lines.append("")
            lines.append("|mPersistent Viruses|n:")
            for idx, v in enumerate(viruses, start=1):
                lines.append(
                    f"  #{idx}: DV {v.get('dv', '?')} by {v.get('author', 'unknown')} "
                    f"(F{v.get('floor', '?')}) - {v.get('description', '')}"
                )
        self.caller.msg("\n".join(lines))

    def cmd_setfloor(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +net/setfloor <arch>=<floor>/<type>[/<value>]")
            return
        arch_name, rhs = self.args.split("=", 1)
        arch = self._find_architecture(arch_name.strip())
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        parts = [p.strip() for p in rhs.split("/") if p.strip()]
        if len(parts) < 2:
            self.caller.msg("Usage: +net/setfloor <arch>=<floor>/<type>[/<value>]")
            return
        try:
            floor_num = int(parts[0])
        except ValueError:
            self.caller.msg("Floor must be a number.")
            return
        floors = arch.db.floors or []
        if floor_num < 1 or floor_num > len(floors):
            self.caller.msg("Floor out of range.")
            return
        ftype = normalize_name(parts[1])
        value = parts[2] if len(parts) > 2 else None
        dv_default = DIFFICULTY_DV.get(arch.db.difficulty, 8)
        if ftype == "password":
            dv = int(value) if value and value.isdigit() else dv_default
            floor = {"floor": floor_num, "type": "password", "name": "Password", "dv": dv}
        elif ftype == "file":
            dv = int(value) if value and value.isdigit() else dv_default
            floor = {"floor": floor_num, "type": "file", "name": "File", "dv": dv}
        elif ftype == "paydata":
            dv = int(value) if value and value.isdigit() else dv_default
            floor = {"floor": floor_num, "type": "paydata", "name": "Paydata Cache", "dv": dv}
            floor["paydata"] = generate_paydata_entry(arch.db.difficulty, floor_num)
        elif ftype == "control":
            node_name = value or f"Control Node {floor_num}"
            defense = None
            if value and "|" in value:
                node_name, defense = [v.strip() for v in value.split("|", 1)]
                if not node_name:
                    node_name = f"Control Node {floor_num}"
            floor = {"floor": floor_num, "type": "control", "name": node_name, "dv": dv_default}
            if defense:
                floor["defense"] = defense
        elif ftype == "ice":
            if not value:
                self.caller.msg("For ICE, give names separated by commas.")
                return
            names = [v.strip() for v in value.split(",") if v.strip()]
            if len(names) == 1:
                floor = {"floor": floor_num, "type": "black_ice", "name": names[0], "dv": None}
            else:
                floor = {"floor": floor_num, "type": "black_ice_group", "name": ", ".join(names), "dv": None}
        elif ftype == "demon":
            name = value or "Imp"
            floor = {"floor": floor_num, "type": "demon", "name": name, "dv": None}
        elif ftype == "empty":
            floor = {"floor": floor_num, "type": "empty", "name": "Empty Floor", "dv": None}
        else:
            self.caller.msg("Type must be password, file, paydata, control, ice, demon, or empty.")
            return
        floors[floor_num - 1] = floor
        arch.db.floors = floors
        self.caller.msg(f"|gUpdated {arch.key} floor {floor_num} to {floor['type']}.|n")

    def cmd_autopaydata(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +net/autopaydata <arch>=<on|off>")
            return
        arch_name, toggle = self.args.split("=", 1)
        arch = self._find_architecture(arch_name.strip())
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        toggle = toggle.strip().lower()
        if toggle not in ("on", "off"):
            self.caller.msg("Value must be on or off.")
            return
        arch.db.auto_paydata = toggle == "on"
        self.caller.msg(f"|g{arch.key} auto paydata set to {toggle}.|n")

    def cmd_refresh_paydata(self):
        arches = evennia.search_object(
            "", typeclass="typeclasses.netrunning.NetArchitecture"
        )
        refreshed = 0
        for arch in arches:
            if not getattr(arch.db, "auto_paydata", False):
                continue
            floors = getattr(arch.db, "floors", None) or []
            changed = False
            for idx, floor in enumerate(floors):
                if floor.get("type") in ("file", "paydata"):
                    floor["paydata"] = generate_paydata_entry(
                        getattr(arch.db, "difficulty", None) or "standard",
                        int(floor.get("floor", idx + 1)),
                    )
                    floors[idx] = floor
                    changed = True
            if changed:
                arch.db.floors = floors
                refreshed += 1
        self.caller.msg(f"|gWeekly paydata refreshed across {refreshed} architecture(s).|n")
