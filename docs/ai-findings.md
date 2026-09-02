# Battle AI: what has been located

Initially found statically by ranking functions on how many of the 100 matched
unit-flag accessors they call; see `tools/callgraph.py`. The central evaluator,
its 92-case dispatch, and the named unit fields are now also protected by
byte-matching and execution checks. Individual sections distinguish remaining
inference from behavior-backed findings.

## The central function

`sub_080C32C0` — 5,352 bytes, reads 39 distinct unit flags, writes 1.

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
| Ability data | `0x0855187C` | stride **0x1C** (28 bytes), 347 entries; entry 0 is a null row |
| Effect dispatch | `0x080C3624` | 92 entries, all internal to `sub_080C32C0` |
| Secondary dispatch | `0x080C347C` | 8 entries, index `uVar7 - 4` |

The full 28-byte layout is maintained in [ability-table.md](ability-table.md).
The three AI-specific fields are:

| Offset | Field | Basis |
|---|---|---|
| `+0x18` | AI condition | Special-case handling; 306/347 entries use the default |
| `+0x19` | AI behavior | Value 2 rejects targets below half HP; values span 0–3 |
| `+0x1A` | AI priority | Higher = more likely; 0 never and 100 always, confirmed by execution |

## Unit struct: confirmed stat offsets

`sub_080C7EA4(unit, statId)` is a 69-entry jump table on the stat id. Each case
is a 4-byte stub that loads one field, so the mapping is exact:

| stat id | load | struct offset | meaning |
|---|---|---|---|
| `0x00` | `ldr` | `+0x00` | **encoded-name text pointer** |
| `0x01` | `ldrb` | `+0x04` | **unit type** |
| `0x02` | `ldrb` | `+0x05` | **base job id** |
| `0x03` | `ldrb` | `+0x06` | **race id** |
| `0x04` | `ldrb` | `+0x07` | **active job id** |
| `0x05` | `ldrb` | `+0x08` | **secondary job id** |
| `0x06` | `ldrb` | `+0x09` | **level** |
| `0x07` | `ldrb` | `+0x0A` | **experience** |
| `0x08` | `ldrb` | `+0x0B` | **innate element id** |
| `0x0A..0x12` | `ldrb` | `+0x0C..+0x14` | **neutral + eight elemental resistances** |
| `0x13` | `ldrh` | **`+0x18`** | **current HP** |
| `0x14` | `ldrh` | **`+0x1A`** | **max HP** |
| `0x15` | `ldrh` | **`+0x1C`** | **current MP** (the field the cost check uses) |
| `0x16` | `ldrh` | `+0x1E` | **max MP**; restoration clamps current MP to this value before writing `+0x1C` |
| `0x17` | `ldrh` | `+0x20` | **Attack** |
| `0x18` | `ldrh` | `+0x22` | **Defense** |
| `0x19` | `ldrh` | `+0x24` | **Magic Power** |
| `0x1A` | `ldrh` | `+0x26` | **Resistance** |
| `0x1D..0x21` | `ldrh` | `+0x2A..+0x32` | **equipped item ids 0–4** |
| `0x22` | address | `+0x34` | **ability-state array** |
| `0x23` | `ldrsh` | `+0xD0` | **charge time (CT)** |
| `0x24` | `ldrsh` | `+0xD2` | **Speed** |
| `0x25` | `ldrsh` | `+0xD4` | **CT carry** |
| `0x26` | `ldrh` | `+0xD6` | **Judge Points (JP)** |
| `0x27` | address | `+0xD8` | **status-state array** |
| `0x28` | `ldrb` | `+0xD8` | **Zombie revival countdown** |
| `0x29` | `ldrb` | `+0xD9` | **Doom countdown** |
| `0x2A..0x32` | `ldrb` | `+0xDA..+0xE2` | **Haste through Charm durations** |
| `0x33` | `ldrb` | `+0xE3` | **Immobilize duration** |
| `0x34` | `ldrb` | `+0xE4` | **Disable duration** |
| `0x35` | `ldrb` | `+0xE5` | **Addle duration** |
| `0x36` | `ldrb` | `+0xE6` | **status link id** |
| `0x37` | `ldrb` | `+0xE7` | **recent target ids** (two packed 4-bit ids) |
| `0x39` | `ldrb` | `+0xF1` | **KOs inflicted** |
| `0x3a` | `ldrb` | `+0xF2` | **KOs suffered** |
| `0x3e..0x40` | `ldrb` | `+0xF6..+0xF8` | **tile X, tile Y, tile height** |
| `0x43` | `ldrb` | `+0xFB` | **battle list index** |
| `0x44` | address | `+0xFC` | **movement profile** |

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

The five named byte fields are also behavioral joins rather than ordering
guesses. `sub_080C8C24` always writes a selected job to `+0x07`, synchronizes
`+0x05` for ordinary units, and clears `+0x08` when it would duplicate the new
active job. The later A-ability path reads a nonzero `+0x08` as a secondary
job. `sub_080C9B8C` increments `+0x09`, clears `+0x0a`, and caps the pair at
level 50 / EXP 99; the award loop at `0x080A718E` adds earned EXP to `+0x0a`.
These transitions execute in check 4 of `tools/validate_ai.py`.

That check also executes the constructor join for unit type/race, the complete
job-to-unit elemental initialization, and the damage consumer. The element
order is neutral, Fire, Wind, Earth, Water, Ice, Lightning, Holy, Dark; codes
0–4 mean weak, normal, nullify, absorb, and resist. Fire damage under a fixed
RNG state produces `33, 24, 0, -19, 11` for those five states. The packed job
table's Wind and Earth slots happen to be equal in all retail jobs, which once
hid a field-map error. A distinct synthetic packing proves the accessor and
unit initializer read all eight slots independently; Earth uses slot 2.

Stat `0x08` completes the direct byte block as innate element id. The job
initializer copies property `0x0d` to unit `+0x0b` immediately before the
affinity array; Jelly executes as Fire (1). Across the table, the only nonzero
values belong to elemental monsters and use the same element ids as abilities.

The five trailing direct halfword loads are equipped item ids. The four retail
combat-total helpers iterate unit `+0x2a..+0x32`, pass every nonzero id to the
item property accessor, and add properties 10–13 to the matching combat base.
Check 4 verifies both the stat-id reads and those executed totals.

The first later battle-state group is now behavior-backed too. The turn tick
adds Speed and carry to CT, clears carry during charging, and normalizes an
over-threshold leader to CT 1000 while recording the common advance in carry.
The base-Speed helper adds signed item property 14. The
Totema selector crosses its boundary at 10 JP (Human command `0x50`, whose UI
label is `Totema`), and combo damage scales by `JP * 4 + 10`.

The next block is status state. Eleven named application handlers set
their matching live bit and `+0xda..+0xe2/+0xe5` counter; the reconciliation
routine pairs and clears those same counters. Checkmate additionally executes
as live Doom with count 3 at `+0xd9`, whose expiry path clears battle statuses.
Aim: Legs/Aim: Arm execute as Immobilize/Disable count 3, and independent
movement/ability-usability readers distinguish their roles. Cover independently
copies the covered unit's `+0x104` id to `+0xe6`; linked-state consumers compare
it against other unit ids. Zombie revival and recent-target history close the
other two bytes in this block. The paired KO result path then names
`+0xf1/+0xf2` as KOs inflicted/suffered. Movement and range consumers name
`+0xf6..+0xf8` as tile X/Y/height, while battle-object insertion names `+0xfb`
as its list index. Removal-result execution names `+0xf3..+0xf5` as the
other/Parley/Oust counters; the Parley count also contributes to the shared
purge hit formula. Placement paths copy live X/Y into saved position
`+0xf9/+0xfa`. Finally, UI renderers identify stat `0x00` as the encoded-name
text pointer, while bounded initializers/consumers identify `+0x34` as ability
state and `+0xfc` as the movement profile. All 69 stat ids are now named: 63
load cases and six address returns.

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
**job table at `0x08521A14`, stride 0x34, priority byte at `+0x32`**. It is
editable through `tools/ability_table.py dump-units/apply-units`; the current
layout and evidence live in [job-table.md](job-table.md).

Only two functions call it, `sub_080C1EB4` and `sub_080C2618`, both in the AI
region. `sub_080C2618` stores the value into a candidate record rather than
comparing it, so the AI builds a list of candidate actions each tagged with a
priority and chooses later.

**Direction verified, and it is the reverse of the published description.**
Both callers pass the byte to `sub_0812F1DC`, whose result decides survival, and
that predicate keeps an ability more often as the priority rises. Higher means
**more** likely. The derivation is in `docs/ability-table.md`.

The table is bounded at **116 entries**. The earlier 123-entry estimate was a
false plausibility bound that included unrelated following data. Its priority
byte spans the same 0-100 scale as the ability table, over 14 distinct values.

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
3. Continue joining unnamed live-status bits to unique action restrictions,
   per-turn behavior, or named ability descriptors; the 69-id stat layout is
   complete.
4. A running game is still useful for sanity-checking behaviour changes, but it
   is no longer needed to read the struct.
