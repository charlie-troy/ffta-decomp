"""Verify a user-supplied FFTA ROM and stage it as baserom.gba.

The ROM is never committed. Every build starts by proving the input is the
exact revision this project targets.

Usage:
    python tools/verify_rom.py <path-to-rom.gba> [--stage]
"""
import sys
import hashlib
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Known-good dumps. sha1 -> (label, game code)
KNOWN = {
    "4ac05441f4de70a4ec3dd932116346c61b8783d9": ("FFTA (USA)", "AFXE"),
}

TARGET = "4ac05441f4de70a4ec3dd932116346c61b8783d9"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    rom_path = Path(sys.argv[1])
    if not rom_path.is_file():
        print(f"error: no such file: {rom_path}")
        return 1

    data = rom_path.read_bytes()
    sha1 = hashlib.sha1(data).hexdigest()

    title = data[0xA0:0xAC].decode("ascii", "replace").rstrip("\x00")
    code = data[0xAC:0xB0].decode("ascii", "replace")

    print(f"file      : {rom_path}")
    print(f"size      : {len(data):,} bytes")
    print(f"title     : {title}")
    print(f"game code : {code}")
    print(f"sha1      : {sha1}")

    if sha1 == TARGET:
        print(f"\nOK: matches {KNOWN[sha1][0]}, the revision this project targets.")
    elif sha1 in KNOWN:
        print(f"\nWRONG REVISION: this is {KNOWN[sha1][0]}. Target is {KNOWN[TARGET][0]}.")
        return 1
    else:
        print("\nUNKNOWN ROM: sha1 not recognised. Refusing to proceed.")
        return 1

    if "--stage" in sys.argv:
        dest = REPO / "baserom.gba"
        shutil.copyfile(rom_path, dest)
        print(f"staged -> {dest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
