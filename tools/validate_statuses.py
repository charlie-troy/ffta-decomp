"""Validate behavior-backed unit status names against the retail ROM.

    python tools/validate_statuses.py baserom.gba
"""
import argparse
import struct

from emulate import Gba
from ffta_names import Names
from status_flags import STATUS_FLAGS, PERSISTENT_STATUS_FLAGS
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
DURATION_RECONCILER = 0x08131C58
YELLOW_CARD_HANDLER = 0x081337F4
YELLOW_CLIP_HANDLER = 0x08133758
DOOM_TICK_START, DOOM_TICK_END = 0x0809E328, 0x0809E398
CLEAR_BATTLE_STATUSES = 0x08097298
MOVEMENT_MODE_READER = 0x080C5320
ABILITY_USABILITY = 0x08133E18
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

    duration_entries = [entry for entry in STATUS_FLAGS
                        if "duration_offset" in entry]
    duration_ok = True
    reconciler_calls = calls_from(rom, DURATION_RECONCILER, 0x08131DA4)
    for entry in duration_entries:
        pointer = pointers[entry["case"] - 1]
        start = pointer & ~1
        extent = find_extent(rom, start - ROM, 512)
        handler_calls = (calls_from(rom, start, ROM + extent[0])
                         if extent else set())
        duration_ok &= entry["duration_setter"] in handler_calls
        duration_ok &= entry["getter"] in reconciler_calls
        duration_ok &= entry["duration_setter"] in reconciler_calls
        gba.reset_ram()
        duration_ok &= gba.call(entry["duration_getter"], [unit]) == 0
        gba.call(entry["duration_setter"], [unit, 7])
        duration_ok &= gba.call(entry["duration_getter"], [unit]) == 7
        stat = 0x28 + entry["duration_offset"] - 0xD8
        duration_ok &= gba.call(STAT_GETTER, [unit, stat]) == 7
    print(f"5. named status durations: {'OK' if duration_ok else 'FAIL'} "
          f"({len(duration_entries)} handler/live-bit/counter joins)")
    if not duration_ok:
        failures.append("named status durations")

    doom = next(entry for entry in STATUS_FLAGS if entry["name"] == "doom")
    context, doom_target = 0x02001400, 0x02001600
    gba.reset_ram()
    gba.write32(context + 8, doom_target)
    gba.call(doom["handler"] & ~1, [context])
    applied_doom = gba.call(doom["getter"], [doom_target])
    doom_count = gba.call(doom["duration_getter"], [doom_target])
    doom_tick_calls = calls_from(rom, DOOM_TICK_START, DOOM_TICK_END)
    doom_ok = (applied_doom == 1 and doom_count == 3 and
               doom["getter"] in doom_tick_calls and
               doom["setter"] in doom_tick_calls and
               doom["duration_getter"] in doom_tick_calls and
               doom["duration_setter"] in doom_tick_calls and
               CLEAR_BATTLE_STATUSES in doom_tick_calls)
    print(f"6. Doom countdown: {'OK' if doom_ok else 'FAIL'} "
          f"(Checkmate applies live Doom/count={applied_doom}/{doom_count}; "
          "expiry path clears battle statuses)")
    if not doom_ok:
        failures.append("Doom countdown")

    disable = next(entry for entry in STATUS_FLAGS
                   if entry["name"] == "disable")
    immobilize = next(entry for entry in STATUS_FLAGS
                     if entry["name"] == "immobilize")
    applied_restrictions = {}
    for entry in (disable, immobilize):
        gba.reset_ram()
        gba.write32(context + 8, doom_target)
        gba.call(entry["handler"] & ~1, [context])
        applied_restrictions[entry["name"]] = (
            gba.call(entry["getter"], [doom_target]),
            gba.call(entry["duration_getter"], [doom_target]),
        )
    movement_obj, holder = 0x02002000, 0x02002200
    movement_results = []
    for mask in (0, immobilize["mask"]):
        gba.reset_ram()
        gba.write32(movement_obj, holder)
        gba.write32(holder, doom_target)
        gba.write8(movement_obj + 0x1C, 5)
        gba.write8(doom_target + immobilize["offset"], mask)
        gba.run_range(MOVEMENT_MODE_READER, 0x080C5336,
                      {"r0": movement_obj})
        movement_results.append(gba.uc.mem_read(movement_obj + 0x1C, 1)[0])
    usability_calls = calls_from(rom, ABILITY_USABILITY, 0x08133F42)
    restriction_ok = (applied_restrictions == {
        "disable": (1, 3), "immobilize": (1, 3)
    } and movement_results == [5, 0] and disable["getter"] in usability_calls)
    print(f"7. Disable/Immobilize behavior: "
          f"{'OK' if restriction_ok else 'FAIL'} "
          f"(applied={applied_restrictions}; movement={movement_results}; "
          "Disable checked by ability usability)")
    if not restriction_ok:
        failures.append("Disable/Immobilize behavior")

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
    print(f"8. effective speed: {'OK' if speed_ok else 'FAIL'} ({speeds})")
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
    print(f"9. Sleep vulnerability: {'OK' if sleep_ok else 'FAIL'} "
          f"(hit chance {ordinary_hit} -> {sleep_hit})")
    if not sleep_ok:
        failures.append("Sleep vulnerability")

    # The speed-down bit also controls the red stat-display palette, while
    # Slow/Haste are the adjacent inverse pair in the effect table.
    slow_case = next(entry["case"] for entry in STATUS_FLAGS
                     if entry["name"] == "slow")
    haste_case = next(entry["case"] for entry in STATUS_FLAGS
                      if entry["name"] == "haste")
    display_ok = (0x080CDA34 in calls_from(rom, 0x08075AA0, 0x08075B30) and
                  rom[0x75AEE:0x75AFA] ==
                  bytes.fromhex("d0263602002801d0a0263602") and
                  slow_case + 1 == haste_case)
    print(f"10. independent naming anchors: {'OK' if display_ok else 'FAIL'} "
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
    persistent_zombie = gba.call(EFFECTIVE_ZOMBIE, [unit])
    effective_calls = calls_from(rom, EFFECTIVE_ZOMBIE, 0x0813091C)
    init_calls = calls_from(rom, STATUS_INITIALIZER, 0x08133AC0)
    persistent_ok = ((blank_zombie, live_zombie,
                      persistent_zombie) == (0, 1, 1) and
                 STAT_GETTER in effective_calls and
                 0x080CD9A4 in effective_calls and
                 0x080CDE80 in init_calls)
    print(f"11. persistent Zombie bridge: {'OK' if persistent_ok else 'FAIL'} "
          f"(blank/live/persistent={blank_zombie}/{live_zombie}/{persistent_zombie})")
    if not persistent_ok:
        failures.append("persistent Zombie bridge")

    yellow = next(entry for entry in PERSISTENT_STATUS_FLAGS
                  if entry["name"] == "yellow_card")
    raw_effect = rom[ABILITY_TABLE - ROM +
                     yellow["ability_id"] * ABILITY_STRIDE + 0x0C]
    descriptor_case = rom[EFFECT_TABLE - ROM + raw_effect * 4 + 1]
    handler_pointer = pointers[yellow["case"] - 1]
    context, target = 0x02001400, 0x02001600
    gba.reset_ram()
    gba.write32(context + 4, target)
    gba.write8(0x02003C33, 1)
    gba.run_range(YELLOW_CARD_HANDLER, 0x0813382E, {"r0": context})
    persistent = struct.unpack("<H", gba.uc.mem_read(target + 0x28, 2))[0]
    cancel_raw = rom[ABILITY_TABLE - ROM +
                     yellow["cancel_ability_id"] * ABILITY_STRIDE + 0x0C]
    cancel_case = rom[EFFECT_TABLE - ROM + cancel_raw * 4 + 1]
    cancel_pointer = pointers[yellow["cancel_case"] - 1]
    gba.run_range(YELLOW_CLIP_HANDLER, 0x0813377C, {"r0": context})
    cleared = struct.unpack("<H", gba.uc.mem_read(target + 0x28, 2))[0]
    yellow_ok = (raw_effect == yellow["raw_effect"] and
                 names.ability(yellow["ability_id"]) ==
                 yellow["ability_name"] and
                 descriptor_case == yellow["case"] and
                 handler_pointer == yellow["handler"] and
                 persistent == yellow["mask"] and
                 cancel_raw == yellow["cancel_raw_effect"] and
                 names.ability(yellow["cancel_ability_id"]) ==
                 yellow["cancel_ability_name"] and
                 cancel_case == yellow["cancel_case"] and
                 cancel_pointer == yellow["cancel_handler"] and
                 cleared == 0)
    print(f"12. Yellow Card persistent flag: {'OK' if yellow_ok else 'FAIL'} "
          f"(apply={persistent:#06x}, clip={cleared:#06x})")
    if not yellow_ok:
        failures.append("Yellow Card persistent flag")

    print()
    if failures:
        print(f"FAILED: {len(failures)} — {', '.join(failures)}")
        return 1
    print("PASS: 12/12 status checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
