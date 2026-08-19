"""Group call sites of a table accessor by the constant property id they pass.

Which code asks for a field is the best evidence of what the field means. A
call site using a constant sets the id register with `movs rN, #imm` shortly
before the BL, so walking back from each call recovers it.

    python tools/accessor_callers.py --target 0x080CA7A4 --reg r1
"""
import os
import re
import sys
import json
import argparse
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"
CODE_END = 0x360000


def bl_sites(rom, target):
    out = []
    for off in range(0, CODE_END, 2):
        h1 = int.from_bytes(rom[off:off + 2], "little")
        h2 = int.from_bytes(rom[off + 2:off + 4], "little")
        if (h1 & 0xF800) != 0xF000 or (h2 & 0xF800) != 0xF800:
            continue
        hi = h1 & 0x7FF
        if hi & 0x400:
            hi -= 0x800
        if (0x08000000 + off + 4) + (hi << 12) + ((h2 & 0x7FF) << 1) == target:
            out.append(0x08000000 + off)
    return out


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--rom", default=ROM)
    p.add_argument("--target", type=lambda s: int(s, 0), required=True)
    p.add_argument("--reg", default="r1")
    p.add_argument("--window", type=int, default=12)
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    rom = open(args.rom, "rb").read()
    sites = bl_sites(rom, args.target)
    print(f"call sites of {args.target:#010x}: {len(sites)}")

    byid = collections.defaultdict(list)
    unknown = []
    for site in sites:
        start = max(0, site - 0x08000000 - args.window * 2)
        pid = None
        for i in reversed(romlib.disasm(rom, start, site - 0x08000000)):
            if i.mnemonic in ("movs", "mov") and \
                    (i.op_str or "").startswith(args.reg + ","):
                m = re.search(r"#(0x[0-9a-fA-F]+|\d+)", i.op_str)
                if m:
                    pid = int(m.group(1), 0)
                break
            if i.mnemonic in ("bl", "blx"):
                break
        (unknown if pid is None else byid[pid]).append(site)

    print(f"  constant {args.reg}: {sum(len(v) for v in byid.values())}")
    print(f"  not a nearby constant: {len(unknown)}")
    print()
    print(f"{'prop':>5} {'sites':>6}  call sites")
    print("-" * 70)
    for pid in sorted(byid):
        s = byid[pid]
        print(f"  {pid:#04x} {len(s):>6}  " +
              " ".join(f"{a:#010x}" for a in s[:5]) +
              ("  ..." if len(s) > 5 else ""))
    if args.out:
        with open(args.out, "w", newline="\n") as fh:
            json.dump({hex(k): [hex(a) for a in v]
                       for k, v in sorted(byid.items())}, fh, indent=1)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
