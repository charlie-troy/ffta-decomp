"""Validate FFTA's terrain, arrangement, clipping, and graphics codecs.

    python tools/validate_maps.py baserom.gba
"""
import argparse
import csv
import hashlib
import os
import tempfile

from ffta_lz import block_length, map_lzss, pack
from map_data import (COUNT, _arrangement_cells, _height_cells,
                      _clipping_cells, cmd_apply_arrangement,
                      cmd_apply_clipping, cmd_apply_terrain, cmd_arrangement,
                      cmd_clipping, cmd_graphics, cmd_terrain, decode_graphics,
                      resolve_block)
from emulate import Gba


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

    clipping = []
    clipping_redirects = 0
    aligned = valid_layers = True
    for map_id in range(COUNT):
        meta = resolve_block(rom, map_id, 0x08)
        parsed, cells = _clipping_cells(meta)
        clipping.append((meta, parsed, cells))
        clipping_redirects += len(meta["chain"]) > 1
        aligned &= all(cell["address"] % 2 == 0 for cell in cells.values())
        valid_layers &= all(cell["layer"] in (0, 1) for cell in cells.values())
    clipping_cells = sum(len(cells) for _, _, cells in clipping)
    clip0_meta, clip0_parsed, clip0_cells = clipping[0]
    ok = (clipping_redirects == 6 and clipping_cells == 120448 and aligned and
          valid_layers and len(clip0_parsed["records"]) == 112 and
          len(clip0_cells) == 771)
    print(f"5. clipping tilemap: {'OK' if ok else 'FAIL'} "
          f"({clipping_cells} tiles; map 0 has 112 runs/771 tiles; "
          f"{clipping_redirects} redirects)")
    if not ok:
        failures.append("clipping tilemap")

    # Known edits prove both codecs can fit an actual retail allocation.
    arrangement_raw = bytearray(meta0["raw"])
    arrangement_raw[cells0[(0, 0)]["data_offset"]:
                    cells0[(0, 0)]["data_offset"] + 2] = (2).to_bytes(2, "little")
    arrangement_fit = len(pack(arrangement_raw)) <= block_length(rom, meta0["offset"])
    height_meta, _, height_cells = terrain[0]
    height_raw = bytearray(height_meta["raw"])
    height_raw[height_cells[(0, 1)]["data_offset"] + 1] = 0
    height_fit = len(pack(height_raw)) <= block_length(rom, height_meta["offset"])
    clipping_raw = bytearray(clip0_meta["raw"])
    clip_cell = clip0_cells[(0, 0)]
    clipping_raw[clip_cell["data_offset"]:clip_cell["data_offset"] + 2] = \
        (0x0161).to_bytes(2, "little")
    clipping_fit = (len(pack(clipping_raw)) <=
                    block_length(rom, clip0_meta["offset"]))
    ok = arrangement_fit and height_fit and clipping_fit
    print(f"6. guarded edit anchors: {'OK' if ok else 'FAIL'} "
          f"(arrangement {arrangement_fit}; terrain {height_fit}; "
          f"clipping {clipping_fit})")
    if not ok:
        failures.append("guarded edit anchors")

    with tempfile.TemporaryDirectory(prefix="ffta-map-validation-") as temp:
        arrangement_csv = os.path.join(temp, "arrangement.csv")
        terrain_csv = os.path.join(temp, "terrain.csv")
        clipping_csv = os.path.join(temp, "clipping.csv")
        arrangement_rom = os.path.join(temp, "arrangement.gba")
        terrain_rom = os.path.join(temp, "terrain.gba")
        clipping_rom = os.path.join(temp, "clipping.gba")
        clipping_edit_csv = os.path.join(temp, "clipping-edit.csv")
        clipping_edit_rom = os.path.join(temp, "clipping-edit.gba")
        cmd_arrangement(args.rom, arrangement_csv)
        cmd_apply_arrangement(args.rom, arrangement_csv, arrangement_rom)
        cmd_terrain(args.rom, terrain_csv)
        cmd_apply_terrain(args.rom, terrain_csv, terrain_rom)
        cmd_clipping(args.rom, clipping_csv)
        cmd_apply_clipping(args.rom, clipping_csv, clipping_rom)
        digest = hashlib.sha256(rom).digest()
        ok = (hashlib.sha256(open(arrangement_rom, "rb").read()).digest() == digest and
              hashlib.sha256(open(terrain_rom, "rb").read()).digest() == digest and
              hashlib.sha256(open(clipping_rom, "rb").read()).digest() == digest)

        # A minimal partial CSV exercises the real apply path, not just pack().
        with open(clipping_edit_csv, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["map", "source_map", "record", "slot",
                             "tile_descriptor"])
            writer.writerow([0, 0, 0, 0, "0x0161"])
        apply_ok = (cmd_apply_clipping(args.rom, clipping_edit_csv,
                                       clipping_edit_rom) == 0)
        edited = open(clipping_edit_rom, "rb").read()
        _, edited_cells = _clipping_cells(resolve_block(edited, 0, 0x08))
        edit_ok = (apply_ok and
                   edited_cells[(0, 0)]["tile_descriptor"] == 0x0161)
    print(f"7. unedited CSV round-trips: {'OK' if ok else 'FAIL'} (byte-identical)")
    if not ok:
        failures.append("unedited CSV round-trips")

    print(f"8. clipping edit round-trip: {'OK' if edit_ok else 'FAIL'} "
          f"(map 0 record 0 slot 0 -> 0x0161)")
    if not edit_ok:
        failures.append("clipping edit round-trip")

    graphics = [decode_graphics(rom, map_id) for map_id in range(COUNT)]
    unique_graphics = {meta["offset"] for meta in graphics}
    types = {kind: sum(meta["wrapper_type"] == kind for meta in graphics)
             for kind in (0x20, 0x22)}
    whole_tiles = all(len(meta["raw"]) % 32 == 0 for meta in graphics)
    ok = len(unique_graphics) == 50 and types == {0x20: 82, 0x22: 80} and whole_tiles
    print(f"9. graphics streams: {'OK' if ok else 'FAIL'} "
          f"(162 maps/50 unique; wrappers {types}; whole 4bpp tiles)")
    if not ok:
        failures.append("graphics streams")

    gba = Gba(args.rom)
    retail_matches = []
    unique_metas = {meta["offset"]: meta for meta in graphics}.values()
    for meta in unique_metas:
        destination = 0x02010000
        gba.reset_ram()
        gba.call(0x0800543C,
                 [destination, 0x08000000 + meta["source_offset"]],
                 timeout_insns=1000000)
        retail = bytes(gba.uc.mem_read(destination, len(meta["raw"])))
        retail_matches.append(retail == meta["raw"])
    malformed = [b"\x00\x00", b"\x00\x00\x00\x01\x03",
                 b"\x00\x00\x00\x03\x80\x00",
                 b"\x00\x00\x00\x01\x41\xaa\xbb"]
    rejected = 0
    for sample in malformed:
        try:
            map_lzss(sample)
        except ValueError:
            rejected += 1
    ok = all(retail_matches) and rejected == len(malformed)
    print(f"10. graphics decoder: {'OK' if ok else 'FAIL'} "
          f"({len(retail_matches)} retail streams byte-match; "
          f"malformed {rejected}/{len(malformed)} rejected)")
    if not ok:
        failures.append("graphics decoder")

    with tempfile.TemporaryDirectory(prefix="ffta-graphics-validation-") as temp:
        cmd_graphics(args.rom, temp)
        files = os.listdir(temp)
        raw_files = [name for name in files if name.endswith(".4bpp")]
        with open(os.path.join(temp, "index.csv"), newline="") as fh:
            index_rows = list(csv.DictReader(fh))
        ok = len(raw_files) == 50 and len(index_rows) == COUNT
    print(f"11. graphics export: {'OK' if ok else 'FAIL'} "
          f"({len(raw_files)} unique files; {len(index_rows)} index rows)")
    if not ok:
        failures.append("graphics export")

    print(f"\n{11 - len(failures)}/11 map checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
