# Player/AI control boundary (A2)

Status: **A2.3 answered** (v46–v48, 2026-09-09): retail player turns DO
ctx-init the AI sequencer; the menu/AI split is a merged pipeline, not two
bodies. Fixture-layout correction: Marche is slot **0**. Remaining: enemy-bit7
reverse test on a non-wedged instance; A3 runner.

## Fixture chain

`outputs/lua-nav/worldmap-nat.ss0` → `engage.ss0` → `a2-battle-start.ss0`
(Marche Lv50 solo vs 6 monsters, menu open, WT 1/7). The battle-start state
reloads deterministically on fresh instances.

## Input channels (the hard-won part)

The battle menu ignores D-pad from **every** source — `emu:setKeys`, real
keyboard (UIA SendKeys), and raw KEYINPUT patches — while A/B/START/SELECT
respond. The key system explains it:

* Per-frame poll: `0x08000482–0x08000494` composes `r1 = (KEYINPUT ^ 0x3FF)` and
  calls the update function: `bl 0x0800221C` with `r0 = 0x03000000`.
* Key-state struct at **IWRAM 0x03000000**: `+0` held (u16), `+2` newly-pressed
  (u16), `+4` unconsumed-pressed (u16), `+5` enable byte, `+7` mode byte,
  `+8` consumed mask, `+0xC..+0x10` auto-repeat state.
* `update_keys` **recomputes** `+2`/`+4` from `r1` every frame, so Lua writes to
  those fields are clobbered before the UI reads them. They do work for
  out-of-battle UI (the world-map cursor moved with `tools/lua_inject_key.lua`),
  but never inside battle screens.
* The working battle input channel is **register patching**: break at the call
  site `0x08000494` and OR the wanted bits into `r1` each frame via GDB `P`
  packets. `tools/gdb_force_key.py --mask 0x80 --frames 4` moves the battle-menu
  cursor one entry. Masks: A=1 B=2 SEL=4 ST=8 RIGHT=16 LEFT=32 UP=64 DOWN=128.

### Crash trap (cost half a session)

Single-stepping into `update_keys` and resuming mid-function leaves the game in
the BIOS illegal-instruction handler (`pc=0x00000004`, stop reply `S04`). The
screen looks alive but game logic is dead; all subsequent breakpoints/injections
silently no-op. Diagnose by connecting GDB and reading the PC. Recovery: reload
a savestate. Never `s`-step through the key system; patch registers only.

## Turn manager (live capture)

* `sub_0809E05C` runs in normal battles, called from `sub_0809E1E0` at
  `lr=0x0809E261` — exactly the turn-order.md chain. 30 hits recorded in
  `outputs/lua-nav/turn-manager.json` across a Wait→enemy-turn boundary.
* Battle struct: `r0 = 0x020159E4`; `[struct+0] = 7` (unit count, matches WT x/7).
* Unit array at `struct+4`, stride **0x108**. The function rebuilds a candidate
  list per unit, gated by `0x080CD8B4` (return byte == 1) and
  `0x0812E368` (nonzero) — the controller-decision surface to decode next.
* At entry `r1` cycles over seven 4-byte records at `0x02016750..0x02016768`
  (scanned in descending order) — the caller's CT-scan loop state.
* Static (prior session): the turn loop clears the new actor's Controlled bit at
  `0x0809E272` (`sub_080CE2F0(actor, 0)`); `sub_080970E8` searches units by
  controller id; Controlled (`0xED` bit 3, duration byte = controller unit id)
  is independent of the `0x8000` side bit and of Charm/Confuse.

## Hands-off loop (A3 prerequisite, proven)

From `a2-battle-start.ss0`: inject DOWN ×2 → Wait → A ×2. Turn ends, enemies
act autonomously (Marche 442→436→438 across rounds), and Marche's menu
re-opens automatically. A runner only needs to re-confirm Wait each round.

## mGBA environment notes

* `-g` instances hang occasionally in a DMA-wait (`0x0800143C`) during boot or
  scene transitions — nondeterministic; relaunch. The title→attract-cutscene
  transition also masquerades as a hang; a START burst skips it.
* Natural boot: title → START burst ×8 (skip cutscene + open menu) → Load →
  FILE NO. 2 → world map. Savestate reloads kill setKeys D-pad on the world
  map; a full-key mash-and-release (`{1023,10}` then release) restores it.
* mGBA 0.10.5 Lua read callbacks never fire; execute callbacks and
  `emu:read16/write16/setKeys` all work.

## A2.3 verdicts (v46–v48, 2026-09-09)

**Fixture layout correction (invalidates earlier slot-6 sampling).** The roster
sits at `0x020159E8`, stride `0x108`, six live units: **slot0 = Marche**
(name ptr `0x085671EE`, CT=45 in the fixture), slot1 = first enemy
(`0x0856702F` — the address `boot_fixture_gdb.py` validates as "name0").
`0x02016018` ("slot6") is a **turn-scratch record** (RAM name ptr, ct=0), not a
unit. All "EA6/CT6" reads in v44–v46 hit a phantom; v44's bit7 flip wrote
slot1's `+0xEA`, and its post-flip silence was a wedge, not evidence.

**Dormant-boot mystery solved.** From `fix3-battle-start` the menu never
idles into auto-battle by itself; the turn loop starts only after Marche's
turn is committed. Wake recipe (v27's, reconstructed from v43's docstring):
write the forward-handout marks on slot0 — `+0xE6`/`+0xDC` = Marche id
(`+0x104`), `+0xED |= 8`, `+0xEA |= 0x80` — then drive DOWN DOWN A A with
`enable=1` (`M3000005,1:01`). With marks the battle self-plays a full round
instantly (6 seeds); without them 8/8 runs stayed frozen despite identical
drives.

**A2.3 Q1 — do retail player turns ctx-init the sequencer? YES.** v48: the
player-driven commit (A-ok at t≈7.0, Marche menu pbody at t=8.9) is followed
by a seed (`0x080C03C2`) at t=10.2. Auto-battle turns pair the same way:
scratch-record pbody burst → seed within 1.6 s (t=54.4→55.2, t=62.0→63.6),
including an enemy seed at t=55.2. Player-side and enemy turns share one
action-execution path through `sub_080C034C`.

**The pipeline model (replaces the two-body picture).** `0x0809E796` is a
**merged continuation**, not an exclusive player body. It has exactly two
in-edges (exhaustive branch scan): the bit-7 router at `0x0809E3AE→E3B8`, and
the status-housekeeping tail at `0x0809E784/788` (`+0xDB`/r6 tests — the
Haste/Slow tick per unit-flags.md). Every active turn flows through it:
bit-7 units jump in directly, all others arrive after AI housekeeping. Hence
pbody hits with `ea=0` and pb≈ai hit counts (v48) — not a contradiction.

**`+0xEA` bit 7 = menu-body router (forward handout only).**
`sub_080CDADC` = `(rec+0xEA) & 0x80`; nonzero routes the turn into the menu
body at the pick. It is **consumed at turn start on turn records** (v48 pbody
hits always show `ea=0` at hit time even when the roster byte was set), and
the auto-battler sets it transiently on scratch records while navigating
menus for player-side units (allies hit pbody with roster ea=0). Therefore
"Marche bit7 → AI" is a category error: bit7=1 routes TO the menu body — that
is the forward handout. A true reverse handout must target a different lever.

**Wedge signature and protocol rules.** A compressed turn (CT=10) opens the
actor's menu; with no commit and `enable=0` the battle freezes forever (CTs
static, no new seeds) — v47/v48's control/reverse phases wedged this way.
Rules: write `enable=1` once at attach; never leave a turn's menu undriven;
sample ticks must call `interrupt()` (a quiet free-pump never samples); keep
presses v27-faithful (5 frames at the `0x08000494` poll, CPU running between
presses); attribute pbody hits by `r7` (actor slot) — `r4` is the record.

## Next (A2.4)

1. Enemy-bit7 reverse test on a **non-wedged** instance: commit Marche's
   turn properly, then set slot1 `+0xEA` bit7 before its CT expires and watch
   whether the enemy turn produces menu-body activity (auto-navigation)
   instead of a bare seed.
2. Controlled-seam experiment: write `0xED` bit 3 + controller id on an enemy
   unit, verify the game hands control to the player (Beastmaster mechanic).
3. Write the reversible A3 runner on top of `gdb_force_key.py` + the fixture
   (wake marks + drive + idle re-confirm).
