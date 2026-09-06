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

#### RNG sites inside the target sort, measured in a live battle

`tools/measure_sort_rng.py` breaks at `sub_080C2940`'s entry in the frozen-seed
snowball battle, optionally engineers an exact score tie in the live arena
(count 3, cand1 tied with cand0), breaks at the caller's return
(`0x080C0782`), and counts exact LCG steps between the two `gRngState`
values. Because the LCG is a known 32-bit recurrence, the draw count is exact,
not statistical. Results:

| run | draws inside one sort call | meaning |
|---|---|---|
| retail, no tie | 1 | baseline draw: the kind-1 behaviour coin at `0x080C2A22` |
| retail, tie | 3 | baseline + 2: the tie window runs twice |
| ties pinned (`deterministic_ties`), tie | 1 | tie costs nothing; exit state == retail control |
| `action_selection: first`, no tie | 0 | entry state == exit state |
| `action_selection: first` + `deterministic_ties`, tie | 0 | entry state == exit state |

The sites, now fully attributed:

- `0x080C29BE..0x080C29C0` — the **walk roll branch**. Before picking targets,
  the AI picks which behaviour slot to act on: the slot list (count at
  `arg0+0x527e`, kind bytes at `arg0+0x5276+i`) is walked from index 0, and
  every non-last slot survives only on `Rand() % 101 > 50` (the roll itself
  sits at `0x080C29C0`; the `bge` at `0x080C29BE` skips it for the last slot).
  The selected slot's kind (0-7) dispatches through a jump table at
  `0x080C29FC` (reached via `mov pc` at `0x080C29EC`).
- `0x080C2A22` — the **kind-1 behaviour coin**: `Rand() % 101 <= 50` sets
  flag 0x80, else 0x81. A Rand() breakpoint at the live sort (frozen-seed
  snowball battle) catches the baseline draw here (`lr=0x080C2A27`), and
  NOPing exactly this call with everything else retail drops the battle's
  draw count to 0 — causal proof that this coin, not the walk roll, is the
  baseline draw in that battle (its actor has a one-slot list, so the walk
  roll never fires there).
- `0x080C2A42` — the **kind-2 behaviour coin**: the same shape with flags
  0x80/0x82.
- `0x080C2C68` — a `Rand() % n` roll feeding a BST insert (setter
  `0x080C7AB4`: key at node+0, unit pointer at node+4, `bge` goes right). The
  block at `0x080C2C2E` enumerates the record's target units and inserts each
  with key `stat(unit, 0x13)` (current HP) when `stat 0x13 <= maxHP/3`
  (`__divsi3` at `0x08142AB0` divides stat 0x14 by 3), else with the random
  key `Rand() % 0x201 + 0x10000` — healthy targets are effectively shuffled
  in insertion order. This is the **target-enumeration weighted roll**, part
  of the record-walk **case 7** regime (second jump table at 0x080C2AC4,
  keyed by `flag & 0x7f`).
- `0x080C2E9E` — the mode=0 order gate (pinned by `deterministic_ties`).
- `0x080C2F7E` — the mode=1 tie roll (pinned by `deterministic_ties`). The
  live measurement shows it executing **twice** per engineered tie (+2 draws
  vs control), consistent with the selection sort comparing the tied pair
  twice; the patched ROM removes both.

The full dispatch is two-stage: slot kind (0-7) through the first table at
0x080C29FC sets a flag at `[sp,#0x1c]` — kinds 1 and 2 draw their coin and
set 0x80/0x81/0x82, kind 7 sets flag 0 with no draw, the others set constants
(0x3, 0x4, 0x5, 0) — and the record walk then dispatches `flag & 0x7f`
through the second table at 0x080C2AC4. Case 0 (flag 0x80 or 0) is the
standard record walk the candidate arena captures; the HP-weighted roll sits
in case 7 — and case 7 is the **mode=0 regime**: its caller (`0x080C078A`)
passes `r1=0x87` directly, skipping the slot walk (`cmp r1, #8; bne` at the
top) and dispatching straight into the weighted enumeration. A live census
confirms it: one mode=0 call in the snowball battle consumes exactly 3 draws
(one enumeration roll per healthy-target record), while forcing the mode=1
actor's slot kind byte to 7 still yields flag 0 (case 0, byte-identical
arena, zero draws) because the walk re-derives the flag from the kind
handlers. `deterministic_ties` NOPs the enumeration branch (0x080C2C58), so
every target uses the HP key and mode=0 full ties break by ascending current
HP instead of a random enumeration order.

So `deterministic_ties` removes every target-*ordering* draw, and the
`action_selection: first` control (`tools/ai_action.py`) removes the
action-selection draws: the walk branch becomes unconditional (slot 0 always
processed) and both behaviour coins become `movs r0, #0` + NOP. In the live
battle that alone takes the sort from 1 draw to 0, and combined with
`deterministic_ties` an engineered tie also costs nothing.

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

## Candidate-list model, confirmed by disassembly and execution

The build-then-filter pipeline is confirmed by reading the two callers' bodies,
not just their call sites.

`sub_080C2618(record, unit, ..., abilityId, ...)` fills one candidate record:

- `+0x00` is the ability id (it is what gets passed to the priority getter as
  `abilityId`); `+0x02` is a second `u16` passed in.
- `sub_080C2314` fills `+0x04`–`+0x0a`, ending in a validity byte at `+0x0a`.
- when the record is valid (`+0x0a != 0`) the priority getter's byte is stored
  at **`+0x10`**, and a run of further checks (`sub_08096D7C`, `sub_08099544`,
  `sub_0812E4A8`, `sub_080CD944`, `sub_080C82B8`) can still invalidate it.

Its caller (at `0x080C2816`) is the **arena builder** `sub_080C26EC`, which
itself is called twice by the two-state fill machine `sub_080C286C` (the
only writer of the AI struct's arenas), which the turn sequencer invokes
once per frame through the zero-extend thunk `0x080C47FC` at `0x080C0752`.
The builder walks a table of 4-byte **pointers to
0x90-stride action entries** and writes one record per entry into a list
whose stride is `0x328` bytes (`0xCA << 2`); `+0x324` of each record is a
running count. In the live capture the four record pointers are consecutive
(`0x020225EC + 0x90*k`), and each entry's first word is a distinct target
unit pointer (current HP 10/16/8/18) — the records are **per-target action
entries** for the actor's chosen action, one per target, not per ability.
The record walk's BST orders these entries: case 0 keys by the entry's
target's current HP (in-vivo keys 10/16/8/18), case 7 (mode=0) randomizes
the key for healthy targets.

### The fill pipeline (call chain, all traced)

The candidate arenas are filled incrementally by a two-state machine, one
batch per rendered frame:

| function | role |
| --- | --- |
| `0x080C0752` | sequencer call site (`bl 0x080C47FC`), one batch per frame |
| `0x080C47FC` | thunk: `bl 0x080C286C`, zero-extend the u8 result |
| `sub_080C286C` | fill machine: dispatches on the **phase byte `[ai+0x5280]`** (0 → mode=1 arena at `ai+0x2968`, 1 → mode=0 arena at `ai+0x5c`); passes and persists the **resume index `[ai+0x527f]`**; gates on pass counter `[ai+0x5a]` vs cap `[ai+0x58]` |
| `sub_080C26EC` | arena builder: walks entries starting at the resume index and appends candidates via `sub_080C2618`; also receives `stat(unit, 6)` (used in the 0x94/0xD3 special-ability resolution) and the selected slot `[ai+0x56]` |
| `sub_080C2618` | fills one 20-byte candidate (calls `sub_080C2314` at `0x080C266E`) |

The builder's byte return is the next resume index, or `0xFF` when the
action-entry table (`ai+0x2908` entries) is exhausted — that retires the
current arena: state 0 then resets the resume index and flips the phase
byte to 1; state 1 resets the index, increments the pass counter
`[ai+0x5a]`, and flips the phase back to 0. The wrapper itself always
returns 1 (the sequencer yields a frame per batch); the gate is at its
head — when the pass counter reaches the cap `[ai+0x58]` it returns 0 and
the sequencer proceeds straight to the two sort calls. So **one full cycle
fills both arenas to entry-table exhaustion**, and the sorts run on
complete arenas: the stable capture counts (4 records mode=1 / 3 mode=0)
reflect the actor's action entries and the per-regime filters, not a
truncated fill. Executed confirmation (`tools/trace_fill.py`, evidence
`outputs/mgba-snowball/fill-trace.json`): breakpointing the machine entry
in the live battle shows the resume index marching per batch (mode=1
arena: batches at resume 0x00–0x04 then retirement; mode=0 arena: resume
0x00–0x04 then retirement), the phase byte flipping 0→1→0 across the
two arenas, the pass counter incrementing to the cap (1/1), and both
sorts then running on complete arenas — the same 4-record mode=1 and
3-record mode=0 snapshots as every capture. The geometry resolves
entirely with the arena-setup stage (below): the arenas' records are
**pre-created by `sub_080C1B8C`** (which sets the count halfword at
`arena+0x2908` to the accepted record count), and the builder's resume
index walks those existing 0x328-stride record slots (`arg0 + 0x328*k`)
with the count halfword as its bound; the final batch of each phase is
the retirement call (`resume == count` → `0xFF`). All 8 records exist
across the two arenas (4 + 4); what differs is candidate-level
acceptance — mode=0's fourth record got no valid candidate from
`sub_080C2618` (its 20-byte block stayed zero), which is why captures
show 3 live mode=0 records. The struct is the same AI struct the
sort uses (literals `0x2968`, `0x5270`, `0x527f`), and the sequencer
memsets 0x5684 bytes of it after the picks (`0x080C07B0` → `0x080C480C`).

An earlier session note claimed the score producer had **no caller** — that
was a broken scan (a halfword-mask bug skipped every odd-halfword BL pair);
the chain above is complete and each link is verified by a decoded call
site.

### The pick stage (sorted arenas -> sequencer outputs)

After the two sorts, the sequencer extracts the results with a matched
pair of pick helpers, each a count-driven word copy of the sorted arenas'
record heads:

| function | count read | copies from | result |
| --- | --- | --- | --- |
| `sub_080C486C` | u16 `ai+0x2964` (mode=0 limit) | mode=0 arena head `ai+0x5c`, word per 0x328 record | `ctx+8`, count at `ctx+0x72` |
| `sub_080C4830` | u16 `ai+0x5270` (mode=1 limit) | mode=1 arena head `ai+0x2968`, word per 0x328 record | `ctx+0x3c`, count at `ctx+0x70` |

(`ctx` = the sequencer context, `r7` — **not** the AI struct; `[ctx]`
holds the AI pointer.) Executed confirmation (`tools/trace_pick.py`,
evidence `outputs/mgba-snowball/pick-trace.json`): the count fields read
4/4 before and after the sorts (they are the arena initializer's record
counts — see the arena-setup section) and `ctx+0x70/0x72` receive 4/4,
so the copies include records whose candidates were all rejected:
mode=0's list is the 3 live heads plus `0x20223ac`, a record whose
20-byte candidate block stayed zero. Both lists are 0x90-stride
consecutive, revealing the actor's **8-entry action-entry table**
(`0x20223ac + 0x90k`): entries 0–3 feed the mode=0 regime, entries 4–7
feed mode=1. The captured heads reconcile exactly with the standing
arena captures (mode=1: `0x202279c/0x270c/0x267c/0x25ec` = the
`#279c/#270c/#267c/#25ec` records).

### The chooser: sequencer phase 3 (`0x080C07C8`) picks the action

The AI turn's decision point is sequencer phase 3. The whole AI turn is a
**14-phase state machine**: head `0x080C045C`, phase index u16 at
`ctx+0x54F4`, word jump table at `0x080C048C` (the phase helper
`0x080C1260` yields one frame per call; `0x080C1248` pops a **phase
stack** — counter at `ctx+0x54F6`, array at `ctx+0x54F8` — so the
sequencer supports sub-sequences). The AI phases:

| phase | entry | role |
| --- | --- | --- |
| 0 | `0x080C0720` | AI setup (`bl 0x080C47A8`), phase 1 |
| 1 | `0x080C0750` | fill batch per frame (`bl 0x080C47FC`), phase 2 when done |
| 2 | `0x080C0770` | sorts + picks + AI-struct reset, phase 3 |
| 3 | `0x080C07C8` | **the chooser** — see below |
| 4 | `0x080C09EC` | copy the decision struct to the object at `ctx[0]`, free the two ctx buffers |
| 5 | `0x080C0A28` | post-decision state updates; when done, `0x080C0AE2` points `ctx[0]` at the AI object again |

### The full turn march and the pre-AI phases (live-traced)

`tools/trace_turn_march.py` breaks at the dispatcher `0x080C045C` every
frame of the frozen-seed enemy turn and logs the phase index, the
`0x54AF` flag byte, and the actor's live vs saved tile
(`outputs/mgba-snowball/turn-march.json`). The complete march of this
enemy turn is
`9 → 10×43 → 0 → 1×11 → 2 → 3 → 5 → [3,5]×3 → 4×8 → 8`. The actor's
**canonical tile (`unit+0xF6/+0xF7`) is frozen during the whole turn**
(write-watch across phases 9→7: zero writes) — the snowball throw
reaches its target from where the unit stands, so this battle never
walks — and at phase 8 it is overwritten once. The rows resolve the
whole phase set:

| phase | entry | role (live/static) |
| --- | --- | --- |
| 9 | `0x080C05FC` | allocate the 0x100-byte **movement grid** at `ctx+0x54EC`, zero it and the `ctx+0x54F0/0x54F1` cell counters, → 10 |
| 10 | `0x080C0644` | **fill the 16×16 movement grid** `[y*16+x]` over several frames (5 cells per frame via `0x080C1260` yield — the observed ~43-frame residence is the 256-cell scan) using the terrain helpers `0x08099FB0` (mark 2) and `0x08099F58` (mark 1, arg 0xff), with the unit-class gate `0x0812F0E4` OR-ing bit 0x80 for its own reachable cells; phase-stack pop (`0x080C1248`) when y>15 |
| 0–5 | (above) | AI plan, choose, execute |
| 8 | `0x080C1068` | end-of-turn restore/commit. Head (`0x1068–0x108C`) writes `ctx+0x54CA/0x54CB` back onto the unit tile and `ctx+0x54C8` onto `unit+0x1C`, saving the *old* tile into `r6/r8` → `ctx+0x54B4/0x54B5`; because the queued `ctx+0x54CA/0x54CB` equals the unit tile at turn start (the turn-starter queued it), that strb pair is a no-op refresh. The canonical tile's *actual* change this turn came from the 9-record sync loop `0x0809F850` (live-call-attributed; see the sync-area note below). Conditional tails on `0x54AF`/`0x54BE` handle knockback/CT bookkeeping (`0x080C11E0` has a second tile-commit pair for the displaced branch) |

Phases 11–13 form the **deferred-displacement route**, reached when the
init's `0x080C95A8(0xd)`-nonzero branch (global byte `0x0200203D`) seeds
phase 0xB. Phase 11 (`0x080C04C4`) tells the shared **placement/move
object at global `0x020158B0`** (0xAC bytes; mode halfword 2 at
`+0x64`, sub-API `0x080C7078`) about the queued target value at
`ctx+0x54CC`; phase 12 (`0x080C04E0`) polls it (`0x080C7638`) until
done, then unpacks the result vector stored **packed** at
`ctx+0x54D0..0x54DC` (low/high nibbles) into the working coordinate
fields `ctx+0x54B4/0x54B5/0x54BA/0x54C2`, appends a per-call result byte
into the `ctx+0x54E4` array, and sets phase 13; phase 13
(`0x080C10EE`) returns 0 to end the sequence. This is the forced-
movement / knockback-style path — distinct from the phase-9/10 movement-
range grid. Its queued input fields (`ctx+0x54CC`, the packed
`ctx+0x54D0..0x54DC`) are written by code outside the sequencer (no ROM
literal addresses them; the writer computes the ctx pointer, so it was
not located by a literal scan). Not exercised by the (stationary,
ranged) traced turn. The initial phase is **9**
for the traced actor (the init path through `0x080C03C2`); the 0xB seed
belongs to the other init branch (`0x080C95A8(0xd)` nonzero) — the older
"phase 0xB for AI units" note over-generalized.

Significance for STRAT9.3 (movement/resource policy): the movement
*range grid* is computed in phases 9–10 **before** the AI plan runs in
phase 0, and phase 3 hands the grid pointer to the decision builder
`0x080C01D0` (`[sp+0xc]` at `0x080C0998`) — reachability is available at
choose time. The tile-write / walk-site itself is never exercised in this
battle (no walking), so that site remains the concrete STRAT9.3 target.

#### The canonical tile is a phase-8-synced copy; live position lives in a snapshot area

A watch on the acting unit's canonical tile (`unit+0xF6/+0xF7`) during
the whole AI turn fires **exactly once, at phase 8** — no movement code
writes it mid-turn. The write is the **unit-record sync loop
`0x0809F850`** (live-call-attributed with `tools/scratch_copy_sync.py`,
`outputs/mgba-snowball/copy-sync.json`; sequence probe
`tools/scratch_phase8_seq.py`; combined watch+sync ordering probe
`tools/scratch_watch_sync.py`): for each of the 9 units, in the
container's pointer-array order (`obj+0xD6C[i]`, obj from `0x08022840`),
it calls the IWRAM memcpy veneer (`bl 0x08142250`, `bx r3`,
r3=`[0x0836D4BC]`) with `r0 = [[obj+0xD6C[i]]]` (the canonical unit
record `0x02002FC4+0x108·k`) as **dst** and `r1 = obj+4+0x108·i`
(the live snapshot slot `0x020159E8+0x108·i`, same object's parallel
array) as **src**, length 0x108. So phase 8 **restores each canonical
record from its live slot** — for this actor the slot held (6,5) while
the canonical had (6,7) (stale from its previous phase-8), and the
restore is what made the canonical tile visibly change. For every other
unit canonical == live slot already. This is why the earlier march probe
read the tile as constant: canonical really does not move until the
actor's own phase 8.

The **live record array at `0x020159E8`** (9 × 0x108) is the first
9×0x108 bytes of the battle container object (`obj = 0x020159E4`, from
`0x08022840`; the record slots live at `obj+4+0x108·i`) — this is where
position state actually updates during play. Write-watching the actor's
slot tile (`0x02015EFE`) caught four stop contexts this turn, all in
phase-2/phase-8 container-refresh code:

- **phase 2** (action binding): stop inside `0x080BDBAC`, a thin wrapper
  that zeroes a 0x4504-byte region (`bl 0x814224C` at `0x080BDBB4`, size
  `r1=0x4504`) — a per-turn reset of a ctx/unit region that contains the
  record slots.
- **phase 8** (×3): stops inside `0x0809DE94` — the container **refresh
  helper** that 0x0809F850 calls in its prologue: it zeroes `[obj,
  obj+0xE1C)` and then bubble-sorts the `obj+0xD6C` pointer list by each
  unit's `+0x104` byte (the placement/order key, swapping `obj+0xD6C[i]`
  elements) — twice, and once inside `0x08121EB7` (battle-flow region
  `0x08121Exx`, the family that also drives entry/unit spawn at
  `0x08124CE8`).

The phase-2 stop's containing function is `0x080BDA30`, a **selection
sort of coordinate-pair entries by Manhattan distance from a reference
point** (`|x-rx|+|y-ry|`, 3-way 4-byte swaps via `0x081443FC`), i.e. a
nearest-to-position ordering — the natural shape of an approach /
destination chooser. It (and the neighboring `0x080BDBC4`, which does
grid-style `x*16+y` indexing) has **no direct `bl` callers and no
pointer-table entry** — it is reached by computed dispatch, consistent
with the placement/move object at global `0x020158B0` (sub-API
`0x080C7078`) that phase 11 drives. That sub-API is a mode state machine
on the object's `+0x64` mode halfword (jump table `0x080C7098`, modes
0–3 → `0x080C70AC`/`0x080C70BA`/`0x080C70D8`/`0x080C7100`, each
advancing the mode) — the placement job steps.

The container-refresh helper family is now fully named: `0x0809DE94`
zeroes `[obj, obj+0xE1C)` and bubble-sorts the `obj+0xD6C` pointer list
by each unit's `+0x104` byte; `0x0809F78C` calls it then gathers the
first-n `obj+0xD6C` pointers into a caller array while zeroing each
record's `+0xD4/+0xD8` (turn-order actor collection); `0x0809F850`
calls it then runs the record-restore copies. The phase-8 watch stops
with `lr=0x0809DEB1` were the prologues of `0x0809F850` and
`0x0809F78C`.

Those four stop regions are the concrete **STRAT9.3 movement-commit
surface** to decode next: when a battle actually walks an AI unit, the
step/destination writes should land in this record array through one of
those helpers, and the canonical tile only catches up at the unit's own
phase 8. This frozen battle exercises only the ranged no-walk path.

**Tooling note.** mGBA write watchpoints in this build behave as
**one-shot**: the first write to the watched range stops the CPU and the
watchpoint is consumed — re-arm (`Z2`) after each event to keep watching
(see `tools/scratch_watch_sync.py`). Watch stops land **several
instructions late** (the PC/registers read at the stop can be mid-way
through a later call in the same region — e.g. the phase-8 slot events
surfaced inside `0x0809DE94`/`0x08121E..`, and stop PCs sit inside
IWRAM-copy routines like `0x03005F08` ↔ ROM `0x08A38ABC`,
byte-matched), so attribute the *region* from the return address but pin
exact write instructions by breaking at ROM call sites or single-
stepping. This reconciles several earlier single-event captures (e.g.
the old walk-control run) whose register snapshots looked incoherent.

Phase 3 walks the ctx's **shadow copies of the sorted arenas** — base
`ctx+0x74 + 0x290C*regime` (`0x290C = 13 records + the count field;
populated by the phase-2 wrapper from the AI struct before the reset),
with `ctx+0x54AC` = regime, `ctx+0x54AD` = candidate index, `ctx+0x54AE`
= record index. For each record's candidates it calls the validity gate
`0x080C32C0(caster, target, candidate, flagByte)` and then applies a
**regime-dependent sign check on the candidate's impact score**
(candidate +0x0C, read through the same `0x84` offset the code uses): the
regime-0 branch accepts only **negative** scores (`blt`), the regime-1
branch only **positive** (`bgt`). The **first candidate passing both**
wins: the decision builder `0x080C01D0` fills the 0x21C-byte
decision struct at `ctx+0x5290` and returns the action handler, stored at
`ctx+0x528C`; phase 4 then copies the struct to the turn object at
`ctx[0]` and the AI phase ends. If no candidate is accepted anywhere, the
shared tail `0x080C1222` memsets the decision area (0x21C bytes at
`ctx+0x5290`), sets phase 5, and the turn ends in passivity.

**Score-value audit (STRAT9.2 close-out, negative result).** A full
read-scan of phase 3 (`0x080C07C8`–`0x080C0A28`) and the decision
builder (`0x080C01D0`) shows the candidate's impact score at `+0x0C` is
read in exactly two places in the chooser — the two regime sign checks
(`ldrsh` at `0x080C0894` with the `blt`, and at `0x080C08DC` with the
`bgt`) — and by no other code in the choose or decide path; the per-rule
gate handlers re-check only its sign as well. The score's magnitude has
no downstream consumer, so a profile control over score magnitude is
structurally impossible without ROM changes. The shipped levers
(`ai_priority` ordering, pool polarity, deterministic rolls) are
therefore the complete control surface; STRAT9.2 is closed on this
evidence.

The validity gate rejects a candidate when: effect flags `+0x0B` bits 0/1
are set (both bail through the shared return-0 tail `0x080C478C`); ability
== 265 without both `0x080C8240`/`0x080C8260` checks; flag-byte bit 7 set
and ability not in category 0x13 (`0x080CCD50`); flag-byte bit 7 clear
and `0x812ED98(a, ability) > [a+0x1C]` (an MP/HP-cost style check);
ability 0 (the job-fallback operand used by every candidate in this
battle) and the caster-vs-target special checks; a reacting caster with a
negative score; ability property `+0x19 == 2` with the target's 0x13/0x14
meters unequal (a full-ness gate, e.g. for heal-type effects); and more
beyond `0x080C3400`.

### Inside the validity gate `0x080C32C0`

Structure beyond `0x080C3400`: after the full-ness gate the code reads an
**element/type value** via `0x812E6A4(target)` (halved if the caster's
`0x812F0E4` class check fires) and dispatches an **8-case switch** (table
`0x080C347C`): case 0 → `0x080C349C` (category-0x1B immunity → reject),
case 1 → `0x080C34B2` (ability must be nonzero), case 2 → `0x080C34BE`
(breakable-object checks via `0x812F0D8`/`0x812EE98`), cases 3/4/6 →
`0x080C350E` (`0x812EED0` element check with a case-7 refinement and the
same halving arithmetic), case 5 → `0x080C34F8` (reads the *other* arena's
slots via `0x812F0D8`+`0x812EE98`), case 7 → `0x080C3546` (category 0x1A
+ `0x812ED98` cost vs the target's `+0x15` meter). Repeated `asrs r7,#1`
through the cases halve an effect-strength intermediate on resist-like
conditions. Then a **per-rule validation loop** (`0x080C35BE`): for each
rule id (u16 at `cand+4+2i`, count at `cand+0xA`, ids 1..0x5C) it checks
`0x080CD8FC(caster)` (caster status → reject), looks the rule up via
`0x8133A58(target, rule)`, re-reads it after `0x080CDD88` state toggles,
and dispatches per rule through a **92-entry table at `0x080C3624`**;
`0x080C477A` advances to the next rule, `0x080C478C` is the reject tail.
A final `0x0812F1DC` check plus a loop over the candidate's rule
meters (`cand+0xA`-bounded) complete the validation; the observed return
is r0=1 on accept, 0 on reject (the per-case score intermediate in r7 is
not the return value).

Executed attribution (`tools/trace_gate.py`, frozen RNG, facing state):
**every candidate passes the gate** — all four stops show r0=1 (scores
+76/+76/+76 in regime 0, +61 in regime 1). The regime-0 trio is rejected
by the post-gate **sign check**, not the gate: +76 is not negative.
Consequence: the two arenas are two **action polarity classes** — the
mode=0 regime (sort arg `0x87`, bit 7 set) handles negative-scored
actions, the mode=1 regime positive-scored ones. In this battle every
action scores positive, so only the mode=1 arena can act; the
`deterministic-ties`/tie-profile controls in that arena therefore decide
the turn, while a negative-score producer (e.g. a post-condition
penalty) would surface through mode=0.

### Rule 0x26 (recovery) and the causal pool flip

In the 92-entry per-rule table, rule **0x26** (recovery) dispatches to
`0x080C3E7A` (damage rule 0x4C → `0x080C45A8`, 0x3D → `0x080C42EE`). Its
acceptance chain:

1. the candidate's score (`cand+0xC`, saved by the gate prologue) **must be
   negative** — `bge` to the reject tail;
2. **current HP ≤ max/3** on the candidate's target unit: the HP getter
   `0x080C7EA4(unit, k)` is a 0x45-entry dispatch where `+0x13` → u16 at
   `unit+0x18` (current) and `+0x14` → u16 at `unit+0x1A` (max); max/3 is
   computed with the libgcc helpers (`0x08142AB0` = divide, `0x08142950` =
   modulo);
3. caster status guards (`0x080CDB6C`/`0x080CDB54`/`0x080CDA94` — bit tests
   at `unit+0xEA`/`+0xEB`);
4. a **`RandNext()%101` roll** (`0x08002804` is the LCG at `0x030034B0`):
   self → ≤10, ally → ≤49, else the rule advances (candidate rejected).

Causal certification of the pool law (`tools/probe_pool_law.py`, frozen
RNG, facing state): retail resolves this battle to regime 1. Rewriting the
mode=0 (help-pool) candidates to rule 0x26 + score −1 still fails — the
three targets are at full HP (26/26, 19/19, 14/14) and step 2 rejects them
(watched live at the handler's HP-check exit). Wounding each target to
exactly max/3 (the unit pointer is a **double deref** of the record head:
`rec+0` → 0x90-stride entry, `entry+0` → unit) makes the gate pass and the
chooser **accept regime 0 record 0** on the walk's first entry, with zero
rejections. The same battle that retail-resolves to a harm-pool action now
resolves to a help-pool action purely through encoded candidate fields —
prediction → intervention → observation match. Two probe lessons: a
damage rule paired with a negative score is malformed and rejected (pool
membership is enforced at both the producer and the gate), and
`cand+0..3` is a u16 **target id**, not a unit pointer — unit resolution
goes through the record's entry pointer.

The sign coupling inside the gate is now fully mapped. Rule 0x26's
negative-score check is inline (`0x080C3E84`); the damage-side mirror is a
helper — rule 0x15 (damage) calls `0x080C442E(score)`, which rejects
scores ≤ 0 (`bgt` passes only positive). Both damage handlers (0x4C →
`0x080C45A8`, 0x3D → `0x080C42EE`) carry the same shape as 0x26's tail:
`RandNext()%101` (self ≤10, ally ≤49) then a target status-bit test. The
gate's prologue before the rule loop also checks: candidate flags
`cand+0x11 & 3`, a special case for ability id 0x109, ability cost vs the
caster's `+0x1C` meter (with an empty-meter reject when field-0x13 is 0),
and a "target HP must be < max/2" gate for abilities whose table byte
`+0x19` == 2 (healing-class abilities).

Executed rejection attribution (`tools/trace_reject.py`, breakpoint on the
gate's shared reject tail `0x080C478C` with LR→call-site mapping, frozen
RNG, facing state): **retail produces zero tail hits** — every rejection
in the retail battle happens before the gate (the chooser's pre-gate sign
check kills the regime-0 trio; the accepted regime-1 candidate never
fails). With `--negate` (all seven candidates rewritten to damage rule +
score −1, malformed by design), all seven are rejected at exactly one
site: rule 0x15's positive-score helper. The full sign-coupling picture:
**the producer sets the sign from the projected effect, the chooser's
pre-gate check enforces pool membership, and the per-rule handlers re-check
the sign so rule semantics and score polarity can never disagree.**

Executed confirmation (`tools/trace_choose.py`, evidence
`outputs/mgba-snowball/choose-trace.json`, frozen RNG, facing state): the
walk visited regime 0 records 0/1/2 candidate 0 — **each rejected by the
gate** (reconciling the watchpoint finding that those candidates were
never even filled) — then accepted regime 1 record 0 candidate 0. The
winner is exactly the mode=1 arena's first record (entry `0x0202267C`),
i.e. **the top-ranked candidate under the priority-ascending key law** —
the AI chooses what the sort put first. Decision struct as filled:
`+0` = `[ctx+4]` (the actor's 0x90-stride action-entry array base,
`0x020223AC` this battle), `+4` = the record's entry pointer,
`+8/+0xA` = the winning candidate's ability operand and rule A (both 0 —
job fallback), `+0xC` = `[ctx+0x54EC]` (battle-side pointer), `+0x10` =
the swapped arena base (`ctx+0x2968` here), `+0x14` = the winning
candidate's address, `+0x28` = regime flag; handler `0x080BF7C5` at
`ctx+0x528C`.

Two decode notes that apply everywhere: `bl 0x0814224C`/`0x08142250` are
**register-dispatch veneers** (`bx r2`, `bx r3`, … one per register) — the
real callee pointer is loaded from ROM (e.g. `r2 = *0x0836D4B8` →
`0x03005E79`, the IWRAM-resident copy routine family), so those literals are function pointers, not direct calls. And `bl 0x080C1260` in any
sequencer-context function is the frame-yield primitive.

### Decision -> execution: phase 4 polls the handler

Phase 4 (`0x080C09EC`) is not a copy step — with the veneer insight its
`bl 0x0814224C` is `bx r2` where `r2 = [ctx+0x528C]`, i.e. it **calls the
action handler** (`0x080BF7C5` observed) with r0 = the decision struct
`ctx+0x5290` and r1 = the turn object `ctx[0]`. It frees `ctx+0x5494` /
`ctx+0x5490` buffers beforehand. Polling polarity: **return 0 = the action
is finished** (phase 4 advances to phase 5); **nonzero = not finished** —
phase 4 re-copies the struct and yields the frame, calling the handler
again next frame. Executed (`tools/trace_exec.py`, frozen RNG, facing
state): 8 calls, phase march `[0, 1, 3, 4, 1, 3, 4, 1]`, returns
1×7 then 0.

### The execution machine `0x080BF7C4`

The handler is a **5-phase per-frame state machine** (dispatch u16 at
`dec+0x1B8`, jump table `0x080BF7EC`):

| phase | entry | role |
| --- | --- | --- |
| 0 | `0x080BF800` | init: validates the ability (`0x080BDF9C`), resolves the target's position/element (`0x812F0D8`/`0x812EED0`/`0x812EE98`), builds the local action record |
| 1 | `0x080BF8C2` | resolves the next target: walks the target-tile pointer list (`dec+0x204` list, `dec+0x20C` count, `dec+0x20E` index) |
| 2 | `0x080BFBC8` | animation-ready wait (`0x080A11DC` busy poll on `dec+0x2C`) — skipped for the plain attack traced here |
| 3 | `0x080BFBE6` | applies the action at the current target's tile (`0x080A8700`), steps the index |
| 4 | `0x080BFC46` | per-target wrap-up (distance/facing checks against the unit's `+0xF6/+0xF7` coords) |

The AI-turn contract is therefore fully explicit: sorted arena → first
gate+sign-passing candidate → decision struct → a per-frame execution
state machine that steps the target list applying the chosen ability.

### The score producer `sub_080C2314`: projected magnitude on the target

`sub_080C2314(caster, target, ability, ...)` computes what the candidate's
`+0x0C` score and `+0x04..0x0A` rules mean: it calls `0x8130200` to
**project the action's effect magnitude on the target**, clamps against
the target's HP meters (`0x080C7EA4(target, 0x13/0x14)`, so a kill can
never project more damage than the target's current HP, and overheal
clamps to the missing amount), and emits rule ids at the out-arg:
**`0x15` (damage) when the projected magnitude is positive,
`0x26` (recovery) when negative, `8`/`9` variants in two switch cases
(jump table `0x080C24F8`)**, accumulating per-effect magnitudes into the
score out-arg over a 2-iteration loop (`sl` counter). Special-case: ability
`0x146` forces score 100 and rule `0x51`; a final check flips the `+0x0B`
flags bit 0 when the summed score went negative (that is where a negative
score can originate — recovery/malus effects) and zeroes the validity
return when the whole projection was zero (zero-delta actions are invalid:
nothing would change on the target). Combined with the chooser's sign
checks this names the two arenas precisely: **regime 1 (mode=1 arena,
sort arg 8) is the harm pool** — it accepts candidates whose projected
effect on the record's target is positive (the target loses HP) — and
**regime 0 (mode=0 arena, sort arg 0x87) is the help pool**, accepting
negative projections (the target recovers). The same (ability, target)
space is projected into both arenas; the polarity check at choose time is
what separates attacking from supporting. The mode=0 arena's rejection of
this battle's damage candidates is the help pool refusing projected-damage
candidates.

### Sequencer context, scheduler, and the entry table

- The sequencer runs from a **fixed context** `ctx = 0x020101F8`: the
  tiny wrapper `0x080C1438` loads that pointer and calls the dispatcher
  `0x080C045C`; its single caller is the **battle scheduler** at
  `0x0809349E`.
- The context initializer is `0x080C034C(ctx, unit)` (called through
  `0x080C144C` from `0x08093456`, arg0 = the unit's battle object): it
  zeroes 0x553C bytes via the veneer copy routine, stores `ctx+4 = unit`,
  copies unit fields (`+0xF6/+0xF7` → `ctx+0x54CA/0x54CB`, writes at
  `0x080C041E`/`0x080C0428`, live-caught by
  `tools/scratch_queue_tile.py`), reads the unit's `0x15` meter into
  `ctx+0x54C8` (write at `0x080C0410` from `0x080C7EA4`), seeds the frame
  counter at
  `ctx+0x54F4+2`, and computes turn-order branch keys (the initial
  phase is 0xB only on the `0x080C95A8(0xd)`-nonzero branch; the traced
  actor seeds phase 9 — see the full-turn-march section; bit 4 of
  `ctx+0x54AF` set by unit class `0x0809AA10`, bit 6 when the special
  condition passes).
- `ctx+4` (the action-entry array base) is written **exactly once per
  turn** — caught live by a write watchpoint: the write is the
  initializer's `str r4,[r5,#4]` at `0x080C0360`, fed by the scheduler's
  `r0 = [unit_obj+4]`. The **0x90-stride entry table itself** (here
  `0x20223AC`, entries 0–3 feeding mode=0 and 4–7 mode=1 this battle) is
  therefore built even further upstream, during battle/unit setup: it
  receives no writes during the AI turn, and after the turn the
  destructor `0x080C1460` (scheduler `0x080934B2`) frees the object at
  `ctx+0x54EC` and `ctx[0]` is left 0 — which is why a probe attaching
  between turns reads `ctx+4 = 0`.
- Phase 0's `0x080C47A8` arg1 is also the **AI struct size** `0x5684`
  (the allocation the memset fills).

### Corrected reading of the `bl 0x0814224C` sites and the battle object

Two stale claims elsewhere in these notes ("template→struct copy") are
wrong, and the correction reorganizes the setup-side picture:

- `0x0814224C` is the register-dispatch veneer (`bx r2`, `bx r3`, ...),
  and the pointer at **`0x0836D4B8` — the constant almost every call
  loads into the dispatch register — is `0x03005E79`, an IWRAM-resident
  `memset(dst, 0, size)`**. The 0xB0-byte routine block it lives in is
  DMA-copied from ROM `0x08A38A2C` to `0x03005E78` by `0x08002768` at
  boot; the block is a small memset/memcpy library (memset-0 at `+0`,
  byte-fill at `+0x34`, memcpy at `+0x70`). So every `bl 0x814224C`
  with `r2 = [0x0836D4B8]` and `(dst, size)` in `r0/r1` is a **zeroing
  call** — there is no template copy: the AI struct (0x5684) and the
  battle object (0x1B8) are allocated fresh and zeroed.
- **Battle object model (live-dumped this session).** Battle init
  `0x08096BA0` allocates 0x1B8 bytes, zeroes them, and installs the
  pointer at global `0x0200F4A8` (value `0x0200F4E8`). Layout as
  observed: `+0` = pointer to the container object built by `0x08097000`
  (its own `+0xC` = a 0x800-byte block whose init returns the owner for
  three 12-byte **list heads stored at `+0x10`/`+0x14`/`+0x18`** — see
  the arena-setup section — plus two sub-objects at `+4`/`+8` and one
  more alloc at `+0x20`); `+4` = **`+8` = the 0x90-stride
  action-entry-array base** (`0x020223AC` this battle, u16 entry count
  8 at `+0xDC`); `+0x40` = `0x0202282C` = table end (base + 8·0x90),
  `+0x44` = one more buffer; the rest zero this battle.
  This object is the scheduler's arg0: `r0 = [battle_obj+4]` feeds the
  ctx initializer, so **`ctx+4` = `[battle_obj+4]` = the entry-array
  base** (not the battle object itself). The AI orchestration
  `sub_080C1EB4(ai, entries)` then receives the **entry-array base** as
  its second argument (`ai+0 = [entries+0x80]`, `ai+4 = entries`) and
  builds target lists from the element containers reachable through it
  (the container iterators `0x080C7CC0/0x080C7D18/0x080C7D70` wrap the
  entries; the arena records' `entry+0` unit pointers are the elements
  of those containers).
- **Unit-record array.** A fixed array of twelve **0x108-byte unit
  records starts at `0x02002FC4`** (0x80-record stride is `0x108`),
  pre-seeded from ROM records `0x0854CD54 + id·0x1C` (12 bytes copied,
  `+4` = active flag) by `0x08096E18(unit_slot)`, which is invoked by
  the battle event-script VM's spawn command `0x08123670`. Battle-flow
  `0x08124CE8` later sweeps all 12 records, wraps each active one
  (`0x08092440`), and binds it into a battle-slot handle
  (`[0x020159CC]` array, slot = `0x4D8 + idx·8`, `str rec,[slot+4]`).
  The entry-table unit pointers observed this battle were exactly
  `0x02002FC4 + 0x108·k` (k = 0..7) — consecutive spawned units.
- **The entry factory and its call site are now pinned (2026-09-05).**
  Each per-unit action entry is created by **`0x0809716C(C, unit)`**,
  called from the wrapper **`0x08092440(C, unit)`**, called per active
  unit by the battle-flow sweep **`0x08124CE8`** (itself reached from
  the unit-spawn region around `0x08124C40`; the same sweep binds each
  unit into its battle-slot handle). The factory: allocates a block of
  **0x84 bytes** (the allocator rounds each block up to the observed
  0x90 stride — 0x84 rounds to 16-byte alignment), zeroes it, writes
  the unit pointer at `+0x00`, the **registration/order key at `+0x24`**
  (`0x08099CB8(C)` = the current count of `C+0x10`; 1-based in this
  battle, a 1..8 permutation — also stored to `unit+0xFB`), the
  container pointer at `+0x80`, the shared ctor buffer `[C+0x1C]` at
  `+0x3C`, constant 1 at `+0x38`, the unit height (`unit+0xF8`) at
  `+0x20`, sets `unit+0x28` bit 0, and links the entry into the
  `C+0x10` list (append `0x080C7A74`) plus its BST (insert
  `0x080C7AB4`, key = `entry+0x24`). The wrapper then fills the pixel
  coords (`+0x08/+0x0C` via `0x08099E68` from `unit+0xF6/+0xF7`), the
  `+0x1E` byte and `+0x34` u16 from the per-unit property call
  `0x08022238(unit, byte*)`, and height via `0x0809836C`, and routes
  the entry into `C+0x14` (side-False) or `C+0x18` (side-True) by the
  same `+0x28`-bit-15 side bit the arena gate uses. The entries are
  therefore born during battle setup, one per active unit — which is
  why the array receives no writes during the AI turn.

### The 0x84-byte action entries (live dump, 8 entries)

Each entry correlates to one spawned unit record. Logical size is
**0x84 bytes** (factory `0x0809716C` allocates 0x84); the allocator
rounds each block up to the observed **0x90 stride** (0x84 → 16-byte
alignment). Fields, now with writer provenance:

| offset | type | meaning (snowball-battle values) | written by |
| --- | --- | --- | --- |
| `+0x00` | ptr | unit record pointer (`0x02002FC4 + 0x108·k`) | factory `0x0809716C` |
| `+0x04` | — | 0 (factory zero-fill) | |
| `+0x08` | u16 | x position · 16 (pixel coords; e.g. `0x00d0` = 208) | wrapper `0x08092440` via `0x08099E68` |
| `+0x0c` | u16 | y position · 16 | wrapper via `0x08099E68` |
| `+0x1e` | u8 | per-type property byte (`0/1/2`) from `0x08022238` (side-aware getter `0x080CB65C` reading the `+8/+9/+0xA` region of a per-type record at ROM `0x085273D8`) — not side-correlated (this battle `{0,0,1,2}` vs `{0,0,1,1}`) | wrapper via `0x08022238` |
| `+0x20` | u8 | **unit height** (copy of `unit+0xF8`) | factory |
| `+0x24` | u32 | **registration/order key** = `C+0x10` count helper `0x08099CB8` at creation (full u32 written; its low byte is the 1-based registration order — a permutation of 1..8 here — and is the ordering key mirrored to `unit+0xFB`; the upper bytes are not consumed) | factory via `0x08099CB8` (also `unit+0xFB`) |
| `+0x34` | u16 | per-type property halfword (`0x2c`-`0x3a` here) from `0x08022238` return — the `+4/+5` u16 of the same per-type record (`0x085273D8`, 0xE-stride, keyed by the `unit+0x04` type byte), read by `0x080CB714` | wrapper via `0x08022238` |
| `+0x38` | u16 | 1 (constant) | factory |
| `+0x3c` | ptr | shared `0x02021A14` buffer (copy of `[C+0x1C]`) | factory |
| `+0x80` | ptr | container `C` back-pointer (`0x0201F134`) | factory |

`tools/trace_choose.py` logs the walk indices at the chooser head and the
decision fields at the choose-call return; `tools/disasm.py` is the
literal-annotated Thumb disassembler (resolves `ldr [pc, #imm]` pools,
branch targets, jump tables via `--table BASE,N`, and function heads via
`--head ADDR`) used for every static decode above.

### Arena setup: `sub_080C1EB4`, the container lists, and the record gate

Before any candidate is filled, the sequencer's first AI-phase call
(`0x080C0730` → `0x080C47A8` → **`sub_080C1EB4`**) builds and installs
the arena records. The source of the two arenas is now mapped end to end
and confirmed live (`tools/probe_pool_sides.py`, evidence
`outputs/mgba-snowball/pool-sides.json`):

**The entry container.** Entry 0 of the 0x90-stride table is **the acting
unit's own entry**, and its word at `+0x80` is a back-pointer to the
container object `C` (this battle `0x0201F134`, which is also what
`battle_obj+0` points to — the ctor object built by `0x08097000`). `C`
carries **two doubly-linked lists of entry pointers at `C+0x14` and
`C+0x18`** (plus a third, differently-shaped structure at `C+0x10`, see
below). List nodes are 12 bytes `{data@0, prev@4, next@8}`, heads are 12
bytes `{owner@0, first@4, last?@8}` created by `0x080C799C`; the append /
count / find helpers are `0x080C7A74` / `0x080C7B08` / `0x080C7BF4`, and
the iteration helpers are `0x080C7CC0` (plain list) and
`0x080C7D18`/`0x080C7D70` (sorted tree). The list builders
`sub_08099D08`/`sub_08099D34`/`sub_08099D60` wrap one iteration each
over `C+0x14`, `C+0x18`, `C+0x10` respectively and append each node's
`data` pointer (the entry pointer) to a count/buffer pair.

**The two lists are the two battle sides.** Each entry's unit record
(`entry+0`) carries the side as **`+0x28` bit 15** (the persistent-status
word; read by `0x080C8240`). Live in the snowball battle: entries 0–3
are side-True, entries 4–7 side-False; `C+0x14` = side-False `[7,6,5,4]`,
`C+0x18` = side-True `[2,0,1,3]`. (The structure at `C+0x10` is a sorted
tree over the entries — first element is the table-end sentinel
`base+8·0x90` — used through builder `0x08099D60`/iterator
`0x080C7D18`; no arena-setup site calls it. Its consumer is the
**battle unit-container subsystem at `0x08098xxx`–`0x0809Axxx`**
(the entry-table builder thread's home): `0x08098C20` enumerates
`[C+0x10]` and bubble-sorts the objects by the byte at `unit+0x104`,
`0x08098CE8` (single caller `0x0809A9B2`) re-checks every object in the
`C+0x10` list and appends it to the appropriate side list — `C+0x18`
for side-True units, `C+0x14` for side-False units, or keeps it only in
`C+0x10` when the unit has the `+0x28`-bit-0x1000 unaffiliated flag —
inserting each into the sorted tree keyed by `[entry+0x24]`, and
`0x080989AC` (single caller `0x0809A618`) is a placement check that
walks `[C+0x10]` against a proposed position. `0x08097504` places a
unit. So the side lists the AI arenas consume are maintained by this
subsystem during battle setup/placement, via the same
`0x080C7A74`/`0x080C7BF4` appends the arena decode uses. The entry
factory itself is `0x0809716C` (see the entry-table section above), so
`C+0x10` is the complete all-entries set and `C+0x14`/`C+0x18` the
per-side subsets. Each of the three heads is a **dual-structure
container**: registration appends to the head's doubly-linked chain
(`0x080C7A74`) *and* BST-inserts the same node keyed by `entry+0x24`
(`0x080C7AB4`), which is why the append/count helpers and the tree
iterators coexist on one head.)

**`sub_080C1EB4(ai, entries)` picks the pairing.** Its prologue computes
a flag `r4` from the actor's own side bit, then flips it under the
**Charm** and **Confuse** live statuses (`+0xEB` bits 0x20/0x10,
`0x080CDB6C`/`0x080CDB54`; Confuse replaces it with the parity of a
`0x08002804` draw — a confused actor randomly chooses whom to regard as
an enemy). Then:

- if the actor has `+0x28` bit 0x1000 set (`0x080C8298`) — the
  "no-help / fight everything" mode — it builds **one combined arena**
  (mode 1 base `ai+0x2968`) by appending the `C+0x14` list then the
  `C+0x18` list, and stores its count at `ai+0x5270`/`ai+0x5275`;
- otherwise it builds two arenas, and which list feeds the help arena is
  side-dependent: for `r4 == 0` (side-False actor) mode 0 (`ai+0x5c`) ←
  `C+0x14` and mode 1 (`ai+0x2968`) ← `C+0x18`; for `r4 != 0` (side-True
  actor) the pairing is swapped — mode 0 ← `C+0x18`, mode 1 ← `C+0x14`.
  Net effect: **the help arena always holds the actor's own side and the
  harm arena always the opposite side**, whichever list that is. Four
  call sites (`0x080C1FFE`/`0x080C2058` in the `r4==0` path,
  `0x080C20E2`/`0x080C213C` in the `r4!=0` path) call the record
  builder twice.

In each two-arena path the actor's own entry is **moved to the end of
its side's list** before the records are built (linear search against
`entries`, memmove of the tail, re-append), which is why the help arena's
last record is the actor's own (in retail it is the empty-record fourth
slot with entry pointer `0x20223ac` — a unit does not produce a
help-pool candidate for itself; see the fill-pipeline note below).

**`sub_080C1B8C(entries, arena, list, count)`** (caller-attributed live
at `lr = 0x080C20E7` → arena `0x02031d14` = `ai+0x5c`, and
`lr = 0x080C2141` → arena `0x02034620` = `ai+0x2968`) zeroes the record
count halfword at `arena+0x2908`, then for each list entry appends the
entry pointer as a record (`arena + count*0x328 = *list` at
`0x080C1C16`) and increments the count. Per-entry gates:

- the unit side byte of caster vs target (both via `0x080C8240`) —
  same-side entries always become records;
- an arena-flag byte derived from the actor's job class
  (`0x080CD50C`: `[unit+6]` race × `[unit+0x3B]` job through the
  `0x0851BA84` table, or the constant `0x0E` when `0x080C8298` is set) —
  a `0x0E` arena flag exempts every cross-side entry;
- cross-side entries are otherwise kept unless the target is
  **Concealed** (`+0xE9` bit 0x10, `0x080CD9BC` — you cannot be put in
  the harm pool while concealed);
- all entries are dropped when the unit is **gone** (`+0xED` bit 0x40,
  `0x080CDCEC`).

The count fields the pick helpers read (`ai+0x2964` / `ai+0x5270` =
`arena+0x2908` of each arena) are therefore **live record counts written
here**, not static limits — the earlier "static limit" reading is
retracted (they are already 4/4 at the sort entry because setup runs
before the fill, and the sort does not change them).

Consequence for the pool law: the help arena is exactly "units the actor
could help", the harm arena exactly "units the actor could hurt", and
the sign checks decoded earlier are what keep a damage projection out of
the help pool (a same-side target in the help arena whose projection is
positive damage) and a recovery out of the harm pool.

The setup entry itself is **`sub_080C47A8`** (the sequencer's first
AI-phase call): `bl 0x08022840` (obtain/allocate the AI struct),
`bl 0x814224c` **memset-0** at `0x080C47BE` (see the corrected veneer
reading below — it zeroes the whole struct, candidate blocks included —
watchpoint-proven), then the orchestrator `sub_080C1EB4`. A write
watchpoint on the mode=0 empty record's candidate block caught exactly
one write all turn — the zeroing (from IWRAM-resident `0x03005E90`,
called at `lr=0x080C47C3`) — and never a candidate write: for the actor's
own record under the mode=0 rule set (`r3=0`), `sub_080C2314` returns
validity 0 before emitting any rule. Which predicate inside the score
producer rejects it is a separate decode (the `sub_080C2314` rule
engine).

### The 20-byte target candidates inside each record

Each 0x328 record holds up to ten 20-byte target candidates at `+0x04`
(candidate `k` at `record + 4 + k*0x14`; the running count at `+0x324` doubles
as the candidate count, capped at 0x0A). Candidate layout, from the store
pattern of `sub_080C2618`/`sub_080C2314` plus execution:

| offset | type | meaning |
| --- | --- | --- |
| `+0x00` | u16 | ability id operand of `sub_080C2618` (verbatim store at 0x080C263E; the same u16 feeds the priority getter — 0 means job fallback, which is why every capture shows priority 100 here) |
| `+0x04` | u16 | first effect rule id |
| `+0x06` | u16 | second effect rule id |
| `+0x08` | u16 | third effect rule id |
| `+0x0a` | u8 | validity (nonzero keeps the candidate) |
| `+0x0b` | u8 | effect flags accumulated by `sub_080C2314` |
| `+0x0c` | s16 | impact score (its **sign class** gates swaps; the value itself is not a sort key — see the executed key law below) |
| `+0x0e` | u16 | first effect rule id copy (the max-rule scan reads this one) |
| `+0x10` | u8 | **AI priority byte — the sort's executed primary key (ascending)** |
| `+0x11` | u8 | flags (`|= 2` in `sub_080C2618`'s tail when the ability-list check passes) |

The sort comparator's addresses reconcile exactly against this layout: its
`record + k*0x14 + 0x10` score read is candidate `k+1`'s `+0x0c`, and its two
signed bytes (`+0x14` / `+0x1C` record-relative) are the pair's `+0x10`
priority bytes.

#### The executed key law (in-vivo, five engineered plans)

The earlier "score primary, priority secondary" reading was a static
misreading — the mode=1 window only *sign-checks* the two scores
(`challenger <= 0` keeps the incumbent order; `incumbent <= 0` forces a
swap) and never compares score against score. In-vivo candidate engineering
(`tools/probe_key_law.py`, evidence `outputs/mgba-snowball/keylaw.jsonl`)
pins the executed law:

1. sign gates first: a negative-score candidate never rises past a
   positive-score one and is demoted to last regardless of its priority
   byte (plans k4/k5);
2. otherwise the **priority byte ascending** orders the candidates
   (k1: prios 90/80/90/10 ended 10/80/90/90 while the scores 30/50/50/70
   ended 70/50/50/30 — non-monotonic in score);
3. equal priorities fall through to the `Rand() % 101 <= 49` tie roll, so
   with all candidates at the saturated priority 100 every pair ties (a
   count=3 arena draws 3 tie rolls + 1 baseline = 4).

A count-engineering bug deserves its own note: the arena count is a
little-endian u16, and writing `:0004` for "count 4" stores big-endian
`0x0400` = 1024 — the sort then walks 1024 garbage slots. The committed
tie-measurement tool had exactly that bug, which is why the retail tie
cost was previously recorded as +2 draws; with the fix it is +3, matching
the law (three tied pairs). The re-certified live matrix now reads:

| ROM | engineered tie | draws inside one mode=1 sort call |
| --- | --- | --- |
| retail | no | 1 (kind-1 behaviour coin) |
| retail | yes | 4 (coin + 3 tie rolls) |
| `action_selection: first`, targeting retail | yes | 3 (coin patched out; 3 tie rolls remain) |
| `action_selection: first`, targeting retail | no | 0 |
| aggressive (`deterministic_ties`, walk retail) | no | 1 (coin) |
| aggressive + `action_selection: first` | yes | 0 |

Every cell is explained by the law: the tie patches remove exactly the tie
rolls, the action patch removes exactly the behaviour coin, and a count=3
all-equal-priority arena contains three tied pairs. Evidence:
`outputs/mgba-snowball/tie-live.json` (matrix) and `keylaw.jsonl` (plans).

### The score producer

`sub_080C2314(caster, target, abilityId, ...)` writes one candidate's effect
block. It takes four stack out-pointers — mapped by execution with distinct
sentinel buffers: first effect rule id, **s16 impact score**, per-element
effect accumulator, and a kill flag — and returns validity in `r0`.

Executed facts (synthetic-unit runs on the emulator harness):

- the score is a numeric impact estimate: the base damage/heal estimate from
  `sub_812E0BC`/`sub_8130200` plus per-element contributions. For blank units
  and ability 0 the estimate is the constant 95 (score 96 with one status
  point), +5 when the target starts at 0 HP, and deterministic across RNG
  seeds.
- the estimate is clamped to the target's HP (death bound) and the target's
  remaining max-HP headroom (overheal bound) before being stored.
- rule ids land in the rule slots: `0x15` positive effect, `0x26`
  negative/drain, `9`/`8` per the element-type switch, `0x51` for the
  ability `0x146` special that forces score 100.
- ability-specific magnitudes for real ability ids need full battle state and
  are not yet exercised; the formula structure above is what is proven.

#### In-vivo confirmation (frozen-RNG snowball battle)

`tools/capture_candidates.py` closes the synthetic-to-real gap: running the
frozen-seed battle under mGBA's GDB stub, it breaks at `sub_080C2940`'s entry
and snapshots both input arenas. The captured turn shows exactly the decoded
model:

- mode=1 list (`arg0+0x2968`): four records whose `+0x00` pointers are
  consecutive 0x90-stride action entries (`0x020225EC + 0x90*k`, one per
  target unit, current HP 10/16/8/18), each with one valid candidate scoring
  **51 / 46 / 61 / 51** — distinct real-ability impact estimates per target,
  not constants.
- mode=0 list (`arg0+0x5c`): three records (consecutive action entries),
  each scoring **76**.
- every candidate carries rule code `0x15` (positive damage) and priority
  byte `100`, and the sort's secondary key is saturated at 100 here — the
  primary score is what would discriminate.
- candidate `+0x00` reads `0x0000` in all records — now explained: it is
  `sub_080C2618`'s ability-id operand (0 = job fallback), not a target unit
  id; the record-to-target association lives in the record's `+0x00` action
  entry pointer, whose first word is the target unit pointer.
- the entry registers identify the caller: `r1=8, r2=1` (score path) and
  `r1=0x87, r2=0` (list scan), matching the `0x080C077C`/`0x080C078A` call
  sites.

Two runs from `state-facing.ss0` with the same frozen seed reproduce the
arena bytes identically, including RNG seeds and registers — the replay
invariant of `whole-battle-trace.md` holds at the candidate-arena level.
Raw captures: `outputs/mgba-snowball/candidates-run-{a,b}.json`.

The tooling is GDB-only because neither the WSL SDL build nor the Windows Qt
build can load a Lua script from the command line. Two stub quirks the tools
encode: `m` reads fail above ~0x200 bytes per packet (chunk small), and `P`
register writes are silently ignored while `G` corrupts ARM state — input is
therefore injected by patching the four bytes at `0x0800048A` (the VBlank key
poll's invert step) to force "A held", then restoring the retail bytes.

`sub_080C1EB4` is the filter: over a list of `u16` ability ids it fetches the
priority byte, runs the `sub_0812F1DC` predicate, and stores `0` back over any
entry that fails — removing it from the list. It skips the predicate for
entries that first pass a three-way `sub_08133970` check, so that check is an
exemption from the priority gate. The evaluator `sub_080C32C0` is the later
chooser: it is the only other caller of the predicate (`0x080C35A0`) and
re-applies the same gate while scoring.

## A per-type record table at `0x085273D8` (reader-discovered, not yet mapped)

`0x080CB65C`/`0x080CB714` (and their neighbours `0x080CB750`, `0x080CB78C`,
... in the `0x080CB6xx`–`0x080CB8xx` family) index a ROM table at
**`0x085273D8` with stride 0xE keyed by the unit-type byte `unit+0x04`**
(`(t<<3) - t) << 1 = t·14`), falling back to the generic battle-stat getter
`0x080C92F0(unit, k)` when the unit is not a battle object (`0x080C817C`).
The reader at `0x08022238` copies one byte of it into each action entry's
`+0x1E` (side-dependent path via `0x080CB65C`, reading the record's
`+8/+9/+0xA` nibble/flag region plus a threshold table at `0x03003A60`) and
the `+4/+5` u16 into `+0x34`. Rows look like `{type, +1..+3, u16@+4, u16@+6,
+8 flags, +0xA, ...}`; individual field meanings are not yet pinned. This is
a candidate for the next table-mapping pass (`tools/find_accessors.py` style:
enumerate readers, then name fields from executed consumers).

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
