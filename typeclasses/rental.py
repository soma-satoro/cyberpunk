"""
RentableRoom - Apartments and housing that can be rented or purchased.

Uses eurodollar-based costs. Monthly rent is a threshold check (abstracted).
Purchase removes monthly checks. Supports co-residents, partners, room customization.
"""

from evennia import create_object
from evennia.utils import create, delay
from .rooms import Room
from world.cyberpunk_sheets.models import CharacterSheet
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from world.rental_data import RENTAL_TYPES
from world.rental_service import (
    get_character_eurodollars,
    get_effective_rent_cost,
    get_effective_purchase_cost,
    create_apartment_rooms,
    ensure_rent_collection_script,
    stop_rent_collection_script,
)
from .scripts import RentCollectionScript
from evennia.utils.ansi import ANSIString
from world.utils.ansi_utils import wrap_ansi
from world.utils.formatting import header, footer, divider


class RentableRoom(Room):
    """
    A room that can be rented or purchased by players.
    Uses eurodollar costs. Rent is threshold-based (abstracted, no deduction).
    """

    RENTAL_TYPES = RENTAL_TYPES

    def at_object_creation(self):
        """Set up the rentable room."""
        super().at_object_creation()
        self.db.rental_type = None
        self.db.owner = None  # Primary renter/owner
        self.db.rent_due_date = None
        self.db.child_rooms = []
        self.db.is_temporary = False
        self.db.purchased = False  # If True, no monthly rent check
        self.db.rent_cost = 0
        self.db.purchase_cost = 0
        self.db.rent_cost_modifier = 0  # Staff can modify
        self.db.purchase_cost_modifier = 0
        # residents: [char] - primary + co-residents + partners
        self.db.residents = []
        # co_residents: {room_id: char} - co-resident assigned to which room
        self.db.co_residents = {}
        # partners: [char] - romantic partners (same authority as primary)
        self.db.partners = []
        # room_owners: {room_id: char_id} - which co-resident owns which room
        self.db.room_owners = {}
        self.db.partner_pending = None  # char awaiting +rent/partner confirm
        self.db.is_awarded = False  # True = staff/mission award, no rent, stacks with rented_room

    def get_main_room(self):
        """Get the main room of this apartment (self if main, else parent)."""
        if getattr(self.db, 'is_child_room', False) and self.db.parent_room:
            return self.db.parent_room
        return self

    def is_primary_owner(self, character):
        """Check if character is the primary owner."""
        return self.db.owner and self.db.owner.id == character.id

    def is_resident(self, character):
        """Check if character is any kind of resident (owner, co-resident, partner)."""
        if not character:
            return False
        main = self.get_main_room()
        if main.db.owner and main.db.owner.id == character.id:
            return True
        for r in main.db.residents or []:
            if r and r.id == character.id:
                return True
        for p in main.db.partners or []:
            if p and p.id == character.id:
                return True
        for rid, c in (main.db.co_residents or {}).items():
            if c and c.id == character.id:
                return True
        return False

    def can_modify_room(self, character):
        """Check if character can modify this room (desc, name, exits)."""
        if not character:
            return False
        main = self.get_main_room()
        if main.is_primary_owner(character):
            return True
        if self.db.is_child_room and self.db.room_role:
            room_owners = main.db.room_owners or {}
            return room_owners.get(self.id) == character.id
        # Partners have same authority as primary
        for p in main.db.partners or []:
            if p and p.id == character.id:
                return True
        return False

    def can_lock_door(self, character):
        """Check if character can lock/unlock doors (owner, co-residents, partners)."""
        return self.is_resident(character)

    def set_rental_type(self, rental_type, is_temporary=False):
        """Set the rental type for this room."""
        if rental_type not in self.RENTAL_TYPES:
            raise ValueError(f"Invalid rental type: {rental_type}")
        data = self.RENTAL_TYPES[rental_type]
        self.db.rental_type = rental_type
        if rental_type != "Custom":
            self.db.rent_cost = data.get("rent") or 0
            self.db.purchase_cost = data.get("purchase") or 0
        self.db.is_temporary = is_temporary

    def award_to(self, character, rental_type=None):
        """
        Award this apartment to a character (staff or mission reward).
        No rent, no eurodollar check. Stacks with rented_room - character can have
        both a rental and awarded apartments (e.g. corporate housing + personal rental).
        """
        main = self.get_main_room()
        if main.db.owner and main.db.owner.id != character.id:
            return False, "This apartment is already assigned to someone else."
        if main.db.owner and main.db.owner.id == character.id:
            return True, f"{character.name} already has this apartment awarded."

        if not hasattr(character, 'character_sheet') or not character.character_sheet:
            return False, "Character has no character sheet."

        rental_type = rental_type or main.db.rental_type
        if not rental_type:
            rental_type = "Studio Apartment"  # Default for awards
        if rental_type not in self.RENTAL_TYPES:
            return False, f"Invalid rental type: {rental_type}"

        main.set_rental_type(rental_type)
        main.db.owner = character
        main.db.residents = [character]
        main.db.co_residents = {}
        main.db.partners = []
        main.db.room_owners = {}
        main.db.purchased = True  # No rent for awarded
        main.db.rent_cost = 0
        main.db.is_awarded = True
        main.db.rent_due_date = None

        awarded = list(character.attributes.get('awarded_apartments', category='rental') or [])
        main_id = main.id
        if main_id not in awarded:
            awarded.append(main_id)
        character.attributes.add('awarded_apartments', awarded, category='rental')

        for child in main.db.child_rooms or []:
            if child:
                child.db.owner = character
                child.db.residents = [character]
                child.db.purchased = True
                child.db.is_awarded = True

        return True, f"Awarded {rental_type} to {character.name} (corporate/staff housing, no rent)."

    def revoke_award(self, character):
        """Staff revokes an awarded apartment from a character."""
        main = self.get_main_room()
        if not main.db.is_awarded:
            return False, "This is not an awarded apartment."
        if not main.db.owner or main.db.owner.id != character.id:
            return False, f"{character.name} is not the recipient of this award."

        awarded = list(character.attributes.get('awarded_apartments', category='rental') or [])
        if main.id in awarded:
            awarded.remove(main.id)
        character.attributes.add('awarded_apartments', awarded, category='rental')

        if character.db.home_location == main:
            character.db.home_location = None

        main.db.owner = None
        main.db.residents = []
        main.db.co_residents = {}
        main.db.partners = []
        main.db.room_owners = {}
        main.db.is_awarded = False
        main.db.purchased = False

        for child in main.db.child_rooms or []:
            if child:
                child.db.owner = None
                child.db.residents = []
                child.db.purchased = False
                child.db.is_awarded = False

        character.msg("Your awarded apartment has been revoked.")
        return True, f"Revoked apartment from {character.name}."

    def rent_to(self, character, rental_type=None):
        """
        Rent the room to a character.
        For vacant apartments: rental_type from building's available types.
        Does NOT deduct eurodollars (abstracted). Checks threshold only.
        """
        if self.db.owner and not self.db.residents:
            # Vacant - allow new rental
            pass
        elif self.db.owner:
            return False, "This apartment is already rented."

        if character.attributes.has('rented_room'):
            existing = character.attributes.get('rented_room')
            if existing and existing != self.get_main_room():
                return False, "You are already renting another place. Leave that one first."

        if not hasattr(character, 'character_sheet') or not character.character_sheet:
            return False, "You don't have a character sheet."

        sheet = character.character_sheet
        if isinstance(sheet, int):
            try:
                sheet = CharacterSheet.objects.get(id=sheet)
            except CharacterSheet.DoesNotExist:
                return False, "Your character sheet could not be found."

        rental_type = rental_type or self.db.rental_type
        if not rental_type:
            return False, "No rental type specified."

        if rental_type not in self.RENTAL_TYPES:
            return False, f"Invalid rental type: {rental_type}"

        data = self.RENTAL_TYPES[rental_type]
        if data.get("role_required") and not character.check_permstring(data["role_required"]):
            return False, f"You need to be {data['role_required']} to rent this type."

        rent_cost = get_effective_rent_cost(self) if self.db.rent_cost is not None else (data.get("rent") or 0)
        if rent_cost > 0:
            balance = get_character_eurodollars(character)
            if balance < rent_cost:
                return False, f"You need at least {rent_cost} Eurodollars to rent this. You have {balance}."

        self.set_rental_type(rental_type)
        self.db.owner = character
        self.db.residents = [character]
        self.db.co_residents = {}
        self.db.partners = []
        self.db.room_owners = {}
        self.db.purchased = False
        self.db.rent_due_date = self.get_next_rent_due_date()
        character.attributes.add('rented_room', self.get_main_room())

        ensure_rent_collection_script(self.get_main_room())

        return True, f"You have rented this {rental_type}. Monthly rent: {rent_cost}eb (threshold check)."

    def purchase_by(self, character):
        """Purchase the apartment. Deducts eurodollars and stops monthly checks."""
        if self.db.purchased:
            return False, "This apartment is already owned."
        if self.db.owner and self.db.owner != character:
            return False, "Someone else is renting this apartment."

        purchase_cost = get_effective_purchase_cost(self)
        if purchase_cost <= 0:
            return False, "This apartment cannot be purchased."

        sheet = character.character_sheet
        if not sheet:
            return False, "You don't have a character sheet."
        if isinstance(sheet, int):
            sheet = CharacterSheet.objects.get(id=sheet)

        if not CharacterSheetMoneyService.spend_money(sheet, purchase_cost):
            return False, f"You need {purchase_cost} Eurodollars to purchase. You have {get_character_eurodollars(character)}."

        self.db.purchased = True
        self.db.owner = character
        if character not in (self.db.residents or []):
            self.db.residents = [character] + (self.db.residents or [])
        stop_rent_collection_script(self.get_main_room())

        for child in self.db.child_rooms or []:
            if child:
                child.db.purchased = True
                child.db.owner = character

        return True, f"You have purchased this apartment for {purchase_cost} Eurodollars. No more monthly rent!"

    def collect_rent(self):
        """
        Monthly rent check. Threshold-based: if balance >= rent, keep apartment.
        Does NOT deduct eurodollars (abstracted).
        """
        main = self.get_main_room()
        if not main.db.owner:
            return False, "No one is renting this apartment."
        if main.db.purchased:
            return True, "Apartment is owned, no rent due."

        rent_cost = get_effective_rent_cost(main)
        if rent_cost <= 0:
            main.db.rent_due_date = main.get_next_rent_due_date()
            return True, "Rent check passed (corporate housing)."

        sheet = main.db.owner.character_sheet
        if not sheet:
            main.evict_renter()
            return False, "Rent check failed: no character sheet. Evicted."
        balance = CharacterSheetMoneyService.get_balance(sheet)
        if balance >= rent_cost:
            main.db.rent_due_date = main.get_next_rent_due_date()
            return True, f"Rent check passed. Balance {balance}eb >= {rent_cost}eb."
        else:
            main.evict_renter()
            return False, f"Rent check failed. Balance {balance}eb < {rent_cost}eb. Evicted."

    def evict_renter(self):
        """Remove the primary renter. Promote co-resident or mark vacant."""
        main = self.get_main_room()
        if main.db.owner:
            main.db.owner.msg("You have been evicted from your apartment due to non-payment.")
            if main.db.is_awarded:
                awarded = list(main.db.owner.attributes.get('awarded_apartments', category='rental') or [])
                if main.id in awarded:
                    awarded.remove(main.id)
                main.db.owner.attributes.add('awarded_apartments', awarded, category='rental')
            else:
                main.db.owner.attributes.remove('rented_room')
            if main.db.owner.db.home_location == main:
                main.db.owner.db.home_location = None

        # Promote first co-resident to primary if any
        co_list = list((main.db.co_residents or {}).values())
        if co_list:
            new_owner = co_list[0]
            main.db.owner = new_owner
            main.db.residents = [new_owner] + [c for c in co_list[1:] if c]
            main.db.co_residents = {k: v for k, v in (main.db.co_residents or {}).items() if v != new_owner}
            if main.db.is_awarded:
                awarded = list(new_owner.attributes.get('awarded_apartments', category='rental') or [])
                if main.id not in awarded:
                    awarded.append(main.id)
                new_owner.attributes.add('awarded_apartments', awarded, category='rental')
            else:
                new_owner.attributes.add('rented_room', main)
            new_owner.msg("You have taken over as primary renter of the apartment.")
        else:
            main.db.owner = None
            main.db.residents = []
            main.db.co_residents = {}
            main.db.partners = []
            main.db.room_owners = {}
            main.db.rent_due_date = None
            main.db.is_awarded = False
            stop_rent_collection_script(main)

        for child in main.db.child_rooms or []:
            if child:
                child.db.owner = main.db.owner
                child.db.residents = main.db.residents
                child.db.co_residents = main.db.co_residents
                child.db.partners = main.db.partners
                child.db.room_owners = main.db.room_owners

    def leave_rental(self, character):
        """Character leaves the rental. Apartment becomes vacant or co-resident takes over."""
        main = self.get_main_room()
        owner = main.db.owner
        if not owner or (hasattr(owner, 'id') and owner.id != character.id):
            return False, "You are not the primary renter."

        if main.db.is_awarded:
            awarded = list(character.attributes.get('awarded_apartments', category='rental') or [])
            if main.id in awarded:
                awarded.remove(main.id)
            character.attributes.add('awarded_apartments', awarded, category='rental')
        else:
            character.attributes.remove('rented_room')
        if character.db.home_location == main:
            character.db.home_location = None

        # Remove from partners
        if main.db.partners:
            main.db.partners = [p for p in main.db.partners if p and p.id != character.id]
        # Remove from co_residents
        if main.db.co_residents:
            main.db.co_residents = {k: v for k, v in main.db.co_residents.items() if v and v.id != character.id}
        # Remove from residents
        if main.db.residents:
            main.db.residents = [r for r in main.db.residents if r and r.id != character.id]

        # Promote co-resident or partner
        co_list = list((main.db.co_residents or {}).values())
        partner_list = main.db.partners or []
        if co_list:
            new_owner = co_list[0]
            main.db.owner = new_owner
            main.db.residents = [new_owner] + [c for c in co_list[1:] if c] + partner_list
            if main.db.is_awarded:
                awarded = list(new_owner.attributes.get('awarded_apartments', category='rental') or [])
                if main.id not in awarded:
                    awarded.append(main.id)
                new_owner.attributes.add('awarded_apartments', awarded, category='rental')
            else:
                new_owner.attributes.add('rented_room', main)
            new_owner.msg("You have taken over as primary renter.")
        elif partner_list:
            new_owner = partner_list[0]
            main.db.owner = new_owner
            main.db.residents = [new_owner] + partner_list[1:]
            if main.db.is_awarded:
                awarded = list(new_owner.attributes.get('awarded_apartments', category='rental') or [])
                if main.id not in awarded:
                    awarded.append(main.id)
                new_owner.attributes.add('awarded_apartments', awarded, category='rental')
            else:
                new_owner.attributes.add('rented_room', main)
            new_owner.msg("You have taken over as primary renter.")
        else:
            main.db.owner = None
            main.db.residents = []
            main.db.rent_due_date = None
            main.db.is_awarded = False
            stop_rent_collection_script(main)

        for child in main.db.child_rooms or []:
            if child:
                child.db.owner = main.db.owner
                child.db.residents = main.db.residents
                child.db.co_residents = main.db.co_residents
                child.db.partners = main.db.partners

        return True, "You have left your rental. The apartment is now vacant."

    def get_next_rent_due_date(self):
        """Next rent due (30 days)."""
        from django.utils import timezone
        return timezone.now() + timezone.timedelta(days=30)

    def return_appearance(self, looker, **kwargs):
        """Room appearance without rental info - use +rent/status to see rental details."""
        return super().return_appearance(looker, **kwargs)

    def at_object_delete(self):
        """Clean up when deleted. Must return True to allow deletion."""
        result = super().at_object_delete()
        try:
            for script in self.scripts.all():
                script.stop()
        except Exception:
            pass
        return result if result is not None else True
