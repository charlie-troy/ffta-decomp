"""A4 route timeline: when does each screen resolve after a press?

One boot of engage.ss0. After each route press, drain-paired renders at
+2, +5, +10 and +20 s (signatures only) to watch the transition state
evolve: forced-blank (white transition), structured screen, or stuck.

No retag (isolate pacing from data), no battle wait. Stdout only.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession  # noqa: E402
import gba_screen  # noqa: E402
from probe_a8_speed import drain_paired  # noqa: E402
from a4_fixture_build import KEY_ENABLE, PRESS_FRAMES, ROUTE, press  # noqa: E402

DELAYS = (2, 5, 10, 20)


def sig(g, tag):
    import contextlib
    import io
    if not drain_paired(g):
        print(f"  sig {tag}: DRAIN-FAILED", flush=True)
        return
    try:
        mode, blank, bgs, disp = gba_screen.bg_config(g)
        g.cont()
        if blank:
            print(f"  sig {tag}: FORCED-BLANK", flush=True)
            return
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            gba_screen.cmd_ascii(g, None)
    except Exception as exc:
        print(f"  sig {tag}: render-failed {exc}", flush=True)
        try:
            g.cont()
        except Exception:
            pass
        return
    lines = [ln.rstrip() for ln in buf.getvalue().splitlines() if ln.strip()]
    hist = {}
    for row in lines:
        for ch in row:
            hist[ch] = hist.get(ch, 0) + 1
    bright = hist.get("@", 0) / max(1, sum(hist.values()))
    top = sorted(hist.items(), key=lambda kv: -kv[1])[:4]
    print(f"  sig {tag}: bright={bright:.2f} hist={top}", flush=True)
    # renders leave the core halted (reads halt; DE-029) — resume so the
    # timeline's delay sleeps actually advance emulated time.
    try:
        g.cont()
    except Exception:
        pass


def main():
    with FixtureSession(os.path.join("outputs", "lua-nav", "engage.ss0"),
                        rom="baserom.gba") as session:
        g = session.g
        session.write_u8(KEY_ENABLE, 1, "key enable")
        g.cont()
        time.sleep(1.5)
        sig(g, "engage-idle")

        for idx, (mask, tag, pause) in enumerate(ROUTE):
            if mask is None:
                time.sleep(pause)
                continue
            if not drain_paired(g):
                print(f"  DRAIN-FAILED before {tag}", flush=True)
            session.write_u8(KEY_ENABLE, 1, f"key enable ({tag})")
            if not drain_paired(g):
                print(f"  DRAIN-FAILED(2) before {tag}", flush=True)
            hits = press(g, mask, frames=PRESS_FRAMES)
            print(f"press #{idx} {tag} hits={hits}", flush=True)
            t0 = time.time()
            for d in DELAYS:
                remain = d - (time.time() - t0)
                if remain > 0:
                    time.sleep(remain)
                sig(g, f"{tag}+{d}s")
            if idx >= 4:   # through pick-1; enough to localize
                print("stopping after pick-1", flush=True)
                return 0
            if hits == 0:
                return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
