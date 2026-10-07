"""Request STOP at a real public CLI confirmation, leaving its owned PID live."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phase", choices=("confirmation", "facing"), required=True)
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id or any(c in args.run_id for c in (":", "\\", "/")):
        parser.error("run-id must be a filename")
    root = Path("outputs/autobattle") / args.run_id
    log_path = root.with_suffix(".log")
    if root.exists() or log_path.exists():
        parser.error("run and log must be new")
    command = [sys.executable, "tools/run_autobattle.py", "--state", args.state,
               "--tactics-policy", "configs/tactics/healer.json", "--bounded-self-cure",
               "--run-id", args.run_id, "--wall-timeout", "150", "--yes"]
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        deadline = time.monotonic() + 180
        fired = False
        while process.poll() is None:
            if (root / f"recovery-{args.phase}.png").exists():
                (root / "STOP").write_text(f"STOP before final {args.phase} input\n", encoding="utf-8")
                fired = True
                break
            if time.monotonic() >= deadline:
                (root / "STOP").write_text("STOP: bounded watcher timeout\n", encoding="utf-8")
                break
            time.sleep(0.02)
        # The CLI owns cleanup and handoff. No global process termination.
        code = process.wait(timeout=90)
    receipt = json.loads((root / "run.json").read_text())
    if not fired or code or receipt["final_state"] != "paused" or receipt["emulator_handoff"] != "left-running-for-player":
        raise RuntimeError(f"CLI STOP not proven: fired={fired}, code={code}; inspect {root}")
    with (root / "paused-run.json").open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")
    print(f"STOP at {args.phase}; public CLI paused and handed off owned PID {receipt['emulator_pid']}")


if __name__ == "__main__":
    main()
