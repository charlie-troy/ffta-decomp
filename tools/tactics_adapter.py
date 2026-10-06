"""A5.3 minimum conditional-action adapter: the live candidate source.

This is the *impure* half of the tactics layer. It reads the engine (read-only
RAM reads through the existing Probe) and hands the frozen chooser a snapshot
whose every field is a fact this packet proved live. It never presses keys and
never writes memory: the runtime drives the chosen candidate through the C2
identified-commit drivers, and the engine's own board state decides whether the
commit happened.

Candidate family exposed here -- deliberately narrow:

* ``move`` -- offered when ``plan_identified_move`` (probe_control_handoff)
  returns a plan, i.e. the decoded command cursor reads Move (0) and the
  decoded target cursor is readable. Destination choice and reachability are
  NOT part of the candidate: the C2 driver steps the real cursor, reads the
  reached tile from RAM, and the engine's confirm-A is the verdict, while the
  runtime verifies the whole-party tile delta afterwards.
* ``wait`` -- offered when the decoded command cursor reads a known command
  (0/1/2), which is the C3 identified-Wait law: Wait is reachable from any
  command by navigating down.

Consequences, recorded rather than papered over: the live candidate set has
**no MP cost and no range/target**, so ``remaining_mp_after_cost`` is only
meaningful at cost 0 and relation/target/ability predicates stay ineligible.
Ability candidates need the Action submenu decoded first (A5.3's remaining
research); until then they cannot silently become enabled options because the
schema rejects any predicate the adapter cannot supply facts for.

Fields supplied live (see docs/tactics-policy.md):

| fact | source |
|---|---|
| actor name/id/job/side | the A5.1 verified fresh-menu owner row (boot-guard identity) |
| actor hp/max_hp/mp/max_mp/ct | the same roster record (+0x18/+0x1A/+0x1C/+0x1E/+0xD0) |
| actor tile | the same record (+0xF6/+0xF7), already part of identity validation |
| candidates | the two command planners above, read from the decoded menu cursors |
| age_seconds | caller-measured: owner observation -> this decision (see below) |

``age_seconds`` is measured from the owner observation that established the
fresh menu to the moment the policy decides. It therefore includes any work
between them (the boundary screenshot). The input drive after the decision is
covered separately: the runtime revalidates the actor before every key press
and cross-checks the actor's committed tile afterwards.
"""
from __future__ import annotations

import time

from probe_control_handoff import MOVE_CMD, WAIT_CMD
from tactics_policy import SNAPSHOT_SCHEMA, evaluate, validate_policy

MOVE_CANDIDATE = "move"
WAIT_CANDIDATE = "wait"
KINDS = (MOVE_CANDIDATE, WAIT_CANDIDATE)


class AdapterError(RuntimeError):
    """The adapter cannot describe the live state; it never authorizes input."""


class TacticsAdapter:
    """Read-only snapshot builder + frozen chooser for one player menu."""

    def __init__(self, probe, policy, clock=time.time):
        self.p = probe
        # A bad policy is a configuration error, not a runtime condition: the
        # runner validates (and fails closed at boot) before any input.
        self.policy = validate_policy(policy)
        self.clock = clock
        self.last_evaluation = None
        self.last_snapshot = None
        self.last_candidate_ids = []
        self.last_age = None
        self.plans = {}

    def observe(self):
        """The candidates the engine currently offers, plus their plans.

        Candidates are emitted in id order (move, wait) so a ``select: first``
        rule does not silently depend on read order.
        """
        plans = {}
        try:
            plans[MOVE_CANDIDATE] = self.p.plan_identified_move()
        except Exception:
            plans[MOVE_CANDIDATE] = None
        try:
            plans[WAIT_CANDIDATE] = self.p.plan_identified_wait()
        except Exception:
            plans[WAIT_CANDIDATE] = None
        candidates = []
        if plans[MOVE_CANDIDATE] is not None:
            candidates.append({"id": MOVE_CANDIDATE, "kind": "move",
                               "action_id": MOVE_CMD, "legal": True, "cost": 0})
        if plans[WAIT_CANDIDATE] is not None:
            candidates.append({"id": WAIT_CANDIDATE, "kind": "wait",
                               "action_id": WAIT_CMD, "legal": True, "cost": 0})
        return candidates, plans

    @staticmethod
    def actor_facts(owner):
        """The verified owner row -> the snapshot actor (no inferred fields)."""
        if owner is None or owner.get("id") in (None, 0xFF):
            raise AdapterError("no verified owner row")
        return {
            "name": owner["name_text"], "id": owner["id"], "job_id": owner["job"],
            "side": "player" if owner.get("side_bit") is False else "enemy",
            "hp": owner.get("hp"), "max_hp": owner.get("max_hp"),
            "mp": owner.get("mp"), "max_mp": owner.get("max_mp"),
            "ct": owner.get("ct"),
            "tile": [owner.get("x"), owner.get("y")],
        }

    def snapshot(self, owner, candidates, age_seconds):
        if age_seconds is None:
            raise AdapterError("missing observation age")
        return {"schema": SNAPSHOT_SCHEMA, "identity": "verified",
                "actor": self.actor_facts(owner), "candidates": list(candidates),
                "age_seconds": float(age_seconds)}

    def choose(self, owner, observed_at=None):
        """Evaluate the policy for this owner; returns the full evaluation.

        ``observed_at`` is the wall time of the owner observation. Out of
        caution the age is only ever derived here, never assumed: a caller
        that cannot say when the state was read must not commit.
        """
        candidates, plans = self.observe()
        age = None if observed_at is None else max(0.0, self.clock() - observed_at)
        self.plans = plans
        self.last_candidate_ids = [c["id"] for c in candidates]
        self.last_age = age
        if age is None:
            # Unknown freshness == no observation: fail closed through the
            # same schema path the runtime's other rejections use.
            evaluation = {"outcome": "none", "reason": "snapshot-invalid",
                          "scope": None, "rule_id": None, "decision": None,
                          "detail": "adapter has no observation timestamp"}
            self.last_snapshot = None
            self.last_evaluation = evaluation
            return evaluation
        snap = self.snapshot(owner, candidates, age)
        evaluation = evaluate(snap, self.policy)
        self.last_snapshot = snap
        self.last_evaluation = evaluation
        return evaluation
