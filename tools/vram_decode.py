"""Decode VRAM dumps produced by lua_dump_vram.lua into readable ASCII/luminance.

Usage:
    python tools/vram_decode.py ascii [outdir]
    python tools/vram_decode.py grid  [outdir]   # tile-id grid per BG
    python tools/vram_decode.py glyphs [outdir]  # distinct glyph bitmaps per BG
"""
import os
import sys

OUT = sys.argv[2] if len(sys.argv) > 2 else "outputs/vram"
W, H = 240, 160


def u16(b, off):
    return int.from_bytes(b[off:off + 2], "little")


def parse_header():
    bgs = {}
    info = {}
    with open(os.path.join(OUT, "header.txt")) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("disp="):
                info["disp"] = int(line.split("=")[1], 16)
            elif line.startswith("bg"):
                parts = line.split()
                idx = int(parts[0][2])
                d = bgs.get(idx, {})
                for tok in parts[1:]:
                    k, v = tok.split("=")
                    if k in ("cnt", "map_base", "tile_base"):
                        d[k] = int(v, 16)
                    else:
                        d[k] = int(v)
                bgs[idx] = d
    return info, bgs


def load_bg(idx, bg):
    mp = os.path.join(OUT, f"bg{idx}.map")
    tp = os.path.join(OUT, f"bg{idx}.tiles")
    if not (os.path.exists(mp) and os.path.exists(tp)):
        return None
    md = open(mp, "rb").read()
    td = open(tp, "rb").read()
    mw, mh = bg["mw"], bg["mh"]
    colors = bg["colors"]
    tb = bg["tb"]
    return md, td, mw, mh, colors, tb


def render_bg(idx, bg):
    d = load_bg(idx, bg)
    if not d:
        return None
    md, td, mw, mh, colors, tb = d
    img = bytearray(W * H)
    cb_tiles = td
    for my in range(mh):
        for mx in range(mw):
            e = u16(md, (my * mw + mx) * 2)
            if not e:
                continue
            tile = (e & 0x1FF) if colors else (e & 0x3FF)
            pal = (e >> 12) & 0xF
            flip_h = bool(e & (1 << 10))
            flip_v = bool(e & (1 << 11))
            tdata = cb_tiles[tile * tb:(tile + 1) * tb]
            for ty in range(8):
                for tx in range(8):
                    if colors:
                        c = tdata[ty * 8 + tx]
                    else:
                        nib = tdata[ty * 4 + tx // 2]
                        c = (nib >> ((tx & 1) * 4)) & 0xF
                    if c == 0:
                        continue
                    lum = min(255, c * 16)
                    px = mx * 8 + (7 - tx if flip_h else tx)
                    py = my * 8 + (7 - ty if flip_v else ty)
                    if 0 <= px < W and 0 <= py < H:
                        img[py * W + px] = max(img[py * W + px], lum)
    return img


def ascii_rows(img):
    rows = []
    for y in range(0, H, 2):
        line = []
        for x in range(0, W, 1):
            v = img[y * W + x]
            line.append(" .:-=+*#%@"[min(9, v // 26)])
        rows.append("".join(line))
    return rows


def cmd_ascii():
    info, bgs = parse_header()
    print(f"disp={info['disp']:#x}")
    # composite all enabled BGs by priority
    layers = []
    for idx, bg in bgs.items():
        if bg.get("en"):
            img = render_bg(idx, bg)
            if img is not None:
                layers.append((bg["cnt"] & 3, img))
    layers.sort(key=lambda t: t[0])
    out = bytearray(W * H)
    for _, img in layers:
        for i in range(len(out)):
            if img[i] and img[i] > out[i]:
                out[i] = img[i]
    for row in ascii_rows(out):
        print(row)


def cmd_grid():
    info, bgs = parse_header()
    for idx, bg in bgs.items():
        if not bg.get("en"):
            continue
        d = load_bg(idx, bg)
        if not d:
            continue
        md, td, mw, mh, colors, tb = d
        print(f"=== BG{idx}: {mw}x{mh}")
        for my in range(min(mh, 20)):
            cells = []
            for mx in range(min(mw, 30)):
                e = u16(md, (my * mw + mx) * 2)
                if not e:
                    cells.append(" .")
                else:
                    t = (e & 0x1FF) if colors else (e & 0x3FF)
                    cells.append(f"{t:2x}")
            print(" ".join(cells))


def tile_bitmap(td, tile, colors, tb):
    tdata = td[tile * tb:(tile + 1) * tb]
    rows = []
    for ty in range(8):
        line = []
        for tx in range(8):
            if colors:
                c = tdata[ty * 8 + tx]
            else:
                nib = tdata[ty * 4 + tx // 2]
                c = (nib >> ((tx & 1) * 4)) & 0xF
            line.append("#" if c else ".")
        rows.append("".join(line))
    return rows


def cmd_glyphs():
    info, bgs = parse_header()
    for idx, bg in bgs.items():
        if not bg.get("en"):
            continue
        d = load_bg(idx, bg)
        if not d:
            continue
        md, td, mw, mh, colors, tb = d
        used = []
        for my in range(mh):
            for mx in range(mw):
                e = u16(md, (my * mw + mx) * 2)
                if not e:
                    continue
                t = (e & 0x1FF) if colors else (e & 0x3FF)
                if t and t not in used:
                    used.append(t)
        print(f"=== BG{idx}: {len(used)} distinct tiles ===")
        for t in used:
            print(f"-- tile {t:#x} --")
            for r in tile_bitmap(td, t, colors, tb):
                print(r)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ascii"
    if cmd == "ascii":
        cmd_ascii()
    elif cmd == "grid":
        cmd_grid()
    elif cmd == "glyphs":
        cmd_glyphs()


if __name__ == "__main__":
    main()
