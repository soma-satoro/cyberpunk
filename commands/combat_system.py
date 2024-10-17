import random
from evennia import Command
from evennia.utils.evtable import EvTable
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import Weapon, Armor, Inventory, Ammunition, AmmoType
from enum import Enum

class WoundState(Enum):
    LIGHTLY_WOUNDED = 1
    SERIOUSLY_WOUNDED = 2
    MORTALLY_WOUNDED = 3
    DEAD = 4

def determine_wound_state(character):
    try:
        cs = CharacterSheet.objects.get(character=character)
        hp_ratio = cs.current_hp / cs.max_hp
        if cs.current_hp <= 0:
            return WoundState.DEAD
        elif cs.current_hp < 1:
            return WoundState.MORTALLY_WOUNDED
        elif hp_ratio <= 0.5:
            return WoundState.SERIOUSLY_WOUNDED
        elif cs.current_hp < cs.max_hp:
            return WoundState.LIGHTLY_WOUNDED
        else:
            return None  # Unwounded
    except CharacterSheet.DoesNotExist:
        # Handle the case where the character doesn't have a sheet
        return None

def apply_wound_effects(character):
    wound_state = determine_wound_state(character)
    if wound_state == WoundState.LIGHTLY_WOUNDED:
        character.wound_effect = "None"
        character.stabilization_dv = 10
    elif wound_state == WoundState.SERIOUSLY_WOUNDED:
        character.wound_effect = "-2 to all Actions"
        character.stabilization_dv = 13
        character.action_penalty = -2
    elif wound_state == WoundState.MORTALLY_WOUNDED:
        character.wound_effect = "-4 to all Actions, -6 to MOVE (Minimum 1), Must make a Death Save at start of each Turn"
        character.stabilization_dv = 15
        character.action_penalty = -4
        character.move_penalty = -6
        character.requires_death_save = True
    elif wound_state == WoundState.DEAD:
        character.wound_effect = "Death"
        character.stabilization_dv = None  # Cannot be stabilized
    else:
        character.wound_effect = character.stabilization_dv = None
        character.action_penalty = character.move_penalty = 0
        character.requires_death_save = False

def make_death_save(character):
    # Implement death save logic here
    return random.choice([True, False])  # Placeholder implementation

def apply_critical_injury(target):
    critical_injuries = [
        "Dismembered Arm", "Dismembered Hand", "Dismembered Leg", "Dismembered Foot",
        "Collapsed Lung", "Broken Ribs", "Broken Arm", "Broken Leg", "Foreign Object",
        "Concussion", "Broken Jaw", "Whiplash", "Cracked Skull", "Damaged Eye",
        "Brain Injury", "Spinal Injury", "Crushed Fingers", "Crushed Toes",
        "Lost Ear", "Lost Nose", "Lost Teeth", "Torn Muscle"
    ]
    return random.choice(critical_injuries)

def roll_damage(num_dice):
    return [random.randint(1, 6) for _ in range(num_dice)]

def check_critical(damage_rolls):
    return sum(1 for roll in damage_rolls if roll == 6) >= 2

class CombatAction:
    def __init__(self, name, description, execute, target_required=False):
        self.name = name
        self.description = description
        self.execute = execute
        self.target_required = target_required

def move_action(character, combat_handler, distance=None, *args):
    if not combat_handler.use_action(character, "move"):
        return "You've already used your move action this turn."

    max_distance = character.character_sheet.move * 2  # MOVE stat in yards
    
    if distance is None:
        distance = max_distance
    else:
        try:
            distance = int(distance)
            if distance > max_distance:
                return f"You can't move more than {max_distance} yards in one action."
        except ValueError:
            return "Please provide a valid number for distance."

    current_pos = combat_handler.get_relative_position(character)
    new_pos = current_pos + distance
    
    combat_handler.update_position(character, new_pos)
    
    return f"{character.name} moved {distance} yards. New relative position: {new_pos} yards."

def run_action(character, combat_handler, distance=None, *args):
    if combat_handler.actions_used[character]["move"] and combat_handler.actions_used[character]["regular"]:
        return "You've already used both your actions this turn."

    if not combat_handler.actions_used[character]["move"]:
        move_result = move_action(character, combat_handler, distance)
        if "moved" not in move_result:  # Check if the move was successful
            return move_result
    
    # Use the regular action for the second move
    if not combat_handler.use_action(character, "regular"):
        return "You've already used your regular action this turn."

    max_distance = character.character_sheet.move * 2  # MOVE stat in yards
    
    if distance is None:
        distance = max_distance
    else:
        try:
            distance = int(distance)
            if distance > max_distance:
                return f"You can't move more than {max_distance} yards in one action."
        except ValueError:
            return "Please provide a valid number for distance."

    current_pos = combat_handler.get_relative_position(character)
    new_pos = current_pos + distance
    
    combat_handler.update_position(character, new_pos)
    
    return f"{character.name} ran an additional {distance} yards. New relative position: {new_pos} yards."

def attack(character, combat_handler, target_name, *args):
    if not combat_handler.use_action(character, "regular"):
        return "You've already used your regular action this turn."

    target = combat_handler.get_combatant(target_name)
    if not target:
        return f"No target named '{target_name}' found."
    
    weapon = character.character_sheet.eqweapon
    if not weapon:
        return f"{character.name} has no equipped weapon."
    
    if weapon.current_ammo <= 0:
        return f"{character.name}'s {weapon.name} is out of ammo!"
    
    # Calculate distance and get the appropriate DV
    distance = calculate_distance(character, target)
    range_dv = weapon.get_dv_for_range(distance)
    
    if range_dv is None:
        return f"{target.name} is out of range for {character.name}'s {weapon.name}."
    
    # Roll for attack success
    attack_roll = random.randint(1, 10) + character.character_sheet.reflex + character.character_sheet.weapon_skill
    attack_success = attack_roll >= range_dv
    
    if attack_success:
        damage_rolls = roll_damage(weapon.damage)
        total_damage = sum(damage_rolls)
        is_critical = check_critical(damage_rolls)

        target_armor = target.character_sheet.eqarmor
        armor_sp = target_armor.sp if target_armor else 0

        # Apply special ammo effects
        if weapon.ammo_type == AmmoType.ARMOR_PIERCING:
            armor_sp = max(0, armor_sp - 2)  # Reduce SP by 2
        elif weapon.ammo_type == AmmoType.EXPANSIVE:
            total_damage += 2  # Add 2 to the damage

        damage_after_armor = max(0, total_damage - armor_sp)

        target.character_sheet.take_damage(damage_after_armor)
        weapon.current_ammo -= 1
        weapon.save()

        result = f"{character.name} attacks {target.name} with {weapon.name} at {distance}m for {damage_after_armor} damage!"

        if is_critical or target.character_sheet._current_hp < 1:
            critical_injury = apply_critical_injury(target)
            target.character_sheet.take_damage(5)  # Additional 5 damage from critical injury
            result += f"\nCRITICAL HIT! {target.name} suffers a {critical_injury} and takes 5 additional damage!"

        if target.character_sheet._current_hp <= 0:
            result += f"\n{target.name} has been incapacitated!"
            combat_handler.remove_combatant(target)
    else:
        result = f"{character.name}'s attack on {target.name} at {distance}m missed! (Roll: {attack_roll}, needed: {range_dv})"
        weapon.current_ammo -= 1
        weapon.save()

    return result

def aimed_shot(character, combat_handler, target_name, aim_location, *args):
    if not combat_handler.use_action(character, "regular"):
        return "You've already used your regular action this turn."

    target = combat_handler.get_combatant(target_name)
    if not target:
        return f"No target named '{target_name}' found."
    if aim_location not in ["head", "held_item", "leg"]:
        return f"Invalid aim location: {aim_location}"
    # Implement aimed shot logic here
    return f"{character.name} performs an aimed shot at {target.name}'s {aim_location}!"

def autofire(character, combat_handler, target_name, *args):
    if not combat_handler.use_action(character, "regular"):
        return "You've already used your regular action this turn."

    target = combat_handler.get_combatant(target_name)
    if not target:
        return f"No target named '{target_name}' found."
    if character.db.ammo < 10:
        return "Not enough ammo for autofire!"
    character.db.ammo -= 10
    # Implement autofire logic here
    return f"{character.name} uses autofire against {target.name}!"

def suppressive_fire(character, combat_handler, *args):
    if not combat_handler.use_action(character, "regular"):
        return "You've already used your regular action this turn."

    if character.db.ammo < 10:
        return "Not enough ammo for suppressive fire!"
    character.db.ammo -= 10
    # Implement suppressive fire logic here
    return f"{character.name} uses suppressive fire!"

COMBAT_ACTIONS = {
    "move": CombatAction("Move", "Move up to MOVE STAT x 2 yards", move_action),
    "run": CombatAction("Run", "Use both actions to move up to MOVE STAT x 4 yards", run_action),
    "attack": CombatAction("Attack", "Make a Melee or Ranged Attack", attack, target_required=True),
    "aimed_shot": CombatAction("Aimed Shot", "Make an aimed shot at a specific body part", aimed_shot, target_required=True),
    "autofire": CombatAction("Autofire", "Use autofire mode", autofire, target_required=True),
    "suppressive_fire": CombatAction("Suppressive Fire", "Use suppressive fire", suppressive_fire),
}

class CombatHandler:
    def __init__(self, combatants):
        self.combatants = combatants
        self.turn_order = self.determine_initiative()
        self.current_turn = 0
        self.actions_used = {combatant: {"move": False, "regular": False} for combatant in combatants}
        self.initialize_positions()

    def determine_initiative(self):
        return sorted(self.combatants, key=lambda x: x.character_sheet.initiative, reverse=True)

    def get_current_combatant(self):
        return self.turn_order[self.current_turn]

    def next_turn(self):
        self.current_turn = (self.current_turn + 1) % len(self.turn_order)
        current_character = self.get_current_combatant()
        self.reset_actions(current_character)
        return current_character

    def is_combat_over(self):
        active_combatants = [c for c in self.combatants if c.character_sheet._current_hp > 0]
        return len(active_combatants) <= 1

    def get_combatant(self, name):
        return next((c for c in self.combatants if c.name.lower() == name.lower()), None)

    def remove_combatant(self, combatant):
        if combatant in self.combatants:
            self.combatants.remove(combatant)
        if combatant in self.turn_order:
            self.turn_order.remove(combatant)

    def initialize_positions(self):
        for i, combatant in enumerate(self.combatants):
            combatant.db.combat_position = i * 10  # Start combatants 10 yards apart

    def get_relative_position(self, character):
        return character.db.combat_position - self.combatants[0].db.combat_position

    def update_position(self, character, new_position):
        character.db.combat_position = new_position

    def reset_actions(self, character):
        self.actions_used[character] = {"move": False, "regular": False}

    def use_action(self, character, action_type):
        if self.actions_used[character][action_type]:
            return False
        self.actions_used[character][action_type] = True
        return True

class CombatCommand(Command):
    key = "combat"
    aliases = ["fight"]
    help_category = "Combat"

    def func(self):
        if not self.caller.ndb.combat_handler:
            self.caller.msg("You are not in combat.")
            return

        combat_handler = self.caller.ndb.combat_handler
        if combat_handler.turn_order[combat_handler.current_turn] != self.caller:
            self.caller.msg("It's not your turn.")
            return

        if not self.args:
            self.caller.msg("Available actions: " + ", ".join(COMBAT_ACTIONS.keys()))
            return

        action_name, *action_args = self.args.split()
        action_name = action_name.lower()

        if action_name not in COMBAT_ACTIONS:
            self.caller.msg(f"Unknown action: {action_name}")
            return

        action = COMBAT_ACTIONS[action_name]
        
        result = action.execute(self.caller, combat_handler, *action_args)
        self.caller.location.msg_contents(result)

        # Check if both actions are used
        if all(combat_handler.actions_used[self.caller].values()):
            next_character = combat_handler.next_turn()
            self.caller.location.msg_contents(f"It's now {next_character.name}'s turn.")
        else:
            remaining_actions = [action for action, used in combat_handler.actions_used[self.caller].items() if not used]
            self.caller.msg(f"You still have your {' and '.join(remaining_actions)} action{'s' if len(remaining_actions) > 1 else ''} available.")

class CombatStartCommand(Command):
    key = "startcombat"
    help_category = "Combat"

    def func(self):
        if self.caller.ndb.combat_handler:
            self.caller.msg("You are already in combat.")
            return

        if not self.args:
            self.caller.msg("Usage: startcombat <target1> [<target2> ...]")
            return

        targets = [self.caller.search(arg) for arg in self.args.split()]
        targets = [target for target in targets if target]

        if not targets:
            self.caller.msg("No valid targets found.")
            return

        combatants = [self.caller] + targets
        combat_handler = CombatHandler(combatants)

        for char in combatants:
            char.ndb.combat_handler = combat_handler
        self.caller.location.ndb.combat_handler = combat_handler

        self.caller.location.msg_contents("Combat has started!")
        self.show_initiative_order(combat_handler)

        first_combatant = combat_handler.get_current_combatant()
        self.caller.location.msg_contents(f"It's {first_combatant.name}'s turn.")

    def show_initiative_order(self, combat_handler):
        table = EvTable("Initiative Order", "Character", "HP", border="cells")
        for i, combatant in enumerate(combat_handler.turn_order):
            cs = combatant.character_sheet
            table.add_row(
                i + 1,
                combatant.name,
                f"{cs._current_hp}/{cs._max_hp}"
            )
        table_str = str(table)
        self.caller.location.msg_contents(f"Current combat order:\n{table_str}")

class CmdReload(Command):
    """
    Reload your currently equipped weapon.

    Usage:
      reload

    This command reloads your currently equipped weapon with the appropriate ammunition from your inventory.
    """

    key = "reload"
    locks = "cmd:all()"

    def func(self):
        character = self.caller
        weapon = character.character_sheet.eqweapon

        if not weapon:
            character.msg("You don't have a weapon equipped.")
            return

        inventory = character.character_sheet.inventory
        ammo = inventory.ammunition.filter(ammo_type=weapon.ammo_type).first()

        if not ammo:
            character.msg(f"You don't have any {weapon.ammo_type} ammunition in your inventory.")
            return

        reloaded = weapon.reload(ammo)
        if reloaded:
            character.msg(f"You reload your {weapon.name} with {reloaded} rounds of {weapon.ammo_type} ammunition.")
        else:
            character.msg(f"Your {weapon.name} is already fully loaded.")

class CmdJoinCombat(Command):
    """
    Join an ongoing combat.

    Usage:
      joincombat

    This command allows a character to join an ongoing combat in their current location.
    """
    key = "joincombat"
    aliases = ["jc", "join combat"]
    lock = "cmd:all()"
    help_category = "Combat"

    def func(self):
        # Check if there's an ongoing combat in the character's location
        location = self.caller.location
        combat = CombatHandler.get_combat(location)

        if not combat:
            self.caller.msg("There is no ongoing combat here to join.")
            return

        # Check if the character is already in combat
        if combat.is_character_in_combat(self.caller):
            self.caller.msg("You are already in this combat.")
            return

        # Add the character to the combat
        combat.add_character(self.caller)
        self.caller.msg("You have joined the combat!")
        location.msg_contents(f"{self.caller.name} has joined the combat!", exclude=[self.caller])

def calculate_distance(char1, char2):
    # Assuming characters have a 'combat_position' attribute
    return abs(char1.db.combat_position - char2.db.combat_position)