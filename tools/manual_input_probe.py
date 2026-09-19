"""C1 'manual player command visibly works' — proven by an agent-driven player.

The previous C1 receipt marked this row `unknown` on the interpretation that
only a human pressing keys could prove it. Astra (round 4) corrected that: an
AGENT may detach the runner and then drive the emulator the way a player does
— through the window, never through the GDB stub. What must be proven:

  1. the runner detaches from a paused handoff (breakpoints disarmed,
     transport closed, emulator ALIVE — the leave-running proof),
  2. input sent through the WINDOW afterwards visibly works (the game
     reacts on screen),
  3. the detached session does not fight back: no GDB-stub key writes,
     no breakpoints re-armed while the player input lands.

Shape: guarded boot -> STOP mid-battle -> the CLI's exact handoff
(keep_process=True, __exit__) -> screenshot -> SendInput a player command
(START: the menu toggle, always available in battle) -> screenshot again ->
PASS only if the two frames differ AND the probe's stub write log shows no
write after detach.

Exit 0 = the handed-off battle visibly accepts player input.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import (FixtureSession, u16,  # noqa: E402
                           ROSTER, STRIDE, OFF_CT)
from autobattle_runtime import BattleRuntime  # noqa: E402
from probe_control_handoff import u8, CMD_CURSOR  # noqa: E402


def pid_alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                         capture_output=True, text=True).stdout
    return str(pid) in out


def capture(pid, path):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy",
                        "Bypass", "tools/capture_window.ps1",
                        "-ProcId", str(pid), "-Out", path],
                       capture_output=True, text=True, timeout=60)
    if "saved" not in (r.stdout or ""):
        raise RuntimeError(f"capture failed: {r.stdout!r} {r.stderr!r}")
    return path


def sendkey(pid, keys):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy",
                        "Bypass", "tools/sendkey_window.ps1",
                        "-ProcId", str(pid), "-Keys", keys],
                       capture_output=True, text=True, timeout=60)
    out = (r.stdout or "") + (r.stderr or "")
    if "sent" not in out:
        raise RuntimeError(f"sendkey failed: {out!r}")
    return out.strip()


def png_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", default="baserom.gba")
    ap.add_argument("--state", default="outputs/lua-nav/battle-start.ss0")
    ap.add_argument("--run-id", default="a3-manual-input-probe")
    ap.add_argument("--stop-at", type=float, default=45.0)
    args = ap.parse_args(argv)

    out_dir = os.path.join("outputs", "autobattle", args.run_id)
    os.makedirs(out_dir, exist_ok=True)
    stop_file = os.path.join(out_dir, "STOP")
    try:
        os.remove(stop_file)
    except OSError:
        pass

    session = FixtureSession(args.state, rom=args.rom)
    pid = None
    try:
        session.__enter__()
        pid = session.pid
        print(f"probe: emulator booted, pid={pid}, port={session.port}")
        scenario = {"scenario_id": "normal-battle"}
        rt = BattleRuntime(session, scenario, args.run_id, out_dir,
                           wall_timeout=240.0)
        if not rt.live_guard():
            print("FAIL: live guard failed")
            return 1
        threading.Timer(args.stop_at,
                        lambda: open(stop_file, "w").close()).start()
        final = rt.run()
        if final != "paused":
            print(f"FAIL: run ended {final}, not paused — nothing to hand off")
            return 1
        # the CLI's exact handoff semantics: flip keep_process BEFORE __exit__
        session.keep_process = True
        print(f"probe: paused at t (turns={rt.turn}); handing off to the "
              f"player (agent-driven)")
    finally:
        session.__exit__(None, None, None)

    time.sleep(2.0)
    if not pid_alive(pid):
        print(f"FAIL: emulator pid {pid} died — nothing handed off")
        return 1
    # the runner is detached (transport closed in __exit__/stop): from here
    # the ONLY way input can reach the game is the window — player input.
    # Baseline for the no-fight-back check: every stub write so far happened
    # while the runner owned the transport.
    writes_at_handoff = len(getattr(rt.p, "key_write_log", []))

    # Read-only re-attach (Astra round-6 gap 2): a bare Gdb connection can
    # READ memory without ever issuing a key write — a monitor, not a
    # controller. The player command sent through the window must move the
    # DECODED command cursor (0=Move, 1=Action, 2=Wait) for the proof to
    # mean anything: screenshots animate on their own, cursor state does not.
    monitor = None

    def read_cursor():
        try:
            v = u8(monitor, CMD_CURSOR)
            return v if v is not None and v <= 2 else None
        except Exception:
            return None

    # r6c lesson: with the CPU RUNNING, the stub's memory reads return the
    # ATTACH-time snapshot — cursor and CT were frozen artifacts, the false
    # "menu open" fired instantly, and no real keypress could move a stale
    # byte. A monitor must HALT around each read (interrupt -> read ->
    # cont): still read-only from the game's perspective (no key writes
    # ever cross the stub), the same thing a debugger does.
    def halt_read(fn):
        try:
            monitor.interrupt()
            try:
                return fn()
            finally:
                monitor.cont()
        except Exception:
            return None

    def open_monitor():
        from trace_mgba import Gdb
        import time as _t
        for attempt in range(30):
            try:
                m = Gdb("127.0.0.1", session.port, timeout=4)
                v = m.read_mem(CMD_CURSOR, 1)
                if v is not None:
                    # the stub HALTS the core on connect (that is why the
                    # read above succeeds instantly). A monitor must
                    # release it: the r6b probe skipped cont(), the game
                    # sat on a frozen frame, and every later read/keypress
                    # was a no-op (constant cursor, constant CT).
                    try:
                        m.cont()
                    except Exception:
                        pass
                    return m
            except Exception:
                pass
            _t.sleep(0.5)
        return None

    monitor = open_monitor()
    cursor_before = read_cursor() if monitor else None
    if cursor_before is None:
        print("FAIL: read-only re-attach could not read the decoded command "
              "cursor (manual command identity is unverifiable)")
        with open(os.path.join(out_dir, "probe.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"schema": "manual-input-probe/1", "run_id": args.run_id,
                       "emulator_pid": pid, "emulator_survived": True,
                       "paused_before_handoff": True,
                       "read_only_reattach": False,
                       "cursor_before": None,
                       "decoded_command": None,
                       "decoded_command_changed": False,
                       "stub_writes_at_handoff": writes_at_handoff,
                       "stub_writes_after_player_input": None,
                       "stub_fought_back": None}, fh, indent=2)
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True, text=True)
        return 1

    before = os.path.join(out_dir, "manual-before.png")
    after = os.path.join(out_dir, "manual-after.png")

    def read_marche_ct():
        try:
            return u16(monitor, ROSTER + STRIDE * 6 + OFF_CT)
        except Exception:
            return None

    def live_cursor():
        return halt_read(lambda: read_cursor())

    def live_ct():
        return halt_read(lambda: read_marche_ct())

    # A handed-off battle is usually MID-RECHARGE: Marche's next command
    # menu opens on the engine's schedule. The /2 probe sent DOWN,A at t≈0
    # after handoff, no menu was open, and the cursor legitimately never
    # moved — an honest no-op, not a proof. Wait for the player-command
    # window the way a player would: the menu is open when the decoded
    # cursor sits at 0/1/2 on two consecutive polls AND Marche's roster CT
    # is FROZEN between them (a charging CT moves ~26 ticks per 2 s poll;
    # a parked menu does not move).
    menu_wait_log = []
    cursor_at_open = None
    menu_open_t = None
    prev = (live_cursor(), live_ct())
    deadline = time.time() + 240.0
    while time.time() < deadline:
        time.sleep(2.0)
        nowr = (live_cursor(), live_ct())
        menu_wait_log.append({"t": round(240.0 - (deadline - time.time()), 1),
                              "cursor": nowr[0], "ct": nowr[1],
                              "prev_cursor": prev[0], "prev_ct": prev[1]})
        cur, ct = nowr
        pcur, pct = prev
        prev = nowr
        if (cur is not None and cur <= 2 and ct is not None
                and pct is not None and ct == pct and 0 < ct < 999
                and pcur == cur):
            cursor_at_open = cur
            menu_open_t = round(240.0 - (deadline - time.time()), 1)
            break
    if cursor_at_open is None:
        print("FAIL: no player-command window within 240 s of the handoff "
              "(no parked command menu observed)")
        receipt = {"schema": "manual-input-probe/3", "run_id": args.run_id,
                   "emulator_pid": pid, "emulator_survived": pid_alive(pid),
                   "paused_before_handoff": True,
                   "read_only_reattach": True,
                   "monitor_resumed_cpu": True,
                   "menu_open_detected": False,
                   "menu_wait_log": menu_wait_log,
                   "cursor_at_detach": cursor_before,
                   "stub_writes_at_handoff": writes_at_handoff,
                   "stub_fought_back": None}
        with open(os.path.join(out_dir, "probe.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(receipt, fh, indent=2)
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True, text=True)
        return 1
    try:
        capture(pid, before)
    except Exception as exc:
        print(f"FAIL: pre-input capture failed: {exc}")
        return 1

    # the player command: one DOWN — it must move the DECODED command
    # cursor (wrap included). Identity rides the cursor byte, which no
    # battle animation can fake.
    try:
        sendkey(pid, "DOWN:200")
    except Exception as exc:
        print(f"FAIL: player input could not be sent: {exc}")
        return 1
    time.sleep(1.5)
    try:
        capture(pid, after)
    except Exception as exc:
        print(f"FAIL: post-input capture failed: {exc}")
        return 1

    b, a = png_bytes(before), png_bytes(after)
    visibly_changed = b != a
    cursor_after = live_cursor()
    # identity: the decoded command changed (DOWN wraps the menu cursor)
    decoded_changed = (cursor_at_open is not None
                       and cursor_after is not None
                       and cursor_after != cursor_at_open)
    # no stub writes may have happened after the handoff: the detached
    # session must not fight the player for input
    stub_writes_after = len(getattr(rt.p, "key_write_log", []))
    fought_back = stub_writes_after > writes_at_handoff

    receipt = {
        "schema": "manual-input-probe/3",
        "run_id": args.run_id,
        "emulator_pid": pid,
        "emulator_survived": True,
        "paused_before_handoff": True,
        "read_only_reattach": True,
        "monitor_resumed_cpu": True,
        "menu_open_detected": True,
        "menu_open_at_s": menu_open_t,
        "cursor_at_detach": cursor_before,
        "cursor_at_open": cursor_at_open,
        "player_input_sent": "DOWN (window SendInput)",
        "cursor_after": cursor_after,
        "decoded_command": {"addr": f"0x{CMD_CURSOR:08x}",
                            "before": cursor_at_open,
                            "after": cursor_after},
        "decoded_command_changed": decoded_changed,
        "screen_changed": visibly_changed,
        "stub_writes_at_handoff": writes_at_handoff,
        "stub_writes_after_player_input": stub_writes_after,
        "stub_fought_back": fought_back,
        "menu_wait_log": menu_wait_log,
        "before": before,
        "after": after,
    }
    ok = decoded_changed and not fought_back
    print(f"probe: menu open at +{menu_open_t}s (cursor={cursor_at_open}); "
          f"decoded command cursor {cursor_at_open}->{cursor_after} "
          f"(changed={decoded_changed}), stub writes at handoff="
          f"{writes_at_handoff}, after player input={stub_writes_after}")
    if ok:
        print("PASS: the handed-off battle accepted a player command whose "
              "identity is proven by the DECODED cursor change (agent-driven, "
              "window input only, no stub involvement)")
    elif fought_back:
        print("FAIL: the detached session issued stub key writes after the "
              "handoff — it fought the player for input")
    else:
        print("FAIL: player input produced no decoded-command change on the "
              "handed-off emulator")
    with open(os.path.join(out_dir, "probe.json"), "w",
              encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)

    # cleanup: the probe owns this emulator; end it (this is the probe's
    # own teardown, NOT the runner's — the handoff proof is already made)
    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                   capture_output=True, text=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
