"""Diagnose the v11 T-phase read failure at packet level.

One boot: commit -> clear_all_bps -> arm/disarm burn -> cont -> window
(interrupt + raw read), printing the RAW reply string of every exchange
so the off-by-one (if any) is visible instead of inferred.  Also tests a
read while the core runs without interrupt, and re-pairs after an
explicit retry-until-OK burn.

No artifacts are claimed; stdout only (plus log via launcher).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, ROSTER, STRIDE, OFF_CT  # noqa: E402
from probe_control_handoff import Probe, BP_KEY  # noqa: E402
from probe_a8_speed import clear_all_bps, arm_key_bp, disarm_key_bp  # noqa: E402

STATE = os.path.join("outputs", "lua-nav", "battle-start.ss0")
CT_BASE = ROSTER + STRIDE * 6 + OFF_CT


def show(tag, fn):
    try:
        r = fn()
        print(f"{tag}: {r!r}", flush=True)
        return r
    except Exception as exc:
        print(f"{tag}: EXC {type(exc).__name__}: {exc}", flush=True)
        return None


def main():
    with FixtureSession(STATE, quiet=True) as s:
        g = s.g
        probe = Probe(s, verbose=False)
        plan = probe.plan_identified_wait()
        if not plan:
            print("no plan", flush=True)
            return 1
        ok, _ = probe.commit_identified_wait(plan)
        print(f"commit={ok}", flush=True)

        print("== pairing probe after commit (z0 expect OK)", flush=True)
        show("z0-after-commit", lambda: g.send(f"z0,{BP_KEY:x},2"))

        clear_all_bps(g)
        show("z0-after-clear", lambda: g.send(f"z0,{BP_KEY:x},2"))
        show("arm", lambda: arm_key_bp(g))
        show("z0-after-arm", lambda: g.send(f"z0,{BP_KEY:x},2"))
        show("disarm", lambda: disarm_key_bp(g))
        show("z0-after-disarm", lambda: g.send(f"z0,{BP_KEY:x},2"))

        # 1) read while core HALTED (never cont'd): is a plain read served?
        show("m-while-halted", lambda: g.send(f"m{CT_BASE:x},2"))

        # 2) cont -> read while core RUNS (no interrupt)
        show("cont-1", lambda: g.cont())
        time.sleep(0.05)
        show("m-while-running", lambda: g.send(f"m{CT_BASE:x},2"))
        time.sleep(0.2)
        show("m-while-running-2", lambda: g.send(f"m{CT_BASE:x},2"))

        # 3) interrupt window (the T phase's sequence)
        show("interrupt-1", lambda: g.interrupt())
        show("m-after-interrupt", lambda: g.send(f"m{CT_BASE:x},2"))
        show("m-after-interrupt-2", lambda: g.send(f"m{CT_BASE:x},2"))

        # 4) second window
        show("cont-2", lambda: g.cont())
        time.sleep(0.25)
        show("interrupt-2", lambda: g.interrupt())
        show("m-after-interrupt-3", lambda: g.send(f"m{CT_BASE:x},2"))

        # 5) burn: retry until OK, then read again
        for i in range(6):
            r = show(f"burn-{i}", lambda: g.send(f"z0,{BP_KEY:x},2"))
            if r == "OK":
                break
        show("m-after-burn", lambda: g.send(f"m{CT_BASE:x},2"))
        show("interrupt-3", lambda: g.interrupt())
        show("m-after-interrupt-4", lambda: g.send(f"m{CT_BASE:x},2"))
        g.cont()
    return 0


if __name__ == "__main__":
    sys.exit(main())
