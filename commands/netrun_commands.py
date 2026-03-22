"""
Cyberpunk RED netrunning command.

Floor-based NET architectures per the core rulebook. Uses +net/scan, +net/jackin, etc.
"""

import random

import evennia
from evennia.commands.default.muxcommand import MuxCommand

from world.netrunning.red_netrunning import (
    ALL_PROGRAMS,
    DIFFICULTY_DV,
    _format_interface_dice,
    generate_architecture,
    generate_paydata_entry,
    get_black_ice,
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
        +net/move <down|up|floor#>
        +net/pathfinder
        +net/backdoor
        +net/eyedee
        +net/control
        +net/grab
        +net/programs
        +net/activate <program>
        +net/deactivate <program>
        +net/zap [=target]              - target: ICE name or index when multiple
        +net/attack <program> [=target] - target: ICE name or index when multiple
        +net/slide [=target]             - target: ICE name or index when multiple
        +net/buy <program or Black ICE>  - Purchase to inventory (for deck install later)
        +net/craft <program>             - Queue program crafting job (same as +make/program/add)
        +net/deck                        - Same as |wdeck|n (full cyberdeck sheet)
        +net/deck/install <deck>=<item> - Install program, Black ICE, or hardware
        +net/deck/remove <deck>=<item> - Unload to inventory (|wdeck/...|n also works)
        +net/delve                        - Sweep current floor for hidden staff-placed leads (Interface)
        +net/trace [lead id]              - Crack a swept lead (Interface); grants paydata / program / text
        +net/leads                        - Notebook: swept leads on this floor and links

    Staff/Storyteller usage:
        +net/create <name>=<difficulty>[,<floors>]
        +net/generate <arch>=<difficulty>[,<floors>]
        +net/show <arch>
        +net/setfloor <arch>=<floor>/<type>[/<value>]
        +net/autopaydata <arch>=<on|off>
        +net/refreshpaydata
        +net/lead/create|list|destroy|requires|link|paydata|program|text|teaser|priority|notes
            - Floor narrative leads (Builder)
    """

    key = "+net"
    aliases = ["net", "netrun", "+netrun"]
    locks = "cmd:all()"
    help_category = "Netrunning"

    STAFF_SWITCHES = {"create", "generate", "setfloor", "autopaydata", "refreshpaydata"}

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
            "backdoor": self.cmd_backdoor,
            "eyedee": self.cmd_eyedee,
            "control": self.cmd_control,
            "grab": self.cmd_grab,
            "programs": self.cmd_programs,
            "activate": self.cmd_activate,
            "deactivate": self.cmd_deactivate,
            "zap": self.cmd_zap,
            "attack": self.cmd_attack_program,
            "slide": self.cmd_slide,
            "buy": self.cmd_buy_program,
            "craft": self.cmd_craft_program,
            "create": self.cmd_create_architecture,
            "generate": self.cmd_generate_architecture,
            "show": self.cmd_show_architecture,
            "setfloor": self.cmd_setfloor,
            "autopaydata": self.cmd_autopaydata,
            "refreshpaydata": self.cmd_refresh_paydata,
            "delve": self.cmd_delve,
            "trace": self.cmd_trace,
            "leads": self.cmd_leads,
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

    def _get_floor(self, arch, state):
        floors = arch.db.floors or []
        idx = int(state.get("floor", 1)) - 1
        if idx < 0 or idx >= len(floors):
            return None
        return floors[idx]

    def _brain_damage(self, amount, reason):
        self.caller.take_damage(amount)
        self.caller.msg(f"|rBrain burn: {amount} damage ({reason}).|n")
        hp = getattr(self.caller.db, "current_hp", None)
        if hp is not None and hp <= 0:
            self.caller.msg("|rYou flatline from neural feedback!|n")
            self._do_jackout(unsafe=True)

    def _get_active_ice_on_floor(self, state, floor_num):
        ice_state = state.get("ice_state", {})
        return ice_state.get(str(floor_num), [])

    def _set_active_ice_on_floor(self, state, floor_num, data):
        ice_state = state.get("ice_state", {})
        ice_state[str(floor_num)] = data
        state["ice_state"] = ice_state

    def _net_actions_available(self, state):
        """
        Effective NET actions this turn.
        Interface sets baseline, with a minimum of 2 and optional penalties.
        """
        rank = max(1, get_interface_rank(self.caller))
        base_actions = int(net_actions_for_rank(rank))
        penalty = int(state.get("action_penalty", 0) or 0)
        return max(2, base_actions - penalty)

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

            atk_total = int(ice.get("atk", 0)) + random.randint(1, 10)
            def_total = runner_rank + random.randint(1, 10)
            self.caller.msg(
                f"  {ice['name']} attack: {atk_total} vs Interface defense {def_total}"
            )
            if atk_total < def_total:
                self.caller.msg(f"  |g{ice['name']} misses.|n")
                continue

            ice_class = (ice.get("class") or "").lower()
            ice_key = normalize_name(ice.get("name", ""))
            if "anti-program" in ice_class:
                if not active_programs:
                    self.caller.msg(f"  |y{ice['name']} finds no active programs to shred.|n")
                    continue
                target_key = random.choice(list(active_programs.keys()))
                target = active_programs.get(target_key) or {}
                damage = _roll_dice(self._ice_program_damage_dice(ice.get("name")))
                target["rez"] = int(target.get("rez", 0)) - damage
                target_name = target.get("name", target_key.replace("_", " ").title())
                self.caller.msg(f"  |r{ice['name']} hits {target_name} for {damage} REZ.|n")
                if target["rez"] <= 0:
                    del active_programs[target_key]
                    self.caller.msg(f"  |y{target_name} is Derezzed by {ice['name']}.|n")
                else:
                    active_programs[target_key] = target
                continue

            # Anti-personnel and special attacks.
            damage_dice = self._ice_brain_damage_dice(ice.get("name"))
            if damage_dice:
                damage = _roll_dice(damage_dice)
                self._brain_damage(damage, ice["name"])

            if ice_key == "asp" and active_programs:
                target_key = random.choice(list(active_programs.keys()))
                target_name = active_programs[target_key].get("name", target_key.replace("_", " ").title())
                del active_programs[target_key]
                self.caller.msg(f"  |rAsp destroys {target_name}.|n")
            elif ice_key == "wisp":
                state["action_penalty_next"] = max(1, int(state.get("action_penalty_next", 0) or 0))
                self.caller.msg("  |yWisp static will reduce your next turn's NET actions by 1 (minimum 2).|n")
            elif ice_key == "giant":
                self.caller.msg("  |rGiant slams your connection out of the Architecture!|n")
                self._do_jackout(unsafe=True)
                return
            elif ice.get("effect"):
                self.caller.msg(f"  |xEffect: {ice['effect']}|n")

        state["active_programs"] = active_programs

    def _consume_net_action(self, state, label="NET Action"):
        """Spend one NET action; trigger ICE turn when the turn budget is exhausted."""
        if not self._is_jacked_in():
            return
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
        state["action_penalty"] = int(state.pop("action_penalty_next", 0) or 0)
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
        for i, ice_dict in enumerate(floor_ice):
            if normalize_name(ice_dict.get("name", "")) == arg_lower:
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

    def _can_buy_programs_here(self):
        """
        Gate +net/buy to tagged rooms.
        Requires at least one role tag and one stock tag:
          role: netrunner or hacker
          stock: program or deck
        """
        room = getattr(self.caller, "location", None)
        if not room:
            return False
        room_tags = set()

        db_tags = getattr(room.db, "tags", None) or []
        for t in db_tags:
            if not t:
                continue
            room_tags.add(str(t).strip().lower().replace(" ", "_"))

        try:
            if hasattr(room, "tags"):
                for tag in room.tags.get() or []:
                    room_tags.add(str(tag).strip().lower().replace(" ", "_"))
        except Exception:
            pass

        has_role_tag = bool({"netrunner", "hacker"} & room_tags)
        has_stock_tag = bool({"program", "deck"} & room_tags)
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
            generated.append({"name": ice["name"], "rez": ice["rez"], "active": True})
        self._set_active_ice_on_floor(state, floor_num, generated)
        return generated

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
            net_total, _, _, _ = interface_check(self.caller, bonus=speed_bonus)
            ice_total = int(ice["spd"]) + random.randint(1, 10)
            if ice_total > net_total:
                self.caller.msg(
                    f"|r{ice['name']} gets a free hit on encounter! ({ice_total} vs {net_total})|n"
                )
                dmg = 2 if "anti-program" in ice["class"].lower() else _roll_dice("1d6")
                self._brain_damage(dmg, ice["name"])

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
        if floor.get("type") == "password":
            cleared = state.get("cleared_passwords", [])
            if floor_num not in cleared:
                self.caller.msg(f"  |yBlocked by Password DV {floor.get('dv', '?')}|n")
            else:
                self.caller.msg("  |gPassword on this floor is already bypassed.|n")
        if floor.get("type") in ("file", "paydata"):
            paydata = floor.get("paydata")
            if paydata:
                self.caller.msg("  |yData cache detected. Use +net/eyedee or +net/grab.|n")
        if floor.get("type") in ("black_ice", "black_ice_group"):
            active = [i for i in self._ensure_floor_ice_state(state, floor) if i.get("active")]
            if active:
                self.caller.msg("  |rHostile ICE:|n " + ", ".join(f"{i['name']}({i['rez']} REZ)" for i in active))
        if NetFloorLead.objects.filter(architecture_object_id=arch.id, floor_number=floor_num).exists():
            self.caller.msg("  |cConcealed data trails may exist on this floor.|n |w+net/delve|n  |w+net/leads|n")

    def _has_netrunning_gear(self):
        sheet = getattr(self.caller, "character_sheet", None)
        if not sheet:
            return False, ["a character sheet"]
        inv = getattr(sheet, "inventory", None)
        if not inv:
            return False, ["an inventory"]
        has_deck = False
        for gear in inv.gear.all():
            if getattr(gear, "is_cyberdeck", False):
                has_deck = True
                break
        for cw in CyberwareInstance.objects.filter(character_sheet=sheet, installed=True):
            if "cyberdeck" in (cw.cyberware.name or "").lower():
                has_deck = True
                break
        cyber_names = set()
        for cw in CyberwareInstance.objects.filter(character_sheet=sheet, installed=True):
            cyber_names.add(normalize_name(cw.cyberware.name or ""))
        needs = []
        if not has_deck:
            needs.append("a Cyberdeck")
        if "neural_link" not in cyber_names:
            needs.append("Neural Link cyberware")
        if "interface_plugs" not in cyber_names:
            needs.append("Interface Plugs cyberware")
        if needs:
            return False, needs
        return True, []

    def _do_jackout(self, unsafe=False):
        state = self._get_state()
        arch = self._current_architecture()
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

        staff_bypass = check_builder_permission(self.caller)
        interface_rank = get_interface_rank(self.caller)
        if interface_rank <= 0 and not staff_bypass:
            self.caller.msg("You need Interface rank to netrun (staff may bypass).")
            return
        if not staff_bypass:
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

        state = {
            "active": True,
            "architecture_id": arch.id,
            "entry_location_id": room.id if room else None,
            "body_id": body.id,
            "floor": 1,
            "active_programs": {},
            "cleared_passwords": [],
            "controlled_nodes": [],
            "ice_state": {},
            "net_actions_used": 0,
            "action_penalty": 0,
            "action_penalty_next": 0,
        }
        self._set_state(state)

        self.caller.msg(f"|gYou jack into {arch.key}. The world resolves into META geometry.|n")
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
        used = int(state.get("net_actions_used", 0) or 0)
        remaining = max(0, actions - used)
        active_programs = state.get("active_programs", {})
        self.caller.msg(
            f"|cNetrun Status|n  Arch: |w{arch.key}|n  Interface: {rank}  "
            f"NET Actions: {remaining}/{actions} this turn"
        )
        if active_programs:
            self.caller.msg("Active programs: " + ", ".join(active_programs.keys()))
        else:
            self.caller.msg("Active programs: none")
        self._show_current_floor(arch, state)

    def cmd_move(self):
        if not self._require_netrun():
            return
        if not self.args:
            self.caller.msg("Usage: +net/move <down|up|floor#>")
            return
        arch = self._current_architecture()
        state = self._get_state()
        if not arch:
            self.caller.msg("Architecture not found.")
            return
        floors = arch.db.floors or []
        cur = int(state.get("floor", 1))

        current_floor = self._get_floor(arch, state)
        if current_floor and current_floor.get("type") == "password":
            cleared = state.get("cleared_passwords", [])
            if cur not in cleared:
                self.caller.msg("A Password blocks your descent. Use +net/backdoor.")
                return

        arg = self.args.strip().lower()
        if arg == "down":
            new_floor = cur + 1
        elif arg == "up":
            new_floor = cur - 1
        else:
            try:
                new_floor = int(arg)
            except ValueError:
                self.caller.msg("Move target must be down, up, or a floor number.")
                return
        if new_floor < 1 or new_floor > len(floors):
            self.caller.msg("That floor is out of range.")
            return

        state["floor"] = new_floor
        floor = floors[new_floor - 1]
        self._encounter_ice(state, floor)
        self._set_state(state)
        self._show_current_floor(arch, state)

    def cmd_pathfinder(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        bonus = self._interface_bonus(state, "pathfinder")
        total, rank, die, details = interface_check(self.caller, bonus=bonus)
        floors = arch.db.floors or []
        visible = []
        for floor in floors:
            visible.append(floor)
            if floor.get("type") == "password" and int(floor.get("dv", 0)) > total:
                break
            if len(visible) >= total:
                break
        dice_str = _format_interface_dice(details, bonus)
        self.caller.msg(f"|cPathfinder|n Interface {rank} + {dice_str} = |w{total}|n")
        for floor in visible:
            self.caller.msg(f"  F{floor['floor']}: {floor.get('name', '?')} ({floor.get('type')})")
        self._consume_net_action(state, "Pathfinder")

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
        else:
            self.caller.msg("|rAccess denied.|n")
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
        dv = int(floor.get("dv", DIFFICULTY_DV.get(arch.db.difficulty, 8)))
        total, rank, die, details = interface_check(self.caller)
        dice_str = _format_interface_dice(details, 0)
        self.caller.msg(f"|cControl|n Interface {rank} + {dice_str} = {total} vs DV {dv}")
        if total > dv:
            controlled = state.get("controlled_nodes", [])
            fnum = int(floor["floor"])
            if fnum not in controlled:
                controlled.append(fnum)
            state["controlled_nodes"] = controlled
            self._set_state(state)
            self.caller.msg("|gControl node seized. You can now issue remote operations in-scene.|n")
        else:
            self.caller.msg("|rControl node resists your command.|n")
        self._consume_net_action(state, "Control")

    def cmd_grab(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
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

    def cmd_programs(self):
        subs = [s.lower() for s in (self.switches or [])[1:]]
        if "shop" in subs:
            return self._show_program_shop()
        active = (self._get_state().get("active_programs", {}) if self._is_jacked_in() else {})
        lines = ["|cProgram Catalog|n"]
        for key, data in sorted(ALL_PROGRAMS.items(), key=lambda item: item[1]["name"]):
            marker = " |g[ON]|n" if key in active else ""
            lines.append(
                f"  {data['name']}{marker} - {data['class']} "
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
        if not self._can_buy_programs_here():
            self.caller.msg(
                "You need to be in a tagged netrunner vendor room to buy programs "
                "(requires room tags like netrunner/hacker and program/deck)."
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
        active = state.get("active_programs", {})
        key = normalize_name(prog["name"])
        if key in active:
            self.caller.msg(f"{prog['name']} is already active.")
            return
        active[key] = {"name": prog["name"], "rez": prog["rez"]}
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
        if not floor_ice:
            self.caller.msg("No ICE target on this floor.")
            return
        if len(floor_ice) > 1 and not self.args:
            self.caller.msg(
                f"Multiple ICE on this floor. Specify target: +net/zap <name or #>  "
                f"(e.g. {', '.join(f['name'] for f in floor_ice)})"
            )
            return
        target_arg = (self.args or "").strip().lstrip("=").strip()
        target, _ = self._pick_ice_target(floor_ice, target_arg)
        if not target:
            self.caller.msg("ICE target not found. Use a name or 1-based index.")
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
        pkey = normalize_name(prog["name"])
        active = state.get("active_programs", {})
        if pkey not in active:
            self.caller.msg("Activate that program first with +net/activate.")
            return
        if "attacker" not in prog["class"].lower():
            self.caller.msg("That is not an attacker program.")
            return
        arch = self._current_architecture()
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("No valid floor.")
            return
        floor_ice = [i for i in self._ensure_floor_ice_state(state, floor) if i.get("active")]
        if not floor_ice:
            self.caller.msg("No valid target for that program on this floor.")
            return
        if len(floor_ice) > 1 and not target_arg:
            self.caller.msg(
                f"Multiple ICE on this floor. Specify target: +net/attack {prog['name']}=<name or #>  "
                f"(e.g. {', '.join(f['name'] for f in floor_ice)})"
            )
            return
        target, idx = self._pick_ice_target(floor_ice, target_arg)
        if not target:
            self.caller.msg("ICE target not found. Use a name or 1-based index.")
            return
        ice = get_black_ice(normalize_name(target["name"]))
        atk_total = get_interface_rank(self.caller) + int(prog["atk"]) + random.randint(1, 10)
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
                self.caller.msg(f"|y{ice['name']} is Derezzed.|n")
        else:
            self.caller.msg("|rProgram attack misses.|n")
        # Attacker programs remain active until manually deactivated.
        state["active_programs"] = active
        self._set_active_ice_on_floor(state, floor["floor"], floor_ice)
        self._set_state(state)
        self._consume_net_action(state, f"{prog['name']} attack")

    def cmd_slide(self):
        if not self._require_netrun():
            return
        arch = self._current_architecture()
        state = self._get_state()
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("No valid floor.")
            return
        floor_ice = [i for i in self._ensure_floor_ice_state(state, floor) if i.get("active")]
        if not floor_ice:
            self.caller.msg("No ICE is currently engaging you on this floor.")
            return
        if len(floor_ice) > 1 and not self.args:
            self.caller.msg(
                f"Multiple ICE on this floor. Specify target: +net/slide <name or #>  "
                f"(e.g. {', '.join(f['name'] for f in floor_ice)})"
            )
            return
        target_arg = (self.args or "").strip().lstrip("=").strip()
        target, _ = self._pick_ice_target(floor_ice, target_arg)
        if not target:
            self.caller.msg("ICE target not found. Use a name or 1-based index.")
            return
        ice = get_black_ice(normalize_name(target["name"]))
        runner_total, rank, die, details = interface_check(self.caller)
        ice_total = int(ice["per"]) + random.randint(1, 10)
        dice_str = _format_interface_dice(details, 0)
        self.caller.msg(
            f"|cSlide|n Interface {rank}+{dice_str} = {runner_total} vs "
            f"{ice['name']} PER {ice['per']}+d10 = {ice_total}"
        )
        if runner_total > ice_total:
            target["active"] = False
            self._set_active_ice_on_floor(state, floor["floor"], floor_ice)
            self._set_state(state)
            self.caller.msg(f"|gYou evade {ice['name']}; it stops pursuit on this floor.|n")
        else:
            self.caller.msg("|rSlide fails; the ICE stays on you.|n")
        self._consume_net_action(state, "Slide")

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

    def _net_lead_create(self):
        raw = (self.args or "").strip()
        if "=" not in raw:
            self.caller.msg(
                "Usage: +net/lead/create <architecture>=<floor>/<slug>/<type>/<scan>/<inv>/<label>[|<extra>]"
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
        extra = ""
        if "|" in rhs:
            rhs, extra = rhs.rsplit("|", 1)
            extra = extra.strip()
        parts = rhs.split("/")
        if len(parts) < 6:
            self.caller.msg("Need |wfloor/slug/type/scan_dv/investigate_dv/label|n")
            return
        floor_s, slug, ltype, scan_s, inv_s = parts[:5]
        label = "/".join(parts[5:])
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
        if ltype not in ("paydata", "program", "narrative", "flavor"):
            self.caller.msg("Type must be paydata, program, narrative, or flavor.")
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
                    self.caller.msg("For paydata, extra after | must be a number (eb).")
                    return
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
        if not self.args or not str(self.args).strip().isdigit():
            self.caller.msg("Usage: +net/lead/destroy <lead id>")
            return
        pk = int(str(self.args).strip())
        lead = NetFloorLead.objects.filter(pk=pk).first()
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
        try:
            child_id = int(left.strip())
            parent_id = int(right.strip())
        except ValueError:
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
        try:
            a_id = int(left.strip())
            b_id = int(right.strip())
        except ValueError:
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
        try:
            lead_id = int(left.strip())
        except ValueError:
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
        try:
            lead_id = int(left.strip())
        except ValueError:
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
        try:
            lead_id = int(left.strip())
        except ValueError:
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
        try:
            lead_id = int(left.strip())
        except ValueError:
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
        try:
            lead_id = int(left.strip())
            pri = int(right.strip())
        except ValueError:
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
        try:
            lead_id = int(left.strip())
        except ValueError:
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
        arch.db.floors = generate_architecture(difficulty, floor_count=floors)
        self.caller.msg(
            f"|gCreated architecture {arch.key}|n "
            f"({difficulty}, {len(arch.db.floors or [])} floors)."
        )

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
        arch.db.floors = generate_architecture(difficulty, floor_count=floors)
        self.caller.msg(f"|gRegenerated {arch.key}|n: {difficulty}, {len(arch.db.floors or [])} floors.")

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
        for floor in arch.db.floors or []:
            line = f"  F{floor['floor']:>2}: {floor.get('name', '?')} ({floor.get('type', '?')})"
            if floor.get("dv") is not None:
                line += f" DV {floor['dv']}"
            if floor.get("paydata"):
                line += f" |y[Paydata {floor['paydata'].get('value', 0)}eb]|n"
            lines.append(line)
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
            floor = {"floor": floor_num, "type": "control", "name": node_name, "dv": dv_default}
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
