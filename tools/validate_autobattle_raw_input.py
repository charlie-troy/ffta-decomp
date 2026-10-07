"""Adversarial raw input ledger checks through the real run receipt validator."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

from validate_autobattle_runtime import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--validator-source")
    args = parser.parse_args()
    validator = validate
    if args.validator_source:
        spec = importlib.util.spec_from_file_location("historical_validator", args.validator_source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        validator = module.validate
    root = Path(args.out_root)
    root.mkdir(parents=True, exist_ok=True)
    checks = []
    raw = {"event": "key_write", "t": 5, "val": 1, "hits": 1, "manual": False}

    def case(name, writes, *, resumed=False, reject=False, terminal_only=False):
        directory = root / name
        directory.mkdir(exist_ok=True)
        run = {"schema": "a3-run/2", "run_id": name, "turns": 0, "mode": "retail-ai",
               "final_state": "paused", "emulator_handoff": "left-running-for-player"}
        events = [{"t": 0, "kind": "start", "state": "running", "scenario": "host-raw",
                   "input_log": "input-log.jsonl"},
                  {"t": 10, "kind": "stop", "state": "paused", "scenario": "host-raw", "note": "STOP"}]
        ledger = [{"event": "stop_requested", "t": 9}]
        if resumed:
            run["resumed"] = True
            events.extend([{"t": 20, "kind": "start", "state": "running", "scenario": "host-raw",
                            "input_log": "input-log.jsonl", "note": "resume: same owned battle"},
                           {"t": 30, "kind": "stop", "state": "paused", "scenario": "host-raw", "note": "STOP"}])
            ledger.extend([{"event": "resume", "t": 20}, {"event": "stop_requested", "t": 29}])
        if terminal_only:
            run["final_state"] = "stalled"
            events[-1]["state"] = "stalled"
            ledger = [r for r in ledger if r["event"] != "stop_requested" or resumed and r["t"] == 9]
        ledger.extend(writes)
        (directory / "run.json").write_text(json.dumps(run), encoding="utf-8")
        (directory / "events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in events), encoding="utf-8")
        (directory / "input-log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ledger), encoding="utf-8")
        errors = validator(str(directory))
        assert bool(errors) == reject, (name, errors, "expected rejection" if reject else "expected pass")
        checks.append({"case": name, "expected": "rejected" if reject else "accepted", "errors": errors})

    case("valid-raw", [raw])
    case("raw-after-stop", [{**raw, "t": 9.5}], reject=True)
    case("raw-after-terminal", [{**raw, "t": 11}], reject=True)
    case("valid-terminal-without-stop-file", [raw], terminal_only=True)
    case("raw-after-terminal-without-stop-file", [{**raw, "t": 11}], terminal_only=True, reject=True)
    case("aborted-label-cannot-hide-raw-write", [{**raw, "t": 11, "aborted": True}], reject=True)
    case("false-completion-cannot-hide-raw-write", [{**raw, "t": 11, "completed": False}], reject=True)
    case("raw-handoff-gap", [{**raw, "t": 15}], resumed=True, reject=True)
    case("raw-valid-resumed-leg", [{**raw, "t": 25}], resumed=True)
    case("raw-resumed-stop", [{**raw, "t": 29.5}], resumed=True, reject=True)
    case("raw-resumed-terminal", [{**raw, "t": 31}], resumed=True, reject=True)
    case("raw-resumed-terminal-without-stop-file", [{**raw, "t": 31}], resumed=True, terminal_only=True, reject=True)
    case("legacy-resumed-terminal", [{"event": "press", "t": 31, "hits": 5}], resumed=True, reject=True)
    case("manual-detached-input", [{"event": "manual_key_write", "t": 15, "val": 1}])
    for field, value in [("manual", True), ("t", None), ("t", "late"), ("t", float("nan")),
                         ("val", 1024), ("hits", 0)]:
        changed = copy.deepcopy(raw)
        changed[field] = value
        case(f"malformed-{field}-{str(value)}", [changed], reject=True)
    (root / "checks.json").write_text(json.dumps({"status": "pass", "scope": "host artifact validation only",
                                                 "checks": checks}, indent=2) + "\n", encoding="utf-8")
    print(f"PASS raw input validation: {len(checks)} cases")


if __name__ == "__main__":
    main()
