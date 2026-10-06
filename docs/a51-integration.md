# A5.1 actor integration — accepted, 2026-10-06

The public runner uses a read-only actor adapter for the two verified
seven/eight-record fixtures. It pins name/id with job/side agreement,
requires two fresh cursor-own-tile observations with stable CT, revalidates
the actor before gameplay input, and compares every player's tile across the
commit. Ambiguous identity, stale owner, and wrong actor/destination prevent a
successful action claim. Conditional tactics remain gated.

Live two-player runs reproduced Marche Move `(4,10)->(4,11)` and Montblanc
Wait without player movement. Enemy sequencer observations remain retail.
These runs stop after two turns; they do not establish multi-player battle
completion. The solo public runner also produced a verified Move.

**The live manual action and the same-PID resume now pass**, and the two
pieces of machinery that made them reproducible are part of the delivered
code:

- `run_autobattle.py --pause-at-boundary` stops **on purpose** at the first
  identified player menu: the fresh menu is identified from RAM, left OPEN and
  untouched, no automation input is issued, the latch is recorded in the raw
  input log exactly as a STOP request is, breakpoints are disarmed and the
  emulator is left running. The C3 handoff used to be reproduced by racing a
  STOP file against the boundary drive, so whether the pause landed with the
  player's menu open was luck; this is the same handoff on purpose. Covered
  offline by the `pause-at-boundary` transport scenario.
- `tools/c3_manual_layer.py` identifies the menu owner from the roster — the
  unique live unit whose own tile holds the target cursor, unchanged across
  three samples with a stable CT and a known command byte — instead of a fixed
  slot 6, probes the mode by seeing which cursor answers (a blocked direction
  answers neither byte, which the old single-DOWN probe read as a dead UI),
  and verifies the destination from a whole-board tile delta.
- `FixtureSession.adopt_existing` retries the roster guard to a bound and
  records every attempt. A turn transition reuses the battle-struct EWRAM
  region for ~10 s (see `docs/dead-ends.md`, DE-032), so a `--resume` that
  attaches in that window sees a garbage roster; each retry must also send
  `c`, because a served read halts the core and a read-only retry freezes the
  engine inside the transition forever.

## The accepted live pair (one battle, two legs, one process)

`outputs/autobattle/a51-live-manual-05/` (window screenshots inspected;
JSON/logs force-added, PNGs local):

| Step | Observation |
|---|---|
| leg 1 `--pause-at-boundary` | paused at t=13.7 s on Marche's fresh menu, `boundary-turn1.png`, zero input writes, `manual_handoff {pid 44528, port 2345}` |
| manual layer (window SendInput) | parked menu owner slot 6 tile (4,10); command probe moved the command cursor, Move→target at (4,10); stepped DOWN to (4,11); A committed the walk; a manual Wait closed the turn (`CT 0 → 188`); roster tile mirrored `(4,10) → (4,11)`; board delta `moved_slots=[6]`, no other same-side slot moved; `keys_sent=[DOWN,UP,A,DOWN,A,DOWN,A,A]`, `monitor_reads=72`, `monitor_faults=0` |
| leg 2 `--resume` | `adopt: roster guard not settled yet … retrying (turn-transition window)` ×2, then **adopted pid 44528** (`match_receipt_handoff_pid: true`, `guard_attempts: 3`, no reboot) and drove two further identified turns whose `position_before` is **(4,11)** — the manually walked tile |

The repeat run `outputs/autobattle/a51-live-manual-04/` shows the same pair
with the automation *moving* out of the manual tile: leg 2 turn 1
`(4,11) -> (5,11)`, turn 2 `(5,11) -> (6,11)`. It predates the `adopt` block in
the receipt, so the canonical artifacts are run 05.

Checks run on the delivered revision: AI 10/10, strategy 9/9, identity/public-CLI
controls 21/21, manual-helper controls 5/5 (a fifth control now covers the
ambiguous-owner case that DE-030 describes: two records on the cursor tile must
never reach the commit path), the full 23-scenario transport suite, and
`validate_all.py baserom.gba` (FULL VALIDATION PASSED in 56.8 s, includes the
WSL rebuild). Two live public-runner runs on the two-player fixture after the
change reproduced Marche Move + Montblanc Wait. See
[the A5 receipt](receipts/autobattle/A5.json) for exact commands, per-run
hashes and artifact hashes.

Reproduce the pair from the repository root, supplying the local ignored solo
savestate and a supported USA ROM (one chain, no inspection gap — the battle
runs live between the legs):

```powershell
python tools/run_autobattle.py --run-id a51-repro-<unique> --yes --pause-at-boundary --wall-timeout 300
python tools/c3_manual_layer.py --receipt outputs/autobattle/a51-repro-<unique>/run.json --window-timeout 150
python tools/run_autobattle.py --resume a51-repro-<unique> --yes --max-turns 2 --wall-timeout 400
python tools/validate_autobattle_runtime.py outputs/autobattle/a51-repro-<unique>
```

A `stalled` turn-budget stop is expected for the resumed leg and must not be
relabelled `completed`. A bounded two-player run:

```powershell
python tools/run_autobattle.py --state outputs/lua-nav/a4-multi-ally-battle-start.ss0 --scenario configs/battle-scenarios/a4-two-player.json --run-id a51-repro2-<unique> --yes --max-turns 2 --wall-timeout 260
python tools/validate_autobattle_runtime.py outputs/autobattle/a51-repro2-<unique>
```

Remaining limits: verified seven/eight-record fixture scope only; `side_bit
false` for the player is fixture-specific; the manual layer's menu gate is
evidence and the destination delta is the proof; no multi-player battle-end
signature; scenario Move/Wait assignment is not conditional tactics. A5.2 stays
gated on its own criteria, not on this packet.
