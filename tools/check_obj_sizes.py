"""Validate object .text sizes against their function-owned ROM ranges.

An object may carry alignment padding past the function. With a base ROM this
tool proves that every padded-over byte is zero; without one it reports padding
as unverified but still rejects missing, unreadable, or truncated objects.

Usage:
    python tools/check_obj_sizes.py <manifest.json> [objdir] [--rom baserom.gba]
"""
import argparse
import os
import sys
import struct

from function_metadata import load_metadata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def text_bytes(path):
    """Return the contents of the .text section of an ELF object."""
    with open(path, "rb") as fh:
        data = fh.read()
    found = _find_text(data)
    if found is None:
        return None
    offset, size = found
    return data[offset:offset + size]


def _find_text(data):
    """Return (file_offset, size) of .text, or None."""
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
        name, off, size = sh(i)
        end = data.index(b"\x00", stroff + name)
        if data[stroff + name:end] == b".text":
            return off, size
    return None


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


def classify_size(expected, actual, offset=None, rom=None):
    """Return (classification, detail) for one compiled .text section."""
    if actual is None:
        return "error", "has no readable .text section"
    if actual < expected:
        return "error", f"is truncated: expected {expected}, got {actual}"
    if actual == expected:
        return "exact", ""

    detail = f"padded {expected} -> {actual}"
    if rom is None:
        return "unverified-padding", detail
    if offset is None or offset + actual > len(rom):
        return "error", f"{detail}, extending past the supplied ROM"
    tail = rom[offset + expected:offset + actual]
    if any(tail):
        return "error", f"{detail}, covering nonzero ROM bytes"
    return "safe-padding", f"{detail}, covering only zero ROM bytes"


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("objdir", nargs="?", default=os.path.join(REPO, "build", "obj"))
    parser.add_argument("--rom", help="base ROM used to prove padding is safe")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    manifest = load_metadata(args.manifest)
    rom = None
    if args.rom:
        with open(args.rom, "rb") as handle:
            rom = handle.read()

    results = []
    for name, row in sorted(manifest.items(), key=lambda item: item[1]["offset"]):
        obj = row.get("object", name)
        path = os.path.join(args.objdir, obj + ".o")
        actual = text_size(path) if os.path.isfile(path) else None
        kind, detail = classify_size(row["size"], actual, row["offset"], rom)
        results.append((name, kind, detail))

    errors = [result for result in results if result[1] == "error"]
    safe = [result for result in results if result[1] == "safe-padding"]
    unverified = [result for result in results if result[1] == "unverified-padding"]

    print(f"checked {len(results)} object(s)")
    for name, _kind, detail in safe:
        print(f"  safe: {name} {detail}")
    for name, _kind, detail in unverified:
        print(f"  note: {name} {detail}; supply --rom to verify")
    for name, _kind, detail in errors:
        print(f"  error: {name} {detail}")

    if errors:
        print(f"FAILED: {len(errors)} unsafe object(s)")
        return 1
    if unverified:
        print(f"PASS with {len(unverified)} unverified padded object(s)")
    elif safe:
        print(f"PASS with {len(safe)} ROM-verified safe padded object(s)")
    else:
        print("PASS: all .text sizes exactly match their function ranges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
