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

`+0x3d` (property 53) goes through the same `sub_080CB4A4` remap, so it is a
third quest-item slot — but it is 0 in all 512 missions, i.e. unused data.

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
| `+0x2d` | 36 | Appraise skill points |
| `+0x2e` | 37 | Gather skill points |
| `+0x2f` | 38 | Smithing skill points |
| `+0x30` | 39 | Craft skill points |
| `+0x31` | 40 | Negotiate skill points |
| `+0x32` | 41 | Track skill points |

The code path is direct. `sub_08046850(mission, ..., index, ...)` adds
`mission[+0x2a + index]` to the matching level-progress byte in the nine-pair
clan state at `0x020021B4`; reaching 100 advances that level. The completion
renderer `sub_080461D4` labels `+0x2a` as `Clan Pts:` and draws the eight skill
levels in the same order used by the
[official manual](https://www.nintendo.com/eu/media/downloads/games_8/emanuals/game_boy_advance_8/Manual_GameBoyAdvance_FinalFantasyTacticsAdvance_EN_DE_FR_ES_IT.pdf).
The standalone validator runs 4,608 accessor reads and then executes
`sub_08046850` once for every track, proving that each byte reaches its matching
progress counter.

They are not dispatch-calculator weights. `sub_080CF310` never reads this
block; it uses the separate dispatch threshold at `+0x43/+0x44`.

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

`+0x3e` is a second 200-unit field: accessor property 54 does the same ×0xC8
multiply. `sub_080CEC78` reads it as a base amount and returns
`base ± base × factor/100`, where the factor comes from two per-index tables
(96-byte and 12-byte records), so it is a gil-valued quantity that receives a
percentage adjustment. Its exact game meaning is still open, not a reward
claim.

## Dispatch rating (`sub_080CF310`)

This function scores a unit against a mission and returns a 1–5 rating, which
is how the game judges a dispatched unit before a non-battle mission resolves.

- It first checks two hard gates and returns 0 (unusable) if either fails:
  `+0x3c` bits 2–7 are compared against `sub_080C93F0(unit[+7])` — a job/race
  requirement — and `+0x3d` (the quest-item remap) is checked against two item
  slots on the dispatch record.
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
| `+0x3c` bits 2–7 | job/race requirement | `sub_080CF310` compares it against `sub_080C93F0(unit[+7])` |
| `+0x43`/`+0x44` | dispatch threshold | 16-bit; `sub_080CF310` scores a unit against it (property 59) |
| property 42 | first required item | byte `+0x36` + 375; verified against 7 real missions |
| property 44 | second required item | byte `+0x37` + 375; same check |
| properties 46, 47 | a count requirement | the same function compares them |

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

## The mission index at `0x08563A7C`

255 records of 12 bytes. `+0x02` is a halfword mission id: all 255 fall inside
the 512-entry table and 220 resolve to a decoded mission name. The end is
fixed by the next table at `0x08564670`, which has 25 direct literal-pool
references in code. An earlier 259-record count incorrectly consumed four
records from that next structure.

`+0x01` runs 0–179 and is non-decreasing across most consecutive record pairs;
`+0x00` runs 0–30. Those shapes suggest ordering/grouping data, but neither is
named here: no identified reader yet proves what the values mean. The dump
keeps all remaining bytes positional for the same reason.

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
