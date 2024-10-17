from evennia import DefaultObject
from evennia.utils import list_to_string

class NetArchitecture(DefaultObject):
    """
    This class represents a Net Architecture in the game.
    """
    def at_object_creation(self):
        """
        Called when the object is first created.
        """
        super().at_object_creation()
        self.db.name = "Unnamed Architecture"
        self.db.description = ""
        self.db.difficulty = 1
        self.db.nodes = []  # List to store Node objects

    def add_node(self, node):
        """
        Add a node to this architecture.
        """
        self.db.nodes.append(node)

    def get_node_count(self):
        """
        Return the number of nodes in this architecture.
        """
        return len(self.db.nodes)

    def return_appearance(self, looker):
        """
        This defines how the architecture looks when examined.
        """
        text = f"|c{self.name}|n\n"
        text += f"Difficulty: {self.db.difficulty}\n"
        text += f"Nodes: {self.get_node_count()}\n"
        text += f"Description: {self.db.description}\n"
        if self.db.nodes:
            text += "Nodes:\n"
            text += list_to_string([node.name for node in self.db.nodes])
        return text

class Node(DefaultObject):
    """
    This class represents a Node within a Net Architecture.
    """
    def at_object_creation(self):
        """
        Called when the object is first created.
        """
        super().at_object_creation()
        self.db.name = "Unnamed Node"
        self.db.description = ""
        self.db.level = 1
        self.db.is_ice = False
        self.db.ice_type = ""
        self.db.ice_strength = 0
        self.db.architecture = None  # Reference to the parent NetArchitecture

    def set_architecture(self, architecture):
        """
        Set the parent architecture for this node.
        """
        self.db.architecture = architecture
        architecture.add_node(self)

    def return_appearance(self, looker):
        """
        This defines how the node looks when examined.
        """
        text = f"|c{self.name}|n (Level {self.db.level})\n"
        text += f"Description: {self.db.description}\n"
        if self.db.is_ice:
            text += f"ICE Type: {self.db.ice_type}\n"
            text += f"ICE Strength: {self.db.ice_strength}\n"
        return text
