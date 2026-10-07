"""State-driven self-Cure and explicit policy Wait research; not a public capability.

The engine must expose enabled Cure and accept the pinned self target through
its final confirmation before the policy receives a legal candidate. Only a
matching policy decision authorizes the final A. A declined recovery can be
followed by a separately evaluated, engine-enabled Wait through owned facing.
"""
from __future__ import annotations

import time

from recovery_menu import require, RecoveryTransient
from tactics_policy import SNAPSHOT_SCHEMA2, evaluate

KEYS = {"A": 1, "B": 2, "DOWN": 0x80, "UP": 0x40}
CURE = "cure-self"
WAIT = "recovery-wait"


class RecoveryStopped(RuntimeError):
    pass


class SelfCureExecutor:
    def __init__(self, menu, probe, policy, *, stop_check=lambda: False,
                 after_key=lambda name: None, before_final=lambda obs: None,
                 clock=time.monotonic, sleep=time.sleep, choose=None,
                 before_policy_final=lambda obs: None):
        self.menu, self.probe, self.policy = menu, probe, policy
        self.stop_check, self.after_key = stop_check, after_key
        self.clock, self.sleep = clock, sleep
        self.before_final = before_final
        self.before_policy_final = before_policy_final
        self.choose = choose if choose is not None else lambda snapshot: evaluate(snapshot, self.policy)
        self.events = []
        self.committed = False

    def check_stop(self):
        if self.stop_check():
            self.events.append({"event": "stop_requested", "at": self.clock()})
            raise RecoveryStopped("STOP observed; no further recovery input")
        return False

    def observe(self, expected=None):
        for _ in range(12):
            self.check_stop()
            try:
                obs = self.menu.snapshot()
                break
            except RecoveryTransient as exc:
                self.events.append({"event": "passive_transient", "detail": str(exc)})
                self.passive_tick()
        else:
            raise TimeoutError("owned menu opening exceeded passive observation bound")
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
            self.validate_final(name, verified)
            # Latch before transport: never retry an ambiguous delivered A.
            self.committed = True
        self.events.append({"event": "input_requested", "key": name,
                            "final": final, "facts": verified.receipt()})
        if final:
            self.before_final(verified)
        hits = self.probe.press(KEYS[name], tag=f"a6-state:{name}",
                                stop_check=self.check_stop)
        require(hits > 0, "input transport did not establish delivery")
        self.events.append({"event": "input_delivered", "key": name, "hits": hits})
        self.after_key(name)

    def validate_final(self, name, verified):
        require(name == "A" and verified.state == "confirmation" and verified.cursor == 0,
                "final confirmation is not Do it")

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
        decision = self.choose(snapshot)
        self.events.append({"event": "policy", "snapshot": snapshot, "evaluation": decision})
        if (decision.get("decision") or {}).get("candidate_id") != CURE:
            return self.cancel(before)
        self.before_policy_final(obs)
        self.check_stop()
        current = self.menu.revalidate(obs)
        final_snapshot = self.snapshot_for_policy(current)
        final_decision = self.choose(final_snapshot)
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


class WaitFacingExecutor(SelfCureExecutor):
    """Confirm one engine-enabled Wait; continuation requires independent proof.

Used only after a bounded recovery decline. The caller must stop issuing input
after confirmation and independently observe the following actor lifecycle.
"""

    def validate_final(self, name, verified):
        require(name == "A" and verified.state == "facing"
                and verified.driver_state == 47 and verified.facing_direction in range(4),
                "final confirmation is not owned Wait facing")

    def wait_snapshot(self, obs, before):
        require((obs.hp, obs.mp, obs.member, obs.target_tile) ==
                (before.hp, before.mp, before.member, before.target_tile),
                "actor/resources changed before Wait confirmation")
        require(obs.state in ("command", "facing"), "Wait candidate outside owned modal boundary")
        if obs.state == "command":
            require(obs.rows.count(10) == 1 and obs.enabled[obs.rows.index(10)],
                    "Wait is unavailable")
        owner = self.menu.owner
        return {"schema": SNAPSHOT_SCHEMA2, "identity": "verified",
                "age_seconds": max(0, self.clock() - obs.observed_at),
                "actor": {"name": owner["name_text"], "id": owner["id"],
                          "job_id": owner["job"], "side": "player",
                          "hp": obs.hp, "max_hp": obs.max_hp,
                          "mp": obs.mp, "max_mp": obs.max_mp,
                          "tile": [owner["x"], owner["y"]]},
                "candidates": [{"id": WAIT, "kind": "wait", "action_id": 10,
                                "legal": True, "cost": 0}]}

    def run(self):
        before = self.observe("command")
        snapshot = self.wait_snapshot(before, before)
        decision = self.choose(snapshot)
        self.events.append({"event": "policy", "snapshot": snapshot, "evaluation": decision})
        if (decision.get("decision") or {}).get("candidate_id") != WAIT:
            return {"outcome": "unexecuted", "reason": decision["reason"],
                    "before": before.receipt()}
        require(self.select("command", 10), "Wait became unavailable")
        facing = self.observe("facing")
        self.before_policy_final(facing)
        self.check_stop()
        current = self.menu.revalidate(facing)
        final_snapshot = self.wait_snapshot(current, before)
        final_decision = self.choose(final_snapshot)
        require((final_decision.get("decision") or {}).get("candidate_id") == WAIT,
                "policy declined Wait before confirmation")
        self.events.append({"event": "final_policy", "snapshot": final_snapshot,
                            "evaluation": final_decision})
        self.press("A", current, final=True)
        return {"outcome": "confirmed", "continuation": "unverified",
                "before": before.receipt(), "facing": current.receipt(), "decision": decision}
