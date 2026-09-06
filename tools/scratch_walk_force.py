"""Force an out-of-range AI turn: rewrite EVERY position field of record.

The earlier teleport probe (`scratch_teleport_far.py`) rewrote only the unit's
canonical tile (unit+0xF6/+0xF7) and the entry pixel coords (entry+8/+0xC).
Its trace proved those are NOT the position of record: the rewritten (1,1)
held through phases 10->0->1->2->3->decision->4 and only phase 8 restored
x=6 from ctx+0x54CA (the turn-starter's queue slot, written at 0x080C041E/
0x0428 and consumed by the phase 8/13 strb tail). So this run additionally
rewrites ctx+0x54CA/54CB to the far tile BEFORE the phase-9/10 grid build,
which is the first code that consumes the position.

If the throw has a finite range, the AI at (TX,TY) with every target 10+
tiles away must either walk (approach), pick a fallback, or go passive. If
the throw is data-map-wide, the decision stays byte-identical. Either result
closes the question the docs left open.

Usage: same harness as the other probes (state-facing.ss0, RNG frozen).
"""
import argparse
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
HANDLER = CTX + 0x528C
DECISION = CTX + 0x5290
TILEQ = CTX + 0x54CA          # turn-starter's committed tile (position of record)
PHASE = CTX + 0x54F4


def u16(b):
    return int.from_bytes(b, "little")


def u32(b):
    return int.from_bytes(b, "little")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tx", type=int, default=1)
    p.add_argument("--ty", type=int, default=1)
    p.add_argument("--timeout", type=float, default=150.0)
    p.add_argument("--out", default=None)
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

    # Sync to the actor's first dispatcher stop.
    actor = None
    entry = None
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
            entry = u32(gdb.read_mem(CTX + 4, 4))
            actor = u32(gdb.read_mem(entry, 4)) if entry else 0
            phase = u16(gdb.read_mem(PHASE, 2))
            if actor:
                break
        pending = None
    if not actor:
        print("never reached the actor's turn")
        return 1

    t = gdb.read_mem(actor + 0xF6, 2)
    q = gdb.read_mem(TILEQ, 2)
    px = u16(gdb.read_mem(entry + 8, 2))
    py = u16(gdb.read_mem(entry + 0xC, 2))
    print(f"actor {actor:#x} entry {entry:#x} phase={phase} "
          f"unit_tile=({t[0]},{t[1]}) ctxq=({q[0]},{q[1]}) "
          f"entry_px=({px},{py})")

    # Teleport every known position-of-record field to (TX,TY):
    #   1. unit canonical tile bytes
    #   2. entry pixel coords (u16, tile*16)
    #   3. ctx turn-starter queue tile (the phase-8 restore source)
    gdb.send(f"M{actor + 0xF6:x},1:{args.tx:02x}")
    gdb.send(f"M{actor + 0xF7:x},1:{args.ty:02x}")
    gdb.send(f"M{entry + 8:x},2:{(args.tx * 16) & 0xFFFF:04x}")
    gdb.send(f"M{entry + 0xC:x},2:{(args.ty * 16) & 0xFFFF:04x}")
    gdb.send(f"M{TILEQ:x},1:{args.tx:02x}")
    gdb.send(f"M{TILEQ + 1:x},1:{args.ty:02x}")

    # Read-only census of battle-container slot records pointing at the actor
    # (0x108-byte slots whose first word is the unit pointer): report the
    # bytes at the offsets where a mirrored tile could live, without writing.
    slots = []
    for base in (0x02015000, 0x020159E4):
        for off in range(0, 0x110 * 16, 0x108):
            blob = gdb.read_mem(base + off, 0x100)
            if not blob:
                continue
            ptr = u32(blob[0:4])
            if ptr == actor:
                slots.append((base + off, blob))
    for s, blob in slots:
        print(f"  slot@{s:#x}: tileF6={blob[0xF6]:02x},{blob[0xF7]:02x} "
              f"D0ct={int.from_bytes(blob[0xD0:0xD2], 'little')}")
    print(f"teleported unit tile, entry px, ctxq -> ({args.tx},{args.ty}); "
          f"{len(slots)} actor slot(s) found (read-only)")

    t2 = gdb.read_mem(actor + 0xF6, 2)
    q2 = gdb.read_mem(TILEQ, 2)
    print(f"verify unit_tile=({t2[0]},{t2[1]}) ctxq=({q2[0]},{q2[1]})")

    # Trace the march: dispatcher breakpoint stays armed; watch the canonical
    # tile (one-shot, re-armed) for any walk write.
    gdb.send(f"Z2,{actor + 0xF6:x},2")

    events = []
    decision_logged = False
    start = time.time()
    gdb.sock.settimeout(25)
    try:
        while time.time() - start < args.timeout:
            gdb.cont()
            pkt = gdb._read_packet()
            if not pkt or pkt[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                continue
            pc = regs[15]
            tile = gdb.read_mem(actor + 0xF6, 2)
            q = gdb.read_mem(TILEQ, 2)
            phase = u16(gdb.read_mem(PHASE, 2))
            tag = "phase" if pc == DISPATCH else "WATCH"
            if pc == DISPATCH and phase == 4 and not decision_logged:
                handler = u32(gdb.read_mem(HANDLER, 4))
                ability = u16(gdb.read_mem(DECISION + 8, 2))
                rule = u16(gdb.read_mem(DECISION + 0xA, 2))
                events.append({"note": "decision", "handler": handler,
                               "ability": ability, "rule": rule})
                print(f"DECISION handler={handler:#x} ability={ability} "
                      f"rule={rule}", flush=True)
                decision_logged = True
            if pc != DISPATCH:
                gdb.send(f"Z2,{actor + 0xF6:x},2")
            tile = tile if tile else b"\0\0"
            q = q if q else b"\0\0"
            ev = {"tag": tag, "phase": phase, "tile": [tile[0], tile[1]],
                  "ctxq": [q[0], q[1]], "pc": pc}
            events.append(ev)
            print(f"{tag:>7}: phase={phase} tile=({tile[0]},{tile[1]}) "
                  f"ctxq=({q[0]},{q[1]}) pc={pc:#x}", flush=True)

    except (TimeoutError, OSError, EOFError) as exc:
        print(f"trace stopped: {exc}")
    finally:
        try:
            gdb.send(f"z2,{actor + 0xF6:x},2")
            gdb.send(f"z0,{DISPATCH:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    out = args.out or ("outputs/mgba-snowball/walk-force-%d-%d.json"
                       % (args.tx, args.ty))
    with open(out, "w", newline="\n") as fh:
        json.dump({"tx": args.tx, "ty": args.ty, "actor": actor,
                   "entry": entry, "events": events}, fh, indent=1)
    print(f"\n{len(events)} events; decision_logged={decision_logged}; "
          f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
