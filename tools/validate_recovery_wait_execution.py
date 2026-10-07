"""Validate retained policy-decline -> guarded Wait -> enemy continuation."""
import argparse
import copy
import json
from pathlib import Path

from recovery_executor import WAIT, CURE
from recovery_menu import require
from tactics_policy import evaluate, validate_policy
from validate_recovery_execution import validate as validate_cure
from validate_recovery_facing_execution import MASKS, continuation, validate as validate_facing


def recovery_prefix(run, outcome="declined"):
    """Validate the explicitly bounded Cure segment before subsequent input."""
    prefix = copy.deepcopy(run)
    count = sum(e["event"] == "input_delivered" for e in run["executor_events"])
    prefix["keys"] = prefix["keys"][:count]
    prefix["key_writes"] = prefix["key_writes"][:sum(k["hits"] for k in prefix["keys"])]
    prefix["status"] = "observed"
    # A later STOP does not undo the completed decline segment. The caller
    # separately validates terminal STOP and all subsequent input ordering.
    prefix.pop("stop_requested", None)
    validate_cure(prefix, outcome)
    if outcome == "accepted":
        return count
    policies = [e for e in run["executor_events"] if e["event"] == "policy"]
    if policies:
        require(len(policies) == 1, "ambiguous Cure decline policy")
        entry = policies[0]
        before = run["recovery"]["before"]
        snapshot = entry["snapshot"]
        actor = snapshot["actor"]
        require(actor["id"] == run["owner"]["id"] and actor["name"] == run["owner"]["name_text"]
                and actor["hp"] == before["hp"] and actor["mp"] == before["mp"]
                and actor["tile"] == before["target_tile"], "Cure decline chooser actor differs")
        require(snapshot["candidates"] == [{
            "id": CURE, "kind": "ability", "action_id": 1, "legal": True,
            "cost": before["cure_cost"], "ability_name": "Cure", "relation": "self",
            "target": {"kind": "unit", "id": run["owner"]["id"]},
            "target_hp": before["hp"], "target_max_hp": before["max_hp"], "target_mp": before["mp"]}],
            "declined Cure candidate differs")
        replay = evaluate(snapshot, validate_policy(run["policy_document"]))
        require(replay == entry["evaluation"] and replay["decision"] is None,
                "policy did not decline Cure")
    else:
        unavailable = [e for e in run["executor_events"] if e["event"] == "unavailable"]
        lists = [e["facts"] for e in run["executor_events"] if e["event"] == "observation"
                 and e["facts"]["state"] == "ability-list"]
        require(unavailable == [{"event": "unavailable", "ability": 1}] and lists
                and lists[0]["ability_ids"].count(1) == 1
                and not lists[0]["enabled"][lists[0]["ability_ids"].index(1)],
                "missing engine-disabled Cure evidence")
    return count


def validate(run, later, *, segment="fallback", cure_outcome="declined"):
    count = recovery_prefix(run, cure_outcome)
    require(run["status"] == "observed" and "stop_requested" not in run, "terminal STOP or failure")
    fallback = run[segment]
    require(fallback["outcome"] == "confirmed" and fallback["continuation"] == "unverified",
            "executor upgraded confirmation to continuation")
    events = run[f"{segment}_events"]
    policies = [e for e in events if e["event"] in ("policy", "final_policy")]
    require([e["event"] for e in policies] == ["policy", "final_policy"], "missing policy recheck")
    policy = validate_policy(run["policy_document"])
    before, recovered = fallback["before"], run["recovery"]["after"]
    for field in ("member", "context", "callback", "hp", "mp", "target_tile", "driver_state"):
        require(before[field] == recovered[field], "Wait not joined to declined actor")
    require(before["state"] == "command" and before["rows"].count(10) == 1
            and before["enabled"][before["rows"].index(10)], "engine-enabled Wait missing")
    for entry in policies:
        snapshot = entry["snapshot"]
        require(snapshot["candidates"] == [{"id": WAIT, "kind": "wait", "action_id": 10,
                                            "legal": True, "cost": 0}], "Wait candidate differs")
        actor = snapshot["actor"]
        require(actor["id"] == run["owner"]["id"] and actor["name"] == run["owner"]["name_text"]
                and actor["hp"] == before["hp"] and actor["mp"] == before["mp"]
                and actor["tile"] == before["target_tile"], "Wait chooser actor differs")
        replay = evaluate(snapshot, policy)
        require(replay == entry["evaluation"] and replay["decision"]
                and replay["decision"]["candidate_id"] == WAIT
                and replay["decision"]["fallback"], "Wait fallback does not replay")
    requests = [e for e in events if e["event"] == "input_requested"]
    delivered = [e for e in events if e["event"] == "input_delivered"]
    require(requests and len(requests) == len(delivered)
            and [e["key"] for e in requests] == [e["key"] for e in delivered]
            == [e["key"] for e in run["keys"][count:]], "fallback input segment disagrees")
    finals = [e for e in requests if e["final"]]
    require(len(finals) == 1 and requests[-1] == finals[0]
            and events.index(policies[-1]) < events.index(finals[0]), "duplicate/post-final or premature input")
    all_requests = [e for e in run["executor_events"] if e["event"] == "input_requested"] + requests
    require([e["hits"] for e in delivered] == [e["hits"] for e in run["keys"][count:]],
            "fallback transport counts differ")
    merged = copy.deepcopy(run)
    merged["menu_guards"] = [{"before_key": i, "key": e["key"], "facts": e["facts"]}
                             for i, e in enumerate(all_requests, 1)]
    validate_facing(merged, later)


def validate_stop(run):
    count = recovery_prefix(run)
    require(run["status"] == "paused" and "stop_requested" in run and "stop_input_t" in run,
            "missing STOP terminal")
    require("fallback" not in run and "facing_confirmation" not in run, "STOP incorrectly confirmed Wait")
    requests = [e for e in run["fallback_events"] if e["event"] == "input_requested"]
    require(requests and not any(e["final"] for e in requests), "STOP allowed final input")
    require(len(run["key_writes"]) == sum(k["hits"] for k in run["keys"])
            and all(w["t"] <= run["stop_input_t"] for w in run["key_writes"]), "post-STOP raw input")
    require([w["val"] for w in run["key_writes"]] ==
            [MASKS[k["key"]] for k in run["keys"] for _ in range(k["hits"])]
            and not any(w["manual"] for w in run["key_writes"]), "STOP raw transport differs")
    require([e["key"] for e in requests] == [k["key"] for k in run["keys"][count:]],
            "STOP segment logs disagree")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--capture", default="outputs/autobattle/a6-policy-wait-reserve-01")
    parser.add_argument("--stopped")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    directory = Path(args.capture)
    run = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
    rom = Path(args.rom).read_bytes()
    tags = run.get("continuation_tags", [f"{len(run['keys']):02d}-A", "99-settled"])
    require(len(tags) == 2 and len(set(tags)) == 2, "continuation capture tags differ")
    later = [continuation(directory, tag, rom) for tag in tags]
    validate(run, later)
    rejected = []

    def wrong_candidate(receipt, **values):
        for e in receipt["fallback_events"]:
            if e["event"] in ("policy", "final_policy"):
                e["snapshot"]["candidates"][0].update(values)
                e["evaluation"] = evaluate(e["snapshot"], validate_policy(receipt["policy_document"]))

    def extra_input(receipt):
        events = receipt["fallback_events"]
        events.extend(copy.deepcopy([e for e in events if e["event"] in
                      ("input_requested", "input_delivered")][-2:]))
        receipt["keys"].append(copy.deepcopy(receipt["keys"][-1]))
        receipt["key_writes"].extend(copy.deepcopy(receipt["key_writes"][-5:]))

    def wrong_decline(receipt):
        policies = [e for e in receipt["executor_events"] if e["event"] == "policy"]
        if policies:
            entry = policies[0]
            entry["snapshot"]["actor"]["mp"] += 1
            entry["evaluation"] = evaluate(entry["snapshot"], validate_policy(receipt["policy_document"]))
        else:
            next(e for e in receipt["executor_events"] if e["event"] == "unavailable")["ability"] = 2

    for name, mutate in [
        ("missing final policy", lambda r: r.update(fallback_events=[e for e in r["fallback_events"] if e["event"] != "final_policy"])),
        ("consistent wrong Wait cost", lambda r: wrong_candidate(r, cost=1)),
        ("consistent wrong Wait action", lambda r: wrong_candidate(r, action_id=1)),
        ("coherent post-final input", extra_input),
        ("empty raw input", lambda r: r.update(key_writes=[])),
        ("claimed executor completion", lambda r: r["fallback"].update(continuation="accepted")),
        ("different fallback actor", lambda r: r["fallback"]["before"].update(member=0)),
        ("disabled engine Wait", lambda r: r["fallback"]["before"]["enabled"].__setitem__(2, 0)),
        ("unspent resource mismatch", lambda r: r["phases"][-1]["actor"].update(mp=0)),
        ("missing Cure rejection evidence", lambda r: r.update(executor_events=[e for e in r["executor_events"] if e["event"] not in ("policy", "unavailable")])),
        ("consistent wrong Cure rejection", wrong_decline),
    ]:
        changed = copy.deepcopy(run)
        mutate(changed)
        try:
            validate(changed, later)
        except (ValueError, KeyError, TypeError):
            rejected.append(name)
        else:
            raise AssertionError(f"mutation survived: {name}")
    if args.stopped:
        stopped = json.loads(Path(args.stopped).read_text(encoding="utf-8"))
        validate_stop(stopped)
        for name, mutate in [
            ("STOP missing raw input", lambda r: r.update(key_writes=[])),
            ("STOP post-terminal raw input", lambda r: r["key_writes"].append({"t": r["stop_input_t"] + 1})),
        ]:
            changed = copy.deepcopy(stopped)
            mutate(changed)
            try:
                validate_stop(changed)
            except (ValueError, KeyError):
                rejected.append(name)
            else:
                raise AssertionError(name)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": __doc__, "capture": str(directory),
                               "stopped": args.stopped, "continuation": later,
                               "rejections": rejected}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Policy Wait: joined decline/confirmation/continuation, {len(rejected)} rejected mutations; pass")


if __name__ == "__main__":
    main()
