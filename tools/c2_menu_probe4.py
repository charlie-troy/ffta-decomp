"""C2 identified-action selector, step 4: pin the move-target cursor.

Round 3 evidence: after A (target mode at Marche's tile), pressing RIGHT
changed exactly ONE byte 4->5: 0x02008f7a. The commit-A afterwards did not
execute a move (tile/ct unchanged) because the cursor was still on Marche's
own tile — in FFTA confirming the start tile is a zero-move that re-opens
the command menu, so cmd cursor stayed 0. Lesson: navigate OFF the start
tile before confirming.

This probe:
  1. settle; exercise DOWN,UP (pristine-menu A pitfall); A -> target mode
  2. sweep T0; RIGHT T1; DOWN T2; RIGHT T3  (full x/y trajectories)
     x candidate: 4,5,5,6  (ticks only on RIGHTs)
     y candidate: 10,10,11,11 (ticks only on DOWN)
  3. A -> confirm move to the READ cursor tile (tx,ty)
  4. wait for execution: roster tile becomes (tx,ty); sweep T4
  5. the address pair whose T4 == (tx,ty) AND whose trajectory matches is
     the CONFIRMED move-target cursor — with engine-verified semantics.
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, u8, u16  # noqa: E402
from probe_control_handoff import (Probe, ROSTER, STRIDE,  # noqa: E402
                                   OFF_CT)

EWRAM_LO, EWRAM_HI = 0x02000000, 0x02030000
IWRAM_LO, IWRAM_HI = 0x03000000, 0x03008000
CHUNK = 0x200
CURSOR_ADDR = 0x0202ddd9   # command-menu cursor (round 1)

OUT_DIR = os.path.join("outputs", "autobattle", "c2-menu-probe4")

KEY_A, KEY_B, KEY_DOWN, KEY_RIGHT, KEY_UP = 0x01, 0x02, 0x80, 0x10, 0x40


def sweep(g):
    snap = {}
    for lo, hi in ((EWRAM_LO, EWRAM_HI), (IWRAM_LO, IWRAM_HI)):
        for base in range(lo, hi, CHUNK):
            data = g.read_mem(base, CHUNK)
            if data:
                snap.update({base + i: v for i, v in enumerate(data)})
    return snap


def capture(pid, name):
    out = os.path.join(OUT_DIR, name)
    try:
        subprocess.run(["powershell", "-NoProfile", "-File",
                        "tools/capture_window.ps1", "-ProcId", str(pid),
                        "-Out", out], timeout=25, capture_output=True)
    except Exception as exc:                       # noqa: BLE001
        print(f"  capture {name} failed: {exc}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state",
                    default=os.path.join("outputs", "lua-nav",
                                         "battle-start.ss0"))
    ap.add_argument("--rom", default="baserom.gba")
    ap.add_argument("--settle-seconds", type=float, default=150.0)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    log_lines = []

    def say(msg):
        line = f"[{time.time() - t0:7.1f}s] {msg}"
        print(line, flush=True)
        log_lines.append(line)

    results = {"traj": {}, "x_cands": [], "y_cands": [], "pairs": [],
               "commit": {}}

    with FixtureSession(args.state, rom=args.rom) as s:
        pid = getattr(s, "pid", None) or getattr(getattr(s, "proc", None),
                                                 "pid", None)
        probe = Probe(s, intervene="none")
        g = s.g

        say(f"waiting up to {args.settle_seconds:.0f}s for the menu")
        deadline = time.time() + args.settle_seconds
        settled = False
        while time.time() < deadline:
            if probe.player_menu_settled(2, tick_secs=2.0, allow_zero=True):
                settled = True
                break
            time.sleep(1.0)
        if not settled:
            say("menu never settled; aborting")
            probe.disarm()
            raise SystemExit(2)
        say("menu settled")
        probe.disarm()

        ps = probe.player_slot()
        base = ROSTER + STRIDE * ps

        def roster_tile():
            return (u8(g, base + 0xF6), u8(g, base + 0xF7))

        def roster_ct():
            return u16(g, base + OFF_CT)

        rx, ry = roster_tile()
        say(f"Marche start tile: ({rx}, {ry}) ct={roster_ct()}")

        def press(mask, tag):
            n = probe.press(mask, pause=1.2, tag=tag)
            say(f"press {tag}: hits={n}")
            time.sleep(1.6)
            return n

        def phase(tag):
            snap = sweep(g)
            cur = g.read_mem(CURSOR_ADDR, 1)
            results["traj"][tag] = {"cmd": cur[0] if cur else None}
            capture(pid, f"p4-{tag}.png")
            say(f"phase {tag} swept")
            return snap

        press(KEY_DOWN, "exercise down")
        press(KEY_UP, "exercise up")
        press(KEY_A, "open-target")
        t0s = phase("T0-open")
        press(KEY_RIGHT, "right1")
        t1 = phase("T1-right")
        press(KEY_DOWN, "down1")
        t2 = phase("T2-down")
        press(KEY_RIGHT, "right2")
        t3 = phase("T3-right")

        # full trajectories: x ticks 4,5,5,6; y ticks 10,10,11,11
        for addr in set(t0s) & set(t1) & set(t2) & set(t3):
            v0, v1, v2, v3 = (t0s[addr], t1[addr], t2[addr], t3[addr])
            if (v0, v1, v2, v3) == (rx, rx + 1, rx + 1, rx + 2):
                results["x_cands"].append(f"{addr:08x}")
            if (v0, v1, v2, v3) == (ry, ry, ry + 1, ry + 1):
                results["y_cands"].append(f"{addr:08x}")
        say(f"x cands: {results['x_cands']}")
        say(f"y cands: {results['y_cands']}")
        results["pairs"] = [{"x": x, "y": y}
                            for x in results["x_cands"]
                            for y in results["y_cands"]]

        tx, ty = rx + 2, ry + 1        # where the cursor should be now
        press(KEY_A, "confirm-move")
        say("move confirmed; waiting for execution (tile change + ct charge)")
        exec_tile = None
        deadline = time.time() + 90.0
        while time.time() < deadline:
            probe.pump(3.0, "exec", sample_every=60.0, tick=3.0)
            t_now = roster_tile()
            if t_now != (rx, ry):
                exec_tile = t_now
                break
        exec_tile = exec_tile or roster_tile()
        results["commit"] = {"planned": [tx, ty],
                             "before": [rx, ry],
                             "executed": list(exec_tile),
                             "ct_after": roster_ct(),
                             "executed_as_read": exec_tile == (tx, ty)}
        capture(pid, "p4-after-exec.png")
        say(f"executed tile: {exec_tile} (planned ({tx}, {ty})) "
            f"ct={roster_ct()}")

        t4 = sweep(g)
        confirmed = []
        for p in results["pairs"]:
            xa, ya = int(p["x"], 16), int(p["y"], 16)
            fx, fy = t4.get(xa), t4.get(ya)
            p["final"] = [fx, fy]
            if (fx, fy) == exec_tile:
                confirmed.append(p)
        results["confirmed"] = confirmed
        say(f"CONFIRMED cursor pairs (final == executed tile): {confirmed}")

        probe.disarm()

    out = {"run": "c2-menu-probe4", "t_elapsed_s": round(time.time() - t0, 1),
           **results}
    with open(os.path.join(OUT_DIR, "probe4.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(OUT_DIR, "probe4.log"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("x_cands", "y_cands", "commit", "confirmed")},
                     indent=2))


if __name__ == "__main__":
    main()
