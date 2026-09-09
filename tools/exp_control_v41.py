"""A2.3 v41: real-key dismissal + idle auto-battle + passive GDB observation.

Everything the session established, combined:
- fix3 resumes with the law NOTICE overlay up (nondeterministically); the
  overlay blocks the battle and clears the key-system enable byte each frame
  (boot-map). It needs ONE A press.
- A/B/START respond from every input source (docs); only D-pad is broken.
  UIA SendKeys reaches the window as a real keyboard. Sending A with the
  GDB stub DETACHED avoids any stub-interference questions entirely.
- Once the menu is open with no input, the ~16 s idle timer hands Marche's
  turn to auto-battle (v28: fight self-plays to completion).
- With the fight rolling, GDB attach is safe for OBSERVATION: pick BP
  (0x0809E260, r0=actor), seed BP (0x080C03C2), pbody/ai path BPs.
  CT compression (write CT6=10) cycles rounds faster. Zero presses needed.

v41 protocol:
  1. boot_fixture_gdb (kill, boot fix3, early halt, verify, release).
  2. UIA real-key 'x' (= GBA A) pairs to the main window, up to 3 pairs,
     8 s apart (NOTICE dismiss + possible confirm).
  3. attach GDB; arm pick BP; pump 25 s. Picks present => battle rolling.
     (If none: one more UIA pair and repeat, max 2 extra rounds.)
  4. full arm (pbody/ai/seed); passive correlate 60 s. Compress CT6=10
     whenever ct6 != 0 and >8 s since the last compress (rounds cycle).
     Marche auto-turns with seeds => control question answered.
  5. bit7 flip (ea6 |= 0x80): his next auto-turn hits pbody (player body)
     or ai (reverse-handout answer). Restore. JSON.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v41.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

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
OUT = "outputs/lua-nav/controlled-v41.json"


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def send_real_key(pid, keys="{x}", pause_ms=120):
    """Real keyboard 'x' (mGBA default A) to the mGBA main window."""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/uia_sendkey.ps1", "-ProcId", str(pid), "-Keys", keys],
        capture_output=True, text=True, timeout=45)
    out = (r.stdout or "").strip()
    time.sleep(pause_ms / 1000.0)
    return out


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

    def now(self):
        return round(time.time() - self.t0, 1)

    def u8(self, a):
        d = self.g.read_mem(a, 1)
        return d[0] if d else None

    def u16(self, a):
        d = self.g.read_mem(a, 2)
        return int.from_bytes(d, "little") if d else None

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

    def pump(self, seconds, during=None, compress=True,
             sample_at=(), last_compress=None):
        g = self.g
        end = time.time() + seconds
        next_samples = list(sample_at)
        last_c = last_compress if last_compress is not None else self.now()
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
                # round-cycling: compress when his turn is not pending
                if (compress and ct6 and ct6 != 10
                        and self.now() - last_c >= 8.0):
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
    out = {"pid": pid}

    # ---- phase A: real-key dismissal (stub detached) -------------------------
    for pair in range(3):
        r1 = send_real_key(pid)
        time.sleep(1.2)
        r2 = send_real_key(pid)
        print(f"UIA pair {pair + 1}: {r1!r} / {r2!r}")
        time.sleep(6.0)
    out["uia_pairs"] = 3

    # ---- phase B: attach, confirm the battle is rolling -----------------------
    g = Gdb("127.0.0.1", 2345, timeout=10)
    r = Run(g, pid)
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
        live = (name0 & 0xFF000000) == 0x08000000
        out["baseline"] = {"ct6": r.u16(CT6), "ea6": r.u8(EA6), "live": live}
        natural_ea = out["baseline"]["ea6"]
        out["natural_ea"] = natural_ea
        print(f"baseline: {out['baseline']}")
        if not live:
            print("battle not live after dismissal")
        assert g.send(f"Z0,{BP_PICK:x},2") == "OK"
        g.cont()
        r.pump(25.0, "confirm", compress=False)
        out["confirm_picks"] = len(r.picks)
        print(f"confirm: picks={len(r.picks)} seeds? (seed BP not armed yet)")

        # ---- phase C: full observation + correlation ----------------------------
        if r.picks:
            assert g.send(f"Z0,{BP_NORM:x},2") == "OK"
            assert g.send(f"Z0,{BP_PBODY:x},2") == "OK"
            assert g.send(f"Z0,{BP_AI:x},2") == "OK"
            r.pump(70.0, "correlate",
                   sample_at=(10.0, 25.0, 40.0, 55.0, 70.0))
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
             "no Marche auto-turn observed (dismissal/confirm failed)"))
        print(f"control: {out['verdict_control']}")

        # ---- phase D: bit7 reverse probe ------------------------------------------
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
            r.pump(50.0, "bit7", sample_at=(15.0, 30.0, 45.0))
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

        # ---- wrap ------------------------------------------------------------------
        g.interrupt()
        out["final"] = {"ct6": r.u16(CT6), "ea6": r.u8(EA6),
                        "live": r.live(), "seeds_total": len(r.seeds),
                        "picks": r.picks, "events": r.events,
                        "samples": r.samples, "battle_exited": r.exited}
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            g.send(f"z0,{bp:x},2")
        g.cont()
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
