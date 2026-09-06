"""Reconstruct the phase-8 write sequence for the acting unit.

Breakpoints (auto-repeat) on: the phase-8 handler head, its two strb
tile-commit instructions, and the unit-record sync-copy call. At every stop we
log the phase, the actor's canonical tile, ctx+0x54CA/54CB (the queued tile),
and the working registers so the exact order and direction of the canonical
tile's final write is settled by observation rather than inference.
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
PATCH_BYTES = "0121c046"
PATCH_ORIG = "811c5940"
PH8_HEAD = 0x080C1068      # phase-8 handler head
PH8_STRB_X = 0x080C107E    # strb unit.x = ctx+0x54CA
PH8_STRB_Y = 0x080C108C    # strb unit.y = ctx+0x54CB
SYNC_CALL = 0x0809F89A     # library copy call in the unit-record sync loop
LOW = 0x02000000
HIGH = 0x03008000

NAMES = {PH8_HEAD: "ph8-head", PH8_STRB_X: "ph8-strb-x",
         PH8_STRB_Y: "ph8-strb-y", SYNC_CALL: "sync-call"}


def u16(b):
    return int.from_bytes(b, "little")


def u32(b):
    return int.from_bytes(b, "little")


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-events", type=int, default=60)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--out", default="outputs/mgba-snowball/phase8-seq.json")
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

    # Wait for the actor's first dispatcher stop (phase 9).
    actor = None
    pending = stop
    gdb.sock.settimeout(20)
    for _ in range(200):
        if pending is None:
            gdb.cont()
            pending = gdb._read_packet()
        if not pending or pending[:1] not in ("S", "T"):
            raise RuntimeError(f"unexpected stop: {pending!r}")
        regs = gdb.read_registers()
        if regs and len(regs) >= 16 and regs[15] == DISPATCH:
            entries = u32(gdb.read_mem(CTX + 4, 4))
            actor = u32(gdb.read_mem(entries, 4)) if entries else 0
            phase = u16(gdb.read_mem(CTX + 0x54F4, 2))
            if actor:
                break
        pending = None
    if not actor:
        print("never reached the actor's turn")
        return 1

    t = gdb.read_mem(actor + 0xF6, 2)
    print(f"actor {actor:#x} tile=({t[0]},{t[1]}) phase={phase}")

    # Drop the dispatcher stop, arm the four breakpoints.
    gdb.send(f"z0,{DISPATCH:x},2")
    for bp in (PH8_HEAD, PH8_STRB_X, PH8_STRB_Y, SYNC_CALL):
        gdb.send(f"Z0,{bp:x},2")

    events = []
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
            if pc not in NAMES:
                continue
            queued = gdb.read_mem(CTX + 0x54CA, 2)
            tile = gdb.read_mem(actor + 0xF6, 2)
            phase = u16(gdb.read_mem(CTX + 0x54F4, 2))
            ev = {"site": NAMES[pc], "pc": pc, "phase": phase,
                  "queued": [queued[0], queued[1]],
                  "tile": [tile[0], tile[1]],
                  "r0": regs[0], "r1": regs[1], "r2": regs[2], "r3": regs[3]}
            events.append(ev)
            print(f"{NAMES[pc]:>10}: phase={phase} queued=({queued[0]},{queued[1]}) "
                  f"tile=({tile[0]},{tile[1]}) r0={regs[0]:#x} r1={regs[1]:#x} "
                  f"r2={regs[2]:#x}", flush=True)
    except (TimeoutError, OSError) as exc:
        print(f"phase-8 seq stopped: {exc}")
    finally:
        try:
            for bp in (PH8_HEAD, PH8_STRB_X, PH8_STRB_Y, SYNC_CALL):
                gdb.send(f"z0,{bp:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    out = args.out
    with open(out, "w", newline="\n") as fh:
        json.dump({"actor": actor, "events": events}, fh, indent=1)
    print(f"\n{len(events)} phase-8 events; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
