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
                             entry["ability_id"] * ABILITY_STRIDE + 0x0C]
        descriptor = EFFECT_TABLE - ROM + entry["raw_effect"] * 4
        descriptor_ok &= ability_effect == entry["raw_effect"]
        descriptor_ok &= rom[descriptor + 1] == entry["case"]
        descriptor_ok &= (names.ability(entry["ability_id"]) ==
                          entry["ability_name"])
    # Poison Claw carries damage first and Poison second; its second raw effect
    # is a separate proof that raw effects 124 and 125 share case 61.
    poison_claw = ABILITY_TABLE - ROM + 293 * ABILITY_STRIDE + 0x0C
    descriptor_ok &= names.ability(293) == "Poison Claw"
    descriptor_ok &= rom[poison_claw + 1] == 124
    descriptor_ok &= rom[EFFECT_TABLE - ROM + 124 * 4 + 1] == 61
    print(f"2. named ability/effect joins: {'OK' if descriptor_ok else 'FAIL'} "
          "(Speedbreak 49->20; Sleep 97->45; Slow 104->51; "
          "Haste 105->52; Poison 125->61)")
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
          "(five internal cases call the expected status setters)")
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
          "(five bits, clear/set round-trips)")
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

    print()
    if failures:
        print(f"FAILED: {len(failures)} — {', '.join(failures)}")
        return 1
    print("PASS: 7/7 status checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
