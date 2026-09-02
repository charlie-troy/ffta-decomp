"""Validate every string used by the project's four primary text tables."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ffta_text import decode, decode1, score


TABLES = (
    ("main", 0x08526680, 753),
    ("ui", 0x085567F0, 767),
    ("missions", 0x0855A64C, 512),
    ("first names", 0x085680DC, 725),
)

ANCHORS = {
    ("main", 682): "Heal < 50",
    ("main", 683): "Heal < 100",
    ("main", 710): "(not used)",
    ("ui", 64): "(---)",
    ("ui", 74): "〖Enhance〗",
    ("ui", 75): "(---)",
    ("ui", 208): "100% Wool",
}


def best(data, off):
    wide = decode(data, off)
    single = decode1(data, off)
    return wide if score(wide[0]) >= score(single[0]) else single


def main(argv):
    if len(argv) != 1:
        print("usage: validate_text.py ROM")
        return 2

    rom = open(argv[0], "rb").read()
    total = 0
    unknown = []
    anchors = {}
    for label, address, count in TABLES:
        table = address - 0x08000000
        for index in range(count):
            pointer = int.from_bytes(
                rom[table + index * 4:table + index * 4 + 4], "little")
            off = pointer - 0x08000000
            text, _, bad = best(rom, off)
            total += 1
            if bad:
                unknown.append((label, index, text, bad))
            if (label, index) in ANCHORS:
                anchors[(label, index)] = text

    bad_anchors = [(key, ANCHORS[key], anchors.get(key))
                   for key in ANCHORS if anchors.get(key) != ANCHORS[key]]
    print(f"strings decoded without unknown codes: {total - len(unknown)}/{total}")
    print(f"resolved edge-case anchors: {len(ANCHORS) - len(bad_anchors)}/{len(ANCHORS)}")
    for key, expected, actual in bad_anchors:
        print(f"  {key[0]}[{key[1]}]: expected {expected!r}, got {actual!r}")
    for label, index, text, bad in unknown:
        print(f"  {label}[{index}]: {text!r}; unknown {bad!r}")
    return 1 if unknown or bad_anchors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
