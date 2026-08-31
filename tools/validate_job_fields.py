"""Validate all 48 job-field formulas and the +0x05 redirect protocol."""
import argparse

from emulate import Gba
from job_fields import ACCESSOR, COUNT, FIELDS, STRIDE, TABLE, read_field

MORPH_FAMILY_INDEX = 0x080C9428


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    args = parser.parse_args(argv)
    rom = open(args.rom, "rb").read()
    gba = Gba(args.rom)

    failures = []
    marker_population = {value: 0 for value in (0, 0xFF)}
    for index in range(COUNT):
        marker = rom[TABLE + index * STRIDE + 0x05]
        marker_population[marker] = marker_population.get(marker, 0) + 1

    # Fallback 5 is an ordinary record. The four 0xff proxy records must read
    # every non-marker field from it; the other 112 records ignore fallback.
    mismatches = []
    for index in range(COUNT):
        for field_id in range(len(FIELDS)):
            got = gba.call(ACCESSOR, [index, 5, field_id])
            want = read_field(rom, index, 5, field_id)
            if got != want:
                mismatches.append((index, field_id, got, want))
    formulas_ok = not mismatches and marker_population == {0: 112, 0xFF: 4}
    print(f"1. all field formulas: {'OK' if formulas_ok else 'FAIL'} "
          f"({COUNT * len(FIELDS)} reads; markers={marker_population}; "
          f"mismatches={len(mismatches)})")
    if not formulas_ok:
        failures.append("field formulas")

    # Causal resistance test: retail happens to keep every slot's high bit
    # clear and slots 1/2 equal. Distinct synthetic values prove that field
    # ids 0x0e..0x15 really expose all eight independent 3-bit slots.
    packed = sum(value << (3 + value * 3) for value in range(8))
    gba.uc.mem_write(0x08000000 + TABLE + 0x12, packed.to_bytes(4, "little"))
    resistance_values = tuple(
        gba.call(ACCESSOR, [0, 5, field_id])
        for field_id in range(0x0E, 0x16))
    resistance_ok = resistance_values == tuple(range(8))
    print(f"2. eight independent resistance slots: "
          f"{'OK' if resistance_ok else 'FAIL'} ({resistance_values})")
    if not resistance_ok:
        failures.append("resistance slots")

    # Retail uses only zero/0xff markers. Patch an ordinary record to a direct
    # index to execute the third code path, then compare every field against
    # record 7. Field 2 intentionally returns the marker itself.
    marker_addr = 0x08000000 + TABLE + 0x05
    original_marker = rom[TABLE + 0x05]
    gba.uc.mem_write(marker_addr, bytes([7]))
    direct_values = [gba.call(ACCESSOR, [0, 5, field_id])
                     for field_id in range(len(FIELDS))]
    direct_want = [7 if field_id == 2 else read_field(rom, 7, 5, field_id)
                   for field_id in range(len(FIELDS))]
    gba.uc.mem_write(marker_addr, bytes([original_marker]))
    direct_ok = direct_values == direct_want
    print(f"3. synthetic direct redirect: {'OK' if direct_ok else 'FAIL'} "
          "(+0x05=7 selects record 7 for 47 fields; field 2 returns 7)")
    if not direct_ok:
        failures.append("direct redirect")

    # +0x31 is not dead data: its only accessor consumer tests bit 0 before
    # mapping supported monster jobs to the compact 0..19 morph-family range.
    unit = 0x02001000
    morph_results = {}
    morph_ok = True
    for index in range(COUNT):
        marker = rom[TABLE + index * STRIDE + 0x05]
        if marker:
            continue
        gba.uc.mem_write(unit, bytes(0x108))
        gba.write8(unit + 0x05, index)
        gba.write8(unit + 0x07, index)
        got = gba.call(MORPH_FAMILY_INDEX, [unit])
        flags = rom[TABLE + index * STRIDE + 0x31]
        if flags & 1:
            expected = ((index - 44) if 44 <= index <= 57 else
                        (index - 48) if 62 <= index <= 67 else 0xFFFFFFFF)
        else:
            expected = 0xFFFFFFFF
        morph_ok &= got == expected
        if index in (44, 58, 62, 90):
            morph_results[index] = (got if got < 0x80000000
                                    else got - 0x100000000)
    print(f"4. morph-family flag: {'OK' if morph_ok else 'FAIL'} "
          f"(Goblin/Toughskin/Red Panther/New Kid={morph_results})")
    if not morph_ok:
        failures.append("morph-family flag")

    print()
    if failures:
        print(f"FAILED: {len(failures)} — {', '.join(failures)}")
        return 1
    print("PASS: 4/4 job-field checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
