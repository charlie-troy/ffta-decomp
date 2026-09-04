"""Literal-annotated Thumb disassembler for quick static decodes.

Capstone renders literal pools as code, which is the main way pool words get
misread (this bit us twice in the sequencer decode: a 14-entry jump table and
two ctx-offset halfwords were first read as instructions). This tool:

  - annotates every `ldr rX, [pc, #imm]` with `=value` (and a +ctx hint when
    the value is small enough to be an offset);
  - annotates every `bl`/`b` with its absolute target;
  - resolves jump-table entries (`mov pc, rX` / `bx rX` after a table load):
    pass --table BASE,N to print the table's word entries;
  - finds a function head: pass --head ADDR to scan back to the `push {.., lr}`.

Game-generic: no FFTA constants. Examples:
  python tools/disasm.py 0x080C0488 0x080C0560
  python tools/disasm.py 0x080C0770 0x080C07C8 --ctx 0
  python tools/disasm.py --table 0x080C048C,14
  python tools/disasm.py --head 0x080C07C8
"""
import argparse
import struct
import sys

import capstone


def _fmt_val(val):
    s = f"{val:#x}"
    if 0 < val < 0x10000:
        s += f" (+ctx {val:#x}={val})"
    return s


def disasm(rom, start, end, ctx=None):
    """Yield annotated lines for [start, end). Addresses are absolute."""
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.skipdata = True
    lines = []
    for ins in md.disasm(rom[start - 0x08000000:end - 0x08000000], start):
        extra = ""
        if ins.mnemonic == "ldr" and "[pc" in ins.op_str:
            try:
                imm = int(ins.op_str.split("#")[1].rstrip("]"), 0)
                pool = (ins.address + 4) & ~3
                val = struct.unpack("<I", rom[pool - 0x08000000 + imm:
                                              pool - 0x08000000 + imm + 4])[0]
                extra = f"    ; ={_fmt_val(val)}"
            except (IndexError, ValueError, struct.error):
                pass
        elif ins.mnemonic in ("bl", "b", "bne", "beq", "bhs", "blt", "bgt",
                              "ble", "bmi", "bpl", "bcs", "bcc", "bvs",
                              "bvc", "bls", "bhi", "bls"):
            op = ins.op_str.lstrip("#")
            if op.startswith("0x"):
                extra = f"    ; -> {op}"
        line = f"{ins.address:08x}: {ins.mnemonic:6s} {ins.op_str}{extra}"
        if ctx is not None and extra.startswith("    ; ="):
            pass
        lines.append(line)
    return lines


def print_lines(lines, ctx=None):
    for line in lines:
        print(line)


def show_table(rom, base, n):
    print(f"jump table {base:#010x}, {n} entries:")
    targets = []
    for i in range(n):
        val = struct.unpack("<I", rom[base - 0x08000000 + 4 * i:
                                      base - 0x08000000 + 4 * i + 4])[0]
        targets.append(val)
        print(f"  [{i:2d}] -> {val:#010x}")
    return targets


def find_head(rom, addr, max_back=0x800):
    """Scan back for the nearest `push {..., lr}` (Thumb 0xB5xx)."""
    off = addr - 0x08000000
    for back in range(2, max_back, 2):
        hw = struct.unpack("<H", rom[off - back:off - back + 2])[0]
        if (hw & 0xFF00) == 0xB500 and hw & 0x100:
            head = addr - back
            print(f"head of {addr:#010x}: {head:#010x}")
            return head
    print(f"no push-lr found within {max_back:#x} before {addr:#010x}")
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("start", nargs="?", type=lambda s: int(s, 0))
    p.add_argument("end", nargs="?", type=lambda s: int(s, 0))
    p.add_argument("--table", help="BASE,N - decode a word jump table")
    p.add_argument("--head", type=lambda s: int(s, 0))
    args = p.parse_args(argv)

    rom = open("baserom.gba", "rb").read()
    if args.table:
        base, n = args.table.split(",")
        show_table(rom, int(base, 0), int(n, 0))
        return 0
    if args.head:
        head = find_head(rom, args.head)
        args.start, args.end = head, args.head + 0x10
    if args.start is None:
        p.error("need START END, --table BASE,N, or --head ADDR")
    end = args.end if args.end is not None else args.start + 0x80
    print_lines(disasm(rom, args.start, end))
    return 0


if __name__ == "__main__":
    sys.exit(main())
