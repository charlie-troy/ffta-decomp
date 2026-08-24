"""Validate behavior-backed unit status names against the retail ROM.

    python tools/validate_statuses.py baserom.gba
"""
import argparse
import struct

from emulate import Gba
from ffta_names import Names
from status_flags import STATUS_FLAGS
from thumb import bl_target, find_extent

HANDLER_TABLE = 0x083A87B4
EFFECT_TABLE = 0x08553E70
ABILITY_TABLE = 0x0855187C
ABILITY_STRIDE = 0x1C
SPEED_READER = 0x0812E368
HIT_READER = 0x0812C8DC
STAT_GETTER = 0x080C7EA4
EFFECTIVE_ZOMBIE = 0x081308F4
STATUS_INITIALIZER = 0x08133A58
ROM = 0x08000000


def calls_from(rom, start, end):
    calls = set()
    for offset in range(start - ROM, end - ROM - 3, 2):
        first = int.from_bytes(rom[offset:offset + 2], "little")
        second = int.from_bytes(rom[offset + 2:offset + 4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            calls.add(bl_target(ROM + offset, first, second))
    return calls


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    args = parser.parse_args(argv)
    rom = open(args.rom, "rb").read()
    failures = []

    table = HANDLER_TABLE - ROM
    pointers = [int.from_bytes(rom[table + i * 12 + 8:
                                   table + i * 12 + 12], "little")
                for i in range(92)]
    table_ok = all(ROM < pointer < 0x08360000 and pointer & 1
                   for pointer in pointers)
    print(f"1. status handler table: {'OK' if table_ok else 'FAIL'} "
          "(92 executable entries, 12-byte stride)")
    if not table_ok:
        failures.append("status handler table")

    descriptor_ok = True
    names = Names(rom)
    for entry in STATUS_FLAGS:
        ability_effect = rom[ABILITY_TABLE - ROM +
                             entry["ability_id"] * ABILITY_STRIDE + 0x0C +
                             entry.get("effect_slot", 0)]
        descriptor = EFFECT_TABLE - ROM + entry["raw_effect"] * 4
        descriptor_ok &= ability_effect == entry["raw_effect"]
        descriptor_ok &= rom[descriptor + 1] == entry["case"]
        descriptor_ok &= (names.ability(entry["ability_id"]) ==
                          entry["ability_name"])
    # Secondary-effect abilities independently converge on the same cases as
    # the pure status abilities, guarding both slot selection and semantics.
    alternates = [
        (280, "Poison Frog", 1, 39, 12),
        (293, "Poison Claw", 1, 124, 61),
        (240, "Blindshot", 1, 85, 35),
        (242, "Stopshot", 1, 47, 19),
    ]
    for ability_id, name, slot, raw_effect, case in alternates:
        effect = (ABILITY_TABLE - ROM + ability_id * ABILITY_STRIDE + 0x0C +
                  slot)
        descriptor_ok &= names.ability(ability_id) == name
        descriptor_ok &= rom[effect] == raw_effect
        descriptor_ok &= rom[EFFECT_TABLE - ROM + raw_effect * 4 + 1] == case
    print(f"2. named ability/effect joins: {'OK' if descriptor_ok else 'FAIL'} "
          f"({len(STATUS_FLAGS)} named effects; Frog/Stop/Blind/Poison have "
          "independent alternate abilities)")
    if not descriptor_ok:
        failures.append("named ability/effect joins")

    handler_ok = True
    for entry in STATUS_FLAGS:
        pointer = pointers[entry["case"] - 1]
        handler_ok &= pointer == entry["handler"]
        start = pointer & ~1
        extent = find_extent(rom, start - ROM, 512)
        handler_ok &= extent is not None
        if extent:
            handler_ok &= entry["setter"] in calls_from(
                rom, start, ROM + extent[0])
    print(f"3. named handler joins: {'OK' if handler_ok else 'FAIL'} "
          f"({len(STATUS_FLAGS)} internal cases call expected setters)")
    if not handler_ok:
        failures.append("named handler joins")

    gba = Gba(args.rom)
    unit = 0x02001000
    getter_ok = True
    for entry in STATUS_FLAGS:
        gba.reset_ram()
        getter_ok &= gba.call(entry["getter"], [unit]) == 0
        gba.write8(unit + entry["offset"], entry["mask"])
        getter_ok &= gba.call(entry["getter"], [unit]) == 1
        gba.call(entry["setter"], [unit, 0])
        getter_ok &= gba.call(entry["getter"], [unit]) == 0
        gba.call(entry["setter"], [unit, 1])
        getter_ok &= gba.call(entry["getter"], [unit]) == 1
    print(f"4. getter/setter pairs: {'OK' if getter_ok else 'FAIL'} "
          f"({len(STATUS_FLAGS)} bits, clear/set round-trips)")
    if not getter_ok:
        failures.append("getter/setter pairs")

    def speed(ea=0, eb=0, ec=0):
        gba.reset_ram()
        gba.uc.mem_write(unit + 0xD2, struct.pack("<H", 100))
        gba.write8(unit + 0xEA, ea)
        gba.write8(unit + 0xEB, eb)
        gba.write8(unit + 0xEC, ec)
        return gba.call(SPEED_READER, [unit])

    speeds = {"base": speed(), "speed_down": speed(ec=0x04),
              "unidentified_ea_bit1": speed(ea=0x02),
              "sleep": speed(eb=0x04), "slow": speed(ea=0x40),
              "haste": speed(ea=0x20),
              "haste_slow": speed(ea=0x60)}
    expected = {"base": 100, "speed_down": 50,
                "unidentified_ea_bit1": 50, "sleep": 100,
                "slow": 50, "haste": 200, "haste_slow": 100}
    speed_ok = speeds == expected
    print(f"5. effective speed: {'OK' if speed_ok else 'FAIL'} ({speeds})")
    if not speed_ok:
        failures.append("effective speed")

    source = 0x02001200
    target = 0x02001400
    for actor in (source, target):
        gba.uc.mem_write(actor, b"\0" * 0x200)
        gba.uc.mem_write(actor + 0x18, struct.pack("<HHH", 100, 100, 20))
        gba.uc.mem_write(actor + 0xD2, struct.pack("<H", 50))
    ordinary_hit = gba.call(HIT_READER, [source, target, 0, 0])
    gba.write8(target + 0xEB, 0x04)
    sleep_hit = gba.call(HIT_READER, [source, target, 0, 0])
    sleep_ok = ordinary_hit == 95 and sleep_hit == 100
    print(f"6. Sleep vulnerability: {'OK' if sleep_ok else 'FAIL'} "
          f"(hit chance {ordinary_hit} -> {sleep_hit})")
    if not sleep_ok:
        failures.append("Sleep vulnerability")

    # The speed-down bit also controls the red stat-display palette, while
    # Slow/Haste are the adjacent inverse pair in the effect table.
    display_ok = (0x080CDA34 in calls_from(rom, 0x08075AA0, 0x08075B30) and
                  rom[0x75AEE:0x75AFA] ==
                  bytes.fromhex("d0263602002801d0a0263602") and
                  STATUS_FLAGS[2]["case"] + 1 == STATUS_FLAGS[3]["case"])
    print(f"7. independent naming anchors: {'OK' if display_ok else 'FAIL'} "
          "(Speed Down display; adjacent Slow/Haste pair)")
    if not display_ok:
        failures.append("independent naming anchors")

    # Unit +0x28 bit 0x0800 is the persistent/innate form of Zombie. The
    # effective predicate accepts either that bit or the live +0xe9 bit 3,
    # and the battle-status initializer copies the effective state through the
    # same setter used by Zombify's application case.
    gba.reset_ram()
    blank_zombie = gba.call(EFFECTIVE_ZOMBIE, [unit])
    gba.write8(unit + 0xE9, 0x08)
    live_zombie = gba.call(EFFECTIVE_ZOMBIE, [unit])
    gba.reset_ram()
    gba.uc.mem_write(unit + 0x28, struct.pack("<H", 0x0800))
    innate_zombie = gba.call(EFFECTIVE_ZOMBIE, [unit])
    effective_calls = calls_from(rom, EFFECTIVE_ZOMBIE, 0x0813091C)
    init_calls = calls_from(rom, STATUS_INITIALIZER, 0x08133AC0)
    innate_ok = ((blank_zombie, live_zombie, innate_zombie) == (0, 1, 1) and
                 STAT_GETTER in effective_calls and
                 0x080CD9A4 in effective_calls and
                 0x080CDE80 in init_calls)
    print(f"8. innate Zombie bridge: {'OK' if innate_ok else 'FAIL'} "
          f"(blank/live/innate={blank_zombie}/{live_zombie}/{innate_zombie})")
    if not innate_ok:
        failures.append("innate Zombie bridge")

    print()
    if failures:
        print(f"FAILED: {len(failures)} — {', '.join(failures)}")
        return 1
    print("PASS: 8/8 status checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
