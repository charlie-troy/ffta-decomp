"""Host checks for the production modal-policy adapter seam; no gameplay proof."""
import argparse
import json
from pathlib import Path

from recovery_executor import SelfCureExecutor
from recovery_menu import RecoveryStateError, RecoveryTransient
from tactics_adapter import TacticsAdapter, AdapterError
from tactics_policy import load_policy_file
from validate_recovery_executor import Menu, Probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    checks = []
    for mp, expected, decisions in [(85, "accepted", 2), (6, "declined", 1), (5, "declined", 0)]:
        menu = Menu(mp=mp, disabled=mp < 6)
        probe = Probe(menu)
        policy = load_policy_file("configs/tactics/healer.json")
        adapter = TacticsAdapter(probe, policy)
        seen = []

        def choose(snapshot):
            seen.append(snapshot)
            return adapter.choose_recovery(snapshot)

        executor = SelfCureExecutor(menu, probe, policy, choose=choose, clock=lambda: 0, sleep=lambda _: None)
        result = executor.run()
        assert result["outcome"] == expected and len(seen) == decisions
        if seen:
            assert adapter.last_snapshot is seen[-1] and adapter.last_candidate_ids == ["cure-self"]
            assert adapter.plans == {} and adapter.last_evaluation == next(
                e["evaluation"] for e in reversed(executor.events) if e["event"] in ("policy", "final_policy"))
        checks.append(f"MP {mp}: production adapter receives exactly {decisions} guarded snapshots")
    menu = Menu()
    probe = Probe(menu)
    policy = load_policy_file("configs/tactics/healer.json")
    adapter = TacticsAdapter(probe, policy)
    calls = []

    def decline_final(snapshot):
        calls.append(snapshot)
        if len(calls) == 2:
            adapter.policy["assignments"] = {}
            adapter.policy["fallback"] = "none"
        return adapter.choose_recovery(snapshot)

    executor = SelfCureExecutor(menu, probe, policy, choose=decline_final, clock=lambda: 0, sleep=lambda _: None)
    try:
        executor.run()
    except RecoveryStateError:
        assert len(calls) == 2 and not menu.final and not executor.committed
        checks.append("adapter decline at final policy check suppresses final input")
    else:
        raise AssertionError("executor bypassed production chooser")
    try:
        adapter.choose_recovery({"schema": "ffta-tactics-snapshot/1"})
    except AdapterError:
        checks.append("ordinary command snapshot cannot enter modal policy seam")
    else:
        raise AssertionError("wrong snapshot accepted")
    for openings in (2, 20):
        menu = Menu()
        probe = Probe(menu)
        read = menu.snapshot
        attempts = []

        def opening():
            attempts.append(1)
            if len(attempts) <= openings:
                raise RecoveryTransient("owned list opening")
            return read()

        menu.snapshot = opening
        executor = SelfCureExecutor(menu, probe, policy, clock=lambda: 0, sleep=lambda _: None)
        if openings == 2:
            assert executor.observe("command").state == "command" and len(attempts) == 3
            checks.append("known opening permits bounded passive observation only")
        else:
            try:
                executor.observe("command")
            except TimeoutError:
                assert len(attempts) == 12
                checks.append("permanent opening reaches passive bound without input")
            else:
                raise AssertionError("permanent opening accepted")
        assert not probe.keys
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": __doc__, "checks": checks}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"PASS modal-policy seam: {len(checks)} host checks")


if __name__ == "__main__":
    main()
