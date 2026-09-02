"""Verify compiled objects against data/functions.json.

Hashes the .text of each object and compares it to the recorded value. This is
the regression gate that works without the ROM, so CI can run it.

Functions that reference a global carry R_ARM_ABS32 relocations, whose pool
words are placeholders until link time. Those are relocated here using
data/symbols.txt so they can be checked like any other function.

It proves every function still compiles to exactly the right bytes. It does not
prove the ROM links or that placement is correct; only `make rom` with a real
base ROM does that.

Usage:
    python tools/verify_functions.py [index.json] [objdir]
"""
import os
import re
import sys
import json
import hashlib

import elfutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def source_function_names():
    """Return every conventionally named decompiled source in src/."""
    names = set()
    for root, _dirs, files in os.walk(os.path.join(REPO, "src")):
        for filename in files:
            match = re.match(r"^(sub_[0-9A-Fa-f]{8})\.c$", filename)
            if match:
                names.add(match.group(1))
    return names


def main(argv):
    index = argv[0] if argv else os.path.join(REPO, "data", "functions.json")
    objdir = argv[1] if len(argv) > 1 else os.path.join(REPO, "build", "obj")
    sympath = os.path.join(REPO, "data", "symbols.txt")

    symaddrs = elfutil.load_symbols(sympath) if os.path.isfile(sympath) else {}
    asmpath = os.path.join(REPO, "data", "asm_symbols.txt")
    if os.path.isfile(asmpath):
        symaddrs.update(elfutil.load_symbols(asmpath))

    with open(index) as fh:
        data = json.load(fh)
    funcs = data["functions"]
    indexed_names = {f["name"] for f in funcs}
    unindexed = sorted(source_function_names() - indexed_names)

    ok, bad, missing, unresolved = [], [], [], []
    relocated = 0
    for f in funcs:
        path = os.path.join(objdir, f["object"] + ".o")
        if not os.path.isfile(path):
            missing.append(f["name"])
            continue
        text, unres = elfutil.Elf(path).text_relocated(
            symaddrs, base_addr=f["address"])
        if text is None:
            missing.append(f["name"])
            continue
        if unres:
            unresolved.append((f["name"], sorted(set(unres))))
            continue
        # The section can be padded past the function; only the function's own
        # bytes are compared, and the ROM build validates the padding itself.
        got = hashlib.sha256(text[:f["size"]]).hexdigest()
        if got == f["sha256"]:
            ok.append(f["name"])
        else:
            bad.append((f["name"], f["size"], len(text)))

    print(f"index      : {len(funcs)} function(s)")
    print(f"verified   : {len(ok)}")
    print(f"MISMATCH   : {len(bad)}")
    print(f"missing    : {len(missing)}")
    print(f"unresolved : {len(unresolved)}")
    print(f"unindexed  : {len(unindexed)}")

    for name, size, actual in bad:
        print(f"  mismatch {name} (expected {size} bytes, object .text {actual})")
    for name in missing[:10]:
        print(f"  missing object for {name}")
    for name, syms in unresolved[:10]:
        print(f"  {name} references unknown symbol(s): {', '.join(syms)}")
        print("    add them to data/symbols.txt")
    for name in unindexed[:10]:
        print(f"  source missing from index: {name}")

    if bad or missing or unresolved or unindexed:
        return 1
    print("\nall functions compile to the expected bytes")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main(sys.argv[1:]))
