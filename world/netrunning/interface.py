from evennia import Command
from evennia.utils.evmenu import EvMenu
from world.netrunning.models import Cyberdeck, NetArchitecture, NetrunSession, Node, Program
from world.cyberpunk_sheets.models import CharacterSheet
import random

class NetrunnerActions:
    @staticmethod
    def roll_check(interface_skill, difficulty):
        return random.randint(1, 10) + interface_skill >= difficulty

    @staticmethod
    def backdoor(caller, target):
        difficulty = target.password_strength  # You'll need to add this attribute to your Node model
        if NetrunnerActions.roll_check(caller.db.interface, difficulty):
            caller.msg("You successfully bypass the password!")
            # Logic to unlock the node
        else:
            caller.msg("You failed to crack the password.")

    @staticmethod
    def cloak(caller):
        difficulty = 15  # Set an appropriate difficulty
        if NetrunnerActions.roll_check(caller.db.interface, difficulty):
            caller.ndb.netrun_session.is_cloaked = True
            caller.msg("You successfully cloak your actions.")
        else:
            caller.msg("You failed to cloak your actions.")

    @staticmethod
    def control(caller, target):
        difficulty = target.control_difficulty  # Add this attribute to your Node model
        if NetrunnerActions.roll_check(caller.db.interface, difficulty):
            caller.msg(f"You take control of the {target.name} node!")
            # Logic to give control of the node to the netrunner
        else:
            caller.msg(f"You failed to take control of the {target.name} node.")

    @staticmethod
    def eye_dee(caller, target):
        difficulty = target.eye_dee_difficulty  # Add this attribute to your Node model
        if NetrunnerActions.roll_check(caller.db.interface, difficulty):
            caller.msg(f"You identify the {target.name}: {target.description}")
            if hasattr(target, 'value'):
                caller.msg(f"Estimated value: {target.value}")
        else:
            caller.msg("You failed to identify the target.")

    @staticmethod
    def pathfinder(caller):
        netrun_session = caller.ndb.netrun_session
        architecture = netrun_session.architecture
        check_result = caller.db.interface + random.randint(1, 10)
        revealed_floors = min(check_result, architecture.total_floors)
        caller.msg(f"You reveal {revealed_floors} floors of the architecture:")
        for floor in range(revealed_floors):
            nodes = Node.objects.filter(architecture=architecture, level=floor)
            caller.msg(f"Floor {floor}: {', '.join(node.name for node in nodes)}")

    @staticmethod
    def scanner(caller):
        # Implementation for scanner action
        pass

    @staticmethod
    def slide(caller):
        netrun_session = caller.ndb.netrun_session
        current_node = netrun_session.current_node
        if not current_node.ice:
            caller.msg("There's no ICE to slide away from.")
            return
        
        ice = current_node.ice
        netrunner_roll = caller.db.interface + random.randint(1, 10)
        ice_roll = ice.perception + random.randint(1, 10)
        
        if netrunner_roll > ice_roll:
            # Move to an adjacent node
            adjacent_nodes = Node.objects.filter(architecture=netrun_session.architecture, level=current_node.level)
            if adjacent_nodes.exists():
                new_node = random.choice(adjacent_nodes)
                netrun_session.current_node = new_node
                netrun_session.save()
                caller.msg(f"You successfully slide away to {new_node.name}!")
            else:
                caller.msg("You slide away, but there's nowhere to go on this level.")
        else:
            caller.msg("You failed to slide away from the ICE.")

    @staticmethod
    def virus(caller, target):
        difficulty = 12  # Base difficulty, adjust as needed
        if NetrunnerActions.roll_check(caller.db.interface, difficulty):
            # Implement virus logic here
            caller.msg("You successfully plant a virus in the system!")
        else:
            caller.msg("You failed to plant the virus.")

class NetCombat:
    @staticmethod
    def attack(attacker, defender):
        attacker_roll = random.randint(1, 10) + attacker.db.interface
        if hasattr(attacker, 'active_program') and attacker.active_program:
            attacker_roll += attacker.active_program.atk

        defender_roll = random.randint(1, 10) + defender.dfv

        if attacker_roll > defender_roll:
            damage = random.randint(1, 6)  # Basic damage, can be modified based on programs
            if hasattr(attacker, 'active_program') and attacker.active_program:
                damage += attacker.active_program.dmg
            defender.rez -= damage
            return True, damage
        return False, 0
    
    @staticmethod
    def apply_program_effect(attacker, defender, program):
        # Implement program-specific effects here
        pass

    def crack_ice(caller, raw_string, **kwargs):
        netrun_session = caller.ndb.netrun_session
        current_node = netrun_session.current_node
        ice = current_node.ice  # Assume the Node model has an 'ice' field

        if not ice:
            caller.msg("There's no ICE to crack on this node.")
            return "netrun_node"

        caller.msg(f"Attempting to crack {ice.name} ICE...")
        
        # Check if the netrunner has an active attack program
        active_program = caller.ndb.active_program
        if active_program:
            caller.msg(f"Using {active_program.name} in your attack.")

        # Initiate combat
        ice_cracked = NetCombat.attack(caller, ice)

        if ice_cracked:
            # Remove ICE from the node
            current_node.ice = None
            current_node.save()
            caller.msg("You've successfully cracked the ICE. The node is now accessible.")
        else:
            # ICE counterattack
            ice_attack_roll = random.randint(1, 10) + ice.atk
            netrunner_defense_roll = random.randint(1, 10) + caller.db.interface

            if ice_attack_roll > netrunner_defense_roll:
                damage = random.randint(1, 6)  # Basic ICE damage
                caller.db.hp -= damage
                caller.msg(f"The ICE counterattacks, dealing {damage} damage to you!")
                if caller.db.hp <= 0:
                    caller.msg("You've taken too much damage. Emergency jack-out initiated.")
                    return "jack_out"
            else:
                caller.msg("You manage to defend against the ICE's counterattack.")

        return "netrun_node"

    @staticmethod
    def apply_effect(attacker, defender, program):
        if program:
            # Apply program effect
            attacker.msg(f"You hit with {program.name}! {program.effect}")
            if isinstance(defender, Program):
                defender.rez -= random.randint(1, 6)  # Example: deal 1d6 damage to ICE
                if defender.rez <= 0:
                    attacker.msg(f"You've destroyed the {defender.name} ICE!")
                    # Logic to remove the ICE from the node
            else:
                # Logic for effects on Netrunner targets
                pass
        else:
            # Basic Zap attack
            damage = random.randint(1, 6)
            if isinstance(defender, Program):
                defender.rez -= damage
                attacker.msg(f"You zap the {defender.name} for {damage} damage!")
                if defender.rez <= 0:
                    attacker.msg(f"You've destroyed the {defender.name} ICE!")
                    # Logic to remove the ICE from the node
            else:
                defender.db.hp -= damage
                attacker.msg(f"You zap the target netrunner for {damage} damage!")

banhammer = Program.objects.create(
    name="Banhammer",
    atk=1,
    dfv=0,
    rez=0,
    effect="Does 3d6 REZ to a Non-Black ICE Program, or 2d6 REZ to a Black ICE Program.",
    cost=50,
    icon="A giant glowing white sledgehammer wielded by the Netrunner."
)

sword_ice = Program.objects.create(
    name="Sword",
    atk=1,
    dfv=0,
    rez=0,
    effect="Does 3d6 REZ to a Black ICE Program, or 2d6 REZ to a Non-Black ICE Program.",
    cost=50,
    icon="Glowing energy katana appearing from the Netrunner's hand."
)

deckkrash = Program.objects.create(
    name="DeckKRASH",
    atk=0,
    dfv=0,
    rez=0,
    effect="Enemy Netrunner is forcibly and unsafely Jacked Out of the Architecture, suffering the effect of all Rezzed enemy Black ICE they've encountered in the Architecture as they leave.",
    cost=100,
    icon="Cartoon stick of dynamite thrown by the Netrunner."
)

nervescrub = Program.objects.create(
    name="Nervescrub",
    atk=0,
    dfv=0,
    rez=0,
    effect="Enemy Netrunner's INT, REF, and DEX are each lowered by 1d6 for the next hour (minimum 1). The effects are largely psychosomatic and leave no permanent effects.",
    cost=100,
    icon="Chrome ball thrown by the Netrunner that sparks with electricity."
)

vrizzbolt = Program.objects.create(
    name="Vrizzbolt",
    atk=1,
    dfv=0,
    rez=0,
    effect="Damage direct to a Netrunner's brain and lowers the amount of total NET Actions the Netrunner can accomplish on their next Turn by 1 (minimum 2).",
    cost=50,
    icon="A double helix comprised of flickering neon light appearing from the Netrunner's finger."
)

poison_flatline = Program.objects.create(
    name="Poison Flatline",
    atk=0,
    dfv=0,
    rez=0,
    effect="Destroys a single Non-Black ICE Program installed on the Netrunner target's Cyberdeck at random.",
    cost=100,
    icon="Beam of neon green light shot from the Netrunner's finger."
)

superglue = Program.objects.create(
    name="Superglue",
    atk=2,
    dfv=0,
    rez=0,
    effect="Enemy Netrunner cannot progress deeper into the Architecture or Jack Out safely for 1d6 Rounds (enemy Netrunner can still perform an unsafe Jack Out, though). Each copy of this Program can only be used once per Netrun.",
    cost=100,
    icon="A mass of sticky red goop fired from the Netrunner's hand."
)
def netrun_node(caller, raw_string, **kwargs):
    netrun_session = caller.ndb.netrun_session
    if not netrun_session or not netrun_session.is_active:
        caller.msg("Your netrun session has ended.")
        return None

    node = netrun_session.current_node
    text = f"You are at node: {node.name}\n{node.description}"

    options = [
        {"key": "1", "desc": "Backdoor", "goto": "perform_action", "exec": NetrunnerActions.backdoor},
        {"key": "2", "desc": "Cloak", "goto": "perform_action", "exec": NetrunnerActions.cloak},
        # Add other actions here
        {"key": "A", "desc": "Attack", "goto": "choose_attack_target"},
        {"key": "P", "desc": "Use Program", "goto": "choose_program"},
        {"key": "J", "desc": "Jack out", "goto": "jack_out"}
    ]

    return text, options

def perform_action(caller, raw_string, **kwargs):
    action = kwargs.get("exec")
    if action:
        action(caller, caller.ndb.netrun_session.current_node)
    return "netrun_node"

def choose_attack_target(caller, raw_string, **kwargs):
    # Logic to choose attack target (ICE or enemy netrunner)
    # Then call NetCombat.attack()
    return "netrun_node"

def choose_program(caller, raw_string, **kwargs):
    # Logic to choose and use a program
    return "netrun_node"

# Update your CmdNetrun class to use these new functions and classes