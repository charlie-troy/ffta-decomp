"""Map the fallback table's field ids to entry offsets.

sub_080C8570(index, ?, fieldId) dispatches through a 48-entry jump table, the
same shape as the unit stat getter and the ability property getter. Each case
guards on a sentinel then loads one byte of the 0x34-byte entry.

Two guards on correctness:
  * offsets at or beyond 0x34 fall outside the entry and are reported as
    suspect rather than accepted
  * field 0x24 must resolve to +0x32 and field 0x25 to +0x33, which are known
    independently from sub_0813413C and sub_08130820

Usage:
    python tools/dump_unit_fields.py <rom.gba> [--md]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

JUMP_POOL = 0x0C859C
SHARED_TAIL = 0x0C8A02
N = 0x30
STRIDE = 0x34
LOAD = re.compile(r"^(ldrb|ldrh|ldr|ldrsb|ldrsh)$")
WID = {"ldrb": "u8", "ldrsb": "s8", "ldrh": "u16", "ldrsh": "s16", "ldr": "u32"}


def resolve(rom, tbl, fid):
    def w(o):
        return int.from_bytes(rom[o:o + 4], "little")

    t = (w(tbl + fid * 4) & ~1) - 0x08000000
    ins = romlib.disasm(rom, t, t + 10)
    br = fall = None
    for i in ins:
        if i.mnemonic in ("bne", "beq"):
            m = re.search(r"#(0x[0-9a-fA-F]+)", i.op_str)
            if m:
                br = int(m.group(1), 0) - 0x08000000
            fall = (i.address - 0x08000000) + 2
            break
    # Whichever path is not the shared chain-walking tail is the real body.
    for cand in (br, fall):
        if cand is None or cand == SHARED_TAIL:
            continue
        add = 0
        for i in romlib.disasm(rom, cand, cand + 24):
            if i.mnemonic == "adds":
                p = i.op_str.split(",")
                if len(p) == 2:
                    m = re.search(r"#(0x[0-9a-fA-F]+|\d+)", p[1])
                    if m:
                        add = int(m.group(1), 0)
            if LOAD.match(i.mnemonic):
                m = re.search(r"\[\w+,\s*#(0x[0-9a-fA-F]+|\d+)\]", i.op_str)
                extra = int(m.group(1), 0) if m else 0
                if extra == 5 and add == 0:
                    continue            # the sentinel guard, not the field
                return add + extra, WID.get(i.mnemonic)
    return None, None


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    rom = romlib.load(argv[0])
    tbl = int.from_bytes(rom[JUMP_POOL:JUMP_POOL + 4], "little") - 0x08000000

    rows = [(f,) + resolve(rom, tbl, f) for f in range(N)]
    good = [(f, o, w) for f, o, w in rows if o is not None and o < STRIDE]
    bad = [(f, o, w) for f, o, w in rows if o is not None and o >= STRIDE]

    checks = {0x24: 0x32, 0x25: 0x33}
    ok = all(dict((f, o) for f, o, _ in rows).get(k) == v for k, v in checks.items())
    print(f"cross-check (field 0x24 -> +0x32, 0x25 -> +0x33): {'PASS' if ok else 'FAIL'}")
    print(f"in-range fields: {len(good)}/{N}; out-of-range (suspect): {len(bad)}\n")

    if "--md" in argv:
        print("| field | offset |")
        print("|---|---|")
        for f, o, _ in good:
            print(f"| `{f:#04x}` | `+{o:#x}` |")
    else:
        for f, o, _ in good:
            print(f"  field {f:#04x} -> +{o:#04x}")
    if bad:
        print("\nsuspect, resolve beyond the 0x34-byte entry:")
        for f, o, _ in bad:
            print(f"  field {f:#04x} -> +{o:#04x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
