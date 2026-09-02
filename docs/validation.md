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
python tools/validate_job_fields.py baserom.gba
python tools/validate_text.py baserom.gba
```

Compile and summarize the current whole-evaluator matching candidate without
printing its full generated assembly:

```bash
bash tools/report_ai_evaluator_candidate.sh
python tools/compare_ai_evaluator_candidate.py
```

The report also gates the known retail frame slots and all 85 retail
self/other probability call sites. It does not claim a match until the reported
size and subsequent byte comparison both reach the 5,352-byte retail target.
The CFG comparison ranks both owned-byte and adjusted total-reachable-byte
differences across the retail 66-root partition. It discovers the candidate's
four evaluator exits, excludes them like the retail partition, and therefore
distinguishes genuinely different paths from bytes merely reassigned to a
shared join. It also calls out case groups that agbcc has merged differently.

No save state, no playable game, no emulator GUI. `tools/emulate.py` maps the
ROM and blank RAM under Unicorn, then calls functions with chosen arguments and
synthetic units built in RAM.

`validate_text.py` is the static completeness gate for the four primary text
tables. It requires all 2,757 strings to decode without unknown codes and locks
the seven punctuation/symbol edge cases that completed the character map.

`validate_maps.py` has sixteen checks. In addition to the decoded map layers,
retail graphics execution, animations, and render modes, it now requires all 50
custom-LZSS streams to recompress within their allocations, an unedited export
to reproduce the ROM byte-for-byte, and a real tile-byte edit to survive
write-back with every ROM change confined to the owning graphics block.

The AI gate now has ten checks. Checks 9 and 10 protect the Phase 7 evaluator
work: the switch remains partitioned into 92 ids / 66 roots / 3,958 owned plus
88 shared code bytes, and executing case 1 and Quicken case 2 proves their
effective-Speed and CT boundaries at 499/500 and 699/700.

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

`validate_statuses.py` is the behavior-backed status/state-name gate. Its
twenty-one checks join 44 named live bits through raw effects and the
descriptor table;
verify the 92-entry application-handler table; join Speed Down, Sleep, Slow,
Haste, Poison, and eleven other named states to their setters; execute all 16
getter/setter pairs; verify thirteen application-handler/live-bit/duration-counter
joins and execute their dedicated and generic stat accessors; execute
Checkmate applying live Doom/count 3 and verify the expiry call chain;
execute Aim: Arm/Aim: Legs applying Disable/Immobilize count 3, then prove
Immobilize zeros movement mode while Disable is checked by ability usability;
execute Astra, consume it with an intercepted Petrify, then apply Petrify to
an unprotected target and prove the CT tick zeros CT/carry 900/25→0/0;
execute Petrify's frozen critical-HP snapshot and reproduce the ordinary
critical boundary at 25/26 HP out of 100;
execute Quicken's handler and preserve the turn-path call that clears its bit;
execute the otherwise-unreferenced `+0xed` bit-6 setter in both directions,
proving set/clear CT outcomes `0/0` and `1000/25` while preserving its zero
direct-call and zero pointer-reference census;
lock the final `+0xed` bit-5/6/7 residue census at 3/13 readers and two
placement writers, verify zero stored setter pointers, and round-trip all
three exact masks without assigning speculative public names;
verify the direct Defending, Hibernate, Morphed, Cover, Expert Guard, and
Controlled effect→case→handler→setter joins and bit round-trips;
execute the physical/magic modifier with Dragon Force's two composite Up bits
and paired Down bits, proving own-channel/cross-channel results `109/100` and
`89/100` from base 100;
execute Cover copying target id 42 into the actor's shared status link and
read it through the dedicated and generic stat accessors;
execute battle-status reset seeding the persistent Zombie revival countdown to
3 (and a blank unit to 0), then verify the dead-Zombie turn path calls the
effective-status, zero-HP, counter getter, and counter setter helpers;
execute the packed recent-target history through insertion, promotion,
eviction, stat read, and AI membership queries, while preserving all four
action-resolution writer sites;
execute the forced-KO result path zeroing target HP while incrementing the
actor's inflicted-KO counter and target's suffered-KO counter;
execute tile X/Y copying into a movement-search origin and verify the paired
X/Y/height stat reads plus range-formula join; execute a two-node battle-list
count and preserve the battle-object builder's matching `+0xfb` store;
execute Wyrmtamer/Parley/Oust removal outcomes into their three saturating
counters and measure the Parley counter's contribution to the shared purge
formula; execute a retail live-X/Y to saved-X/Y snapshot and read it through
stats `0x41/0x42`;
execute Mow Down's secondary handler, verify its dedicated penalty bit halves
Speed and raises incoming hit chance, exercise Sleep's hit-chance branch; and
preserve the independent Speed Down display and Slow/Haste adjacency anchors.
The eighth check proves unit `+0x28` bit `0x0800` and live status `+0xe9` bit 3
both satisfy the effective Zombie predicate, and that initialization calls the
Zombie setter. The final check executes Yellow Card's handler through its write and
Yellow Clip through its inverse store, confirming target `+0x28` changes
`0x0000 -> 0x0040 -> 0x0000`.

## The ten checks

1. **Ability priority filter.** Measured keep-rate against a model of the
   predicate, across the range. See the modulo-bias note below.
2. **Ability property accessor.** `sub_080CCD50` executed for ability ids 1-10
   returns MP cost and Power matching published stats exactly, and `+0x03 x 10`
   matches published AP cost.
3. **Flag decoding.** 1239 bit reads through the property API match a direct
   parse of `+0x10`, confirming the `prop - 0x0B` mapping across the live range.
4. **Stat ids, transitions, resistances, combat totals, and turn state.** Constructor
   execution confirms unit type/race at stats `0x01/0x03`; direct reads confirm
   base/active/secondary job, level, and EXP at `0x02/0x04..0x07`. The six
   address cases execute and return unit `+0x0c/+0x2a/+0x34/+0xd8/+0xe8/
   +0xfc` exactly. Stat `0x00` preserves a full encoded-name text pointer;
   the ability-state initializer writes Human's 142-entry count at `+0x34`,
   and the movement-profile store writes `2,3,4,251` at `+0xfc`. Job
   initialization fills stat `0x08` as innate element and stats `0x0a..0x12`
   as neutral, Fire, Wind, Earth, Water, Ice, Lightning, Holy, and Dark
   resistance. A synthetic 0–7 packing proves all eight sources remain
   independent through unit initialization; Earth uses slot 2. Executing
   Fire damage produces positive
   weak/normal/resist results in descending order, zero for nullify, and a
   negative result for absorb. The job-change fragment synchronizes
   base/active job and clears a duplicate secondary job; the EXP path changes
   40 to 45; and level-up enforces 50/99. HP/MP and the four combat bases still
   read through stats `0x13..0x1a`. Stats `0x1d..0x21` read the five equipped
   item ids at `+0x2a..+0x32`, and all four item-derived combat totals execute.
   Stats `0x23..0x26` then read CT, Speed, CT carry, and Judge Points. The
   base-Speed/item join executes; a one-unit tick normalizes `900 + 100 + 25`
   to CT 1000 / carry 25; and the action selector exposes Human Totema command
   `0x50` at 10 JP but not 9 JP, with the command's UI text decoded as `Totema`.
5. **The healthy-target rule.** Running the `ai_behaviour == 2` fragment against
   synthetic targets shows it rejects exactly when HP < MaxHP/2, including at
   the boundaries (50 of 100 passes, 49 rejects; 30 of 60 passes, 29 rejects).
6. **The status-effect gate.** Running one case body's gate 1200 times per
   branch gives 11.2% when the AI would target itself and 50.8% otherwise,
   against the 10 and 49 thresholds read out of the code.
7. **Packed resistance slots.** All 928 accessor reads (eight slots across 116
   jobs) match the packed 3-bit layout. Retail leaves every slot's high bit
   clear; a separate synthetic test exercises the full 0–7 encoding.
8. **Unarmed attack power.** `sub_08130820` returns job-table `+0x33` for all
   116 jobs, and changing that byte changes the executed result.
9. **Evaluator control-flow partition.** All 92 effect ids resolve to 66 roots.
   Recursive ARMv4T traversal keeps 3,958 case-owned and 88 shared code bytes
   disjoint, excludes embedded tables/pools, preserves all four exit joins,
   and requires matched source coverage for every id 1..92.
10. **First reconstructed rule families.** Direct fragment execution proves case 1 accepts
    only nonzero-effective-Speed targets above CT 499. Quicken/Smile case 2
    accepts only nonzero-effective-Speed targets through CT 699. Remove-Frog
    case 13 rejects when Frog is absent and accepts when it is present, anchoring
    the seven-root present-state cancellation family. Cases 7 and 75 share a
    stat-above-one tail; execution proves the 1/2 boundary for Judge Points and
    HP respectively. Case 9 additionally rejects when Max MP / 3 is zero,
    accepts MP 2 of 6, and rejects MP 3 of 6.

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

## Job-field accessor gate

`validate_job_fields.py` separately executes all 48 accessor formulas across
all 116 records (5,568 reads), including the four `0xff` proxy records. It then
patches eight distinct resistance values and a non-retail direct redirect to
prove the mapping causally. A fourth check executes `+0x31` bit 0 through the
twenty-entry morph-family index. The result is 4/4 checks; there are no
remaining conditional job-field formulas.

## What is still unvalidated

- **Four raw job bytes remain semantically unnamed.** Offsets `+0x02/+0x27`
  have no accessor field; `+0x0c/+0x2c` have fields but no constant call site.
  Complete table-base reachability keeps these numeric rather than assigning
  speculative meanings. `+0x31` is no longer in this set: bit 0 gates the
  morph-family index.
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
