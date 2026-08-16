"""Summarise a compiler/flag matrix sweep: which combo gets closest per target.

Usage:
    python tools/matrix_report.py <rom.gba> <manifest.json> <matrix_root>
"""
import os
import re
import sys
import json
import collections

NAME_RE = re.compile(r"^(sub_[0-9A-Fa-f]{8})(?:__(.+))?\.bin$")


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2

    rom_path, manifest, root = argv
    rom = open(rom_path, "rb").read()
    funcs = {f["name"]: f for f in json.load(open(manifest))}

    # combo -> target -> (best_diff, tag)
    grid = collections.defaultdict(dict)
    combos = sorted(d for d in os.listdir(root)
                    if os.path.isdir(os.path.join(root, d)))

    for combo in combos:
        d = os.path.join(root, combo)
        for fn in sorted(os.listdir(d)):
            m = NAME_RE.match(fn)
            if not m:
                continue
            target, tag = m.group(1), m.group(2) or "-"
            f = funcs.get(target)
            if f is None:
                continue
            built = open(os.path.join(d, fn), "rb").read()
            orig = rom[f["offset"]:f["offset"] + f["size"]]
            cand = built[:f["size"]]
            nd = sum(1 for a, b in zip(orig, cand) if a != b)
            nd += abs(len(orig) - len(cand))
            prev = grid[combo].get(target)
            if prev is None or nd < prev[0]:
                grid[combo][target] = (nd, tag)

    targets = sorted({t for c in grid.values() for t in c})
    if not targets:
        print("no results")
        return 2

    w = max(len(c) for c in combos) + 2
    print("best byte-diff per target (0 = match)\n")
    print("combo".ljust(w) + "  ".join(t[-8:].rjust(10) for t in targets))
    print("-" * (w + 12 * len(targets)))
    for combo in combos:
        row = combo.ljust(w)
        for t in targets:
            nd, tag = grid[combo].get(t, (None, ""))
            cell = "-" if nd is None else ("MATCH" if nd == 0 else str(nd))
            row += cell.rjust(10) + "  "
        print(row)

    print("\nwinning spellings:")
    for combo in combos:
        for t in targets:
            nd, tag = grid[combo].get(t, (None, ""))
            if nd == 0:
                print(f"  {t}  {combo}  variant={tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
