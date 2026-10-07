"""Exercise real Wait fallback flow with fake modal/transport dependencies."""
import argparse
import copy
import json
from dataclasses import replace
from pathlib import Path

from recovery_executor import WaitFacingExecutor, RecoveryStopped
from recovery_menu import MenuObservation, RecoveryStateError
from tactics_policy import load_policy_file
from validate_recovery_executor import Menu, Probe


class WaitProbe(Probe):
    def __init__(self, menu, *, effect="normal"):
        super().__init__(menu)
        self.effect = effect

    def press(self, mask, **kwargs):
        kwargs["stop_check"]()
        if mask in (0x80, 0x40):
            return super().press(mask, **kwargs)
        self.keys.append(mask)
        assert mask == 1
        if self.menu.state == "command":
            obs = self.menu.states["command"]
            assert obs.rows[obs.cursor] == 10
            self.menu.state = "facing"
            if self.effect == "resources":
                self.menu.states["facing"] = replace(self.menu.states["facing"], mp=0)
            elif self.effect == "wrong-state":
                self.menu.state = "description"
        else:
            assert self.menu.state == "facing"
            self.menu.state = "handoff"
            if self.effect == "ambiguous-final":
                return 0
        return 5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    policy = load_policy_file("configs/tactics/healer.json")
    captured = json.loads(Path("outputs/autobattle/a6-wait-facing-cancel-01/probe.json").read_text(encoding="utf-8"))
    data = dict(next(p["guarded_menu"] for p in captured["phases"] if p["tag"] == "11-A"))
    for field in ("rows", "enabled", "ability_ids", "target_tile"):
        data[field] = tuple(data[field])
    facing = MenuObservation(**data)
    checks = []

    def setup(effect="normal"):
        menu = Menu(mp=6)
        menu.states["command"] = replace(menu.states["command"], cursor=1)
        menu.states["facing"] = replace(facing, observed_at=0)
        probe = WaitProbe(menu, effect=effect)
        executor = WaitFacingExecutor(menu, probe, copy.deepcopy(policy), clock=lambda: 0)
        return menu, probe, executor

    for reordered in (False, True):
        menu, probe, executor = setup()
        if reordered:
            obs = menu.states["command"]
            menu.states["command"] = replace(obs, rows=obs.rows[::-1], enabled=obs.enabled[::-1], cursor=0)
        result = executor.run()
        assert result["outcome"] == "confirmed" and result["continuation"] == "unverified"
        assert executor.committed and probe.keys[-2:] == [1, 1]
        final = [e for e in executor.events if e.get("final")]
        assert len(final) == 1 and final[0]["facts"]["state"] == "facing"
        count = len(probe.keys)
        try:
            executor.press("B", menu.states["facing"])
        except RecoveryStateError:
            assert len(probe.keys) == count
        else:
            raise AssertionError("post-final input allowed")
        checks.append(f"Wait by row ID, reordered={reordered}; one final and no completion inference")

    menu, probe, executor = setup()
    executor.policy["fallback"] = "none"
    assert executor.run()["outcome"] == "unexecuted" and not probe.keys
    checks.append("fallback none suppresses all Wait input")

    for name, change in [
        ("disabled Wait", lambda m: m.states.update(command=replace(m.states["command"], enabled=(1, 1, 0, 1)))),
        ("missing Wait", lambda m: m.states.update(command=replace(m.states["command"], rows=(8, 9, 11, 12)))),
    ]:
        menu, probe, executor = setup()
        change(menu)
        try:
            executor.run()
        except RecoveryStateError:
            assert not probe.keys
            checks.append(name)
        else:
            raise AssertionError(name)

    for effect in ("resources", "wrong-state", "ambiguous-final"):
        menu, probe, executor = setup(effect)
        try:
            executor.run()
        except RecoveryStateError:
            assert len(probe.keys) == (3 if effect == "ambiguous-final" else 2)
            if effect == "ambiguous-final":
                assert executor.committed
            checks.append(f"{effect} fails closed without retry")
        else:
            raise AssertionError(effect)

    for boundary in range(3):
        menu, probe, executor = setup()
        executor.stop_check = lambda: len(probe.keys) >= boundary
        try:
            executor.run()
        except RecoveryStopped:
            assert len(probe.keys) == boundary
            checks.append(f"STOP after {boundary} keys")
        else:
            raise AssertionError("STOP ignored")

    menu, probe, executor = setup()
    original = menu.revalidate

    def stop_during_revalidation(token):
        result = original(token)
        executor.stop_check = lambda: True
        return result

    menu.revalidate = stop_during_revalidation
    try:
        executor.run()
    except RecoveryStopped:
        assert not probe.keys
        checks.append("STOP arriving during pre-input revalidation")
    else:
        raise AssertionError("STOP ignored")

    for boundary in ("facing revalidation", "latched final request"):
        menu, probe, executor = setup()
        if boundary == "facing revalidation":
            original = menu.revalidate

            def stop_at_facing(token):
                result = original(token)
                if result.state == "facing":
                    executor.stop_check = lambda: True
                return result

            menu.revalidate = stop_at_facing
        else:
            executor.before_final = lambda obs: setattr(executor, "stop_check", lambda: True)
        try:
            executor.run()
        except RecoveryStopped:
            assert len(probe.keys) == 2
            assert executor.committed == (boundary == "latched final request")
            checks.append(f"STOP during {boundary} suppresses transport")
        else:
            raise AssertionError("final STOP ignored")

    menu, probe, executor = setup()
    original = menu.revalidate

    def decline_final(token):
        result = original(token)
        if result.state == "facing":
            executor.policy["fallback"] = "none"
        return result

    menu.revalidate = decline_final
    try:
        executor.run()
    except RecoveryStateError:
        assert len(probe.keys) == 2 and not executor.committed
        checks.append("policy re-evaluated before final facing A")
    else:
        raise AssertionError("changed policy ignored")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"status": "pass", "scope": __doc__, "checks": checks}, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"Wait executor: {len(checks)} host checks; pass")


if __name__ == "__main__":
    main()
