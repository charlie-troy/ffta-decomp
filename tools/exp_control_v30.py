"""A2.3 v30: order-based control + reverse handout. No menu gate needed.

Why earlier drives failed: mode byte 0x03000007 flickers 0x83/0x8b with no
input (gate-timeline.json) and phase 0x020101F8+0x54F4 pins at 8 from boot -
neither marks the command menu. The presses themselves DO register (menu-probe
key-struct diffs: held bits appear, pressed bits get consumed). The boot skit
simply absorbed early presses.

v30 design (order-based, no gate):
- Wait 10 s (skit over), then run the proven route DOWN,DOWN,A,A up to 3
  times (a B press precedes retries to close any submenu v27c saw A open).
  Commit verified by Marche's CT (record +0xD0) leaving 0 while halted.
- Control verdict, per compressed round: after commit write CT=10; his
  round-(n+1) turn then starts within ~2 s, BEFORE any menu can open.
  A BP_NORM seed (0x080C03C2, sequencer ctx-init, once per AI-turn start)
  in that pre-menu window would mean player turns ctx-init. No seed
  between commit and the next menu commit = player turns do not ctx-init
  (v27's frozen slot0 state was therefore the real menu handout).
- Reverse handout: after the last control commit, set Marche +0xEA bit 7
  (pick branch sub_080CDADC at 0x0809E3AE; v27 proved bit7-set routes a
  unit through the player-turn body) + CT=10. A seed with NO menu opening
  = he took an AI turn (the A2 experiment). A reopened menu = bit7
  insufficient for a player unit (class gate overrides).
- Restoration: clear bit 7 + CT=10; menu must reopen and the route must
  commit. All writes are single RAM bytes; nothing persists.

Run: python tools/boot_fixture_gdb.py && python tools/exp_control_v30.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
SLOT0 = 0x020159E8
STRIDE = 0x108
SLOT6 = SLOT0 + STRIDE * 6
EA6 = SLOT6 + 0xEA
ID6 = SLOT6 + 0x104
CT6 = SLOT6 + 0xD0
NAME0 = SLOT0                     # record +0x00 = ROM name ptr while live
BP_NORM = 0x080C03C2
OUT = "outputs/lua-nav/controlled-v30.json"
ROUTE = [(0x80, "DOWN1"), (0x80, "DOWN2"),
         (0x01, "A-wait"), (0x01, "A-confirm")]


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def window_capture(pid, path):
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=45)


class Run:
    def __init__(self, g, pid):
        self.g = g
        self.pid = pid
        self.t0 = time.time()
        self.seeds = []
        self.exited = False
        self.budget = 300.0

    def now(self):
        return round(time.time() - self.t0, 1)

    def expired(self):
        return time.time() - self.t0 > self.budget

    def u8(self, a):
        d = self.g.read_mem(a, 1)
        return d[0] if d else None

    def u16(self, a):
        d = self.g.read_mem(a, 2)
        return int.from_bytes(d, "little") if d else None

    def halt_state(self):
        g = self.g
        name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
        return {"ct6": self.u16(CT6), "ea6": self.u8(EA6),
                "live": (name0 & 0xFF000000) == 0x08000000}

    def press(self, mask, tag, frames=5, pause=0.9):
        g = self.g
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
                    self.seeds.append({"t": self.now(), "r4": regs[4],
                                       "during": tag})
        finally:
            try:
                g.send(f"z0,{KEY_BL:x},2")
            except Exception:
                pass
        time.sleep(pause)
        print(f"  key {mask:#04x} x{hits} {tag} (t={self.now()})")
        return hits

    def assert_enable(self):
        assert self.g.send("M3000005,1:01") == "OK", "enable write rejected"

    def commit_drive(self, tag):
        """Route attempts until CT leaves 0 (max 3, B-recovery on retries)."""
        for attempt in (1, 2, 3):
            try:
                self.g.interrupt()
                self.assert_enable()
                self.g.cont()
            except Exception:
                pass
            time.sleep(0.3)
            keys = ([(0x02, "B-recover")] if attempt > 1 else []) + ROUTE
            for mask, name in keys:
                self.press(mask, f"{tag}#{attempt}:{name}")
            deadline = time.time() + 6.0
            while time.time() < deadline:
                self.g.interrupt()
                st = self.halt_state()
                if not st["live"]:
                    self.exited = True
                    return False
                if st["ct6"] != 0:
                    print(f"  {tag}: COMMIT (attempt {attempt}, "
                          f"ct6={st['ct6']}) t={self.now()}")
                    return True
                self.g.cont()
                time.sleep(0.5)
            print(f"  {tag}: attempt {attempt} no commit")
        return False

    def listen(self, seconds, tag):
        g = self.g
        end = time.time() + seconds
        g.sock.settimeout(0.4)
        while time.time() < end:
            try:
                g.cont()
                stop = g._read_packet()
            except Exception:
                continue
            if stop and stop[:1] in ("S", "T"):
                regs = g.read_registers()
                if regs and regs[15] == BP_NORM:
                    g.interrupt()
                    st = self.halt_state()
                    self.seeds.append({"t": self.now(), "r4": regs[4],
                                       "during": tag})
                    print(f"  SEED t={self.now()} r4={regs[4]:#010x} ({tag})")
                    if not st["live"]:
                        self.exited = True
                        return
                continue

    def compress(self):
        g = self.g
        g.interrupt()
        assert g.send(f"M{CT6:x},2:{10:04x}") == "OK", "CT write rejected"
        g.cont()


def main():
    pid = mgba_pid()
    if not pid:
        print("no mGBA process; run tools/boot_fixture_gdb.py first")
        return 1
    print(f"mGBA pid {pid}")
    out = {}
    g = Gdb("127.0.0.1", 2345, timeout=10)
    r = Run(g, pid)
    try:
        stop = g.interrupt()
        print(f"GDB attached; stop={stop}")
        st = r.halt_state()
        if r.u8(ID6) != 6 or not st["live"]:
            print(f"fixture signature missing: id6={r.u8(ID6)} state={st}")
            return 1
        out["baseline"] = st
        assert g.send(f"Z0,{BP_NORM:x},2") == "OK", "BP_NORM rejected"

        # -------- phase A: three committed retail rounds --------------------
        print("waiting 10 s for the boot skit to finish...")
        r.listen(10.0, "skit")
        rounds = []
        for rnd in (1, 2, 3):
            if r.exited or r.expired():
                break
            ok = r.commit_drive(f"r{rnd}")
            rounds.append({"round": rnd, "committed": ok})
            if not ok:
                if pid:
                    window_capture(pid, f"outputs/lua-nav/v30-nocommit-r{rnd}.png")
                break
            # compress and watch the pre-menu window of his next turn
            r.compress()
            n_before = len(r.seeds)
            r.listen(8.0, f"r{rnd}->pre-menu")
            rounds[-1]["pre_menu_seeds"] = r.seeds[n_before:]
        out["phase_a"] = {
            "rounds": rounds,
            "seeds": r.seeds,
            "battle_exited": r.exited,
            "verdict": ("no ctx-init in any pre-menu window "
                        "=> player turns do not ctx-init"
                        if not r.seeds else
                        f"seeds observed: {r.seeds}"),
        }
        print(f"phase A: {out['phase_a']['verdict']}")

        # -------- phase B: reverse handout ----------------------------------
        committed_rounds = [x for x in rounds if x.get("committed")]
        if not r.exited and len(committed_rounds) >= 1:
            g.interrupt()
            ea = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea | 0x80:02x}") == "OK"
            out["phase_b"] = {"ea_before": ea, "ea_set": r.u8(EA6)}
            print(f"phase B: bit7 set ({ea:02x} -> {out['phase_b']['ea_set']:02x})")
            r.compress()
            n_before = len(r.seeds)
            got = None
            reopened = False
            t0 = time.time()
            while time.time() - t0 < 45 and not r.expired():
                r.listen(1.5, "B-bit7")
                if r.exited:
                    break
                g.interrupt()
                st = r.halt_state()
                if not st["live"]:
                    r.exited = True
                    break
                new = r.seeds[n_before:]
                if new:
                    got = new[0]
                    print(f"  t={r.now()}: seed with no menu -> Marche AI turn")
                    if pid:
                        time.sleep(2.0)
                        window_capture(pid, "outputs/lua-nav/v30-b-ai.png")
                    break
                # menu proxy: enable byte set + a B press opens nothing?
                # simplest observable: the route's DOWN would commit if a
                # menu were open - probe with one DOWN + CT check
                r.press(0x80, "B-probe", frames=3, pause=0.4)
                g.interrupt()
                if r.halt_state()["ct6"] != 0:
                    reopened = True
                    print(f"  t={r.now()}: DOWN committed a menu -> "
                          "Marche did NOT take an AI turn")
                    if pid:
                        window_capture(pid, "outputs/lua-nav/v30-b-menu.png")
                    break
                g.cont()
            out["phase_b"]["ai_turn_seed"] = got
            out["phase_b"]["menu_reopened"] = reopened
            out["phase_b"]["verdict"] = (
                "AI turn with ctx-init (seed, no menu)" if got else
                "menu reopened: bit7 insufficient for a player unit"
                if reopened else "no outcome (battle ended / timeout)")
            print(f"phase B verdict: {out['phase_b']['verdict']}")

            # -------- restoration -------------------------------------------
            g.interrupt()
            ea = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea & 0x7F:02x}") == "OK"
            out["phase_b"]["ea_restored"] = r.u8(EA6)
            r.compress()
            restored = r.commit_drive("restore")
            out["phase_b"]["restoration_committed"] = restored
            print(f"restoration: committed = {restored}")
        else:
            out["phase_b"] = {"skipped": True, "reason": f"exited={r.exited}"}

        # -------- wrap -------------------------------------------------------
        g.interrupt()
        out["final"] = {**r.halt_state(), "seeds_total": len(r.seeds),
                        "battle_exited": r.exited,
                        "budget_exceeded": r.expired()}
        g.send(f"z0,{BP_NORM:x},2")
        g.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/v30-final.png")
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"wrote {OUT}")
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
