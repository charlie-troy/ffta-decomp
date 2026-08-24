"""Validate the packed height and tile-arrangement map codecs.

    python tools/validate_maps.py baserom.gba
"""
import argparse
import hashlib
import os
import tempfile

from ffta_lz import block_length, pack
from map_data import (COUNT, _arrangement_cells, _height_cells,
                      cmd_apply_arrangement, cmd_apply_terrain,
                      cmd_arrangement, cmd_terrain, resolve_block)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    args = parser.parse_args(argv)
    rom = open(args.rom, "rb").read()
    failures = []

    arrangements = []
    storage = {}
    widths = {}
    aligned = True
    valid_layers = True
    for map_id in range(COUNT):
        meta = resolve_block(rom, map_id, 0x04)
        parsed, cells = _arrangement_cells(meta)
        arrangements.append((meta, parsed, cells))
        key = (meta["storage"], len(meta["chain"]) > 1)
        storage[key] = storage.get(key, 0) + 1
        width = parsed["value_width"]
        widths[width] = widths.get(width, 0) + 1
        aligned &= all(cell["address"] % 4 == 0 for cell in cells.values())
        valid_layers &= all(cell["layer"] in (0, 1) for cell in cells.values())
    expected_storage = {("wrapped-lz77", False): 113, ("raw", False): 40,
                        ("wrapped-lz77", True): 9}
    ok = storage == expected_storage and widths == {2: 121, 1: 41}
    print(f"1. arrangement variants: {'OK' if ok else 'FAIL'} "
          f"({storage}; widths {widths})")
    if not ok:
        failures.append("arrangement variants")

    placements = sum(len(cells) for _, _, cells in arrangements)
    ok = placements == 119749 and aligned and valid_layers
    print(f"2. arrangement coordinates: {'OK' if ok else 'FAIL'} "
          f"({placements} placements; 4-byte aligned; layers 0/1)")
    if not ok:
        failures.append("arrangement coordinates")

    meta0, parsed0, cells0 = arrangements[0]
    layer_counts = {layer: sum(c["layer"] == layer for c in cells0.values())
                    for layer in (0, 1)}
    ok = (len(parsed0["records"]) == 107 and len(cells0) == 770 and
          parsed0["tile_format_offset"] == 0x750 and
          layer_counts == {0: 157, 1: 613})
    print(f"3. map 0 arrangement anchor: {'OK' if ok else 'FAIL'} "
          f"(107 runs, 770 placements, layers {layer_counts})")
    if not ok:
        failures.append("map 0 arrangement anchor")

    terrain = []
    redirected = 0
    for map_id in range(COUNT):
        meta = resolve_block(rom, map_id, 0x10)
        parsed, cells = _height_cells(meta)
        terrain.append((meta, parsed, cells))
        redirected += len(meta["chain"]) > 1
    map0_cells = terrain[0][2]
    xs = [cell["x"] for cell in map0_cells.values()]
    ys = [cell["y"] for cell in map0_cells.values()]
    ok = (redirected == 9 and len(map0_cells) == 196 and
          (min(xs), max(xs), min(ys), max(ys)) == (0, 13, 0, 13))
    print(f"4. packed terrain: {'OK' if ok else 'FAIL'} "
          f"(all {COUNT} maps; map 0 is 14x14/196 cells; {redirected} redirects)")
    if not ok:
        failures.append("packed terrain")

    # Known edits prove both codecs can fit an actual retail allocation.
    arrangement_raw = bytearray(meta0["raw"])
    arrangement_raw[cells0[(0, 0)]["data_offset"]:
                    cells0[(0, 0)]["data_offset"] + 2] = (2).to_bytes(2, "little")
    arrangement_fit = len(pack(arrangement_raw)) <= block_length(rom, meta0["offset"])
    height_meta, _, height_cells = terrain[0]
    height_raw = bytearray(height_meta["raw"])
    height_raw[height_cells[(0, 1)]["data_offset"] + 1] = 0
    height_fit = len(pack(height_raw)) <= block_length(rom, height_meta["offset"])
    ok = arrangement_fit and height_fit
    print(f"5. guarded edit anchors: {'OK' if ok else 'FAIL'} "
          f"(arrangement {arrangement_fit}; terrain {height_fit})")
    if not ok:
        failures.append("guarded edit anchors")

    with tempfile.TemporaryDirectory(prefix="ffta-map-validation-") as temp:
        arrangement_csv = os.path.join(temp, "arrangement.csv")
        terrain_csv = os.path.join(temp, "terrain.csv")
        arrangement_rom = os.path.join(temp, "arrangement.gba")
        terrain_rom = os.path.join(temp, "terrain.gba")
        cmd_arrangement(args.rom, arrangement_csv)
        cmd_apply_arrangement(args.rom, arrangement_csv, arrangement_rom)
        cmd_terrain(args.rom, terrain_csv)
        cmd_apply_terrain(args.rom, terrain_csv, terrain_rom)
        digest = hashlib.sha256(rom).digest()
        ok = (hashlib.sha256(open(arrangement_rom, "rb").read()).digest() == digest and
              hashlib.sha256(open(terrain_rom, "rb").read()).digest() == digest)
    print(f"6. unedited CSV round-trips: {'OK' if ok else 'FAIL'} (byte-identical)")
    if not ok:
        failures.append("unedited CSV round-trips")

    print(f"\n{6 - len(failures)}/6 map checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
