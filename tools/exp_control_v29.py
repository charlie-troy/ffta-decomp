"""A2.3 v29 (v2): disciplined control + reverse handout.

What the earlier attempts got wrong, now fixed:
- v28 read memory while the CPU ran (stub never answers) and gated on the
  ctx phase byte (0x020101F8+0x54F4 == 8). The phase byte is a poor
  menu-open signal: the ctx-init wrapper hardcodes 0x020101F8 for every
  battle (0x080C144C -> 0x080C034C), and phase 8 in the snowball march was
  end-of-turn restore, its value merely persisting between turns. The real
  live-input gate is key-struct +7 bit 3 (0x03000007): 0x8b while the menu
  accepts input, 0x83 after idle takeover (v27c's own probe data).
- v29 v1 checked liveness at record +0xF0; unit records carry their ROM
  name pointer at +0x00 (boot_fixture_gdb validates slot1's at SLOT0+0x108).
- The idle auto-battle (~16 s) hijacked undriven menus. Fix: drive within
  ~2 s of the gate opening, and compress rounds by writing Marche's CT=10
  after each commit so his next pick arrives in ~2 s instead of ~70.

Phases (one live battle, boot -> done in well under a minute):
  A control (retail): drive round-1 (menu open at boot), then two more
    Marche rounds via the CT trick. Verdict: seed count (BP_NORM
    0x080C03C2 = sequencer ctx-init) across his retail turns. Expectation
    from v27/v28: enemy turns seed; player turns do not.
  B reverse handout: with round-3 committed, set slot6 +0xEA bit 7 (the
    pick branch sub_080CDADC at 0x0809E3AE; v27 proved bit7-set routes a
    unit through the player-turn body 0x0809E796 - the inverse question is
    whether a bit7-set PLAYER unit gets an AI turn) and CT=10. Watch for a
    seed with NO menu (his AI turn) vs a menu reopening (bit7 insufficient,
    class gate may override). Then clear bit 7, CT=10, drive the reopened
    menu -> restoration proof.

Boot first: python tools/boot_fixture_gdb.py
Run:        python tools/exp_control_v29.py
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
SLOT6 = SLOT0 + STRIDE * 6          # Marche's record
EA6 = SLOT6 + 0xEA                  # bit 7 = pick branch (sub_080CDADC)
ID6 = SLOT6 + 0x104                 # Marche class/id byte (6)
CT6 = SLOT6 + 0xD0                  # u16 CT
NAME0 = SLOT0                       # record +0x00 = ROM name ptr while live
KEYSTRUCT = 0x03000000
MODE = KEYSTRUCT + 7                # bit 3 = live player input
BP_NORM = 0x080C03C2                # sequencer ctx-init seed
OUT = "outputs/lua-nav/controlled-v29.json"
MENU_ROUTE = [(0x80, "DOWN1"), (0x80, "DOWN2"),
              (0x01, "A-wait"), (0x01, "A-confirm")]


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


class Session:
    """All state reads happen while the CPU is HALTED. budget caps the run
    so the tool timeout can never kill it before the JSON is written."""

    def __init__(self, g, pid):
        self.g = g
        self.pid = pid
        self.seeds = []          # {"t", "r4", "menu_live"}
        self.rounds = []         # {"round", "t_open", "committed", "bit7"}
        self.t0 = time.time()
        self.budget = 420.0
        self.exited = False

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

    def state(self):
        g = self.g
        mode = self.u8(MODE)
        ct6 = self.u16(CT6)
        name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
        return {"mode": mode, "input_live": bool(mode & 8), "ct6": ct6,
                "live": (name0 & 0xFF000000) == 0x08000000,
                "menu": bool(mode & 8) and ct6 == 0}

    def force_enable(self):
        g = self.g
        assert g.send("M3000005,1:01") == "OK", "enable write rejected"

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
                                       "menu_live": None, "during": tag})
        finally:
            try:
                g.send(f"z0,{KEY_BL:x},2")
            except Exception:
                pass
        time.sleep(pause)
        print(f"  key {mask:#04x} x{hits} {tag} (t={self.now()})")
        return hits

    def drive(self, tag):
        """Proven Wait route; verifies the commit by CT leaving 0."""
        self.force_enable()
        for mask, name in MENU_ROUTE:
            self.press(mask, f"{tag}:{name}")
        deadline = time.time() + 6.0
        committed = False
        while time.time() < deadline:
            self.g.interrupt()
            st = self.state()
            if st["ct6"] != 0:
                committed = True
                break
            self.g.cont()
            time.sleep(0.5)
        print(f"  drive {tag}: {'committed' if committed else 'NO COMMIT'} "
              f"t={self.now()}")
        return committed

    def listen(self, seconds):
        """Run the CPU; record BP_NORM hits tagged with the last gate state."""
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
                    st = self.state()
                    self.seeds.append({"t": self.now(), "r4": regs[4],
                                       "menu_live": st["menu"],
                                       "during": None})
                    print(f"  SEED t={self.now()} r4={regs[4]:#010x} "
                          f"menu_live={st['menu']}")
                continue

    def compress(self):
        """Marche CT=10 while halted so his next pick lands in ~2 s."""
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
    s = Session(g, pid)
    try:
        stop = g.interrupt()
        print(f"GDB attached; stop={stop}")
        st = s.state()
        if s.u8(ID6) != 6 or not st["live"]:
            print(f"fixture signature missing: id6={s.u8(ID6)} state={st}; "
                  "run tools/boot_fixture_gdb.py first")
            return 1
        print(f"baseline: {st}")
        out["baseline"] = st
        assert g.send(f"Z0,{BP_NORM:x},2") == "OK", "BP_NORM rejected"

        # ---------------- phase A: retail control ---------------------------
        rounds = []
        for rnd in (1, 2, 3):
            # wait for the menu gate (round 1 is already open at boot)
            opened = None
            t0 = time.time()
            while time.time() - t0 < 30 and not s.expired():
                s.listen(1.5)
                if s.exited:
                    break
                g.interrupt()
                st = s.state()
                if not st["live"]:
                    s.exited = True
                    break
                if st["menu"]:
                    opened = s.now()
                    break
                g.cont()
            if opened is None:
                print(f"  round {rnd}: menu never opened (exited={s.exited})")
                break
            print(f"  round {rnd}: menu open t={opened} "
                  f"(mode={st['mode']:02x})")
            rounds.append({"round": rnd, "t_open": opened, "bit7": False})
            if pid:
                window_capture(pid, f"outputs/lua-nav/v29-menu-r{rnd}.png")
            ok = s.drive(f"r{rnd}")
            if not ok:
                ok = s.drive(f"r{rnd}-retry")
            rounds[-1]["committed"] = ok
            if not ok:
                print(f"  round {rnd}: drive failed twice; stopping phase A")
                break
            if rnd < 3:
                s.compress()
        seeds_a = list(s.seeds)
        out["phase_a"] = {
            "rounds": rounds, "seeds": seeds_a,
            "battle_exited": s.exited,
            "verdict": ("no ctx-init across retail player turns"
                        if not seeds_a else
                        f"seeds observed: {seeds_a}"),
        }
        print(f"phase A verdict: {out['phase_a']['verdict']}")

        # ---------------- phase B: reverse handout --------------------------
        if not s.exited and len(rounds) >= 3 and rounds[-1]["committed"]:
            g.interrupt()
            ea = s.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea | 0x80:02x}") == "OK"
            out["phase_b"] = {"ea_before": ea, "ea_set": s.u8(EA6)}
            print(f"phase B: bit7 set on Marche "
                  f"({ea:02x} -> {out['phase_b']['ea_set']:02x})")
            s.compress()
            # his next pick should route to the AI body: a seed with no menu
            got = None
            t0 = time.time()
            while time.time() - t0 < 45 and not s.expired():
                s.listen(1.5)
                if s.exited:
                    break
                g.interrupt()
                st = s.state()
                if not st["live"]:
                    s.exited = True
                    break
                if st["menu"]:
                    print(f"  t={s.now()}: menu reopened - Marche did NOT "
                          "take an AI turn (bit7 insufficient?)")
                    if pid:
                        window_capture(pid, "outputs/lua-nav/v29-b-menu.png")
                    break
                new = [x for x in s.seeds if x not in seeds_a]
                if new:
                    got = new[0]
                    print(f"  t={s.now()}: seed with NO menu -> Marche AI "
                          f"turn (r4={got['r4']:#010x})")
                    if pid:
                        time.sleep(2.0)
                        window_capture(pid, "outputs/lua-nav/v29-b-ai.png")
                    break
                g.cont()
            out["phase_b"]["ai_turn_seed"] = got
            out["phase_b"]["verdict"] = (
                "AI turn with ctx-init (seed, no menu)" if got else
                "no AI turn (menu reopened or battle ended)")
            print(f"phase B verdict: {out['phase_b']['verdict']}")

            # restore: clear bit7, compress, drive the reopened menu
            g.interrupt()
            ea = s.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea & 0x7F:02x}") == "OK"
            out["phase_b"]["ea_restored"] = s.u8(EA6)
            print(f"phase B: bit7 cleared -> {out['phase_b']['ea_restored']:02x}")
            s.compress()
            restored = False
            t0 = time.time()
            while time.time() - t0 < 45 and not s.expired():
                s.listen(1.5)
                if s.exited:
                    break
                g.interrupt()
                st = s.state()
                if not st["live"]:
                    s.exited = True
                    break
                if st["menu"]:
                    restored = s.drive("restore")
                    break
                g.cont()
            out["phase_b"]["restoration"] = restored
            print(f"restoration: menu reopened and drove = {restored}")
        else:
            out["phase_b"] = {"skipped": True,
                              "reason": f"exited={s.exited} rounds={rounds}"}

        # ---------------- wrap up -------------------------------------------
        g.interrupt()
        st = s.state()
        out["final"] = {**st, "seeds_total": len(s.seeds),
                        "battle_exited": s.exited,
                        "budget_exceeded": s.expired()}
        g.send(f"z0,{BP_NORM:x},2")
        g.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/v29-final.png")
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
