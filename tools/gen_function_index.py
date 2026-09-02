"""Generate data/functions.json: the per-function regression index.

For every decompiled function this records its address, size and a SHA-256 of
the bytes it must compile to. Hashes, not bytes, so the index carries no ROM
content and can be committed; that is what lets CI verify every function
without the ROM being present.

Re-run this whenever a function is added to src/.

Usage:
    python tools/gen_function_index.py <rom.gba> <manifest.json>
"""
import os
import re
import sys
import json
import hashlib

from function_metadata import load_metadata

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2

    rom = open(argv[0], "rb").read()
    manifest = load_metadata(argv[1])

    entries = []
    missing = []
    for root, _dirs, files in os.walk(os.path.join(REPO, "src")):
        for fn in sorted(files):
            m = re.match(r"^(sub_[0-9A-Fa-f]{8})\.c$", fn)
            if not m:
                continue
            name = m.group(1)
            f = manifest.get(name)
            if f is None:
                missing.append(name)
                continue
            entries.append((name, name, f["offset"], f["size"]))

    if missing:
        for name in sorted(missing):
            print(f"error: source {name} has no discovery or manual metadata")
        print("function index not written")
        return 1

    entries.sort(key=lambda e: e[2])

    out = {
        "rom_sha1": hashlib.sha1(rom).hexdigest(),
        "functions": [
            {
                "name": name,
                "object": obj,
                "address": 0x08000000 + off,
                "offset": off,
                "size": size,
                "sha256": hashlib.sha256(rom[off:off + size]).hexdigest(),
            }
            for name, obj, off, size in entries
        ],
    }

    os.makedirs(os.path.join(REPO, "data"), exist_ok=True)
    path = os.path.join(REPO, "data", "functions.json")
    with open(path, "w", newline="\n") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")

    total = sum(e[3] for e in entries)
    print(f"wrote {path}: {len(entries)} function(s), {total:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
