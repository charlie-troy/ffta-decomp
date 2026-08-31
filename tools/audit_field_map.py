"""Print and verify the exact 48-field job-table accessor map.

Usage:
    python tools/audit_field_map.py [rom.gba]
"""
import argparse

from emulate import Gba
from job_fields import ACCESSOR, COUNT, FIELDS, read_field


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", nargs="?", default="baserom.gba")
    args = parser.parse_args(argv)
    rom = open(args.rom, "rb").read()
    gba = Gba(args.rom)

    print("+0x05 resolution: 0 = current record; 0xff = caller fallback; "
          "other = direct job index")
    print(f"{'field':>6}  {'name':<24} {'formula':<46} result")
    print("-" * 92)
    failures = 0
    for field_id, field in enumerate(FIELDS):
        bad = sum(
            gba.call(ACCESSOR, [index, 5, field_id]) !=
            read_field(rom, index, 5, field_id)
            for index in range(COUNT))
        failures += bad
        result = "116/116" if not bad else f"{COUNT - bad}/116"
        print(f"  {field_id:#04x}  {field.name:<24} "
              f"{field.formula:<46} {result}")
    print()
    print(f"{len(FIELDS)} fields, {len(FIELDS) * COUNT} executed reads, "
          f"{failures} mismatches")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
