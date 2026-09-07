# Player/AI control boundary (A2)

Status: **turn-manager instrumented in a live normal battle**; input channel
solved; hands-off loop proven. Remaining: actor-pick decode + Controlled-seam
experiment (A2.3).

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

## Next (A2.3)

1. Decode the actor pick: which unit the candidate rebuild selects and the
   CT/tick fields at `0x02016750`.
2. Controlled-seam experiment: write `0xED` bit 3 + controller id on an enemy
   unit, verify the game hands control to the player (Beastmaster mechanic).
3. Write the reversible A3 runner on top of `gdb_force_key.py` + the fixture.
