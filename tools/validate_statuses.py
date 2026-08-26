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
BATTLE_ZOMBIE_PREDICATE = 0x08131030
STATUS_INITIALIZER = 0x08133A58
DURATION_RECONCILER = 0x08131C58
QUICKEN_CONSUME_START, QUICKEN_CONSUME_END = 0x0809E380, 0x0809E3AC
YELLOW_CARD_HANDLER = 0x081337F4
YELLOW_CLIP_HANDLER = 0x08133758
DOOM_TICK_START, DOOM_TICK_END = 0x0809E328, 0x0809E398
CLEAR_BATTLE_STATUSES = 0x08097298
MOVEMENT_MODE_READER = 0x080C5320
ABILITY_USABILITY = 0x08133E18
COVER_HANDLER = 0x08131F44
COVER_GETTER = 0x080CDBCC
STATUS_LINK_GETTER = 0x080CE410
ZOMBIE_COUNT_GETTER = 0x080CE3A0
ZOMBIE_COUNT_SETTER = 0x080CE418
ZERO_HP_PREDICATE = 0x080C8280
RECENT_TARGET_PUSH = 0x08134170
RECENT_TARGET_CONTAINS = 0x081341BC
FORCED_KO_START, FORCED_KO_END = 0x08132AEA, 0x08132B34
MOVEMENT_ORIGIN_START, MOVEMENT_ORIGIN_END = 0x080C537C, 0x080C5390
BATTLE_LIST_SIZE = 0x080C7B08
BATTLE_LIST_INDEX_READER = 0x08099CB8
REMOVAL_COUNTER_START, REMOVAL_COUNTER_END = 0x080A3674, 0x080A36C2
PURGE_FORMULA_START, PURGE_FORMULA_END = 0x0812D3C6, 0x0812D420
POSITION_SNAPSHOT_START, POSITION_SNAPSHOT_END = 0x08096E46, 0x08096E5E
CT_TICK = 0x0809DF7C
PETRIFY_SET_END = 0x08132982
ROM = 0x08000000


def calls_from(rom, start, end):
    calls = set()
    for offset in range(start - ROM, end - ROM - 3, 2):
        first = int.from_bytes(rom[offset:offset + 2], "little")
        second = int.from_bytes(rom[offset + 2:offset + 4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            calls.add(bl_target(ROM + offset, first, second))
    return calls


def call_sites_to(rom, start, end, target):
    sites = []
    for offset in range(start - ROM, end - ROM - 3, 2):
        first = int.from_bytes(rom[offset:offset + 2], "little")
        second = int.from_bytes(rom[offset + 2:offset + 4], "little")
        if (first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800 and
                bl_target(ROM + offset, first, second) == target):
            sites.append(ROM + offset)
    return sites


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
        (136, "Mog Shield", 0, 37, 10),
        (161, "Rockseal", 0, 98, 46),
        (296, "Blaster", 0, 98, 46),
        (216, "Smile", 0, 29, 2),
    ]
    for ability_id, name, slot, raw_effect, case in alternates:
        effect = (ABILITY_TABLE - ROM + ability_id * ABILITY_STRIDE + 0x0C +
                  slot)
        descriptor_ok &= names.ability(ability_id) == name
        descriptor_ok &= rom[effect] == raw_effect
        descriptor_ok &= rom[EFFECT_TABLE - ROM + raw_effect * 4 + 1] == case
    print(f"2. named ability/effect joins: {'OK' if descriptor_ok else 'FAIL'} "
          f"({len(STATUS_FLAGS)} named effects; eight independent alternate "
          "ability joins)")
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
    astra = next(entry for entry in STATUS_FLAGS if entry["name"] == "astra")
    petrify = next(entry for entry in STATUS_FLAGS
                   if entry["name"] == "petrify")
    gba.reset_ram()
    gba.write32(context + 8, doom_target)
    gba.call(astra["handler"] & ~1, [context])
    astra_petrify_states = [(gba.call(astra["getter"], [doom_target]),
                             gba.call(petrify["getter"], [doom_target]))]
    # Astra intercepts Petrify and is consumed. A second unprotected
    # application reaches the Petrify setter; stop before unrelated battle
    # presentation/global-list work later in that handler.
    gba.call(petrify["handler"] & ~1, [context])
    astra_petrify_states.append(
        (gba.call(astra["getter"], [doom_target]),
         gba.call(petrify["getter"], [doom_target])))
    gba.run_range(petrify["handler"] & ~1, PETRIFY_SET_END,
                  {"r0": context})
    astra_petrify_states.append(
        (gba.call(astra["getter"], [doom_target]),
         gba.call(petrify["getter"], [doom_target])))

    battle = 0x02002000
    battle_unit = battle + 4
    gba.reset_ram()
    gba.uc.mem_write(battle, bytes(0x10C))
    gba.write32(battle, 1)
    gba.uc.mem_write(battle_unit + 0xD0, struct.pack("<H", 900))
    gba.uc.mem_write(battle_unit + 0xD2, struct.pack("<H", 100))
    gba.uc.mem_write(battle_unit + 0xD4, struct.pack("<H", 25))
    gba.write8(battle_unit + petrify["offset"], petrify["mask"])
    gba.call(CT_TICK, [battle])
    petrified_ct = tuple(struct.unpack("<H", gba.uc.mem_read(offset, 2))[0]
                         for offset in (battle_unit + 0xD0,
                                        battle_unit + 0xD4))

    quicken = next(entry for entry in STATUS_FLAGS
                   if entry["name"] == "quicken")
    gba.reset_ram()
    gba.write32(context + 8, doom_target)
    gba.call(quicken["handler"] & ~1, [context])
    quicken_applied = gba.call(quicken["getter"], [doom_target])
    quicken_consume_calls = calls_from(
        rom, QUICKEN_CONSUME_START, QUICKEN_CONSUME_END)
    quicken_ok = (quicken_applied == 1 and
                  quicken["setter"] in quicken_consume_calls)

    restriction_ok = (applied_restrictions == {
        "disable": (1, 3), "immobilize": (1, 3)
    } and movement_results == [5, 0] and disable["getter"] in usability_calls
        and astra_petrify_states == [(1, 0), (0, 0), (0, 1)]
        and petrified_ct == (0, 0) and quicken_ok)
    print(f"7. action-restriction behavior: "
          f"{'OK' if restriction_ok else 'FAIL'} "
          f"(applied={applied_restrictions}; movement={movement_results}; "
          f"Astra/Petrify={astra_petrify_states}; "
          f"Petrify CT/carry={petrified_ct}; Quicken={quicken_applied})")
    if not restriction_ok:
        failures.append("action-restriction behavior")

    cover_actor, cover_target = 0x02001800, 0x02001A00
    gba.reset_ram()
    gba.write32(context, cover_actor)
    gba.write32(context + 8, cover_target)
    gba.write8(cover_target + 0x104, 0x2A)
    gba.call(COVER_HANDLER, [context])
    cover_live = gba.call(COVER_GETTER, [cover_actor])
    status_link = gba.call(STATUS_LINK_GETTER, [cover_actor])
    link_stat = gba.call(STAT_GETTER, [cover_actor, 0x36])
    link_ok = (cover_live, status_link, link_stat) == (1, 0x2A, 0x2A)
    print(f"8. shared status link: {'OK' if link_ok else 'FAIL'} "
          f"(Cover live/link/stat={cover_live}/{status_link}/{link_stat})")
    if not link_ok:
        failures.append("shared status link")

    def speed(ea=0, eb=0, ec=0):
        gba.reset_ram()
        gba.uc.mem_write(unit + 0xD2, struct.pack("<H", 100))
        gba.write8(unit + 0xEA, ea)
        gba.write8(unit + 0xEB, eb)
        gba.write8(unit + 0xEC, ec)
        return gba.call(SPEED_READER, [unit])

    speeds = {"base": speed(), "speed_down": speed(ec=0x04),
              "mow_down_penalty": speed(ea=0x02),
              "sleep": speed(eb=0x04), "slow": speed(ea=0x40),
              "haste": speed(ea=0x20),
              "haste_slow": speed(ea=0x60)}
    expected = {"base": 100, "speed_down": 50,
                "mow_down_penalty": 50, "sleep": 100,
                "slow": 50, "haste": 200, "haste_slow": 100}
    mow_down = next(entry for entry in STATUS_FLAGS
                    if entry["name"] == "mow_down_speed_penalty")
    gba.reset_ram()
    gba.write32(context + 8, unit)
    gba.uc.mem_write(unit + 0xD2, struct.pack("<H", 100))
    gba.call(mow_down["handler"] & ~1, [context])
    mow_down_applied = (gba.call(mow_down["getter"], [unit]),
                        gba.call(SPEED_READER, [unit]))
    speed_ok = speeds == expected and mow_down_applied == (1, 50)
    print(f"9. effective speed: {'OK' if speed_ok else 'FAIL'} "
          f"({speeds}; Mow Down apply={mow_down_applied})")
    if not speed_ok:
        failures.append("effective speed")

    source = 0x02001200
    target = 0x02001400
    for actor in (source, target):
        gba.uc.mem_write(actor, b"\0" * 0x200)
        gba.uc.mem_write(actor + 0x18, struct.pack("<HHH", 100, 100, 20))
        gba.uc.mem_write(actor + 0xD2, struct.pack("<H", 50))
    ordinary_hit = gba.call(HIT_READER, [source, target, 0, 0])
    gba.write8(target + 0xEA, 0x02)
    mow_down_hit = gba.call(HIT_READER, [source, target, 0, 0])
    gba.write8(target + 0xEA, 0)
    gba.write8(target + 0xEB, 0x04)
    sleep_hit = gba.call(HIT_READER, [source, target, 0, 0])
    sleep_ok = ordinary_hit == 95 and mow_down_hit == 100 and sleep_hit == 100
    print(f"10. Sleep vulnerability: {'OK' if sleep_ok else 'FAIL'} "
          f"(base/Mow Down/Sleep hit chance "
          f"{ordinary_hit}/{mow_down_hit}/{sleep_hit})")
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
    print(f"11. independent naming anchors: {'OK' if display_ok else 'FAIL'} "
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
    print(f"12. persistent Zombie bridge: {'OK' if persistent_ok else 'FAIL'} "
          f"(blank/live/persistent={blank_zombie}/{live_zombie}/{persistent_zombie})")
    if not persistent_ok:
        failures.append("persistent Zombie bridge")

    # Clearing transient battle statuses is also the reset point for the
    # three-turn Zombie revival delay. Persistent Zombie proves the effective
    # status independently of the live bit, while a blank unit remains zero.
    gba.reset_ram()
    gba.uc.mem_write(unit + 0x28, struct.pack("<H", 0x0800))
    gba.call(CLEAR_BATTLE_STATUSES, [unit])
    revive_count = gba.call(ZOMBIE_COUNT_GETTER, [unit])
    revive_stat = gba.call(STAT_GETTER, [unit, 0x28])
    gba.reset_ram()
    gba.call(CLEAR_BATTLE_STATUSES, [unit])
    blank_count = gba.call(ZOMBIE_COUNT_GETTER, [unit])
    zombie_tick_calls = calls_from(rom, 0x0809E7A2, 0x0809E7F2)
    revive_ok = (revive_count == 3 and revive_stat == 3 and
                 blank_count == 0 and
                 BATTLE_ZOMBIE_PREDICATE in zombie_tick_calls and
                 ZERO_HP_PREDICATE in zombie_tick_calls and
                 ZOMBIE_COUNT_GETTER in zombie_tick_calls and
                 ZOMBIE_COUNT_SETTER in zombie_tick_calls)
    print(f"13. Zombie revival countdown: {'OK' if revive_ok else 'FAIL'} "
          f"(persistent/blank={revive_count}/{blank_count}; stat={revive_stat})")
    if not revive_ok:
        failures.append("Zombie revival countdown")

    # +0xe7 is a two-entry MRU of distinct action targets. Each nibble stores
    # unit +0x104; the low nibble is newest and 0xf is the empty sentinel.
    actor = 0x02001000
    target_a, target_b, target_c = 0x02001200, 0x02001400, 0x02001600
    gba.reset_ram()
    gba.write8(actor + 0xE7, 0xFF)
    for target, unit_id in ((target_a, 5), (target_b, 6), (target_c, 7)):
        gba.write8(target + 0x104, unit_id)
    history_states = []
    for target in (target_a, target_b, target_a, target_c):
        gba.call(RECENT_TARGET_PUSH, [actor, target])
        history_states.append(gba.call(STAT_GETTER, [actor, 0x37]))
    memberships = tuple(gba.call(RECENT_TARGET_CONTAINS, [actor, target])
                        for target in (target_a, target_b, target_c))
    action_sites = call_sites_to(rom, 0x080A23B8, 0x080A3778,
                                RECENT_TARGET_PUSH)
    ai_calls = calls_from(rom, 0x080C32C0, 0x080C35B0)
    history_ok = (history_states == [0xF5, 0x56, 0x65, 0x57] and
                  memberships == (1, 0, 1) and len(action_sites) == 4 and
                  RECENT_TARGET_CONTAINS in ai_calls)
    print(f"14. recent target ids: {'OK' if history_ok else 'FAIL'} "
          f"(states={[hex(v) for v in history_states]}; "
          f"contains={memberships}; action writers={len(action_sites)})")
    if not history_ok:
        failures.append("recent target ids")

    # The forced-KO result path exposes the direction of the adjacent counters:
    # actor +0xf1 records the inflicted KO and target +0xf2 records suffering it.
    result = 0x02001000
    ko_actor, ko_target = 0x02001200, 0x02001400
    gba.reset_ram()
    gba.write32(result, ko_actor)
    gba.write32(result + 8, ko_target)
    gba.write8(ko_actor + 0xF1, 9)
    gba.write8(ko_target + 0xF2, 11)
    gba.uc.mem_write(ko_target + 0x18, struct.pack("<H", 123))
    gba.run_range(FORCED_KO_START, FORCED_KO_END, {"r4": result, "r1": 0})
    ko_hp = struct.unpack("<H", gba.uc.mem_read(ko_target + 0x18, 2))[0]
    ko_inflicted = gba.call(STAT_GETTER, [ko_actor, 0x39])
    ko_suffered = gba.call(STAT_GETTER, [ko_target, 0x3A])
    ko_ok = (ko_hp, ko_inflicted, ko_suffered) == (0, 10, 12)
    print(f"15. KO counters: {'OK' if ko_ok else 'FAIL'} "
          f"(target HP={ko_hp}; inflicted/suffered={ko_inflicted}/{ko_suffered})")
    if not ko_ok:
        failures.append("KO counters")

    # +0xf6/+0xf7 are copied into the movement-search origin, while the
    # adjacent +0xf8 is the vertical component passed with that X/Y pair to
    # spatial range formulas.
    unit = 0x02001000
    holder, movement = 0x02001200, 0x02001400
    gba.reset_ram()
    gba.write8(unit + 0xF6, 12)
    gba.write8(unit + 0xF7, 9)
    gba.write8(unit + 0xF8, 4)
    gba.write32(holder, unit)
    gba.write32(movement, holder)
    gba.run_range(MOVEMENT_ORIGIN_START, MOVEMENT_ORIGIN_END,
                  {"r4": movement})
    spatial_stats = tuple(gba.call(STAT_GETTER, [unit, stat])
                          for stat in (0x3E, 0x3F, 0x40))
    movement_origin = tuple(gba.uc.mem_read(movement + 0x18, 2))
    range_calls = calls_from(rom, 0x0812D2F0, 0x0812D350)
    spatial_ok = (spatial_stats == (12, 9, 4) and
                  movement_origin == (12, 9) and 0x0812D1DC in range_calls)
    print(f"16. battle tile position: {'OK' if spatial_ok else 'FAIL'} "
          f"(stats={spatial_stats}; movement origin={movement_origin})")
    if not spatial_ok:
        failures.append("battle tile position")

    # The battle object builder stores the current unit-list length both as
    # its insertion key and in unit +0xfb, making it a zero-based list index.
    owner, unit_list = 0x02001800, 0x02001A00
    node_a, node_b = 0x02001C00, 0x02001E00
    gba.reset_ram()
    gba.write32(owner + 0x10, unit_list)
    gba.write32(unit_list + 4, node_a)
    gba.write32(node_a + 8, node_b)
    gba.write32(node_b + 8, 0)
    list_size = gba.call(BATTLE_LIST_INDEX_READER, [owner])
    gba.write8(unit + 0xFB, list_size)
    list_stat = gba.call(STAT_GETTER, [unit, 0x43])
    builder_calls = calls_from(rom, 0x0809716C, 0x080971F0)
    builder_store = rom[0x971AA:0x971B0] == bytes.fromhex("2968fb310870")
    list_ok = (list_size == 2 and list_stat == 2 and
               BATTLE_LIST_SIZE in calls_from(rom, BATTLE_LIST_INDEX_READER,
                                              0x08099CC4) and
               BATTLE_LIST_INDEX_READER in builder_calls and builder_store)
    print(f"17. battle list index: {'OK' if list_ok else 'FAIL'} "
          f"(two-node list -> index/stat={list_size}/{list_stat})")
    if not list_ok:
        failures.append("battle list index")

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
    print(f"18. Yellow Card persistent flag: {'OK' if yellow_ok else 'FAIL'} "
          f"(apply={persistent:#06x}, clip={cleared:#06x})")
    if not yellow_ok:
        failures.append("Yellow Card persistent flag")

    # A removal-result branch saturating-increments one of three adjacent
    # counters. Parley and Oust have dedicated ids; Wyrmtamer proves the
    # default/other bucket. The shared purge hit formula then reads the Parley
    # counter as a +10-point threshold modifier alongside KOs inflicted.
    wrapper, inner, removal_unit = 0x02001000, 0x02001200, 0x02001400
    action = 0x02001600
    removal_states = []
    for ability_id in (126, 91, 181):  # Wyrmtamer, Parley, Oust
        gba.reset_ram()
        gba.write32(wrapper, inner)
        gba.write32(inner, removal_unit)
        gba.uc.mem_write(action + 0x10, struct.pack("<H", ability_id))
        gba.uc.mem_write(0x0200F390 + 0x86, struct.pack("<H", 0x40))
        gba.write8(removal_unit + 0xF3, 9)
        gba.write8(removal_unit + 0xF4, 11)
        gba.write8(removal_unit + 0xF5, 13)
        gba.run_range(REMOVAL_COUNTER_START, REMOVAL_COUNTER_END,
                      {"r6": wrapper, "sb": action})
        removal_states.append(tuple(gba.uc.mem_read(removal_unit + 0xF3, 3)))

    caster, purge_target = 0x02001800, 0x02001A00
    purge_rates = []
    for parley_count in (0, 1, 5):
        gba.reset_ram()
        gba.write8(caster + 0xF1, 3)
        gba.write8(caster + 0xF4, parley_count)
        gba.uc.mem_write(purge_target + 0x18, struct.pack("<H", 10))
        gba.uc.mem_write(purge_target + 0x1A, struct.pack("<H", 100))
        purge_rates.append(gba.run_range(
            PURGE_FORMULA_START, PURGE_FORMULA_END,
            {"r6": caster, "r5": purge_target}))
    purge_descriptor_ids = tuple(
        rom[ABILITY_TABLE - ROM + ability_id * ABILITY_STRIDE + 0x0C]
        for ability_id in (91, 126, 181))
    purge_selectors = tuple(
        rom[EFFECT_TABLE - ROM + effect_id * 4 + 2]
        for effect_id in purge_descriptor_ids)
    removal_ok = (removal_states == [(10, 11, 13), (9, 12, 13),
                                     (9, 11, 14)] and
                  purge_rates == [78, 82, 89] and
                  purge_selectors == (8, 8, 8))
    print(f"19. removal counters and purge formula: "
          f"{'OK' if removal_ok else 'FAIL'} "
          f"(states={removal_states}; rates={purge_rates})")
    if not removal_ok:
        failures.append("removal counters and purge formula")

    # Several placement paths snapshot current X/Y into +0xf9/+0xfa. Execute
    # one retail copy and read the result through generic stats 0x41/0x42.
    holder, position_unit = 0x02001C00, 0x02001E00
    gba.reset_ram()
    gba.write32(holder, position_unit)
    gba.write8(position_unit + 0xF6, 12)
    gba.write8(position_unit + 0xF7, 9)
    gba.run_range(POSITION_SNAPSHOT_START, POSITION_SNAPSHOT_END,
                  {"r0": holder})
    saved_position = tuple(gba.call(STAT_GETTER, [position_unit, stat])
                           for stat in (0x41, 0x42))
    snapshot_pattern = bytes.fromhex(
        "2068011cf6310978f93001702068011cf7310978fa300170")
    snapshot_sites = rom.count(snapshot_pattern)
    position_ok = saved_position == (12, 9) and snapshot_sites >= 4
    print(f"20. saved tile position: {'OK' if position_ok else 'FAIL'} "
          f"(saved X/Y={saved_position}; copy anchors={snapshot_sites})")
    if not position_ok:
        failures.append("saved tile position")

    print()
    if failures:
        print(f"FAILED: {len(failures)} — {', '.join(failures)}")
        return 1
    print("PASS: 20/20 status/state checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
