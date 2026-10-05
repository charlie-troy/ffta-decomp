"""Decisive: does the core run after cont, and what does a raw halt window
return?  Exposes the exact packet sequence of an interrupt window:

  drain -> cont -> sleep -> [raw 0x03 -> packet, '?' -> reply, 'm' -> data]
  repeat twice; plus one read-while-running between windows.

Interpretation:
  * 'm' after a raw halt showing an EVOLVED CT (not 296) proves the core
    ran during the sleep and that halt-reads are fresh;
  * read-while-running showing 296 proves the stale-snapshot law;
  * the raw strings show exactly which reply belongs to which request,
  i.e. where the off-by-one in interrupt() comes from.
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


def raw_halt(g, tag):
    t = time.time()
    g.sock.sendall(b"\x03")
    try:
        stop = g._read_packet()
    except Exception as exc:
        stop = f"EXC:{type(exc).__name__}"
    t_halt = time.time()
    try:
        st = g.send("?")
    except Exception as exc:
        st = f"EXC:{type(exc).__name__}"
    try:
        d = g.send(f"m{CT_BASE:x},2")
    except Exception as exc:
        d = f"EXC:{type(exc).__name__}"
    print(f"{tag}: stop={stop!r} status={st!r} ct={d!r} "
          f"(halt_rtt={t_halt - t:.3f}s)", flush=True)
    return d


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
        # drain strays while halted
        for i in range(8):
            try:
                raw = g.send(f"m{CT_BASE:x},2")
            except Exception as exc:
                raw = f"EXC:{exc}"
            print(f"drain[{i}]: {raw!r}", flush=True)
            if raw and len(raw) == 4 and all(
                    c in "0123456789abcdef" for c in raw):
                break

        # window 1: cont, sleep 1 s, raw halt sequence
        g.cont()
        time.sleep(1.0)
        try:
            while_running = g.send(f"m{CT_BASE:x},2")
        except Exception as exc:
            while_running = f"EXC:{type(exc).__name__}"
        print(f"read-while-running: {while_running!r}", flush=True)
        raw_halt(g, "w1")

        # window 2: cont, sleep 0.5 s, raw halt sequence
        g.cont()
        time.sleep(0.5)
        raw_halt(g, "w2")

        # window 3: cont, sleep 0.5 s, g.interrupt() as the probe uses it
        g.cont()
        time.sleep(0.5)
        r = g.interrupt()
        print(f"w3 g.interrupt() returned: {r!r}", flush=True)
        print(f"w3 m after interrupt: {g.send(f'm{CT_BASE:x},2')!r}",
              flush=True)
        g.cont()
    return 0


if __name__ == "__main__":
    sys.exit(main())
