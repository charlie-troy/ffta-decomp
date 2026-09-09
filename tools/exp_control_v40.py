"""A2.3 v40: A1-documented drive (dismiss law NOTICE first) + retries.

Why this should work (session evidence):
- A1 route: entering battle shows the law NOTICE dialog; ONE A dismisses it.
- Session-8 v27 (route DOWN DOWN A A with no dismissal) committed; today the
  same script left a text screen up => today's boots resume with the NOTICE
  overlay present, so press #1 (DOWN) was ignored by the overlay and the
  route drifted into a status/help screen.
- v27's battle logic stayed healthy today (3 deterministic enemy seeds,
  lone bit7 pick frames), so the drive is the only broken piece.

v40 protocol:
  1. boot, attach, verify signature, arm seed BP only (cheap), enable=1.
  2. drive attempt = [A-dismiss] + DOWN DOWN A A (v27-faithful press),
     each press logging keystruct+ct6 state; after the route, wait 6 s and
     check ct6 != 0 (commit) or name0 released (battle exit).
  3. up to 4 attempts; between attempts: one B (close submenu/help) and a
     fresh capture.
  4. on commit: compress CT6=10, watch 8 s for a seed in the pre-menu
     window of his next turn (control question), repeat up to 3 rounds.
  5. then the reverse-handout probe: set Marche ea6|=0x80, compress, watch:
     pbody (0x0809E796) vs ai (0x0809E2DA) at his next pick + seed presence.
     Restore. JSON.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v40.py
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
EA6 = SLOT0 + STRIDE * 6 + 0xEA
CT6 = SLOT0 + STRIDE * 6 + 0xD0
NAME0 = SLOT0
BP_PICK = 0x0809E260
BP_PBODY = 0x0809E796
BP_AI = 0x0809E2DA
BP_NORM = 0x080C03C2
BP_NAMES = {BP_PICK: "pick", BP_PBODY: "pbody", BP_AI: "ai", BP_NORM: "seed"}
OUT = "outputs/lua-nav/controlled-v40.json"
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


def screen_brief(path):
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return "?"
    px = img.load()
    w, h = img.size
    dark = bright = n = 0
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            r, g, b = px[x, y][:3]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            n += 1
            if lum < 60:
                dark += 1
            elif lum > 200:
                bright += 1
    return f"{w}x{h} dark={dark / n:.2f} bright={bright / n:.2f}"


class Run:
    def __init__(self, g, pid):
        self.g = g
        self.pid = pid
        self.t0 = time.time()
        self.seeds = []
        self.picks = []
        self.events = []
        self.exited = False
        self.cap_i = 0

    def now(self):
        return round(time.time() - self.t0, 1)

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
        p = f"outputs/lua-nav/v40-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def live(self):
        name0 = int.from_bytes(self.g.read_mem(NAME0, 4) or b"\0\0\0\0",
                               "little")
        return (name0 & 0xFF000000) == 0x08000000

    def state(self):
        return {"ct6": self.u16(CT6), "ea6": self.u8(EA6),
                "ks": (self.g.read_mem(0x03000000, 8) or b"?").hex()}

    def log_stop(self, pc, regs, during=None):
        name = BP_NAMES.get(pc)
        if name == "seed":
            self.seeds.append({"t": self.now(), "r4": regs[4],
                               "r7": regs[7], "during": during})
            print(f"  SEED t={self.now()} r4={regs[4]:08x} ({during})")
        elif name == "pick":
            rec = {"t": self.now(), "actor": regs[0], "ea6": self.u8(EA6)}
            self.picks.append(rec)
            print(f"  PICK t={rec['t']} actor={rec['actor']} "
                  f"ea6={rec['ea6']:#04x}")
        elif name:
            self.events.append({"t": self.now(), "bp": name,
                                "r0": regs[0], "r7": regs[7],
                                "during": during})

    def press(self, mask, tag, need=5, pause=1.2, max_iters=60):
        g = self.g
        hits = 0
        iters = 0
        try:
            if g.send(f"Z0,{KEY_BL:x},2") != "OK":
                return 0
            while hits < need and iters < max_iters:
                iters += 1
                g.cont()
                stop = g._read_packet()
                if not stop or stop[:1] not in ("S", "T"):
                    break
                regs = g.read_registers()
                if not regs:
                    break
                pc = regs[15]
                if pc == KEY_BL:
                    val = (regs[1] | mask) & 0x3FF
                    g.send("P1=" + val.to_bytes(4, "little").hex())
                    hits += 1
                else:
                    self.log_stop(pc, regs, f"press:{tag}")
        finally:
            try:
                g.send(f"z0,{KEY_BL:x},2")
                g.cont()
            except Exception:
                pass
        time.sleep(pause)
        return hits

    def pump(self, seconds, during=None):
        g = self.g
        end = time.time() + seconds
        g.sock.settimeout(0.4)
        while time.time() < end and not self.exited:
            try:
                g.cont()
                stop = g._read_packet()
            except Exception:
                continue
            if stop and stop[:1] in ("S", "T"):
                regs = g.read_registers()
                if regs:
                    self.log_stop(regs[15], regs, during)
                    if regs[15] not in BP_NAMES:
                        g.interrupt()
                        if not self.live():
                            self.exited = True
                            print(f"  battle exited (t={self.now()})")
                            return

    def commit_drive(self, tag, attempts=4):
        for attempt in range(1, attempts + 1):
            try:
                self.g.interrupt()
                assert self.g.send("M3000005,1:01") == "OK"
                self.g.cont()
            except Exception:
                pass
            time.sleep(0.3)
            keys = ([(0x02, "B-close")] if attempt > 1 else
                    [(0x01, "dismiss-NOTICE")]) + ROUTE
            for mask, name in keys:
                self.press(mask, f"{tag}#{attempt}:{name}")
            deadline = time.time() + 6.0
            while time.time() < deadline:
                self.g.interrupt()
                if not self.live():
                    self.exited = True
                    return False
                st = self.state()
                if st["ct6"] != 0:
                    print(f"  {tag}: COMMIT (attempt {attempt}, "
                          f"ct6={st['ct6']}) t={self.now()}")
                    return True
                self.g.cont()
                time.sleep(0.5)
            p = self.cap(f"{tag}-no{attempt}")
            print(f"  {tag}: attempt {attempt} no commit "
                  f"(screen={screen_brief(p) if p else '?'})")
            if self.exited:
                return False
        return False

    def compress(self):
        self.g.interrupt()
        assert self.g.send(f"M{CT6:x},2:{10:04x}") == "OK"
        self.g.cont()


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
        out["baseline"] = r.state()
        natural_ea = out["baseline"]["ea6"]
        out["natural_ea"] = natural_ea
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        g.cont()
        time.sleep(0.5)
        p = r.cap("start")
        print(f"start screen: {screen_brief(p) if p else '?'}")

        # ---- rounds: drive + compressed control windows -----------------------
        rounds = []
        for rnd in (1, 2, 3):
            if r.exited:
                break
            ok = r.commit_drive(f"r{rnd}")
            rounds.append({"round": rnd, "committed": ok})
            if not ok:
                break
            r.compress()
            n_seed = len(r.seeds)
            r.pump(8.0, f"r{rnd}-pre-menu")
            rounds[-1]["pre_menu_seeds"] = r.seeds[n_seed:]
            if r.seeds[n_seed:]:
                break
        out["rounds"] = rounds
        pre = [s for x in rounds for s in x.get("pre_menu_seeds", [])]
        out["verdict_control"] = (
            f"seeds in Marche pre-menu windows: {len(pre)} => " +
            ("retail player turns ctx-init the sequencer" if pre else
             "retail player turns do NOT ctx-init")
            if any(x.get("committed") for x in rounds) else
            "drive never committed (see rounds)")
        print(f"control: {out['verdict_control']}")

        # ---- reverse-handout probe --------------------------------------------
        rev = {"attempted": False}
        if not r.exited and any(x.get("committed") for x in rounds):
            g.interrupt()
            ea = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea | 0x80:02x}") == "OK"
            rev = {"attempted": True, "ea_before": ea,
                   "ea_written": r.u8(EA6), "t": r.now()}
            print(f"bit7 SET at t={r.now()}")
            r.compress()
            n_ev = len(r.events)
            n_pick = len(r.picks)
            r.pump(25.0, "bit7")
            win = r.events[n_ev:]
            wp = r.picks[n_pick:]
            rev["pbody_hits"] = sum(1 for e in win if e["bp"] == "pbody")
            rev["ai_hits"] = sum(1 for e in win if e["bp"] == "ai")
            rev["marche_picks"] = [p2 for p2 in wp if p2["actor"] == 6]
            rev["verdict"] = (
                "pbody hit => bit7 routes Marche to the player body"
                if rev["pbody_hits"] else
                "Marche pick with ai-path activity => reverse handout works"
                if rev["marche_picks"] and rev["ai_hits"] else
                "no Marche pick observed after flip (inconclusive)")
            print(f"reverse: {rev['verdict']}")
            g.interrupt()
            ea2 = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea2 & 0x7F:02x}") == "OK"
            rev["ea_restored"] = r.u8(EA6)
        out["phase_bit7"] = rev

        # ---- wrap ---------------------------------------------------------------
        g.interrupt()
        out["final"] = {**r.state(), "live": r.live(),
                        "seeds_total": len(r.seeds), "picks": r.picks,
                        "events": r.events, "battle_exited": r.exited}
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            g.send(f"z0,{bp:x},2")
        g.cont()
        time.sleep(0.5)
        p2 = r.cap("final")
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
