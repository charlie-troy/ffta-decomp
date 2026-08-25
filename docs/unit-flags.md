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

`sub_08131C58` reconciles live status bits with their turn-duration counters.
For each status it checks, an unset bit clears the corresponding byte at unit
`+0xd9..+0xe5`. The old documentation called these bytes "capabilities"; the
application handlers and per-turn decrementers prove they are durations.

The duration getters (`0x080CE3A8`-`0x080CE408`) and setters
(`0x080CE420`-`0x080CE480`) are eight bytes apart in parallel families.

| status getter | struct bit | duration | duration setter | meaning |
|---|---|---|---|---|
| `sub_080CDA94` | 0xea bit 4 | `+0xd9` | `sub_080CE420` | **Doom countdown**; application starts at 3 |
| `sub_080CDAAC` | 0xea bit 5 | `+0xda` | `sub_080CE428` | **Haste duration** |
| `sub_080CDAC4` | 0xea bit 6 | `+0xdb` | `sub_080CE430` | **Slow duration** |
| `sub_080CDADC` | 0xea bit 7 | `+0xdc` | `sub_080CE438` | **Stop duration** |
| `sub_080CDAF4` | 0xeb bit 0 | `+0xdd` | `sub_080CE440` | **Shell duration** |
| `sub_080CDB0C` | 0xeb bit 1 | `+0xde` | `sub_080CE448` | **Protect duration** |
| `sub_080CDB24` | 0xeb bit 2 | `+0xdf` | `sub_080CE450` | **Sleep duration** |
| `sub_080CDB3C` | 0xeb bit 3 | `+0xe0` | `sub_080CE458` | **Silence duration** |
| `sub_080CDB54` | 0xeb bit 4 | `+0xe1` | `sub_080CE460` | **Confuse duration** |
| `sub_080CDB6C` | 0xeb bit 5 | `+0xe2` | `sub_080CE468` | **Charm duration** |
| `sub_080CDB84` | 0xeb bit 6 | `+0xe3` | `sub_080CE470` | **Immobilize duration** |
| `sub_080CDB9C` | 0xeb bit 7 | `+0xe4` | `sub_080CE478` | **Disable duration** |
| `sub_080CDBB4` | 0xec bit 0 | `+0xe5` | `sub_080CE480` | **Addle duration** |

Thirteen duration names are promoted because the same named application handler calls
both the live-bit setter and the paired duration setter. `+0xd9` is Doom:
Checkmate applies the live bit with count 3, and the per-turn expiry path
clears the bit and all battle statuses. `+0xe3/+0xe4` are independently closed
as Immobilize/Disable by executed Aim: Legs/Aim: Arm handlers plus movement
and ability-usability consumers. `+0xd8`, `+0xe6`, and `+0xe7` are outside this
one-to-one duration table.

`+0xe6` is a shared **status link id**, not another timer. Executing Cover
copies the covered target's byte `+0x104` to the covering actor's `+0xe6` while
setting its live state. Two other application handlers share the field, and
battle consumers compare it with candidate units' `+0x104` ids. The status
gate executes Cover with target id 42 and reads 42 through both the dedicated
getter and generic stat `0x36`. Only `+0xd8/+0xe7` remain open in this region.

## Named status flags

| getter | status | how |
|---|---|---|
| `sub_080CDA94` | **Doom** | Checkmate raw effect 170 selects case 42; its handler sets this bit and countdown 3. The per-turn path decrements `+0xd9`, then clears the bit and all battle statuses when it expires |
| `sub_080CDB84` | **Immobilize** | Aim: Legs raw effect 73 selects case 24 and applies this bit/count 3; executing the movement-mode reader changes its synthetic mode from 5 to 0 only when this bit is set |
| `sub_080CDB9C` | **Disable** | Aim: Arm raw effect 69 selects case 22 and applies this bit/count 3; the ability-usability predicate rejects on this getter before its success path |
| `sub_080CDA34` | **Speed Down** | `+0xec` bit 2. Status case 20 calls its setter; `sub_0812E368` halves effective speed, and the stat display changes the speed value from its ordinary palette to the red penalty palette |
| `sub_080CDB24` | **Sleep** | `+0xeb` bit 2. Sleep ability 32 stores raw effect 97; its descriptor selects internal case 45, whose handler calls this bit's setter. `sub_0812C8DC` forces an ordinary attack's hit chance from 95 to 100 against this state |
| `sub_080CDAC4` | **Slow** | `+0xea` bit 6. Status case 51 calls its setter and `sub_0812E368` halves effective speed |
| `sub_080CDAAC` | **Haste** | `+0xea` bit 5. Status case 52 calls its setter and `sub_0812E368` doubles effective speed; its handler is adjacent to Slow and the two effects cancel in execution |
| `sub_080CD974` | **Poison** | `+0xe9` bit 1. Poison ability 64 stores raw effect 125; its descriptor selects internal case 61, whose handler calls this bit's setter. Poison Claw's secondary raw effect 124 selects the same case |
| `sub_080CD9A4` | **Zombie** | `+0xe9` bit 3. Zombify raw effect 127 selects case 63 and this bit's setter. `sub_081308F4` also returns true for persistent unit `+0x28` bit `0x0800` |
| `sub_080CD95C` | **Frog** | `+0xe9` bit 0. Frogsong raw effect 40 and Poison Frog's secondary raw effect 39 both select case 12 and this bit's setter |
| `sub_080CDADC` | **Stop** | `+0xea` bit 7. Stop raw effect 48 and Stopshot's secondary raw effect 47 both select case 19 and this bit's setter |
| `sub_080CD98C` | **Blind** | `+0xe9` bit 2. Blind raw effect 87 and Blindshot's secondary raw effect 85 both select case 35 and this bit's setter |
| `sub_080CDB54` | **Confuse** | `+0xeb` bit 4. Confushot's secondary raw effect 93 selects case 41 and this bit's setter |
| `sub_080CDB6C` | **Charm** | `+0xeb` bit 5. Charmshot's secondary raw effect 140 selects case 80 and this bit's setter |
| `sub_080CDBB4` | **Addle** | `+0xec` bit 0. Addle raw effect 188 selects case 71 and this bit's setter |
| `sub_080CDB0C` | **Protect** | `+0xeb` bit 1. Protect raw effect 78 selects case 82 and this bit's setter |
| `sub_080CDAF4` | **Shell** | `+0xeb` bit 0. Shell raw effect 45 selects case 83 and this bit's setter |
| `sub_080CDB3C` | **Silence** | `+0xeb` bit 3. `sub_08133E18` blocks the ability when this is set unless the ability has property `0x14`, the documented Ignore Silence flag |
| `sub_080CD914` | **Reflect** | `+0xe8` bit 5. `sub_0812F154` returns true when this bit is set (barring a global override), and the AI evaluator calls it precisely where it has already checked the ability's Reflectable flag, to avoid casting reflectable magic at a reflecting target |

`tools/validate_statuses.py` protects all 19 joins independently: it
checks each named ability's raw effect against the descriptor table at
`0x08553E70`, checks the 92-entry handler table, executes every getter/setter
pair, verifies thirteen named duration handlers and direct counter/stat reads,
executes Checkmate's Doom application and checks its expiry call chain, runs
the Aim: Arm/Aim: Legs handlers and the movement/usability consumers, runs
the speed arithmetic, exercises Sleep's hit-chance branch, preserves
the separate display/adjacency anchors, and executes the persistent/live Zombie
bridge plus Yellow Card's write to `+0x28` bit `0x0040`. Raw ability effects and internal cases are separate namespaces joined
by descriptor byte `+0x01`.

## Persistent status flags at `+0x28`

This u16 is separate from the live `+0xe8..+0xed` block. Two bits have direct
application or effective-state joins:

| mask | meaning | evidence |
|---|---|---|
| `0x0040` | **Yellow Card** | Yellow Card raw effect 207/case 92 writes this bit; Yellow Clip raw effect 206/case 91 clears it |
| `0x0800` | **Zombie** | the effective Zombie predicate accepts this bit or live `+0xe9` bit 3; initialization copies it through the live setter |

The other observed masks (`0x0004`, `0x0008`, `0x0020`, `0x0100`, `0x1000`,
`0x2000`, `0x4000`, and `0x8000`) have broad category/capability callers but
no unique named application join, so they remain numeric.

Two patterns name a status bit, both keyed on a documented ability flag:

1. **Exemption.** `status(unit) == 0 || ability_property(a, N) != 0`. Where `N`
   is a documented "ignore X" flag, the paired getter reads X. This named
   Silence via Ignore Silence.
2. **Avoidance.** The AI checks an ability flag and a unit predicate together
   and bails. Where the flag is Reflectable, the predicate reads Reflect. This
   named Reflect via `sub_0812F154`.

The effect-descriptor join no longer depends on an exemption flag, so named
single-effect abilities can identify substantially more of the condition
space.

## Why this matters for modding

The AI evaluator `sub_080C32C0` branches on several of these bits directly
(`sub_080CDB54`, `sub_080CDB6C`, `sub_080CD8FC`). Naming them names the
conditions under which the AI refuses to act, which is most of what a
behaviour mod needs to reach.
