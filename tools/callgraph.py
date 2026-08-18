"""Find battle/AI code by who calls the known unit-struct accessors.

The flag getters and setters in src/generated all operate on one struct (fields
around 0x28 and 0xE8-0xEC). Whatever that struct is, code that interrogates
many of its flags is doing decision-making about units, which is where AI and
autobattle logic lives.

This builds the call graph from BL edges and ranks callers by how many
*distinct* accessors they touch. No emulator required.

Usage:
    python tools/callgraph.py <rom.gba> <manifest.json> [--top N] [--min N]
"""
import os
import sys
import json
import glob
import bisect
import argparse
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib
import thumb

BASE = 0x08000000
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def accessor_names():
    out = set()
    for p in glob.glob(os.path.join(REPO, "src", "generated", "sub_*.c")):
        out.add(os.path.basename(p)[:-2])
    return out


def classify(funcs, acc):
    """Split accessors into readers and writers.

    Reading a flag is a decision; writing one is a state change. Code that
    reads many distinct flags is choosing what to do, which is the AI. Code
    that writes many is an initialiser, which is not what we are looking for.
    """
    import gen_bitfield as G
    getters = {G.GET_BYTE_BIT, G.GET_BYTE_BIT_ALT, G.GET_HW_BIT, G.GET_HW_BIT_SHIFT}
    setters = {G.SET_BYTE_BIT_NEG, G.SET_BYTE_BIT_POS}
    g, s = set(), set()
    for i, f in enumerate(funcs):
        if f["name"] not in acc:
            continue
        if f.get("shape") in getters:
            g.add(i)
        elif f.get("shape") in setters:
            s.add(i)
    return g, s


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("manifest")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--min", type=int, default=3)
    args = ap.parse_args(argv)

    rom = romlib.load(args.rom)
    funcs = json.load(open(args.manifest))
    funcs.sort(key=lambda f: f["offset"])
    starts = [f["offset"] for f in funcs]
    ends = [f["offset"] + f["size"] for f in funcs]
    names = [f["name"] for f in funcs]
    sizes = [f["size"] for f in funcs]

    def containing(off):
        i = bisect.bisect_right(starts, off) - 1
        if i >= 0 and off < ends[i]:
            return i
        return None

    scan_end = min(len(rom), 0x360000)
    callees = collections.defaultdict(set)
    counts = collections.Counter()

    for o in range(0, scan_end - 4, 2):
        if (romlib.halfword(rom, o) & 0xF800) != 0xF000:
            continue
        if (romlib.halfword(rom, o + 2) & 0xF800) != 0xF800:
            continue
        tgt = thumb.bl_target(o, romlib.halfword(rom, o), romlib.halfword(rom, o + 2))
        if not (0 <= tgt < scan_end):
            continue
        ci = containing(o)
        ti = containing(tgt)
        if ci is None or ti is None or ci == ti:
            continue
        if starts[ti] != tgt:      # only real entry points
            continue
        callees[ci].add(ti)
        counts[ci] += 1

    acc = accessor_names()
    gi, si = classify(funcs, acc)
    print(f"functions: {len(funcs):,}   call edges: {sum(counts.values()):,}")
    print(f"accessors: {len(gi)} getters, {len(si)} setters\n")

    scored = []
    for ci, outs in callees.items():
        ng, ns = len(outs & gi), len(outs & si)
        if ng >= args.min:
            scored.append((ng, -ns, len(outs), ci))
    scored.sort(reverse=True)

    print(f"{'get':>4} {'set':>4} {'callees':>7} {'size':>6}  function")
    print("-" * 56)
    for ng, negs, nout, ci in scored[:args.top]:
        print(f"{ng:>4} {-negs:>4} {nout:>7} {sizes[ci]:>6}  {names[ci]}")
    print(f"\n{len(scored)} function(s) read >= {args.min} distinct flags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
