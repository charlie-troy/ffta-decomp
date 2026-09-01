"""Extract the per-effect probability gates from the AI evaluator's 92 cases.

Each case body is a probability gate: pick a threshold based on a condition,
roll Rand() % divisor, compare, and either bail or apply the effect. The
thresholds are hardcoded per effect type, so they are the AI's per-effect
weighting and cannot be reached by editing tables.

Usage:
    python tools/ai_case_rules.py <rom.gba> <manifest.json> [--md]
"""
import os
import re
import sys
import json
import bisect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romlib
import thumb

BASE = 0x08000000
TABLE = 0x0C3624
COUNT = 92
FEND = 0x0C47A8
RNG = 0x002804
MOD = 0x142950
IMM = re.compile(r"#(0x[0-9a-fA-F]+|\d+)\s*$")


def main(argv):
    rom = romlib.load(argv[0])
    funcs = json.load(open(argv[1]))
    funcs.sort(key=lambda f: f["offset"])
    starts = [f["offset"] for f in funcs]
    ends = [f["offset"] + f["size"] for f in funcs]

    def owner(off):
        i = bisect.bisect_right(starts, off) - 1
        return funcs[i]["name"] if i >= 0 and off < ends[i] else None

    def w(o):
        return int.from_bytes(rom[o:o + 4], "little")

    targets = {}
    for i in range(COUNT):
        t = (w(TABLE + i * 4) & ~1) - BASE
        targets.setdefault(t, []).append(i + 1)

    bounds = sorted(targets)
    rows = []
    for k, t in enumerate(bounds):
        end = min(bounds[k + 1] if k + 1 < len(bounds) else FEND, FEND)
        divisor = None
        thresholds = []
        effect = None
        prev = None
        for i in romlib.disasm(rom, t, end):
            if i.mnemonic == "movs" and i.op_str.startswith("r1,"):
                m = IMM.search(i.op_str)
                if m:
                    prev = int(m.group(1), 0)
            if i.mnemonic == "bl":
                m = re.search(r"#(0x[0-9a-fA-F]+)", i.op_str)
                if not m:
                    continue
                tgt = int(m.group(1), 0) - BASE
                if tgt == MOD and prev is not None:
                    divisor = prev
                elif tgt not in (RNG, MOD):
                    nm = owner(tgt)
                    # the last non-RNG call is the effect being applied
                    if nm and nm != "sub_080C32C0":
                        effect = nm
            if i.mnemonic == "cmp" and i.op_str.startswith("r0,"):
                m = IMM.search(i.op_str)
                if m:
                    v = int(m.group(1), 0)
                    if v not in (0, 1):
                        thresholds.append(v)
        rows.append((targets[t], t, divisor, thresholds[:2], effect))

    if "--md" in argv:
        print("| effect ids | divisor | thresholds | applies |")
        print("|---|---|---|---|")
        for ids, t, d, th, eff in rows:
            i = ",".join(map(str, ids))
            print(f"| {i[:24]} | {d if d else '-'} | "
                  f"{', '.join(map(str, th)) if th else '-'} | "
                  f"{'`'+eff+'`' if eff else '-'} |")
    else:
        print(f"{'effect ids':<22} {'div':>5} {'thresholds':>14}  applies")
        print("-" * 74)
        for ids, t, d, th, eff in rows:
            i = ",".join(map(str, ids))
            print(f"{i[:22]:<22} {d if d else '-':>5} "
                  f"{', '.join(map(str, th)) if th else '-':>14}  {eff or '-'}")
        gated = sum(1 for _, _, d, th, _ in rows if th)
        print(f"\n{gated} of {len(rows)} case bodies carry a probability gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
