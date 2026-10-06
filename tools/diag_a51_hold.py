"""Hold the stub the way the manual layer does and watch what changes (A5.1).

Reproduces the manual layer's client behaviour WITHOUT sending any input:
connect, then sample the roster base and the ROM header every second for N
seconds, then report before/after. Two questions:

  * does the ROM header stay byte-identical (stream aligned) while the roster
    base changes (real engine state change), or do both shift (DE-028)?
  * does merely holding the client for the manual layer's duration break the
    state the resuming runner's guard needs?

Read-only: one read per interrupt, cont after every read.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trace_mgba import Gdb                    # noqa: E402
from fixture_guard import (BATTLE_STRUCT, ROSTER, STRIDE,  # noqa: E402
                           read_roster)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 2345
HOLD = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0


def u32(raw):
    return int.from_bytes(raw, "little") if raw and len(raw) >= 4 else None


def main():
    rom = open("baserom.gba", "rb").read(16)
    g = Gdb("127.0.0.1", PORT, timeout=6)
    print(f"interrupt -> {g.interrupt()!r}")

    def probe(tag):
        g.interrupt()
        header = g.read_mem(0x08000000, 16)
        g.interrupt()
        count = u32(g.read_mem(BATTLE_STRUCT, 4))
        g.interrupt()
        name = u32(g.read_mem(ROSTER, 4))
        g.interrupt()
        tile = g.read_mem(ROSTER + STRIDE * 6 + 0xF6, 2)
        g.cont()
        print(f"  [{tag}] rom_ok={header == rom} count={count} "
              f"slot0_name={hex(name) if name else name} "
              f"slot6_tile={tuple(tile) if tile else None}")
        return header == rom, count

    probe("start")
    t_end = time.time() + HOLD
    last = 0
    while time.time() < t_end:
        time.sleep(5.0)
        last += 5
        probe(f"hold+{last}s")
    g.interrupt()
    roster = read_roster(g, rom=open("baserom.gba", "rb").read())
    print(f"  roster now: count={roster['struct_count']} "
          f"live={roster['live_count']} names={roster['live_names']}")
    g.cont()
    g.close()
    print("done (core resumed)")


if __name__ == "__main__":
    main()
