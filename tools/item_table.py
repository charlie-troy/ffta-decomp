"""Dump and apply the FFTA item table as CSV, with no compiler needed.

Table at 0x0851D180, 0x20 bytes an entry, ids 0..375. Id 0 is an empty "none"
entry, so the game's ids run 1..375. Published documentation gives the base as
0x51D1A0 with 374 items, which is this table starting one entry later: their
item N is the game's item N+1. The accessor sub_080CA7A4 uses the base here,
so these ids are the ones code actually passes.

Field names follow the published layout except where running the ROM
disagreed; those are marked in COLUMNS.

    python tools/item_table.py dump  baserom.gba items.csv
    python tools/item_table.py apply baserom.gba items.csv out.gba
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_names import Names

BASE = 0x0851D180 - 0x08000000
STRIDE = 0x20
COUNT = 376          # ids 0..375; 376 onward is zero fill

# (name, offset, width). Property ids the accessor exposes are noted; all 19
# were confirmed as plain loads by execution over the whole table.
COLUMNS = [
    ("name_id",      0x00, 2),   # prop 0
    ("desc_id",      0x02, 2),   # prop 1
    ("buy_value",    0x04, 2),   # prop 2
    ("sell_value",   0x06, 2),   # not derived from buy_value; only 140 of 375
                                 # items have sell == buy/2
    ("item_type",    0x08, 1),   # prop 3; selects a 19-entry jump table
    ("element",      0x09, 1),   # prop 4
    ("range",        0x0A, 1),   # prop 5
    ("worn",         0x0B, 1),   # prop 6
    ("flags_0c",     0x0C, 1),   # prop 7; a bitfield, not a scalar -- the code
                                 # at 0x080cacf0 tests bit 1 of it
    ("unk_0d",       0x0D, 1),   # prop 8; 3 distinct values
    ("unk_0e",       0x0E, 1),   # prop 9; 62 distinct values
    ("attack",       0x10, 1),   # prop 10; the damage path uses it as weapon
                                 # power, and 0x0812e578 sorts two weapons by it
    ("defense",      0x11, 1),   # prop 11
    ("magic_power",  0x12, 1),   # prop 12
    ("resistance",   0x13, 1),   # prop 13
    ("speed",        0x14, 1),   # prop 14; signed -- 0x0812e368 halves it with
                                 # asrs under Slow and doubles it under Haste
    ("evade",        0x15, 1),   # prop 15
    ("move",         0x16, 1),   # prop 16
    ("jump",         0x17, 1),   # prop 17
    ("category",     0x18, 1),   # no property id; random-item category. 0 =
                                 # excluded from random generation (the 81
                                 # unique/quest items); 1-30 classify the rest
                                 # (sub_080CC788 filters on it being nonzero)
    ("effect_0",     0x1A, 1),
    ("effect_1",     0x1B, 1),
    ("effect_2",     0x1C, 1),
    ("ability",      0x1D, 1),   # prop 18
]

# Offsets that are zero in every real item: +0x0f, +0x19, +0x1e, +0x1f.
PADDING = (0x0F, 0x19, 0x1E, 0x1F)

FLAG_BITS = [(b, f"f_0c_bit{b}") for b in range(8)]


def read(rom, i, off, width):
    o = BASE + i * STRIDE + off
    return int.from_bytes(rom[o:o + width], "little")


def cmd_dump(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        cols = [c[0] for c in COLUMNS if c[0] != "flags_0c"]
        names = Names(rom)
        w.writerow(["id", "name"] + cols + [n for _, n in FLAG_BITS])
        for i in range(COUNT):
            vals = [read(rom, i, o, wd) for n, o, wd in COLUMNS
                    if n != "flags_0c"]
            f = read(rom, i, 0x0C, 1)
            w.writerow([i, names.item(i)] + vals +
                       [(f >> b) & 1 for b, _ in FLAG_BITS])
    print(f"wrote {out_path}: {COUNT} items, {len(COLUMNS)} fields")
    return 0


def cmd_apply(rom_path, csv_path, out_path):
    rom = bytearray(open(rom_path, "rb").read())
    byname = {n: (o, wd) for n, o, wd in COLUMNS}
    changes = 0
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            i = int(row["id"])
            if not 0 <= i < COUNT:
                print(f"  skipping out-of-range id {i}")
                continue
            for name, (off, wd) in byname.items():
                if name == "flags_0c" or name not in row or row[name] == "":
                    continue
                new = int(row[name], 0)
                if not 0 <= new < (1 << (8 * wd)):
                    print(f"  id {i} {name}: {new} does not fit, skipped")
                    continue
                o = BASE + i * STRIDE + off
                old = int.from_bytes(rom[o:o + wd], "little")
                if old != new:
                    print(f"  id {i:>3} {name} (+{off:#04x}): {old} -> {new}")
                    rom[o:o + wd] = new.to_bytes(wd, "little")
                    changes += 1
            f = old_f = rom[BASE + i * STRIDE + 0x0C]
            for b, col in FLAG_BITS:
                if col in row and row[col] != "":
                    if int(row[col], 0):
                        f |= 1 << b
                    else:
                        f &= ~(1 << b)
            if f != old_f:
                print(f"  id {i:>3} flags_0c: {old_f:#04x} -> {f:#04x}")
                rom[BASE + i * STRIDE + 0x0C] = f
                changes += 1
    open(out_path, "wb").write(rom)
    print()
    print(f"{changes} field(s) changed, wrote {out_path}")
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
