"""Replay successful self-Cure, guarded turn finish and enemy continuation."""
import argparse
import copy
import json
from pathlib import Path

from recovery_menu import require
from validate_recovery_facing_execution import continuation
from validate_recovery_wait_execution import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--capture", default="outputs/autobattle/a6-cure-complete-turn-01")
    parser.add_argument("--out", required=True)
    parser.add_argument("--require-scoped-transport", action="store_true")
    args = parser.parse_args()
    directory = Path(args.capture)
    run = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
    rom = Path(args.rom).read_bytes()
    tags = run.get("continuation_tags", [f"{len(run['keys']):02d}-A", "99-settled"])
    require(len(tags) == 2 and len(set(tags)) == 2, "continuation capture tags differ")
    later = [continuation(directory, tag, rom) for tag in tags]

    def check(receipt):
        if "continuation_tags" in receipt:
            halts = receipt["capture_halts"]
            require([h["tag"] for h in halts] == [p["tag"] for p in receipt["phases"]]
                    and all(h["reply"][:1] in ("S", "T") and h["reply"] != "S04" for h in halts),
                    "missing or invalid halted capture")
            if "continuation_polls" in receipt:
                captured = [p for p in receipt["continuation_polls"] if p["candidate"] == "capture"]
                require([p["tag"] for p in captured] == receipt["continuation_tags"]
                        and all(p["roster"] == "verified" for p in captured), "poll/capture join differs")
        return validate(receipt, later, segment="finish", cure_outcome="accepted")

    def check_transport(receipt):
        events = receipt["modal_transport"]
        require(events[0]["event"] == "halt" and events[1]["event"] == "trace_suspended"
                and events[-1]["event"] == "trace_restored",
                "modal trace suspension/restoration order differs")
        require(sum(e["event"] == "trace_suspended" for e in events) == 1
                and sum(e["event"] == "trace_restored" for e in events) == 1
                and all(e["event"] in ("halt", "trace_suspended", "trace_restored") for e in events),
                "duplicate/failed modal trace lifecycle")
        halts = [e for e in events if e["event"] == "halt"]
        require(len(halts) >= len(receipt["keys"]) and all(
            isinstance(e["reply"], str) and len(e["reply"]) >= 3 and e["reply"][0] in "ST"
            and all(c in "0123456789abcdefABCDEF" for c in e["reply"][1:3])
            and e["reply"][:3] not in ("S04", "T04") for e in halts), "invalid modal halts")
        writes = receipt["modal_raw_writes"]
        require(writes and all(w["event"] == "key_write" for w in writes)
                and [{k: v for k, v in w.items() if k != "event"} for w in writes] == receipt["key_writes"],
                "modal ledger differs from raw transport writes")
        require(events[-1]["write_count"] == len(writes), "input after modal tracing restoration")
        trace = receipt["restored_trace"]
        seed_traffic = (trace["after"]["seeds"] > trace["before"]["seeds"]
                        and len(trace["seed_observations"]) == trace["after"]["seeds"]
                        and any(s.get("ctx_units") for s in trace["seed_observations"]))
        # Router preview traffic proves only hook restoration, never another
        # action. The independent raw joins above still own continuation.
        router_traffic = (trace["after"]["router_hits"] > trace["before"]["router_hits"]
                          and len(trace["router_observations"]) == trace["after"]["router_hits"]
                          and any(r.get("enemy") is True and r.get("during") == "a6-restored-trace"
                                  and r.get("branch") == "ai_path_0x0809E3BA"
                                  and any((r.get("id"), r.get("name"), r.get("slot")) ==
                                          (c["actor"]["id"], c["actor"]["name_text"], c["actor"]["slot"])
                                          for c in later) for r in trace["router_observations"]))
        require(seed_traffic or router_traffic, "restored tracing lacks decoded seed/router evidence")

    if args.require_scoped_transport:
        check_transport(run)

    check(run)
    rejected = []

    def extra_final(receipt):
        events = receipt["finish_events"]
        events.extend(copy.deepcopy([e for e in events if e["event"] in
                      ("input_requested", "input_delivered")][-2:]))
        receipt["keys"].append(copy.deepcopy(receipt["keys"][-1]))
        receipt["key_writes"].extend(copy.deepcopy(receipt["key_writes"][-5:]))

    for name, mutate in [
        ("Cure did not heal", lambda r: r["recovery"]["after"].update(hp=100)),
        ("Cure did not spend MP", lambda r: r["recovery"]["after"].update(mp=85)),
        ("Cure did not consume Action", lambda r: r["recovery"]["after"]["enabled"].__setitem__(1, 1)),
        ("finish belongs to different actor", lambda r: r["finish"]["before"].update(member=0)),
        ("finish before healing settled", lambda r: r["finish"]["before"].update(hp=100)),
        ("missing final Wait policy", lambda r: r.update(finish_events=[e for e in r["finish_events"] if e["event"] != "final_policy"])),
        ("coherent duplicate final input", extra_final),
        ("missing raw input", lambda r: r.update(key_writes=[])),
        ("claimed completion inside executor", lambda r: r["finish"].update(continuation="accepted")),
        ("enemy-only healing", lambda r: r["phases"][-1]["actor"].update(hp=100)),
    ]:
        changed = copy.deepcopy(run)
        mutate(changed)
        try:
            check(changed)
        except (ValueError, KeyError, TypeError):
            rejected.append(name)
        else:
            raise AssertionError(f"mutation survived: {name}")
    if "continuation_tags" in run:
        changed = copy.deepcopy(run)
        changed["capture_halts"] = []
        try:
            check(changed)
        except ValueError:
            rejected.append("missing halted capture evidence")
        else:
            raise AssertionError("missing halted captures survived")
    for name, mutate in [
        ("continuing enemy HP outside bounds", lambda c: c[0]["actor"].update(hp=1000)),
        ("coherent invalid enemy coordinate", lambda c: (c[0]["actor"].update(tile=[255, 255]),
                                                       c[0].update(target_tile=[255, 255]))),
    ]:
        changed = copy.deepcopy(later)
        mutate(changed)
        try:
            validate(run, changed, segment="finish", cure_outcome="accepted")
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name)
    if args.require_scoped_transport:
        for name, mutate in [
            ("missing modal trace", lambda r: r.pop("modal_transport")),
            ("missing modal halts", lambda r: r.update(modal_transport=[e for e in r["modal_transport"] if e["event"] != "halt"])),
            ("fatal modal halt", lambda r: r["modal_transport"][0].update(reply="T04")),
            ("duplicate trace restoration", lambda r: r["modal_transport"].append(copy.deepcopy(r["modal_transport"][-1]))),
            ("missing modal ledger", lambda r: r.update(modal_raw_writes=[])),
            ("altered modal write", lambda r: r["modal_raw_writes"][0].update(val=0)),
            ("input after trace restoration", lambda r: r["modal_transport"][-1].update(write_count=0)),
            ("no restored trace traffic", lambda r: r["restored_trace"]["after"].update(seeds=0, router_hits=0)),
            ("missing restored trace observations", lambda r: r["restored_trace"].update(seed_observations=[], router_observations=[])),
            ("unattributed restored router evidence", lambda r: (
                r["restored_trace"].update(seed_observations=[]),
                [entry.update(id=255, name="unknown") for entry in r["restored_trace"]["router_observations"]])),
        ]:
            changed = copy.deepcopy(run)
            mutate(changed)
            try:
                check_transport(changed)
            except (ValueError, KeyError, TypeError, IndexError):
                rejected.append(name)
            else:
                raise AssertionError(f"transport mutation survived: {name}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": __doc__, "capture": str(directory),
                               "continuation": later, "rejections": rejected,
                               "limits": "constructed self-Cure research only; no public runner/manual handoff"},
                              indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Cure turn: healing/cost/Action joined to guarded finish and two enemies; {len(rejected)} mutations rejected")


if __name__ == "__main__":
    main()
