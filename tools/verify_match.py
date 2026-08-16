"""Diff a compiled candidate against the original bytes in the base ROM.

Usage:
    python tools/verify_match.py <rom.gba> <built.bin> <rom_offset> <length>
"""
import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

BASE = 0x08000000


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 2

    rom_path, bin_path, off_s, len_s = argv
    off = int(off_s, 0)
    length = int(len_s, 0)

    rom = open(rom_path, "rb").read()
    built = open(bin_path, "rb").read()

    orig = rom[off:off + length]
    # the assembler pads the section to a 4-byte boundary; that padding is not
    # part of the function
    cand = built[:length]

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    o_ins = list(md.disasm(orig, BASE + off))
    c_ins = list(md.disasm(cand, BASE + off))

    print(f"target : {BASE + off:#010x}  ({length} bytes)")
    print(f"built  : {bin_path}  ({len(built)} bytes, {len(built) - length} pad)\n")
    print(f"{'ORIGINAL':<44}   {'AGBCC OUTPUT':<44}")
    print("-" * 92)

    bad = 0
    for i in range(max(len(o_ins), len(c_ins))):
        a = o_ins[i] if i < len(o_ins) else None
        b = c_ins[i] if i < len(c_ins) else None

        def fmt(x):
            if x is None:
                return "-"
            raw = " ".join(f"{v:02x}" for v in x.bytes)
            return f"{raw:<6} {x.mnemonic:<7} {x.op_str}"

        same = (a is not None and b is not None and a.bytes == b.bytes)
        if not same:
            bad += 1
        mark = "  " if same else "<<"
        print(f"{fmt(a):<44} {mark} {fmt(b):<44}")

    print("-" * 92)
    if orig == cand:
        print(f"\nMATCH: {length}/{length} bytes identical.")
        return 0

    ndiff = sum(1 for x, y in zip(orig, cand) if x != y) + abs(len(orig) - len(cand))
    print(f"\nNO MATCH: {ndiff} byte(s) differ, {bad} instruction(s) differ.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
