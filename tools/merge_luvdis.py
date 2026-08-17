"""Build the canonical function manifest from luvdis's disassembly.

Boundaries come from luvdis, not from tools/thumb.py's extent walker. That
walker was written for small leaf functions and resolved only 784 of 3,594
candidate starts, and it could run past a trailing literal pool into the next
function. luvdis emits a `thumb_func_start` for every function it finds, so a
function simply spans from its start to the next one, trailing literal pools
included.

Trailing zero bytes are trimmed. That direction is safe: tools/gen_build.py
tolerates an object that is larger than the manifest size, validating that the
extra bytes are zero in the ROM, but errors if an object is smaller. Erring
towards a smaller size therefore fails loudly rather than silently.

Writes the same schema as cluster_candidates.py --json, so gen_build.py,
gen_function_index.py and show_funcs.py keep working unchanged.

Usage:
    python tools/merge_luvdis.py <rom.gba> <luvdis rom.s> <out.json>
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
MAX_FUNC = 0x2000

START_RE = re.compile(r"^\s*(thumb|arm)_func_start\s+\S*?([0-9A-Fa-f]{8})\s*$")


def load_starts(path):
    """Return {offset: mode} for every function luvdis marks."""
    out = {}
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            m = START_RE.match(line)
            if not m:
                continue
            addr = int(m.group(2), 16)
            if BASE <= addr < BASE + SCAN_END:
                out[addr - BASE] = m.group(1)
    return out


def has_call(rom, start, end):
    for o in range(start, max(start, end - 2), 2):
        if (romlib.halfword(rom, o) & 0xF800) == 0xF000 and \
           (romlib.halfword(rom, o + 2) & 0xF800) == 0xF800:
            return True
    return False


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2

    rom_path, asm_path, out_path = argv
    rom = romlib.load(rom_path)
    starts = load_starts(asm_path)
    callers = romlib.discover_calls(rom, scan_end=SCAN_END)

    # luvdis's starts plus the ones local BL scanning finds; neither list is a
    # superset of the other.
    for o in callers:
        if o < SCAN_END:
            starts.setdefault(o, "thumb")

    ordered = sorted(starts)
    funcs = []
    skipped_big = 0
    arm_funcs = 0
    exact = 0
    approx = 0

    for idx, off in enumerate(ordered):
        if starts.get(off) == "arm":
            arm_funcs += 1
            continue                      # the pipeline is Thumb-only for now

        nxt = ordered[idx + 1] if idx + 1 < len(ordered) else min(SCAN_END, off + MAX_FUNC)

        # luvdis marks fewer starts than there are functions, so "next start"
        # alone over-estimates wherever it missed one: sub_080023D0, a known
        # 26-byte function, comes out as 340. The local walker is exact when it
        # succeeds, so prefer it and use luvdis only as a cap and a fallback.
        res = thumb.find_extent(rom, off, max_bytes=1024)
        if res is not None:
            end = min(res[0], nxt)
            is_leaf = res[1]
            exact += 1
        else:
            end = min(nxt, off + MAX_FUNC)
            if nxt - off > MAX_FUNC:
                skipped_big += 1
            # Only the inexact path may over-run into padding. Trimming trailing
            # zeros errs small, which gen_build.py reports rather than hides.
            while end > off and rom[end - 1] == 0:
                end -= 1
            if (end - off) % 2:
                end += 1
            is_leaf = not has_call(rom, off, end)
            approx += 1

        if end <= off:
            continue

        insns = romlib.disasm(rom, off, end)
        funcs.append({
            "offset": off,
            "addr": BASE + off,
            "size": end - off,
            "callers": len(callers.get(off, ())),
            "leaf": not has_call(rom, off, end),
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
    sizes = sorted(f["size"] for f in funcs)
    med = sizes[len(sizes) // 2] if sizes else 0
    print(f"candidate starts       : {len(starts):,}")
    print(f"thumb functions written: {len(funcs):,}")
    print(f"  exact (local walker) : {exact:,}")
    print(f"  approx (luvdis span) : {approx:,}")
    print(f"  leaf                 : {leaves:,}")
    print(f"  median size          : {med} bytes")
    print(f"  largest              : {sizes[-1] if sizes else 0} bytes")
    print(f"arm functions skipped  : {arm_funcs:,}")
    print(f"clamped at {MAX_FUNC:#x}     : {skipped_big:,}")

    # A size that disagrees with an already-verified function would silently
    # corrupt the build, so check against the committed index.
    idx_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "functions.json")
    if os.path.isfile(idx_path):
        with open(idx_path) as fh:
            known = {f["name"]: f["size"] for f in json.load(fh)["functions"]}
        by_name = {f["name"]: f["size"] for f in funcs}
        bad = [(n, s, by_name.get(n)) for n, s in known.items()
               if by_name.get(n) != s]
        if bad:
            print(f"\nERROR: {len(bad)} verified function(s) changed size:")
            for n, want, got in bad[:10]:
                print(f"  {n}: verified {want}, manifest {got}")
            return 1
        print(f"\nall {len(known)} verified function sizes preserved")

    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
