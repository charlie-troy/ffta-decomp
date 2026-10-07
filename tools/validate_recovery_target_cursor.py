"""Execute the target-acceptance coordinate-copy fragment on synthetic RAM.

This does not execute the surrounding acceptance branch or prove live target
legality. The UI cursor and acceptance-coordinate structure are distinct.
"""
import argparse
import hashlib
import json
from pathlib import Path

from emulate import Gba


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    gba = Gba(args.rom)
    processor = 0x02030000
    cases = []
    for cursor, display in [([4, 10], [4, 10]), ([5, 10], [5, 10]),
                            ([5, 10], [4, 10]), ([4, 10], [5, 10])]:
        gba.uc.mem_write(processor, bytes(0x200))
        gba.uc.mem_write(0x0200F3B8, bytes([cursor[0], 0, 0, 0, cursor[1], 0]))
        gba.uc.mem_write(0x0200FFC9, bytes(display))
        gba.run_range(0x080B76FC, 0x080B7710, {"r8": processor})
        copied = list(gba.uc.mem_read(processor + 0x109, 2))
        assert copied == cursor, (cursor, display, copied)
        cases.append({"acceptance_coordinates": cursor, "display_cursor": display,
                      "copied_processor_coordinates": copied})
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": __doc__,
                              "rom_sha256": hashlib.sha256(gba.rom).hexdigest(),
                              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                              "fragment": [0x080B76FC, 0x080B7710], "cases": cases,
                              "live_coordinate_agreement": "unknown"}, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print("PASS 4 ROM coordinate-copy cases; live coordinate agreement unknown")


if __name__ == "__main__":
    main()
