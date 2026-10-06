"""ASCII screen snapshots along the A4 dispatch route (where do we end up?).

Boots engage.ss0, renders the screen (gba_screen.cmd_ascii over the session's
own stub connection), applies the retag + dispatch route from a4_fixture_build,
and renders again after notice-dismiss and at the end. The ASCII luminance
art distinguishes: engage prompt, notice dialog (bottom text band), placement
screen (member list + pedestal), unit roster, banner/confirm, battle.

Stdout only.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession  # noqa: E402
import gba_screen  # noqa: E402
from probe_a8_speed import drain_paired  # noqa: E402 (DE-028 offset cure)
from a4_fixture_build import (JOB_THIEF, KEY_ENABLE, MEMBER_BASE,  # noqa: E402
                              MEMBER_COUNT, MEMBER_STRIDE, PRESS_FRAMES,
                              RACE_HUMAN, ROUTE, press)


def render(g, tag, full=False):
    """Compact screen signature: char histogram + 10x30 downsample.

    Uniform-@ screens are the white-transition/soft-lock signature; a real
    screen mixes .:-=+*#%@ glyphs. `full=True` also prints the coarse art.
    """
    import contextlib
    import io
    buf = io.StringIO()
    try:
        if not drain_paired(g):
            print(f"sig {tag}: DRAIN-FAILED (reads may be shifted)", flush=True)
        mode, blank, bgs, disp = gba_screen.bg_config(g)
        g.cont()
        with contextlib.redirect_stdout(buf):
            gba_screen.cmd_ascii(g, None)
    except Exception as exc:
        print(f"render failed: {exc}", flush=True)
        try:
            g.cont()
        except Exception:
            pass
        return
    lines = [ln.rstrip() for ln in buf.getvalue().splitlines() if ln.strip()]
    if not lines:
        print(f"sig {tag}: EMPTY", flush=True)
        return
    hist = {}
    for row in lines:
        for ch in row:
            hist[ch] = hist.get(ch, 0) + 1
    top = sorted(hist.items(), key=lambda kv: -kv[1])[:5]
    small = [row[::2] for row in lines[::4]]
    bright = hist.get("@", 0) / max(1, sum(hist.values()))
    print(f"sig {tag}: bright={bright:.2f} hist={top}", flush=True)
    for row in small:
        print(f"    {row}", flush=True)


def main():
    no_retag = "--no-retag" in sys.argv
    stop_after = None
    for i, a in enumerate(sys.argv):
        if a == "--stop-after":
            stop_after = sys.argv[i + 1]
    with FixtureSession(os.path.join("outputs", "lua-nav", "engage.ss0"),
                        rom="baserom.gba") as session:
        g = session.g
        session.write_u8(KEY_ENABLE, 1, "key enable")
        if not no_retag:
            for k in range(MEMBER_COUNT):
                base = MEMBER_BASE + MEMBER_STRIDE * k
                for off, val in ((5, JOB_THIEF), (6, RACE_HUMAN),
                                 (7, JOB_THIEF), (8, 0)):
                    session.write_u8(base + off, val, "diag retag")
        else:
            print("RETAG SKIPPED (--no-retag)", flush=True)
        g.cont()
        time.sleep(1.5)
        render(g, "engage-idle")

        for mask, tag, pause in ROUTE:
            if mask is None:
                time.sleep(pause)
                continue
            session.write_u8(KEY_ENABLE, 1, f"key enable ({tag})")
            hits = press(g, mask, frames=PRESS_FRAMES)
            print(f"press {tag} hits={hits}", flush=True)
            time.sleep(pause)
            render(g, tag)
            if hits == 0:
                return 3
            if stop_after and tag == stop_after:
                print(f"stopping after {stop_after}", flush=True)
                return 0
        time.sleep(20.0)
        render(g, "post-route+20s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
