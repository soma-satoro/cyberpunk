# -*- coding: utf-8 -*-
"""
Voucher commands - manage IC objects represented by vouchers.
Based on Shadowrun Denver voucher system.
"""
import re
from evennia import create_object
from evennia.commands.default.muxcommand import MuxCommand
from typeclasses.vouchers import Voucher

VOUCHER_TYPECLASS = "typeclasses.vouchers.Voucher"
ALIAS_RE = re.compile(r'^[a-zA-Z0-9_-]+$')


def find_voucher(caller, arg, location=None, quiet=False):
    """Find voucher by name, dbref, or alias. Searches caller's inventory, then room.

    Args:
        caller: Object performing the search
        arg: Name, dbref, or alias to search for
        location: Optional location to search in; if None, searches caller and caller.location
        quiet: If True, suppress "Could not find" message when falling back to global search
               (useful when arg might be a character name, e.g. sheet <name>)
    """
    def search_in(container):
        if not container:
            return None
        if arg.startswith("#"):
            try:
                dbref = int(arg[1:])
                for obj in container.contents:
                    if obj.id == dbref and obj.is_typeclass(VOUCHER_TYPECLASS):
                        return obj
            except ValueError:
                pass
        arg_lower = arg.lower()
        for obj in container.contents:
            if not obj.is_typeclass(VOUCHER_TYPECLASS):
                continue
            alias = getattr(obj.db, 'voucher_alias', '') or ''
            if alias.lower() == arg_lower:
                return obj
            if obj.key and obj.key.lower() == arg_lower:
                return obj
        return None

    loc = location
    if loc is None:
        v = search_in(caller)
        if v:
            return v
        if caller and caller.location and caller.location != caller:
            v = search_in(caller.location)
            if v:
                return v
        return caller.search(arg, typeclass=VOUCHER_TYPECLASS, quiet=quiet) if caller else None
    return search_in(loc) or (caller.search(arg, location=loc, typeclass=VOUCHER_TYPECLASS, quiet=quiet) if caller else None)


class CmdVoucher(MuxCommand):
    """
    Manage vouchers (IC objects).

    Usage:
      +voucher/info <voucher>           - Show voucher contents
      +voucher/info <voucher>/<item#>   - Detailed info for item
      +voucher/alias <voucher>=<alias>  - Set alias (max 20 chars)
      +voucher/lock <voucher>           - Lock (only you can pick up/change)
      +voucher/unlock <voucher>         - Unlock
      +voucher/loc <voucher>/<item#>=<location>  - Set IC location
      +voucher/use <voucher>/<item#>[:<qty>]      - Use/remove items
      +voucher/chown <voucher>=<player> - Set IC owner
      +voucher/rename <voucher>=<name>  - Rename (max 38 chars)
      +voucher/nuke <voucher>           - Destroy empty voucher
      +voucher/move <voucher>/<item#>=<newvoucher> - Move items
      +voucher/join <voucher1>=<voucher2> - Merge voucher2 into voucher1
      +voucher/split <voucher>/<item#>[:<qty>]    - Split to new voucher
      +voucher/cloneitem <voucher>/<item#>[:<qty>] - Clone cloneable item
      +voucher/create [name]           - Create voucher; use space, not = (e.g. +voucher/create My Pouch)
      +voucher/add <voucher>=<name> - Add item from your inventory
      +voucher/add <voucher>=<type>/<name> - Staff: create custom item
      +voucher/setstat <voucher>/<item#>=<field>=<value> - Staff: set item stat

    Abbrev: +vinfo for +voucher/info
    """
    key = "voucher"
    aliases = ["vinfo"]
    lock = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        if not self.switches:
            self.do_list()
            return
        switch = self.switches[0].lower()
        if switch == "info" or (self.cmdstring == "vinfo" and not self.switches):
            self.do_info()
        elif switch == "alias":
            self.do_alias()
        elif switch == "lock":
            self.do_lock(True)
        elif switch == "unlock":
            self.do_lock(False)
        elif switch == "loc":
            self.do_loc()
        elif switch == "use":
            self.do_use()
        elif switch == "chown":
            self.do_chown()
        elif switch == "rename":
            self.do_rename()
        elif switch == "nuke":
            self.do_nuke()
        elif switch == "move":
            self.do_move()
        elif switch == "join":
            self.do_join()
        elif switch == "split":
            self.do_split()
        elif switch == "cloneitem":
            self.do_cloneitem()
        elif switch == "create":
            self.do_create()
        elif switch == "add":
            self.do_add()
        elif switch == "setstat":
            self.do_setstat()
        else:
            self.caller.msg(f"Unknown switch: {switch}")

    def do_list(self):
        """List all vouchers the character has (in inventory)."""
        vouchers = [o for o in self.caller.contents if o.is_typeclass(VOUCHER_TYPECLASS)]
        if not vouchers:
            self.caller.msg("You have no vouchers.")
            return
        from world.utils.formatting import sheet_header, sheet_section, footer
        W = 80
        out = sheet_header("Your Vouchers", width=W)
        out += f"|y{'Voucher':<35}{'Items':<12}{'Locked':<10}|n\n"
        for v in vouchers:
            items = v.get_items() if hasattr(v, 'get_items') else []
            item_count = sum(it.get("quantity", 1) for it in items)
            locked = "Yes" if getattr(v.db, 'locked', False) else "No"
            out += f"|w{v.key:<35}{item_count:<12}{locked:<10}|n\n"
        out += footer(width=W, fillchar="-")
        self.caller.msg(out)

    def do_info(self):
        if not self.args:
            self.caller.msg("Usage: +voucher/info <voucher> or +voucher/info <voucher>/<item#>")
            return
        parts = self.args.split("/", 1)
        v_arg = parts[0].strip()
        item_num = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else None
        v = find_voucher(self.caller, v_arg)
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if item_num is not None:
            item, _ = v.get_item_by_num(item_num)
            if not item:
                self.caller.msg(f"No such item #{item_num}.")
                return
            from world.voucher.utils import format_voucher_item
            self.caller.msg(format_voucher_item(item, item_num))
        else:
            self.caller.msg(v.format_sheet())

    def do_alias(self):
        if "=" not in self.args:
            self.caller.msg("Usage: +voucher/alias <voucher>=<alias>")
            return
        v_arg, alias = self.args.split("=", 1)
        v_arg, alias = v_arg.strip(), alias.strip()[:20]
        if not alias:
            self.caller.msg("Alias cannot be empty.")
            return
        if not ALIAS_RE.match(alias):
            self.caller.msg("Alias may only contain letters, numbers, dashes, and underscores.")
            return
        v = find_voucher(self.caller, v_arg)
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if not v.can_modify(self.caller):
            self.caller.msg("That voucher is locked.")
            return
        v.db.voucher_alias = alias
        self.caller.msg(f"Alias for {v.key} set to '{alias}'.")

    def do_lock(self, locked):
        if not self.args:
            self.caller.msg("Usage: +voucher/lock <voucher> or +voucher/unlock <voucher>")
            return
        v = find_voucher(self.caller, self.args.strip())
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        v.db.locked = locked
        if locked:
            v.db.locked_by = self.caller.id
        else:
            v.db.locked_by = None
        self.caller.msg(f"{v.key} is now {'locked' if locked else 'unlocked'}.")

    def do_loc(self):
        if "=" not in self.args:
            self.caller.msg("Usage: +voucher/loc <voucher>/<item#>=<ic location>")
            return
        left, loc = self.args.split("=", 1)
        loc = loc.strip()[:20]
        parts = left.split("/", 1)
        if len(parts) < 2:
            self.caller.msg("Specify item number: <voucher>/<item#>")
            return
        v_arg, num_str = parts[0].strip(), parts[1].strip()
        try:
            num = int(num_str)
        except ValueError:
            self.caller.msg("Item number must be an integer.")
            return
        v = find_voucher(self.caller, v_arg)
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if not v.can_modify(self.caller):
            self.caller.msg("That voucher is locked.")
            return
        item, _ = v.get_item_by_num(num)
        if not item:
            self.caller.msg(f"No such item #{num}.")
            return
        items = v.get_items()
        items[num - 1] = dict(item)
        items[num - 1]["ic_location"] = loc
        v.set_items(items)
        self.caller.msg(f"IC location for item #{num} set to '{loc}'.")

    def do_use(self):
        parts = self.args.split("/", 1)
        if len(parts) < 2:
            self.caller.msg("Usage: +voucher/use <voucher>/<item#>[:<qty>]")
            return
        v_arg, rest = parts[0].strip(), parts[1].strip()
        if ":" in rest:
            num_str, qty_str = rest.split(":", 1)
            try:
                qty = int(qty_str.strip())
            except ValueError:
                qty = 1
        else:
            num_str = rest
            qty = 1
        try:
            num = int(num_str.strip())
        except ValueError:
            self.caller.msg("Item number must be an integer.")
            return
        v = find_voucher(self.caller, v_arg)
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if not v.can_modify(self.caller):
            self.caller.msg("That voucher is locked.")
            return
        item, idx = v.get_item_by_num(num)
        if not item:
            self.caller.msg(f"No such item #{num}.")
            return
        have = item.get("quantity", 1)
        if qty > have:
            qty = have
        items = v.get_items()
        if qty >= have:
            items.pop(idx - 1)
        else:
            items[idx - 1] = dict(item)
            items[idx - 1]["quantity"] = have - qty
        v.set_items(items)
        self.caller.msg(f"Used {qty} of {item.get('name', '?')}.")

    def do_chown(self):
        from typeclasses.npcs import is_npc
        if is_npc(self.caller):
            self.caller.msg("NPCs cannot give vouchers or transfer ownership to people.")
            return
        if "=" not in self.args:
            self.caller.msg("Usage: +voucher/chown <voucher>=<player>")
            return
        v_arg, target_arg = self.args.split("=", 1)
        v = find_voucher(self.caller, v_arg.strip())
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if not v.can_modify(self.caller):
            self.caller.msg("That voucher is locked.")
            return
        target = self.caller.search(target_arg.strip(), global_search=True)
        if not target:
            return
        name = getattr(target.db, 'full_name', None) or target.key
        v.db.ic_owner = name
        self.caller.msg(f"IC owner of {v.key} set to {name}.")

    def do_rename(self):
        if "=" not in self.args:
            self.caller.msg("Usage: +voucher/rename <voucher>=<new name>")
            return
        v_arg, new_name = self.args.split("=", 1)
        new_name = new_name.strip()[:38]
        if not new_name:
            self.caller.msg("Name cannot be empty.")
            return
        v = find_voucher(self.caller, v_arg.strip())
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if not v.can_modify(self.caller):
            self.caller.msg("That voucher is locked.")
            return
        old = v.key
        v.key = new_name
        self.caller.msg(f"Renamed {old} to {new_name}.")

    def do_nuke(self):
        if not self.args:
            self.caller.msg("Usage: +voucher/nuke <voucher>")
            return
        v = find_voucher(self.caller, self.args.strip())
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if not v.can_modify(self.caller):
            self.caller.msg("That voucher is locked.")
            return
        if not v.is_empty():
            self.caller.msg("You can only nuke empty vouchers.")
            return
        v.delete()
        self.caller.msg("Voucher destroyed.")

    def do_move(self):
        if "=" not in self.args:
            self.caller.msg("Usage: +voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>")
            return
        left, dest_arg = self.args.split("=", 1)
        dest_arg = dest_arg.strip()
        parts = left.split("/", 1)
        if len(parts) < 2:
            self.caller.msg("Specify item: <voucher>/<item#>")
            return
        v_arg, rest = parts[0].strip(), parts[1].strip()
        qty = None
        if ":" in rest:
            num_str, qty_str = rest.split(":", 1)
            try:
                qty = int(qty_str.strip())
            except ValueError:
                pass
            rest = num_str.strip()
        try:
            nums = [int(x.strip()) for x in rest.split() if x.strip().isdigit()]
        except ValueError:
            nums = []
        if not nums:
            self.caller.msg("Specify at least one item number.")
            return
        v = find_voucher(self.caller, v_arg)
        if not v:
            return
        dest = find_voucher(self.caller, dest_arg)
        if not dest:
            return
        if v.location != self.caller or dest.location != self.caller:
            self.caller.msg("Both vouchers must be in your inventory.")
            return
        if not v.can_modify(self.caller) or not dest.can_modify(self.caller):
            self.caller.msg("One or both vouchers are locked.")
            return
        items = v.get_items()
        to_move = []
        for n in sorted(set(nums), reverse=True):
            if 1 <= n <= len(items):
                it = items[n - 1]
                take = qty if qty is not None else it.get("quantity", 1)
                have = it.get("quantity", 1)
                take = min(take, have)
                if take >= have:
                    to_move.append(items.pop(n - 1))
                else:
                    copy = dict(it)
                    copy["quantity"] = take
                    to_move.append(copy)
                    items[n - 1]["quantity"] = have - take
        v.set_items(items)
        dest_items = dest.get_items()
        for it in to_move:
            name = it.get("name", "?")
            found = next((x for x in dest_items if x.get("name") == name and x.get("ic_location") == it.get("ic_location")), None)
            if found:
                found["quantity"] = found.get("quantity", 1) + it.get("quantity", 1)
            else:
                dest_items.append(it)
        dest.set_items(dest_items)
        self.caller.msg(f"Moved item(s) to {dest.key}.")

    def do_join(self):
        if "=" not in self.args:
            self.caller.msg("Usage: +voucher/join <voucher1>=<voucher2>")
            return
        v1_arg, v2_arg = self.args.split("=", 1)
        v1 = find_voucher(self.caller, v1_arg.strip())
        v2 = find_voucher(self.caller, v2_arg.strip())
        if not v1 or not v2:
            return
        if v1.location != self.caller or v2.location != self.caller:
            self.caller.msg("Both vouchers must be in your inventory.")
            return
        if not v1.can_modify(self.caller) or not v2.can_modify(self.caller):
            self.caller.msg("One or both vouchers are locked.")
            return
        dest_items = v1.get_items()
        for it in v2.get_items():
            name = it.get("name", "?")
            found = next((x for x in dest_items if x.get("name") == name and x.get("ic_location") == it.get("ic_location")), None)
            if found:
                found["quantity"] = found.get("quantity", 1) + it.get("quantity", 1)
            else:
                dest_items.append(it)
        v1.set_items(dest_items)
        v2.delete()
        self.caller.msg(f"Merged {v2.key} into {v1.key}.")

    def do_split(self):
        parts = self.args.split("/", 1)
        if len(parts) < 2:
            self.caller.msg("Usage: +voucher/split <voucher>/<item#>[:<qty>]")
            return
        v_arg, rest = parts[0].strip(), parts[1].strip()
        qty = None
        if ":" in rest:
            num_str, qty_str = rest.split(":", 1)
            try:
                qty = int(qty_str.strip())
            except ValueError:
                pass
            rest = num_str.strip()
        try:
            nums = [int(x.strip()) for x in rest.split() if x.strip().isdigit()]
        except ValueError:
            nums = []
        if not nums:
            self.caller.msg("Specify at least one item number.")
            return
        v = find_voucher(self.caller, v_arg)
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if not v.can_modify(self.caller):
            self.caller.msg("That voucher is locked.")
            return
        items = v.get_items()
        split_items = []
        for n in sorted(set(nums), reverse=True):
            if 1 <= n <= len(items):
                it = items[n - 1]
                take = qty if qty is not None else it.get("quantity", 1)
                have = it.get("quantity", 1)
                take = min(take, have)
                copy = dict(it)
                copy["quantity"] = take
                split_items.append(copy)
                if take >= have:
                    items.pop(n - 1)
                else:
                    items[n - 1]["quantity"] = have - take
        v.set_items(items)
        if not split_items:
            self.caller.msg("No valid items to split.")
            return
        first_name = split_items[0].get("name", "voucher")
        new_v = create_object(Voucher, key=first_name, location=self.caller)
        new_v.set_items(split_items)
        self.caller.msg(f"Created new voucher '{first_name}' with split items.")

    def do_cloneitem(self):
        parts = self.args.split("/", 1)
        if len(parts) < 2:
            self.caller.msg("Usage: +voucher/cloneitem <voucher>/<item#>[:<qty>]")
            return
        v_arg, rest = parts[0].strip(), parts[1].strip()
        qty = 1
        if ":" in rest:
            num_str, qty_str = rest.split(":", 1)
            try:
                qty = int(qty_str.strip())
            except ValueError:
                pass
            rest = num_str.strip()
        try:
            num = int(rest.strip())
        except ValueError:
            self.caller.msg("Item number must be an integer.")
            return
        v = find_voucher(self.caller, v_arg)
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if not v.can_modify(self.caller):
            self.caller.msg("That voucher is locked.")
            return
        item, idx = v.get_item_by_num(num)
        if not item:
            self.caller.msg(f"No such item #{num}.")
            return
        if not item.get("cloneable"):
            self.caller.msg("That item is not cloneable.")
            return
        items = v.get_items()
        for _ in range(qty - 1):
            copy = dict(item)
            copy["quantity"] = 1
            items.append(copy)
        v.set_items(items)
        self.caller.msg(f"Cloned {item.get('name', '?')} {qty} time(s).")

    def do_setstat(self):
        """Staff: set a stat on a custom voucher item. +voucher/setstat <voucher>/<item#>=<field>=<value>"""
        if not (self.caller.check_permstring("Builders") or self.caller.check_permstring("Admins")):
            self.caller.msg("Only staff can set voucher item stats.")
            return
        parts = self.args.split("=", 2)
        if len(parts) < 3:
            self.caller.msg("Usage: +voucher/setstat <voucher>/<item#>=<field>=<value>")
            return
        left, field, value = parts[0].strip(), parts[1].strip().lower(), parts[2].strip()
        voucher_item = left.split("/", 1)
        if len(voucher_item) < 2:
            self.caller.msg("Specify item number: <voucher>/<item#>")
            return
        v_arg, num_str = voucher_item[0].strip(), voucher_item[1].strip()
        try:
            num = int(num_str)
        except ValueError:
            self.caller.msg("Item number must be an integer.")
            return
        v = find_voucher(self.caller, v_arg)
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        item, idx = v.get_item_by_num(num)
        if not item:
            self.caller.msg(f"No such item #{num}.")
            return
        item_type = (item.get("item_type") or "").lower()
        if not item_type:
            self.caller.msg("That item has no type; setstat only works on typed items.")
            return
        from world.voucher.utils import ITEM_TYPE_FIELDS
        allowed = ITEM_TYPE_FIELDS.get(item_type, [])
        if field not in allowed:
            self.caller.msg(f"Invalid field '{field}'. Allowed for {item_type}: {', '.join(allowed)}")
            return
        item_data = item.get("item_data") or {}
        # Coerce value by field type
        if field in ("weight", "value", "sp", "ev", "cost", "humanity_loss", "slots", "hands",
                     "current_ammo", "max_ammo", "clip", "damage_dice", "damage_die_type",
                     "rate_of_fire", "quantity", "damage_modifier", "armor_piercing",
                     "sdp", "seats", "speed_combat"):
            try:
                item_data[field] = int(value)
            except ValueError:
                self.caller.msg(f"'{value}' is not a valid number for {field}.")
                return
        elif field in ("concealable", "is_weapon"):
            item_data[field] = value.lower() in ("1", "yes", "true")
        else:
            item_data[field] = value
        if field == "name":
            item["name"] = value
        item["item_data"] = item_data
        items = v.get_items()
        items[idx - 1] = item
        v.set_items(items)
        self.caller.msg(f"Set {field} to '{value}' on item #{num}.")

    def do_add(self):
        """Players: add from owned inventory only. Staff: create custom items with type/stats."""
        if "=" not in self.args:
            self.caller.msg(
                "Usage: +voucher/add <voucher>=<item name>  (from your inventory)\n"
                "Staff: +voucher/add <voucher>=<type>/<name>  (types: weapon, armor, gear, cyberware, ammunition, vehicle)"
            )
            return
        v_arg, rest = self.args.split("=", 1)
        v_arg = v_arg.strip()
        rest = rest.strip()
        v = find_voucher(self.caller, v_arg)
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if not v.can_modify(self.caller):
            self.caller.msg("That voucher is locked.")
            return

        is_staff = self.caller.check_permstring("Builders") or self.caller.check_permstring("Admins")

        # Staff custom item: <type>/<name>
        if is_staff and "/" in rest:
            type_part, name_part = rest.split("/", 1)
            item_type = type_part.strip().lower()
            item_name = name_part.strip()[:80]
            if not item_name:
                self.caller.msg("Item name cannot be empty.")
                return
            from world.voucher.utils import ITEM_TYPES
            if item_type not in ITEM_TYPES:
                self.caller.msg(f"Invalid type. Use one of: {', '.join(ITEM_TYPES)}")
                return
            # Create blank custom item with default stats for that type
            from world.voucher.utils import _blank_item_data_for_type
            item_data = _blank_item_data_for_type(item_type, item_name)
            voucher_item = {
                "name": item_name,
                "description": item_data.get("description", ""),
                "quantity": 1,
                "ic_location": "",
                "cloneable": False,
                "item_type": item_type,
                "item_data": item_data,
            }
            items = v.get_items()
            items.append(voucher_item)
            v.set_items(items)
            self.caller.msg(f"Added custom {item_type} '{item_name}' to {v.key}. Use +voucher/setstat to set stats.")
            return

        # Player: add from owned inventory only
        item_name = rest.strip()[:80]
        if not item_name:
            self.caller.msg("Item name cannot be empty.")
            return
        from world.voucher.utils import find_inventory_item
        from world.inventory.models import Inventory

        item_type, obj, serializer, removal_obj = find_inventory_item(self.caller, item_name)
        if not obj:
            self.caller.msg(f"You don't have '{item_name}' in your inventory.")
            return

        try:
            inv, _ = Inventory.get_or_create_for_character(self.caller)
        except (ValueError, AttributeError):
            self.caller.msg("You don't have an inventory.")
            return

        item_data = serializer(obj)
        qty = 1
        if item_type == "ammunition":
            qty = obj.quantity or 1
            item_data["quantity"] = qty

        voucher_item = {
            "name": item_data.get("name", item_name),
            "description": item_data.get("description", ""),
            "quantity": qty,
            "ic_location": "",
            "cloneable": False,
            "item_type": item_type,
            "item_data": item_data,
        }

        # Remove from inventory
        if item_type == "weapon":
            inv.weapons.remove(removal_obj)
        elif item_type == "armor":
            inv.armor.remove(removal_obj)
        elif item_type == "gear":
            inv.gear.remove(removal_obj)
        elif item_type == "cyberware":
            inv.cyberware.remove(removal_obj)
            removal_obj.delete()
        elif item_type == "ammunition":
            inv.ammunition.remove(removal_obj)
        elif item_type == "vehicle":
            inv.vehicles.remove(removal_obj)

        items = v.get_items()
        items.append(voucher_item)
        v.set_items(items)
        self.caller.msg(f"Added {qty} x {item_data.get('name', item_name)} to {v.key}.")

    def do_create(self):
        name = (self.args or "").strip()[:38] or "voucher"
        v = create_object(Voucher, key=name, location=self.caller)
        self.caller.msg(f"Created voucher '{name}'.")


class CmdConceal(MuxCommand):
    """Conceal or unconceal a voucher."""
    key = "conceal"
    aliases = ["unconceal"]
    lock = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        if not self.args:
            switch = "unconceal" if self.cmdstring == "unconceal" else "conceal"
            self.caller.msg(f"Usage: +{switch} <voucher>")
            return
        v = find_voucher(self.caller, self.args.strip())
        if not v:
            return
        if v.location != self.caller:
            self.caller.msg("You don't have that voucher.")
            return
        if self.cmdstring == "unconceal":
            v.db.concealed = False
            self.caller.msg(f"{v.key} is now visible.")
        else:
            v.db.concealed = True
            self.caller.msg(f"{v.key} is now concealed.")


class CmdOwner(MuxCommand):
    """Show IC owner of a voucher."""
    key = "owner"
    lock = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: +owner <voucher>")
            return
        v = find_voucher(self.caller, self.args.strip())
        if not v:
            return
        owner = v.db.ic_owner or "(none)"
        self.caller.msg(f"IC owner of {v.key}: {owner}")
