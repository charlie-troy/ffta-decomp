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

The raw ability-effect descriptor table at `0x08553E70` supplies a second,
stronger route. Each four-byte descriptor's `+0x01` selects this internal case
space. Named single-effect abilities therefore join directly to cases: Sleep
raw effect 97 selects case 45, while Poison raw effect 125 selects case 61.
The corresponding application handlers and executed getter/setter pairs then
pin the unit bits without relying on list order. This route now contributes to
41 named live bits, with 21 alternate-ability joins independently converging
on the same internal cases. Six direct application cases sit outside the
evaluator map below: Cover (14), Expert Guard (55), Hibernate (58), Defending
(84), Controlled (86), and Morphed (87).

## Full map

| case ids | gate | accessor | status bit |
|---|---|---|---|
| 3 | 10, 49 | `sub_080CDC74` | `+0xed` bit 1 — **Resistance Up** (Dragon Force composite) |
| 10 | 10, 49 | `sub_080CD8FC` | `+0xe8` bit 4 — **Astra** |
| 12 | 10, 49 | `sub_080CD95C` | `+0xe9` bit 0 — **Frog** |
| 13 | - | `sub_080CD95C` | `+0xe9` bit 0 — **Frog cancel** |
| 17 | 10, 49 | `sub_080CDA1C` | `+0xea` bit 0 — **Advice** |
| 19 | 10, 49 | `sub_080CDADC` | `+0xea` bit 7 — **Stop** |
| 20 | 10, 49 | `sub_080CDA34` | `+0xec` bit 2 |
| 22 | 10, 49 | `sub_080CDB9C` | `+0xeb` bit 7 |
| 23 | - | `sub_080CDB9C` | `+0xeb` bit 7 — **Disable cancel** |
| 24 | 10, 49 | `sub_080CDB84` | `+0xeb` bit 6 |
| 25 | - | `sub_080CDB84` | `+0xeb` bit 6 — **Immobilize cancel** |
| 27 | 10, 49 | `sub_080CD944` | `+0xe8` bit 7 — **Berserk** |
| 28 | 10, 49 | `sub_080CDAC4` | `+0xea` bit 6 — **Slow** (Hastebreak) |
| 30 | - | `sub_080CDADC` | `+0xea` bit 7 — **Stop** |
| 31 | 10, 49 | `sub_080CD8E4` | `+0xe8` bit 3 — **Regen** |
| 32 | 10, 49 | `sub_080CD914` | `+0xe8` bit 5 — **Reflect** |
| 33 | 10, 49 | `sub_080CD8CC` | `+0xe8` bit 2 — **Auto-Life** |
| 35 | 10, 49 | `sub_080CD98C` | `+0xe9` bit 2 — **Blind** |
| 36 | - | `sub_080CD98C` | `+0xe9` bit 2 — **Blind** |
| 37 | 10, 49 | `sub_080CDA64` | `+0xea` bit 1 — **Mow Down speed penalty** |
| 41 | 10, 49 | `sub_080CDB54` | `+0xeb` bit 4 — **Confuse** |
| 42 | 10, 49 | `sub_080CDA94` | `+0xea` bit 4 |
| 43 | 10, 49 | `sub_080CDB24` | `+0xeb` bit 2 — **Sleep** (Bad Breath) |
| 45 | 10, 49 | `sub_080CDB24` | `+0xeb` bit 2 — **Sleep** |
| 46 | 10, 49 | `sub_080CD92C` | `+0xe8` bit 6 — **Petrify** |
| 47 | - | `sub_080CD92C` | `+0xe8` bit 6 — **Petrify cancel** |
| 48 | 10, 49 | `sub_080CDC8C` | `+0xed` bit 2 — **Resistance Down** (Guard-Off composite) |
| 51 | 10, 49 | `sub_080CDAC4` | `+0xea` bit 6 |
| 52 | 10, 49 | `sub_080CDAAC` | `+0xea` bit 5 |
| 56 | 10, 49 | `sub_080CDB3C` | `+0xeb` bit 3 — **Silence** |
| 57 | - | `sub_080CDB3C` | `+0xeb` bit 3 — **Silence** |
| 60 | 10, 49 | `sub_080CD9BC` | `+0xe9` bit 4 — **Conceal** |
| 61 | 10, 49 | `sub_080CD974` | `+0xe9` bit 1 — **Poison** |
| 62 | 10, 49 | `sub_080CD974` | `+0xe9` bit 1 — **Poison cancel** |
| 63 | 10, 49 | `sub_08131030` | live `+0xe9` bit 3 or persistent `+0x28` bit 11 — **Zombie** |
| 69 | 10, 49 | `sub_080CDBFC` | `+0xec` bit 4 — **Attack Down** |
| 70 | 10, 49 | `sub_080CD9EC` | `+0xe9` bit 6 — **Boost** |
| 71 | 10, 49 | `sub_080CDBB4` | `+0xec` bit 0 — **Addle** |
| 72 | 10, 49 | `sub_080CDC5C` | `+0xed` bit 0 — **Defense Down** |
| 73 | 10, 49 | `sub_080CDC44` | `+0xec` bit 7 — **Defense Up** |
| 76 | 10, 49 | `sub_080CDC2C` | `+0xec` bit 6 — **Magic Down** |
| 77 | 10, 49 | `sub_080CDC8C` | `+0xed` bit 2 — **Resistance Down** |
| 78 | 10, 49 | `sub_080CDC74` | `+0xed` bit 1 — **Resistance Up** |
| 80 | 10, 49 | `sub_080CDB6C` | `+0xeb` bit 5 — **Charm** |
| 82 | 10, 49 | `sub_080CDB0C` | `+0xeb` bit 1 — **Protect** |
| 83 | 10, 49 | `sub_080CDAF4` | `+0xeb` bit 0 — **Shell** |
| 91 | - | `sub_080C832C` | clear `+0x28` bit 6 — **Yellow Clip** |
| 92 | - | `sub_080C832C` | set `+0x28` bit 6 — **Yellow Card** |
