# Dead ends

A structured log of approaches that were tried and refuted, so no session
repeats them. This is the same discipline as the "traps" list in `CLAUDE.md`
and the stuck-log in autonomous RE workflows: a refuted hypothesis that is
not written down will be re-derived, believed, and cost time again.

## How to use this file

Add an entry when a hypothesis is refuted by evidence, or after a few
fruitless probes of one approach. Each entry must name:

- **Tried** — the concrete approach, specific enough to recognize on sight.
- **Refuted by** — the observation or measurement that killed it.
- **Do not** — the rule that prevents a repeat.

Split an entry rather than inflating it: if part of the approach later worked,
say exactly which part died and which survived (see DE-010, where the
8bpp-stride tile reader died but the palette decode survived).

When a trap here generalizes beyond one incident, also consider adding a line
to the shorter invariants list in `CLAUDE.md`; this file carries the evidence,
CLAUDE.md carries the slogan.

## Index

| ID | Area | Dead end |
|---|---|---|
| DE-001 | missions | Resolving a value as an id proves nothing |
| DE-002 | missions | One data point enshrines a wrong answer |
| DE-003 | jobs | Trusting published documentation (Data Crystal) |
| DE-004 | tooling | Self-checks written against the tool's own assumptions |
| DE-005 | text | Assuming one shared string table |
| DE-006 | tooling | Heredocs corrupt Python |
| DE-007 | maps | Graphics block `0x20`/`0x22` assumed Huffman |
| DE-008 | maps | A formation table |
| DE-009 | maps | Metatile definitions read as placement tiles |
| DE-010 | maps | GBA 8bpp row stride applied to 4bpp tiles |
| DE-011 | maps | `bit 15` of a metatile entry treated as "empty" |
| DE-012 | generalizing | One traced battle turn generalized to all paths |

## Entries

### DE-001 — Resolving a value as an id proves nothing

- **Tried:** reading mission fields as job ids and counting how many resolved
  to a job name.
- **Refuted by:** hit rates like 368/368, because every byte below 116 resolves
  to *some* job name. The coverage test could not fail, so it proved nothing.
- **Do not:** trust a resolution-rate test unless the field's value range can
  exceed the candidate space. A test that cannot fail is not evidence.

### DE-002 — One data point enshrines a wrong answer

- **Tried:** naming mission `+0x34` as AP/10 from a single mission with a
  plausible reward.
- **Refuted by:** a second mission with known rewards disagreed.
- **Do not:** name a field from one example. Always find a second case before
  writing a claim into the CSV or the docs.

### DE-003 — Trusting published documentation (Data Crystal)

- **Tried:** adopting Data Crystal's published layouts directly.
- **Refuted by:** three specific, checkable errors in this project's area:
  job resistances are eight packed 3-bit slots (not four bytes), the item
  table base is one entry earlier than documented, and there are 162 maps
  (not 163 — entry 162 would start inside the table's own pointer data).
- **Do not:** skip verification because a wiki sounds authoritative. Look it
  up, then prove it against the ROM.

### DE-004 — Self-checks written against the tool's own assumptions

- **Tried:** validating `tools/dump_unit_fields.py` (instruction-pattern
  version) with a cross-check built from the same decoding assumptions.
- **Refuted by:** the check passed while the tool was substantially wrong; it
  was replaced by the 5,568-read formula gate that exercises retail code.
- **Do not:** validate a decoder with a checker that shares its assumptions.
  Execute the ROM's own code or round-trip against an independent path.

### DE-005 — Assuming one shared string table

- **Tried:** decoding ability names from the main string table.
- **Refuted by:** plausible but incorrect text — abilities index the UI table;
  items and jobs index the main one.
- **Do not:** assume id spaces are global. The wrong table decodes without
  error, so a wrong-table read is silent, not loud.

### DE-006 — Heredocs corrupt Python

- **Tried:** writing Python through `bash <<'EOF'`.
- **Refuted by:** backslash escapes mangled, producing subtly wrong scripts.
- **Do not:** create files via shell heredocs. Write the file with an editor
  or a file tool, then run it.

### DE-007 — Map graphics wrapper `0x20`/`0x22` assumed to be Huffman

- **Tried:** classifying the graphics blocks as GBA Huffman because the
  leading byte matched the BIOS type numbering pattern.
- **Refuted by:** retail loader `0x0800543C` calls FFTA's custom LZSS-family
  decoder; the Python reimplementation byte-matches the retail decoder on all
  50 unique streams.
- **Do not:** infer a compression format from a leading byte. Find the code
  that consumes the block.

### DE-008 — A formation table

- **Tried:** the roadmap once expected battle setups to reference a formation
  table.
- **Refuted by:** the ROM scan that mapped mission accessors found no such
  consumer; battles place units with scripted Place Character opcodes, one
  unit at a time.
- **Do not:** go looking for a formation table. It does not exist.

### DE-009 — Metatile definitions read as placement tiles

- **Tried (2026-09-02):** rendering map thumbnails by treating each
  arrangement `tile_id` as a direct graphics-tile index into the block's
  byte stream (`tile_id * 32`).
- **Refuted by:** placement ids run to 539 on map 0 while the region below
  `tile_format_offset` holds only ~58 tiles' worth of bytes; ids index the
  u16 metatile-entry table *at* `tile_format_offset`, whose length
  `(block_size - tile_format_offset) / 2` exactly covers every observed id
  (544 entries for max id 539 on map 0; 796 for 791 on map 2).
- **Do not:** read the arrangement block below `tile_format_offset` as tiles.
  That region is placement records; at and after the offset is the u16
  metatile-entry table (tile index bits 0-9, flips 10-11, palette bank
  12-14, bit 15 still unnamed).

### DE-010 — GBA 8bpp row stride applied to 4bpp tiles

- **Tried (2026-09-02):** decoding 4bpp tiles with an 8-row stride of 4
  bytes using only the first two bytes of each row (8bpp-style planes).
- **Refuted by:** half of every pixel row silently vanished; the tile sheet
  rendered as sparse one-pixel-wide noise while the same bytes rendered as
  coherent art under the correct 4bpp layout (8 nibbles from 4 consecutive
  bytes per row). A linear-nibble bitmap of the raw stream made the damage
  obvious by comparison.
- **Do not:** reuse an 8bpp row reader for 4bpp data. When tile output looks
  like thin vertical noise, render the raw stream as a flat bitmap first to
  separate "bad decode" from "wrong palette or layout".

### DE-011 — Metatile-entry bit 15 treated as "empty"

- **Tried (2026-09-02):** skipping placements whose metatile entry has
  bit 15 set, by analogy with palette-bank semantics (bank 8 of 5).
- **Refuted by:** the most common entries in every block (e.g. `0x9085`) set
  bit 15; skipping them gutted the composite. Entries like `0x1182` also set
  it while using low bank numbers, so it is not a palette-bit overflow.
- **Do not:** give bit 15 a rendering meaning yet. Entries with it set draw
  normally; its retail meaning is an open naming task under D-002's rule.

### DE-012 — One traced battle turn generalized to all paths

- **Tried:** treating the verified snowball-turn replay as covering mission-,
  law-, and effect-specific AI paths.
- **Refuted by:** scope, not counter-evidence: the replay covers one actor,
  four targets, one turn, one mission type. CLAUDE.md records the boundary
  explicitly.
- **Do not:** cite `docs/whole-battle-trace.md` as evidence for paths it did
  not trace. Whole-battle closure applies to the traced turn only.

### DE-013 — A position rewrite can put the tutorial AI out of range

- **Tried (2026-09-05/06):** teleporting the snowball-battle AI actor far from
  every target to force an approach-walk: `scratch_teleport_far.py` (unit
  tile + entry pixels), then `scratch_walk_force.py` (additionally
  `ctx+0x54CA/54CB`, the turn-starter queue tile that phase 8 restores from).
- **Refuted by:** the decision stayed byte-identical (handler `0x080BF7C5`,
  ability 0, rule 0) with the actor at (1,1) 10+ tiles from every target —
  `teleport-far-1-1.json`, `walk-force-1-1.json`. The snowball throw's reach
  is data-map-wide or the tutorial enemy's candidate set is degenerate (one
  command, four forced targets).
- **Do not:** spend more emulator cycles trying to make this battle's AI walk;
  it structurally cannot. A real battle (Zophar endgame save, Windows mGBA) is
  required for the live walk-site observation.

### DE-014 — WSL headless mGBA boots FFTA into a stuck intro page

- **Tried (2026-09-06):** booting baserom.gba headless under the WSL SDL mGBA
  build (dummy SDL video, Xvfb, and with the Zophar battery save) to reach the
  title/menus for input automation. Ten-plus distinct attempts, input injected
  by RAM-patching the key poll at `0x0800048A`.
- **Refuted by:** every boot wedges on the same unresponsive intro story slide
  ~40-70 s in, even untouched (keys are polled at ~20/s but A/START change
  nothing). The identical ROM/save on the **Windows Qt build**
  (`C:/Users/charl/ffta-tools/mGBA-0.10.5-win64/mGBA.exe`) boots normally and
  reaches the title when START is pressed in the first seconds; without early
  START the same unresponsive slide appears there too — so the slide is a
  real game state (the video's tail), not an emulator bug.
- **Do not:** drive FFTA boot navigation on the WSL/headless build; use the
  Windows Qt build with `-g` and the steer client
  (`tools/steer_mgba.py`). Its GDB stub accepts only one client per emulator
  session, so each boot must be driven by a single long-lived connection.

### DE-015 — Keypad register writes drive mGBA input

- **Tried (2026-09-06):** writing `0x04000130` (KEYINPUT) directly to inject
  key presses, and connecting to the GDB stub with a poll-then-close probe
  before the real client.
- **Refuted by:** mGBA ignores KEYINPUT register writes from the stub
  (readback unchanged); the only input channel is patching the game's poll at
  `0x0800048A` to report a held mask. And a connect-then-close pre-poll
  consumes the stub's initial stop packet and wedges the listener ("Connection
  lost", subsequent connects refused) — launch mGBA, sleep, then connect once.
- **Do not:** write KEYINPUT; never pre-poll the port. One client per mGBA
  session, started after the emulator is up.
