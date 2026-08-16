"""Group leaf-function candidates by instruction shape.

Functions sharing a shape differ only in offsets, immediates and registers, so
one C template covers the whole cluster. Attacking the largest clusters first
is far and away the cheapest route to a high match count.

Usage:
    python tools/cluster_candidates.py <rom.gba> [--max-bytes N]
                                       [--min-callers N] [--show N]
                                       [--json out.json]
"""
import sys
import json
import argparse
import collections

import romlib


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("rom")
    p.add_argument("--max-bytes", type=int, default=48)
    p.add_argument("--min-callers", type=int, default=2)
    p.add_argument("--show", type=int, default=12, help="clusters to detail")
    p.add_argument("--json", default=None)
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    rom = romlib.load(args.rom)

    funcs = romlib.discover_functions(
        rom, min_callers=args.min_callers, max_bytes=args.max_bytes)

    clusters = collections.defaultdict(list)
    for f in funcs:
        clusters[f["shape"]].append(f)

    ranked = sorted(clusters.items(), key=lambda kv: -len(kv[1]))

    print(f"leaf candidates: {len(funcs)}   distinct shapes: {len(ranked)}\n")
    print(f"{'count':>5}  {'bytes':>5}  shape")
    print("-" * 88)
    for sh, group in ranked:
        print(f"{len(group):>5}  {group[0]['size']:>5}  {sh[:74]}")
    print()

    for sh, group in ranked[:args.show]:
        print("=" * 88)
        print(f"SHAPE x{len(group)}   {sh}")
        print("=" * 88)
        for f in group[:3]:
            print(romlib.format_function(f))
            print()
        if len(group) > 3:
            others = ", ".join(g["name"] for g in group[3:])
            print(f"    ... {len(group) - 3} more: {others}\n")

    if args.json:
        dump = []
        for f in funcs:
            d = {k: v for k, v in f.items() if k != "insns"}
            d["disasm"] = [
                {"addr": i.address, "bytes": i.bytes.hex(),
                 "mnemonic": i.mnemonic, "op_str": i.op_str}
                for i in f["insns"]
            ]
            dump.append(d)
        with open(args.json, "w") as fh:
            json.dump(dump, fh, indent=1)
        print(f"wrote {args.json} ({len(dump)} functions)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
