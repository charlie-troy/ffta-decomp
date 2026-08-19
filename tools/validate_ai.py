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
import struct
import collections

from emulate import Gba
from unicorn import UC_HOOK_CODE

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
    print("1. ability priority filter, measured vs the bias-corrected model")
    print(f"   {'prio':>5} {'measured':>10} {'predicted':>10} {'delta':>7}")
    worst = 0.0
    for prio in (0, 20, 40, 60, 80, 100):
        keep = sum(1 for _ in range(n) if gba.call(PRIO_FILTER, [prio]))
        rate = 100.0 * keep / n
        exp = expected_keep(prio) * 100.0
        d = abs(rate - exp)
        worst = max(worst, d)
        print(f"   {prio:>5} {rate:>9.1f}% {exp:>9.1f}% {d:>6.1f}")
    ok = worst < 4.0
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


STAT_GET = 0x080C7EA4
# The ai_behaviour == 2 fragment of the evaluator, and its bail-out call.
HEALTHY_START, HEALTHY_END, HEALTHY_REJECT = 0x080C3364, 0x080C3380, 0x080C337C
# One case body's probability gate, up to the pass/fail test.
GATE_START, GATE_END = 0x080C3A3E, 0x080C3A76
BLANK = bytes(0x40)
RAND_RANGE = 32768


def expected_keep(prio):
    """Predicted keep-rate, accounting for the generator's modulo bias.

    Rand() yields 0..32767, so Rand() % 10000 is not uniform: remainders
    0..2767 occur four times in that span and the rest three. The low bias
    makes the keep test easier to pass, so the real rate sits above the
    nominal ai_priority percentage. At priority 20 it is about 25%.
    """
    if prio <= 0:
        return 0.0
    if prio >= 100:
        return 1.0
    big = collections.Counter(v % 10000 for v in range(RAND_RANGE))
    small = collections.Counter(v % 100 for v in range(RAND_RANGE))
    total = 0.0
    for a, pa in small.items():
        thr = prio * 100 + a
        drop = sum(c for r, c in big.items() if r >= thr) / RAND_RANGE
        total += (pa / RAND_RANGE) * (1.0 - drop)
    return total


def _put16(gba, addr, val):
    gba.uc.mem_write(addr, struct.pack("<H", val & 0xFFFF))


def check_stat_ids(gba):
    """Stat ids 0x13/0x14/0x15 should read unit +0x18/+0x1A/+0x1C."""
    print("")
    print("4. stat ids against a synthetic unit")
    UNIT = 0x02001000
    ok = True
    for hp, mx, mp in [(1, 1, 1), (37, 80, 12), (250, 999, 64), (0, 50, 0)]:
        gba.uc.mem_write(UNIT, BLANK)
        _put16(gba, UNIT + 0x18, hp)
        _put16(gba, UNIT + 0x1A, mx)
        _put16(gba, UNIT + 0x1C, mp)
        got = tuple(gba.call(STAT_GET, [UNIT, s]) for s in (0x13, 0x14, 0x15))
        if got != (hp, mx, mp):
            ok = False
            print(f"   wrote {hp}/{mx}/{mp}, read {got}")
    print(f"   0x13/0x14/0x15 == +0x18/+0x1A/+0x1C -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_healthy_rule(gba):
    """ai_behaviour 2 must reject exactly when target HP < MaxHP/2."""
    print("")
    print("5. healthy-target rule, executed")
    UNIT = 0x02001000
    hit = {"v": False}

    def hook(uc, addr, size, ud):
        if addr == HEALTHY_REJECT:
            hit["v"] = True
            uc.emu_stop()      # the real bail-out unwinds the caller's frame

    h = gba.uc.hook_add(UC_HOOK_CODE, hook, begin=HEALTHY_START, end=HEALTHY_END)
    ok = True
    for hp, mx in [(100, 100), (51, 100), (50, 100), (49, 100), (0, 100),
                   (30, 60), (29, 60)]:
        gba.uc.mem_write(UNIT, BLANK)
        _put16(gba, UNIT + 0x18, hp)
        _put16(gba, UNIT + 0x1A, mx)
        hit["v"] = False
        gba.run_range(HEALTHY_START, HEALTHY_END, {"r8": UNIT})
        if hit["v"] != (hp < mx // 2):
            ok = False
            print(f"   HP {hp}/{mx}: rejected={hit['v']}, expected={hp < mx // 2}")
    gba.uc.hook_del(h)
    print(f"   rejects exactly when HP < MaxHP/2 -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_gate(gba, n):
    """The shared status gate: about 11% self-targeting, 50% otherwise."""
    print("")
    print("6. status-effect gate, measured")
    gba.write32(RNG_STATE, 0xDEADBEEF)
    results = []
    for label, sl, r8, want in (("self", 0x02000100, 0x02000100, 11),
                                ("other", 0x02000100, 0x02000200, 50)):
        hits = sum(1 for _ in range(n)
                   if gba.run_range(GATE_START, GATE_END, {"sl": sl, "r8": r8}))
        rate = 100.0 * hits / n
        results.append(abs(rate - want) < 5.0)
        print(f"   {label:>5}-target {rate:>5.1f}% (expected about {want}%)")
    ok = all(results)
    print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


def check_resist_slots(gba, rom):
    """The eight resistance slots must reproduce the accessor exactly.

    Solved as a 3-bit stride from +0x12 bit 3 over +0x11..+0x15. Slot 2 is
    excluded because no field id reaches it, so there is nothing to compare
    against.
    """
    print("")
    print("7. packed resistance slots vs the job field accessor")
    base = 0x08521A14 - 0x08000000
    stride, count = 0x34, 116
    acc = 0x080C8570
    slot_field = {0: 0x0e, 1: 0x0f, 3: 0x11, 4: 0x12, 5: 0x13, 6: 0x14, 7: 0x15}

    def slot(i, n):
        o = base + i * stride + 0x11
        w = int.from_bytes(rom[o:o + 5], "little")
        return (w >> (11 + n * 3)) & 3

    bad = total = 0
    wide = 0
    for i in range(count):
        for n, fid in slot_field.items():
            total += 1
            if gba.call(acc, [i, 0, fid]) != slot(i, n):
                bad += 1
        for n in range(8):
            o = base + i * stride + 0x11
            w = int.from_bytes(rom[o:o + 5], "little")
            if (w >> (11 + n * 3 + 2)) & 1:
                wide += 1
    ok = bad == 0 and wide == 0
    print(f"   {total} slot reads, {bad} mismatch(es)")
    print(f"   third bit set in {wide} slot(s) (expected 0)")
    print(f"   -> {'PASS' if ok else 'FAIL'}")
    return ok


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--samples", type=int, default=2000)
    args = ap.parse_args(argv)

    gba = Gba(args.rom)
    rom = open(args.rom, "rb").read()

    results = [check_priority(gba, args.samples),
               check_properties(gba, rom),
               check_flags(gba, rom),
               check_stat_ids(gba),
               check_healthy_rule(gba),
               check_gate(gba, args.samples),
               check_resist_slots(gba, rom)]
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
