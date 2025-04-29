# commands/netrun_commands.py

from evennia.commands.default.muxcommand import MuxCommand
from evennia.utils.evmenu import EvMenu
from world.netrunning.models import Cyberdeck, NetArchitecture, NetrunSession, Node, Program, ICE, BlackICE
from world.cyberpunk_sheets.models import CharacterSheet
from world.inventory.models import Gear, CyberwareInstance, Inventory
from world.netrunning.interface import NetrunnerActions, NetCombat
from evennia import DefaultCharacter
from typeclasses.net_architecture import NetArchitecture  # Adjust import path as needed

class CmdNet(MuxCommand):
    """
    Command for netrunning operations.

    Usage:
      net/run <architecture>      - Initiate a netrun against an architecture
      net/install <program>       - Install a program on your cyberdeck
      net/programs                - List installed programs on your cyberdeck
      net/list                    - List all available net architectures

    Examples:
      net/run Arasaka             - Start a netrun against Arasaka architecture
      net/install Sword           - Install the Sword program
      net/programs                - Show all programs installed on your cyberdeck
      net/list                    - Display all available architectures
    """
    key = "net"
    locks = "cmd:all()"
    help_category = "Netrunning"
    switch_options = ("run", "install", "programs", "list")

    def func(self):
        if not self.switches:
            self.caller.msg(self.__doc__)
            return

        # Handle different switches
        if "run" in self.switches:
            self.cmd_run()
        elif "install" in self.switches:
            self.cmd_install()
        elif "programs" in self.switches:
            self.cmd_programs()
        elif "list" in self.switches:
            self.cmd_list()
        else:
            self.caller.msg(f"Unknown switch. Use one of: {', '.join(self.switch_options)}")

    def cmd_run(self):
        """Initiate a netrun against an architecture."""
        if not self.args:
            self.caller.msg("Usage: net/run <architecture>")
            return

        # Check if the character is a Netrunner
        try:
            char_sheet = CharacterSheet.objects.get(character=self.caller)
            if char_sheet.role != "Netrunner":
                self.caller.msg("Only Netrunners can perform netruns.")
                return
        except CharacterSheet.DoesNotExist:
            self.caller.msg("You don't have a character sheet.")
            return

        # Check if the character has a Cyberdeck (either as gear or cyberware)
        cyberdeck = None
        try:
            inventory = Inventory.objects.get(character=char_sheet)
            gear_cyberdeck = next((gear for gear in inventory.gear.all() if gear.is_cyberdeck), None)
        except Inventory.DoesNotExist:
            gear_cyberdeck = None

        cyberware_cyberdeck = next((cw for cw in char_sheet.cyberware_instances.filter(installed=True) if cw.is_cyberdeck), None)

        if gear_cyberdeck:
            cyberdeck, created = Cyberdeck.objects.get_or_create(
                gear=gear_cyberdeck,
                defaults={'name': gear_cyberdeck.name, 'owner': char_sheet}
            )
        elif cyberware_cyberdeck:
            cyberdeck, created = Cyberdeck.objects.get_or_create(
                cyberware=cyberware_cyberdeck,
                defaults={'name': cyberware_cyberdeck.cyberware.name, 'owner': char_sheet}
            )

        if not cyberdeck:
            self.caller.msg("You need a Cyberdeck to perform a netrun.")
            return

        # Find the target architecture
        arch_name = self.args.strip()
        try:
            architecture = NetArchitecture.objects.get(name__iexact=arch_name)
        except NetArchitecture.DoesNotExist:
            self.caller.msg(f"Architecture '{arch_name}' not found.")
            return

        # Start the netrun session
        netrun_session = NetrunSession.objects.create(
            netrunner=char_sheet,
            architecture=architecture,
            current_node=architecture.nodes.first(),
            is_active=True
        )

        self.caller.msg(f"Initiating netrun against {architecture.name}...")
        
        # Define the menu nodes
        def netrun_node(caller, raw_string, **kwargs):
            netrun_session = caller.ndb.netrun_session
            if not netrun_session or not netrun_session.is_active:
                caller.msg("Your netrun session has ended.")
                return None

            node = netrun_session.current_node
            text = f"You are at node: {node.name}\n{node.description}"
            text += f"\nICE: {node.ice.name if node.ice else 'None'}"
            text += f"\nPrograms: {', '.join(p.name for p in cyberdeck.installed_programs.all())}"

            options = [
                {"key": "1", "desc": "Backdoor", "goto": "perform_action", "exec": NetrunnerActions.backdoor},
                {"key": "2", "desc": "Cloak", "goto": "perform_action", "exec": NetrunnerActions.cloak},
                {"key": "3", "desc": "Control", "goto": "perform_action", "exec": NetrunnerActions.control},
                {"key": "4", "desc": "Eye-Dee", "goto": "perform_action", "exec": NetrunnerActions.eye_dee},
                {"key": "5", "desc": "Pathfinder", "goto": "perform_action", "exec": NetrunnerActions.pathfinder},
                {"key": "6", "desc": "Scanner", "goto": "perform_action", "exec": NetrunnerActions.scanner},
                {"key": "7", "desc": "Slide", "goto": "perform_action", "exec": NetrunnerActions.slide},
                {"key": "8", "desc": "Virus", "goto": "perform_action", "exec": NetrunnerActions.virus},
            ]

            if node.ice:
                options.append({"key": "C", "desc": f"Attempt to crack {node.ice.name} ICE", "goto": "crack_ice"})

            next_nodes = Node.objects.filter(architecture=netrun_session.architecture, level=node.level+1)
            for i, next_node in enumerate(next_nodes, start=9):
                options.append({"key": str(i), "desc": f"Move to {next_node.name}", "goto": ("move_to_node", {"node_id": next_node.id})})
                options.append({"key": "A", "desc": "Activate a program", "goto": "activate_program"})
                options.append({"key": "J", "desc": "Jack out", "goto": "jack_out"})

            return text, options

        def perform_action(caller, raw_string, **kwargs):
            action = kwargs.get("exec")
            if action:
                action(caller, caller.ndb.netrun_session.current_node)
            return "netrun_node"

        def crack_ice(caller, raw_string, **kwargs):
            netrun_session = caller.ndb.netrun_session
            current_node = netrun_session.current_node
            ice = current_node.ice

            if not ice:
                caller.msg("There's no ICE to crack on this node.")
                return "netrun_node"

            caller.msg(f"Attempting to crack {ice.name} ICE...")
            
            success, damage = NetCombat.attack(caller, ice)

            if success:
                ice.rez -= damage
                caller.msg(f"You successfully attack the ICE, dealing {damage} damage!")
                if ice.rez <= 0:
                    caller.msg(f"You've cracked the {ice.name} ICE!")
                    current_node.ice = None
                    current_node.save()
                else:
                    caller.msg(f"The ICE is damaged but still active. It has {ice.rez} REZ remaining.")
            else:
                caller.msg("Your attack failed to penetrate the ICE's defenses.")
                
                # ICE counterattack
                ice_success, ice_damage = NetCombat.attack(ice, caller)
                if ice_success:
                    caller.db.hp -= ice_damage
                    caller.msg(f"The ICE counterattacks, dealing {ice_damage} damage to you!")
                    if caller.db.hp <= 0:
                        caller.msg("You've taken too much damage. Emergency jack-out initiated.")
                        return "jack_out"
                else:
                    caller.msg("You manage to defend against the ICE's counterattack.")

            return "netrun_node"

        def move_to_node(caller, raw_string, **kwargs):
            netrun_session = caller.ndb.netrun_session
            node_id = kwargs.get('node_id')
            
            try:
                new_node = Node.objects.get(id=node_id)
                netrun_session.current_node = new_node
                netrun_session.save()
                caller.msg(f"Moving to node: {new_node.name}")
            except Node.DoesNotExist:
                caller.msg("Invalid node.")
            
            return "netrun_node"

        def jack_out(caller, raw_string, **kwargs):
            netrun_session = caller.ndb.netrun_session
            netrun_session.is_active = False
            netrun_session.save()
            caller.msg("You've jacked out of the system.")
            return None

        # Store the netrun_session in the caller's ndb attribute
        self.caller.ndb.netrun_session = netrun_session

        # Create the EvMenu
        EvMenu(self.caller,
               {
                   "netrun_node": netrun_node,
                   "perform_action": perform_action,
                   "crack_ice": crack_ice,
                   "move_to_node": move_to_node,
                   "jack_out": jack_out
               },
               startnode="netrun_node",
               cmdset_mergetype="Replace",
               cmdset_priority=1,
               auto_quit=True,
               auto_look=False,
               auto_help=False,
               cmd_on_exit="look",
               persistent=False)

    def cmd_install(self):
        """Install a program on your cyberdeck."""
        if not self.args:
            self.caller.msg("Usage: net/install <program>")
            return

        program_name = self.args.strip()
        try:
            program = Program.objects.get(name__iexact=program_name)
        except Program.DoesNotExist:
            self.caller.msg(f"Program '{program_name}' not found.")
            return

        # Check if the character has a Cyberdeck
        try:
            char_sheet = CharacterSheet.objects.get(character=self.caller)
        except CharacterSheet.DoesNotExist:
            self.caller.msg("You don't have a character sheet.")
            return

        # Try to get cyberdeck (from gear or cyberware)
        cyberdeck = None
        try:
            inventory = Inventory.objects.get(character=char_sheet)
            gear_cyberdeck = next((gear for gear in inventory.gear.all() if gear.is_cyberdeck), None)
        except Inventory.DoesNotExist:
            gear_cyberdeck = None

        cyberware_cyberdeck = next((cw for cw in char_sheet.cyberware_instances.filter(installed=True) if cw.is_cyberdeck), None)

        if gear_cyberdeck:
            cyberdeck, created = Cyberdeck.objects.get_or_create(
                gear=gear_cyberdeck,
                defaults={'name': gear_cyberdeck.name, 'owner': char_sheet}
            )
        elif cyberware_cyberdeck:
            cyberdeck, created = Cyberdeck.objects.get_or_create(
                cyberware=cyberware_cyberdeck,
                defaults={'name': cyberware_cyberdeck.cyberware.name, 'owner': char_sheet}
            )

        if not cyberdeck:
            self.caller.msg("You don't have a Cyberdeck installed.")
            return

        if cyberdeck.available_slots > 0:
            cyberdeck.install_program(program)
            self.caller.msg(f"Successfully installed {program.name} on your Cyberdeck.")
        else:
            self.caller.msg("Your Cyberdeck has no available slots for new programs.")

    def cmd_programs(self):
        """List all programs installed on your cyberdeck."""
        # Check if the character has a Cyberdeck
        try:
            char_sheet = CharacterSheet.objects.get(character=self.caller)
        except CharacterSheet.DoesNotExist:
            self.caller.msg("You don't have a character sheet.")
            return

        # Try to get cyberdeck (from gear or cyberware)
        cyberdeck = None
        try:
            inventory = Inventory.objects.get(character=char_sheet)
            gear_cyberdeck = next((gear for gear in inventory.gear.all() if gear.is_cyberdeck), None)
        except Inventory.DoesNotExist:
            gear_cyberdeck = None

        cyberware_cyberdeck = next((cw for cw in char_sheet.cyberware_instances.filter(installed=True) if cw.is_cyberdeck), None)

        if gear_cyberdeck:
            cyberdeck, created = Cyberdeck.objects.get_or_create(
                gear=gear_cyberdeck,
                defaults={'name': gear_cyberdeck.name, 'owner': char_sheet}
            )
        elif cyberware_cyberdeck:
            cyberdeck, created = Cyberdeck.objects.get_or_create(
                cyberware=cyberware_cyberdeck,
                defaults={'name': cyberware_cyberdeck.cyberware.name, 'owner': char_sheet}
            )

        if not cyberdeck:
            self.caller.msg("You don't have a Cyberdeck installed.")
            return

        installed_programs = cyberdeck.installed_programs.all()
        if not installed_programs:
            self.caller.msg("You have no programs installed on your Cyberdeck.")
        else:
            self.caller.msg("Installed programs:")
            for program in installed_programs:
                self.caller.msg(f"- {program.name}: {program.description}")

    def cmd_list(self):
        """List all available Net Architectures."""
        architectures = NetArchitecture.objects.all().order_by('db_tags__db_key')
        
        if not architectures:
            self.caller.msg("No Net Architectures have been created yet.")
            return

        table = self.styled_table("Name", "Difficulty", "Nodes", "Description")
        for arch in architectures:
            table.add_row(
                arch.db.name,
                arch.db.difficulty,
                arch.get_node_count(),
                arch.db.description[:30] + "..." if arch.db.description else ""
            )

        self.caller.msg("|wAvailable Net Architectures:|n")
        self.caller.msg(table)