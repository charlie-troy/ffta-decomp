"""A2.3 v37: the idle auto-battle harness — no menu driving at all.

Session synthesis:
- fix3 resumes BEFORE the law card; the card needs A (boot-map: 40 s dark,
  phase=0, no picks). v27's captures were 85% black = the law card, yet its
  BP watch worked: the pick/seed BPs are the reliable signal, screens lie.
- v28 accidentally proved the idle auto-battle plays EVERY unit's turn
  (3 seeds observed, fight ran to battle-exit) when the menu idles ~16 s.
- So: dismiss to the first pick (battle rolling), then press NOTHING. The
  idle timer auto-plays the whole fight. Correlate picks (r0=actor) with
  seeds: seeds during Marche's auto turns answer the control question
  (retail player turns ctx-init?) with zero input injection.
- Reverse handout: once the fight is rolling, write Marche +0xEA bit7=1
  while halted; his next auto turn must hit pbody (0x0809E796) if bit7
  routes player units to the player body, or ai (0x0809E2DA) if not.

Protocol:
  0. boot fix3, attach, verify signature, arm BPs, enable=1.
  1. dismiss-to-first-pick: A presses (need=3, v27-faithful) with a screen
     capture each; stop at the FIRST pick (max 30 presses / 100 s).
  2. hands-off correlation: pump 80 s, no input; log picks/seeds/pbody/ai;
     sample ct6 every ~5 s (halted). Detect battle exit (name0).
  3. bit7 reverse: after >=2 picks with the battle still live, write
     ea6|=0x80; keep pumping; record which body his next turn takes.
  4. restore natural ea; final state; JSON with correlation table+verdicts.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v37.py
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
OUT = "outputs/lua-nav/controlled-v37.json"


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
    if img.size != (480, 351):
        return f"size{img.size}"
    px = img.load()
    dark = bright = n = 0
    for y in range(40, 351, 8):
        for x in range(0, 480, 8):
            r, g, b = px[x, y][:3]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            n += 1
            if lum < 60:
                dark += 1
            elif lum > 200:
                bright += 1
    return f"dark={dark / n:.2f} bright={bright / n:.2f}"


class Run:
    def __init__(self, g, pid):
        self.g = g
        self.pid = pid
        self.t0 = time.time()
        self.seeds = []
        self.picks = []
        self.events = []
        self.ct_samples = []
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
        p = f"outputs/lua-nav/v37-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def live(self):
        name0 = int.from_bytes(
            self.g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
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

    def press(self, mask, tag, need=3, pause=1.0, max_iters=36):
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

    def pump(self, seconds, during=None, sample_every=0.0):
        g = self.g
        end = time.time() + seconds
        last_sample = 0.0
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
            if sample_every and time.time() - self.t0 - last_sample >= sample_every:
                g.interrupt()
                self.ct_samples.append({"t": self.now(), "ct6": self.u16(CT6),
                                        "live": self.live()})
                if not self.live():
                    self.exited = True
                    print(f"  battle exited (t={self.now()})")
                    return
                last_sample = time.time() - self.t0


def correlate(picks, seeds):
    res = []
    for i, p in enumerate(picks):
        nxt = picks[i + 1]["t"] if i + 1 < len(picks) else p["t"] + 15.0
        window = [s for s in seeds if p["t"] <= s["t"] < nxt]
        res.append({"actor": p["actor"], "t": p["t"],
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
        assert g.send("M3000005,1:01") == "OK"
        g.cont()

        # ---- phase 0: dismiss to the first pick ------------------------------
        t0 = time.time()
        n = 0
        first_pick_t = None
        while n < 30 and time.time() - t0 < 100:
            if r.picks:
                first_pick_t = r.picks[0]["t"]
                print(f"first pick at t={first_pick_t} "
                      f"(actor={r.picks[0]['actor']}, A presses={n})")
                break
            p = r.cap(f"d{n}")
            hits = r.press(0x01, f"dismiss#{n}")
            n += 1
            print(f"  A#{n} hits={hits} t={r.now()} "
                  f"screen={screen_brief(p) if p else '?'} "
                  f"picks={len(r.picks)}")
            if not r.live():
                r.exited = True
                break
        out["dismissal"] = {"presses": n, "first_pick": first_pick_t,
                            "battle_exited": r.exited}

        # ---- phase 1: hands-off correlation -----------------------------------
        if r.picks and not r.exited:
            # let the idle timer fire; pump with ct samples
            r.pump(80.0, "idle", sample_every=5.0)
            table = correlate(r.picks, r.seeds)
            out["correlation"] = table
            marche = [x for x in table if x["actor"] == 6]
            ai = [x for x in table if x["actor"] != 6]
            out["verdict_control"] = (
                f"Marche auto-turns: {len(marche)}, with seeds: "
                f"{sum(1 for x in marche if x['seeds'])}; AI-actor turns: "
                f"{len(ai)}, with seeds: {sum(1 for x in ai if x['seeds'])}"
                f" => " + ("player turns ctx-init the sequencer"
                           if any(x["seeds"] for x in marche) else
                           "player turns do NOT ctx-init"
                           if marche else "no Marche auto-turn observed"))
            print(f"control: {out['verdict_control']}")
        else:
            out["correlation"] = None
            out["verdict_control"] = "no picks; dismissal failed"
            print(f"control: {out['verdict_control']}")

        # ---- phase 2: bit7 reverse during the idle fight ----------------------
        rev = {"attempted": False}
        if not r.exited and r.picks:
            g.interrupt()
            ea = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea | 0x80:02x}") == "OK"
            rev = {"attempted": True, "ea_written": r.u8(EA6),
                   "t": r.now()}
            print(f"bit7 set at t={r.now()} (ea6={rev['ea_written']:#04x})")
            n_pick = len(r.picks)
            n_ev = len(r.events)
            r.pump(45.0, "bit7", sample_every=5.0)
            win = r.events[n_ev:]
            rev["picks_after"] = r.picks[n_pick:]
            rev["pbody_hits"] = sum(1 for e in win if e["bp"] == "pbody")
            rev["ai_hits"] = sum(1 for e in win if e["bp"] == "ai")
            marche_after = [p for p in r.picks[n_pick:] if p["actor"] == 6]
            rev["marche_turns_after"] = len(marche_after)
            rev["verdict"] = (
                "Marche turn hit pbody => bit7 routes player units to the "
                "player body (reverse lever NOT confirmed for AI)" if
                rev["pbody_hits"] else
                "no pbody; AI path ran for Marche's turns => reverse handout "
                "works under idle auto-battle" if rev["marche_turns_after"]
                and rev["ai_hits"] else "inconclusive (no Marche turn after)")
            print(f"reverse: {rev['verdict']}")
            # restore
            g.interrupt()
            ea = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea & 0x7F:02x}") == "OK"
            rev["ea_restored"] = r.u8(EA6)
        out["phase_bit7"] = rev

        # ---- wrap ---------------------------------------------------------------
        g.interrupt()
        out["final"] = {"ct6": r.u16(CT6), "ea6": r.u8(EA6),
                        "live": r.live(), "seeds_total": len(r.seeds),
                        "picks": r.picks, "events": r.events,
                        "ct_samples": r.ct_samples,
                        "battle_exited": r.exited}
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            g.send(f"z0,{bp:x},2")
        g.cont()
        time.sleep(0.5)
        p = r.cap("final")
        out["final_screen"] = screen_brief(p) if p else "?"
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
