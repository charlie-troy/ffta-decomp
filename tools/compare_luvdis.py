"""Cross-check luvdis's function discovery against this project's own.

Two independent implementations disagreeing is worth knowing about: a function
only luvdis found is one my scan is blind to, and vice versa.

Usage:
    python tools/compare_luvdis.py <rom.gba> <luvdis functions.cfg>
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

BASE = 0x08000000
ADDR_RE = re.compile(r"^\s*(?:(arm_func|thumb_func)\s+)?(0x[0-9A-Fa-f]+)")


def load_cfg(path):
    """Return {address: kind} from a luvdis config."""
    out = {}
    with open(path) as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            m = ADDR_RE.match(line)
            if m:
                out[int(m.group(2), 0)] = m.group(1) or "thumb_func"
    return out


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2

    rom = romlib.load(argv[0])
    theirs = load_cfg(argv[1])
    limit = 0x360000

    callers = romlib.discover_calls(rom, scan_end=limit)
    mine = {BASE + off for off, sites in callers.items() if len(sites) >= 2}
    theirs_in_range = {a for a in theirs if BASE <= a < BASE + limit}

    both = mine & theirs_in_range
    only_mine = mine - theirs_in_range
    only_theirs = theirs_in_range - mine

    print(f"scan range        : {BASE:#010x}..{BASE + limit:#010x}")
    print(f"mine (>=2 callers): {len(mine):,}")
    print(f"luvdis            : {len(theirs_in_range):,}")
    print(f"agree             : {len(both):,}")
    print(f"only mine         : {len(only_mine):,}")
    print(f"only luvdis       : {len(only_theirs):,}")

    if mine:
        print(f"\nluvdis covers {100.0 * len(both) / len(mine):.1f}% of mine")
    if theirs_in_range:
        print(f"mine covers   {100.0 * len(both) / len(theirs_in_range):.1f}% of luvdis")

    def sample(label, s):
        if not s:
            return
        print(f"\n{label} (first 10):")
        for a in sorted(s)[:10]:
            print(f"  {a:#010x}")

    sample("only mine", only_mine)
    sample("only luvdis", only_theirs)

    # Anything already decompiled that luvdis missed would be a real blind spot
    # in its discovery, and vice versa.
    import json
    idx = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "functions.json")
    if os.path.isfile(idx):
        with open(idx) as fh:
            done = json.load(fh)["functions"]
        addrs = {f["address"] for f in done}
        missed = sorted(a for a in addrs if a not in theirs and a < BASE + limit)
        print(f"\ndecompiled functions in range: "
              f"{len([a for a in addrs if a < BASE + limit])}")
        print(f"  not found by luvdis: {len(missed)}")
        for a in missed[:10]:
            print(f"    {a:#010x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
