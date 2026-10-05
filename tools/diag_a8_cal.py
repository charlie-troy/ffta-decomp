"""One-boot A8 calibration diagnostic.

Arms the Lua watch, commits one identified Wait, waits well past the
known ~12 s recharge, then reads back the debug line. Discriminates:
  * callback dead (n small/0, start nil)
  * callback alive but CT stale (n large, cur_ct stuck at 296)
  * comparison/branch bug (n large, cur_ct >= 998, full still nil)
  * callback alive and window closed late (full pair present)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from probe_a8_speed import (arm_lua_watch, console_open, lua,  # noqa: E402
                            STATE, LUA_READ, TOOLS)
from fixture_guard import FixtureSession  # noqa: E402
from probe_control_handoff import Probe  # noqa: E402

DEBUG_READ = os.path.join(TOOLS, "lua_a8_debug_read.lua").replace("\\", "/")


def debug_read(pid):
    try:
        r = lua(pid, 'dofile("' + DEBUG_READ + '")', timeout=40)
    except Exception as exc:      # noqa: BLE001 - bridge hangs are data too
        return "READ-HANG: " + str(exc)[:80]
    out = (r.stdout or "")
    for line in out.splitlines():
        t = line[5:] if line.startswith("LOG: ") else line
        if t.startswith("WD") or t.startswith("W-") or t.startswith("TJ"):
            return t
    return "no-debug-line: " + out[:160]


LUA_ARM = os.path.join(TOOLS, "lua_a8_frames.lua").replace("\\", "/")


def read_n(pid):
    line = debug_read(pid)
    if line.startswith("W- none"):
        try:
            return int(line.split("n=")[1].split()[0]), line
        except Exception:      # noqa: BLE001
            return -1, line
    if line.startswith("WD"):
        try:
            return int(line.split()[1]), line
        except Exception:      # noqa: BLE001
            return -1, line
    return -1, line


def main():
    with FixtureSession(STATE, quiet=True) as s:
        pid = s.pid
        print("console open:", console_open(pid), flush=True)
        time.sleep(2.0)
        # Liveness law test: arm, check, and if the callback is dead,
        # RE-ARM up to 4 times. Does re-registration revive delivery?
        for attempt in range(1, 5):
            r = lua(pid, 'dofile("' + LUA_ARM + '")', timeout=40)
            armed = "A8C armed" in (r.stdout or "")
            time.sleep(3.0)
            n1, line1 = read_n(pid)
            time.sleep(3.0)
            n2, line2 = read_n(pid)
            print(f"attempt {attempt}: armed={armed} n={n1}->{n2}",
                  flush=True)
            print("   ", line1[:110], flush=True)
            if n2 > n1 >= 0:
                print("CALLBACK LIVE after attempt", attempt, flush=True)
                break
        else:
            print("CALLBACK NEVER LIVE across re-arms", flush=True)
            return 1
        probe = Probe(s, verbose=False)
        plan = probe.plan_identified_wait()
        completed, _ = probe.commit_identified_wait(plan)
        print("commit:", completed, flush=True)
        for i in range(5):
            time.sleep(5)
            n, line = read_n(pid)
            print(f"t=+{(i + 1) * 5}s n={n}", flush=True)
            print("   ", line[:200], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
