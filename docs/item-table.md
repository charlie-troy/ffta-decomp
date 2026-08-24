# The item table

376 entries of 0x20 bytes at `0x0851D180`. Id 0 is an empty "none" entry, so
the game's item ids run 1..375.

**The published base is one entry later.** Documentation gives the table as
`0x51D1A0` with 374 items. That is this table starting at entry 1, so a
published item N is the game's item N+1. The accessor `sub_080CA7A4` indexes
from `0x0851D180`, and its ids are the ones code actually passes, so those are
the ids used here and by `tools/item_table.py`.

## The accessor is unusually clean

`sub_080CA7A4(itemId, propId)` multiplies by the 0x20 stride and bounds-checks
the property id against 19. Running all 19 ids over the whole table shows
**every one is a plain byte or halfword load** -- no computed values, no packed
fields. That is the opposite of the job table, where only 16 of 45 offsets
survived the same test, and it means the static offsets can be trusted here.

```bash
python tools/map_table.py --base 0x0851D180 --stride 0x20 \
    --accessor 0x080CA7A4 --props 19 --count 376
```

| prop | offset | field | prop | offset | field |
|---|---|---|---|---|---|
| 0 | `+0x00` u16 | name_id | 10 | `+0x10` | attack |
| 1 | `+0x02` u16 | desc_id | 11 | `+0x11` | defense |
| 2 | `+0x04` u16 | buy_value | 12 | `+0x12` | magic_power |
| 3 | `+0x08` | item_type | 13 | `+0x13` | resistance |
| 4 | `+0x09` | element | 14 | `+0x14` | speed |
| 5 | `+0x0a` | range | 15 | `+0x15` | evade |
| 6 | `+0x0b` | worn | 16 | `+0x16` | move |
| 7 | `+0x0c` | flags (see below) | 17 | `+0x17` | jump |
| 8 | `+0x0d` | unknown | 18 | `+0x1d` | ability |
| 9 | `+0x0e` | unknown | | | |

`+0x06` (sell_value) and `+0x18` have no property id. `+0x0f`, `+0x19`, `+0x1e`
and `+0x1f` are zero in every real item, which supports the published reading
of them as padding.

## Two confirmations from running the code

**`+0x10` is attack power**, from two independent places. The damage path
substitutes the job's `unarmed_attack` for `sub_080CA7A4(weapon, 10)` when
nothing is equipped, and `0x0812e578` reads property 10 for two item ids and
**swaps them** when the first is smaller, which is a dual-wield routine picking
the stronger weapon as primary.

**`+0x14` is speed, and it is signed.** `sub_0812E368(unit)` reads property 14,
then halves it with `asrs` if either of two status predicates holds and doubles
it if a third does. Slow and Haste, in other words, and the arithmetic shift
says the field is treated as signed even though no retail item uses a negative
value.

## Two corrections to the published layout

**`+0x0c` is a bitfield, not a scalar.** It is listed as part of an "Unknown"
run of three bytes. The code at `0x080cacf0` calls property 7 and immediately
does `lsrs r0, #1; ands r0, #1`, testing bit 1. It takes 21 distinct values up
to 248, which is a flag byte rather than a quantity. `tools/item_table.py`
expands it into eight named bit columns so it can be edited without hex.

**`+0x06` is not derived from `+0x04`.** The first several entries have
sell_value exactly half of buy_value, which is a tempting rule. Across the
whole table it holds for only 140 of 375 items -- unpurchasable items have a
buy value of 0 and a nonzero sell value -- so the two are independent fields.

**`+0x18` is the random-item category, and 0 means "excluded".** It has no
accessor property id, so it is read by direct indexing. `sub_080CC788` draws
five random item ids with `id % 376` and keeps only those whose `+0x18` is
nonzero — the 81 items with `+0x18 = 0` are exactly the unique/quest weapons
(Victor Sword, Onion Sword, Excalibur 2, Nagrarok, Chirijiraden, the Ayvuir
pair, and so on), i.e. the ones that must never fall out of the random pool.

The 30 nonzero values classify the rest into coarser slots than `item_type`:
1–19 are the 19 weapon types (matching `item_type`), then shield (20), helm
(21), headgear (22, which merges `item_type` 22 hairwear and 23 hats), armor
(23), clothing (24), robe (25), footwear (26), gloves (27), accessory (28),
consumable (29), and a Mythril class (30) for the Mythril weapon series. So
`+0x18` is the category used for random drops/shop generation, not a stat.

## Item ids run past the stat table

The stat table holds 376 entries, but item **ids** keep going to about 629.
Loot and quest items — Wyrmstone, Rabbit Tail, Flower Vase — have names and can
be required by missions without carrying combat stats, so they have no entry
here.

Their names continue in the main string table at the offset this table implies,
`name index = id + 123`, which holds from Shortsword at id 1 through to the end
of the table. `Names.item_by_id` resolves the whole range; `item_table.py`
covers only the 376 that have stats to edit.

## Editing

```bash
python tools/item_table.py dump  baserom.gba items.csv
python tools/item_table.py apply baserom.gba items.csv ffta-mod.gba
```

Verified: re-applying an unedited dump reproduces the ROM byte for byte, and a
single field edit changes exactly one byte. Running the game's own accessor
over the modded ROM returns the edited value and still agrees with the raw
table on every other property.
