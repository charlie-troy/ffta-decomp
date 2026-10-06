"""A4 no-input control: what does engage.ss0 do with NO key injection?

Renders (drain-paired) at +5/+15/+30/+45/+60/+75 s after boot. Establishes
which screen changes are autonomous (state animations/transitions) so the
route's press effects can be isolated. Stdout only.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession  # noqa: E402
from diag_a4_timeline import sig  # noqa: E402

STEPS = (5, 15, 30, 45, 60, 75)


def main():
    with FixtureSession(os.path.join("outputs", "lua-nav", "engage.ss0"),
                        rom="baserom.gba", quiet=True) as session:
        g = session.g
        g.cont()
        t0 = time.time()
        sig(g, "boot")
        for s in STEPS:
            remain = s - (time.time() - t0)
            if remain > 0:
                time.sleep(remain)
            sig(g, f"t+{s}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
