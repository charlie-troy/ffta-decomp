"""Execute target-table ROM fragments on synthetic wrappers, without gameplay.

This proves index and pointer-copy semantics only. It does not prove which
live wrappers are legal Cure targets or the meaning of a menu peer pointer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from emulate import Gba


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    gba = Gba(args.rom)
    processor, first, second = 0x02030000, 0x02032000, 0x02032100
    table = processor + 0x4C
    for wrapper, tile in [(first, (4, 10)), (second, (5, 10))]:
        gba.uc.mem_write(wrapper, bytes(0x30))
        gba.uc.mem_write(wrapper + 8, struct.pack("<h", tile[0] << 5))
        gba.uc.mem_write(wrapper + 12, struct.pack("<h", tile[1] << 5))
    cases = []
    for label, mask, cursor, count, index, expected_result, expected_index in [
        ("no-input", 0, (4, 10), 2, 0, 0, 0),
        ("next-from-first", 0x100, (4, 10), 2, 0, 1, 1),
        ("next-wrap", 0x100, (5, 10), 2, 1, 1, 0),
        ("previous-from-second", 0x200, (5, 10), 2, 1, 1, 0),
        ("previous-wrap", 0x200, (4, 10), 2, 0, 1, 1),
        ("empty-list", 0x100, (4, 10), 0, 0, 0, 0),
    ]:
        gba.uc.mem_write(processor, bytes(0x200))
        gba.write32(processor + 0x50, first)
        gba.write32(processor + 0x54, second)
        gba.write8(processor + 0xA1, index)
        gba.write8(processor + 0xA2, count)
        result = gba.call(0x080B50F0, (table, mask, *cursor))
        selected = bytes(gba.uc.mem_read(processor + 0xA1, 1))[0]
        assert (result, selected) == (expected_result, expected_index), (label, result, selected)
        cases.append({"case": label, "result": result, "index": selected})
    copies = []
    for index, expected in enumerate((first, second)):
        gba.write8(processor + 0xA1, index)
        gba.run_range(0x080B752C, 0x080B7542, {"r8": processor})
        assert gba.read32(processor + 0xC) == gba.read32(processor + 0x10) == expected
        copies.append({"index": index, "wrapper": expected, "destination_offsets": [12, 16]})
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": __doc__,
                              "rom_sha256": hashlib.sha256(gba.rom).hexdigest(),
                              "source_sha256": {"tools/validate_recovery_target_table.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                              "selection_cases": cases, "pointer_copy_cases": copies,
                              "live_target_legality": "unknown"}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("PASS 6 ROM target-index cases and 2 wrapper-copy fragments; live legality unknown")


if __name__ == "__main__":
    main()
