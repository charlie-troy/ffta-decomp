"""Validate the FFTA item table against the retail executable.

    python tools/validate_items.py baserom.gba
"""
import argparse
import contextlib
import csv
import hashlib
import io
import os
import tempfile

from emulate import Gba, ROM
from item_table import (BASE, COLUMNS, COUNT, FLAG_BITS, STRIDE, cmd_apply,
                        cmd_dump, read)

ACCESSOR = 0x080CA7A4
RESOURCE_RESOLVER = 0x08021004
PALETTE_GETTER = 0x08021E60
PALETTE_SETTER = 0x08021E64
PRICE_READER = 0x080CBC14
RESOURCE_TABLE = 0x08390E44


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom")
    args = parser.parse_args(argv)
    rom = open(args.rom, "rb").read()
    gba = Gba(args.rom)
    failures = []

    # Every property must remain a plain load from the documented raw offset.
    props = [column for column in COLUMNS if column[0] not in
             ("sell_value", "category", "effect_0", "effect_1", "effect_2")]
    mismatches = []
    for item_id in range(COUNT):
        for prop_id, (_, offset, width) in enumerate(props):
            got = gba.call(ACCESSOR, [item_id, prop_id])
            expected = read(rom, item_id, offset, width)
            if got != expected:
                mismatches.append((item_id, prop_id, got, expected))
    ok = not mismatches
    print(f"1. accessor layout: {'OK' if ok else 'FAIL'} "
          f"({COUNT * len(props)} executed loads)")
    if not ok:
        failures.append("accessor layout")

    palette_values = {read(rom, i, 0x0D, 1) for i in range(1, COUNT)}
    graphics_values = {read(rom, i, 0x0E, 1) for i in range(1, COUNT)}
    object_addr = 0x02001000
    icon_ok = palette_values == {0, 1, 2} and len(graphics_values) == 62
    for item_id in range(1, COUNT):
        palette = gba.call(ACCESSOR, [item_id, 8])
        graphics = gba.call(ACCESSOR, [item_id, 9])
        expected_resource = int.from_bytes(
            rom[RESOURCE_TABLE - ROM + graphics * 4:
                RESOURCE_TABLE - ROM + graphics * 4 + 4], "little")
        icon_ok &= gba.call(RESOURCE_RESOLVER, [graphics, 0]) == expected_resource
        gba.write8(object_addr + 0x1D, 0xFF)
        gba.call(PALETTE_SETTER, [object_addr, palette])
        icon_ok &= gba.call(PALETTE_GETTER, [object_addr]) == palette
    print(f"2. icon resource path: {'OK' if icon_ok else 'FAIL'} "
          f"(375 items; 62 graphics ids; palettes {sorted(palette_values)})")
    if not icon_ok:
        failures.append("icon resource path")

    # The renderer takes object +0x1d through the getter, then adds it to the
    # high nibble of OAM attr2 (the four-bit OBJ palette bank).
    oam_palette_anchor = bytes.fromhex("697909090f98091809016a790f20")
    anchor_ok = (rom[0x21E60:0x21E68] == bytes.fromhex("407f704741777047") and
                 rom[0x1686:0x1694] == oam_palette_anchor)
    print(f"3. OAM palette-bank chain: {'OK' if anchor_ok else 'FAIL'} "
          "(object +0x1d -> attr2 bits 12-15)")
    if not anchor_ok:
        failures.append("OAM palette-bank chain")

    counts = {name: sum(bool(read(rom, i, 0x0C, 1) & (1 << bit))
                        for i in range(1, COUNT))
              for bit, name in FLAG_BITS}
    expected_counts = {"dual_wield": 139, "one_handed": 215,
                       "two_handed": 22, "discount_eligible": 137,
                       "shop_early": 46, "shop_mid": 96,
                       "shop_late": 139, "special_pool": 31}
    flags_ok = counts == expected_counts
    print(f"4. flag populations: {'OK' if flags_ok else 'FAIL'} ({counts})")
    if not flags_ok:
        failures.append("flag populations")

    # Force a 2% discount in the blank-RAM harness. Toggling only bit 3 must
    # switch the Shortsword from its discounted price back to full buy value.
    gba.reset_ram()
    gba.write8(0x020021B4, 10)
    flag_addr = ROM + BASE + STRIDE + 0x0C
    original_flag = gba.uc.mem_read(flag_addr, 1)[0]
    discounted = gba.call(PRICE_READER, [0, 1])
    gba.write8(0x020021B4, 10)
    gba.write8(flag_addr, original_flag & ~0x08)
    full_price = gba.call(PRICE_READER, [0, 1])
    discount_ok = discounted == 294 and full_price == 300
    print(f"5. discount flag execution: {'OK' if discount_ok else 'FAIL'} "
          f"(Shortsword {discounted} with bit 3, {full_price} without)")
    if not discount_ok:
        failures.append("discount flag execution")

    # Retail shop-list code selects bit 4, 5, or 6 from progression stage;
    # its direct reader is at 0x080CBE2E. The special-pool generator combines
    # the chosen tier with bit 7 at 0x080D2136/0x080D2180.
    shop_anchor_ok = (rom[0xCBDE8:0xCBDFE] ==
                      bytes.fromhex("10210391012802d12020039003e0012801d940210391") and
                      rom[0xD2136:0xD2140] ==
                      bytes.fromhex("087b2840002800d00134"))
    print(f"6. shop/pool flag readers: {'OK' if shop_anchor_ok else 'FAIL'} "
          "(tier bits 4-6; special bit 7)")
    if not shop_anchor_ok:
        failures.append("shop/pool flag readers")

    with tempfile.TemporaryDirectory(prefix="ffta-item-validation-") as temp:
        csv_path = os.path.join(temp, "items.csv")
        roundtrip_path = os.path.join(temp, "roundtrip.gba")
        edit_csv = os.path.join(temp, "edit.csv")
        edit_rom = os.path.join(temp, "edit.gba")
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_dump(args.rom, csv_path)
            cmd_apply(args.rom, csv_path, roundtrip_path)
        roundtrip_ok = hashlib.sha256(open(roundtrip_path, "rb").read()).digest() == \
            hashlib.sha256(rom).digest()
        with open(edit_csv, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["id", "icon_palette", "icon_graphics"])
            writer.writerow([1, 2, 125])
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_apply(args.rom, edit_csv, edit_rom)
        edited = open(edit_rom, "rb").read()
        edit_gba = Gba(edit_rom)
        edit_ok = (edit_gba.call(ACCESSOR, [1, 8]) == 2 and
                   edit_gba.call(ACCESSOR, [1, 9]) == 125 and
                   sum(a != b for a, b in zip(rom, edited)) == 2)
    print(f"7. unedited CSV round-trip: {'OK' if roundtrip_ok else 'FAIL'} "
          "(byte-identical)")
    if not roundtrip_ok:
        failures.append("unedited CSV round-trip")
    print(f"8. icon edit round-trip: {'OK' if edit_ok else 'FAIL'} "
          "(two fields, two changed bytes, accessor-visible)")
    if not edit_ok:
        failures.append("icon edit round-trip")

    print()
    if failures:
        print(f"FAILED: {len(failures)} — {', '.join(failures)}")
        return 1
    print("PASS: 8/8 item-table checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
