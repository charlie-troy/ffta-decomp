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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Matched before the src/ naming convention settled.
EXTRA = {
    "sub_08005BB0": ("match_test", 0x005BB0, 18),
    "sub_080DBD5C": ("match_test2", 0x0DBD5C, 20),
}

# The evaluator's final literal is a 32-bit word ending in two zero bytes.
# Discovery stops at the last non-zero halfword, but those zero bytes remain
# part of the function-owned literal and the matching source's .text section.
SIZE_OVERRIDES = {
    "sub_080C32C0": 5352,
}


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2

    rom = open(argv[0], "rb").read()
    manifest = {f["name"]: f for f in json.load(open(argv[1]))}

    entries = []
    for root, _dirs, files in os.walk(os.path.join(REPO, "src")):
        for fn in sorted(files):
            m = re.match(r"^(sub_[0-9A-Fa-f]{8})\.c$", fn)
            if not m:
                continue
            name = m.group(1)
            f = manifest.get(name)
            if f is None:
                print(f"warning: {name} not in manifest, skipped")
                continue
            entries.append((name, name, f["offset"],
                            SIZE_OVERRIDES.get(name, f["size"])))

    for name, (obj, off, size) in EXTRA.items():
        if os.path.isfile(os.path.join(REPO, "src", obj + ".c")):
            entries.append((name, obj, off, size))

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
