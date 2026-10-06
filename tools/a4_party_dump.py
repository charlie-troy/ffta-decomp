"""A4 fixture research: dump EWRAM on the placement screen and hunt the
party roster.

Goal (A4): find whether the save's dispatchable clan members contain two
units with the same battle-job id, and whether that id matches an enemy
job of the Bervenia encounter (41/5/40/36/22). If yes, a two-ally
same-job fixture is constructible from this save.

Method: boot placement.ss0 read-only, dump EWRAM in 512-byte chunks
(DE-026 cap; single halt), write the raw dump to scratch (save-derived
bytes are NEVER committed), then scan for record strides whose entries
hold EWRAM pointers (member name strings live in EWRAM save data, e.g.
Marche at 0x02001F1C).

stdout only; the dump lands in outputs/autobattle/scratch/.
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession  # noqa: E402

STATE = os.path.join("outputs", "lua-nav", "placement.ss0")
OUT = os.path.join("outputs", "autobattle", "scratch", "a4-placement-ewram.bin")
EWRAM = 0x02000000
EWRAM_SIZE = 0x40000


def dump(g, addr, size, chunk=0x200):
    out = bytearray()
    for off in range(0, size, chunk):
        d = g.read_mem(addr + off, min(chunk, size - off))
        if not d:
            raise RuntimeError(f"read failed at {addr + off:#x}")
        out += d
    return bytes(out)


def main():
    with FixtureSession(STATE, quiet=True) as s:
        g = s.g
        print(f"booted pid={s.pid}", flush=True)
        data = dump(g, EWRAM, EWRAM_SIZE)
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "wb") as fh:
            fh.write(data)
        print(f"dumped {len(data)} bytes -> {OUT}", flush=True)
        g.cont()
    # ---- scan for pointer strides -------------------------------------
    words = {}
    for off in range(0, len(data) - 3, 4):
        w = struct.unpack_from("<I", data, off)[0]
        if 0x02000000 <= w < 0x02040000:
            words.setdefault(w, []).append(off)
    # candidate record strides: a base offset whose +stride slots each
    # begin with an EWRAM pointer, repeated >= 5 times
    ptr_offs = sorted({o for v in words.values() for o in v})
    print(f"EWRAM pointers: {len(words)} distinct, {len(ptr_offs)} sites",
          flush=True)
    hits = []
    for stride in (0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28, 0x2C, 0x30,
                   0x34, 0x38, 0x3C, 0x40, 0x44, 0x48, 0x4C, 0x50, 0x54,
                   0x58, 0x60, 0x68, 0x70, 0x78, 0x80, 0x84, 0x88, 0x90,
                   0xA0, 0xB0, 0xC0, 0xD0, 0xE0, 0xF0, 0x100, 0x108):
        offs = set(ptr_offs)
        for base in sorted(offs):
            run = 0
            i = 0
            while base + i * stride in offs:
                run += 1
                i += 1
                if run >= 5:
                    break
            if run >= 5:
                hits.append((stride, base, run))
                break  # one base per stride is enough to inspect
    for stride, base, run in hits:
        print(f"stride=0x{stride:x} base=0x{EWRAM + base:08x} run={run}",
              flush=True)
        for i in range(min(run + 3, 10)):
            o = base + i * stride
            if o + 4 > len(data):
                break
            w = struct.unpack_from("<I", data, o)[0]
            tail = data[o:o + min(stride, 48)].hex()
            print(f"  +{i:<2} @0x{EWRAM + o:08x} ptr={w:08x} {tail}",
                  flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
