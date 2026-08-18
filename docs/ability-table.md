# Ability table

Base `0x0855187C`, stride **0x1C** (28 bytes), **347 entries** (entry 0 is a
null row). Columns come from `sub_080CCD50(abilityId, propId)`, which resolves
a property either as a direct column load or as a bit of the flag word.
Regenerate with `python tools/dump_ability_props.py <rom>`.

## Confirmed from code

| column | width | prop | meaning | evidence |
|---|---|---|---|---|
| `+0x03` | u8 | none | **AP cost / 10** | stored value x10 is the in-game AP; verified against 19 published abilities |
| `+0x04` | u8 | `0x02` | **MP cost** | `sub_0812ED98` reads prop 2 as the cost and the AI compares it against unit MP (`+0x1C`); verified against 19 published abilities |
| `+0x0B` | u8 | `0x21` | **Power** | verified against 19 published abilities |
| `+0x10` | u32 | `0x0B`-`0x1F` | **flag word**, 21 bits | prop id `n` tests bit `n - 0x0B` |
| `+0x0C` | ptr | `0x09` | sub-structure | the property handler returns an address, not a value |
| `+0x19` | u8 | none | **AI class**; 2 = harmful status/debuff | ids 13, 14 and 18 (Judge, Break, Blind) are class 2 while damage and healing are class 1; not reachable through the property API |

## Candidates, by evidence

These are not confirmed. Value profiles over all 347 entries:

| column | width | prop | range | distinct | most common | reading |
|---|---|---|---|---|---|---|
| `+0x00` | u16 | 0x00 | 0-542 | 335 | near-unique | name/text id |
| `+0x03` | u8 | - | 1-100 | 5 | 20, 10, 30, 100 | tier or rate; only 5 round values |
| `+0x0B` | u8 | 0x21 | 0-100 | 24 | 0, 40, 30, 50 | cost or rate; round values |
| `+0x14` | u16 | 0x20 | 0-341 | 340 | near-unique, near-sequential | secondary index, tracks entry number |
| `+0x16` | u8 | - | 0-255 | 256 | uniform | id or hash, uses the full byte |
| `+0x17` | u8 | - | 0-1 | 2 | 203 zero / 144 one | boolean |
| `+0x1A` | u8 | - | 0-100 | 13 | 30, 80, 0, 60 | **accuracy** is the natural reading |
| `+0x1B` | u8 | - | 0 | 1 | always zero | padding |

## Flag word bits

Bits 1-4 are never set in any entry, so 17 of the 21 are live. The AI reads
props `0x11`, `0x12` and `0x13`, which are bits 6, 7 and 8.

| bit | prop | set in | note |
|---|---|---|---|
| 0 | `0x0b` | 104/347 |  |
| 1 | `0x0c` | 0/347 | never set |
| 2 | `0x0d` | 0/347 | never set |
| 3 | `0x0e` | 0/347 | never set |
| 4 | `0x0f` | 0/347 | never set |
| 5 | `0x10` | 236/347 |  |
| 6 | `0x11` | 7/347 | **read by the AI** |
| 7 | `0x12` | 27/347 | **read by the AI** |
| 8 | `0x13` | 92/347 | **read by the AI** |
| 9 | `0x14` | 212/347 |  |
| 10 | `0x15` | 55/347 |  |
| 11 | `0x16` | 20/347 |  |
| 12 | `0x17` | 145/347 |  |
| 13 | `0x18` | 308/347 |  |
| 14 | `0x19` | 246/347 |  |
| 15 | `0x1a` | 42/347 |  |
| 16 | `0x1b` | 2/347 |  |
| 17 | `0x1c` | 71/347 |  |
| 18 | `0x1d` | 94/347 |  |
| 19 | `0x1e` | 55/347 |  |
| 20 | `0x1f` | 327/347 |  |

## First entries

Ability id is the entry index, so these can be checked against known abilities.

| id | +0x00 | +0x03 | +0x04 MP | +0x0B | +0x14 | +0x19 AI | +0x1A |
|---|---|---|---|---|---|---|---|
| 1 | 267 | 10 | 6 | 40 | 2 | 1 | 80 |
| 2 | 269 | 20 | 10 | 60 | 3 | 1 | 65 |
| 3 | 268 | 30 | 16 | 80 | 4 | 1 | 50 |
| 4 | 218 | 20 | 18 | 0 | 5 | 1 | 100 |
| 5 | 497 | 20 | 10 | 90 | 6 | 1 | 100 |
| 6 | 201 | 30 | 20 | 100 | 7 | 1 | 100 |
| 7 | 496 | 20 | 16 | 0 | 8 | 1 | 40 |
| 8 | 292 | 10 | 6 | 0 | 9 | 1 | 20 |
| 9 | 429 | 10 | 6 | 0 | 10 | 1 | 20 |
| 10 | 348 | 20 | 12 | 0 | 11 | 1 | 30 |
| 11 | 441 | 30 | 32 | 50 | 12 | 1 | 30 |
| 12 | 385 | 30 | 10 | 0 | 13 | 1 | 20 |

## How the names were settled

Cross-referenced against the published ability data on
[Data Crystal](https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance/Abilities),
which documents the same table at the same offset with the same 0x1C stride.
For ability ids 1-19, `+0x03 * 10` matches the published AP cost and `+0x0B`
matches the published Power on every entry, which settles both columns.

`+0x1A` remains unidentified: Data Crystal does not document a hit-rate field,
and its value profile (0-100, clustering on 30/60/70/80) is consistent with
accuracy but not proven.
