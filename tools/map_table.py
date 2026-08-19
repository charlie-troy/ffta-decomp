"""Map a table's accessor property ids to entry offsets, by execution.

Same method the job table needed: decode the accessor statically and you get a
plausible offset per id, several of which are wrong. Running the accessor over
every entry and comparing against the raw bytes separates offsets that are
plain loads from ids that compute or unpack a value.

    python tools/map_table.py --base 0x0851D180 --stride 0x20 \
        --accessor 0x080CA7A4 --props 19 --count 370
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emulate import Gba

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--rom", default=ROM)
    p.add_argument("--base", type=lambda s: int(s, 0), required=True)
    p.add_argument("--stride", type=lambda s: int(s, 0), required=True)
    p.add_argument("--accessor", type=lambda s: int(s, 0), required=True)
    p.add_argument("--props", type=int, required=True)
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--first", type=int, default=1)
    args = p.parse_args(argv)

    rom = open(args.rom, "rb").read()
    gba = Gba(args.rom)
    base = args.base - 0x08000000
    ids = list(range(args.first, min(args.first + 120, args.count)))

    def u8(i, o):
        return rom[base + i * args.stride + o]

    def u16(i, o):
        off = base + i * args.stride + o
        return int.from_bytes(rom[off:off + 2], "little")

    print(f"table {args.base:#010x}  stride {args.stride:#04x}  "
          f"{args.count} entries, sampled over {len(ids)}")
    print()
    print(f"{'prop':>5}  {'source':<26} {'range':>14}  verdict")
    print("-" * 70)
    solved, computed = {}, []
    for pid in range(args.props):
        got = [gba.call(args.accessor, [i, pid]) for i in ids]
        hits = []
        for o in range(args.stride):
            if all(got[k] == u8(i, o) for k, i in enumerate(ids)):
                hits.append(f"+{o:#04x} u8")
        for o in range(args.stride - 1):
            if all(got[k] == u16(i, o) for k, i in enumerate(ids)):
                hits.append(f"+{o:#04x} u16")
        rng = f"{min(got)}..{max(got)}"
        if hits:
            solved[pid] = hits[0]
            print(f"  {pid:>3}  {', '.join(hits):<26} {rng:>14}  plain load")
        else:
            computed.append(pid)
            # how many entries a nearby byte would match, to spot a packed field
            best, bo = 0, None
            for o in range(args.stride):
                n = sum(1 for k, i in enumerate(ids) if got[k] == u8(i, o))
                if n > best:
                    best, bo = n, o
            note = (f"closest +{bo:#04x} {best}/{len(ids)}"
                    if best else "no byte resembles it")
            print(f"  {pid:>3}  {'(computed or packed)':<26} {rng:>14}  {note}")

    print()
    print(f"plain loads: {len(solved)}/{args.props}   "
          f"computed or packed: {len(computed)} -> {computed}")
    covered = sorted({int(v.split()[0], 16) for v in solved.values()})
    print(f"offsets covered by a plain load: "
          f"{', '.join(f'{o:#04x}' for o in covered)}")
    missing = [o for o in range(args.stride) if o not in covered]
    print(f"offsets no plain load reaches : "
          f"{', '.join(f'{o:#04x}' for o in missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
