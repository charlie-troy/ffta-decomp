"""A2 experiment: catch the turn manager (sub_0809E05C) across a turn boundary.

Arms a GDB breakpoint at the turn manager entry (r0 = battle struct) and
records every hit: registers, LR call-site, RNG, and a raw dump of the battle
struct's first 0x60 bytes (actor slots + count). Set-and-continue only -- the
stub is never polled, so the Lua key-injection channel can drive the menu
while this waits for the player-to-enemy boundary.

Usage:
    python tools/exp_turn_manager.py --hits 40 --timeout 300 [--out FILE]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

TURN_MANAGER = 0x0809E05C
BATTLE_STRUCT = 0x020159E4
RNG = 0x030034B0


def u32(gdb, addr):
    b = gdb.read_mem(addr, 4)
    return int.from_bytes(b, "little") if b else 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    p.add_argument("--hits", type=int, default=40)
    p.add_argument("--timeout", type=float, default=300.0)
    p.add_argument("--struct", type=lambda v: int(v, 0), default=BATTLE_STRUCT)
    p.add_argument("--out", default="outputs/lua-nav/turn-manager.json")
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    reply = gdb.send(f"Z0,{TURN_MANAGER:x},2")
    print(f"break {TURN_MANAGER:#010x} -> {reply!r}", flush=True)
    if reply != "OK":
        return 1

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
                print(f"unexpected stop: {pending!r}", flush=True)
                break
            regs = gdb.read_registers()
            if not regs or regs[15] != TURN_MANAGER:
                pending = None
                continue
            rng = gdb.read_mem(RNG, 4)
            row = {
                "i": len(rows),
                "t": round(time.time() - t0, 1),
                "lr": regs[14],
                "r0": regs[0],
                "r1": regs[1],
                "r2": regs[2],
                "r3": regs[3],
                "rng": int.from_bytes(rng, "little") if rng else None,
                "struct": gdb.read_mem(args.struct, 0x60).hex(),
            }
            rows.append(row)
            print(f"[{row['i']:>3}] t={row['t']:>6}s lr={regs[14]:#010x} "
                  f"r0={regs[0]:#010x} r1={regs[1]:#010x}", flush=True)
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"ended after {len(rows)} rows: {exc}", flush=True)
    finally:
        try:
            gdb.send(f"z0,{TURN_MANAGER:x},2")
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
