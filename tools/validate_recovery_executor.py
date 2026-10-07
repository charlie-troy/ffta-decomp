"""Host-only executor contract tests; fake transport is not ROM proof."""
from dataclasses import replace
import argparse
import json
from pathlib import Path

from recovery_executor import SelfCureExecutor, RecoveryStopped
from recovery_menu import MenuObservation, RecoveryStateError, require
from tactics_policy import load_policy_file


class Menu:
    def __init__(self, *, mp=85, hp=100, disabled=False, reordered=False, effect="normal"):
        run = json.loads(Path("outputs/autobattle/a6-modal-cure-05/probe.json").read_text())
        self.owner = run["owner"]
        self.identity = (0, 0, 0, 0, 0, 0, 7)
        self.states = {}
        for phase in run["phases"]:
            data = dict(phase["guarded_menu"])
            for field in ("rows", "enabled", "ability_ids", "target_tile"):
                data[field] = tuple(data[field])
            obs = MenuObservation(**data)
            self.states.setdefault(obs.state, replace(obs, observed_at=0, hp=hp, mp=mp))
        self.states["command"] = replace(self.states["command"], cursor=0)
        if disabled:
            obs = self.states["ability-list"]
            self.states["ability-list"] = replace(obs, enabled=(0,) + obs.enabled[1:])
        if reordered:
            for state in ("command", "action-group", "ability-list"):
                obs = self.states[state]
                self.states[state] = replace(obs, rows=obs.rows[::-1], enabled=obs.enabled[::-1],
                                             ability_ids=obs.ability_ids[::-1], cursor=0)
        self.state, self.last, self.effect, self.final = "command", None, effect, False

    def snapshot(self):
        self.last = self.states[self.state]
        return self.last

    def revalidate(self, token):
        require(token is self.last, "changed token")
        return self.snapshot()


class Probe:
    def __init__(self, menu):
        self.menu, self.keys, self.g = menu, [], self

    def disarm(self):
        pass

    def cont(self):
        m = self.menu
        if not m.final and m.state == "settling":
            m.state = "target-overlay"
        if m.final:
            before = m.states["command"]
            hp = before.hp if m.effect == "enemy-only" else before.hp + 50
            mp = before.mp if m.effect == "unspent" else before.mp - 6
            flags = tuple(0 if row == 9 else flag for row, flag in zip(before.rows, before.enabled))
            m.states["command"] = replace(before, hp=hp, mp=mp, enabled=flags)
            m.state = "command"

    def press(self, mask, **kwargs):
        kwargs["stop_check"]()
        self.keys.append(mask)
        m, state = self.menu, self.menu.state
        obs = m.states[state]
        if mask in (0x80, 0x40):
            m.states[state] = replace(obs, cursor=obs.cursor + (1 if mask == 0x80 else -1))
        elif mask == 2:
            m.state = {"confirmation": "description", "description": "settling",
                       "target-overlay": "ability-list", "ability-list": "action-group",
                       "action-group": "command"}[state]
        else:
            m.state = {"command": "action-group", "action-group": "ability-list",
                       "ability-list": "target-overlay", "target-overlay": "description",
                       "description": "confirmation", "confirmation": "description"}[state]
            if state == "confirmation":
                m.final = True
        return 5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    policy = load_policy_file("configs/tactics/healer.json")
    checks = []

    def setup(**kwargs):
        menu = Menu(**kwargs)
        probe = Probe(menu)
        executor = SelfCureExecutor(menu, probe, policy, clock=lambda: 0, sleep=lambda _: None)
        return menu, probe, executor

    for name, params, outcome in [
        ("selected Cure", {}, "accepted"),
        ("reordered rows still choose Cure", {"reordered": True}, "accepted"),
        ("reserve decline cancels", {"mp": 6}, "declined"),
        ("healthy actor declines", {"hp": 400}, "declined"),
        ("disabled Cure never confirmed", {"mp": 5, "disabled": True}, "declined"),
    ]:
        menu, probe, executor = setup(**params)
        result = executor.run()
        assert result["outcome"] == outcome
        assert sum(e.get("final", False) for e in executor.events) == (outcome == "accepted")
        if outcome == "declined":
            assert not menu.final and menu.state == "command"
        else:
            count = len(probe.keys)
            try:
                executor.press("A", menu.snapshot())
            except RecoveryStateError:
                assert len(probe.keys) == count
            else:
                raise AssertionError("duplicate input after final confirmation")
        checks.append(name)

    for name, params in [("enemy-only effect rejected", {"effect": "enemy-only"}),
                         ("unspent MP rejected", {"effect": "unspent"})]:
        menu, probe, executor = setup(**params)
        try:
            executor.run()
        except RecoveryStateError:
            checks.append(name)
        else:
            raise AssertionError(name)

    for boundary in range(10):
        menu, probe, executor = setup()
        executor.stop_check = lambda: len(probe.keys) >= boundary
        try:
            executor.run()
        except RecoveryStopped:
            assert len(probe.keys) == boundary
            checks.append(f"STOP after {boundary} keys suppresses subsequent input")
        else:
            raise AssertionError(f"STOP ignored: {boundary}")
    for boundary in range(9, 14):
        menu, probe, executor = setup(mp=6)
        executor.stop_check = lambda: len(probe.keys) >= boundary
        try:
            executor.run()
        except RecoveryStopped:
            assert len(probe.keys) == boundary and not menu.final
            checks.append(f"STOP during cancellation at {boundary} keys")
        else:
            raise AssertionError("cancellation STOP ignored")
    menu, probe, executor = setup()
    menu.revalidate = lambda token: (_ for _ in ()).throw(RecoveryStateError("identity drift"))
    try:
        executor.run()
    except RecoveryStateError:
        assert not probe.keys
        checks.append("pre-input identity failure suppresses transport")
    else:
        raise AssertionError("identity failure ignored")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"scope": "host-only real executor with fake menu/transport; no ROM semantics claim",
                               "status": "pass", "checks": checks}, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"Executor: {len(checks)} host checks; pass")


if __name__ == "__main__":
    main()
