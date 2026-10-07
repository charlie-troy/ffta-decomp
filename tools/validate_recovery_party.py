"""Replay a captured A6.2 baseline and reject identity/resource mutations.

Retained-reader proof only; no modal target or live Cure acceptance.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from fixture_guard import ROSTER, STRIDE
from recovery_menu import MEMBERS, RecoveryStateError
from recovery_party import pin_party


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    directory = Path(args.capture)
    doc = json.loads((directory / "baseline.json").read_text())
    assert doc["status"] == "pass-pre-targeting-baseline" and doc["inputs_unchanged"]
    assert doc["gameplay_keys"] == doc["gameplay_writes"] == doc["fixture_writes"] == []
    for name, digest in doc["capture_sha256"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest, name
    for path, digest in doc["source_sha256"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
    roster = (directory / f"{ROSTER:08x}.bin").read_bytes()
    members = (directory / f"{MEMBERS:08x}.bin").read_bytes()
    rows = doc["expected_party"]
    def read_name(address):
        return (directory / f"name-{address:08x}.bin").read_bytes()
    assert pin_party(roster, members, rows, read_name) == doc["party"]
    rejected = []
    def reject(label, r=roster, m=members, expected=rows, reader=read_name):
        try:
            pin_party(r, m, expected, reader)
        except (RecoveryStateError, KeyError):
            rejected.append(label)
        else:
            raise AssertionError("accepted mutation: " + label)
    reject("short-roster", r=roster[:-1])
    reject("short-members", m=members[:-1])
    reject("missing-ally", expected=rows[:1])
    reject("short-name", reader=lambda address: b"x")
    for pin in doc["party"]:
        offset = pin["canonical"] - MEMBERS
        for label, field, value in [("wrong-name", 0, 0), ("wrong-id", 0x104, 42),
                                    ("job-drift", 7, 6), ("race-drift", 6, 2),
                                    ("tile-drift", 0xF6, 63), ("hp-drift", 0x18, 1),
                                    ("mp-drift", 0x1C, 1)]:
            changed = bytearray(members)
            changed[offset + field] = value
            reject(f"{pin['id']}-{label}", m=bytes(changed))
        # Coherent mirror/canonical corruption cannot be excused by agreement.
        for label, field, data in [("ko", 0x18, b"\x00\x00"),
                                   ("enemy-side", 0x28, b"\x00\x80"),
                                   ("unaffiliated", 0x28, b"\x00\x10"),
                                   ("hp-over-max", 0x18, b"\xff\xff"),
                                   ("mp-over-max", 0x1C, b"\xff\xff"),
                                   ("tile-outside", 0xF6, b"\x40"),
                                   ("wrong-job", 7, b"\x06")]:
            changed, mirrored = bytearray(members), bytearray(roster)
            changed[offset+field:offset+field+len(data)] = data
            base = pin["slot"] * STRIDE + field
            mirrored[base:base+len(data)] = data
            reject(f"{pin['id']}-coherent-{label}", r=bytes(mirrored), m=bytes(changed))
        # An unused canonical record cloning either identifier must reject.
        for label, field, width in [("name-alias", 0, 4), ("id-alias", 0x104, 1)]:
            changed = bytearray(members)
            spare = next(i * STRIDE for i in range(14)
                         if MEMBERS + i * STRIDE not in {p["canonical"] for p in doc["party"]})
            changed[spare+field:spare+field+width] = members[offset+field:offset+field+width]
            reject(f"{pin['id']}-{label}", m=bytes(changed))
    aliased = copy.deepcopy(rows)
    aliased[1] = copy.deepcopy(aliased[0])
    reject("same-job-party-alias", expected=aliased)
    result = {"status": "pass", "scope": __doc__, "capture": str(directory),
              "baseline_sha256": hashlib.sha256((directory / "baseline.json").read_bytes()).hexdigest(),
              "canonical_joins": 2, "mutations_rejected": rejected,
              "target_identity": "unknown; no targeting entered"}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS two pre-targeting joins; {len(rejected)} rejected mutations")


if __name__ == "__main__":
    main()
