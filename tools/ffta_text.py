"""Decode FFTA text.

Strings are sequences of two-byte codes ending in a 0x00 byte. The first byte
selects a bank and the second the glyph. Bank 0x80 holds the alphabet, laid out
so 0xB0..0xC9 is A..Z and 0xCA..0xE3 is a..z; bank 0x40 holds punctuation and
the space.

Derived by decoding the 511-entry pointer table at 0x0855A64C and checking the
result against known mission names: entry 1 comes out as "Snowball Fight",
which is the first mission in the game.
"""
ALPHA_UPPER = 0xB0
ALPHA_LOWER = 0xCA
DIGIT = 0xA6

# Punctuation, read off from strings whose text is known independently:
# "Materite Now!", "Raven's Oath", "Castle Sit-In", "Damage > MP",
# "Weapon Atk+", "Flesh & Bones", "Aim: Armor", "Sorry, Friend".
BANK40 = {0x73: " ", 0x3E: " ", 0x3C: ""}
BANK80 = {0xE4: ".", 0xEA: "?", 0xEB: "!", 0xEC: ",", 0xEE: ":",
          0xF1: "/", 0xF4: "'", 0xFD: "+", 0xFE: "-"}
BANK81 = {0x03: ">", 0x08: "&"}


def _glyph(bank, code):
    if bank == 0x80:
        if ALPHA_UPPER <= code < ALPHA_UPPER + 26:
            return chr(ord("A") + code - ALPHA_UPPER)
        if ALPHA_LOWER <= code < ALPHA_LOWER + 26:
            return chr(ord("a") + code - ALPHA_LOWER)
        if DIGIT <= code < DIGIT + 10:
            return chr(ord("0") + code - DIGIT)
    if bank == 0x80 and code in BANK80:
        return BANK80[code]
    if bank == 0x81 and code in BANK81:
        return BANK81[code]
    if bank == 0x40 and code in BANK40:
        return BANK40[code]
    return None


BANKS = (0x40, 0x80)


def decode(data, off, limit=512, marks=False):
    """Decode one string. Returns (text, bytes_consumed, unknown_codes).

    A byte below 0x20 is a single-byte control code; 0x40 and 0x80 introduce a
    two-byte glyph. Mixing the two is why a naive two-byte read desynchronises
    partway through some strings.
    """
    out = []
    unknown = []
    p = off
    end = min(len(data), off + limit)
    while p < end:
        b = data[p]
        if b == 0x00:
            p += 1
            break
        if b < 0x20 or b == 0xFF:
            if marks:
                out.append(f"<{b:02x}>")
            p += 1
            continue
        if p + 1 >= end:
            break
        code = data[p + 1]
        g = _glyph(b, code)
        if g is None:
            unknown.append((b, code))
            out.append(f"[{b:02x}{code:02x}]")
        else:
            out.append(g)
        p += 2
    return "".join(out), p - off, unknown


def table(data, ptr_table, count):
    """Decode a run of strings addressed by a pointer table."""
    out = []
    for i in range(count):
        a = int.from_bytes(data[ptr_table + i * 4:ptr_table + i * 4 + 4],
                           "little") - 0x08000000
        out.append(decode(data, a)[0])
    return out


# A second encoding stores one byte a character, with the alphabet shifted up
# by one from the two-byte form: 0xB1 is A and 0xCB is a. Character names use
# it; mission names and UI text use the two-byte form.
WIDE_UPPER, WIDE_LOWER, WIDE_DIGIT = 0xB1, 0xCB, 0xA7


def decode1(data, off, limit=256, marks=False):
    """Decode a single-byte-encoded string."""
    out, unknown = [], []
    p = off
    end = min(len(data), off + limit)
    while p < end:
        b = data[p]
        if b == 0x00:
            p += 1
            break
        if WIDE_UPPER <= b < WIDE_UPPER + 26:
            out.append(chr(ord("A") + b - WIDE_UPPER))
        elif WIDE_LOWER <= b < WIDE_LOWER + 26:
            out.append(chr(ord("a") + b - WIDE_LOWER))
        elif WIDE_DIGIT <= b < WIDE_DIGIT + 10:
            out.append(chr(ord("0") + b - WIDE_DIGIT))
        elif (b - 1) in BANK80:
            out.append(BANK80[b - 1])
        elif b < 0x20 or b == 0xFF:
            if marks:
                out.append(f"<{b:02x}>")
        else:
            unknown.append(b)
            out.append(f"[{b:02x}]")
        p += 1
    return "".join(out), p - off, unknown


def score(text):
    """Share of the output that came out as real characters."""
    if not text:
        return 0.0
    bad = text.count("[")
    return 1.0 - (bad * 4.0) / max(len(text), 1)


def decode_auto(data, off):
    """Pick whichever codec reads this string more cleanly."""
    a = decode(data, off)[0]
    b = decode1(data, off)[0]
    return a if score(a) >= score(b) else b
