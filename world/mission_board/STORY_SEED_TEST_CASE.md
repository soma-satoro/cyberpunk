# Story Seed Test Case: Full Rewards (Faction Rep, Cash, Rep, Voucher, Item)

This document provides step-by-step commands to create and test a story seed with all reward types: faction rep, cash payout, general reputation, a voucher (containing a custom test item), and an item payout (gear from the equipment database in a voucher).

---

## Prerequisites

- Staff (Builder) permissions
- A Fixer character for grabbing the seed
- Arasaka faction must exist (or use another faction name)

---

## Step 1: Create the Voucher with Custom Test Item

Staff creates a voucher and adds a custom gear item that will be the "voucher payout":

```
+voucher/create Mission Reward Voucher
+voucher/add mission reward voucher=gear/Corpo Data Chip
```

Optionally set stats on the custom item (staff only):

```
+voucher/setstat mission reward voucher/1=value=500
+voucher/setstat mission reward voucher/1=description=Encrypted data chip from a corpo server
```

Note the voucher's dbref (e.g. `#12345`) -- you'll need it for the seed. Use `+vinfo mission reward voucher` or `look mission reward voucher` to see it, or check the object list.

---

## Step 2: Create the Item Payout Voucher (Gear from Equipment Database)

For an item from the equipment database, staff must first have it in inventory (purchase from chargen or a vendor), then add it to a voucher:

**Option A -- Staff has the item in inventory:** If staff already owns "Light Armorjack" (armor) or "Medtech Kit" (gear) from a prior purchase:

```
+voucher/create Item Reward
+voucher/add item reward=Light Armorjack
```
(Use the exact name as shown in your inventory.)

**Option B -- Staff creates custom armor (Light Armorjack):** Light Armorjack is armor, not gear:

```
+voucher/create Item Reward
+voucher/add item reward=armor/Light Armorjack
+voucher/setstat item reward/1=sp=4
+voucher/setstat item reward/1=ev=0
+voucher/setstat item reward/1=value=100
+voucher/setstat item reward/1=locations=Body
```

**Option C -- Staff creates custom gear (e.g. Medtech Kit):** For gear, use only name, description, weight, value, category:

```
+voucher/create Item Reward
+voucher/add item reward=gear/Medtech Kit
+voucher/setstat item reward/1=value=100
+voucher/setstat item reward/1=category=Medical
+voucher/setstat item reward/1=description=Standard field medical supplies
```

Note this voucher's dbref (e.g. `#12346`).

---

## Step 3: Place Vouchers in a Holding Location

Mission completion moves reward objects to the mission lead. The vouchers must exist and have a valid location. Either:

- **Drop them in the room** where you'll run the test, or  
- **Keep them in your inventory** -- they will be moved to the lead on completion.

For testing, keeping them in staff inventory is fine. Ensure they are **unlocked** so the completion logic can move them.

---

## Step 4: Create the Story Seed

Create the seed with max budget 3000 eb, 15 general rep, 5 Arasaka faction rep, and both reward vouchers:

```
mission/seed/create Full Reward Test=A data heist with multiple payouts/3000/15/Arasaka/5/voucher:#12345/item:#12346
```

Replace `12345` and `12346` with the actual dbrefs from Steps 1 and 2 (e.g. `voucher:#12345` or `voucher:12345`).

---

## Step 5: Verify the Seed

```
mission/seed 1
```

(or the seed's ID)

You should see:

- Max Budget: 3000 eb  
- Rep: 15, 5 Arasaka rep  
- Rewards: 1 vouchers, 1 items  

---

## Step 6: Fixer Grabs the Seed and Posts to General Mission Board

When a Fixer grabs a story seed, the mission is created and **automatically posted** to the general mission board. There is no separate "post" step.

**As a Fixer character:**

1. Browse available seeds:
```
mission/seeds
```

2. Grab the seed and create the mission (this posts it to the board):
```
mission/grab 1=Data Heist/Pick up the data and armor from the warehouse/2025-04-15/2500/12/Arasaka/5
```

Replace `1` with the seed ID. This creates a mission with:
- Player payout: 2500 eb (split among survivors)
- Fixer cut on completion: 500 eb (3000 - 2500)
- Rep: 12 general, 5 Arasaka

3. The mission is now visible on the general board. No further action is needed.

---

## Step 6b: Player Views and Accepts from General Mission Board

**As any player (non-Fixer):**

1. List missions on the general board:
```
mission
```

2. View mission details (use the ID from the list, e.g. 2):
```
mission 2
```
or
```
mission/info 2
```

3. Accept the mission (you become the lead):
```
mission/accept 2
```

4. Add companions (optional):
```
mission/add 2=CompanionName
```

---

## Step 7: Run the Mission Flow

1. Player accepts: `mission/accept 2`  
2. Add companions: `mission/add 2=CharacterName`  
3. Assign GM: `mission/gm 2=GMCharacterName`  
4. Run the scene.  
5. Complete (all survive): `mission/complete 2`  
   Or with casualties: `mission/complete 2=DeadCharacterName`  

---

## Step 8: Verify Payouts

- **Fixer:** 500 eb (3000 - 2500)  
- **Surviving players:** 2500 / number of survivors (e.g. 1250 each for 2 survivors)  
- **General rep:** 12 to each survivor  
- **Arasaka rep:** 5 to each survivor  
- **Lead receives:** Both vouchers (Corpo Data Chip + Light Armorjack) moved to their inventory  

---

## Command Reference Summary

| Step | Command |
|------|---------|
| Create voucher | `+voucher/create Mission Reward Voucher` |
| Add custom item | `+voucher/add mission reward voucher=gear/Corpo Data Chip` |
| Optional stats | `+voucher/setstat mission reward voucher/1=value=500` |
| Item voucher (from inventory) | `+voucher/create Item Reward` then `+voucher/add item reward=Light Armorjack` |
| Item voucher (staff custom) | `+voucher/add item reward=gear/Light Armorjack` + setstat |
| Create seed | `mission/seed/create Full Reward Test=A data heist/3000/15/Arasaka/5/voucher:#ID/item:#ID` |
| Add rewards to existing seed | `mission/seed/reward <#>=voucher:#ID,item:#ID` |
| Remove rewards by dbref | `mission/seed/reward <#>/remove=#ID,#ID` |
| Clear all rewards | `mission/seed/reward <#>/clear` |
| View seed | `mission/seed <#>` |
| List seeds | `mission/seeds` |
| Fixer grab (posts to board) | `mission/grab <seed#>=<name>/<desc>/<due>/<payout>/<rep>/<faction_rep>/<FactionName>` |
| List missions (general board) | `mission` |
| View mission details | `mission <#>` or `mission/info <#>` |
| Accept mission (become lead) | `mission/accept <#>` |
| Add companion | `mission/add <#>=<character>` |
| Complete | `mission/complete <#>` or `mission/complete <#>=<dead1>,<dead2>` |

---

## Equipment Database Lookup

To see available items for rewards:

```
equipdb armor
equipdb gear
```

- **Armor** (use `armor/Name` for custom): Light Armorjack, Medium Armorjack, Heavy Armorjack -- fields: name, description, weight, value, sp, ev, locations
- **Gear** (use `gear/Name` for custom): Medtech Kit, Stim, Antidote, Trauma Plate -- fields: name, description, weight, value, category
