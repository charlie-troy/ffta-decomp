# AI per-effect probability gates

The 92-case switch at the end of `sub_080C32C0` is not a scoring system in
the usual sense. Each case is a **probability gate**: pick one of two
hardcoded thresholds based on a condition, roll `Rand() % divisor`, compare,
and either bail out or apply the effect.

Regenerate with `python tools/ai_case_rules.py <rom> build/functions_all.json`.

## The dominant pattern

Most status-inflicting effects share exactly the same gate: divisor **101**,
thresholds **10** and **49**. From the disassembly of case 17:

```
cmp  sl, r8            ; some condition on the target
bne  .other
  r = Rand() % 101
  if (r > 10)  -> fail        ~11% pass
  -> pass
.other:
  r = Rand() % 101
  if (r <= 49) -> pass        ~50% pass
  -> fail
```

So the AI applies a status effect roughly **11%** of the time in one case and
**50%** in the other. Which condition selects which is not yet identified.

Because the pair is shared across around twenty effects, changing those two
constants shifts the AI's willingness to use status effects as a whole.
They live in code, not data, so that needs `make mod` rather than the CSV
editor.

## All case bodies

| effect ids | divisor | thresholds | applies |
|---|---|---|---|
| 1 | - | - | `sub_0812E368` |
| 5,18,26,39,40,44,68,81 | - | - | - |
| 2 | - | - | `sub_0812E368` |
| 3 | 101 | 10, 49 | `sub_080CDC74` |
| 7 | - | - | - |
| 8 | - | - | `sub_080C7EA4` |
| 9 | - | - | `sub_080C7EA4` |
| 10 | 101 | 10, 49 | `sub_080CD8FC` |
| 11,53,54,58,79 | - | - | `sub_08022854` |
| 12 | 101 | 10, 49 | `sub_080CD95C` |
| 13 | - | - | `sub_080CD95C` |
| 15,50 | 101 | 49 | - |
| 16 | - | - | `sub_080C13C8` |
| 17 | 101 | 10, 49 | `sub_080CDA1C` |
| 19 | 101 | 10, 49 | `sub_080CDADC` |
| 20 | 101 | 10, 49 | `sub_080CDA34` |
| 4,6,21 | - | - | - |
| 22 | 101 | 10, 49 | `sub_080CDB9C` |
| 23 | - | - | `sub_080CDB9C` |
| 24 | 101 | 10, 49 | `sub_080CDB84` |
| 25 | - | - | `sub_080CDB84` |
| 27 | 101 | 10, 49 | `sub_080CD944` |
| 28 | 101 | 10, 49 | `sub_080CDAC4` |
| 29 | - | - | `sub_080C7EA4` |
| 30 | - | - | `sub_080CDADC` |
| 31 | 101 | 10, 49 | `sub_080CD8E4` |
| 32 | 101 | 10, 49 | `sub_080CD914` |
| 33 | 101 | 10, 49 | `sub_080CD8CC` |
| 35 | 101 | 10, 49 | `sub_080CD98C` |
| 36 | - | - | `sub_080CD98C` |
| 37 | 101 | 10, 49 | `sub_080CDA64` |
| 38 | - | - | `sub_080C7EA4` |
| 41 | 101 | 10, 49 | `sub_080CDB54` |
| 42 | 101 | 10, 49 | `sub_080CDA94` |
| 43 | 101 | 10, 49 | `sub_080CDB24` |
| 45 | 101 | 10, 49 | `sub_080CDB24` |
| 46 | 101 | 10, 49 | `sub_080CD92C` |
| 47 | - | - | `sub_080CD92C` |
| 48 | 101 | 10, 49 | `sub_080CDC8C` |
| 49 | - | 26, 24 | `sub_080CA7A4` |
| 51 | 101 | 10, 49 | `sub_080CDAC4` |
| 52 | 101 | 10, 49 | `sub_080CDAAC` |
| 55 | 101 | 10, 49 | `sub_080C7EA4` |
| 56 | 101 | 10, 49 | `sub_080CDB3C` |
| 57 | - | - | `sub_080CDB3C` |
| 59 | 101 | 10, 49 | - |
| 60 | 101 | 10, 49 | `sub_080CD9BC` |
| 61 | 101 | 10, 49 | `sub_080CD974` |
| 62 | 101 | 10, 49 | `sub_080CD974` |
| 63 | 101 | 10, 49 | `sub_08131030` |
| 64 | - | - | `sub_08131030` |
| 65,66,67 | 101 | 10, 49 | `sub_0812F0D8` |
| 69 | 101 | 10, 49 | `sub_080CDBFC` |
| 70 | 101 | 10, 49 | `sub_080CD9EC` |
| 71 | 101 | 10, 49 | `sub_080CDBB4` |
| 72 | 101 | 10, 49 | `sub_080CDC5C` |
| 73 | 101 | 10, 49 | `sub_080CDC44` |
| 75 | - | - | `sub_080C7EA4` |
| 76 | 101 | 10, 49 | `sub_080CDC2C` |
| 77 | 101 | 10, 49 | `sub_080CDC8C` |
| 78 | 101 | 10, 49 | `sub_080CDC74` |
| 80 | 101 | 10, 49 | `sub_080CDB6C` |
| 82 | 101 | 10, 49 | `sub_080CDB0C` |
| 83 | 101 | 10, 49 | `sub_080CDAF4` |
| 92 | - | - | `sub_080C832C` |
| 14,34,74,84,85,86,87,88, | - | - | - |
