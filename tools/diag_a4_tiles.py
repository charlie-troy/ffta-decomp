"""Read-only: what do the roster tile fields read at the player menu?

menu1's plan_identified_move rejected tile=(0,0) for slot7 (Marche, who
deployed at (4,10)). Boot the fixture, settle the menu, then read slot5/
slot7 tile bytes repeatedly (with drains between) plus the cmd/target
cursors and a full F0-FA dump, to separate a genuine 0,0 roster copy
from stream-shift garbage. Stdout only.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, ROSTER, STRIDE, u8  # noqa: E402
from probe_control_handoff import Probe, CMD_CURSOR, TARGET_X, TARGET_Y  # noqa: E402
from probe_a8_speed import drain_paired  # noqa: E402

STATE = os.path.join("outputs", "lua-nav", "a4-multi-ally-battle-start.ss0")


def dump(g, tag):
    print(f"-- {tag}", flush=True)
    for slot in (5, 7):
        base = ROSTER + STRIDE * slot
        row = [u8(g, base + off) for off in range(0xF0, 0xFB)]
        g.cont()
        print(f"   slot{slot} F0-FA: {row}", flush=True)
    drain_paired(g)
    print(f"   cursor={u8(g, CMD_CURSOR)} target="
          f"({u8(g, TARGET_X)},{u8(g, TARGET_Y)})", flush=True)
    g.cont()


def main():
    with FixtureSession(STATE, rom="baserom.gba") as session:
        probe = Probe(session, verbose=False)
        deadline = time.time() + 160
        settled = False
        while time.time() < deadline:
            if probe.player_menu_settled(2, tick_secs=3.0, allow_zero=True):
                settled = True
                break
        probe.disarm()
        print(f"settled={settled} player_slot={probe.player_slot()}",
              flush=True)
        if not settled:
            return 1
        for i in range(3):
            drain_paired(probe.g)
            dump(probe.g, f"read{i}")
        # effect snapshot cross-check (its x/y vs the raw reads)
        drain_paired(probe.g)
        for row in probe.effect_snapshot():
            if row["slot"] in (5, 7):
                print(f"   snapshot slot{row['slot']}: x={row['x']} "
                      f"y={row['y']} ct={row['ct']}", flush=True)
        probe.g.cont()
    return 0


if __name__ == "__main__":
    sys.exit(main())
