"""A4 multi-ally fixture: retag the clan, drive the A1 dispatch route, save.

Astra round 9 step 3 — the missing fixture for the same-job cross-side
divergence demo. No verified roster held two same-job units (player jobs
were all distinct from the enemy set 41/5/40/36/22), so this builds one:

  1. boot `engage.ss0` through the owned FixtureSession (GDB stub),
  2. retag every save member record to Thief (job 5, race 1, secondary 0) —
     job 5 is enemy Velasquez's job, so any two deployed members are
     same-job allies AND an enemy of that job exists by construction,
  3. drive the proven A1 dispatch route through the 0x08000494 key-poll
     channel (A, A, A, A, DOWN, A, A, settle, START, A): two members
     deployed regardless of post-place cursor semantics — both are job 5,
  4. wait for the battle roster to fill (2 players + 5 enemies + judge),
  5. save the state with mGBA's Shift+F2 slot hotkey (discovered by
     tools/discover_state_hotkey.py; the Lua console channel is dead per
     DE-024) and copy `baserom.ss2` out as the fixture .ss0,
  6. write the build evidence JSON.

`--verify <state>` re-boots a built fixture read-only and dumps the roster
for round-trip comparison.

Key presses: verify_fixture_baseline.py's proven Recorder.press shape —
only the key-poll breakpoint armed during a press, 5 frames, r1 |= mask,
disable in finally; key-enable byte written once at attach.

Evidence: outputs/autobattle/A4-demo/fixture-build.json (committed via
force-add; no game bytes beyond identity fields already used in receipts).
The .ss0 itself stays untracked, like every other savestate here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import (FixtureSession, OFF_CT, ROSTER, STRIDE,  # noqa: E402
                           decode_ram_name, u8, u16, u32)
from probe_a8_speed import drain_paired  # noqa: E402  (DE-028 offset cure)

KEY_BL = 0x08000494
KEY_ENABLE = 0x03000005
A, DOWN, START, RIGHT = 0x01, 0x80, 0x08, 0x10
JOB_THIEF, RACE_HUMAN = 5, 1
MEMBER_BASE = 0x02000080
MEMBER_COUNT = 14
MEMBER_STRIDE = 0x108
OUT_DIR = os.path.join("outputs", "autobattle", "A4-demo")
FIXTURE = os.path.join("outputs", "lua-nav", "a4-multi-ally-battle-start.ss0")
SENDKEY = os.path.join("tools", "sendhotkey_window.ps1")
DEFAULT_STATE = os.path.join("outputs", "lua-nav", "engage.ss0")

# (mask, label, pause seconds) — pauses follow the A1 timing caveat
# (START fires reliably only ~2 s after the placement screen settles).
# Full dispatch flow pinned live by tools/diag_a4_deploy.py (stage4/5):
#   A enter, A dismiss -> LIST; A pick0 (writes +0x28 flag + tile), A
#   place0; A back to LIST; **re-pick cycle** (two extra A's before the
#   switch — the stage5-winnning path had them, without them pick1 never
#   deploys); **D-pad RIGHT (0x10, NOT the R shoulder 0x100) switches the
#   pedestal unit**; A pick1, A place1; A back to LIST;
#   settle; START (fires ONLY from the list); A confirm -> intro -> battle.
ROUTE = [
    (A, "enter-dispatch", 1.6),
    (A, "dismiss-notice", 2.6),
    (A, "pick-0", 1.4),
    (A, "place-0", 1.8),
    (A, "back-to-list", 1.6),
    (A, "re-pick-0", 1.4),
    (A, "re-place-0", 1.8),
    (A, "re-back-to-list", 1.6),
    (RIGHT, "switch-member", 1.2),
    (A, "pick-1", 1.4),
    (A, "place-1", 1.8),
    (A, "back-to-list-2", 1.6),
    (None, "settle", 3.0),
    (START, "to-battle", 1.7),
    (A, "confirm", 1.6),
]
PRESS_FRAMES = 12   # A1 Lua used 14-30 frame holds; Recorder uses 5


def press(g, mask, frames=12):
    """One key press through the key-poll breakpoint. Returns hit count."""
    hits = 0
    try:
        if g.send(f"Z0,{KEY_BL:x},2") != "OK":
            print(f"  FAIL: key poll breakpoint rejected ({mask:#x})")
            return 0
        for _ in range(frames):
            g.cont()
            stop = g._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = g.read_registers()
            if not regs:
                break
            if regs[15] == KEY_BL:
                val = (regs[1] | mask) & 0x3FF
                g.send("P1=" + val.to_bytes(4, "little").hex())
                hits += 1
    finally:
        try:
            g.send(f"z0,{KEY_BL:x},2")
            g.cont()
        except Exception:
            pass
    return hits


def roster_rows(session, g):
    """Live roster identity rows (job/side/name) — the demo's ground truth."""
    rows = []
    for i in range(8):
        base = ROSTER + STRIDE * i
        name_ptr = u32(g, base)
        if not name_ptr:
            continue
        hp, mx = u16(g, base + 0x18), u16(g, base + 0x1A)
        rows.append({
            "slot": i,
            "name_text": decode_ram_name(g, name_ptr, rom=session.read_rom_bytes()),
            "job": u8(g, base + 0x07),
            "base_job": u8(g, base + 0x05),
            "race": u8(g, base + 0x06),
            "level": u8(g, base + 0x09),
            "type": u8(g, base + 0x04),
            "id": u8(g, base + 0x104),
            "side_bit": bool(u16(g, base + 0x28) & 0x8000),
            "hp": hp, "max_hp": mx,
            "ct": u16(g, base + OFF_CT),
        })
    # DE-029: a served read implicitly halts the core; only 'c' resumes it.
    # Every roster poll must re-continue or the intro freezes mid-drive.
    try:
        g.cont()
    except Exception:
        pass
    return rows


def build(args):
    lines = []
    t0 = time.time()

    def say(msg):
        print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)
        lines.append(msg)

    os.makedirs(OUT_DIR, exist_ok=True)
    with FixtureSession(args.state, rom=args.rom) as session:
        g = session.g
        pid = session.pid
        say(f"booted {os.path.basename(args.state)} pid={pid}")

        # -- 1. key enable (protocol: write once at attach) ----------------
        session.write_u8(KEY_ENABLE, 1, "key enable (dispatch route)")

        # -- 2. retag every clan member to Thief ---------------------------
        rom_data = session.read_rom_bytes()
        for k in range(MEMBER_COUNT):
            base = MEMBER_BASE + MEMBER_STRIDE * k
            old = (u8(g, base + 5), u8(g, base + 6), u8(g, base + 7),
                   u8(g, base + 8))
            session.write_u8(base + 5, JOB_THIEF,
                             f"member {k} base job -> 5 (A4 same-job fixture)")
            session.write_u8(base + 6, RACE_HUMAN,
                             f"member {k} race -> job-5 race (A4 fixture)")
            session.write_u8(base + 7, JOB_THIEF,
                             f"member {k} active job -> 5 (A4 same-job fixture)")
            session.write_u8(base + 8, 0,
                             f"member {k} secondary -> 0 (A4 same-job fixture)")
            new = (u8(g, base + 5), u8(g, base + 6), u8(g, base + 7),
                   u8(g, base + 8))
            if new != (JOB_THIEF, RACE_HUMAN, JOB_THIEF, 0):
                say(f"FATAL: member {k} patch readback {new}")
                return 2
            if k == 0:
                say(f"member 0 patch {old} -> {new}")
        say(f"retagged {MEMBER_COUNT} members to job {JOB_THIEF}")
        g.cont()   # readbacks halted the core (DE-029) — let the prompt run

        # -- 3. dispatch route ---------------------------------------------
        time.sleep(1.0)   # engage prompt settle after attach
        for mask, tag, pause in ROUTE:
            if mask is None:
                time.sleep(pause)
                say(f"  settle {pause}s")
                continue
            # DE-028: any read before the press can leave the stream one
            # reply out of phase, after which the press's register patches
            # misapply and the input silently no-ops (A4 route, 2026-10-05).
            # Converge pairing immediately before arming; keep the hot path
            # free of readbacks (one key-enable write at boot is enough —
            # the engine's re-clear is not gating, run 13).
            if not drain_paired(g):
                say(f"WARN: stream not paired before {tag}")
            hits = press(g, mask, frames=PRESS_FRAMES)
            say(f"  press {tag} mask={mask:#04x} hits={hits}")
            if hits == 0:
                say(f"FATAL: {tag} delivered 0 hits — route aborted")
                return 3
            time.sleep(pause)
            # stage5 cadence: flag probe between presses (the timing of
            # these reads mattered — R+pick deploys only at this pace)
            if not drain_paired(g):
                say(f"WARN: stream not paired at {tag} flag probe")
            fl = [k for k in range(MEMBER_COUNT)
                  if u8(g, MEMBER_BASE + MEMBER_STRIDE * k + 0x28)]
            g.cont()
            say(f"    flags after {tag}: {fl}")

        # -- 4. wait for the battle roster to fill -------------------------
        # fail fast: both deploy flags must be set before the roster wait
        if not drain_paired(g):
            say("WARN: stream not confirmed paired; reads may be shifted")
        flags = [k for k in range(MEMBER_COUNT)
                 if u8(g, MEMBER_BASE + MEMBER_STRIDE * k + 0x28)]
        g.cont()
        say(f"deployed members after route: {flags}")
        if len(flags) < 2:
            say("FATAL: fewer than two members deployed — route broke")
            return 8
        deadline = time.time() + 120.0
        rows = []
        while time.time() < deadline:
            rows = roster_rows(session, g)   # re-continues the core itself
            players = [r for r in rows
                       if not r["side_bit"] and r["type"] != 20]
            enemies = [r for r in rows if r["side_bit"]]
            if len(players) == 2 and len(enemies) == 5:
                break
            time.sleep(3.0)
        players = [r for r in rows if not r["side_bit"] and r["type"] != 20]
        enemies = [r for r in rows if r["side_bit"]]
        judges = [r for r in rows if not r["side_bit"] and r["type"] == 20]
        say(f"roster: {len(players)} players {len(enemies)} enemies "
            f"{len(judges)} judge")
        for r in rows:
            say(f"  slot{r['slot']} {r['name_text']} job={r['job']} "
                f"side_enemy={r['side_bit']} hp={r['hp']}/{r['max_hp']}")
        ok_roster = (len(players) == 2 and len(enemies) == 5
                     and all(r["job"] == JOB_THIEF for r in players)
                     and any(r["job"] == JOB_THIEF for r in enemies))
        if not ok_roster:
            say("FATAL: roster does not satisfy the same-job demo shape")
            return 4

        # -- 5. save state via the mGBA slot hotkey ------------------------
        g.cont()   # core running for the snapshot
        ss_target = None
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-ExecutionPolicy",
                 "Bypass", "-File", SENDKEY, "-ProcId", str(pid),
                 "-Combo", "Shift+F2"],
                capture_output=True, text=True, timeout=40)
            say(f"hotkey: {(r.stdout + r.stderr).strip()[:120]}")
        except Exception as exc:
            say(f"FATAL: hotkey send failed: {exc}")
            return 5
        work_dir = session.work_dir
        cand = os.path.join(work_dir, "baserom.ss2")
        deadline = time.time() + 12.0
        while time.time() < deadline:
            if os.path.exists(cand) and os.path.getsize(cand) > 40000:
                ss_target = cand
                break
            time.sleep(1.0)
        if not ss_target:
            say(f"FATAL: state file not written at {cand}")
            return 6
        say(f"state saved: {ss_target} ({os.path.getsize(ss_target)} bytes)")

    # session closed (owned mGBA killed) — copy the state out
    os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
    shutil.copyfile(ss_target, FIXTURE)
    sha1 = hashlib.sha1(open(FIXTURE, "rb").read()).hexdigest()
    say(f"fixture written: {FIXTURE} sha1={sha1}")

    evidence = {
        "schema": "a4-fixture-build/1",
        "date": time.strftime("%Y-%m-%d"),
        "source_state": os.path.abspath(args.state),
        "fixture": FIXTURE,
        "fixture_sha1": sha1,
        "retag": {"job": JOB_THIEF, "race": RACE_HUMAN, "secondary": 0,
                  "members": MEMBER_COUNT},
        "route": [{"mask": m, "tag": t} for m, t, _ in ROUTE
                  if m is not None],
        "roster": rows,
        "players_same_job": all(r["job"] == JOB_THIEF for r in players),
        "enemy_same_job": any(r["job"] == JOB_THIEF for r in enemies),
        "ok": ok_roster,
        "log": lines,
        "t_elapsed_s": round(time.time() - t0, 1),
    }
    path = os.path.join(OUT_DIR, "fixture-build.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, indent=2)
    print(f"evidence: {path}")
    print(f"A4-FIXTURE BUILD {'PASS' if ok_roster else 'FAIL'}")
    return 0 if ok_roster else 7


def verify(args):
    """Read-only round trip: boot the built fixture, dump the roster."""
    with FixtureSession(args.verify, rom=args.rom) as session:
        rows = roster_rows(session, session.g)
    players = [r for r in rows if not r["side_bit"] and r["type"] != 20]
    enemies = [r for r in rows if r["side_bit"]]
    out = {"schema": "a4-fixture-verify/1",
           "fixture": os.path.basename(args.verify),
           "roster": rows,
           "players": len(players), "enemies": len(enemies),
           "players_same_job": len(players) >= 2
           and len({r["job"] for r in players}) == 1,
           "enemy_same_job": any(r["job"] == players[0]["job"]
                                 for r in enemies) if players else False}
    print(json.dumps(out, indent=1))
    ok = out["players"] == 2 and out["enemies"] == 5 \
        and out["players_same_job"] and out["enemy_same_job"]
    print(f"A4-FIXTURE VERIFY {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--rom", default="baserom.gba")
    ap.add_argument("--verify", metavar="STATE",
                    help="read-only roster dump of a built fixture")
    args = ap.parse_args()
    if args.verify:
        return verify(args)
    # retries: the R-switch step is timing-sensitive (stage5 vs the first
    # build attempt differed only in inter-press cadence); a fresh boot
    # per attempt is cheap and the winning attempt saves the state.
    rc = 1
    for attempt in (1, 2, 3):
        print(f"===== BUILD ATTEMPT {attempt} =====", flush=True)
        rc = build(args)
        if rc == 0 or rc not in (4, 8):
            break
    return rc


if __name__ == "__main__":
    sys.exit(main())
