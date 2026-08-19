# AI effect ids and unit status bits

Each of the 92 evaluator cases applies one accessor. Joining that against the
flag map in `docs/unit-flags.md` links **46 of 60 case bodies to a specific
unit status bit**.

Regenerate the inputs with `tools/ai_case_rules.py` and `tools/flag_map.py`.

## These ids are not the published effect ids

Worth stating plainly, because assuming otherwise wastes time. The dispatch
reads the action's field `[2]` after advancing the pointer, not the ability
table's effect column, so the two id spaces are unrelated.

The anchor disproves any alignment: cases 56 and 57 apply `sub_080CDB3C`,
which is **Silence** (established independently in `docs/unit-flags.md` from
the Ignore-Silence exemption pairing). Neither decimal 56 nor hex 0x56 is a
Silence effect in the published list, and the published Silence ids sit above
this switch's range of 1-92 entirely.

So this is an internal status enum, not the ability effect list.

## Structure: inflict and cancel are adjacent

17 accessors are used by more than one case, and 12 of those have consecutive
ids. That is the inflict/cancel pattern:

```
  sub_080CD95C: cases 12, 13     +0xe9 bit 0
  sub_080CDB9C: cases 22, 23     +0xeb bit 7
  sub_080CDB84: cases 24, 25     +0xeb bit 6
  sub_080CD98C: cases 35, 36     +0xe9 bit 2
  sub_080CD92C: cases 46, 47     +0xe8 bit 6
  sub_080CDB3C: cases 56, 57     +0xeb bit 3   <- Silence
  sub_080CD974: cases 61, 62     +0xe9 bit 1
```

In each pair the lower id carries the 10/49 probability gate and the higher
one does not, which fits inflict-then-cancel: the AI rolls to decide whether
to inflict a status, but removing one is unconditional.

## What naming the rest needs

One anchor is not enough to order 46 bits. The exemption pattern that named
Silence only works where an "ignore X" ability flag exists, and only two are
documented.

The tractable route is behavioural: find the code that acts on each bit
outside the AI, for instance whatever applies damage each turn (Poison) or
clears a bit when a unit is hit (Sleep). Each such site names one bit, and
the inflict/cancel pairing then propagates it to a case id.

## Full map

| case ids | gate | accessor | status bit |
|---|---|---|---|
| 3 | 10, 49 | `sub_080CDC74` | `+0xed` bit 1 |
| 10 | 10, 49 | `sub_080CD8FC` | `+0xe8` bit 4 |
| 12 | 10, 49 | `sub_080CD95C` | `+0xe9` bit 0 |
| 13 | - | `sub_080CD95C` | `+0xe9` bit 0 |
| 17 | 10, 49 | `sub_080CDA1C` | `+0xea` bit 0 |
| 19 | 10, 49 | `sub_080CDADC` | `+0xea` bit 7 |
| 20 | 10, 49 | `sub_080CDA34` | `+0xec` bit 2 |
| 22 | 10, 49 | `sub_080CDB9C` | `+0xeb` bit 7 |
| 23 | - | `sub_080CDB9C` | `+0xeb` bit 7 |
| 24 | 10, 49 | `sub_080CDB84` | `+0xeb` bit 6 |
| 25 | - | `sub_080CDB84` | `+0xeb` bit 6 |
| 27 | 10, 49 | `sub_080CD944` | `+0xe8` bit 7 |
| 28 | 10, 49 | `sub_080CDAC4` | `+0xea` bit 6 |
| 30 | - | `sub_080CDADC` | `+0xea` bit 7 |
| 31 | 10, 49 | `sub_080CD8E4` | `+0xe8` bit 3 |
| 32 | 10, 49 | `sub_080CD914` | `+0xe8` bit 5 |
| 33 | 10, 49 | `sub_080CD8CC` | `+0xe8` bit 2 |
| 35 | 10, 49 | `sub_080CD98C` | `+0xe9` bit 2 |
| 36 | - | `sub_080CD98C` | `+0xe9` bit 2 |
| 37 | 10, 49 | `sub_080CDA64` | `+0xea` bit 1 |
| 41 | 10, 49 | `sub_080CDB54` | `+0xeb` bit 4 |
| 42 | 10, 49 | `sub_080CDA94` | `+0xea` bit 4 |
| 43 | 10, 49 | `sub_080CDB24` | `+0xeb` bit 2 |
| 45 | 10, 49 | `sub_080CDB24` | `+0xeb` bit 2 |
| 46 | 10, 49 | `sub_080CD92C` | `+0xe8` bit 6 |
| 47 | - | `sub_080CD92C` | `+0xe8` bit 6 |
| 48 | 10, 49 | `sub_080CDC8C` | `+0xed` bit 2 |
| 51 | 10, 49 | `sub_080CDAC4` | `+0xea` bit 6 |
| 52 | 10, 49 | `sub_080CDAAC` | `+0xea` bit 5 |
| 56 | 10, 49 | `sub_080CDB3C` | `+0xeb` bit 3 |
| 57 | - | `sub_080CDB3C` | `+0xeb` bit 3 |
| 60 | 10, 49 | `sub_080CD9BC` | `+0xe9` bit 4 |
| 61 | 10, 49 | `sub_080CD974` | `+0xe9` bit 1 |
| 62 | 10, 49 | `sub_080CD974` | `+0xe9` bit 1 |
| 69 | 10, 49 | `sub_080CDBFC` | `+0xec` bit 4 |
| 70 | 10, 49 | `sub_080CD9EC` | `+0xe9` bit 6 |
| 71 | 10, 49 | `sub_080CDBB4` | `+0xec` bit 0 |
| 72 | 10, 49 | `sub_080CDC5C` | `+0xed` bit 0 |
| 73 | 10, 49 | `sub_080CDC44` | `+0xec` bit 7 |
| 76 | 10, 49 | `sub_080CDC2C` | `+0xec` bit 6 |
| 77 | 10, 49 | `sub_080CDC8C` | `+0xed` bit 2 |
| 78 | 10, 49 | `sub_080CDC74` | `+0xed` bit 1 |
| 80 | 10, 49 | `sub_080CDB6C` | `+0xeb` bit 5 |
| 82 | 10, 49 | `sub_080CDB0C` | `+0xeb` bit 1 |
| 83 | 10, 49 | `sub_080CDAF4` | `+0xeb` bit 0 |
| 92 | - | `sub_080C832C` | `+0x28` bit 6 |
