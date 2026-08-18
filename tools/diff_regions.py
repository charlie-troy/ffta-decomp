"""Attribute the differences between two ROMs to named functions.

For a mod build the interesting question is not how many bytes changed but
which functions they belong to, so an unintended change elsewhere is obvious.

Usage:
    python tools/diff_regions.py <base.gba> <built.gba> <functions.json>
"""
import sys
import json
import bisect


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    a = open(argv[0], "rb").read()
    b = open(argv[1], "rb").read()
    funcs = json.load(open(argv[2]))["functions"]
    funcs.sort(key=lambda f: f["offset"])
    starts = [f["offset"] for f in funcs]

    if len(a) != len(b):
        print(f"  size differs: base {len(a):,}, built {len(b):,}")

    runs = []
    i = 0
    n = min(len(a), len(b))
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1

    if not runs:
        print("  no byte differences")
        return 0

    named = {}
    unattributed = 0
    for lo, hi in runs:
        k = bisect.bisect_right(starts, lo) - 1
        if k >= 0 and lo < funcs[k]["offset"] + funcs[k]["size"]:
            named[funcs[k]["name"]] = named.get(funcs[k]["name"], 0) + (hi - lo)
        else:
            unattributed += hi - lo

    print(f"  {len(runs)} changed region(s)")
    for name, nb in sorted(named.items(), key=lambda kv: -kv[1]):
        print(f"    {name}: {nb} byte(s)")
    if unattributed:
        print(f"    outside any known function: {unattributed} byte(s)")
        print("    ^ unexpected; a mod should only change functions you edited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
