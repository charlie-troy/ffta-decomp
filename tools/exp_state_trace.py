"""A2.3 v14: breakpoint the turn-flow dispatcher and log its state values.

Marche's menu is open. One GDB session:
1. Arm a breakpoint on the dispatcher 0x0809ED38.
2. Drive Wait (DOWN DOWN A A) to end Marche's turn.
3. Log every dispatcher hit for 60s: obj (r0), state ([r0+0xCC]), lr.
4. Remove breakpoint, resume, disconnect.

Usage:
    python tools/exp_state_trace.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
DISPATCH = 0x0809ED38
MARCHE = 0x02001F1C


def set_reg(gdb, n, value):
    return gdb.send(f"P{n:x}=" + value.to_bytes(4, "little").hex())


def force_key(gdb, mask, frames, tag=""):
    hits = 0
    for _ in range(frames):
        gdb.cont()
        stop = gdb._read_packet()
        regs = gdb.read_registers()
        if not regs or regs[15] != KEY_BL:
            if regs:
                print(f"  ! stop at {regs[15]:#010x}")
            continue
        set_reg(gdb, 1, (regs[1] | mask) & 0x3FF)
        hits += 1
    print(f"  forced {mask:#04x} x{hits} {tag}")
    return hits


def press(gdb, mask, frames=4, pause=0.6, tag=""):
    gdb.send(f"Z0,{KEY_BL:x},2")
    force_key(gdb, mask, frames, tag)
    gdb.send(f"z0,{KEY_BL:x},2")
    gdb.cont()
    time.sleep(pause)


def main():
    gdb = Gdb("127.0.0.1", 2345, timeout=10)
    gdb.send("?")
    out = {}

    gdb.interrupt()
    mid = gdb.read_mem(MARCHE + 0x104, 2)
    print(f"marche id={mid[0]:02x}")
    gdb.cont()

    print("menu: DOWN, DOWN, A, arm, A ...")
    press(gdb, 0x80, 4, 0.8, "DOWN->Action")
    press(gdb, 0x80, 4, 0.8, "DOWN->Wait")
    press(gdb, 0x01, 4, 1.2, "A=select")
    reply = gdb.send(f"Z0,{DISPATCH:x},2")
    print(f"breakpoint: {reply!r}")
    press(gdb, 0x01, 4, 0.1, "A=confirm")

    events = []
    t0 = time.time()
    try:
        while time.time() - t0 < 60:
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if regs and regs[15] == DISPATCH:
                r0 = regs[0]
                st = gdb.read_mem(r0 + 0xCC, 2)
                state = int.from_bytes(st, "little") if st else -1
                lr = regs[14]
                events.append({"state": state, "obj": hex(r0), "lr": hex(lr)})
                if len(events) <= 50 or state in (3, 6, 0x19):
                    print(f"DISPATCH obj={r0:#010x} state={state:#04x} lr={lr:#010x}")
                if len(events) >= 400:
                    break
            gdb.cont()
    except (TimeoutError, OSError) as exc:
        print(f"trace ended: {exc}")

    try:
        gdb.send(f"z0,{DISPATCH:x},2")
        gdb.cont()
    except Exception:
        pass
    out["events"] = events
    gdb.close()

    os.makedirs("outputs/lua-nav", exist_ok=True)
    with open("outputs/lua-nav/state-trace.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote outputs/lua-nav/state-trace.json ({len(events)} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
