"""A3 CLI: run one battle scenario under the autonomous runtime.

Roadmap A3: `run_autobattle.py --rom PATH --scenario PATH --mode retail-ai`.
Defaults to paused: the fixture guard, ROM hash, and live roster are verified
before the runtime leaves `idle`, and the run stops at the first bounded
terminal state. Turn events append to
`outputs/autobattle/<run-id>/events.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession  # noqa: E402
from autobattle_runtime import BattleRuntime  # noqa: E402


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
    ap.add_argument("--yes", action="store_true",
                    help="run without the interactive paused prompt")
    ap.add_argument("--on-stop", choices=["kill", "leave-running"],
                    default="leave-running",
                    help="what happens to the emulator when the run stops "
                         "with a STOP file (manual takeover): leave-running "
                         "detaches and leaves the battle for the player; "
                         "kill ends it (default: leave-running)")
    args = ap.parse_args(argv)

    with open(args.scenario, encoding="utf-8") as fh:
        scenario = json.load(fh)

    run_id = args.run_id or time.strftime("a3-%Y%m%d-%H%M%S")
    out_dir = os.path.join(args.out_root, run_id)
    os.makedirs(out_dir, exist_ok=True)

    print(f"scenario {scenario.get('scenario_id')} -> run {run_id}")
    print("paused: booting guarded fixture before any input is issued")
    # Astra 2026-09-17: the leave-running decision must reach the actual
    # process cleanup, not only the receipt text — with the session created
    # explicitly, __exit__ is guaranteed to run on every path (finally) and
    # the paused handoff flips session.keep_process BEFORE it does.
    session = FixtureSession(args.state, rom=args.rom)
    try:
        session.__enter__()
        runtime = BattleRuntime(session, scenario, run_id, out_dir,
                                mode=args.mode,
                                stall_seed_seconds=args.stall_seed_seconds,
                                wall_timeout=args.wall_timeout,
                                max_turns=args.max_turns)
        if not args.yes:
            ans = input("guards will run now; continue? [y/N] ").strip().lower()
            if ans != "y":
                runtime.event("stop", note="paused: aborted before guards")
                return 2
        if not runtime.live_guard():
            runtime.state = "stalled"
            runtime.event("stop", reason="live guard failed before start")
            return 1
        stop_file = os.path.join(out_dir, "STOP")
        try:
            os.remove(stop_file)
        except OSError:
            pass
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
            "schema": "a3-run/1",
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
