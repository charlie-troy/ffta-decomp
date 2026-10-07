"""Drop STOP at a named screenshot in an owned recovery research run."""
import argparse
from pathlib import Path
import os
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--phase", required=True, help="screenshot tag, for example15-A")
    parser.add_argument("--mp", type=int, default=6)
    parser.add_argument("--finish-recovery-turn", action="store_true")
    parser.add_argument("--scoped-transport", action="store_true")
    args = parser.parse_args()
    root = Path(args.out)
    stop = root.with_suffix(".stop")
    log_path = root.with_suffix(".log")
    if root.exists() or stop.exists() or log_path.exists():
        parser.error("output, STOP and log paths must be new")
    if Path(args.phase).name != args.phase or any(c in args.phase for c in ('/', '\\', ':')):
        parser.error("phase must be a filename tag")
    root.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(Path(__file__).with_name("probe_a6_action_menu.py")),
               "--out", str(root), "--secondary-job", "7", "--hp", "100",
               "--mp", str(args.mp), "--edit-members", "--policy", "configs/tactics/healer.json",
               "--stop-file", str(stop),
               "--finish-recovery-turn" if args.finish_recovery_turn else "--wait-fallback"]
    if args.scoped_transport:
        command.append("--scoped-transport")
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        deadline = time.monotonic() + 180
        fired = False
        while process.poll() is None:
            if (root / f"{args.phase}.png").exists():
                stop.write_text(f"STOP at recovery phase {args.phase}\n", encoding="utf-8")
                fired = True
                break
            if time.monotonic() >= deadline:
                stop.write_text("STOP: bounded watcher timeout\n", encoding="utf-8")
                break
            time.sleep(0.02)
        # The child owns emulator cleanup. Never terminate a foreign process.
        code = process.wait(timeout=60)
    if not fired or code:
        raise RuntimeError(f"STOP phase not proven: fired={fired}, child exit={code}; inspect {log_path}")
    print(f"STOP written at {args.phase}; owned research child exited{code}; receipt: {root / 'probe.json'}")


if __name__ == "__main__":
    main()
