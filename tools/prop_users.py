"""Find which ability properties the code queries, and from where.

sub_080CCD50(abilityId, propId) takes the property in r1, so scanning backwards
from each call for the constant that loads r1 shows which properties the game
actually uses and which functions care about them.

Usage:
    python tools/prop_users.py <rom.gba> <manifest.json> [--prop N]
"""
import os
import sys
import json
import bisect
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib
import thumb

TARGET = 0x0CCD50
SCAN_END = 0x360000


def main(argv):
    rom = romlib.load(argv[0])
    funcs = json.load(open(argv[1]))
    funcs.sort(key=lambda f: f["offset"])
    starts = [f["offset"] for f in funcs]
    ends = [f["offset"] + f["size"] for f in funcs]

    def owner(off):
        i = bisect.bisect_right(starts, off) - 1
        return funcs[i]["name"] if i >= 0 and off < ends[i] else "<none>"

    hits = collections.defaultdict(list)
    unknown = 0
    for o in range(0, SCAN_END - 4, 2):
        if (romlib.halfword(rom, o) & 0xF800) != 0xF000:
            continue
        if (romlib.halfword(rom, o + 2) & 0xF800) != 0xF800:
            continue
        if thumb.bl_target(o, romlib.halfword(rom, o), romlib.halfword(rom, o + 2)) != TARGET:
            continue
        # walk back for "movs r1, #imm" (0x21xx)
        prop = None
        for b in range(2, 20, 2):
            hw = romlib.halfword(rom, o - b)
            if (hw & 0xFF00) == 0x2100:
                prop = hw & 0xFF
                break
        if prop is None:
            unknown += 1
            continue
        hits[prop].append(owner(o))

    print(f"calls to sub_080CCD50 with a literal property: "
          f"{sum(len(v) for v in hits.values())} ({unknown} with a computed one)\n")
    print(f"{'prop':>5} {'column/bit':>12} {'calls':>6}  callers")
    print("-" * 74)
    for prop in sorted(hits):
        col = f"+0x10 bit {prop - 0x0B}" if 0x0B <= prop <= 0x1F else "direct column"
        who = collections.Counter(hits[prop])
        top = ", ".join(f"{n}x{c}" if c > 1 else n for n, c in who.most_common(3))
        print(f"{prop:>#5x} {col:>12} {len(hits[prop]):>6}  {top[:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
