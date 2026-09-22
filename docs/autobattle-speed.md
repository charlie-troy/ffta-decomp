# Battle speed: what controls gameplay wall-clock speed (A8)

Measured on the verified `battle-start.ss0` fixture, 2026-09-21. Evidence:
`outputs/autobattle/A8-speed/speed.json` (mechanism matrix + 6 repeated
recharge measurements), `outputs/autobattle/A8-speed/frame-clock.json`
(transport-overhead law), `tools/probe_a8_speed.py`,
`tools/probe_frame_clock.py`.

## The result: the runner has always been accelerated

There is no acceleration lever to expose, because the speed the runner
already runs at IS accelerated. On this machine (mGBA 0.10.5 Qt build,
`-g`, audio present-or-not irrelevant), a GDB-attached free-run is
**unthrottled**: audio sync is inert here, and `videoSync` defaults to 0,
so nothing paces the emulation loop to real time.

Measured metric: Marche's full CT recharge (296 → 998) after a committed
turn — frame-driven engine work, so the duration ratio is the speed
ratio, independent of the charge curve's shape. True 1x prediction at the
recorded ~12.9 CT/s (DE-022): ~54 s.

| setting | recharge (s) | vs true 1x |
|---|---|---|
| default (3 boots) | 13.21, 13.21, 13.21 | **4.1x** |
| `videoSync=1` (3 boots) | 13.21, 13.21, 13.21 | 4.1x |

`videoSync=1` engaged exactly once across seven boots (20.4 s ≈ 165
frames/s = this monitor's refresh rate) and never reproduced — an
unreliable lever, not a usable one.

## Mechanism matrix (each row verified live)

| mechanism tried | result |
|---|---|
| `-C fpsTarget=N` (launch) | no effect (9 boots, all ≈ 6.35 CT/s point-rate rows, then 13.21 s durations). fpsTarget is SDL-port-only; on the Qt build it *disables* the videoSync wait when combined with it (13.2 s). |
| `-C fastForwardRatio=3` (launch) | no effect (11.4 s) — the ratio only scales FF while FF is active |
| Fast forward toggle via UIA (`Emulation > Fast forward`) | invoke reports success; recharge unchanged (11.4 s) |
| Fast forward hotkey (Tab) via the C1 window channel | never engages — not as a blocking hold, not from a holder thread. A blocking main-thread Tab hold instead **pauses** the game (CT parked across the hold). One early run's "112 CT/s" was the engine's natural fast ramp (310→998) coinciding with the hold, not FF. |
| `audioDriver=wasapi` / `directsound`, `audioSync=0` | all identical (14.4 s) — audio pacing is dead here regardless of driver |
| `videoSync=0` vs default | identical (13.2 s) |
| `mgba-sdl.exe` (where fpsTarget works) | ships **without the GDB stub** — unusable for this project |
| stub detach (clean `D`, socket closed) | the game **pauses**: all seven roster CTs byte-identical across a 12 s detached window, execution resumes on reconnect. Caveat recorded: interrupt/cont is inert on a raw attach that skipped the `?` handshake, so "CT frozen" alone is not evidence of a paused game. |

## Consequences for the contract

- **"Expose a verified accelerated setting" is already satisfied by
  default** — every A2.5/A3/C3 run to date ran at ~4.1x true hardware
  speed. Wall-clock durations in older receipts describe this
  accelerated clock, and their ~14.8 min full-battle figure corresponds
  to ~60 min of hardware time.
- **"Restore the previous speed on stop" is moot**: there is one speed,
  and execution stops with the run (the detach law doubles as the C1
  pause primitive: no stub client, no execution).
- **Takeover responsiveness at the accelerated speed is proven live**
  (`a8-resp1`, 2026-09-21): STOP injected mid-recharge was observed with
  **zero key presses after the stop event**, `paused` receipt 8 s later,
  emulator left running for the player. This is the same mid-wait
  cancellation the C1 strict-press scenario covers offline.
- **The runtime is speed-agnostic**: the offline takeover scenario
  produces byte-identical clean receipts at 60 Hz and 120 Hz fake frame
  rates (the runtime classifies on decoded engine state, not wall
  time), so no runtime change is needed or made.
- If true 1x or a *controlled* multiplier is ever needed, the lever is a
  60 Hz monitor + `videoSync=1` (60 fps) — verified to engage but not
  reliably on this 165 Hz panel — not fast forward, which never engages
  synthetically. `-C` passthrough now exists on `FixtureSession`
  (`mgba_args=`), so any future mechanism is one flag away.

## Tracing overhead (published, not hidden)

The traced loop (stop-reply round trip per frame) caps at **~19.2
traced-frames/s** (four 3 s intervals, 58 hits each,
`frame-clock.json`). That is the transport ceiling, not the game's
frame rate — untraced free-run is the unthrottled ~4.1x above. Key-poll
breakpoint hits remain the free frame counter: one stop per VBlank, no
extra breakpoints, no memory writes.
