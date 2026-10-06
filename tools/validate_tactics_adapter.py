"""A5.3 pure-host suite for the conditional-tactics adapter seam.

Two layers, both offline:

* adapter-level: the snapshot the live adapter builds and the chooser's
  decision over it (including the engine-fact condition that flips Move to
  Wait, stale/missing observation timestamps, and an offering menu with no
  candidates at all);
* runtime-level: the *real* `BattleRuntime._drive_player_boundary` code path
  with a policy configured, proving that a decision it cannot back with the
  engine's current menu issues ZERO key writes (a changed candidate cancels
  the commit instead of silently committing the policy's unselected Wait),
  and that a policy-driven turn reaches the event stream with its rule
  metadata through the real CLI.

Synthetic RAM certifies control flow and rejection behavior only. It does not
show that any candidate is engine-legal in the game, which only live runs can.

    python tools/validate_tactics_adapter.py
"""
import argparse
import json
import os

from autobattle_identity import ActorAdapter
from autobattle_runtime import BattleRuntime
from probe_control_handoff import CMD_CURSOR
from tactics_adapter import MOVE_CANDIDATE, WAIT_CANDIDATE, TacticsAdapter
from tactics_policy import PolicyError

from validate_actor_identity import fixture as identity_fixture, write_int


def policy(**overrides):
    doc = {"schema": "ffta-tactics-policy/1", "fallback": "wait",
           "assignments": {}}
    doc.update(overrides)
    return doc


def when_match(kind, **extra):
    cond = {"kind": kind}
    cond.update(extra)
    return cond


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", default="outputs/autobattle/a53-tactics-adapter")
    args = parser.parse_args(argv)
    root = args.out_root
    os.makedirs(root, exist_ok=True)
    checks = []

    def check(label, fn):
        fn()
        checks.append(label)
        print("PASS", label, flush=True)

    def raises(label, error, fn):
        def run():
            try:
                fn()
            except error:
                return
            raise AssertionError(f"{label}: expected {error.__name__}")
        check(label, run)

    def session_with_owner():
        """A verified fresh-menu owner for slot 6 plus a runtime on that state."""
        s = identity_fixture()
        s.receipt["roster"]["ram_named_slots"] = [6]
        session_root = os.path.join(root, "synthetic")
        os.makedirs(session_root, exist_ok=True)
        runtime = BattleRuntime(s, {"scenario_id": "synthetic-policy"}, "host",
                                session_root, verbose=False)
        runtime.adapter, runtime.g = ActorAdapter(s), s.g
        rows = runtime.adapter.snapshot()
        runtime.adapter.observe(runtime.p, rows)          # first sample
        owner = runtime.adapter.observe(runtime.p, rows)  # paired sample
        assert owner is not None, "fixture did not yield a fresh-menu owner"
        runtime.owner = owner
        runtime.p.active_player_slot = owner["slot"]
        runtime._owner_observed_at = 1000.0
        return s, runtime, owner

    def adapter_for(runtime, doc, now=1000.5):
        return TacticsAdapter(runtime.p, doc, clock=lambda: now)

    # -- the offered candidate set -----------------------------------------
    def offers_move_and_wait_from_ram():
        _s, runtime, _owner = session_with_owner()
        ta = adapter_for(runtime, policy())
        candidates, plans = ta.observe()
        assert [c["id"] for c in candidates] == [MOVE_CANDIDATE, WAIT_CANDIDATE], candidates
        assert [c["kind"] for c in candidates] == ["move", "wait"]
        assert [c["action_id"] for c in candidates] == [0, 2]
        assert all(c["legal"] and c["cost"] == 0 for c in candidates)
        assert plans["move"]["kind"] == "identified-move"
        assert plans["wait"]["kind"] == "identified-wait"
    check("the adapter offers only the commands the engine menu names, in id order",
          offers_move_and_wait_from_ram)

    def closed_menu_offers_nothing():
        _s, runtime, _owner = session_with_owner()
        write_int(runtime.g, CMD_CURSOR, 3)  # not a known command id
        ta = adapter_for(runtime, policy())
        candidates, _plans = ta.observe()
        assert candidates == []
        evaluation = ta.choose(runtime.owner, observed_at=1000.0)
        assert evaluation["outcome"] == "none"
        assert evaluation["reason"] == "no-legal-candidate"
        assert evaluation["decision"] is None
    check("an unnamed command offers no candidates (no-legal-candidate, no commit)",
          closed_menu_offers_nothing)

    # -- rule-driven selection ---------------------------------------------
    def rules_select_each_candidate():
        _s, runtime, owner = session_with_owner()
        by_player = {"party": {"player": {
            "rules": [{"id": "hold", "when": when_match("wait"), "select": "first"}]}}}
        evaluation = adapter_for(runtime, policy(assignments=by_player)).choose(
            owner, observed_at=1000.0)
        assert evaluation["outcome"] == "selected"
        assert evaluation["decision"]["candidate_id"] == WAIT_CANDIDATE
        assert evaluation["rule_id"] == "hold" and evaluation["scope"] == "party"
        by_move = {"party": {"player": {
            "rules": [{"id": "walk", "when": when_match("move"), "select": "first"}]}}}
        evaluation = adapter_for(runtime, policy(assignments=by_move)).choose(
            owner, observed_at=1000.0)
        assert evaluation["decision"]["candidate_id"] == MOVE_CANDIDATE
        assert evaluation["rule_id"] == "walk"
    check("a rule selects each offered candidate through the adapter",
          rules_select_each_candidate)

    def engine_fact_flips_the_decision():
        """The live conditional family: one engine-read actor fact, two rules."""
        doc = policy(assignments={"party": {"player": {"rules": [
            {"id": "hold-when-hurt", "when": when_match("wait", actor_hp_pct={"lte": 50}),
             "select": "first"},
            {"id": "advance-when-healthy", "when": when_match("move"),
             "select": "first"},
        ]}}})
        _s, runtime, owner = session_with_owner()
        runtime.owner["hp"], runtime.owner["max_hp"] = 20, 100
        hurt = adapter_for(runtime, doc).choose(runtime.owner, observed_at=1000.0)
        assert hurt["decision"]["candidate_id"] == WAIT_CANDIDATE
        assert hurt["rule_id"] == "hold-when-hurt"
        runtime.owner["hp"], runtime.owner["max_hp"] = 90, 100
        healthy = adapter_for(runtime, doc).choose(runtime.owner, observed_at=1000.0)
        assert healthy["decision"]["candidate_id"] == MOVE_CANDIDATE
        assert healthy["rule_id"] == "advance-when-healthy"
    check("an engine-read HP condition flips the same policy from Move to Wait",
          engine_fact_flips_the_decision)

    def scope_precedence_and_fallback_hold_live():
        doc = policy(
            fallback="wait",
            assignments={
                "characters": {"Marche#6": {"rules": [
                    {"id": "char-only-wait", "when": when_match("wait"), "select": "first"}]}},
                "party": {"player": {"rules": [
                    {"id": "party-never", "when": {"ability_name": "Cure"}, "select": "first"}]}},
            })
        _s, runtime, owner = session_with_owner()
        evaluation = adapter_for(runtime, doc).choose(owner, observed_at=1000.0)
        assert evaluation["scope"] == "character"
        assert evaluation["decision"]["candidate_id"] == WAIT_CANDIDATE
        no_wait = policy(assignments={"party": {"player": {"rules": [
            {"id": "no-wait", "when": when_match("move"), "select": "first"}]}}},
            fallback="none")
        fresh = adapter_for(runtime, no_wait).choose(owner, observed_at=1000.0)
        assert fresh["decision"]["candidate_id"] == MOVE_CANDIDATE
    check("character scope beats party scope and an explicit no-match returns None",
          scope_precedence_and_fallback_hold_live)

    # -- freshness / fail-closed ------------------------------------------
    def stale_or_missing_observation_never_commits():
        _s, runtime, owner = session_with_owner()
        ta = adapter_for(runtime, policy(observation={"max_age_seconds": 2.0}))
        stale = ta.choose(owner, observed_at=995.0)
        assert stale["outcome"] == "none" and stale["reason"] == "snapshot-stale"
        assert stale["decision"] is None
        fresh = ta.choose(owner, observed_at=999.0)
        assert fresh["decision"] is not None
        unknown = ta.choose(owner, observed_at=None)
        assert unknown["outcome"] == "none"
        assert unknown["reason"] == "snapshot-invalid"
        assert unknown["decision"] is None
    check("a stale or timestamp-less observation never commits",
          stale_or_missing_observation_never_commits)

    def bad_policy_fails_at_construction():
        _s, runtime, _owner = session_with_owner()
        raises("unknown policy key rejected by the adapter",
               PolicyError, lambda: adapter_for(runtime, policy(extras=1)))
    check("a bad policy cannot even construct the adapter", bad_policy_fails_at_construction)

    # -- runtime: no input on a decision it cannot back --------------------
    def runtime_cancels_a_changed_candidate():
        """The engine changes the menu between the decision and the drive."""
        _s, runtime, _owner = session_with_owner()
        doc = policy(assignments={"party": {"player": {"rules": [
            {"id": "walk", "when": when_match("move"), "select": "first"}]}}})
        runtime.tactics = TacticsAdapter(runtime.p, doc, clock=lambda: 1000.5)
        decide = runtime.tactics.choose

        def choose_then_change_menu(owner, observed_at=None):
            evaluation = decide(owner, observed_at)
            # the menu the policy read is gone by drive time: the command
            # cursor now reads Action, so the Move plan no longer exists and
            # the identified-Wait fallback WOULD otherwise close the turn
            write_int(runtime.g, CMD_CURSOR, 1)
            return evaluation

        runtime.tactics.choose = choose_then_change_menu
        before = len(runtime.s.write_ledger)
        runtime._drive_player_boundary()
        assert len(runtime.s.write_ledger) == before, "cancelled candidate still pressed keys"
        events = [json.loads(line) for line in
                  open(runtime.events_path, encoding="utf-8") if line.strip()]
        assert not [e for e in events if e["kind"] == "turn"], "a turn was claimed"
        assert any("commit cancelled" in (e.get("note") or "") for e in events), events
        runtime._input_log.close()
    check("a policy-chosen candidate the engine no longer offers cancels with zero input",
          runtime_cancels_a_changed_candidate)

    def runtime_issues_no_input_when_the_policy_matches_nothing():
        _s, runtime, _owner = session_with_owner()
        doc = policy(fallback="none", assignments={"party": {"player": {"rules": [
            {"id": "needs-cure", "when": {"ability_name": "Cure"}, "select": "first"}]}}})
        runtime.tactics = TacticsAdapter(runtime.p, doc, clock=lambda: 1000.5)
        before = len(runtime.s.write_ledger)
        runtime._drive_player_boundary()
        assert len(runtime.s.write_ledger) == before
        events = [json.loads(line) for line in
                  open(runtime.events_path, encoding="utf-8") if line.strip()]
        assert any("selected no candidate (no-rule-match)" in (e.get("note") or "")
                   for e in events), events
        assert not [e for e in events if e["kind"] == "turn"]
        runtime._input_log.close()
    check("no rule match and no fallback issues zero input on the real runtime path",
          runtime_issues_no_input_when_the_policy_matches_nothing)

    # -- runtime through the real CLI --------------------------------------
    def cli_records_the_matched_rule():
        from unittest.mock import patch
        import shutil
        import run_autobattle
        from validate_transport_paths import FakeSession, FakeWorld
        # a fresh run directory: the runner APPENDS to events.jsonl, and a
        # reused directory would silently mix two runs' turns (C3's offline
        # gate rejects exactly that)
        run_dir = os.path.join(root, "cli")
        shutil.rmtree(run_dir, ignore_errors=True)
        os.makedirs(run_dir, exist_ok=True)
        policy_path = os.path.join(run_dir, "policy.json")
        with open(policy_path, "w", encoding="utf-8") as fh:
            json.dump(policy(assignments={"party": {"player": {"rules": [
                {"id": "hold", "when": when_match("wait"), "select": "first"}]}}}), fh)
        scenario = os.path.join(run_dir, "scenario.json")
        with open(scenario, "w", encoding="utf-8") as fh:
            json.dump({"scenario_id": "policy-wait"}, fh)
        world = FakeWorld()
        session = FakeSession(world)
        world.identified_move, world.allow_seeds = True, True
        with patch.object(run_autobattle, "FixtureSession", lambda *a, **kw: session):
            rc = run_autobattle.main(
                ["--scenario", scenario, "--out-root", root, "--run-id", "cli",
                 "--yes", "--max-turns", "1", "--wall-timeout", "60",
                 "--tactics-policy", policy_path])
        assert rc in (0, 1), rc
        receipt = json.load(open(os.path.join(run_dir, "run.json"), encoding="utf-8"))
        assert receipt["tactics_policy"]["schema"] == "ffta-tactics-policy/1"
        assert receipt["tactics_policy"]["scopes"] == ["party"]
        assert receipt["tactics_policy"]["path"] == policy_path
        assert policy_path in receipt["input_sha256"], receipt["input_sha256"].keys()
        decisions = receipt["tactics_policy"]["decisions"]
        assert decisions, "no policy decision reached the receipt"
        first = decisions[0]
        assert first["rule_id"] == "hold" and first["scope"] == "party"
        assert first["outcome"] == "selected" and first["reason"] == "rule:matched"
        assert first["candidates"] == [MOVE_CANDIDATE, WAIT_CANDIDATE], first
        assert isinstance(first["age_seconds"], float) and first["age_seconds"] < 3.0
        events = [json.loads(line) for line in
                  open(os.path.join(run_dir, "events.jsonl"), encoding="utf-8")
                  if line.strip()]
        turns = [e for e in events if e["kind"] == "turn"]
        assert len(turns) == 1, turns
        assert turns[0]["selected_action"]["kind"] == "identified-wait"
        assert turns[0]["tactics"]["rule_id"] == "hold"
        assert turns[0]["engine_result"]["verified"]
    check("the real CLI records the matched rule on a policy-driven turn",
          cli_records_the_matched_rule)

    def cli_rejects_a_bad_policy_before_booting():
        import run_autobattle
        from unittest.mock import patch
        from validate_transport_paths import FakeSession, FakeWorld
        bad = os.path.join(root, "bad-policy.json")
        with open(bad, "w", encoding="utf-8") as fh:
            json.dump({"schema": "ffta-tactics-policy/1", "fallback": "retreat"}, fh)
        booted = []
        with patch.object(run_autobattle, "FixtureSession",
                          lambda *a, **kw: booted.append(1)):
            rc = run_autobattle.main(["--tactics-policy", bad, "--yes"])
        assert rc == 2 and not booted, (rc, booted)
    check("a bad policy is rejected before the emulator is touched",
          cli_rejects_a_bad_policy_before_booting)

    with open(os.path.join(root, "checks.json"), "w", encoding="utf-8") as fh:
        json.dump({"checks": checks, "passed": len(checks),
                   "scope": "synthetic control-flow evidence only; no engine "
                            "legality or live acceptance claimed"},
                  fh, indent=2)
    print(f"TACTICS ADAPTER PASS: {len(checks)} checks")


if __name__ == "__main__":
    main()
