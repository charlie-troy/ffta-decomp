"""Verify compiled objects against data/functions.json.

Hashes the .text of each object and compares it to the recorded value. This is
the regression gate that works without the ROM, so CI can run it.

It proves every function still compiles to exactly the right bytes. It does not
prove the ROM links or that placement is correct; only `make rom` with a real
base ROM does that.

Usage:
    python tools/verify_functions.py [index.json] [objdir]
"""
import os
import sys
import json
import hashlib

import check_obj_sizes

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    index = argv[0] if argv else os.path.join(REPO, "data", "functions.json")
    objdir = argv[1] if len(argv) > 1 else os.path.join(REPO, "build", "obj")

    with open(index) as fh:
        data = json.load(fh)
    funcs = data["functions"]

    ok, bad, missing = [], [], []
    for f in funcs:
        path = os.path.join(objdir, f["object"] + ".o")
        if not os.path.isfile(path):
            missing.append(f["name"])
            continue
        text = check_obj_sizes.text_bytes(path)
        if text is None:
            missing.append(f["name"])
            continue
        # The section can be padded past the function; only the function's own
        # bytes are compared, and the ROM build validates the padding itself.
        got = hashlib.sha256(text[:f["size"]]).hexdigest()
        if got == f["sha256"]:
            ok.append(f["name"])
        else:
            bad.append((f["name"], f["size"], len(text)))

    print(f"index    : {len(funcs)} function(s)")
    print(f"verified : {len(ok)}")
    print(f"MISMATCH : {len(bad)}")
    print(f"missing  : {len(missing)}")

    for name, size, actual in bad:
        print(f"  mismatch {name} (expected {size} bytes, object .text {actual})")
    for name in missing[:10]:
        print(f"  missing object for {name}")

    if bad or missing:
        return 1
    print("\nall functions compile to the expected bytes")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main(sys.argv[1:]))
