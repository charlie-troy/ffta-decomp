"""Decompress FFTA map blocks.

Each block carries an 8-byte header: the four bytes 11 FF FF FF, then a
standard GBA LZ77 header (0x10 plus a 24-bit decompressed size). The payload
that follows is ordinary BIOS LZ77, so the game decompresses it with SWI 0x11,
which is where the leading byte comes from.
"""
WRAPPER = bytes((0x11, 0xFF, 0xFF, 0xFF))


def parse_header(data, off=0):
    """Return (payload_offset, decompressed_size), or None if not a block."""
    if data[off:off + 4] != WRAPPER:
        return None
    if data[off + 4] != 0x10:
        return None
    size = int.from_bytes(data[off + 5:off + 8], "little")
    return off + 8, size


def lz77(data, off, size):
    """BIOS LZ77 (SWI 0x11): flag byte, MSB first; 0 literal, 1 back-reference."""
    out = bytearray()
    p = off
    while len(out) < size and p < len(data):
        flags = data[p]
        p += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                if p + 1 >= len(data):
                    return bytes(out)
                b0, b1 = data[p], data[p + 1]
                p += 2
                n = (b0 >> 4) + 3
                disp = (((b0 & 0x0F) << 8) | b1) + 1
                if disp > len(out):
                    return bytes(out)
                for _ in range(n):
                    out.append(out[len(out) - disp])
                    if len(out) >= size:
                        break
            else:
                if p >= len(data):
                    return bytes(out)
                out.append(data[p])
                p += 1
    return bytes(out)


def block_length(data, off):
    """Total bytes the block at off occupies, header included.

    Needed before writing a modded block back: the replacement has to fit the
    space the original used, and nothing else records that length.
    """
    h = parse_header(data, off)
    if h is None:
        return None
    payload, size = h
    out = 0
    p = payload
    while out < size and p < len(data):
        flags = data[p]
        p += 1
        for bit in range(8):
            if out >= size:
                break
            if flags & (0x80 >> bit):
                b0 = data[p]
                p += 2
                out += (b0 >> 4) + 3
            else:
                p += 1
                out += 1
    return p - off


def decompress(data, off=0):
    h = parse_header(data, off)
    if h is None:
        return None
    payload, size = h
    return lz77(data, payload, size)


def compress(raw):
    """Greedy LZ77 producing a stream the BIOS decoder accepts.

    Written so a modded block can be put back in place. The result is not
    guaranteed to be as small as the original, so callers must check that it
    still fits the space available rather than assume it does.
    """
    out = bytearray()
    p = 0
    n = len(raw)
    while p < n:
        flags = 0
        chunk = bytearray()
        for bit in range(8):
            if p >= n:
                break
            best_len, best_disp = 0, 0
            start = max(0, p - 0x1000)
            # A match may not read past the current position by more than the
            # displacement allows; keep it simple and bounded.
            for disp in range(1, min(0x1000, p) + 1):
                q = p - disp
                ln = 0
                while ln < 18 and p + ln < n and raw[q + ln] == raw[p + ln]:
                    ln += 1
                if ln > best_len:
                    best_len, best_disp = ln, disp
                    if ln == 18:
                        break
            if best_len >= 3:
                flags |= 0x80 >> bit
                v = ((best_len - 3) << 12) | (best_disp - 1)
                chunk.append((v >> 8) & 0xFF)
                chunk.append(v & 0xFF)
                p += best_len
            else:
                chunk.append(raw[p])
                p += 1
        out.append(flags)
        out += chunk
    return bytes(out)


def pack(raw):
    """Wrap compressed data in the 8-byte header the map blocks use."""
    body = compress(raw)
    return WRAPPER + bytes((0x10,)) + len(raw).to_bytes(3, "little") + body
