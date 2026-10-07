"""A3 CLI: run one battle scenario under the autonomous runtime.

Roadmap A3: `run_autobattle.py --rom PATH --scenario PATH --mode retail-ai`.
Defaults to paused: the fixture guard, ROM hash, and live roster are verified
before the runtime leaves `idle`, and the run stops at the first bounded
terminal state. Turn events append to
`outputs/autobattle/<run-id>/events.jsonl`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession  # noqa: E402
from autobattle_runtime import BattleRuntime  # noqa: E402
from tactics_policy import PolicyError, load_policy_file  # noqa: E402


def _input_hashes(args):
    inputs = [args.rom, args.state, args.scenario,
              "tools/run_autobattle.py", "tools/autobattle_runtime.py",
              "tools/autobattle_identity.py", "tools/probe_control_handoff.py",
              "tools/tactics_policy.py", "tools/tactics_adapter.py"]
    if args.bounded_self_cure:
        inputs.extend(["tools/recovery_runtime.py", "tools/recovery_transport.py",
                       "tools/recovery_menu.py", "tools/recovery_executor.py",
                       "tools/recovery_continuation.py", "tools/ability_resources.py",
                       "tools/fixture_guard.py", "tools/trace_mgba.py"])
    if args.bounded_ally_cure:
        inputs.extend(['tools/party_recovery_runtime.py','tools/recovery_party.py',
                       'tools/recovery_ally_confirmation.py','tools/recovery_ally_preview.py',
                       'tools/recovery_ally_target.py','tools/recovery_ally_executor.py',
                       'tools/recovery_party_continuation.py','tools/recovery_menu.py',
                       'tools/recovery_executor.py','tools/recovery_transport.py',
                       'tools/probe_recovery_party.py','tools/ability_resources.py',
                       'tools/fixture_guard.py','tools/trace_mgba.py'])
    if args.tactics_policy:
        inputs.append(args.tactics_policy)
    result = {}
    for path in inputs:
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                result[path] = hashlib.sha256(handle.read()).hexdigest()
    return result


def _tactics_decisions(events_path):
    """Turn events' tactics metadata, for the run receipt (A5.3 evidence)."""
    out = []
    try:
        with open(events_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("kind") == "turn" and rec.get("tactics"):
                    out.append(rec["tactics"])
    except (OSError, ValueError):
        return []
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default="baserom.gba")
    ap.add_argument("--state", default="outputs/lua-nav/battle-start.ss0")
    ap.add_argument("--scenario", default="configs/battle-scenarios/normal-battle.json")
    ap.add_argument("--mode", choices=["retail-ai"], default="retail-ai")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out-root", default="outputs/autobattle")
    ap.add_argument("--stall-seed-seconds", type=float, default=150.0)
    ap.add_argument("--wall-timeout", type=float, default=600.0)
    ap.add_argument("--max-turns", type=int, default=None)
    ap.add_argument("--pause-at-boundary", action="store_true",
                    help="manual-handoff entry point (A5.1): stop ON PURPOSE "
                         "at the first identified player menu instead of "
                         "driving it, leaving that fresh menu OPEN and "
                         "untouched with zero automation input so a player "
                         "can take the turn over and --resume afterwards. "
                         "Just like a STOP-file pause, the emulator is left "
                         "running (--on-stop) and the receipt records the "
                         "handoff pid/port.")
    ap.add_argument("--yes", action="store_true",
                    help="run without the interactive paused prompt")
    ap.add_argument("--on-stop", choices=["kill", "leave-running"],
                    default="leave-running",
                    help="what happens to the emulator when the run stops "
                         "with a STOP file (manual takeover): leave-running "
                         "detaches and leaves the battle for the player; "
                         "kill ends it (default: leave-running)")
    ap.add_argument("--tactics-policy", metavar="PATH", default=None,
                    help="A5.3 conditional tactics: load a frozen policy "
                         "(docs/tactics-policy.md) and let it choose among the "
                         "commands the engine currently offers, instead of the "
                         "scenario's fixed per-actor assignment. Validated "
                         "before the emulator is touched; a bad document exits 2.")
    recovery_flags = ap.add_mutually_exclusive_group()
    recovery_flags.add_argument("--bounded-self-cure", action="store_true",
                    help="A6.1 opt-in seven-unit self-Cure fixture transaction; requires schema-2 tactics")
    recovery_flags.add_argument('--bounded-ally-cure',action='store_true',
                    help='A6.3 opt-in eight-unit living ally-Cure fixture; requires schema-2 tactics')
    ap.add_argument("--resume", metavar="RUN_ID", default=None,
                    help="continue the battle of a previously paused run: "
                         "adopt the ALREADY-RUNNING emulator (no reboot — "
                         "a restart would not continue the same battle), "
                         "append to the same events/input logs, and drive "
                         "the battle to its end. The pid must match the "
                         "paused run's recorded handoff pid.")
    args = ap.parse_args(argv)

    with open(args.scenario, encoding="utf-8") as fh:
        scenario = json.load(fh)

    # A5.3: validate the policy BEFORE any emulator work. A configuration
    # error must fail closed at the CLI, not after a boot and a menu.
    tactics_policy = None
    if args.tactics_policy:
        try:
            tactics_policy = load_policy_file(args.tactics_policy)
        except (PolicyError, OSError, ValueError) as exc:
            print(f"FAIL: tactics policy {args.tactics_policy}: {exc}")
            return 2
        print(f"tactics policy {args.tactics_policy} "
              f"({tactics_policy['schema']}) validated")

    if (args.bounded_self_cure or args.bounded_ally_cure) and (tactics_policy or {}).get("schema") != "ffta-tactics-policy/2":
        print("FAIL: bounded recovery requires a schema-2 --tactics-policy")
        return 2
    resumed_run = None
    if args.resume:
        # same run id, same artifacts: one battle, two runner legs
        run_id = args.resume
        out_dir = os.path.join(args.out_root, run_id)
        if not os.path.isfile(os.path.join(out_dir, "run.json")):
            print(f"FAIL: --resume {run_id}: no paused receipt at "
                  f"{out_dir}/run.json")
            return 2
        with open(os.path.join(out_dir, "run.json"), encoding="utf-8") as fh:
            resumed_run = json.load(fh)
        if resumed_run.get("final_state") != "paused" or \
                resumed_run.get("emulator_handoff") != "left-running-for-player":
            print(f"FAIL: --resume {run_id}: receipt is "
                  f"{resumed_run.get('final_state')}/"
                  f"{resumed_run.get('emulator_handoff')!r}, not a paused "
                  "left-running handoff")
            return 2
        if resumed_run.get("resumed"):
            print(f"FAIL: --resume {run_id}: this run already resumed once "
                  "(one manual handoff per battle is the audited shape)")
            return 2
        # A5.4: the guard expectations come from the SCENARIO file, and the
        # receipt does not carry them — so resuming with the wrong --scenario
        # (or the default) fails the roster guard for a reason that looks like
        # a damaged battle. Observed live 2026-10-06: a resume of the two-ally
        # fixture with the default scenario reported
        # "struct_count=8 expected=7" for 45 s. Name the real cause instead.
        given_scenario = scenario.get("scenario_id")
        run_scenario = resumed_run.get("scenario")
        if run_scenario and given_scenario and run_scenario != given_scenario:
            print(f"FAIL: --resume {run_id}: scenario {given_scenario!r} does not "
                  f"match the resumed run's {run_scenario!r} — pass the same "
                  "--scenario (the fixture guard expectations are per-scenario, "
                  "so a mismatch looks like a failed roster guard)")
            return 2
    else:
        run_id = args.run_id or time.strftime("a3-%Y%m%d-%H%M%S")
        out_dir = os.path.join(args.out_root, run_id)
    os.makedirs(out_dir, exist_ok=True)

    print(f"scenario {scenario.get('scenario_id')} -> run {run_id}"
          + (" [RESUME]" if args.resume else ""))
    if not args.resume:
        print("paused: booting guarded fixture before any input is issued")
    # Astra 2026-09-17: the leave-running decision must reach the actual
    # process cleanup, not only the receipt text — with the session created
    # explicitly, __exit__ is guaranteed to run on every path (finally) and
    # the paused handoff flips session.keep_process BEFORE it does.
    expect = dict(scenario.get("guard_expectations", {}))
    if isinstance(expect.get("slot0_name"), str):
        expect["slot0_name"] = int(expect["slot0_name"], 0)
    launch_inputs = _input_hashes(args)
    session = FixtureSession(args.state, rom=args.rom, expect=expect)
    if args.resume:
        try:
            session.adopt_existing()
        except Exception as exc:
            print(f"FAIL: could not adopt the running emulator: {exc}")
            # A failed read-only adoption may have opened the transport.
            # Close it while preserving the existing emulator.
            session.keep_process = True
            session.__exit__(None, None, None)
            return 2
        handoff_pid = (resumed_run.get("manual_handoff") or {}).get("pid")
        if handoff_pid and session.pid != handoff_pid:
            print(f"FAIL: adopted pid {session.pid} but the paused receipt "
                  f"handed off pid {handoff_pid} — refusing to resume a "
                  "different emulator")
            session.__exit__(None, None, None)
            return 2
    try:
        if not args.resume:
            session.__enter__()
        runtime = BattleRuntime(session, scenario, run_id, out_dir,
                                mode=args.mode,
                                stall_seed_seconds=args.stall_seed_seconds,
                                wall_timeout=args.wall_timeout,
                                max_turns=args.max_turns,
                                resume=bool(args.resume),
                                pause_at_boundary=args.pause_at_boundary,
                                tactics_policy=tactics_policy,
                                tactics_policy_source=args.tactics_policy,
                                bounded_self_cure=args.bounded_self_cure,
                                bounded_ally_cure=args.bounded_ally_cure)
        if not args.yes:
            ans = input("guards will run now; continue? [y/N] ").strip().lower()
            if ans != "y":
                runtime.event("stop", note="paused: aborted before guards")
                return 2
        if not runtime.live_guard():
            runtime.state = "stalled"
            # Astra round 4 gap 3: the guard failure itself must reach the
            # receipt. The run DID start (boot, guards) even though run()
            # never did, so the start event is emitted here — without it
            # the receipt cannot satisfy the one-start lifecycle rule.
            runtime.event("start", control_mode=args.mode,
                          input_log="input-log.jsonl")
            # This event's note is the run's terminal reason, and run.json
            # is written on THIS path too — the old shape returned before
            # any receipt, leaving only stdout text behind.
            runtime.event("stop", note="stalled: live guard failed before start")
            guard_receipt = {
                "schema": "a3-run/2",
                "run_id": run_id,
                "scenario": scenario.get("scenario_id"),
                "mode": args.mode,
                "final_state": "stalled",
                "turns": 0,
                "seeds": 0,
                "router_hits": runtime.p.router_hits,
                "terminal_reason": "live guard failed before start",
                "events": runtime.events_path,
                # honest even on the adopt path: an adopted session keeps
                # its process, a booted one is terminated by __exit__
                "emulator_handoff": ("left-running-for-player"
                                     if session.keep_process
                                     else "terminated"),
            }
            with open(os.path.join(out_dir, "run.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(guard_receipt, fh, indent=2)
            print(f"final state: stalled (guard failure); receipt "
                  f"{out_dir}/run.json")
            return 1
        stop_file = os.path.join(out_dir, "STOP")
        try:
            os.remove(stop_file)
        except OSError:
            pass
        if args.resume:
            # continue the turn count of leg 1 so run.json's total and the
            # events' turn numbers describe ONE battle
            runtime.turn = int(resumed_run.get("turns") or 0)
        final = runtime.run()
        # manual takeover handoff: a paused run leaves the emulator alive
        # so the player can continue the battle from the live screen.
        # This flip is the REAL decision: __exit__ (finally below) passes
        # session.keep_process to stop(), which skips the taskkill. Every
        # non-paused terminal state terminates the emulator even with
        # --on-stop leave-running (the flag only governs the pause handoff).
        paused = final == "paused"
        keep_process = paused and args.on_stop == "leave-running"
        session.keep_process = keep_process
        receipt = {
            "schema": "a3-run/2",
            "run_id": run_id,
            "scenario": scenario.get("scenario_id"),
            "mode": args.mode,
            "final_state": final,
            "turns": runtime.turn,
            "seeds": len(runtime.p.seeds),
            "router_hits": runtime.p.router_hits,
            "terminal_reason": runtime._terminal_reason,
            "events": runtime.events_path,
            "emulator_handoff": ("left-running-for-player" if keep_process
                                 else "terminated"),
            "emulator_pid": session.pid,
            "bounded_self_cure": args.bounded_self_cure,
            "bounded_ally_cure": args.bounded_ally_cure,
            "player_identities": [list((r["name_text"], r["id"]))
                                  for r in runtime.adapter.expected],
        }
        receipt["input_sha256"] = launch_inputs
        receipt["input_sha256_after"] = _input_hashes(args)
        receipt["inputs_unchanged"] = receipt["input_sha256_after"] == launch_inputs
        if args.resume:
            receipt["previous_leg"] = resumed_run
            # A5.1: an adopt may have to wait out the engine's turn-transition
            # window (the battle-struct region is reused for a few seconds
            # after a turn closes), so the receipt must carry HOW the adopt
            # was verified, not only that it happened.
            adopt_attempts = (session.receipt or {}).get("adopt_attempts") or []
            first_failed = next((a["failed_required"] for a in adopt_attempts
                                 if a.get("failed_required")), [])
            receipt["adopt"] = {
                "pid": session.pid,
                "match_receipt_handoff_pid": session.pid == resumed_run.get(
                    "manual_handoff", {}).get("pid"),
                "roster_guard_ok": bool((session.receipt or {}).get("ok")),
                "guard_attempts": len(adopt_attempts),
                "guard_first_failed_checks": first_failed[:3],
            }
            receipt["resumed"] = True
            # runtime.turn was preset to leg 1's count: it IS the battle's
            # running total (and matches the events' turn numbering, which
            # the receipt validator cross-checks)
            receipt["turns"] = runtime.turn
            receipt["terminal_reason"] = (
                (runtime._terminal_reason or "")
                + " [resumed after manual handoff; leg 1 ended paused]")
        if paused and keep_process:
            # C3 resume precondition: the NEXT leg must verify it adopts
            # THIS emulator, not any running mGBA (pid check in --resume)
            receipt["manual_handoff"] = {"pid": session.pid,
                                         "port": session.port}

        if args.tactics_policy:
            receipt["tactics_policy"] = {
                "path": args.tactics_policy,
                "schema": (tactics_policy or {}).get("schema"),
                "fallback": (tactics_policy or {}).get("fallback"),
                "scopes": sorted((tactics_policy or {}).get("assignments", {})),
                "decisions": _tactics_decisions(runtime.events_path),
                "note": "choices made by the frozen chooser among the "
                        "commands the engine offered; the scenario's fixed "
                        "actor_actions are not used in this run",
            }
        with open(os.path.join(out_dir, "run.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(receipt, fh, indent=2)
        print(f"final state: {final}; receipt {out_dir}/run.json")
        if paused:
            print(f"paused: battle left running for manual play "
                  f"(emulator pid {session.pid}; --on-stop=kill to end it)")
            return 0
        return 0 if final == "completed" else 1
    finally:
        session.__exit__(None, None, None)


if __name__ == "__main__":
    sys.exit(main())
