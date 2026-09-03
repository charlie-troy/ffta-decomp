# The m4a/MP2K audio driver

The ROM's audio engine is Nintendo's stock MP2K/m4a driver, the same engine
pret has fully decompiled for Pokémon Ruby/Sapphire/Emerald. It is identified
here and **deliberately excluded from the decompilation target**: like libgcc's
`__negdi2` (see `nonmatching/README.md`), it is known library code, not game
logic. Re-deriving it would duplicate pokeemerald's `m4a/` for no modding
value; music mods need the data formats, which are documented below.

Identified 2026-09-02 by literal-pool scan, entry-format validation, and
 Thumb instruction decoding against the ROM (evidence inline).

## Code region

| | |
|---|---|
| Range | `0x08141500` – `0x081458AC` (file `0x141500`–`0x1458AC`) |
| Discovered functions inside | 94 (`sub_08141500` … `sub_08145834`) |
| Bytes | 10,880, none of them matched, none to be matched |
| Entered by | SWI-callable API and the IRQ handler; **zero** direct BL calls from game code |

The zero-external-callers property is what makes the island provable: every
entry point reachable from game code is one of the `swi 0x0A..0x0F` stubs at
`0x08141860`–`0x08141874` (one `swi` + `bx r3` each, the standard m4a SDK
trampoline), plus the pointer-based `sub_08141500`/`sub_08141520` pair called
by the sound-task code at `0x080DFE3E`, `0x080DFE82`, and the 484 callers of
`sub_08141540` (the `m4aMPlayStart`-shaped API: loads the table, scales the
song number by 8, bounds-checks, then chases the header pointer).

Known sub-names follow pret's pokeemerald `m4a/` naming and are recorded in
`data/sym_driver_fns.txt` as intent-to-name, not yet linker symbols.

## Data formats (the modding surface)

**Song table — `gSongTable` at `0x0814BB48`, 640 entries, 8 bytes each.**
Validated every entry: each is `{ u32 song header pointer; u8 ms; u8 me;
u16 zero }`, with `ms`/`me` the mid-screen/mid-frame play slots (0–16) and
padding always zero. Entries 0–99 use direct song headers; most battle and
scene tracks carry `ms=2, me=2` or `ms=1, me=1`. The table ends exactly at
`0x0814CF48`, whose own word is the header pointer of the first entry that
follows the original 100 in an earlier count — the "640 entries" in the README
is 8-byte entries, not 4-byte words.

The table is preceded by the **player table** (`gMPlayTable`) at `0x0814BB24`:
three 12-byte `MusicPlayerInfo` records (`{track pointer, part pointer,
0x10}/{…0x06}/{…0x03}` pattern), filling the gap between the last code bytes
and the song table.

**Song header** (what a table entry points at), 16 bytes:
`u8 trackCount; u8 blockId; u8 priority; u8 reverb; u32 toneGroup; u32
sequence; u32 voices`. Entry 0 decodes as 12 tracks, block 0, priority 1,
reverb 0xA8, tone group `0x0814A004`, sequence `0x083337E4`, voices
`0x0833394C`. The tone group sits *inside* the code region at `0x0814A004`,
so the sound font (instrument bank) region begins there; sample data runs
from `0x08333xxx` upward, interleaved per song.

**Voice group**: standard MP2K `{count, records[n]}` with 16-byte records for
direct/drum, 12 for square, 4 for noise — the layout pokeemerald's tools
already parse.

Modding consequence: song numbers are just indices into `gSongTable`, so
replacing a track is an 8-byte edit (header pointer + ms/me) once the
replacement song and its font exist. No code changes are required.

## What is deliberately not here

- No attempt to name all 94 driver functions in this repo; pokeemerald's
  `m4a/` is the reference implementation of the same engine.
- No re-derivation of the mixer, envelope, or CGB channels; the frozen-RNG
  battle traces run with audio present and never touch this island's
  behavior.
- The interrupt vectors the driver hooks (`m4a's VBlank work) are runtime
  state, not ROM data; the IRQ dispatcher analysis lives in
  `docs/turn-order.md`'s engine notes.
