"""Host regression for FixtureSession cleanup on the resumed (adopted) path.

The C1 cleanup rows were validated with a BOOTED session: the CLI kills its own
Popen. The A5.4 resume evidence exposed a second shape. `--resume` adopts an
already-running emulator by taking the pid from the GDB port listener and
creating no Popen, so `stop()`'s old `self.proc is not None` gate skipped the
kill entirely and logged nothing, while the CLI receipt still said
`emulator_handoff: terminated`. Observed live 2026-10-06: the resumed leg of
`a53-live-policy-handoff-01` ended `stalled` with `terminated pid: 57716` in its
receipt and mGBA 57716 still listening on the GDB port.

This suite pins the decision logic without touching a real process:

    python tools/validate_session_cleanup.py

It certifies control flow only. It does not prove that taskkill can end a real
mGBA, and it does not replace the live handoff/resume evidence.
"""
import argparse
import json
import os

import fixture_guard
from fixture_guard import FixtureSession


class FakeProc:
    def __init__(self, running):
        self.running = running

    def poll(self):
        return None if self.running else 0


def make_session(pid, proc, keep_process):
    s = FixtureSession("outputs/lua-nav/battle-start.ss0", rom="baserom.gba",
                       verify_rom=False, quiet=True)
    s.pid, s.proc, s.keep_process = pid, proc, keep_process
    return s


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-root", default="outputs/autobattle/a54-session-cleanup")
    args = parser.parse_args(argv)
    os.makedirs(args.out_root, exist_ok=True)
    checks = []

    def check(label, fn):
        fn()
        checks.append(label)
        print("PASS", label, flush=True)

    class FakeTime:
        """A clock that advances one second per sleep, so the wait loop is
        exercised without 15 real seconds per still-held port."""

        def __init__(self):
            self.t = 0.0

        def time(self):
            return self.t

        def sleep(self, seconds):
            self.t += seconds

    def stop_with(session, listener=None):
        """Run the REAL cleanup path (`__exit__` -> stop) with taskkill and the
        port probe intercepted."""
        calls = []
        logs = []

        def run(cmd, **kw):
            calls.append(list(cmd))
            return None

        with patch_objects(run, listener, logs, FakeTime()):
            session.__exit__(None, None, None)
        return calls, " ".join(logs)

    def patch_objects(run, listener, logs, fake_time):
        from unittest.mock import patch

        class _Ctx:
            def __enter__(self):
                self.patches = [
                    patch.object(fixture_guard.subprocess, "run", run),
                    patch.object(fixture_guard, "port_listener_pid",
                                 lambda port: None if listener is None else listener),
                    patch.object(fixture_guard, "time", fake_time),
                    patch.object(fixture_guard.FixtureSession, "log",
                                 lambda self, msg: logs.append(msg)),
                ]
                for p in self.patches:
                    p.start()
                return self

            def __exit__(self, *exc):
                for p in self.patches:
                    p.stop()
                return False

        return _Ctx()

    def adopted_running_leg_terminates_the_pid():
        s = make_session(4242, None, keep_process=False)
        calls, log = stop_with(s)
        assert calls == [["taskkill", "/F", "/PID", "4242"]], calls
        assert "'adopted' pid 4242" in log or "adopted pid 4242" in log, log
        assert s.pid is None
    check("an adopted session's non-paused exit kills the handed-off pid",
          adopted_running_leg_terminates_the_pid)

    def paused_handoff_keeps_the_process():
        s = make_session(4243, None, keep_process=True)
        calls, log = stop_with(s)
        assert calls == [], calls
        assert "terminated" not in log, log
    check("a paused handoff leaves the adopted process alone",
          paused_handoff_keeps_the_process)

    def booted_session_still_kills_and_says_owned():
        s = make_session(4244, FakeProc(running=False), keep_process=False)
        calls, log = stop_with(s)
        assert calls == [["taskkill", "/F", "/PID", "4244"]], calls
        assert "owned pid 4244" in log, log
    check("a booted session keeps its original behaviour and label",
          booted_session_still_kills_and_says_owned)

    def a_held_port_is_reported_honestly():
        s = make_session(4245, None, keep_process=False)
        calls, log = stop_with(s, listener=4245)
        assert calls == [["taskkill", "/F", "/PID", "4245"]], calls
        assert "STILL HELD" in log, log
    check("a still-listening port is never reported as free",
          a_held_port_is_reported_honestly)

    with open(os.path.join(args.out_root, "checks.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"checks": checks, "passed": len(checks),
                   "scope": "synthetic cleanup control flow only; no real "
                            "process is killed by this suite"}, fh, indent=2)
    print(f"SESSION CLEANUP PASS: {len(checks)} checks")


if __name__ == "__main__":
    main()
