"""Compare every compiled candidate against the base ROM.

Usage:
    python tools/report_matches.py <rom.gba> <manifest.json> <bindir> [--verbose]
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elfutil

_SYMS = None


def _symbols():
    global _SYMS
    if _SYMS is None:
        _SYMS = {}
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data")
        for name in ("symbols.txt", "sym_ewram.txt", "sym_iwram.txt"):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                _SYMS.update(elfutil.load_symbols(p))
    return _SYMS


def built_bytes(bindir, name, size):
    """Prefer the object, so relocations to globals are applied.

    A raw .bin still holds placeholder literal-pool words for any function that
    references a global, which shows up as a spurious mismatch.
    """
    obj = os.path.join(bindir, name + ".o")
    if os.path.isfile(obj):
        try:
            text, unresolved = elfutil.Elf(obj).text_relocated(_symbols())
            if text is not None and not unresolved:
                return text[:size]
        except Exception:
            pass
    path = os.path.join(bindir, name + ".bin")
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()[:size]


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2

    rom_path, manifest, bindir = argv[:3]
    verbose = "--verbose" in argv

    rom = open(rom_path, "rb").read()
    funcs = {f["name"]: f for f in json.load(open(manifest))}

    matched, mismatched, missing = [], [], []
    matched_bytes = 0

    for name, f in sorted(funcs.items()):
        built = built_bytes(bindir, name, f["size"])
        if built is None:
            missing.append(name)
            continue
        orig = rom[f["offset"]:f["offset"] + f["size"]]
        if built == orig:
            matched.append(name)
            matched_bytes += f["size"]
        else:
            ndiff = sum(1 for a, b in zip(orig, built) if a != b)
            ndiff += abs(len(orig) - len(built))
            mismatched.append((name, f, ndiff))

    attempted = len(matched) + len(mismatched)
    print(f"attempted   : {attempted}")
    print(f"MATCHED     : {len(matched)}")
    print(f"mismatched  : {len(mismatched)}")
    print(f"not built   : {len(missing)}")
    print(f"bytes matched: {matched_bytes:,}")
    if attempted:
        print(f"match rate  : {100.0 * len(matched) / attempted:.1f}%")

    if mismatched:
        print("\n--- mismatches ---")
        for name, f, ndiff in sorted(mismatched, key=lambda x: x[2]):
            print(f"  {name}  {f['size']:>3}b  {ndiff} byte(s) differ")
            if verbose:
                built = open(os.path.join(bindir, name + ".bin"), "rb").read()
                orig = rom[f["offset"]:f["offset"] + f["size"]]
                print(f"      orig  {orig.hex(' ')}")
                print(f"      built {built[:f['size']].hex(' ')}")

    if verbose and matched:
        print("\n--- matched ---")
        for name in matched:
            print(f"  {name}")

    return 0 if not mismatched else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
