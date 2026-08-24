"""Map mission accessor property ids to columns of the mission table.

sub_080CE4DC(missionId, propId) resolves 65 properties (0..0x40) by dispatch
through a jump table. Each target is a few instructions, so the column (or the
computation) for every property is read straight off the code -- the same
technique as tools/dump_ability_props.py for abilities.

    python tools/mission_props.py <rom.gba> [--md]

Known named properties (see docs/mission-data.md):

    prop 30 -> +0x33 * 200   gil reward
    prop 31 -> +0x34         AP reward (in units of 10)
    prop 29 -> +0x35         item reward id
    prop 54 -> +0x3e * 200   a second 200-unit gil quantity

Everything else prints its column and the raw case body so the remaining
"computed or packed" fields can be named by following the reader, exactly as
the reward fields were.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib

JUMP = 0x080CE508
N_PROPS = 0x41

LOAD = re.compile(r"^(ldrb|ldrh|ldr|ldrsb|ldrsh)$")
WIDTH = {"ldrb": "u8", "ldrsb": "s8", "ldrh": "u16", "ldrsh": "s16", "ldr": "u32"}
OFF = re.compile(
    r"\[(\w+)(?:,\s*#(0x[0-9a-fA-F]+|\d+))?\]"
)
ADD = re.compile(r"adds\s+\w+,\s+#(0x[0-9a-fA-F]+|\d+)")
BR = re.compile(r"#(0x[0-9a-fA-F]+|\d+)")

# A `b #addr` after computing the column hands off to one of these shared
# helpers; the target tells you what the property returns.
HELPERS = {
    0x080CE84A: ("load", "u16"),     # two bytes -> halfword
    0x080CE850: ("load", "u16"),     # combine two already-loaded bytes
    0x080CE80A: ("x200", "u8"),      # byte * 0xC8
    0x080CE7FA: ("lookup", "u8"),    # byte -> sub_080CB4A4
    0x080CE89A: ("bit", "u8"),       # value & 1
    0x080CE8A0: ("zero", None),      # returns 0
}


def classify(rom, pid):
    jmp = JUMP - 0x08000000
    tgt = (int.from_bytes(rom[jmp + pid * 4:jmp + pid * 4 + 4], "little") & ~1) \
        - 0x08000000
    ins = list(romlib.disasm(rom, tgt, tgt + 0x20))
    col = width = kind = None
    notes = []
    helper = None
    has_load = False
    for i in ins:
        if i.mnemonic == "b":
            m = BR.search(i.op_str or "")
            if m:
                helper = int(m.group(1), 0)
            break  # end of this case body; what follows is a shared helper
        if i.mnemonic in ("bx", "pop"):
            break
        op = i.op_str or ""
        full = f"{i.mnemonic} {op}"
        if col is None:
            m = OFF.search(op)
            if m:
                col = int(m.group(2), 0) if m.group(2) is not None else 0
            else:
                m = ADD.search(full)
                if m:
                    col = int(m.group(1), 0)
        if i.mnemonic in WIDTH:
            has_load = True
            if width is None:
                width = WIDTH[i.mnemonic]
        if i.mnemonic in ("lsrs", "lsls", "asrs", "ands", "orrs", "eors"):
            notes.append(f"{i.mnemonic} {op}")
        if i.mnemonic == "muls":
            notes.append(f"muls {op}")
        if i.mnemonic == "bl":
            notes.append(f"bl {op}")
    body = " ".join(f"{i.mnemonic} {i.op_str}" for i in ins[:4])
    if helper in HELPERS:
        kind, hw = HELPERS[helper]
        if hw:
            width = hw
    elif col is not None and not has_load and not notes:
        kind = "&column"
    elif notes:
        kind = "computed"
    else:
        kind = "load"
    return col, width, kind, notes, body


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    rom = romlib.load(argv[0])
    md = "--md" in argv
    rows = []
    for pid in range(N_PROPS):
        col, width, kind, notes, body = classify(rom, pid)
        rows.append((pid, col, width, kind, notes, body))
    if md:
        print("| prop | column | width | kind | case body |")
        print("|---|---|---|---|---|")
        for pid, col, width, kind, notes, body in rows:
            print(f"| `{pid:#04x}` | `+{col:#x}` | {width or '-'} | "
                  f"{kind} | `{body[:60]}` |")
    else:
        print(f"{'prop':>5} {'col':>6} {'w':>4}  {'kind':>9}  case body")
        print("-" * 88)
        for pid, col, width, kind, notes, body in rows:
            extra = "  [" + "; ".join(notes[:3]) + "]" if notes else ""
            print(f"{pid:>#5x} +{col if col is not None else -1:#05x} "
                  f"{width or '-':>4}  {kind:>9}  {body[:52]}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
