# Elflines Online Setup Guide

Elflines Online (ELO) is the MMO within the Cyberpunk universe--edgerunners log in via Braindance to play as elves in the Elflands.

## Staff Setup

1. **Create the ELO Lobby** (Builder+)
   ```
   +elosetup
   ```
   This creates the "ELO Lobby" room. Players will arrive here when they `+elo/login`.

2. **Build the Elflands Grid**
   - Create more rooms using typeclass `typeclasses.elflines_rooms.ElflinesRoom`
   - Use `dig`, `tunnel`, or `@open` to connect rooms with exits
   - Example: `tunnel north = Valley of Ancients` then `@dig Valley of Ancients` with typeclass overridden to ElflinesRoom

   For custom typeclass when creating:
   - `create_object("typeclasses.elflines_rooms.ElflinesRoom", key="Valley of Ancients", location=...)

3. **Tag ELO Rooms**
   Rooms using `ElflinesRoom` are automatically tagged as ELO. Characters in these rooms show in `+elo/who`.

## Player Usage

- `+elo` -- Status
- `+elo/sheet` -- Create/view ELO character (50 STAT, 60 skills, 200gp)
- `+elo/login` -- Enter Elflands
- `+elo/logout` -- Return to meat world
- `+elo/who` -- Who's in the Elflands
- `+elfline/create/join/leave/invite/kick` -- Guild management

## Miasma (Future)

The PDF describes Miasma: outside major cities and camps, it enables PvP and suspends healing. Set `room.db.is_miasma = True` on ELO rooms for PvP zones. The Lobby is safe (`is_miasma = False`).
