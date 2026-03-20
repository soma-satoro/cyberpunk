import random
from evennia import Command
from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.search import search_object
from evennia.utils.utils import crop
from evennia.utils import gametime
from world.cyberpunk_sheets.services import CharacterMoneyService
from world.inventory.models import Weapon, Armor, Gear, Vehicle as VehicleModel, CyberwareInstance, Inventory, Ammunition
from world.equipment_data import weapons, armors, gears, cyberdecks as cyberdecks_data, vehicles as vehicles_data, ammunition as ammunition_data
from world.edgerunner_weapon_flavor import resolve_weapon_for_inventory
from world.cyberware.models import Cyberware
from world.cyberware.merchants import check_cyberware_requirements
from world.cyberware.validation import (
    validate_parent_for_new_child,
    find_best_cyberaudio_parent,
    select_balanced_parent_instance,
    PAIRABLE_NAMES,
    allows_multiples,
    FOUNDATION_EYE_NAME_LOWERS,
    _CYBEREYE_INSTANCE_NAMES,
)
from world.cyberware.cyberware_data import BODYCULPT_PACKAGES
from evennia.utils.evmenu import get_input, EvMenu
from world.cyberpunk_sheets.merchants import Merchant
from world.utils.character_utils import get_character_sheet
from world.utils.formatting import header, footer, section_header
from world.utils.ansi_utils import wrap_ansi
from world.commerce.pricing import (
    EXPENSIVE_THRESHOLD,
    can_purchase_expensive_from_vendor,
    get_purchase_discount_percent,
    calculate_final_price,
    is_expensive_item,
)
from world.commerce.vendor_tags import (
    is_vendor_room,
    get_vendor_catalog_filters,
    item_matches_vendor_filters,
    get_available_main_categories,
    get_available_subcategories,
)

# Import ChargenRoom for chargen buy
from typeclasses.chargen import ChargenRoom
from commands.list_commands import _find_item_info, format_item_info
from commands.equipment_commands import format_search_equipment
from world.chargen_constants import (
    FASHION_ITEM_NAMES,
    CHARGEN_EURODOLLARS_EDGERUNNER,
    CHARGEN_EURODOLLARS_COMPLETE_PACKAGE,
)


class Merchant:
    def __init__(self, merchant_type):
        self.merchant_type = merchant_type
        self.inventory = self._load_inventory()

    def _load_inventory(self):
        if self.merchant_type == "arms_dealer":
            return {item['name']: item for item in weapons}
        elif self.merchant_type == "clothier":
            return {item['name']: item for item in armors}
        elif self.merchant_type == "gear_merchant":
            return {item['name']: item for item in gears}
        else:
            return {}

    def get_item(self, item_name):
        return self.inventory.get(item_name)

    def list_items(self):
        return [f"{name} - {item['value']} eb" for name, item in self.inventory.items()]


# Chargen only sells items at or under 1000 eb (nothing over 1000)
CHARGEN_MAX_PRICE = 1000


def _is_fashion_item(item, item_type, gear_category=None):
    """Return True if item uses fashion budget (clothing/fashionware) during chargen."""
    if item_type == "cyberware_implant":
        return getattr(item.get("_cyberware"), "type", "") == "Fashionware"
    if gear_category and (str(gear_category or "").lower() == "clothing"):
        return True
    name = item.get("name", "")
    return name in FASHION_ITEM_NAMES


def _get_chargen_catalog(category=None, subcategory=None):
    """
    Build catalog of chargen items (value <= 1000).
    category: 'weapons', 'armor', 'gear', 'cyberware' or None for all.
    subcategory: filter by subcategory (e.g. 'medical' for gear, 'shoulder_arms' for weapons).
    """
    catalog = []
    if category is None or category == "weapons":
        for w in weapons:
            if w.get("value", 0) <= CHARGEN_MAX_PRICE:
                if subcategory and w.get("category", "").lower() != subcategory.lower():
                    continue
                entry = dict(w)
                entry["_type"] = "weapon"
                entry["_merchant_type"] = "arms_dealer"
                catalog.append(entry)
    if category is None or category == "armor":
        for a in armors:
            if a.get("value", 0) <= CHARGEN_MAX_PRICE:
                if subcategory:
                    locs = [x.strip().lower() for x in (a.get("locations", "") or "").split(",")]
                    if subcategory.lower() not in locs:
                        continue
                entry = dict(a)
                entry["_type"] = "armor"
                entry["_merchant_type"] = "clothier"
                catalog.append(entry)
    if category is None or category == "gear":
        for g in gears:
            if g.get("value", 0) <= CHARGEN_MAX_PRICE and g.get("category") != "Cyberware":
                if subcategory and g.get("category", "").lower() != subcategory.lower():
                    continue
                entry = dict(g)
                entry["_type"] = "gear"
                entry["_merchant_type"] = "gear_merchant"
                catalog.append(entry)
        if not subcategory or subcategory.lower() == "cyberdeck":
            for cd in cyberdecks_data:
                if cd.get("value", 0) <= CHARGEN_MAX_PRICE:
                    catalog.append({
                        "name": cd["name"],
                        "value": cd["value"],
                        "hardware_slots": cd.get("hardware_slots", 0),
                        "program_slots": cd.get("program_slots", 0),
                        "any_slots": cd.get("any_slots", 0),
                        "_type": "cyberdeck",
                        "_merchant_type": "cyberdeck_merchant",
                    })
    if category is None or category == "cyberware":
        for cw in Cyberware.objects.filter(cost__lte=CHARGEN_MAX_PRICE).order_by("type", "name"):
            if subcategory and getattr(cw, "type", "").lower() != subcategory.lower():
                continue
            catalog.append({
                "name": cw.name,
                "value": cw.cost,
                "_type": "cyberware_implant",
                "_cyberware": cw,
            })
        for g in gears:
            if g.get("value", 0) <= CHARGEN_MAX_PRICE and g.get("category") == "Cyberware":
                if subcategory:
                    continue
                entry = dict(g)
                entry["_type"] = "gear"
                entry["_merchant_type"] = "gear_merchant"
                catalog.append(entry)
    if category is None or category == "ammo":
        for a in ammunition_data:
            cost = a.get("cost", 10)
            if cost * 10 <= CHARGEN_MAX_PRICE:
                catalog.append({
                    "name": a["name"],
                    "ammo_type": a.get("ammo_type", "Basic"),
                    "cost": cost,
                    "_type": "ammo",
                    "_ammo_data": a,
                })
    return catalog


def _get_chargen_subcategories():
    """Return dict of main_category -> set of subcategories present in chargen catalog."""
    result = {"weapons": set(), "armor": set(), "gear": set(), "cyberware": set()}
    for w in weapons:
        if w.get("value", 0) <= CHARGEN_MAX_PRICE and w.get("category"):
            result["weapons"].add(w["category"])
    for a in armors:
        if a.get("value", 0) <= CHARGEN_MAX_PRICE and a.get("locations"):
            for loc in str(a["locations"]).split(","):
                result["armor"].add(loc.strip())
    for g in gears:
        if g.get("value", 0) <= CHARGEN_MAX_PRICE and g.get("category") and g.get("category") != "Cyberware":
            result["gear"].add(g["category"])
    if any(cd.get("value", 0) <= CHARGEN_MAX_PRICE for cd in cyberdecks_data):
        result["gear"].add("Cyberdeck")
    for cw in Cyberware.objects.filter(cost__lte=CHARGEN_MAX_PRICE).values_list("type", flat=True).distinct():
        if cw:
            result["cyberware"].add(cw)
    return result


def _get_vendor_catalog(room, main_cat=None, subcategory=None):
    """
    Build catalog for a tag-based vendor room. No price limit (filtered at buy time).
    Filters by room's vendor tags. main_cat/subcategory further narrow the result.
    """
    filters = get_vendor_catalog_filters(room)
    if not filters:
        return []

    catalog = []
    # Weapons
    if main_cat is None or main_cat == "weapons":
        for w in weapons:
            entry = dict(w)
            entry["_type"] = "weapon"
            entry["_merchant_type"] = "arms_dealer"
            if not item_matches_vendor_filters(entry, filters):
                continue
            if subcategory and w.get("category", "").lower() != subcategory.lower():
                continue
            catalog.append(entry)
    # Armor
    if main_cat is None or main_cat == "armor":
        for a in armors:
            entry = dict(a)
            entry["_type"] = "armor"
            entry["_merchant_type"] = "clothier"
            if not item_matches_vendor_filters(entry, filters):
                continue
            if subcategory:
                locs = [x.strip().lower() for x in (a.get("locations", "") or "").split(",")]
                if subcategory.lower() not in locs:
                    continue
            catalog.append(entry)
    # Gear (including cyberdecks)
    if main_cat is None or main_cat == "gear":
        for g in gears:
            if g.get("category") == "Cyberware":
                continue
            entry = dict(g)
            entry["_type"] = "gear"
            entry["_merchant_type"] = "gear_merchant"
            if not item_matches_vendor_filters(entry, filters):
                continue
            if subcategory and g.get("category", "").lower() != subcategory.lower():
                continue
            catalog.append(entry)
        if not subcategory or subcategory.lower() == "cyberdeck":
            for cd in cyberdecks_data:
                entry = {
                    "name": cd["name"],
                    "value": cd["value"],
                    "hardware_slots": cd.get("hardware_slots", 0),
                    "program_slots": cd.get("program_slots", 0),
                    "any_slots": cd.get("any_slots", 0),
                    "_type": "cyberdeck",
                    "_merchant_type": "cyberdeck_merchant",
                }
                if item_matches_vendor_filters(entry, filters):
                    catalog.append(entry)
    # Cyberware
    if main_cat is None or main_cat == "cyberware":
        for cw in Cyberware.objects.all().order_by("type", "name"):
            entry = {
                "name": cw.name,
                "value": cw.cost,
                "_type": "cyberware_implant",
                "_cyberware": cw,
            }
            if not item_matches_vendor_filters(entry, filters):
                continue
            if subcategory and getattr(cw, "type", "").lower() != subcategory.lower():
                continue
            catalog.append(entry)
        for g in gears:
            if g.get("category") != "Cyberware":
                continue
            entry = dict(g)
            entry["_type"] = "gear"
            entry["_merchant_type"] = "gear_merchant"
            if not item_matches_vendor_filters(entry, filters):
                continue
            if subcategory:
                continue
            catalog.append(entry)
    # Ammunition (cost per 10 rounds; buy <ammo>=<units> adds units*10 rounds)
    if main_cat is None or main_cat == "ammo":
        for a in ammunition_data:
            entry = {
                "name": a["name"],
                "ammo_type": a.get("ammo_type", "Basic"),
                "cost": a.get("cost", 10),
                "_type": "ammo",
                "_ammo_data": a,
            }
            if not item_matches_vendor_filters(entry, filters):
                continue
            catalog.append(entry)
    return catalog


def _get_vendor_subcategories(room):
    """Return dict of main_category -> set of subcategories available in this vendor room."""
    catalog = _get_vendor_catalog(room)
    result = {"weapons": set(), "armor": set(), "gear": set(), "cyberware": set()}
    for item in catalog:
        mt = item.get("_type")
        if mt == "weapon":
            if item.get("category"):
                result["weapons"].add(item["category"])
        elif mt == "armor":
            for loc in (item.get("locations") or "").split(","):
                if loc.strip():
                    result["armor"].add(loc.strip())
        elif mt == "gear":
            cat = item.get("category")
            if cat and cat != "Cyberware":
                result["gear"].add(cat)
        elif mt == "cyberdeck":
            result["gear"].add("Cyberdeck")
        elif mt == "cyberware_implant":
            cw = item.get("_cyberware")
            if cw and getattr(cw, "type", ""):
                result["cyberware"].add(cw.type)
    return result


def _find_vendor_item(room, item_name, cyberware_only=False):
    """Find item in vendor room catalog by name. Returns (item_dict, item_type, gear_category) or None."""
    item_name_lower = item_name.lower()
    if cyberware_only:
        catalog = _get_vendor_catalog(room, main_cat="cyberware")
        for item in catalog:
            if item.get("_type") == "cyberware_implant" and item.get("name", "").lower() == item_name_lower:
                return (item, "cyberware_implant", None)
        return None
    catalog = _get_vendor_catalog(room)
    for item in catalog:
        name = item.get("name", "")
        itype = item.get("_type")
        if name.lower() == item_name_lower:
            gear_cat = item.get("category") if itype == "gear" else None
            return (item, itype, gear_cat)
        # Fuzzy ammo: "hollow point" matches "Hollow Point Ammo"
        if itype == "ammo" and item_name_lower in name.lower():
            return (item, "ammo", None)
    return None


def _find_chargen_item(item_name, cyberware_only=False):
    """Find item in chargen catalog by name (value <= 1000). Returns (item_dict_or_cyberware, item_type, gear_category) or None.
    cyberware_only: if True, only search Cyberware model (body implants). If False, search weapons/armor/gear/cyberdecks only."""
    item_name_lower = item_name.lower()
    if cyberware_only:
        # Body cyberware only - requires /cyberware switch
        try:
            cw = Cyberware.objects.get(name__iexact=item_name, cost__lte=CHARGEN_MAX_PRICE)
            return ({"_cyberware": cw, "name": cw.name, "value": cw.cost}, "cyberware_implant", None)
        except Cyberware.DoesNotExist:
            pass
        return None
    # Equipment: weapons, armor, gear, external cyberdecks (NOT body cyberware)
    for w in weapons:
        if w.get("value", 0) <= CHARGEN_MAX_PRICE and w.get("name", "").lower() == item_name_lower:
            return (dict(w), "weapon", None)
    for a in armors:
        if a.get("value", 0) <= CHARGEN_MAX_PRICE and a.get("name", "").lower() == item_name_lower:
            return (dict(a), "armor", None)
    for g in gears:
        if g.get("value", 0) <= CHARGEN_MAX_PRICE and g.get("name", "").lower() == item_name_lower:
            return (dict(g), "gear", g.get("category"))
    for cd in cyberdecks_data:
        if cd.get("value", 0) <= CHARGEN_MAX_PRICE and cd.get("name", "").lower() == item_name_lower:
            return ({
                "name": cd["name"],
                "value": cd["value"],
                "description": cd.get("description", ""),
                "category": "Cyberdeck",
                "weight": 0.5,
                "_type": "cyberdeck",
            }, "cyberdeck", "Cyberdeck")
    for a in ammunition_data:
        if a.get("name", "").lower() == item_name_lower or item_name_lower in a.get("name", "").lower():
            return ({
                "name": a["name"],
                "ammo_type": a.get("ammo_type", "Basic"),
                "cost": a.get("cost", 10),
                "_type": "ammo",
                "_ammo_data": a,
            }, "ammo", None)
    return None


class CmdBuy(MuxCommand):
    """
    Buy an item from a merchant, vendor room, or chargen catalog.

    Usage:
      buy <item name> from <merchant>   - Buy from an NPC vendor
      buy <item name>                   - In chargen or vendor room: buy equipment
      buy/cyberware <name>              - Buy body cyberware (implants)
      buy/cyberware pair=<Name> <Name>   - Buy paired Cybereye/Cyberarm/Cyberleg (requires existing, e.g. pair=Cybereye Cybereye)
      buy/cyberware parent=<option>/<parent> - Buy option and attach to parent limb
          (if you have several with that name, e.g. multiple Cybereyes, the emptiest is chosen)
      buy/stash <cyberware>             - Buy cyberware without installing (use with /cyberware)

    Vendor rooms are locations tagged with item categories (e.g. handguns, drugs, cyberware).
    Use 'list' to see what's available. Items over 1000eb require role specialty.
    Role discounts apply.
    """

    key = "buy"
    switches = [("stash", "stash"), ("cyberware", "cyberware"), ("quality", "quality")]
    locks = "cmd:all()"
    help_category = "Economy"

    def parse(self):
        MuxCommand.parse(self)
        # Fallback: if parser put switch in args (e.g. "/cyberware biomonitor"), strip it
        args = (self.args or "").strip()
        for prefix in ("/cyberware ", "cyberware ", "/stash ", "stash "):
            if args.lower().startswith(prefix.lower()):
                self.args = args[len(prefix):].strip()
                break

    def func(self):
        in_chargen = isinstance(self.caller.location, ChargenRoom)
        in_vendor_room = is_vendor_room(self.caller.location)

        if "quality" in (self.switches or []) or (
            self.args and "=" in self.args
            and self.args.split("=", 1)[1].strip().lower() in ("poor", "standard", "excellent")
        ):
            self._buy_weapon_with_quality(in_chargen, in_vendor_room)
            return
        if " from " in self.args:
            # Vendor purchase: buy <item> from <merchant>
            self._buy_from_vendor()
        elif in_chargen and self.args.strip():
            # Chargen purchase: buy <item> (no merchant)
            self._buy_from_chargen()
        elif in_vendor_room and self.args.strip():
            # Tag-based vendor room: buy <item> (no merchant)
            self._buy_from_vendor_room()
        else:
            if in_chargen:
                self.caller.msg(
                    "Usage: buy <item name> - Purchase equipment (weapons, armor, gear, cyberdecks). "
                    "Use buy/cyberware <name> for body cyberware. "
                    "Use buy/cyberware pair=Cybereye Cybereye for paired limbs. "
                    "Use buy/cyberware parent=<option>/<parent> to attach options to a limb. "
                    "Use 'list chargen/weapons', 'list chargen/armor', 'list chargen/gear', "
                    "or 'list chargen/cyberware' to see available items."
                )
            elif in_vendor_room:
                self.caller.msg(
                    "Usage: buy <item name> - Purchase from this vendor. "
                    "Use buy/cyberware <name> for cyberware. "
                    "Use buy/cyberware pair=Cybereye Cybereye for paired limbs. "
                    "Use buy/cyberware parent=<option>/<parent> to attach options to a limb. "
                    "Use 'list' to see available items."
                )
            else:
                self.caller.msg(
                    "Usage: buy <item name> from <merchant> - Purchase from a vendor in your location."
                )
            return

    def _buy_from_vendor_room(self):
        """Handle purchase from tag-based vendor room (no NPC merchant)."""
        item_name = self.args.strip()
        ammo_units = 1
        if "=" in item_name:
            lhs, rhs = item_name.split("=", 1)
            lhs, rhs = lhs.strip(), rhs.strip()
            if rhs.isdigit():
                ammo_units = max(1, int(rhs))
                item_name = lhs
        cyberware_only = "cyberware" in (self.switches or [])
        if cyberware_only and "=" in self.args:
            lhs, rhs = self.args.strip().split("=", 1)
            lhs, rhs = lhs.strip().lower(), rhs.strip()
            if lhs == "pair":
                # Require item name to be explicitly stated: "pair=Cybereye Cybereye" not just "pair=cybereye"
                if " " not in rhs or not rhs.strip():
                    self.caller.msg(
                        "You must explicitly state the item name when buying a paired limb. "
                        "Correct syntax: |wbuy/cyberware pair=Cybereye Cybereye|n "
                        "(or Cyberarm/Cyberleg)."
                    )
                    return
                cyberware_name = rhs.split(None, 1)[0]
                self._buy_cyberware_pair(cyberware_name, chargen_purchase=False)
                return
            if lhs == "parent" and "/" in rhs:
                opt, parent = rhs.split("/", 1)
                self._buy_cyberware_with_parent(opt.strip(), parent.strip(), chargen_purchase=False)
                return
        result = _find_vendor_item(self.caller.location, item_name, cyberware_only=cyberware_only)
        if not result:
            hint = "Use 'buy/cyberware <name>' for cyberware." if not cyberware_only else ""
            self.caller.msg(
                f"'{item_name}' is not available here. Use 'list' to see what's for sale. " + hint
            )
            return

        item, item_type, gear_category = result

        if item_type == "ammo":
            self._buy_ammo_from_vendor(item, ammo_units, chargen_purchase=False)
            return

        if item_type == "cyberware_implant":
            stash = "stash" in (self.switches or [])
            self._buy_cyberware_from_chargen(item, stash=stash)
            return

        merchant_type = item.get("_merchant_type", "gear_merchant")
        base_price = item["value"]
        item_type_for_pricing = "gear" if item_type == "cyberdeck" else item_type

        if is_expensive_item(base_price):
            if not can_purchase_expensive_from_vendor(
                self.caller, base_price, item_type_for_pricing,
                "Cyberdeck" if item_type == "cyberdeck" else gear_category
            ):
                self.caller.msg(
                    f"{item['name']} costs {base_price} eb and is too expensive for vendors to sell. "
                    "Very expensive items can only be purchased in the chargen room, or by Fixer, "
                    "Medtech, Netrunner, Tech, or Nomad within their specialty categories."
                )
                return

        discount = get_purchase_discount_percent(
            self.caller, item_type_for_pricing,
            "Cyberdeck" if item_type == "cyberdeck" else gear_category
        )
        price = calculate_final_price(base_price, discount)

        inventory, _ = Inventory.get_or_create_for_character(self.caller)

        if self._item_exists_in_inventory(inventory, item):
            self.caller.msg(f"You already own {item['name']}.")
            return

        is_fashion = (
            gear_category == "Clothing"
            or (item.get("name") or "").strip() in FASHION_ITEM_NAMES
        )
        fashion_to_spend = 0
        cash_to_spend = 0
        if is_fashion:
            fashion_budget = CharacterMoneyService.get_fashion_budget(self.caller)
            cash_balance = CharacterMoneyService.get_balance(self.caller)
            fashion_to_spend = min(fashion_budget, price)
            cash_to_spend = price - fashion_to_spend
            if fashion_budget + cash_balance < price:
                self.caller.msg(
                    f"You don't have enough for {item['name']}. "
                    f"It costs {price} eb."
                )
                return
            if fashion_to_spend > 0 and not CharacterMoneyService.spend_fashion_money(self.caller, fashion_to_spend):
                self.caller.msg(f"You don't have enough fashion budget.")
                return
            if cash_to_spend > 0 and not CharacterMoneyService.spend_money(self.caller, cash_to_spend):
                if fashion_to_spend > 0:
                    CharacterMoneyService.add_fashion_money(self.caller, fashion_to_spend)
                self.caller.msg(
                    f"You don't have enough Eurodollars for {item['name']}. "
                    f"It costs {price} eb (after {fashion_to_spend} eb from fashion budget)."
                )
                return
        elif not CharacterMoneyService.spend_money(self.caller, price):
            self.caller.msg(
                f"You don't have enough Eurodollars to buy {item['name']}. It costs {price} eb."
            )
            return

        self._add_item_to_inventory(self.caller, item, merchant_type)
        if discount > 0:
            self.caller.msg(
                f"You have purchased {item['name']} for {price} eb "
                f"(base {base_price} eb, {discount}% role discount applied)."
            )
        elif is_fashion and fashion_to_spend > 0 and cash_to_spend > 0:
            self.caller.msg(
                f"You have purchased {item['name']} for {price} eb "
                f"({fashion_to_spend} eb from fashion budget, {cash_to_spend} eb from cash)."
            )
        else:
            self.caller.msg(f"You have purchased {item['name']} for {price} eb.")

    def _buy_from_chargen(self):
        """Handle chargen room purchase - only items 1000eb or under."""
        item_name = self.args.strip()
        ammo_units = 1
        if "=" in item_name:
            lhs, rhs = item_name.split("=", 1)
            lhs, rhs = lhs.strip(), rhs.strip()
            if rhs.isdigit():
                ammo_units = max(1, int(rhs))
                item_name = lhs
        cyberware_only = "cyberware" in (self.switches or [])
        if cyberware_only and "=" in self.args and not (self.args.split("=", 1)[1].strip().isdigit()):
            lhs, rhs = item_name.split("=", 1) if "=" in item_name else (item_name, "")
            lhs, rhs = lhs.strip().lower(), rhs.strip()
            if lhs == "pair":
                # Require item name to be explicitly stated: "pair=Cybereye Cybereye" not just "pair=cybereye"
                if " " not in rhs or not rhs.strip():
                    self.caller.msg(
                        "You must explicitly state the item name when buying a paired limb. "
                        "Correct syntax: |wbuy/cyberware pair=Cybereye Cybereye|n "
                        "(or Cyberarm/Cyberleg)."
                    )
                    return
                cyberware_name = rhs.split(None, 1)[0]
                self._buy_cyberware_pair(cyberware_name, chargen_purchase=True)
                return
            if lhs == "parent" and "/" in rhs:
                opt, parent = rhs.split("/", 1)
                self._buy_cyberware_with_parent(opt.strip(), parent.strip(), chargen_purchase=True)
                return
        result = _find_chargen_item(item_name, cyberware_only=cyberware_only)
        if not result:
            hint = "Use 'buy/cyberware <name>' for body cyberware." if not cyberware_only else ""
            self.caller.msg(
                f"'{item_name}' is not available in the chargen catalog. "
                "Use 'list chargen/weapons', 'list chargen/armor', 'list chargen/gear', "
                "or 'list chargen/cyberware' to see options. " + hint
            )
            return

        item, item_type, gear_category = result

        if item_type == "ammo":
            self._buy_ammo_from_vendor(item, ammo_units, chargen_purchase=True)
            return

        if item_type == "cyberware_implant":
            stash = "stash" in (self.switches or [])
            self._buy_cyberware_from_chargen(item, stash=stash, chargen_purchase=True)
            return

        merchant_type_map = {"weapon": "arms_dealer", "armor": "clothier", "gear": "gear_merchant", "cyberdeck": "cyberdeck_merchant"}
        merchant_type = merchant_type_map.get(item_type) or item.get("_merchant_type", "gear_merchant")

        base_price = item["value"]
        # Chargen purchases use full price - no role discounts
        discount = 0
        price = base_price

        try:
            inventory, _ = Inventory.get_or_create_for_character(self.caller)
        except Exception as e:
            from evennia import logger
            logger.log_err(f"buy chargen: get_or_create_for_character failed: {e}")
            self.caller.msg("Could not access or create your inventory. Please contact staff.")
            return

        if self._item_exists_in_inventory(inventory, item):
            self.caller.msg(f"You already own {item['name']}.")
            return

        # Fashion items (clothing): use fashion budget first, overflow to eurodollars
        is_fashion = (
            gear_category == "Clothing"
            or (item.get("name") or "").strip() in FASHION_ITEM_NAMES
        )
        fashion_to_spend = 0
        cash_to_spend = 0
        if is_fashion:
            fashion_budget = CharacterMoneyService.get_fashion_budget(self.caller)
            cash_balance = CharacterMoneyService.get_balance(self.caller)
            fashion_to_spend = min(fashion_budget, price)
            cash_to_spend = price - fashion_to_spend
            if fashion_budget + cash_balance < price:
                self.caller.msg(
                    f"You don't have enough for {item['name']}. "
                    f"It costs {price} eb. You have {fashion_budget} eb fashion budget and {cash_balance} eb."
                )
                return
            if fashion_to_spend > 0 and not CharacterMoneyService.spend_fashion_money(self.caller, fashion_to_spend):
                self.caller.msg(f"You don't have enough fashion budget. You have {fashion_budget} eb for clothing/fashionware.")
                return
            if cash_to_spend > 0 and not CharacterMoneyService.spend_money(self.caller, cash_to_spend):
                if fashion_to_spend > 0:
                    CharacterMoneyService.add_fashion_budget(self.caller, fashion_to_spend)
                self.caller.msg(
                    f"You don't have enough Eurodollars to buy {item['name']}. "
                    f"It costs {price} eb (after {fashion_to_spend} eb from fashion budget)."
                )
                return
        elif not CharacterMoneyService.spend_money(self.caller, price):
            self.caller.msg(
                f"You don't have enough Eurodollars to buy {item['name']}. "
                f"It costs {price} eb."
            )
            return

        in_chargen = isinstance(self.caller.location, ChargenRoom)
        self._add_item_to_inventory(self.caller, item, merchant_type, chargen_purchase=in_chargen)
        if discount > 0:
            self.caller.msg(
                f"You have purchased {item['name']} for {price} eb "
                f"(base {base_price} eb, {discount}% role discount applied)."
            )
        elif is_fashion and fashion_to_spend > 0 and cash_to_spend > 0:
            self.caller.msg(
                f"You have purchased {item['name']} for {price} eb "
                f"({fashion_to_spend} eb from fashion budget, {cash_to_spend} eb from cash)."
            )
        else:
            self.caller.msg(f"You have purchased {item['name']} for {price} eb.")

    def _buy_bodysculpt_package(self, package_cyberware, chargen_purchase=False):
        """Purchase a bodysculpt package; add all contained cyberware to character."""
        pkg_data = BODYCULPT_PACKAGES.get(package_cyberware.name)
        if not pkg_data:
            self.caller.msg(f"Unknown bodysculpt package: {package_cyberware.name}.")
            return
        try:
            character_sheet = self.caller.character_sheet
        except AttributeError:
            self.caller.msg("No character sheet found for your character.")
            return
        inventory, _ = Inventory.get_or_create_for_character(self.caller)
        base_cost = pkg_data["cost"]
        # Chargen purchases use full price - no role discounts
        discount = 0 if chargen_purchase else get_purchase_discount_percent(self.caller, "cyberware", None)
        final_cost = calculate_final_price(base_cost, discount)
        if not CharacterMoneyService.spend_money(self.caller, final_cost):
            self.caller.msg(
                f"Not enough money for {package_cyberware.name}. It costs {final_cost} eb."
            )
            return
        added = []
        missing = []
        for cw_name in pkg_data["package_contains"]:
            try:
                cw = Cyberware.objects.get(name__iexact=cw_name)
            except Cyberware.DoesNotExist:
                missing.append(cw_name)
                continue
            instance = CyberwareInstance.objects.create(
                cyberware=cw,
                character_sheet=character_sheet,
                installed=True,
            )
            inventory.cyberware.add(instance)
            character_sheet.consume_uninstalled_hl_for_cyberware(cw)
            added.append(cw_name)
            if cw.name.lower() == "cyberarm":
                character_sheet.has_cyberarm = True
        if missing:
            self.caller.msg(
                f"Warning: some package items not found: {', '.join(missing)}. "
                f"Added {len(added)} items."
            )
        character_sheet.refresh_from_db()
        character_sheet.calculate_humanity_loss()
        character_sheet.save()
        if chargen_purchase:
            purchased = inventory.chargen_purchased or []
            purchased.append({"type": "cyberware", "name": package_cyberware.name})
            inventory.chargen_purchased = purchased
            inventory.save()
        if discount > 0:
            self.caller.msg(
                f"You have purchased {package_cyberware.name} for {final_cost} eb "
                f"(base {base_cost} eb, {discount}% discount). Package installed: {len(added)} cyberware items."
            )
        else:
            self.caller.msg(
                f"You have purchased {package_cyberware.name} for {final_cost} eb. "
                f"Package installed: {len(added)} cyberware items."
            )

    def _buy_cyberware_from_chargen(self, item, stash=False, chargen_purchase=False):
        """Handle chargen purchase of body cyberware (from Cyberware model). stash=True = buy without installing."""
        cyberware = item["_cyberware"]
        # Bodysculpt packages: add all package cyberware to character
        if getattr(cyberware, "type", "") == "Bodysculpt Package":
            self._buy_bodysculpt_package(cyberware, chargen_purchase)
            return
        try:
            character_sheet = self.caller.character_sheet
        except AttributeError:
            self.caller.msg("No character sheet found for your character.")
            return
        inventory, _ = Inventory.get_or_create_for_character(self.caller)
        # Popup Melee/Ranged require weapon selection at install - must stash
        cw_lower = cyberware.name.lower()
        if not stash and cw_lower in ("popup melee weapon", "popup ranged weapon"):
            stash = True
            self.caller.msg(
                f"{cyberware.name} requires selecting a weapon when installing. "
                f"Use: cyberware/install \"{cyberware.name}\" = \"<weapon>\" (e.g. Light Melee Weapon, Heavy Pistol)"
            )
        # Pairable items (Cybereye, Cyberarm, Cyberleg): handle 2nd/3rd purchase
        if cw_lower in PAIRABLE_NAMES:
            count = CyberwareInstance.objects.filter(
                character_sheet=character_sheet,
                cyberware__name__in=list(_CYBEREYE_INSTANCE_NAMES) + [
                    "Cyberarm", "Neo-Soviet Cyberarm", "Cyberleg",
                ],
                installed=True,
            ).count()
            # Normalize: only count matching type
            if cw_lower == "cyberleg":
                count = CyberwareInstance.objects.filter(
                    character_sheet=character_sheet,
                    cyberware__name__iexact="Cyberleg",
                    installed=True,
                ).count()
            elif cw_lower in ("cyberarm", "neo-soviet cyberarm"):
                count = CyberwareInstance.objects.filter(
                    character_sheet=character_sheet,
                    cyberware__name__in=["Cyberarm", "Neo-Soviet Cyberarm"],
                    installed=True,
                ).count()
            elif cw_lower in FOUNDATION_EYE_NAME_LOWERS:
                count = CyberwareInstance.objects.filter(
                    character_sheet=character_sheet,
                    cyberware__name__in=_CYBEREYE_INSTANCE_NAMES,
                    installed=True,
                ).count()
            if count == 1:
                self.caller.msg(
                    f"You already have one {cyberware.name}. To add a second (paired), use: "
                    f"|wbuy/cyberware pair={cyberware.name} {cyberware.name}|n"
                )
                return
            if count >= 2 and cw_lower == "cyberleg":
                stash = True
                self.caller.msg(
                    f"You cannot install a third Cyberleg. It will be added to your inventory (uninstalled). "
                    f"You can sell it, transfer it, or refund it. No humanity loss."
                )
            elif count >= 2 and cw_lower in ("cyberarm", "neo-soviet cyberarm"):
                has_asm = CyberwareInstance.objects.filter(
                    character_sheet=character_sheet,
                    cyberware__name__iexact="Artificial Shoulder Mount",
                    installed=True,
                ).exists()
                if not has_asm:
                    stash = True
                    self.caller.msg(
                        f"You need an Artificial Shoulder Mount to install more than two Cyberarms. "
                        f"It will be added to your inventory (uninstalled). "
                        f"Install an Artificial Shoulder Mount first, then use |wcyberware/install {cyberware.name}|n. No humanity loss."
                    )
            elif count >= 2 and cw_lower in FOUNDATION_EYE_NAME_LOWERS:
                has_mom = CyberwareInstance.objects.filter(
                    character_sheet=character_sheet,
                    cyberware__name__iexact="MultiOptic Mount",
                    installed=True,
                ).exists()
                if not has_mom:
                    stash = True
                    self.caller.msg(
                        f"You need a MultiOptic Mount to install more than two Cybereyes. "
                        f"It will be added to your inventory (uninstalled). "
                        f"Install a MultiOptic Mount first, then use |wcyberware/install {cyberware.name}|n. No humanity loss."
                    )
        base_cost = cyberware.cost
        # Chargen purchases use full price - no role discounts
        discount = 0 if chargen_purchase else get_purchase_discount_percent(self.caller, "cyberware", None)
        final_cost = calculate_final_price(base_cost, discount)

        if not stash and not allows_multiples(cyberware) and inventory.cyberware.filter(cyberware=cyberware, installed=True).exists():
            self.caller.msg(f"You already have {cyberware.name} installed.")
            return

        if not stash:
            requirements_met, error_message = check_cyberware_requirements(character_sheet, cyberware)
            if not requirements_met:
                self.caller.msg(error_message)
                return

        type_slots = {
            "Fashionware": 7,
            "Neuralware": 5,
            "Cyberoptics": 3,
            "Cyberaudio": 3,
            "Internal Body Cyberware": 7,
            "External Body Cyberware": 7,
        }
        if not stash and cyberware.type in type_slots:
            installed = inventory.cyberware.filter(
                installed=True, cyberware__type=cyberware.type
            )
            used_slots = sum(cw.cyberware.slots for cw in installed)
            if used_slots + cyberware.slots > type_slots[cyberware.type]:
                self.caller.msg(f"Not enough slots available for {cyberware.type}.")
                return

        # Fashionware: use fashion budget first, overflow to eurodollars
        is_fashionware = getattr(cyberware, "type", "") == "Fashionware"
        fashion_to_spend = 0
        cash_to_spend = 0
        if is_fashionware:
            fashion_budget = CharacterMoneyService.get_fashion_budget(self.caller)
            cash_balance = CharacterMoneyService.get_balance(self.caller)
            fashion_to_spend = min(fashion_budget, final_cost)
            cash_to_spend = final_cost - fashion_to_spend
            if fashion_budget + cash_balance < final_cost:
                self.caller.msg(
                    f"Not enough for {cyberware.name}. "
                    f"It costs {final_cost} eb. You have {fashion_budget} eb fashion budget and {cash_balance} eb."
                )
                return
            if fashion_to_spend > 0 and not CharacterMoneyService.spend_fashion_money(self.caller, fashion_to_spend):
                self.caller.msg(f"You don't have enough fashion budget. You have {fashion_budget} eb for fashionware.")
                return
            if cash_to_spend > 0 and not CharacterMoneyService.spend_money(self.caller, cash_to_spend):
                if fashion_to_spend > 0:
                    CharacterMoneyService.add_fashion_budget(self.caller, fashion_to_spend)
                self.caller.msg(
                    f"Not enough Eurodollars for {cyberware.name}. "
                    f"It costs {final_cost} eb (after {fashion_to_spend} eb from fashion budget)."
                )
                return
        elif not CharacterMoneyService.spend_money(self.caller, final_cost):
            self.caller.msg(
                f"Not enough money to buy {cyberware.name}. It costs {final_cost} eb."
            )
            return

        try:
            instance = CyberwareInstance.objects.create(
                cyberware=cyberware,
                character_sheet=character_sheet,
                installed=not stash,
            )
            inventory.cyberware.add(instance)
            if chargen_purchase:
                purchased = inventory.chargen_purchased or []
                purchased.append({"type": "cyberware", "name": cyberware.name})
                inventory.chargen_purchased = purchased
                inventory.save()
        except Exception as e:
            if is_fashionware:
                if fashion_to_spend > 0:
                    CharacterMoneyService.add_fashion_budget(self.caller, fashion_to_spend)
                if cash_to_spend > 0:
                    CharacterMoneyService.add_money(self.caller, cash_to_spend)
            else:
                CharacterMoneyService.add_money(self.caller, final_cost)
            self.caller.msg(f"Error installing cyberware: {str(e)}")
            return

        if not stash and cyberware.name.lower() == "cyberarm":
            character_sheet.has_cyberarm = True
            character_sheet.save()

        character_sheet.refresh_from_db()
        if not stash:
            character_sheet.consume_uninstalled_hl_for_cyberware(cyberware)
            character_sheet.calculate_humanity_loss()
        character_sheet.save()

        if stash:
            if discount > 0:
                self.caller.msg(
                    f"You have purchased {cyberware.name} (not installed) for {final_cost} eb "
                    f"(base {base_cost} eb, {discount}% Medtech discount applied)."
                )
            elif is_fashionware and fashion_to_spend > 0 and cash_to_spend > 0:
                self.caller.msg(
                    f"You have purchased {cyberware.name} (not installed) for {final_cost} eb "
                    f"({fashion_to_spend} eb from fashion budget, {cash_to_spend} eb from cash)."
                )
            else:
                self.caller.msg(f"You have purchased {cyberware.name} (not installed) for {final_cost} eb.")
        elif discount > 0:
            self.caller.msg(
                f"You have purchased and installed {cyberware.name} for {final_cost} eb "
                f"(base {base_cost} eb, {discount}% Medtech discount applied)."
            )
        elif is_fashionware and fashion_to_spend > 0 and cash_to_spend > 0:
            self.caller.msg(
                f"You have purchased and installed {cyberware.name} for {final_cost} eb "
                f"({fashion_to_spend} eb from fashion budget, {cash_to_spend} eb from cash)."
            )
        else:
            self.caller.msg(f"You have purchased and installed {cyberware.name} for {final_cost} eb.")
        if not stash:
            self.caller.msg(f"Your new humanity is {character_sheet.humanity}.")
            # Keep puppet HP/death save in sync with sheet (effective BODY from cyberware)
            if hasattr(self.caller, "recalculate_derived_stats"):
                self.caller.recalculate_derived_stats()
            try:
                from world.cyberware.implanted_armor import ensure_implanted_armor_for_sheet

                ensure_implanted_armor_for_sheet(character_sheet)
            except Exception:
                pass

    def _buy_cyberware_pair(self, cyberware_name, chargen_purchase=False):
        """Buy a paired second Cybereye/Cyberarm/Cyberleg. Requires existing unpaired instance."""
        name_lower = cyberware_name.lower()
        if name_lower not in PAIRABLE_NAMES:
            self.caller.msg(
                "Only pairable cyberlimbs or cybereyes can be purchased as paired (see |whelp buy|n). "
                "Examples: pair=Cybereye Cybereye, pair=Sponsored Cybereye Sponsored Cybereye, "
                "pair=Cyberarm Cyberarm, pair=Cyberleg Cyberleg."
            )
            return
        if chargen_purchase:
            result = _find_chargen_item(cyberware_name, cyberware_only=True)
        else:
            result = _find_vendor_item(self.caller.location, cyberware_name, cyberware_only=True)
        if not result:
            self.caller.msg(f"'{cyberware_name}' is not available here.")
            return
        item = result[0]
        cyberware = item["_cyberware"]
        try:
            character_sheet = self.caller.character_sheet
        except AttributeError:
            self.caller.msg("No character sheet found.")
            return
        inventory, _ = Inventory.get_or_create_for_character(self.caller)
        # Only pair root-level limbs (not those under MultiOptic/Artificial Shoulder Mount)
        first_instance = inventory.cyberware.filter(
            cyberware__name__iexact=cyberware_name,
            installed=True,
            paired_with__isnull=True,
            parent__isnull=True,
        ).first()
        if not first_instance:
            self.caller.msg(
                f"You don't have an unpaired {cyberware.name} to pair with. "
                "Buy the first one with buy/cyberware <name>."
            )
            return
        if inventory.cyberware.filter(
            cyberware__name__iexact=cyberware_name,
            installed=True,
            paired_with=first_instance,
        ).exists():
            self.caller.msg(f"You already have a paired {cyberware.name}.")
            return
        base_cost = cyberware.cost
        # Chargen purchases use full price - no role discounts
        discount = 0 if chargen_purchase else get_purchase_discount_percent(self.caller, "cyberware", None)
        final_cost = calculate_final_price(base_cost, discount)
        is_fashionware = getattr(cyberware, "type", "") == "Fashionware"
        if is_fashionware:
            fashion_budget = CharacterMoneyService.get_fashion_budget(self.caller)
            cash_balance = CharacterMoneyService.get_balance(self.caller)
            fashion_to_spend = min(fashion_budget, final_cost)
            cash_to_spend = final_cost - fashion_to_spend
            if fashion_budget + cash_balance < final_cost:
                self.caller.msg(f"Not enough for {cyberware.name}. It costs {final_cost} eb.")
                return
            if fashion_to_spend > 0 and not CharacterMoneyService.spend_fashion_money(self.caller, fashion_to_spend):
                return
            if cash_to_spend > 0 and not CharacterMoneyService.spend_money(self.caller, cash_to_spend):
                if fashion_to_spend > 0:
                    CharacterMoneyService.add_fashion_money(self.caller, fashion_to_spend)
                self.caller.msg(f"Not enough Eurodollars for {cyberware.name}.")
                return
        elif not CharacterMoneyService.spend_money(self.caller, final_cost):
            self.caller.msg(f"Not enough money for {cyberware.name}. It costs {final_cost} eb.")
            return
        instance = CyberwareInstance.objects.create(
            cyberware=cyberware,
            character_sheet=character_sheet,
            character_object=self.caller,
            installed=True,
            paired_with=first_instance,
        )
        inventory.cyberware.add(instance)
        character_sheet.consume_uninstalled_hl_for_cyberware(cyberware)
        character_sheet.calculate_humanity_loss()
        if cyberware.name.lower() == "cyberarm":
            character_sheet.has_cyberarm = True
            character_sheet.recalculate_derived_stats()
        if chargen_purchase:
            purchased = inventory.chargen_purchased or []
            purchased.append({"type": "cyberware", "name": cyberware.name, "paired": True})
            inventory.chargen_purchased = purchased
            inventory.save()
        self.caller.msg(
            f"You have purchased and installed {cyberware.name} (paired) for {final_cost} eb."
        )
        self.caller.msg(f"Your new humanity is {character_sheet.humanity}.")

    def _buy_cyberware_with_parent(self, option_name, parent_name, chargen_purchase=False):
        """Buy a cyberware option and attach it to an existing parent limb."""
        if chargen_purchase:
            result = _find_chargen_item(option_name, cyberware_only=True)
        else:
            result = _find_vendor_item(self.caller.location, option_name, cyberware_only=True)
        if not result:
            self.caller.msg(f"'{option_name}' is not available here.")
            return
        item = result[0]
        cyberware = item["_cyberware"]
        try:
            character_sheet = self.caller.character_sheet
        except AttributeError:
            self.caller.msg("No character sheet found.")
            return
        requirements_met, error_message = check_cyberware_requirements(character_sheet, cyberware)
        if not requirements_met:
            self.caller.msg(error_message)
            return
        inventory, _ = Inventory.get_or_create_for_character(self.caller)
        parent_candidates = list(inventory.cyberware.filter(
            cyberware__name__iexact=parent_name,
            installed=True,
        ).select_related("cyberware"))
        if not parent_candidates:
            self.caller.msg(f"You don't have {parent_name} installed. Install the parent limb first.")
            return
        # For Cyberaudio Suite: try main suite first, then Sensor Array when full
        parent_inst = None
        if parent_name.lower() in ("cyberaudio suite", "discount cyberaudio suite"):
            parent_inst, err = find_best_cyberaudio_parent(character_sheet, cyberware)
            if err:
                self.caller.msg(err)
                return
        # For Chipware Socket / Budget Chipware Socket: find one with available slots
        elif parent_name.lower() in ("chipware socket", "budget chipware socket"):
            for cand in parent_candidates:
                ok, _ = validate_parent_for_new_child(cand, cyberware)
                if ok:
                    parent_inst = cand
                    break
        if parent_inst is None:
            parent_inst, err = select_balanced_parent_instance(parent_candidates, cyberware)
            if err:
                self.caller.msg(err)
                return
        base_cost = cyberware.cost
        # Chargen purchases use full price - no role discounts
        discount = 0 if chargen_purchase else get_purchase_discount_percent(self.caller, "cyberware", None)
        final_cost = calculate_final_price(base_cost, discount)
        is_fashionware = getattr(cyberware, "type", "") == "Fashionware"
        if is_fashionware:
            fashion_budget = CharacterMoneyService.get_fashion_budget(self.caller)
            cash_balance = CharacterMoneyService.get_balance(self.caller)
            fashion_to_spend = min(fashion_budget, final_cost)
            cash_to_spend = final_cost - fashion_to_spend
            if fashion_budget + cash_balance < final_cost:
                self.caller.msg(f"Not enough for {cyberware.name}. It costs {final_cost} eb.")
                return
            if fashion_to_spend > 0 and not CharacterMoneyService.spend_fashion_money(self.caller, fashion_to_spend):
                return
            if cash_to_spend > 0 and not CharacterMoneyService.spend_money(self.caller, cash_to_spend):
                if fashion_to_spend > 0:
                    CharacterMoneyService.add_fashion_money(self.caller, fashion_to_spend)
                self.caller.msg(f"Not enough Eurodollars for {cyberware.name}.")
                return
        elif not CharacterMoneyService.spend_money(self.caller, final_cost):
            self.caller.msg(f"Not enough money for {cyberware.name}. It costs {final_cost} eb.")
            return
        instance = CyberwareInstance.objects.create(
            cyberware=cyberware,
            character_sheet=character_sheet,
            character_object=self.caller,
            installed=True,
            parent=parent_inst,
        )
        inventory.cyberware.add(instance)
        character_sheet.consume_uninstalled_hl_for_cyberware(cyberware)
        character_sheet.calculate_humanity_loss()
        if chargen_purchase:
            purchased = inventory.chargen_purchased or []
            purchased.append({"type": "cyberware", "name": cyberware.name})
            inventory.chargen_purchased = purchased
            inventory.save()
        actual_parent = parent_inst.cyberware.name if parent_inst and parent_inst.cyberware else parent_name
        self.caller.msg(
            f"You have purchased and installed {cyberware.name} (on {actual_parent}) for {final_cost} eb."
        )
        self.caller.msg(f"Your new humanity is {character_sheet.humanity}.")

    def _buy_from_vendor(self):
        """Handle vendor purchase - block items over 1000eb unless role allows."""
        item_name, merchant_name = self.args.split(" from ", 1)
        item_name = item_name.strip().lower()
        merchant_name = merchant_name.strip().lower()

        merchants = [
            obj for obj in self.caller.location.contents
            if obj.is_typeclass("world.cyberpunk_sheets.merchants.Merchant")
            and merchant_name in obj.name.lower()
        ]
        if not merchants:
            self.caller.msg(f"There's no merchant named '{merchant_name}' here.")
            return
        merchant = merchants[0]

        item = merchant.get_item(item_name)
        if not item:
            self.caller.msg(f"Sorry, {item_name} is not available from this merchant.")
            return

        try:
            inventory, _ = Inventory.get_or_create_for_character(self.caller)
        except Exception as e:
            from evennia import logger
            logger.log_err(f"buy from vendor: get_or_create_for_character failed: {e}")
            self.caller.msg("Could not access or create your inventory. Please contact staff.")
            return

        if self._item_exists_in_inventory(inventory, item):
            self.caller.msg(f"You already own {item['name']}.")
            return

        base_price = item['value']
        merchant_type = merchant.db.merchant_type

        item_type = (
            "weapon" if merchant_type == "arms_dealer"
            else "armor" if merchant_type == "clothier"
            else "vehicle" if merchant_type == "vehicle_dealer"
            else "gear"
        )
        gear_category = item.get("category") if item_type == "gear" else None

        if is_expensive_item(base_price):
            if not can_purchase_expensive_from_vendor(self.caller, base_price, item_type, gear_category):
                self.caller.msg(
                    f"{item['name']} costs {base_price} eb and is too expensive for vendors to sell. "
                    "Very expensive items can only be purchased in the chargen room, or by Fixer, "
                    "Medtech, Netrunner, Tech, or Nomad within their specialty categories."
                )
                return

        discount = get_purchase_discount_percent(self.caller, item_type, gear_category)
        price = calculate_final_price(base_price, discount)

        if not CharacterMoneyService.spend_money(self.caller, price):
            self.caller.msg(
                f"You don't have enough Eurodollars to buy {item['name']}. It costs {price} eb."
            )
            return

        resolved_item = dict(item)
        if merchant_type == "arms_dealer":
            resolved_item = resolve_weapon_for_inventory(
                dict(item),
                quality=(item.get("quality") or "standard"),
                paid_value=price,
                source_note="Vendor purchase",
            )
        self._add_item_to_inventory(self.caller, resolved_item, merchant_type)
        display_name = resolved_item.get("name", item["name"])
        if discount > 0:
            self.caller.msg(
                f"You have purchased {display_name} for {price} eb "
                f"(base {base_price} eb, {discount}% role discount applied)."
            )
        else:
            self.caller.msg(f"You have purchased {display_name} for {price} eb.")

    def get_character_inventory(self, character):
        """Get a character's inventory, checking typeclass first, then character sheet"""
        # Try to get inventory via typeclass attribute
        if hasattr(character, 'db') and hasattr(character.db, 'inventory'):
            return character.db.inventory
            
        # Try to get inventory via inventory_object relation
        if hasattr(character, 'inventory_object'):
            return character.inventory_object
            
        # Fall back to character sheet
        if hasattr(character, 'character_sheet') and character.character_sheet:
            return character.character_sheet.inventory
            
        return None

    def _item_exists_in_inventory(self, inventory, item):
        """Check if the item already exists in the character's inventory."""
        item_name = item['name'].lower()
        
        # Check weapons
        if inventory.weapons.filter(name__iexact=item_name).exists():
            return True
        
        # Check armor
        if inventory.armor.filter(name__iexact=item_name).exists():
            return True
        
        # Check gear
        if inventory.gear.filter(name__iexact=item_name).exists():
            return True

        # Check vehicles
        if inventory.vehicles.filter(name__iexact=item_name).exists():
            return True
        
        return False

    def _add_item_to_inventory(self, character, item, merchant_type, chargen_purchase=False):
        # Get or create character's inventory (creates if missing, e.g. during chargen)
        inventory, _ = Inventory.get_or_create_for_character(character)
        
        if merchant_type == "arms_dealer":
            from world.weapon_constants import DEFAULT_RANGED_ATTACHMENT_SLOTS
            clip = item.get('clip', 0)
            slots = item.get('attachment_slots')
            if slots is None and item.get('category') in ('handgun', 'shoulder_arms', 'heavy_weapons'):
                slots = DEFAULT_RANGED_ATTACHMENT_SLOTS
            weapon, created = Weapon.objects.get_or_create(
                name=item['name'],
                defaults={
                    'damage': item['damage'],
                    'rof': item['rof'],
                    'hands': item['hands'],
                    'concealable': item['concealable'],
                    'weight': item['weight'],
                    'value': item['value'],
                    'category': item.get('category', 'handgun'),
                    'quality': item.get('quality', 'standard'),
                    'weapon_type': item.get('weapon_type', ''),
                    'ammo_type': item.get('ammo_type', 'Basic'),
                    'clip': clip,
                    'max_ammo': clip,
                    'current_ammo': 0,
                    'attachment_slots': slots or 0,
                    'description': item.get('description', ''),
                }
            )
            inventory.weapons.add(weapon)
        elif merchant_type == "clothier":
            armor, created = Armor.objects.get_or_create(
                name=item['name'],
                defaults={
                    'sp': item['sp'],
                    'ev': item['ev'],
                    'locations': item['locations'],
                    'weight': item['weight'],
                    'value': item['value']
                }
            )
            inventory.armor.add(armor)
        elif merchant_type == "gear_merchant":
            gear, created = Gear.objects.get_or_create(
                name=item['name'],
                defaults={
                    'category': item['category'],
                    'description': item.get('description', ''),
                    'weight': item['weight'],
                    'value': item['value']
                }
            )
            inventory.add_gear(gear)
        elif merchant_type == "vehicle_dealer":
            vehicle_model, _ = VehicleModel.objects.get_or_create(
                name=item['name'],
                defaults={
                    'description': item.get('description', ''),
                    'category': item.get('category', 'land'),
                    'sdp': item.get('sdp', 35),
                    'seats': item.get('seats', 2),
                    'speed_combat': item.get('speed_combat', 20),
                    'speed_narrative': item.get('speed_narrative', ''),
                    'value': item['value'],
                }
            )
            inventory.vehicles.add(vehicle_model)
        elif merchant_type == "cyberdeck_merchant":
            gear, created = Gear.objects.get_or_create(
                name=item['name'],
                defaults={
                    'category': 'Cyberdeck',
                    'description': item.get('description', ''),
                    'weight': item.get('weight', 0.5),
                    'value': item['value'],
                }
            )
            inventory.add_gear(gear)

        if chargen_purchase:
            type_map = {
                "arms_dealer": "weapon",
                "clothier": "armor",
                "gear_merchant": "gear",
                "cyberdeck_merchant": "gear",
                "vehicle_dealer": "vehicle",
            }
            item_type = type_map.get(merchant_type, "gear")
            purchased = inventory.chargen_purchased or []
            purchased.append({"type": item_type, "name": item["name"]})
            inventory.chargen_purchased = purchased
            inventory.save()

    def _buy_ammo_from_vendor(self, item, units, chargen_purchase=False):
        """Buy ammunition. Each unit = 10 rounds. cost is per 10 rounds."""
        cost_per_unit = item.get("cost", 10)
        total_cost = cost_per_unit * units
        rounds = units * 10
        ammo_type = item.get("ammo_type", "Basic")
        ammo_name = item.get("name", "")
        if chargen_purchase:
            total_cost = cost_per_unit * units
        else:
            discount = get_purchase_discount_percent(self.caller, "gear", None)
            total_cost = calculate_final_price(total_cost, discount)
        if not CharacterMoneyService.spend_money(self.caller, total_cost):
            self.caller.msg(f"You need {total_cost} eb for {rounds} rounds of {ammo_name}.")
            return
        inventory, _ = Inventory.get_or_create_for_character(self.caller)
        existing = inventory.ammunition.filter(ammo_type=ammo_type).first()
        if existing:
            existing.quantity += rounds
            existing.save()
        else:
            ammo = Ammunition.objects.create(
                name=ammo_name,
                ammo_type=ammo_type,
                quantity=rounds,
                cost=cost_per_unit,
                weapon_type=item.get("weapon_type", "Generic"),
            )
            inventory.ammunition.add(ammo)
        self.caller.msg(f"You purchased {rounds} rounds of {ammo_name} for {total_cost} eb.")

    def _get_quality_price(self, base_value, quality):
        """Get price for weapon with quality. Uses weapon_constants.get_quality_price."""
        from world.weapon_constants import get_quality_price
        return get_quality_price(base_value, quality)

    def _buy_weapon_with_quality(self, in_chargen, in_vendor_room):
        """buy/quality <weapon>=<quality> or buy <weapon>=<quality> - Buy weapon with Poor/Standard/Excellent.
        Standard-quality weapons can be bought at any quality. Fixed-quality weapons only at their quality."""
        if not self.args:
            self.caller.msg("Usage: buy <weapon> [=poor|standard|excellent] or buy/quality <weapon>=<quality>")
            return
        weapon_name = self.args.strip()
        quality = None
        if "=" in weapon_name:
            weapon_name, quality = weapon_name.split("=", 1)
            weapon_name = weapon_name.strip()
            quality = quality.strip().lower() if quality else None
        if quality and quality not in ("poor", "standard", "excellent"):
            self.caller.msg("Quality must be Poor, Standard, or Excellent.")
            return

        # Find weapon in equipment_data (fuzzy match)
        base_weapon = None
        for w in weapons:
            if (w.get("name") or "").lower() == weapon_name.lower():
                base_weapon = dict(w)
                break
        if not base_weapon:
            # Fuzzy: startswith
            for w in weapons:
                if (w.get("name") or "").lower().startswith(weapon_name.lower()):
                    base_weapon = dict(w)
                    break
        if not base_weapon:
            self.caller.msg(f"'{weapon_name}' is not available.")
            return

        base_quality = (base_weapon.get("quality") or "standard").strip().lower()
        if quality is None:
            quality = base_quality

        # Fixed-quality weapons: only that quality
        if base_quality in ("poor", "excellent"):
            if quality != base_quality:
                self.caller.msg(
                    f"{base_weapon.get('name')} is only available in {base_quality} quality."
                )
                return
            quality = base_quality

        base_value = base_weapon.get("value", 0)
        price = self._get_quality_price(base_value, quality)

        if not (in_chargen or in_vendor_room):
            self.caller.msg("Weapon purchase is only available in chargen or vendor rooms.")
            return

        if in_vendor_room:
            filters = get_vendor_catalog_filters(self.caller.location)
            item_info = {"_type": "weapon", "category": base_weapon.get("category")}
            if not item_matches_vendor_filters(item_info, filters):
                self.caller.msg(f"'{base_weapon.get('name')}' is not available at this vendor.")
                return

        if not CharacterMoneyService.spend_money(self.caller, price):
            self.caller.msg(f"You need {price} eb for {base_weapon.get('name')} ({quality} quality).")
            return

        inventory, _ = Inventory.get_or_create_for_character(self.caller)
        merged = dict(base_weapon)
        merged["quality"] = quality
        resolved = resolve_weapon_for_inventory(
            merged,
            quality=quality,
            paid_value=price,
            source_note="Purchase",
        )
        from world.weapon_constants import DEFAULT_RANGED_ATTACHMENT_SLOTS
        clip = int(resolved.get("clip", 0))
        slots = resolved.get("attachment_slots")
        if slots is None and resolved.get("category") in ("handgun", "shoulder_arms", "heavy_weapons"):
            slots = DEFAULT_RANGED_ATTACHMENT_SLOTS
        weapon = Weapon.objects.create(
            name=resolved["name"],
            damage=resolved.get("damage", "2d6"),
            rof=resolved.get("rof", "1"),
            hands=resolved.get("hands", 1),
            concealable=resolved.get("concealable", False),
            weight=resolved.get("weight", 1),
            value=price,
            category=resolved.get("category", "handgun"),
            quality=quality,
            weapon_type=resolved.get("weapon_type", ""),
            ammo_type=resolved.get("ammo_type", "Basic"),
            clip=clip,
            max_ammo=clip,
            current_ammo=0,
            attachment_slots=int(slots or 0),
            description=resolved.get("description", ""),
        )
        inventory.weapons.add(weapon)
        if in_chargen:
            purchased = inventory.chargen_purchased or []
            purchased.append({"type": "weapon", "name": resolved["name"]})
            inventory.chargen_purchased = purchased
            inventory.save()
        qual_str = f" ({quality} quality)" if quality != "standard" else ""
        self.caller.msg(f"You purchased {weapon.name}{qual_str} for {price} eb.")


class CmdRefund(MuxCommand):
    """
    Refund a gear purchase made during character generation.

    Usage:
      refund <item name>           - Refund a purchased weapon, armor, or gear
      refund/cyberware <name>     - Refund purchased cyberware

    Only works in the chargen room. You can refund items you bought with 'buy'
    during chargen and receive eurodollars back (up to your allotment: 500 eb
    for edgerunner, 2550 eb for complete package). Items provided by your role
    package (edgerunner chargen) cannot be refunded.
    """

    key = "refund"
    switches = [("cyberware", "cyberware")]
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        if not isinstance(self.caller.location, ChargenRoom):
            self.caller.msg("Refunds are only available in the character generation room.")
            return

        if self.caller.tags.has("approved", category="approval"):
            self.caller.msg("Your character is already approved. Refunds are only during chargen.")
            return

        item_name = (self.args or "").strip()
        if not item_name:
            self.caller.msg("Usage: refund <item name> or refund/cyberware <name>")
            return

        cyberware_only = "cyberware" in (self.switches or [])
        inventory, _ = Inventory.get_or_create_for_character(self.caller)
        purchased = list(inventory.chargen_purchased or [])

        # Find a matching chargen purchase
        item_name_lower = item_name.lower()
        match_idx = None
        match_type = None
        for i, entry in enumerate(purchased):
            if entry.get("name", "").lower() == item_name_lower:
                etype = entry.get("type", "")
                if cyberware_only and etype == "cyberware":
                    match_idx = i
                    match_type = "cyberware"
                    break
                if not cyberware_only and etype in ("weapon", "armor", "gear", "vehicle"):
                    match_idx = i
                    match_type = etype
                    break
        if cyberware_only and match_type != "cyberware":
            match_idx = None
        elif not cyberware_only and match_type == "cyberware":
            match_idx = None

        if match_idx is None:
            hint = "Use refund/cyberware <name> for cyberware." if not cyberware_only else ""
            self.caller.msg(
                f"'{item_name}' was not purchased during chargen, or you don't have it. "
                f"Only items you bought with 'buy' can be refunded; role package items cannot. " + hint
            )
            return

        # Remove from chargen_purchased
        purchased.pop(match_idx)
        inventory.chargen_purchased = purchased
        inventory.save()

        # Get refund value and remove item from inventory
        refund_value = 0
        if match_type == "weapon":
            weapon = inventory.weapons.filter(name__iexact=item_name).first()
            if weapon:
                refund_value = weapon.value
                inventory.weapons.remove(weapon)
        elif match_type == "armor":
            armor = inventory.armor.filter(name__iexact=item_name).first()
            if armor:
                refund_value = armor.value
                inventory.armor.remove(armor)
        elif match_type == "gear":
            gear = inventory.gear.filter(name__iexact=item_name).first()
            if gear:
                refund_value = gear.value
                inventory.gear.remove(gear)
        elif match_type == "vehicle":
            vehicle = inventory.vehicles.filter(name__iexact=item_name).first()
            if vehicle:
                refund_value = vehicle.value
                inventory.vehicles.remove(vehicle)
        elif match_type == "cyberware":
            instance = inventory.cyberware.filter(cyberware__name__iexact=item_name).first()
            if instance:
                refund_value = instance.cyberware.cost
                inventory.cyberware.remove(instance)
                instance.delete()

        if refund_value == 0:
            # Item wasn't in inventory (shouldn't happen) - restore the purchase record
            purchased.append({"type": match_type, "name": item_name})
            inventory.chargen_purchased = purchased
            inventory.save()
            self.caller.msg(f"Could not find '{item_name}' in your inventory.")
            return

        # Cap refund at allotment (500 edgerunner, 2550 complete package)
        method = (getattr(self.caller.db, "chargen_method", None) or "").strip().lower()
        allotment = (
            CHARGEN_EURODOLLARS_EDGERUNNER
            if method == "edgerunner"
            else CHARGEN_EURODOLLARS_COMPLETE_PACKAGE
        )
        current = CharacterMoneyService.get_balance(self.caller)
        refund_amount = min(refund_value, allotment - current)
        if refund_amount <= 0:
            self.caller.msg(
                f"You have reached your eurodollar allotment ({allotment} eb). "
                f"No refund added, but '{item_name}' has been removed from your inventory."
            )
        else:
            CharacterMoneyService.add_money(self.caller, refund_amount)
            self.caller.msg(
                f"You have refunded {item_name} and received {refund_amount} eb. "
                f"Your balance is now {current + refund_amount} eb."
            )


class CmdListItems(MuxCommand):
    """
    List items available from a merchant, vendor room, or chargen catalog.

    Usage:
      list                            - In vendor room: show category menu
      list <category>                 - In vendor room: list weapons, handguns, cyberware, etc.
      list from <merchant>            - List from NPC vendor
      list chargen                    - In chargen: show category menu
      list chargen/weapons            - All weapons (or list chargen weapons)
      list chargen/gear               - All gear
      list chargen/medical            - Gear in Medical category
      list chargen/shoulder_arms      - Weapons in shoulder_arms category
      list chargen/search <string>    - Search chargen catalog (in chargen room)
      list/search <string>            - Search equipment (or vendor catalog if in vendor room)
      list/search chargen <string>    - Search chargen catalog (1000 eb or under)
      list/info <item>                - Detailed info on an item

    Vendor rooms use +room/tag with categories like handguns, drugs, cyberware, ranged, melee.
    """

    key = "list"
    aliases = ["list items"]
    locks = "cmd:all()"
    help_category = "Economy"
    arg_regex = r"[\s/]|$"  # Allow / for list/info

    def parse(self):
        MuxCommand.parse(self)

    def func(self):
        # list/search [chargen] <string> - search equipment
        if "search" in (self.switches or []):
            raw = (self.args or "").strip()
            if is_vendor_room(self.caller.location) and raw:
                self._list_vendor_search(raw)
                return
            chargen_only = False
            if raw.lower().startswith("chargen"):
                rest = raw[7:].lstrip(" /")
                if rest:
                    chargen_only = True
                    raw = rest
            if not raw:
                self.caller.msg("Usage: list/search <string> or list/search chargen <string>")
                return
            self.caller.msg("\n".join(format_search_equipment(raw, chargen_only=chargen_only)))
            return

        # list/info <item> or list/info chargen/<item>
        if "info" in (self.switches or []):
            item_name = (self.args or "").strip()
            if item_name.lower().startswith("chargen/"):
                item_name = item_name[8:].strip()
            if not item_name:
                self.caller.msg("Usage: list/info <item name> or list/info chargen/<item name>")
                return
            source, data = _find_item_info(item_name)
            if not data:
                self.caller.msg(f"Item '{item_name}' not found. Try |wlist chargen|n or |wequipdb/search <name>|n.")
                return
            self.caller.msg("\n".join(format_item_info(source, data)))
            return

        in_chargen = isinstance(self.caller.location, ChargenRoom)
        in_vendor_room = is_vendor_room(self.caller.location)

        if not self.args:
            if in_vendor_room:
                self._list_vendor_menu()
                return
            if in_chargen:
                self.caller.msg(
                    "Usage: list chargen | list chargen/weapons | list chargen/armor | "
                    "list chargen/gear | list chargen/cyberware"
                )
            else:
                self.caller.msg(
                    "Usage: list from <merchant> | list chargen/weapons | list chargen/armor | "
                    "list chargen/gear | list chargen/cyberware"
                )
            return

        args = self.args.strip().lower()

        # Vendor room: list, list weapons, list handguns, etc. (list/search handled above)
        if in_vendor_room and " from " not in args:
            self._list_vendor(args)
            return

        if in_chargen and (args == "chargen" or args.startswith("chargen/") or args.startswith("chargen ")):
            if "/" in args:
                _, sub = args.split("/", 1)
                sub = sub.strip()
            elif args.startswith("chargen "):
                sub = args[8:].strip()  # "chargen gear" -> "gear"
            else:
                sub = None
            # list chargen/search <string>
            if sub and sub.lower().startswith("search"):
                search_str = sub[6:].strip()
                if search_str:
                    self.caller.msg("\n".join(format_search_equipment(search_str, chargen_only=True)))
                else:
                    self.caller.msg("Usage: list chargen/search <string>")
                return
            self._list_chargen(sub)
            return

        if args.startswith("items from "):
            merchant_name = args[11:]
        elif args.startswith("from "):
            merchant_name = args[5:]
        else:
            self.caller.msg("Usage: list from <merchant> or list items from <merchant>")
            return

        merchants = search_object(merchant_name)
        merchants = [
            obj for obj in merchants
            if obj.typeclass_path == "world.cyberpunk_sheets.merchants.Merchant"
        ]

        if not merchants:
            self.caller.msg(f"There's no merchant named '{merchant_name}' found.")
            return

        merchant = merchants[0]
        if merchant.location != self.caller.location:
            self.caller.msg(f"{merchant.name} is not here. They are located in {merchant.location}.")
            return

        items = merchant.list_items()
        if items:
            self.caller.msg(f"Items available from {merchant.name}:")
            for item in items:
                self.caller.msg(item)
        else:
            self.caller.msg(f"No items available from {merchant.name}.")

    def _list_chargen(self, category=None):
        """List items in the chargen catalog (value <= 1000 eb), formatted like equipdb.
        category=None shows a menu. category can be main (weapons/armor/gear/cyberware)
        or subcategory (medical, shoulder_arms, etc.)."""
        main_cats = ("weapons", "armor", "gear", "cyberware")
        subcats = _get_chargen_subcategories()

        if not category:
            self._list_chargen_menu(main_cats, subcats)
            return

        # Resolve: is category a main category or a subcategory?
        cat_lower = category.lower().replace(" ", "_")
        main_cat = None
        subcategory = None

        if cat_lower in main_cats:
            main_cat = cat_lower
        else:
            # Try to find which main category this subcategory belongs to
            cat_norm = cat_lower.replace(" ", "_")
            for mc in main_cats:
                for sc in subcats[mc]:
                    if sc.lower().replace(" ", "_") == cat_norm:
                        main_cat = mc
                        subcategory = sc
                        break
                if main_cat:
                    break

        if not main_cat:
            self.caller.msg(
                f"Unknown category '{category}'. Use |wlist chargen|n to see available categories."
            )
            return

        catalog = _get_chargen_catalog(main_cat, subcategory)
        if not catalog:
            label = f"{subcategory or main_cat}" if subcategory else main_cat
            self.caller.msg(f"No {label} items available in the chargen catalog (1000 eb or under).")
            return

        display_label = f"{subcategory} ({main_cat})" if subcategory else main_cat.title()
        output = []
        output.append(header(f"Chargen Catalog: {display_label} (1000 eb or under)"))

        if main_cat == "weapons":
            output.append(self._format_chargen_weapons(catalog))
        elif main_cat == "armor":
            output.append(self._format_chargen_armor(catalog))
        elif main_cat == "gear":
            gears = [e for e in catalog if e.get("_type") == "gear"]
            cyberdecks = [e for e in catalog if e.get("_type") == "cyberdeck"]
            if gears:
                output.append(self._format_chargen_gear(gears))
            if cyberdecks:
                output.append(self._format_chargen_cyberdecks(cyberdecks))
        elif main_cat == "cyberware":
            output.append(self._format_chargen_cyberware(catalog))
            output.append(
                "|wCyberware pairs:|n buy/cyberware pair=Cybereye Cybereye | "
                "|wAttach option:|n buy/cyberware parent=Image Enhance/Cybereye"
            )

        output.append(footer())
        self.caller.msg("\n".join(filter(None, output)))

    def _list_chargen_menu(self, main_cats, subcats):
        """Show chargen category menu with subcategories."""
        output = []
        output.append(header("Chargen Catalog (1000 eb or under)"))
        output.append("The following equipment types can be used when looking at possible items for")
        output.append("purchase during character generation. Note that these commands can only be")
        output.append("used |rPRE-APPROVAL|n. If you are approved, you will not be able to access these")
        output.append("commands. Make sure you have done this before completing character generation")
        output.append("and submitting your character.")
        output.append("|b-----------------------------------------------------------------------------|n")
        output.append("Use |wlist chargen <category>|n or |wlist chargen/<category>|n to browse.\n")
        for mc in main_cats:
            subs = sorted(subcats.get(mc, []))
            if subs:
                sub_links = " | ".join(f"|w{s.lower().replace(' ', '_')}|n" for s in subs)
                output.append(f"  |y{mc.title()}|n: {sub_links}")
                output.append(f"      Or |w{mc}|n for all")
            else:
                output.append(f"  |y{mc.title()}|n: |w{mc}|n")
        output.append("")
        output.append("Examples: |wlist chargen gear|n  |wlist chargen medical|n  |wlist chargen/search pistol|n")
        output.append("          |wlist/search pistol|n  |wlist/info Medium Pistol|n")
        output.append("          |wlist/info constitutional arms multi|n  (fuzzy string matching)")
        output.append(footer())
        self.caller.msg("\n".join(output))

    def _list_vendor_menu(self):
        """Show vendor category menu based on room tags."""
        main_cats = get_available_main_categories(self.caller.location)
        if not main_cats:
            self.caller.msg("This location doesn't have any vendor categories configured.")
            return
        subcats = _get_vendor_subcategories(self.caller.location)
        output = []
        output.append(header("Vendor Catalog"))
        output.append("Items available at this location. Use |wlist <category>|n to browse.")
        output.append("|b-----------------------------------------------------------------------------|n")
        for mc in main_cats:
            subs = sorted(subcats.get(mc, []))
            if subs:
                sub_links = " | ".join(f"|w{s.lower().replace(' ', '_')}|n" for s in subs)
                output.append(f"  |y{mc.title()}|n: {sub_links}")
                output.append(f"      Or |w{mc}|n for all")
            else:
                output.append(f"  |y{mc.title()}|n: |w{mc}|n")
        output.append("")
        output.append("Examples: |wlist weapons|n  |wlist handguns|n  |wlist cyberware|n  |wlist/search pistol|n")
        output.append(footer())
        self.caller.msg("\n".join(output))

    def _list_vendor(self, category):
        """List items in vendor room by category."""
        main_cats = get_available_main_categories(self.caller.location)
        subcats = _get_vendor_subcategories(self.caller.location)
        cat_lower = category.lower().replace(" ", "_")
        main_cat = None
        subcategory = None
        if cat_lower in main_cats:
            main_cat = cat_lower
        else:
            for mc in main_cats:
                for sc in subcats.get(mc, []):
                    if sc.lower().replace(" ", "_") == cat_lower:
                        main_cat = mc
                        subcategory = sc
                        break
                if main_cat:
                    break
        if not main_cat:
            self.caller.msg(
                f"Unknown category '{category}'. Use |wlist|n to see available categories."
            )
            return
        catalog = _get_vendor_catalog(self.caller.location, main_cat, subcategory)
        if not catalog:
            label = f"{subcategory or main_cat}" if subcategory else main_cat
            self.caller.msg(f"No {label} items available here.")
            return
        display_label = f"{subcategory} ({main_cat})" if subcategory else main_cat.title()
        output = []
        output.append(header(f"Vendor: {display_label}"))
        if main_cat == "weapons":
            output.append(self._format_chargen_weapons(catalog))
        elif main_cat == "armor":
            output.append(self._format_chargen_armor(catalog))
        elif main_cat == "gear":
            gears = [e for e in catalog if e.get("_type") == "gear"]
            cyberdecks = [e for e in catalog if e.get("_type") == "cyberdeck"]
            if gears:
                output.append(self._format_chargen_gear(gears))
            if cyberdecks:
                output.append(self._format_chargen_cyberdecks(cyberdecks))
        elif main_cat == "cyberware":
            output.append(self._format_chargen_cyberware(catalog))
        output.append(footer())
        self.caller.msg("\n".join(filter(None, output)))

    def _list_vendor_search(self, search_str):
        """Search vendor catalog and display results."""
        catalog = _get_vendor_catalog(self.caller.location)
        q = search_str.lower()
        matches = [
            item for item in catalog
            if q in (item.get("name") or "").lower()
            or q in (item.get("category") or "").lower()
            or q in (str(item.get("description", "") or "").lower())
        ]
        if not matches:
            self.caller.msg(f"No items matching '{search_str}' at this vendor.")
            return
        output = []
        output.append(header(f"Vendor Search: {search_str}"))
        weapons = [m for m in matches if m.get("_type") == "weapon"]
        armor = [m for m in matches if m.get("_type") == "armor"]
        gear = [m for m in matches if m.get("_type") in ("gear", "cyberdeck")]
        cyberware = [m for m in matches if m.get("_type") == "cyberware_implant" or m.get("category") == "Cyberware"]
        if weapons:
            output.append(self._format_chargen_weapons(weapons))
        if armor:
            output.append(self._format_chargen_armor(armor))
        if gear:
            output.append(self._format_chargen_gear(gear))
        if cyberware:
            output.append(self._format_chargen_cyberware(cyberware))
        output.append(footer())
        self.caller.msg("\n".join(filter(None, output)))

    def _format_chargen_weapons(self, catalog):
        """Format weapons like equipdb."""
        out = [section_header("Weapons", width=78)]
        for w in catalog:
            name = w.get("name", "?")
            damage = w.get("damage", "?")
            rof = w.get("rof", "?")
            hands = w.get("hands", "?")
            value = w.get("value", 0)
            cat = w.get("category", "?")
            conceal = "Yes" if w.get("concealable") else "No"
            weight = w.get("weight", "?")
            nm = crop(name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gDamage:|n {str(damage):<8} |gROF:|n {str(rof):<4} |gHands:|n {hands} |gValue:|n |y{value} eb|n")
            out.append(f"  |gCategory:|n {str(cat):<14} |gConceal:|n {conceal} |gWeight:|n {weight}")
        out.append(section_header("", width=78))
        return "\n".join(out) + "\n"

    def _format_chargen_armor(self, catalog):
        """Format armor like equipdb."""
        out = [section_header("Armor", width=78)]
        for a in catalog:
            name = a.get("name", "?")
            sp = a.get("sp", "?")
            ev = a.get("ev", "?")
            value = a.get("value", 0)
            locations = a.get("locations", "?")
            nm = crop(name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gSP:|n {str(sp):<3} |gEV:|n {str(ev):<3} |gValue:|n |y{value} eb|n |gLocations:|n {locations}")
        out.append(section_header("", width=78))
        return "\n".join(out) + "\n"

    def _format_chargen_gear(self, catalog):
        """Format gear like equipdb."""
        out = [section_header("Gear", width=78)]
        for g in catalog:
            name = g.get("name", "?")
            cat = g.get("category", "?")
            value = g.get("value", 0)
            desc = g.get("description", "--") or "--"
            nm = crop(name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gCategory:|n {str(cat):<14} |gValue:|n |y{value} eb|n")
            out.append(wrap_ansi(desc, 74, left_padding=2))
        out.append(section_header("", width=78))
        return "\n".join(out) + "\n"

    def _format_chargen_cyberdecks(self, catalog):
        """Format cyberdecks like equipdb."""
        out = [section_header("Cyberdecks", width=78)]
        for d in catalog:
            name = d.get("name", "?")
            hw = d.get("hardware_slots", 0)
            prog = d.get("program_slots", 0)
            any_slots = d.get("any_slots", 0)
            value = d.get("value", 0)
            nm = crop(name, width=28, suffix="...")
            out.append(f"|c{nm:<28}|n    |gHW:|n {hw} |gProg:|n {prog} |gAny:|n {any_slots} |gValue:|n |y{value} eb|n")
        out.append(section_header("", width=78))
        return "\n".join(out) + "\n"

    def _format_chargen_cyberware(self, catalog):
        """Format cyberware like equipdb (type, slots, humanity, value)."""
        out = [section_header("Cyberware", width=78)]
        for e in catalog:
            if "_cyberware" in e:
                cw = e["_cyberware"]
                name = cw.name
                ctype = getattr(cw, "type", "?")
                slots = getattr(cw, "slots", 0)
                hl = getattr(cw, "humanity_loss", 0)
                value = cw.cost
            else:
                name = e.get("name", "?")
                ctype = e.get("type", "?")
                slots = e.get("slots", 0)
                hl = e.get("humanity_loss", 0)
                value = e.get("value", e.get("cost", 0))
            nm = crop(str(name), width=28, suffix="...")
            out.append(f"|c{nm:<28}|n |gType:|n {str(ctype):<20} |gSlots:|n {slots} |gHL:|n {hl} |gValue:|n |y{value} eb|n")
        out.append(section_header("", width=78))
        out.append("|wBuy:|n buy/cyberware <name> | buy/cyberware pair=Cybereye Cybereye | buy/cyberware parent=<option>/<parent>")
        return "\n".join(out) + "\n"

class CleanExitEvMenu(EvMenu):
    def close_menu(self):
        """Clean up and exit the menu without any additional output."""
        self.caller.cmdset.remove(self.cmdset_class)
        del self.caller.ndb._evmenu

def player_sale_offer_node(caller, raw_string, **kwargs):
    """EvMenu node for buyer to accept/decline a player-to-player sale offer."""
    offer = getattr(caller.ndb, '_pending_sale_offer', None)
    if not offer:
        caller.msg("No pending offer.")
        return None
    text = (
        f"{offer['seller'].get_display_name(caller)} offers to sell you "
        f"{offer['display_name']} for {offer['price']} eurodollars.\n"
        "Do you accept?"
    )
    options = (
        {"key": ("y", "yes"), "desc": "Yes", "goto": "execute_player_sale"},
        {"key": ("n", "no"), "desc": "No", "goto": "decline_player_sale"},
    )
    return text, options


def execute_player_sale(caller, raw_string, **kwargs):
    """Buyer accepted - transfer money and item."""
    offer = getattr(caller.ndb, '_pending_sale_offer', None)
    if not offer:
        caller.msg("Offer no longer valid.")
        return None
    del caller.ndb._pending_sale_offer

    seller = offer['seller']
    item = offer['item']
    category = offer['category']
    price = offer['price']
    display_name = offer['display_name']

    if not CharacterMoneyService.spend_money(caller, price):
        caller.msg(f"You don't have enough eurodollars. The price is {price} eb.")
        seller.msg(f"{caller.get_display_name(seller)} couldn't afford the {price} eb.")
        return None

    seller_inv = get_character_inventory(seller)
    buyer_inv, _ = Inventory.get_or_create_for_character(caller)
    if not seller_inv:
        CharacterMoneyService.add_money(caller, price)
        caller.msg("The sale could not be completed.")
        return None

    if category == 'weapon':
        seller_inv.weapons.remove(item)
        buyer_inv.weapons.add(item)
    elif category == 'armor':
        seller_inv.armor.remove(item)
        buyer_inv.armor.add(item)
    elif category == 'gear':
        seller_inv.remove_gear(item)
        buyer_inv.add_gear(item)
    elif category == 'vehicle':
        seller_inv.vehicles.remove(item)
        buyer_inv.vehicles.add(item)
    elif category == 'cyberware':
        seller_inv.cyberware.remove(item)
        if hasattr(caller, 'character_sheet') and caller.character_sheet:
            item.character_sheet = caller.character_sheet
        item.character_object = caller
        item.save()
        buyer_inv.cyberware.add(item)

    CharacterMoneyService.add_money(seller, price)

    caller.msg(f"You purchased {display_name} from {seller.get_display_name(caller)} for {price} eb.")
    seller.msg(f"{caller.get_display_name(seller)} purchased your {display_name} for {price} eb.")
    if hasattr(caller.ndb, '_evmenu') and caller.ndb._evmenu:
        caller.ndb._evmenu.close_menu()
    return None


def decline_player_sale(caller, raw_string, **kwargs):
    """Buyer declined."""
    offer = getattr(caller.ndb, '_pending_sale_offer', None)
    if offer:
        seller = offer['seller']
        seller.msg(f"{caller.get_display_name(seller)} declined your offer.")
        del caller.ndb._pending_sale_offer
    caller.msg("You declined the offer.")
    if hasattr(caller.ndb, '_evmenu') and caller.ndb._evmenu:
        caller.ndb._evmenu.close_menu()
    return None


def sell_node(caller, raw_string, **kwargs):
    context = caller.ndb._sell_item_context
    if not context:
        caller.msg("Error: Sell context not found.")
        return None

    item = context['item']
    item_name = item.name if hasattr(item, 'name') else item.cyberware.name
    text = f"{context['merchant'].name} offers {context['price']} eb for your {item_name}.\nDo you want to sell it?"
    options = (
        {"key": ("y", "yes"), "desc": "Yes", "goto": "execute_sale"},
        {"key": ("n", "no"), "desc": "No", "goto": "cancel_sale"},
    )
    return text, options

def execute_sale(caller, raw_string, **kwargs):
    context = caller.ndb._sell_item_context
    merchant = context['merchant']
    item = context['item']
    price = context['price']

    inventory = get_character_inventory(caller)
    if hasattr(item, 'damage'):
        category = 'weapons'
    elif hasattr(item, 'sp'):
        category = 'armor'
    elif hasattr(item, 'cyberware'):
        category = 'cyberware'
    elif hasattr(item, 'sdp') and hasattr(item, 'speed_combat'):
        category = 'vehicles'
    else:
        category = 'gear'
    if category == 'cyberware':
        inventory.cyberware.remove(item)
        item.delete()
    else:
        getattr(inventory, category).remove(item)

    # Add money to the character
    CharacterMoneyService.add_money(caller, price)

    caller.msg(f"You sold {item.name} to {merchant.name} for {price} eb.")
    merchant.msg(f"{caller.name} sold you {item.name} for {price} eb.")

    del caller.ndb._sell_item_context
    
    # Update inventory display
    caller.execute_cmd('inventory')
    
    # Close the menu
    caller.ndb._evmenu.close_menu()

def cancel_sale(caller, raw_string, **kwargs):
    caller.msg("You decided not to sell the item.")
    del caller.ndb._sell_item_context
    
    # Close the menu
    caller.ndb._evmenu.close_menu()

def get_character_inventory(character):
    """Get a character's inventory. Uses same lookup as inventory command (via character sheet)."""
    from world.utils.character_utils import get_character_sheet
    sheet = get_character_sheet(character)
    if sheet and hasattr(sheet, 'inventory'):
        return sheet.inventory
    try:
        inventory, _ = Inventory.get_or_create_for_character(character)
        return inventory
    except (ValueError, AttributeError):
        return None


def find_item_in_inventory(inventory, item_name):
    """Find item by name. Returns (item, category) or (None, None). category: weapon/armor/gear/vehicle/cyberware"""
    item_name_lower = item_name.lower().strip()
    for cat in ['weapons', 'armor', 'gear', 'vehicles']:
        qs = getattr(inventory, cat).filter(name__iexact=item_name_lower)
        if qs.exists():
            return qs.first(), cat.rstrip('s')
    cw = inventory.cyberware.filter(cyberware__name__iexact=item_name_lower, installed=False).first()
    if cw:
        return cw, 'cyberware'
    return None, None


class CmdGive(Command):
    """
    Give equipment, uninstalled cyberware, or vouchers to another player.

    Usage:
      give <item>=<character>
    """

    key = "give"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        from typeclasses.npcs import is_npc
        if is_npc(self.caller):
            self.caller.msg("NPCs cannot give money, gear, or vouchers to people.")
            return
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: give <item>=<character>")
            return

        item_name, target_name = self.args.split("=", 1)
        item_name = item_name.strip()
        target_name = target_name.strip()

        target = self.caller.search(target_name)
        if not target:
            return
        if not target.has_account:
            self.caller.msg(f"{target.get_display_name(self.caller)} is not a player character.")
            return
        if target == self.caller:
            self.caller.msg("You can't give items to yourself.")
            return
        if target.location != self.caller.location:
            self.caller.msg(f"{target.get_display_name(self.caller)} is not here.")
            return

        inventory = get_character_inventory(self.caller)
        if not inventory:
            self.caller.msg("You don't have an inventory!")
            return

        item, category = find_item_in_inventory(inventory, item_name)
        if not item:
            # Try giving a physical object (e.g. voucher) from contents
            from commands.voucher_commands import find_voucher, VOUCHER_TYPECLASS
            obj = find_voucher(self.caller, item_name, location=self.caller)
            if obj and obj.location == self.caller:
                obj.move_to(target, quiet=True)
                display_name = obj.key or obj.name
                self.caller.msg(f"You give {display_name} to {target.get_display_name(self.caller)}.")
                target.msg(f"{self.caller.get_display_name(target)} gives you {display_name}.")
                return
            self.caller.msg(f"You don't have '{item_name}' in your inventory.")
            return

        to_inv, _ = Inventory.get_or_create_for_character(target)
        if category == 'weapon':
            inventory.weapons.remove(item)
            to_inv.weapons.add(item)
        elif category == 'armor':
            inventory.armor.remove(item)
            to_inv.armor.add(item)
        elif category == 'gear':
            inventory.remove_gear(item)
            to_inv.add_gear(item)
        elif category == 'vehicle':
            inventory.vehicles.remove(item)
            to_inv.vehicles.add(item)
        elif category == 'cyberware':
            inventory.cyberware.remove(item)
            if hasattr(target, 'character_sheet') and target.character_sheet:
                item.character_sheet = target.character_sheet
            item.character_object = target
            item.save()
            to_inv.cyberware.add(item)

        display_name = item.name if hasattr(item, 'name') else item.cyberware.name
        self.caller.msg(f"You give {display_name} to {target.get_display_name(self.caller)}.")
        target.msg(f"{self.caller.get_display_name(target)} gives you {display_name}.")


class CmdSellItem(Command):
    """
    Sell an item to a merchant or to another player.

    Usage:
      sell <item> to <merchant>   - Sell to a vendor
      sell <item>=<player>       - Offer to sell to a player (you set the price)

    When selling to a player, you'll be asked for your asking price. The buyer
    will receive an offer they can accept or decline.
    """

    key = "sell"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: sell <item> to <merchant>  OR  sell <item>=<player>")
            return

        if "=" in self.args:
            self._sell_to_player()
        elif " to " in self.args:
            self._sell_to_merchant()
        else:
            self.caller.msg("Usage: sell <item> to <merchant>  OR  sell <item>=<player>")

    def _sell_to_player(self):
        """Sell item to another player - prompt for price, buyer accepts/declines."""
        item_name, target_name = self.args.split("=", 1)
        item_name = item_name.strip()
        target_name = target_name.strip()

        inventory = get_character_inventory(self.caller)
        if not inventory:
            self.caller.msg("You don't have an inventory!")
            return

        item, category = find_item_in_inventory(inventory, item_name)
        if not item:
            self.caller.msg(f"You don't have '{item_name}' in your inventory.")
            return

        target = self.caller.search(target_name)
        if not target:
            return
        if not target.has_account:
            self.caller.msg(f"{target.get_display_name(self.caller)} is not a player character.")
            return
        if target == self.caller:
            self.caller.msg("You can't sell to yourself.")
            return
        if target.location != self.caller.location:
            self.caller.msg(f"{target.get_display_name(self.caller)} is not here.")
            return

        display_name = item.name if hasattr(item, 'name') else item.cyberware.name
        get_input(
            self.caller,
            "How much do you want to sell it for?",
            callback=lambda char, prompt, result: self._player_sale_price_entered(char, result, item, category, target, display_name),
        )

    def _player_sale_price_entered(self, seller, price_str, item, category, target, display_name):
        """Callback after seller enters price - validate and send offer to buyer."""
        try:
            price = int(price_str.strip())
            if price < 1:
                seller.msg("Price must be at least 1 eb.")
                return
        except (ValueError, AttributeError):
            seller.msg("Please enter a valid number.")
            return

        target.ndb._pending_sale_offer = {
            'seller': seller,
            'item': item,
            'category': category,
            'price': price,
            'display_name': display_name,
        }
        target.msg(
            f"{seller.get_display_name(target)} offers to sell you {display_name} for {price} eurodollars. "
            "Do you accept?"
        )
        EvMenu(
            target,
            "world.cyberpunk_sheets.commerce",
            startnode="player_sale_offer_node",
            auto_quit=True,
            cmd_on_exit=None,
        )
        seller.msg(f"You offer to sell {display_name} to {target.get_display_name(seller)} for {price} eb.")

    def _sell_to_merchant(self):
        """Sell item to a merchant (existing flow)."""
        item_name, merchant_name = self.args.split(" to ", 1)
        item_name = item_name.strip().lower()
        merchant_name = merchant_name.strip().lower()

        merchants = [
            obj for obj in self.caller.location.contents
            if obj.is_typeclass("world.cyberpunk_sheets.merchants.Merchant")
            and merchant_name in obj.name.lower()
        ]
        if not merchants:
            self.caller.msg(f"There's no merchant named '{merchant_name}' here.")
            return
        merchant = merchants[0]

        inventory = get_character_inventory(self.caller)
        if not inventory:
            self.caller.msg("You don't have an inventory!")
            return

        item, category = find_item_in_inventory(inventory, item_name)
        if not item:
            self.caller.msg(f"You don't have an item named '{item_name}' in your inventory.")
            return

        item_value = getattr(item, 'value', None) or (getattr(item.cyberware, 'cost', 0) if hasattr(item, 'cyberware') else 0)
        sell_price = merchant.get_sell_price({'value': item_value})

        self.caller.ndb._sell_item_context = {
            'merchant': merchant,
            'item': item,
            'price': sell_price
        }
        EvMenu(self.caller, "world.cyberpunk_sheets.commerce",
               startnode="sell_node", auto_quit=True, cmd_on_exit=None)

class CmdHaggle(Command):
    """
    Haggle with a merchant over the price of an item.

    Usage:
      haggle <item name> with <merchant>

    This command allows you to haggle with merchants to get a better price for your items.
    """

    key = "haggle"
    locks = "cmd:all()"
    help_category = "Economy"

    def func(self):
        if not self.args or " with " not in self.args:
            self.caller.msg("Usage: haggle <item name> with <merchant>")
            return

        item_name, merchant_name = self.args.split(" with ")
        item_name = item_name.strip().lower()
        merchant_name = merchant_name.strip().lower()

        # Search for the merchant in the current location
        merchants = [obj for obj in self.caller.location.contents 
                     if isinstance(obj, Merchant)  # Use isinstance instead of is_typeclass
                     and merchant_name in obj.name.lower()]
        
        if not merchants:
            self.caller.msg(f"There's no merchant named '{merchant_name}' here.")
            return
        merchant = merchants[0]

        # Check if the character can haggle
        if not merchant.can_haggle(self.caller):
            self.caller.msg(f"You can't haggle with {merchant.name} yet. Try again later.")
            return

        # Find the item in the character's inventory
        inventory = get_character_inventory(self.caller)
        if not inventory:
            self.caller.msg("You don't have an inventory!")
            return
            
        item = None

        for category in ['weapons', 'armor', 'gear']:
            items = getattr(inventory, category).filter(name__iexact=item_name)
            if items.exists():
                item = items.first()
                break

        if not item:
            self.caller.msg(f"You don't have an item named '{item_name}' in your inventory.")
            return

        # Get character's cool and trading skill values
        cool = merchant.get_character_cool(self.caller)
        trading = merchant.get_character_trading_skill(self.caller)

        from world.utils.roll_utils import roll_skill_check, check_success

        total, details = roll_skill_check(cool, trading)
        first_roll = details.get("first_roll", 0)

        # Determine the result (DV 14 for success = total > 13)
        base_price = merchant.get_sell_price(item.__dict__)
        if first_roll == 1:  # Critical failure (natural 1)
            price_multiplier = 0.50
            self.caller.msg("Critical failure! The merchant is offended by your low offer.")
            merchant.db.haggle_attempts[self.caller.id] = gametime.time() + 7 * 24 * 60 * 60  # 1 week cooldown
        elif first_roll == 10:  # Critical success (natural 10)
            price_multiplier = 1.75
            self.caller.msg("Critical success! The merchant is impressed by your negotiation skills.")
        elif check_success(total, 13):  # Success = total exceeds 13 (i.e. total >= 14)
            price_multiplier = 1.25
            self.caller.msg("Success! You've negotiated a better price.")
        else:  # Failure
            price_multiplier = 1.0
            self.caller.msg("Your attempt to haggle was unsuccessful.")

        final_price = int(base_price * price_multiplier)

        # Record the haggle attempt
        merchant.record_haggle_attempt(self.caller)

        self.caller.ndb._sell_item_context = {
            'merchant': merchant,
            'item': item,
            'price': final_price
        }
        EvMenu(self.caller, "world.cyberpunk_sheets.commerce", 
               startnode="sell_node", auto_quit=True, cmd_on_exit=None)

def handle_sell_confirmation(character, prompt, response):
    context = character.ndb._sell_item_context
    if not context:
        character.msg("Error: Sell context not found.")
        return

    response = (response or "").strip().lower()
    if response in ["y", "yes"]:
        merchant = context['merchant']
        item = context['item']
        price = context['price']

        # Remove the item from the character's inventory
        inventory = get_character_inventory(character)
        category = 'weapons' if hasattr(item, 'damage') else 'armor' if hasattr(item, 'sp') else 'gear'
        getattr(inventory, category).remove(item)

        # Add money to the character
        CharacterMoneyService.add_money(character, price)

        character.msg(f"You sold {item.name} to {merchant.name} for {price} eb.")
        merchant.msg(f"{character.name} sold you {item.name} for {price} eb.")
        
        # Clean up
        del character.ndb._sell_item_context
    elif response in ["n", "no"]:
        character.msg("You decided not to sell the item.")
        
        # Clean up
        del character.ndb._sell_item_context
    else:
        character.msg("Invalid response. Please type 'y' or 'n'.")
        get_input(character, "Do you want to sell it? (y/n)", handle_sell_confirmation)

class CmdAddItem(Command):
    """
    Add an item to a merchant's inventory.

    Usage:
      additem <item name> to <merchant>

    This command allows administrators to add items to a merchant's inventory.
    The item must exist in the equipment data.
    """

    key = "additem"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or " to " not in self.args:
            self.caller.msg("Usage: additem <item name> to <merchant>")
            return

        item_name, merchant_name = self.args.split(" to ")
        item_name = item_name.strip()
        merchant_name = merchant_name.strip()

        # Search for the merchant
        merchants = search_object(merchant_name)
        if not merchants:
            self.caller.msg(f"No merchant named '{merchant_name}' found.")
            return
        merchant = merchants[0]

        if not merchant.is_typeclass("world.cyberpunk_sheets.merchants.Merchant"):
            self.caller.msg(f"{merchant_name} is not a valid merchant.")
            return

        # Find the item in the equipment data
        all_items = weapons + armors + gears
        item = next((item for item in all_items if item['name'].lower() == item_name.lower()), None)

        if not item:
            self.caller.msg(f"No item named '{item_name}' found in the equipment data.")
            return

        # Add the item to the merchant's inventory
        if not hasattr(merchant.db, 'inventory'):
            merchant.db.inventory = []
        
        if item not in merchant.db.inventory:
            merchant.db.inventory.append(item)
            self.caller.msg(f"Added {item_name} to {merchant_name}'s inventory.")
        else:
            self.caller.msg(f"{item_name} is already in {merchant_name}'s inventory.")

class CmdRemItem(Command):
    """
    Remove an item from a merchant's inventory.

    Usage:
      remitem <item name> from <merchant>

    This command allows administrators to remove items from a merchant's inventory.
    """

    key = "remitem"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        if not self.args or " from " not in self.args:
            self.caller.msg("Usage: remitem <item name> from <merchant>")
            return

        item_name, merchant_name = self.args.split(" from ")
        item_name = item_name.strip()
        merchant_name = merchant_name.strip()

        # Search for the merchant
        merchants = search_object(merchant_name)
        if not merchants:
            self.caller.msg(f"No merchant named '{merchant_name}' found.")
            return
        merchant = merchants[0]

        if not merchant.is_typeclass("world.cyberpunk_sheets.merchants.Merchant"):
            self.caller.msg(f"{merchant_name} is not a valid merchant.")
            return

        # Remove the item from the merchant's inventory
        if not hasattr(merchant.db, 'inventory'):
            self.caller.msg(f"{merchant_name} has no inventory.")
            return

        item = next((item for item in merchant.db.inventory if item['name'].lower() == item_name.lower()), None)
        if item:
            merchant.db.inventory.remove(item)
            self.caller.msg(f"Removed {item_name} from {merchant_name}'s inventory.")
        else:
            self.caller.msg(f"No item named '{item_name}' found in {merchant_name}'s inventory.")