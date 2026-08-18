# Battle AI: what has been located

Found statically, with no emulator, by ranking functions on how many of the
100 matched unit-flag accessors they call. See `tools/callgraph.py`.

Confidence is marked per item. Addresses are verified; field *meanings* are
inferred from how the AI uses them and are not yet confirmed by running the game.

## The central function

`sub_080C32C0` — 5,350 bytes, reads 39 distinct unit flags, writes 1.

Signature (from Ghidra): `(int user, int target, u16 *ability, char flag)`.

Shape:

1. A gauntlet of eligibility checks, each bailing out through a common
   reject helper at `0x080C478C`.
2. A **92-case switch** on the ability's effect id, dispatching through a table
   at `0x080C3624`. All 92 targets are internal to the function, so this is one
   large switch rather than a table of handlers. 66 of the 92 ids have distinct
   code; the rest share.

This is the AI's ability evaluator: given a user, a target and an ability,
decide whether and how much the AI wants it. **This is the function to modify
for AI behaviour changes.**

## Concrete AI rules already readable

- **Cost check.** `sub_0812ED98(user, abilityId)` is compared against
  `*(u16 *)(user + 0x1C)`, and the ability is rejected when the resource is
  short. `user + 0x1C` is **MP**. *(confirmed, see the stat table below)*
- **Do not waste debuffs on the nearly dead.** When the ability table's byte
  `+0x19` equals 2, the AI reads the target's current and max HP (stats `0x13`
  and `0x14`, at `+0x18` and `+0x1A`) and **rejects the ability when current HP
  is below half of max**.

  Class 2 is the harmful status/debuff group: ability ids 13, 14 and 18 (Judge,
  Break, Blind) are class 2, while damage and healing abilities are class 1.
  So the rule reads as "do not bother inflicting a status effect on something
  already close to death, just kill it". 97 of 347 abilities are class 2.

  **Correction:** an earlier version of this document had this rule backwards,
  describing it as "only heal below 50%". The branch rejects when HP is *below*
  half, not above, and class 2 is not healing. Both were wrong.
- **Cost is class-modified.** `sub_0812ED98` reads ability property 2 as the
  base cost, then adjusts it by the unit's class from `sub_080CD50C`: class
  `0x04` doubles-then-halves via a shift, class `0x0A` rounds up and halves.
  A half-MP-cost class is exactly the sort of thing worth tuning.
- **Status gating.** Several checks call the matched flag getters
  (`sub_080CDB54`, `sub_080CDB6C`, `sub_080CD8FC`) on user or target and reject
  on certain states.
- **Self-targeting.** `if (user == target)` has its own rejection rules.

## Data tables

| What | Address | Notes |
|---|---|---|
| Ability data | `0x0855187C` | stride **0x1C** (28 bytes), roughly 344 usable entries; entry 0 is a null row |
| Effect dispatch | `0x080C3624` | 92 entries, all internal to `sub_080C32C0` |
| Secondary dispatch | `0x080C347C` | 8 entries, index `uVar7 - 4` |

Ability entry fields, inferred from the first rows and from AI usage:

| Offset | Guess | Basis |
|---|---|---|
| `+0x0B` | AP cost | values 40, 60, 80, 0, 90 |
| `+0x19` | ability class | AI treats `2` as heal-like; distribution is almost entirely 0/1/2 |
| `+0x1A` | accuracy | values 80, 65, 50, 100, 100 |

The remaining 24 bytes per entry are not yet identified.

## Unit struct: confirmed stat offsets

`sub_080C7EA4(unit, statId)` is a 69-entry jump table on the stat id. Each case
is a 4-byte stub that loads one field, so the mapping is exact:

| stat id | load | struct offset | meaning |
|---|---|---|---|
| `0x10` | `ldrb` | `+0x12` | byte stat |
| `0x11` | `ldrb` | `+0x13` | byte stat |
| `0x12` | `ldrb` | `+0x14` | byte stat |
| `0x13` | `ldrh` | **`+0x18`** | **current HP** |
| `0x14` | `ldrh` | **`+0x1A`** | **max HP** |
| `0x15` | `ldrh` | **`+0x1C`** | **current MP** (the field the cost check uses) |
| `0x16` | `ldrh` | `+0x1E` | max MP *(by symmetry)* |
| `0x17` | `ldrh` | `+0x20` | u16 stat |

The `0x13`/`0x14` pair being adjacent u16s at `+0x18`/`+0x1A`, with the AI
comparing one against half the other, is what makes current/max HP certain
rather than guessed. `+0x1C` then follows as MP because it is both the next
stat in the sequence and the field the ability-cost check reads.

This was established statically. No emulator was needed.

## Supporting primitives worth naming

- `sub_080C7EA4(unit, statId)` — stat getter. `0x13` and `0x14` behave as
  current and max HP.
- `sub_080CCD50(abilityId, propId)` — ability property query; the AI asks for
  properties `0x11`, `0x12`, `0x13`.
- `sub_0812ED98(user, abilityId)` — resource cost of an ability for a unit.
- `sub_08131C58` — 332 bytes: for each of 16 status flags, clears a matching
  capability when the flag is unset. Recomputes what a unit may do.
- `sub_08097298` — initialiser; writes 0 to every unit flag.

## Next steps

1. Decompile `sub_080C32C0` case by case; the switch makes it separable.
2. Name the ability table fields by cross-referencing entries against known
   in-game ability stats.
3. Decompile the remaining stat cases (69 in total) to finish the struct's
   numeric fields, the same way `0x13`-`0x15` were resolved.
4. A running game is still useful for sanity-checking behaviour changes, but it
   is no longer needed to read the struct.
