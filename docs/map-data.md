# Map data

162 entries of `0x58` bytes at `0x08569104`. Each entry stores its pointers as
diffs against the table base, so an absolute address is `0x08569104 + diff`.

## There are 162 maps, not 163

Published documentation says 163, indexed `0x00`–`0xA2`. The table holds 162,
and the ROM proves it: `162 * 0x58 = 0x37B0`, and map 0's first pointer is
exactly `0x37B0`, so the table ends precisely where the first block it points
at begins. Entry 162 would start inside that data, and reading it produces
pointer diffs like `0x20380000` that fall outside the cartridge.

## Entry layout

| offset | meaning | present on |
|---|---|---|
| `+0x00` | tile graphics | all 162 |
| `+0x04` | tile arrangement | all 162 |
| `+0x08` | unknown block | all 162 |
| `+0x0c` | palette | all 162 |
| `+0x10` | height and permissions | all 162 |
| `+0x14`, `+0x18`, `+0x1c` | animation blocks | 83 of 162 |
| `+0x54`, `+0x55` | mode bytes | all 162 |

`+0x54` runs 0–24 and `+0x55` runs 0–31, which is consistent with the
published description of a byte at `+0x54` selecting among palette handling
methods. Note that reading `+0x54` as a halfword is misleading: the high half
is `+0x55`, and the pair increases across the table in a way that looks like a
pointer but is not one.

## Packed-block wrapper and redirects

Packed blocks use a four-byte dispatch header. Type `0x11` means packed and
LZ77-compressed; type `0x01` means packed and uncompressed. The following
24-bit value is either `0xffffff` for local data or another map id to reuse.
Nine logical maps redirect for both arrangement and terrain.

For local type-`0x11` data, the dispatch header is `11 FF FF FF`, followed by
a standard GBA LZ77 header (`0x10` plus a 24-bit decompressed size) and BIOS
LZ77 data. Arrangement has 113 direct compressed maps, 40 direct uncompressed
maps, and nine redirects. Terrain has 153 direct compressed maps and nine
redirects. `tools/map_data.py` resolves every variant rather than skipping the
non-LZ77 entries.

The first byte of each block type is consistent across the table: palettes
start `0x10` (plain BIOS LZ77) on 159 of 162 maps, height, arrangement and the
unknown block start `0x11` on most, and graphics start `0x20` or `0x22`, which
is the Huffman range.

`tools/ffta_lz.py` implements both directions. Round-tripping decompress ->
compress -> decompress reproduces the source data exactly.

## Tile arrangement (`+0x04`)

The decompressed block begins with a four-byte header. Its first halfword is
the offset of the 16x8 metatile-definition list; bit 6 of header byte 3 selects
16-bit rather than 8-bit placement ids. Placement records begin at byte 4:

```text
u16 destination
u8  count
u8/u16 tile_id[count]
```

A zero destination terminates the placement stream. Each tile advances the
destination by four. The destination describes a sparse 32x64 grid on each of
two layers: `x = (address % 0x80) / 4`, `y = (address / 0x80) % 0x40`, and
`layer = address / 0x2000`. All 119,749 logical-map placements are four-byte
aligned and land on layer 0 or 1.

Map 0 is the concrete anchor: 107 runs produce 770 placements (157 on layer 0,
613 on layer 1), and its metatile definitions start at `0x750`. The separate
terrain grid for the same map is 14x14. These are intentionally different
coordinate systems: arrangement stores the two-layer isometric pixels, while
terrain stores gameplay cells overlaid by the renderer. This structure agrees
with the independent [FFTAUtils map editor](https://github.com/spiiin/FFTAUtils);
our implementation is a native, guarded Python decoder rather than a port of
its C# code.

## Terrain is packed runs of two-byte cells

The old exporter incorrectly treated the decompressed height block as a flat
array. It is a sparse run stream. Each record is `u16 destination`, `u16 byte
count`, then that many bytes of `(height, permission)` cells; four zero bytes
terminate it. Destinations address a 16-column gameplay grid in bytes.

After unpacking, map 0 contains 196 explicit cells covering x/y 0–13: a 14x14
terrain grid. Its 456 decompressed bytes are encoded records and padding, not
228 terrain cells.

The permission byte uses 0 walkable, 1 impassable, 2 water, and other values
for not-selectable cells. The corrected exporter resolves and decodes all 162
logical maps, including nine redirects.

The former reported height values above 127 were packed-run destination and
length bytes misread as cells. They disappear under the correct decoder; no
height flag is implied by that evidence.

## Editing

```bash
python tools/map_data.py table   baserom.gba maps.csv      # resolved pointers
python tools/map_data.py terrain baserom.gba terrain.csv   # every tile
python tools/map_data.py apply-terrain baserom.gba terrain.csv out.gba
python tools/map_data.py arrangement baserom.gba arrangement.csv
python tools/map_data.py apply-arrangement baserom.gba arrangement.csv out.gba
python tools/validate_maps.py baserom.gba
```

Because compressed data must fit its original allocation, both apply commands
recompress, measure, and refuse growth. Uncompressed arrangement blocks edit
only the selected tile-id bytes. Redirected and pointer-aliased maps share
storage; conflicting edits to the same underlying value are refused.

Verified across all 162 logical maps: both unedited CSVs reproduce the ROM
byte-for-byte. A compressed map-0 arrangement edit fits in 2,510 of 2,511
bytes, an uncompressed map-24 edit writes its one-byte id in place, and a
map-0 permission edit fits exactly in its 137-byte terrain allocation. A
separate map-0 height edit that grew to 139 bytes was refused as designed.
