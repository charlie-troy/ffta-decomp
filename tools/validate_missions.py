"""Validate the named mission fields by executing the retail ROM's code.

    python tools/validate_missions.py baserom.gba

This is intentionally independent of the CSV writer. It checks the raw table,
the mission property accessor, and the function that applies clan progression
rewards to the save-data structure.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emulate import Gba
from ffta_names import Names
from mission_table import (JOB_KIND_BASE, JOB_KIND_STRIDE, JOB_COUNT,
                           availability_days_get, availability_days_set,
                           blocked_item_get, blocked_item_set,
                           blocked_job_get, blocked_job_set,
                           clear_condition_get, clear_condition_set,
                           clear_count_get, clear_count_set,
                           mission_behavior_get, mission_behavior_set,
                           mission_icon_group_get, mission_icon_group_set,
                           mission_type_name,
                           required_job_get, required_job_set)

BASE = 0x0855AE4C
STRIDE = 0x46
COUNT = 512
ACCESSOR = 0x080CE4DC
APPLY_CLAN_REWARD = 0x08046850
ADJUST_FEE = 0x080CEC78
RATE_DISPATCH = 0x080CF310
INDEX_PLACEMENT = 0x08045400
INDEX_TRIGGER = 0x08123898
CLAN_STATE = 0x020021B4
MAP_SYMBOL_STATE = 0x02002CC3
SELECTED_MISSION = 0x02002170
SELECTED_INDEX = 0x02003C2A

INDEX_BASE = 0x08563A70
INDEX_STRIDE = 12
INDEX_COUNT = 256
INDEX_END = 0x08564670

# Accessor properties 0x21..0x29 are direct loads of +0x2a..+0x32.
TRACKS = (
    ("clan", 0x2A, 0x21),
    ("combat", 0x2B, 0x22),
    ("magic", 0x2C, 0x23),
    ("appraise", 0x2D, 0x24),
    ("gather", 0x2E, 0x25),
    ("smithing", 0x2F, 0x26),
    ("craft", 0x30, 0x27),
    ("negotiate", 0x31, 0x28),
    ("track", 0x32, 0x29),
)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rom")
    args = p.parse_args(argv)

    rom = open(args.rom, "rb").read()
    gba = Gba(args.rom)
    names = Names(rom)
    failures = []

    ids_ok = all(
        int.from_bytes(
            rom[BASE - 0x08000000 + i * STRIDE:
                BASE - 0x08000000 + i * STRIDE + 2], "little"
        ) == i
        for i in range(COUNT)
    )
    print(f"1. mission id echo: {'OK' if ids_ok else 'FAIL'} ({COUNT} entries)")
    if not ids_ok:
        failures.append("mission id echo")

    accessor_checks = 0
    accessor_ok = True
    for i in range(COUNT):
        entry = BASE - 0x08000000 + i * STRIDE
        for _name, off, prop in TRACKS:
            got = gba.call(ACCESSOR, [i, prop])
            want = rom[entry + off]
            accessor_checks += 1
            if got != want:
                accessor_ok = False
                failures.append(
                    f"accessor mission {i} prop {prop:#x}: {got} != {want}"
                )
                break
        if not accessor_ok:
            break
    print(
        f"2. clan reward properties: {'OK' if accessor_ok else 'FAIL'} "
        f"({accessor_checks} executed reads)"
    )

    flow_ok = True
    flow_details = []
    for index, (name, off, _prop) in enumerate(TRACKS):
        sample = next(
            (
                (i, rom[BASE - 0x08000000 + i * STRIDE + off])
                for i in range(COUNT)
                if 0 < rom[BASE - 0x08000000 + i * STRIDE + off] < 100
            ),
            None,
        )
        if sample is None:
            flow_ok = False
            failures.append(f"no non-boundary sample for {name}")
            continue
        mission, reward = sample
        gba.reset_ram()
        level_addr = CLAN_STATE + index * 2
        gba.write8(level_addr, 1)
        gba.write8(level_addr + 1, 0)
        gba.call(APPLY_CLAN_REWARD, [BASE + mission * STRIDE, 0, index, 1])
        got = tuple(gba.uc.mem_read(level_addr, 2))
        want = (1, reward)
        flow_details.append(f"{name}=mission {mission}/{reward}")
        if got != want:
            flow_ok = False
            failures.append(f"{name} apply path: {got} != {want}")
    print(
        f"3. clan reward application: {'OK' if flow_ok else 'FAIL'} "
        f"({'; '.join(flow_details)})"
    )

    job_names = {0: ""}
    for job in range(JOB_COUNT):
        code = rom[JOB_KIND_BASE + job * JOB_KIND_STRIDE + 1]
        name = names.job(job)
        if code and name and code not in job_names:
            job_names[code] = name
    job_ok = True
    job_checks = 0
    for i in range(COUNT):
        entry = BASE - 0x08000000 + i * STRIDE
        for prop, get, label in (
            (0x30, required_job_get, "required"),
            (0x34, blocked_job_get, "blocked"),
        ):
            got = gba.call(ACCESSOR, [i, prop])
            want = get(rom, entry)
            job_checks += 1
            if got != want:
                job_ok = False
                failures.append(f"{label} job mission {i}: {got} != {want}")
                break
        if not job_ok:
            break
    anchors = {130: "Soldier", 137: "Juggler", 164: "Gadgeteer"}
    anchor_names = {
        i: job_names.get(required_job_get(
            rom, BASE - 0x08000000 + i * STRIDE), "")
        for i in anchors
    }
    job_ok = job_ok and anchor_names == anchors
    if anchor_names != anchors:
        failures.append(f"required job anchors: {anchor_names}")
    probe = bytearray(rom)
    probe_entry = BASE - 0x08000000 + 130 * STRIDE
    keep_39 = probe[probe_entry + 0x39] & 0x07
    keep_3a = probe[probe_entry + 0x3A] & 0xFE
    for code in (0, 1, 31, 32, 34, 63):
        required_job_set(probe, probe_entry, code)
        if (
            required_job_get(probe, probe_entry) != code
            or probe[probe_entry + 0x39] & 0x07 != keep_39
            or probe[probe_entry + 0x3A] & 0xFE != keep_3a
        ):
            job_ok = False
            failures.append(f"required job packing failed for {code}")
            break
    blocked_entry = BASE - 0x08000000 + 173 * STRIDE
    keep_3c = probe[blocked_entry + 0x3C] & 0x03
    for code in (0, 1, 31, 32, 34, 63):
        blocked_job_set(probe, blocked_entry, code)
        if (
            blocked_job_get(probe, blocked_entry) != code
            or probe[blocked_entry + 0x3C] & 0x03 != keep_3c
        ):
            job_ok = False
            failures.append(f"blocked job packing failed for {code}")
            break

    # The Match blocks normalized job code 1 (Soldier). Execute the dispatch
    # rating with otherwise-identical synthetic units to verify the polarity:
    # Soldier is rejected as 0; Paladin reaches normal scoring.
    dispatch = 0x02001000
    unit = 0x02001100
    gba.reset_ram()
    gba.uc.mem_write(dispatch, bytes([173, 0]) + bytes(0x20))
    gba.uc.mem_write(unit, bytes(0x108))
    gba.write8(unit + 7, 2)  # Soldier -> normalized code 1
    blocked_rating = gba.call(RATE_DISPATCH, [dispatch, unit, 0])
    gba.write8(unit + 7, 3)  # Paladin -> normalized code 2
    allowed_rating = gba.call(RATE_DISPATCH, [dispatch, unit, 0])
    job_ok = job_ok and blocked_rating == 0 and allowed_rating != 0
    if blocked_rating != 0 or allowed_rating == 0:
        failures.append(
            f"blocked job behavior: Soldier={blocked_rating}, "
            f"Paladin={allowed_rating}"
        )
    print(
        f"4. dispatch job rules: {'OK' if job_ok else 'FAIL'} "
        f"({job_checks} accessor reads; required {anchor_names}; "
        f"The Match ratings Soldier={blocked_rating}/Paladin={allowed_rating}; "
        "packing preserves adjacent bits)"
    )

    fee_ok = True
    fee_checks = 0
    for i in range(COUNT):
        entry = BASE - 0x08000000 + i * STRIDE
        got = gba.call(ACCESSOR, [i, 0x36])
        want = rom[entry + 0x3E] * 200
        fee_checks += 1
        if got != want:
            fee_ok = False
            failures.append(f"base fee mission {i}: {got} != {want}")
            break
    base_fee_anchors = {
        i: rom[BASE - 0x08000000 + i * STRIDE + 0x3E] * 200
        for i in (3, 4, 164)
    }
    adjusted_fee_anchors = {
        i: gba.call(ADJUST_FEE, [i, 2, 0]) for i in (3, 4)
    }
    fee_ok = fee_ok and base_fee_anchors == {3: 200, 4: 600, 164: 1600}
    fee_ok = fee_ok and adjusted_fee_anchors == {3: 300, 4: 900}
    if not fee_ok:
        failures.append(
            f"fee anchors: base={base_fee_anchors}, adjusted={adjusted_fee_anchors}"
        )
    print(
        f"5. base pub fee: {'OK' if fee_ok else 'FAIL'} "
        f"({fee_checks} accessor reads; base {base_fee_anchors}; "
        f"unliberated-town prices {adjusted_fee_anchors})"
    )

    # Retail leaves +0x3d clear on every mission, but the reader and rater both
    # implement it. Prove the latent path by patching the emulator's ROM map:
    # raw 7 maps to item 382, and either matching dispatch slot rejects the
    # unit. The third argument gates this item check.
    dormant_clear = all(
        rom[BASE - 0x08000000 + i * STRIDE + 0x3D] == 0
        for i in range(COUNT)
    )
    dormant_entry = BASE - 0x08000000 + 173 * STRIDE
    probe = bytearray(rom)
    dormant_pack_ok = True
    for item in (0, 376, 382, 630):
        blocked_item_set(probe, dormant_entry, item)
        if blocked_item_get(probe, dormant_entry) != item:
            dormant_pack_ok = False
            failures.append(f"blocked item packing failed for {item}")
            break
    gba.reset_ram()
    gba.uc.mem_write(dispatch, bytes([173, 0, 0, 0, 7, 8]) + bytes(0x20))
    gba.uc.mem_write(unit, bytes(0x108))
    gba.write8(unit + 7, 3)  # Paladin, not blocked by The Match's job rule
    gba.uc.mem_write(BASE + 173 * STRIDE + 0x3D, bytes([7]))
    mapped_item = gba.call(ACCESSOR, [173, 0x35])
    slot4_rating = gba.call(RATE_DISPATCH, [dispatch, unit, 1])
    gba.write8(dispatch + 4, 6)
    gba.write8(dispatch + 5, 7)
    slot5_rating = gba.call(RATE_DISPATCH, [dispatch, unit, 1])
    gate_off_rating = gba.call(RATE_DISPATCH, [dispatch, unit, 0])
    dormant_ok = (
        dormant_clear and dormant_pack_ok and mapped_item == 382
        and slot4_rating == 0 and slot5_rating == 0 and gate_off_rating != 0
    )
    if not dormant_ok:
        failures.append(
            "dormant item exclusion: "
            f"clear={dormant_clear}, item={mapped_item}, "
            f"ratings={slot4_rating}/{slot5_rating}/{gate_off_rating}"
        )
    print(
        f"6. dormant dispatch-item exclusion: "
        f"{'OK' if dormant_ok else 'FAIL'} "
        f"(retail clear={dormant_clear}; item={mapped_item}; "
        f"ratings slot4={slot4_rating}/slot5={slot5_rating}/gate-off="
        f"{gate_off_rating})"
    )

    def reward(i):
        entry = BASE - 0x08000000 + i * STRIDE
        return rom[entry + 0x33] * 200, rom[entry + 0x34] * 10

    anchors_ok = reward(3) == (600, 40) and reward(25) == (28600, 80)
    print(
        "7. gil/AP anchors: "
        f"{'OK' if anchors_ok else 'FAIL'} "
        f"(Herb Picking {reward(3)}, Over The Hill {reward(25)})"
    )
    if not anchors_ok:
        failures.append("gil/AP anchors")

    index_off = INDEX_BASE - 0x08000000
    sentinel_ok = rom[index_off:index_off + INDEX_STRIDE] == bytes(INDEX_STRIDE)
    index_ids_ok = all(
        int.from_bytes(
            rom[index_off + i * INDEX_STRIDE + 2:
                index_off + i * INDEX_STRIDE + 4], "little"
        ) < COUNT
        for i in range(INDEX_COUNT)
    )
    boundary_ok = INDEX_BASE + INDEX_COUNT * INDEX_STRIDE == INDEX_END

    # Record 2 carries map symbol id 2. sub_08045400 resolves that id through
    # the persistent 12-byte-per-symbol placement state and returns placement-1.
    gba.reset_ram()
    gba.write8(MAP_SYMBOL_STATE + 1 * 12, 17)
    gba.write8(MAP_SYMBOL_STATE + 2 * 12, 29)
    placement = gba.call(INDEX_PLACEMENT, [2])

    # The script handler at 0x08123898 scans records 255..1 for +0x01 and
    # selects +0x02. Trigger 1 is unique and skips an unrelated sound call,
    # making it a stable execution anchor: record 1 -> mission 30.
    trigger_arg = 0x02001200
    gba.reset_ram()
    gba.uc.mem_write(trigger_arg, bytes([0, 1, 0]) + bytes(8))
    gba.call(INDEX_TRIGGER, [0, trigger_arg])
    selected_index = gba.uc.mem_read(SELECTED_INDEX, 1)[0]
    selected_mission = int.from_bytes(
        gba.uc.mem_read(SELECTED_MISSION, 2), "little"
    )
    index_ok = (
        sentinel_ok and index_ids_ok and boundary_ok and placement == 16
        and selected_index == 1 and selected_mission == 30
    )
    if not index_ok:
        failures.append(
            "mission index: "
            f"sentinel={sentinel_ok}, ids={index_ids_ok}, end={boundary_ok}, "
            f"placement={placement}, selection={selected_index}/"
            f"{selected_mission}"
        )
    print(
        f"8. mission index: {'OK' if index_ok else 'FAIL'} "
        f"({INDEX_COUNT} records; zero sentinel; symbol 2 -> placement "
        f"{placement}; trigger 1 -> record {selected_index}/mission "
        f"{selected_mission})"
    )

    type_ok = True
    type_checks = 0
    for i in range(COUNT):
        entry = BASE - 0x08000000 + i * STRIDE
        for prop, get, label in (
            (1, mission_behavior_get, "behavior"),
            (2, mission_icon_group_get, "icon group"),
        ):
            got = gba.call(ACCESSOR, [i, prop])
            want = get(rom, entry)
            type_checks += 1
            if got != want:
                type_ok = False
                failures.append(f"mission {label} {i}: {got} != {want}")
                break
        if not type_ok:
            break
    type_anchors = {
        i: (
            mission_behavior_get(rom, BASE - 0x08000000 + i * STRIDE),
            mission_icon_group_get(rom, BASE - 0x08000000 + i * STRIDE),
        )
        for i in (3, 15, 73, 130, 365)
    }
    expected_type_anchors = {
        3: (3, 1),       # Herb Picking: Regular
        15: (1, 1),      # The Bounty: Encounter override
        73: (2, 2),      # Free Sprohm!: Free-Area
        130: (0, 0),     # Dueling Sub: Non-Battle
        365: (2, 3),     # Pam Le Fey: special group
    }
    type_names = {
        i: mission_type_name(*value) for i, value in type_anchors.items()
    }
    type_ok = type_ok and type_anchors == expected_type_anchors
    if type_anchors != expected_type_anchors:
        failures.append(f"mission type anchors: {type_anchors}")
    probe = bytearray(rom)
    type_entry = BASE - 0x08000000 + 3 * STRIDE
    keep_high = probe[type_entry + 2] & 0xC0
    for behavior in range(8):
        mission_behavior_set(probe, type_entry, behavior)
        if (mission_behavior_get(probe, type_entry) != behavior or
                probe[type_entry + 2] & 0xC0 != keep_high):
            type_ok = False
            failures.append(f"mission behavior packing failed for {behavior}")
            break
    for icon_group in range(8):
        keep_behavior = mission_behavior_get(probe, type_entry)
        mission_icon_group_set(probe, type_entry, icon_group)
        if (mission_icon_group_get(probe, type_entry) != icon_group or
                mission_behavior_get(probe, type_entry) != keep_behavior or
                probe[type_entry + 2] & 0xC0 != keep_high):
            type_ok = False
            failures.append(f"mission icon packing failed for {icon_group}")
            break
    print(
        f"9. mission behavior/type: {'OK' if type_ok else 'FAIL'} "
        f"({type_checks} accessor reads; anchors {type_names}; packed edits "
        "preserve adjacent bits)"
    )

    timing_ok = True
    timing_checks = 0
    timing_fields = (
        (0x10, availability_days_get, "availability"),
        (0x11, clear_condition_get, "clear condition"),
        (0x12, clear_count_get, "clear count"),
    )
    for i in range(COUNT):
        entry = BASE - 0x08000000 + i * STRIDE
        for prop, get, label in timing_fields:
            got = gba.call(ACCESSOR, [i, prop])
            want = get(rom, entry)
            timing_checks += 1
            if got != want:
                timing_ok = False
                failures.append(f"mission {label} {i}: {got} != {want}")
                break
        if not timing_ok:
            break

    availability_anchors = {
        41: 10,   # Fire! Fire!
        43: 15,   # Battle Tourney
        104: 20,  # Fiend Run
        106: 35,  # Wyrms Awaken
        113: 40,  # Smuggle Bust
    }
    clear_anchors = {
        128: (2, 2),  # Watching You: win 2 battles
        130: (1, 3),  # Dueling Sub: 3 days
        137: (2, 1),  # Run For Fun: win 1 battle
        138: (1, 10),  # Hungry Ghost: 10 days
    }
    got_availability = {
        i: availability_days_get(
            rom, BASE - 0x08000000 + i * STRIDE)
        for i in availability_anchors
    }
    got_clear = {
        i: (
            clear_condition_get(rom, BASE - 0x08000000 + i * STRIDE),
            clear_count_get(rom, BASE - 0x08000000 + i * STRIDE),
        )
        for i in clear_anchors
    }
    if got_availability != availability_anchors:
        timing_ok = False
        failures.append(f"availability anchors: {got_availability}")
    if got_clear != clear_anchors:
        timing_ok = False
        failures.append(f"clear-condition anchors: {got_clear}")

    probe = bytearray(rom)
    timing_entry = BASE - 0x08000000 + 130 * STRIDE
    for value in (0, 1, 31, 32, 40, 63):
        keep_0f = probe[timing_entry + 0x0F] & 0x07
        keep_10 = probe[timing_entry + 0x10] & 0xFE
        availability_days_set(probe, timing_entry, value)
        if (availability_days_get(probe, timing_entry) != value or
                probe[timing_entry + 0x0F] & 0x07 != keep_0f or
                probe[timing_entry + 0x10] & 0xFE != keep_10):
            timing_ok = False
            failures.append(f"availability packing failed for {value}")
            break
    for value in range(8):
        keep_10 = probe[timing_entry + 0x10] & 0xC7
        clear_condition_set(probe, timing_entry, value)
        if (clear_condition_get(probe, timing_entry) != value or
                probe[timing_entry + 0x10] & 0xC7 != keep_10):
            timing_ok = False
            failures.append(f"clear-condition packing failed for {value}")
            break
    for value in (0, 1, 3, 10, 40, 63):
        keep_10 = probe[timing_entry + 0x10] & 0x3F
        keep_11 = probe[timing_entry + 0x11] & 0xF0
        clear_count_set(probe, timing_entry, value)
        if (clear_count_get(probe, timing_entry) != value or
                probe[timing_entry + 0x10] & 0x3F != keep_10 or
                probe[timing_entry + 0x11] & 0xF0 != keep_11):
            timing_ok = False
            failures.append(f"clear-count packing failed for {value}")
            break
    print(
        f"10. mission availability/clear: "
        f"{'OK' if timing_ok else 'FAIL'} ({timing_checks} accessor reads; "
        f"availability {got_availability}; clear {got_clear}; packed edits "
        "preserve adjacent bits)"
    )

    if failures:
        print("\nFAIL:")
        for failure in failures[:10]:
            print(f"  - {failure}")
        return 1
    print("\n10/10 mission checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
