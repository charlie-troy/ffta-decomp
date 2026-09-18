"""C2 identified-action selector, step 2: submenu + move-target cursors.

Round 1 (tools/c2_menu_probe.py) decoded the command-menu cursor:
0x0202ddd9 (u8), trajectory [0,1,2,1,0] for Move/Action/Wait, reproduced
across two cycles. This round finds the remaining two cursors the selector
needs:

  A. action-submenu cursor (WHICH ability/command)
     command cursor -> Action (1), press A: submenu opens.
     Sweep T_B; press DOWN, sweep T_C; press DOWN, sweep T_D.
     A true submenu cursor ticks +1 each press: keep addresses where
     C-B == +1 and D-C == +1 (arithmetic progression, stronger than the
     round-1 move/return filter). B cancels back to the command menu.

  B. move-target cursor (WHICH tile: x and y separately)
     command cursor -> Move (0), press A: target mode.
     Sweep T0; press DOWN, sweep T1; press RIGHT, sweep T2.
     x candidates: T1==T0 and T2==T0+1 (right moved x, down did not).
     y candidates: T1==T0+1 and T2==T1 (down moved y, right did not).
     B cancels back to the command menu.

Every phase screenshots the window so values can be matched to visible UI.
No commit is driven. Cleanup kills the owned emulator.
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession  # noqa: E402
from probe_control_handoff import Probe   # noqa: E402

EWRAM_LO, EWRAM_HI = 0x02000000, 0x02030000
IWRAM_LO, IWRAM_HI = 0x03000000, 0x03008000
# mGBA 0.10.5 stub caps 'm' replies: 0x200 ok, >=0x800 dropped (round 1).
CHUNK = 0x200
CURSOR_ADDR = 0x0202ddd9   # round-1 result: command-menu cursor

OUT_DIR = os.path.join("outputs", "autobattle", "c2-menu-probe2")

KEY_A, KEY_B, KEY_DOWN, KEY_RIGHT, KEY_UP = 0x01, 0x02, 0x80, 0x10, 0x40


def sweep(g, regions=((EWRAM_LO, EWRAM_HI), (IWRAM_LO, IWRAM_HI))):
    snap = {}
    for lo, hi in regions:
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

    results = {"expA_submenu": [], "expB_x": [], "expB_y": [],
               "menu_cursor_per_phase": {}, "context": {}}

    with FixtureSession(args.state, rom=args.rom) as s:
        pid = getattr(s, "pid", None) or getattr(getattr(s, "proc", None),
                                                 "pid", None)
        probe = Probe(s, intervene="none")
        g = s.g

        # boot state IS the open command menu parked at CT 0 (round 1) —
        # settle value-agnostically, exactly like the fixed round-1 probe.
        say(f"waiting up to {args.settle_seconds:.0f}s for the menu "
            "(player_menu_settled, allow_zero)")
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
        say("menu settled; starting focused sweeps")
        probe.disarm()

        def press(mask, tag):
            n = probe.press(mask, pause=1.2, tag=tag)
            say(f"press {tag}: hits={n}")
            time.sleep(1.6)      # UI redraw
            return n

        def phase(tag):
            snap = sweep(g)
            shot = capture(pid, f"p2-{tag}.png")
            cur = g.read_mem(CURSOR_ADDR, 1)
            cur_v = cur[0] if cur else None
            results["menu_cursor_per_phase"][tag] = cur_v
            ctx = g.read_mem(CURSOR_ADDR - 8, 16)
            if ctx:
                results["context"][tag] = ctx.hex()
            say(f"phase {tag}: cmd_cursor={cur_v} (shot {shot})")
            return snap

        # ---------------- experiment A: submenu cursor -------------------
        press(KEY_DOWN, "A to-Action")            # Move -> Action
        a = phase("A-pre")                        # command menu, Action
        press(KEY_A, "A open-submenu")
        b = phase("A-open")                       # submenu, cursor at entry i
        press(KEY_DOWN, "A down1")
        c = phase("A-down1")
        press(KEY_DOWN, "A down2")
        d = phase("A-down2")
        for addr in set(b) & set(c) & set(d):
            if c[addr] - b[addr] == 1 and d[addr] - c[addr] == 1:
                results["expA_submenu"].append(
                    {"addr": f"{addr:08x}", "open": b[addr],
                     "down1": c[addr], "down2": d[addr]})
        press(KEY_B, "A cancel-submenu")
        e = phase("A-after-cancel")
        results["expA_cancel_cursor_ok"] = \
            results["menu_cursor_per_phase"]["A-after-cancel"] == 1
        say(f"expA: {len(results['expA_submenu'])} progression candidates; "
            f"cancel returns cmd cursor to Action: "
            f"{results['expA_cancel_cursor_ok']}")

        # ---------------- experiment B: move-target cursor ----------------
        press(KEY_UP, "B to-Move")                # Action -> Move
        press(KEY_A, "B open-target")
        t0s = phase("B-open")
        press(KEY_DOWN, "B down")
        t1 = phase("B-down")
        press(KEY_RIGHT, "B right")
        t2 = phase("B-right")
        xs, ys = [], []
        for addr in set(t0s) & set(t1) & set(t2):
            if t1[addr] == t0s[addr] and t2[addr] - t0s[addr] == 1:
                xs.append({"addr": f"{addr:08x}", "x0": t0s[addr]})
            if t1[addr] - t0s[addr] == 1 and t2[addr] == t1[addr]:
                ys.append({"addr": f"{addr:08x}", "y0": t0s[addr]})
        results["expB_x"], results["expB_y"] = xs, ys
        press(KEY_B, "B cancel-target")
        phase("B-after-cancel")
        say(f"expB: {len(xs)} x-candidates, {len(ys)} y-candidates")

        probe.disarm()

    out = {"run": "c2-menu-probe2", "t_elapsed_s": round(time.time() - t0, 1),
           **results}
    with open(os.path.join(OUT_DIR, "probe2.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(OUT_DIR, "probe2.log"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    print(json.dumps({"expA": out["expA_submenu"][:8],
                      "expB_x": out["expB_x"][:8],
                      "expB_y": out["expB_y"][:8]}, indent=2))


if __name__ == "__main__":
    main()
