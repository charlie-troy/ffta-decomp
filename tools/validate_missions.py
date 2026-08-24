"""Validate the named mission fields by executing the retail ROM's code.

    python tools/validate_missions.py baserom.gba

This is intentionally independent of the CSV writer. It checks the raw table,
the mission property accessor, and the function that applies clan progression
rewards to the save-data structure.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emulate import Gba

BASE = 0x0855AE4C
STRIDE = 0x46
COUNT = 512
ACCESSOR = 0x080CE4DC
APPLY_CLAN_REWARD = 0x08046850
CLAN_STATE = 0x020021B4

# Accessor properties 0x21..0x29 are direct loads of +0x2a..+0x32.
TRACKS = (
    ("clan", 0x2A, 0x21),
    ("combat", 0x2B, 0x22),
    ("magic", 0x2C, 0x23),
    ("appraise", 0x2D, 0x24),
    ("gather", 0x2E, 0x25),
    ("smithing", 0x2F, 0x26),
    ("craft", 0x30, 0x27),
    ("negotiate", 0x31, 0x28),
    ("track", 0x32, 0x29),
)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rom")
    args = p.parse_args(argv)

    rom = open(args.rom, "rb").read()
    gba = Gba(args.rom)
    failures = []

    ids_ok = all(
        int.from_bytes(
            rom[BASE - 0x08000000 + i * STRIDE:
                BASE - 0x08000000 + i * STRIDE + 2], "little"
        ) == i
        for i in range(COUNT)
    )
    print(f"1. mission id echo: {'OK' if ids_ok else 'FAIL'} ({COUNT} entries)")
    if not ids_ok:
        failures.append("mission id echo")

    accessor_checks = 0
    accessor_ok = True
    for i in range(COUNT):
        entry = BASE - 0x08000000 + i * STRIDE
        for _name, off, prop in TRACKS:
            got = gba.call(ACCESSOR, [i, prop])
            want = rom[entry + off]
            accessor_checks += 1
            if got != want:
                accessor_ok = False
                failures.append(
                    f"accessor mission {i} prop {prop:#x}: {got} != {want}"
                )
                break
        if not accessor_ok:
            break
    print(
        f"2. clan reward properties: {'OK' if accessor_ok else 'FAIL'} "
        f"({accessor_checks} executed reads)"
    )

    flow_ok = True
    flow_details = []
    for index, (name, off, _prop) in enumerate(TRACKS):
        sample = next(
            (
                (i, rom[BASE - 0x08000000 + i * STRIDE + off])
                for i in range(COUNT)
                if 0 < rom[BASE - 0x08000000 + i * STRIDE + off] < 100
            ),
            None,
        )
        if sample is None:
            flow_ok = False
            failures.append(f"no non-boundary sample for {name}")
            continue
        mission, reward = sample
        gba.reset_ram()
        level_addr = CLAN_STATE + index * 2
        gba.write8(level_addr, 1)
        gba.write8(level_addr + 1, 0)
        gba.call(APPLY_CLAN_REWARD, [BASE + mission * STRIDE, 0, index, 1])
        got = tuple(gba.uc.mem_read(level_addr, 2))
        want = (1, reward)
        flow_details.append(f"{name}=mission {mission}/{reward}")
        if got != want:
            flow_ok = False
            failures.append(f"{name} apply path: {got} != {want}")
    print(
        f"3. clan reward application: {'OK' if flow_ok else 'FAIL'} "
        f"({'; '.join(flow_details)})"
    )

    def reward(i):
        entry = BASE - 0x08000000 + i * STRIDE
        return rom[entry + 0x33] * 200, rom[entry + 0x34] * 10

    anchors_ok = reward(3) == (600, 40) and reward(25) == (28600, 80)
    print(
        "4. gil/AP anchors: "
        f"{'OK' if anchors_ok else 'FAIL'} "
        f"(Herb Picking {reward(3)}, Over The Hill {reward(25)})"
    )
    if not anchors_ok:
        failures.append("gil/AP anchors")

    if failures:
        print("\nFAIL:")
        for failure in failures[:10]:
            print(f"  - {failure}")
        return 1
    print("\n4/4 mission checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
