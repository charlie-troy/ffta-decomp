"""A2 experiment: catch the sequencer dispatcher's first run after a turn boundary.

Arms a GDB breakpoint at the sequencer phase dispatcher (0x080C045C), waits
while the player turn sits in its menu, then -- after the operator (or a
concurrent Lua drive) ends the turn -- records the first N dispatcher hits:
active actor (ctx entries[0]), its allegiance bit, phase, and the LR call-site
that entered the dispatcher. This names who launches the sequencer and for
whom, which is the player-to-AI control boundary.

Usage:
    python tools/exp_dispatcher_boundary.py [--hits 6] [--timeout 240]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

CTX = 0x020101F8
ENTRIES = CTX + 4
PHASE = CTX + 0x54F4
BRANCH = CTX + 0x54AF
DISPATCH = 0x080C045C


def u32(b):
    return int.from_bytes(b, "little")


def u16(b):
    return int.from_bytes(b, "little")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    p.add_argument("--hits", type=int, default=6)
    p.add_argument("--timeout", type=float, default=240.0)
    p.add_argument("--out", default="outputs/lua-nav/dispatcher-boundary.json")
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    print(f"break {DISPATCH:#010x} -> {gdb.send(f'Z0,{DISPATCH:x},2')!r}")
    rows = []
    pending = None
    gdb.sock.settimeout(args.timeout)
    t0 = time.time()
    try:
        while len(rows) < args.hits:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                print(f"unexpected stop: {pending!r}")
                break
            regs = gdb.read_registers()
            if not regs or regs[15] != DISPATCH:
                pending = None
                continue
            entries = u32(gdb.read_mem(ENTRIES, 4))
            unit = u32(gdb.read_mem(entries, 4)) if entries else 0
            side = None
            ctrl = None
            tile = None
            if unit:
                side = bool(u16(gdb.read_mem(unit + 0x28, 2)) & 0x8000)
                ctrl = bool(gdb.read_mem(unit + 0xED, 1)[0] & 0x8)
                tile = list(gdb.read_mem(unit + 0xF6, 2))
            r = {
                "i": len(rows),
                "t": round(time.time() - t0, 1),
                "pc": regs[15],
                "lr": regs[14],
                "sp": regs[13],
                "phase": u16(gdb.read_mem(PHASE, 2)),
                "branch": gdb.read_mem(BRANCH, 1)[0],
                "entries": entries,
                "unit": unit,
                "side_ai": side,
                "controlled": ctrl,
                "tile": tile,
                "stack": [u32(gdb.read_mem(regs[13] + 4 * k, 4))
                          for k in range(8)],
            }
            rows.append(r)
            print(f"[{r['i']}] t={r['t']}s lr={regs[14]:#010x} "
                  f"unit={unit:#09x} side_ai={side} ctrl={ctrl} "
                  f"phase={r['phase']} branch={r['branch']:#04x} "
                  f"tile={tile}", flush=True)
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"ended after {len(rows)} rows: {exc}")
    finally:
        try:
            gdb.send(f"z0,{DISPATCH:x},2")
            gdb.cont()
        except Exception:
            pass
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", newline="\n") as fh:
            json.dump(rows, fh, indent=1)
        gdb.close()
        print(f"wrote {len(rows)} rows -> {args.out}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
