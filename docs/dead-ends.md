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

### DE-016 — Slot index and ROM-name pointers identify a battle's player

- **Tried (A2.3, 2026-09-09):** naming the battle roster by array position —
  "slot0 = Marche" because its name pointer `0x085671EE` looked protagonist-like
  and its CT was 45 — and treating any record whose name pointer was not in ROM
  (`0x02016018`, "slot6") as turn scratch rather than a unit.
- **Refuted by:** A2.4a live reads (2026-09-10). `0x085671EE` decodes to `Jon`,
  an **enemy** clan member; the seven-unit array at `0x020159E8` is five
  enemies (0x8000 set), the neutral Judge, and **Marche at slot6**, whose name
  pointer `0x02001F1C` is in EWRAM because the player's name is save data. The
  "scratch" record has level 50, 442 max HP and id 6. Sequencer context
  pointers at `0x080C03C2` reference a *second* array (`0x02002FC4`) that omits
  Marche entirely, so slot indexes do not even name the same units across
  arrays.
- **Do not:** infer role from array position, or treat a non-ROM name pointer
  as scratch. Identify a unit by decoding its name from either ROM or EWRAM,
  and attribute an observed actor by that name, never by slot index.

### DE-017 — Relative paths handed to a launched emulator

- **Tried (A2.4a tooling, 2026-09-10):** launching mGBA with a relative
  `--savestate`/ROM path while also setting the child's `cwd` to the scratch
  directory, after copying the fixtures there.
- **Refuted by:** mGBA resolves its file arguments against its own working
  directory, so the child looked for
  `<scratch>/<scratch>/<fixture>` — nothing loaded, the GDB stub came up but
  never answered `\x03`, and the symptom looked exactly like the known
  nondeterministic `-g` boot flake (three relaunches, same result).
- **Do not:** pass relative paths to a child process launched with a different
  `cwd`. Absolutize every path at the tool boundary, and before blaming a flake,
  check that the child actually loaded its inputs.

### DE-018 — Reading a status bit as the player/AI control seam

- **Tried (A2.3, then tested in A2.4b, 2026-09-10):** treating `+0xEA` bit 7 as
  the "menu-body router / forward handout", so that setting it on an actor would
  hand that turn to the player menu (`sub_080CDADC` at `0x0809E3AE`).
- **Refuted by:** `sub_080CDADC` is the `+0xEA` bit 7 getter for **Stop**
  (`docs/unit-flags.md`), and the branch at `0x0809E3AE` is a Stop skip, not a
  menu. Live on `battle-start.ss0`, all seven units — the five enemies, the
  Judge and the player Marche — reach the router with `+0xEA = 0` and take
  `0x0809E3BA`; every turn then reaches the shared tail `0x0809E796`
  (`tail hits == router hits`), so that tail is a common continuation and not a
  player body. Forcing bit7 on one enemy moved exactly that one turn to
  `0x0809E3B8` and changed nothing else; the game's own countdown cleared it.
  Evidence: `outputs/autobattle/A2.4b/slice1-bit7.json`.
- **Do not:** infer a control seam from a branch a status getter feeds. Name the
  bit from its setter/duration/consumers first, and check the branch is
  side-discriminating by logging the branch for **every** actor, player included.

### DE-019 — Pre-setting Controlled (`+0xED` bit 3) as a persistent handoff

- **Tried (A2.4b, 2026-09-10):** writing `+0xED` bit 3 plus the controller id
  in `+0xE6` on an enemy to hand that enemy's turn to the player (the
  Beastmaster "Control" mechanic), at boot, immediately before, and immediately
  after the turn-start clear.
- **Refuted by:** `0x0809E272` (`sub_080CE2F0(actor, 0)`) clears bit 3 at the
  actor's turn start. Written at boot, the bit is gone before the turn loop
  reads it; written immediately before the clear, the clear consumes it in the
  same instruction (`ed_after = 0`); written immediately after, it survives to
  the router (`ed = 8`, `e6 = 6`) but the branch is still `ai_path`, the enemy
  still acts, and the end CT vector is byte-identical to the natural baseline.
  Evidence: `outputs/autobattle/A2.4b/slice2-controlled-pc.json`.
- **Do not:** treat Controlled as a durable delegation flag. It is a same-turn
  marker with a controller id in `+0xE6`, cleared from its own consumer at turn
  start, and it does not change the router's side-agnostic decision.


### DE-020 — Single-key input at a battle menu boundary

- **Tried (A2.5, 2026-09-15):** pressing one key to satisfy an open command
  menu — a bare A to "commit" (runs 4, 10-13 pre-fix) and frames=1 A/B
  injections in a freeze-recovery ladder (runs 16-17).
- **Refuted by:** the run 17 wedge screenshot shows the command menu open
  while every frames=1 press landed (`x1`) and changed nothing — a single
  key-poll injection does not register with the menu; and the run 4 wedge
  shows a bare A selects Move and leaves the move-target modal open, which
  stops the turn driver (frozen CTs, seed silence). The only shape that has
  ever committed is the full route DOWN, DOWN, A, A at frames=5 (`x5` hits).
- **Do not:** try to close or satisfy a menu with single keys, and never
  deliver a partial route. If presses land but the engine state is
  unchanged, suspect the wrong UI state — get a screenshot onto the primary
  monitor (DE-021) before pressing anything else.

### DE-021 — Trusting CopyFromScreen screenshots in a multi-monitor setup

- **Tried (A2.5, 2026-09-15):** diagnosing engine states from in-run
  screenshots while mGBA sat on the secondary portrait monitor. Frames came
  back as desktop pixels (six byte-identical captures across one run; a
  "battle teardown" reading that was actually the wallpaper).
- **Refuted by:** the GL surface on that monitor does not composite into
  screen captures at all — GetWindowRect/ClientToScreen report the right
  rect, focus sticks, and the capture is still not the game. The same window
  moved to the primary monitor captures perfectly (run 17 onward: real menu
  frames that immediately decoded two wedges).
- **Do not:** treat a screenshot as evidence without validating it
  (distinct-row hashing: an occluded or void frame collapses to a
  near-constant row set). Run the emulator on the primary monitor;
  `FixtureSession` now enforces this at boot.


### DE-022 — Counting probe reads as engine time

- **Tried (A3, 2026-09-16):** the offline transport fake advanced its engine
  one frame per probe-visible read. The probe's polling loops read memory
  thousands of times per second, so the fake clock ran ~1,650x real time:
  CTs saturated in under a second, menus "re-opened" as phantoms mid-charge,
  seed stops buried under a million stale queue entries, and every engine
  cadence the runtime classifies on (settle times, seed intervals, stall
  windows) was silently warped. Scenarios passed or failed based on read
  scheduling, not engine semantics.
- **Refuted by:** on hardware the engine advances in real time regardless of
  when the probe looks. Rebuilt the fake on a wall-clock ticker (60 fps
  frames, recorded ~12.9 CT/s, input consumed as a one-write-per-poll FIFO
  with per-frame edge detection); every scenario then reproduced its recorded
  shape without timing knobs.
- **Do not:** let fake-engine progress be a function of observation frequency.
  Any offline model of a real-time engine needs a wall-clock heartbeat.

### DE-023 — Single B press backed out two menu layers

- **Tried (A3, 2026-09-16):** in the first submenu-recovery run, one held B
  press closed both the submenu and the parent command menu, stranding the
  unit on the map and eating the re-drive route. Root cause was in the fake:
  the B branch fired on every held frame because only A was edge-detected.
- **Refuted by:** making B edge-detected like A (one press = one edge = one
  menu layer). On hardware the engine navigates on key-down; a 5-frame press
  must not count as five B taps.
- **Do not:** fire per-held-frame input effects for any key; edge-detect
  every press in a per-poll input model.

### DE-024 — The scripting console freezes a stub-attached boot

- **Tried (A8, 2026-09-22):** to calibrate emulated time independently of
  the CT trajectory, drove the mGBA scripting console via the UIA bridge
  (`uia_lua2.ps1`): open console, `dofile` a driver, read results. Every
  attempt on a stub-attached boot died the same way: the FIRST console
  command returns its reply, and from that instant the emulated core is
  frozen — `emu:currentFrame` and every memory read return identical
  values minutes later, while the process still answers.
- **Refuted by:** nonce-tagged diagnostic (`tools/lua_a8_nonce.lua`,
  `tools/diag_a8_sample.py`): three samples with distinct nonces all
  parsed with correct nonces (bridge/log path healthy), and B/C came
  60+ s later at the *same* frame with CT 0 — core frozen, channel fine.
  A boot with the console never touched runs normally (v5's GDB
  measurements).
- **Amended (2026-09-22):** the escape hatch does not exist either — a
  stub-FREE boot hung the same UIA bridge (first sample call, 120 s
  timeout, no reply). The bridge is unreliable in every observed
  context; the console is dead as a measurement channel on this setup,
  not merely incompatible with the stub.
- **Do not:** mix the scripting console with a GDB-attached core on this
  build, and do not plan on console reads as a calibration fallback —
  use the GDB channel (v7's frame-exact method) for emulated-time work.

### DE-025 — IO-register writes via the stub are silently discarded

- **Tried (A8, 2026-09-22):** to build an emulated-cycle clock, armed the
  idle GBA timers TM2/TM3 (`0x04000108+`) via stub `write_bytes`: TM2
  prescalar 1024, TM3 cascade — 32-bit emulated time readable over the
  stub with no console and no detach.
- **Refuted by:** the stub replies `OK` to every width (byte/halfword/
  word) and RAM writes land, but IO reads back unchanged: DISPCNT is
  invariant under an inverted-value write, and timer control registers
  stay 0x0000 after arming. IO writes never reach the memory core.
- **Do not:** expect stub writes to affect memory-mapped IO on this
  build; treat IO as read-only through the stub.

### DE-026 — Stub reads over 512 bytes fail silently

- **Tried (A8, 2026-09-22):** one-shot whole-roster blob reads
  (8 slots x 0x108 = 2112 bytes) for identity-anchored CT scans;
  `read_mem` returned None with no exception for anything over 512
  bytes while 512 and below succeed.
- **Refuted by:** bisection against a live boot (`512 -> 512 bytes,
  1024 -> None`). The per-field helper reads that desync (roster-diag)
  each did their own halt/cont; the fix is sub-reads inside ONE
  halt/cont pair, which stays a consistent instant.
- **Do not:** request >512-byte memory reads from this stub; chunk
  inside a single interrupt window instead.

### DE-027 — The battle roster array is scratch between turn-order phases

- **Tried (A8, 2026-09-22):** to track Marche across a charging window by
  identity, repeatedly decoded the 8-slot roster at `0x020159E8` (name
  pointer + CT per slot, one halt window per scan). Immediately after an
  identified-Wait commit the array is fully populated; seconds later it
  reads as zeros/garbage, then rebuilds — with Marche back at slot 6 —
  several times per minute.
- **Refuted by:** time-series diagnostic (45 s of scans after the
  commit): valid windows (6–7 named slots) alternate with scratch
  windows (0–1 named slots) on a multi-second cadence; v4's "mostly
  zeros with spikes" trajectory was the same array being read across
  scratch windows. Fixed-slot reads without validity checks average
  scratch values into measurements.
- **Do not:** treat a successful roster decode as a live roster. Require
  a named-slot validity gate before using any slot, and retry identity
  matching across windows.
- **Amended (2026-09-22, v7 calibration):** the "scratch" verdict is
  REFUTED for the array's CT data. The v4/v5 garbage was the multi-read
  desync law (DE-013's halt/cont discipline), not array invalidation: a
  SINGLE 2-byte read at slot6's CT (`0x020162F8`) tracks a coherent
  monotone curve through the whole cycle — 296 -> 310 -> 535 -> 998 ->
  wrap -> next cycle 253 -> 415 — with none of the "zeros with spikes"
  v4 saw from 2-byte reads inside multi-slot scans. What IS true: bulk
  multi-slot decodes inside one halt window desync and produce garbage;
  the CT datum read singly is reliable, and `CT_BASE` is the anchor for
  any Marche-CT measurement. Identity (name pointer) verification of
  OTHER fields still requires the valid-window gates above.

### DE-028 — One stray reply offsets every later exchange (self-sustaining)

- **Tried (A8, 2026-10-05):** v11's free-run T phase read CT with
  `interrupt()` + `read_mem` after a clear/arm/disarm burn; every read
  returned None ("3 consecutive CT read failures" on all 4 boots), and
  packet-level tracing (`tools/diag_t_phase3.py`) showed
  `interrupt()` returning mem data (`bc00`) where the stop reply
  should be.
- **Refuted by:** the byte-level sniffer (`tools/diag_t_phase4.py`):
  every command gets `+` + one reply, raw `0x03` gets one un-acked
  `S02`, `c` gets only `+`. One stray reply (here an `OK` left by the
  retry-until-OK burn) makes `send()` consume the PREVIOUS reply; from
  then on every exchange reports one reply late, and since each send
  still produces exactly one reply, the offset never heals by itself.
  `interrupt()` is hit hardest because it needs ITS stop reply
  specifically. The cure is a pump: `{send 'm'; raw-drain the socket}`
  until two consecutive drains come back empty — an empty drain after a
  send that blocked for its own reply proves buffer and kernel are both
  drained (`drain_paired` in `tools/probe_a8_speed.py`).
- **Do not:** debug shifted streams by retrying reads (retries consume
  nothing while the offset persists); drain with raw recvs instead, and
  never call `interrupt()` on a stream whose pairing was not proven
  after the last non-standard send.

### DE-029 — A served stub read implicitly halts the core; only 'c' resumes it

- **Tried (A8, 2026-10-05):** free-run CT polling without any continue:
  `tools/diag_t_phase2.py` polled every ~20 ms (147 reads over 3 s, all
  the park value 296), and the first v12 T run polled every 250 ms the
  same way (`tools/probe_a8_speed.py` before the cont-after-read fix):
  CT read 188 at the first poll and stayed at 188 for the whole 60 s
  budget — 234 windows, last_ct=188 — as if the event never charged.
  The cadence difference (20 ms vs 250 ms) changed nothing, which
  killed the initial "poll floods starve the core" reading.
- **Refuted by:** `tools/diag_t_phase4.py` window structure: every
  window in that trace starts with 'c', idles, then reads — and the
  values advance exactly as the traced waveform (188 at +1 s, 0 at
  +1.5 s). Removing the 'c' freezes the value regardless of gap size:
  the read itself pauses the core and the pause persists until the
  next continue (mGBA serves the read from the just-halted instant,
  freshly). This is the same halt/cont discipline DE-013 established,
  now known to be triggered by reads themselves, not only by explicit
  interrupts.
- **Do not:** count wall time between bare reads as emulated time —
  resume with `c` after every read and bracket the event from
  cont/read timestamp pairs (the T phase's running windows), not from
  poll arrival times alone.

### DE-030 — CT cannot name the menu owner on a multi-ally fixture

- **Tried (A4 demo, 2026-10-05):** owner attribution by CT park: the
  rule that worked on the solo fixture — the turn-ready 1000 flash plus
  a stable park at `ct <= PARK_CT_MAX` (300) — was carried onto the
  two-ally fixture. Demo run 2 used it on two consecutive menus.
- **Refuted by:** the engine's own answer. Run 2's rule named
  Montblanc for menu 1 and Marche for menu 2 — both wrong. The commits
  were engine-correct (the engine always moves the unit whose menu is
  open), and the full-snapshot tile delta showed it: menu 1 moved
  slot 7 `(4,10) -> (4,11)` while the label said slot 5, menu 2 moved
  slot 5 `(5,10) -> (5,11)` while the label said slot 7. The CT trace
  explains the swap: **the real owner parks ABOVE `PARK_CT_MAX`**
  (306 and 353 observed across the two menus) while the *frozen* ally
  sits stable at 0 — so `flash ∩ parked` selected exactly the
  non-owner both times. A 1000-flash alone is also not owner proof:
  both allies flashed within the same wait.
- **Cure:** the owner is read from the engine itself — at a freshly
  opened menu `TARGET_X/Y` reads the **owner's own tile** (the C2 law),
  so the owner is the live player slot standing on the cursor tile,
  matched across two ticks with tiles populated and at least one slot
  byte-stable as settle gates, and with already-committed allies
  excluded so a stale cursor cannot mislabel the next menu
  (`wait_menu` in `tools/a4_divergence_demo.py`). The full-snapshot
  `moved_slots` delta is the independent cross-check: engine moves the
  menu owner, nobody else.
- **Do not:** attribute menu ownership from absolute CT thresholds or
  turn-ready flashes on fixtures with more than one player unit; the
  park value is unit-specific and the frozen ally can be the "stable
  low" one. Trust a tile delta or the engine's own cursor.

### DE-031 — The R shoulder does not switch the pedestal unit in dispatch

- **Tried (A4 fixture build, 2026-10-05):** three build attempts used
  the R shoulder (`0x100`) to cycle the pedestal member in the
  placement screen between placing the first and second ally.
- **Refuted by:** the pinned route — the pedestal cycles on **D-pad
  RIGHT (`0x10`)**. With R the route re-picked the same member, the
  second placement overwrote the first, and the built state failed the
  two-player guard (`players=1`) each time. After switching to
  D-pad RIGHT the build passed `--verify` on the first run
  (`players_same_job=true`, `enemy_same_job=true`).
- **Do not:** assume shoulder buttons mirror list-cursor D-pad
  semantics on this screen; probe the D-pad first, and always
  round-trip the built state through the guard before citing it as a
  fixture.

### DE-032 — The battle struct is scratch for ~10 s after a turn closes

- **Tried (A5.1 same-process resume, 2026-10-06):** after the manual layer
  committed its window Move+Wait, `--resume` adopted the same pid but the
  roster guard failed — `struct_count=328201`, `slot0 name=0x40309`,
  all seven required checks failing. Two false leads followed: "the
  window input damaged the battle memory" and "the stub is desynced
  (DE-028)"; a `drain_paired` cure was tried and changed nothing.
- **Refuted by two read-only probes.** `tools/diag_a51_hold.py` held a
  stub client for 40 s with **no input at all**: the roster stayed perfect
  (count=7, all seven names, Marche still on (4,10)) and the ROM header
  stayed byte-identical, so neither the client nor elapsed time is the
  cause and the stream is aligned. `tools/diag_a51_manual_watch.py` then
  replayed the manual route key by key through the real window channel and
  showed the transition exactly: healthy until the Wait committed, then
  `count=7 → 328201 → 328711 → 7 again` about 14 s later, with Marche's
  tile already mirrored to (4,11). The address is reused as scratch during
  the post-turn transition and restored afterwards.
- **Cure:** `FixtureSession.adopt_existing` retries the roster guard to a
  45 s bound and records every attempt (`adopt_attempts` in the guard
  receipt; the resumed run receipt carries `adopt.guard_attempts`). Each
  retry must also **send `c`**: a served read halts the core (DE-029), so a
  retry loop that only re-reads freezes the engine inside the transition
  forever — observed live as 16 attempts returning the identical scratch
  bytes until the `cont` was added. With both, the live resume reported
  `roster guard ok after 3 attempt(s)` on pid 44528 and drove on from the
  manually walked tile.
- **Do not:** read a roster-shape failure in the seconds after a turn
  closes as a wrong emulator, a damaged battle or a stream desync; and
  never retry a live guard by re-reading alone.
