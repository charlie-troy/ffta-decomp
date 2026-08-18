"""Dump the unit stat table: stat id -> struct offset and width.

sub_080C7EA4 dispatches on a stat id through a 69-entry jump table, and each
case is a short stub that loads exactly one field. Reading every case gives the
numeric layout of the unit struct without running the game.

Usage:
    python tools/dump_stats.py <rom.gba> [--md]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

TABLE_POOL = 0x0C7EBC
N = 0x45
LOAD = re.compile(r"^(ldrb|ldrh|ldr|ldrsb|ldrsh)$")
OFF = re.compile(r"\[\w+,\s*#(0x[0-9a-fA-F]+|\d+)\]")

WIDTH = {"ldrb": "u8", "ldrsb": "s8", "ldrh": "u16", "ldrsh": "s16", "ldr": "u32"}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    rom = romlib.load(argv[0])
    md = "--md" in argv

    def w(o):
        return int.from_bytes(rom[o:o + 4], "little")

    table = w(TABLE_POOL) - 0x08000000
    rows = []
    for sid in range(N):
        tgt = (w(table + sid * 4) & ~1) - 0x08000000
        ins = romlib.disasm(rom, tgt, tgt + 12)
        off = width = None
        for i in ins[:3]:
            if LOAD.match(i.mnemonic):
                m = OFF.search(i.op_str)
                if m:
                    off, width = int(m.group(1), 0), WIDTH.get(i.mnemonic, "?")
                break
        first = "; ".join(f"{i.mnemonic} {i.op_str}" for i in ins[:2])
        rows.append((sid, off, width, first))

    known = sum(1 for r in rows if r[1] is not None)
    if md:
        print("| stat | offset | width |")
        print("|---|---|---|")
        for sid, off, width, _ in rows:
            if off is not None:
                print(f"| `{sid:#04x}` | `+{off:#x}` | {width} |")
    else:
        print(f"{'stat':>5} {'offset':>7} {'w':>4}  first instructions")
        print("-" * 62)
        for sid, off, width, first in rows:
            o = f"+{off:#x}" if off is not None else "-"
            print(f"{sid:>#5x} {o:>7} {width or '-':>4}  {first[:40]}")
        print(f"\n{known} of {N} stats resolve to a direct field load")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
