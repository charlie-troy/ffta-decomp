# A5.1 actor integration — partial, 2026-10-06

The public runner uses a read-only actor adapter for the two verified
seven/eight-record fixtures. It pins name/id with job/side agreement,
requires two fresh cursor-own-tile observations with stable CT, revalidates
the actor before gameplay input, and compares every player's tile across
the commit. Ambiguous identity, stale owner, and wrong actor/destination
prevent a successful action claim. Conditional tactics remain gated.

Live two-player runs reproduced Marche Move `(4,10)->(4,11)` and Montblanc
Wait without player movement. Enemy sequencer observations remain retail.
These runs stop after two turns; they do not establish multi-player battle
completion. The solo public runner also produced a verified Move and pause.

**The required live manual action and same-PID resume have not passed.**
Window input produced CT progress without reaching its selected move tile.
The old manual helper's unconditional PASS was incorrect; it now requires
destination verification. An initial resume probe overlapped the manual
monitor, and a later reconnect failed to halt the stub. Close the monitor
before attempting adoption. All owned live emulators have been terminated;
original saves and ROM remain untouched.

Use [the A5 receipt](receipts/autobattle/A5.json) for commands, exact input
and artifact hashes, positive/negative observations, and current gate status.
Use [the roadmap](auto-battle-roadmap.md) for packet ownership. A5.2 remains
gated until a fresh owned emulator produces independent manual-destination
evidence and a successful same-process continuation.

Checks run: AI 10/10, strategy 9/9, identity/public-CLI controls 21/21, manual
helper controls 4/4. The initial 22-scenario transport suite passed 18 and
exposed four issues; final targeted reruns cover those four plus STOP/resume
and an early cleared-actor results control. This is not a claim that a second
full suite or ROM rebuild ran. See the receipt for individual outcomes.

Reproduce a bounded two-player run from the repository root, supplying the
local ignored A4 savestate and a supported USA ROM:

```powershell
python tools/run_autobattle.py --state outputs/lua-nav/a4-multi-ally-battle-start.ss0 --scenario configs/battle-scenarios/a4-two-player.json --run-id a51-repro-unique --yes --max-turns 2 --wall-timeout 260
python tools/validate_autobattle_runtime.py outputs/autobattle/a51-repro-unique
```

Use a fresh run ID/output directory for every check. A `stalled` turn-budget
stop is expected here and must not be relabeled `completed`.
