"""Validate retained bounded policy-Cure receipts; this does not run gameplay."""
import argparse
import copy
import json
from pathlib import Path

from recovery_executor import CURE
from tactics_policy import evaluate, validate_policy


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(run, outcome="accepted"):
    require(run.get("status") == "observed", "run did not finish observations")
    recovery = run["recovery"]
    require(recovery["outcome"] == outcome, "wrong outcome")
    events = run["executor_events"]
    requests = [e for e in events if e["event"] == "input_requested"]
    delivered = [e for e in events if e["event"] == "input_delivered"]
    require(requests and len(requests) == len(delivered), "missing or ambiguous input log")
    require([e["key"] for e in requests] == [e["key"] for e in delivered]
            == [e["key"] for e in run["keys"]], "input logs disagree")
    require(all(e["hits"] > 0 for e in delivered), "undelivered input")
    require(len(run.get("key_writes", [])) == sum(e["hits"] for e in delivered),
            "raw key write count differs")
    require(not any(e["event"] == "stop_requested" for e in events)
            and "stop_requested" not in run, "terminal run contains STOP")
    before, after = recovery["before"], recovery["after"]
    owner = run["owner"]
    require(before["state"] == after["state"] == "command", "command boundary missing")
    for field in ("member", "context", "callback", "max_hp", "max_mp"):
        require(before[field] == after[field], "actor binding changed")
    require(after["member"] == int(run["member_addr"], 16), "canonical member differs")
    require(after["target_tile"] == [owner["x"], owner["y"]], "target moved")
    require(len(run["writes"]) == 6 and all("research fixture" in w["note"] for w in run["writes"]),
            "unexpected fixture writes")
    finals = [e for e in requests if e["final"]]
    if outcome == "accepted":
        require(len(finals) == 1 and requests[-1] == finals[0], "duplicate or post-final input")
        facts = finals[0]["facts"]
        require(facts["state"] == "confirmation" and facts["cursor"] == 0
                and facts["selected_ability"] == 1 and facts["member"] == facts["peer"]
                == after["member"], "final action or target differs")
        require(facts["hp"] == before["hp"] and facts["mp"] == before["mp"]
                and facts["target_tile"] == [owner["x"], owner["y"]],
                "final resources or cursor differ")
        policies = [e for e in events if e["event"] in ("policy", "final_policy")]
        require([e["event"] for e in policies] == ["policy", "final_policy"], "policy confirmations missing")
        require(events.index(policies[-1]) < events.index(finals[0]), "policy recorded after final input")
        policy = validate_policy(run["policy_document"])
        for entry in policies:
            snapshot = entry["snapshot"]
            require(evaluate(snapshot, policy) == entry["evaluation"], "policy receipt does not replay")
            decision = entry["evaluation"]["decision"]
            require(decision and decision["candidate_id"] == CURE, "policy did not select Cure")
            actor = snapshot["actor"]
            require(actor["id"] == owner["id"] and actor["name"] == owner["name_text"]
                    and actor["hp"] == before["hp"] and actor["mp"] == before["mp"],
                    "chooser actor differs")
            candidate = snapshot["candidates"]
            require(len(candidate) == 1 and candidate[0] == {
                "id": CURE, "kind": "ability", "action_id": 1, "legal": True,
                "cost": before["cure_cost"], "ability_name": "Cure", "relation": "self",
                "target": {"kind": "unit", "id": owner["id"]}, "target_hp": before["hp"],
                "target_max_hp": before["max_hp"], "target_mp": before["mp"]},
                "chooser candidate differs from engine-confirmed self Cure")
        require(after["hp"] > before["hp"] and after["mp"] == before["mp"] - before["cure_cost"],
                "healing or exact MP effect missing")
        require(9 in after["rows"] and after["enabled"][after["rows"].index(9)] == 0,
                "Action was not consumed")
        final_phase = next(p for p in run["phases"] if p["tag"] == "99-settled")
        actor = final_phase.get("actor")
        require(actor and actor["id"] == owner["id"] and actor["hp"] == after["hp"]
                and actor["mp"] == after["mp"], "restored battle mirror disagrees")
    else:
        require(not finals and (before["hp"], before["mp"]) == (after["hp"], after["mp"]),
                "declined action committed or spent resources")
        require(recovery["fallback"] == "unexecuted", "unproven fallback claimed")


def validate_stopped(stopped):
    require(stopped["status"] == "paused" and "stop_requested" in stopped
            and "stop_input_t" in stopped, "STOP observation missing")
    writes = stopped.get("key_writes")
    require(isinstance(writes, list), "STOP raw input log missing")
    require(all(w["t"] <= stopped["stop_input_t"] for w in writes), "input after observed STOP")
    require(len(writes) == sum(k["hits"] for k in stopped["keys"]), "STOP logs disagree")
    require(not stopped.get("recovery"), "STOP incorrectly claims completed recovery")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cast", required=True)
    parser.add_argument("--declined", action="append", default=[])
    parser.add_argument("--stopped", action="append", default=[])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run = json.loads(Path(args.cast).read_text())
    validate(run)
    for path in args.declined:
        validate(json.loads(Path(path).read_text()), "declined")
    for path in args.stopped:
        stopped = json.loads(Path(path).read_text())
        validate_stopped(stopped)

    def post_terminal(r):
        events = r["executor_events"]
        events.append(copy.deepcopy(next(e for e in events if e["event"] == "input_requested")))
        events.append(copy.deepcopy(next(e for e in events if e["event"] == "input_delivered")))
        r["keys"].append(copy.deepcopy(r["keys"][0]))
        r["key_writes"].extend(copy.deepcopy(r["key_writes"][:r["keys"][0]["hits"]]))

    def altered_candidate(r, **changes):
        for entry in r["executor_events"]:
            if entry["event"] in ("policy", "final_policy"):
                entry["snapshot"]["candidates"][0].update(changes)
                entry["evaluation"] = evaluate(entry["snapshot"], validate_policy(r["policy_document"]))
    mutations = [
        ("missing input log", lambda r: r.pop("key_writes")),
        ("empty input log", lambda r: r.update(key_writes=[])),
        ("missing final policy", lambda r: r["executor_events"].__setitem__(slice(None),
          [e for e in r["executor_events"] if e["event"] != "final_policy"])),
        ("wrong final target", lambda r: next(e for e in r["executor_events"]
          if e.get("final"))["facts"].update(peer=0)),
        ("unspent MP", lambda r: r["recovery"]["after"].update(mp=r["recovery"]["before"]["mp"])),
        ("enemy-only healing", lambda r: r["recovery"]["after"].update(hp=r["recovery"]["before"]["hp"])),
        ("mirror mismatch", lambda r: next(p for p in r["phases"]
          if p["tag"] == "99-settled")["actor"].update(hp=1)),
        ("coherent post-terminal input", post_terminal),
        ("consistent but wrong chooser cost", lambda r: altered_candidate(r, cost=0)),
        ("consistent but wrong chooser target", lambda r: altered_candidate(r, target={"kind": "unit", "id": 5})),
        ("STOP marked completed", lambda r: r.update(stop_requested=1)),
        ("extra fixture write", lambda r: r["writes"].append(r["writes"][0])),
    ]
    rejected = []
    for name, mutate in mutations:
        changed = copy.deepcopy(run)
        mutate(changed)
        try:
            validate(changed)
        except (ValueError, KeyError, TypeError):
            rejected.append(name)
        else:
            raise AssertionError(f"mutation survived: {name}")
    if args.stopped:
        stopped = json.loads(Path(args.stopped[0]).read_text())
        for name, mutate in [
            ("missing STOP input log", lambda r: r.pop("key_writes")),
            ("post-STOP raw input", lambda r: r["key_writes"].append({"t": r["stop_input_t"] + 1})),
        ]:
            changed = copy.deepcopy(stopped)
            mutate(changed)
            try:
                validate_stopped(changed)
            except (ValueError, KeyError):
                rejected.append(name)
            else:
                raise AssertionError(name)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": "retained policy recovery receipts; no fresh gameplay claim",
                              "controls": 1 + len(args.declined) + len(args.stopped), "rejected": rejected}, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"Recovery receipts: {1 + len(args.declined) + len(args.stopped)} controls, {len(rejected)} rejected mutations; pass")


if __name__ == "__main__":
    main()
