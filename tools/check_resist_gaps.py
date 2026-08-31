"""Show retail populations for all eight 3-bit resistance slots and gaps."""
import os
import sys
import collections
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = 0x08521A14 - 0x08000000
STRIDE, COUNT = 0x34, 116
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("rom", nargs="?", default="baserom.gba")
args = parser.parse_args()
rom = open(args.rom, "rb").read()


def word(i):
    o = BASE + i * STRIDE + 0x11
    return int.from_bytes(rom[o:o + 5], "little")


READ = list(range(11, 35, 3))
print("slots that consecutive field ids read (3 bits each):")
for sh in READ:
    vals = collections.Counter((word(i) >> sh) & 7 for i in range(COUNT))
    print(f"  bit {sh:>2}: {dict(sorted(vals.items()))}")

print("\nthird bit of each slot (set => the slot is wider than 2 bits):")
for sh in READ:
    third = sum(1 for i in range(COUNT) if (word(i) >> (sh + 2)) & 1)
    print(f"  bit {sh + 2:>2}: set in {third:>3}/{COUNT} entries")

print("\nbit ranges outside the eight resistance fields:")
for lo, hi in ((4, 10), (35, 39)):
    vals = collections.Counter((word(i) >> lo) & ((1 << (hi - lo + 1)) - 1)
                               for i in range(COUNT))
    top = dict(sorted(vals.items())[:6])
    print(f"  bits {lo}-{hi}: {len(vals)} distinct, {top}")
