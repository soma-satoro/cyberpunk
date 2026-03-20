# Voucher System Documentation

## Overview

The voucher system enables players to manage in-character (IC) objects that they are carrying. A **voucher** is a physical game object that represents one or more IC items. Multiple items may be combined onto a single voucher. Anything which is not another type of in-character item (weapons, armor, gear, vehicles, cyberware) can be represented by a voucher.

Vouchers can be picked up and dropped just like regular items using the standard `get` and `drop` commands. They appear in rooms and in your inventory.

---

## Core Concepts

### What is a Voucher?

- A **voucher** is an Evennia Object (typeclass: `typeclasses.vouchers.Voucher`) that holds a list of IC items
- Each item on a voucher has: `name`, `description`, `quantity`, `ic_location`, and `cloneable` (boolean)
- Vouchers are physical objects--they have a location (your inventory, a room, another character)
- You can refer to a voucher by: its **name** (if unique), its **dbref** (#12345), or its **alias** (if set)

### Item Structure

Each item stored on a voucher is a dictionary:

```python
{
    "name": "Medtech Kit",
    "description": "Standard field medical supplies",
    "quantity": 2,
    "ic_location": "backpack",  # Where you're carrying it IC
    "cloneable": False          # Can it be copied with +voucher/cloneitem?
}
```

---

## Commands Reference

### Creating and Adding Items

| Command | Usage | Description |
|---------|-------|-------------|
| `+voucher/create` | `+voucher/create [name]` | Create an empty voucher. Use a space before the name (e.g. `+voucher/create My Pouch`). No equals sign. |
| `+voucher/add` | `+voucher/add <voucher>=<name>[:<qty>][:cloneable]` | Add items to a voucher. Use `:cloneable` to mark copyable items. |

**Examples:**
```
+voucher/create
+voucher/create=My Pouch
+voucher/add my pouch=Medtech Kit:3
+voucher/add my pouch=Deck Program:1:cloneable
```

### Viewing Contents

| Command | Usage | Description |
|---------|-------|-------------|
| `+voucher/info` or `+vinfo` | `+voucher/info <voucher>` | Display voucher contents (sheet format) |
| `+voucher/info` | `+voucher/info <voucher>/<item#>` | Detailed info for a specific item |
| `+sheet` | `+sheet <voucher>` | Same as +voucher/info--shows voucher contents |
| `look` | `look <voucher>` | Look at a voucher to see its contents inline |

### Alias and Naming

| Command | Usage | Description |
|---------|-------|-------------|
| `+voucher/alias` | `+voucher/alias <voucher>=<alias>` | Set a shortcut alias (max 20 chars, letters/numbers/dashes/underscores only) |
| `+voucher/rename` | `+voucher/rename <voucher>=<new name>` | Rename the voucher (max 38 chars) |

### Concealment

| Command | Usage | Description |
|---------|-------|-------------|
| `+conceal` | `+conceal <voucher>` | Hide voucher from others when they view your inventory |
| `+unconceal` | `+unconceal <voucher>` | Make concealed voucher visible again |

### Locking

| Command | Usage | Description |
|---------|-------|-------------|
| `+voucher/lock` | `+voucher/lock <voucher>` | Lock voucher--only you can pick it up or modify it |
| `+voucher/unlock` | `+voucher/unlock <voucher>` | Unlock voucher |

**Important:** Lock vouchers before leaving them unattended. A locked voucher cannot be picked up by anyone except the person who locked it.

### IC Location and Ownership

| Command | Usage | Description |
|---------|-------|-------------|
| `+voucher/loc` | `+voucher/loc <voucher>/<item#>=<ic location>` | Set where you're carrying an item IC (max 20 chars) |
| `+voucher/chown` | `+voucher/chown <voucher>=<player>` | Set IC owner (for +owner lookup; use when giving/selling IC) |
| `+owner` | `+owner <voucher>` | Display the IC owner of a voucher |

### Using and Removing Items

| Command | Usage | Description |
|---------|-------|-------------|
| `+voucher/use` | `+voucher/use <voucher>/<item#>[:<qty>]` | "Use up" and remove items from the voucher |

### Moving and Reorganizing

| Command | Usage | Description |
|---------|-------|-------------|
| `+voucher/move` | `+voucher/move <voucher>/<item#>[:<qty>]=<newvoucher>` | Move item(s) from one voucher to another. Multiple item#s allowed. |
| `+voucher/join` | `+voucher/join <voucher1>=<voucher2>` | Merge all items from voucher2 into voucher1; voucher2 is destroyed |
| `+voucher/split` | `+voucher/split <voucher>/<item#>[:<qty>]` | Split item(s) into a new voucher in your inventory |
| `+voucher/cloneitem` | `+voucher/cloneitem <voucher>/<item#>[:<qty>]` | Copy cloneable items (e.g., deck programs, formulae) |

### Destruction

| Command | Usage | Description |
|---------|-------|-------------|
| `+voucher/nuke` | `+voucher/nuke <voucher>` | Destroy an **empty** voucher. Fails if it contains items. |

---

## Integration with Other Systems

### +inventory

The `+inventory` command displays a **Vouchers** section showing all vouchers you are carrying, with item count and lock status.

### +sheet

Using `+sheet <voucher>` (or `+sheet` with a voucher name as argument) displays the voucher's contents in the same format as `+voucher/info`. Works for vouchers in your inventory or in the room.

### get / drop

Vouchers are normal Evennia objects. Use `get <voucher>` and `drop <voucher>` to pick them up and put them down. Locked vouchers can only be picked up by the person who locked them.

### look

When you `look` at a voucher, its contents are displayed below the default description.

---

## Technical Implementation

### Files

| File | Purpose |
|------|---------|
| `typeclasses/vouchers.py` | Voucher typeclass--data model, `return_appearance`, `at_pre_get`, `format_sheet` |
| `commands/voucher_commands.py` | All +voucher/*, +conceal, +unconceal, +owner commands |
| `commands/default_cmdsets.py` | Registers CmdVoucher, CmdConceal, CmdOwner in CharacterCmdSet |
| `commands/character_commands.py` | CmdSheet checks for vouchers and displays `format_sheet()` |
| `commands/inventory_commands.py` | CmdInventory adds Vouchers section |
| `world/help_entries.py` | Help entries for voucher, voucher2, voucher3, voucher4, voucher5 |

### Voucher Attributes (db)

| Attribute | Type | Description |
|-----------|------|-------------|
| `voucher_items` | list of dicts | The items on the voucher |
| `concealed` | bool | Hidden from others' inventory view |
| `locked` | bool | Only locker can pick up/modify |
| `locked_by` | int | dbref of character who locked it |
| `ic_owner` | str | Character name for +owner display |
| `voucher_alias` | str | Custom alias (max 20 chars) |

### find_voucher()

The `find_voucher(caller, arg, location=None)` helper in `voucher_commands.py` locates a voucher by:
1. Searching caller's inventory (caller.contents)
2. Searching the room (caller.location.contents)
3. Fallback: `caller.search()` with typeclass filter

Matches by: dbref (#123), alias, or key (name).

---

## Workflow Examples

### Creating a Medtech Kit

```
+voucher/create=Medtech Kit
+voucher/add medtech kit=Trauma Plate:2
+voucher/add medtech kit=Stim:5
+voucher/add medtech kit=Antidote:3
+voucher/loc medtech kit/1=backpack
+voucher/loc medtech kit/2=vest pocket
+voucher/lock medtech kit
```

### Giving an Item to Another Player

```
+voucher/split my pouch/2:1
get new voucher
give new voucher to Bob
+voucher/chown new voucher=Bob
```

### Merging Two Pouches

```
+voucher/join main pouch=spare pouch
```

### Cloning a Deck Program

```
+voucher/add my deck=Killer:1:cloneable
+voucher/cloneitem my deck/1:3
```

---

## Limitations and Notes

1. **Concealment** applies when others view your inventory. Your own `+inventory` always shows all your vouchers.
2. **Locking** stores `locked_by` as the character's dbref. Only that character can pick up a locked voucher.
3. **+voucher/nuke** only works on empty vouchers. Remove or move all items first.
4. **Cloneable** items must be marked when adding: `+voucher/add voucher=Program:1:cloneable`
5. **IC owner** is separate from lock ownership--use `+voucher/chown` when transferring items IC.

---

## Origin

This system is adapted from the Shadowrun Denver server's voucher system, adapted for the Cyberpunk Red / Evennia codebase.
