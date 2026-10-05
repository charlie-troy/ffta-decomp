"""Trajectory diagnostic: read CT while the core free-runs, nothing else.

After commit + clear + arm/disarm burn, drain strays with polls while
halted, then cont() and hammer 'm' reads with timestamps only - no
interrupt, no z0, no breakpoints.  Answers the one question v12 needs:
are read-while-running values fresh and frame-consistent with the
traced waveform (296 -> 188 -> ... -> 998), or stale/garbage?

Prints the first 40 raw replies, the full parsed trajectory summary,
and any non-hex reply.  stdout only.
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
        clear_all_bps(g)
        arm_key_bp(g)
        disarm_key_bp(g)

        # drain strays while halted: poll until a genuine hex reply
        drained = []
        for i in range(8):
            try:
                raw = g.send(f"m{CT_BASE:x},2")
            except Exception as exc:
                raw = f"EXC:{exc}"
            drained.append(raw)
            if raw and all(c in "0123456789abcdef" for c in raw) and len(raw) == 4:
                break
        print(f"drain: {drained}", flush=True)

        polls = []
        t0 = time.time()
        g.cont()
        nonhex = 0
        # paced poll: 20 ms between reads so CT evolution over seconds
        # is observable (the unpaced version exhausted its iteration cap
        # inside one frame)
        while time.time() - t0 < 3.0 and len(polls) < 400:
            t = time.time()
            try:
                raw = g.send(f"m{CT_BASE:x},2")
            except Exception as exc:
                raw = f"EXC:{type(exc).__name__}"
            dt = time.time() - t
            hexok = (raw and len(raw) == 4
                     and all(c in "0123456789abcdef" for c in raw))
            ct = int.from_bytes(bytes.fromhex(raw), "little") if hexok else None
            if not hexok:
                nonhex += 1
            polls.append({"t": round(t - t0, 4), "rtt": round(dt, 4),
                          "raw": raw, "ct": ct})
            if ct is not None and ct >= 998:
                break
            time.sleep(0.02)
        print(f"polls={len(polls)} nonhex={nonhex} wall={time.time()-t0:.2f}s",
              flush=True)
        print("first 40:", [(p["t"], p["raw"]) for p in polls[:40]], flush=True)
        seq = [p["ct"] for p in polls if p["ct"] is not None]
        # run-length encode the parsed trajectory
        rle = []
        for v in seq:
            if rle and rle[-1][0] == v:
                rle[-1][1] += 1
            else:
                rle.append([v, 1])
        print("rle(ct,count):", rle[:30], flush=True)
        rtts = sorted(p["rtt"] for p in polls)
        if rtts:
            print(f"rtt ms: p50={rtts[len(rtts)//2]*1000:.1f} "
                  f"min={rtts[0]*1000:.2f} max={rtts[-1]*1000:.1f}",
                  flush=True)
        if polls:
            print(f"end: last t={polls[-1]['t']:.3f} ct={polls[-1]['ct']}",
                  flush=True)
        g.cont()
    return 0


if __name__ == "__main__":
    sys.exit(main())
