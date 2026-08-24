# Mission data

Undocumented before this. Data Crystal has pages for jobs, items, abilities and
maps, but nothing for missions, so the table had to be found rather than looked
up.

## Finding it

Both accessors already mapped share a shape: scale an index by the entry
stride, add a table base from a literal pool, bounds-check a property id, and
dispatch through a jump table ending in `mov pc, rN`. `tools/find_accessors.py`
scans the ROM for that dispatch and walks backwards to recover the base.

It finds 16 distinct table bases, including all four already known. Exactly one
of the new ones is a clean property accessor:

```
sub_080CE4DC(id, propId):
    r1 = id * 0x46
    r3 = r1 + 0x0855AE4C
    if propId > 0x40: return default
    dispatch through a 65-entry jump table
```

## Shape

| | |
|---|---|
| Table | `0x0855AE4C` |
| Stride | `0x46` (70 bytes) |
| Entries | 512, of which 418 carry content |
| Accessor | `sub_080CE4DC`, 65 properties |

The little-endian halfword at `+0x00`/`+0x01` holds the entry's own index, and
does so on all 512 entries, which is what fixes the count. Entry 0 is blank.

Running all 65 properties over the whole table: **35 are plain loads, 30 are
computed or packed.** Six properties (19–24) and property 32 return the
**address** of a four-byte slot inside the entry rather than a value, at
`+0x12`, `+0x16`, `+0x1a`, `+0x1e`, `+0x22` and `+0x2a`, so the caller reads
the slot itself.

## What identifies it as missions

`sub_080CEECC` reads properties 42 and 44, and for each one scans a 64-entry
list for a match, returning 0 if it is absent. It then reads property 46,
indexes a table with it, and compares the count found against property 47.
That is a requirement check of the form "do you hold this item, and this one,
and at least N of that one" — which is how a mission decides whether it can be
taken.

Properties 42 and 44 are byte fields `+0x36` and `+0x37` remapped by
`sub_080CB4A4`: it returns 0 for 0, and `byte + 375` otherwise. A mission
stores `item id − 375` in the byte and the accessor returns the real item id.
The observed range 0–496 is 375 plus a byte of up to 121. Because 0 means
"none", a mission can only require a quest/loot item (id ≥ 376), never a
combat item from the 376-entry stat table.

`+0x3d` (property 53) goes through the same `sub_080CB4A4` remap. It is a
dormant **dispatch-item exclusion**, not a third acceptance requirement:
`sub_080CF310` returns rating 0 when its raw value matches either item slot on
the dispatch record. All 512 retail missions leave it zero. The validator
patches the ROM map in memory to prove both the `+375` accessor remap and the
two rejection branches without claiming that retail content uses them.

With the text decoded, this is now checkable end to end, and it holds:

| mission | requires |
|---|---|
| Staring Eyes | Ahriman Eye |
| Desert Rose | Flower Vase |
| Den of Evil | Helje Key |
| A Dragon's Aid | Wyrmstone |
| Missing Meow | Rabbit Tail |
| The Hero Blade | Rusty Sword |
| The Fey Blade | Zodiac Ore |

Those are the actual requirements in the game. 92 missions set at least one.
`python tools/mission_table.py requires baserom.gba out.csv` dumps them all.

The check is worth more than its own result: producing it correctly requires
the mission table, the two properties, the item id space and the text decoder
to all be right at once, so it validates the lot.

Properties 33–41 read nine consecutive bytes at `+0x2a`–`+0x32`. They are the
mission's **clan progression rewards**, in points:

| offset | property | reward |
|---|---:|---|
| `+0x2a` | 33 | clan points |
| `+0x2b` | 34 | Combat skill points |
| `+0x2c` | 35 | Magic skill points |
| `+0x2d` | 36 | Smithing skill points |
| `+0x2e` | 37 | Craft skill points |
| `+0x2f` | 38 | Appraise skill points |
| `+0x30` | 39 | Gather skill points |
| `+0x31` | 40 | Negotiate skill points |
| `+0x32` | 41 | Track skill points |

The code path is direct. `sub_08046850(mission, ..., index, ...)` adds
`mission[+0x2a + index]` to the matching level-progress byte in the nine-pair
clan state at `0x020021B4`; reaching 100 advances that level. The completion
renderer `sub_080461D4` labels `+0x2a` as `Clan Pts:` and draws the eight skill
icons. The internal state order is established independently by the mission
requirement UI's consecutive text entries: Combat, Magic, Smithing, Craft,
Appraise, Gather, Negotiate, Track. The official manual presents the same eight
skills in a different visual grid, so it is not a storage-order source.
The standalone validator runs 4,608 accessor reads and then executes
`sub_08046850` once for every track, proving that each byte reaches its matching
progress counter.

They are not dispatch-calculator weights. `sub_080CF310` never reads this
block; it uses the separate dispatch threshold at `+0x43/+0x44`.

## Clan-skill acceptance requirement

Accessor property `0x2e` is the **required clan-skill code**, stored in
`+0x38` bits 0–3. Zero means no skill requirement; codes 1–8 select Combat,
Magic, Smithing, Craft, Appraise, Gather, Negotiate, and Track. The mission
information UI adds 97 to the nonzero code and indexes those exact consecutive
labels in the UI string table.

Property `0x2f` is the **required clan-skill level**, packed as
`(+0x38 >> 4) | ((+0x39 & 7) << 4)`. The acceptance predicate
`sub_080CEECC` reads the selected level byte at
`0x020021B4 + 2 × skill_code` and rejects the mission when it is below the
required value. Executing the complete predicate proves Twin Swords rejects
Combat 9 and accepts Combat 10.

Published requirements provide independent anchors: Den of Evil requires
[Combat 25](https://www.supercheats.com/gameboyadvance/walkthroughs/finalfantasytacticsadvance-walkthrough04.txt),
the alloy missions require Smithing 15, and the later alloy orders require
[Smithing 35](https://gamefaqs.gamespot.com/gba/560436-final-fantasy-tactics-advance/faqs/25687).
The CSV exposes both packed fields and preserves the other nibble and the upper
five bits of `+0x39`.

## Cancellation rule

Accessor property `0x37` is **cancellation allowed**, stored at `+0x41` bit 2.
The mission-information formatter's control code `0x13` selects resource 8
when the bit is set (`Cancellations Accepted`) and resource 9 when it is clear
(`No Cancellations`). Icon group 3 overrides both with
`Mission Begins Immediately`.

The validator executes all 512 flag reads and the formatter itself for one
mission on each presentation path: Snowball Fight cannot be cancelled, a
Wanted! mission can, and Pam Le Fey starts immediately. The computed CSV setter
preserves all seven adjacent flag bits.

## Hidden reward previews

Properties `0x3d..0x40` are four one-bit **reward-preview hidden** flags. The
first two cover item reward slots (`+0x41` bits 6 and 7); the next two cover law
card reward slots (`+0x42` bits 0 and 1). Their two UI callbacks normally
resolve the generated slot value to an item or law-card name. When the matching
flag is set, the callback displays `????` instead.

The names stay behavioral rather than calling every hidden slot random. A
published mission listing does independently show the common correlation:
[Fire Sigil has a fixed sigil plus a random item and random cards](https://www.geocities.ws/gamecc2000/ffta.html),
and its second item-preview flag is set. But the formatter proves concealment;
it does not by itself prove how each reward is generated.

All 2,048 accessor reads match the four raw bits. Executed callbacks show a
visible Shortsword for an unhidden item slot and `????` for hidden item and law
card slots. Property `0x40` is clear in all 512 retail missions, so validation
injects it into a ROM map in memory to prove the dormant second-card branch.
All four computed CSV setters preserve adjacent flags.

## Mission behavior and public type

Mission `+0x02` is packed. Accessor property 1 returns bits 0–2, the engine's
**behavior code**; property 2 returns bits 3–5, the **icon group code**. The UI
helper `sub_080CEBF8` maps icon groups 0, 1 and 2 to the Non-Battle, Regular and
Free-Area presentation assets, while behavior 1 overrides the result with the
Encounter asset. Those are the four player-facing mission types named by the
[official manual](https://www.nintendo.com/eu/media/downloads/games_8/emanuals/game_boy_advance_8/Manual_GameBoyAdvance_FinalFantasyTacticsAdvance_EN_DE_FR_ES_IT.pdf).
Group 3 is used by a small special/postgame set and stays labeled `Special`.

The behavior code is intentionally exposed as a number rather than given six
overconfident labels. Two values have direct behavioral identities:

- behavior 0 reaches the dispatch-unit rating path;
- behavior 1 creates/uses an opposing-clan encounter and forces the Encounter
  icon.

The remaining values separate internal battle/event paths; they do not map
one-to-one onto the four public icons. Verified anchors are Dueling Sub
`(behavior 0, Non-Battle)`, The Bounty `(1, Encounter)`, Free Sprohm!
`(2, Free-Area)`, Herb Picking `(3, Regular)`, and Pam Le Fey
`(2, Special)`. Computed CSV setters preserve both the other packed field and
the upper two bits of `+0x02`.

## Availability and clear conditions

Three adjacent computed properties drive the deadline and progress text shown
for accepted missions:

- property `0x10`, **availability days**, is a 6-bit value packed as
  `(+0x0f >> 3) | ((+0x10 & 1) << 5)`. Zero renders as a dash, meaning no
  deadline; nonzero values render as a day count. Published anchors include
  Fire! Fire! 10, Battle Tourney 15, Fiend Run 20, Wyrms Awaken 35, and
  Smuggle Bust 40.
- property `0x11`, **clear condition code**, is `(+0x10 >> 3) & 7`. Code 0 is
  `Win battle`, code 1 is `Days`, and code 2 is `Battles`. Other codes remain
  numeric until a reader or retail example establishes their presentation.
- property `0x12`, **clear count**, is
  `(+0x10 >> 6) | ((+0x11 & 0x0f) << 2)`. Dueling Sub is `(Days, 3)`, Run For
  Fun is `(Battles, 1)`, Watching You is `(Battles, 2)`, and Hungry Ghost is
  `(Days, 10)`, matching published mission listings.

The CSV exposes all three as computed columns. Their setters preserve the
unrelated low bits of `+0x0f`, the neighboring fields in `+0x10`, and the high
nibble of `+0x11`. Validation executes all 1,536 accessor reads and probes the
full bit-boundary cases.

## Gil, AP and item rewards are in this table

An earlier draft of this file concluded the opposite, and was wrong. The
rewards are three plain bytes, missed because of two compounding slips — one
mislabeled anchor mission and one missing scale factor — that are worth
recording rather than hiding.

- **`+0x33` is the gil reward, in units of 200.** Accessor property 30 loads
  this byte and multiplies by 0xC8 (200) inline, and the mission-info getter
  `sub_080194A8` fetches exactly that property. Herb Picking has `+0x33 = 3`,
  so it awards 600 gil — the published value.
- **`+0x34` is the AP reward, in units of 10.** Herb Picking has `+0x34 = 4`,
  matching its published 40 AP.
- **`+0x35` is the item reward id.** Resolving it as an item name gives the
  actual rewards: the "Wanted!" missions award Buster Sword, Apocalypse,
  Shadow Blade, Pearl Blade and Blue Saber; Salika Keep awards Kotetsu;
  Fire! Fire! and The Wanderer award Djinn Flyssa.

The bad anchor: this file used "Herb Picking = 600 gil / 40 AP" and
"Thesis Hunt = 28,600 gil / 80 AP". The second pair is real but belongs to
**Over The Hill** (mission 25): it has `+0x33 = 143` (×200 = 28,600) and
`+0x34 = 8` (×10 = 80). Thesis Hunt (mission 4) is `+0x33 = 20` (4,000 gil)
and `+0x34 = 4` (40 AP).

The missing scale factor: the dead-end search tried 1, 10, 100 and 1000, and
gil is scaled by 200 — not in that set. With the right mission and the right
scale the whole thing locks together, and the rewards turn out to be stored in
the table, not computed from type/rank.

`+0x3e` is the **base pub information fee**, in units of 200 gil. Accessor
property 54 performs the ×200 conversion. `sub_080CEC78` applies the active
town/turf percentage modifier before mission acceptance compares the result
with clan funds. Executing that path in an unliberated-town state changes Herb
Picking from 200 to 300 gil and Thesis Hunt from 600 to 900 gil. Clocktower's
stored base is 1,600 gil; its published 1,280-gil listing is the same value
after a 20% discount.

## Dispatch rating (`sub_080CF310`)

This function scores a unit against a mission and returns a 1–5 rating, which
is how the game judges a dispatched unit before a non-battle mission resolves.

- It first checks two hard gates and returns 0 (unusable) if either fails:
  `+0x3c` bits 2–7 are a **blocked job code**, compared against the canonical
  job code returned by `sub_080C93F0(unit[+7])`; dormant `+0x3d` is checked
  against two item slots on the dispatch record when the caller enables that
  gate.
- The score is a weighted sum read from a 9-entry table at `0x08527E2A`:
  `2 × level + max HP + MP + attack + defense + magic power + magic resist`
  (the four combat terms via `sub_080CA400`/`sub_080CA478`), two boolean
  bonuses, and the **maximum attack power among the unit's four equipped
  weapons** (`sub_080CA7A4(item, 10)` over slots `+0x2a`/`+0x2c`/`+0x2e`/
  `+0x30`).
- The score is compared against the 16-bit threshold at `+0x43`/`+0x44`
  (accessor property 59, `[+0x44] << 8 | [+0x43]`): score above threshold
  returns 1, and the gap `threshold − score` returns 2/3/4/5 as it crosses
  9/29/49.

So `+0x43`/`+0x44` is the **dispatch threshold** — a named field this project
contributes rather than adopts — and the rating is a coarse difficulty readout,
not a success percentage.

The separate **required dispatch job** is accessor property 48, packed across
`+0x39` bits 3–7 and `+0x3a` bit 0. A roster filter accepts only units whose
canonical job code matches it. Retail anchors are Dueling Sub → Soldier, Run
For Fun → Juggler, and Clocktower → Gadgeteer. The Match demonstrates the
opposite rule at `+0x3c`: it blocks Soldier (rating 0) while an otherwise
identical Paladin reaches rating 5. `mission_table.py` exposes both packed
fields as safe computed columns and preserves their adjacent bits on edits.

## What the field-naming attempts did and did not establish

Named, with the code or the game as evidence:

| field | meaning | basis |
|---|---|---|
| `+0x00`/`+0x01` | mission id | little-endian; equals the entry index on all 512 |
| `+0x2a` | clan points | applied to clan progress by `sub_08046850`; completion UI says `Clan Pts:` |
| `+0x2b`–`+0x32` | eight clan-skill point rewards | applied to the eight paired skill counters; order documented above |
| `+0x33` | gil reward, ÷200 | accessor property 30 multiplies by 200; matches Herb Picking's 600 |
| `+0x34` | AP reward, ÷10 | matches Herb Picking's 40 and Over The Hill's 80 |
| `+0x35` | item reward id | resolves to the Wanted! sword rewards, Kotetsu, etc. |
| `+0x02` bits 0–2 | mission behavior code | properties 1; dispatch/encounter and internal battle/event paths |
| `+0x02` bits 3–5 | mission icon group code | property 2; combined with behavior 1 to select the public mission type |
| `+0x0f` bits 3–7, `+0x10` bit 0 | availability days | property 16; zero displays no deadline, otherwise a day count |
| `+0x10` bits 3–5 | clear condition code | property 17; known codes are Win battle, Days, and Battles |
| `+0x10` bits 6–7, `+0x11` bits 0–3 | clear count | property 18; count used by the selected clear condition |
| `+0x38` bits 0–3 | required clan-skill code | property 46; codes 1–8 select the eight named clan skills |
| `+0x38` bits 4–7, `+0x39` bits 0–2 | required clan-skill level | property 47; acceptance compares the selected clan level against it |
| `+0x41` bit 2 | cancellation allowed | property 55; selects accepted/no-cancellation text unless the mission starts immediately |
| `+0x41` bit 6 | item reward slot 1 hidden | property 61; preview displays `????` when set |
| `+0x41` bit 7 | item reward slot 2 hidden | property 62; preview displays `????` when set |
| `+0x42` bit 0 | law-card reward slot 1 hidden | property 63; preview displays `????` when set |
| `+0x42` bit 1 | law-card reward slot 2 hidden | property 64; dormant in retail, but its formatter branch executes when injected |
| `+0x39` bits 3–7, `+0x3a` bit 0 | required dispatch job | roster filter requires the canonical job code (property 48) |
| `+0x3c` bits 2–7 | blocked dispatch job | a matching canonical job returns rating 0 in `sub_080CF310` |
| `+0x3d` | dormant blocked dispatch item, −375 | rating gate is executable, but all retail entries are zero (property 53) |
| `+0x3e` | base pub information fee, ÷200 | property 54 multiplies by 200; `sub_080CEC78` applies turf pricing |
| `+0x43`/`+0x44` | dispatch threshold | 16-bit; `sub_080CF310` scores a unit against it (property 59) |
| property 42 | first required item | byte `+0x36` + 375; verified against 7 real missions |
| property 44 | second required item | byte `+0x37` + 375; same check |

Two approaches were tried and are recorded here because they look productive
and are not:

**Resolving bytes as ids proves nothing on its own.** Reading a field as a job
id gave hit rates like 368 of 368, which is meaningless: every byte below 116
resolves to some job name. The same trap applies to item ids, where the id
space runs to 629 and so swallows any byte-sized field whole. A coverage test
only discriminates when the field's range can *exceed* the candidate space.

**Sparse entries are not evidence of a small mission.** Herb Picking sets only
16 of its 70 bytes despite being a full mission with rewards, requirements and
a map, which is consistent with most of its definition living outside this
table.

The remaining fields keep positional names. In particular, `+0x45` is not a
general id echo: it matches the low mission id only through entry 122 (with one
exception) and is zero for most later entries. Naming it, or any other remaining
field, needs the same thing that worked for the required items: a function that
reads the property and does something identifiable with the value.

The corrected constant-caller sweep is now exhausted: 57 accessor call sites,
50 with recoverable constant property ids, and every constant family accounted
for above or by an already-named plain field. Seven variable-id calls remain;
they are not evidence for assigning names to the remaining positional bytes.

## The mission index at `0x08563A70`

256 records of 12 bytes, beginning with an all-zero sentinel. `+0x02` is a
halfword mission id: the 255 content records all fall inside the 512-entry
table and 220 resolve to a decoded mission name. The end is fixed by the next
table at `0x08564670`. The earlier `0x08563A7C`/255-record model omitted the
sentinel: retail code has dozens of literal-pool references to the true base,
while the only pointer inside the table starts at record 224 for a deliberate
31-record subrange.

The two leading bytes now have behavioral names:

- `+0x00` is the **world-map symbol id**. Mission availability paths take the
  mission's `+0x45` index, read this byte, and resolve that symbol's persistent
  12-byte placement record through `sub_08036330`. Location filters compare
  it directly. Executing `sub_08045400` for index record 2 reads symbol 2's
  injected placement value 17 and returns placement index 16.
- `+0x01` is the **script trigger id**. The handler at `0x08123898` receives a
  16-bit script argument, scans content records 255 down to 1 for a matching
  byte, stores the matched index, and selects its `+0x02` mission id. Executed
  anchor: trigger 1 selects index record 1 and mission 30 (`Wanted!`). Duplicate
  trigger ids deliberately resolve to the last matching record.

The focused dump names both columns. Other record fields remain positional
until their own readers establish semantics.

## Formations do not exist as a table

Worth stating plainly, because it is a negative result rather than a gap in the
search. The accessor scan covers the whole ROM and turned up no table of unit
placements, and neither gap between the known tables holds one.

They are not missing — battle setups are **scripted**. The scripting system
places units with individual opcodes: `0x1F` and `0x20` are Place Character,
taking a character id, tile coordinates on both diagonals, and a facing
direction, and opcode `0x18` covers predefined placement events. So enemy
layout lives in per-mission scripts, one placement at a time, not in a
formation table that could be dumped to CSV.

## Editing

```bash
python tools/mission_table.py dump  baserom.gba missions.csv
python tools/mission_table.py apply baserom.gba missions.csv out.gba
python tools/mission_table.py index baserom.gba mission-index.csv
python tools/mission_table.py clan-rewards baserom.gba clan-rewards.csv
python tools/mission_props.py baserom.gba          # all 65 property ids -> columns
python tools/validate_missions.py baserom.gba      # execution-backed field checks
```

Columns are named only where the code showed what a field does; the rest keep
positional names so the file still round-trips exactly. Verified: re-applying
an unedited dump reproduces the ROM byte for byte, a single field edit changes
one byte, and the game's accessor returns the edited value while still agreeing
with the raw table on all 25 plain-load properties checked.
