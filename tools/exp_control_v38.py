"""A2.3 v38: zero-input observation + mid-fight bit7 flip.

Session evidence:
- fix3's resume state is nondeterministic (law card / menu cursor position /
  help screens); ANY injected press before the first pick risks derailing
  the intro (v33-37). The idle auto-battle plays the whole fight with no
  input (v28).
- Seeds at t=4.6/14.0/23.8 fired identically across two independent v27
  runs while Marche's menu was OPEN (ct6=0, no Controlled marks) — strong
  hint that the sequencer ctx-inits during retail player turns. The pick BP
  (0x0809E260, r0=actor) + seed correlation will settle it per-actor.
- Reverse handout: set Marche +0xEA bit7=1 while the fight cycles; his next
  auto-turn must hit pbody (0x0809E796) or ai (0x0809E2DA).

v38 protocol (NO key presses at all):
  1. boot, attach, verify signature, arm pick/pbody/ai/seed BPs, release.
     No enable write (the idle path may need the retail key state).
  2. passive pump 150 s: log every pick/seed/body event. Minimal interrupts
     (CT samples at ~40/80/120 s only). The idle timer should auto-commit
     Marche ~16 s in and the fight self-plays.
  3. at t=60 (if live): write ea6 |= 0x80; keep pumping; his next pick
     reveals the path (pbody vs ai) and whether a seed still fires.
  4. restore ea6; correlation table + verdicts + JSON.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v38.py
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
OUT = "outputs/lua-nav/controlled-v38.json"


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
        p = f"outputs/lua-nav/v38-{self.cap_i:02d}-{tag}.png"
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
        """Run; log BP events; interrupt only at the sample_at times."""
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
                self.samples.append({"t": self.now(),
                                     "ct6": self.u16(CT6),
                                     "ea6": self.u8(EA6)})
                print(f"  [t={self.now()}] ct6={self.samples[-1]['ct6']} "
                      f"ea6={self.samples[-1]['ea6']:#04x}")


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
        out["baseline"] = {"ct6": r.u16(CT6), "ea6": r.u8(EA6)}
        natural_ea = out["baseline"]["ea6"]
        out["natural_ea"] = natural_ea
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        g.cont()
        print("released; passive observation (NO input)...")

        # ---- phase 1: passive idle-fight observation -------------------------
        r.pump(60.0, "passive", sample_at=(20.0, 40.0))
        out["phase1_picks"] = len(r.picks)
        out["phase1_seeds"] = len(r.seeds)
        p = r.cap("p60")
        print(f"t=60: picks={len(r.picks)} seeds={len(r.seeds)} "
              f"live={r.live()}")

        # ---- phase 2: bit7 flip mid-fight --------------------------------------
        rev = {"attempted": False}
        if r.live():
            g.interrupt()
            ea = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea | 0x80:02x}") == "OK"
            rev = {"attempted": True, "ea_before": ea,
                   "ea_written": r.u8(EA6), "t": r.now()}
            print(f"bit7 SET at t={r.now()} ({ea:#04x} -> "
                  f"{rev['ea_written']:#04x})")
            n_pick = len(r.picks)
            n_ev = len(r.events)
            n_seed = len(r.seeds)
            r.pump(90.0, "bit7", sample_at=(90.0,))
            win_ev = r.events[n_ev:]
            win_picks = r.picks[n_pick:]
            win_seeds = r.seeds[n_seed:]
            marche_picks = [p2 for p2 in win_picks if p2["actor"] == 6]
            # seed attribution for marche picks after the flip
            corr_after = correlate(win_picks, win_seeds)
            rev["picks_after"] = win_picks
            rev["seeds_after"] = len(win_seeds)
            rev["pbody_after"] = sum(1 for e in win_ev if e["bp"] == "pbody")
            rev["ai_after"] = sum(1 for e in win_ev if e["bp"] == "ai")
            rev["marche_picks_after"] = len(marche_picks)
            rev["correlation_after"] = corr_after
            rev["verdict"] = (
                "pbody hit after flip => bit7 routes Marche's turn to the "
                "player body (no reverse handout)" if rev["pbody_after"]
                else "Marche pick(s) with no pbody and ai-path activity => "
                "reverse handout (Marche -> AI turn) works" if
                rev["marche_picks_after"] and rev["ai_after"] else
                "no Marche pick after the flip (inconclusive)")
            print(f"reverse verdict: {rev['verdict']}")
            g.interrupt()
            ea2 = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea2 & 0x7F:02x}") == "OK"
            rev["ea_restored"] = r.u8(EA6)
        out["phase_bit7"] = rev

        # ---- wrap -----------------------------------------------------------------
        table = correlate(r.picks, r.seeds)
        out["correlation"] = table
        marche = [x for x in table if x["actor"] == 6]
        others = [x for x in table if x["actor"] != 6]
        natural = [x for x in marche if x["ea6"] is not None
                   and x["ea6"] < 0x80]
        out["verdict_control"] = (
            f"Marche picks: {len(marche)} (natural-bit7: {len(natural)}), "
            f"with seeds: {sum(1 for x in marche if x['seeds'])}; "
            f"AI-actor picks: {len(others)}, with seeds: "
            f"{sum(1 for x in others if x['seeds'])} => " +
            ("retail player turns ctx-init the sequencer"
             if any(x["seeds"] for x in natural) else
             "retail player turns do NOT ctx-init" if natural else
             "no natural Marche pick observed"))
        print(f"control verdict: {out['verdict_control']}")
        g.interrupt()
        out["final"] = {"ct6": r.u16(CT6), "ea6": r.u8(EA6),
                        "live": r.live(), "seeds_total": len(r.seeds),
                        "picks": r.picks, "events": r.events,
                        "samples": r.samples, "battle_exited": r.exited}
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
