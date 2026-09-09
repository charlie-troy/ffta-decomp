"""A2.3 control: does a PLAYER unit's turn produce a sequencer ctx init?

v27 observed: after the 5 enemy turns (5 normal-seed BP hits), the round
froze with slot0 (ct=0, freshly picked, marks cleared) and NO further ctx
init. FFTA freezes CTs while a command menu is open, so that freeze is
consistent with "the game opened the player command menu on the controlled
enemy" — but only if player turns in general do NOT run the AI sequencer
init. This control answers it on pure retail:

  end Marche's turn (proven key route) -> the 5 enemies act (5 normal-seeds)
  -> the round eventually returns to Marche -> does a 6th normal-seed fire?

If YES: player turns ctx-init -> v27's slot0 stop means its turn never
started (handout incomplete). If NO: player turns skip the AI sequencer ->
v27's frozen-on-slot0 state IS the player-menu handout.

Robustness: every exchange is interrupt-first (resync + drain), BPs armed
while halted, single clean session, cont before waiting, never abandon an
exchange mid-reply.

Usage: python tools/exp_control_v27c.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
BP_NORM = 0x080C03C2
BP_0B = 0x080C03B4
SLOT0 = 0x020159E8
STRIDE = 0x108
OUT = "outputs/lua-nav/round1-control.json"


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def window_capture(pid, path):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=45)
    print(f"  capture {path}: {'ok' if r.returncode == 0 else 'FAIL'}")


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=12)
    events = []
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        # v27-identical seam writes on slot0 (marks + side bit + duration).
        # NOTE: v27's menu input worked WITH these; testing whether they are
        # in fact required for the menu to accept input.
        SLOT0 = 0x020159E8
        STRIDE = 0x108
        mid = g.read_mem(0x02016018 + STRIDE * 6 + 0x104, 1)[0]
        e6 = g.read_mem(SLOT0 + 0xE6, 1)[0]
        dc = g.read_mem(SLOT0 + 0xDC, 1)[0]
        ea = g.read_mem(SLOT0 + 0xEA, 1)[0]
        ed = g.read_mem(SLOT0 + 0xED, 1)[0]
        assert g.send(f"M{SLOT0 + 0xE6:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xDC:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xED:x},1:{ed | 8:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xEA:x},1:{ea | 0x80:02x}") == "OK"
        print(f"  seam writes: e6={mid} dc={mid} ed={ed | 8:02x} "
              f"ea={ea | 0x80:02x}")
        # FFTA idle timer: menu input disables (~16 s). Force-enable before
        # driving the menu; also record the observed state for the log.
        ks = g.read_mem(0x03000000, 8)
        print(f"  keystruct: {ks.hex() if ks else None}")
        assert g.send("M3000005,1:01") == "OK", "enable write rejected"
        for bp in (KEY_BL, BP_NORM, BP_0B):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"

        def press(mask, tag, frames=5, pause=1.2):
            # v27-identical press: arm, 5 frames, disarm, cont, sleep with
            # the CPU RUNNING between presses (frozen gaps stall the menu
            # state machine)
            hits = 0
            try:
                if g.send(f"Z0,{KEY_BL:x},2") != "OK":
                    print(f"  FAIL: KEY_BL BP rejected ({tag})")
                    return 0
                for _ in range(frames):
                    g.cont()
                    stop = g._read_packet()
                    if not stop or stop[:1] not in ("S", "T"):
                        break
                    regs = g.read_registers()
                    if regs and regs[15] == KEY_BL:
                        val = (regs[1] | mask) & 0x3FF
                        g.send("P1=" + val.to_bytes(4, "little").hex())
                        hits += 1
                    elif regs and regs[15] == BP_NORM:
                        events.append(("norm", "during-key"))
                        print("  norm-seed during key press")
            finally:
                try:
                    g.send(f"z0,{KEY_BL:x},2")
                    g.cont()
                except Exception:
                    pass
            time.sleep(pause)
            print(f"  key {mask:#04x} x{hits} {tag}")
            return hits

        # ---- drive the menu -------------------------------------------------
        # Mirror v27 exactly: force enable (+5)=1 while HALTED (the stub
        # rejects M writes while running), then cont and press immediately.
        # No wake presses: UP/B/A sacrificial presses all scramble the menu
        # (0x40 is UP, not B).
        assert g.send("M3000005,1:01") == "OK", "enable write rejected"
        g.send("M3000007,1:8b")   # mode bit3: manual input gate (idle clears it)
        ks2 = g.read_mem(0x03000000, 8)
        print(f"  keystruct (halted, post-write): {ks2.hex() if ks2 else '?'}")
        g.cont()
        # The fixture resumes inside the battle-start sequence (law skit).
        # Pressing too early is ignored; waiting lets the idle timer kill
        # input. Robust memory gate: A on a cadence until the ctx main phase
        # byte (0x020101F8+0x54F4) reads 8 = command menu open (observed live
        # on a good boot; skit/dialog phases differ). A presses may open the
        # Move submenu once the menu is up - one B returns to root.
        ctx_phase = 0x020101F8 + 0x54F4

        def phase():
            d = g.read_mem(ctx_phase, 1)
            return d[0] if d else -1

        opened = False
        t0 = time.time()
        while time.time() - t0 < 120:
            try:
                p = phase()
            except Exception:
                g.interrupt()
                p = phase()
            if p == 8:
                opened = True
                print(f"  menu phase reached at t={time.time()-t0:.0f}s")
                break
            press(0x01, "skit-A")
            g.cont()          # press() leaves the CPU halted; skit must run
            time.sleep(2.5)
        if not opened:
            print("  menu phase never reached in 120 s")
        # re-force enable+mode while halted, then the proven sequence
        # immediately (v27's exact timing)
        g.interrupt()
        assert g.send("M3000005,1:01") == "OK", "enable write rejected"
        g.send("M3000007,1:8b")   # mode bit3 alongside enable
        g.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/v27c-0-menu.png")
        # NO preparation presses at phase 8: the root menu is already up and
        # a B here CLOSES it (observed: turn never commits afterwards). The
        # exact v27 sequence starts directly:
        for mask, tag in [(0x80, "DOWN1"), (0x80, "DOWN2"),
                          (0x01, "A-wait"), (0x01, "A-confirm")]:
            press(mask, tag)
        window_capture(pid, "outputs/lua-nav/v27c-1-committed.png")
        # KEY_BL BP no longer needed
        g.send(f"z0,{KEY_BL:x},2")

        # ---- watch up to 150 s: enemy turns, then Marche's round-2 turn ----
        norms = 0
        t0 = time.time()
        last_cap = 0.0
        g.sock.settimeout(3.0)
        while time.time() - t0 < 150 and norms < 7:
            try:
                g.cont()
                stop = g._read_packet()
            except Exception:
                stop = None
            now = time.time() - t0
            if stop and stop[:1] in ("S", "T"):
                regs = g.read_registers()
                pc = regs[15] if regs else 0
                if pc == BP_NORM:
                    norms += 1
                    events.append(("norm", round(now, 1)))
                    print(f"  norm-seed #{norms} t={now:.1f} "
                          f"r4={regs[4]:#010x}")
                    if norms >= 5:
                        time.sleep(1.0)
                        window_capture(
                            pid, f"outputs/lua-nav/v27c-norm{norms}.png")
                    if norms == 6:
                        # Marche's round-2 turn: capture + probe the menu
                        window_capture(pid, "outputs/lua-nav/v27c-round2.png")
                        print("  round-2 ctx init fired: player turns DO "
                              "ctx-init")
                        break
                continue
            if now - last_cap >= 12:
                window_capture(pid, f"outputs/lua-nav/v27c-t{now:.0f}.png")
                last_cap = now

        g.send(f"z0,{BP_NORM:x},2")
        g.send(f"z0,{BP_0B:x},2")
        g.interrupt()
        cts = [int.from_bytes(g.read_mem(SLOT0 + STRIDE * i + 0xD0, 2),
                              "little") for i in range(7)]
        print(f"final cts={cts} norm-seeds={norms}")
        g.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/v27c-final.png")
        json.dump({"events": events, "norms": norms, "final_cts": cts},
                  open(OUT, "w"), indent=1)
        print(f"wrote {OUT}")
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
