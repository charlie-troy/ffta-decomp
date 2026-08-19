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

`+0x00` holds the entry's own index, and does so on all 512 entries, which is
what fixes the count. Entry 0 is blank.

Running all 65 properties over the whole table: **35 are plain loads, 30 are
computed or packed.** Six properties (19–24) and property 32 return the
**address** of a four-byte slot inside the entry rather than a value, at
`+0x12`, `+0x16`, `+0x1a`, `+0x1e`, `+0x22` and `+0x2a`, so the caller reads
the slot itself.

## What identifies it as missions

`sub_080CEECC` reads properties 42 and 44 as halfwords, and for each one scans
a 64-entry list for a match, returning 0 if it is absent. It then reads
property 46, indexes a table with it, and compares the count found against
property 47. That is a requirement check of the form "do you hold this item,
and this one, and at least N of that one" — which is how a mission decides
whether it can be taken. Properties 42 and 44 range over 0–487 and 0–496,
consistent with item ids.

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

Properties 33–41 read nine consecutive bytes at `+0x2a`–`+0x32`, all round
multiples of 5 and 10 capped at 100, which look like weights or percentages but
are not pinned to a meaning here.

## Gil and AP are not in this table

This is established rather than assumed, and it is the most useful thing to
know before hunting for them.

Two missions have published rewards: Herb Picking gives 600 gil and 40 AP,
Thesis Hunt gives 28,600 gil and 80 AP. Searching every offset of the entry at
widths 1, 2 and 4, against scale factors of 1, 10, 100 and 1000, finds **no
field that holds both values**. Neither number appears literally anywhere in
either entry.

One hypothesis got far enough to be worth recording as dead: `+0x34` is 4 for
Herb Picking, and 40 AP divided by 10 is 4, which looks convincing on its own.
Thesis Hunt has `+0x34 = 4` as well but awards 80 AP, so the field is not AP at
any scale. A second mission killed it; a single one would have enshrined it.

So the reward figures are computed elsewhere — from mission type and rank, or
from a table this one does not contain.

## What the field-naming attempts did and did not establish

Named, with the code or the game as evidence:

| field | meaning | basis |
|---|---|---|
| `+0x00` | mission id | equals the entry index on all 512 |
| `+0x45` | id echo | mirrors the low byte of the id |
| property 42 | first required item | verified against 7 real missions |
| property 44 | second required item | same check |
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

The remaining fields keep positional names. Naming them needs the same thing
that worked for the required items: a function that reads the property and does
something identifiable with the value.

## The mission index at `0x08563A7C`

259 records of 12 bytes. `+0x02` is a halfword mission id: all 259 fall inside
the 512-entry table and 223 point at an entry that has content. `+0x01` runs
0–179 and is non-decreasing across 233 of 258 consecutive record pairs, so the
table is sorted by it; `+0x00` runs 0–30. The sorting field and the small
leading byte are not named here.

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
```

Columns are named only where the code showed what a field does; the rest keep
positional names so the file still round-trips exactly. Verified: re-applying
an unedited dump reproduces the ROM byte for byte, a single field edit changes
one byte, and the game's accessor returns the edited value while still agreeing
with the raw table on all 25 plain-load properties checked.
