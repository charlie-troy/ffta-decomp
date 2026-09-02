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
| `+0x00` | custom-LZSS 4bpp tile graphics | all 162 |
| `+0x04` | tile arrangement | all 162 |
| `+0x08` | clipping tilemap | all 162 |
| `+0x0c` | palette | all 162 |
| `+0x10` | height and permissions | all 162 |
| `+0x14` | animation metadata pointer | 83 of 162 |
| `+0x18` | animation 4bpp tile pointer | 83 of 162 |
| `+0x1c` | animation VRAM destination (`0x06000020`) | 83 of 162 |
| `+0x54`, `+0x55` | primary/alternate render modes | all 162 |
| `+0x56` | shared-palette index | all 162 |
| `+0x57` | reserved zero | all 162 |

Reading `+0x54` as a halfword is misleading: `+0x55` is a separate alternate
mode, not its high byte. Their values happen to correlate strongly.

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
start `0x10` (plain BIOS LZ77) on 159 of 162 maps, while height, arrangement
and clipping usually start `0x11`. Graphics start `0x20` or `0x22`, but those
values are FFTA wrapper types rather than GBA BIOS compression identifiers.

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

## Clipping tilemap (`+0x08`)

This block uses the same `u16 destination`, `u16 byte count`, halfword-run
grammar as packed terrain, but its destinations address a two-layer visual
tilemap. Each layer is 32x64 halfwords (`0x1000` bytes):
`layer = address / 0x1000`, `x = (address % 0x40) / 2`, and
`y = (address / 0x40) % 0x40`.

The name is behavior-backed, not inherited blindly from external tooling.
`sub_0801F2EC` loads map-table `+0x08`, clears the `0x2000`-byte buffer at
`0x0200D1A0`, and calls `sub_0801EFB0` to expand its sparse runs. Render and
occlusion paths then read the two `0x1000`-byte halves; the path at
`0x0801D7A8` performs a direct zero/nonzero visibility test on a selected
entry. This also agrees with FFTAUtils' independent “clipping data” label.

All 162 logical maps decode: 156 contain local wrapped-LZ77 data and six
redirect to another map. They expose 120,448 populated logical-map entries.
Map 0 anchors the format with 112 runs and 771 entries. The CSV deliberately
calls the payload a raw `tile_descriptor`; its bit-level art meaning is not
needed to edit the clipping layer safely and is not claimed here.

## Tile graphics (`+0x00`)

The former roadmap called `0x20`/`0x22` GBA Huffman based only on the leading
byte. Retail code disproves that: the graphics loader calls FFTA's custom
decoder at `0x0800543C`. Type `0x20` places its inner stream at wrapper `+4`;
type `0x22` places it at `+8`. The inner stream begins with a big-endian u32
output size and uses six token families: literal runs, short/long/extended
back-references, zero runs, and `0xff` runs.

`tools/ffta_lz.py::map_lzss` implements that grammar with strict input, output,
and back-reference bounds. It produces a flat run of GBA 4bpp 8x8 tiles (32
bytes per tile). All 162 logical maps decode to whole tiles: 82 use wrapper
`0x20`, 80 use `0x22`, and shared pointers reduce them to 50 unique graphics
streams. The Python output byte-matches the retail decoder on all 50.

`graphics` exports those 50 unique `.4bpp` files plus a 162-row `index.csv`
containing source addresses, wrapper types, sizes, tile counts, hashes, and
filenames. `apply-graphics` uses a bounded dynamic-programming encoder over all
six token families. Every retail stream recompresses within its original
allocation (613,977 bytes total versus retail's 621,615), so edited files can
be written back without relocating adjacent ROM data. Decompressed sizes must
remain unchanged, shared pointers must agree, and any stream that grows past
its own allocation is refused. Graphics apply is atomic: if any edited stream
does not fit, no output ROM is written.

## Animation and render modes

For 83 logical maps, `+0x14` points to this metadata structure:

```text
u16 graphics_byte_count
u16 frame_count
struct frame[frame_count] {
    u16 duration
    u16 source_tile
}
```

`+0x18` points immediately after the metadata to uncompressed 4bpp frame
tiles. Each exported frame is `graphics_byte_count` bytes beginning at
`animation_tiles + source_tile * 32`. All sizes are whole tiles. The 83 maps
share 28 unique animation sets: 124 unique frames total, with four or eight
frames per set and retail duration values 8 or 10.

`+0x1c` was previously listed as a third animation pointer. Retail loader
`0x0801A2AA` proves it is instead the DMA destination: every animated map uses
VRAM address `0x06000020`. The first metadata halfword supplies the copy size,
and `+0x18` supplies the source.

The mode selector at `0x0801DB98` returns `+0x54` under the primary environment
state and, when available, `+0x55` under the alternate state. All 324
map/state selections execute and agree with those columns. These are named
primary/alternate **render modes** because the return feeds map render setup;
their remaining bit-level submodes are intentionally left numeric. The palette
loader at `0x0801A3DC` uses `+0x56` to index shared palette streams. `+0x57` is
zero on every entry.

`animations` exports a 162-row index, one metadata row per unique animation,
and 124 duration/source-indexed `.4bpp` frames.

## Editing

```bash
python tools/map_data.py table   baserom.gba maps.csv      # resolved pointers
python tools/map_data.py terrain baserom.gba terrain.csv   # every tile
python tools/map_data.py apply-terrain baserom.gba terrain.csv out.gba
python tools/map_data.py arrangement baserom.gba arrangement.csv
python tools/map_data.py apply-arrangement baserom.gba arrangement.csv out.gba
python tools/map_data.py clipping baserom.gba clipping.csv
python tools/map_data.py apply-clipping baserom.gba clipping.csv out.gba
python tools/map_data.py graphics baserom.gba graphics-dir
python tools/map_data.py apply-graphics baserom.gba graphics-dir out.gba
python tools/map_data.py animations baserom.gba animations-dir
python tools/validate_maps.py baserom.gba
```

Because compressed data must fit its original allocation, all apply commands
recompress, measure, and refuse growth. Uncompressed arrangement blocks edit
only the selected tile-id bytes. Redirected and pointer-aliased maps share
storage; conflicting edits to the same underlying value are refused.

Verified across all 162 logical maps: all three unedited CSVs and an unedited
graphics directory reproduce the ROM byte-for-byte. All 50 graphics streams
round-trip through the new encoder and fit their allocations. A one-byte map-0
tile edit survives re-read with every changed ROM byte confined to that
stream's allocation. A compressed map-0 arrangement edit fits in 2,510 of 2,511
bytes, an uncompressed map-24 edit writes its one-byte id in place, and a
map-0 permission edit fits exactly in its 137-byte terrain allocation. A
separate map-0 height edit that grew to 139 bytes was refused as designed.
Changing map 0's first clipping descriptor from `0x0160` to `0x0161` survives
re-read and recompresses to 1,483 of 1,485 available bytes.
