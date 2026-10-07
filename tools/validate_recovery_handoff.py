"""Check a source-pinned public recovery STOP, manual Wait and same-PID resume."""
import argparse
import copy
import json
from pathlib import Path

from recovery_menu import require
from validate_autobattle_runtime import validate

MASKS = {"A": 1, "B": 2, "UP": 0x40, "DOWN": 0x80}


def check(run, paused, events, ledger, manual, phase):
    require(paused["final_state"] == "paused" and paused["emulator_handoff"] == "left-running-for-player"
            and paused["inputs_unchanged"] and run["inputs_unchanged"], "source-pinned paused handoff missing")
    pid = paused["manual_handoff"]["pid"]
    require(run["resumed"] is True and run["previous_leg"] == paused
            and pid == run["emulator_pid"] == run["adopt"]["pid"] == manual["pid"]
            and run["adopt"]["match_receipt_handoff_pid"] and run["adopt"]["roster_guard_ok"], "same-PID adopt missing")
    require(run["turns"] >= 1 and any(e["kind"] == "turn" for e in events), "resume verified no turn")
    require(manual["status"] == "verified-manual-wait" and manual["stub_gameplay_writes"] == 0
            and len(manual["source_sha256"]) == 6, "manual command proof missing")
    require(manual["initial"]["state"] == phase and manual["facing"]["state"] == "facing"
            and (manual["initial"]["hp"], manual["initial"]["mp"])
            == (manual["facing"]["hp"], manual["facing"]["mp"]), "manual cancellation/Wait spent resources")
    require(manual["keys"] and manual["keys"][-1]["key"] == "A"
            and manual["keys"][-1]["before"]["state"] == "facing"
            and all(k["window"]["pid"] == pid and k["window"]["foreground_verified"] is True
                    for k in manual["keys"]), "manual keys not verified against owned window")
    later = manual["continuations"]
    require(len(later) == 2 and len({r["actor"]["id"] for r in later}) == 2
            and all(r["actor"]["side_bit"] is True and r["actor"]["tile"] == r["target_tile"]
                    and (r["player_after"]["hp"], r["player_after"]["mp"])
                    == (manual["facing"]["hp"], manual["facing"]["mp"]) for r in later),
            "manual Wait lacks independent continuation")
    journal = next(e["recovery"] for e in events if e.get("recovery"))
    family = journal["cure_events" if phase == "confirmation" else "wait_events"]
    require(not any(e.get("final") for e in family if e["event"] == "input_requested"), "STOP arrived after final request")
    require(len(journal["raw_writes"]) == (40 if phase == "confirmation" else 60)
            and journal["transport"][-1]["event"] == "trace_restored", "STOP raw count/restoration differs")
    stop = next(e["t"] for e in ledger if e["event"] == "stop_requested")
    resume = next(e["t"] for e in ledger if e["event"] == "resume")
    require(all(w["t"] <= stop for w in journal["raw_writes"]), "automation input after STOP")
    manual_log = [e for e in ledger if e["event"] == "manual_key_write"]
    require([e["val"] for e in manual_log] == [MASKS[k["key"]] for k in manual["keys"]]
            and all(stop < e["t"] < resume for e in manual_log), "manual channel/timeline differs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--phase", choices=("confirmation", "facing"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.run)
    require(not validate(str(root)), "runtime validator rejected handoff artifacts")
    run = json.loads((root / "run.json").read_text())
    paused = json.loads((root / "paused-run.json").read_text())
    events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    ledger = [json.loads(line) for line in (root / "input-log.jsonl").read_text().splitlines()]
    manual = json.loads((root / "manual-recovery.json").read_text())
    check(run, paused, events, ledger, manual, args.phase)
    rejected = []
    for name, mutate in [
        ("different adopted PID", lambda r, m: r["adopt"].update(pid=0)),
        ("different manual window", lambda r, m: m["keys"][0]["window"].update(pid=0)),
        ("unverified window focus", lambda r, m: m["keys"][0]["window"].update(foreground_verified=False)),
        ("stub gameplay input", lambda r, m: m.update(stub_gameplay_writes=1)),
        ("manual Wait did not continue", lambda r, m: m.update(continuations=[])),
        ("manual resource drift", lambda r, m: m["facing"].update(mp=0)),
        ("source changed during first leg", lambda r, m: r["previous_leg"].update(inputs_unchanged=False)),
        ("resumed without verified action", lambda r, m: r.update(turns=0)),
    ]:
        changed, altered = copy.deepcopy(run), copy.deepcopy(manual)
        mutate(changed, altered)
        try:
            check(changed, paused, events, ledger, altered, args.phase)
        except (ValueError, KeyError, TypeError):
            rejected.append(name)
        else:
            raise AssertionError(f"handoff mutation survived: {name}")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"status": "pass", "scope": __doc__, "run": args.run,
                                  "phase": args.phase, "pid": run["emulator_pid"], "rejections": rejected}, indent=2)
                      + "\n", encoding="utf-8", newline="\n")
    print(f"PASS public {args.phase} handoff: manual Wait, same-PID resume, {len(rejected)} rejected mutations")


if __name__ == "__main__":
    main()
