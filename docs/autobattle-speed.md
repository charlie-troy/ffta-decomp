# Battle speed: what controls gameplay wall-clock speed (A8)

Measured on the verified `battle-start.ss0` fixture, 2026-10-05, probe
v12 (`tools/probe_a8_speed.py`). Evidence: `outputs/autobattle/A8-speed/speed.json`
(schema a8-speed/12 — all 8 rows usable, all gates pass, every sample
retained with absolute epoch timestamps), `outputs/autobattle/A8-speed/frame-clock.json`
(transport law), `tools/diag_t_phase4.py` (the packet-level sniffer the
method rests on).

## Status

**Investigation complete, product acceptance open.** The investigation
questions are now answered with a self-contained, timestamped
measurement: how fast the emulator actually runs this battle, how
stable that rate is, and whether any tested setting changes it. The
product criterion — selectable normal vs accelerated speed with
equivalent outcomes at both — is **not** satisfied: no tested mechanism
changes the rate materially, and there is only one speed to observe.

## The measurement (two independent channels, one event)

The event is definitional: Marche's CT from the committed-turn park
(296) until the recharge completes (first CT >= 998), on one fixed
fixture. Two channels measure it per boot:

1. **Traced channel (frame count N).** All trace breakpoints cleared,
   only the key-poll breakpoint armed: one stop = one emulated frame
   (`tools/probe_frame_clock.py`). Stop 1 must read the park value 296,
   the final stop must read >= 998, zero PC anomalies, every
   cont/stop timestamped. This channel gives the event's exact frame
   count; it does **not** measure speed, because the cont→stop interval
   is stub-service-bound: dt p50 = 52.2 ms with a hard ~50.4 ms floor,
   identical under `videoSync=1`. The traced cycle rate
   (18.5–18.7 fps in all four boots) is the transport cap, published as
   **tracing overhead only**.

2. **Free-run channel (duration D).** No breakpoints, no `interrupt()`.
   After a reply-pairing drain (`drain_paired`, law DE-028), the core
   free-runs and a sparse poll loop brackets the event in wall time:
   every served read implicitly halts the core and only the next `c`
   resumes it (law DE-029), so each poll window `[t_resume, t_recv]` is
   a running interval and halting windows contribute nothing. The event
   starts at `t0` (first cont, start CT confirmed 296/188-adjacent by
   the first poll; frame-1 = 296 pinned by the traced channel) and ends
   on either a direct CT >= 998 read or the wrap signature (after a
   late-phase marker ct >= 400, the next read >= 200 — the counter
   cannot return to >= 200 from 0 without passing 998 first). The
   duration is bracketed `D ∈ [t_resume_detect − t0 − 60 ms,
   t_recv_detect − t0]`; both endpoints are retained per sample.

`fps = N / D`, with N bracketed by the pooled traced observations of
the same fixture event across v9+v10 boots (default 1126–1190 frames,
vsync1 1123–1162; the few-% boot jitter is carried into the bracket
rather than hidden). No CT-rate folklore, no Lua console (dead channel,
DE-024), no hardcoded baseline, no whole-battle extrapolation.

## The numbers

| mode | D bracket (s) | fps bracket | vs GBA nominal (59.73) |
|---|---|---|---|
| default | 20.51 – 21.45 | 52.5 – 58.0 | **0.88× – 0.97×** |
| `videoSync=1` | 20.65 – 21.51 | 52.2 – 56.3 | **0.87× – 0.94×** |

- Free-run reproducibility: two boots per mode, per-boot fps brackets
  overlap (default 54.3–58.0 / 52.5–56.0; vsync1 52.2–54.6 /
  53.8–56.3), start CT = 296 in all four T boots, end by wrap
  signature, 131–140 timestamped polls per boot.
- Mode separation: worst-case ratio 0.90×, best-case **1.11×** — below
  the pre-registered 1.30× mechanism gate, so the verdict reads
  **"no tested mechanism changes gameplay speed materially"**.
- Tracing costs ~3× wall: the same event takes ~63 s under the traced
  loop (transport-bound 18.7 fps) vs ~21 s free-running.

**The runner is not accelerated.** It runs at slightly *under* real
time (0.87–0.97× nominal) on this host. Earlier claims that this setup
runs "unthrottled/always accelerated" are refuted by the brackets
above.

## Corrections made this round (what was withdrawn and why)

- The v1 "4.1× speedup" is **withdrawn**: it divided measured durations
  by a ~54 s prediction derived from an earlier observed CT rate — a
  derived baseline, not a measured one.
- The v2 "independent calibration" via `emu:currentFrame` Lua callbacks
  is **withdrawn entirely**: the scripting console freezes a
  stub-attached boot on this build (DE-024), so that channel could not
  have produced trustworthy numbers; its claims are re-evidenced by the
  v12 two-channel measurement above.
- The v1 stability table (13.21 s × 3) is **superseded**; it predates
  start-CT gating and frame counting.
- The whole-battle conversion of the C3 ~14.8-minute run into "~60 min
  of hardware time" is **withdrawn**: that run interleaved traced
  boundary loops (transport-bound ~19.2 fps) with free-run phases, so
  its average is an unmeasured mixture. No published number depends on
  it. (For orientation only, not as a conversion: the traced segments
  run ~3× slower than free-run on this fixture.)

## Mechanism matrix (each row verified live, 2026-09-21/22)

| mechanism tried | result |
|---|---|
| `-C fpsTarget=N` (launch) | no effect (9 boots). fpsTarget is SDL-port-only; on the Qt build it *disables* the videoSync wait when combined with it. |
| `-C fastForwardRatio=3` (launch) | no effect — the ratio only scales FF while FF is active |
| Fast forward toggle via UIA (`Emulation > Fast forward`) | invoke reports success; recharge unchanged |
| Fast forward hotkey (Tab) via the C1 window channel | never engages. A blocking main-thread Tab hold instead **pauses** the game. |
| `audioDriver=wasapi` / `directsound`, `audioSync=0` | all identical — audio pacing is dead here regardless of driver |
| `videoSync=0` vs default | identical |
| `videoSync=1` (v12 re-test, timestamped) | no material effect: mode separation bracket 0.90–1.11×, best case below the 1.30× gate |
| `mgba-sdl.exe` (where fpsTarget works) | ships **without the GDB stub** — unusable for this project |
| stub detach (clean `D`, socket closed) | the game **pauses**: all seven roster CTs byte-identical across a 12 s detached window, execution resumes on reconnect. Caveat: interrupt/cont is inert on a raw attach that skipped the `?` handshake, so "CT frozen" alone is not evidence of a paused game. |

## Consequences for the contract

- **"Expose a verified accelerated setting" remains OPEN and is now
  measured as unsatisfiable on this host**: there is one speed, it runs
  at ~0.87–0.97× nominal, and no tested mechanism moves it materially.
  Identical settings prove stability, not a speed knob.
- **"Restore the previous speed on stop" is moot**: there is one speed;
  execution stops with the run (the detach law doubles as the C1 pause
  primitive: no stub client, no execution).
- **Takeover responsiveness** is proven live with durable artifacts
  (`a8-resp2`, 2026-10-05, `outputs/autobattle/a8-takeover-resp2/`):
  STOP injected mid-recharge, zero automation key writes after the
  stop event (input-log proof), paused receipt written, emulator left
  alive. The same mid-wait cancellation the C1 strict-press scenario
  covers offline. (a8-resp1 of 2026-09-21 showed the same behavior but
  its artifacts were transient.)
- **Detach law vs manual takeover (reconciled):** with no stub client
  the core does not step, so `--on-stop leave-running` hands the player
  a **paused** battle. Continuing requires a monitoring client or
  another attach path (the C3 manual layer: one connection,
  interrupt → read → cont per observation, window input for keys,
  clean close before resume). Leaving the process alive alone never
  meant "the player can continue unassisted"; an unassisted
  no-software session is impossible under the law and is not claimed.
- **The runtime is speed-agnostic**: offline takeover receipts are
  byte-identical at 60/120 Hz fake frame rates (the runtime classifies
  on decoded engine state, not wall time), so no runtime change is
  needed or made. Two-speed *equivalence of live battles* stays open
  until a second speed exists.
- If true 1× or a controlled multiplier is ever needed, the documented
  lever remains a 60 Hz monitor + `videoSync=1` on a host where vsync
  actually paces the loop — not fast forward, which never engages
  synthetically, and not fpsTarget, which this build ignores. `-C`
  passthrough exists on `FixtureSession` (`mgba_args=`), so any future
  mechanism is one flag away.

## Method laws this measurement rests on (see docs/dead-ends.md)

- DE-028: one stray reply offsets every later exchange, self-sustaining;
  `drain_paired` (send + raw-pump until two empty pumps) proves pairing.
- DE-029: a served stub read implicitly halts the core; only `c`
  resumes it — wall time between bare reads is not emulated time.
- DE-024..027: console channel dead, IO writes inert, ≤512-byte reads,
  single 2-byte CT reads coherent, no RAM frame counter.
- Key-poll breakpoint hits remain the free frame counter: one stop per
  VBlank, no extra breakpoints, no memory writes; the traced ceiling is
  ~19.2 stops/s (stop-reply round trip), not the game's frame rate.
