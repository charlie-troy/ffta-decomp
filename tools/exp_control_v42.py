"""A2.3 v42: adaptive per-boot-state experiment.

Final unifying model of the session:
- fix3 resume state is a per-boot lottery: (a) field+open menu (vs-0 capture,
  enable=0, ct6=0), or (b) dark law-NOTICE card (boot-map).
- enable=0 freezes the menu: input ignored AND the 16 s idle auto-battle
  timer never runs (v38: 150 s of nothing pressless; v28 with enable=1:
  auto-battle engaged ~16 s in).
- Real keyboard A reaches the key system in both states (mode pulses); on
  the menu instance pure A does nothing visible (FFTA root menu needs the
  D-pad route to commit); on the NOTICE it should dismiss.

v42: classify at attach, write enable=1, then:
  - field instance: press NOTHING; the idle auto-battle engages <=16 s and
    plays every unit's turn (picks+seeds = the control data).
  - dark instance: real-A dismissal until the field appears, then as above.
  Passive correlation 90 s with CT compression (ct6 -> 10 when nonzero)
  cycling Marche's turns. Then the bit7 reverse probe (pbody vs ai at his
  next auto-turn). Restore. JSON.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v42.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402
from PIL import Image  # noqa: E402

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
OUT = "outputs/lua-nav/controlled-v42.json"


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


def uia_send(pid, keys):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/uia_sendkey.ps1", "-ProcId", str(pid), "-Keys", keys],
        capture_output=True, text=True, timeout=45)
    return (r.stdout or "").strip()


def classify_screen(path):
    """'dark' (law card) / 'bright' (flash) / 'field' (battle field+menu)."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None
    px = img.load()
    w, h = img.size
    dark = bright = n = 0
    for y in range(0, h, 6):
        for x in range(0, w, 6):
            r, g, b = px[x, y][:3]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            n += 1
            if lum < 60:
                dark += 1
            elif lum > 200:
                bright += 1
    if dark / n >= 0.5:
        return "dark"
    if bright / n >= 0.6:
        return "bright"
    return "field"


class Run:
    def __init__(self, g, pid):
        self.g = g
        self.pid = pid
        self.t0 = time.time()
        self.seeds = []
        self.picks = []
        self.events = []
        self.samples = []
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
        p = f"outputs/lua-nav/v42-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def live(self):
        name0 = int.from_bytes(self.g.read_mem(NAME0, 4) or b"\0\0\0\0",
                               "little")
        return (name0 & 0xFF000000) == 0x08000000

    def log_stop(self, pc, regs, during=None):
        name = BP_NAMES.get(pc)
        if name == "seed":
            self.seeds.append({"t": self.now(), "r4": regs[4],
                               "r7": regs[7], "during": during})
            print(f"  SEED t={self.now()} r4={regs[4]:08x} r7={regs[7]:08x}")
        elif name == "pick":
            rec = {"t": self.now(), "actor": regs[0], "ea6": self.u8(EA6)}
            self.picks.append(rec)
            print(f"  PICK t={rec['t']} actor={rec['actor']} "
                  f"ea6={rec['ea6']:#04x}")
        elif name:
            self.events.append({"t": self.now(), "bp": name,
                                "r0": regs[0], "r7": regs[7],
                                "during": during})
            print(f"  {name.upper()} t={self.now()} r0={regs[0]:08x}")

    def pump(self, seconds, during=None, compress=True, sample_at=()):
        g = self.g
        end = time.time() + seconds
        next_samples = list(sample_at)
        last_c = self.now()
        g.sock.settimeout(0.5)
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
            while next_samples and self.now() >= next_samples[0]:
                next_samples.pop(0)
                g.interrupt()
                if not self.live():
                    self.exited = True
                    print(f"  battle exited (t={self.now()})")
                    return
                ct6 = self.u16(CT6)
                self.samples.append({"t": self.now(), "ct6": ct6,
                                     "ea6": self.u8(EA6)})
                print(f"  [t={self.now()}] ct6={ct6} picks={len(self.picks)} "
                      f"seeds={len(self.seeds)}")
                if (compress and ct6 and ct6 != 10
                        and self.now() - last_c >= 9.0):
                    assert g.send(f"M{CT6:x},2:{10:04x}") == "OK"
                    last_c = self.now()
                    print(f"  compress ct6->10 at t={self.now()}")


def correlate(picks, seeds):
    res = []
    for i, p in enumerate(picks):
        nxt = picks[i + 1]["t"] if i + 1 < len(picks) else p["t"] + 20.0
        window = [s for s in seeds if p["t"] <= s["t"] < nxt]
        res.append({"actor": p["actor"], "t": p["t"], "ea6": p["ea6"],
                    "seeds": len(window),
                    "seed_ts": [s["t"] for s in window]})
    return res


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
        p0 = r.cap("attach")
        cls0 = classify_screen(p0) if p0 else None
        out["attach_screen"] = cls0
        out["baseline"] = {"ct6": r.u16(CT6), "ea6": r.u8(EA6)}
        natural_ea = out["baseline"]["ea6"]
        out["natural_ea"] = natural_ea
        print(f"attach screen: {cls0}, baseline: {out['baseline']}")
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        # THE unblocking write
        assert g.send("M3000005,1:01") == "OK"
        g.cont()

        # ---- adaptive: dismiss dark instances; field instances go pressless --
        deadline = time.time() + 120
        dismissed = 0
        while time.time() < deadline and not r.picks and not r.exited:
            r.pump(10.0, "idle", compress=False)
            if r.picks:
                break
            p = r.cap(f"cls{dismissed}")
            cls = classify_screen(p) if p else None
            print(f"  no picks; screen={cls} (t={r.now()})")
            if cls == "dark":
                uia_send(pid, "x")
                dismissed += 1
                time.sleep(2.0)
            elif cls == "bright":
                time.sleep(3.0)
            else:
                # field instance with no idle engagement: one gentle A,
                # then continue waiting (idle timer may need enable bit3 too)
                uia_send(pid, "x")
                dismissed += 1
                time.sleep(2.0)
        out["dismissal_presses"] = dismissed
        out["first_pick"] = r.picks[0] if r.picks else None
        print(f"first pick: {out['first_pick']}")

        # ---- passive correlation ---------------------------------------------
        if r.picks and not r.exited:
            r.pump(90.0, "correlate",
                   sample_at=(15.0, 35.0, 55.0, 75.0, 90.0))
        table = correlate(r.picks, r.seeds)
        out["correlation"] = table
        marche = [x for x in table if x["actor"] == 6]
        others = [x for x in table if x["actor"] != 6]
        out["verdict_control"] = (
            f"Marche auto-turns: {len(marche)} (with seeds: "
            f"{sum(1 for x in marche if x['seeds'])}); AI-actor turns: "
            f"{len(others)} (with seeds: "
            f"{sum(1 for x in others if x['seeds'])}) => " +
            ("retail player turns ctx-init the sequencer"
             if any(x["seeds"] for x in marche) else
             "retail player turns do NOT ctx-init" if marche else
             "no Marche auto-turn observed"))
        print(f"control: {out['verdict_control']}")

        # ---- bit7 reverse probe -----------------------------------------------
        rev = {"attempted": False}
        if r.live() and r.picks:
            g.interrupt()
            ea = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea | 0x80:02x}") == "OK"
            rev = {"attempted": True, "ea_before": ea,
                   "ea_written": r.u8(EA6), "t": r.now()}
            print(f"bit7 SET at t={r.now()} ({ea:#04x} -> "
                  f"{rev['ea_written']:#04x})")
            n_pick = len(r.picks)
            n_ev = len(r.events)
            r.pump(60.0, "bit7", sample_at=(15.0, 30.0, 45.0, 60.0))
            win_ev = r.events[n_ev:]
            win_picks = r.picks[n_pick:]
            marche_picks = [p2 for p2 in win_picks if p2["actor"] == 6]
            rev["picks_after"] = win_picks
            rev["pbody_after"] = sum(1 for e in win_ev if e["bp"] == "pbody")
            rev["ai_after"] = sum(1 for e in win_ev if e["bp"] == "ai")
            rev["marche_picks_after"] = len(marche_picks)
            rev["verdict"] = (
                "pbody hit => bit7 routes Marche's turn to the player body"
                if rev["pbody_after"] else
                "Marche pick(s) with ai-path activity => reverse handout "
                "works" if rev["marche_picks_after"] and rev["ai_after"]
                else "no Marche pick after the flip (inconclusive)")
            print(f"reverse: {rev['verdict']}")
            g.interrupt()
            ea2 = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea2 & 0x7F:02x}") == "OK"
            rev["ea_restored"] = r.u8(EA6)
        out["phase_bit7"] = rev

        # ---- wrap ----------------------------------------------------------------
        g.interrupt()
        out["final"] = {"ct6": r.u16(CT6), "ea6": r.u8(EA6),
                        "live": r.live(), "seeds_total": len(r.seeds),
                        "picks": r.picks, "events": r.events,
                        "samples": r.samples, "battle_exited": r.exited}
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            g.send(f"z0,{bp:x},2")
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
