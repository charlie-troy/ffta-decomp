"""C2 identified-action selector, step 3: prove the move-target cursor.

Round 2 narrowed candidates; the leading move-target (x,y) pairs read
(4,10) at target-open. If the target cursor starts on the acting unit's
own tile, the true cursor pair must equal Marche's roster tile (+0xF6/
+0xF7) at open, tick to the navigated neighbor, and — after committing —
Marche's roster tile must land exactly on the final cursor values.

This probe does the full loop ONCE:
  1. settle (value-agnostic, boot state is the open menu at CT 0)
  2. read Marche's roster tile (rx, ry); cmd cursor must be 0 (Move)
  3. press A -> target mode; sweep T0
  4. press RIGHT once; sweep T1
  5. candidates: T0 pair == (rx, ry) AND T1 == (rx+1, ry)
  6. press A -> COMMIT the movement
  7. pump until the engine executes; read Marche's roster tile again
  8. the address pair whose final value == the new roster tile is the
     move-target cursor, with verified committed-movement semantics

Screenshots at every phase. The commit is deliberate: Move is a legal
non-Wait command and this is the roadmap's named verification example
("committed movement at the correct boundary").
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
from autobattle_runtime import BattleRuntime  # noqa: E402

EWRAM_LO, EWRAM_HI = 0x02000000, 0x02030000
IWRAM_LO, IWRAM_HI = 0x03000000, 0x03008000
CHUNK = 0x200
CURSOR_ADDR = 0x0202ddd9   # command-menu cursor (round 1)

OUT_DIR = os.path.join("outputs", "autobattle", "c2-menu-probe3")

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

    results = {"phases": {}, "candidates": [], "commit": {}}

    with FixtureSession(args.state, rom=args.rom) as s:
        pid = getattr(s, "pid", None) or getattr(getattr(s, "proc", None),
                                                 "pid", None)
        scenario = json.load(open(
            "configs/battle-scenarios/normal-battle.json", encoding="utf-8"))
        out_dir = os.path.join("outputs", "autobattle", "scratch",
                               "c2-probe3-run")
        os.makedirs(out_dir, exist_ok=True)
        rt = BattleRuntime(s, scenario, "c2-probe3", out_dir, max_turns=1)
        probe = rt.p
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
        say(f"player slot={ps}")
        base = ROSTER + STRIDE * ps

        def roster_tile():
            return (u8(g, base + 0xF6), u8(g, base + 0xF7))

        def roster_ct():
            return u16(g, base + OFF_CT)

        rx, ry = roster_tile()
        say(f"Marche roster tile before: ({rx}, {ry}) ct={roster_ct()}")

        def press(mask, tag):
            n = probe.press(mask, pause=1.2, tag=tag)
            say(f"press {tag}: hits={n}")
            time.sleep(1.6)
            return n

        def phase(tag):
            snap = sweep(g)
            cur = g.read_mem(CURSOR_ADDR, 1)
            cur_v = cur[0] if cur else None
            results["phases"][tag] = cur_v
            capture(pid, f"p3-{tag}.png")
            say(f"phase {tag}: cmd_cursor={cur_v}")
            return snap

        cur0 = g.read_mem(CURSOR_ADDR, 1)
        if not cur0 or cur0[0] != 0:
            say(f"command cursor is {cur0}, expected 0 (Move); aborting")
            probe.disarm()
            raise SystemExit(3)

        press(KEY_DOWN, "exercise down")   # Move -> Action: the boot menu's
        press(KEY_UP, "exercise up")       # first A is consumed oddly (probe2
                                           # expB worked only on an exercised
                                           # menu); down+up returns to Move
        pre = sweep(g)
        press(KEY_A, "open-target")
        t0s = phase("target-open")
        press(KEY_RIGHT, "right")
        t1 = phase("target-right")

        # round-2 pairs were 4 bytes apart (x@0200f3b8, y@0200f3bc), so x and
        # y are matched independently — no adjacency assumption.
        xs = {a for a in set(t0s) & set(t1)
              if t0s.get(a) == rx and t1.get(a) == rx + 1}
        ys = {a for a in set(t0s) & set(t1)
              if t0s.get(a) == ry and t1.get(a) == ry and a not in xs}
        cands = [{"x_addr": f"{xa:08x}", "y_addr": f"{ya:08x}",
                  "start": [rx, ry], "after_right": [rx + 1, ry]}
                 for xa in xs for ya in ys]
        changed = sum(1 for a in set(t0s) & set(t1) if t0s[a] != t1[a])
        results["target_opened_evidence"] = {
            "changed_bytes_after_right": changed,
            "witness_x": [t0s.get(a) for a in (0x0200f3b8, 0x0200f3c0)],
            "witness_y": [t0s.get(a) for a in (0x0200f3bc, 0x0200f3c4)]}
        say(f"target-open diff vs pre-target: {changed} bytes changed; "
            f"witness x={results['target_opened_evidence']['witness_x']} "
            f"y={results['target_opened_evidence']['witness_y']}")
        results["candidates"] = cands
        say(f"candidates (started on roster tile, ticked right): "
            f"{[c['x_addr'] + '/' + c['y_addr'] for c in cands]}")

        # ---- commit the movement ------------------------------------
        ct_before = roster_ct()
        press(KEY_A, "commit-move")
        say("commit pressed; waiting for execution (roster tile change)")
        new_tile = None
        deadline = time.time() + 60.0
        while time.time() < deadline:
            probe.pump(3.0, "exec", sample_every=60.0, tick=3.0)
            t_now = roster_tile()
            if t_now != (rx, ry):
                new_tile = t_now
                break
        new_tile = new_tile or roster_tile()
        results["commit"] = {"before": [rx, ry], "after": list(new_tile),
                             "ct_before": ct_before,
                             "ct_after": roster_ct(),
                             "moved_as_planned": new_tile == (rx + 1, ry)}
        capture(pid, "p3-after-commit.png")
        say(f"roster tile after: ({new_tile[0]}, {new_tile[1]}) "
            f"ct={roster_ct()} planned=( {rx + 1}, {ry} )")

        # ---- which candidate matches the final roster tile? ----------
        final = sweep(g)
        confirmed = []
        for c in cands:
            xa, ya = int(c["x_addr"], 16), int(c["y_addr"], 16)
            fx, fy = final.get(xa), final.get(ya)
            c["final_cursor"] = [fx, fy]
            c["matches_new_tile"] = (fx, fy) == new_tile
            if c["matches_new_tile"]:
                confirmed.append(c)
        results["confirmed"] = confirmed
        say(f"CONFIRMED move-target cursor: "
            f"{[c['x_addr'] + '/' + c['y_addr'] for c in confirmed]}")

        probe.disarm()

    out = {"run": "c2-menu-probe3", "t_elapsed_s": round(time.time() - t0, 1),
           **results}
    with open(os.path.join(OUT_DIR, "probe3.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(OUT_DIR, "probe3.log"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    print(json.dumps(out, indent=2)[:2000])


if __name__ == "__main__":
    main()
