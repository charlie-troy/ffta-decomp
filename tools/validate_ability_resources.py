"""Compare the MP reader to executed retail ROM code, without gameplay claims."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from unicorn.arm_const import UC_ARM_REG_PC
from ability_resources import effective_mp_cost
from ability_table import COUNT
from emulate import Gba, STOP


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rom = Path(args.rom).read_bytes()
    if hashlib.sha1(rom).hexdigest() != "4ac05441f4de70a4ec3dd932116346c61b8783d9":
        parser.error("requires the supported retail USA ROM")
    gba = Gba(args.rom)
    cases, failures = [], []
    # Real race-table entries with numeric support effects 10 (halve),
    # 4 (double), and 7 (unchanged). No support-name mapping is claimed.
    for label, race, support in [("plain", 1, 0), ("human-effect10", 1, 31),
                                  ("moogle-effect10", 2, 74), ("viera-effect4", 4, 30),
                                  ("numou-effect4", 5, 52), ("unrelated-effect7", 1, 32)]:
        unit = bytearray(0x108)
        unit[6], unit[0x3B] = race, support
        gba.uc.mem_write(0x02000400, bytes(unit))
        for ability in range(COUNT):
            engine = gba.call(0x0812ED98, [0x02000400, ability])
            actual = effective_mp_cost(rom, ability, unit)
            passed = engine == actual and gba.uc.reg_read(UC_ARM_REG_PC) == STOP
            if not passed:
                failures.append({"profile": label, "ability": ability,
                                 "engine": engine, "reader": actual})
        cases.append({"profile": label, "race": race, "support_index": support,
                      "abilities": COUNT})
    for ability in range(COUNT):
        engine = gba.call(0x0812ED98, [0, ability])
        if engine != effective_mp_cost(rom, ability, None) or gba.uc.reg_read(UC_ARM_REG_PC) != STOP:
            failures.append({"profile": "null-unit", "ability": ability})
    # Reject missing facts instead of silently inventing a resource cost.
    invalid = [(rom, -1, None), (rom, COUNT, None), (rom, True, None),
               (b"", 1, None), (rom, 1, b""),
               (rom, 1, bytes([0] * 6 + [255] + [0] * 52 + [1])),
               (rom, 1, bytes([0] * 6 + [1] + [0] * 52 + [255]))]
    for i, params in enumerate(invalid):
        try:
            effective_mp_cost(*params)
        except ValueError:
            continue
        failures.append({"invalid_control": i})
    result = {"scope": "executed retail function on constructed unit records; not live availability",
              "rom_sha1": hashlib.sha1(rom).hexdigest(), "profiles": cases,
              "engine_comparisons": COUNT * 7, "invalid_controls": len(invalid),
              "failures": failures, "status": "pass" if not failures else "fail"}
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"MP cost: {COUNT * 7} engine comparisons, {len(invalid)} invalid controls; {result['status']}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
