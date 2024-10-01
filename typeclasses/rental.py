from evennia import create_object
from evennia.utils import create, delay
from .rooms import Room
from world.cyberpunk_sheets.models import CharacterSheet
from world.cyberpunk_sheets.services import CharacterSheetMoneyService
from .scripts import RentCollectionScript

class RentableRoom(Room):
    """
    A room that can be rented by players for a monthly fee.
    """

    RENTAL_TYPES = {
        "Cube Hotel": {"cost": 900, "rooms": 1},
        "Cargo Container": {"cost": 1000, "rooms": 1},
        "Studio Apartment": {"cost": 1500, "rooms": 1},
        "Two-Bedroom Apartment": {"cost": 2500, "rooms": 2},
        "Corporate Conapt": {"cost": 0, "rooms": 3, "role": "Exec"},
        "Upscale Conapt": {"cost": 7500, "rooms": 3},
        "Luxury Penthouse": {"cost": 15000, "rooms": 5},
    }

    def at_object_creation(self):
        """Set up the rentable room."""
        super().at_object_creation()
        self.db.rental_type = None
        self.db.renter = None
        self.db.rent_due_date = None
        self.db.child_rooms = []
        self.db.is_temporary = False  # New attribute to mark temporary units

    def set_rental_type(self, rental_type, is_temporary=False):
        """Set the rental type for this room and mark if it's temporary."""
        if rental_type in self.RENTAL_TYPES:
            self.db.rental_type = rental_type
            self.db.rent_cost = self.RENTAL_TYPES[rental_type]["cost"]
            self.db.is_temporary = is_temporary
            self.generate_child_rooms(self.RENTAL_TYPES[rental_type]["rooms"])
        else:
            raise ValueError(f"Invalid rental type: {rental_type}")

    def generate_child_rooms(self, num_rooms):
        """Generate child rooms for multi-room rentals."""
        for i in range(num_rooms - 1):  # -1 because the main room counts as one
            room = create_object(
                RentableRoom,
                key=f"{self.key} - Room {i+2}",
                location=None,  # Set to None so it's not placed in the current location
            )
            room.db.parent_room = self
            self.db.child_rooms.append(room)

    def rent_to(self, character):
        """Rent the room to a character."""
        if self.db.renter:
            return False, "This room is already rented."

        # Check if the character is already renting another room
        if character.attributes.has('rented_room'):
            return False, "You are already renting another room. Leave that one first."

        rental_type = self.db.rental_type
        if rental_type == "Corporate Conapt" and not character.check_permstring("Exec"):
            return False, "You need to be an Executive to rent this type of apartment."

        if not hasattr(character, 'character_sheet'):
            return False, "You don't have a character sheet."

        sheet = character.character_sheet
        if isinstance(sheet, CharacterSheet):
            character_sheet = sheet
        else:
            try:
                character_sheet = CharacterSheet.objects.get(id=sheet)
            except CharacterSheet.DoesNotExist:
                return False, "Your character sheet could not be found."

        if not CharacterSheetMoneyService.spend_money(character_sheet, self.db.rent_cost):
            return False, "You don't have enough Eurodollars to rent this room."

        self.db.renter = character
        self.db.rent_due_date = self.get_next_rent_due_date()
        character.attributes.add('rented_room', self)
        
        # Set up a script to handle monthly rent collection
        create.create_script(
            RentCollectionScript,
            key=f"rent_collection_{self.id}",
            obj=self,
            interval=2592000,  # 30 days in seconds
            persistent=True,
        )

        return True, f"You have successfully rented the {rental_type} for {self.db.rent_cost} Eurodollars per month."

    def get_next_rent_due_date(self):
        """Calculate the next rent due date (30 days from now)."""
        from django.utils import timezone
        return timezone.now() + timezone.timedelta(days=30)

    def collect_rent(self):
        """Collect rent from the renter."""
        if not self.db.renter:
            return False, "This room is not currently rented."

        character_sheet = CharacterSheet.objects.get(account=self.db.renter.account)
        if CharacterSheetMoneyService.spend_money(character_sheet, self.db.rent_cost):
            self.db.rent_due_date = self.get_next_rent_due_date()
            return True, f"Rent of {self.db.rent_cost} Eurodollars collected successfully."
        else:
            self.evict_renter()
            return False, "Rent collection failed. The renter has been evicted."

    def evict_renter(self):
        """Evict the current renter and schedule room destruction if empty."""
        if self.db.renter:
            self.db.renter.msg("You have been evicted from your rented room due to non-payment.")
            self.db.renter.attributes.remove('rented_room')
            self.db.renter = None
            self.db.rent_due_date = None
            # Remove the rent collection script
            for script in self.scripts.all():
                if script.key.startswith("rent_collection_"):
                    script.stop()
            
            # Schedule room destruction
            if self.db.is_temporary:
                delay(300, self.check_and_destroy)  # Check after 5 minutes

    def check_and_destroy(self):
        """Check if the room is still empty and destroy it if it's temporary."""
        if self.db.is_temporary and not self.db.renter and not self.contents:
            # Destroy child rooms first
            for child_room in self.db.child_rooms:
                child_room.delete()
            # Destroy this room
            self.delete()
        elif self.db.is_temporary:
            # If the room is occupied or not temporary, schedule another check
            delay(3600, self.check_and_destroy)  # Check again after 1 hour

    def leave_rental(self, character):
        """Allow a character to leave their rental."""
        if self.db.renter != character:
            return False, "You are not renting this room."

        self.db.renter = None
        self.db.rent_due_date = None
        character.attributes.remove('rented_room')

        # Remove the rent collection script
        for script in self.scripts.all():
            if script.key.startswith("rent_collection_"):
                script.stop()

        # Schedule room destruction if it's temporary
        if self.db.is_temporary:
            delay(300, self.check_and_destroy)  # Check after 5 minutes

        return True, "You have successfully left your rental. Your security deposit will be refunded."

    def return_appearance(self, looker, **kwargs):
        """Customize the room's appearance."""
        string = super().return_appearance(looker, **kwargs)
        if self.db.rental_type:
            string += f"\n|wRental Type:|n {self.db.rental_type}"
            string += f"\n|wMonthly Rent:|n {self.db.rent_cost} Eurodollars"
            if self.db.renter:
                string += f"\n|wRented by:|n {self.db.renter.name}"
                string += f"\n|wRent Due Date:|n {self.db.rent_due_date.strftime('%Y-%m-%d %H:%M:%S')}"
            else:
                string += "\n|wStatus:|n Available for rent"
        return string

    def at_object_delete(self):
        """Clean up when the room is deleted."""
        super().at_object_delete()
        # Remove any remaining scripts
        for script in self.scripts.all():
            script.stop()
        # Remove references from the parent location
        parent_location = self.location
        if parent_location and hasattr(parent_location, 'db'):
            exits = parent_location.exits
            for exit in exits:
                if exit.destination == self:
                    exit.delete()