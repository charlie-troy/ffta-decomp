# Battle Fixtures (A1)

Captured 2026-09-07. Goal of assignment A1: a repeatable normal battle with player units,
enemies, and observed autonomous turn flow — the substrate for A2 (player-to-AI handoff)
and A3 (autonomous battle runner).

## Fixture chain (savestates in `outputs/lua-nav/`)

| savestate | state | notes |
|---|---|---|
| `worldmap.ss0` | World map, day 17, clan token idle | reliable "hub" reset point |
| `bervenia.ss0` | Day 18, clan on Bervenia Palace (engage ring) | after Area-List travel |
| `engage.ss0` | "Engage!" battle prompt on skull token | **fixture anchor** — the reproducible entry point |
| `placement.ss0` / `placement2.ss0` | Dispatch/placement screen (Marche on pedestal) | mid-flow milestone |
| `battle-start.ss0` | Battle live, Marche's turn, MENU open, WT 1/7 | **primary battle fixture** |
| `battle-start-r1.ss0` | Same, from reproducibility run 1 | run-2 settle differs 1.7% (noise) |

## The proven capture route

All key injection goes through the mGBA Scripting console (UIA bridge, `tools/uia_*.ps1`)
with `emu:setKeys` — see `tools/lua_cursor_tour.lua` (step-wise drive with per-step
screenshots) and `tools/lua_watch.lua` (dense passive watch). Key bitmasks:
A=1, B=2, SELECT=4, START=8, RIGHT=16, LEFT=32, UP=64, DOWN=128, R=256, L=512.

1. `emu:loadStateFile(engage.ss0)` — battle prompt appears.
2. **A** — enters dispatch; law NOTICE dialog appears ("press SELECT to check current laws").
3. **A** — dismiss NOTICE; placement screen (0/6, Marche on pedestal at right).
4. **A**, **A** — pick up Marche, place on highlighted deployment tile (1/6).
5. **START** — "START: To Battle!" banner; **A** — confirm dialog (cursor on Yes).
6. Wait ~40 s (intro pan + walk-in) → Marche's turn, MENU open, WT 1/7.

**Timing caveat**: START fires reliably only after the placement screen has settled
(~2 s after the last A); a START issued too early opens the unit roster instead.

## Reproducibility (reload-twice check)

Two identical runs from `engage.ss0` settle at the same battle-start state:
2400-point grid diff **1.7%** (>60 RGB delta), attributable to water/sprite animation.
Map, unit placement, and turn order (Marche first, WT 1/7) are identical; the RNG stream
is not expected to match across entries. Fixture therefore guarantees *state*, not *RNG*.

## Observed autonomous enemy turn (the A1 payoff)

After ending Marche's turn (MENU → Wait → confirm facing), a 40-shot dense watch
(`ewatch-01..40.png`, 1 shot/60 frames) captured the full cycle hands-off:

1. **Turn banner** — enemy **Schneider**, Lv 41, HP 323/323, MP 107/114, red plate, WT 1/7.
2. **Move-range target tile** — red tile rendered on a reachable ledge (`ewatch-09`).
3. **Tile transition** — Schneider walks to the chosen tile (`ewatch-13`).
4. **Ability cutscene** — golden-phoenix attack animation (`ewatch-21`).
5. **Damage popup** — "55" on the target (`ewatch-25`).
6. More units reposition (`ewatch-29..37`) — the battle continues unattended.

This is the in-vivo evidence that the game's own AI drives enemy movement/actions, and
the same save exposes the player menu surface A2 needs to hand off.

## Known constraints

- **Input dies on savestate reloads into battle menus.** Dialogs tolerate reloads; the
  battle MENU does not (cursor ignores D-pad after `loadStateFile` while a menu is open).
  All menu interactions must happen in a natural flow from a pre-menu savestate.
- **mGBA launch**: `-g` stub pauses emulation until a GDB client continues it once
  (`python tools/gdb_once.py`-style one-shot); after that the game runs at full speed.
- **Lua API limits**: memory *read* callbacks never fire on this build (execute/write do);
  ROM writes are dropped; use `emu:setKeys`/`loadStateFile`/`saveStateFile`/`screenshot`.
- Scenario metadata: `configs/battle-scenarios/normal-battle.json`.
