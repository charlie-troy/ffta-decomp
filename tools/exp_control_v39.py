"""A2.3 v39: the enable=1 idle-fight experiment (NO key presses).

Cross-session evidence:
- v28 (enable=1 written, zero presses): idle auto-battle engaged ~16 s in,
  fight self-played, 3 seeds logged, battle ran to exit.
- v38 (no writes at all): 150 s of nothing — the game waits forever with
  enable=0 and no input.
- Hypothesis: enable=1 (M3000005=1) alone arms the menu idle timer, which
  hands Marche's turn to auto-battle; the fight then plays itself.

v39 protocol (ONE memory write, ZERO presses):
  1. boot, attach, verify signature, arm pick/pbody/ai/seed BPs.
  2. write enable=1; release; passive pump 100 s with CT samples.
     Expect: idle auto-commit ~16 s, then picks+seeds per unit turn.
  3. correlation: per pick (r0=actor), seeds in [pick, next pick).
     Marche's auto-turns with seeds => retail player turns ctx-init.
  4. bit7 flip on Marche mid-fight (if live): his next auto-turn must hit
     pbody (player body) or ai — the reverse-handout answer.
  5. restore, final JSON.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v39.py
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
OUT = "outputs/lua-nav/controlled-v39.json"


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
        p = f"outputs/lua-nav/v39-{self.cap_i:02d}-{tag}.png"
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
            print(f"  SEED t={self.now()} r4={regs[4]:08x} r7={regs[7]:08x}"
                  + (f" ({during})" if during else ""))
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

    def pump(self, seconds, during=None, sample_at=()):
        g = self.g
        end = time.time() + seconds
        next_samples = list(sample_at)
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
                st = next_samples.pop(0)
                g.interrupt()
                if not self.live():
                    self.exited = True
                    print(f"  battle exited (t={self.now()})")
                    return
                self.samples.append({"t": self.now(), "ct6": self.u16(CT6),
                                     "ea6": self.u8(EA6),
                                     "ks": (self.g.read_mem(0x03000000, 8)
                                            or b"?").hex()})
                print(f"  [t={self.now()}] ct6={self.samples[-1]['ct6']} "
                      f"ea6={self.samples[-1]['ea6']:#04x} "
                      f"ks={self.samples[-1]['ks']}")


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
        out["baseline"] = {"ct6": r.u16(CT6), "ea6": r.u8(EA6),
                           "ks": (g.read_mem(0x03000000, 8) or b"?").hex()}
        natural_ea = out["baseline"]["ea6"]
        out["natural_ea"] = natural_ea
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        # THE experiment: enable=1, nothing else
        assert g.send("M3000005,1:01") == "OK"
        out["enable_written"] = True
        g.cont()
        print("enable=1 written; passive observation (NO presses)...")

        # ---- phase 1: idle fight (enable-only) --------------------------------
        r.pump(100.0, "enable-idle", sample_at=(8.0, 16.0, 24.0, 32.0, 48.0,
                                                64.0, 80.0))
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
             "no auto-turn engaged (enable-only hypothesis fails)"))
        print(f"control: {out['verdict_control']}")

        # ---- phase 2: bit7 flip mid-fight ---------------------------------------
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
            r.pump(80.0, "bit7", sample_at=(16.0, 32.0, 48.0, 64.0))
            win_ev = r.events[n_ev:]
            win_picks = r.picks[n_pick:]
            marche_picks = [p2 for p2 in win_picks if p2["actor"] == 6]
            rev["picks_after"] = win_picks
            rev["pbody_after"] = sum(1 for e in win_ev if e["bp"] == "pbody")
            rev["ai_after"] = sum(1 for e in win_ev if e["bp"] == "ai")
            rev["marche_picks_after"] = len(marche_picks)
            rev["verdict"] = (
                "pbody hit after flip => bit7 routes Marche's turn to the "
                "player body (no reverse handout)" if rev["pbody_after"]
                else "Marche pick(s) with no pbody + ai-path activity => "
                "reverse handout works" if
                rev["marche_picks_after"] and rev["ai_after"] else
                "no Marche pick after the flip (inconclusive)")
            print(f"reverse: {rev['verdict']}")
            g.interrupt()
            ea2 = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea2 & 0x7F:02x}") == "OK"
            rev["ea_restored"] = r.u8(EA6)
        out["phase_bit7"] = rev

        # ---- wrap ------------------------------------------------------------------
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
