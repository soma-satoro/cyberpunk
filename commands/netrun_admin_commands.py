# commands/netrun_admin_commands.py
from evennia.commands.default.muxcommand import MuxCommand
from evennia import Command, CmdSet, DefaultScript
from evennia.utils import create
from world.netrunning.models import NetArchitecture, Node, ICE, BlackICE, Program
import random

class CmdArchitecture(MuxCommand):
    """
    Command for managing Net Architectures.

    Usage:
      arch[itecture]/create         - Initialize a new Net Architecture
      arch[itecture]/name <name>    - Set the name of the architecture
      arch[itecture]/desc <desc>    - Set the description of the architecture
      arch[itecture]/node <name>    - Add a node to the architecture
      arch[itecture]/ice <idx> <y/n>- Set whether node is ICE
      arch[itecture]/icetype <idx> <type> - Set ICE type (Black/White/Red)
      arch[itecture]/icestr <idx> <1-10> - Set ICE strength
      arch[itecture]/nodedesc <idx> <desc> - Set node description
      arch[itecture]/status         - Check current architecture creation status
      arch[itecture]/finish         - Complete architecture creation
      arch[itecture]/cancel         - Cancel architecture creation
      arch[itecture]/generate <diff> <name> <location> - Generate random architecture
                                       <diff> can be basic, standard, uncommon, advanced
    """
    key = "architecture"
    aliases = ["arch"]
    locks = "cmd:perm(Admin)"
    help_category = "Admin"
    
    def func(self):
        # No switch provided, show help
        if not self.switches:
            self.caller.msg(self.__doc__)
            return
            
        # Handle different switches
        switch = self.switches[0]
        
        if switch == "create":
            self.cmd_create()
        elif switch in ["name", "setname"]:
            self.cmd_name()
        elif switch in ["desc", "description", "setdesc"]:
            self.cmd_description()
        elif switch in ["node", "addnode"]:
            self.cmd_add_node()
        elif switch in ["ice", "setice"]:
            self.cmd_set_ice()
        elif switch in ["icetype", "seticetype"]:
            self.cmd_set_ice_type()
        elif switch in ["icestr", "icestrength", "seticestrength"]:
            self.cmd_set_ice_strength()
        elif switch in ["nodedesc", "setnodedesc"]:
            self.cmd_set_node_description()
        elif switch == "status":
            self.cmd_status()
        elif switch == "finish":
            self.cmd_finish()
        elif switch == "cancel":
            self.cmd_cancel()
        elif switch == "generate":
            self.cmd_generate()
        else:
            self.caller.msg(f"Unknown switch '{switch}'. See 'help architecture' for usage.")
    
    def cmd_create(self):
        """Initialize a new Net Architecture."""
        self.caller.msg("Initializing new Net Architecture. Use arch/status to see your progress.")
        # Initialize creation data
        self.caller.ndb._netarch_creation = {"nodes": []}
    
    def cmd_name(self):
        """Set the name of the Net Architecture."""
        if not self.args:
            self.caller.msg("You must specify a name.")
            return
            
        # Create the creation data if it doesn't exist
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.ndb._netarch_creation = {"nodes": []}
            
        self.caller.ndb._netarch_creation["name"] = self.args.strip()
        self.caller.msg(f"Net Architecture name set to '{self.args.strip()}'.")
    
    def cmd_description(self):
        """Set the description of the Net Architecture."""
        if not self.args:
            self.caller.msg("You must specify a description.")
            return
            
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.ndb._netarch_creation = {"nodes": []}
            
        self.caller.ndb._netarch_creation["description"] = self.args.strip()
        self.caller.msg("Description set.")
    
    def cmd_add_node(self):
        """Add a node to the Net Architecture."""
        if not self.args:
            self.caller.msg("You must specify a node name.")
            return
            
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.ndb._netarch_creation = {"nodes": []}
            
        node_name = self.args.strip()
        self.caller.ndb._netarch_creation["nodes"].append({"name": node_name})
        node_idx = len(self.caller.ndb._netarch_creation["nodes"]) - 1
        self.caller.msg(f"Node '{node_name}' added as index {node_idx}.")
    
    def cmd_set_ice(self):
        """Set a node as ICE or not."""
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: arch/ice <node_index> <yes/no>")
            return
            
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.ndb._netarch_creation = {"nodes": []}
            return
            
        index, is_ice = self.args.split()
        try:
            index = int(index)
            if index < 0 or index >= len(self.caller.ndb._netarch_creation["nodes"]):
                self.caller.msg(f"Node index {index} is out of range. Valid indices are 0 to {len(self.caller.ndb._netarch_creation['nodes']) - 1}")
                return
            node = self.caller.ndb._netarch_creation["nodes"][index]
        except (ValueError, IndexError):
            self.caller.msg(f"Invalid index '{index}'. Please provide a number.")
            return
            
        node["is_ice"] = is_ice.lower() in ["yes", "y", "true"]
        if node["is_ice"]:
            self.caller.msg(f"Node {index} set as ICE.")
        else:
            self.caller.msg(f"Node {index} set as not ICE.")
    
    def cmd_set_ice_type(self):
        """Set the ICE type for a node."""
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: arch/icetype <node_index> <Black/White/Red>")
            return
            
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.ndb._netarch_creation = {"nodes": []}
            return
            
        index, ice_type = self.args.split()
        try:
            index = int(index)
            if index < 0 or index >= len(self.caller.ndb._netarch_creation["nodes"]):
                self.caller.msg(f"Node index {index} is out of range. Valid indices are 0 to {len(self.caller.ndb._netarch_creation['nodes']) - 1}")
                return
            node = self.caller.ndb._netarch_creation["nodes"][index]
        except (ValueError, IndexError):
            self.caller.msg(f"Invalid index '{index}'. Please provide a number.")
            return
            
        if ice_type not in ["Black", "White", "Red"]:
            self.caller.msg("Invalid ICE type. Must be Black, White, or Red.")
            return
            
        node["ice_type"] = ice_type
        self.caller.msg(f"ICE type for node {index} set to {ice_type}.")
    
    def cmd_set_ice_strength(self):
        """Set the ICE strength for a node."""
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: arch/icestr <node_index> <1-10>")
            return
            
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.ndb._netarch_creation = {"nodes": []}
            return
            
        index, strength = self.args.split()
        try:
            index = int(index)
            strength = int(strength)
            if index < 0 or index >= len(self.caller.ndb._netarch_creation["nodes"]):
                self.caller.msg(f"Node index {index} is out of range. Valid indices are 0 to {len(self.caller.ndb._netarch_creation['nodes']) - 1}")
                return
            node = self.caller.ndb._netarch_creation["nodes"][index]
        except (ValueError, IndexError):
            self.caller.msg("Invalid node index or strength.")
            return
            
        if not 1 <= strength <= 10:
            self.caller.msg("Strength must be between 1 and 10.")
            return
            
        node["ice_strength"] = strength
        self.caller.msg(f"ICE strength for node {index} set to {strength}.")
    
    def cmd_set_node_description(self):
        """Set the description for a node."""
        if not self.args:
            self.caller.msg("Usage: arch/nodedesc <node_index> <description>")
            return
            
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.ndb._netarch_creation = {"nodes": []}
            return
            
        try:
            index, description = self.args.split(maxsplit=1)
            index = int(index)
            if index < 0 or index >= len(self.caller.ndb._netarch_creation["nodes"]):
                self.caller.msg(f"Node index {index} is out of range. Valid indices are 0 to {len(self.caller.ndb._netarch_creation['nodes']) - 1}")
                return
            node = self.caller.ndb._netarch_creation["nodes"][index]
        except (ValueError, IndexError):
            self.caller.msg("Invalid node index or description format.")
            return
            
        node["description"] = description.strip()
        self.caller.msg(f"Description set for node {index}.")
    
    def cmd_status(self):
        """Check the current status of architecture creation."""
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.msg("No architecture creation in progress. Use arch/create to start.")
            return
            
        data = self.caller.ndb._netarch_creation
        self.caller.msg("|wCurrent Architecture Creation Status:|n")
        self.caller.msg(f"Name: {data.get('name', 'Not set')}")
        self.caller.msg(f"Description: {data.get('description', 'Not set')}")
        self.caller.msg(f"Nodes: {len(data['nodes'])}")
        
        if data['nodes']:
            self.caller.msg("\n|wNode Details:|n")
            for i, node in enumerate(data['nodes']):
                ice_info = "ICE" if node.get('is_ice', False) else "Not ICE"
                if node.get('is_ice', False):
                    ice_info += f" ({node.get('ice_type', 'Type not set')}, Strength: {node.get('ice_strength', 'Not set')})"
                self.caller.msg(f"{i}: {node['name']} - {ice_info}")
                if 'description' in node:
                    self.caller.msg(f"   Description: {node['description']}")
    
    def cmd_finish(self):
        """Finish creating the Net Architecture."""
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.msg("No architecture creation in progress. Use arch/create to start.")
            return
            
        data = self.caller.ndb._netarch_creation
        
        # Validate required fields
        missing = []
        if "name" not in data or not data["name"]:
            missing.append("name")
        if not data["nodes"]:
            missing.append("at least one node")
            
        if missing:
            self.caller.msg(f"Cannot complete architecture creation. Missing: {', '.join(missing)}.")
            return
            
        # Create the architecture
        architecture = NetArchitecture.objects.create(
            name=data["name"],
            description=data.get("description", ""),
            difficulty=1
        )
        
        # Create the nodes
        for i, node_data in enumerate(data["nodes"]):
            Node.objects.create(
                architecture=architecture,
                name=node_data["name"],
                description=node_data.get("description", ""),
                level=i+1,
                is_ice=node_data.get("is_ice", False),
                ice_type=node_data.get("ice_type"),
                ice_strength=node_data.get("ice_strength", 0)
            )
            
        self.caller.msg(f"Net Architecture '{architecture.name}' created successfully with {len(data['nodes'])} nodes.")
        del self.caller.ndb._netarch_creation
    
    def cmd_cancel(self):
        """Cancel the Net Architecture creation process."""
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.msg("No architecture creation in progress.")
            return
            
        self.caller.msg("Net Architecture creation canceled.")
        del self.caller.ndb._netarch_creation
    
    def cmd_generate(self):
        """Generate a random NET Architecture based on Cyberpunk Red rules."""
        if not self.args:
            self.caller.msg("Usage: arch/generate <difficulty> <name> <location>")
            self.caller.msg("Difficulty can be: basic, standard, uncommon, advanced")
            return
            
        try:
            args_list = self.args.strip().split(None, 2)
            if len(args_list) < 3:
                self.caller.msg("You must provide difficulty, name, and location.")
                return
                
            difficulty, name, location = args_list
            
            # Validate difficulty
            if difficulty.lower() not in ["basic", "standard", "uncommon", "advanced"]:
                self.caller.msg("Invalid difficulty. Must be basic, standard, uncommon, or advanced.")
                return
                
            # Generate the architecture
            architecture_data = self.generate_random_architecture(difficulty.lower(), name, location)
            
            # Create the architecture in the database
            architecture = self.create_architecture_from_data(architecture_data)
            
            # Display summary
            self.display_generated_architecture(architecture_data)
            
            self.caller.msg(f"NET Architecture '{name}' at {location} successfully generated with {len(architecture_data['nodes'])} nodes.")
            
        except Exception as e:
            self.caller.msg(f"Error generating architecture: {e}")
    
    def generate_random_architecture(self, difficulty, name, location):
        """Generate a random NET architecture based on Cyberpunk Red rules."""
        # Step 1: Shape the architecture
        floor_count = sum([random.randint(1, 6) for _ in range(3)])  # 3d6 for total floors
        
        # Determine if there are branches
        branches = []
        if random.randint(1, 10) >= 7:  # 40% chance of a branch
            branch_count = 1
            while branch_count < 3 and random.randint(1, 10) >= 7:  # Up to 3 branches
                branch_count += 1
                
            # Distribute floors between main branch and side branches
            if branch_count > 0:
                main_branch_floors = floor_count // 2
                remaining_floors = floor_count - main_branch_floors
                
                for i in range(branch_count):
                    if i < branch_count - 1:
                        branch_floors = remaining_floors // (branch_count - i)
                        remaining_floors -= branch_floors
                    else:
                        branch_floors = remaining_floors
                    
                    if branch_floors > 0:
                        branches.append({
                            "name": f"Branch {i+1}",
                            "floors": branch_floors
                        })
        
        # Set difficulty value based on selected difficulty
        dv_map = {
            "basic": 6,
            "standard": 8,
            "uncommon": 10,
            "advanced": 12
        }
        
        base_dv = dv_map[difficulty]
        
        # Create architecture data
        architecture_data = {
            "name": name,
            "description": f"NET Architecture at {location} - {difficulty.capitalize()} Difficulty",
            "difficulty": difficulty,
            "difficulty_value": base_dv,
            "location": location,
            "floor_count": floor_count,
            "branches": branches,
            "nodes": []
        }
        
        # Step 2: Fill in the architecture
        
        # Helper function to determine node content based on difficulty and floor
        def get_node_content(floor_num, difficulty):
            if floor_num <= 2:
                # First two floors use the Lobby table
                result = random.randint(1, 6)
                if result == 1:
                    return {"type": "File", "dv": 6, "description": f"Generic data file (DV{6})"}
                elif result == 2:
                    return {"type": "Password", "dv": 6, "description": f"Basic security password (DV{6})"}
                elif result == 3:
                    return {"type": "Password", "dv": 8, "description": f"Enhanced security password (DV{8})"}
                elif result == 4:
                    return {"type": "BlackICE", "name": "Skunk", "description": "Anti-personnel program that does 3d6 damage directly to a Netrunner's brain"}
                elif result == 5:
                    return {"type": "BlackICE", "name": "Wisp", "description": "Tracer program that follows the datastream back to a runner's location"}
                elif result == 6:
                    return {"type": "BlackICE", "name": "Killer", "description": "Dangerous program that does 3d6 damage to a Netrunner's Cyberdeck"}
            else:
                # Other floors use difficulty-specific tables
                result = sum([random.randint(1, 6) for _ in range(3)])  # 3d6 roll
                
                # Basic difficulty table
                if difficulty == "basic":
                    if result == 3:
                        return {"type": "BlackICE", "name": "Hellhound", "description": "Vicious Black ICE that attacks for 4d6 damage"}
                    elif result == 4:
                        return {"type": "BlackICE", "name": "Sabertooth", "description": "Dangerous Black ICE that does 4d6 damage and reduces REZ by 1d6"}
                    elif result == 5:
                        return {"type": "BlackICE", "name": "Raven", "count": 2, "description": "Two Raven programs that work together, each dealing 2d6 damage"}
                    elif result == 6:
                        return {"type": "BlackICE", "name": "Hellhound", "description": "Vicious Black ICE that attacks for 4d6 damage"}
                    elif result == 7:
                        return {"type": "BlackICE", "name": "Wisp", "description": "Tracer program that follows the datastream back to a runner's location"}
                    elif result == 8:
                        return {"type": "BlackICE", "name": "Raven", "description": "Black ICE that does 2d6 damage to a Netrunner's Cyberdeck"}
                    elif result == 9:
                        return {"type": "Password", "dv": 6, "description": f"Basic security password (DV{6})"}
                    elif result == 10:
                        return {"type": "File", "dv": 6, "description": f"Important data file (DV{6})"}
                    elif result == 11:
                        return {"type": "Control Node", "dv": 6, "description": f"System control node (DV{6})"}
                    elif result == 12:
                        return {"type": "Password", "dv": 6, "description": f"Basic security password (DV{6})"}
                    elif result == 13:
                        return {"type": "BlackICE", "name": "Skunk", "description": "Anti-personnel program that does 3d6 damage directly to a Netrunner's brain"}
                    elif result == 14:
                        return {"type": "BlackICE", "name": "Asp", "description": "Deadly Black ICE that does 3d6 damage and reduces REZ by 1d6"}
                    elif result == 15:
                        return {"type": "BlackICE", "name": "Scorpion", "description": "Powerful Black ICE that does 3d6 damage"}
                    elif result == 16:
                        return {"type": "BlackICE", "name": "Killer", "count": 1, "additional": "Skunk", "description": "Dangerous ICE combo: Killer and Skunk working together"}
                    elif result == 17:
                        return {"type": "BlackICE", "name": "Wisp", "count": 3, "description": "Three Wisp programs working together"}
                    elif result == 18:
                        return {"type": "BlackICE", "name": "Liche", "description": "Extremely dangerous Black ICE that does 5d6 damage"}
                
                # Standard difficulty table
                elif difficulty == "standard":
                    if result == 3:
                        return {"type": "BlackICE", "name": "Hellhound", "count": 2, "description": "Two vicious Hellhound programs working together"}
                    elif result == 4:
                        return {"type": "BlackICE", "name": "Hellhound", "additional": "Killer", "description": "Dangerous ICE combo: Hellhound and Killer working together"}
                    elif result == 5:
                        return {"type": "BlackICE", "name": "Skunk", "count": 2, "description": "Two Skunk programs working together"}
                    elif result == 6:
                        return {"type": "BlackICE", "name": "Sabertooth", "description": "Dangerous Black ICE that does 4d6 damage and reduces REZ by 1d6"}
                    elif result == 7:
                        return {"type": "BlackICE", "name": "Scorpion", "description": "Powerful Black ICE that does 3d6 damage"}
                    elif result == 8:
                        return {"type": "BlackICE", "name": "Hellhound", "description": "Vicious Black ICE that attacks for 4d6 damage"}
                    elif result == 9:
                        return {"type": "Password", "dv": 8, "description": f"Enhanced security password (DV{8})"}
                    elif result == 10:
                        return {"type": "File", "dv": 8, "description": f"Valuable data file (DV{8})"}
                    elif result == 11:
                        return {"type": "Control Node", "dv": 8, "description": f"Important system control node (DV{8})"}
                    elif result == 12:
                        return {"type": "Password", "dv": 8, "description": f"Enhanced security password (DV{8})"}
                    elif result == 13:
                        return {"type": "BlackICE", "name": "Asp", "description": "Deadly Black ICE that does 3d6 damage and reduces REZ by 1d6"}
                    elif result == 14:
                        return {"type": "BlackICE", "name": "Killer", "description": "Dangerous program that does 3d6 damage to a Netrunner's Cyberdeck"}
                    elif result == 15:
                        return {"type": "BlackICE", "name": "Liche", "description": "Extremely dangerous Black ICE that does 5d6 damage"}
                    elif result == 16:
                        return {"type": "BlackICE", "name": "Asp", "description": "Deadly Black ICE that does 3d6 damage and reduces REZ by 1d6"}
                    elif result == 17:
                        return {"type": "BlackICE", "name": "Raven", "count": 3, "description": "Three Raven programs working together"}
                    elif result == 18:
                        return {"type": "BlackICE", "name": "Liche", "additional": "Raven", "description": "Extremely dangerous ICE combo: Liche and Raven working together"}
                
                # Uncommon difficulty table
                elif difficulty == "uncommon":
                    if result == 3:
                        return {"type": "BlackICE", "name": "Kraken", "description": "Extremely powerful Black ICE that does 6d6 damage"}
                    elif result == 4:
                        return {"type": "BlackICE", "name": "Hellhound", "additional": "Scorpion", "description": "Dangerous ICE combo: Hellhound and Scorpion working together"}
                    elif result == 5:
                        return {"type": "BlackICE", "name": "Hellhound", "additional": "Killer", "description": "Dangerous ICE combo: Hellhound and Killer working together"}
                    elif result == 6:
                        return {"type": "BlackICE", "name": "Raven", "count": 2, "description": "Two Raven programs working together"}
                    elif result == 7:
                        return {"type": "BlackICE", "name": "Sabertooth", "description": "Dangerous Black ICE that does 4d6 damage and reduces REZ by 1d6"}
                    elif result == 8:
                        return {"type": "BlackICE", "name": "Hellhound", "description": "Vicious Black ICE that attacks for 4d6 damage"}
                    elif result == 9:
                        return {"type": "Password", "dv": 10, "description": f"Advanced security password (DV{10})"}
                    elif result == 10:
                        return {"type": "File", "dv": 10, "description": f"High-value data file (DV{10})"}
                    elif result == 11:
                        return {"type": "Control Node", "dv": 10, "description": f"Critical system control node (DV{10})"}
                    elif result == 12:
                        return {"type": "Password", "dv": 10, "description": f"Advanced security password (DV{10})"}
                    elif result == 13:
                        return {"type": "BlackICE", "name": "Killer", "description": "Dangerous program that does 3d6 damage to a Netrunner's Cyberdeck"}
                    elif result == 14:
                        return {"type": "BlackICE", "name": "Liche", "description": "Extremely dangerous Black ICE that does 5d6 damage"}
                    elif result == 15:
                        return {"type": "BlackICE", "name": "Dragon", "description": "The most dangerous Black ICE, dealing 8d6 damage"}
                    elif result == 16:
                        return {"type": "BlackICE", "name": "Asp", "additional": "Raven", "description": "Dangerous ICE combo: Asp and Raven working together"}
                    elif result == 17:
                        return {"type": "BlackICE", "name": "Dragon", "additional": "Wisp", "description": "Lethal ICE combo: Dragon and Wisp working together"}
                    elif result == 18:
                        return {"type": "BlackICE", "name": "Giant", "description": "Powerful Black ICE that does 6d6 damage"}
                
                # Advanced difficulty table
                elif difficulty == "advanced":
                    if result == 3:
                        return {"type": "BlackICE", "name": "Hellhound", "count": 3, "description": "Three vicious Hellhounds working together"}
                    elif result == 4:
                        return {"type": "BlackICE", "name": "Asp", "count": 2, "description": "Two deadly Asp programs working together"}
                    elif result == 5:
                        return {"type": "BlackICE", "name": "Hellhound", "additional": "Liche", "description": "Lethal ICE combo: Hellhound and Liche working together"}
                    elif result == 6:
                        return {"type": "BlackICE", "name": "Wisp", "count": 3, "description": "Three Wisp programs working together"}
                    elif result == 7:
                        return {"type": "BlackICE", "name": "Hellhound", "additional": "Sabertooth", "description": "Dangerous ICE combo: Hellhound and Sabertooth working together"}
                    elif result == 8:
                        return {"type": "BlackICE", "name": "Kraken", "description": "Extremely powerful Black ICE that does 6d6 damage"}
                    elif result == 9:
                        return {"type": "Password", "dv": 12, "description": f"Military-grade security password (DV{12})"}
                    elif result == 10:
                        return {"type": "File", "dv": 12, "description": f"Critical data file (DV{12})"}
                    elif result == 11:
                        return {"type": "Control Node", "dv": 12, "description": f"Top-tier system control node (DV{12})"}
                    elif result == 12:
                        return {"type": "Password", "dv": 12, "description": f"Military-grade security password (DV{12})"}
                    elif result == 13:
                        return {"type": "BlackICE", "name": "Giant", "description": "Powerful Black ICE that does 6d6 damage"}
                    elif result == 14:
                        return {"type": "BlackICE", "name": "Dragon", "description": "The most dangerous Black ICE, dealing 8d6 damage"}
                    elif result == 15:
                        return {"type": "BlackICE", "name": "Killer", "additional": "Scorpion", "description": "Dangerous ICE combo: Killer and Scorpion working together"}
                    elif result == 16:
                        return {"type": "BlackICE", "name": "Kraken", "description": "Extremely powerful Black ICE that does 6d6 damage"}
                    elif result == 17:
                        return {"type": "BlackICE", "name": "Raven", "additional": "Wisp", "count": 1, "count2": 1, "count3": 1, "description": "Multi-ICE combo: Raven, Wisp, and Hellhound"}
                    elif result == 18:
                        return {"type": "BlackICE", "name": "Dragon", "count": 2, "description": "Two Dragon programs - a lethal combination"}
            
            # Default fallback - shouldn't reach here
            return {"type": "Password", "dv": base_dv, "description": f"Fallback security password (DV{base_dv})"}
        
        # Generate all floors
        current_floor = 1
        
        # Create main branch first (always exists)
        main_branch_floors = floor_count
        if branches:
            main_branch_floors = floor_count - sum(branch["floors"] for branch in branches)
        
        # Generate main branch nodes
        for floor in range(1, main_branch_floors + 1):
            node_content = get_node_content(floor, difficulty)
            
            # Add strength for ICE
            if node_content["type"] == "BlackICE":
                # Set strength based on difficulty
                strength_map = {
                    "basic": random.randint(3, 6),
                    "standard": random.randint(4, 7),
                    "uncommon": random.randint(5, 8),
                    "advanced": random.randint(6, 10)
                }
                strength = strength_map[difficulty]
                node_content["strength"] = strength
            
            # Create node
            node = {
                "name": f"Floor {floor}",
                "level": floor,
                "branch": "Main",
                "content": node_content
            }
            
            architecture_data["nodes"].append(node)
            current_floor += 1
        
        # Generate branch nodes
        branch_floor_offset = 2  # Branches can only start after floor 2
        for branch in branches:
            branch_name = branch["name"]
            branch_floors = branch["floors"]
            
            for floor in range(1, branch_floors + 1):
                # Adjust level to make branches come off main branch
                branched_level = branch_floor_offset + floor
                
                node_content = get_node_content(branched_level, difficulty)
                
                # Add strength for ICE
                if node_content["type"] == "BlackICE":
                    # Set strength based on difficulty
                    strength_map = {
                        "basic": random.randint(3, 6),
                        "standard": random.randint(4, 7),
                        "uncommon": random.randint(5, 8),
                        "advanced": random.randint(6, 10)
                    }
                    strength = strength_map[difficulty]
                    node_content["strength"] = strength
                
                # Create node
                node = {
                    "name": f"{branch_name} Floor {floor}",
                    "level": branched_level,
                    "branch": branch_name,
                    "content": node_content
                }
                
                architecture_data["nodes"].append(node)
            
            # Increment branch offset for next branch
            branch_floor_offset += 1
        
        # Step 3: Add a demon if needed (1 demon per 6 floors)
        if floor_count >= 6:
            demon_count = floor_count // 6
            for i in range(demon_count):
                # Determine demon type based on difficulty
                demon_type = "Imp"  # Default
                if difficulty == "standard":
                    if random.random() > 0.7:
                        demon_type = "Efreet"
                elif difficulty == "uncommon":
                    roll = random.random()
                    if roll > 0.8:
                        demon_type = "Balron"
                    elif roll > 0.4:
                        demon_type = "Efreet"
                elif difficulty == "advanced":
                    roll = random.random()
                    if roll > 0.6:
                        demon_type = "Balron"
                    elif roll > 0.2:
                        demon_type = "Efreet"
                
                architecture_data["demon"] = {
                    "type": demon_type,
                    "description": f"{demon_type} demon that monitors and defends the architecture"
                }
        
        return architecture_data
    
    def create_architecture_from_data(self, data):
        """Create an architecture in the database from the generated data."""
        # Create the main architecture object
        architecture = NetArchitecture.objects.create(
            name=data["name"],
            description=data["description"],
            difficulty={"basic": 1, "standard": 2, "uncommon": 3, "advanced": 4}[data["difficulty"]]
        )
        
        # Create nodes
        for node_data in data["nodes"]:
            content = node_data["content"]
            is_ice = content["type"] in ["BlackICE"]
            
            # Create the node
            node = Node.objects.create(
                architecture=architecture,
                name=node_data["name"],
                description=content["description"],
                level=node_data["level"],
                is_ice=is_ice
            )
            
            # If it's ICE, create the ICE object
            if is_ice:
                ice_name = content["name"]
                ice_strength = content.get("strength", 5)  # Default to 5 if not specified
                
                # Determine ICE type
                ice_type = "Black"  # Default
                
                ice = ICE.objects.create(
                    name=f"{ice_name} ({node_data['name']})",
                    node=node,
                    strength=ice_strength,
                    type=ice_type
                )
                
                # Set the ICE on the node
                node.ice = ice
                node.save()
        
        # Return the created architecture
        return architecture
    
    def display_generated_architecture(self, data):
        """Display a summary of the generated architecture."""
        self.caller.msg("|wGenerated NET Architecture:|n")
        self.caller.msg(f"Name: {data['name']}")
        self.caller.msg(f"Location: {data['location']}")
        self.caller.msg(f"Difficulty: {data['difficulty'].capitalize()} (DV{data['difficulty_value']})")
        self.caller.msg(f"Total Floors: {data['floor_count']}")
        
        if data.get("branches"):
            self.caller.msg(f"Branches: {len(data['branches'])}")
            for branch in data["branches"]:
                self.caller.msg(f"  - {branch['name']}: {branch['floors']} floors")
        
        if data.get("demon"):
            self.caller.msg(f"Demon: {data['demon']['type']} - {data['demon']['description']}")
        
        self.caller.msg("\n|wNode Contents:|n")
        for node in data["nodes"]:
            content = node["content"]
            content_type = content["type"]
            
            # Format node display based on content type
            if content_type == "BlackICE":
                ice_name = content["name"]
                strength = content.get("strength", "??")
                count = content.get("count", 1)
                
                if count > 1:
                    display = f"{node['name']} ({node['branch']}): {count}x {ice_name} ICE (Strength {strength})"
                else:
                    display = f"{node['name']} ({node['branch']}): {ice_name} ICE (Strength {strength})"
                
                # Check for additional ICE
                if "additional" in content:
                    display += f" + {content['additional']} ICE"
            
            elif content_type in ["Password", "File", "Control Node"]:
                dv = content.get("dv", "??")
                display = f"{node['name']} ({node['branch']}): {content_type} (DV{dv})"
            
            else:
                display = f"{node['name']} ({node['branch']}): {content_type}"
            
            self.caller.msg(f"  - {display}")

class NetArchCreationCmdSet(CmdSet):
    key = "netarch_creation"
    mergetype = "Replace"
    priority = 1
    no_exits = True

class NetArchCreationScript(DefaultScript):
    """
    This script handles the Net Architecture creation process.
    """
    def at_script_creation(self):
        self.key = "net_arch_creation"
        self.desc = "Handles Net Architecture creation"
        self.persistent = True

    # Add any other methods needed for Net Architecture creation