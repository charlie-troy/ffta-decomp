"""Read and edit FFTA map data.

The map table holds 162 entries of 0x58 bytes at 0x08569104. Each entry stores
pointers as diffs against the table base, and the blocks they point at are
compressed: four marker bytes 11 FF FF FF, then a standard GBA LZ77 header,
then BIOS LZ77 data. The leading 0x11 is the BIOS call number the game uses to
unpack it.

    python tools/map_data.py table   baserom.gba maps.csv
    python tools/map_data.py terrain baserom.gba terrain.csv
    python tools/map_data.py apply-terrain baserom.gba terrain.csv out.gba
"""
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_lz import decompress, parse_header, block_length, pack

TBL = 0x08569104
STRIDE = 0x58
COUNT = 162
B = TBL - 0x08000000
PTRS = [("graphics", 0x00), ("arrangement", 0x04), ("unknown_08", 0x08),
        ("palette", 0x0C), ("height", 0x10),
        ("anim_0", 0x14), ("anim_1", 0x18), ("anim_2", 0x1C)]
# 0 walkable, 1 impassable, 2 water, anything else not selectable.
PERM = {0: "walkable", 1: "impassable", 2: "water"}


def u32(rom, i, k):
    o = B + i * STRIDE + k
    return int.from_bytes(rom[o:o + 4], "little")


def cmd_table(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["map"] + [n for n, _ in PTRS] + ["mode_54", "mode_55"])
        for i in range(COUNT):
            row = [i]
            for _, k in PTRS:
                v = u32(rom, i, k)
                row.append(f"{TBL + v:#010x}" if v else "")
            row += [rom[B + i * STRIDE + 0x54], rom[B + i * STRIDE + 0x55]]
            w.writerow(row)
    print(f"wrote {out_path}: {COUNT} maps")
    return 0


def cmd_terrain(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    n = skipped = 0
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["map", "tile", "height", "permission", "meaning"])
        for i in range(COUNT):
            off = B + u32(rom, i, 0x10)
            if parse_header(rom, off) is None:
                skipped += 1
                continue
            data = decompress(rom, off)
            for t in range(len(data) // 2):
                h, p = data[2 * t], data[2 * t + 1]
                w.writerow([i, t, h, p, PERM.get(p, "not selectable")])
            n += 1
    print(f"wrote {out_path}: {n} maps")
    if skipped:
        print(f"  {skipped} maps skipped: their height block does not carry "
              f"the 11 FF FF FF header")
    return 0


def cmd_apply_terrain(rom_path, csv_path, out_path):
    rom = bytearray(open(rom_path, "rb").read())
    want = {}
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            want.setdefault(int(row["map"]), {})[int(row["tile"])] = (
                int(row["height"], 0), int(row["permission"], 0))

    changed = refused = 0
    for i, tiles in sorted(want.items()):
        off = B + u32(rom, i, 0x10)
        if parse_header(rom, off) is None:
            continue
        data = bytearray(decompress(rom, off))
        dirty = False
        for t, (h, p) in tiles.items():
            if 2 * t + 1 >= len(data):
                continue
            if data[2 * t] != h or data[2 * t + 1] != p:
                data[2 * t], data[2 * t + 1] = h & 0xFF, p & 0xFF
                dirty = True
        if not dirty:
            continue
        blob = pack(bytes(data))
        room = block_length(rom, off)
        if len(blob) > room:
            print(f"  map {i}: recompressed to {len(blob)} bytes but only "
                  f"{room} are available, refused")
            refused += 1
            continue
        rom[off:off + len(blob)] = blob
        # leave anything between the new end and the old end untouched
        print(f"  map {i}: rewritten, {len(blob)}/{room} bytes used")
        changed += 1
    open(out_path, "wb").write(rom)
    print()
    print(f"{changed} map(s) rewritten, {refused} refused, wrote {out_path}")
    return 0


def main(argv):
    if len(argv) == 3 and argv[0] == "table":
        return cmd_table(argv[1], argv[2])
    if len(argv) == 3 and argv[0] == "terrain":
        return cmd_terrain(argv[1], argv[2])
    if len(argv) == 4 and argv[0] == "apply-terrain":
        return cmd_apply_terrain(argv[1], argv[2], argv[3])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
