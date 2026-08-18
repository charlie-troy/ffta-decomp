"""Read and edit the ability table.

The AI's per-ability tuning lives in three bytes of each entry (condition,
behaviour, priority), and those are data, not code. Editing them changes AI
behaviour without recompiling anything, which makes this the cheapest way to
tune the game.

    python tools/ability_table.py dump  <rom.gba> out.csv
    python tools/ability_table.py apply <rom.gba> in.csv out.gba

`apply` rewrites only the bytes that differ and reports each change, so an
accidental edit is visible rather than silent.
"""
import csv
import sys

BASE = 0x0855187C - 0x08000000
STRIDE = 0x1C
COUNT = 347

# name -> (offset, width). Only fields whose meaning is established.
COLUMNS = [
    ("name_id",     0x00, 2),
    ("element",     0x02, 1),
    ("ap_over_10",  0x03, 1),
    ("mp_cost",     0x04, 1),
    ("weapon_req",  0x05, 1),
    ("range_h",     0x06, 1),
    ("range_v",     0x07, 1),
    ("targeting",   0x08, 1),
    ("aoe_h",       0x09, 1),
    ("aoe_v",       0x0A, 1),
    ("power",       0x0B, 1),
    ("flags",       0x10, 4),
    ("anim_id",     0x14, 2),
    ("desc_id",     0x16, 2),
    ("ai_condition", 0x18, 1),
    ("ai_behaviour", 0x19, 1),
    ("ai_priority",  0x1A, 1),
]


def read(rom, i, off, width):
    o = BASE + i * STRIDE + off
    return int.from_bytes(rom[o:o + width], "little")


def cmd_dump(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id"] + [c[0] for c in COLUMNS])
        for i in range(COUNT):
            w.writerow([i] + [read(rom, i, off, wd) for _, off, wd in COLUMNS])
    print(f"wrote {out_path}: {COUNT} abilities, {len(COLUMNS)} columns")
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
            for name, off, width in COLUMNS:
                if name not in row or row[name] == "":
                    continue
                new = int(row[name], 0)
                old = read(rom, i, off, width)
                if new == old:
                    continue
                limit = 1 << (width * 8)
                if not 0 <= new < limit:
                    print(f"  id {i} {name}: {new} does not fit in {width} byte(s), skipped")
                    continue
                o = BASE + i * STRIDE + off
                rom[o:o + width] = new.to_bytes(width, "little")
                print(f"  id {i:>3} {name}: {old} -> {new}")
                changes += 1
    open(out_path, "wb").write(rom)
    print(f"\n{changes} field(s) changed, wrote {out_path}")
    if changes:
        print("this ROM differs from the base on purpose; keep it separate from baserom.gba")
    return 0


def main(argv):
    if len(argv) == 3 and argv[0] == "dump":
        return cmd_dump(argv[1], argv[2])
    if len(argv) == 4 and argv[0] == "apply":
        return cmd_apply(argv[1], argv[2], argv[3])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
