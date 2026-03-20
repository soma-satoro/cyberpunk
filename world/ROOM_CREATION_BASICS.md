# Room Creation Basics

A step-by-step guide to creating and configuring rooms. Requires Builder permission.

## Step 1: Creating Rooms with Dig

Use `dig` to create a new room. You must be in an existing room (or Limbo) to dig from.

- **dig \<roomname\>** -- Creates a room with no exits. You will need to add exits manually later.

- **dig \<roomname\> = \<exit_to_new\>, \<exit_back\>** -- Creates a room and two exits: one from your current room to the new room, and one back.
  - Example: `dig Corpo Plaza = east, west`

Use `tunnel` to quickly create a room in a direction with bidirectional exits:

- **tunnel \<direction\> = \<roomname\>**
  - Example: `tunnel north = Back Alley`
  - Creates "Back Alley" north of you and adds north/south exits both ways.

## Step 2: Descriptions

Use `@desc` to set what players see when they look at the room:

- **@desc here = \<text\>** -- Sets the description of the room you are in. Use `here` to refer to your current location.

- **@desc/edit** -- Opens a line editor for longer descriptions. Type your text, then type `@` on a new line to save.

### Room description formatting

Room descriptions support special formatting:

- **%r** -- Paragraph break (blank line)
- **%t** -- Indent (for secondary/indented lines within a paragraph)

## Step 3: Area Management (+area)

Areas organize rooms with codes like NC01, WB02. Use `+area/list` to see defined areas. Admins may need to run `+area/init` first.

| Command | Description |
|---------|-------------|
| `+area/list` | List all areas and their codes |
| `+area/add <code>=<name>/<description>` | Add area (e.g. `+area/add NC=Night City/The megacity`) |
| `+area/remove <code>` | Remove an empty area |
| `+area/info <code>` | Show area details |
| `+area/rooms <code>` | List rooms in an area |

Area codes are 2-4 characters (e.g. NC, WB, WA). Default areas include NC (Night City), WB (Westbrook), WA (Watson), etc.

## Step 4: Room Setup (+room and +room/tag)

Use `+room` to configure room properties. Target: `here`, room name, or `#dbref`.

| Command | Description |
|---------|-------------|
| `+room` | Shows current room settings (area, hierarchy, resources, tags, etc.) |
| `+room/area here=\<code\>` | Assigns the room to an area and auto-assigns the next room number (e.g. NC -> NC01) |
| `+room/code here=\<fullcode\>` | Manually set room code (e.g. NC01). Use when you need a specific number. |
| `+room/hierarchy here=\<district\>,\<area\>` | Sets location display (e.g. Watson, Northside). Shown in room header and +where. |
| `+room/tag here=\<tag1\>,\<tag2\>` | Sets room tags (comma-separated). Tags help with searching and categorization. |
| `+room/tags here` | View current tags on the room. |

### Other +room options

- `+room/res here=\<number\>` -- Set resources (0-5)
- `+room/type here=\<type\>` -- Set room type (e.g. Beach Town, Bar)
- `+room/coords here=\<x\>,\<y\>` -- Set coordinates for area maps
- `+room/unfindable here=on` -- Hide room from +where (staff can still see)

## Quick Workflow

1. `dig Room Name = exit_in, exit_out` (or use `tunnel`)
2. `@desc here = Your description here.`
3. `+room/area here=NC` (or appropriate area code)
4. `+room/hierarchy here=District,Area`
5. `+room/tag here=bar,nightlife`
6. `+room/res here=3` (if applicable)
7. Add exits to other rooms with `@open` or `@link`

## See Also

- `+help +area`
- `+help +room`
- `+help +view`
