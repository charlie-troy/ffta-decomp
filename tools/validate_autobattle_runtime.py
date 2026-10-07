"""A3 validator: assert the runtime receipt contract from artifacts alone.

Roadmap A3: validate `events.jsonl` + `run.json` invariants — complete state
machine transitions, no unknown-null fields, bounded-stop reasons, and turn
records with positions before/after. This runs offline (no emulator) so it
can gate every run in CI or by hand.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

VALID_STATES = {"idle", "running", "takeover", "completed", "stalled",
                "connection_lost", "paused"}
TERMINAL = {"completed", "stalled", "connection_lost", "paused"}
KNOWN_KINDS = {"start", "guard", "boundary", "turn", "note", "stop"}
KNOWN_FIELDS = {"t", "kind", "scenario", "turn", "actor", "actor_slot",
                "control_mode", "selected_action", "selected_target",
                "position_before", "position_after", "state", "seeds",
                "router_hits", "note", "input_log", "actor_identity",
                "engine_result", "next_actor",
                # A5.3: the conditional-tactics receipt (policy path, outcome,
                # reason, matched scope/rule, observation age, offered
                # candidates). Null on every scenario-driven run.
                "tactics"}
# kinds whose presence after the terminal stop means the run kept driving:
# boundaries, turns, and notes about recovery cycles are all input activity
INPUT_EVENT_KINDS = {"boundary", "turn", "note"}
# C1 gap 1: the validator READS the raw write log (Astra round 4: the old
# validator never opened input-log.jsonl, so an injected log containing a
# successful post-STOP press passed validation). A "manual_key_write"
# record is input the player/agent sent AFTER the runner detached from a
# paused handoff — it is not automation input and never counts as a leak.
MANUAL_WRITE_EVENT = "manual_key_write"
STOP_EVENTS = ("stop_requested", "stop_observed")


def fail(msg, errors):
    errors.append(msg)


def validate(out_dir):
    errors = []
    run_path = os.path.join(out_dir, "run.json")
    ev_path = os.path.join(out_dir, "events.jsonl")
    if not os.path.exists(run_path):
        fail(f"missing {run_path}", errors)
        return errors
    if not os.path.exists(ev_path):
        fail(f"missing {ev_path}", errors)
        return errors
    with open(run_path, encoding="utf-8") as fh:
        run = json.load(fh)
    events = []
    with open(ev_path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                fail(f"events line {ln}: not JSON ({exc})", errors)
                continue
            events.append(rec)

    # schema conformance: no unknown fields, no null-required fields
    for i, rec in enumerate(events):
        unknown = set(rec) - KNOWN_FIELDS
        if unknown:
            fail(f"event {i}: unknown fields {sorted(unknown)}", errors)
        if rec.get("kind") not in KNOWN_KINDS:
            fail(f"event {i}: kind {rec.get('kind')!r} not in {sorted(KNOWN_KINDS)}",
                 errors)
        if rec.get("scenario") is None:
            fail(f"event {i}: scenario is null (must name the scenario)", errors)
        if rec.get("state") not in VALID_STATES:
            fail(f"event {i}: state {rec.get('state')!r} invalid", errors)

    # lifecycle: exactly one start (or two for a C3 resumed battle: leg 1
    # ended `paused`, leg 2 continues the SAME battle), exactly one terminal
    # stop, last state. A resume is only honest when the receipt marks it,
    # leg 1 ended paused with the emulator left running, and leg 2's start
    # SAYS it continues that handoff.
    kinds = [r.get("kind") for r in events]
    n_starts = kinds.count("start")
    starts = [r for r in events if r.get("kind") == "start"]
    stops = [r for r in events if r.get("kind") == "stop"]
    resumed = bool(run.get("resumed"))
    expected_starts = 2 if resumed else 1
    if n_starts != expected_starts:
        fail(f"expected exactly {expected_starts} start event(s)"
             + (" (resumed battle: leg 1 + leg 2)" if resumed else "")
             + f", got {n_starts}", errors)
    if resumed:
        if len(stops) < 1:
            fail("resumed battle but no stop events at all", errors)
        else:
            first, last = stops[0], stops[-1]
            if first.get("state") != "paused":
                fail(f"resumed battle: leg 1's first stop is "
                     f"{first.get('state')!r}, not 'paused' — the manual "
                     "handoff precondition is missing", errors)
            if not (starts[-1].get("note") or "").startswith("resume:"):
                fail("resumed battle: leg 2's start event must say it "
                     "continues a paused handoff (note 'resume: ...')",
                     errors)
    elif len(stops) == 1 and starts:
        if (starts[0].get("note") or "").startswith("resume:"):
            fail("start event claims a resume but run.json does not mark "
                 "'resumed' — an untracked second leg", errors)
    if len(stops) == 1:
        if stops[0].get("state") not in TERMINAL:
            fail(f"stop state {stops[0].get('state')!r} is not terminal", errors)
        if stops[0].get("state") != run.get("final_state"):
            fail("run.json final_state disagrees with the stop event", errors)
        reason = stops[0].get("note") or ""
        if stops[0].get("state") in ("completed", "stalled") and not reason:
            fail("terminal stop must record its reason", errors)
    elif len(stops) >= 2:
        if stops[-1].get("state") not in TERMINAL:
            fail(f"final stop state {stops[-1].get('state')!r} is not "
                 "terminal", errors)
        if stops[-1].get("state") != run.get("final_state"):
            fail("run.json final_state disagrees with the final stop event",
                 errors)
        reason = stops[-1].get("note") or ""
        if stops[-1].get("state") in ("completed", "stalled") and not reason:
            fail("terminal stop must record its reason", errors)

    # lifecycle guarantee: nothing the runtime does after the terminal stop
    # may issue or schedule input. Astra's live check: an events file with a
    # second boundary after `completed` passed the old validator. A stop is
    # the LAST event; any boundary/turn/note after it fails, and a pause
    # handoff must record that the emulator was left running.
    if stops:
        last_stop_idx = max(i for i, r in enumerate(events)
                            if r.get("kind") == "stop")
        # resumed battles: leg-2 activity sits between the two stops, so
        # the no-input-after-terminal rule applies to the FINAL stop only
        # (leg 1's paused stop is a handoff, not a terminal — C3 resume is
        # input after it BY DESIGN, the player's move plus the automated
        # continuation). With no stops at all the lifecycle check above
        # has already failed; there is nothing further to scan.
        for i in range(last_stop_idx + 1, len(events)):
            if events[i].get("kind") in INPUT_EVENT_KINDS:
                fail(f"event {i}: {events[i].get('kind')} after the terminal "
                     "stop — input activity after the run ended", errors)
    if stops and stops[0].get("state") == "paused":
        handoff = run.get("emulator_handoff")
        if handoff not in ("left-running-for-player", "terminated"):
            fail("paused run.json must record emulator_handoff "
                 "(left-running-for-player or terminated)", errors)

    # turn records: bounded fields present when claimed. selected_action may
    # be a structured object (a deliberate non-Wait route) or null; null
    # requires a note saying the action is not decoded (a3-full2 lesson).
    for i, rec in enumerate(events):
        if rec.get("kind") != "turn":
            continue
        for field in ("actor", "control_mode"):
            if rec.get(field) is None:
                fail(f"turn event {i}: {field} is null", errors)
        if rec.get("selected_action") is None and not rec.get("note"):
            fail(f"turn event {i}: null selected_action without a note", errors)
        for field in ("position_before", "position_after"):
            pos = rec.get(field)
            if pos is None or "x" not in pos or "y" not in pos:
                fail(f"turn event {i}: {field} must be an x/y pair", errors)
    # boundary events must precede their turn event
    first_boundary = next((i for i, r in enumerate(events)
                           if r.get("kind") == "boundary"), None)
    first_turn = next((i for i, r in enumerate(events)
                       if r.get("kind") == "turn"), None)
    if first_turn is not None and (first_boundary is None
                                   or first_boundary > first_turn):
        fail("a turn event precedes its boundary event", errors)

    # A5.1 receipts bind EVERY turn to its latest actor boundary and verify
    # raw party tile deltas rather than trusting the engine_result label.
    boundary = None
    for i, rec in enumerate(events):
        if rec.get("kind") in ("start", "stop"):
            boundary = None
        elif rec.get("kind") == "boundary":
            boundary = rec
        elif rec.get("kind") == "turn" and (run.get("schema") == "a3-run/2" or rec.get("actor_identity")):
            identity = rec.get("actor_identity") or {}
            if (boundary is None or identity != boundary.get("actor_identity")
                    or rec.get("actor") != identity.get("name_text")
                    or rec.get("actor_slot") != boundary.get("actor_slot")
                    or identity.get("side_bit") is not False
                    or identity.get("id") is None):
                fail(f"turn event {i}: actor identity disagrees with boundary", errors)
            result = rec.get("engine_result") or {}
            action = rec.get("selected_action") or {}
            try:
                pre = {(r["name_text"], r["id"]): r for r in result["players_before"]}
                post = {(r["name_text"], r["id"]): r for r in result["players_after"]}
                if (not result.get("verified") or not pre or set(pre) != set(post)
                        or len(pre) != len(result["players_before"])
                        or len(post) != len(result["players_after"])):
                    raise ValueError("missing/duplicate result identities")
                actor = (identity["name_text"], identity["id"])
                row = pre[actor]
                if row["slot"] != rec["actor_slot"] or row["job"] != identity["job"] or row["side_bit"] is not False:
                    raise ValueError("result actor/job/side mismatch")
                moved = [k for k in pre if (pre[k]["x"], pre[k]["y"]) != (post[k]["x"], post[k]["y"])]
                if action.get("kind") == "identified-move":
                    if moved != [actor] or [post[actor]["x"], post[actor]["y"]] != action.get("dest"):
                        raise ValueError("wrong player/destination moved")
                elif action.get("kind") == "identified-wait":
                    if moved:
                        raise ValueError("Wait moved a player")
                else:
                    raise ValueError("missing supported selected action")
            except (KeyError, TypeError, ValueError) as exc:
                fail(f"turn event {i}: invalid actor-linked result ({exc})", errors)
            boundary = None

    # monotonic timestamps
    ts = [r.get("t") for r in events if r.get("t") is not None]
    if any(b < a for a, b in zip(ts, ts[1:])):
        fail("event timestamps are not monotonic", errors)

    # cross-check run.json counters against the event stream
    n_turn_events = kinds.count("turn")
    if run.get("turns") != n_turn_events:
        fail(f"run.json turns={run.get('turns')} but {n_turn_events} turn "
             "events exist", errors)
    if run.get("mode") != "retail-ai":
        fail(f"unexpected mode {run.get('mode')!r}", errors)

    # C1 gap 1: cross-check the raw write log. A stopped/terminal run must
    # show NO automation key write after the stop was latched. Records with
    # a start time BEFORE the latch may legitimately END after it (a press
    # cycle already in flight when STOP was observed) — the per-input gate
    # lets an in-flight press finish but never STARTS a new one.
    ilog_path = os.path.join(out_dir, "input-log.jsonl")
    if not os.path.exists(ilog_path):
        # round 6 gap 1: a MISSING input log must fail when the run is the
        # kind that owns input at all — automation runs always write the log
        # (the runtime opens it at construction). A TURN event implies
        # committed input; a boundary is only a detection (zero-input runs
        # carry boundaries too), so it does not count. The bare guard-
        # failure stream (no input possible) legitimately has an empty log.
        claims_input = any(e.get("kind") == "turn" for e in events)
        if events and run and claims_input:
            fail(f"missing {ilog_path} — a run that committed turns must "
                 "carry its raw write log", errors)
        return errors
    ilog = []
    with open(ilog_path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                ilog.append(json.loads(line))
            except json.JSONDecodeError as exc:
                fail(f"input-log line {ln}: not JSON ({exc})", errors)
    # Actual transport writes cannot inherit the aborted/completed labels of
    # a surrounding request. A delivered write remains input in every case.
    valid_raw = []
    for index, record in enumerate(ilog):
        if record.get("event") != "key_write":
            continue
        stamp = record.get("t")
        if (type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp < 0
                or type(record.get("val")) is not int or not 0 < record["val"] <= 0x3FF
                or type(record.get("hits")) is not int or record["hits"] < 1
                or record.get("manual") is not False):
            fail(f"input-log record {index}: malformed automation key_write", errors)
        else:
            valid_raw.append(record)

    valid_raw_ids = {id(record) for record in valid_raw}

    def owns_input(record):
        if record.get("event") == "key_write":
            return id(record) in valid_raw_ids
        return (record.get("event") in ("press", "drive")
                and not (record.get("aborted") or record.get("completed") is False))
    # C3 resume: the leak threshold is the TERMINAL stop of the run's own
    # leg — a resumed battle's leg-2 presses start AFTER leg 1's paused
    # stop on purpose (the player's move and the continuation). The leg-1
    # stop still governs leg 1 itself: everything after the first stop and
    # before leg 2's resume marker must be manual or the resume marker.
    stops_il = [r for r in ilog if r.get("event") in STOP_EVENTS]
    resume_marker_t = next((r.get("t") for r in ilog
                            if r.get("event") == "resume"), None)
    # a TRUNCATED log is the same cheat as a deleted one: a run that
    # committed turns must carry at least the input records that auditing
    # those commits requires (boundary-only streams may be empty — zero
    # input is legitimate evidence FOR zero input)
    claims_input = any(e.get("kind") == "turn" for e in events)
    if claims_input and not ilog:
        fail("input-log.jsonl is empty but the run records committed turns "
             "— the raw write log cannot be missing for an input-owning run",
             errors)
    # threshold: the stop LATCH when one exists, otherwise the terminal
    # stop event's timestamp — so runs that ended without a STOP file
    # (completed/stalled) are still guarded against post-terminal input
    # (Astra round 4 gap 1: the old validator never read this log at
    # all, so an injected post-STOP press passed validation)
    stop_t = None
    if resumed and resume_marker_t is not None:
        # leg 2's presses are audited against leg 2's OWN terminal; leg 1's
        # window (first stop .. resume marker) must contain NO automation
        # press — anything there is either the manual write or a leak
        leg1_stop_t = stops_il[0].get("t", 0) if stops_il else stops[0].get("t", 0)
        leg1_leaks = [r for r in ilog
                      if owns_input(r)
                      and r.get("t", 0) > leg1_stop_t + 0.001
                      and r.get("t", 0) < resume_marker_t]
        if leg1_leaks:
            fail(f"input-log: {len(leg1_leaks)} automation press/drive "
                 "between leg 1's paused stop and the resume marker "
                 "(input during the handoff gap must be manual)", errors)
        # Leg 1's handoff does not exempt leg 2 from its own terminal latch.
        later_stops = [r["t"] for r in stops_il if r.get("t", 0) >= resume_marker_t]
        stop_t = min(later_stops) if later_stops else (stops[-1].get("t") if stops else None)
    elif stops_il:
        stop_t = stops_il[0].get("t")
    else:
        stop_t = stops[-1].get("t") if stops else None
    if stop_t is not None:
        leaks = []
        for r in ilog:
            if owns_input(r):
                if r.get("t", 0) > stop_t + 0.001:
                    leaks.append(r)
            elif r.get("event") == MANUAL_WRITE_EVENT:
                continue  # manual input after a detached handoff
        if leaks:
            fail(f"input-log: {len(leaks)} successful press/drive "
                 f"started after the stop was latched (t={stop_t}): "
                 f"{[r.get('tag') or r.get('event') for r in leaks[:3]]}",
                 errors)
        if run.get("final_state") == "paused" and not stops_il:
            fail("paused run.json but input-log.jsonl never latched "
                 "the stop", errors)
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", help="outputs/autobattle/<run-id> directory")
    args = ap.parse_args(argv)
    errors = validate(args.run_dir)
    if errors:
        print(f"FAIL {args.run_dir}")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PASS {args.run_dir}: events/receipt contract holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
