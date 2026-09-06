"""Pixel-accurate GBA BG renderer over the mGBA GDB stub.

Renders the enabled BG layers of a mode 0/1 screen with window clipping and
real 16-bit palettes. Mode 5 (bitmap video) is rendered directly. OBJ sprites
are not rendered. Pure-python: writes PNGs without PIL (the Windows-side PIL
can be used afterwards for inspection).

Run inside WSL against the live stub:
    python3 tools/gba_render.py --out shot.png --ascii
"""
import sys
import os
import struct
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gba_drive import Session  # noqa: E402

VRAM = 0x06000000
PAL = 0x05000000
IO = 0x04000000
W, H = 240, 160


def _u16(b, off=0):
    return int.from_bytes(b[off:off + 2], "little")


def load(s, addr, n, chunk=0x200):
    return s.read_mem(addr, n, chunk=chunk)


def _bgr555(v):
    return ((v & 0x1F) * 255 // 31,
            ((v >> 5) & 0x1F) * 255 // 31,
            ((v >> 10) & 0x1F) * 255 // 31)


def write_png(path, rgb):
    """Write an RGB bytearray (w*h*3) as a PNG without PIL."""
    raw = b"".join(b"\x00" + bytes(rgb[y * W * 3:(y + 1) * W * 3])
                   for y in range(H))
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


def ascii_of(rgb, scale=4):
    rows = []
    for y in range(0, H, scale):
        line = []
        for x in range(0, W, scale):
            tot = 0
            n = 0
            for yy in range(y, min(y + scale, H)):
                for xx in range(x, min(x + scale, W)):
                    o = (yy * W + xx) * 3
                    lum = rgb[o] * 3 + rgb[o + 1] * 6 + rgb[o + 2]
                    tot += lum
                    n += 1
            v = tot / (n * 10)
            line.append(" .:-=+*#%@"[min(9, int(v / 25.6))])
        rows.append("".join(line))
    return rows


class Renderer:
    def __init__(self, s: Session):
        self.s = s

    def _disp(self):
        return _u16(load(self.s, IO, 2))

    def _bgcnt(self, i):
        return _u16(load(self.s, IO + 8 + 2 * i, 2))

    def _bg_palette(self):
        raw = load(self.s, PAL, 0x200)
        return [_bgr555(_u16(raw, k * 2)) for k in range(256)]

    def _windows(self):
        disp = self._disp()
        w0 = bool(disp & 0x2000)
        w1 = bool(disp & 0x4000)
        winin = _u16(load(self.s, IO + 0x48, 2))
        winout = _u16(load(self.s, IO + 0x4A, 2))
        h0 = _u16(load(self.s, IO + 0x40, 2))
        v0 = _u16(load(self.s, IO + 0x42, 2))
        h1 = _u16(load(self.s, IO + 0x44, 2))
        v1 = _u16(load(self.s, IO + 0x46, 2))
        return (w0, w1, winin, winout,
                [(h0 & 0xFF, (h0 >> 8) & 0xFF, v0 & 0xFF, (v0 >> 8) & 0xFF),
                 (h1 & 0xFF, (h1 >> 8) & 0xFF, v1 & 0xFF, (v1 >> 8) & 0xFF)])

    def _text_bg(self, i, pal):
        """RGB bytearray for a 16/256-color text BG (opaque, no windows)."""
        cnt = self._bgcnt(i)
        colors = (cnt >> 5) & 1
        mw, mh = [(32, 32), (64, 32), (32, 64), (64, 64)][(cnt >> 6) & 3]
        map_base = VRAM + ((cnt >> 8) & 0x1F) * 0x800
        cb = VRAM + ((cnt >> 2) & 3) * (0x8000 if colors else 0x4000)
        tile_bytes = 64 if colors else 32
        md = load(self.s, map_base, mw * mh * 2)
        img = bytearray(W * H * 3)
        cache = {}

        def decoded(tile, bank):
            key = tile if colors else tile * 16 + bank
            if key not in cache:
                t = load(self.s, cb + tile * tile_bytes, tile_bytes)
                rows = []
                for ty in range(8):
                    rr = []
                    for tx in range(8):
                        if colors:
                            c = t[ty * 8 + tx]
                            rr.append(pal[c] if c < 256 else (0, 0, 0))
                        else:
                            nib = t[ty * 4 + tx // 2]
                            c = (nib >> ((tx & 1) * 4)) & 0xF
                            rr.append(pal[bank * 16 + c])
                    rows.append(rr)
                cache[key] = rows
            return cache[key]

        for my in range(mh):
            for mx in range(mw):
                e = _u16(md, (my * mw + mx) * 2)
                t = e & (0x3FF if not colors else 0x1FF)
                bank = (e >> 12) & 0xF if not colors else 0
                rows = decoded(t, bank)
                flip_h = bool(e & (1 << 10))
                flip_v = bool(e & (1 << 11))
                px0 = mx * 8
                py0 = my * 8
                for ty in range(8):
                    for tx in range(8):
                        x = px0 + (7 - tx if flip_h else tx)
                        y = py0 + (7 - ty if flip_v else ty)
                        if 0 <= x < W and 0 <= y < H:
                            o = (y * W + x) * 3
                            r, g, b = rows[ty][tx]
                            img[o] = r
                            img[o + 1] = g
                            img[o + 2] = b
        return img

    def _bitmap(self):
        disp = self._disp()
        page = 0xA000 if (disp & 0x10) else 0x0000
        img = bytearray(W * H * 3)
        raw = load(self.s, VRAM + page, W * H * 2)
        for p in range(W * H):
            r, g, b = _bgr555(_u16(raw, p * 2))
            o = p * 3
            img[o] = r
            img[o + 1] = g
            img[o + 2] = b
        return img

    # -- OBJ sprites ------------------------------------------------------
    OBJ_DIMS = {
        (0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
        (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
        (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64),
    }

    def _obj(self, pal):
        """Render OBJ sprites; returns (img, prio_grid) with transparency."""
        disp = self._disp()
        oam = load(self.s, 0x07000000, 0x400)
        tile_base = 0x06010000 if not (disp & 0x40) else 0x06014000
        img = bytearray(W * H * 3)
        prio = [[None] * W for _ in range(H)]
        for s in range(128):
            a0 = _u16(oam, s * 8)
            a1 = _u16(oam, s * 8 + 2)
            a2 = _u16(oam, s * 8 + 4)
            if a0 & (1 << 9):
                continue
            shape = (a0 >> 14) & 3
            size = (a1 >> 14) & 3
            if (shape, size) not in self.OBJ_DIMS:
                continue
            w, h = self.OBJ_DIMS[(shape, size)]
            colors = (a0 >> 13) & 1
            pr = (a2 >> 10) & 3
            flip_h = bool(a1 & (1 << 12))
            flip_v = bool(a1 & (1 << 13))
            tile = a2 & 0x3FF
            bank = (a2 >> 12) & 0xF
            x = a1 & 0x1FF
            y = a0 & 0xFF
            if x >= 240:
                x -= 512
            if y >= 160:
                y -= 256
            tb = 64 if colors else 32
            for ty in range(h // 8):
                for tx in range(w // 8):
                    t = tile + (ty * (16 if colors else 32) + tx)
                    t = t & 0x3FF
                    tdata = load(self.s, tile_base + t * tb, tb)
                    for py in range(8):
                        for px in range(8):
                            if colors:
                                c = tdata[py * 8 + px]
                                if c == 0:
                                    continue
                                col = pal[c] if c < 256 else (0, 0, 0)
                            else:
                                nib = tdata[py * 4 + px // 2]
                                c = (nib >> ((px & 1) * 4)) & 0xF
                                if c == 0:
                                    continue
                                idx = bank * 16 + c
                                col = pal[idx] if idx < 256 else (0, 0, 0)
                            sx = x + tx * 8 + (7 - px if flip_h else px)
                            sy = y + ty * 8 + (7 - py if flip_v else py)
                            if 0 <= sx < W and 0 <= sy < H:
                                if prio[sy][sx] is not None and \
                                        prio[sy][sx] <= pr:
                                    continue
                                o = (sy * W + sx) * 3
                                img[o] = col[0]
                                img[o + 1] = col[1]
                                img[o + 2] = col[2]
                                prio[sy][sx] = pr
        return img, prio

    def render(self):
        disp = self._disp()
        mode = disp & 7
        blank = bool(disp & 0x80)
        if blank:
            return bytearray(W * H * 3)
        if mode == 5:
            return self._bitmap()
        if mode not in (0, 1):
            return bytearray(W * H * 3)
        pal = self._bg_palette()
        w0, w1, winin, winout, wins = self._windows()
        # per-BG full images + per-pixel visibility closures
        layers = []
        for i in range(4):
            if not (disp & (0x100 << i)):
                continue
            if mode == 1 and i == 2:
                continue  # affine BG2 not rendered
            bit = 1 << i
            in0 = bool(winin & bit)
            in1 = bool((winin >> 8) & bit)
            outside = bool(winout & bit)
            (a0, b0, c0, d0) = wins[0]
            (a1, b1, c1, d1) = wins[1]

            def vis(x, y, _i=i, _w0=w0, _w1=w1, _a0=a0, _b0=b0, _c0=c0,
                    _d0=d0, _a1=a1, _b1=b1, _c1=c1, _d1=d1,
                    _in0=in0, _in1=in1, _outside=outside):
                if _w0 and _a0 <= x < _b0 and _c0 <= y < _d0:
                    return _in0
                if _w1 and _a1 <= x < _b1 and _c1 <= y < _d1:
                    return _in1
                return _outside
            layers.append((self._bgcnt(i) & 3, i, self._text_bg(i, pal), vis))
        layers.sort()
        out = bytearray(W * H * 3)
        for _, _i, img, vis in layers:
            for y in range(H):
                base = y * W
                for x in range(W):
                    if not vis(x, y):
                        continue
                    o = (base + x) * 3
                    if out[o] or out[o + 1] or out[o + 2]:
                        continue
                    out[o] = img[o]
                    out[o + 1] = img[o + 1]
                    out[o + 2] = img[o + 2]
        # OBJ layer: visible per window rules (OBJ bit 4), drawn over BG
        if disp & 0x1000:
            oimg, oprio = self._obj(pal)
            oin0 = bool(winin & 0x10)
            oin1 = bool((winin >> 8) & 0x10)
            oout = bool(winout & 0x10)
            (a0, b0, c0, d0) = wins[0]
            (a1, b1, c1, d1) = wins[1]
            for y in range(H):
                base = y * W
                for x in range(W):
                    inside0 = w0 and a0 <= x < b0 and c0 <= y < d0
                    inside1 = w1 and a1 <= x < b1 and c1 <= y < d1
                    if inside0:
                        ok = oin0
                    elif inside1:
                        ok = oin1
                    else:
                        ok = oout
                    if not ok:
                        continue
                    o = (base + x) * 3
                    if oprio[y][x] is None:
                        continue
                    out[o] = oimg[o]
                    out[o + 1] = oimg[o + 1]
                    out[o + 2] = oimg[o + 2]
        return out


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="screen.png")
    p.add_argument("--ascii", action="store_true")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args()
    s = Session(args.host, args.port)
    try:
        disp = s.read_u16(IO)
        print(f"DISPCNT={disp:#06x} mode={disp & 7}")
        rgb = Renderer(s).render()
        if args.out:
            write_png(args.out, rgb)
            print(f"saved {args.out}")
        if args.ascii:
            for row in ascii_of(rgb):
                print(row)
    finally:
        s.close()
