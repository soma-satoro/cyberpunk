import random
from evennia.commands.default.muxcommand import MuxCommand
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
    """Determine a character's wound state based on their current HP."""
    # Get current HP and max HP directly from character attributes
    current_hp = character.db.current_hp
    max_hp = character.db.max_hp
    
    if current_hp is None or max_hp is None:
        # Fallback to using CharacterSheet model if DB attributes aren't available
        try:
            cs = CharacterSheet.objects.get(character=character)
            current_hp = cs._current_hp
            max_hp = cs._max_hp
        except CharacterSheet.DoesNotExist:
            # Handle the case where the character doesn't have a sheet
            return None
    
    hp_ratio = current_hp / max_hp
    
    if current_hp <= 0:
        return WoundState.DEAD
    elif current_hp < 1:
        return WoundState.MORTALLY_WOUNDED
    elif hp_ratio <= 0.5:
        return WoundState.SERIOUSLY_WOUNDED
    elif current_hp < max_hp:
        return WoundState.LIGHTLY_WOUNDED
    else:
        return None  # Unwounded

def apply_wound_effects(character):
    """Apply wound effects to a character based on their wound state."""
    wound_state = determine_wound_state(character)
    
    # Initialize attributes if they don't exist
    if not hasattr(character.db, 'wound_effect'):
        character.db.wound_effect = None
    if not hasattr(character.db, 'stabilization_dv'):
        character.db.stabilization_dv = None
    if not hasattr(character.db, 'action_penalty'):
        character.db.action_penalty = 0
    if not hasattr(character.db, 'move_penalty'):
        character.db.move_penalty = 0
    if not hasattr(character.db, 'requires_death_save'):
        character.db.requires_death_save = False
    
    if wound_state == WoundState.LIGHTLY_WOUNDED:
        character.db.wound_effect = "None"
        character.db.stabilization_dv = 10
        character.db.action_penalty = 0
        character.db.move_penalty = 0
        character.db.requires_death_save = False
    elif wound_state == WoundState.SERIOUSLY_WOUNDED:
        character.db.wound_effect = "-2 to all Actions"
        character.db.stabilization_dv = 13
        character.db.action_penalty = -2
        character.db.move_penalty = 0
        character.db.requires_death_save = False
    elif wound_state == WoundState.MORTALLY_WOUNDED:
        character.db.wound_effect = "-4 to all Actions, -6 to MOVE (Minimum 1), Must make a Death Save at start of each Turn"
        character.db.stabilization_dv = 15
        character.db.action_penalty = -4
        character.db.move_penalty = -6
        character.db.requires_death_save = True
    elif wound_state == WoundState.DEAD:
        character.db.wound_effect = "Death"
        character.db.stabilization_dv = None  # Cannot be stabilized
        character.db.action_penalty = 0
        character.db.move_penalty = 0
        character.db.requires_death_save = False
    else:  # Unwounded
        character.db.wound_effect = None
        character.db.stabilization_dv = None
        character.db.action_penalty = 0
        character.db.move_penalty = 0
        character.db.requires_death_save = False

def make_death_save(character):
    """
    Make a death save for a character.
    
    Args:
        character: The character making the death save
        
    Returns:
        bool: True if the character survives, False if they die
    """
    # Get the body attribute for the death save
    body = character.db.body
    
    # Roll 1d10 + modifier
    roll = random.randint(1, 10)
    total = roll + body
    
    # Death save target is 10
    success = total >= 10
    
    if not success:
        # If the character fails, they die
        character.db.current_hp = 0
        character.db.wound_effect = "Death"
    
    return success

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

    # Get the character's MOVE stat, accounting for any penalties from wounds
    move_stat = character.db.move
    move_penalty = character.db.move_penalty if hasattr(character.db, 'move_penalty') else 0
    
    # Calculate effective move stat (minimum of 1)
    effective_move = max(1, move_stat + move_penalty)
    max_distance = effective_move * 2  # MOVE stat in yards
    
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

    # Get the character's MOVE stat, accounting for any penalties from wounds
    move_stat = character.db.move
    move_penalty = character.db.move_penalty if hasattr(character.db, 'move_penalty') else 0
    
    # Calculate effective move stat (minimum of 1)
    effective_move = max(1, move_stat + move_penalty)
    max_distance = effective_move * 2  # MOVE stat in yards
    
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
    
    # Check if the character has an equipped weapon in inventory
    weapon = None
    if hasattr(character, 'inventory') and character.inventory:
        weapon = character.db.equipped_weapon
    
    # Fallback to character sheet for backward compatibility
    if not weapon and hasattr(character, 'character_sheet'):
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
    
    # Get combat stats from character
    reflexes = character.db.reflexes
    
    # Determine the appropriate weapon skill to use
    weapon_skill = 0
    if weapon.weapon_type == "Handgun":
        weapon_skill = character.db.skills.get("handgun", 0)
    elif weapon.weapon_type == "Assault Rifle":
        weapon_skill = character.db.skills.get("shoulder_arms", 0)
    elif weapon.weapon_type == "SMG":
        weapon_skill = character.db.skills.get("handgun", 0)  # SMGs use handgun skill
    elif weapon.weapon_type == "Shotgun":
        weapon_skill = character.db.skills.get("shoulder_arms", 0)
    elif weapon.weapon_type == "Heavy Weapon":
        weapon_skill = character.db.skills.get("heavy_weapons", 0)
    elif weapon.weapon_type == "Melee":
        weapon_skill = character.db.skills.get("melee", 0)
    
    # Include action penalty from wounds
    action_penalty = character.db.action_penalty if hasattr(character.db, 'action_penalty') else 0
    
    # Roll for attack success
    attack_roll = random.randint(1, 10) + reflexes + weapon_skill + action_penalty
    attack_success = attack_roll >= range_dv
    
    if attack_success:
        damage_rolls = roll_damage(weapon.damage)
        total_damage = sum(damage_rolls)
        is_critical = check_critical(damage_rolls)

        # Get target's armor
        target_armor = None
        if hasattr(target, 'inventory') and target.inventory:
            target_armor = target.db.equipped_armor
        
        # Fallback to character sheet for backward compatibility
        if not target_armor and hasattr(target, 'character_sheet'):
            target_armor = target.character_sheet.eqarmor
        
        armor_sp = target_armor.sp if target_armor else 0

        # Apply special ammo effects
        if weapon.ammo_type == AmmoType.ARMOR_PIERCING:
            armor_sp = max(0, armor_sp - 2)  # Reduce SP by 2
        elif weapon.ammo_type == AmmoType.EXPANSIVE:
            total_damage += 2  # Add 2 to the damage

        damage_after_armor = max(0, total_damage - armor_sp)

        # Apply damage to target
        if hasattr(target, 'take_damage') and callable(target.take_damage):
            target.take_damage(damage_after_armor)
        elif target.db.current_hp is not None:
            target.db.current_hp = max(0, target.db.current_hp - damage_after_armor)
        elif hasattr(target, 'character_sheet'):
            target.character_sheet.take_damage(damage_after_armor)
        
        # Reduce ammo
        weapon.current_ammo -= 1
        weapon.save()

        result = f"{character.name} attacks {target.name} with {weapon.name} at {distance}m for {damage_after_armor} damage!"

        # Check for critical hit
        if is_critical or (target.db.current_hp is not None and target.db.current_hp < 1) or \
           (hasattr(target, 'character_sheet') and target.character_sheet._current_hp < 1):
            critical_injury = apply_critical_injury(target)
            
            # Apply additional damage from critical
            if hasattr(target, 'take_damage') and callable(target.take_damage):
                target.take_damage(5)
            elif target.db.current_hp is not None:
                target.db.current_hp = max(0, target.db.current_hp - 5)
            elif hasattr(target, 'character_sheet'):
                target.character_sheet.take_damage(5)
                
            result += f"\nCRITICAL HIT! {target.name} suffers a {critical_injury} and takes 5 additional damage!"

        # Check if target is incapacitated
        target_hp = 0
        if target.db.current_hp is not None:
            target_hp = target.db.current_hp
        elif hasattr(target, 'character_sheet'):
            target_hp = target.character_sheet._current_hp
            
        if target_hp <= 0:
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
        """Determine initiative order based on REF + initiative skill."""
        # Sort combatants by initiative (REF + initiative skill)
        sorted_combatants = sorted(
            self.combatants,
            key=lambda x: self._get_initiative_value(x),
            reverse=True
        )
        return sorted_combatants
    
    def _get_initiative_value(self, character):
        """Get the initiative value for a character."""
        # Check if the character has the attributes directly
        if hasattr(character.db, 'reflexes'):
            initiative = character.db.reflexes + character.db.skills.get('concentration', 0)
            return initiative
        
        # Fallback to character sheet
        if hasattr(character, 'character_sheet'):
            return character.character_sheet.initiative
        
        # Default value if nothing else works
        return 0

    def get_current_combatant(self):
        return self.turn_order[self.current_turn]

    def next_turn(self):
        self.current_turn = (self.current_turn + 1) % len(self.turn_order)
        current_character = self.get_current_combatant()
        self.reset_actions(current_character)
        return current_character

    def is_combat_over(self):
        """Check if combat is over (only one or zero combatants left)."""
        active_combatants = []
        
        for c in self.combatants:
            # Check character attribute first
            if hasattr(c.db, 'current_hp') and c.db.current_hp is not None:
                if c.db.current_hp > 0:
                    active_combatants.append(c)
            # Fallback to character sheet
            elif hasattr(c, 'character_sheet'):
                if c.character_sheet._current_hp > 0:
                    active_combatants.append(c)
        
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

class CmdCombat(MuxCommand):
    """
    Use this command to perform actions in combat, including starting combat,
    joining a combat, and leaving a combat (fleeing).

    Usage:
      combat
      combat <action>
      combat/start <target1>, <target2>, ...
      combat/join <target>
      combat/leave
      combat/flee

    Examples:
      combat
      combat move 10
      combat/start John, Jane, Jim
      combat/join Bob
      combat/leave
      combat/flee
    """
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

        if self.args.startswith("start"):
            self.start_combat()
            return

        if self.args.startswith("join"):
            self.join_combat()
            return
        
        if self.args.startswith("leave"):
            self.leave_combat()
            return

        if self.args.startswith("flee"):
            self.flee_combat()
            return
        
        if self.args.startswith("reload"):
            self.reload_weapon()
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

    def start_combat(self):
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
            # Get HP values directly from character attributes if possible
            current_hp = max_hp = "?"
            
            if hasattr(combatant.db, 'current_hp') and combatant.db.current_hp is not None:
                current_hp = combatant.db.current_hp
                max_hp = combatant.db.max_hp
            elif hasattr(combatant, 'character_sheet'):
                cs = combatant.character_sheet
                current_hp = cs._current_hp
                max_hp = cs._max_hp
                
            table.add_row(
                i + 1,
                combatant.name,
                f"{current_hp}/{max_hp}"
            )
        table_str = str(table)
        self.caller.location.msg_contents(f"Current combat order:\n{table_str}")

    def reload_weapon(self):
        character = self.caller
        
        # Get equipped weapon
        weapon = None
        if hasattr(character.db, 'equipped_weapon'):
            weapon = character.db.equipped_weapon
        
        # Fallback to character sheet
        if not weapon and hasattr(character, 'character_sheet'):
            weapon = character.character_sheet.eqweapon

        if not weapon:
            character.msg("You don't have a weapon equipped.")
            return

        # Get inventory
        inventory = None
        if hasattr(character, 'inventory'):
            inventory = character.inventory
        elif hasattr(character, 'character_sheet'):
            inventory = character.character_sheet.inventory
            
        if not inventory:
            character.msg("You don't have an inventory to get ammunition from.")
            return

        # Find appropriate ammunition
        ammo = inventory.ammunition.filter(ammo_type=weapon.ammo_type).first()

        if not ammo:
            character.msg(f"You don't have any {weapon.ammo_type} ammunition in your inventory.")
            return

        reloaded = weapon.reload(ammo)
        if reloaded:
            character.msg(f"You reload your {weapon.name} with {reloaded} rounds of {weapon.ammo_type} ammunition.")
        else:
            character.msg(f"Your {weapon.name} is already fully loaded.")

    def join_combat(self):
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