"""Retained scoped recovery STOP evidence; no public CLI handoff claim."""
import argparse
import copy
import json
from pathlib import Path

from recovery_menu import require


def validate(run, state):
    require(run["status"] == "paused" and "stop_input_t" in run, "STOP not observed")
    raw, ledger, keys = run["key_writes"], run["modal_raw_writes"], run["keys"]
    require(raw and ledger and keys, "missing delivered input evidence")
    require([{k: v for k, v in w.items() if k != "event"} for w in ledger] == raw
            and all(w["event"] == "key_write" for w in ledger), "modal raw ledger differs")
    masks = {"A": 1, "B": 2, "DOWN": 128, "UP": 64}
    require([w["val"] for w in raw] == [masks[k["key"]] for k in keys for _ in range(k["hits"])]
            and all(k["hits"] > 0 for k in keys), "keys/raw delivery differs")
    require(all(not w["manual"] and w["t"] <= run["stop_input_t"] for w in raw), "input after STOP")
    require(run["phases"][-1]["guarded_menu"]["state"] == state, "STOP at wrong modal")
    events = run["executor_events"] + run.get("finish_events", [])
    requests = [e for e in events if e["event"] == "input_requested"]
    require([e["key"] for e in requests] == [k["key"] for k in keys], "request/key mismatch")
    require(sum(e.get("final", False) for e in requests) == (state == "facing"),
            "final input escaped STOP boundary")
    require(any(e["event"] == "stop_requested" for e in events) or "STOP" in run["error"], "missing STOP reason")
    transport = run["modal_transport"]
    require(transport[-1]["event"] == "trace_restored" and transport[-1]["write_count"] == len(raw)
            and sum(e["event"] == "trace_restored" for e in transport) == 1, "cleanup not restored or input after cleanup")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--state", choices=["confirmation", "facing"], required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run = json.loads((Path(args.capture) / "probe.json").read_text(encoding="utf-8"))
    validate(run, args.state)
    rejected = []

    def append_write(receipt):
        raw = copy.deepcopy(receipt["key_writes"][-1])
        raw["t"] = receipt["stop_input_t"] + 1
        receipt["key_writes"].append(raw)
        receipt["modal_raw_writes"].append({"event": "key_write", **raw})
        receipt["keys"].append({"key": receipt["keys"][-1]["key"], "hits": 1})
        segment = receipt.get("finish_events", receipt["executor_events"])
        segment.append({"event": "input_requested", "key": receipt["keys"][-1]["key"], "final": False})
        receipt["modal_transport"][-1]["write_count"] = len(receipt["key_writes"])

    for name, mutate in [
        ("missing raw input", lambda r: r.update(key_writes=[])),
        ("missing modal ledger", lambda r: r.update(modal_raw_writes=[])),
        ("post-STOP raw input", append_write),
        ("missing tracing restoration", lambda r: r["modal_transport"].pop()),
        ("final confirmation escaped", lambda r: r["executor_events"].append({"event": "input_requested", "key": "A", "final": True})),
        ("wrong STOP modal", lambda r: r["phases"][-1]["guarded_menu"].update(state="command")),
        ("missing stop timestamp", lambda r: r.pop("stop_input_t")),
    ]:
        changed = copy.deepcopy(run)
        mutate(changed)
        try:
            validate(changed, args.state)
        except (ValueError, KeyError, TypeError, IndexError):
            rejected.append(name)
        else:
            raise AssertionError(f"mutation survived: {name}")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"status": "pass", "scope": __doc__, "capture": args.capture,
                                 "state": args.state, "keys": len(run["keys"]), "raw_writes": len(run["key_writes"]),
                                 "rejected": rejected}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS scoped recovery STOP at {args.state}: {len(rejected)} rejected mutations")


if __name__ == "__main__":
    main()
