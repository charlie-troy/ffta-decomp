"""Dump and apply the FFTA mission table as CSV, with no compiler needed.

Table at 0x0855AE4C, 0x46 bytes an entry, 512 entries of which 418 carry
content. Undocumented before this: found by scanning the ROM for accessors of
the same shape as the job and item ones, which turned up sub_080CE4DC indexing
this table with 65 properties.

Entry 0 is blank, and the little-endian halfword at +0x00/+0x01 holds the
entry's own index on all 512 entries, which is what fixes the count.

A second table at 0x08563A7C holds 255 twelve-byte records whose +0x02 is a
mission id. Dump it with the `index` command.

    python tools/mission_table.py dump  baserom.gba missions.csv
    python tools/mission_table.py apply baserom.gba missions.csv out.gba
    python tools/mission_table.py index baserom.gba mission-index.csv
    python tools/mission_table.py rewards baserom.gba mission-rewards.csv
    python tools/mission_table.py clan-rewards baserom.gba clan-rewards.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_names import Names

BASE = 0x0855AE4C - 0x08000000
STRIDE = 0x46
COUNT = 512

IDX_BASE = 0x08563A7C - 0x08000000
IDX_STRIDE = 12
IDX_COUNT = 255
IDX_END = 0x08564670 - 0x08000000  # next table; referenced directly by code

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
}
# +0x45 equals the low mission id only for entries 0-122 (except 27) and is
# zero for most later entries. It is not a general id echo, so it stays b45.
# +0x3e is a second 200-unit field: accessor prop 54 does the same *0xC8
# multiply. Its meaning is not pinned yet, so it stays positional.
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


def col(o):
    return NAMED.get(o, f"b{o:02x}")


def cmd_dump(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        names = Names(rom)
        w.writerow(["id", "name"] + [col(o) for o in range(STRIDE)])
        for i in range(COUNT):
            b = BASE + i * STRIDE
            w.writerow([i, names.mission(i)] + list(rom[b:b + STRIDE]))
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
            for o in range(STRIDE):
                name = col(o)
                if name not in row or row[name] == "":
                    continue
                new = int(row[name], 0)
                if not 0 <= new < 256:
                    print(f"  id {i} {name}: {new} does not fit a byte, skipped")
                    continue
                p = BASE + i * STRIDE + o
                if rom[p] != new:
                    print(f"  id {i:>3} {name} (+{o:#04x}): {rom[p]} -> {new}")
                    rom[p] = new
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


def cmd_index(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        names = Names(rom)
        w.writerow(["record", "b00", "b01", "mission_id", "mission_name",
                    "w04", "w06", "b08", "b09", "b0a", "b0b"])
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
    if len(argv) == 3 and argv[0] == "index":
        return cmd_index(argv[1], argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
