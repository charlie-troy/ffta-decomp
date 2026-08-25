# Validation by execution

The rest of this repository is static analysis: reading code and saying what it
appears to do. This runs the ROM's own functions on an emulated ARM7TDMI and
measures the result.

```bash
python tools/validate_ai.py baserom.gba
python tools/validate_missions.py baserom.gba
python tools/validate_maps.py baserom.gba
python tools/validate_items.py baserom.gba
python tools/validate_statuses.py baserom.gba
```

No save state, no playable game, no emulator GUI. `tools/emulate.py` maps the
ROM and blank RAM under Unicorn, then calls functions with chosen arguments and
synthetic units built in RAM.

`validate_missions.py` is the equivalent gate for mission data. Its thirteen
checks cover all 512 mission ids; all 4,608 clan-reward reads and nine executed
application paths; required/blocked dispatch jobs and safe packed edits; all
512 base-fee reads plus adjusted-price anchors; the dormant item-exclusion
path; the corrected 256-record mission index and both leading-field behaviors;
all 1,024 packed behavior/icon reads; all 1,536 availability/clear-condition
reads; all 1,024 clan-skill requirement reads plus an executed acceptance
boundary; all 512 cancellation reads plus three executed formatter paths and
all 2,048 reward-preview flag reads plus visible, hidden, and injected dormant
formatter paths; safe setters; and the two known gil/AP reward anchors.

`validate_items.py` is the item-table gate. Its eight checks execute all 7,144
accessor loads, resolve all 375 real items through the icon graphics and
palette object paths, preserve the final OAM palette packing and shop-pool
reader anchors, force a live bit-3 price boundary, reproduce an unedited CSV
byte for byte, and prove a two-field icon edit changes exactly two accessor-
visible bytes.

`validate_statuses.py` is the behavior-backed status-name gate. Its nine
checks join 16 named abilities through raw effects and the descriptor table;
verify the 92-entry application-handler table; join Speed Down, Sleep, Slow,
Haste, Poison, and eleven other named states to their setters; execute all 16
getter/setter pairs;
measure the effective-speed shifts; exercise Sleep's hit-chance branch; and
preserve the independent Speed Down display and Slow/Haste adjacency anchors.
The eighth check proves unit `+0x28` bit `0x0800` and live status `+0xe9` bit 3
both satisfy the effective Zombie predicate, and that initialization calls the
Zombie setter. The ninth executes Yellow Card's handler through its write and
Yellow Clip through its inverse store, confirming target `+0x28` changes
`0x0000 -> 0x0040 -> 0x0000`.

## The eight checks

1. **Ability priority filter.** Measured keep-rate against a model of the
   predicate, across the range. See the modulo-bias note below.
2. **Ability property accessor.** `sub_080CCD50` executed for ability ids 1-10
   returns MP cost and Power matching published stats exactly, and `+0x03 x 10`
   matches published AP cost.
3. **Flag decoding.** 1239 bit reads through the property API match a direct
   parse of `+0x10`, confirming the `prop - 0x0B` mapping across the live range.
4. **Stat ids, transitions, resistances, and combat totals.** Constructor
   execution confirms unit type/race at stats `0x01/0x03`; direct reads confirm
   base/active/secondary job, level, and EXP at `0x02/0x04..0x07`. Job
   initialization fills stat `0x08` as innate element and stats `0x0a..0x12`
   as neutral, Fire, Wind, Earth, Water, Ice, Lightning, Holy, and Dark
   resistance, including the retail duplicate-Wind Earth source. Executing
   Fire damage produces positive
   weak/normal/resist results in descending order, zero for nullify, and a
   negative result for absorb. The job-change fragment synchronizes
   base/active job and clears a duplicate secondary job; the EXP path changes
   40 to 45; and level-up enforces 50/99. HP/MP and the four combat bases still
   read through stats `0x13..0x1a`. Stats `0x1d..0x21` read the five equipped
   item ids at `+0x2a..+0x32`, and all four item-derived combat totals execute.
5. **The healthy-target rule.** Running the `ai_behaviour == 2` fragment against
   synthetic targets shows it rejects exactly when HP < MaxHP/2, including at
   the boundaries (50 of 100 passes, 49 rejects; 30 of 60 passes, 29 rejects).
6. **The status-effect gate.** Running one case body's gate 1200 times per
   branch gives 11.2% when the AI would target itself and 50.8% otherwise,
   against the 10 and 49 thresholds read out of the code.
7. **Packed resistance slots.** All 812 accessor reads (seven reachable slots
   across 116 jobs) match the packed 3-bit layout, and the unused third bit of
   every slot is clear.
8. **Unarmed attack power.** `sub_08130820` returns job-table `+0x33` for all
   116 jobs, and changing that byte changes the executed result.

## The priority field is not exactly a percentage

`Rand()` returns 0..32767, so `Rand() % 10000` is **not uniform**: remainders
0..2767 occur four times in that span and the rest three. The low bias makes
the keep test easier to pass, so the true rate sits above the nominal
`ai_priority` value:

| ai_priority | nominal | actual | measured |
|---|---|---|---|
| 20 | 20% | 25.0% | 27.5% |
| 40 | 40% | 45.5% | 42.8% |
| 60 | 60% | 63.8% | 65.2% |
| 80 | 80% | 82.1% | 81.7% |

So `ai_priority` is a percentage-*like* dial: monotonic, 0 never, 100 always,
but consistently more generous than the number suggests, by up to five points
in the middle of the range. Worth knowing when tuning, and it is why check 1
compares against the corrected model rather than `prio/100`.

This also settles the direction question by measurement rather than by reading:
published documentation describes the field as "high = less likely"; 0 keeps
nothing and 100 keeps everything.

## What is still unvalidated

- **Four job fields are dead data**, not merely unnamed: `+0x02`, `+0x0c`,
  `+0x2c` and `+0x31`. No code in the ROM reads them, and that is established
  by enumeration rather than by failing to find a reader -- see
  [job-table.md](job-table.md). Nothing further is knowable about them from
  this ROM, dynamically or statically.
- **Most of the job field accessor.** Execution confirms 16 of its 45 in-range
  offsets as plain byte loads. Seven are the packed resistances, now solved.
  The remaining 22 match on some entries and not others, so they compute a
  value rather than fetch one, and what they compute is not established.
- **Resistance slot 2.** It is a real slot with the same value distribution as
  the other seven, but no field id in the accessor reaches it, so nothing here
  shows the game reading it.
- **Whole-battle behaviour beyond the traced case.** The opening snowball
  engagement is now execution-traced: one enemy actor evaluates four distinct
  targets through `sub_080C32C0`, and two frozen-RNG replays match exactly (see
  [whole-battle-trace.md](whole-battle-trace.md)). That closes the live-path
  question for this turn, but does not prove every later mission-, law-, or
  effect-specific path is free of an additional dominating rule.

## Why this beats a playtest for these claims

A playtest shows an ability being used more often. It does not isolate why, and
against a randomised AI it takes many battles to separate a real effect from
variance. Calling the filter 1200 times per setting with a seeded RNG measures
the thing directly, in seconds, and the boundary cases (HP exactly half) are
reachable on demand rather than by chance.
