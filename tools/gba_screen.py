"""Read the GBA display state through the mGBA GDB stub.

Provides screen inspection (BG config, ASCII rendering of text layers,
glyph-based text extraction) used to navigate FFTA menus headlessly.

Run against a live stub:
    python tools/gba_screen.py inspect     # dump display/BG/map config
    python tools/gba_screen.py ascii       # coarse luminance ASCII art
    python tools/gba_screen.py text        # decode visible text-layer glyphs
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb

VRAM = 0x06000000
PAL = 0x05000000
IO = 0x04000000


def u16(b, off=0):
    return int.from_bytes(b[off:off + 2], "little")


def load(gdb, addr, n, chunk=0x200):
    out = bytearray()
    for off in range(0, n, chunk):
        d = gdb.read_mem(addr + off, min(chunk, n - off))
        if d is None or len(d) != min(chunk, n - off):
            raise RuntimeError(f"read failed at {addr + off:#x} len {n}")
        out += d
    return bytes(out)


def bg_config(gdb):
    disp = u16(load(gdb, IO, 2))
    mode = disp & 7
    forced_blank = bool(disp & 0x80)
    bgs = []
    for i in range(4):
        en = bool(disp & (0x100 << i))
        cnt = u16(load(gdb, IO + 8 + 2 * i, 2))
        bgs.append(dict(enabled=en, cnt=cnt, priority=cnt & 3,
                        char_base=((cnt >> 2) & 3),
                        colors=((cnt >> 5) & 1),
                        size=((cnt >> 6) & 3),
                        screen_base=((cnt >> 8) & 0x1F)))
    return mode, forced_blank, bgs, disp


def text_map_geometry(cnt):
    """Return (map_w_tiles, map_h_tiles) for a text BG."""
    s = (cnt >> 6) & 3
    return [(32, 32), (64, 32), (32, 64), (64, 64)][s]


def render_text_bg(gdb, bg):
    """Render a 16- or 256-color text BG into a 240x160 luminance bytearray."""
    cnt = bg["cnt"]
    map_base = VRAM + bg["screen_base"] * 0x800
    mw, mh = text_map_geometry(cnt)
    colors = (cnt >> 5) & 1
    cb = VRAM + bg["char_base"] * (0x8000 if colors else 0x4000)
    tile_bytes = 64 if colors else 32
    tile_shift = 6 if colors else 5
    img = bytearray(240 * 160)
    map_data = load(gdb, map_base, mw * mh * 2)
    for my in range(min(mh, 20)):
        for mx in range(min(mw, 30)):
            e = u16(map_data, (my * mw + mx) * 2)
            if colors:
                tile = e & 0x1FF
                pal = 0
            else:
                tile = e & 0x3FF
                pal = (e >> 12) & 0xF
            if tile == 0:
                continue
            flip_h = bool(e & (1 << 10))
            flip_v = bool(e & (1 << 11))
            tdata = load(gdb, cb + tile * tile_bytes, tile_bytes)
            for ty in range(8):
                for tx in range(8):
                    if colors:
                        c = tdata[ty * 8 + tx]
                        if c == 0:
                            continue
                        lum = c  # 256-color palettes: use index as brightness proxy
                    else:
                        nib = tdata[ty * 4 + tx // 2]
                        c = (nib >> ((tx & 1) * 4)) & 0xF
                        if c == 0:
                            continue
                        lum = 16 * pal + c
                    px = mx * 8 + (7 - tx if flip_h else tx)
                    py = my * 8 + (7 - ty if flip_v else ty)
                    if 0 <= px < 240 and 0 <= py < 160:
                        img[py * 240 + px] = min(255, lum * 16 if colors == 0 else lum)
    return img


def ascii_of(img, w=240, h=160, scale=4):
    """Coarse luminance ASCII, `scale` px per character."""
    rows = []
    for y in range(0, h, scale):
        line = []
        for x in range(0, w, scale):
            tot = 0
            n = 0
            for yy in range(y, min(y + scale, h)):
                for xx in range(x, min(x + scale, w)):
                    tot += img[yy * 240 + xx]
                    n += 1
            v = tot / n
            line.append(" .:-=+*#%@"[min(9, int(v / 25.6))])
        rows.append("".join(line))
    return rows


def cmd_inspect(gdb, args):
    mode, blank, bgs, disp = bg_config(gdb)
    print(f"DISPCNT={disp:#06x} mode={mode} forced_blank={blank}")
    for i, bg in enumerate(bgs):
        if bg["enabled"]:
            print(f" BG{i}: enabled prio={bg['priority']} "
                  f"charbase={bg['char_base']} colors={'256' if bg['colors'] else '16'}"
                  f" size={bg['size']} scrbase={bg['screen_base']} cnt={bg['cnt']:#06x}")
    # nonzero statistics per potential map base
    print("map bases (screen_base*0x800):")
    for sb in range(32):
        base = VRAM + sb * 0x800
        d = load(gdb, base, 0x800)
        nz = sum(1 for b in d if b)
        if nz > 8:
            print(f"  0x{sb * 0x800:05x}: {nz} nonzero/2048")
    # char bases nonzero
    for cbi in range(4):
        base = VRAM + cbi * 0x4000
        d = load(gdb, base, 0x4000)
        nz = sum(1 for b in d if b)
        print(f" charbase {cbi} (0x{cbi * 0x4000:05x}): {nz} nonzero/16384")


def cmd_ascii(gdb, args):
    mode, blank, bgs, disp = bg_config(gdb)
    if blank:
        print("FORCED BLANK")
        return
    if mode in (0, 1):
        text_bgs = [bg for i, bg in enumerate(bgs) if bg["enabled"] and
                    not (mode == 1 and i == 2)]
    else:
        text_bgs = [bg for i, bg in enumerate(bgs) if bg["enabled"]]
    layers = [(bg["priority"], render_text_bg(gdb, bg)) for bg in text_bgs]
    layers.sort()
    out = bytearray(240 * 160)
    for _, img in layers:
        for i in range(len(out)):
            if img[i]:
                out[i] = img[i]
    for row in ascii_of(out):
        print(row)


def tile_bitmap(gdb, base, tile, colors):
    """Return 8 strings of 8 chars for a tile's bitmap."""
    tb = 64 if colors else 32
    d = load(gdb, base + tile * tb, tb)
    rows = []
    for ty in range(8):
        line = []
        for tx in range(8):
            if colors:
                c = d[ty * 8 + tx]
            else:
                nib = d[ty * 4 + tx // 2]
                c = (nib >> ((tx & 1) * 4)) & 0xF
            line.append("#" if c else ".")
        rows.append("".join(line))
    return rows


def cmd_text(gdb, args):
    """Dump each text BG's tilemap grid and the distinct glyph bitmaps."""
    mode, blank, bgs, disp = bg_config(gdb)
    for i, bg in enumerate(bgs):
        if not bg["enabled"]:
            continue
        cnt = bg["cnt"]
        colors = (cnt >> 5) & 1
        mw, mh = text_map_geometry(cnt)
        map_base = VRAM + bg["screen_base"] * 0x800
        cb = VRAM + bg["char_base"] * (0x8000 if colors else 0x4000)
        md = load(gdb, map_base, mw * mh * 2)
        entries = [u16(md, k * 2) for k in range(mw * mh)]
        used = sorted({(e & 0x3FF) if not colors else (e & 0x1FF)
                       for e in entries if e})
        print(f"=== BG{i}: {mw}x{mh} map at {map_base:#x} charbase {cb:#x} "
              f"{"256" if colors else "16"}-color; {len(used)} distinct tiles ===")
        # Tile-id grid
        for row in range(mh):
            cells = []
            for col in range(mw):
                e = entries[row * mw + col]
                if not e:
                    cells.append("  .")
                else:
                    t = (e & 0x3FF) if not colors else (e & 0x1FF)
                    cells.append(f"{t:3x}")
            print(" ".join(cells))
        # Distinct glyph bitmaps (only meaningful when few tiles)
        if len(used) <= 64:
            for t in used:
                rows = tile_bitmap(gdb, cb, t, colors)
                print(f"-- tile {t:#x} --")
                for r in rows:
                    print(r)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["inspect", "ascii", "text"])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)
    gdb = Gdb(args.host, args.port, timeout=10)
    gdb.send("?")
    gdb.interrupt()
    if args.cmd == "inspect":
        cmd_inspect(gdb, args)
    elif args.cmd == "ascii":
        cmd_ascii(gdb, args)
    elif args.cmd == "text":
        cmd_text(gdb, args)
    gdb.close()


if __name__ == "__main__":
    main()
