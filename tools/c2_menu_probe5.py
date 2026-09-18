"""C2 identified-action selector, step 5: commit a real one-step move.

Round 4: cursor bytes fully decoded (x: 0200f3b8/c0, y: 0200f3bc/c4 with
exact trajectories) but the confirm-A did not execute a move to (6,11) —
possibly out of movement range, possibly a press-vs-drive mechanics gap.
The runtime commits turns live with drive(); this probe uses exactly that
path for the confirm, on an ADJACENT tile, with dense logging so a
zero-move (turn ends without moving) is distinguishable from a rejected
confirm (menu/target stays up):

  zero-move: ct charges away then next menu opens (cursor re-parks)
  rejected:  target mode persists, ct stays 0, cursor unchanged
  executed:  roster tile changes to the destination
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
CURSOR_ADDR = 0x0202ddd9
X_ADDRS = (0x0200f3b8, 0x0200f3c0, 0x0200ffc9, 0x02010058)
Y_ADDRS = (0x0200f3bc, 0x0200f3c4, 0x0200ffca, 0x02010059)

OUT_DIR = os.path.join("outputs", "autobattle", "c2-menu-probe5")

KEY_A, KEY_B, KEY_DOWN, KEY_UP, KEY_RIGHT = 0x01, 0x02, 0x80, 0x40, 0x10


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

    results = {"cursor_watch": [], "outcome": None}

    with FixtureSession(args.state, rom=args.rom) as s:
        pid = getattr(s, "pid", None) or getattr(getattr(s, "proc", None),
                                                 "pid", None)
        probe = Probe(s, intervene="none")
        g = s.g

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

        def cursor_xy():
            xs = [u8(g, a) for a in X_ADDRS]
            ys = [u8(g, a) for a in Y_ADDRS]
            return xs, ys

        rx, ry = roster_tile()
        say(f"Marche start tile: ({rx}, {ry}) ct={roster_ct()}")

        def press(mask, tag):
            n = probe.press(mask, pause=1.2, tag=tag)
            say(f"press {tag}: hits={n}")
            time.sleep(1.6)
            return n

        press(KEY_DOWN, "exercise down")
        press(KEY_UP, "exercise up")
        press(KEY_A, "open-target")
        xs, ys = cursor_xy()
        say(f"after open: x={xs} y={ys}")
        capture(pid, "p5-target-open.png")
        press(KEY_DOWN, "down1")
        xs, ys = cursor_xy()
        say(f"after down: x={xs} y={ys}  (dest should be ({rx},{ry + 1}))")
        capture(pid, "p5-target-down.png")

        # --- confirm via the runtime's proven drive() path ---------------
        say("drive-confirm A (runtime commit path)")
        ok = probe.drive("p5-confirm", route=[(KEY_A, "A-confirm")])
        say(f"drive ok={ok}")
        capture(pid, "p5-after-confirm.png")

        # --- dense watch: classify the outcome ---------------------------
        dest = (rx, ry + 1)
        start = time.time()
        outcome = "unknown"
        while time.time() - start < 120.0:
            probe.pump(3.0, "watch", sample_every=60.0, tick=3.0)
            tile, ct = roster_tile(), roster_ct()
            cur = g.read_mem(CURSOR_ADDR, 1)
            cur_v = cur[0] if cur else None
            results["cursor_watch"].append(
                {"t": round(time.time() - t0, 1), "tile": list(tile),
                 "ct": ct, "cmd_cursor": cur_v,
                 "seeds": len(probe.seeds)})
            say(f"t={results['cursor_watch'][-1]['t']:7.1f} "
                f"tile={tile} ct={ct} cmd={cur_v} seeds={len(probe.seeds)}")
            if tile == dest:
                outcome = "executed"
                break
            if ct not in (0,) and ct > 2:
                outcome = "turn-ended-no-move"   # charging away: zero-move
                break
        results["outcome"] = outcome
        results["dest"] = list(dest)
        capture(pid, "p5-final.png")
        say(f"OUTCOME: {outcome} (dest {dest})")

        if outcome == "executed":
            final = sweep(g)
            confirmed = []
            for xa in X_ADDRS:
                for ya in Y_ADDRS:
                    if final.get(xa) == dest[0] and final.get(ya) == dest[1]:
                        confirmed.append([f"{xa:08x}", f"{ya:08x}"])
            results["confirmed_pairs"] = confirmed
            say(f"CONFIRMED cursor pairs at destination: {confirmed}")

        probe.disarm()

    out = {"run": "c2-menu-probe5", "t_elapsed_s": round(time.time() - t0, 1),
           **results}
    with open(os.path.join(OUT_DIR, "probe5.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(OUT_DIR, "probe5.log"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("outcome", "dest", "confirmed_pairs") if k in out},
                     indent=2))


if __name__ == "__main__":
    main()
