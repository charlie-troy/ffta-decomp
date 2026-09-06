"""Force an out-of-range AI turn by teleporting the actor far away.

The AI's position sense comes from the action-entry pixel coords (entry+8/
+0xC, u16 pixel = tile*16) and the unit's canonical tile (unit+0xF6/+0xF7).
Both are rewritten at the actor's first phase-9 dispatch to tile (TX,TY),
which should put every harm-pool target out of range of every ability. We
then trace the resulting march: whether the AI picks a movement/fallback
candidate, walks (writes to the canonical or slot tile), or ends passive.

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
PH4 = 0x080C09EC


def u16(b):
    return int.from_bytes(b, "little")


def u32(b):
    return int.from_bytes(b, "little")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tx", type=int, default=1)
    p.add_argument("--ty", type=int, default=1)
    p.add_argument("--timeout", type=float, default=120.0)
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
            phase = u16(gdb.read_mem(CTX + 0x54F4, 2))
            if actor:
                break
        pending = None
    if not actor:
        print("never reached the actor's turn")
        return 1

    t = gdb.read_mem(actor + 0xF6, 2)
    px = u16(gdb.read_mem(entry + 8, 2))
    py = u16(gdb.read_mem(entry + 0xC, 2))
    print(f"actor {actor:#x} entry {entry:#x} tile=({t[0]},{t[1]}) "
          f"entry_px=({px},{py}) phase={phase}")

    # Teleport: unit tile bytes + entry pixel coords (u16, tile*16).
    gdb.send(f"M{actor + 0xF6:x},1:{args.tx:02x}")
    gdb.send(f"M{actor + 0xF7:x},1:{args.ty:02x}")
    gdb.send(f"M{entry + 8:x},2:{(args.tx * 16) & 0xFFFF:04x}")
    gdb.send(f"M{entry + 0xC:x},2:{(args.ty * 16) & 0xFFFF:04x}")
    t2 = gdb.read_mem(actor + 0xF6, 2)
    px2 = u16(gdb.read_mem(entry + 8, 2))
    print(f"teleported unit tile=({t2[0]},{t2[1]}) entry_px=({px2},"
          f"{u16(gdb.read_mem(entry + 0xC, 2))})")

    # Trace the march from here: the dispatcher breakpoint stays armed;
    # add the one-shot canonical-tile watch (re-armed after each event).
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
            phase = u16(gdb.read_mem(CTX + 0x54F4, 2))
            if pc == DISPATCH:
                tag = f"phase{phase}"
                if phase == 4 and not decision_logged:
                    handler = u32(gdb.read_mem(HANDLER, 4))
                    ability = u16(gdb.read_mem(DECISION + 8, 2))
                    rule = u16(gdb.read_mem(DECISION + 0xA, 2))
                    events.append({"note": "decision",
                                   "handler": handler, "ability": ability,
                                   "rule": rule})
                    print(f"DECISION handler={handler:#x} ability={ability} "
                          f"rule={rule}", flush=True)
                    decision_logged = True
            else:
                tag = "WATCH"
                # One-shot watch fired: re-arm so later writes are caught.
                gdb.send(f"Z2,{actor + 0xF6:x},2")
            ev = {"tag": tag, "phase": phase, "tile": [tile[0], tile[1]],
                  "pc": pc}
            events.append(ev)
            print(f"{tag:>8}: phase={phase} tile=({tile[0]},{tile[1]}) "
                  f"pc={pc:#x}", flush=True)

    except (TimeoutError, OSError) as exc:
        print(f"teleport trace stopped: {exc}")
    finally:
        try:
            gdb.send(f"z2,{actor + 0xF6:x},2")
            gdb.send(f"z0,{DISPATCH:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    final = events[-1]["tile"] if events else list(t)
    out = args.out or ("outputs/mgba-snowball/teleport-far-%d-%d.json"
                       % (args.tx, args.ty))
    with open(out, "w", newline="\n") as fh:
        json.dump({"tx": args.tx, "ty": args.ty, "actor": actor,
                   "entry": entry, "events": events}, fh, indent=1)
    print(f"\n{len(events)} events; final tile {final}; wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
