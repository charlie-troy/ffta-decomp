"""A2.3 v31: the control question and the reverse handout, with the proven press.

v30 diagnosis (session evidence):
- v30's press() left the CPU halted through its pause (no cont in finally), so
  pressed bits accumulated but the menu app barely ran; no commit.
- v27 (the only committed run) pressed with the CPU resumed between presses,
  wrote ONLY enable (+5)=1 (no mode-byte 0x8b), and drove ~1 s after attach,
  when the boot skit had not yet covered the menu.
- Screen classification (session 09-09): dialog frames score max-tan-block
  70-75; field frames ~17-20. Today's captures all score 70-75 => a dialog
  box covers the screen on this boot; it must be dismissed before driving.

Plan (one boot, ~5 min wall budget):
  1. attach immediately (boot_fixture_gdb first), verify slot1 name ptr.
  2. dialog-dismiss loop: A presses with the CPU RUNNING between presses,
     ending each window with a window capture; stop when the screen score
     drops below 40 (field visible) or 60 s pass.
  3. control phase A: drive Marche's menu (proven DOWN DOWN A A, cont in
     finally); on commit (CT6 leaves 0) compress CT=10; listen for seeds in
     the pre-menu window of his next turn. Seeds before any menu => retail
     player turns ctx-init the AI sequencer.
  4. reverse handout phase B: set Marche +0xEA bit 7, compress, listen:
     seed with no menu => his turn routed to the AI body.
  5. restore: clear bit 7, drive the reopened menu, confirm commit.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v31.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402
from PIL import Image  # noqa: E402

KEY_BL = 0x08000494
SLOT0 = 0x020159E8
STRIDE = 0x108
SLOT6 = SLOT0 + STRIDE * 6
EA6 = SLOT6 + 0xEA
ID6 = SLOT6 + 0x104
CT6 = SLOT6 + 0xD0
NAME0 = SLOT0                     # record +0x00 = ROM name ptr while live
BP_NORM = 0x080C03C2              # normal ctx-init seed (every unit turn)
OUT = "outputs/lua-nav/controlled-v31.json"
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


def screen_score(path):
    """Max contiguous tan-block score: dialogs 70-75, field 17-20 (session
    calibration). Returns None if the capture failed."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None
    if img.size != (480, 351):
        return None
    px = img.load()
    w, h = 480, 351

    def tan(x, y):
        r, g, b = px[x, y][:3]
        return (r > 200 and g > 180 and b > 140
                and not (abs(r - g) < 8 and abs(g - b) < 8 and r > 245))

    best = 0
    for cy in range(40, h - 8, 8):
        for cx in range(0, w - 8, 8):
            cnt = 0
            for yy in range(cy, min(cy + 32, h), 4):
                for xx in range(cx, min(cx + 64, w), 4):
                    if tan(xx, yy):
                        cnt += 1
            best = max(best, cnt)
    return best


class Run:
    def __init__(self, g, pid):
        self.g = g
        self.pid = pid
        self.t0 = time.time()
        self.seeds = []
        self.exited = False
        self.budget = 260.0
        self.cap_i = 0

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

    def cap(self, tag):
        if not self.pid:
            return None
        self.cap_i += 1
        p = f"outputs/lua-nav/v31-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def halt_state(self):
        g = self.g
        name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
        return {"ct6": self.u16(CT6), "ea6": self.u8(EA6),
                "live": (name0 & 0xFF000000) == 0x08000000}

    def press(self, mask, tag, frames=5, pause=1.2):
        """v27-faithful: arm, patch r1 per frame, disarm, RESUME, sleep."""
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
                    print(f"  seed during press {tag}")
        finally:
            try:
                g.send(f"z0,{KEY_BL:x},2")
                g.cont()
            except Exception:
                pass
        time.sleep(pause)
        print(f"  key {mask:#04x} x{hits} {tag} (t={self.now()})")
        return hits

    def dismiss_dialogs(self, max_s=60.0):
        """A on a running-CPU cadence until the screen leaves dialog-score."""
        t0 = time.time()
        n = 0
        while time.time() - t0 < max_s and not self.expired():
            self.press(0x01, f"dismiss#{n}", pause=1.5)
            n += 1
            if self.exited:
                return False
            self.g.interrupt()
            st = self.halt_state()
            if not st["live"]:
                self.exited = True
                return False
            p = self.cap(f"dismiss{n}")
            score = screen_score(p) if p else None
            print(f"  screen score {score}")
            self.g.cont()
            if score is not None and score < 40:
                print(f"  field visible after {n} dismissals "
                      f"(t={self.now()})")
                return True
        print("  dismissal window exhausted; proceeding anyway")
        return False

    def listen(self, seconds, tag):
        g = self.g
        end = time.time() + seconds
        g.sock.settimeout(0.4)
        while time.time() < end and not self.expired():
            try:
                g.cont()
                stop = g._read_packet()
            except Exception:
                continue
            if stop and stop[:1] in ("S", "T"):
                regs = g.read_registers()
                if regs and regs[15] == BP_NORM:
                    self.seeds.append({"t": self.now(), "r4": regs[4],
                                       "during": tag})
                    print(f"  SEED t={self.now()} r4={regs[4]:08x} ({tag})")

    def compress(self):
        self.g.interrupt()
        assert self.g.send(f"M{CT6:x},2:{10:04x}") == "OK"
        self.g.cont()

    def commit_drive(self, tag, attempts=3):
        """Drive the proven route; commit verified by CT6 leaving 0."""
        for attempt in (1, 2, 3)[:attempts]:
            try:
                self.g.interrupt()
                assert self.g.send("M3000005,1:01") == "OK"
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


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    out = {}
    r = Run(g, pid)
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
        if (name0 & 0xFF000000) != 0x08000000:
            print(f"fixture signature missing: name0={name0:08x}")
            return 1
        assert g.send(f"Z0,{BP_NORM:x},2") == "OK", "BP_NORM rejected"
        out["baseline"] = r.halt_state()
        g.cont()

        # ---- dismiss the boot dialog(s) by screen classification ----------
        got_field = r.dismiss_dialogs()
        out["dismissal"] = {"ok": got_field, "t": r.now()}
        if not got_field and not r.expired():
            p = r.cap("no-field")
            print(f"  capture for inspection: {p}")

        # ---- phase A: control question -------------------------------------
        committed = False
        rounds = []
        for rnd in (1, 2, 3):
            if r.exited or r.expired():
                break
            ok = r.commit_drive(f"r{rnd}")
            rounds.append({"round": rnd, "committed": ok})
            if not ok:
                r.cap(f"nocommit-r{rnd}")
                break
            committed = True
            r.compress()
            n_before = len(r.seeds)
            r.listen(8.0, f"r{rnd}->pre-menu")
            rounds[-1]["pre_menu_seeds"] = r.seeds[n_before:]
            if r.seeds[n_before:]:
                break   # question answered
        out["phase_a"] = {
            "rounds": rounds,
            "seeds": r.seeds,
            "battle_exited": r.exited,
            "verdict": ("no ctx-init in any pre-menu window => retail player "
                        "turns do not ctx-init the sequencer"
                        if not r.seeds else
                        f"seeds in pre-menu window => player turns ctx-init: "
                        f"{r.seeds}"),
        }
        print(f"phase A verdict: {out['phase_a']['verdict']}")

        # ---- phase B: reverse handout --------------------------------------
        if not r.exited and committed:
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
            while time.time() - t0 < 40 and not r.expired():
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
                    r.cap("b-ai-turn")
                    print(f"  t={r.now()}: seed with no menu => Marche AI turn")
                    break
                # probe: a DOWN that commits means a menu is open (not AI)
                r.press(0x80, "B-probe", frames=3, pause=0.4)
                g.interrupt()
                if r.halt_state()["ct6"] != 0:
                    reopened = True
                    r.cap("b-menu-reopened")
                    print(f"  t={r.now()}: DOWN committed => menu reopened; "
                          "bit7 alone insufficient")
                    break
                g.cont()
            out["phase_b"]["ai_turn_seed"] = got
            out["phase_b"]["menu_reopened"] = reopened
            out["phase_b"]["verdict"] = (
                "AI turn with ctx-init (seed, no menu) => reverse handout works"
                if got else
                "menu reopened: bit7 insufficient for a player unit"
                if reopened else "no outcome (battle ended / timeout)")
            print(f"phase B verdict: {out['phase_b']['verdict']}")

            # ---- restoration -------------------------------------------------
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

        # ---- wrap ------------------------------------------------------------
        g.interrupt()
        out["final"] = {**r.halt_state(), "seeds_total": len(r.seeds),
                        "battle_exited": r.exited,
                        "budget_exceeded": r.expired()}
        g.send(f"z0,{BP_NORM:x},2")
        g.cont()
        time.sleep(0.5)
        r.cap("final")
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
