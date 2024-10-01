from evennia import Command
from evennia.utils.evtable import EvTable
from world.bulletin_boards import get_or_create_bulletin_board_handler

class CmdBoardList(Command):
    """
    List all available bulletin boards.

    Usage:
      bb

    This command shows all available bulletin boards.
    """
    key = "bb"
    aliases = ["listboards"]
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        try:
            board_handler = get_or_create_bulletin_board_handler()
            
            if not board_handler:
                self.caller.msg("Error: Unable to initialize the bulletin board system.")
                return

            boards = board_handler.list_boards()
            
            if not boards:
                self.caller.msg("There are no bulletin boards available.")
                return

            table = EvTable("Available Boards", border="cells")
            for board in boards:
                table.add_row(board)

            self.caller.msg(table)
        except Exception as e:
            self.caller.msg(f"An error occurred: {str(e)}")

class CmdBoardRead(Command):
    """
    Read posts from a bulletin board.

    Usage:
      bbread <board_name>
      bbread <board_name>/<post_id>

    This command allows you to read posts from a specific bulletin board.
    If no post_id is specified, it will show a list of recent posts.
    """
    key = "bbread"
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        if not self.args:
            self.caller.msg("Usage: bbread <board_name> [/<post_id>]")
            return

        board_handler = get_or_create_bulletin_board_handler()
        if not board_handler:
            self.caller.msg("Error: Unable to initialize the bulletin board system.")
            return

        args = self.args.split("/")
        board_name = args[0].strip()
        post_id = None if len(args) == 1 else args[1].strip()

        board = board_handler.get_board(board_name)
        if not board:
            self.caller.msg(f"Board '{board_name}' not found.")
            return

        if post_id:
            try:
                post_id = int(post_id)
                post = board.get_post(post_id)
                if post:
                    self.caller.msg(f"Title: {post['title']}\nAuthor: {post['author']}\nDate: {post['created_at']}\n\n{post['content']}")
                else:
                    self.caller.msg(f"Post {post_id} not found on board '{board_name}'.")
            except ValueError:
                self.caller.msg("Invalid post ID. Please use a number.")
        else:
            posts = board.get_posts(end=10)  # Show last 10 posts
            table = EvTable("ID", "Title", "Author", "Date", border="cells")
            for i, post in enumerate(posts):
                table.add_row(i, post['title'], post['author'], post['created_at'])
            self.caller.msg(table)

class CmdBoardPost(Command):
    """
    Post a message to a bulletin board.

    Usage:
      bbpost <board_name> = <title> / <content>

    This command allows you to post a new message to a specific bulletin board.
    """
    key = "bbpost"
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: post <board_name> = <title> / <content>")
            return

        board_name, args = self.args.split("=", 1)
        board_name = board_name.strip()
        args = args.strip()

        if "/" not in args:
            self.caller.msg("You must provide both a title and content for your post.")
            return

        title, content = args.split("/", 1)
        title = title.strip()
        content = content.strip()

        board_handler = get_or_create_bulletin_board_handler()
        if not board:
            self.caller.msg(f"Board '{board_name}' not found.")
            return

        board = board_handler.get_board(board_name)
        if not board:
            self.caller.msg(f"Board '{board_name}' not found.")
            return

        post = board.create_post(title, content, self.caller.name)
        self.caller.msg(f"Posted to '{board_name}' board: {title}")

class CmdBoardDelete(Command):
    """
    Delete a post from a bulletin board.

    Usage:
      bbdelete <board_name>/<post_id>

    This command allows you to delete a post from a specific bulletin board.
    You can only delete your own posts unless you have admin privileges.
    """
    key = "bbdelete"
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        if not self.args or "/" not in self.args:
            self.caller.msg("Usage: boarddelete <board_name>/<post_id>")
            return

        board_name, post_id = self.args.split("/", 1)
        board_name = board_name.strip()
        post_id = post_id.strip()

        board_handler = get_or_create_bulletin_board_handler()
        if not board:
            self.caller.msg(f"Board '{board_name}' not found.")
            return

        board = board_handler.get_board(board_name)
        if not board:
            self.caller.msg(f"Board '{board_name}' not found.")
            return

        try:
            post_id = int(post_id)
            post = board.get_post(post_id)
            if post:
                if post['author'] == self.caller.name or self.caller.check_permstring("Admin"):
                    if board.delete_post(post_id):
                        self.caller.msg(f"Post {post_id} deleted from '{board_name}' board.")
                    else:
                        self.caller.msg(f"Failed to delete post {post_id}.")
                else:
                    self.caller.msg("You don't have permission to delete this post.")
            else:
                self.caller.msg(f"Post {post_id} not found on board '{board_name}'.")
        except ValueError:
            self.caller.msg("Invalid post ID. Please use a number.")

class CmdBoardEdit(Command):
    """
    Edit a post on a bulletin board.

    Usage:
      bbedit <board_name>/<post_id> = <new_content>

    This command allows you to edit a post on a specific bulletin board.
    You can only edit your own posts unless you have admin privileges.
    """
    key = "bbedit"
    locks = "cmd:all()"
    help_category = "Communication"

    def func(self):
        if not self.args or "=" not in self.args:
            self.caller.msg("Usage: boardedit <board_name>/<post_id> = <new_content>")
            return

        args, new_content = self.args.split("=", 1)
        args = args.strip()
        new_content = new_content.strip()

        if "/" not in args:
            self.caller.msg("Usage: boardedit <board_name>/<post_id> = <new_content>")
            return

        board_name, post_id = args.split("/", 1)
        board_name = board_name.strip()
        post_id = post_id.strip()

        board_handler = get_or_create_bulletin_board_handler()
        if not board:
            self.caller.msg(f"Board '{board_name}' not found.")
            return

        board = board_handler.get_board(board_name)
        if not board:
            self.caller.msg(f"Board '{board_name}' not found.")
            return

        try:
            post_id = int(post_id)
            post = board.get_post(post_id)
            if post:
                if post['author'] == self.caller.name or self.caller.check_permstring("Admin"):
                    if board.edit_post(post_id, new_content):
                        self.caller.msg(f"Post {post_id} on '{board_name}' board has been updated.")
                    else:
                        self.caller.msg(f"Failed to edit post {post_id}.")
                else:
                    self.caller.msg("You don't have permission to edit this post.")
            else:
                self.caller.msg(f"Post {post_id} not found on board '{board_name}'.")
        except ValueError:
            self.caller.msg("Invalid post ID. Please use a number.")