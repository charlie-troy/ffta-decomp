# Validation by execution

The rest of this repository is static analysis: reading code and saying what it
appears to do. This runs the ROM's own functions on an emulated ARM7TDMI and
measures the result.

```bash
python tools/validate_ai.py baserom.gba
```

No save state, no playable game, no emulator GUI. `tools/emulate.py` maps the
ROM and blank RAM under Unicorn, then calls functions with chosen arguments and
synthetic units built in RAM.

## The six checks

1. **Ability priority filter.** Measured keep-rate against a model of the
   predicate, across the range. See the modulo-bias note below.
2. **Ability property accessor.** `sub_080CCD50` executed for ability ids 1-10
   returns MP cost and Power matching published stats exactly, and `+0x03 x 10`
   matches published AP cost.
3. **Flag decoding.** 1239 bit reads through the property API match a direct
   parse of `+0x10`, confirming the `prop - 0x0B` mapping across the live range.
4. **Stat ids.** Writing HP, max HP and MP into a synthetic unit and reading
   them back through `sub_080C7EA4` confirms stat `0x13`/`0x14`/`0x15` are
   unit `+0x18`/`+0x1A`/`+0x1C`.
5. **The healthy-target rule.** Running the `ai_behaviour == 2` fragment against
   synthetic targets shows it rejects exactly when HP < MaxHP/2, including at
   the boundaries (50 of 100 passes, 49 rejects; 30 of 60 passes, 29 rejects).
6. **The status-effect gate.** Running one case body's gate 1200 times per
   branch gives 11.2% when the AI would target itself and 50.8% otherwise,
   against the 10 and 49 thresholds read out of the code.

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

- **Four unnamed job fields**: `+0x02`, `+0x0c`, `+0x2c`, `+0x31`. No code
  reads any of them, by either the accessor or direct indexing, so there is
  nothing to derive a meaning from. See [job-table.md](job-table.md).
- **Most of the job field accessor.** Execution confirms 16 of its 45 in-range
  offsets as plain byte loads. Seven are the packed resistances, now solved.
  The remaining 22 match on some entries and not others, so they compute a
  value rather than fetch one, and what they compute is not established.
- **Resistance slot 2.** It is a real slot with the same value distribution as
  the other seven, but no field id in the accessor reaches it, so nothing here
  shows the game reading it.
- **Whole-battle behaviour.** The evaluator's decision inputs are confirmed
  individually, but no test here assembles a map, a turn order and a full unit
  to watch the AI actually choose. Calling fragments proves the rules; it does
  not prove there is no seventh rule elsewhere that dominates them.

## Why this beats a playtest for these claims

A playtest shows an ability being used more often. It does not isolate why, and
against a randomised AI it takes many battles to separate a real effect from
variance. Calling the filter 1200 times per setting with a seeded RNG measures
the thing directly, in seconds, and the boundary cases (HP exactly half) are
reachable on demand rather than by chance.
