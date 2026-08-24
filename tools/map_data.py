"""Read and safely edit FFTA map blocks.

    python tools/map_data.py table             baserom.gba maps.csv
    python tools/map_data.py terrain           baserom.gba terrain.csv
    python tools/map_data.py apply-terrain     baserom.gba terrain.csv out.gba
    python tools/map_data.py arrangement       baserom.gba arrangement.csv
    python tools/map_data.py apply-arrangement baserom.gba arrangement.csv out.gba
    python tools/map_data.py clipping          baserom.gba clipping.csv
    python tools/map_data.py apply-clipping    baserom.gba clipping.csv out.gba
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_lz import block_length, compress, lz77, pack

TBL = 0x08569104
STRIDE = 0x58
COUNT = 162
B = TBL - 0x08000000
PTRS = [("graphics", 0x00), ("arrangement", 0x04), ("unknown_08", 0x08),
        ("palette", 0x0C), ("height", 0x10),
        ("anim_0", 0x14), ("anim_1", 0x18), ("anim_2", 0x1C)]
PERM = {0: "walkable", 1: "impassable", 2: "water"}


def u32(rom, i, k):
    o = B + i * STRIDE + k
    return int.from_bytes(rom[o:o + 4], "little")


def _uint(data, off, size):
    return int.from_bytes(data[off:off + size], "little")


def resolve_block(rom, map_id, field):
    """Resolve a packed-map redirect and return decoded storage metadata."""
    chain = []
    source = map_id
    while True:
        if source in chain:
            raise ValueError(f"map redirect cycle: {chain + [source]}")
        if not 0 <= source < COUNT:
            raise ValueError(f"map {map_id} redirects outside table to {source}")
        chain.append(source)
        off = B + u32(rom, source, field)
        kind = rom[off]
        if kind in (0x01, 0x11):
            target = _uint(rom, off + 1, 3)
            if target != 0xFFFFFF:
                source = target
                continue
            if kind == 0x01:
                return {"map": map_id, "source_map": source, "offset": off,
                        "raw_offset": off + 4,
                        "raw": bytes(rom[off + 4:off + 4 + 0x10000]),
                        "storage": "raw", "chain": chain}
            size = _uint(rom, off + 5, 3)
            raw = lz77(rom, off + 8, size)
            if len(raw) != size:
                raise ValueError(f"map {source} block at {off:#x} is truncated")
            return {"map": map_id, "source_map": source, "offset": off,
                    "raw_offset": None, "raw": raw, "storage": "wrapped-lz77",
                    "chain": chain}
        if kind == 0x10:
            size = _uint(rom, off + 1, 3)
            raw = lz77(rom, off + 4, size)
            if len(raw) != size:
                raise ValueError(f"map {source} block at {off:#x} is truncated")
            return {"map": map_id, "source_map": source, "offset": off,
                    "raw_offset": None, "raw": raw, "storage": "lz77",
                    "chain": chain}
        raise ValueError(f"map {source} block at {off:#x} has type {kind:#x}")


def parse_arrangement(raw):
    """Decode sparse 16x8 metatile placement runs."""
    if len(raw) < 6:
        raise ValueError("arrangement is too short")
    tile_format_offset = _uint(raw, 0, 2)
    width = 2 if raw[3] & 0x40 else 1
    p = 4
    records = []
    while True:
        if p + 2 > tile_format_offset:
            raise ValueError("arrangement has no placement terminator")
        destination = _uint(raw, p, 2)
        if destination == 0:
            p += 2
            break
        if p + 3 > tile_format_offset:
            raise ValueError("truncated arrangement record")
        count = raw[p + 2]
        values = p + 3
        end = values + count * width
        if end > tile_format_offset:
            raise ValueError("arrangement record overlaps tile definitions")
        records.append((destination, count, values))
        p = end
    return {"tile_format_offset": tile_format_offset, "value_width": width,
            "record_end": p, "records": records}


def parse_halfword_runs(raw):
    """Decode sparse destination/byte-count records containing halfwords."""
    p = 0
    records = []
    while True:
        if p + 4 > len(raw):
            raise ValueError("height data has no terminator")
        destination = _uint(raw, p, 2)
        byte_count = _uint(raw, p + 2, 2)
        p += 4
        if destination == 0 and byte_count == 0:
            break
        if destination & 1 or byte_count & 1:
            raise ValueError("height run is not aligned to two-byte cells")
        if p + byte_count > len(raw):
            raise ValueError("truncated height record")
        records.append((destination, byte_count // 2, p))
        p += byte_count
    return {"record_end": p, "records": records}


def parse_height(raw):
    """Decode packed (height, permission) runs on the 16-column grid."""
    return parse_halfword_runs(raw)


def _arrangement_cells(meta):
    parsed = parse_arrangement(meta["raw"])
    cells = {}
    width = parsed["value_width"]
    for record, (destination, count, values) in enumerate(parsed["records"]):
        for slot in range(count):
            data_offset = values + slot * width
            address = destination + slot * 4
            cells[(record, slot)] = {
                "data_offset": data_offset, "address": address,
                "tile_id": _uint(meta["raw"], data_offset, width),
                "layer": address // 0x2000,
                "x": (address % 0x80) // 4,
                "y": (address // 0x80) % 0x40,
                "width": width,
            }
    return parsed, cells


def _height_cells(meta):
    parsed = parse_height(meta["raw"])
    cells = {}
    for record, (destination, count, values) in enumerate(parsed["records"]):
        for slot in range(count):
            data_offset = values + slot * 2
            tile = destination // 2 + slot
            cells[(record, slot)] = {
                "data_offset": data_offset, "tile": tile, "x": tile % 16,
                "y": tile // 16, "height": meta["raw"][data_offset],
                "permission": meta["raw"][data_offset + 1],
            }
    return parsed, cells


def _clipping_cells(meta):
    parsed = parse_halfword_runs(meta["raw"])
    cells = {}
    for record, (destination, count, values) in enumerate(parsed["records"]):
        for slot in range(count):
            data_offset = values + slot * 2
            address = destination + slot * 2
            cells[(record, slot)] = {
                "data_offset": data_offset, "address": address,
                "layer": address // 0x1000,
                "x": (address % 0x40) // 2,
                "y": (address // 0x40) % 0x40,
                "tile_descriptor": _uint(meta["raw"], data_offset, 2),
            }
    return parsed, cells


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
    rows = 0
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["map", "source_map", "record", "slot", "tile", "x", "y",
                    "height", "permission", "meaning"])
        for i in range(COUNT):
            meta = resolve_block(rom, i, 0x10)
            _, cells = _height_cells(meta)
            for (record, slot), cell in cells.items():
                permission = cell["permission"]
                w.writerow([i, meta["source_map"], record, slot, cell["tile"],
                            cell["x"], cell["y"], cell["height"], permission,
                            PERM.get(permission, "not selectable")])
                rows += 1
    print(f"wrote {out_path}: {rows} cells across {COUNT} logical maps")
    return 0


def cmd_arrangement(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    rows = 0
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["map", "source_map", "record", "slot", "address", "layer",
                    "x", "y", "tile_id", "tile_id_width"])
        for i in range(COUNT):
            meta = resolve_block(rom, i, 0x04)
            _, cells = _arrangement_cells(meta)
            for (record, slot), cell in cells.items():
                w.writerow([i, meta["source_map"], record, slot,
                            f"{cell['address']:#06x}", cell["layer"], cell["x"],
                            cell["y"], cell["tile_id"], cell["width"]])
                rows += 1
    print(f"wrote {out_path}: {rows} placements across {COUNT} logical maps")
    return 0


def cmd_clipping(rom_path, out_path):
    rom = open(rom_path, "rb").read()
    rows = 0
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["map", "source_map", "record", "slot", "address", "layer",
                    "x", "y", "tile_descriptor"])
        for i in range(COUNT):
            meta = resolve_block(rom, i, 0x08)
            _, cells = _clipping_cells(meta)
            for (record, slot), cell in cells.items():
                w.writerow([i, meta["source_map"], record, slot,
                            f"{cell['address']:#06x}", cell["layer"], cell["x"],
                            cell["y"], f"{cell['tile_descriptor']:#06x}"])
                rows += 1
    print(f"wrote {out_path}: {rows} clipping tiles across {COUNT} logical maps")
    return 0


def _write_changed_blocks(rom, changes, out_path):
    rewritten = refused = 0
    for off, change in sorted(changes.items()):
        meta = change["meta"]
        raw = bytearray(meta["raw"])
        for data_offset, value, width in change["writes"].values():
            raw[data_offset:data_offset + width] = value.to_bytes(width, "little")
        if meta["storage"] == "raw":
            base = meta["raw_offset"]
            for data_offset, value, width in change["writes"].values():
                rom[base + data_offset:base + data_offset + width] = \
                    value.to_bytes(width, "little")
            print(f"  source map {meta['source_map']}: raw block rewritten")
            rewritten += 1
            continue
        blob = (pack(bytes(raw)) if meta["storage"] == "wrapped-lz77" else
                bytes((0x10,)) + len(raw).to_bytes(3, "little") + compress(bytes(raw)))
        room = block_length(rom, off) if meta["storage"] == "wrapped-lz77" else None
        if room is None:
            print(f"  source map {meta['source_map']}: bare LZ77 allocation unknown, refused")
            refused += 1
            continue
        if len(blob) > room:
            print(f"  source map {meta['source_map']}: recompressed to {len(blob)} bytes "
                  f"but only {room} are available, refused")
            refused += 1
            continue
        rom[off:off + len(blob)] = blob
        print(f"  source map {meta['source_map']}: rewritten, {len(blob)}/{room} bytes used")
        rewritten += 1
    open(out_path, "wb").write(rom)
    print(f"{rewritten} block(s) rewritten, {refused} refused, wrote {out_path}")
    return 1 if refused else 0


def _collect_changes(rom, csv_path, field, cell_reader, value_reader):
    changes = {}
    cache = {}
    map_cache = {}
    with open(csv_path, newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"map", "source_map", "record", "slot"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("CSV uses the obsolete pre-packed-map schema; dump it again")
        for row in reader:
            map_id = int(row["map"], 0)
            if map_id not in map_cache:
                map_cache[map_id] = resolve_block(rom, map_id, field)
            meta = map_cache[map_id]
            if int(row["source_map"], 0) != meta["source_map"]:
                raise ValueError(f"map {map_id}: stale source_map in CSV")
            key = meta["offset"]
            if key not in cache:
                cache[key] = (meta, cell_reader(meta)[1])
            canonical, cells = cache[key]
            cell_key = (int(row["record"], 0), int(row["slot"], 0))
            if cell_key not in cells:
                raise ValueError(f"map {map_id}: record/slot {cell_key} does not exist")
            cell = cells[cell_key]
            value, current, width = value_reader(row, cell)
            if value == current:
                continue
            limit = (1 << (8 * width)) - 1
            if not 0 <= value <= limit:
                raise ValueError(f"map {map_id}: value {value} exceeds {width}-byte field")
            group = changes.setdefault(key, {"meta": canonical, "writes": {}})
            data_offset = cell["data_offset"]
            prior = group["writes"].get(data_offset)
            write = (data_offset, value, width)
            if prior is not None and prior != write:
                raise ValueError(f"conflicting edits to shared block at {key:#x}")
            group["writes"][data_offset] = write
    return changes


def cmd_apply_arrangement(rom_path, csv_path, out_path):
    rom = bytearray(open(rom_path, "rb").read())
    def requested(row, cell):
        return int(row["tile_id"], 0), cell["tile_id"], cell["width"]
    changes = _collect_changes(rom, csv_path, 0x04, _arrangement_cells, requested)
    return _write_changed_blocks(rom, changes, out_path)


def cmd_apply_terrain(rom_path, csv_path, out_path):
    rom = bytearray(open(rom_path, "rb").read())
    def requested(row, cell):
        height = int(row["height"], 0)
        permission = int(row["permission"], 0)
        if not 0 <= height <= 0xFF or not 0 <= permission <= 0xFF:
            raise ValueError("height and permission must fit in one byte")
        return (height | permission << 8,
                cell["height"] | cell["permission"] << 8, 2)
    changes = _collect_changes(rom, csv_path, 0x10, _height_cells, requested)
    return _write_changed_blocks(rom, changes, out_path)


def cmd_apply_clipping(rom_path, csv_path, out_path):
    rom = bytearray(open(rom_path, "rb").read())
    def requested(row, cell):
        return (int(row["tile_descriptor"], 0),
                cell["tile_descriptor"], 2)
    changes = _collect_changes(rom, csv_path, 0x08, _clipping_cells, requested)
    return _write_changed_blocks(rom, changes, out_path)


def main(argv):
    try:
        if len(argv) == 3 and argv[0] == "table":
            return cmd_table(argv[1], argv[2])
        if len(argv) == 3 and argv[0] == "terrain":
            return cmd_terrain(argv[1], argv[2])
        if len(argv) == 3 and argv[0] == "arrangement":
            return cmd_arrangement(argv[1], argv[2])
        if len(argv) == 3 and argv[0] == "clipping":
            return cmd_clipping(argv[1], argv[2])
        if len(argv) == 4 and argv[0] == "apply-terrain":
            return cmd_apply_terrain(argv[1], argv[2], argv[3])
        if len(argv) == 4 and argv[0] == "apply-arrangement":
            return cmd_apply_arrangement(argv[1], argv[2], argv[3])
        if len(argv) == 4 and argv[0] == "apply-clipping":
            return cmd_apply_clipping(argv[1], argv[2], argv[3])
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
