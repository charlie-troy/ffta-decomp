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

Properties 33–41 read nine consecutive bytes at `+0x2a`–`+0x32`, all round
multiples of 5 and 10 capped at 100, which look like weights or percentages but
are not pinned to a meaning here.

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
