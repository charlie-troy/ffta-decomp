"""Cancel/finish a recovery modal through the owned window, then prove Wait.

Requires a real paused CLI handoff. GDB is a read-only held monitor; every
gameplay key uses the verified foreground window. Leaves that same PID alive
for the public --resume path. Never sends gameplay input through the stub.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from fixture_guard import port_listener_pid
from manual_input_probe import capture
from recovery_continuation import observe_continuation
from recovery_menu import RecoveryMenu, RecoveryTransient, RecoveryStateError, require
from trace_mgba import Gdb

MASKS = {"A": 1, "B": 2, "UP": 0x40, "DOWN": 0x80}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--rom", default="baserom.gba")
    parser.add_argument("--out", help="new metadata filename for a retained retry")
    args = parser.parse_args()
    root = Path(args.run)
    output = Path(args.out) if args.out else root / "manual-recovery.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    require(not output.exists(), "manual evidence must be new")
    run = json.loads((root / "run.json").read_text())
    require(run["final_state"] == "paused" and run["emulator_handoff"] == "left-running-for-player",
            "real paused CLI handoff required")
    pid, port = run["manual_handoff"]["pid"], run["manual_handoff"]["port"]
    require(port_listener_pid(port) == pid, "refusing a different emulator listener")
    events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
    journal = next(e["recovery"] for e in reversed(events) if e.get("recovery"))
    owner = journal["owner"]
    rom = Path(args.rom).read_bytes()
    record = {"schema": "ffta-recovery-manual/1", "status": "unknown", "pid": pid,
              "input_channel": "verified owned window; GDB reads/control only",
              "stub_gameplay_writes": 0, "keys": [], "observations": [], "continuations": []}
    record["source_sha256"] = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in (
        "tools/manual_recovery_handoff.py", "tools/send_owned_mgba_key.ps1", "tools/recovery_menu.py",
        "tools/recovery_continuation.py", "tools/fixture_guard.py", "tools/trace_mgba.py")}
    started = time.time()
    base = max(e.get("t", 0) for e in events) + 1
    g = Gdb("127.0.0.1", port, timeout=6)
    try:
        def halt():
            reply = g.interrupt()
            require(reply and reply[:1] in ("S", "T") and reply[:3] not in ("S04", "T04"), "manual halt not established")

        halt()
        menu = RecoveryMenu(g, rom, owner)

        def observe():
            halt()
            facts = menu.snapshot()
            record["observations"].append(facts.receipt())
            return facts

        def passive():
            g.cont()
            time.sleep(0.25)

        def press(key, facts):
            require(len(record["keys"]) < 14, "manual input bound exceeded")
            require(port_listener_pid(port) == pid, "manual listener ownership changed")
            verified = menu.revalidate(facts)
            g.cont()
            sent = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                   "tools/send_owned_mgba_key.ps1", "-ProcId", str(pid), "-Key", key],
                                  capture_output=True, text=True, timeout=40,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            require(sent.returncode == 0, "manual key failed: " + sent.stdout + sent.stderr)
            record["keys"].append({"key": key, "before": verified.receipt(), "window": json.loads(sent.stdout)})
            with (root / "input-log.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps({"event": "manual_key_write", "val": MASKS[key],
                                      "t": round(base + time.time() - started, 3)}) + "\n")
            passive()

        initial = observe()
        record["initial"] = initial.receipt()
        capture(pid, str(output.with_name(output.stem + "-before.png").resolve()))
        if initial.state != "facing":
            deadline = time.monotonic() + 50
            while True:
                require(time.monotonic() < deadline, "manual cancellation timeout")
                try:
                    facts = observe()
                except RecoveryTransient:
                    passive()
                    continue
                require((facts.hp, facts.mp) == (initial.hp, initial.mp), "manual cancellation spent resources")
                if facts.state == "command":
                    break
                if facts.state == "settling":
                    passive()
                    continue
                require(facts.state in ("confirmation", "description", "target-overlay", "ability-list", "action-group"),
                        "manual cancellation modal unknown")
                press("B", facts)
            for _ in range(6):
                facts = observe()
                require(facts.state == "command" and facts.rows.count(10) == 1
                        and facts.enabled[facts.rows.index(10)], "manual Wait unavailable")
                index = facts.rows.index(10)
                current = facts.cursor + facts.scroll
                if current == index:
                    press("A", facts)
                    break
                press("DOWN" if current < index else "UP", facts)
            else:
                raise RuntimeError("manual Wait navigation bound exceeded")
        facing = observe()
        require(facing.state == "facing" and facing.driver_state == 47
                and (facing.hp, facing.mp) == (initial.hp, initial.mp), "manual Wait facing not owned")
        capture(pid, str(output.with_name(output.stem + "-facing.png").resolve()))
        press("A", facing)
        record["facing"] = facing.receipt()
        deadline = time.monotonic() + 20
        while len(record["continuations"]) < 2 and time.monotonic() < deadline:
            passive()
            halt()
            try:
                later = observe_continuation(g, rom, owner, facing.receipt())
            except RecoveryStateError:
                continue
            if later["actor"]["id"] not in {r["actor"]["id"] for r in record["continuations"]}:
                record["continuations"].append(later)
        require(len(record["continuations"]) == 2, "manual Wait continuation unverified")
        capture(pid, str(output.with_name(output.stem + "-after.png").resolve()))
        record["status"] = "verified-manual-wait"
    except BaseException as exc:
        record["error"] = repr(exc)
        raise
    finally:
        try:
            g.cont()
        finally:
            g.close()
            output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Verified manual Wait and two later actors on handed-off PID {pid}; left alive for --resume")


if __name__ == "__main__":
    main()
