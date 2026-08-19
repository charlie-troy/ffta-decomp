"""Check the bit ranges no field id reads, and whether any slot exceeds 2 bits."""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"
BASE = 0x08521A14 - 0x08000000
STRIDE, COUNT = 0x34, 116
rom = open(ROM, "rb").read()


def word(i):
    o = BASE + i * STRIDE + 0x11
    return int.from_bytes(rom[o:o + 5], "little")


READ = [11, 14, 20, 23, 26, 29, 32]
print("slots that a field id reads (2 bits each):")
for sh in READ:
    vals = collections.Counter((word(i) >> sh) & 3 for i in range(COUNT))
    print(f"  bit {sh:>2}: {dict(sorted(vals.items()))}")

print("\nthird bit of each slot (set => the slot is wider than 2 bits):")
for sh in READ:
    third = sum(1 for i in range(COUNT) if (word(i) >> (sh + 2)) & 1)
    print(f"  bit {sh + 2:>2}: set in {third:>3}/{COUNT} entries")

print("\nbit ranges no field id reads:")
for lo, hi in ((4, 10), (16, 19), (34, 39)):
    vals = collections.Counter((word(i) >> lo) & ((1 << (hi - lo + 1)) - 1)
                               for i in range(COUNT))
    top = dict(sorted(vals.items())[:6])
    print(f"  bits {lo}-{hi}: {len(vals)} distinct, {top}")
