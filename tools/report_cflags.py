"""Report which agbcc flag setting gets each function closest.

Usage:
    python tools/report_cflags.py <rom.gba> <manifest.json> <sweep_root>
"""
import os
import sys
import json
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import elfutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def symbols():
    out = {}
    for name in ("symbols.txt", "asm_symbols.txt"):
        p = os.path.join(REPO, "data", name)
        if os.path.isfile(p):
            out.update(elfutil.load_symbols(p))
    return out


def built(objdir, fn, size, addr, syms):
    obj = os.path.join(objdir, fn + ".o")
    if os.path.isfile(obj):
        try:
            text, unres = elfutil.Elf(obj).text_relocated(syms, base_addr=addr)
            if text is not None and not unres:
                return text[:size]
        except Exception:
            pass
    b = os.path.join(objdir, fn + ".bin")
    if os.path.isfile(b):
        with open(b, "rb") as fh:
            return fh.read()[:size]
    return None


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    rom_path, manifest, root = argv
    rom = open(rom_path, "rb").read()
    manifest = {f["name"]: f for f in json.load(open(manifest))}
    syms = symbols()

    tags = sorted(d for d in os.listdir(root)
                  if os.path.isdir(os.path.join(root, d)))

    results = collections.defaultdict(dict)
    for tag in tags:
        d = os.path.join(root, tag)
        for fn in os.listdir(d):
            if not fn.endswith(".o"):
                continue
            name = fn[:-2]
            f = manifest.get(name)
            if f is None:
                continue
            b = built(d, name, f["size"], f["addr"], syms)
            if b is None:
                continue
            orig = rom[f["offset"]:f["offset"] + f["size"]]
            nd = sum(1 for x, y in zip(orig, b) if x != y) + abs(len(orig) - len(b))
            results[name][tag] = nd

    for name in sorted(results):
        rows = sorted(results[name].items(), key=lambda kv: kv[1])
        base = results[name].get("baseline")
        print(f"\n=== {name} (baseline {base}) ===")
        for tag, nd in rows[:6]:
            mark = "  MATCH" if nd == 0 else ""
            better = " <-- better" if base is not None and nd < base else ""
            print(f"  {nd:>4}  {tag}{mark}{better}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
