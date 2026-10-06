# Battle Fixtures (A1, repaired by A2.4a)

Captured 2026-09-07, reconciled 2026-09-10. Goal: a repeatable normal battle with
player units, enemies, and observed autonomous turn flow — the substrate for A2
(player-to-AI handoff) and A3 (autonomous battle runner).

**Read this first:** the A1 notes below described a six-member clan and a
second-ever actor named Schneider. A2.4a's live reads show the fixture is
**solo Marche vs a five-member enemy clan, with the Judge present**, and that
Schneider is an *enemy*. The corrections are in "What the fixture actually
holds". Nothing in this file is a game byte; savestates stay untracked.

## Fixture chain (savestates in `outputs/lua-nav/`)

| savestate | state | SHA-256 (first 16) |
|---|---|---|
| `worldmap.ss0` | World map, day 17, clan token idle — reliable hub reset | `9804c9cfe5653351` |
| `bervenia.ss0` | Day 18, clan on Bervenia Palace (engage ring) | — |
| `engage.ss0` | "Engage!" battle prompt | `0e821b87ab09a9d7` |
| `placement.ss0` / `placement2.ss0` | Dispatch/placement screen | `3acb4efc8b561ec0` / `2e5283939a340e3c` |
| `battle-start.ss0` | **verified battle fixture** | `4da58bfe0e162210` |
| `battle-start-r1.ss0` | A1 reproducibility run; same live roster | `4d87b5db2ef5f358` |
| `fix3-battle-start.ss0` | Live state byte-identical to `battle-start.ss0` | `591f64c6760f9898` |
| `a4-multi-ally-battle-start.ss0` | **A4 two-ally same-job fixture** (Marche + Montblanc job 5 vs five enemies incl. same-job Velasquez; Judge present) | `7cbe2f661279d148` |

`a2-battle-start.ss0` (`ac80bafab261a245`), `a2b-battle-start.ss0`,
`a2run-battle-start.ss0`, `fix2-battle-start.ss0` and `dp-battle-start.ss0` all
**fail the guard** — none holds the battle roster. Their files are preserved but
they must not be cited as fixture evidence.

## Verified start command (A2.4a)

```bash
python tools/boot_fixture_gdb.py battle-start.ss0
```

The helper copies the ROM and battery save into `outputs/autobattle/scratch/`,
launches an mGBA it owns, connects **one** GDB session, halts, runs the read-only
guard in `tools/fixture_guard.py`, prints the receipt, and terminates only the
PID it launched. It refuses to start if the stub port already has a listener:
mGBA 0.10.5 hardcodes port 2345 for `-g`, so a second guarded instance is not
possible and attaching to another worker's or the user's emulator is forbidden.
The ROM SHA1 (`4ac05441f4de70a4ec3dd932116346c61b8783d9`) is checked before
boot.

Guard exit codes: `0` verified, `2` rejected, `1` boot failure. A rejected
fixture means the savestate is not the state the packet claims; no memory write
is permitted until the mismatch is reconciled.

## What the fixture actually holds (live, 2026-09-10)

Battle struct `0x020159E4`: count `7` at `+0x00`, roster inline at `+4`
(`0x020159E8`), stride `0x108`. All seven records are units; there is no turn
scratch inside the array.

| slot | name | id | job | lvl | HP | 0x8000 | role |
|---|---|---|---|---|---|---|---|
| 0 | Jon | 0 | 41 | 40 | 319/319 | set | enemy clan |
| 1 | Velasquez | 1 | 5 | 42 | 300/300 | set | enemy clan |
| 2 | Godfrey | 2 | 40 | 40 | 303/303 | set | enemy clan |
| 3 | Schneider | 3 | 36 | 41 | 323/323 | set | enemy clan |
| 4 | Carson | 4 | 22 | 40 | 231/231 | set | enemy clan |
| 5 | Judge | 5 | 104 | 10 | 10/10 | clear (0x1000 unaffiliated) | neutral Judge |
| 6 | **Marche** | 6 | 2 | 50 | 388/442 | clear | player |

Corrections of record:

* **Slot0 is an enemy named Jon**, not Marche. Its name pointer `0x085671EE`
  decodes to `Jon`; A1's and A2.3's "name0 = Marche" claim came from reading the
  wrong end of the array.
* **Marche is slot6**, and his name pointer `0x02001F1C` is in EWRAM because the
  player's name is save data. A ROM-pointer-only rule — the one A2.3 used —
  misclassifies him as a turn-scratch record. Decoding the EWRAM string gives
  `Marche` (type 2, job 2, level 50, HP 388/442, MP 85/85, id 6).
* **Schneider is an enemy clan unit** (job 36, level 41, HP 323/323,
  MP 107/114), matching A1's observed banner; the A1 notes were right about
  the unit and wrong about the actor order.
* A second array at `0x02002FC4` mirrors the six AI units (ids 0–5, Marche
  absent) in a different order with different CT values. Sequencer context
  pointers captured at `0x080C03C2` reference *that* copy, so actor
  attribution must be by decoded name, not by slot index.
* The old boot guard's `NAME0_ADDR = 0x02015AF0` sampled slot1 (Velasquez) and
  `MID6_ADDR = 0x0201611C` sampled slot6's unit id — the latter was the one
  accidental truth in it. Both are now replaced by slot0 identity, live roster
  bounds, count/unit agreement, and a named-player check.

## The proven capture route (A1, unchanged)

All key injection in A1 went through the mGBA Scripting console (UIA bridge,
`tools/uia_*.ps1`) with `emu:setKeys` — see `tools/lua_cursor_tour.lua` and
`tools/lua_watch.lua`. Key bitmasks: A=1, B=2, SELECT=4, START=8, RIGHT=16,
LEFT=32, UP=64, DOWN=128, R=256, L=512.

1. `emu:loadStateFile(engage.ss0)` — battle prompt appears.
2. **A** — enters dispatch; law NOTICE dialog appears.
3. **A** — dismiss NOTICE; placement screen (0/6, unit on pedestal at right).
4. **A**, **A** — pick up the unit, place on highlighted deployment tile (1/6).
5. **START** — "START: To Battle!" banner; **A** — confirm dialog.
6. Wait ~40 s (intro pan + walk-in) → player menu open.

**Timing caveat:** START fires reliably only after the placement screen has
settled (~2 s after the last A); issued too early it opens the unit roster.

## Two-ally same-job fixture (A4, 2026-10-05)

`a4-multi-ally-battle-start.ss0` (sha1
`34c88fa47dc314891f93584e151484451dc94aa6`) holds the roster A4 needed:
two player units of the same job plus an enemy of that job.

| slot | name | job | type | side | role |
|---|---|---|---|---|---|
| 0 | Jon | 41 | enemy | clan | enemy |
| 1 | **Velasquez** | **5** | enemy | clan | same-job enemy |
| 2 | Godfrey | 40 | enemy | clan | enemy |
| 3 | Schneider | 36 | enemy | clan | enemy |
| 4 | Carson | 22 | enemy | clan | enemy |
| 5 | **Montblanc** | **5** | player | party | ally 2 |
| 6 | Judge | 104 | neutral | unaffiliated | Judge |
| 7 | **Marche** | **5** | player | party | ally 1 |

Built and verified by:

```bash
python tools/a4_fixture_build.py            # writes the state + fixture-build.json
python tools/a4_fixture_build.py --verify   # roster round-trip vs the receipt
```

Evidence: `outputs/autobattle/A4-demo/fixture-build.json` (roster, jobs,
side bits, CTs at build, `players_same_job` + `enemy_same_job` both true).

**Pinned dispatch route** (drives the key-poll channel from the A1
engage state; the two failure-prone steps are called out):

1. A — enter dispatch; A — dismiss NOTICE (lands on the LIST screen).
2. A pick-0, A place-0, A back-to-list.
3. A re-pick-0, A re-place-0, A re-back-to-list (refreshes the pedestal).
4. **D-pad RIGHT (`0x10`) — NOT the R shoulder (`0x100`) — switches the
   pedestal unit.** The R-shoulder candidate failed three build attempts
   before the D-pad law was found (recorded in `docs/dead-ends.md`).
5. A pick-1, A place-1, A back-to-list-2; settle 3 s.
6. **START only from the LIST screen** (too early opens the unit roster),
   then A confirm → ~40 s intro + walk-in.

The same route plus the demo drive are exercised end-to-end by
`tools/a4_divergence_demo.py` (fixture shape asserted from the guard's
receipt before any input).

## Reproducibility (reload-twice check)

Two identical runs from `engage.ss0` settle at the same battle-start state
(2400-point grid diff 1.7%, water/sprite animation only). A2.4a re-verified the
*fixture* twice directly (`verify_fixture_baseline.py baseline --runs 2`):
identical PC (`0x08000428`), CT vector `[45, 464, 850, 821, 515, 315, 0]`,
slot0 id/ea, and identical outcome. State is reproducible; RNG is not promised.

## Observed turn flow from the fixture

`python tools/verify_fixture_baseline.py baseline` drives the A1/A2.3 menu route
(DOWN DOWN A Wait A confirm, five frames per press at the `0x08000494` key
poll) and watches the sequencer seed at `0x080C03C2`:

* seed at t≈10 s and t≈20 s with contexts naming **Carson, Jon, Schneider**;
* Godfrey's and Schneider's CT fall to 0 as their turns are consumed; Marche's
  CT charges 0→257;
* only one memory write all run: the key-enable byte at `0x03000005`, restored
  afterwards.

`python tools/verify_fixture_baseline.py control` runs the same window with no
input: zero seeds, CT vector unchanged (`dormant_awaits_player_input`). The
fixture genuinely waits for player input, so progress in the baseline comes from
the driven commit rather than from idle auto-battle.

## Known constraints

- **Input dies on savestate reloads into battle menus.** Dialogs tolerate
  reloads; an open battle MENU does not (D-pad is ignored after
  `loadStateFile`). Natural flow from a pre-menu savestate is required.
- **mGBA launch flake.** `-g` instances occasionally come up non-responsive;
  `FixtureSession` relaunches its own process up to three times instead of
  weakening the guard.
- **Lua API limits:** memory *read* callbacks never fire on this build
  (execute/write do); ROM writes are dropped.
- **Crash trap:** single-stepping `update_keys` leaves PC at `0x00000004`
  (BIOS illegal-instruction handler); patch registers at `0x08000494` instead.
- Metadata: `configs/battle-scenarios/normal-battle.json`; evidence:
  `outputs/autobattle/A2.4a/` (untracked).
