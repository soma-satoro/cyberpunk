# commands/netrun_admin_commands.py

from evennia import Command, CmdSet, DefaultScript
from evennia.utils import create
from world.netrunning.models import NetArchitecture, Node

class CmdCreateNetArchitecture(Command):
    """
    Start creating a new Net Architecture.

    Usage:
      createnetarch
    """
    key = "createnetarch"
    locks = "cmd:perm(Admin)"
    help_category = "Admin"

    def func(self):
        self.caller.msg("Starting Net Architecture creation. Use 'setname <name>' to begin.")
        self.caller.cmdset.add(NetArchCreationCmdSet)

class CmdSetName(Command):
    """
    Set the name of the Net Architecture.

    Usage:
      setname <name>
    """
    key = "setname"

    def func(self):
        if not self.args:
            self.caller.msg("You must specify a name.")
            return
        self.caller.ndb._netarch_creation = {"name": self.args.strip(), "nodes": []}
        self.caller.msg(f"Net Architecture name set to '{self.args.strip()}'. Use 'setdesc <description>' to add a description.")

class CmdSetDescription(Command):
    """
    Set the description of the Net Architecture.

    Usage:
      setdesc <description>
    """
    key = "setdesc"

    def func(self):
        if not self.args:
            self.caller.msg("You must specify a description.")
            return
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.msg("You must set a name first. Use 'setname <name>'.")
            return
        self.caller.ndb._netarch_creation["description"] = self.args.strip()
        self.caller.msg(f"Description set. Use 'addnode <name>' to add nodes or 'finish' to complete.")

class CmdAddNode(Command):
    """
    Add a node to the Net Architecture.

    Usage:
      addnode <name>
    """
    key = "addnode"

    def func(self):
        if not self.args:
            self.caller.msg("You must specify a node name.")
            return
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.msg("You must set a name and description first.")
            return
        node_name = self.args.strip()
        self.caller.ndb._netarch_creation["nodes"].append({"name": node_name})
        self.caller.msg(f"Node '{node_name}' added. Is this node ICE? Use 'setice <node_index> <yes/no>'.")

class CmdSetICE(Command):
    """
    Set a node as ICE or not.

    Usage:
      setice <node_index> <yes/no>
    """
    key = "setice"

    def func(self):
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: setice <node_index> <yes/no>")
            return
        index, is_ice = self.args.split()
        try:
            index = int(index)
            # Debug: Print the current state of _netarch_creation
            self.caller.msg(f"Debug: Current _netarch_creation state: {self.caller.ndb._netarch_creation}")
            # Debug: Print the number of nodes
            self.caller.msg(f"Debug: Number of nodes: {len(self.caller.ndb._netarch_creation['nodes'])}")
            node = self.caller.ndb._netarch_creation["nodes"][index]
        except AttributeError:
            self.caller.msg("Debug: _netarch_creation attribute not found. Have you started creating an architecture?")
            return
        except KeyError:
            self.caller.msg("Debug: 'nodes' key not found in _netarch_creation. Have you added any nodes?")
            return
        except IndexError:
            self.caller.msg(f"Debug: Node index {index} is out of range. Valid indices are 0 to {len(self.caller.ndb._netarch_creation['nodes']) - 1}")
            return
        except ValueError:
            self.caller.msg(f"Debug: Invalid index '{index}'. Please provide a number.")
            return
        node["is_ice"] = is_ice.lower() == "yes"
        if node["is_ice"]:
            self.caller.msg(f"Node set as ICE. Use 'seticetype {index} <Black/White/Red>' to set ICE type.")
        else:
            self.caller.msg(f"Node set as not ICE. Use 'setnodedesc {index} <description>' to add a description.")

class CmdSetICEType(Command):
    """
    Set the ICE type for a node.

    Usage:
      seticetype <node_index> <Black/White/Red>
    """
    key = "seticetype"

    def func(self):
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: seticetype <node_index> <Black/White/Red>")
            return
        index, ice_type = self.args.split()
        try:
            index = int(index)
            node = self.caller.ndb._netarch_creation["nodes"][index]
        except (ValueError, IndexError):
            self.caller.msg("Invalid node index.")
            return
        if ice_type not in ["Black", "White", "Red"]:
            self.caller.msg("Invalid ICE type. Must be Black, White, or Red.")
            return
        node["ice_type"] = ice_type
        self.caller.msg(f"ICE type set to {ice_type}. Use 'seticestrength {index} <1-10>' to set ICE strength.")

class CmdSetICEStrength(Command):
    """
    Set the ICE strength for a node.

    Usage:
      seticestrength <node_index> <1-10>
    """
    key = "seticestrength"

    def func(self):
        if not self.args or len(self.args.split()) != 2:
            self.caller.msg("Usage: seticestrength <node_index> <1-10>")
            return
        index, strength = self.args.split()
        try:
            index = int(index)
            strength = int(strength)
            node = self.caller.ndb._netarch_creation["nodes"][index]
        except (ValueError, IndexError):
            self.caller.msg("Invalid node index or strength.")
            return
        if not 1 <= strength <= 10:
            self.caller.msg("Strength must be between 1 and 10.")
            return
        node["ice_strength"] = strength
        self.caller.msg(f"ICE strength set to {strength}. Use 'setnodedesc {index} <description>' to add a description.")

class CmdSetNodeDescription(Command):
    """
    Set the description for a node.

    Usage:
      setnodedesc <node_index> <description>
    """
    key = "setnodedesc"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: setnodedesc <node_index> <description>")
            return
        try:
            index, description = self.args.split(maxsplit=1)
            index = int(index)
            node = self.caller.ndb._netarch_creation["nodes"][index]
        except (ValueError, IndexError):
            self.caller.msg("Invalid node index.")
            return
        node["description"] = description.strip()
        self.caller.msg(f"Description set for node {index}. Use 'addnode' to add more nodes or 'finish' to complete.")

class CmdFinishArchitecture(Command):
    """
    Finish creating the Net Architecture.

    Usage:
      finish
    """
    key = "finish"

    def func(self):
        if not hasattr(self.caller.ndb, '_netarch_creation'):
            self.caller.msg("You haven't started creating a Net Architecture.")
            return
        data = self.caller.ndb._netarch_creation
        architecture = NetArchitecture.objects.create(
            name=data["name"],
            description=data.get("description", ""),
            difficulty=1
        )
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
        self.caller.cmdset.delete(NetArchCreationCmdSet)
        del self.caller.ndb._netarch_creation

class CmdCancelCreation(Command):
    """
    Cancel the Net Architecture creation process.

    Usage:
      cancel
    """
    key = "cancel"

    def func(self):
        self.caller.msg("Net Architecture creation canceled.")
        self.caller.cmdset.delete(NetArchCreationCmdSet)
        if hasattr(self.caller.ndb, '_netarch_creation'):
            del self.caller.ndb._netarch_creation

class NetArchCreationCmdSet(CmdSet):
    key = "netarch_creation"
    mergetype = "Replace"
    priority = 1
    no_exits = True

    def at_cmdset_creation(self):
        self.add(CmdSetName())
        self.add(CmdSetDescription())
        self.add(CmdAddNode())
        self.add(CmdSetICE())
        self.add(CmdSetICEType())
        self.add(CmdSetICEStrength())
        self.add(CmdSetNodeDescription())
        self.add(CmdFinishArchitecture())
        self.add(CmdCancelCreation())

class NetArchCreationScript(DefaultScript):
    """
    This script handles the Net Architecture creation process.
    """
    def at_script_creation(self):
        self.key = "net_arch_creation"
        self.desc = "Handles Net Architecture creation"
        self.persistent = True

    # Add any other methods needed for Net Architecture creation