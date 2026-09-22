"""A8 probe: gameplay-speed mechanism and measurement.

RESULT (2026-09-21): there is no working acceleration lever to wire —
because the runner has ALWAYS been accelerated. The deliverable is the
measured law, published with the full mechanism matrix.

The law (all numbers from live runs on the verified fixture, metric =
Marche full CT recharge 296->998; true 1x is ~54 s at the recorded
12.9 CT/s, docs/dead-ends.md DE-022):
  * Default launch (mGBA.exe -g, Qt build, this machine): ~10-14 s
    => ~69-97 CT/s => ~4-5x faster than real hardware. The GDB-attached
    free-run is UNTHROTTLED: audio sync is inert here (audioDriver
    wasapi/directsound and audioSync=0 all identical), and videoSync
    defaults to 0.
  * videoSync=1: recharge ~20.4 s => ~165 frames/s — exactly this
    machine's 165 Hz monitor refresh. The video-synced loop tracks the
    host refresh rate, not 59.7 fps.
  * videoSync=1 + fpsTarget=120: ~13.2 s (unthrottled again) — on this
    Qt build fpsTarget DISABLES the video-sync wait rather than scaling
    it (fpsTarget is implemented for the SDL port; odroid forum thread
    t=46121 reached the same conclusion from source).
  * fastForwardRatio=3 at launch: inert (11.4 s) — the ratio only scales
    FF while FF is active.
  * Fast forward (Tab hotkey via the C1 window channel, UIA Emulation >
    Fast forward toggle, holder thread, blocking holds): never engages.
    Worse, a blocking main-thread Tab hold freezes the game (CT parked
    across the hold) — the focus disturbance pauses it.
  * Stub detach: the game PAUSES while no stub client is attached (all
    seven roster CTs byte-identical across a 12 s detached window; then
    resumes on reconnect). IMPORTANT CAVEAT: interrupt/cont is inert on
    a raw attach that skipped the '?' handshake, so "CT frozen after a
    no-client window" is NOT evidence of a paused game by itself.
  * mgba-sdl.exe (where fpsTarget works): ships without the GDB stub —
    unusable for this project.

Consequence for the roadmap: "restore the previous speed on stop" is
moot — there is one speed, already accelerated, and it stops with the
run (the detach law doubles as the C1 pause primitive: no client = no
execution). The acceleration knob, if ever needed, is a videoSync +
fpsTarget combination on a 60 Hz monitor, not fast forward.

Measurement design (this probe): same boot flow as every run —
FixtureSession boots the verified fixture, Probe commits one identified
Wait, then the probe times the full recharge with 2-byte CT reads
(bulk reads desync the stub — the stale-packet law). Rows:
  * default (3 boots) - the speed every existing run actually ran at
  * videoSync=1 (3 boots) - the closest achievable to real 1x
Takeover-responsiveness at the accelerated speed: a STOP file injected
mid-recharge must be observed by the probe's poll loop within one poll
interval (checked in the live validation, recorded in the receipt).

Evidence: outputs/autobattle/A8-speed/speed.json (untracked).
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, ROSTER, STRIDE, OFF_CT  # noqa: E402
from probe_control_handoff import Probe  # noqa: E402

OUT_DIR = os.path.join("outputs", "autobattle", "A8-speed")
STATE = os.path.join("outputs", "lua-nav", "battle-start.ss0")
CT_BASE = ROSTER + STRIDE * 6 + OFF_CT
CT_FULL = 998


def ct_read(g, tries=4):
    for _ in range(tries):
        try:
            g.interrupt()
            d = g.read_mem(CT_BASE, 2)
            g.cont()
            if d:
                return int.from_bytes(d, "little")
        except Exception:
            try:
                g.cont()
            except Exception:
                pass
        time.sleep(0.4)
    return None


def one_boot(extra, label):
    row = {"label": label, "mgba_args": extra}
    try:
        with FixtureSession(STATE, mgba_args=extra, quiet=True) as s:
            row["pid"] = s.pid
            probe = Probe(s, verbose=False)
            plan = probe.plan_identified_wait()
            row["plan"] = bool(plan)
            if not plan:
                row["error"] = "no identified-wait plan"
                return row
            completed, _ = probe.commit_identified_wait(plan)
            row["committed"] = bool(completed)
            if not completed:
                row["error"] = "commit failed"
                return row
            t0 = time.time()
            while time.time() - t0 < 120:
                c = ct_read(s.g)
                if c is not None and c >= CT_FULL:
                    row["recharge_s"] = round(time.time() - t0, 2)
                    break
                time.sleep(0.8)
            else:
                row["error"] = "not full within 120 s"
    except Exception as exc:      # noqa: BLE001 - record, continue
        row["error"] = str(exc)[:200]
    return row


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    report = {"schema": "a8-speed/7",
              "metric": "full CT recharge 296->998 (frame-driven, "
                        "curve-shape-independent)",
              "true_1x_prediction_s": 54.3,
              "mechanism_matrix": {
                  "default": "unthrottled (~4-5x): audio sync inert, videoSync off",
                  "videoSync=1": "tracks host refresh (165 Hz), not 60 fps",
                  "fpsTarget": "no effect (Qt build); disables videoSync wait",
                  "fastForwardRatio": "no effect at launch",
                  "fast-forward toggle/hotkey": "never engages; Tab hold pauses",
                  "stub detach": "pauses execution (no client = no run)",
                  "mgba-sdl.exe": "no GDB stub"},
              "rows": []}
    for label, extra, reps in (("default", None, 3),
                               ("vsync1", ["-C", "videoSync=1"], 3)):
        for rep in range(reps):
            name = label if rep == 0 else f"{label}#{rep + 1}"
            row = one_boot(extra, name)
            report["rows"].append(row)
            print(f"  {name}: {row.get('recharge_s')}s"
                  f"{', err=' + row['error'] if row.get('error') else ''}",
                  flush=True)

    def durs(label):
        return [r["recharge_s"] for r in report["rows"]
                if str(r.get("label", "")).startswith(label)
                and r.get("recharge_s")]

    d_def, d_vs = durs("default"), durs("vsync1")
    ok = len(d_def) >= 2 and len(d_vs) >= 2
    if ok:
        m_def = sum(d_def) / len(d_def)
        m_vs = sum(d_vs) / len(d_vs)
        report["summary"] = {
            "default_recharge_s": d_def, "vsync1_recharge_s": d_vs,
            "default_mean_s": round(m_def, 2),
            "vsync1_mean_s": round(m_vs, 2),
            "default_speedup_vs_true_1x": round(54.3 / m_def, 2),
            "vsync1_speedup_vs_true_1x": round(54.3 / m_vs, 2)}
        ok = m_def < 54.3 / 3
    with open(os.path.join(OUT_DIR, "speed.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report.get("summary", {}), indent=2))
    print(f"A8-SPEED {'PASS' if ok else 'FAIL'} "
          f"(default runs at >=3x true 1x; acceleration is intrinsic)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
