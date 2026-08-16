"""Compare every compiled candidate against the base ROM.

Usage:
    python tools/report_matches.py <rom.gba> <manifest.json> <bindir> [--verbose]
"""
import os
import sys
import json


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
        path = os.path.join(bindir, name + ".bin")
        if not os.path.isfile(path):
            missing.append(name)
            continue
        built = open(path, "rb").read()[:f["size"]]
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
