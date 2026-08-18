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

- **Cost check.** `func_0x0812ED98(user, abilityId)` is compared against
  `*(u16 *)(user + 0x1C)`, and the ability is rejected when the resource is
  short. `user + 0x1C` is very likely current MP. *(high confidence on the
  mechanism, medium on which resource)*
- **Heal-only-when-hurt.** When the ability table's byte `+0x19` equals 2, the
  AI compares `stat(target, 0x13)` against `stat(target, 0x14) >> 1` and rejects
  unless the first is below half the second. That is the classic "only heal
  below 50%" rule, which makes `+0x19 == 2` a healing/support class and
  `0x13`/`0x14` current and max HP. *(high confidence)*
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
3. Confirm `0x13`/`0x14` and `user + 0x1C` with mGBA watchpoints. This is the
   one step that needs the game running.
