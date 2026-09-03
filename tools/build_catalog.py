"""Build a browsable visual catalog of FFTA's map assets.

    python tools/build_catalog.py catalog baserom.gba outputs/catalog
    python tools/build_catalog.py catalog baserom.gba outputs/catalog --maps 0-9
    python tools/build_catalog.py catalog baserom.gba outputs/catalog --embedded

Writes into the output directory: catalog.html (open it in a browser),
catalog.json (the data the page renders), thumbnails/, tiles/, palettes/,
and anim/. Everything is derived from the ROM, so the output directory must
stay out of version control; outputs/ is already gitignored for this reason.

With --embedded it also writes catalog-embedded.html, a single standalone
file with the PNGs inlined as data URLs, openable anywhere with no server
and no sibling files.

The catalog exists to make graphics workflows visually checkable: decoded
tile sheets, palettes, thumbnails, and animation frames can be compared
against real emulator screenshots instead of trusting hex dumps. It is a
read-only view over the same decoders tools/map_data.py uses, so anything
it shows is exactly what apply-graphics and apply-arrangement would write.

Two approximations are deliberate and are labeled in the page itself:

- Tile sheets and animation frames render with palette bank 0. Thumbnails
  use each placement's palette-bank bits (12-14), which resolve to the
  block's own banks.
- Thumbnails composite layer 0, then layer 1, in placement order. The real
  renderer's depth sorting is not reimplemented.
"""
import csv
import hashlib
import json
import os
import sys
import time

try:
    from PIL import Image
except ImportError:
    print("error: Pillow is required (pip install pillow)", file=sys.stderr)
    raise SystemExit(2)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from map_data import (COUNT, _arrangement_cells, _clipping_cells,
                      _height_cells, decode_animation, decode_graphics,
                      resolve_block)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def bgr555(value):
    r = value & 0x1F
    g = (value >> 5) & 0x1F
    b = (value >> 10) & 0x1F
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))


def load_palette_colors(rom, map_id):
    """Decode one map's LZ77 palette block into a flat list of RGB tuples."""
    raw = resolve_block(rom, map_id, 0x0C)["raw"]
    if len(raw) % 32:
        raise ValueError(f"map {map_id} palette is {len(raw)} bytes, "
                         "not whole 16-color banks")
    colors = []
    for i in range(0, len(raw), 2):
        colors.append(bgr555(int.from_bytes(raw[i:i + 2], "little")))
    return colors


def render_4bpp(raw, palette, transparent=True, columns=16):
    """Render GBA 4bpp tiles (32 bytes each) into an RGBA sheet.

    Each 32-byte tile is 8 rows of 4 bytes; byte b holds pixels 2b and
    2b+1 as its low and high nibble. (The 4-bytes-per-row stride of 8bpp
    tiles is a different format and silently drops half the pixels here.)
    """
    if len(raw) % 32:
        raise ValueError(f"tile data is {len(raw)} bytes, not whole tiles")
    if len(palette) < 16:
        raise ValueError("palette has fewer than 16 colors")
    tiles = len(raw) // 32
    rows = (tiles + columns - 1) // columns
    img = Image.new("RGBA", (columns * 8, rows * 8), (0, 0, 0, 0))
    px = img.load()
    for t in range(tiles):
        base = t * 32
        tx = (t % columns) * 8
        ty = (t // columns) * 8
        for y in range(8):
            row = base + y * 4
            for x in range(8):
                idx = (raw[row + x // 2] >> ((x % 2) * 4)) & 0xF
                r, g, b = palette[idx]
                px[tx + x, ty + y] = (r, g, b, 0 if idx == 0 and transparent
                                      else 255)
    return img


def render_thumbnail(rom, map_id, palette):
    """Composite one map's arrangement into a 512x1024 RGBA image.

    Each placement is a 16x16 block of four graphics tiles (2x2). The
    placement's u16 entry at the metatile-index region selects the first
    tile (bits 0-9), h/v flip (bits 10/11), and palette bank (bits 12-14);
    bit 15 is set on many entries and not yet named. Layer 0 draws before
    layer 1, in placement order.
    """
    meta = resolve_block(rom, map_id, 0x04)
    block = meta["raw"]
    parsed, cells = _arrangement_cells(meta)
    defs_at = parsed["tile_format_offset"]
    entries = [int.from_bytes(block[i:i + 2], "little")
               for i in range(defs_at, len(block) - len(block) % 2, 2)]
    gfx = decode_graphics(rom, map_id)["raw"]
    tile_count = len(gfx) // 32
    img = Image.new("RGBA", (32 * 16, 64 * 16), (0, 0, 0, 0))
    for layer in (0, 1):
        for (record, slot), cell in sorted(cells.items()):
            if cell["layer"] != layer:
                continue
            entry = (entries[cell["tile_id"]]
                     if cell["tile_id"] < len(entries) else 0)
            base = entry & 0x3FF
            hflip = (entry >> 10) & 1
            vflip = (entry >> 11) & 1
            bank = (entry >> 12) & 0x7
            bank_colors = (palette[bank * 16:bank * 16 + 16]
                           if bank * 16 + 16 <= len(palette) else palette[:16])
            if base + 4 > tile_count:
                continue
            for k in range(4):
                tile = render_4bpp(gfx[(base + k) * 32:(base + k) * 32 + 32],
                                   bank_colors)
                if hflip:
                    tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
                if vflip:
                    tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
                img.alpha_composite(tile, (cell["x"] * 16 + (k % 2) * 8,
                                           cell["y"] * 16 + (k // 2) * 8))
    return img


def render_palette_png(colors):
    banks = len(colors) // 16
    cell = 12
    img = Image.new("RGBA", (16 * cell, banks * cell), (40, 40, 40, 255))
    px = img.load()
    for i, (r, g, b) in enumerate(colors):
        x = (i % 16) * cell
        y = (i // 16) * cell
        for dy in range(1, cell):
            for dx in range(1, cell):
                px[x + dx, y + dy] = (r, g, b, 255)
    return img


def parse_map_range(spec):
    maps = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            lo, hi = int(lo, 0), int(hi, 0)
            if not 0 <= lo <= hi < COUNT:
                raise ValueError(f"map range {part} outside 0-{COUNT - 1}")
            maps.update(range(lo, hi + 1))
        else:
            m = int(part, 0)
            if not 0 <= m < COUNT:
                raise ValueError(f"map {m} outside 0-{COUNT - 1}")
            maps.add(m)
    if not maps:
        raise ValueError("empty --maps selection")
    return sorted(maps)


def _embed_data_urls(catalog, out_dir):
    """Copy the catalog with every PNG reference replaced by a data URL."""
    import base64
    import copy

    cache = {}

    def data_url(rel):
        if rel not in cache:
            path = os.path.join(out_dir, rel.replace("/", os.sep))
            with open(path, "rb") as fh:
                cache[rel] = ("data:image/png;base64," +
                              base64.b64encode(fh.read()).decode("ascii"))
        return cache[rel]

    embedded = copy.deepcopy(catalog)
    for entry in embedded["maps"]:
        entry["thumbnail"] = data_url(entry["thumbnail"])
        entry["tiles_png"] = data_url(entry["tiles_png"])
        entry["palette_png"] = data_url(entry["palette_png"])
    for entry in embedded["graphics_streams"]:
        entry["file"] = data_url(entry["file"])
    for entry in embedded["palettes"]:
        entry["file"] = data_url(entry["file"])
    for entry in embedded["animations"]:
        for frame in entry["frames"]:
            frame["file"] = data_url(frame["file"])
    return embedded


def build_catalog(rom_path, out_dir, map_ids, embedded=False):
    rom = open(rom_path, "rb").read()
    rom_sha1 = hashlib.sha1(rom).hexdigest()
    os.makedirs(out_dir, exist_ok=True)
    thumbs = os.path.join(out_dir, "thumbnails")
    tiles_dir = os.path.join(out_dir, "tiles")
    palettes_dir = os.path.join(out_dir, "palettes")
    anim_dir = os.path.join(out_dir, "anim")
    for d in (thumbs, tiles_dir, palettes_dir, anim_dir):
        os.makedirs(d, exist_ok=True)

    gfx_by_source = {}
    pal_by_offset = {}
    anim_by_metadata = {}
    maps = []

    for map_id in map_ids:
        print(f"  map {map_id}")
        gfx = decode_graphics(rom, map_id)
        source_address = 0x08000000 + gfx["source_offset"]
        if source_address not in gfx_by_source:
            filename = f"tiles_{source_address:08x}.png"
            gfx_by_source[source_address] = {
                "file": filename, "tile_count": gfx["tile_count"],
                "decompressed_bytes": len(gfx["raw"]),
                "compressed_bytes": gfx["compressed_bytes"],
                "wrapper_type": gfx["wrapper_type"], "maps": []}
        entry = gfx_by_source[source_address]
        entry["maps"].append(map_id)

        pal = resolve_block(rom, map_id, 0x0C)
        pal_offset = pal["offset"]
        if pal_offset not in pal_by_offset:
            colors = load_palette_colors(rom, map_id)
            filename = f"palette_{0x08000000 + pal_offset:08x}.png"
            render_palette_png(colors).save(
                os.path.join(palettes_dir, filename))
            pal_by_offset[pal_offset] = {
                "file": filename, "bank_count": len(colors) // 16,
                "maps": [], "colors": colors}
        pal_entry = pal_by_offset[pal_offset]
        pal_entry["maps"].append(map_id)
        colors = pal_entry["colors"]

        anim = decode_animation(rom, map_id)
        anim_entry = None
        if anim is not None:
            metadata_address = 0x08000000 + anim["metadata_offset"]
            if metadata_address not in anim_by_metadata:
                frames = []
                for frame in anim["frames"]:
                    ffile = (f"animation_{metadata_address:08x}"
                             f"_frame_{frame['frame']:02d}.png")
                    render_4bpp(frame["raw"], colors[:16]).save(
                        os.path.join(anim_dir, ffile))
                    frames.append({"file": ffile,
                                   "duration": frame["duration"],
                                   "source_tile": frame["source_tile"]})
                anim_by_metadata[metadata_address] = {
                    "metadata_address": f"{metadata_address:#010x}",
                    "frame_count": anim["frame_count"],
                    "vram_destination": f"{anim['vram_destination']:#010x}",
                    "frames": frames, "maps": []}
            anim_entry = anim_by_metadata[metadata_address]
            anim_entry["maps"].append(map_id)

        tile_file = os.path.join(tiles_dir, entry["file"])
        if not os.path.exists(tile_file):
            render_4bpp(gfx["raw"], colors[:16]).save(tile_file)

        thumb_name = f"map_{map_id:03d}.png"
        render_thumbnail(rom, map_id, colors[:16]).save(
            os.path.join(thumbs, thumb_name))

        meta = resolve_block(rom, map_id, 0x04)
        clip = resolve_block(rom, map_id, 0x08)
        terrain = resolve_block(rom, map_id, 0x10)
        _, placement_cells = _arrangement_cells(meta)
        _, clip_cells = _clipping_cells(clip)
        _, terrain_cells = _height_cells(terrain)
        table_entry = 0x08569104 - 0x08000000 + map_id * 0x58
        maps.append({
            "id": map_id,
            "source_map": meta["source_map"],
            "block_storage": {"arrangement": meta["storage"],
                              "clipping": clip["storage"],
                              "palette": pal["storage"],
                              "terrain": terrain["storage"]},
            "render_modes": [rom[table_entry + 0x54], rom[table_entry + 0x55]],
            "shared_palette_index": rom[table_entry + 0x56],
            "tile_count": gfx["tile_count"],
            "wrapper_type": gfx["wrapper_type"],
            "graphics_source": f"{source_address:#010x}",
            "placements": len(placement_cells),
            "clipping_entries": len(clip_cells),
            "terrain_cells": len(terrain_cells),
            "thumbnail": f"thumbnails/{thumb_name}",
            "tiles_png": f"tiles/{entry['file']}",
            "palette_png": f"palettes/{pal_entry['file']}",
            "animation": (anim_entry["metadata_address"]
                          if anim_entry else None),
        })

    for entry in gfx_by_source.values():
        entry["maps"] = sorted(set(entry["maps"]))
    fixed_palettes = []
    for offset, entry in pal_by_offset.items():
        entry["address"] = f"{0x08000000 + offset:#010x}"
        entry["maps"] = sorted(set(entry["maps"]))
        entry["file"] = f"palettes/{entry['file']}"
        fixed_palettes.append(entry)
    for entry in anim_by_metadata.values():
        entry["maps"] = sorted(set(entry["maps"]))
        for frame in entry["frames"]:
            frame["file"] = f"anim/{frame['file']}"

    catalog = {
        "generated_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC",
                                       time.gmtime()),
        "rom_sha1": rom_sha1,
        "map_count": len(maps),
        "unique_graphics": len(gfx_by_source),
        "unique_palettes": len(fixed_palettes),
        "unique_animations": len(anim_by_metadata),
        "notes": [
            "Thumbnails composite each placement as a 16x16 block of four "
            "tiles. The placement's u16 metatile entry selects the first "
            "tile (bits 0-9), h/v flip (bits 10-11), and palette bank "
            "(bits 12-14); bit 15 is set on many entries and not yet named.",
            "Tile sheets and animation frames render with palette bank 0; "
            "thumbnails use each placement's bank bits.",
            "Thumbnails composite layer 0 then layer 1 in placement order; "
            "the renderer's depth sorting is not reimplemented.",
            "Index 0 renders transparent everywhere.",
            "All data is read with the same decoders tools/map_data.py uses "
            "for its guarded editing workflows.",
        ],
        "maps": maps,
        "graphics_streams": [
            {"source_address": f"{src:#010x}",
             **{k: v for k, v in e.items() if k not in ("maps", "file")},
             "file": f"tiles/{e['file']}", "maps": e["maps"]}
            for src, e in sorted(gfx_by_source.items())],
        "palettes": sorted(fixed_palettes, key=lambda e: e["address"]),
        "animations": [anim_by_metadata[k]
                       for k in sorted(anim_by_metadata)],
    }
    json_path = os.path.join(out_dir, "catalog.json")
    with open(json_path, "w", newline="") as fh:
        json.dump(catalog, fh, indent=1)

    html_src = os.path.join(HERE, "catalog_template.html")
    with open(html_src, encoding="utf-8") as fh:
        html = fh.read()
    with open(os.path.join(out_dir, "catalog.html"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    if embedded:
        payload = ("window.CATALOG = " +
                   json.dumps(_embed_data_urls(catalog, out_dir),
                              separators=(",", ":")) + ";")
        marker = "<script>\n\"use strict\";"
        if marker not in html:
            raise ValueError("catalog template is missing the script marker")
        with open(os.path.join(out_dir, "catalog-embedded.html"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(html.replace(marker, "<script>\n" + payload +
                                  "\n\"use strict\";", 1))
        print(f"wrote {os.path.join(out_dir, 'catalog-embedded.html')} "
              f"(standalone, PNGs inlined)")

    print(f"wrote {json_path}: {len(maps)} maps, "
          f"{len(gfx_by_source)} unique graphics streams, "
          f"{len(fixed_palettes)} palettes, "
          f"{len(anim_by_metadata)} unique animations")
    print(f"open {os.path.join(out_dir, 'catalog.html')} in a browser")
    return 0


def main(argv):
    try:
        if not argv or argv[0] != "catalog":
            print(__doc__)
            return 2
        if len(argv) < 3:
            print(__doc__)
            return 2
        rom_path, out_dir = argv[1], argv[2]
        embedded = False
        maps_spec = None
        rest = argv[3:]
        i = 0
        while i < len(rest):
            if rest[i] == "--embedded":
                embedded = True
                i += 1
            elif rest[i] == "--maps" and i + 1 < len(rest):
                maps_spec = rest[i + 1]
                i += 2
            else:
                raise ValueError(f"unknown argument {rest[i]!r}")
        map_ids = parse_map_range(maps_spec) if maps_spec else list(range(COUNT))
        return build_catalog(rom_path, out_dir, map_ids, embedded)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
