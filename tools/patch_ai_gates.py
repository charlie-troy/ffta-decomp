"""Read or change the AI's status-effect probability gates.

Every case body in the evaluator rolls Rand() % 101 and compares against one of
two thresholds: one when the AI would apply the effect to itself, one for any
other target. Those constants live in code, not in a table, but they are plain
immediate operands and can be patched without a compiler.

    python tools/patch_ai_gates.py show  <rom.gba>
    python tools/patch_ai_gates.py set    <rom.gba> <self> <other> <out.gba>

Defaults in the retail ROM are 10 (about 11% when self-targeting) and 49
(about 50% otherwise). Raising them makes the AI reach for status effects more
often; 100 makes it always, 0 never.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib
import thumb

BASE = 0x08000000
TABLE = 0x0C3624
COUNT = 92
FEND = 0x0C47A6
MOD = 0x142950
DIVISOR = 101


def find_gates(rom):
    """Return [(offset, current_threshold)] for every gate comparison.

    A gate is a `cmp r0, #imm` that follows a Rand() % 101 within a case body.
    Anchoring on the modulo call avoids catching unrelated comparisons.
    """
    def w(o):
        return int.from_bytes(rom[o:o + 4], "little")

    bounds = sorted({(w(TABLE + i * 4) & ~1) - BASE for i in range(COUNT)})
    out = []
    for k, start in enumerate(bounds):
        end = min(bounds[k + 1] if k + 1 < len(bounds) else FEND, FEND)
        armed = False
        prev_div = None
        for i in romlib.disasm(rom, start, end):
            if i.mnemonic == "movs" and i.op_str.startswith("r1,"):
                m = re.search(r"#(0x[0-9a-fA-F]+|\d+)\s*$", i.op_str)
                if m:
                    prev_div = int(m.group(1), 0)
            if i.mnemonic == "bl":
                m = re.search(r"#(0x[0-9a-fA-F]+)", i.op_str)
                if m and int(m.group(1), 0) - BASE == MOD and prev_div == DIVISOR:
                    armed = True
            elif armed and i.mnemonic == "cmp" and i.op_str.startswith("r0,"):
                m = re.search(r"#(0x[0-9a-fA-F]+|\d+)\s*$", i.op_str)
                if m:
                    out.append((i.address - BASE, int(m.group(1), 0)))
                armed = False
    return out


def main(argv):
    if len(argv) == 2 and argv[0] == "show":
        rom = romlib.load(argv[1])
        gates = find_gates(rom)
        seen = {}
        for off, val in gates:
            seen.setdefault(val, 0)
            seen[val] += 1
        print(f"{len(gates)} gate comparison(s) found")
        for val, n in sorted(seen.items()):
            pct = (val + 1) * 100 // (DIVISOR)
            print(f"  threshold {val:>3} used {n:>3} time(s)  (~{pct}% of rolls)")
        return 0

    if len(argv) == 5 and argv[0] == "set":
        rom = bytearray(open(argv[1], "rb").read())
        lo, hi = int(argv[2], 0), int(argv[3], 0)
        gates = find_gates(bytes(rom))
        if not gates:
            print("no gates found; refusing to patch")
            return 1
        vals = sorted({v for _, v in gates})
        if len(vals) != 2:
            print(f"expected two distinct thresholds, found {vals}; refusing")
            return 1
        mapping = {vals[0]: lo, vals[1]: hi}
        n = 0
        for off, val in gates:
            new = mapping[val]
            if not 0 <= new < 256:
                print(f"threshold {new} does not fit in a byte")
                return 1
            if rom[off] != new:
                rom[off] = new
                n += 1
        open(argv[4], "wb").write(bytes(rom))
        print(f"self-target threshold {vals[0]} -> {lo}")
        print(f"other-target threshold {vals[1]} -> {hi}")
        print(f"{n} byte(s) changed, wrote {argv[4]}")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
