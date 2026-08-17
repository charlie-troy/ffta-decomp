"""Report how much of the ROM is compiled from C rather than incbinned.

Usage:
    python tools/progress.py <manifest.json>
"""
import os
import re
import sys
import json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Rough estimate of the code-dense region, from the initial ROM survey.
CODE_REGION = 0x360000
ROM_SIZE = 0x1000000

EXTRA = {"sub_08005BB0": 18, "sub_080DBD5C": 20}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    manifest = {f["name"]: f for f in json.load(open(argv[0]))}

    names = set(EXTRA)
    for root, _dirs, files in os.walk(os.path.join(REPO, "src")):
        for fn in files:
            m = re.match(r"^(sub_[0-9A-Fa-f]{8})\.c$", fn)
            if m:
                names.add(m.group(1))

    total = 0
    for n in names:
        if n in manifest:
            total += manifest[n]["size"]
        elif n in EXTRA:
            total += EXTRA[n]

    print(f"functions decompiled : {len(names)}")
    print(f"bytes as C           : {total:,}")
    print(f"  of code region     : {100.0 * total / CODE_REGION:.3f}%  "
          f"(~{CODE_REGION:,} bytes to {CODE_REGION:#x})")
    print(f"  of whole ROM       : {100.0 * total / ROM_SIZE:.4f}%")

    remaining = len(manifest) - len([n for n in names if n in manifest])
    print(f"\nleaf candidates left in manifest: {remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
