"""
Voucher typeclass - IC objects that can hold multiple items.

A voucher represents in-character objects. Multiple items may be combined
onto a single voucher. Vouchers can be picked up and dropped like regular items.
"""
from typeclasses.objects import Object
from world.utils.formatting import sheet_header, sheet_section, footer


def _default_items():
    return []


class Voucher(Object):
    """
    A voucher is a physical object that holds a list of IC items.
    Each item: {name, description, quantity, ic_location, cloneable}
    """
    def at_object_creation(self):
        super().at_object_creation()
        self.db.voucher_items = []
        self.db.concealed = False
        self.db.locked = False
        self.db.ic_owner = ""  # Character name for +owner
        self.db.voucher_alias = ""  # Custom alias (max 20 chars)
        self.tags.add("voucher", category="object")

    def get_items(self):
        return self.db.voucher_items or []

    def set_items(self, items):
        self.db.voucher_items = items

    def get_item_by_num(self, num):
        items = self.get_items()
        if 1 <= num <= len(items):
            return items[num - 1], num
        return None, None

    def is_empty(self):
        return len(self.get_items()) == 0

    def is_concealed(self):
        return bool(self.db.concealed)

    def is_locked(self):
        return bool(self.db.locked)

    def can_modify(self, character):
        """Locked vouchers can only be modified by owner."""
        if not self.is_locked():
            return True
        return self.location == character if character else False

    def at_pre_get(self, getter, **kwargs):
        """Locked vouchers can only be picked up by the person who locked them."""
        if not self.is_locked():
            return True
        locked_by = getattr(self.db, "locked_by", None)
        if locked_by and getter and getattr(getter, "id", None) == locked_by:
            return True
        if self.location == getter:
            return True  # Already carrying it
        if locked_by:
            getter.msg("That voucher is locked.")
        return False

    def return_appearance(self, looker, **kwargs):
        """Look shows voucher contents."""
        string = super().return_appearance(looker, **kwargs)
        items = self.get_items()
        if items:
            string += "\n|yContents:|n\n"
            for i, it in enumerate(items, 1):
                qty = it.get("quantity", 1)
                name = it.get("name", "?")
                loc = it.get("ic_location", "")
                loc_str = f" ({loc})" if loc else ""
                string += f"  {i}. {name}"
                if qty > 1:
                    string += f" x{qty}"
                string += f"{loc_str}\n"
        return string

    def format_sheet(self, width=80):
        """Format voucher for +sheet display."""
        items = self.get_items()
        out = sheet_header(f"Voucher: {self.key}", width=width)
        out += sheet_section("Contents", width=width)
        if not items:
            out += "|w(empty)|n\n"
        else:
            out += f"|y{'#':<4}{'Item':<30}{'Qty':<8}{'Location':<20}|n\n"
            for i, it in enumerate(items, 1):
                name = (it.get("name", "?") or "?")[:29]
                qty = it.get("quantity", 1)
                loc = (it.get("ic_location", "") or "")[:19]
                out += f"|w{i:<4}{name:<30}{qty:<8}{loc:<20}|n\n"
        out += footer(width=width, fillchar="-")
        return out
