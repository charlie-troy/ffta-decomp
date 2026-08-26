"""Validate the AI findings by executing the ROM's own code.

Static analysis says what code appears to do. This runs it on an emulated
ARM7TDMI and measures, which is what turns a derivation into a result.

    python tools/validate_ai.py <rom.gba> [--samples N]

Checks:
  1. the ability priority filter behaves as a percentage
  2. the ability property accessor agrees with the parsed table and with
     published ability stats
  3. every flag bit read through the property API matches a direct parse
  4. named unit-stat ids and equipped-item combat totals agree
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import struct
import collections

from emulate import Gba
from ffta_names import Names
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
ITEM_TABLE = 0x0851D180 - 0x08000000
ITEM_STRIDE = 0x20
COMBAT_TOTALS = (
    ("Attack", 0x17, 0x20, 0x10, 0x080CA624),
    ("Defense", 0x18, 0x22, 0x11, 0x080CA6B4),
    ("Magic Power", 0x19, 0x24, 0x12, 0x080CA66C),
    ("Resistance", 0x1A, 0x26, 0x13, 0x080CA6FC),
)
JOB_SWITCH_START, JOB_SWITCH_END = 0x080C8C32, 0x080C8C46
UNIT_IDENTITY_START, UNIT_IDENTITY_END = 0x080C975C, 0x080C9768
JOB_DERIVED_START, JOB_DERIVED_END = 0x080C8C46, 0x080C8CB6
EXP_AWARD_START, EXP_AWARD_END = 0x080A718E, 0x080A71AC
LEVEL_UP = 0x080C9B8C
DAMAGE = 0x0812FE38
BASE_SPEED_TOTAL = 0x080CA580
CT_TICK = 0x0809DF7C
TOTEMA_SELECT = 0x080260E0
ABILITY_STATE_INIT_START = 0x080C9F96
ABILITY_STATE_INIT_END = 0x080C9FB0
MOVEMENT_PROFILE_WRITE_START = 0x080CA37E
MOVEMENT_PROFILE_WRITE_END = 0x080CA38C
JOB_TABLE = 0x08521A14 - 0x08000000
JOB_STRIDE = 0x34
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


def check_stat_ids(gba, rom):
    """Named unit fields, transitions, and combat totals should agree."""
    print("")
    print("4. stat ids against a synthetic unit")
    UNIT = 0x02001000
    ok = True
    samples = [(1, 1, 1, 2), (37, 80, 12, 40),
               (250, 999, 64, 123), (0, 50, 0, 0)]
    for hp, mx, mp, max_mp in samples:
        gba.uc.mem_write(UNIT, BLANK)
        _put16(gba, UNIT + 0x18, hp)
        _put16(gba, UNIT + 0x1A, mx)
        _put16(gba, UNIT + 0x1C, mp)
        _put16(gba, UNIT + 0x1E, max_mp)
        got = tuple(gba.call(STAT_GET, [UNIT, s])
                    for s in (0x13, 0x14, 0x15, 0x16))
        if got != (hp, mx, mp, max_mp):
            ok = False
            print(f"   wrote {hp}/{mx}/{mp}/{max_mp}, read {got}")
    print("   0x13..0x16 == HP/MaxHP/MP/MaxMP at +0x18..+0x1E "
          f"-> {'PASS' if ok else 'FAIL'}")

    gba.uc.mem_write(UNIT, BLANK)
    identity = ((0x02, 0x05, 0x3C), (0x04, 0x07, 0x3D),
                (0x05, 0x08, 7), (0x06, 0x09, 50), (0x07, 0x0A, 99))
    for _, off, value in identity:
        gba.write8(UNIT + off, value)
    got = tuple(gba.call(STAT_GET, [UNIT, stat])
                for stat, _, _ in identity)
    want = tuple(value for _, _, value in identity)
    if got != want:
        ok = False
        print(f"   job/level fields read {got}, expected {want}")
    print("   0x02/0x04..0x07 == base job/active job/secondary job/level/EXP "
          f"-> {'PASS' if got == want else 'FAIL'}")

    # Stat 0 is the stored encoded-name pointer. UI call sites pass it as the
    # text argument to sub_08025688; here the accessor must preserve all bits.
    name_text = 0x0855A64C
    gba.write32(UNIT, name_text)
    name_pointer = gba.call(STAT_GET, [UNIT, 0x00])
    if name_pointer != name_text:
        ok = False
    print("   stat 0x00 returns the full encoded-name text pointer "
          f"-> {'PASS' if name_pointer == name_text else 'FAIL'}")

    pointer_stats = ((0x09, 0x0C), (0x1C, 0x2A), (0x22, 0x34),
                     (0x27, 0xD8), (0x38, 0xE8), (0x44, 0xFC))
    pointer_values = tuple(gba.call(STAT_GET, [UNIT, stat])
                           for stat, _ in pointer_stats)
    pointer_want = tuple(UNIT + off for _, off in pointer_stats)
    if pointer_values != pointer_want:
        ok = False
        print(f"   pointer stats read {pointer_values}, expected {pointer_want}")
    print("   six address-returning stat ids point to their exact unit regions "
          f"-> {'PASS' if pointer_values == pointer_want else 'FAIL'}")

    # +0x34 is a 12-byte ability header followed by one byte per ability. The
    # retail initializer writes the race-specific count; Human race 1 has 142,
    # which fits exactly before CT at +0xd0. +0xfc is populated as a movement
    # mode/variant profile by the same family that builds unit tile state.
    gba.uc.mem_write(UNIT, BLANK)
    gba.write8(UNIT + 0x06, 1)
    gba.run_range(ABILITY_STATE_INIT_START, ABILITY_STATE_INIT_END,
                  {"r0": UNIT, "r7": UNIT})
    ability_count = gba.uc.mem_read(UNIT + 0x34, 1)[0]
    gba.run_range(MOVEMENT_PROFILE_WRITE_START, MOVEMENT_PROFILE_WRITE_END,
                  {"r5": UNIT, "r7": 2, "r6": 3, "r4": 4})
    movement_profile = tuple(gba.uc.mem_read(UNIT + 0xFC, 4))
    regions_ok = ability_count == 142 and movement_profile == (2, 3, 4, 251)
    if not regions_ok:
        ok = False
    print("   +0x34 ability state and +0xfc movement profile initialize "
          f"-> {'PASS' if regions_ok else 'FAIL'} "
          f"(count={ability_count}, profile={movement_profile})")

    # The unit constructor copies its record discriminator to +0x04 and the
    # selected job's race property to +0x06. Jelly (job 46) is race 7.
    gba.uc.mem_write(UNIT, BLANK)
    gba.write8(UNIT + 0x05, 46)
    gba.write8(UNIT + 0x07, 46)
    gba.run_range(UNIT_IDENTITY_START, UNIT_IDENTITY_END,
                  {"r2": 1, "r7": UNIT})
    unit_identity = tuple(gba.uc.mem_read(UNIT + off, 1)[0]
                          for off in (0x04, 0x06))
    identity_getters = (gba.call(STAT_GET, [UNIT, 0x01]),
                        gba.call(STAT_GET, [UNIT, 0x03]))
    if unit_identity != (1, 7) or identity_getters != unit_identity:
        ok = False
        print(f"   unit type/race wrote {unit_identity}, getters {identity_getters}")
    print("   constructor copies unit type 1 and Jelly race 7 "
          f"-> {'PASS' if unit_identity == (1, 7) and identity_getters == unit_identity else 'FAIL'}")

    # Job initialization writes the neutral element plus eight elemental
    # resistance codes to +0x0C..+0x14. The retail field accessor duplicates
    # packed slot 1 for Earth; packed slot 2 is never copied.
    gba.run_range(JOB_DERIVED_START, JOB_DERIVED_END,
                  {"r4": UNIT, "r6": 1, "r7": 0})
    packed = int.from_bytes(
        rom[JOB_TABLE + 46 * JOB_STRIDE + 0x11:
            JOB_TABLE + 46 * JOB_STRIDE + 0x16], "little")
    slots = tuple((packed >> (11 + n * 3)) & 3 for n in range(8))
    want_resist = (1, slots[0], slots[1], slots[1], *slots[3:])
    got_resist = tuple(gba.call(STAT_GET, [UNIT, stat])
                       for stat in range(0x0A, 0x13))
    innate_element = gba.call(STAT_GET, [UNIT, 0x08])
    want_element = rom[JOB_TABLE + 46 * JOB_STRIDE + 0x11] & 0x0F
    if got_resist != want_resist:
        ok = False
        print(f"   elemental resistance fields {got_resist}, expected {want_resist}")
    if innate_element != want_element or innate_element != 1:
        ok = False
        print(f"   innate element {innate_element}, expected Jelly Fire (1)")
    print("   stat 0x08 == innate element; Jelly is Fire "
          f"-> {'PASS' if innate_element == want_element == 1 else 'FAIL'}")
    print("   neutral/Fire/Wind/Earth/Water/Ice/Lightning/Holy/Dark fields "
          f"-> {'PASS' if got_resist == want_resist else 'FAIL'}")

    # Fire is element 1, so the damage routine indexes target +0x0D. Execute
    # all five retail resistance meanings under the same RNG state.
    TARGET = UNIT + 0x800
    for actor in (UNIT, TARGET):
        gba.uc.mem_write(actor, bytes(0x108))
        for off, value in ((0x18, 100), (0x1A, 100), (0x20, 100),
                           (0x22, 50), (0x24, 100), (0x26, 50)):
            _put16(gba, actor + off, value)
    damage = []
    for resistance in range(5):
        gba.write8(TARGET + 0x0D, resistance)
        gba.write32(RNG_STATE, 0x12345678)
        value = gba.call(DAMAGE, [UNIT, TARGET, 23, 0], timeout_insns=500000)
        damage.append(value - 0x100000000 if value & 0x80000000 else value)
    damage_ok = (damage[0] > damage[1] > damage[4] > 0 and
                 damage[2] == 0 and damage[3] < 0)
    if not damage_ok:
        ok = False
        print(f"   Fire resistance outcomes {damage}")
    print(f"   Fire weak/normal/null/absorb/resist outcomes {damage} "
          f"-> {'PASS' if damage_ok else 'FAIL'}")

    # An ordinary unit changing to its secondary job synchronizes base and
    # active job, then clears the now-duplicate secondary slot.
    gba.uc.mem_write(UNIT, BLANK)
    gba.write8(UNIT + 0x04, 1)
    gba.write8(UNIT + 0x05, 2)
    gba.write8(UNIT + 0x08, 7)
    gba.run_range(JOB_SWITCH_START, JOB_SWITCH_END,
                  {"r4": UNIT, "r5": 7, "r6": 7})
    switched = tuple(gba.uc.mem_read(UNIT + off, 1)[0]
                     for off in (0x05, 0x07, 0x08))
    if switched != (7, 7, 0):
        ok = False
        print(f"   job switch wrote {switched}, expected (7, 7, 0)")
    print("   ordinary job switch synchronizes base/active and clears duplicate "
          f"secondary -> {'PASS' if switched == (7, 7, 0) else 'FAIL'}")

    # The award loop dereferences a list node twice, reads stat 7, and writes
    # the bounded sum to unit +0x0A.
    NODE, HOLDER = UNIT + 0x400, UNIT + 0x500
    gba.uc.mem_write(UNIT, BLANK)
    gba.write8(UNIT + 0x0A, 40)
    gba.write32(NODE, HOLDER)
    gba.write32(HOLDER, UNIT)
    _put16(gba, NODE + 4, 5)
    gba.run_range(EXP_AWARD_START, EXP_AWARD_END, {"r4": NODE})
    awarded = gba.uc.mem_read(UNIT + 0x0A, 1)[0]
    if awarded != 45:
        ok = False
        print(f"   EXP award wrote {awarded}, expected 45")
    print(f"   EXP award 40 + 5 -> {awarded} -> "
          f"{'PASS' if awarded == 45 else 'FAIL'}")

    # At the retail cap, the level-up routine restores level 50 / EXP 99 and
    # returns before entering the stat-growth path.
    gba.uc.mem_write(UNIT, BLANK)
    gba.write8(UNIT + 0x09, 50)
    gba.write8(UNIT + 0x0A, 99)
    gba.call(LEVEL_UP, [UNIT])
    capped = tuple(gba.uc.mem_read(UNIT + off, 1)[0]
                   for off in (0x09, 0x0A))
    if capped != (50, 99):
        ok = False
        print(f"   level cap wrote {capped}, expected (50, 99)")
    print("   level-up cap restores level 50 / EXP 99 "
          f"-> {'PASS' if capped == (50, 99) else 'FAIL'}")

    bases = (71, 83, 97, 109)
    items = (1, 3, 7, 10, 0)
    gba.uc.mem_write(UNIT, BLANK)
    for (_, _, off, _, _), value in zip(COMBAT_TOTALS, bases):
        _put16(gba, UNIT + off, value)
    for n, item in enumerate(items):
        _put16(gba, UNIT + 0x2A + n * 2, item)
    equipped = tuple(gba.call(STAT_GET, [UNIT, stat])
                     for stat in range(0x1D, 0x22))
    if equipped != items:
        ok = False
        print(f"   equipped-item stats read {equipped}, expected {items}")
    print("   0x1D..0x21 == five equipped-item ids at +0x2A..+0x32 "
          f"-> {'PASS' if equipped == items else 'FAIL'}")

    for (name, stat_id, _, item_off, total_fn), base in zip(COMBAT_TOTALS, bases):
        direct = gba.call(STAT_GET, [UNIT, stat_id])
        item_bonus = sum(rom[ITEM_TABLE + item * ITEM_STRIDE + item_off]
                         for item in items if item)
        total = gba.call(total_fn, [UNIT, 1])
        if direct != base or total != base + item_bonus:
            ok = False
            print(f"   {name}: stat={direct}, total={total}, "
                  f"expected {base}+{item_bonus}")
    print("   0x17..0x1A == Attack/Defense/Magic Power/Resistance and "
          f"item props 10..13 join correctly -> {'PASS' if ok else 'FAIL'}")

    # The next four scalar ids are CT, base Speed, CT carry, and Judge Points.
    # Speed's item join is independent of the direct accessor. The one-unit CT
    # tick consumes base speed and carry, then normalizes 1025 to CT 1000 and
    # records the 25-point common advance back into carry.
    gba.uc.mem_write(UNIT, bytes(0x108))
    later = ((0x23, 0xD0, 900), (0x24, 0xD2, 73),
             (0x25, 0xD4, 25), (0x26, 0xD6, 10))
    for _, off, value in later:
        _put16(gba, UNIT + off, value)
    later_got = tuple(gba.call(STAT_GET, [UNIT, stat])
                      for stat, _, _ in later)
    later_want = tuple(value for _, _, value in later)
    if later_got != later_want:
        ok = False
        print(f"   CT/Speed/carry/JP reads {later_got}, expected {later_want}")

    speed_items = (1, 3, 7, 10, 0)
    for n, item in enumerate(speed_items):
        _put16(gba, UNIT + 0x2A + n * 2, item)
    speed_bonus = sum(struct.unpack("<b", bytes([
        rom[ITEM_TABLE + item * ITEM_STRIDE + 0x14]
    ]))[0] for item in speed_items if item)
    speed_total = gba.call(BASE_SPEED_TOTAL, [UNIT])
    if speed_total != 73 + speed_bonus:
        ok = False
        print(f"   total Speed {speed_total}, expected 73+{speed_bonus}")
    print("   0x23..0x26 == CT/Speed/CT carry/Judge Points at +0xD0..+0xD6; "
          f"item Speed joins -> {'PASS' if later_got == later_want and speed_total == 73 + speed_bonus else 'FAIL'}")

    BATTLE = 0x02002000
    battle_unit = BATTLE + 4
    gba.uc.mem_write(BATTLE, bytes(0x10C))
    gba.write32(BATTLE, 1)
    _put16(gba, battle_unit + 0xD0, 900)
    _put16(gba, battle_unit + 0xD2, 100)
    _put16(gba, battle_unit + 0xD4, 25)
    gba.call(CT_TICK, [BATTLE])
    ct_after = (
        struct.unpack("<H", gba.uc.mem_read(battle_unit + 0xD0, 2))[0],
        struct.unpack("<H", gba.uc.mem_read(battle_unit + 0xD4, 2))[0],
    )
    if ct_after != (1000, 25):
        ok = False
        print(f"   CT tick wrote {ct_after}, expected (1000, 25)")
    print(f"   CT tick 900 + Speed 100 + carry 25 -> {ct_after} "
          f"-> {'PASS' if ct_after == (1000, 25) else 'FAIL'}")

    # The action-menu selector exposes a race-specific Totema command only at
    # 10+ JP. Human race 1 selects command/string id 0x50, decoded as Totema.
    MENU = UNIT + 0x200
    gba.uc.mem_write(UNIT, bytes(0x108))
    gba.write8(UNIT + 0x06, 1)
    totema_commands = []
    for jp in (9, 10):
        _put16(gba, UNIT + 0xD6, jp)
        gba.uc.mem_write(MENU, bytes(0x20))
        gba.call(TOTEMA_SELECT, [UNIT, MENU])
        totema_commands.append(struct.unpack("<H", gba.uc.mem_read(MENU, 2))[0])
    totema_label = Names(rom)._string(0x085567F0, 0x50)
    jp_ok = totema_commands == [0x0E, 0x50] and totema_label == "Totema"
    if not jp_ok:
        ok = False
        print(f"   JP boundary commands {totema_commands}, label {totema_label!r}")
    print(f"   JP 9/10 selects commands {totema_commands}; 0x50={totema_label!r} "
          f"-> {'PASS' if jp_ok else 'FAIL'}")
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


def check_unarmed(gba, rom):
    """+0x33 must be what the damage path reads when no weapon is equipped.

    sub_08130820 takes a unit pointer and reads the job index from unit+5.
    Patching the field has to move the return value, or the link is only a
    correlation.
    """
    print("")
    print("8. unarmed attack power at +0x33")
    base, stride, count = 0x08521A14 - 0x08000000, 0x34, 116
    getter, unit = 0x08130820, 0x02000400
    bad = 0
    for job in range(count):
        gba.uc.mem_write(unit, bytes(0x40))
        gba.uc.mem_write(unit + 5, bytes([job]))
        if gba.call(getter, [unit]) != rom[base + job * stride + 0x33]:
            bad += 1
    moved = True
    addr = 0x08000000 + base + 5 * stride + 0x33
    for probe in (0, 7, 99, 255):
        gba.uc.mem_write(addr, bytes([probe]))
        gba.uc.mem_write(unit + 5, bytes([5]))
        if gba.call(getter, [unit]) != probe:
            moved = False
    gba.uc.mem_write(addr, bytes([rom[base + 5 * stride + 0x33]]))
    ok = bad == 0 and moved
    print(f"   getter matches the table for {count - bad}/{count} jobs")
    print(f"   patching the field moves the result: {moved}")
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
               check_stat_ids(gba, rom),
               check_healthy_rule(gba),
               check_gate(gba, args.samples),
               check_resist_slots(gba, rom),
               check_unarmed(gba, rom)]
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
