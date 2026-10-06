"""Where does the A4 dispatch route actually end up? PC-loop fingerprints.

Two sessions:
  A. boot placement.ss0 (KNOWN placement screen) — sample the idle-loop
     PC repeatedly for a baseline,
  B. boot engage.ss0, apply the retag + dispatch route from
     a4_fixture_build, sample PC after every stage, dump EWRAM at the
     end for offline diff against the placement dump.

A served 'g'/'m' implicitly halts the core (DE-029) — every sample is
followed by cont(). Matching PC loops place the screen: post-route PCs
inside the placement baseline loop means the route died on the placement
screen; engage-loop means the first A never landed.

Stdout only; EWRAM dump lands in outputs/autobattle/scratch/.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, u8, u32  # noqa: E402
from a4_fixture_build import (JOB_THIEF, KEY_ENABLE, MEMBER_BASE,  # noqa: E402
                              MEMBER_COUNT, MEMBER_STRIDE, PRESS_FRAMES,
                              RACE_HUMAN, ROUTE, press)

EWRAM = 0x02000000
EWRAM_SIZE = 0x40000


def sample_pcs(g, n=6, gap=0.7):
    pcs = []
    for _ in range(n):
        pc = g.read_pc()
        pcs.append(pc)
        g.cont()
        time.sleep(gap)
    return [hex(p) if p else None for p in pcs]


def dump_ewram(g, path):
    blob = b""
    for off in range(0, EWRAM_SIZE, 512):
        chunk = g.read_mem(EWRAM + off, 512)
        blob += chunk or b"\x00" * 512
    g.cont()
    with open(path, "wb") as fh:
        fh.write(blob)
    print(f"  ewram dump -> {path} ({len(blob)} bytes)", flush=True)


def session_anchor(state, tag):
    print(f"== anchor {tag}: {state}", flush=True)
    with FixtureSession(state, rom="baserom.gba", quiet=True) as s:
        time.sleep(1.5)
        pcs = sample_pcs(s.g, n=6)
        print(f"  {tag} PCs: {pcs}", flush=True)
        return pcs


def main():
    session_anchor(os.path.join("outputs", "lua-nav", "placement.ss0"),
                   "placement")

    t0 = time.time()

    def say(msg):
        print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    print("== route session (engage.ss0)", flush=True)
    with FixtureSession(os.path.join("outputs", "lua-nav", "engage.ss0"),
                        rom="baserom.gba") as session:
        g = session.g
        say(f"booted pid={session.pid}")
        session.write_u8(KEY_ENABLE, 1, "key enable")
        for k in range(MEMBER_COUNT):
            base = MEMBER_BASE + MEMBER_STRIDE * k
            for off, val in ((5, JOB_THIEF), (6, RACE_HUMAN),
                             (7, JOB_THIEF), (8, 0)):
                session.write_u8(base + off, val, "diag retag")
        g.cont()
        time.sleep(1.0)
        print(f"  engage idle PCs: {sample_pcs(g, n=4)}", flush=True)

        for mask, tag, pause in ROUTE:
            if mask is None:
                time.sleep(pause)
                continue
            session.write_u8(KEY_ENABLE, 1, f"key enable ({tag})")
            hits = press(g, mask, frames=PRESS_FRAMES)
            time.sleep(pause)
            pcs = sample_pcs(g, n=4)
            say(f"{tag}: hits={hits} PCs={pcs}")
            if hits == 0:
                say("FATAL zero hits")
                return 3

        say("polling for menu/route progress 60 s (PC samples)")
        for i in range(6):
            pcs = sample_pcs(g, n=3, gap=5.0)
            say(f"t+{i}: {pcs}")
        dump_ewram(g, os.path.join("outputs", "autobattle", "scratch",
                                   "a4-route-ewram.bin"))
    say("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
