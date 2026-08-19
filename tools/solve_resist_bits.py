"""Resolve every resistance field id against the +0x11..+0x15 region treated
as one little-endian bit stream, so slices crossing a byte boundary resolve."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emulate import Gba

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"
ACC = 0x080C8570
BASE = 0x08521A14 - 0x08000000
STRIDE, COUNT = 0x34, 116

rom = open(ROM, "rb").read()
gba = Gba(ROM)


def word(i):
    o = BASE + i * STRIDE + 0x11
    return int.from_bytes(rom[o:o + 5], "little")


print(f"{'field':>6}  width/shift matching all 116 entries (base +0x11)")
print("-" * 62)
for fid in range(0x0d, 0x16):
    got = [gba.call(ACC, [i, 0, fid]) for i in range(COUNT)]
    hits = []
    for bits in (2, 3, 4):
        m = (1 << bits) - 1
        for sh in range(0, 40 - bits):
            if all(got[i] == ((word(i) >> sh) & m) for i in range(COUNT)):
                hits.append((bits, sh))
    if hits:
        best = min(hits, key=lambda h: (h[0], h[1]))
        b, sh = best
        byte, bit = 0x11 + sh // 8, sh % 8
        extra = f"  (+{len(hits)-1} wider alias)" if len(hits) > 1 else ""
        print(f"  {fid:#04x}  {b}-bit at stream bit {sh:>2}"
              f"  = +{byte:#04x} bits {bit}-{bit+b-1}{extra}")
    else:
        print(f"  {fid:#04x}  no slice of +0x11..+0x15 reproduces it")
