"""Attribute the phase-8 tile commit to a specific library copy call.

The control walk probe showed the acting unit's canonical tile (unit+0xF6)
jumps (6,7) -> (6,5) in one write at phase 8, executed from the IWRAM copy
library (pc 0x03005F08). The ROM call site of that library is inside a sync
loop at 0x0809F850 (copy call at 0x0809F89A: bl -> bx r3, r3 = [0x0836D4BC]).
Registers read *inside* the library are mid-loop working values, so instead we
break at the call site itself and log the clean arguments (r0=src, r1=dst,
r2=len) plus the tile values at src+0xF6 / dst+0xF6, which identifies the
source record that already held the committed tile.

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
SYNC_FN = 0x0809F850      # sync loop head (copies every unit's record)
SYNC_CALL = 0x0809F89A    # bl -> library copy inside the loop
RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_LEN = 4
PATCH_BYTES = "0121c046"   # movs r1, #1 ; nop  (forces A held)
PATCH_ORIG = "811c5940"    # retail
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
    p.add_argument("--hits", type=int, default=40,
                   help="max copy-call hits to record")
    p.add_argument("--timeout", type=float, default=110.0)
    p.add_argument("--out", default="outputs/mgba-snowball/copy-sync.json")
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

    gdb.send(f"z0,{DISPATCH:x},2")
    gdb.send(f"Z0,{SYNC_CALL:x},2")
    hits = []
    start = time.time()
    gdb.sock.settimeout(25)
    try:
        while len(hits) < args.hits and time.time() - start < args.timeout:
            gdb.cont()
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if not regs or len(regs) < 16 or regs[15] != SYNC_CALL:
                continue
            r0, r1, r2, r3 = regs[0], regs[1], regs[2], regs[3]
            r6, r7 = regs[6], regs[7]
            src_t = gdb.read_mem(r0 + 0xF6, 2) if in_ram(r0) else None
            dst_t = gdb.read_mem(r1 + 0xF6, 2) if in_ram(r1) else None
            if r0 == actor or r1 == actor or (in_ram(r0) and r0 + 0x108 > actor >= r0) \
                    or (in_ram(r1) and r1 + 0x108 > actor >= r1):
                touch = "ACTOR"
            else:
                touch = ""
            canon = gdb.read_mem(actor + 0xF6, 2)
            phase = u16(gdb.read_mem(CTX + 0x54F4, 2))
            ev = {"r0": r0, "r1": r1, "r2": r2, "r3": r3, "r6": r6,
                  "r7": r7, "phase": phase,
                  "src_tile": [src_t[0], src_t[1]] if src_t else None,
                  "dst_tile": [dst_t[0], dst_t[1]] if dst_t else None,
                  "canon": [canon[0], canon[1]],
                  "touches_actor": bool(touch)}
            hits.append(ev)
            print(f"hit {len(hits)}: r0={r0:#x} r1={r1:#x} r2={r2:#x} "
                  f"src+0xf6={src_t.hex() if src_t else '-'} "
                  f"dst+0xf6={dst_t.hex() if dst_t else '-'} "
                  f"phase={phase} {touch}", flush=True)
    except (TimeoutError, OSError) as exc:
        print(f"copy-sync watch stopped: {exc}")
    finally:
        try:
            gdb.send(f"z0,{SYNC_CALL:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    out = args.out
    with open(out, "w", newline="\n") as fh:
        json.dump({"actor": actor, "hits": hits}, fh, indent=1)
    print(f"\n{len(hits)} copy-call hits; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
