"""
NPC Commands - Create and manage NPCs for staff and storytellers.
"""
import re
import random
import json
from datetime import datetime
from evennia import Command, search_object
from evennia.server.models import ServerConfig
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.create import create_object

from world.cyberpunk_constants import ROLES, STATS, ROLE_SKILLS, ROLE_SKILL_NAME_MAP, EQUIPMENT
from world.cyberpunk_sheets.edgerunner import EdgerunnerChargen
from world.inventory.models import Inventory, Weapon, Armor, Gear, Ammunition, AmmoType, CyberwareInstance
from world.cyberware.models import Cyberware
from world.equipment_data import weapons as weapon_data, armors as armor_data, gears as gear_data, ammunition
from world.utils.formatting import header, footer, divider, sheet_header, sheet_section, format_stat
from world.utils.character_utils import get_full_attribute_name, format_skill_display, STAT_MAPPING, SKILL_MAPPING, is_character_approved
from world.utils.difficulty_values import parse_dv
from typeclasses.npcs import NPC, is_npc
from commands.attack_commands import (
    _get_dodge_dv,
    _set_last_dodge_dv,
    _get_and_clear_pending_attacks,
    _clear_last_dodge_dv,
    execute_attack_roll,
    _resolve_pending_autofire,
    _get_armor_ev_penalty,
)

from commands.CmdPose import PoseBreakMixin
from utils.text import process_special_characters


def _is_staff(caller):
    return caller.check_permstring("builders") or caller.check_permstring("wizards")


def _is_storyteller(caller):
    return caller.check_permstring("storyteller")


def _can_manage_npc(caller, npc):
    """True if caller can manage this NPC (owner or staff)."""
    if _is_staff(caller):
        return True
    acc = getattr(caller, 'account', None)
    if not acc:
        return False
    return npc.db.owner_account_id == acc.id


def _search_npc(caller, name):
    """Search for NPC by name. Returns NPC or None. Uses closest match (e.g. 'john' matches 'John Doe')."""
    if not name or not name.strip():
        return None
    search = name.strip().lower()
    all_npcs = _get_owner_npcs(caller)
    if not all_npcs:
        caller.msg(f"No NPC named '{name}' found.")
        return None
    exact_key = [n for n in all_npcs if n.key and n.key.lower() == search]
    if len(exact_key) == 1:
        return exact_key[0]
    exact_full = [n for n in all_npcs if getattr(n.db, "full_name", "") and getattr(n.db, "full_name", "").lower() == search]
    if len(exact_full) == 1:
        return exact_full[0]
    start_key = [n for n in all_npcs if n.key and n.key.lower().startswith(search)]
    if len(start_key) == 1:
        return start_key[0]
    start_full = [n for n in all_npcs if getattr(n.db, "full_name", "") and getattr(n.db, "full_name", "").lower().startswith(search)]
    if len(start_full) == 1:
        return start_full[0]
    contains_key = [n for n in all_npcs if n.key and search in n.key.lower()]
    if len(contains_key) == 1:
        return contains_key[0]
    contains_full = [n for n in all_npcs if getattr(n.db, "full_name", "") and search in getattr(n.db, "full_name", "").lower()]
    if len(contains_full) == 1:
        return contains_full[0]
    multi = start_key or start_full or contains_key or contains_full
    if len(multi) > 1:
        caller.msg(f"Multiple NPCs match '{name}': {', '.join(n.key for n in multi[:5])}. Be more specific.")
        return None
    caller.msg(f"No NPC named '{name}' found.")
    return None


def _get_owner_npcs(caller):
    """Get all NPCs owned by caller (or all if staff)."""
    from evennia.objects.models import ObjectDB
    all_npcs = list(ObjectDB.objects.filter(db_typeclass_path="typeclasses.npcs.NPC"))
    if _is_staff(caller):
        return all_npcs
    acc = getattr(caller, 'account', None)
    if not acc:
        return []
    return [n for n in all_npcs if getattr(n.db, 'owner_account_id', None) == acc.id]


NPC_LOG_KEY = "npc_neutralized_log"


def _log_neutralized_npc(npc, destroyed_by, reason=None):
    """Append a neutralized NPC to the log. Call before deleting the NPC."""
    try:
        data = ServerConfig.objects.conf(key=NPC_LOG_KEY, default="[]")
        if isinstance(data, str):
            entries = json.loads(data)
        else:
            entries = list(data)
    except (json.JSONDecodeError, TypeError):
        entries = []
    inv, _ = Inventory.get_or_create_for_character(npc)
    weapons = [w.name for w in inv.weapons.all()]
    cyber = [c.cyberware.name for c in inv.cyberware.filter(installed=True)]
    entry = {
        "name": npc.key,
        "full_name": getattr(npc.db, "full_name", "") or npc.key,
        "npc_type": getattr(npc.db, "npc_type", "minor"),
        "role": getattr(npc.db, "role", ""),
        "destroyed_at": datetime.now().isoformat(),
        "destroyed_by": getattr(destroyed_by, "key", str(destroyed_by)),
        "reason": (reason or "").strip() or None,
        "stats": {s: npc.get_attribute(s) for s in STATS},
        "skills": dict(npc.db.skills or {}),
        "weapons": weapons,
        "cyberware": cyber,
        "notes": dict(npc.db.notes or {}),
    }
    entries.append(entry)
    ServerConfig.objects.conf(key=NPC_LOG_KEY, value=json.dumps(entries))


def _get_neutralized_log():
    """Return list of neutralized NPC log entries (newest last)."""
    try:
        data = ServerConfig.objects.conf(key=NPC_LOG_KEY, default="[]")
        if isinstance(data, str):
            return json.loads(data)
        return list(data or [])
    except (json.JSONDecodeError, TypeError):
        return []


class CmdNpc(MuxCommand):
    """
    Create and manage NPCs (Non-Player Characters).

    Usage:
      +npc                           - List your NPCs
      +npc <name>                    - View NPC sheet and data
      +npc/create name=<major|minor>/<role> - Create an NPC (name must be unique)
      +npc/type <name>=<major|minor>
      +npc/set <name>/<stat or skill>=<value>
      +npc/chargen <name>=<role>
      +npc/inventory add/<name>=<item>
      +npc/inventory remove/<name>=<item>
      +npc/cyber add/<name>=<cyberware>
      +npc/cyber remove/<name>=<cyberware>
      +npc/equip <name>=<item>
      +npc/improve <name>=<skill>
      +npc/lang <name>=<language>
      +npc/desc <name>=<text>
      +npc/note new/<name>=<note>
      +npc/note <name>               - List notes
      +npc/note <name>/<number>      - Show a note
      +npc/note delete/<name>=<number>
      +npc/note edit/<name>=<number>/<text>
      +npc/note append/<name>=<number>/<text>
      +npc/attack <name> vs <DV>
      +npc/pose <name>=<text>
      +npc/emit <name>=<text>
      +npc/say <name>=<text>
      +npc/roll <name>=<roll syntax>
      +npc/heal <name>=<amount>/<reason>  - Heal NPC by amount
      +npc/damage <name>=<amount>/<reason> - Damage NPC; minor NPCs at 0 HP are neutralized
      +npc/clear <name>              - Remove a minor NPC from the scene
      +npc/destroy <name>[=reason]   - Neutralize NPC (optional reason for log)
      +npc/dodge <name>              - Roll dodge for NPC when they are being attacked
      +npc/log [major|minor] [<name>] - Staff: list neutralized NPCs (filter by type)
      +npc/log/all [major|minor]     - Staff: list all neutralized NPCs

    Staff can manage any NPC. Players with storyteller permission can create and manage NPCs.
    """

    key = "+npc"
    aliases = ["npc"]
    locks = "cmd:all()"
    help_category = "Storyteller"

    def func(self):
        if not self.switches:
            if not self.args:
                self.cmd_list()
            else:
                self.cmd_view(self.args.strip())
            return

        # Dispatch by switch
        if "create" in self.switches:
            self.cmd_create()
        elif "type" in self.switches:
            self.cmd_type()
        elif "set" in self.switches:
            self.cmd_set()
        elif "chargen" in self.switches:
            self.cmd_chargen()
        elif "inventory" in self.switches:
            self.cmd_inventory()
        elif "cyber" in self.switches:
            self.cmd_cyber()
        elif "equip" in self.switches:
            self.cmd_equip()
        elif "improve" in self.switches:
            self.cmd_improve()
        elif "lang" in self.switches:
            self.cmd_lang()
        elif "desc" in self.switches:
            self.cmd_desc()
        elif "note" in self.switches:
            self.cmd_note()
        elif "attack" in self.switches:
            self.cmd_attack()
        elif "pose" in self.switches:
            self.cmd_pose()
        elif "emit" in self.switches:
            self.cmd_emit()
        elif "say" in self.switches:
            self.cmd_say()
        elif "roll" in self.switches:
            self.cmd_roll()
        elif "heal" in self.switches:
            self.cmd_heal()
        elif "damage" in self.switches:
            self.cmd_damage()
        elif "clear" in self.switches:
            self.cmd_clear()
        elif "destroy" in self.switches:
            self.cmd_destroy()
        elif "log" in self.switches:
            self.cmd_log()
        elif "dodge" in self.switches:
            self.cmd_dodge()
        else:
            self.caller.msg("Unknown +npc switch.")

    def _require_staff_or_storyteller(self):
        if _is_staff(self.caller):
            return True
        if _is_storyteller(self.caller):
            if not is_character_approved(self.caller):
                self.caller.msg("You must be approved by staff before creating or managing NPCs.")
                return False
            return True
        self.caller.msg("You must be staff or a player storyteller to use NPC commands.")
        return False

    def cmd_list(self):
        """List NPCs belonging to caller."""
        if not self._require_staff_or_storyteller():
            return
        npcs = _get_owner_npcs(self.caller)
        out = header("Your NPCs", width=78) + "\n"
        if not npcs:
            out += "No NPCs found.\n"
        else:
            for n in sorted(npcs, key=lambda x: x.key):
                ntype = getattr(n.db, 'npc_type', 'minor')
                role = getattr(n.db, 'role', '') or '-'
                out += f"  |w{n.key}|n ({ntype}) - {role}\n"
        out += footer(width=78)
        self.caller.msg(out)

    def cmd_view(self, name):
        """View NPC sheet."""
        npc = _search_npc(self.caller, name)
        if not npc or not _can_manage_npc(self.caller, npc):
            if npc and not _can_manage_npc(self.caller, npc):
                self.caller.msg("You don't have permission to view that NPC.")
            return
        out = self._format_npc_sheet(npc)
        self.caller.msg(out)

    def _format_stat_cell(self, name, val, width=25):
        """Format one stat cell for 3-column layout."""
        from world.utils.formatting import format_stat
        return format_stat(name, val, default=1, width=width)

    def _format_npc_sheet(self, npc):
        """Format NPC sheet using world.utils.formatting (no EvTable). 3-column layout for stats/skills."""
        from world.utils.formatting import format_stat
        W = 80
        COL_WIDTH = 26
        COLS = 3
        display = getattr(npc.db, 'full_name', None) or npc.key
        ntype = getattr(npc.db, 'npc_type', 'minor')
        role = getattr(npc.db, 'role', '') or '-'
        out = sheet_header(f"{display} ({ntype} NPC)", width=W)
        out += sheet_section("Overview", width=W)
        out += f"|yName:|n {npc.key}\n"
        out += f"|yType:|n {ntype}\n"
        out += f"|yRole:|n {role}\n"
        desc = getattr(npc.db, 'desc', '') or ''
        if desc:
            out += f"|yDescription:|n {desc[:200]}{'...' if len(desc) > 200 else ''}\n"
        out += "\n"

        out += sheet_section("Stats", width=W)
        stat_rows = []
        for i in range(0, len(STATS), COLS):
            row_stats = STATS[i:i + COLS]
            cells = []
            for stat in row_stats:
                val = npc.get_attribute(stat)
                cells.append(self._format_stat_cell(stat.replace('_', ' ').title(), val, COL_WIDTH))
            stat_rows.append(" ".join(cells))
        out += "\n".join(stat_rows) + "\n\n"

        out += sheet_section("Derived", width=W)
        derived = [
            ("Max HP", getattr(npc.db, 'max_hp', 10)),
            ("Current HP", getattr(npc.db, 'current_hp', 10)),
            ("Humanity", getattr(npc.db, 'humanity', 10)),
        ]
        cells = [self._format_stat_cell(name, val, COL_WIDTH) for name, val in derived]
        out += " ".join(cells) + "\n\n"

        skills = npc.db.skills or {}
        improved = npc.db.improved_skills or []
        active = [(k, v) for k, v in sorted(skills.items()) if v > 0]
        if active:
            out += sheet_section("Skills", width=W)
            skill_rows = []
            for i in range(0, len(active), COLS):
                row = active[i:i + COLS]
                cells = []
                for sk, v in row:
                    disp = format_skill_display(sk)
                    imp = " |y(improved)|n" if sk in improved else ""
                    pad = max(0, COL_WIDTH - 2 - len(disp) - 1 - len(str(v)) - (11 if imp else 0))
                    cells.append(f"  {disp}{'.' * pad} {v}{imp}")
                skill_rows.append(" ".join(cells))
            out += "\n".join(skill_rows) + "\n\n"

        lang = npc.get_speaking_language()
        if lang:
            out += sheet_section("Language", width=W)
            out += f"  Speaking: {lang}\n\n"

        inv, _ = Inventory.get_or_create_for_character(npc)
        out += sheet_section("Inventory", width=W)
        weps = list(inv.weapons.all())
        eq_wid = npc.db.equipped_weapon_id
        if weps:
            out += f"  |yWeapons:|n {', '.join(w.name + (' |g(equipped)|n' if w.pk == eq_wid else '') for w in weps)}\n"
        else:
            out += "  |yWeapons:|n None\n"
        armors = list(inv.armor.all())
        out += f"  |yArmor:|n {', '.join(a.name for a in armors) if armors else 'None'}\n"
        gears = list(inv.gear.all())
        out += f"  |yGear:|n {', '.join(g.name for g in gears) if gears else 'None'}\n"
        ammo = list(inv.ammunition.all())
        ammo_strs = [f"{a.name} x{a.quantity}" for a in ammo] if ammo else []
        out += f"  |yAmmunition:|n {', '.join(ammo_strs) if ammo_strs else 'None'}\n"
        out += "\n"

        cyber = list(inv.cyberware.filter(installed=True))
        if cyber:
            out += sheet_section("Cyberware", width=W)
            for c in cyber:
                out += f"  {c.cyberware.name}\n"
            out += "\n"

        notes = npc.db.notes or {}
        if notes:
            out += sheet_section("Notes", width=W)
            for nid, ndat in sorted(notes.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
                txt = ndat.get('text', '')[:50]
                out += f"  #{nid}: {txt}{'...' if len(txt) >= 50 else ''}\n"

        out += footer(width=W)
        return out

    def cmd_create(self):
        """+npc/create <name>=<major|minor>/<role> - e.g. +npc/create "Bruiser"=minor/Solo"""
        if not self._require_staff_or_storyteller():
            return
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/create <name>=<major|minor>/<role>")
            return
        npc_name, type_role = self.args.split("=", 1)
        npc_name = npc_name.strip().strip('"')
        if "/" not in type_role:
            self.caller.msg("Usage: +npc/create <name>=<major|minor>/<role>")
            return
        npc_type, role = type_role.split("/", 1)
        npc_type = npc_type.strip().lower()
        role = role.strip().capitalize()
        if npc_type not in ("major", "minor"):
            self.caller.msg("Type must be 'major' or 'minor'.")
            return
        if role not in ROLES:
            self.caller.msg(f"Role must be one of: {', '.join(ROLES)}")
            return
        npc_name = npc_name.strip()
        if not npc_name:
            self.caller.msg("Provide an NPC name.")
            return
        existing = search_object(npc_name, typeclass="typeclasses.npcs.NPC")
        if existing:
            self.caller.msg(f"An NPC named '{npc_name}' already exists.")
            return
        loc = self.caller.location
        npc = create_object(
            "typeclasses.npcs.NPC",
            key=npc_name,
            location=loc
        )
        npc.db.npc_type = npc_type
        npc.db.role = role
        npc.db.full_name = npc_name
        acc = getattr(self.caller, 'account', None)
        if acc:
            npc.db.owner_account_id = acc.id
        npc.db.owner_character_id = getattr(self.caller, 'id', None)
        EdgerunnerChargen.edgerunner_chargen_for_typeclass(npc, role, npc_name)
        EdgerunnerChargen.spend_remaining_points_for_npc(npc, role)
        npc.db.is_complete = True
        npc.recalculate_derived_stats()
        first_weapon = None
        inv, _ = Inventory.get_or_create_for_character(npc)
        weps = list(inv.weapons.all())
        if weps:
            first_weapon = weps[0]
            npc.set_equipped_weapon(first_weapon)
        self.caller.msg(f"Created {npc_type} NPC '{npc_name}' ({role}).")
        if first_weapon:
            self.caller.msg(f"Equipped {first_weapon.name}.")

    def cmd_type(self):
        """+npc/type <name>=<major|minor>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/type <name>=<major|minor>")
            return
        name, ntype = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            if npc and not _can_manage_npc(self.caller, npc):
                self.caller.msg("You don't have permission to modify that NPC.")
            return
        ntype = ntype.strip().lower()
        if ntype not in ("major", "minor"):
            self.caller.msg("Type must be 'major' or 'minor'.")
            return
        npc.db.npc_type = ntype
        self.caller.msg(f"Set {npc.key} to {ntype} NPC.")

    def cmd_set(self):
        """+npc/set <name>/<stat or skill>=<value>"""
        if not self.args or "/" not in self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/set <name>/<stat or skill>=<value>")
            return
        name_part, rest = self.args.split("/", 1)
        name = name_part.strip()
        if "=" not in rest:
            self.caller.msg("Usage: +npc/set <name>/<stat or skill>=<value>")
            return
        field, value = rest.split("=", 1)
        field = field.strip()
        value = value.strip()
        npc = _search_npc(self.caller, name)
        if not npc or not _can_manage_npc(self.caller, npc):
            if npc and not _can_manage_npc(self.caller, npc):
                self.caller.msg("You don't have permission.")
            return
        if npc.db.npc_type != "major":
            self.caller.msg("+npc/set only works on major NPCs.")
            return
        try:
            val = int(value)
        except ValueError:
            self.caller.msg("Value must be a number.")
            return
        full_name = get_full_attribute_name(field)
        if not full_name:
            self.caller.msg(f"Unknown stat or skill: {field}")
            return
        if full_name in STAT_MAPPING.values():
            npc.set_attribute(full_name, val)
        elif full_name in SKILL_MAPPING.values():
            npc.set_skill(full_name, val)
        else:
            self.caller.msg(f"Unknown stat or skill: {field}")
            return
        npc.recalculate_derived_stats()
        self.caller.msg(f"Set {npc.key}'s {full_name} to {val}.")

    def cmd_chargen(self):
        """+npc/chargen <name>=<role>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/chargen <name>=<role>")
            return
        name, role = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        if npc.db.npc_type != "major":
            self.caller.msg("+npc/chargen only works on major NPCs.")
            return
        role = role.strip().capitalize()
        if role not in ROLES:
            self.caller.msg(f"Role must be one of: {', '.join(ROLES)}")
            return
        EdgerunnerChargen.edgerunner_chargen_for_typeclass(npc, role, npc.key)
        EdgerunnerChargen.spend_remaining_points_for_npc(npc, role)
        npc.db.role = role
        npc.recalculate_derived_stats()
        inv, _ = Inventory.get_or_create_for_character(npc)
        weps = list(inv.weapons.all())
        if weps:
            npc.set_equipped_weapon(weps[0])
        self.caller.msg(f"Regenerated {npc.key} as {role} using Edgerunner chargen.")

    def cmd_inventory(self):
        """+npc/inventory add/<name>=<item> or remove/<name>=<item>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/inventory add/<name>=<item> or +npc/inventory remove/<name>=<item>")
            return
        action_part, item = self.args.split("=", 1)
        item = item.strip()
        action = action_part.split("/")[0].strip().lower()
        if action not in ("add", "remove"):
            self.caller.msg("Use 'add' or 'remove'.")
            return
        name = action_part.split("/", 1)[-1].strip() if "/" in action_part else ""
        if not name:
            self.caller.msg("Usage: +npc/inventory add/<name>=<item>")
            return
        npc = _search_npc(self.caller, name)
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        inv, _ = Inventory.get_or_create_for_character(npc)
        if action == "add":
            for model, attr, name_attr in [
                (Weapon, "weapons", "name"),
                (Armor, "armor", "name"),
                (Gear, "gear", "name"),
            ]:
                try:
                    obj = model.objects.get(**{f"{name_attr}__iexact": item})
                    getattr(inv, attr).add(obj)
                    self.caller.msg(f"Added {obj.name} to {npc.key}'s inventory.")
                    return
                except model.DoesNotExist:
                    pass
            self.caller.msg(f"Item '{item}' not found in weapons, armor, or gear.")
        else:
            for model, attr in [(Weapon, "weapons"), (Armor, "armor"), (Gear, "gear")]:
                try:
                    obj = getattr(inv, attr).get(name__iexact=item)
                    getattr(inv, attr).remove(obj)
                    self.caller.msg(f"Removed {obj.name} from {npc.key}'s inventory.")
                    return
                except model.DoesNotExist:
                    pass
            self.caller.msg(f"'{item}' not found in {npc.key}'s inventory.")

    def cmd_cyber(self):
        """+npc/cyber add/<name>=<cyberware> or remove/<name>=<cyberware>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/cyber add/<name>=<cyberware> or remove/<name>=<cyberware>")
            return
        action_part, cw_name = self.args.split("=", 1)
        cw_name = cw_name.strip()
        action = action_part.split("/")[0].strip().lower()
        if action not in ("add", "remove"):
            self.caller.msg("Use 'add' or 'remove'.")
            return
        name = action_part.split("/", 1)[-1].strip() if "/" in action_part else ""
        if not name:
            self.caller.msg("Usage: +npc/cyber add/<name>=<cyberware>")
            return
        npc = _search_npc(self.caller, name)
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        if action == "add":
            try:
                cw = Cyberware.objects.get(name__iexact=cw_name)
            except Cyberware.DoesNotExist:
                self.caller.msg(f"Cyberware '{cw_name}' not found.")
                return
            inv, _ = Inventory.get_or_create_for_character(npc)
            inst = CyberwareInstance.objects.create(
                cyberware=cw,
                character_object=npc,
                installed=True
            )
            inv.cyberware.add(inst)
            npc.calculate_humanity()
            npc.recalculate_derived_stats()
            self.caller.msg(f"Added {cw.name} to {npc.key}.")
        else:
            inv, _ = Inventory.get_or_create_for_character(npc)
            inst = inv.cyberware.filter(cyberware__name__iexact=cw_name, installed=True).first()
            if not inst:
                self.caller.msg(f"'{cw_name}' not installed on {npc.key}.")
                return
            inst.delete()
            npc.calculate_humanity()
            npc.recalculate_derived_stats()
            self.caller.msg(f"Removed {cw_name} from {npc.key}.")

    def cmd_equip(self):
        """+npc/equip <name>=<item>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/equip <name>=<item>")
            return
        name, item = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        inv, _ = Inventory.get_or_create_for_character(npc)
        try:
            wep = inv.weapons.get(name__iexact=item.strip())
        except Weapon.DoesNotExist:
            self.caller.msg(f"{npc.key} doesn't have that weapon.")
            return
        npc.set_equipped_weapon(wep)
        self.caller.msg(f"{npc.key} equipped {wep.name}.")

    def cmd_improve(self):
        """+npc/improve <name>=<skill>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/improve <name>=<skill>")
            return
        name, skill = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        if npc.db.npc_type != "major":
            self.caller.msg("+npc/improve only works on major NPCs.")
            return
        full = get_full_attribute_name(skill.strip())
        if not full or full not in SKILL_MAPPING.values():
            self.caller.msg(f"Unknown skill: {skill}")
            return
        key = full.lower().replace(' ', '_')
        cur = npc.get_skill(key)
        npc.set_skill(key, cur + 1)
        improved = list(npc.db.improved_skills or [])
        if key not in improved:
            improved.append(key)
        npc.db.improved_skills = improved
        self.caller.msg(f"Improved {npc.key}'s {full} to {cur + 1}.")

    def cmd_lang(self):
        """+npc/lang <name>=<language>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/lang <name>=<language>")
            return
        name, lang = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        lang = lang.strip()
        if not lang or lang.lower() == "none":
            npc.set_speaking_language(None)
            self.caller.msg(f"Cleared {npc.key}'s speaking language.")
            return
        npc.db.languages = npc.db.languages or {}
        npc.db.languages[lang] = 4
        try:
            npc.set_speaking_language(lang)
        except ValueError:
            pass
        self.caller.msg(f"Set {npc.key}'s speaking language to {lang}.")

    def cmd_desc(self):
        """+npc/desc <name>=<text>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/desc <name>=<text>")
            return
        name, text = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        npc.db.desc = text.strip()
        self.caller.msg(f"Set {npc.key}'s description.")

    def cmd_note(self):
        """+npc/note new/delete/edit/append/list"""
        if not self.args:
            self.caller.msg("Usage: +npc/note new/<name>=<note> or +npc/note <name> or +npc/note <name>/<number>")
            return
        parts = self.args.split(None, 1)
        first = parts[0].split("/")[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else parts[0] if parts else ""
        if first == "new":
            if "/" not in rest or "=" not in rest:
                self.caller.msg("Usage: +npc/note new/<name>=<note>")
                return
            name_part, text = rest.split("=", 1)
            name = name_part.split("/")[-1].strip() if "/" in name_part else name_part.strip()
            npc = _search_npc(self.caller, name)
            if not npc or not _can_manage_npc(self.caller, npc):
                return
            notes = npc.db.notes or {}
            used = {int(k) for k in notes if str(k).isdigit()}
            nid = 1
            while nid in used:
                nid += 1
            notes[str(nid)] = {"text": text.strip(), "created_at": datetime.now().isoformat()}
            npc.db.notes = notes
            self.caller.msg(f"Added note #{nid} to {npc.key}.")
            return
        if first == "delete":
            if "=" not in self.args:
                self.caller.msg("Usage: +npc/note delete/<name>=<number>")
                return
            name_part, num = self.args.split("=", 1)
            name = name_part.split("/")[-1].strip()
            npc = _search_npc(self.caller, name)
            if not npc or not _can_manage_npc(self.caller, npc):
                return
            notes = npc.db.notes or {}
            if num.strip() in notes:
                del notes[num.strip()]
                npc.db.notes = notes
                self.caller.msg(f"Deleted note #{num} from {npc.key}.")
            else:
                self.caller.msg(f"Note #{num} not found.")
            return
        if first == "edit":
            if "=" not in self.args or self.args.count("/") < 2:
                self.caller.msg("Usage: +npc/note edit/<name>=<number>/<text>")
                return
            name_part, rest2 = self.args.split("=", 1)
            name = name_part.split("/")[-1].strip()
            if "/" not in rest2:
                self.caller.msg("Usage: +npc/note edit/<name>=<number>/<text>")
                return
            num, text = rest2.split("/", 1)
            npc = _search_npc(self.caller, name)
            if not npc or not _can_manage_npc(self.caller, npc):
                return
            notes = npc.db.notes or {}
            if num.strip() in notes:
                notes[num.strip()]["text"] = text.strip()
                npc.db.notes = notes
                self.caller.msg(f"Updated note #{num}.")
            else:
                self.caller.msg(f"Note #{num} not found.")
            return
        if first == "append":
            if "=" not in self.args or "/" not in rest:
                self.caller.msg("Usage: +npc/note append/<name>=<number>/<text>")
                return
            name_part, rest2 = self.args.split("=", 1)
            name = name_part.split("/")[-1].strip()
            if "/" not in rest2:
                self.caller.msg("Usage: +npc/note append/<name>=<number>/<text>")
                return
            num, text = rest2.split("/", 1)
            npc = _search_npc(self.caller, name)
            if not npc or not _can_manage_npc(self.caller, npc):
                return
            notes = npc.db.notes or {}
            if num.strip() in notes:
                notes[num.strip()]["text"] = (notes[num.strip()].get("text", "") + " " + text.strip()).strip()
                npc.db.notes = notes
                self.caller.msg(f"Appended to note #{num}.")
            else:
                self.caller.msg(f"Note #{num} not found.")
            return
        if "/" in self.args:
            name, num = self.args.split("/", 1)
            npc = _search_npc(self.caller, name.strip())
            if not npc or not _can_manage_npc(self.caller, npc):
                return
            notes = npc.db.notes or {}
            nd = notes.get(num.strip())
            if nd:
                self.caller.msg(f"Note #{num}:\n{nd.get('text', '')}")
            else:
                self.caller.msg(f"Note #{num} not found.")
        else:
            npc = _search_npc(self.caller, self.args.strip())
            if not npc or not _can_manage_npc(self.caller, npc):
                return
            notes = npc.db.notes or {}
            if not notes:
                self.caller.msg(f"No notes on {npc.key}.")
                return
            out = header(f"Notes for {npc.key}", width=78) + "\n"
            for nid, nd in sorted(notes.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
                txt = nd.get("text", "")[:60]
                out += f"  #{nid}: {txt}{'...' if len(nd.get('text', '')) > 60 else ''}\n"
            out += footer(width=78)
            self.caller.msg(out)

    def cmd_attack(self):
        """+npc/attack <name> vs <DV>"""
        if not self.args:
            self.caller.msg("Usage: +npc/attack <name> vs <DV>")
            return
        vs_match = re.search(r'\s+vs\s+', self.args, re.IGNORECASE)
        if not vs_match:
            self.caller.msg("Usage: +npc/attack <name> vs <DV>")
            return
        name = self.args[:vs_match.start()].strip()
        vs_str = self.args[vs_match.end():].strip()
        npc = _search_npc(self.caller, name)
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        wep = npc.get_equipped_weapon()
        if not wep:
            self.caller.msg(f"{npc.key} has no weapon equipped.")
            return
        vs_info = parse_dv(vs_str)
        if vs_info is None:
            self.caller.msg("Invalid DV. Use a number or difficulty name.")
            return
        dv, diff_name, _ = vs_info
        ref = npc.get_attribute("reflexes")
        if "handgun" in wep.name.lower() or "pistol" in wep.name.lower():
            sk = "handgun"
        elif "melee" in wep.name.lower() or "heavy" in wep.name.lower() and "weapon" in wep.name.lower():
            sk = "melee"
        elif "autofire" in (wep.rof or "").lower():
            sk = "autofire"
        elif "shoulder" in wep.name.lower() or "rifle" in wep.name.lower() or "shotgun" in wep.name.lower():
            sk = "shoulder_arms"
        else:
            sk = "handgun"
        skill = npc.get_skill(sk)
        roll = random.randint(1, 10)
        total = ref + skill + roll
        success = total > dv
        loc = npc.location or self.caller.location
        poser_name = getattr(npc.db, 'full_name', None) or npc.key
        out = f"{poser_name} attacks with {wep.name}: {ref} + {format_skill_display(sk)} + {roll} = {total} vs {dv}"
        if diff_name:
            out += f" ({diff_name})"
        out += f" - {'|gSuccess|n' if success else '|rFailure|n'}"
        if loc:
            loc.msg_contents(out, exclude=[self.caller])
        self.caller.msg(out)
        if success:
            try:
                dmg = int(re.search(r'\d+', str(wep.damage)).group())
            except (AttributeError, TypeError):
                dmg = 2
            out2 = f"{poser_name}'s {wep.name} deals {dmg} damage."
            if loc:
                loc.msg_contents(out2, exclude=[self.caller])
            self.caller.msg(out2)

    def cmd_pose(self):
        """+npc/pose <name>=<text>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/pose <name>=<text>")
            return
        name, text = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        loc = self.caller.location
        if not npc.location or npc.location != loc:
            self.caller.msg("NPC must be in your location to pose as them.")
            return
        text = process_special_characters(text.strip())
        if "~" in text:
            if not npc.get_speaking_language():
                self.caller.msg("Set the NPC's language first with +npc/lang.")
                return
        poser_name = getattr(npc.db, 'full_name', None) or npc.key
        if "~" not in text:
            final = f"{poser_name} {text}"
            loc.msg_contents(final)
            return
        lang = npc.get_speaking_language()
        for obj in loc.contents:
            if not getattr(obj, 'has_account', lambda: False)():
                continue
            parts = []
            current = 0
            for m in re.finditer(r'"~([^"]+)"', text):
                parts.append(text[current:m.start()])
                speech = "~" + m.group(1)
                _, msg_u, msg_nu, _ = npc.prepare_say(speech, viewer=obj, language_only=True, skip_english=True)
                understands = obj == npc or (lang and lang in obj.get_languages())
                parts.append(msg_u if understands else msg_nu)
                current = m.end()
            parts.append(text[current:])
            final = poser_name + " " + "".join(parts)
            obj.msg(final)

    def cmd_emit(self):
        """+npc/emit <name>=<text>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/emit <name>=<text>")
            return
        name, text = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        if not npc.location or npc.location != self.caller.location:
            self.caller.msg("NPC must be in your location.")
            return
        text = process_special_characters(text.strip())
        if "~" in text:
            if not npc.get_speaking_language():
                self.caller.msg("Set the NPC's language first with +npc/lang.")
                return
        self.caller.location.msg_contents(text)

    def cmd_say(self):
        """+npc/say <name>=<text>"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/say <name>=<text>")
            return
        name, speech = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        loc = self.caller.location
        if not npc.location or npc.location != loc:
            self.caller.msg("NPC must be in your location.")
            return
        speech = process_special_characters(speech.strip())
        if speech.startswith('"') and speech.endswith('"'):
            speech = speech[1:-1]
        if not speech.startswith('~') and npc.get_speaking_language():
            speech = '~' + speech
        for obj in loc.contents:
            if not getattr(obj, 'has_account', lambda: False)():
                continue
            _, msg_understand, msg_not_understand, lang = npc.prepare_say(speech, viewer=obj)
            understands = obj == npc or not lang or (lang in obj.get_languages())
            msg = msg_understand if understands else msg_not_understand
            obj.msg(msg)

    def _parse_roll_modifier(self, s):
        """Extract trailing modifier (+1, -3) from string. Returns (stripped_string, modifier)."""
        mod_match = re.search(r'\s*([+-])\s*(\d+)\s*$', s)
        if mod_match:
            sign, num = mod_match.group(1), int(mod_match.group(2))
            mod = num if sign == '+' else -num
            return s[:mod_match.start()].strip(), mod
        return s.strip(), 0

    def cmd_roll(self):
        """+npc/roll <name>=<attribute> + <skill> [<+/- modifier>] [vs <DV>]"""
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +npc/roll <name>=<attribute> + <skill> [<+/- modifier>] [vs <DV>]")
            return
        name, rest = self.args.split("=", 1)
        npc = _search_npc(self.caller, name.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        rest = rest.strip()
        vs_info = None
        vs_m = re.search(r'\s+vs\s+', rest, re.IGNORECASE)
        if vs_m:
            vs_str = rest[vs_m.end():].strip()
            rest = rest[:vs_m.start()].strip()
            vs_info = parse_dv(vs_str)
        if " + " not in rest:
            self.caller.msg("Usage: +npc/roll <name>=<attribute> + <skill> [<+/- modifier>] [vs <DV>]")
            return
        attr_in, skill_in = rest.split(" + ", 1)
        skill_in, modifier = self._parse_roll_modifier(skill_in)
        full_attr = get_full_attribute_name(attr_in.strip())
        full_skill = get_full_attribute_name(skill_in.strip())
        if not full_attr or full_attr not in STAT_MAPPING.values():
            self.caller.msg(f"Invalid attribute.")
            return
        if not full_skill or full_skill not in SKILL_MAPPING.values():
            self.caller.msg(f"Invalid skill.")
            return
        attr_val = npc.get_attribute(full_attr)
        skill_val = npc.get_skill(full_skill)

        from world.utils.roll_utils import roll_skill_check, check_success, format_roll_details

        total, details = roll_skill_check(attr_val, skill_val, modifier=modifier)
        breakdown = format_roll_details(details, attr_val, skill_val, modifier)
        poser_name = getattr(npc.db, 'full_name', None) or npc.key
        out = f"{poser_name} rolls {format_skill_display(full_attr)} + {format_skill_display(full_skill)} + 1d10: {breakdown} = |w{total}|n"
        if details.get("is_crit_success"):
            out += " |g(Critical Success!)|n"
        elif details.get("is_crit_failure"):
            out += " |r(Critical Failure!)|n"
        if vs_info:
            dv, diff_name, _ = vs_info
            success = check_success(total, dv)
            out += f" vs {dv}"
            if diff_name:
                out += f" ({diff_name})"
            out += f" - {'|gSuccess|n' if success else '|rFailure|n'}"
        loc = npc.location or self.caller.location
        if loc:
            loc.msg_contents(out, exclude=[self.caller])
        self.caller.msg(out)

    def cmd_heal(self):
        """+npc/heal <name>=<amount>/<reason> - Heal NPC by amount."""
        if not self.args or "=" not in self.args or "/" not in self.args:
            self.caller.msg("Usage: +npc/heal <name>=<amount>/<reason>")
            return
        name_part, rest = self.args.split("=", 1)
        if "/" not in rest:
            self.caller.msg("Usage: +npc/heal <name>=<amount>/<reason>")
            return
        amount_str, reason = rest.split("/", 1)
        amount_str = amount_str.strip()
        reason = reason.strip()
        try:
            amount = int(amount_str)
        except ValueError:
            self.caller.msg("Amount must be a number.")
            return
        if amount < 1:
            self.caller.msg("Amount must be at least 1.")
            return
        npc = _search_npc(self.caller, name_part.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        max_hp = getattr(npc.db, "max_hp", 10)
        current = getattr(npc.db, "current_hp", max_hp)
        old_hp = current
        new_hp = min(current + amount, max_hp)
        actual = new_hp - old_hp
        npc.db.current_hp = new_hp
        poser_name = getattr(npc.db, "full_name", None) or npc.key
        out = f"{poser_name} is healed for {actual} HP"
        if reason:
            out += f" ({reason})"
        out += f". HP: {old_hp} -> {new_hp}/{max_hp}"
        loc = npc.location or self.caller.location
        if loc:
            loc.msg_contents(out, exclude=[self.caller])
        self.caller.msg(out)

    def cmd_damage(self):
        """+npc/damage <name>=<amount>/<reason> - Damage NPC. Minor NPCs at 0 HP are neutralized with reason."""
        if not self.args or "=" not in self.args or "/" not in self.args:
            self.caller.msg("Usage: +npc/damage <name>=<amount>/<reason>")
            return
        name_part, rest = self.args.split("=", 1)
        if "/" not in rest:
            self.caller.msg("Usage: +npc/damage <name>=<amount>/<reason>")
            return
        amount_str, reason = rest.split("/", 1)
        amount_str = amount_str.strip()
        reason = reason.strip()
        try:
            amount = int(amount_str)
        except ValueError:
            self.caller.msg("Amount must be a number.")
            return
        if amount < 1:
            self.caller.msg("Amount must be at least 1.")
            return
        npc = _search_npc(self.caller, name_part.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        max_hp = getattr(npc.db, "max_hp", 10)
        current = getattr(npc.db, "current_hp", max_hp)
        old_hp = current
        new_hp = max(0, current - amount)
        actual = old_hp - new_hp
        npc.db.current_hp = new_hp
        poser_name = getattr(npc.db, "full_name", None) or npc.key
        loc = npc.location or self.caller.location

        # Minor NPC at 0 or below HP: neutralize and log with damage reason
        if new_hp <= 0 and getattr(npc.db, "npc_type", "minor") == "minor":
            _log_neutralized_npc(npc, self.caller, reason=reason)
            name = npc.key
            npc.delete()
            out = f"{poser_name} takes {actual} damage"
            if reason:
                out += f" ({reason})"
            out += f". Neutralized (was at {old_hp} HP)."
            if loc:
                loc.msg_contents(out, exclude=[self.caller])
            self.caller.msg(out)
            self.caller.msg(f"Logged to +npc/log with reason: {reason or '(none)'}")
            return

        out = f"{poser_name} takes {actual} damage"
        if reason:
            out += f" ({reason})"
        out += f". HP: {old_hp} -> {new_hp}/{max_hp}"
        if loc:
            loc.msg_contents(out, exclude=[self.caller])
        self.caller.msg(out)

    def cmd_clear(self):
        """+npc/clear <name> - Remove a minor NPC from the scene."""
        if not self.args:
            self.caller.msg("Usage: +npc/clear <name>")
            return
        npc = _search_npc(self.caller, self.args.strip())
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        if npc.db.npc_type != "minor":
            self.caller.msg("+npc/clear only works on minor NPCs.")
            return
        name = npc.key
        npc.delete()
        self.caller.msg(f"Cleared minor NPC '{name}' from the scene.")

    def cmd_destroy(self):
        """+npc/destroy <name>[=reason] - Neutralize and remove NPC (logs to +npc/log)."""
        if not self.args:
            self.caller.msg("Usage: +npc/destroy <name>[=reason]")
            return
        parts = self.args.strip().split("=", 1)
        name_part = parts[0].strip()
        reason = parts[1].strip() if len(parts) > 1 else None
        npc = _search_npc(self.caller, name_part)
        if not npc or not _can_manage_npc(self.caller, npc):
            return
        name = npc.key
        _log_neutralized_npc(npc, self.caller, reason=reason)
        npc.delete()
        self.caller.msg(f"Neutralized and removed NPC '{name}'. Logged to +npc/log.")

    def cmd_log(self):
        """+npc/log [major|minor] [<name>] - Staff: list neutralized NPCs. Use major/minor to filter by type."""
        if not _is_staff(self.caller):
            self.caller.msg("Only staff can view the NPC log.")
            return
        entries = _get_neutralized_log()
        if not entries:
            self.caller.msg("No neutralized NPCs in the log.")
            return
        # Filter by type if major or minor switch
        if "major" in self.switches:
            entries = [e for e in entries if e.get("npc_type", "").lower() == "major"]
            type_label = " (Major only)"
        elif "minor" in self.switches:
            entries = [e for e in entries if e.get("npc_type", "").lower() == "minor"]
            type_label = " (Minor only)"
        else:
            type_label = ""
        if not entries:
            self.caller.msg("No neutralized NPCs in the log" + (" for that type" if type_label else "") + ".")
            return
        show_all = "all" in self.switches
        if self.args and self.args.strip() and not show_all:
            name = self.args.strip()
            matches = [e for e in entries if e.get("name", "").lower() == name.lower()]
            if not matches:
                matches = [e for e in entries if name.lower() in (e.get("name", "") or "").lower()]
            if not matches:
                self.caller.msg(f"No log entry found for '{name}'.")
                return
            entry = matches[-1]
            out = header(f"Neutralized NPC: {entry.get('name', '?')}", width=78) + "\n"
            out += f"|yName:|n {entry.get('full_name', entry.get('name', '?'))}\n"
            out += f"|yType:|n {entry.get('npc_type', '?')}\n"
            out += f"|yRole:|n {entry.get('role', '') or '-'}\n"
            out += f"|yDestroyed:|n {entry.get('destroyed_at', '?')}\n"
            out += f"|yBy:|n {entry.get('destroyed_by', '?')}\n"
            reason = entry.get("reason")
            if reason:
                out += f"|yReason:|n {reason}\n"
            stats = entry.get("stats", {})
            if stats:
                out += f"\n|yStats:|n " + ", ".join(f"{k}:{v}" for k, v in sorted(stats.items())[:5]) + "\n"
            skills = entry.get("skills", {})
            active_skills = {k: v for k, v in skills.items() if v > 0}
            if active_skills:
                out += f"|ySkills:|n " + ", ".join(f"{format_skill_display(k)}:{v}" for k, v in sorted(active_skills.items())[:8]) + "\n"
            weps = entry.get("weapons", [])
            if weps:
                out += f"|yWeapons:|n {', '.join(weps)}\n"
            cyber = entry.get("cyberware", [])
            if cyber:
                out += f"|yCyberware:|n {', '.join(cyber)}\n"
            notes = entry.get("notes", {})
            if notes:
                out += f"\n|yNotes:|n {len(notes)} note(s)\n"
            out += footer(width=78)
            self.caller.msg(out)
        else:
            to_show = entries if show_all else entries[-50:]
            out = header("Neutralized NPC Log" + type_label + (" (All)" if show_all else ""), width=78) + "\n"
            for e in reversed(to_show):
                name = e.get("name", "?")
                ntype = e.get("npc_type", "?")
                role = e.get("role", "") or "-"
                when = e.get("destroyed_at", "")[:19] if e.get("destroyed_at") else "?"
                by = e.get("destroyed_by", "?")
                reason = e.get("reason") or ""
                reason_str = f" | {reason[:50]}{'...' if len(reason) > 50 else ''}" if reason else ""
                out += f"  |w{name}|n ({ntype}) {role} | {when} | by {by}{reason_str}\n"
            out += footer(width=78)
            out += "\nUse +npc/log <name> to view details."
            self.caller.msg(out)

    def cmd_dodge(self):
        """+npc/dodge <name> - Roll dodge for an NPC you own. Used when the NPC is being attacked."""
        if not self.args or not self.args.strip():
            self.caller.msg("Usage: +npc/dodge <name>")
            return
        npc = _search_npc(self.caller, self.args.strip())
        if not npc:
            return
        if not _can_manage_npc(self.caller, npc):
            self.caller.msg(f"You cannot roll dodge for {npc.key}.")
            return
        # Roll dodge
        d10, dex, evasion, total = _get_dodge_dv(npc)
        _set_last_dodge_dv(npc, total)
        # Broadcast
        loc = self.caller.location
        if npc.location:
            loc = npc.location
        ev_penalty = _get_armor_ev_penalty(npc)
        roll_str = f"1d10 [{d10}] + Dexterity + Evasion"
        if ev_penalty:
            roll_str += f" - {ev_penalty} (armor EV)"
        roll_str += f" = {total}"
        msg_lines = [
            f"|w{npc.key}|n dodges!",
            f"  Roll: {roll_str} (DV for attacks)",
        ]
        output = "\n".join(msg_lines)
        loc.msg_contents(output)
        # Check for pending autofire first
        if _resolve_pending_autofire(npc, total):
            return
        # Check for pending attacks and auto-execute each
        pending = _get_and_clear_pending_attacks(npc)
        if pending:
            _clear_last_dodge_dv(npc)
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
                execute_attack_roll(attacker, npc, total, f"{npc.key}'s dodge", npc.location,
                                   aim_location=aim_loc, **kwargs)
