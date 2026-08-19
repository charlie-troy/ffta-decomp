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

## The blocks are compressed, and the format is decodable

Each block opens with the four bytes `11 FF FF FF`, then a **standard GBA LZ77
header** — `0x10` followed by a 24-bit decompressed size — and then ordinary
BIOS LZ77 data. The leading `0x11` is the BIOS call number the game uses to
unpack it, which is why it appears where a compression type byte would.

The first byte of each block type is consistent across the table: palettes
start `0x10` (plain BIOS LZ77) on 159 of 162 maps, height, arrangement and the
unknown block start `0x11` on most, and graphics start `0x20` or `0x22`, which
is the Huffman range.

`tools/ffta_lz.py` implements both directions. Round-tripping decompress ->
compress -> decompress reproduces the data exactly on every map sampled.

## Terrain is two bytes a tile

Decompressed, the height block is a flat run of `(height, permission)` pairs.
Map 0 declares 456 bytes and produces exactly 456, giving 228 tiles.

The permission byte matches the published reading on all 28,222 tiles across
the 153 decodable maps: 0 walkable, 1 impassable, 2 water, anything else not
selectable. Values 0, 1 and 2 account for 95.8%, and the remainder are 3, 4, 8
and 9, which the published "other values" case covers.

Heights fall in the documented 0–99 range for 96.7% of tiles. The exceptions
are worth knowing about before trusting the field blindly: in map 0 they sit at
tile indices 64, 80, 96, 112, 192 and 208 — every sixteenth tile — and hold
128, 160, 192 and 224, all of which have bit 7 set. That regular spacing and
the set high bit suggest the byte carries a flag rather than a height in those
positions. This is not established, so treat a height above 127 as unexplained
rather than as elevation.

Nine of the 162 maps do not carry the `11 FF FF FF` header on their height
block and are skipped by the tooling rather than guessed at.

## Editing

```bash
python tools/map_data.py table   baserom.gba maps.csv      # resolved pointers
python tools/map_data.py terrain baserom.gba terrain.csv   # every tile
python tools/map_data.py apply-terrain baserom.gba terrain.csv out.gba
```

Because the data is compressed, a rewritten block has to fit the space the
original used. `apply-terrain` recompresses, measures the original block's true
length, and **refuses any map that grew** rather than overrunning into the next
block. Nothing outside the edited block is touched.

Verified: applying an unedited dump produces a byte-identical ROM. Editing ten
tiles of map 0 recompressed to 133 bytes against 137 available, changed 108
bytes, and every one of them fell inside that map's height block.
