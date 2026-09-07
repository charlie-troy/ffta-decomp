"""Force game-side key presses by patching r1 at the key-update call.

The per-frame poll composes the active-high pressed mask into r1 and calls
the key-system update at 0x08000494 (`bl 0x0800221c`). Breaking there and
OR-ing bits into r1 injects presses through the game's own edge/repeat
logic -- the only input channel that reaches battle screens, where
emu:setKeys D-pad delivery is ignored by the UI.

Usage:
  python tools/gdb_force_key.py --mask 0x80 --frames 12
  python tools/gdb_force_key.py --mask 0x80 --frames 12 --pc 0x08000494
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

POLL_BL = 0x08000494  # `bl update_keys` -- r1 = active-high pressed mask


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    p.add_argument("--mask", type=lambda v: int(v, 0), default=0x80,
                   help="pressed-mask bits to OR in (A=1 B=2 SEL=4 ST=8 "
                        "R=16 L=32 U=64 D=128)")
    p.add_argument("--frames", type=int, default=12)
    p.add_argument("--pc", type=lambda v: int(v, 0), default=POLL_BL)
    p.add_argument("--clear-first", action="store_true",
                   help="hold with no forced bits first (release shadow)")
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=10)
    gdb.send("?")
    reply = gdb.send(f"Z0,{args.pc:x},2")
    if reply != "OK":
        print(f"breakpoint rejected: {reply!r}")
        return 1

    def set_reg(n, value):
        payload = value.to_bytes(4, "little").hex()
        return gdb.send(f"P{n:x}={payload}")

    frames = 0
    try:
        for i in range(args.frames):
            gdb.cont()
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                print(f"unexpected stop: {stop!r}")
                break
            regs = gdb.read_registers()
            if regs[15] != args.pc:
                continue
            new_r1 = regs[1] & 0x3FF
            if not args.clear_first:
                new_r1 |= args.mask
            ok = set_reg(1, new_r1)
            frames += 1
            if i < 3 or i == args.frames - 1:
                print(f"hit {i+1}: r1 {regs[1]:#06x} -> {new_r1:#06x} "
                      f"(P: {ok!r})")
    finally:
        try:
            gdb.send(f"z0,{args.pc:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()
    print(f"forced {args.mask:#04x} across {frames} frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
