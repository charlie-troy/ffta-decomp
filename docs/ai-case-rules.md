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
cmp  sl, r8            ; user == target ?
bne  .other
  r = Rand() % 101
  if (r > 10)  -> fail        ~11% pass   (self)
  -> pass
.other:
  r = Rand() % 101
  if (r <= 49) -> pass        ~50% pass   (someone else)
  -> fail
```

The prologue settles what the comparison is: `sl` is loaded from `r0` and `r8`
from `r1`, which are the user and the target. So `cmp sl, r8` is **user ==
target**.

The rule is therefore: the AI applies a status effect to **itself** about
**11%** of the time, and to **anyone else** about **50%**. Self-targeting is
strongly discouraged but not forbidden, which is what you want when the same
machinery handles both debuffs aimed at enemies and buffs aimed at allies.

Because the pair is shared across around twenty effects, changing those two
constants shifts the AI's willingness to use status effects as a whole.
They live in code, not data, so that needs `make mod` rather than the CSV
editor.

## Pre-switch mode dispatch

Before the 92 effect cases, the evaluator derives a target mode with
`sub_0812E6A4`. An invalid target tile or ability property 17 clears it to
zero. Modes 4 through 11 then enter a second local jump table:

| Mode | Rule before the shared Reflect/final checks |
|---:|---|
| 4 | Ability zero skips Reflect; otherwise property 27 rejects and its absence continues |
| 5 | Ability zero rejects; nonzero continues |
| 6 | A nonzero ability without property 3 continues; otherwise estimate into `sp+0`, map it with `sub_0812EE98`, and reject mapped codes 13–14 |
| 7 | For ability zero, estimate into `sp+8` and map with `sub_0812EED0`; codes 0–1 reject, codes 0–2 halve the signed action value, and the negative-action flag rejects |
| 8,10 | Same `sp+8` estimate; codes 0–2 halve the signed action value and the negative-action flag rejects |
| 9 | A nonzero ability continues; ability zero estimates into `sp+4` and shares mode 6's `sub_0812EE98` / code 13–14 rejection tail |
| 11 | Ability zero skips Reflect; property 26 halves the signed action value when its target-side MP cost is no greater than target MP |

The shared Reflect path rejects a nonzero ability when the target has the
Reflect predicate and ability property 18. All paths then require
`sub_0812F1DC(signedActionValue)` to succeed. The helper names remain numeric
where their broader meaning is not yet established.

## All case bodies

| effect ids | divisor | thresholds | applies |
|---|---|---|---|
| 1 | - | effective Speed nonzero; CT > 499 | accept candidate |
| 5,18,26,39,40,44,68,81 | - | - | - |
| 2 | - | effective Speed nonzero; CT <= 699 | accept Quicken/Smile candidate |
| 3 | 101 | 10, 49; reject only when all four tested Up states present | composite gate |
| 7 | - | Judge Points > 1 | accept candidate |
| 8 | - | generated ability list contains property 2; MP nonzero | accept candidate |
| 9 | - | Max MP / 3 nonzero; MP <= Max MP / 3 | accept candidate |
| 10 | 101 | 10, 49 | `sub_080CD8FC` |
| 11,53,54,58,79 | - | simulated effect changes status words `+0xe8/+0xec` | accept candidate |
| 12 | 101 | 10, 49 | `sub_080CD95C` |
| 13 | - | - | `sub_080CD95C` |
| 15,50 | 101 | 10, 49 | probability gate only |
| 16 | - | self-target; `sub_080C13C8(target)` nonzero | accept candidate |
| 17 | 101 | 10, 49 | `sub_080CDA1C` |
| 19 | 101 | 10, 49 | `sub_080CDADC` |
| 20 | 101 | 10, 49 | `sub_080CDA34` |
| 4,6,21 | - | signed action value > 0 | accept candidate |
| 22 | 101 | 10, 49 | `sub_080CDB9C` |
| 23 | - | - | `sub_080CDB9C` |
| 24 | 101 | 10, 49 | `sub_080CDB84` |
| 25 | - | - | `sub_080CDB84` |
| 27 | 101 | 10, 49 | `sub_080CD944` |
| 28 | 101 | 10, 49; Haste branch requires Stop absent, otherwise Slow absent | composite gate |
| 29 | - | reject only when Disable, Immobilize, Blind, Berserk, and HP == 1 | composite gate |
| 30 | - | reject only when Disable, Immobilize, Slow, and Stop are all present | composite gate |
| 31 | 101 | 10, 49 | `sub_080CD8E4` |
| 32 | 101 | 10, 49 | `sub_080CD914` |
| 33 | 101 | 10, 49 | `sub_080CD8CC` |
| 35 | 101 | 10, 49 | `sub_080CD98C` |
| 36 | - | - | `sub_080CD98C` |
| 37 | 101 | 10, 49 | `sub_080CDA64` |
| 38 | - | signed action negative; HP <= Max HP / 3 | accept candidate |
| 41 | 101 | 10, 49; reject Confuse+Charm combination | composite gate |
| 42 | 101 | 10, 49 | `sub_080CDA94` |
| 43 | 101 | 10, 49; reject only when all seven tested states present | composite gate |
| 45 | 101 | 10, 49 | `sub_080CDB24` |
| 46 | 101 | 10, 49 | `sub_080CD92C` |
| 47 | - | - | `sub_080CD92C` |
| 48 | 101 | 10, 49; reject only when both tested states present | composite gate |
| 49 | - | any equipped item property 3 in 24..26 | accept candidate |
| 51 | 101 | 10, 49 | `sub_080CDAC4` |
| 52 | 101 | 10, 49 | `sub_080CDAAC` |
| 55 | 101 | 10, 49; Expert Guard absent; HP <= Max HP / 3 | composite gate |
| 56 | 101 | 10, 49 | `sub_080CDB3C` |
| 57 | - | - | `sub_080CDB3C` |
| 59 | 101 | 10, 49 | probability gate only |
| 60 | 101 | 10, 49 | `sub_080CD9BC` |
| 61 | 101 | 10, 49 | `sub_080CD974` |
| 62 | 101 | 10, 49 | `sub_080CD974` |
| 63 | 101 | 10, 49; persistent Zombie and effective state absent | composite gate |
| 64 | - | - | `sub_08131030` |
| 65,66,67 | 101 | 10, 49 | `sub_0812F0D8` |
| 69 | 101 | 10, 49 | `sub_080CDBFC` |
| 70 | 101 | 10, 49 | `sub_080CD9EC` |
| 71 | 101 | 10, 49 | `sub_080CDBB4` |
| 72 | 101 | 10, 49 | `sub_080CDC5C` |
| 73 | 101 | 10, 49 | `sub_080CDC44` |
| 75 | - | HP > 1 | accept candidate |
| 76 | 101 | 10, 49 | `sub_080CDC2C` |
| 77 | 101 | 10, 49 | `sub_080CDC8C` |
| 78 | 101 | 10, 49 | `sub_080CDC74` |
| 80 | 101 | 10, 49; reject Confuse+Charm combination | composite gate |
| 82 | 101 | 10, 49 | require Protect absent |
| 83 | 101 | 10, 49 | require Shell absent |
| 92 | - | global `0x02003C33` enabled; Yellow Card absent | accept candidate |
| 14,34,74,84,85,86,87,88, | - | - | - |
