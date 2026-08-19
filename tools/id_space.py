"""Test each field of a table against every candidate id space.

The weak version of this test asks whether a value happens to resolve to
something. Any byte below 116 resolves to some job name, so that proves
nothing. The useful test is coverage: a field really holding job ids has
*every* non-zero value inside the job range, and every one of them resolving
to clean text. A field that merely overlaps the range fails on its outliers.

    python tools/id_space.py
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_names import Names

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"
MISSION = (0x0855AE4C - 0x08000000, 0x46, 512)


def clean(t):
    return bool(t) and "[" not in t


def main():
    rom = open(ROM, "rb").read()
    n = Names(rom)
    base, stride, count = MISSION
    real = [i for i in range(count)
            if any(rom[base + i * stride + 2:base + i * stride + 0x45])]

    spaces = {
        "job": (116, n.job),
        "ability": (347, n.ability),
        "item": (630, n.item_by_id),
        "mission": (512, n.mission),
    }

    print(f"{len(real)} populated mission entries")
    print()
    print(f"{'off':>6} {'width':>5} {'nonzero':>8}  best id space (needs every "
          f"value to fit and resolve)")
    print("-" * 78)
    hits = []
    for width in (1, 2):
        for o in range(stride - width + 1):
            vals = []
            for i in real:
                p = base + i * stride + o
                vals.append(int.from_bytes(rom[p:p + width], "little"))
            nz = [v for v in vals if v]
            if len(nz) < 20:
                continue
            for name, (hi, fn) in spaces.items():
                if not all(v < hi for v in nz):
                    continue
                ok = sum(1 for v in nz if clean(fn(v)))
                frac = ok / len(nz)
                if frac >= 0.97:
                    hits.append((o, width, name, len(nz), frac,
                                 len(set(nz))))
    for o, width, name, nz, frac, dis in sorted(hits):
        print(f"  +{o:#04x} {'u8' if width == 1 else 'u16':>5} {nz:>8}  "
              f"{name} ({100*frac:.0f}% resolve, {dis} distinct)")
    if not hits:
        print("  (nothing passes the coverage test)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
