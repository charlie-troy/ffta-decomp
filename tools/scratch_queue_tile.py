"""Catch the writer of ctx+0x54CA (the queued committed-tile field).

Phase 8 of the acting unit's turn commits ctx+0x54CA/0x54CB (byte x/y) onto
the unit record's tile (unit+0xF6/0xF7). The value already sits in ctx+0x54CA
at the actor's first phase-9 dispatch and receives no writes during the whole
turn, so it is queued before the actor's turn begins. This probe boots the
savestate, forces the facing confirm, then write-watches ctx+0x54CA from the
earliest moment to catch the queuer: its PC identifies the turn-queue code and
its source registers identify the field the queue position is copied from
(which is the unit's live position during play).

Usage: same harness as the other probes (state-facing.ss0, RNG frozen).
"""
import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

CTX = 0x020101F8
DISPATCH = 0x080C045C
RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_LEN = 4
PATCH_BYTES = "0121c046"   # movs r1, #1 ; nop  (forces A held)
PATCH_ORIG = "811c5940"    # retail
QUEUED_TILE = CTX + 0x54CA  # 0x020156C2, byte x at +0, byte y at +1
LOW = 0x02000000
HIGH = 0x03008000


def u16(b):
    return int.from_bytes(b, "little")


def u32(b):
    return int.from_bytes(b, "little")


def in_ram(a):
    return LOW <= a < HIGH


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-events", type=int, default=80)
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--out", default="outputs/mgba-snowball/queue-tile.json")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    gdb.send(f"M{RNG:x},4:78563412")
    gdb.send(f"Z0,{DISPATCH:x},2")
    gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_BYTES}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_ORIG}")

    # Re-consume any pending stop so the watch loop below pairs cleanly.
    pending = stop
    if pending is None or pending[:1] not in ("S", "T"):
        raise RuntimeError(f"unexpected initial stop: {pending!r}")

    # Arm the write watch on the queued tile field right away.
    gdb.send(f"z0,{DISPATCH:x},2")
    gdb.send(f"Z2,{QUEUED_TILE:x},2")

    events = []
    actor = None
    phase = None
    start = time.time()
    gdb.sock.settimeout(25)
    try:
        while len(events) < args.max_events and time.time() - start < args.timeout:
            gdb.cont()
            pkt = gdb._read_packet()
            if not pkt or pkt[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                continue
            pc = regs[15]
            val = gdb.read_mem(QUEUED_TILE, 2)
            phase = u16(gdb.read_mem(CTX + 0x54F4, 2))
            ev = {"pc": pc, "phase": phase,
                  "val": [val[0], val[1]] if val else None,
                  "r0": regs[0], "r1": regs[1], "r2": regs[2],
                  "r3": regs[3], "lr": regs[14]}
            # Snapshot src memory when a register points at a likely field.
            for name, reg in (("r0", regs[0]), ("r1", regs[1]),
                              ("r2", regs[2]), ("r3", regs[3])):
                if in_ram(reg) and reg % 4 == 0:
                    head = gdb.read_mem(reg, 0x10)
                    if head:
                        ev[name + "_head"] = head.hex()
            events.append(ev)
            print(f"write: pc={pc:#x} phase={phase} val={val.hex() if val else '-'} "
                  f"r0={regs[0]:#x} r1={regs[1]:#x} r2={regs[2]:#x} "
                  f"r3={regs[3]:#x} lr={regs[14]:#x}", flush=True)
            if actor is None:
                # First dispatcher stop after the turn starts identifies actor.
                if pc == DISPATCH and val is None:
                    pass
    except (TimeoutError, OSError) as exc:
        print(f"watch stopped: {exc}")
    finally:
        try:
            gdb.send(f"z2,{QUEUED_TILE:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    out = args.out
    with open(out, "w", newline="\n") as fh:
        json.dump({"events": events, "phase_final": phase}, fh, indent=1)
    print(f"\n{len(events)} writes to ctx+0x54ca; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
