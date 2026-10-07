"""State-driven, bounded self-Cure research; not a public runner capability.

The engine must expose enabled Cure and accept the pinned self target through
its final confirmation before the policy receives a legal candidate. Only a
matching policy decision authorizes the final A. No fallback Wait is inferred.
"""
from __future__ import annotations

import time

from recovery_menu import require, RecoveryTransient
from tactics_policy import SNAPSHOT_SCHEMA2, evaluate

KEYS = {"A": 1, "B": 2, "DOWN": 0x80, "UP": 0x40}
CURE = "cure-self"


class RecoveryStopped(RuntimeError):
    pass


class SelfCureExecutor:
    def __init__(self, menu, probe, policy, *, stop_check=lambda: False,
                 after_key=lambda name: None, clock=time.monotonic, sleep=time.sleep):
        self.menu, self.probe, self.policy = menu, probe, policy
        self.stop_check, self.after_key = stop_check, after_key
        self.clock, self.sleep = clock, sleep
        self.events = []
        self.committed = False

    def check_stop(self):
        if self.stop_check():
            self.events.append({"event": "stop_requested", "at": self.clock()})
            raise RecoveryStopped("STOP observed; no further recovery input")
        return False

    def observe(self, expected=None):
        self.check_stop()
        obs = self.menu.snapshot()
        if expected is not None:
            require(obs.state == expected, f"expected {expected}, observed {obs.state}")
        self.events.append({"event": "observation", "facts": obs.receipt()})
        return obs

    def press(self, name, token, *, final=False):
        self.check_stop()
        require(not self.committed, "input forbidden after final confirmation")
        verified = self.menu.revalidate(token)
        self.check_stop()
        if final:
            require(name == "A" and verified.state == "confirmation" and verified.cursor == 0,
                    "final confirmation is not Do it")
            # Latch before transport: never retry an ambiguous delivered A.
            self.committed = True
        self.events.append({"event": "input_requested", "key": name,
                            "final": final, "facts": verified.receipt()})
        hits = self.probe.press(KEYS[name], tag=f"a6-state:{name}",
                                stop_check=self.check_stop)
        require(hits > 0, "input transport did not establish delivery")
        self.events.append({"event": "input_delivered", "key": name, "hits": hits})
        self.after_key(name)

    def select(self, state, row_id, *, ability=False):
        for _ in range(34):
            obs = self.observe(state)
            ids = obs.ability_ids if ability else obs.rows
            require(ids.count(row_id) == 1, "requested menu row missing or ambiguous")
            index = ids.index(row_id)
            if not obs.enabled[index]:
                return False
            current = obs.scroll + obs.cursor
            if current == index:
                self.press("A", obs)
                return True
            self.press("DOWN" if current < index else "UP", obs)
        raise ValueError("menu navigation exceeded row bound")

    def snapshot_for_policy(self, obs):
        require(obs.state == "confirmation" and obs.cursor == 0,
                "candidate requires engine final confirmation")
        owner = self.menu.owner
        require(obs.target_tile == (owner["x"], owner["y"]), "self target cursor moved")
        require(obs.selected_ability == 1 and obs.peer == obs.member,
                "self Cure identity missing")
        require(obs.mp >= obs.cure_cost, "Cure cost exceeds current MP")
        return {"schema": SNAPSHOT_SCHEMA2, "identity": "verified",
                "age_seconds": max(0, self.clock() - obs.observed_at),
                "actor": {"name": owner["name_text"], "id": owner["id"],
                          "job_id": owner["job"], "side": "player",
                          "hp": obs.hp, "max_hp": obs.max_hp,
                          "mp": obs.mp, "max_mp": obs.max_mp,
                          "tile": [owner["x"], owner["y"]]},
                "candidates": [{"id": CURE, "kind": "ability", "action_id": 1,
                                "legal": True, "cost": obs.cure_cost,
                                "ability_name": "Cure", "relation": "self",
                                "target": {"kind": "unit", "id": owner["id"]},
                                "target_hp": obs.hp, "target_max_hp": obs.max_hp,
                                "target_mp": obs.mp}]}

    def cancel(self, before):
        """Return through known modal states; leave fallback execution unknown."""
        presses = 0
        for _ in range(72):
            try:
                obs = self.observe()
            except RecoveryTransient:
                self.passive_tick()
                continue
            require((obs.hp, obs.mp) == (before.hp, before.mp), "resources changed during cancellation")
            if obs.state == "command":
                return {"outcome": "declined", "fallback": "unexecuted",
                        "before": before.receipt(), "after": obs.receipt()}
            if obs.state == "settling":
                self.passive_tick()
                continue
            require(obs.state in ("confirmation", "description", "target-overlay",
                                  "ability-list", "action-group"), "unknown cancellation state")
            require(presses < 8, "cancellation exceeded input bound")
            self.press("B", obs)
            presses += 1
        raise ValueError("cancellation did not reach command menu")

    def passive_tick(self):
        self.check_stop()
        self.probe.disarm()
        self.probe.g.cont()
        self.sleep(0.25)

    def run(self):
        before = self.observe("command")
        # This bounded path owns only secondary White Magic on this fixture.
        require(self.menu.identity[6] == 7, "secondary White Mage job required")
        require(self.select("command", 9), "Action is unavailable")
        require(self.select("action-group", 10), "secondary action group unavailable")
        if not self.select("ability-list", 1, ability=True):
            self.events.append({"event": "unavailable", "ability": 1})
            return self.cancel(before)
        obs = self.observe("target-overlay")
        require(obs.target_tile == (self.menu.owner["x"], self.menu.owner["y"]),
                "initial target is not pinned self")
        self.press("A", obs)
        self.press("A", self.observe("description"))
        obs = self.observe("confirmation")
        snapshot = self.snapshot_for_policy(obs)
        decision = evaluate(snapshot, self.policy)
        self.events.append({"event": "policy", "snapshot": snapshot, "evaluation": decision})
        if (decision.get("decision") or {}).get("candidate_id") != CURE:
            return self.cancel(before)
        current = self.menu.revalidate(obs)
        final_snapshot = self.snapshot_for_policy(current)
        final_decision = evaluate(final_snapshot, self.policy)
        require((final_decision.get("decision") or {}).get("candidate_id") == CURE,
                "policy changed before final confirmation")
        self.events.append({"event": "final_policy", "snapshot": final_snapshot,
                            "evaluation": final_decision})
        self.press("A", current, final=True)
        deadline = self.clock() + 15
        while self.clock() < deadline:
            self.passive_tick()
            try:
                obs = self.observe()
            except RecoveryTransient as exc:
                self.events.append({"event": "passive_transient", "detail": str(exc)})
                continue
            if obs.state == "command":
                require(obs.hp > before.hp and obs.mp == before.mp - before.cure_cost,
                        "self Cure effect missing or resource cost differs")
                require(9 in obs.rows and not obs.enabled[obs.rows.index(9)],
                        "Action not consumed after Cure")
                return {"outcome": "accepted", "before": before.receipt(),
                        "after": obs.receipt(), "decision": decision}
            require(obs.state in ("description", "confirmation", "settling"),
                    "unexpected post-confirmation state")
        raise TimeoutError("Cure confirmation did not settle to command menu")
