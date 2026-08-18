"""Build a map of the unit struct's flag bits from the matched accessors.

Every generated accessor encodes exactly which byte of the struct it touches
and which bit within it. Collecting them turns 100 anonymous functions into a
picture of the struct, and pairs each getter with the setter for the same bit,
which is the first step to naming any of it.

Usage:
    python tools/flag_map.py [--md]
"""
import os
import re
import sys
import glob
import collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILLER = re.compile(r"filler_00\[(0x[0-9a-fA-F]+|\d+)\]")
MASK = re.compile(r"int (?:not)?mask = (~?)(0x[0-9a-fA-F]+|\d+)")
FIELD = re.compile(r"^\s*(u8|u16) flags;", re.M)
ISSET = re.compile(r"\*p = \*p & notmask|p->unk_|= a != 0 \?")


def parse(path):
    src = open(path).read()
    name = os.path.basename(path)[:-2]
    m = FILLER.search(src)
    off = int(m.group(1), 0) if m else None
    f = FIELD.search(src)
    width = f.group(1) if f else "u8"
    masks = [int(g[1], 0) for g in MASK.findall(src)]
    mask = None
    for v in masks:
        if v and (v & (v - 1)) == 0:      # single bit
            mask = v
            break
    if mask is None and masks:
        mask = masks[0]
    kind = "set" if ("void " + name) in src else "get"
    return name, off, width, mask, kind


def main(argv):
    rows = []
    for p in sorted(glob.glob(os.path.join(REPO, "src", "generated", "sub_*.c"))):
        rows.append(parse(p))

    by_bit = collections.defaultdict(dict)
    for name, off, width, mask, kind in rows:
        if off is None or mask is None:
            continue
        by_bit[(off, width, mask)][kind] = name

    md = "--md" in argv
    keys = sorted(by_bit)
    if md:
        print("| byte | width | mask | bit | getter | setter |")
        print("|---|---|---|---|---|---|")
    else:
        print(f"{'byte':>6} {'width':>5} {'mask':>6} {'bit':>3}  {'getter':<14} setter")
        print("-" * 62)
    paired = 0
    for off, width, mask in keys:
        e = by_bit[(off, width, mask)]
        g, s = e.get("get", "-"), e.get("set", "-")
        if g != "-" and s != "-":
            paired += 1
        bit = mask.bit_length() - 1 if mask and (mask & (mask - 1)) == 0 else -1
        if md:
            print(f"| {off:#x} | {width} | {mask:#x} | {bit if bit>=0 else ''} | `{g}` | `{s}` |")
        else:
            print(f"{off:>#6x} {width:>5} {mask:>#6x} {bit:>3}  {g:<14} {s}")
    if not md:
        print(f"\n{len(keys)} distinct flag bits, {paired} with both a getter and a setter")
        offs = collections.Counter(k[0] for k in keys)
        print("bits per struct byte: " + ", ".join(f"{o:#x}:{n}" for o, n in sorted(offs.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
