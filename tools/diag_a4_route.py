"""Stage-by-stage diagnostic for the A4 dispatch route (one boot).

Runs the same boot/patch/route as tools/a4_fixture_build.py but prints,
after every press, three scene fingerprints (all reads re-continue the
core afterwards, DE-029):

  * u32 @ 0x0200020d4 / 0x020005d84 — the placement screen's
    current-member pointers (member record base or not),
  * u32 @ 0x0200F4A8 — the battle object pointer (0x0200F4E8 once the
    battle exists; ai-findings.md), the battle-formed discriminator,
  * u8  @ 0x03000005 — key-enable after the engine had a chance to
    clear it.

After the confirm it polls the battle object for 90 s, then runs a 6 s
router-breakpoint window (menu-loop router, ~10 hits/s when an open
battle menu exists) to say outright whether a battle menu is open.

Stdout only; no artifacts claimed.
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

BP_ROUTER = 0x080C2944  # fallback if probe constant differs; verified below
try:
    from probe_control_handoff import BP_ROUTER  # noqa: E402
except Exception:
    pass
BATTLE_OBJ = 0x0200F4A8
PTR_SLOTS = (0x0200020D4, 0x020005D84)


def fp(g, tag):
    vals = []
    for a in PTR_SLOTS:
        vals.append(u32(g, a))
    bo = u32(g, BATTLE_OBJ)
    ke = u8(g, KEY_ENABLE)
    g.cont()
    print(f"  fp {tag:16s} ptr020d4={vals[0] and hex(vals[0])} "
          f"ptr05d84={vals[1] and hex(vals[1])} "
          f"battleobj={bo and hex(bo)} keyen={ke}", flush=True)


def main():
    t0 = time.time()

    def say(msg):
        print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    with FixtureSession(os.path.join("outputs", "lua-nav", "engage.ss0"),
                        rom="baserom.gba") as session:
        g = session.g
        say(f"booted pid={session.pid}")
        session.write_u8(KEY_ENABLE, 1, "key enable (diag)")
        for k in range(MEMBER_COUNT):
            base = MEMBER_BASE + MEMBER_STRIDE * k
            session.write_u8(base + 5, JOB_THIEF, "diag retag")
            session.write_u8(base + 6, RACE_HUMAN, "diag retag")
            session.write_u8(base + 7, JOB_THIEF, "diag retag")
            session.write_u8(base + 8, 0, "diag retag")
        say("retagged")
        g.cont()
        time.sleep(1.0)
        fp(g, "engage-prompt")

        for mask, tag, pause in ROUTE:
            if mask is None:
                time.sleep(pause)
                say(f"settle {pause}s")
                continue
            session.write_u8(KEY_ENABLE, 1, f"key enable ({tag})")
            hits = press(g, mask, frames=PRESS_FRAMES)
            say(f"press {tag} hits={hits}")
            time.sleep(pause)
            fp(g, tag)
            if hits == 0:
                say("FATAL: zero hits")
                return 3

        say("polling battle object for 90 s")
        deadline = time.time() + 90.0
        bo = 0
        while time.time() < deadline:
            bo = u32(g, BATTLE_OBJ)
            g.cont()
            if bo == 0x0200F4E8:
                break
            time.sleep(5.0)
        say(f"battle object after confirm: {bo and hex(bo)}")

        # router BP: fires while an open battle menu exists
        try:
            if g.send(f"Z0,{BP_ROUTER:x},2") != "OK":
                say(f"router BP rejected: {g.send(f'Z0,{BP_ROUTER:x},2')!r}")
                return 4
            g.cont()
            try:
                stop = g._read_packet()
            except Exception:
                stop = None
            say(f"router window stop: {stop!r}")
            g.send(f"z0,{BP_ROUTER:x},2")
            g.cont()
        except Exception as exc:
            say(f"router window error: {exc}")
    say("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
