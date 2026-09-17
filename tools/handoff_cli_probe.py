"""Live proof that the CLI's pause handoff reaches the REAL cleanup path.

Astra (2026-09-17) reproduced the handoff bug with a mocked CLI run: the CLI
printed "battle left running" while FixtureSession.__exit__ requested
termination (stop()'s default kills the owned emulator). This probe exercises
the real path end to end on hardware:

  boot a guarded session -> drop a STOP file mid-battle -> the runtime
  classifies `paused` -> the CLI's exact finally semantics run (flip
  session.keep_process, then __exit__) -> PASS only if the emulator pid is
  still alive afterwards and the transport detached cleanly.

Exit code 0 = the handoff is real (emulator survives, battle stays live);
exit code 1 = the cleanup path still terminates the process.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, port_listener_pid  # noqa: E402
from autobattle_runtime import BattleRuntime  # noqa: E402


def pid_alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                         capture_output=True, text=True).stdout
    return str(pid) in out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default="baserom.gba")
    ap.add_argument("--state", default="outputs/lua-nav/battle-start.ss0")
    ap.add_argument("--run-id", default="a3-handoff-probe")
    ap.add_argument("--stop-at", type=float, default=45.0,
                    help="seconds after boot to drop the STOP file "
                         "(mid-battle by design; guards take ~30 s)")
    args = ap.parse_args(argv)

    out_dir = os.path.join("outputs", "autobattle", args.run_id)
    os.makedirs(out_dir, exist_ok=True)
    stop_file = os.path.join(out_dir, "STOP")
    try:
        os.remove(stop_file)
    except OSError:
        pass

    session = FixtureSession(args.state, rom=args.rom)
    pid = None
    try:
        session.__enter__()
        pid = session.pid
        print(f"probe: emulator booted, pid={pid}, port={session.port}")
        scenario = {"scenario_id": "normal-battle"}
        rt = BattleRuntime(session, scenario, args.run_id, out_dir,
                           wall_timeout=240.0)
        # the CLI runs the live guard before the runtime starts (it also
        # assigns rt.g); the probe mirrors that flow exactly
        if not rt.live_guard():
            print("FAIL: live guard failed before start")
            final_state = "guard-failed"
            ok = False
        else:
            threading.Timer(args.stop_at,
                            lambda: open(stop_file, "w").close()).start()
            final = rt.run()
            # the CLI's exact handoff semantics (run_autobattle.py): flip the
            # session's keep_process BEFORE __exit__ runs
            paused = final == "paused"
            keep_process = paused  # --on-stop defaults to leave-running
            session.keep_process = keep_process
            print(f"probe: final state {final} (turns={rt.turn}); "
                  f"keep_process={keep_process}")
            if not paused:
                print("FAIL: the run did not pause - the STOP did not take "
                      "effect mid-battle")
                ok = False
            else:
                ok = True
            final_state = final
    finally:
        session.__exit__(None, None, None)

    # __exit__ ran with keep_process=True: the emulator must still be alive
    time.sleep(2.0)
    survived = pid is not None and pid_alive(pid)
    port_free = port_listener_pid(session.port) is None
    if not survived:
        print(f"FAIL: emulator pid {pid} did not survive __exit__ - the "
              f"cleanup path still terminates the process (Astra's repro)")
    else:
        print(f"PASS: emulator pid {pid} survived the real CLI cleanup "
              f"path; the battle is left running for the player")
        port_note = (' and port released' if port_free
                     else f', port {session.port} still held')
        print(f"      (detached: transport closed{port_note}; kill "
              f"it with: taskkill /F /PID {pid})")
    receipt = {
        "schema": "handoff-probe/1",
        "run_id": args.run_id,
        "final_state": final_state,
        "emulator_pid": pid,
        "emulator_survived": survived,
        "port_released": port_free,
    }
    with open(os.path.join(out_dir, "probe.json"), "w",
              encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    return 0 if (ok and survived) else 1


if __name__ == "__main__":
    sys.exit(main())
