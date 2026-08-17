"""Build the canonical function manifest from luvdis plus local discovery.

luvdis finds functions this project's own scan cannot see: pure leaves that
never push lr, and functions reached through pointer tables rather than two or
more direct BL calls. Merging both lists and computing extents locally gives a
manifest that the rest of the pipeline can use unchanged.

Writes the same schema as cluster_candidates.py --json, so gen_build.py,
gen_function_index.py and show_funcs.py all keep working.

Usage:
    python tools/merge_luvdis.py <rom.gba> <functions.cfg> <out.json>
"""
import os
import re
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib
import thumb

BASE = 0x08000000
SCAN_END = 0x360000
ADDR_RE = re.compile(r"^\s*(?:(arm_func|thumb_func)\s+)?(0x[0-9A-Fa-f]+)")


def load_cfg(path):
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
    if len(argv) != 3:
        print(__doc__)
        return 2

    rom_path, cfg_path, out_path = argv
    rom = romlib.load(rom_path)

    callers = romlib.discover_calls(rom, scan_end=SCAN_END)
    cfg = load_cfg(cfg_path)

    starts = set()
    for a, kind in cfg.items():
        if kind == "thumb_func" and BASE <= a < BASE + SCAN_END:
            starts.add(a - BASE)
    starts.update(o for o in callers if o < SCAN_END)

    funcs = []
    skipped = 0
    ordered = sorted(starts)
    for idx, off in enumerate(ordered):
        res = thumb.find_extent(rom, off, max_bytes=1024)
        if res is None:
            skipped += 1
            continue
        end, is_leaf = res
        # The walker can run past the real end when a literal pool sits at the
        # boundary, swallowing the next function. Another function's start is a
        # hard upper bound.
        if idx + 1 < len(ordered):
            end = min(end, ordered[idx + 1])
        if end <= off:
            skipped += 1
            continue
        insns = romlib.disasm(rom, off, end)
        if len(insns) * 2 != end - off:
            skipped += 1          # capstone disagreed; treat as suspect
            continue
        funcs.append({
            "offset": off,
            "addr": BASE + off,
            "size": end - off,
            "callers": len(callers.get(off, ())),
            "leaf": is_leaf,
            "name": f"sub_{BASE + off:08X}",
            "bytes": rom[off:end].hex(),
            "shape": romlib.shape(insns),
            "disasm": [
                {"addr": i.address, "bytes": i.bytes.hex(),
                 "mnemonic": i.mnemonic, "op_str": i.op_str}
                for i in insns
            ],
        })

    funcs.sort(key=lambda f: f["offset"])
    with open(out_path, "w", newline="\n") as fh:
        json.dump(funcs, fh, indent=1)

    leaves = sum(1 for f in funcs if f["leaf"])
    nopush = sum(1 for f in funcs
                 if not f["bytes"].startswith(("00b5", "10b5", "30b5", "70b5", "f0b5"))
                 and (int(f["bytes"][2:4] + f["bytes"][0:2], 16) & 0xFF00) != 0xB500)
    print(f"luvdis thumb funcs in range : {len(starts) - len([o for o in callers if o < SCAN_END]):,} (union {len(starts):,})")
    print(f"extents resolved            : {len(funcs):,}")
    print(f"  leaf                      : {leaves:,}")
    print(f"  no push (my old blind spot): {nopush:,}")
    print(f"skipped (bad extent)        : {skipped:,}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
