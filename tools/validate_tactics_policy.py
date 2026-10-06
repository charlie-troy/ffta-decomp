"""A5.2 pure-host regression suite for the frozen tactics-policy contract.

Every check runs the shipped `tools/tactics_policy.py` module directly: no
ROM, no emulator, no engine state. It certifies control flow, schema
rejection and determinism only -- it never claims a candidate is
engine-legal in the game, because only the adapter's live legality read can
establish that.

    python tools/validate_tactics_policy.py
"""
import argparse
import copy
import glob
import json
import os

from tactics_policy import (
    REASON_FALLBACK_WAIT, REASON_IDENTITY_UNVERIFIED, REASON_NO_LEGAL_CANDIDATE,
    REASON_NO_RULE_MATCH, REASON_SNAPSHOT_INVALID, REASON_SNAPSHOT_STALE,
    SCHEMA, SNAPSHOT_SCHEMA, STATUS_BITS,
    PolicyError, SnapshotError, choose_action, evaluate, hp_percent,
    load_policy_file, matches, select, statuses_present, target_statuses,
    validate_policy, validate_snapshot,
)


def policy(**overrides):
    doc = {"schema": SCHEMA, "fallback": "wait", "assignments": {}}
    doc.update(overrides)
    return doc


def cand(cid, kind="wait", action_id=2, **overrides):
    base = {"id": cid, "kind": kind, "action_id": action_id, "legal": True, "cost": 0}
    base.update(overrides)
    return base


def actor(name="Marche", unit_id=7, job_id=5, side="player", **overrides):
    base = {"name": name, "id": unit_id, "job_id": job_id, "side": side,
            "hp": 100, "max_hp": 100, "mp": 10, "max_mp": 10}
    base.update(overrides)
    return base


def snap(actors=None, candidates=None, age=0.0, identity="verified", **overrides):
    doc = {"schema": SNAPSHOT_SCHEMA, "identity": identity,
           "actor": actors if actors is not None else actor(),
           "candidates": candidates if candidates is not None else [cand("w1")],
           "age_seconds": age}
    doc.update(overrides)
    return doc


def ruleset(*rules, fallback=None):
    out = {"rules": [dict(rule) for rule in rules]}
    if fallback is not None:
        out["fallback"] = fallback
    return out


def rule(rule_id, when=None, select="first", **overrides):
    base = {"id": rule_id, "when": when or {}, "select": select}
    base.update(overrides)
    return base


def enemy(cid, hp, maximum=100, **overrides):
    return cand(cid, "ability", action_id=10, relation="enemy", target_hp=hp,
                target_max_hp=maximum, target={"kind": "unit", "id": 20},
                **overrides)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", default="outputs/autobattle/a52-tactics-policy")
    parser.add_argument("--configs", default="configs/tactics")
    parser.add_argument("--no-mutation-check", action="store_true",
                        help="skip the non-vacuity check (used by that check itself)")
    args = parser.parse_args(argv)
    # Accept the roadmap's exact CLI from any cwd: a relative --configs that
    # does not resolve here is retried against the repository root.
    if not os.path.isdir(args.configs):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(repo_root, args.configs)
        if os.path.isdir(candidate):
            args.configs = candidate
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

    # -- fallback ----------------------------------------------------------
    def empty_policy_falls_back_to_legal_wait():
        result = evaluate(snap(candidates=[cand("w1")]), policy())
        assert result["outcome"] == "fallback" and result["reason"] == REASON_FALLBACK_WAIT
        assert result["scope"] is None and result["rule_id"] == "fallback"
        decision = result["decision"]
        assert decision["candidate_id"] == "w1" and decision["fallback"] is True
        assert decision["kind"] == "wait" and choose_action(snap(), policy()) == decision
    check("empty policy falls back to the explicit legal Wait", empty_policy_falls_back_to_legal_wait)

    def fallback_none_is_the_documented_no_match_path():
        result = evaluate(snap(candidates=[cand("w1")]), policy(fallback="none"))
        assert result["outcome"] == "none" and result["reason"] == REASON_NO_RULE_MATCH
        assert result["decision"] is None
        assert choose_action(snap(candidates=[cand("w1")]), policy(fallback="none")) is None
    check("fallback none returns None (documented no-match path)", fallback_none_is_the_documented_no_match_path)

    def fallback_wait_without_a_legal_wait_returns_none():
        doc = policy()
        snap_ = snap(candidates=[cand("m1", "move", 0, relation="enemy")])
        result = evaluate(snap_, doc)
        assert result["outcome"] == "none" and result["reason"] == REASON_NO_LEGAL_CANDIDATE
        assert choose_action(snap_, doc) is None
        illegal = snap(candidates=[cand("w1", legal=False)])
        assert evaluate(illegal, doc)["reason"] == REASON_NO_LEGAL_CANDIDATE
    check("fallback wait with no legal Wait candidate returns None", fallback_wait_without_a_legal_wait_returns_none)

    def empty_candidate_set_returns_none():
        result = evaluate(snap(candidates=[]), policy())
        assert result["outcome"] == "none" and result["reason"] == REASON_NO_LEGAL_CANDIDATE
    check("empty candidate set returns None", empty_candidate_set_returns_none)

    # -- predicates --------------------------------------------------------
    wounded = policy(assignments={"party": {"player": ruleset(
        rule("finish-wounded-enemy", {"relation": "enemy", "target_hp_pct": {"lte": 25}},
             "lowest-target-hp"))}})

    def wounded_enemy_is_selected():
        players = [enemy("e-healthy", 100), enemy("e-wounded", 20),
                   enemy("e-middle", 40), cand("ally-low", "ability", 11,
                                               relation="ally", target_hp=10,
                                               target_max_hp=100,
                                               target={"kind": "unit", "id": 3})]
        result = evaluate(snap(candidates=players), wounded)
        assert result["outcome"] == "selected" and result["rule_id"] == "finish-wounded-enemy"
        assert result["scope"] == "party" and result["decision"]["candidate_id"] == "e-wounded"
        assert result["decision"]["target_id"] == 20
    check("relation+HP threshold selects the wounded enemy, not the wounded ally",
          wounded_enemy_is_selected)

    def healthy_enemy_is_not_selected_by_threshold():
        result = evaluate(snap(candidates=[enemy("e-healthy", 100), cand("w1")]), wounded)
        assert result["outcome"] == "fallback" and result["decision"]["kind"] == "wait"
    check("healthy enemy does not satisfy the wounded threshold (falls back)",
          healthy_enemy_is_not_selected_by_threshold)

    def boundary_is_inclusive_and_lt_is_strict():
        exact = policy(assignments={"party": {"player": ruleset(
            rule("at-quarter", {"target_hp_pct": {"lte": 25}}, "first"),)}},
            fallback="none")
        above = policy(assignments={"party": {"player": ruleset(
            rule("at-quarter", {"target_hp_pct": {"lt": 25}}, "first"),)}},
            fallback="none")
        assert choose_action(snap(candidates=[enemy("e", 25)]), exact) is not None
        assert choose_action(snap(candidates=[enemy("e", 26)]), exact) is None
        assert choose_action(snap(candidates=[enemy("e", 25)]), above) is None
        assert choose_action(snap(candidates=[enemy("e", 24)]), above) is not None
    check("HP-percent boundaries are inclusive for lte and strict for lt",
          boundary_is_inclusive_and_lt_is_strict)

    def hp_percent_is_floored():
        assert hp_percent(1, 3) == 33
        assert hp_percent(25, 100) == 25
        assert hp_percent(100, 100) == 100
        assert hp_percent(200, 100) == 100
        assert hp_percent(None, 100) is None and hp_percent(5, 0) is None
    check("HP percent is floored and rejects missing/zero-max facts", hp_percent_is_floored)

    def actor_hp_threshold_uses_actor_facts():
        doc = policy(assignments={"party": {"player": ruleset(
            rule("hurt", {"actor_hp_pct": {"lte": 30}}, "first"))}}, fallback="none")
        wounded_actor = {k: v for k, v in actor().items() if k not in ("hp", "max_hp")}
        assert choose_action(snap(actors=actor(hp=30)), doc) is not None
        assert choose_action(snap(actors=actor(hp=31)), doc) is None
        assert choose_action(snap(actors=wounded_actor), doc) is None
    check("actor HP-percent predicate reads actor facts and fails closed when absent",
          actor_hp_threshold_uses_actor_facts)

    def remaining_mp_after_cost():
        enough = policy(assignments={"party": {"player": ruleset(
            rule("cheap", {"remaining_mp_after_cost": {"gte": 1}}, "first"))}},
            fallback="none")
        free = policy(assignments={"party": {"player": ruleset(
            rule("affordable", {"remaining_mp_after_cost": {"gte": 0}}, "first"))}},
            fallback="none")
        cost9 = cand("a9", "ability", 12, cost=9)
        cost10 = cand("a10", "ability", 12, cost=10)
        assert choose_action(snap(actors=actor(mp=10), candidates=[cost9]), enough)["candidate_id"] == "a9"
        assert choose_action(snap(actors=actor(mp=10), candidates=[cost10]), enough) is None
        assert choose_action(snap(actors=actor(mp=10), candidates=[cost10]), free)["candidate_id"] == "a10"
        no_mp = {k: v for k, v in actor().items() if k != "mp"}
        assert choose_action(snap(actors=no_mp, candidates=[cost9]), free) is None
    check("remaining MP after cost predicate handles the exact boundary and missing MP",
          remaining_mp_after_cost)

    def ability_name_predicate_is_kind_scoped():
        doc = policy(assignments={"party": {"player": ruleset(
            rule("cast-cure", {"ability_name": "Cure"}, "first"))}}, fallback="none")
        nuke = cand("nuke", "ability", 10, ability_name="Fire")
        cure = cand("cure", "ability", 12, ability_name="Cure")
        walk = cand("walk", "move", 0)
        assert choose_action(snap(candidates=[nuke, cure, walk]), doc)["candidate_id"] == "cure"
        assert choose_action(snap(candidates=[nuke, walk]), doc) is None
        move_with_name = cand("m", "move", 0, ability_name="Cure")
        assert choose_action(snap(candidates=[move_with_name]), doc) is None
    check("ability-name predicate matches identified abilities only", ability_name_predicate_is_kind_scoped)

    def action_id_predicate_matches_any_kind():
        doc = policy(assignments={"party": {"player": ruleset(
            rule("engine-command-0", {"action_id": 0}, "first"))}}, fallback="none")
        assert choose_action(snap(candidates=[cand("w", "wait", 2), cand("m", "move", 0)]), doc)["candidate_id"] == "m"
    check("action-id predicate matches the engine command id", action_id_predicate_matches_any_kind)

    def status_predicates_decode_the_frozen_bits():
        poisoned = {"0xe9": STATUS_BITS["Poison"][1]}
        doc = policy(assignments={"party": {"player": ruleset(
            rule("hit-poisoned", {"target_status_present": ["Poison"]}, "first"))}},
            fallback="none")
        clean = policy(assignments={"party": {"player": ruleset(
            rule("hit-clean", {"target_status_absent": ["Poison"]}, "first"))}},
            fallback="none")
        marked = enemy("e", 50, target_status_bytes=poisoned)
        clear = enemy("e", 50, target_status_bytes={"0xe9": 0})
        assert choose_action(snap(candidates=[marked]), doc) is not None
        assert choose_action(snap(candidates=[clear]), doc) is None
        assert choose_action(snap(candidates=[clear]), clean) is not None
        assert choose_action(snap(candidates=[marked]), clean) is None
        # absent facts are NOT "known absent": no status bytes means ineligible
        unknown = enemy("e-unknown", 50)
        assert choose_action(snap(candidates=[unknown]), clean) is None
        normalized = validate_snapshot(snap(candidates=[marked, unknown]))
        subject = normalized["actor"]
        assert target_statuses(subject, normalized["candidates"][0]) == {"Poison"}
        assert target_statuses(subject, normalized["candidates"][1]) is None
        assert statuses_present(subject) is None
    check("status present/absent predicates decode the frozen bits and fail closed on unknown",
          status_predicates_decode_the_frozen_bits)

    def actor_status_predicates():
        doc = policy(assignments={"party": {"player": ruleset(
            rule("disabled-actor", {"actor_status_present": ["Disable"]}, "first"))}},
            fallback="none")
        clean = policy(assignments={"party": {"player": ruleset(
            rule("not-disabled", {"actor_status_absent": ["Disable"]}, "first"))}},
            fallback="none")
        disabled = actor(status_bytes={"0xeb": STATUS_BITS["Disable"][1]})
        assert choose_action(snap(actors=disabled), doc) is not None
        assert choose_action(snap(actors=disabled), clean) is None
        assert choose_action(snap(actors=actor(status_bytes={"0xeb": 0})), clean) is not None
        assert choose_action(snap(actors=actor()), clean) is None
    check("actor status predicates read actor bytes and fail closed when absent",
          actor_status_predicates)

    # -- precedence --------------------------------------------------------
    def character_beats_job_beats_party():
        doc = policy(assignments={
            "characters": {"Marche#7": ruleset(rule("char-wait", {"kind": "wait"}, "first"))},
            "jobs": {"5": ruleset(rule("job-move", {"kind": "move"}, "first"))},
            "party": {"player": ruleset(rule("party-ability", {"kind": "ability"}, "first"))},
        })
        candidates = [cand("w", "wait", 2), cand("m", "move", 0), cand("a", "ability", 9)]
        assert choose_action(snap(candidates=candidates), doc)["rule_id"] == "char-wait"
        assert choose_action(snap(candidates=candidates), doc)["scope"] == "character"
        without_chars = copy.deepcopy(doc)
        without_chars["assignments"].pop("characters")
        assert choose_action(snap(candidates=candidates), without_chars)["rule_id"] == "job-move"
        assert choose_action(snap(candidates=candidates), without_chars)["scope"] == "job"
        without_jobs = copy.deepcopy(without_chars)
        without_jobs["assignments"].pop("jobs")
        assert choose_action(snap(candidates=candidates), without_jobs)["rule_id"] == "party-ability"
        assert choose_action(snap(candidates=candidates), without_jobs)["scope"] == "party"
    check("assignment precedence is character -> job -> party", character_beats_job_beats_party)

    def matched_scope_does_not_fall_through():
        doc = policy(assignments={
            "characters": {"Marche#7": ruleset(rule("needs-cure", {"ability_name": "Cure"}, "first"))},
            "jobs": {"5": ruleset(rule("job-move", {"kind": "move"}, "first"))},
        })
        result = evaluate(snap(candidates=[cand("m", "move", 0), cand("w", "wait", 2)]), doc)
        assert result["outcome"] == "fallback" and result["scope"] == "character"
        assert result["decision"]["rule_id"] == "fallback"
        assert result["decision"]["candidate_id"] == "w"
    check("a matched scope governs; it does not fall through to a lower scope",
          matched_scope_does_not_fall_through)

    def absent_character_assignment_falls_to_party():
        doc = policy(assignments={
            "characters": {"Marche#7": ruleset(rule("char-wait", {"kind": "wait"}, "first"))},
            "party": {"player": ruleset(rule("party-move", {"kind": "move"}, "first"))},
        })
        result = evaluate(snap(actors=actor(name="Montblanc", unit_id=5),
                               candidates=[cand("m", "move", 0), cand("w", "wait", 2)]), doc)
        assert result["scope"] == "party" and result["rule_id"] == "party-move"
    check("a character assignment for an absent unit falls through to party",
          absent_character_assignment_falls_to_party)

    def scope_fallback_override_wins():
        doc = policy(fallback="none", assignments={"party": {"player": ruleset(
            rule("never", {"kind": "ability"}, "first"), fallback="wait")}})
        result = evaluate(snap(candidates=[cand("w", "wait", 2)]), doc)
        assert result["outcome"] == "fallback" and result["reason"] == REASON_FALLBACK_WAIT
    check("a scope-level fallback overrides the policy default", scope_fallback_override_wins)

    def disabled_rules_are_skipped():
        doc = policy(assignments={"party": {"player": ruleset(
            rule("disabled", {"kind": "wait"}, "first", enabled=False),
            rule("enabled", {"kind": "move"}, "first"))}})
        result = evaluate(snap(candidates=[cand("m", "move", 0), cand("w", "wait", 2)]), doc)
        assert result["rule_id"] == "enabled"
        only_disabled = policy(assignments={"party": {"player": ruleset(
            rule("disabled", {"kind": "wait"}, "first", enabled=False))}})
        assert evaluate(snap(candidates=[cand("w", "wait", 2)]), only_disabled)["outcome"] == "fallback"
    check("disabled rules are skipped by the ordered walk", disabled_rules_are_skipped)

    # -- determinism, ties, duplicates -------------------------------------
    def ties_break_on_candidate_id_regardless_of_order():
        doc = policy(assignments={"party": {"player": ruleset(
            rule("weakest", {"relation": "enemy"}, "lowest-target-hp"))}})
        first = [enemy("e-b", 30), enemy("e-a", 30), enemy("e-c", 30)]
        second = list(reversed(first))
        assert choose_action(snap(candidates=first), doc)["candidate_id"] == "e-a"
        assert choose_action(snap(candidates=second), doc)["candidate_id"] == "e-a"
    check("equal-priority targets tie-break deterministically on candidate id",
          ties_break_on_candidate_id_regardless_of_order)

    def duplicate_ability_names_stay_deterministic():
        doc = policy(assignments={"party": {"player": ruleset(
            rule("any-cure", {"ability_name": "Cure", "relation": "ally"},
                 "lowest-target-hp"))}})
        a = cand("a", "ability", 12, ability_name="Cure", relation="ally",
                 target_hp=40, target_max_hp=100, target={"kind": "unit", "id": 3})
        b = cand("b", "ability", 12, ability_name="Cure", relation="ally",
                 target_hp=40, target_max_hp=100, target={"kind": "unit", "id": 4})
        assert choose_action(snap(candidates=[a, b]), doc)["candidate_id"] == "a"
        assert choose_action(snap(candidates=[b, a]), doc)["candidate_id"] == "a"
    check("duplicate ability names resolve deterministically by candidate id",
          duplicate_ability_names_stay_deterministic)

    def repeated_evaluation_is_identical():
        doc = policy(assignments={"party": {"player": ruleset(
            rule("weakest", {"relation": "enemy"}, "lowest-target-hp", note="doc"))}})
        snap_ = snap(candidates=[enemy("e2", 30), enemy("e1", 10)])
        assert choose_action(snap_, doc) == choose_action(copy.deepcopy(snap_), copy.deepcopy(doc))
    check("repeated evaluation returns an identical decision", repeated_evaluation_is_identical)

    def highest_selector_and_mp_selector():
        strongest = policy(assignments={"party": {"player": ruleset(
            rule("strongest", {"relation": "enemy"}, "highest-target-hp"))}})
        weakest_mp = policy(assignments={"party": {"player": ruleset(
            rule("drain", {"kind": "ability"}, "lowest-remaining-mp"))}})
        assert choose_action(snap(candidates=[enemy("e1", 10), enemy("e2", 90)]), strongest)[
            "candidate_id"] == "e2"
        assert choose_action(snap(actors=actor(mp=20), candidates=[
            cand("cheap", "ability", 1, cost=1), cand("dear", "ability", 1, cost=19)]), weakest_mp)[
            "candidate_id"] == "dear"
        # the selector's fact can be missing entirely: the rule is not selected
        no_score = policy(assignments={"party": {"player": ruleset(
            rule("weakest", {"kind": "move"}, "lowest-target-hp"))}})
        unorderable = snap(candidates=[cand("m", "move", 0), cand("w", "wait", 2)])
        result = evaluate(unorderable, no_score)
        assert result["outcome"] == "fallback" and result["decision"]["candidate_id"] == "w"
    check("highest/remaining-MP selectors order by their fact and skip unorderable candidates",
          highest_selector_and_mp_selector)

    # -- rejection ---------------------------------------------------------
    def bad_policies_rejected():
        good = {"schema": SCHEMA, "assignments": {}, "fallback": "wait",
                "observation": {"max_age_seconds": 3.0}}
        validate_policy(good)
        bad = {
            "unknown top-level key": {**good, "extras": 1},
            "unknown assignment scope": {**good, "assignments": {"monsters": {}}},
            "unknown observation key": {**good, "observation": {"max_age_seconds": 1, "ttl": 2}},
            "unknown fallback": {**good, "fallback": "retreat"},
            "unknown ruleset key": {**good, "assignments": {"party": {"player": {"rulez": []}}}},
            "unknown rule key": {**good, "assignments": {"party": {"player": {
                "rules": [{"id": "r", "select": "first", "then": "wait"}]}}}},
            "unknown when key": {**good, "assignments": {"party": {"player": {
                "rules": [{"id": "r", "select": "first", "when": {"distance": {"lte": 2}}}]}}}},
            "unknown selector": {**good, "assignments": {"party": {"player": {
                "rules": [{"id": "r", "select": "smartest"}]}}}},
            "duplicate rule id": {**good, "assignments": {"party": {"player": {
                "rules": [{"id": "r", "select": "first"}, {"id": "r", "select": "first"}]}}}},
            "unknown relation": {**good, "assignments": {"party": {"player": {
                "rules": [{"id": "r", "select": "first", "when": {"relation": "neutral"}}]}}}},
            "unknown kind": {**good, "assignments": {"party": {"player": {
                "rules": [{"id": "r", "select": "first", "when": {"kind": "item"}}]}}}},
            "unknown status name": {**good, "assignments": {"party": {"player": {
                "rules": [{"id": "r", "select": "first",
                           "when": {"target_status_present": ["Petrified"]}}]}}}},
            "case-sensitive status name": {**good, "assignments": {"party": {"player": {
                "rules": [{"id": "r", "select": "first",
                           "when": {"target_status_present": ["poison"]}}]}}}},
            "empty status list": {**good, "assignments": {"party": {"player": {
                "rules": [{"id": "r", "select": "first", "when": {"actor_status_absent": []}}]}}}},
            "missing schema": {"assignments": {}},
            "wrong schema": {**good, "schema": "ffta-tactics-policy/2"},
            "policy not an object": ["nope"],
        }
        for label, doc in bad.items():
            raises(f"rejects policy: {label}", PolicyError, lambda doc=doc: validate_policy(doc))
    check("unknown keys, values and schema versions are rejected", bad_policies_rejected)

    def bad_thresholds_rejected():
        for value in (101, -1, 25.5, True, "25", {}, {"lte": 25, "gte": 10},
                      {"around": 25}, None, [25]):
            doc = policy(assignments={"party": {"player": ruleset(
                rule("r", {"target_hp_pct": value}, "first"))}})
            raises(f"rejects threshold {value!r}", PolicyError, lambda doc=doc: validate_policy(doc))
        for value in (-1, 1.5, True, "0"):
            doc = policy(assignments={"party": {"player": ruleset(
                rule("r", {"remaining_mp_after_cost": {"gte": value}}, "first"))}})
            raises(f"rejects MP threshold {value!r}", PolicyError, lambda doc=doc: validate_policy(doc))
        doc = policy(assignments={"party": {"player": ruleset(
            rule("r", {"action_id": -1}, "first"))}})
        raises("rejects negative action id", PolicyError, lambda: validate_policy(doc))
        bool_doc = policy(assignments={"party": {"player": ruleset(
            rule("r", {"action_id": True}, "first"))}})
        raises("rejects boolean action id", PolicyError, lambda: validate_policy(bool_doc))
    check("invalid thresholds and malformed comparisons are rejected", bad_thresholds_rejected)

    def bad_assignment_keys_rejected():
        for key in ("Marche", "Marche#", "Marche#07", "Marche#-1", "Marche#999",
                    "Marche#7#8", "#7", "Marche#x"):
            doc = policy(assignments={"characters": {key: {"rules": []}}})
            raises(f"rejects character key {key!r}", PolicyError, lambda doc=doc: validate_policy(doc))
        for key in ("05", "abc", "-1", "5.0", ""):
            doc = policy(assignments={"jobs": {key: {"rules": []}}})
            raises(f"rejects job key {key!r}", PolicyError, lambda doc=doc: validate_policy(doc))
        for key in ("monsters", "PLAYER", ""):
            doc = policy(assignments={"party": {key: {"rules": []}}})
            raises(f"rejects party key {key!r}", PolicyError, lambda doc=doc: validate_policy(doc))
    check("malformed assignment keys are rejected", bad_assignment_keys_rejected)

    def unverified_identity_never_commits():
        for identity in ("ambiguous", "stale", "duplicate"):
            result = evaluate(snap(identity=identity), policy())
            assert result["outcome"] == "none" and result["reason"] == REASON_IDENTITY_UNVERIFIED
            assert result["decision"] is None
            assert choose_action(snap(identity=identity), policy()) is None
    check("an unverified actor identity never commits", unverified_identity_never_commits)

    def stale_snapshot_never_commits():
        doc = policy(observation={"max_age_seconds": 2.5})
        assert evaluate(snap(age=2.5), doc)["outcome"] == "fallback"
        stale = evaluate(snap(age=2.6), doc)
        assert stale["outcome"] == "none" and stale["reason"] == REASON_SNAPSHOT_STALE
        missing = snap()
        del missing["age_seconds"]
        assert evaluate(missing, doc)["reason"] == REASON_SNAPSHOT_INVALID
    check("a stale snapshot never commits; a missing age is invalid",
          stale_snapshot_never_commits)

    def invalid_snapshots_never_commit():
        cases = {
            "duplicate candidate id": snap(candidates=[cand("w1"), cand("w1", "move", 0)]),
            "missing actor job": snap(actors={k: v for k, v in actor().items() if k != "job_id"}),
            "bad side": snap(actors=actor(side="neutral")),
            "actor hp not an integer": snap(actors=actor(hp=1.5)),
            "unknown snapshot key": snap(extra="x"),
            "unknown candidate key": snap(candidates=[cand("w1", damage=5)]),
            "unknown status byte key": snap(candidates=[cand("w1", target_status_bytes={"0xee": 1})]),
            "status byte out of range": snap(candidates=[cand("w1", target_status_bytes={"0xe9": 300})]),
            "wrong snapshot schema": snap(schema="other/1"),
            "negative age": snap(age=-1),
        }
        for label, doc in cases.items():
            def run(doc=doc):
                try:
                    validate_snapshot(doc)
                except SnapshotError:
                    pass
                else:
                    raise AssertionError(f"{label}: expected SnapshotError")
                result = evaluate(doc, policy())
                assert result["outcome"] == "none" and result["reason"] == REASON_SNAPSHOT_INVALID, label
                assert result["decision"] is None
            check(f"rejects and never commits: {label}", run)
    check("malformed snapshots are rejected and never commit", invalid_snapshots_never_commit)

    def illegal_candidates_are_invisible_to_rules():
        illegal = cand("bad", "ability", 10, legal=False, relation="enemy",
                       target_hp=1, target_max_hp=100)
        doc = policy(assignments={"party": {"player": ruleset(
            rule("finish", {"relation": "enemy", "target_hp_pct": {"lte": 25}},
                 "lowest-target-hp"))}})
        assert evaluate(snap(candidates=[illegal]), doc)["outcome"] == "none"
        assert not matches(doc["assignments"]["party"]["player"]["rules"][0]["when"],
                           actor(), validate_snapshot(snap(candidates=[illegal]))["candidates"][0])
    check("engine-illegal candidates are never selectable", illegal_candidates_are_invisible_to_rules)

    def selector_fails_closed_without_facts():
        assert select([], "first", actor()) is None
        snapshot = validate_snapshot(snap(candidates=[cand("w1")]))
        assert select(snapshot["candidates"], "first", snapshot["actor"])["id"] == "w1"
    check("the selector is total: empty input yields no decision", selector_fails_closed_without_facts)

    # -- shipped presets ---------------------------------------------------
    def shipped_presets_validate():
        files = sorted(glob.glob(os.path.join(args.configs, "*.json")))
        assert files, f"no presets under {args.configs}"
        names = {os.path.basename(path) for path in files}
        for required in ("default.json", "damage-focused.json", "contrast-two-ally.json"):
            assert required in names, f"missing shipped preset {required}"
        for path in files:
            doc = load_policy_file(path)
            assert doc["schema"] == SCHEMA
        print(f"    presets validated: {sorted(names)}", flush=True)
    check("every shipped preset validates against the frozen schema",
          shipped_presets_validate)

    def contrast_preset_diverges_per_character():
        doc = load_policy_file(os.path.join(args.configs, "contrast-two-ally.json"))
        candidates = [cand("m1", "move", 0, relation="enemy"),
                      cand("w1", "wait", 2)]
        marche = evaluate(snap(actors=actor("Marche", 7, 5), candidates=candidates), doc)
        montblanc = evaluate(snap(actors=actor("Montblanc", 5, 5), candidates=candidates), doc)
        assert marche["scope"] == "character" and montblanc["scope"] == "character"
        assert marche["decision"]["candidate_id"] == "m1"
        assert montblanc["decision"]["candidate_id"] == "w1"
        assert marche["decision"]["kind"] != montblanc["decision"]["kind"]
    check("the contrast preset gives two same-job allies different decisions",
          contrast_preset_diverges_per_character)

    # -- non-vacuity: the suite must fail on a mutated contract -----------
    # A regression suite written against the same assumptions as the code
    # confirms the assumptions, not the result (CLAUDE.md). Each mutation
    # below disables one contract guarantee in a throwaway copy of the
    # module; every mutant must make this suite exit non-zero.
    def suite_can_fail():
        import shutil
        import subprocess
        import sys
        import tempfile
        module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "tactics_policy.py")
        with open(module_path, encoding="utf-8") as fh:
            source = fh.read()
        validator = os.path.abspath(__file__)
        mutations = {
            "legality gate removed":
                ('    if not candidate["legal"]:\n        return False',
                 "    pass  # MUTANT"),
            "identity gate removed":
                ('    if snap["identity"] != "verified":', "    if False:"),
            "staleness gate removed":
                ('    if snap["age_seconds"] > normalized_policy["observation"]["max_age_seconds"]:',
                 "    if False:"),
            "fallback ignores legality":
                ('    waits = [c for c in snap["candidates"] if c["legal"] and c["kind"] == "wait"]',
                 '    waits = [c for c in snap["candidates"] if c["kind"] == "wait"]'),
            "tie-break replaced by adapter order":
                ('        return min(scored, key=lambda pair: (pair[0], pair[1]["id"]))[1]',
                 "        return scored[0][1]"),
        }
        survivors = []
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(validator, os.path.join(tmp, os.path.basename(validator)))
            for label, (old, new) in mutations.items():
                assert old in source, f"mutation anchor missing: {label}"
                with open(os.path.join(tmp, "tactics_policy.py"), "w", encoding="utf-8") as fh:
                    fh.write(source.replace(old, new, 1))
                env = dict(os.environ)
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                result = subprocess.run(
                    [sys.executable, os.path.join(tmp, os.path.basename(validator)),
                     "--no-mutation-check", "--out-root", os.path.join(tmp, "out")],
                    cwd=tmp, capture_output=True, text=True, env=env)
                if result.returncode == 0:
                    survivors.append(label)
        assert not survivors, f"mutants survived the suite: {survivors}"
        print(f"    mutants rejected: {sorted(mutations)}", flush=True)
    if args.no_mutation_check:
        print("    (non-vacuity check skipped)", flush=True)
    else:
        check("the suite fails on every mutated contract (non-vacuity)", suite_can_fail)

    def damage_preset_prefers_the_weakest_enemy():
        doc = load_policy_file(os.path.join(args.configs, "damage-focused.json"))
        candidates = [enemy("e-strong", 100), enemy("e-weak", 5),
                      enemy("e-mid", 60), cand("ally", "ability", 11, relation="ally",
                                               target_hp=10, target_max_hp=100,
                                               target={"kind": "unit", "id": 2})]
        result = evaluate(snap(actors=actor("Marche", 7, 5), candidates=candidates), doc)
        assert result["outcome"] == "selected"
        assert result["decision"]["candidate_id"] == "e-weak"
    check("the damage-focused preset takes the weakest enemy", damage_preset_prefers_the_weakest_enemy)

    root = args.out_root
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "checks.json"), "w", encoding="utf-8") as fh:
        json.dump({"checks": checks, "passed": len(checks),
                   "scope": "pure host policy evaluation only; no engine legality or "
                            "ROM semantics claimed by this suite"}, fh, indent=2)
    print(f"TACTICS POLICY PASS: {len(checks)} checks")


if __name__ == "__main__":
    main()
