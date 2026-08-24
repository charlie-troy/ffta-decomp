# Unit struct flags

The layout is derived from the 100 matched accessors in `src/generated`, which
each encode the struct byte and bit they touch. Behavior-backed names are kept
in `tools/status_flags.py`. Regenerate both views with
`python tools/flag_map.py --md`.

Bit *meanings* are not yet known. What is known is the layout, and which
getter and setter belong to each bit.

| byte | width | mask | bit | getter | setter |
|---|---|---|---|---|---|
| 0x28 | u16 | 0x4 | 2 | `sub_080C8310` | `-` |
| 0x28 | u16 | 0x8 | 3 | `sub_080C82D8` | `-` |
| 0x28 | u16 | 0x20 | 5 | `sub_080C8348` | `-` |
| 0x28 | u16 | 0x40 | 6 | `sub_080C832C` | `-` |
| 0x28 | u16 | 0x100 | 8 | `sub_080C8364` | `-` |
| 0x28 | u16 | 0x1000 | 12 | `sub_080C8298` | `-` |
| 0x28 | u16 | 0x2000 | 13 | `sub_080C8260` | `-` |
| 0x28 | u16 | 0x4000 | 14 | `sub_080C82B8` | `-` |
| 0x28 | u16 | 0x8000 | 15 | `sub_080C8240` | `-` |
| 0xe8 | u8 | 0x2 | 1 | `sub_080CD8B4` | `sub_080CDD1C` |
| 0xe8 | u8 | 0x4 | 2 | `sub_080CD8CC` | `sub_080CDD40` |
| 0xe8 | u8 | 0x8 | 3 | `sub_080CD8E4` | `sub_080CDD64` |
| 0xe8 | u8 | 0x10 | 4 | `sub_080CD8FC` | `sub_080CDD88` |
| 0xe8 | u8 | 0x20 | 5 | `sub_080CD914` | `sub_080CDDAC` |
| 0xe8 | u8 | 0x40 | 6 | `sub_080CD92C` | `sub_080CDDD0` |
| 0xe8 | u8 | 0x80 | 7 | `sub_080CD944` | `sub_080CDDF4` |
| 0xe9 | u8 | 0x1 | 0 | `sub_080CD95C` | `sub_080CDE14` |
| 0xe9 | u8 | 0x2 | 1 | `sub_080CD974` | `sub_080CDE38` |
| 0xe9 | u8 | 0x4 | 2 | `sub_080CD98C` | `sub_080CDE5C` |
| 0xe9 | u8 | 0x8 | 3 | `sub_080CD9A4` | `sub_080CDE80` |
| 0xe9 | u8 | 0x10 | 4 | `sub_080CD9BC` | `sub_080CDEA4` |
| 0xe9 | u8 | 0x20 | 5 | `sub_080CD9D4` | `sub_080CDEC8` |
| 0xe9 | u8 | 0x40 | 6 | `sub_080CD9EC` | `sub_080CDEEC` |
| 0xe9 | u8 | 0x80 | 7 | `sub_080CDA04` | `sub_080CDF10` |
| 0xea | u8 | 0x1 | 0 | `sub_080CDA1C` | `sub_080CDF30` |
| 0xea | u8 | 0x2 | 1 | `sub_080CDA64` | `sub_080CDF9C` |
| 0xea | u8 | 0x4 | 2 | `sub_080CDA7C` | `sub_080CDFC0` |
| 0xea | u8 | 0x8 | 3 | `sub_080CDBCC` | `sub_080CE1B0` |
| 0xea | u8 | 0x10 | 4 | `sub_080CDA94` | `sub_080CDFE4` |
| 0xea | u8 | 0x20 | 5 | `sub_080CDAAC` | `sub_080CE008` |
| 0xea | u8 | 0x40 | 6 | `sub_080CDAC4` | `sub_080CE02C` |
| 0xea | u8 | 0x80 | 7 | `sub_080CDADC` | `sub_080CE050` |
| 0xeb | u8 | 0x1 | 0 | `sub_080CDAF4` | `sub_080CE070` |
| 0xeb | u8 | 0x2 | 1 | `sub_080CDB0C` | `sub_080CE094` |
| 0xeb | u8 | 0x4 | 2 | `sub_080CDB24` | `sub_080CE0B8` |
| 0xeb | u8 | 0x8 | 3 | `sub_080CDB3C` | `sub_080CE0DC` |
| 0xeb | u8 | 0x10 | 4 | `sub_080CDB54` | `sub_080CE100` |
| 0xeb | u8 | 0x20 | 5 | `sub_080CDB6C` | `sub_080CE124` |
| 0xeb | u8 | 0x40 | 6 | `sub_080CDB84` | `sub_080CE148` |
| 0xeb | u8 | 0x80 | 7 | `sub_080CDB9C` | `sub_080CE16C` |
| 0xec | u8 | 0x1 | 0 | `sub_080CDBB4` | `sub_080CE18C` |
| 0xec | u8 | 0x2 | 1 | `sub_080CDA4C` | `sub_080CDF78` |
| 0xec | u8 | 0x4 | 2 | `sub_080CDA34` | `sub_080CDF54` |
| 0xec | u8 | 0x8 | 3 | `sub_080CDBE4` | `sub_080CE1D4` |
| 0xec | u8 | 0x10 | 4 | `sub_080CDBFC` | `sub_080CE1F8` |
| 0xec | u8 | 0x20 | 5 | `sub_080CDC14` | `sub_080CE21C` |
| 0xec | u8 | 0x40 | 6 | `sub_080CDC2C` | `sub_080CE240` |
| 0xec | u8 | 0x80 | 7 | `sub_080CDC44` | `sub_080CE264` |
| 0xed | u8 | 0x1 | 0 | `sub_080CDC5C` | `sub_080CE284` |
| 0xed | u8 | 0x2 | 1 | `sub_080CDC74` | `sub_080CE2A8` |
| 0xed | u8 | 0x4 | 2 | `sub_080CDC8C` | `sub_080CE2CC` |
| 0xed | u8 | 0x8 | 3 | `sub_080CDCA4` | `sub_080CE2F0` |
| 0xed | u8 | 0x10 | 4 | `sub_080CDCBC` | `sub_080CE314` |
| 0xed | u8 | 0x20 | 5 | `sub_080CDCD4` | `-` |
| 0xed | u8 | 0x40 | 6 | `sub_080CDCEC` | `-` |
| 0xed | u8 | 0x80 | 7 | `-` | `sub_080CE380` |

## Status bits gate capability bits

`sub_08131C58` recomputes what a unit may do. For each status bit it checks,
it clears a corresponding capability when the status is unset. That pairs two
different flag families and is the clearest semantic handle found so far.

The capability setters (`0x080CE420`-`0x080CE480`, spaced 8 bytes) are a
separate, smaller family that is not yet decompiled.

| status getter | struct bit | clears capability |
|---|---|---|
| `sub_080CDA94` | 0xea bit 4 | `sub_080CE420` |
| `sub_080CDAAC` | 0xea bit 5 | `sub_080CE428` |
| `sub_080CDAC4` | 0xea bit 6 | `sub_080CE430` |
| `sub_080CDADC` | 0xea bit 7 | `sub_080CE438` |
| `sub_080CDAF4` | 0xeb bit 0 | `sub_080CE440` |
| `sub_080CDB0C` | 0xeb bit 1 | `sub_080CE448` |
| `sub_080CDB24` | 0xeb bit 2 | `sub_080CE450` |
| `sub_080CDB3C` | 0xeb bit 3 | `sub_080CE458` |
| `sub_080CDB54` | 0xeb bit 4 | `sub_080CE460` |
| `sub_080CDB6C` | 0xeb bit 5 | `sub_080CE468` |
| `sub_080CDB84` | 0xeb bit 6 | `sub_080CE470` |
| `sub_080CDB9C` | 0xeb bit 7 | `sub_080CE478` |
| `sub_080CDBB4` | 0xec bit 0 | `sub_080CE480` |

## Named status flags

| getter | status | how |
|---|---|---|
| `sub_080CDA34` | **Speed Down** | `+0xec` bit 2. Status case 20 calls its setter; `sub_0812E368` halves effective speed, and the stat display changes the speed value from its ordinary palette to the red penalty palette |
| `sub_080CDB24` | **Sleep** | `+0xeb` bit 2. Sleep ability 32 stores raw effect 97; its descriptor selects internal case 45, whose handler calls this bit's setter. `sub_0812C8DC` forces an ordinary attack's hit chance from 95 to 100 against this state |
| `sub_080CDAC4` | **Slow** | `+0xea` bit 6. Status case 51 calls its setter and `sub_0812E368` halves effective speed |
| `sub_080CDAAC` | **Haste** | `+0xea` bit 5. Status case 52 calls its setter and `sub_0812E368` doubles effective speed; its handler is adjacent to Slow and the two effects cancel in execution |
| `sub_080CD974` | **Poison** | `+0xe9` bit 1. Poison ability 64 stores raw effect 125; its descriptor selects internal case 61, whose handler calls this bit's setter. Poison Claw's secondary raw effect 124 selects the same case |
| `sub_080CDB3C` | **Silence** | `+0xeb` bit 3. `sub_08133E18` blocks the ability when this is set unless the ability has property `0x14`, the documented Ignore Silence flag |
| `sub_080CD914` | **Reflect** | `+0xe8` bit 5. `sub_0812F154` returns true when this bit is set (barring a global override), and the AI evaluator calls it precisely where it has already checked the ability's Reflectable flag, to avoid casting reflectable magic at a reflecting target |
| `sub_080CDB54` | blocked-by-status, unidentified | same shape with property `0x18` (flag bit 13), which no public list names |

`tools/validate_statuses.py` protects the five new joins independently: it
checks each named ability's raw effect against the descriptor table at
`0x08553E70`, checks the 92-entry handler table, executes every getter/setter
pair, runs the speed arithmetic, exercises Sleep's hit-chance branch, and
preserves the separate display/adjacency anchors. Raw ability effects and
internal cases are separate namespaces joined by descriptor byte `+0x01`.

Two patterns name a status bit, both keyed on a documented ability flag:

1. **Exemption.** `status(unit) == 0 || ability_property(a, N) != 0`. Where `N`
   is a documented "ignore X" flag, the paired getter reads X. This named
   Silence via Ignore Silence.
2. **Avoidance.** The AI checks an ability flag and a unit predicate together
   and bails. Where the flag is Reflectable, the predicate reads Reflect. This
   named Reflect via `sub_0812F154`.

Both need a documented ability flag to key on, which is what limits the method:
the flag list has only a handful that name a status.

## Why this matters for modding

The AI evaluator `sub_080C32C0` branches on several of these bits directly
(`sub_080CDB54`, `sub_080CDB6C`, `sub_080CD8FC`). Naming them names the
conditions under which the AI refuses to act, which is most of what a
behaviour mod needs to reach.
