"""Mutate real public ally-Cure artifacts through the full runtime validator."""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from validate_autobattle_runtime import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.run)
    assert not validate(str(root)), validate(str(root))
    run = json.loads((root / "run.json").read_text())
    events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    ledger = [json.loads(line) for line in (root / "input-log.jsonl").read_text().splitlines()]
    turn = next(i for i, e in enumerate(events) if e["kind"] == "turn" and e.get("recovery"))
    assert events[turn]["recovery"]["recovery"]["outcome"] == "accepted-effect-only"
    rejected = []

    def duplicate_final(e, log):
        journal = e[turn]["recovery"]
        journal["wait_events"].extend(copy.deepcopy(journal["wait_events"][-2:]))
        writes = copy.deepcopy(journal["raw_writes"][-5:])
        journal["raw_writes"].extend(writes)
        journal["transport"][-1]["write_count"] += 5
        log.extend({"event": "key_write", **w} for w in writes)

    def final_policy(e):
        return next(r for r in e[turn]["recovery"]["cure_events"] if r["event"]=="final_policy")

    mutations = [
        ("missing public adapter observations", lambda e,l:e[turn]["recovery"].update(policy_observations=[])),
        ("adapter ignores target", lambda e,l:e[turn]["recovery"]["policy_observations"][0]["snapshot"]["candidates"][0]["target"].update(id=7)),
        ("caster heals instead of ally", lambda e,l:e[turn]["recovery"]["recovery"]["after"].update(hp=443)),
        ("target spends MP", lambda e,l:e[turn]["recovery"]["recovery"]["target_after"].update(mp=215)),
        ("wrong accepted target token", lambda e,l:final_policy(e)["target_token"].update(target=0x02000080)),
        ("stale accepted tile", lambda e,l:final_policy(e)["target_token"].update(tile=[4,10])),
        ("wrong accepted cost", lambda e,l:final_policy(e)["target_token"].update(cost=0)),
        ("stale final policy", lambda e,l:final_policy(e)["snapshot"].update(age_seconds=999)),
        ("changed final caster MP", lambda e,l:final_policy(e)["snapshot"]["actor"].update(mp=79)),
        ("stale Wait resources", lambda e,l:next(r for r in e[turn]['recovery']['wait_events'] if r['event']=='final_policy')['snapshot']['actor'].update(mp=85)),
        ("aliased canonical party", lambda e,l:e[turn]["recovery"]["party_before"][0].update(canonical=0x02000080)),
        ("next actor is allied", lambda e,l:e[turn]["recovery"]["continuations"][0].update(relation="ally")),
        ("stale next actor wrapper", lambda e,l:e[turn]["recovery"]["continuations"][0].update(wrapper=e[turn]["recovery"]["owner"].get("actor_wrapper",e[turn]["recovery"]["recovery"]["before"]["actor_wrapper"]))),
        ("missing journal", lambda e, l: e[turn].update(recovery=None)),
        ("empty raw journal", lambda e, l: e[turn]["recovery"].update(raw_writes=[])),
        ("empty raw ledger", lambda e, l: l.clear()),
        ("truncated raw ledger", lambda e, l: l.pop()),
        ("wrong ally target", lambda e, l: e[turn]["selected_target"].update(id=7)),
        ("wrong ability", lambda e, l: e[turn]["selected_action"].update(ability_id=2)),
        ("missing ally healing", lambda e, l: e[turn]["recovery"]["recovery"]["target_after"].update(hp=100)),
        ("no MP spent", lambda e, l: e[turn]["recovery"]["recovery"]["after"].update(mp=85)),
        ("Action remains enabled", lambda e, l: e[turn]["recovery"]["recovery"]["after"]["enabled"].__setitem__(1, 1)),
        ("Wait outside facing", lambda e, l: e[turn]["recovery"]["finish"]["facing"].update(state="command")),
        ("missing Wait final policy", lambda e, l: e[turn]["recovery"].update(wait_events=[r for r in e[turn]["recovery"]["wait_events"] if r["event"] != "final_policy"])),
        ("coherent duplicate final input", duplicate_final),
        ("missing next enemy", lambda e, l: e[turn]["recovery"]["continuations"].pop()),

        ("wrong later side", lambda e, l: e[turn]["recovery"]["continuations"][0]["actor"].update(side_bit=False)),
        ("invalid later tile", lambda e, l: e[turn]["recovery"]["continuations"][0]["actor"].update(tile=[255, 255])),
        ("dead continuing actor", lambda e, l: e[turn]["recovery"]["continuations"][0]["actor"].update(hp=0)),
        ("completed player resources change", lambda e, l: e[turn]["recovery"]["continuations"][0]["party_after"][0].update(hp=100)),
        ("missing restoration", lambda e, l: e[turn]["recovery"]["transport"].pop()),
        ("invalid explicit halt", lambda e, l: e[turn]["recovery"]["transport"][0].update(reply="S04")),
        ("write after restoration", lambda e, l: e[turn]["recovery"]["transport"][-1].update(write_count=0)),
        ("borrowed owner", lambda e, l: e[turn]["recovery"]["owner"].update(id=0)),
        ("wrong chooser target", lambda e, l: next(r for r in e[turn]["recovery"]["cure_events"] if r["event"] == "final_policy")["snapshot"]["candidates"][0]["target"].update(id=0)),
        ("input owner drift", lambda e, l: next(r for r in e[turn]["recovery"]["cure_events"] if r["event"] == "input_requested")["facts"].update(member=0)),
        ("modal timing excludes writes", lambda e, l: e[turn]["recovery"].update(started_t=9999)),
    ]
    with tempfile.TemporaryDirectory(prefix="ffta-recovery-mutants-") as scratch:
        path = Path(scratch)
        (path / "run.json").write_text(json.dumps(run), encoding="utf-8")
        for name, mutate in mutations:
            changed, raw = copy.deepcopy(events), copy.deepcopy(ledger)
            mutate(changed, raw)
            (path / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in changed), encoding="utf-8")
            (path / "input-log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in raw), encoding="utf-8")
            errors = validate(str(path))
            assert errors, f"mutation survived: {name}"
            rejected.append({"case": name, "errors": errors})
        (path / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        (path / "input-log.jsonl").unlink()
        assert validate(str(path)), "missing ledger survived"
        rejected.append({"case": "missing raw ledger"})
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"status": "pass", "run": args.run, "scope": __doc__,
                                  "rejections": rejected}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS public ally recovery receipt: {len(rejected)} rejected mutations")


if __name__ == "__main__":
    main()
