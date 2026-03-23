"""
File-based help entries. These complements command-based help and help entries
added in the database using the `sethelp` command in-game.

Control where Evennia reads these entries with `settings.FILE_HELP_ENTRY_MODULES`,
which is a list of python-paths to modules to read.

A module like this should hold a global `HELP_ENTRY_DICTS` list, containing
dicts that each represent a help entry. If no `HELP_ENTRY_DICTS` variable is
given, all top-level variables that are dicts in the module are read as help
entries.

Each dict is on the form
::

    {'key': <str>,
     'text': <str>}``     # the actual help text. Can contain # subtopic sections
     'category': <str>,   # optional, otherwise settings.DEFAULT_HELP_CATEGORY
     'aliases': <list>,   # optional
     'locks': <str>       # optional, 'view' controls seeing in help index, 'read'
                          #           if the entry can be read. If 'view' is unset,
                          #           'read' is used for the index. If unset, everyone
                          #           can read/view the entry.

"""

HELP_ENTRY_DICTS = [
    {
        "key": "room creation",
        "aliases": ["building rooms", "dig", "room basics"],
        "category": "Building and Housing",
        "locks": "read:perm(Builder)",
        "text": """
A step-by-step guide to creating and configuring rooms. Requires Builder permission.

# Step 1: Creating Rooms with Dig

Use |wdig|n to create a new room. You must be in an existing room (or Limbo) to dig from.

|wdig <roomname>|n
  Creates a room with no exits. You will need to add exits manually later.

|wdig <roomname> = <exit_to_new>, <exit_back>|n
  Creates a room and two exits: one from your current room to the new room, and one back.
  Example: dig Corpo Plaza = east, west

Use |wtunnel|n to quickly create a room in a direction with bidirectional exits:

|wtunnel <direction> = <roomname>|n
  Example: tunnel north = Back Alley
  Creates "Back Alley" north of you and adds north/south exits both ways.

# Step 2: Descriptions

Use |w@desc|n to set what players see when they look at the room:

|w@desc here = <text>|n
  Sets the description of the room you are in. Use |where|n to refer to your current location.

|w@desc/edit|n
  Opens a line editor for longer descriptions. Type your text, then type |w@|n on a new line to save.

Room descriptions support special formatting:
  |w%r|n  - Paragraph break (blank line)
  |w%t|n  - Indent (for secondary/indented lines within a paragraph)

# Step 3: Area Management (+area)

Areas organize rooms with codes like NC01, WB02. Use |w+area/list|n to see defined areas. Admins may need to run |w+area/init|n first.

|w+area/list|n           - List all areas and their codes
|w+area/add <code>=<name>/<description>|n  - Add area (e.g. +area/add NC=Night City/The megacity)
|w+area/remove <code>|n - Remove an empty area
|w+area/info <code>|n   - Show area details
|w+area/rooms <code>|n  - List rooms in an area

Area codes are 2-4 characters (e.g. NC, WB, WA). Default areas include NC (Night City), WB (Westbrook), WA (Watson), etc.

# Step 4: Room Setup (+room and +room/tag)

Use |w+room|n to configure room properties. Target: |where|n, room name, or |w#dbref|n.

|w+room|n
  Shows current room settings (area, hierarchy, resources, tags, etc.)

|w+room/area here=<code>|n
  Assigns the room to an area and auto-assigns the next room number (e.g. NC -> NC01).
  Example: +room/area here=NC

|w+room/code here=<fullcode>|n
  Manually set room code (e.g. NC01). Use when you need a specific number.

|w+room/hierarchy here=<district>,<area>|n
  Sets location display (e.g. Watson, Northside). Shown in room header and +where.
  Example: +room/hierarchy here=Watson,Northside

|w+room/tag here=<tag1>,<tag2>|n
  Sets room tags (comma-separated). Tags help with searching and categorization.
  Example: +room/tag here=bar,nightlife,corporate

|w+room/tags here|n
  View current tags on the room.

Other useful +room options:
  |w+room/res here=<value>|n     - Set resources: 0-6 or Cheap, Everyday, Costly, Premium, Expensive, Very Expensive, Luxury
  |w+room/type here=<type>|n      - Set room type (e.g. Beach Town, Bar)
  |w+room/coords here=<x>,<y>|n   - Set coordinates for area maps
  |w+room/unfindable here=on|n    - Hide room from +where (staff can still see)

# Quick Workflow

1. dig Room Name = exit_in, exit_out      (or use tunnel)
2. @desc here = Your description here.
3. +room/area here=NC                     (or appropriate area code)
4. +room/hierarchy here=District,Area
5. +room/tag here=bar,nightlife
6. +room/res here=3                       (if applicable)
7. Add exits to other rooms with |w@open|n or |w@link|n

See also: +help +area, +help +room, +help +view
        """,
    },
    {
        "key": "evennia",
        "aliases": ["ev"],
        "category": "General",
        "locks": "read:perm(Developer)",
        "text": """
            Evennia is a MU-game server and framework written in Python. You can read more
            on https://www.evennia.com.

            # subtopics

            ## Installation

            You'll find installation instructions on https://www.evennia.com.

            ## Community

            There are many ways to get help and communicate with other devs!

            ### Discussions

            The Discussions forum is found at https://github.com/evennia/evennia/discussions.

            ### Discord

            There is also a discord channel for chatting - connect using the
            following link: https://discord.gg/AJJpcRUhtF

        """,
    },
    {
        "key": "voucher",
        "aliases": ["vouchers", "vinfo"],
        "category": "Inventory",
        "text": """
The voucher system enables you to manage IC objects that you are carrying. A voucher item represents the in-character object. Multiple items may be combined onto a single voucher. Anything which is not some other kind of in-character item will be represented by a voucher.

You can look at a voucher to see its contents. Vouchers may be picked up and dropped just like regular items. You may also use +sheet on a voucher to see the items contained in it.

A voucher may always be referred to by its name, if it's unique; by its dbref (the number after the #), or by its alias, if one is set.

Usage: +voucher/info <voucher>
       +voucher/info <voucher>/<item#>

     The first form displays the contents of the indicated <voucher>. The
     second form displays more detailed information about the indicated
     <item#> on the <voucher>. This command may be abbreviated as '+vinfo'

# voucher2

Usage: +voucher/alias <voucher>=<alias>

     Sets the <alias> of the <voucher> to the value you specify. The <alias>
     will then be able to be used to refer to the voucher in commands that
     require a <voucher> argument. The alias may be at most 20 characters and
     may only contain letters, numbers, dashes (-), and underscores (_).

Usage: +conceal <voucher>
       +unconceal <voucher>

     A concealed voucher will not show up when other people look at your
     inventory. Use the first command to hide it, the second command to
     make it visible again.

Usage: +voucher/lock <voucher>
       +voucher/unlock <voucher>

     A locked voucher may be picked up or changed only by you. It's
     recommended that you lock all vouchers that you leave unattended.

# voucher3

Usage: +voucher/loc <voucher>/<item#>=<ic location>

     Each item on a voucher may have a specified IC location. You can use
     this to specify where you're carrying it, or even that it's located
     'somewhere else' ICly. The location can be up to 20 characters long.

Usage: +voucher/use <voucher>/<item#>[:<qty>]

     This command 'uses up' <qty> of <item#>, effectively removing it from
     the voucher. If no <qty> is specified, then a quantity of 1 is assumed.

Usage: +voucher/chown <voucher>=<player>

     This command changes the IC owner of a voucher to <player>. This shows
     up via the '+owner' command (see '+help owner') and can be used to help
     us find a voucher's owner if it is lost. If you give or sell something
     of yours, ICly, then please use this command to transfer ownership.

# voucher4

Usage: +voucher/rename <voucher>=<new name>

     This command may be used to change the name of <voucher> as it appears
     in your inventory or a room's contents to <new name>. The new name may
     be at most 38 characters long.

Usage: +voucher/nuke <voucher>

     This command may be used to destroy an empty voucher. It will fail if
     the indicated <voucher> contains items.

Usage: +voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>

     This command is used to move an item from one voucher to another. It
     will move <qty> of the item numbered <item#> from <voucher> to
     <newvoucher>. If <qty> is not specified, then the entire quantity that
     exists on <voucher> is moved to <newvoucher>. <item#> may be a list of
     items, separated by spaces; all those specified will be moved.

# voucher5

Usage: +voucher/join <voucher1>=<voucher2>

     Use this to take all items from <voucher2> and place them on
     <voucher1>. <voucher2> will be destroyed.

Usage: +voucher/split <voucher>/<item#>[:<qty>]

     This command can be used to take an item specified by <item#> from
     <voucher> and create a new voucher to contain it. The new item is
     moved to the newly created voucher, which will be in your inventory.
     You may move multiple items by specifying their numbers, separated
     by spaces, as <item#>.

Usage: +voucher/cloneitem <voucher>/<item#>[:<qty>]

     Some items are marked 'cloneable', such as spell formulae or deck
     programs, meaning they can be freely copied. This command performs
     that task to create another copy of the voucher item, usually for
     distribution. A quantity can be specified as a quantity of copies
     to create.

Usage: +voucher/create [=name]
       +voucher/add <voucher>=<name>[:<qty>][:cloneable]

     Create an empty voucher, or add items to an existing voucher.

See also: +help equip
        """,
    },
    {
        "key": "voucher",
        "aliases": ["vouchers", "vinfo"],
        "category": "Inventory",
        "text": """
The voucher system enables you to manage IC objects that you are carrying. A voucher item represents the in-character object. Multiple items may be combined onto a single voucher. Anything which is not some other kind of in-character item will be represented by a voucher.

You can look at a voucher to see its contents. Vouchers may be picked up and dropped just like regular items. You may also use +sheet on a voucher to see the items contained in it.

A voucher may always be referred to by its name, if it's unique; by its dbref (the number after the #), or by its alias, if one is set.

Usage: +voucher/info <voucher>
       +voucher/info <voucher>/<item#>

     The first form displays the contents of the indicated <voucher>. The
     second form displays more detailed information about the indicated
     <item#> on the <voucher>. This command may be abbreviated as '+vinfo'

-----------------------> Continued in '+help voucher2' <-----------------------
        """,
    },
    {
        "key": "voucher2",
        "category": "Inventory",
        "text": """
Usage: +voucher/alias <voucher>=<alias>

     Sets the <alias> of the <voucher> to the value you specify. The <alias>
     will then be able to be used to refer to the voucher in commands that
     require a <voucher> argument. The alias may be at most 20 characters and
     may only contain letters, numbers, dashes (-), and underscores (_).

Usage: +conceal <voucher>
       +unconceal <voucher>

     A concealed voucher will not show up when other people look at your
     inventory. Use the first command to hide it, the second command to
     make it visible again.

Usage: +voucher/lock <voucher>
       +voucher/unlock <voucher>

     A locked voucher may be picked up or changed only by you. It's
     recommended that you lock all vouchers that you leave unattended.

-----------------------> Continued in '+help voucher3' <-----------------------
        """,
    },
    {
        "key": "voucher3",
        "category": "Inventory",
        "text": """
Usage: +voucher/loc <voucher>/<item#>=<ic location>

     Each item on a voucher may have a specified IC location. You can use
     this to specify where you're carrying it, or even that it's located
     'somewhere else' ICly. The location can be up to 20 characters long.

Usage: +voucher/use <voucher>/<item#>[:<qty>]

     This command 'uses up' <qty> of <item#>, effectively removing it from
     the voucher. If no <qty> is specified, then a quantity of 1 is assumed.

Usage: +voucher/chown <voucher>=<player>

     This command changes the IC owner of a voucher to <player>. This shows
     up via the '+owner' command (see '+help owner') and can be used to help
     us find a voucher's owner if it is lost. If you give or sell something
     of yours, ICly, then please use this command to transfer ownership.

-----------------------> Continued in '+help voucher4' <-----------------------
        """,
    },
    {
        "key": "voucher4",
        "category": "Inventory",
        "text": """
Usage: +voucher/rename <voucher>=<new name>

     This command may be used to change the name of <voucher> as it appears
     in your inventory or a room's contents to <new name>. The new name may
     be at most 38 characters long.

Usage: +voucher/nuke <voucher>

     This command may be used to destroy an empty voucher. It will fail if
     the indicated <voucher> contains items.

Usage: +voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>

     This command is used to move an item from one voucher to another. It
     will move <qty> of the item numbered <item#> from <voucher> to
     <newvoucher>. If <qty> is not specified, then the entire quantity that
     exists on <voucher> is moved to <newvoucher>. <item#> may be a list of
     items, separated by spaces; all those specified will be moved.

-----------------------> Continued in '+help voucher5' <-----------------------
        """,
    },
    {
        "key": "voucher5",
        "category": "Inventory",
        "text": """
Usage: +voucher/join <voucher1>=<voucher2>

     Use this command to take all items from <voucher2> and place them on
     <voucher1>. <voucher2> will be destroyed.

Usage: +voucher/split <voucher>/<item#>[:<qty>]

     This command can be used to take an item specified by <item#> from
     <voucher> and create a new voucher to contain it. The new item is
     moved to the newly created voucher, which will be in your inventory.
     You may move multiple items by specifying their numbers, separated
     by spaces, as <item#>.

Usage: +voucher/cloneitem <voucher>/<item#>[:<qty>]

     Some items are marked 'cloneable', such as spell formulae or deck
     programs, meaning they can be freely copied. This command performs
     that task to create another copy of the voucher item, usually for
     distribution. A quantity can be specified as a quantity of copies
     to create.

Usage: +voucher/create [=name]
       +voucher/add <voucher>=<name>[:<qty>][:cloneable]

     Create an empty voucher, or add items to an existing voucher.

See also: +help equip
        """,
    },
    {
        "key": "voucher",
        "aliases": ["vouchers", "vinfo"],
        "category": "Inventory",
        "text": """
The voucher system enables you to manage IC objects that you are carrying. A voucher
item represents the in-character object. Multiple items may be combined onto a
single voucher. Anything which is not some other kind of in-character item will
be represented by a voucher.

You can look at a voucher to see its contents. Vouchers may be picked up and
dropped just like regular items. You may also use +sheet on a voucher to see the
items contained in it.

A voucher may always be referred to by its name, if it's unique; by its dbref
(the number after the #), or by its alias, if one is set.

Usage: +voucher/info <voucher>
       +voucher/info <voucher>/<item#>

  The first form displays the contents of the indicated <voucher>. The second
  form displays more detailed information about the indicated <item#> on the
  <voucher>. This command may be abbreviated as '+vinfo'

See also: +help voucher2
        """,
    },
    {
        "key": "voucher2",
        "category": "Inventory",
        "text": """
Usage: +voucher/alias <voucher>=<alias>

  Sets the <alias> of the <voucher> to the value you specify. The <alias> will
  then be able to be used to refer to the voucher in commands that require a
  <voucher> argument. The alias may be at most 20 characters and may only
  contain letters, numbers, dashes (-), and underscores (_).

Usage: +conceal <voucher>
       +unconceal <voucher>

  A concealed voucher will not show up when other people look at your inventory.
  Use the first command to hide it, the second command to make it visible again.

Usage: +voucher/lock <voucher>
       +voucher/unlock <voucher>

  A locked voucher may be picked up or changed only by you. It's recommended
  that you lock all vouchers that you leave unattended.

See also: +help voucher3
        """,
    },
    {
        "key": "voucher3",
        "category": "Inventory",
        "text": """
Usage: +voucher/loc <voucher>/<item#>=<ic location>

  Each item on a voucher may have a specified IC location. You can use this to
  specify where you're carrying it, or even that it's located 'somewhere else'
  ICly. The location can be up to 20 characters long.

Usage: +voucher/use <voucher>/<item#>[:<qty>]

  This command 'uses up' <qty> of <item#>, effectively removing it from the
  voucher. If no <qty> is specified, then a quantity of 1 is assumed.

Usage: +voucher/chown <voucher>=<player>

  This command changes the IC owner of a voucher to <player>. This shows up via
  the '+owner' command and can be used to help find a voucher's owner if it is
  lost. If you give or sell something of yours ICly, please use this command
  to transfer ownership.

See also: +help voucher4
        """,
    },
    {
        "key": "voucher4",
        "category": "Inventory",
        "text": """
Usage: +voucher/rename <voucher>=<new name>

  This command may be used to change the name of <voucher> as it appears in your
  inventory or a room's contents to <new name>. The new name may be at most 38
  characters long.

Usage: +voucher/nuke <voucher>

  This command may be used to destroy an empty voucher. It will fail if the
  indicated <voucher> contains items.

Usage: +voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>

  This command is used to move an item from one voucher to another. It will move
  <qty> of the item numbered <item#> from <voucher> to <newvoucher>. If <qty> is
  not specified, then the entire quantity that exists on <voucher> is moved to
  <newvoucher>. <item#> may be a list of items, separated by spaces; all those
  specified will be moved.

See also: +help voucher5
        """,
    },
    {
        "key": "voucher5",
        "category": "Inventory",
        "text": """
Usage: +voucher/join <voucher1>=<voucher2>

  Use this command to take all items from <voucher2> and place them on
  <voucher1>. <voucher2> will be destroyed.

Usage: +voucher/split <voucher>/<item#>[:<qty>]

  This command can be used to take an item specified by <item#> from <voucher>
  and create a new voucher to contain it. The new item is moved to the newly
  created voucher, which will be in your inventory. You may move multiple items
  by specifying their numbers, separated by spaces, as <item#>.

Usage: +voucher/cloneitem <voucher>/<item#>[:<qty>]

  Some items are marked 'cloneable', such as spell formulae or deck programs,
  meaning they can be freely copied. This command performs that task to create
  another copy of the voucher item, usually for distribution. A quantity can be
  specified as a quantity of copies to create.

Usage: +voucher/create [=name]
       +voucher/add <voucher>=<name>[:<qty>][:cloneable]

  Create an empty voucher, or add items to an existing voucher. Use +voucher/add
  to add items; append :cloneable to mark an item as cloneable.

See also: +help equip
        """,
    },
    {
        "key": "voucher",
        "aliases": ["vouchers", "vinfo"],
        "category": "Inventory",
        "text": """
The voucher system enables you to manage IC objects that you are carrying. A voucher item represents the in-character object. Multiple items may be combined onto a single voucher. Anything which is not some other kind of in-character item will be represented by a voucher.

You can look at a voucher to see its contents. Vouchers may be picked up and dropped just like regular items. You may also use +sheet on a voucher to see the items contained in it.

A voucher may always be referred to by its name, if it's unique; by its dbref (the number after the #), or by its alias, if one is set.

Usage: +voucher/info <voucher>
       +voucher/info <voucher>/<item#>

     The first form displays the contents of the indicated <voucher>. The
     second form displays more detailed information about the indicated
     <item#> on the <voucher>. This command may be abbreviated as '+vinfo'

# voucher2

Usage: +voucher/alias <voucher>=<alias>

     Sets the <alias> of the <voucher> to the value you specify. The <alias>
     will then be able to be used to refer to the voucher in commands that
     require a <voucher> argument. The alias may be at most 20 characters and
     may only contain letters, numbers, dashes (-), and underscores (_).

Usage: +conceal <voucher>
       +unconceal <voucher>

     A concealed voucher will not show up when other people look at your
     inventory. Use the first command to hide it, the second command to
     make it visible again.

Usage: +voucher/lock <voucher>
       +voucher/unlock <voucher>

     A locked voucher may be picked up or changed only by you. It's
     recommended that you lock all vouchers that you leave unattended.

# voucher3

Usage: +voucher/loc <voucher>/<item#>=<ic location>

     Each item on a voucher may have a specified IC location. You can use
     this to specify where you're carrying it, or even that it's located
     'somewhere else' ICly. The location can be up to 20 characters long.

Usage: +voucher/use <voucher>/<item#>[:<qty>]

     This command 'uses up' <qty> of <item#>, effectively removing it from
     the voucher. If no <qty> is specified, then a quantity of 1 is assumed.

Usage: +voucher/chown <voucher>=<player>

     This command changes the IC owner of a voucher to <player>. This shows
     up via the '+owner' command (see '+help owner') and can be used to help
     us find a voucher's owner if it is lost. If you give or sell something
     of yours, ICly, then please use this command to transfer ownership.

# voucher4

Usage: +voucher/rename <voucher>=<new name>

     This command may be used to change the name of <voucher> as it appears
     in your inventory or a room's contents to <new name>. The new name may
     be at most 38 characters long.

Usage: +voucher/nuke <voucher>

     This command may be used to destroy an empty voucher. It will fail if
     the indicated <voucher> contains items.

Usage: +voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>

     This command is used to move an item from one voucher to another. It
     will move <qty> of the item numbered <item#> from <voucher> to
     <newvoucher>. If <qty> is not specified, then the entire quantity that
     exists on <voucher> is moved to <newvoucher>. <item#> may be a list of
     items, separated by spaces; all those specified will be moved.

# voucher5

Usage: +voucher/join <voucher1>=<voucher2>

     Use this to take all items from <voucher2> and place them on
     <voucher1>. <voucher2> will be destroyed.

Usage: +voucher/split <voucher>/<item#>[:<qty>]

     This command can be used to take an item specified by <item#> from
     <voucher> and create a new voucher to contain it. The new item is
     moved to the newly created voucher, which will be in your inventory.
     You may move multiple items by specifying their numbers, separated
     by spaces, as <item#>.

Usage: +voucher/cloneitem <voucher>/<item#>[:<qty>]

     Some items are marked 'cloneable', such as spell formulae or deck
     programs, meaning they can be freely copied. This command performs
     that task to create another copy of the voucher item, usually for
     distribution. A quantity can be specified as a quantity of copies
     to create.

Usage: +voucher/create [=name]
       +voucher/add <voucher>=<name>[:<qty>][:cloneable]

     Create an empty voucher, or add items to an existing voucher. Use
     :cloneable to mark an item as cloneable for +voucher/cloneitem.

See also: +help equip
        """,
    },
    {
        "key": "voucher",
        "aliases": ["vouchers"],
        "category": "Inventory",
        "text": """
The voucher system enables you to manage IC objects that you are carrying. A voucher item represents the in-character object. Multiple items may be combined onto a single voucher. Anything which is not some other kind of in-character item will be represented by a voucher.

You can look at a voucher to see its contents. Vouchers may be picked up and dropped just like regular items. You may also use +sheet on a voucher to see the items contained in it.

A voucher may always be referred to by its name, if it's unique; by its dbref (the number after the #), or by its alias, if one is set.

Usage: +voucher/info <voucher>
       +voucher/info <voucher>/<item#>

     The first form displays the contents of the indicated <voucher>. The
     second form displays more detailed information about the indicated
     <item#> on the <voucher>. This command may be abbreviated as '+vinfo'

-----------------------> Continued in '+help voucher2' <-----------------------
        """,
    },
    {
        "key": "voucher2",
        "category": "Inventory",
        "text": """
Usage: +voucher/alias <voucher>=<alias>

     Sets the <alias> of the <voucher> to the value you specify. The <alias>
     will then be able to be used to refer to the voucher in commands that
     require a <voucher> argument. The alias may be at most 20 characters and
     may only contain letters, numbers, dashes (-), and underscores (_).

Usage: +conceal <voucher>
       +unconceal <voucher>

     A concealed voucher will not show up when other people look at your
     inventory. Use the first command to hide it, the second command to
     make it visible again.

Usage: +voucher/lock <voucher>
       +voucher/unlock <voucher>

     A locked voucher may be picked up or changed only by you. It's
     recommended that you lock all vouchers that you leave unattended.

-----------------------> Continued in '+help voucher3' <-----------------------
        """,
    },
    {
        "key": "voucher3",
        "category": "Inventory",
        "text": """
Usage: +voucher/loc <voucher>/<item#>=<ic location>

     Each item on a voucher may have a specified IC location. You can use
     this to specify where you're carrying it, or even that it's located
     'somewhere else' ICly. The location can be up to 20 characters long.

Usage: +voucher/use <voucher>/<item#>[:<qty>]

     This command 'uses up' <qty> of <item#>, effectively removing it from
     the voucher. If no <qty> is specified, then a quantity of 1 is assumed.

Usage: +voucher/chown <voucher>=<player>

     This command changes the IC owner of a voucher to <player>. This shows
     up via the '+owner' command (see '+help owner') and can be used to help
     us find a voucher's owner if it is lost. If you give or sell something
     of yours, ICly, then please use this command to transfer ownership.

-----------------------> Continued in '+help voucher4' <-----------------------
        """,
    },
    {
        "key": "voucher4",
        "category": "Inventory",
        "text": """
Usage: +voucher/rename <voucher>=<new name>

     This command may be used to change the name of <voucher> as it appears
     in your inventory or a room's contents to <new name>. The new name may
     be at most 38 characters long.

Usage: +voucher/nuke <voucher>

     This command may be used to destroy an empty voucher. It will fail if
     the indicated <voucher> contains items.

Usage: +voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>

     This command is used to move an item from one voucher to another. It
     will move <qty> of the item numbered <item#> from <voucher> to
     <newvoucher>. If <qty> is not specified, then the entire quantity that
     exists on <voucher> is moved to <newvoucher>. <item#> may be a list of
     items, separated by spaces; all those specified will be moved.

-----------------------> Continued in '+help voucher5' <-----------------------
        """,
    },
    {
        "key": "voucher5",
        "category": "Inventory",
        "text": """
Usage: +voucher/join <voucher1>=<voucher2>

     Use this command to take all items from <voucher2> and place them on
     <voucher1>. <voucher2> will be destroyed.

Usage: +voucher/split <voucher>/<item#>[:<qty>]

     This command can be used to take an item specified by <item#> from
     <voucher> and create a new voucher to contain it. The new item is
     moved to the newly created voucher, which will be in your inventory.
     You may move multiple items by specifying their numbers, separated
     by spaces, as <item#>.

Usage: +voucher/cloneitem <voucher>/<item#>[:<qty>]

     Some items are marked 'cloneable', such as spell formulae or deck
     programs, meaning they can be freely copied. This command performs
     that task to create another copy of the voucher item, usually for
     distribution. A quantity can be specified as a quantity of copies
     to create.

Usage: +voucher/create [=name]  - Create an empty voucher
Usage: +voucher/add <voucher>=<name>[:<qty>][:cloneable]  - Add item to voucher

See also: +help equip
        """,
    },
    {
        "key": "voucher",
        "aliases": ["vouchers"],
        "category": "Inventory",
        "text": """
The voucher system enables you to manage IC objects that you are carrying. A voucher item represents the in-character object. Multiple items may be combined onto a single voucher. Anything which is not some other kind of in-character item will be represented by a voucher.

You can look at a voucher to see its contents. Vouchers may be picked up and dropped just like regular items. You may also use +sheet on a voucher to see the items contained in it.

A voucher may always be referred to by its name, if it's unique; by its dbref (the number after the #), or by its alias, if one is set.

Usage: +voucher/info <voucher>
       +voucher/info <voucher>/<item#>

     The first form displays the contents of the indicated <voucher>. The
     second form displays more detailed information about the indicated
     <item#> on the <voucher>. This command may be abbreviated as '+vinfo'

-----------------------> Continued in '+help voucher2' <-----------------------
        """,
    },
    {
        "key": "voucher2",
        "category": "Inventory",
        "text": """
Usage: +voucher/alias <voucher>=<alias>

     Sets the <alias> of the <voucher> to the value you specify. The <alias>
     will then be able to be used to refer to the voucher in commands that
     require a <voucher> argument. The alias may be at most 20 characters and
     may only contain letters, numbers, dashes (-), and underscores (_).

Usage: +conceal <voucher>
       +unconceal <voucher>

     A concealed voucher will not show up when other people look at your
     inventory. Use the first command to hide it, the second command to
     make it visible again.

Usage: +voucher/lock <voucher>
       +voucher/unlock <voucher>

     A locked voucher may be picked up or changed only by you. It's
     recommended that you lock all vouchers that you leave unattended.

-----------------------> Continued in '+help voucher3' <-----------------------
        """,
    },
    {
        "key": "voucher3",
        "category": "Inventory",
        "text": """
Usage: +voucher/loc <voucher>/<item#>=<ic location>

     Each item on a voucher may have a specified IC location. You can use
     this to specify where you're carrying it, or even that it's located
     'somewhere else' ICly. The location can be up to 20 characters long.

Usage: +voucher/use <voucher>/<item#>[:<qty>]

     This command 'uses up' <qty> of <item#>, effectively removing it from
     the voucher. If no <qty> is specified, then a quantity of 1 is assumed.

Usage: +voucher/chown <voucher>=<player>

     This command changes the IC owner of a voucher to <player>. This shows
     up via the '+owner' command (see '+help owner') and can be used to help
     us find a voucher's owner if it is lost. If you give or sell something
     of yours, ICly, then please use this command to transfer ownership.

-----------------------> Continued in '+help voucher4' <-----------------------
        """,
    },
    {
        "key": "voucher4",
        "category": "Inventory",
        "text": """
Usage: +voucher/rename <voucher>=<new name>

     This command may be used to change the name of <voucher> as it appears
     in your inventory or a room's contents to <new name>. The new name may
     be at most 38 characters long.

Usage: +voucher/nuke <voucher>

     This command may be used to destroy an empty voucher. It will fail if
     the indicated <voucher> contains items.

Usage: +voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>

     This command is used to move an item from one voucher to another. It
     will move <qty> of the item numbered <item#> from <voucher> to
     <newvoucher>. If <qty> is not specified, then the entire quantity that
     exists on <voucher> is moved to <newvoucher>. <item#> may be a list of
     items, separated by spaces; all those specified will be moved.

-----------------------> Continued in '+help voucher5' <-----------------------
        """,
    },
    {
        "key": "voucher5",
        "category": "Inventory",
        "text": """
Usage: +voucher/join <voucher1>=<voucher2>

     Use this command to take all items from <voucher2> and place them on
     <voucher1>. <voucher2> will be destroyed.

Usage: +voucher/split <voucher>/<item#>[:<qty>]

     This command can be used to take an item specified by <item#> from
     <voucher> and create a new voucher to contain it. The new item is
     moved to the newly created voucher, which will be in your inventory.
     You may move multiple items by specifying their numbers, separated
     by spaces, as <item#>.

Usage: +voucher/cloneitem <voucher>/<item#>[:<qty>]

     Some items are marked 'cloneable', such as spell formulae or deck
     programs, meaning they can be freely copied. This command performs
     that task to create another copy of the voucher item, usually for
     distribution. A quantity can be specified as a quantity of copies
     to create.

See also: +help equip
        """,
    },
    {
        "key": "voucher",
        "aliases": ["vouchers", "vinfo"],
        "category": "Inventory",
        "text": """
The voucher system enables you to manage IC objects that you are carrying. A voucher item represents the in-character object. Multiple items may be combined onto a single voucher. Anything which is not some other kind of in-character item will be represented by a voucher.

You can look at a voucher to see its contents. Vouchers may be picked up and dropped just like regular items. You may also use +sheet on a voucher to see the items contained in it.

A voucher may always be referred to by its name, if it's unique; by its dbref (the number after the #), or by its alias, if one is set.

Usage: +voucher/info <voucher>
       +voucher/info <voucher>/<item#>

     The first form displays the contents of the indicated <voucher>. The
     second form displays more detailed information about the indicated
     <item#> on the <voucher>. This command may be abbreviated as '+vinfo'

-----------------------> Continued in '+help voucher2' <-----------------------
        """,
    },
    {
        "key": "voucher2",
        "category": "Inventory",
        "text": """
Usage: +voucher/alias <voucher>=<alias>

     Sets the <alias> of the <voucher> to the value you specify. The <alias>
     will then be able to be used to refer to the voucher in commands that
     require a <voucher> argument. The alias may be at most 20 characters and
     may only contain letters, numbers, dashes (-), and underscores (_).

Usage: +conceal <voucher>
       +unconceal <voucher>

     A concealed voucher will not show up when other people look at your
     inventory. Use the first command to hide it, the second command to
     make it visible again.

Usage: +voucher/lock <voucher>
       +voucher/unlock <voucher>

     A locked voucher may be picked up or changed only by you. It's
     recommended that you lock all vouchers that you leave unattended.

-----------------------> Continued in '+help voucher3' <-----------------------
        """,
    },
    {
        "key": "voucher3",
        "category": "Inventory",
        "text": """
Usage: +voucher/loc <voucher>/<item#>=<ic location>

     Each item on a voucher may have a specified IC location. You can use
     this to specify where you're carrying it, or even that it's located
     'somewhere else' ICly. The location can be up to 20 characters long.

Usage: +voucher/use <voucher>/<item#>[:<qty>]

     This command 'uses up' <qty> of <item#>, effectively removing it from
     the voucher. If no <qty> is specified, then a quantity of 1 is assumed.

Usage: +voucher/chown <voucher>=<player>

     This command changes the IC owner of a voucher to <player>. This shows
     up via the '+owner' command (see '+help owner') and can be used to help
     us find a voucher's owner if it is lost. If you give or sell something
     of yours, ICly, then please use this command to transfer ownership.

-----------------------> Continued in '+help voucher4' <-----------------------
        """,
    },
    {
        "key": "voucher4",
        "category": "Inventory",
        "text": """
Usage: +voucher/rename <voucher>=<new name>

     This command may be used to change the name of <voucher> as it appears
     in your inventory or a room's contents to <new name>. The new name may
     be at most 38 characters long.

Usage: +voucher/nuke <voucher>

     This command may be used to destroy an empty voucher. It will fail if
     the indicated <voucher> contains items.

Usage: +voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>

     This command is used to move an item from one voucher to another. It
     will move <qty> of the item numbered <item#> from <voucher> to
     <newvoucher>. If <qty> is not specified, then the entire quantity that
     exists on <voucher> is moved to <newvoucher>. <item#> may be a list of
     items, separated by spaces; all those specified will be moved.

-----------------------> Continued in '+help voucher5' <-----------------------
        """,
    },
    {
        "key": "voucher5",
        "category": "Inventory",
        "text": """
Usage: +voucher/join <voucher1>=<voucher2>

     Use this command to take all items from <voucher2> and place them on
     <voucher1>. <voucher2> will be destroyed.

Usage: +voucher/split <voucher>/<item#>[:<qty>]

     This command can be used to take an item specified by <item#> from
     <voucher> and create a new voucher to contain it. The new item is
     moved to the newly created voucher, which will be in your inventory.
     You may move multiple items by specifying their numbers, separated
     by spaces, as <item#>.

Usage: +voucher/cloneitem <voucher>/<item#>[:<qty>]

     Some items are marked 'cloneable', such as spell formulae or deck
     programs, meaning they can be freely copied. This command performs
     that task to create another copy of the voucher item, usually for
     distribution. A quantity can be specified as a quantity of copies
     to create.

See also: +help equip
        """,
    },
    # === Investigation / Mystery System (Interface RED Vol 5) ===
    {
        "key": "investigation",
        "aliases": ["mystery", "focus", "evidence check", "investigate"],
        "category": "General",
        "text": """
The |wInvestigation System|n (Interface RED Vol 5) uses |wFocus|n to |wscan|n for leads, then |wEvidence Checks|n to decipher them. Mysteries have hidden |wcomplexity|n; successful leads reduce it to zero to solve the case.

# Mysteries (no spoilers)

|w+mystery|n
  Open investigations, your Focus, and short blurbs. Not full clue lists.

|w+mystery/info <id>|n
  Public summary: description, clue/obstacle counts, where to start looking.

|w+mystery/focus|n
  Focus details.

# Scanning and following up

You do |wnot|n see staff clues until you |wnotice|n them.

|w+investigate/scan [here|<name>]|n
  |wPerception + INT|n vs the mystery's scan DV. If you have |walready noticed|n every lead that can appear in this scope, |wno roll and no Focus cost|n -- try another spot, decipher a prerequisite, or clear a gate. Otherwise costs 1d6 Focus. On success, exposes new leads in scope (room, element, object, or exit) that you are allowed to know about. Lower-|wpriority|n clues tend to surface first. Linked clues stay hidden until prerequisites are met and any |wgating obstacle|n is overcome.

|w+investigate <id>|n or |w+investigate <spot>|n
  |wEvidence check|n on a lead you |walready noticed|n (after scan). Uses the clue's skill vs its DV.

|w+investigate/leads|n
  Notebook: every lead you |wnoticed|n, where it was placed, what you must decipher first, and |wother leads that depend on this one|n.

|w+investigate/hint|n
  DV15 Deduction; 1d6 Focus either way -- GM may give a nudge.

|w+investigate/overcome <obstacle id>|n
  Push past a mystery obstacle (DV on the obstacle). Focus cost on success or failure. If a lead is |wgated|n, |w+investigate/scan|n and |w+mystery|n will point you at the obstacle id and |c+investigate/overcome|n; |w+mystery/info|n lists obstacles for that case.

|w+rest|n / |w+rest/concentrate|n
  Recover extra Focus (see help +rest).

# How evidence works

Each lead has a DV. Roll |wSkill + Stat + 1d10|n vs DV (exact hit fails). The game shows your |wstat + skill + dice|n breakdown, the |wDV|n, and |wby how much|n you beat or missed the DV. |gSuccess:|n deals damage to mystery complexity; staff may show |wdescription|n text. |rFailure:|n costs Focus; fumbles may add complications. One attempt per lead per day.

See also: +help facilitating mysteries (staff)
        """,
    },
    {
        "key": "facilitating mysteries",
        "aliases": ["mystery staff", "mystery building", "investigation staff"],
        "category": "Building and Housing",
        "locks": "read:perm(Builder)",
        "text": """
Staff guide to setting up and running investigation mysteries. Requires Builder permission.

# Overview

Players use |w+investigate/scan|n and |w+investigate|n only after exposure -- they never see raw clue lists. Staff use |w+mystery/*|n and |w+clue/*|n.

# Mystery shell

|w+mystery/create <name>=<goal>,<complexity or tier>|n
  Create a mystery. Then set player text:

|w+mystery/public <id>=<player-facing description>|n
|w+mystery/start <id>=<where to start looking>|n
|w+mystery/scandv <id>=<dv>|n -- Perception scan difficulty for this mystery (default 13).

|w+mystery/obstacle <mystery id>=<type>,<skill>,<dv>[,desc]|n
  Add an obstacle. Players use |w+investigate/overcome <id>|n.

|w+mystery/link <mystery id>=<mission id>|n
|w+mystery/unlink <mystery id>|n

# Character Focus (staff)

|w+focus <character>|n or |w+focus/show <character>|n -- Current / max Focus.

|w+focus/refresh <character>|n -- Set Focus to maximum (fixes bad state or post-event top-up).

|w+focus/set <character>=<n>|n -- Set Focus to a number (clamped 0..max).

|w+focus/resetrest <character>|n -- Clear the daily |c+rest|n lock so they can concentrate again today.

# Daily attempts (staff)

|w+clue/resetattempts <character>[=<clue id>]|n -- Clears |wtoday's|n evidence check so they can roll again. |w+clue/resetattempts/all <character>[=<clue id>]|n wipes full history (dangerous for chains).

|w+clue/resetobstacle <character>[=<obstacle id>]|n -- Same for |w+investigate/overcome|n daily lock. |w/all|n for full history.

# Clues and placement

|w+clue/create <mystery id>=<type>,<skills>,<dv>,<obfuscation>[,staff description]|n

|w+clue/add <target>=<clue id>|n or |w<room>=<id>/<element>|n

|w+clue/playerhint <clue id>=<text>|n -- Shown to players when the clue is exposed (after scan).

|w+clue/priority <clue id>=<n>|n -- Lower = appears earlier on scan (ordering).

|w+clue/gate <clue id>=<obstacle id>|n -- Must overcome that obstacle before the clue can be exposed or investigated. |w0|n clears.

|w+clue/requires <dependent id>=<prerequisite id>|n -- Prereq must be |wsuccessfully deciphered|n before the dependent can appear on scan.

|w+clue/link <id>=<id>|n -- Informational link only.

|w+clue/list [mystery]|n or |w+clues|n -- Full staff listing.

|w+clue/remove|n / |w+clue/destroy|n -- Remove placement or delete clue.

# Workflow

1. +mystery/create ... then +mystery/public, +mystery/start, +mystery/scandv
2. +mystery/obstacle ... if needed; +clue/gate to tie clues to obstacles
3. +clue/create ... for each clue; +clue/playerhint and +clue/priority
4. +clue/add ... place on grid (elements/exits/objects)
5. +clue/requires ... for chains
6. +mystery/link ... optional mission
7. +clue/list to verify

See also: +help investigation
        """,
    },
    {
        "key": "elflines",
        "aliases": ["elo", "elflines online", "+elo"],
        "category": "General",
        "text": """
Elflines Online (ELO) is the massively multiplayer online game within the Cyberpunk universe. Played via the Segotari RUSH REVOLUTION Braindance headset, edgerunners escape the meat world to fight the forces of darkness as elves in the Elflands.

# Commands

|w+elo|n
  Show your ELO status and character summary.

|w+elo/sheet|n
  View your ELO character sheet.

|wsheet/elo|n
  Elflines Online character generation: allocate stats (50 pts, 3-8 each), skills (60 pts, max 6 each), set elfname, and pick equipment (200gp). New characters get 50 STAT points, 60 skill points, and 200gp. No LUCK. Stats 3-8 at creation. Language (Elven) is free at 4.

|w+elo/login|n
  Enter the Elflands. Requires subscription (20eb/month, included in Generic Prepak+) and a RUSH REVOLUTION headset. You leave the meat world and appear in the ELO lobby.

|w+elo/logout|n
  Leave the Elflands and return to the meat world.

|w+elo/who|n
  List players currently in the Elflands.

|w+elo/armory|n
  List equipment available in ELO (armor, weapons, consumables) and gp prices.

# Elflines (Guilds)

|w+elfline|n
  List your Elflines.

|w+elfline/create <name>|n
  Found a new Elfline. You become the leader.

|w+elfline/join <name>|n
  Join an existing Elfline.

|w+elfline/leave [<name>]|n
  Leave your current Elfline.

|w+elfline/info [<name>]|n
  View Elfline details, leader, and member count.

|w+elfline/invite <player>|n
  Invite someone to your Elfline (leader/officer only).

|w+elfline/kick <player>|n
  Remove a member (leader only).

# Lore

The forests of the Elflands were once protected by a great hero. With the hero gone, the forces of darkness spread miasma and drove the elves behind settlement walls. A new generation of heroes rises to fight back. Elflines (guilds) are your family in the game--more than the parents who ignored you or the sibling who stole your Kibble.

# Staff

Builders use |w+elosetup|n to create the ELO Lobby room. Then add exits to build the Elflands grid. Use typeclass |wtypeclasses.elflines_rooms.ElflinesRoom|n for ELO rooms.
        """,
    },
    # === Apartment Rental System ===
    {
        "key": "rental workflow",
        "aliases": ["rent", "apartments", "housing", "rent workflow"],
        "category": "Economy",
        "text": """
The apartment rental system lets you rent or purchase housing in Night City. Costs are in Eurodollars (eb). Rent is a |wthreshold check|n--you must maintain enough eb to keep your apartment, but no eb is deducted monthly. You can also |wpurchase|n an apartment outright to avoid monthly checks.

|yFinding Apartments|n

|w+rent/search|n
  List all buildings with available apartments. Shows location (hierarchy), area code, available slots, apartment types, and any non-default cost modifiers. Use this to find where to rent without scouring the grid.

|yRenting an Apartment|n

|w+rent <type>|n
  Rent at your current location. You must specify an apartment type (e.g. |w+rent Studio Apartment|n or |w+rent One-Bedroom Apartment|n). Use |w+rent/status|n in the lobby or on a floor to see available types.
  Use this in:
  - A building |wlobby|n -- assigns you an apartment on a random floor
  - On a specific |wfloor|n -- assigns you an apartment on that floor
  - Inside a |wvacant apartment|n -- take over the existing unit

You need enough Eurodollars to meet the rent threshold. Check your balance with |wbalance|n.

|yCustomizing Your Apartment|n

|w+rent/desc =<text>|n
  Change the description of the room you're in.

|w+rent/name =<name>|n
  Rename the room (e.g. change "Bedroom 2" to "Workshop").

|w+rent/exit <exit>=<new name>|n
  Change the display name of an exit. Aliases (B1, B2, O, etc.) stay the same.
  Example: +rent/exit Bedroom 2=Workshop

|w+rent/home|n
  Set this apartment as your IC home. Use the |whome|n command to return here.

|yCo-Residents and Partners|n

|w+rent/add <character>|n
  Add a co-resident (primary renter only). They get a room and can set this as their home. Available on One-Bedroom and larger apartments.

|w+rent/remove <character>|n
  Remove a co-resident (primary renter only).

|w+rent/partner <character>|n
  Invite a romantic partner to move in. They must go to your apartment and type |w+rent/partner confirm|n to accept. Partners have the same authority as you.

|yDoors and Security|n

|w+rent/lock [<exit>]|n
  Lock the door. Residents and partners can lock/unlock.

|w+rent/unlock [<exit>]|n
  Unlock the door.

|yOther Commands|n

|w+rent/purchase|n
  Buy the apartment outright. Deducts eb once; no more monthly rent checks.

|w+rent/info|n
  Show rental details (type, cost, residents, status).

|w+rent/leave|n
  Leave your rental. If you're primary, a co-resident takes over or the apartment becomes vacant.

|whome|n
  Return to your IC home (after using +rent/home).

|yLocation Format|n

Apartments display as: |wRoom/Apt# -- Building Name -- District|n
Example: 212 Main Room -- Kabuki Heights -- Watson

See also: +help balance, +help rental staff
        """,
    },
    {
        "key": "rental staff",
        "aliases": ["staff rental", "rental creation", "apartment building", "housing setup"],
        "category": "Building and Housing",
        "locks": "read:perm(Builder)",
        "text": """
Staff guide to setting up apartment buildings and rental floors. Requires Builder permission.

|yOverview|n

Apartments are created when players use |w+rent <type>|n. Staff configure the building lobby, add floor rooms, set floor numbers, and choose which apartment types are available. Costs can be modified per building or per apartment.

|yInitial Building Setup|n

|w+manage/setlobby|n
  Set the current room as the building lobby. Do this first.

|w+manage/sethousing/apartment <resources> [max_units]|n
  Configure as an apartment building. Resources and max_units are legacy; rental costs come from apartment types.

|w+manage/addtype <type>|n
  Add apartment types available in this building. Use exact names:
  Cube Hotel, Cargo Container, Studio Apartment, One-Bedroom Apartment,
  Two-Bedroom Apartment, Corporate Conapt, Upscale Conapt, Luxury Penthouse,
  Corporate Beaverville House, Corporate Beaverville McMansion

  Example: +manage/addtype "One-Bedroom Apartment"

|w+manage/types|n
  List all available types and which are enabled for this building.

|yAdding Floors|n

1. Create the floor room (e.g. with |wdig|n) and add exits between lobby and floor.
2. Stand in the floor room.
3. |w+manage/addroom|n -- Adds this room to the building zone.
4. |w+manage/floor <number> [max_units]|n -- Set floor number and max units per floor (default 6).
   Example: +manage/floor 4 6 -- Floor 4, up to 6 apartments (401-406).

The floor number becomes the prefix for apartment numbers. Floor 4 with unit 05 = apartment 405.

|yCost Modification|n

|w+manage/setcost <room>=<rent_modifier>,<purchase_modifier>|n
  Adjust costs for a specific apartment. Modifiers are added to base costs.
  Example: +manage/setcost #12345=500,5000 -- Adds 500eb to rent, 5000eb to purchase.

# Creating Apartments (Staff)

|w+manage/createapt [type] [=rent,purchase,rooms]|n
  Create an apartment on the current floor. Use in lobby (random floor) or on a floor.
  |w+manage/createapt|n -- Create using first available type
  |w+manage/createapt "Luxury Penthouse"|n -- Create with default costs
  |w+manage/createapt "Luxury Penthouse"=20000,200000|n -- Override rent and purchase
  |w+manage/createapt "Luxury Penthouse"=20000,200000,6|n -- Override all (6 rooms)
  |w+manage/createapt Custom=5000,75000,4|n -- Bespoke: 4 rooms, 5k rent, 75k purchase

Custom apartments use generic room names (Room 2, Room 3, ...). Add "Custom" to available types with +manage/addtype Custom first.

|yOther +manage Commands|n

|w+manage/info|n
  Show building info, connected rooms, available types.

|w+manage/removeroom|n
  Remove current room from the building zone.

|w+manage/apartments|n
  List apartments in the building.

|w+manage/apartments/floor=<number>|n
  List apartments on a specific floor.

|w+manage/apartments <player>|n
  List apartments owned by a player.

|yWorkflow Summary|n

1. Create lobby room, set description and exits to floors.
2. +manage/setlobby
3. +manage/addtype "Studio Apartment"
4. +manage/addtype "One-Bedroom Apartment"
5. (Repeat for each floor) dig Floor 4; add exits lobby<->floor; +manage/addroom; +manage/floor 4 6
6. Players can now +rent in the lobby or on any floor.

|yRoom Layouts|n

Apartment types generate rooms automatically:
- One-Bedroom: Main Room, Bedroom
- Two-Bedroom: Main Room, Bedroom 1, Bedroom 2
- Corporate Conapt: Main Room, Bedroom, Side Room
- Upscale Conapt: Main Room, Bedroom 1, Bedroom 2, Side Room
- Luxury Penthouse: Main Room, Bedroom 1, Bedroom 2, Side Room, Patio
- Beaverville House: Main Room, Bedroom 1, Bedroom 2, Side Room, Yard
- McMansion: Main Room, Bedroom 1-3, Side Room, Yard

Exits use aliases (B1, B2, SR, O, etc.) that players cannot change.

See also: +help rental workflow, +help room creation
        """,
    },
    {
        "key": "policies",
        "aliases": ["policy", "policies"],
        "category": "General",
        "text": """
|wPolicies|n
|yAll characters and character art is 18+. No exceptions.|n

|yDont be a dick, choom|n, In fact if the opportunity presents itself you
should be excellent.

|yCheating|n
In the unlikely event that you find a way to hack around the code and
cheat, DO report it to staff. DON'T use it to cheat.
We rely on your logs as a means to verify things that happened. Please
don't falsify them. See the section below on logs.

|yLogs|n
We rely on your logs as a means to verify things that happened. Please
don't falsify them. See the section below on logs.

|yHarassment|n
Harassment is bad, m'kay?

|yLying|n
Lying to other players (including admins) OOCly about IC events is not
acceptable. This especially applies to situations where your OOC words can
have an IC effect. Lying about intentions within a scene can also result in major problems due to consent issues.
Please don't randomly pick up objects that don't belong to you. This is
not a MUD, and items lying around are not free gifts from the game to pick up
as your own. Instead, please notify a staff member.

|yThe Admins are not always right.|n
The Admins are not always right. We are human beings and fallible. If you
believe something is wrong, whether with a plot, a queue request, or
whatever, then please feel free to let us know. However, continuing to argue
a point with a given admin once they've said they are no longer willing to
debate the point is not allowed. If you still feel there are grounds for a
complaint, contact Mnemosyne. 

|ySpoofing|n
Spoofing of other players (i.e. using @emit to cause poses, messages, OOC
comments/bbposts/channel chat, etc. to be displayed as if they had typed them
is not allowed.

|yPrivacy|n
Do not enter private areas of the grid without either the approval of an
admin or the permission of the player who owns the private area, even if those areas are unlocked via code.
Private areas include apartments or any other area that is clearly set up as
not intended for general public access. If you inadvertently enter a private
area, leave immediately.

|yOuting|n
Do not OOCly 'out' someone's alts, IC secrets or in any other way betray 
another players trust or damage their story. This applies to staff plots and
staff files as well.
        """,
    },
    {
        "key": "vehicle combat",
        "aliases": ["vehicles", "driving", "ramming", "vehicle rules"],
        "category": "Combat",
        "text": """
Vehicle combat quick reference (Cyberpunk RED core style):

# Vehicle stats

|wSDP|n (Structural Damage Points) is a vehicle's HP.
- If SDP is at least 1, the vehicle can still move.
- At 0 SDP, the vehicle is destroyed, no longer cover, and cannot move until repaired.

|wSeats|n is comfortable passenger capacity.
|wSpeed (Combat)|n is the vehicle's MOVE in combat time.
|wSpeed (Narrative)|n is top speed for non-combat travel.

# Targeting and weak points

- Vehicles cannot dodge attacks.
- Occupants can still dodge attacks targeted at them if they could normally dodge those attacks on foot.
- Vehicle glass has no HP and provides no cover (unless upgraded).
- You can use an aimed shot vs weak points at -8.
  If you hit, damage that gets through vehicle SP is doubled.
- Against a moving vehicle with melee, weak-point hit requires DV13 and still takes the -8.

# Entering, starting, and driving

- Getting into a vehicle is an Action.
- Getting out is movement (no Action).
- Starting or stopping a vehicle is an Action.
- Starting a vehicle immediately:
  1) Puts driver at top of Initiative
  2) Uses vehicle MOVE instead of driver's MOVE
  3) Driver cannot use Run Action

|wInterface Plugs|n:
- With plugs, you can drive hands-free.
- Without plugs, one hand must remain on controls.
- If you remove that hand, at start of your next Turn you Lose Control.

# Basic driving and maneuvers

Basic driving needs no Check if |wREF + control skill > 9|n.
Otherwise, each Turn requires an Action and DV10 check:
|wREF + relevant control skill + 1d10|n.
Failure = Lose Control.

Maneuvers require both Action and Move Action.
Failure = Lose Control.

Common maneuver DVs:
- Swerve: 13
- Sharp Turn: 13
- Emergency Stop: 13
- Bootleg Turn: 17
- Jump: 17
- Landing (air vehicle): 13
- Aerobatic Maneuver (air vehicle): 17

# Losing control and ramming

If you lose control, GM determines your movement for that Turn.
If you impact something, resolve as a ram.

Ramming deals |w6d6|n to:
- your vehicle, and
- the impacted pedestrian/cover/vehicle.

Everyone involved suffers |wWhiplash|n Critical Injury.

If impacted cover/vehicle is reduced to 0 HP, movement can continue.
Otherwise movement stops.

Pedestrians can attempt to dodge a ramming vehicle at:
|wDV13 (DEX + Evasion + 1d10)|n.
        """,
    },
]


def _build_unified_voucher_help_entry():
    """Single authoritative voucher help entry (replaces voucher2-5 pages)."""
    return {
        "key": "voucher",
        "aliases": ["vouchers", "vinfo", "voucher2", "voucher3", "voucher4", "voucher5"],
        "category": "Inventory",
        "text": """
Vouchers are physical IC objects that store one or more item entries. You can carry, drop,
lock, conceal, rename, split, merge, and transfer ownership just like before.

Typed voucher items now integrate with standard inventory:
* weapon, armor, gear, cyberware, ammunition, vehicle
* claimed items become normal inventory objects and work with existing systems

# Core usage

|w+voucher|n
  List vouchers you are carrying.

|w+voucher/info <voucher>|n
|w+voucher/info <voucher>/<item#>|n
  View voucher contents or item details.

|w+voucher/use <voucher>/<item#>[:<qty>]|n
  For typed items: claim into normal inventory.
  For untyped items: consume/remove quantity from voucher.

|w+voucher/withdraw <voucher>/<item#>[:<qty>]|n
  Explicitly claim typed voucher items into inventory models.

# Item and voucher management

|w+voucher/alias <voucher>=<alias>|n
|w+voucher/lock <voucher>|n / |w+voucher/unlock <voucher>|n
|w+voucher/loc <voucher>/<item#>=<ic location>|n
|w+voucher/chown <voucher>=<player>|n
|w+voucher/rename <voucher>=<new name>|n
|w+voucher/nuke <voucher>|n
|w+voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>|n
|w+voucher/join <voucher1>=<voucher2>|n
|w+voucher/split <voucher>/<item#>[:<qty>]|n
|w+voucher/cloneitem <voucher>/<item#>[:<qty>]|n

# Creating and editing vouchers

|w+voucher/create [name]|n
  Create an empty voucher.

|w+voucher/add <voucher>=<item name>|n
  Add an item from your inventory to a voucher.

|w+voucher/add <voucher>=<type>/<name>|n  (staff)
  Create a typed custom voucher item.

|w+voucher/setstat <voucher>/<item#>=<field>=<value>|n  (staff)
  Set type-specific stats/fields.

# Integration notes

* Claimed weapons/armor can be equipped and used by attack commands.
* Claimed equipment appears in HUD and standard inventory views.
* Claimed cyberware is installable via |wcyberware/install|n.
* |wattack/reload|n can consume matching ammo from vouchers when inventory ammo is low.
* Deck/program/deck-option voucher items work through normal inventory/netrunning paths once claimed.

See also:
|w+help owner|n, |w+help equip|n, |w+help cyberware|n, |w+help deck|n
        """,
    }


def _consolidate_voucher_help_entries(entries):
    """
    Consolidate legacy paginated voucher entries into one authoritative entry.
    Keeps non-voucher entries in original order.
    """
    voucher_keys = {"voucher", "voucher2", "voucher3", "voucher4", "voucher5"}
    first_idx = None
    filtered = []
    for idx, entry in enumerate(entries):
        key = (entry.get("key") or "").strip().lower()
        if key in voucher_keys:
            if first_idx is None:
                first_idx = len(filtered)
            continue
        filtered.append(entry)

    insert_at = first_idx if first_idx is not None else len(filtered)
    filtered.insert(insert_at, _build_unified_voucher_help_entry())
    return filtered


HELP_ENTRY_DICTS = _consolidate_voucher_help_entries(HELP_ENTRY_DICTS)
