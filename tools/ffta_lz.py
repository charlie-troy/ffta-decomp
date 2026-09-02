"""Decode and encode FFTA's BIOS-LZ77 map blocks and custom-LZSS graphics.

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


def map_lzss(data, off=0, with_consumed=False):
    """Decode FFTA's custom map-graphics LZSS stream.

    This is not the GBA BIOS Huffman format despite the outer map block types
    0x20/0x22. The inner stream starts with a big-endian u32 output size and
    uses six token forms for literals, zero/0xff runs, and back-references.
    Malformed streams raise ValueError instead of reading outside the input or
    fabricating bytes before the output buffer.
    """
    if off < 0 or off + 4 > len(data):
        raise ValueError("truncated map LZSS header")
    size = int.from_bytes(data[off:off + 4], "big")
    p = off + 4
    out = bytearray()

    def need(count, what):
        if p + count > len(data):
            raise ValueError(f"truncated map LZSS {what}")

    def emit_run(value, count):
        if len(out) + count > size:
            raise ValueError("map LZSS token exceeds declared output size")
        out.extend(bytes((value,)) * count)

    def emit_backref(displacement, count):
        if displacement <= 0 or displacement > len(out):
            raise ValueError("map LZSS back-reference precedes output")
        if len(out) + count > size:
            raise ValueError("map LZSS token exceeds declared output size")
        for _ in range(count):
            out.append(out[-displacement])

    while len(out) < size:
        need(1, "token")
        token = data[p]
        p += 1
        if token & 0x80:
            need(1, "short back-reference")
            displacement = ((token & 0x07) << 8) | data[p]
            p += 1
            emit_backref(displacement + 1, ((token >> 3) & 0x0F) + 3)
        elif token & 0x40:
            count = (token & 0x3F) + 1
            need(count, "literal run")
            if len(out) + count > size:
                raise ValueError("map LZSS literal exceeds declared output size")
            out.extend(data[p:p + count])
            p += count
        elif token & 0x20:
            emit_run(0, (token & 0x1F) + 2)
        elif token & 0x10:
            need(2, "long back-reference")
            b1, b2 = data[p], data[p + 1]
            p += 2
            displacement = ((b1 & 0x3F) << 8) | b2
            count = (((b1 >> 2) & 0x30) | (token & 0x0F)) + 4
            emit_backref(displacement + 1, count)
        elif token == 0x01:
            need(1, "0xff run")
            count = data[p] + 3
            p += 1
            emit_run(0xFF, count)
        elif token == 0x02:
            need(1, "extended zero run")
            count = data[p] + 3
            p += 1
            emit_run(0, count)
        elif token == 0x00:
            need(3, "extended back-reference")
            count = data[p] + 5
            displacement = (data[p + 1] << 8) | data[p + 2]
            p += 3
            emit_backref(displacement + 1, count)
        else:
            raise ValueError(f"unknown map LZSS token {token:#04x}")

    result = bytes(out)
    return (result, p - off) if with_consumed else result


def map_lzss_compress(raw):
    """Compress bytes with FFTA's map-graphics LZSS grammar.

    Dynamic programming chooses the smallest stream from the legal candidates.
    Back-reference candidates are drawn from equal three-byte prefixes within
    the format's 64 KiB window. Capping a pathological prefix chain keeps the
    search bounded; zero and 0xff runs have dedicated tokens and are evaluated
    independently.
    """
    size = len(raw)
    matches = [None] * size
    history = {}

    for pos in range(size):
        short_len = long_len = extended_len = 0
        short_disp = long_disp = extended_disp = 0
        if pos + 3 <= size:
            key = raw[pos:pos + 3]
            checked = 0
            for prior in reversed(history.get(key, ())):
                displacement = pos - prior
                if displacement > 0x10000:
                    break
                limit = min(260, size - pos)
                length = 3
                while (length < limit and
                       raw[prior + length] == raw[pos + length]):
                    length += 1
                if displacement <= 0x800 and min(length, 18) > short_len:
                    short_len, short_disp = min(length, 18), displacement
                if displacement <= 0x4000 and min(length, 67) > long_len:
                    long_len, long_disp = min(length, 67), displacement
                if length > extended_len:
                    extended_len, extended_disp = length, displacement
                checked += 1
                if short_len == 18 and long_len == 67 and extended_len == 260:
                    break
                if checked >= 512:
                    break
            history.setdefault(key, []).append(pos)

        zero_run = ff_run = 0
        if raw[pos] == 0:
            zero_run = 1
            while (pos + zero_run < size and zero_run < 258 and
                   raw[pos + zero_run] == 0):
                zero_run += 1
        elif raw[pos] == 0xFF:
            ff_run = 1
            while (pos + ff_run < size and ff_run < 258 and
                   raw[pos + ff_run] == 0xFF):
                ff_run += 1
        matches[pos] = (short_len, short_disp, long_len, long_disp,
                        extended_len, extended_disp, zero_run, ff_run)

    costs = [10 ** 9] * (size + 1)
    choices = [None] * size
    costs[size] = 0
    for pos in range(size - 1, -1, -1):
        options = (("literal", 1, min(64, size - pos), 1, 0),)
        short_len, short_disp, long_len, long_disp, extended_len, \
            extended_disp, zero_run, ff_run = matches[pos]
        options += (
            ("zero-short", 2, min(zero_run, 33), 1, 0),
            ("zero-extended", 3, zero_run, 2, 0),
            ("ff", 3, ff_run, 2, 0),
            ("backref-short", 3, short_len, 2, short_disp),
            ("backref-long", 4, long_len, 3, long_disp),
            ("backref-extended", 5, extended_len, 4, extended_disp),
        )
        for kind, first, last, overhead, displacement in options:
            for length in range(first, last + 1):
                cost = overhead + (length if kind == "literal" else 0)
                cost += costs[pos + length]
                if cost < costs[pos]:
                    costs[pos] = cost
                    choices[pos] = (kind, length, displacement)

    out = bytearray(size.to_bytes(4, "big"))
    pos = 0
    while pos < size:
        kind, length, displacement = choices[pos]
        if kind == "literal":
            out.append(0x40 + length - 1)
            out.extend(raw[pos:pos + length])
        elif kind == "zero-short":
            out.append(0x20 + length - 2)
        elif kind == "zero-extended":
            out.extend((0x02, length - 3))
        elif kind == "ff":
            out.extend((0x01, length - 3))
        elif kind == "backref-short":
            value = displacement - 1
            out.extend((0x80 | ((length - 3) << 3) | ((value >> 8) & 7),
                        value & 0xFF))
        elif kind == "backref-long":
            value = displacement - 1
            out.extend((0x10 | ((length - 4) & 0x0F),
                        ((value >> 8) & 0x3F) | (((length - 4) & 0x30) << 2),
                        value & 0xFF))
        else:
            value = displacement - 1
            out.extend((0x00, length - 5, (value >> 8) & 0xFF,
                        value & 0xFF))
        pos += length
    return bytes(out)
