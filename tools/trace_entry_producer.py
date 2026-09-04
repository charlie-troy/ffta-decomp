"""Catch the action-entry producer and limit writer with hardware watchpoints.

From the pick-stage trace (tools/trace_pick.py): the actor's 8-entry
0x90-stride action-entry table sits at 0x20223ac (battle-heap), the AI
struct at 0x02031cb8 with the mode=1 record-limit u16 at ai+0x5270.

This tool sets write watchpoints on
  - 0x20223ac (entry 0, first word: target unit pointer),
  - 0x20223ac+0x90*4 (entry 4, first mode=1-regime entry),
  - ai+0x5270 (the mode=1 limit),
plus the sort-entry breakpoint, then injects the A-confirm and logs every
stop: PC, LR, and the watch address parsed from the stop reply.

Prediction to falsify: the entry table is written by a specific setup
function (per-target action entries), and the limit 4 is written either
by the same producer or by battle/AI init.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

POLL_PATCH = 0x0800048A
PATCH_BYTES = "0121c046"
PATCH_ORIG = "811c5940"
SORT_ENTRY = 0x080C2940

AI = 0x02031CB8
ENTRY0 = 0x020223AC
ENTRY4 = ENTRY0 + 0x90 * 4
LIMIT1 = AI + 0x5270

WATCHES = {
    ENTRY0: "entry0.word0",
    ENTRY4: "entry4.word0",
    LIMIT1: "ai.mode1_limit",
}


def name_watch(stop_reply):
    m = re.search(r"watch:([0-9a-f]+)", stop_reply or "")
    if not m:
        return None
    return WATCHES.get(int(m.group(1), 16), f"watch:{m.group(1)}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="outputs/mgba-snowball/entry-producer.json")
    p.add_argument("--max-stops", type=int, default=30)
    p.add_argument("--idle-timeout", type=float, default=60.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    for addr, name in WATCHES.items():
        print(f"watch write {name} @ {addr:#x} -> "
              f"{gdb.send(f'Z2,{addr:x},2')!r}")
    print(f"sort bp -> {gdb.send(f'Z0,{SORT_ENTRY:x},2')!r}")

    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")
    print("confirm injected; collecting")

    events = []
    pending = stop
    gdb.sock.settimeout(args.idle_timeout)
    try:
        while len(events) < args.max_stops:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            pc = regs[15] if regs and len(regs) >= 16 else None
            lr = regs[14] if regs and len(regs) >= 15 else None
            w = name_watch(pending)
            ev = {
                "stop": pending,
                "watch": w,
                "pc": f"{pc:08x}" if pc is not None else None,
                "lr": f"{lr:08x}" if lr is not None else None,
            }
            if pc == SORT_ENTRY:
                ev["note"] = "sort entry reached - done"
                events.append(ev)
                print(f"stop {len(events):2d}: SORT ENTRY (ai={regs[0]:#x})")
                break
            events.append(ev)
            label = w or "stop"
            print(f"stop {len(events):2d}: {label} pc={ev['pc']} "
                  f"lr={ev['lr']} [{pending}]")
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"collection ended: {exc}")

    try:
        for addr in WATCHES:
            gdb.send(f"z2,{addr:x},2")
        gdb.send(f"z0,{SORT_ENTRY:x},2")
        gdb.cont()
    except Exception:
        pass
    gdb.close()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="\n") as fh:
        json.dump({"watches": {f"{a:#x}": n for a, n in WATCHES.items()},
                   "events": events}, fh, indent=1)
    print(f"wrote {args.out} ({len(events)} stops)")
    return 0 if events else 1


if __name__ == "__main__":
    sys.exit(main())
