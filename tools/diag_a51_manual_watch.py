"""Replay the manual route key by key and snapshot the roster after each key.

The manual layer's own board check reads a healthy roster immediately after
the turn closes, yet the resuming runner's guard finds the battle struct
replaced seconds later. This diagnostic presses the SAME keys through the
SAME window channel and reads the roster base after every press, so the
press that changes it (or proves nothing did) is identified.

Read-only stub use (one read per interrupt, cont after every read) plus real
window input. Pass a paused run receipt: python tools/diag_a51_manual_watch.py
--receipt outputs/autobattle/<run>/run.json
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from c3_manual_layer import (Monitor, pid_alive, sendkey,  # noqa: E402
                            CMD_CURSOR, TARGET_X)
from fixture_guard import BATTLE_STRUCT, ROSTER, STRIDE  # noqa: E402

ROUTE = ["DOWN", "UP", "A", "DOWN", "A", "DOWN", "A", "A"]


def u32(raw):
    return int.from_bytes(raw, "little") if raw and len(raw) >= 4 else None


def u16(raw):
    return int.from_bytes(raw, "little") if raw and len(raw) >= 2 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--settle", type=float, default=2.0)
    ap.add_argument("--route", default=",".join(ROUTE))
    ap.add_argument("--monitor-seconds", type=float, default=0.0,
                    help="after the route, keep sampling for this long")
    args = ap.parse_args()

    leg1 = json.load(open(args.receipt, encoding="utf-8"))
    handoff = leg1.get("manual_handoff") or {}
    pid, port = handoff.get("pid"), int(handoff.get("port") or 2345)
    if not pid or not pid_alive(pid):
        print(f"FAIL: no live handed-off emulator for pid {pid}")
        return 2
    mon = Monitor(port)
    t0 = time.time()

    def snap(tag):
        count = u32(mon.read(BATTLE_STRUCT, 4))
        name = u32(mon.read(ROSTER, 4))
        tile = mon.read(ROSTER + STRIDE * 6 + 0xF6, 2)
        ct = u16(mon.read(ROSTER + STRIDE * 6 + 0xD0, 2))
        cmd = mon.read(CMD_CURSOR, 1)
        tgt = mon.read(TARGET_X, 2)
        print(f"[{time.time() - t0:6.1f}s] {tag:28s} count={count} "
              f"slot0_name={hex(name) if name else name} "
              f"slot6=({tuple(tile) if tile else None}, ct={ct}) "
              f"cmd={tuple(cmd) if cmd else None} tgt={tuple(tgt) if tgt else None}",
              flush=True)

    print(f"adopted pid={pid} port={port} (read-only monitor)")
    snap("initial")
    for key in [k for k in (args.route or "").split(",") if k]:
        sendkey(pid, f"{key}:200")
        time.sleep(args.settle)
        snap(f"after {key}")
    end = time.time() + args.monitor_seconds
    while time.time() < end:
        time.sleep(5.0)
        snap("idle")
    mon.detach()
    print("done (core resumed, client closed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
