"""Summarise a large switch by case: size, calls made, constants used.

Ghidra gives up on sub_080C32C0's 92-way jump table ("too many branches"), so
the cases never appear in its output. The table itself is easy to read, and
each case can be summarised from the disassembly directly.

Usage:
    python tools/analyze_switch.py <rom.gba> <manifest.json> <table_addr> <count> <func_start> <func_end>
"""
import os
import sys
import json
import bisect
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib
import thumb

BASE = 0x08000000


def main(argv):
    rom = romlib.load(argv[0])
    funcs = json.load(open(argv[1]))
    funcs.sort(key=lambda f: f["offset"])
    starts = [f["offset"] for f in funcs]
    ends = [f["offset"] + f["size"] for f in funcs]

    def owner(off):
        i = bisect.bisect_right(starts, off) - 1
        return funcs[i]["name"] if i >= 0 and off < ends[i] else None

    table = int(argv[2], 0) - BASE
    count = int(argv[3], 0)
    fstart = int(argv[4], 0) - BASE
    fend = int(argv[5], 0) - BASE

    def w(o):
        return int.from_bytes(rom[o:o + 4], "little")

    targets = []
    for i in range(count):
        t = (w(table + i * 4) & ~1) - BASE
        targets.append((t, i + 1))

    bounds = sorted({t for t, _ in targets})
    ids_at = collections.defaultdict(list)
    for t, cid in targets:
        ids_at[t].append(cid)

    print(f"{len(bounds)} distinct case bodies over {count} ids\n")
    print(f"{'case ids':<22} {'addr':>10} {'len':>5}  calls")
    print("-" * 96)
    for k, t in enumerate(bounds):
        end = bounds[k + 1] if k + 1 < len(bounds) else fend
        end = min(end, fend)
        calls = []
        o = t
        while o < end - 2:
            if (romlib.halfword(rom, o) & 0xF800) == 0xF000 and \
               (romlib.halfword(rom, o + 2) & 0xF800) == 0xF800:
                tgt = thumb.bl_target(o, romlib.halfword(rom, o),
                                      romlib.halfword(rom, o + 2))
                nm = owner(tgt)
                calls.append(nm or f"{tgt + BASE:#x}")
                o += 4
                continue
            o += 2
        ids = ",".join(str(i) for i in ids_at[t])
        if len(ids) > 20:
            ids = ids[:17] + "..."
        uniq = list(dict.fromkeys(calls))
        print(f"{ids:<22} {t + BASE:#010x} {end - t:>5}  {', '.join(uniq[:4])[:58]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
