"""Discover Thumb functions in the base ROM from their call sites.

Linear scanning for `push {..., lr}` finds mostly graphics data that happens to
contain the right byte. Instead this walks every Thumb BL pair in the ROM,
resolves its target, and keeps targets that are called from more than one site
and decode cleanly as ARMv4T. Those are real functions.

Leaf functions (no BL, no SWI) are the correct first targets for a match test,
since they can be compiled without any other symbol being known.

Usage:
    python tools/find_leaf_funcs.py <rom.gba> [--max-bytes N] [--count N]
                                    [--min-callers N] [--leaf-only]
"""
import sys
import argparse
import collections

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
import thumb

BASE = 0x08000000


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("rom")
    p.add_argument("--max-bytes", type=int, default=64)
    p.add_argument("--count", type=int, default=10)
    p.add_argument("--min-callers", type=int, default=2)
    p.add_argument("--scan-end", type=lambda x: int(x, 0), default=0xA3A000)
    p.add_argument("--leaf-only", action="store_true", default=True)
    p.add_argument("--all", dest="leaf_only", action="store_false")
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    rom = open(args.rom, "rb").read()

    def hw(o):
        return rom[o] | (rom[o + 1] << 8)

    # --- pass 1: every BL pair, resolved to a target ---
    callers = collections.defaultdict(set)
    for o in range(0, args.scan_end - 4, 2):
        if (hw(o) & 0xF800) != 0xF000:
            continue
        if (hw(o + 2) & 0xF800) != 0xF800:
            continue
        tgt = thumb.bl_target(o, hw(o), hw(o + 2))
        if 0 <= tgt < args.scan_end and tgt % 2 == 0:
            if (hw(tgt) & 0xFF00) == 0xB500:      # target opens with push {..,lr}
                callers[tgt].add(o)

    print(f"BL-resolved function starts: {len(callers):,}")

    # --- pass 2: extent + leafness ---
    funcs = []
    for start, sites in callers.items():
        if len(sites) < args.min_callers:
            continue
        res = thumb.find_extent(rom, start, max_bytes=args.max_bytes)
        if res is None:
            continue
        end, is_leaf = res
        if args.leaf_only and not is_leaf:
            continue
        funcs.append((end - start, start, end, len(sites)))

    funcs.sort()
    kind = "leaf " if args.leaf_only else ""
    print(f"clean {kind}functions <= {args.max_bytes} bytes "
          f"with >= {args.min_callers} callers: {len(funcs):,}\n")

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    for size, start, end, ncall in funcs[:args.count]:
        print(f"--- {BASE + start:#010x}  (file {start:#08x})  "
              f"{size} bytes  {ncall} callers ---")
        for i in md.disasm(rom[start:end], BASE + start):
            raw = " ".join(f"{b:02x}" for b in i.bytes)
            print(f"    {i.address:08x}  {raw:<12} {i.mnemonic:<8} {i.op_str}")
        print()

    return 0


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
    raise SystemExit(main(sys.argv[1:]))
