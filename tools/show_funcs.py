"""Print candidate functions from the manifest, smallest first.

Used to pick the next batch to decompile by hand. Shapes already covered by a
generator are skipped by default so the listing only shows unclaimed work.

Usage:
    python tools/show_funcs.py <manifest.json> [--max-size N] [--limit M]
                               [--min-callers N] [--include-templated]
"""
import sys
import json
import argparse

import gen_bitfield as G

TEMPLATED = {
    G.GET_BYTE_BIT, G.SET_BYTE_BIT_NEG, G.SET_BYTE_BIT_POS,
    G.GET_HW_BIT_SHIFT, G.GET_HW_BIT,
}

# already matched by hand
DONE = {"sub_08005BB0", "sub_080DBD5C"}


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("manifest")
    p.add_argument("--max-size", type=int, default=32)
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--min-callers", type=int, default=2)
    p.add_argument("--include-templated", action="store_true")
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    funcs = json.load(open(args.manifest))

    sel = []
    for f in funcs:
        if f["size"] > args.max_size:
            continue
        if f["callers"] < args.min_callers:
            continue
        if f["name"] in DONE:
            continue
        if not args.include_templated and f["shape"] in TEMPLATED:
            continue
        sel.append(f)

    sel.sort(key=lambda f: (f["size"], -f["callers"]))
    print(f"{len(sel)} unclaimed candidate(s) <= {args.max_size} bytes\n")

    for f in sel[:args.limit]:
        print(f"--- {f['name']}  file {f['offset']:#08x}  "
              f"{f['size']} bytes  {f['callers']} callers ---")
        for i in f["disasm"]:
            raw = " ".join(f"{b:02x}" for b in bytes.fromhex(i["bytes"]))
            print(f"    {i['addr']:08x}  {raw:<6} {i['mnemonic']:<8} {i['op_str']}")
        print()

    return 0


if __name__ == "__main__":
    sys.path.insert(0, __file__.replace("\\", "/").rsplit("/", 1)[0])
    raise SystemExit(main(sys.argv[1:]))
