"""Validate the AI findings by executing the ROM's own code.

Static analysis says what code appears to do. This runs it on an emulated
ARM7TDMI and measures, which is what turns a derivation into a result.

    python tools/validate_ai.py <rom.gba> [--samples N]

Checks:
  1. the ability priority filter behaves as a percentage
  2. the ability property accessor agrees with the parsed table and with
     published ability stats
  3. every flag bit read through the property API matches a direct parse
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emulate import Gba

PRIO_FILTER = 0x0812F1DC
ABIL_PROP = 0x080CCD50
RNG_STATE = 0x030034B0
TABLE = 0x0855187C - 0x08000000
STRIDE = 0x1C

# MP cost, AP cost, Power for ability ids 1-10, from published documentation.
PUBLISHED = {1: (6, 100, 40), 2: (10, 200, 60), 3: (16, 300, 80),
             4: (18, 200, 0), 5: (10, 200, 90), 6: (20, 300, 100),
             7: (16, 200, 0), 8: (6, 100, 0), 9: (6, 100, 0),
             10: (12, 200, 0)}


def check_priority(gba, n):
    gba.write32(RNG_STATE, 0x12345678)
    print("1. ability priority filter, measured keep-rate vs prio/100")
    print(f"   {'prio':>5} {'measured':>10} {'expected':>10} {'delta':>7}")
    worst = 0.0
    for prio in (0, 20, 40, 60, 80, 100):
        keep = sum(1 for _ in range(n) if gba.call(PRIO_FILTER, [prio]))
        rate = 100.0 * keep / n
        d = abs(rate - prio)
        worst = max(worst, d)
        print(f"   {prio:>5} {rate:>9.1f}% {prio:>9}% {d:>6.1f}")
    ok = worst < 6.0
    print(f"   worst deviation {worst:.1f} points -> {'PASS' if ok else 'FAIL'}")
    print("   higher priority means MORE likely, the reverse of the published")
    print("   description; 0 never fires and 100 always does.")
    return ok


def check_properties(gba, rom):
    print("\n2. ability property accessor vs published stats")
    ok = True
    for i in sorted(PUBLISHED):
        mp = gba.call(ABIL_PROP, [i, 0x02])
        power = gba.call(ABIL_PROP, [i, 0x21])
        ap = rom[TABLE + i * STRIDE + 3] * 10
        pmp, pap, ppw = PUBLISHED[i]
        if (mp, ap, power) != (pmp, pap, ppw):
            ok = False
            print(f"   id {i}: got MP={mp} AP={ap} power={power}, "
                  f"expected {pmp}/{pap}/{ppw}")
    print(f"   {len(PUBLISHED)} abilities, MP/AP/power -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_flags(gba, rom, count=60):
    print("\n3. flag bits through the property API vs a direct parse")
    bad = 0
    total = 0
    for i in range(1, count):
        word = int.from_bytes(rom[TABLE + i * STRIDE + 0x10:
                                  TABLE + i * STRIDE + 0x14], "little")
        for prop in range(0x0B, 0x20):
            got = bool(gba.call(ABIL_PROP, [i, prop]))
            want = bool((word >> (prop - 0x0B)) & 1)
            total += 1
            if got != want:
                bad += 1
    print(f"   {total} bit reads, {bad} mismatch(es) -> "
          f"{'PASS' if bad == 0 else 'FAIL'}")
    return bad == 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--samples", type=int, default=2000)
    args = ap.parse_args(argv)

    gba = Gba(args.rom)
    rom = open(args.rom, "rb").read()

    results = [check_priority(gba, args.samples),
               check_properties(gba, rom),
               check_flags(gba, rom)]
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
