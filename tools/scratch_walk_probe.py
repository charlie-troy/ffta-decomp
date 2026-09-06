"""Watch the AI actor's tile during its turn, optionally teleported far.

Baseline (no teleport) reproduces the stationary ranged throw. With
--teleport X,Y the actor's unit tile (unit+0xF6/+0xF7) is rewritten right
after its turn begins (first dispatcher stop), so an out-of-range target
forces the approach decision: any walk shows up as 2-byte write-watch hits
on unit+0xF6, each logged with the PC (the walk-site candidate) and phase.

Run with the mGBA stub up from state-facing.ss0, exactly like the other
trace_*/scratch_* probes.

Usage:
    python tools/scratch_walk_probe.py                 # control
    python tools/scratch_walk_probe.py --teleport 24,5 # forced approach
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

CTX = 0x020101F8
DISPATCH = 0x080C045C
RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_LEN = 4
PATCH_BYTES = "0121c046"   # movs r1, #1 ; nop  (forces A held)
PATCH_ORIG = "811c5940"    # adds r1, r2, #0 ; eors r1, r3 (retail)


def u16(b):
    return int.from_bytes(b, "little")


def u32(b):
    return int.from_bytes(b, "little")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--teleport", default=None,
                   help="X,Y tile to move the actor to before its action")
    p.add_argument("--watch", default=None,
                   help="address to write-watch (default: the actor tile)")
    p.add_argument("--timeout", type=float, default=45.0,
                   help="idle seconds before giving up")
    p.add_argument("--out", default=None)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    gdb.send(f"M{RNG:x},4:78563412")
    gdb.send(f"Z0,{DISPATCH:x},2")

    # Facing-confirm A press.
    gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_BYTES}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_ORIG}")

    # Wait for the first dispatcher stop on the actor's turn.
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
    print(f"actor {actor:#x} at tile ({t[0]},{t[1]}) phase={phase}")

    if args.teleport:
        x, y = (int(v) for v in args.teleport.split(","))
        gdb.send(f"M{actor + 0xF6:x},1:{x:02x}")
        gdb.send(f"M{actor + 0xF7:x},1:{y:02x}")
        t2 = gdb.read_mem(actor + 0xF6, 2)
        print(f"teleported to ({t2[0]},{t2[1]})")

    # Drop the dispatcher break, arm a write watch on the tile, run free.
    gdb.send(f"z0,{DISPATCH:x},2")
    watch_addr = (int(args.watch, 0) if args.watch
                  else actor + 0xF6)
    gdb.send(f"Z2,{watch_addr:x},2")
    events = []
    start = time.time()
    gdb.sock.settimeout(args.timeout)
    try:
        while time.time() - start < args.timeout:
            gdb.cont()
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                continue
            pc = regs[15]
            tile = gdb.read_mem(actor + 0xF6, 2)
            saved = gdb.read_mem(CTX + 0x54CA, 2)
            phase = u16(gdb.read_mem(CTX + 0x54F4, 2))
            r0 = regs[0] if len(regs) > 0 else 0
            r1 = regs[1] if len(regs) > 1 else 0
            r2 = regs[2] if len(regs) > 2 else 0
            lr = regs[14] if len(regs) > 14 else 0
            # Snapshot the source/dest heads so we can see where the
            # committed tile value lives (both should be RAM pointers at
            # the top of a copy routine).
            src_head = dst_head = None
            if 0x02000000 <= r1 < 0x03008000 or 0x03000000 <= r1 < 0x03008000:
                src_head = gdb.read_mem(r1, 8)
            if 0x02000000 <= r0 < 0x03008000:
                dst_head = gdb.read_mem(r0, 8)
            ev = {"pc": pc, "tile": [tile[0], tile[1]],
                  "saved": [saved[0], saved[1]], "phase": phase,
                  "r0": r0, "r1": r1, "r2": r2, "lr": lr,
                  "src_head": src_head.hex() if src_head else None,
                  "dst_head": dst_head.hex() if dst_head else None}
            events.append(ev)
            print(f"  write: pc={pc:#x} tile=({tile[0]},{tile[1]}) "
                  f"phase={phase} r0={r0:#x} r1={r1:#x} r2={r2:#x} "
                  f"lr={lr:#x} src={src_head.hex() if src_head else '-'} "
                  f"dst={dst_head.hex() if dst_head else '-'}", flush=True)
    except (TimeoutError, OSError) as exc:
        print(f"watch stopped: {exc}")
    finally:
        try:
            gdb.send(f"z2,{actor + 0xF6:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    final = events[-1]["tile"] if events else list(t)
    print(f"\n{len(events)} write(s); final tile {final}")
    if args.out:
        out = args.out
    elif args.teleport:
        out = ("outputs/mgba-snowball/walk-teleport-"
               + args.teleport.replace(",", "-") + ".json")
    elif args.watch:
        out = "outputs/mgba-snowball/walk-watch-" + args.watch + ".json"
    else:
        out = "outputs/mgba-snowball/walk-control.json"
    with open(out, "w", newline="\n") as fh:
        json.dump({"teleport": args.teleport, "watch": args.watch,
                   "actor": actor, "events": events}, fh, indent=1)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
