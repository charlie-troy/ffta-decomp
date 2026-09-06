"""Order the canonical-tile write against the phase-8 sync-copy loop.

Combines a 2-byte write watch on the actor's canonical tile with auto-repeat
breakpoints on the phase-8 strb commits and the sync-copy call site, so a
single run settles whether the sync loop (or something between the strb
commits and the loop) is what changes the actor's canonical tile to its final
value.
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
PH8_STRB_X = 0x080C107E
PH8_STRB_Y = 0x080C108C
SYNC_CALL = 0x0809F89A


def u16(b):
    return int.from_bytes(b, "little")


def u32(b):
    return int.from_bytes(b, "little")


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--out", default="outputs/mgba-snowball/watch-sync.json")
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
    # Repeating breakpoints first; the one-shot watch armed last.
    gdb.send(f"Z0,{SYNC_CALL:x},2")
    gdb.send(f"Z0,{PH8_STRB_X:x},2")
    gdb.send(f"Z0,{PH8_STRB_Y:x},2")
    gdb.send(f"Z2,{actor + 0xF6:x},2")

    sync_idx = 0
    events = []
    watch_fired = False
    start = time.time()
    gdb.sock.settimeout(25)
    try:
        while not (watch_fired and sync_idx >= 9) and time.time() - start < args.timeout:
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
            if pc == SYNC_CALL:
                sync_idx += 1
                tag = f"sync#{sync_idx}"
            elif pc == PH8_STRB_X:
                tag = "strb-x"
            elif pc == PH8_STRB_Y:
                tag = "strb-y"
            else:
                tag = "WATCH"      # hardware-watch stop; pc after the store
                watch_fired = True
            ev = {"tag": tag, "pc": pc, "phase": phase,
                  "tile": [tile[0], tile[1]], "sync_idx": sync_idx,
                  "r0": regs[0], "r1": regs[1], "r2": regs[2]}
            events.append(ev)
            print(f"{tag:>7}: phase={phase} tile=({tile[0]},{tile[1]}) "
                  f"sync_idx={sync_idx} pc={pc:#x} r0={regs[0]:#x} "
                  f"r1={regs[1]:#x} r2={regs[2]:#x}", flush=True)
            if watch_fired:
                # Re-arm the one-shot watch after it fires.
                gdb.send(f"Z2,{actor + 0xF6:x},2")
    except (TimeoutError, OSError) as exc:
        print(f"watch+sync stopped: {exc}")
    finally:
        try:
            gdb.send(f"z2,{actor + 0xF6:x},2")
            gdb.send(f"z0,{SYNC_CALL:x},2")
            gdb.send(f"z0,{PH8_STRB_X:x},2")
            gdb.send(f"z0,{PH8_STRB_Y:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    out = args.out
    with open(out, "w", newline="\n") as fh:
        json.dump({"actor": actor, "events": events}, fh, indent=1)
    print(f"\n{len(events)} events (watch fired {watch_fired}); wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
