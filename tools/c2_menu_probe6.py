"""C2 identified-action selector, step 6: commit a real move turn.

Round 5 discovery: confirming a destination in Move-target mode moves the
unit visually and RE-OPENS the command menu (FFTA turns are move + action +
wait sub-choices); cmd cursor read 1 (Action) after the move, roster tile
still (4,10), ct still 0 — the turn was still open. The roster tile updates
only at turn commit.

This probe finishes the turn:
  1. settle; exercise; A -> target mode; DOWN -> (4,11); A -> move
     (command menu re-opens; log its cursor)
  2. navigate the re-opened menu to Wait (cmd cursor 2) and confirm
     (DOWN to 2, A select, A confirm-self)
  3. wait for commit: ct charges away from 0 and the engine runs
  4. read the roster tile — must be (4,11) — and sweep; the cursor pair
     whose value == (4,11) is the CONFIRMED move-target cursor, now with
     engine-verified committed-movement semantics (C2's named example).
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

OUT_DIR = os.path.join("outputs", "autobattle", "c2-menu-probe6")

KEY_A, KEY_B, KEY_DOWN, KEY_UP = 0x01, 0x02, 0x80, 0x40


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

    results = {"steps": [], "commit": {}}

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

        def cmd_cursor():
            v = g.read_mem(CURSOR_ADDR, 1)
            return v[0] if v else None

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
        press(KEY_DOWN, "down-to-dest")
        capture(pid, "p6-target-dest.png")
        press(KEY_A, "move")
        cur_after_move = cmd_cursor()
        results["steps"].append({"after_move_cmd_cursor": cur_after_move,
                                 "tile": list(roster_tile()),
                                 "ct": roster_ct()})
        say(f"after move: cmd_cursor={cur_after_move} "
            f"tile={roster_tile()} ct={roster_ct()}")
        capture(pid, "p6-after-move.png")

        # navigate the re-opened command menu to Wait (2) and confirm
        for i in range(3):
            cur = cmd_cursor()
            if cur == 2:
                break
            press(KEY_DOWN, f"nav-down-{i}")
        cur = cmd_cursor()
        say(f"cursor before Wait confirm: {cur}")
        if cur != 2:
            say("could not reach Wait; aborting (turn still open)")
            probe.disarm()
            raise SystemExit(3)
        press(KEY_A, "select-wait")
        press(KEY_A, "confirm-wait")
        capture(pid, "p6-after-wait.png")

        # wait for the commit: ct leaves 0 (charging) and tile updates
        say("waiting for turn commit (tile update)")
        exec_tile = None
        deadline = time.time() + 120.0
        while time.time() < deadline:
            probe.pump(3.0, "commit-watch", sample_every=60.0, tick=3.0)
            t_now, ct_now = roster_tile(), roster_ct()
            if t_now != (rx, ry):
                exec_tile = t_now
                break
            if time.time() - t0 > deadline - 1:
                break
        exec_tile = exec_tile or roster_tile()
        dest = (rx, ry + 1)
        results["commit"] = {"planned": list(dest),
                             "before": [rx, ry],
                             "executed": list(exec_tile),
                             "executed_as_read": exec_tile == dest,
                             "ct_after": roster_ct(),
                             "cmd_cursor_final": cmd_cursor()}
        capture(pid, "p6-final.png")
        say(f"executed tile: {exec_tile} (planned {dest}) ct={roster_ct()}")

        if exec_tile == dest:
            final = sweep(g)
            confirmed = []
            for xa in X_ADDRS:
                for ya in Y_ADDRS:
                    if (final.get(xa) == dest[0]
                            and final.get(ya) == dest[1]):
                        confirmed.append([f"{xa:08x}", f"{ya:08x}"])
            results["confirmed_pairs"] = confirmed
            say(f"CONFIRMED move-target cursor pairs: {confirmed}")

        probe.disarm()

    out = {"run": "c2-menu-probe6", "t_elapsed_s": round(time.time() - t0, 1),
           **results}
    with open(os.path.join(OUT_DIR, "probe6.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(OUT_DIR, "probe6.log"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    print(json.dumps({k: out.get(k) for k in
                      ("steps", "commit", "confirmed_pairs")}, indent=2))


if __name__ == "__main__":
    main()
