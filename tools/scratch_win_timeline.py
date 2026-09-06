"""One-client timeline: render PNGs at intervals to survey a live boot.

The mGBA GDB stub accepts a single client per emulator session (after a
client disconnects the listener stops accepting), so everything must happen
inside one connection. This tool resumes the CPU for `step` seconds, stops
it, renders the current screen, and repeats `count` times.

Usage: launch mGBA.exe -g rom.gba fresh, then run this once.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gba_drive import Session  # noqa: E402
from gba_render import Renderer, write_png  # noqa: E402

IO = 0x04000000


def u16(b):
    return int.from_bytes(b, "little")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="outputs/mgba-snowball/win-tl")
    p.add_argument("--count", type=int, default=12)
    p.add_argument("--step", type=float, default=5.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    s = Session(args.host, args.port, timeout=15)
    try:
        for i in range(args.count):
            if i:
                s.resume(args.step)
            else:
                s.gdb.interrupt()
            disp = u16(s.read_mem(IO, 2) or b"\0\0")
            rgb = Renderer(s).render()
            path = f"{args.out}-{i:02d}.png"
            write_png(path, rgb)
            print(f"shot {i:02d}: DISPCNT={disp:#06x} mode={disp & 7} -> {path}",
                  flush=True)
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
