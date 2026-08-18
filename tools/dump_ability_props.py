"""Map ability property ids to columns of the ability table.

sub_080CCD50(abilityId, propId) resolves a property two ways:

  * ids 0x0B-0x1F are bits (propId - 0x0B) of the u32 at entry +0x10
  * the rest dispatch through a jump table, each case loading one column

Reading both gives the layout of the 28-byte ability entry straight from the
code, the same way tools/dump_stats.py did for the unit struct.

Usage:
    python tools/dump_ability_props.py <rom.gba> [--md]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

TABLE_BASE_POOL = 0x0CCD84      # -> ability table
JUMP_POOL = 0x0CCD98            # -> property jump table
N_PROPS = 0x22
BIT_LO, BIT_N = 0x0B, 0x15

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

    tbl = w(TABLE_BASE_POOL)
    jmp = w(JUMP_POOL) - 0x08000000
    print(f"ability table : {tbl:#010x}  stride 0x1c")
    print(f"property table: {w(JUMP_POOL):#010x}\n")

    rows = []
    for pid in range(N_PROPS):
        if BIT_LO <= pid < BIT_LO + BIT_N:
            rows.append((pid, "+0x10", f"bit {pid - BIT_LO}", "flag"))
            continue
        tgt = (w(jmp + pid * 4) & ~1) - 0x08000000
        ins = romlib.disasm(rom, tgt, tgt + 12)
        off = width = None
        for i in ins[:3]:
            if LOAD.match(i.mnemonic):
                m = OFF.search(i.op_str)
                off = int(m.group(1), 0) if m else 0
                width = WIDTH.get(i.mnemonic, "?")
                break
        first = "; ".join(f"{i.mnemonic} {i.op_str}" for i in ins[:2])
        rows.append((pid, f"+{off:#x}" if off is not None else "-",
                     width or "-", first[:38]))

    if md:
        print("| prop | column | width/bit |")
        print("|---|---|---|")
        for pid, off, width, _ in rows:
            print(f"| `{pid:#04x}` | `{off}` | {width} |")
    else:
        print(f"{'prop':>5} {'column':>7} {'w/bit':>7}  detail")
        print("-" * 60)
        for pid, off, width, first in rows:
            print(f"{pid:>#5x} {off:>7} {width:>7}  {first}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
