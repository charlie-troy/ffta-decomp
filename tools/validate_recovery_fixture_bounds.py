"""Unsupported public recovery owners must reject before ROM reads or input."""
import argparse
import io
import json
from pathlib import Path
import time
from types import SimpleNamespace

from recovery_menu import RecoveryStateError
from recovery_runtime import drive_recovery
from recovery_receipt import validate_recovery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    checks = []
    def unexpected():
        raise AssertionError("unsupported owner reached engine access")
    for label, change, count, tactics in [
        ("wrong actor id", {"id": 0}, 1, True),
        ("unsupported job", {"job": 7}, 1, True),
        ("unsupported race", {"race": 2}, 1, True),
        ("different actor tile", {"x": 5}, 1, True),
        ("multiple player actors", {}, 2, True),
        ("missing policy", {}, 1, False),
    ]:
        owner = {"id": 6, "job": 2, "race": 1, "x": 4, "y": 10} | change
        probe = SimpleNamespace(key_write_log=[])
        runtime = SimpleNamespace(owner=owner, p=probe, s=SimpleNamespace(read_rom_bytes=unexpected),
                                  _pre_players=[None] * count, t0=time.time(), wall_timeout=10,
                                  _stop_check=lambda: False, _input_log=io.StringIO(),
                                  tactics=SimpleNamespace(policy={}) if tactics else None)
        journal = {}
        try:
            drive_recovery(runtime, journal)
        except RecoveryStateError:
            assert journal["raw_writes"] == [] and journal["transport"] == []
            assert runtime._input_log.getvalue() == ""
            validate_recovery(journal, [])
            checks.append(label)
        else:
            raise AssertionError("unsupported fixture reached action path")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"status": "pass", "scope": __doc__, "checks": checks}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS recovery bounds: {len(checks)} zero-input host controls")


if __name__ == "__main__":
    main()
