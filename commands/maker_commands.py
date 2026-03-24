# -*- coding: utf-8 -*-
"""
+make command - Crafting for Techs (fabrication), Medtechs (pharma), and Netrunners (programs, deck options).
"""
from django.utils import timezone
from evennia.commands.default.muxcommand import MuxCommand

from world.maker.models import CraftOrder
from world.maker.services import (
    create_fabrication_order,
    create_upgrade_order,
    preview_upgrade_quote,
    create_staff_reward_upgrade,
    create_pharma_order,
    create_program_order,
    create_deckoption_order,
    process_due_orders,
    process_craft_order,
    PHARMA_ITEMS,
)
from world.maker.scripts import get_or_create_maker_script
from world.maker.upgrades import get_upgrade_listing_rows
from world.utils.formatting import sheet_header, sheet_section, footer
from world.voucher.utils import format_voucher_item


class CmdMake(MuxCommand):
    """
    Craft items - Tech fabrication, Medtech pharma, Netrunner programs/deck options.

    Usage:
      +make                    - List your craft queue
      +make/add <item>         - Tech: fabricate item (weapons, armor, gear, etc.)
      +make/add <item>=<who>   - Craft for someone else
      +make/upgrade            - Tech: list available upgrades
      +make/upgrade/add <item>=<upgrade> - Tech: queue an item upgrade
      +make/upgrade/quote <item>=<upgrade> - Tech: show Cost #1/#2 + NPC labor estimate
      +make/staff <who>=<item>=<upgrade> - Staff: instant upgraded reward voucher (no cost/roll)
      +make/pharma             - Medtech: list craftable drugs
      +make/pharma/add <drug>  - Medtech: craft a drug
      +make/program            - Netrunner: list craftable programs
      +make/program/add <name> - Netrunner: craft a program
      +make/deckoption         - Netrunner: list craftable deck options
      +make/deckoption/add <name> - Netrunner: craft a deck option
      +make/info <#>           - Show item details for a queued order
      +make/cancel <#>         - Cancel a queued order (refund materials)
      +make/process <char>=<#>  - Staff: force process a specific order
    """

    key = "+make"
    aliases = ["make"]
    lock = "cmd:all()"
    help_category = "Crafting"

    def func(self):
        if not self.switches:
            self._do_queue()
            return
        switch = self.switches[0].lower()
        if switch == "add":
            self._do_add()
        elif switch == "pharma":
            self._do_pharma()
        elif switch == "upgrade":
            self._do_upgrade()
        elif switch == "staff":
            self._do_staff_reward_upgrade()
        elif switch == "program":
            self._do_program()
        elif switch == "deckoption":
            self._do_deckoption()
        elif switch == "info":
            self._do_info()
        elif switch == "cancel":
            self._do_cancel()
        elif switch == "process":
            self._do_process()
        else:
            self._do_queue()

    def _do_queue(self):
        """List caller's craft queue (all types)."""
        orders = CraftOrder.objects.filter(crafter=self.caller).filter(
            status__in=(CraftOrder.STATUS_QUEUED, CraftOrder.STATUS_IN_PROGRESS)
        ).order_by("completed_at")

        W = 80
        out = sheet_header("Craft Queue", width=W)
        if not orders:
            out += "|wNo items in queue.|n\n"
            out += "\n|yTech:|n +make/add <item> - Fabricate weapons, armor, gear, vehicles\n"
            out += "|yTech:|n +make/upgrade - Upgrade an existing item into a custom item\n"
            out += "|yMedtech:|n +make/pharma - Craft drugs\n"
            out += "|yNetrunner:|n +make/program - Craft programs | +make/deckoption - Craft deck options\n"
        else:
            out += f"|y{'#':<4}{'Type':<12}{'Item':<22}{'DV':<5}{'Time':<8}{'Cost':<8}{'Ready':<18}|n\n"
            now = timezone.now()
            type_labels = dict(CraftOrder.CRAFT_TYPE_CHOICES)
            for o in orders:
                t = type_labels.get(o.craft_type, o.craft_type)[:11]
                ready = "Now" if o.completed_at <= now else o.completed_at.strftime("%m/%d %H:%M")
                out += f"|w{o.id:<4}{t:<12}{o.item_name[:21]:<22}{o.dv:<5}{o.time_hours}h{'':<4}{o.materials_cost:<8}{ready:<18}|n\n"
        out += footer(width=W, fillchar="-")
        self.caller.msg(out)

    def _do_info(self):
        """Show item details for a queued order by number."""
        if not self.args or not self.args.strip():
            self.caller.msg("Usage: +make/info <#>")
            return
        try:
            oid = int(self.args.strip())
        except ValueError:
            self.caller.msg("Usage: +make/info <#> (number from your craft queue)")
            return

        order = CraftOrder.objects.filter(
            crafter=self.caller,
            id=oid,
            status__in=(CraftOrder.STATUS_QUEUED, CraftOrder.STATUS_IN_PROGRESS),
        ).first()
        if not order:
            self.caller.msg("No such order in your queue, or it has already been processed.")
            return

        # Build item dict for format_voucher_item
        item = {
            "name": order.item_name,
            "item_type": order.item_type,
            "item_data": order.item_data or {},
            "quantity": 1,
        }
        if order.craft_type == "pharma":
            from world.chargen_constants import get_medical_tech_skill
            doses = get_medical_tech_skill(
                getattr(order.crafter.db, "medicine_pharma", 0),
                getattr(order.crafter.db, "medicine_cryo", 0),
            )
            item["quantity"] = max(1, doses)
            item["item_data"]["quantity"] = item["quantity"]

        out = format_voucher_item(item, item_num=oid)
        # Append craft queue metadata
        now = timezone.now()
        ready = "Now" if order.completed_at <= now else order.completed_at.strftime("%Y-%m-%d %H:%M")
        type_labels = dict(CraftOrder.CRAFT_TYPE_CHOICES)
        craft_type = type_labels.get(order.craft_type, order.craft_type)
        out += f"\n|yCraft:|n {craft_type} | DV{order.dv} | {order.time_hours}h | {order.materials_cost} eb | Ready: {ready}\n"
        self.caller.msg(out)

    def _do_add(self):
        """Tech fabrication."""
        if not self.args or not self.args.strip():
            self.caller.msg("Usage: +make/add <item name> or +make/add <item>=<recipient>")
            return

        recipient = None
        arg = self.args.strip()
        if "=" in arg:
            item_name, recipient_name = arg.split("=", 1)
            item_name = item_name.strip()
            recipient_name = recipient_name.strip()
            if recipient_name:
                recipient = self.caller.search(recipient_name, global_search=True)
                if not recipient:
                    return
        else:
            item_name = arg

        order, err = create_fabrication_order(self.caller, item_name, recipient=recipient)
        if err:
            self.caller.msg(f"|r{err}|n")
            return

        recip_str = f" for {recipient.key}" if recipient and recipient != self.caller else ""
        self.caller.msg(
            f"|gQueued fabrication of {order.item_name}{recip_str}.|n "
            f"Materials: {order.materials_cost} eb. DV{order.dv}, ~{order.time_hours}h. "
            f"Ready around {order.completed_at.strftime('%Y-%m-%d %H:%M')}. "
            f"The system will auto-roll when complete."
        )
        get_or_create_maker_script()

    def _do_pharma(self):
        """Medtech: list drugs or add with /add."""
        role = (getattr(self.caller.db, "role", None) or "").strip()
        if role != "Medtech":
            self.caller.msg("Only Medtech characters can craft pharmaceuticals. Use +make/add for Tech fabrication.")
            return

        if "add" in self.switches and len(self.switches) > 1:
            # +make/pharma/add <drug>
            drug_name = self.args.strip() if self.args else ""
            if not drug_name:
                self.caller.msg("Usage: +make/pharma/add <drug name>")
                return
            order, err = create_pharma_order(self.caller, drug_name)
            if err:
                self.caller.msg(f"|r{err}|n")
                return
            self.caller.msg(
                f"|gQueued pharmaceutical synthesis: {order.item_name}.|n "
                f"200eb materials, DV13, 1 hour. Doses = your Medical Tech when complete."
            )
            get_or_create_maker_script()
            return

        # List craftable pharmaceuticals (not street drugs)
        W = 80
        out = sheet_header("Medical Tech (Pharmaceuticals)", width=W)
        out += "|y200eb materials, DV13, 1 hour. Doses = your Medical Tech Skill.|n\n"
        out += "|yUse +make/pharma/add <name> to craft.|n\n\n"
        out += f"|y{'Name':<15}{'Effect':<60}|n\n"
        for data in PHARMA_ITEMS.values():
            desc = (data["description"] or "")[:58] + ".." if len(data["description"] or "") > 60 else (data["description"] or "")
            out += f"  {data['name']:<15}{desc}\n"
        out += footer(width=W, fillchar="-")
        self.caller.msg(out)

    def _do_upgrade(self):
        """Tech: list upgrades or queue an upgrade with /add."""
        role = (getattr(self.caller.db, "role", None) or "").strip()
        if role != "Tech":
            self.caller.msg("Only Tech characters can use Upgrade Expertise.")
            return

        if "add" in self.switches and len(self.switches) > 1:
            raw = (self.args or "").strip()
            if "=" not in raw:
                self.caller.msg("Usage: +make/upgrade/add <item>=<upgrade key or name>")
                return
            item_name, upgrade_name = raw.split("=", 1)
            item_name = item_name.strip()
            upgrade_name = upgrade_name.strip()
            if not item_name or not upgrade_name:
                self.caller.msg("Usage: +make/upgrade/add <item>=<upgrade key or name>")
                return

            order, err = create_upgrade_order(self.caller, item_name, upgrade_name)
            if err:
                self.caller.msg(f"|r{err}|n")
                return
            cost1 = (order.item_data or {}).get("_maker_cost_1", order.materials_cost)
            cost2 = (order.item_data or {}).get("_maker_cost_2", 0)
            upg_name = (order.item_data or {}).get("_maker_upgrade_name", "Maker Upgrade")
            self.caller.msg(
                f"|gQueued upgrade: {order.item_name}.|n Upgrade: {upg_name}. "
                f"Materials: {order.materials_cost} eb (Cost #1 {cost1} + Cost #2 {cost2}). "
                f"DV{order.dv}, ~{order.time_hours}h. Ready around {order.completed_at.strftime('%Y-%m-%d %H:%M')}."
            )
            get_or_create_maker_script()
            return
        if "quote" in self.switches and len(self.switches) > 1:
            raw = (self.args or "").strip()
            if "=" not in raw:
                self.caller.msg("Usage: +make/upgrade/quote <item>=<upgrade key or name>")
                return
            item_name, upgrade_name = raw.split("=", 1)
            item_name = item_name.strip()
            upgrade_name = upgrade_name.strip()
            if not item_name or not upgrade_name:
                self.caller.msg("Usage: +make/upgrade/quote <item>=<upgrade key or name>")
                return
            quote, err = preview_upgrade_quote(self.caller, item_name, upgrade_name)
            if err:
                self.caller.msg(f"|r{err}|n")
                return
            src = "Invented" if quote["upgrade_source"] == "invented" else "Core"
            self.caller.msg(
                f"|wUpgrade Quote|n - {quote['item_name']} -> {quote['upgraded_name']}\n"
                f"  Upgrade: {quote['upgrade_name']} ({src})\n"
                f"  DV/Time: DV{quote['dv']} / ~{quote['time_hours']}h ({quote['price_category']})\n"
                f"  Cost #1 (materials): {quote['cost1']} eb\n"
                f"  Cost #2 (invented): {quote['cost2']} eb\n"
                f"  Materials total: {quote['materials_total']} eb\n"
                f"  NPC labor fee (50%): {quote['labor_fee']} eb\n"
                f"  |yNPC total estimate: {quote['npc_total']} eb|n\n"
                f"  |cPlayer Tech install pays materials only: {quote['materials_total']} eb|n"
            )
            return

        rows = get_upgrade_listing_rows()
        W = 80
        out = sheet_header("Maker Upgrade Expertise", width=W)
        out += "|yUse +make/upgrade/add <item>=<upgrade key>|n\n"
        out += "|yUse +make/upgrade/quote <item>=<upgrade key>|n\n\n"
        out += f"|y{'Key':<28}{'Source':<10}{'Cost #2':<10}{'Types':<30}|n\n"
        for row in rows:
            src = "Invented" if row["source"] == "invented" else "Core"
            cost2 = f"{row['cost2']} eb" if row["cost2"] else "-"
            out += f"  {row['key'][:27]:<28}{src:<10}{cost2:<10}{row['types'][:29]:<30}\n"
        out += "\n|yDescriptions|n\n"
        for row in rows:
            out += f"  |w{row['key']}|n - {row['description']}\n"
        out += footer(width=W, fillchar="-")
        self.caller.msg(out)

    def _do_program(self):
        """Netrunner: list programs or add with /add."""
        role = (getattr(self.caller.db, "role", None) or "").strip()
        if role != "Netrunner":
            self.caller.msg("Only Netrunner characters can craft programs. Use +make/add for Tech fabrication.")
            return

        if "add" in self.switches and len(self.switches) > 1:
            prog_name = self.args.strip() if self.args else ""
            if not prog_name:
                self.caller.msg("Usage: +make/program/add <program name>")
                return
            order, err = create_program_order(self.caller, prog_name)
            if err:
                self.caller.msg(f"|r{err}|n")
                return
            self.caller.msg(
                f"|gQueued program craft: {order.item_name}.|n "
                f"Materials: {order.materials_cost} eb. DV{order.dv}, ~{order.time_hours}h."
            )
            get_or_create_maker_script()
            return

        from world.netrunning.deckoptions import programs
        W = 80
        out = sheet_header("Craftable Programs (Netrunner)", width=W)
        out += "|yUse +make/program/add <name> to craft.|n\n\n"
        out += f"|y{'Name':<25}{'Type':<20}{'Cost':<10}|n\n"
        for p in programs:
            out += f"  {(p.get('name') or '?'):<25}{(p.get('type') or '?'):<20}{(p.get('cost') or 0):<10} eb\n"
        out += footer(width=W, fillchar="-")
        self.caller.msg(out)

    def _do_staff_reward_upgrade(self):
        """Staff: instantly grant a custom upgraded item as a voucher reward."""
        if not (
            hasattr(self.caller, "check_permstring")
            and (self.caller.check_permstring("Builders") or self.caller.check_permstring("Admins"))
        ):
            self.caller.msg("Only staff can use +make/staff.")
            return

        raw = (self.args or "").strip()
        parts = [p.strip() for p in raw.split("=")] if raw else []
        if len(parts) != 3 or not all(parts):
            self.caller.msg("Usage: +make/staff <character>=<base item name>=<upgrade key or name>")
            return

        who, item_name, upgrade_name = parts
        target = self.caller.search(who, global_search=True)
        if not target:
            return

        voucher, err = create_staff_reward_upgrade(
            target_character=target,
            item_name=item_name,
            upgrade_name=upgrade_name,
            staff_character=self.caller,
        )
        if err:
            self.caller.msg(f"|r{err}|n")
            return

        self.caller.msg(
            f"|gCreated reward voucher '{voucher.key}' for {target.key}.|n "
            f"Item: {item_name} | Upgrade: {upgrade_name}"
        )
        if hasattr(target, "msg"):
            target.msg(
                f"|gYou received a custom upgraded reward voucher: {voucher.key}.|n"
            )

    def _do_deckoption(self):
        """Netrunner: list deck options or add with /add."""
        role = (getattr(self.caller.db, "role", None) or "").strip()
        if role != "Netrunner":
            self.caller.msg("Only Netrunner characters can craft deck options. Use +make/add for Tech fabrication.")
            return

        if "add" in self.switches and len(self.switches) > 1:
            opt_name = self.args.strip() if self.args else ""
            if not opt_name:
                self.caller.msg("Usage: +make/deckoption/add <deck option name>")
                return
            order, err = create_deckoption_order(self.caller, opt_name)
            if err:
                self.caller.msg(f"|r{err}|n")
                return
            self.caller.msg(
                f"|gQueued deck option craft: {order.item_name}.|n "
                f"Materials: {order.materials_cost} eb. DV{order.dv}, ~{order.time_hours}h."
            )
            get_or_create_maker_script()
            return

        from world.netrunning.deckoptions import hardware
        W = 80
        out = sheet_header("Craftable Deck Options (Netrunner)", width=W)
        out += "|yUse +make/deckoption/add <name> to craft.|n\n\n"
        out += f"|y{'Name':<25}{'Slots':<8}{'Cost':<10}|n\n"
        for h in hardware:
            out += f"  {(h.get('name') or '?'):<25}{(h.get('slots') or 0):<8}{(h.get('cost') or 0):<10} eb\n"
        out += footer(width=W, fillchar="-")
        self.caller.msg(out)

    def _do_cancel(self):
        """Cancel a queued order."""
        if not self.args or not self.args.strip().isdigit():
            self.caller.msg("Usage: +make/cancel <order#>")
            return

        oid = int(self.args.strip())
        order = CraftOrder.objects.filter(
            id=oid,
            crafter=self.caller,
            status__in=(CraftOrder.STATUS_QUEUED, CraftOrder.STATUS_IN_PROGRESS),
        ).first()
        if not order:
            self.caller.msg("No such order in your queue, or it has already been processed.")
            return

        from world.cyberpunk_sheets.services import CharacterMoneyService
        from evennia import create_object
        CharacterMoneyService.add_money(self.caller, order.materials_cost)

        restored = False
        if order.craft_type == CraftOrder.CRAFT_TYPE_UPGRADE:
            base_item = (order.item_data or {}).get("_maker_base_item")
            if base_item:
                base_name = base_item.get("name", "Original Item")
                base_data = dict(base_item.get("item_data") or {})
                base_type = base_item.get("item_type", order.item_type)
                qty = max(1, int(base_item.get("quantity", 1) or 1))
                voucher = create_object(
                    "typeclasses.vouchers.Voucher",
                    key=f"Recovered: {base_name}",
                    location=self.caller,
                )
                voucher.set_items([{
                    "name": base_name,
                    "description": base_data.get("description", ""),
                    "quantity": qty,
                    "ic_location": "",
                    "cloneable": False,
                    "item_type": base_type,
                    "item_data": base_data,
                }])
                order.voucher = voucher
                restored = True

        order.status = CraftOrder.STATUS_CANCELLED
        order.save()
        extra = " Original item returned as a voucher." if restored else ""
        self.caller.msg(
            f"|yCancelled order #{oid} ({order.item_name}). Refunded {order.materials_cost} eb.{extra}|n"
        )

    def _do_process(self):
        """Staff: force process a specific craft order."""
        if not (
            hasattr(self.caller, "check_permstring")
            and (self.caller.check_permstring("Builders") or self.caller.check_permstring("Admins"))
        ):
            self.caller.msg("Only staff can use +make/process.")
            return

        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: +make/process <character>=<queue#>")
            return

        char_arg, num_arg = self.args.split("=", 1)
        char_arg = char_arg.strip()
        num_arg = num_arg.strip()
        if not char_arg or not num_arg:
            self.caller.msg("Usage: +make/process <character>=<queue#>")
            return

        char = self.caller.search(char_arg, global_search=True)
        if not char:
            return

        try:
            oid = int(num_arg)
        except ValueError:
            self.caller.msg("Queue number must be an integer.")
            return

        order = CraftOrder.objects.filter(
            crafter=char,
            id=oid,
            status__in=(CraftOrder.STATUS_QUEUED, CraftOrder.STATUS_IN_PROGRESS),
        ).first()
        if not order:
            self.caller.msg(f"No such order #{oid} in {char.key}'s queue, or it has already been processed.")
            return

        process_craft_order(order)
        self.caller.msg(f"|gProcessed order #{oid} ({order.item_name}) for {char.key}.|n")
