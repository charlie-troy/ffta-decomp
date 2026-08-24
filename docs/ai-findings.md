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
| `+0x1A` | AI priority | higher = more likely; corrected from the earlier "accuracy" guess, see [ability-table.md](ability-table.md) |

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
| `0x16` | `ldrh` | `+0x1E` | **max MP**; restoration clamps current MP to this value before writing `+0x1C` |
| `0x17` | `ldrh` | `+0x20` | **Attack** |
| `0x18` | `ldrh` | `+0x22` | **Defense** |
| `0x19` | `ldrh` | `+0x24` | **Magic Power** |
| `0x1A` | `ldrh` | `+0x26` | **Resistance** |

The `0x13`/`0x14` pair being adjacent u16s at `+0x18`/`+0x1A`, with the AI
comparing one against half the other, is what makes current/max HP certain
rather than guessed. `+0x1C` then follows as MP because it is both the next
stat in the sequence and the field the ability-cost check reads.

The four combat names are joined through the retail total-stat helpers, not
assigned from ordering alone. `sub_080CA624`, `sub_080CA6B4`, `sub_080CA66C`,
and `sub_080CA6FC` add item properties 10, 11, 12, and 13 respectively to
unit `+0x20`, `+0x22`, `+0x24`, and `+0x26`; those item properties are the
independently mapped Attack, Defense, Magic Power, and Resistance fields.
The stat reads and all four equipment joins are covered by the emulator gate.

## The AI is randomised

`sub_08002804` is the game's random number generator, a textbook linear
congruential generator:

```c
u32 Rand(void)
{
    gRngState = gRngState * 1103515245 + 12345;
    return (gRngState & 0x7FFFFFFF) >> 16;
}
```

Those are the ANSI C reference constants. The state lives at **`0x030034B0`**
in IWRAM.

**43 of the 66 case bodies in the evaluator call it**, each pairing it with the
libgcc division helper at `0x08142950`, which is the `Rand() % n` idiom. So the
AI's per-effect scoring is deliberately noisy rather than deterministic, and
roughly two thirds of the effect types are affected.

Two consequences worth knowing:

- **Testing AI changes is awkward** without pinning the state. Freezing
  `0x030034B0` makes a battle reproducible, which is the fastest way to tell a
  behaviour change from a dice roll.
- **Removing the randomness is a mod in itself.** Making the AI play its best
  option every time is a plausible difficulty mode and needs no new logic.

`0x08142950` is libgcc's signed modulo (`__modsi3`), not game code, and should come from
building libgcc rather than being decompiled. It is the same category as
`sub_08142A94` (`__negdi2`).

## How AI priority is consumed

`sub_0813413C(unit, abilityId)` is the priority getter. For a real ability it
returns the ability table's `+0x1A`; for ability id 0 it falls back to a
**second table at `0x08521A14`, stride 0x34, priority byte at `+0x32`**. That
second table is a separate AI-tunable dataset and is not yet covered by
`tools/ability_table.py`.

Only two functions call it, `sub_080C1EB4` and `sub_080C2618`, both in the AI
region. `sub_080C2618` stores the value into a candidate record rather than
comparing it, so the AI builds a list of candidate actions each tagged with a
priority and chooses later.

**Direction verified, and it is the reverse of the published description.**
Both callers pass the byte to `sub_0812F1DC`, whose result decides survival, and
that predicate keeps an ability more often as the priority rises. Higher means
**more** likely. The derivation is in `docs/ability-table.md`.

The fallback table is bounded at **123 entries**: index 123 and 124 are all
zero and 125 onwards is unrelated data. Its priority byte spans the same 0-100
scale as the ability table, over 14 distinct values.

## Candidate-list model, confirmed by disassembly

The build-then-filter pipeline is confirmed by reading the two callers' bodies,
not just their call sites.

`sub_080C2618(record, unit, ..., abilityId, ...)` fills one candidate record:

- `+0x00` is the ability id (it is what gets passed to the priority getter as
  `abilityId`); `+0x02` is a second `u16` passed in.
- `sub_080C2314` fills `+0x04`–`+0x0a`, ending in a validity byte at `+0x0a`.
- when the record is valid (`+0x0a != 0`) the priority getter's byte is stored
  at **`+0x10`**, and a run of further checks (`sub_08096D7C`, `sub_08099544`,
  `sub_0812E4A8`, `sub_080CD944`, `sub_080C82B8`) can still invalidate it.

Its only caller (at `0x080C2816`) walks a table of 4-byte ability entries and
writes one record per entry into a list whose stride is `0x328` bytes
(`0xCA << 2`); `+0x324` of each record is a running count.

`sub_080C1EB4` is the filter: over a list of `u16` ability ids it fetches the
priority byte, runs the `sub_0812F1DC` predicate, and stores `0` back over any
entry that fails — removing it from the list. It skips the predicate for
entries that first pass a three-way `sub_08133970` check, so that check is an
exemption from the priority gate. The evaluator `sub_080C32C0` is the later
chooser: it is the only other caller of the predicate (`0x080C35A0`) and
re-applies the same gate while scoring.

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

> **Most of the original next steps are now done.** See [ability-table.md](ability-table.md)
> for the full ability layout, [unit-struct.md](unit-struct.md) for all 69 stat
> fields, and [roadmap.md](roadmap.md) for what remains. The items below are kept
> as a record of the original plan.

1. Decompile `sub_080C32C0` case by case; the switch makes it separable.
2. Name the ability table fields by cross-referencing entries against known
   in-game ability stats.
3. Decompile the remaining stat cases (69 in total) to finish the struct's
   numeric fields, the same way `0x13`-`0x15` were resolved.
4. A running game is still useful for sanity-checking behaviour changes, but it
   is no longer needed to read the struct.
