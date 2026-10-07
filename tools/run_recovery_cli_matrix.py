"""Sequential real CLI recovery acceptance cases; owned CLI cleanup per run.

Uses already verified disposable fixtures. Does not construct/edit RAM, send
keys, bypass guards or substitute a model for the public BattleRuntime.
STOP/manual/resume is a separate live gate. All binary fixtures remain local.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from recovery_menu import require
from validate_autobattle_runtime import validate


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--cure-state", required=True)
    parser.add_argument("--reserve-state", required=True)
    parser.add_argument("--disabled-state", required=True)
    args = parser.parse_args()
    require(Path(args.prefix).name == args.prefix and not any(c in args.prefix for c in (":", "/", "\\")), "prefix must be a filename")
    root = Path("outputs/autobattle")
    summary = root / (args.prefix + "-matrix.json")
    require(not summary.exists(), "matrix receipt must be new")
    cases = [("cure1", args.cure_state, "configs/tactics/healer.json", "accepted"),
             ("cure2", args.cure_state, "configs/tactics/healer.json", "accepted"),
             ("reserve", args.reserve_state, "configs/tactics/healer.json", "declined"),
             ("disabled", args.disabled_state, "configs/tactics/healer.json", "declined"),
             ("no-match-wait", args.cure_state, None, "declined"),
             ("no-match-none", args.cure_state, None, "unexecuted-wait")]
    for label, state, policy, outcome in cases:
        require(Path(state).is_file(), f"missing verified fixture {state}")
        require(not (root / f"{args.prefix}-{label}").exists(), "case output must be new")
        require(not (root / f"{args.prefix}-{label}.log").exists(), "case log must be new")
    result = {"scope": __doc__, "status": "partial", "cases": [],
              "limits": ["Bounded single-player self-Cure fixture only", "Does not close STOP/manual/resume or broader party A6 gates"]}
    pinned = None
    try:
        for label, state, policy, expected in cases:
            run_id = f"{args.prefix}-{label}"
            directory = root / run_id
            if policy is None:
                policy_file = root / f"{run_id}-policy.json"
                with policy_file.open("x", encoding="utf-8") as handle:
                    json.dump({"schema": "ffta-tactics-policy/2", "fallback": "none" if label.endswith("none") else "wait",
                               "observation": {"max_age_seconds": 3.0}, "assignments": {}}, handle, indent=2)
                    handle.write("\n")
                policy = str(policy_file)
            command = [sys.executable, "tools/run_autobattle.py", "--state", state,
                       "--tactics-policy", policy, "--bounded-self-cure", "--run-id", run_id,
                       "--max-turns", "1", "--wall-timeout", "150", "--on-stop", "kill", "--yes"]
            with (root / f"{run_id}.log").open("x", encoding="utf-8") as log:
                child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                try:
                    code = child.wait(timeout=240)
                except subprocess.TimeoutExpired:
                    (directory / "STOP").write_text("STOP: matrix child timeout\n", encoding="utf-8")
                    child.wait(timeout=90)  # child owns emulator cleanup
                    raise RuntimeError(f"public CLI exceeded matrix bound: {run_id}")
            require(code == 1, f"expected truthful bounded CLI exit1, got {code}")
            errors = validate(str(directory))
            require(not errors, "runtime receipt failed: " + str(errors))
            run = json.loads((directory / "run.json").read_text())
            require(run["inputs_unchanged"], "source/state/policy changed during execution")
            sources = {p: h for p, h in run["input_sha256"].items() if p.startswith("tools/")}
            if pinned is None:
                pinned = sources
            require(sources == pinned, "matrix runtime sources changed between cases")
            events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
            journal = next(e["recovery"] for e in events if e.get("recovery"))
            cure = journal["recovery"]
            require(cure["outcome"] == ("declined" if expected == "unexecuted-wait" else expected), "wrong Cure outcome")
            require(journal["status"] == ("unexecuted-wait" if expected == "unexecuted-wait" else "confirmed"), "wrong transaction status")
            require(run["turns"] == int(expected != "unexecuted-wait"), "wrong verified turn count")
            entry = {"run": run_id, "command": command, "status": "pass", "outcome": cure["outcome"],
                     "hp": [cure["before"]["hp"], cure["after"]["hp"]],
                     "mp": [cure["before"]["mp"], cure["after"]["mp"]],
                     "raw_writes": len(journal["raw_writes"]), "turns": run["turns"],
                     "later_enemy_ids": [r["actor"]["id"] for r in journal["continuations"]],
                     "metadata_sha256": {name: digest(directory / name) for name in ("run.json", "events.jsonl", "input-log.jsonl")}}
            if expected == "accepted":
                subprocess.run([sys.executable, "tools/validate_recovery_runtime.py", "--run", str(directory),
                                "--out", str(directory / "checks.json")], check=True)
                entry["checks_sha256"] = digest(directory / "checks.json")
            result["cases"].append(entry)
            print(f"PASS {run_id}: {entry['hp']} HP, {entry['mp']} MP, {entry['raw_writes']} raw writes", flush=True)
        result["status"] = "pass-bounded-cli-matrix"
        result["runtime_source_sha256"] = pinned
    except BaseException as exc:
        result["error"] = repr(exc)
        raise
    finally:
        summary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Public recovery matrix: {summary}")


if __name__ == "__main__":
    main()
