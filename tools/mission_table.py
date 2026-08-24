"""Dump and apply the FFTA mission table as CSV, with no compiler needed.

Table at 0x0855AE4C, 0x46 bytes an entry, 512 entries of which 418 carry
content. Undocumented before this: found by scanning the ROM for accessors of
the same shape as the job and item ones, which turned up sub_080CE4DC indexing
this table with 65 properties.

Entry 0 is blank, and the little-endian halfword at +0x00/+0x01 holds the
entry's own index on all 512 entries, which is what fixes the count.

A second table at 0x08563A70 holds 256 twelve-byte records whose +0x02 is a
mission id. Record 0 is an all-zero sentinel. Dump it with the `index` command.

    python tools/mission_table.py dump  baserom.gba missions.csv
    python tools/mission_table.py apply baserom.gba missions.csv out.gba
    python tools/mission_table.py index baserom.gba mission-index.csv
    python tools/mission_table.py rewards baserom.gba mission-rewards.csv
    python tools/mission_table.py clan-rewards baserom.gba clan-rewards.csv
    python tools/mission_table.py job-rules baserom.gba jobs.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_names import Names

BASE = 0x0855AE4C - 0x08000000
STRIDE = 0x46
COUNT = 512

IDX_BASE = 0x08563A70 - 0x08000000
IDX_STRIDE = 12
IDX_COUNT = 256
IDX_END = 0x08564670 - 0x08000000  # next table; referenced directly by code

# sub_080C93F0(job_id) returns byte 1 of each two-byte record here. The value
# normalizes duplicate job ids (for example each race's White Mage) to one
# canonical job code used by mission requirements.
JOB_KIND_BASE = 0x085231F4 - 0x08000000
JOB_KIND_STRIDE = 2
JOB_COUNT = 116

assert IDX_BASE + IDX_COUNT * IDX_STRIDE == IDX_END

# Offsets the accessor reaches with a plain load, confirmed by running it over
# every entry. Names are given only where the code showed what the field does;
# everything else keeps a positional name so the CSV still round-trips.
NAMED = {
    0x00: "mission_id_lo",          # +0x00/+0x01 little-endian entry index
    0x01: "mission_id_hi",
    0x2A: "clan_points",            # points toward the next clan level
    0x2B: "combat_points",          # eight clan-skill progress rewards
    0x2C: "magic_points",
    0x2D: "appraise_points",
    0x2E: "gather_points",
    0x2F: "smithing_points",
    0x30: "craft_points",
    0x31: "negotiate_points",
    0x32: "track_points",
    0x33: "gil_units_200",          # accessor prop 30 multiplies by 200
    0x34: "ap_units_10",            # displayed reward multiplies by 10
    0x35: "item_reward_id",         # accessor prop 29
    0x36: "require_item1_minus_375", # accessor prop 42 adds 375 (0 = none)
    0x37: "require_item2_minus_375", # accessor prop 44 adds 375 (0 = none)
    0x3D: "blocked_dispatch_item_minus_375", # prop 53; unused in retail
    0x3E: "fee_units_200",          # accessor prop 54; adjusted by pub/turf
}
# +0x45 equals the low mission id only for entries 0-122 (except 27) and is
# zero for most later entries. It is not a general id echo, so it stays b45.
# +0x39/+0x3a pack accessor property 0x30, the required dispatch job. It is
# exposed as a computed CSV field because neither raw byte can be named alone.
# +0x43/+0x44 is the dispatch threshold (16-bit, accessor prop 59):
# sub_080CF310 scores a dispatched unit against it and returns a 1-5 rating.
# It stays positional because the CSV is one byte per column.
# +0x12, +0x16, +0x1a, +0x1e, +0x22 and +0x2a are handed out as addresses by
# properties 19-24 and 32, so each is the start of a four-byte slot the caller
# reads itself rather than a value the accessor returns.
SLOTS = (0x12, 0x16, 0x1A, 0x1E, 0x22, 0x2A)

CLAN_REWARDS = (
    (0x2A, "clan_points"),
    (0x2B, "combat_points"),
    (0x2C, "magic_points"),
    (0x2D, "appraise_points"),
    (0x2E, "gather_points"),
    (0x2F, "smithing_points"),
    (0x30, "craft_points"),
    (0x31, "negotiate_points"),
    (0x32, "track_points"),
)

MISSION_ICON_GROUPS = {
    0: "Non-Battle",
    1: "Regular",
    2: "Free-Area",
    3: "Special",
}


def col(o):
    return NAMED.get(o, f"b{o:02x}")


def mission_behavior_get(data, entry):
    """Decode accessor property 1 from +0x02 bits 0..2."""
    return data[entry + 0x02] & 0x07


def mission_behavior_set(data, entry, value):
    """Set property 1 while preserving +0x02 bits 3..7."""
    if not 0 <= value <= 7:
        raise ValueError("mission behavior code must fit 3 bits")
    data[entry + 0x02] = (data[entry + 0x02] & 0xF8) | value


def mission_icon_group_get(data, entry):
    """Decode accessor property 2 from +0x02 bits 3..5."""
    return (data[entry + 0x02] >> 3) & 0x07


def mission_icon_group_set(data, entry, value):
    """Set property 2 while preserving +0x02 bits 0..2 and 6..7."""
    if not 0 <= value <= 7:
        raise ValueError("mission icon group code must fit 3 bits")
    data[entry + 0x02] = (data[entry + 0x02] & 0xC7) | (value << 3)


def mission_type_name(behavior, icon_group):
    """Public mission type selected by the UI icon path."""
    if behavior == 1:
        return "Encounter"
    return MISSION_ICON_GROUPS.get(icon_group, "")


def required_job_get(data, entry):
    """Decode accessor property 0x30 from packed mission bytes."""
    return (data[entry + 0x39] >> 3) | ((data[entry + 0x3A] & 0x01) << 5)


def required_job_set(data, entry, value):
    """Set property 0x30 while preserving unrelated bits in both bytes."""
    if not 0 <= value <= 0x3F:
        raise ValueError("required job code must fit 6 bits")
    data[entry + 0x39] = (data[entry + 0x39] & 0x07) | ((value & 0x1F) << 3)
    data[entry + 0x3A] = (data[entry + 0x3A] & 0xFE) | ((value >> 5) & 0x01)


def blocked_job_get(data, entry):
    """Decode the dispatch-rating job exclusion from +0x3c bits 2..7."""
    return data[entry + 0x3C] >> 2


def blocked_job_set(data, entry, value):
    """Set the dispatch job exclusion while preserving +0x3c bits 0..1."""
    if not 0 <= value <= 0x3F:
        raise ValueError("blocked job code must fit 6 bits")
    data[entry + 0x3C] = (data[entry + 0x3C] & 0x03) | (value << 2)


def blocked_item_get(data, entry):
    """Decode the dormant dispatch-item exclusion as a public item id."""
    value = data[entry + 0x3D]
    return value + 375 if value else 0


def blocked_item_set(data, entry, value):
    """Set the dormant exclusion (0 or item id 376..630)."""
    if value == 0:
        data[entry + 0x3D] = 0
    elif 376 <= value <= 630:
        data[entry + 0x3D] = value - 375
    else:
        raise ValueError("blocked dispatch item must be 0 or item id 376..630")


def job_code_names(rom, names):
    """Return canonical display names keyed by normalized job code."""
    out = {0: ""}
    for job in range(JOB_COUNT):
        code = rom[JOB_KIND_BASE + job * JOB_KIND_STRIDE + 1]
        name = names.job(job)
        if code and name and code not in out:
            out[code] = name
    return out


def cmd_dump(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        names = Names(rom)
        w.writerow(["id", "name"] + [col(o) for o in range(STRIDE)] +
                   ["mission_behavior_code", "mission_icon_group_code",
                    "mission_type", "required_job_code", "required_job",
                    "blocked_dispatch_job_code", "blocked_dispatch_job",
                    "blocked_dispatch_item_id", "blocked_dispatch_item"])
        job_names = job_code_names(rom, names)
        for i in range(COUNT):
            b = BASE + i * STRIDE
            behavior = mission_behavior_get(rom, b)
            icon_group = mission_icon_group_get(rom, b)
            required_job = required_job_get(rom, b)
            blocked_job = blocked_job_get(rom, b)
            blocked_item = blocked_item_get(rom, b)
            w.writerow([i, names.mission(i)] + list(rom[b:b + STRIDE]) +
                       [behavior, icon_group,
                        mission_type_name(behavior, icon_group), required_job,
                        job_names.get(required_job, ""),
                        blocked_job, job_names.get(blocked_job, ""),
                        blocked_item, names.item_by_id(blocked_item)])
    print(f"wrote {out_path}: {COUNT} entries, {STRIDE} bytes each")
    return 0


def cmd_apply(rom_path, csv_path, out_path):
    rom = bytearray(open(rom_path, "rb").read())
    changes = 0
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            i = int(row["id"])
            if not 0 <= i < COUNT:
                print(f"  skipping out-of-range id {i}")
                continue
            p = BASE + i * STRIDE
            original_behavior = mission_behavior_get(rom, p)
            original_icon_group = mission_icon_group_get(rom, p)
            original_required_job = required_job_get(rom, p)
            original_blocked_job = blocked_job_get(rom, p)
            original_blocked_item = blocked_item_get(rom, p)
            for o in range(STRIDE):
                name = col(o)
                if name not in row or row[name] == "":
                    continue
                new = int(row[name], 0)
                if not 0 <= new < 256:
                    print(f"  id {i} {name}: {new} does not fit a byte, skipped")
                    continue
                field = p + o
                if rom[field] != new:
                    print(f"  id {i:>3} {name} (+{o:#04x}): "
                          f"{rom[field]} -> {new}")
                    rom[field] = new
                    changes += 1
            requested = row.get("mission_behavior_code", "")
            if requested != "":
                requested = int(requested, 0)
                if not 0 <= requested <= 7:
                    print(f"  id {i} mission_behavior_code: {requested} does "
                          "not fit 3 bits, skipped")
                elif requested != original_behavior:
                    before = mission_behavior_get(rom, p)
                    mission_behavior_set(rom, p, requested)
                    print(f"  id {i:>3} mission_behavior_code: "
                          f"{before} -> {requested}")
                    changes += 1
            requested = row.get("mission_icon_group_code", "")
            if requested != "":
                requested = int(requested, 0)
                if not 0 <= requested <= 7:
                    print(f"  id {i} mission_icon_group_code: {requested} "
                          "does not fit 3 bits, skipped")
                elif requested != original_icon_group:
                    before = mission_icon_group_get(rom, p)
                    mission_icon_group_set(rom, p, requested)
                    print(f"  id {i:>3} mission_icon_group_code: "
                          f"{before} -> {requested}")
                    changes += 1
            requested = row.get("required_job_code", "")
            if requested != "":
                requested = int(requested, 0)
                if not 0 <= requested <= 0x3F:
                    print(f"  id {i} required_job_code: {requested} does not "
                          "fit 6 bits, skipped")
                elif requested != original_required_job:
                    before = required_job_get(rom, p)
                    required_job_set(rom, p, requested)
                    print(f"  id {i:>3} required_job_code: "
                          f"{before} -> {requested}")
                    changes += 1
            requested = row.get("blocked_dispatch_job_code", "")
            if requested != "":
                requested = int(requested, 0)
                if not 0 <= requested <= 0x3F:
                    print(f"  id {i} blocked_dispatch_job_code: {requested} "
                          "does not fit 6 bits, skipped")
                elif requested != original_blocked_job:
                    before = blocked_job_get(rom, p)
                    blocked_job_set(rom, p, requested)
                    print(f"  id {i:>3} blocked_dispatch_job_code: "
                          f"{before} -> {requested}")
                    changes += 1
            requested = row.get("blocked_dispatch_item_id", "")
            if requested != "":
                requested = int(requested, 0)
                if requested != 0 and not 376 <= requested <= 630:
                    print(f"  id {i} blocked_dispatch_item_id: {requested} "
                          "must be 0 or 376..630, skipped")
                elif requested != original_blocked_item:
                    before = blocked_item_get(rom, p)
                    blocked_item_set(rom, p, requested)
                    print(f"  id {i:>3} blocked_dispatch_item_id: "
                          f"{before} -> {requested}")
                    changes += 1
    open(out_path, "wb").write(rom)
    print()
    print(f"{changes} field(s) changed, wrote {out_path}")
    return 0


def cmd_rewards(rom_path, out_path):
    """Computed gil/AP/item rewards, no emulator needed.

    The reward bytes are stored scaled: +0x33 is gil/200, +0x34 is AP/10 and
    +0x35 is an item id. Verified against Herb Picking (600 gil, 40 AP) and
    Over The Hill (28,600 gil, 80 AP).
    """
    rom = open(rom_path, "rb").read()
    names = Names(rom)
    rows = 0
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name", "gil", "ap", "item_reward_id",
                    "item_reward"])
        for i in range(COUNT):
            b = BASE + i * STRIDE
            gil = rom[b + 0x33] * 200
            ap = rom[b + 0x34] * 10
            item = rom[b + 0x35]
            if not (gil or ap or item):
                continue
            w.writerow([i, names.mission(i), gil, ap, item,
                        names.item_by_id(item)])
            rows += 1
    print(f"wrote {out_path}: {rows} missions with a reward")

    # Self-check the formula against the two published anchors so the claim
    # cannot silently rot.
    def reward(i):
        b = BASE + i * STRIDE
        return rom[b + 0x33] * 200, rom[b + 0x34] * 10
    ok = reward(3) == (600, 40) and reward(25) == (28600, 80)
    print(f"anchor check: Herb Picking {reward(3)}, Over The Hill {reward(25)}"
          f" -> {'OK' if ok else 'MISMATCH'}")
    return 0 if ok else 1


def cmd_clan_rewards(rom_path, out_path):
    """Dump the clan and clan-skill progress awarded by each mission."""
    rom = open(rom_path, "rb").read()
    names = Names(rom)
    rows = 0
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name"] + [name for _off, name in CLAN_REWARDS])
        for i in range(COUNT):
            b = BASE + i * STRIDE
            values = [rom[b + off] for off, _name in CLAN_REWARDS]
            if not any(values):
                continue
            w.writerow([i, names.mission(i)] + values)
            rows += 1
    print(f"wrote {out_path}: {rows} missions with clan progression rewards")
    return 0


def cmd_job_rules(rom_path, out_path):
    """Dump required and blocked job rules for dispatch missions."""
    rom = open(rom_path, "rb").read()
    names = Names(rom)
    job_names = job_code_names(rom, names)
    rows = 0
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name", "required_job_code", "required_job",
                    "blocked_dispatch_job_code", "blocked_dispatch_job"])
        for i in range(COUNT):
            b = BASE + i * STRIDE
            required = required_job_get(rom, b)
            blocked = blocked_job_get(rom, b)
            if not (required or blocked):
                continue
            w.writerow([i, names.mission(i), required,
                        job_names.get(required, ""), blocked,
                        job_names.get(blocked, "")])
            rows += 1
    print(f"wrote {out_path}: {rows} missions with a dispatch job rule")
    return 0


def cmd_index(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        names = Names(rom)
        w.writerow(["record", "map_symbol_id", "script_trigger_id",
                    "mission_id", "mission_name", "w04", "w06", "b08",
                    "b09", "b0a", "b0b"])
        for i in range(IDX_COUNT):
            o = IDX_BASE + i * IDX_STRIDE
            mid = int.from_bytes(rom[o + 2:o + 4], "little")
            w.writerow([i, rom[o], rom[o + 1], mid, names.mission(mid),
                        int.from_bytes(rom[o + 4:o + 6], "little"),
                        int.from_bytes(rom[o + 6:o + 8], "little"), rom[o + 8],
                        rom[o + 9], rom[o + 10], rom[o + 11]])
    print(f"wrote {out_path}: {IDX_COUNT} records")
    bad = []
    for i in range(IDX_COUNT):
        o = IDX_BASE + i * IDX_STRIDE
        mid = int.from_bytes(rom[o + 2:o + 4], "little")
        if mid >= COUNT:
            bad.append((i, mid))
    print(f"  mission ids in range: {IDX_COUNT - len(bad)}/{IDX_COUNT}")
    print(f"  ends at next table: {IDX_BASE + IDX_COUNT * IDX_STRIDE == IDX_END}")
    return 1 if bad else 0


def cmd_requires(rom_path, out_path):
    """What each mission requires you to hold.

    Properties 42 and 44 are item ids and 46/47 a count check; sub_080CEECC
    reads them and scans your inventory, refusing the mission when an item is
    absent. Needs the emulator, since neither property is a plain load.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from emulate import Gba
    rom = open(rom_path, "rb").read()
    gba = Gba(rom_path)
    names = Names(rom)
    acc = 0x080CE4DC
    rows = 0
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["mission", "mission_name", "item_1_id", "item_1",
                    "item_2_id", "item_2"])
        for i in range(COUNT):
            a = gba.call(acc, [i, 42])
            b = gba.call(acc, [i, 44])
            if not (a or b):
                continue
            w.writerow([i, names.mission(i), a, names.item_by_id(a),
                        b, names.item_by_id(b)])
            rows += 1
    print(f"wrote {out_path}: {rows} missions with a requirement")
    return 0


def main(argv):
    if len(argv) == 3 and argv[0] == "dump":
        return cmd_dump(argv[1], argv[2])
    if len(argv) == 4 and argv[0] == "apply":
        return cmd_apply(argv[1], argv[2], argv[3])
    if len(argv) == 3 and argv[0] == "requires":
        return cmd_requires(argv[1], argv[2])
    if len(argv) == 3 and argv[0] == "rewards":
        return cmd_rewards(argv[1], argv[2])
    if len(argv) == 3 and argv[0] == "clan-rewards":
        return cmd_clan_rewards(argv[1], argv[2])
    if len(argv) == 3 and argv[0] == "job-rules":
        return cmd_job_rules(argv[1], argv[2])
    if len(argv) == 3 and argv[0] == "index":
        return cmd_index(argv[1], argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
