"""Find table accessors ROM-wide, and the table each one indexes.

Both accessors already mapped -- sub_080C8570 for jobs and sub_080CA7A4 for
items -- have the same shape: scale an index by the entry stride, add a table
base from a literal pool, bounds-check a property id, then dispatch through a
jump table with `mov pc, rN`. Scanning for that dispatch and walking backwards
finds the other tables without needing documentation for them.
"""
import os
import re
import sys
import json
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

ROM = "D:/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba"
CODE_END = 0x360000
DATA_LO, DATA_HI = 0x08300000, 0x08A00000

rom = open(ROM, "rb").read()

# `mov pc, rN` for N in 0..7
DISPATCH = {0x4687 | (n << 3): n for n in range(8)}


def pool_value(addr, imm):
    p = (((addr + 4) & ~3) + imm) - 0x08000000
    if 0 <= p + 4 <= len(rom):
        return int.from_bytes(rom[p:p + 4], "little")
    return None


found = []
for off in range(0, CODE_END, 2):
    h = int.from_bytes(rom[off:off + 2], "little")
    if h not in DISPATCH:
        continue
    ins = romlib.disasm(rom, max(0, off - 0x40), off + 2)
    if not ins:
        continue
    base = stride = bound = None
    # walk backwards over the prologue
    for i in reversed(ins):
        o = i.op_str or ""
        if i.mnemonic == "ldr" and "pc" in o:
            m = re.search(r"#(0x[0-9a-fA-F]+|\d+)", o)
            if m:
                v = pool_value(i.address, int(m.group(1), 0))
                if v is not None and DATA_LO <= v < DATA_HI and base is None:
                    base = v
        if i.mnemonic == "lsls" and stride is None:
            m = re.search(r"#(\d+)", o)
            if m and not o.startswith("r0, r0"):
                sh = int(m.group(1))
                if 3 <= sh <= 8:
                    stride = 1 << sh
        if i.mnemonic == "movs" and stride is None:
            m = re.search(r"#(0x[0-9a-fA-F]+|\d+)", o)
            if m:
                v = int(m.group(1), 0)
                if 8 <= v <= 0x100:
                    stride = v
        if i.mnemonic == "cmp" and bound is None:
            m = re.search(r"#(0x[0-9a-fA-F]+|\d+)", o)
            if m:
                bound = int(m.group(1), 0)
    if base is not None:
        # find the enclosing function start
        start = None
        for a in range(off, max(0, off - 0x200), -2):
            hh = int.from_bytes(rom[a:a + 2], "little")
            if (hh & 0xFE00) == 0xB400 and (hh & 0x0100):
                start = 0x08000000 + a
                break
        found.append((start or 0x08000000 + off, base, stride, bound))

# collapse to one row per table base
by = {}
for fn, base, stride, bound in found:
    key = base
    if key not in by or (by[key][2] is None and stride is not None):
        by[key] = (fn, base, stride, bound)

KNOWN = {0x08521A14: "job table", 0x0851D180: "item table",
         0x0855187C: "ability table", 0x08569104: "map table"}
print(f"dispatch sites with a data-region table base: {len(found)}")
print(f"distinct table bases: {len(by)}")
print()
print(f"{'base':>12} {'stride':>7} {'props':>6}  accessor      note")
print("-" * 72)
for base in sorted(by):
    fn, _, stride, bound = by[base]
    note = KNOWN.get(base, "")
    st = f"{stride:#04x}" if stride else "?"
    bd = f"{bound + 1}" if bound is not None else "?"
    print(f"  {base:#010x} {st:>7} {bd:>6}  {fn:#010x}  {note}")

with open("build/accessors.json", "w", newline="\n") as fh:
    json.dump({hex(b): {"accessor": hex(v[0]), "stride": v[2], "props": v[3]}
               for b, v in sorted(by.items())}, fh, indent=1)
print("\nwrote build/accessors.json")
