"""Report objects whose .text size does not equal the function's ROM size.

A mismatch means the assembler padded the section, which makes the object
overrun whatever follows it in the ROM and breaks the link.

Usage:
    python tools/check_obj_sizes.py <manifest.json> [objdir]
"""
import os
import re
import sys
import json
import struct

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXTRA = {"match_test": ("sub_08005BB0", 18), "match_test2": ("sub_080DBD5C", 20)}


def text_size(path):
    """Read the ELF section headers and return the size of .text."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"\x7fELF":
        return None
    e_shoff = struct.unpack_from("<I", data, 0x20)[0]
    e_shentsize = struct.unpack_from("<H", data, 0x2E)[0]
    e_shnum = struct.unpack_from("<H", data, 0x30)[0]
    e_shstrndx = struct.unpack_from("<H", data, 0x32)[0]

    def sh(i):
        off = e_shoff + i * e_shentsize
        name, _type, _flags, _addr, offset, size = struct.unpack_from("<IIIIII", data, off)
        return name, offset, size

    _n, stroff, _s = sh(e_shstrndx)
    for i in range(e_shnum):
        name, _off, size = sh(i)
        end = data.index(b"\x00", stroff + name)
        if data[stroff + name:end] == b".text":
            return size
    return None


def main(argv):
    manifest = {f["name"]: f for f in json.load(open(argv[0]))}
    objdir = argv[1] if len(argv) > 1 else os.path.join(REPO, "build", "obj")

    bad = []
    checked = 0
    for fn in sorted(os.listdir(objdir)):
        if not fn.endswith(".o") or fn == "rom.o":
            continue
        stem = fn[:-2]
        if stem in EXTRA:
            expect = EXTRA[stem][1]
        elif stem in manifest:
            expect = manifest[stem]["size"]
        else:
            continue
        actual = text_size(os.path.join(objdir, fn))
        checked += 1
        if actual != expect:
            bad.append((stem, expect, actual))

    print(f"checked {checked} object(s)")
    if not bad:
        print("all .text sizes match their ROM sizes")
        return 0

    print(f"{len(bad)} mismatch(es):")
    for stem, expect, actual in bad:
        print(f"  {stem}: expected {expect}, got {actual} (+{actual - expect})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
