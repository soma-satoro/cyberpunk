"""
Cyberpunk RED netrunning command.
"""

import random

import evennia
from evennia.commands.default.muxcommand import MuxCommand

from world.cyberpunk.netrunning import (
    ALL_PROGRAMS,
    BLACK_ICE,
    DIFFICULTY_DV,
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
        +net/zap
        +net/attack <program>
        +net/slide

    Staff/Storyteller usage:
        +net/create <name>=<difficulty>[,<floors>]
        +net/generate <arch>=<difficulty>[,<floors>]
        +net/show <arch>
        +net/setfloor <arch>=<floor>/<type>[/<value>]
        +net/autopaydata <arch>=<on|off>
        +net/refreshpaydata
    """

    key = "+net"
    aliases = ["net", "netrun", "+netrun"]
    locks = "cmd:all()"
    help_category = "Cyberpunk RED"

    STAFF_SWITCHES = {"create", "generate", "setfloor", "autopaydata", "refreshpaydata"}

    def func(self):
        if not self.switches:
            self.cmd_status()
            return

        switch = self.switches[0].lower()
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
            "create": self.cmd_create_architecture,
            "generate": self.cmd_generate_architecture,
            "show": self.cmd_show_architecture,
            "setfloor": self.cmd_setfloor,
            "autopaydata": self.cmd_autopaydata,
            "refreshpaydata": self.cmd_refresh_paydata,
        }
        handler = dispatch.get(switch)
        if not handler:
            self.caller.msg(f"Unknown switch '{switch}'. See help +net.")
            return
        handler()

    # -------------------------------------------------------------------------
    # State helpers
    # -------------------------------------------------------------------------

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
                if obj.db.is_net_architecture:
                    return obj
        global_matches = evennia.search_object(name)
        for obj in global_matches:
            if obj.db.is_net_architecture:
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
        if not arch.db.is_net_architecture:
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
        dealt = self.caller.take_damage(amount)
        self.caller.msg(f"|rBrain burn: {dealt} damage ({reason}).|n")
        if self.caller.get_hp_current() <= 0:
            self.caller.msg("|rYou flatline from neural feedback!|n")
            self._do_jackout(unsafe=True)

    def _get_active_ice_on_floor(self, state, floor_num):
        ice_state = state.get("ice_state", {})
        return ice_state.get(str(floor_num), [])

    def _set_active_ice_on_floor(self, state, floor_num, data):
        ice_state = state.get("ice_state", {})
        ice_state[str(floor_num)] = data
        state["ice_state"] = ice_state

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
            ice = get_black_ice(name)
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
            ice = get_black_ice(ice_instance["name"])
            if not ice:
                continue
            net_total, _, _ = interface_check(self.caller, bonus=speed_bonus)
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

    def _has_netrunning_gear(self):
        inv = self.caller.db.inventory or []
        has_deck = any(item.get("type") == "cyberdeck" for item in inv)
        cyber = self.caller.get_installed_cyberware()
        cyber_names = {normalize_name(c.get("name", "")) for c in cyber}
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
        marker_id = state.get("body_marker_id")
        if marker_id:
            marker = evennia.search_object(f"#{marker_id}")
            if marker:
                marker[0].delete()
        arch = self._current_architecture()
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

    # -------------------------------------------------------------------------
    # Player switches
    # -------------------------------------------------------------------------

    def cmd_scan(self):
        room = self.caller.location
        if not room:
            self.caller.msg("You have no location to scan.")
            return
        arches = [obj for obj in room.contents if obj.db.is_net_architecture]
        if not arches:
            self.caller.msg("No NET access points detected here.")
            return
        lines = ["|cAccess Points in range:|n"]
        for arch in arches:
            lines.append(
                f"  {arch.key} - {arch.db.difficulty.title()} ({len(arch.db.floors or [])} floors)"
            )
        self.caller.msg("\n".join(lines))

    def cmd_jackin(self):
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

        marker = evennia.create_object(
            "typeclasses.netrunning.NetrunBodyMarker",
            key=f"{self.caller.key}'s netrunning body",
            location=self.caller.location,
        )
        marker.db.owner_id = self.caller.id

        state = {
            "active": True,
            "architecture_id": arch.id,
            "entry_location_id": self.caller.location.id if self.caller.location else None,
            "floor": 1,
            "active_programs": {},
            "cleared_passwords": [],
            "controlled_nodes": [],
            "body_marker_id": marker.id,
            "ice_state": {},
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
        actions = net_actions_for_rank(rank)
        active_programs = state.get("active_programs", {})
        self.caller.msg(
            f"|cNetrun Status|n  Arch: |w{arch.key}|n  Interface: {rank}  NET Actions/turn: {actions}"
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
        total, rank, die = interface_check(self.caller, bonus=bonus)
        floors = arch.db.floors or []
        visible = []
        for floor in floors:
            visible.append(floor)
            if floor.get("type") == "password" and int(floor.get("dv", 0)) > total:
                break
            if len(visible) >= total:
                break
        self.caller.msg(f"|cPathfinder|n Interface {rank} + {die} + {bonus} = |w{total}|n")
        for floor in visible:
            self.caller.msg(f"  F{floor['floor']}: {floor['name']} ({floor['type']})")

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
        total, rank, die = interface_check(self.caller, bonus=bonus)
        self.caller.msg(f"|cBackdoor|n Interface {rank} + {die} + {bonus} = {total} vs DV {dv}")
        if total >= dv:
            cleared = state.get("cleared_passwords", [])
            floor_num = int(floor["floor"])
            if floor_num not in cleared:
                cleared.append(floor_num)
            state["cleared_passwords"] = cleared
            self._set_state(state)
            self.caller.msg("|gPassword bypassed.|n")
        else:
            self.caller.msg("|rAccess denied.|n")

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
        total, rank, die = interface_check(self.caller)
        self.caller.msg(f"|cEye-Dee|n Interface {rank} + {die} = {total} vs DV {dv}")
        if total < dv:
            self.caller.msg("|rYou cannot decode this payload yet.|n")
            return
        paydata = floor.get("paydata")
        if paydata:
            self.caller.msg(
                f"|gIdentified:|n {paydata.get('label')}  "
                f"(Estimated value: {paydata.get('value', 0)} eb)"
            )
        else:
            self.caller.msg("|gYou identify a file node. It appears valuable.|n")

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
        total, rank, die = interface_check(self.caller)
        self.caller.msg(f"|cControl|n Interface {rank} + {die} = {total} vs DV {dv}")
        if total >= dv:
            controlled = state.get("controlled_nodes", [])
            fnum = int(floor["floor"])
            if fnum not in controlled:
                controlled.append(fnum)
            state["controlled_nodes"] = controlled
            self._set_state(state)
            self.caller.msg("|gControl node seized. You can now issue remote operations in-scene.|n")
        else:
            self.caller.msg("|rControl node resists your command.|n")

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
        total, rank, die = interface_check(self.caller)
        self.caller.msg(f"|cExfiltrate|n Interface {rank} + {die} = {total} vs DV {dv}")
        if total < dv:
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
        active = (self._get_state().get("active_programs", {}) if self._is_jacked_in() else {})
        lines = ["|cProgram Catalog|n"]
        for key, data in sorted(ALL_PROGRAMS.items(), key=lambda item: item[1]["name"]):
            marker = " |g[ON]|n" if key in active else ""
            lines.append(
                f"  {data['name']}{marker} - {data['class']} "
                f"(ATK {data['atk']} DEF {data['def']} REZ {data['rez']})"
            )
        self.caller.msg("\n".join(lines))

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
        target = floor_ice[0]
        ice = get_black_ice(target["name"])
        atk_total, rank, die = interface_check(self.caller)
        def_total = int(ice["def"]) + random.randint(1, 10)
        self.caller.msg(
            f"|cZap|n Interface {rank}+{die} = {atk_total} vs "
            f"{ice['name']} DEF {ice['def']}+d10 = {def_total}"
        )
        if atk_total < def_total:
            self.caller.msg("|rZap misses.|n")
            return
        dmg = _roll_dice("1d6")
        target["rez"] -= dmg
        self.caller.msg(f"|gHit!|n {ice['name']} takes {dmg} REZ damage.")
        if target["rez"] <= 0:
            target["active"] = False
            self.caller.msg(f"|y{ice['name']} is Derezzed.|n")
        self._set_active_ice_on_floor(state, floor["floor"], floor_ice)
        self._set_state(state)

    def cmd_attack_program(self):
        if not self._require_netrun():
            return
        if not self.args:
            self.caller.msg("Usage: +net/attack <attacker program>")
            return
        arch = self._current_architecture()
        state = self._get_state()
        floor = self._get_floor(arch, state)
        if not floor:
            self.caller.msg("No valid floor.")
            return
        prog = get_program(self.args.strip())
        if not prog:
            self.caller.msg("Unknown program.")
            return
        pkey = normalize_name(prog["name"])
        active = state.get("active_programs", {})
        if pkey not in active:
            self.caller.msg("Activate that program first with +net/activate.")
            return
        if "attacker" not in prog["class"].lower():
            self.caller.msg("That is not an attacker program.")
            return
        floor_ice = [i for i in self._ensure_floor_ice_state(state, floor) if i.get("active")]
        if not floor_ice:
            self.caller.msg("No valid target for that program on this floor.")
            return
        target = floor_ice[0]
        ice = get_black_ice(target["name"])
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
        # Attacker programs auto-deactivate after use.
        del active[pkey]
        state["active_programs"] = active
        self._set_active_ice_on_floor(state, floor["floor"], floor_ice)
        self._set_state(state)

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
        target = floor_ice[0]
        ice = get_black_ice(target["name"])
        runner_total, rank, die = interface_check(self.caller)
        ice_total = int(ice["per"]) + random.randint(1, 10)
        self.caller.msg(
            f"|cSlide|n Interface {rank}+{die} = {runner_total} vs "
            f"{ice['name']} PER {ice['per']}+d10 = {ice_total}"
        )
        if runner_total > ice_total:
            target["active"] = False
            self._set_active_ice_on_floor(state, floor["floor"], floor_ice)
            self._set_state(state)
            self.caller.msg(f"|gYou evade {ice['name']}; it stops pursuit on this floor.|n")
        else:
            self.caller.msg("|rSlide fails; the ICE stays on you.|n")

    # -------------------------------------------------------------------------
    # Staff/Storyteller switches
    # -------------------------------------------------------------------------

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
        lines = [f"|c{arch.key}|n  Difficulty: {arch.db.difficulty.title()}"]
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
        from evennia.objects.models import ObjectDB

        arches = ObjectDB.objects.filter(db_typeclass_path="typeclasses.netrunning.NetArchitecture")
        refreshed = 0
        for arch in arches:
            if not arch.db.auto_paydata:
                continue
            floors = arch.db.floors or []
            changed = False
            for idx, floor in enumerate(floors):
                if floor.get("type") in ("file", "paydata"):
                    floor["paydata"] = generate_paydata_entry(arch.db.difficulty, int(floor.get("floor", idx + 1)))
                    floors[idx] = floor
                    changed = True
            if changed:
                arch.db.floors = floors
                refreshed += 1
        self.caller.msg(f"|gWeekly paydata refreshed across {refreshed} architecture(s).|n")

