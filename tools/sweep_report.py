"""Report which spelling of a function reproduces the original bytes.

Reads `<target>__<tag>.bin` files produced from a sweep and diffs each against
the target function in the base ROM.

Usage:
    python tools/sweep_report.py <rom.gba> <manifest.json> <bindir>
"""
import os
import re
import sys
import json
import collections

NAME_RE = re.compile(r"^(sub_[0-9A-Fa-f]{8})__(.+)\.bin$")


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2

    rom_path, manifest, bindir = argv
    rom = open(rom_path, "rb").read()
    funcs = {f["name"]: f for f in json.load(open(manifest))}

    results = collections.defaultdict(list)
    for fn in sorted(os.listdir(bindir)):
        m = NAME_RE.match(fn)
        if not m:
            continue
        target, tag = m.group(1), m.group(2)
        f = funcs.get(target)
        if f is None:
            continue
        built = open(os.path.join(bindir, fn), "rb").read()
        orig = rom[f["offset"]:f["offset"] + f["size"]]
        cand = built[:f["size"]]
        ndiff = sum(1 for a, b in zip(orig, cand) if a != b)
        ndiff += abs(len(orig) - len(cand))
        results[target].append((ndiff, tag, len(built)))

    rc = 1
    for target, rows in results.items():
        f = funcs[target]
        print(f"=== {target}  ({f['size']} bytes, {f['callers']} callers) ===")
        for ndiff, tag, blen in sorted(rows):
            if ndiff == 0:
                print(f"   MATCH   {tag}")
                rc = 0
            else:
                print(f"   {ndiff:>3} off  {tag}   (built {blen}b)")
        print()

    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
