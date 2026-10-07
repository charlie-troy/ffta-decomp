"""A resumed runner must start after manual-channel input as well as events."""
import argparse
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from autobattle_runtime import BattleRuntime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    checks = []
    for event_t, manual_t in [(10, 40), (40, 10), (10, 10)]:
        with tempfile.TemporaryDirectory(prefix="ffta-resume-clock-") as directory:
            root = Path(directory)
            (root / "events.jsonl").write_text(json.dumps({"t": event_t}) + "\n", encoding="utf-8")
            (root / "input-log.jsonl").write_text(json.dumps({"event": "manual_key_write", "val": 1, "t": manual_t}) + "\n", encoding="utf-8")
            runtime = BattleRuntime(SimpleNamespace(g=None), {}, "host", directory, resume=True, verbose=False)
            try:
                records = [json.loads(line) for line in (root / "input-log.jsonl").read_text().splitlines()]
                assert records[-1]["event"] == "resume"
                assert records[-1]["t"] >= max(event_t, manual_t) + 1
                checks.append({"event_t": event_t, "manual_t": manual_t, "resume_t": records[-1]["t"]})
            finally:
                runtime._input_log.close()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"status": "pass", "scope": __doc__, "checks": checks}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS resume clock: {len(checks)} host timeline checks")


if __name__ == "__main__":
    main()
