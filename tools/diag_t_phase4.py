"""Byte-level ground truth: log every byte the stub sends, timestamped,
against a scripted command sequence mimicking the T phase.

Sequence: drain polls -> 'c' -> sleep 1 s -> 'm' -> sleep -> raw 0x03 ->
'?' -> 'm' -> 'c' -> sleep 0.5 -> raw 0x03 -> '?' -> 'm'.

After each send, pump the socket for up to PUMP_S and print what
arrives, so reply counts (and any '+' acks / duplicates / lazy replies)
are observed rather than inferred.
"""

import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, ROSTER, STRIDE, OFF_CT  # noqa: E402
from probe_control_handoff import Probe, BP_KEY  # noqa: E402
from probe_a8_speed import clear_all_bps, arm_key_bp, disarm_key_bp  # noqa: E402

STATE = os.path.join("outputs", "lua-nav", "battle-start.ss0")
CT_BASE = ROSTER + STRIDE * 6 + OFF_CT
PUMP_S = 0.6


def pump(g, tag, dur=PUMP_S):
    """Recv whatever arrives for up to dur seconds; log raw bytes."""
    end = time.time() + dur
    got = b""
    g.sock.settimeout(0.05)
    while time.time() < end:
        try:
            chunk = g.sock.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            print(f"  {tag}: EOF", flush=True)
            break
        got += chunk
        print(f"  {tag} +{time.time():.3f}: {chunk!r}", flush=True)
    g.sock.settimeout(5.0)
    if not got:
        print(f"  {tag}: (nothing in {dur}s)", flush=True)
    return got


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

        print("== drain: m x2 while halted ==", flush=True)
        g.sock.sendall(g._frame(f"m{CT_BASE:x},2"))
        pump(g, "m1-halted")
        g.sock.sendall(g._frame(f"m{CT_BASE:x},2"))
        pump(g, "m2-halted")

        print("== c -> sleep 1s -> m (while running) ==", flush=True)
        g.sock.sendall(g._frame("c"))
        pump(g, "after-c", dur=0.3)
        time.sleep(1.0)
        g.sock.sendall(g._frame(f"m{CT_BASE:x},2"))
        pump(g, "m-running")

        print("== raw 0x03 -> ? -> m ==", flush=True)
        g.sock.sendall(b"\x03")
        pump(g, "0x03")
        g.sock.sendall(g._frame("?"))
        pump(g, "?")
        g.sock.sendall(g._frame(f"m{CT_BASE:x},2"))
        pump(g, "m-halted-1")

        print("== c -> sleep 0.5 -> raw 0x03 -> ? -> m ==", flush=True)
        g.sock.sendall(g._frame("c"))
        pump(g, "after-c2", dur=0.2)
        time.sleep(0.5)
        g.sock.sendall(b"\x03")
        pump(g, "0x03-2")
        g.sock.sendall(g._frame("?"))
        pump(g, "?-2")
        g.sock.sendall(g._frame(f"m{CT_BASE:x},2"))
        pump(g, "m-halted-2")

        print("== idle pump (any unsolicited traffic?) ==", flush=True)
        pump(g, "idle", dur=1.0)
        g.sock.sendall(g._frame("c"))
        pump(g, "final-c", dur=0.3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
