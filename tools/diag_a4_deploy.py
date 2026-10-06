"""A4 deploy-state diagnostic: does each route stage actually deploy?

After every press, drain-paired reads of each member's dispatch signature
(found by diffing the engage 0/6 dump vs the A1 placement 1/6 dump):

  member +0x028  deployed flag (00 -> 01 when placed)
  member +0x0F6  placement tile x
  member +0x0F7  placement tile y

plus a window screenshot after START/confirm. Stdout only.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, u8  # noqa: E402
from probe_a8_speed import drain_paired  # noqa: E402
from a4_fixture_build import (A, DOWN, START, JOB_THIEF, KEY_ENABLE,  # noqa: E402
                              MEMBER_BASE,
                              MEMBER_COUNT, MEMBER_STRIDE, PRESS_FRAMES,
                              RACE_HUMAN, ROUTE, press)

SCRATCH = os.path.join("outputs", "autobattle", "scratch")


def deployed(g):
    out = []
    for k in range(MEMBER_COUNT):
        base = MEMBER_BASE + MEMBER_STRIDE * k
        if u8(g, base + 0x28):
            out.append((k, u8(g, base + 0x28), u8(g, base + 0xF6),
                        u8(g, base + 0xF7)))
    g.cont()
    return out


PTR_SLOTS = (0x0200020D4, 0x020005D84, 0x02002267C, 0x020030F9C,
             0x0200315EC)


def cursor_ptrs(g):
    """The five UI slots that held the highlighted member's record ptr."""
    from fixture_guard import u32
    out = []
    for a in PTR_SLOTS:
        v = u32(g, a)
        if v and MEMBER_BASE <= v < MEMBER_BASE + MEMBER_STRIDE * MEMBER_COUNT:
            out.append((v - MEMBER_BASE) // MEMBER_STRIDE)
        else:
            out.append(None)
    g.cont()
    return out


def shot(pid, tag):
    path = os.path.join(SCRATCH, f"a4dep-{tag}.png")
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=60)
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        px = img.load()
        w, h = img.size
        vals = [(px[x, y][0] + px[x, y][1] + px[x, y][2]) // 3
                for y in range(0, h, 3) for x in range(0, w, 3)]
        mean = sum(vals) / len(vals)
        sd = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
        print(f"  shot {tag}: mean={mean:.1f} sd={sd:.1f}", flush=True)
    except Exception as exc:
        print(f"  shot {tag}: {exc}", flush=True)



def stage5():
    """Adaptive second-member experiment on the proven deploy skeleton.

    Skeleton (pinned by stage4): enter, dismiss, pick, place,
    back-to-list (A), START (list only!), confirm -> battle.
    Between place and START, try selector candidates for a SECOND member:
    plain A (pedestal auto-advance), R/L, UP, DOWN — each followed by a
    pick-A and a flag check. First candidate deploying a new member wins;
    then finish the skeleton and verify the battle roster. Last resort:
    RAM-patch member 1's deploy signature (+0x28/+0xF6/F7/+0xFB).
    """
    from fixture_guard import u16, u32, ROSTER, STRIDE
    UP, LEFT, RIGHT = 0x40, 0x20, 0x10
    seq = [(A, "enter", 1.6), (A, "dismiss", 2.6), (A, "pick", 1.4),
           (A, "place", 1.8), (A, "back-to-list", 1.6)]
    with FixtureSession(os.path.join("outputs", "lua-nav", "engage.ss0"),
                        rom="baserom.gba") as session:
        g = session.g
        pid = session.pid
        session.write_u8(KEY_ENABLE, 1, "key enable")
        for k in range(MEMBER_COUNT):
            base = MEMBER_BASE + MEMBER_STRIDE * k
            for off, val in ((5, JOB_THIEF), (6, RACE_HUMAN),
                             (7, JOB_THIEF), (8, 0)):
                session.write_u8(base + off, val, "retag")
        g.cont()
        time.sleep(1.0)
        for mask, tag, pause in seq:
            drain_paired(g)
            hits = press(g, mask, frames=PRESS_FRAMES)
            time.sleep(pause)
            print(f"{tag}: hits={hits} deployed={deployed(g)}", flush=True)
            if hits == 0:
                return 3

        candidates = [(None, "plain-A"), (RIGHT, "R"), (LEFT, "L"),
                      (UP, "up"), (DOWN, "down")]
        winner = None
        for ckey, cname in candidates:
            if ckey is not None:
                drain_paired(g)
                press(g, ckey, frames=PRESS_FRAMES)
                time.sleep(1.2)
            drain_paired(g)
            hits = press(g, A, frames=PRESS_FRAMES)
            time.sleep(1.4)
            dep = deployed(g)
            n = len({k for k, *_ in dep})
            print(f"candidate {cname}: deployed={dep}", flush=True)
            if n >= 2:
                winner = cname
                # place + back-to-list, then START from the list
                for tag2 in ("place2", "back2"):
                    drain_paired(g)
                    press(g, A, frames=PRESS_FRAMES)
                    time.sleep(1.6)
                    print(f"  {tag2}: deployed={deployed(g)}", flush=True)
                break
            # undo a stray pick (un-place / back to list) before next try
            drain_paired(g)
            press(g, A, frames=PRESS_FRAMES)
            time.sleep(1.4)
            drain_paired(g)
            press(g, A, frames=PRESS_FRAMES)
            time.sleep(1.4)
            print(f"  undo state: deployed={deployed(g)}", flush=True)

        if winner is None:
            print("NAV FAILED -> RAM-patch member 1 deploy signature",
                  flush=True)
            base1 = MEMBER_BASE + MEMBER_STRIDE * 1
            session.write_u8(base1 + 0x28, 1,
                             "A4: force member 1 deploy flag (nav failed)")
            session.write_u8(base1 + 0xF6, 5,
                             "A4: member 1 deploy tile x (nav failed)")
            session.write_u8(base1 + 0xF7, 10,
                             "A4: member 1 deploy tile y (nav failed)")
            session.write_u8(base1 + 0xFB, 5,
                             "A4: member 1 facing (nav failed)")
            time.sleep(0.5)
            print(f"after patch: {deployed(g)}", flush=True)

        time.sleep(2.5)
        drain_paired(g)
        hits = press(g, START, frames=PRESS_FRAMES)
        time.sleep(1.8)
        drain_paired(g)
        hits2 = press(g, A, frames=PRESS_FRAMES)
        time.sleep(1.6)
        print(f"START hits={hits} confirm hits={hits2}", flush=True)

        # wait for the battle roster
        rows = []
        players = enemies = judges = 0
        deadline = time.time() + 95.0
        while time.time() < deadline:
            drain_paired(g)
            rows = []
            for i in range(8):
                base = ROSTER + STRIDE * i
                name_ptr = u32(g, base)
                if not name_ptr:
                    continue
                rows.append({
                    "slot": i,
                    "job": u8(g, base + 7),
                    "side": bool(u16(g, base + 0x28) & 0x8000),
                    "type": u8(g, base + 4),
                    "flag": u8(g, MEMBER_BASE + 0x28) if i == 0 else None,
                })
            g.cont()
            players = [r for r in rows if not r["side"] and r["type"] != 20]
            enemies = [r for r in rows if r["side"]]
            judges = [r for r in rows if not r["side"] and r["type"] == 20]
            if len(players) >= 2 and len(enemies) == 5:
                break
            time.sleep(4.0)
        print(f"roster: players={[(r['slot'], r['job']) for r in players]} "
              f"enemies={[(r['slot'], r['job']) for r in enemies]} "
              f"judge={len(judges)}", flush=True)
        ok = (len(players) >= 2 and len(enemies) == 5
              and all(r["job"] == 5 for r in players)
              and any(r["job"] == 5 for r in enemies))
        print(f"winner={winner} STAGE5 {'PASS' if ok else 'FAIL'}",
              flush=True)
        shot(pid, "stage5-end")
    return 0 if ok else 1


def main():
    if "--stage5" in sys.argv:
        return stage5()
    with FixtureSession(os.path.join("outputs", "lua-nav", "engage.ss0"),
                        rom="baserom.gba") as session:
        g = session.g
        pid = session.pid
        session.write_u8(KEY_ENABLE, 1, "key enable")
        for k in range(MEMBER_COUNT):
            base = MEMBER_BASE + MEMBER_STRIDE * k
            for off, val in ((5, JOB_THIEF), (6, RACE_HUMAN),
                             (7, JOB_THIEF), (8, 0)):
                session.write_u8(base + off, val, "retag")
        g.cont()
        time.sleep(1.0)
        print(f"deployed before route: {deployed(g)}", flush=True)

        # --stage2: DOWN-first on the initial list (cursor before pick) --
        # --stage4: key-cycle study (UP/DOWN/LEFT/RIGHT + shots on the
        #   initial list), then pick/place/back-to-list, then START from
        #   the list screen (hypothesis: START only fires from the list).
        S4 = [(A, "enter-dispatch", 1.6), (A, "dismiss-notice", 2.6)]
        for kname, kmask in (("up", 0x40), ("down", 0x80),
                             ("left", 0x20), ("right", 0x10)):
            S4.append((kmask, f"key-{kname}", 1.2))
        S4 += [(A, "pick-x", 1.4), (A, "place-x", 1.8),
               (A, "back-to-list", 1.6),
               (None, "settle", 2.5),
               (START, "to-battle", 1.7), (A, "confirm", 1.6)]
        if "--stage4" in sys.argv:
            route = S4
        else:
            route = ROUTE
        for idx, (mask, tag, pause) in enumerate(route):
            if mask is None:
                time.sleep(pause)
                print(f"  settle {pause}s", flush=True)
                continue
            drain_paired(g)
            hits = press(g, mask, frames=PRESS_FRAMES)
            time.sleep(pause)
            drain_paired(g)
            dep = deployed(g)
            cur = cursor_ptrs(g)
            print(f"press #{idx} {tag} hits={hits} deployed={dep} "
                  f"cursor={cur}", flush=True)
            shot(pid, f"{idx}-{tag}")
            if hits == 0:
                return 3
        time.sleep(8.0)
        shot(pid, "post-route")
        time.sleep(40.0)
        shot(pid, "post+40s")
        drain_paired(g)
        print(f"deployed at end: {deployed(g)}", flush=True)
        rows = []
        deadline = time.time() + 60.0
        while time.time() < deadline:
            from fixture_guard import ROSTER, STRIDE, u16, u32
            names = [u32(g, ROSTER + STRIDE * i) for i in range(8)]
            g.cont()
            live = sum(1 for n in names if n)
            if live >= 5:
                break
            time.sleep(4.0)
        print(f"roster live slots: {live}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
