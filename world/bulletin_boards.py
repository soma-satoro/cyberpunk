from evennia import DefaultScript
from evennia.utils import create
from evennia.utils.utils import make_iter
from evennia.scripts.models import ScriptDB

class BulletinBoard(DefaultScript):
    """
    This script represents a bulletin board in the game.
    """
    def at_script_creation(self):
        self.key = "BulletinBoard"
        self.desc = "A bulletin board for posting messages"
        self.persistent = True

        # Board properties
        self.db.name = ""
        self.db.posts = []

    def create_post(self, title, content, author):
        """
        Create a new post on the board.
        """
        post = {
            "title": title,
            "content": content,
            "author": author,
            "created_at": self.db.gametime.gametime(),
        }
        self.db.posts.append(post)
        return post

    def get_posts(self, start=0, end=None):
        """
        Get a range of posts from the board.
        """
        return self.db.posts[start:end]

    def get_post(self, post_id):
        """
        Get a specific post by its ID (index).
        """
        try:
            return self.db.posts[post_id]
        except IndexError:
            return None

    def edit_post(self, post_id, new_content):
        """
        Edit an existing post.
        """
        try:
            post = self.db.posts[post_id]
            post["content"] = new_content
            post["edited_at"] = self.db.gametime.gametime()
            return True
        except IndexError:
            return False

    def delete_post(self, post_id):
        """
        Delete a post from the board.
        """
        try:
            del self.db.posts[post_id]
            return True
        except IndexError:
            return False

class BulletinBoardHandler(DefaultScript):
    """
    This script manages all bulletin boards in the game.
    """
    def at_script_creation(self):
        self.key = "BulletinBoardHandler"
        self.desc = "Manages all bulletin boards"
        self.persistent = True

        # Initialize default boards
        self.db.boards = {
            "Public": create.create_script(BulletinBoard, key="Public_Board"),
            "Screamsheets": create.create_script(BulletinBoard, key="Screamsheets_Board"),
            "OOC News": create.create_script(BulletinBoard, key="OOC_News_Board"),
            "Code": create.create_script(BulletinBoard, key="Code_Board"),
            "Character Introductions": create.create_script(BulletinBoard, key="Character_Intros_Board"),
            "Events": create.create_script(BulletinBoard, key="Events_Board"),
        }

    def get_board(self, board_name):
        """
        Get a specific board by name.
        """
        return self.db.boards.get(board_name)

    def list_boards(self):
        """
        List all available boards.
        """
        return list(self.db.boards.keys())

    def create_board(self, board_name):
        """
        Create a new board.
        """
        if board_name not in self.db.boards:
            self.db.boards[board_name] = create.create_script(BulletinBoard, key=f"{board_name}_Board")
            return True
        return False

    def delete_board(self, board_name):
        """
        Delete an existing board.
        """
        if board_name in self.db.boards:
            board = self.db.boards.pop(board_name)
            board.delete()
            return True
        return False

def init_bulletin_board_system():
    handlers = ScriptDB.objects.filter(db_key="BulletinBoardHandler")
    
    if handlers.exists():
        # If multiple handlers exist, keep the first one and delete the rest
        handler = handlers.first()
        for extra_handler in handlers[1:]:
            extra_handler.delete()
    else:
        # If no handler exists, create a new one
        handler = create.create_script(BulletinBoardHandler, key="BulletinBoardHandler")
    
    if isinstance(handler, bool):
        # If create_script returned a boolean, we need to fetch the actual script
        try:
            handler = ScriptDB.objects.get(db_key="BulletinBoardHandler")
        except ScriptDB.DoesNotExist:
            return None
    
    if handler and hasattr(handler, 'is_active') and callable(handler.is_active):
        if not handler.is_active():
            handler.start()
    
    return handler

# Function to get or create the bulletin board handler
def get_or_create_bulletin_board_handler():
    handler = init_bulletin_board_system()
    if not handler:
        # If init_bulletin_board_system failed to create or retrieve a handler, create a new one
        handler = create.create_script(BulletinBoardHandler, key="BulletinBoardHandler")
        if isinstance(handler, bool):
            try:
                handler = ScriptDB.objects.get(db_key="BulletinBoardHandler")
            except ScriptDB.DoesNotExist:
                return None
    return handler