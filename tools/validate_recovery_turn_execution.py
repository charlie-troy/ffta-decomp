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
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": __doc__, "capture": str(directory),
                               "continuation": later, "rejections": rejected,
                               "limits": "constructed self-Cure research only; no public runner/manual handoff"},
                              indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Cure turn: healing/cost/Action joined to guarded finish and two enemies; {len(rejected)} mutations rejected")


if __name__ == "__main__":
    main()
