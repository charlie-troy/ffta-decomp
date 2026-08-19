# Validation by execution

Everything else in this repository is static analysis: reading code and saying
what it appears to do. This runs the ROM's own functions on an emulated
ARM7TDMI and measures the result.

```bash
python tools/validate_ai.py baserom.gba
```

No save state, no playable game, no emulator GUI. `tools/emulate.py` maps the
ROM and blank RAM, then calls individual functions with chosen arguments.

## What it establishes

**The priority filter is a percentage, and runs opposite to the published
description.** Calling `sub_0812F1DC` 1500 times at each setting:

| ai_priority | measured keep-rate |
|---|---|
| 0 | 0.0% |
| 20 | 25.7% |
| 40 | 44.5% |
| 60 | 64.9% |
| 80 | 81.9% |
| 100 | 100.0% |

Monotonic, tracking `prio/100`, with 0 never firing and 100 always firing. The
slight overshoot in the middle is the `+ 1` and the second roll in the
predicate. Published documentation describes this field as "high = less
likely"; it is the reverse, and this is a measurement rather than a reading.

**The ability table layout is right.** `sub_080CCD50` executed for ability ids
1-10 returns MP cost and Power matching published stats exactly, and `+0x03 x
10` matches published AP cost.

**The flag word is decoded correctly.** 1239 bit reads through the property
API, compared against a direct parse of `+0x10`, with no mismatches. That
confirms the `prop - 0x0B` bit mapping across the whole live range.

## What it does not establish

This validates the *decision inputs*: what the AI reads and how the filter
behaves. It does not validate the *outcome* in a real battle, because that
needs the surrounding game state, and nothing here builds a unit or a map.

Specifically still unmeasured:

- that `ai_behaviour == 2` produces the healthy-target rejection in play
- that patching the 11%/50% gates visibly changes enemy behaviour
- what the 43 unnamed job fields mean

Those need the game running. Everything that could be settled by executing code
in isolation has been.

## Why this beats a playtest for these claims

A playtest tells you an ability was used more often. It does not isolate *why*,
and with a randomised AI it takes many battles to distinguish a real effect from
variance. Calling the filter 1500 times per setting measures the thing directly,
in seconds, with the RNG seeded.
