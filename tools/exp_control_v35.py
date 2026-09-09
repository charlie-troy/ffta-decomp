"""A2.3 v35: pick/seed correlation (no drive needed) + guarded intro + drive.

Evidence accumulated this session:
- Boot-to-boot intro nondeterminism: some boots open straight onto Marche's
  menu (v27), others sit on a law card / dark intro (boot-map: 40 s of
  phase=0, ct6=0, no picks despite 24 registered A presses). Blind pressing
  cannot be trusted; the pick BP 0x0809E260 is the only 'battle running'
  signal.
- v28's idle auto-battle run showed seeds firing during a battle that played
  itself; seed times exist but were never correlated with per-actor picks.

v35 answers A2.3 with minimal input:
  1. attach, enable=1, arm pick/pbody/ai/seed BPs, press NOTHING.
  2. guarded intro escalation: if no pick for 15 s, press ONE A (max 4),
     logging the screen each time. The first pick = battle running.
  3. passive correlation round: pump at full speed logging every pick
     (r0 = actor) and every seed. For each pick, was there a seed in
     [pick_t, next_pick_t)? Seeds for AI actors are the positive control;
     a seed for a Marche (actor 6) pick answers the control question
     (retail player turns ctx-init the sequencer) WITHOUT driving.
  4. drive phase (if a Marche pick opens a menu): 2 s pre-drive window,
     then the v27-faithful route; commit = CT6 leaves 0; compress CT6=10
     to cycle rounds quickly.
  5. reverse handout: before one compressed Marche pick write bit7=1;
     observe pbody (player body) vs ai (AI path) vs seeds; try to commit.
     Then bit7=0 as control. Restore natural ea.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v35.py
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
OUT = "outputs/lua-nav/controlled-v35.json"
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
    if img.size != (480, 351):
        return "?"
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
        self.exited = False
        self.budget = 320.0
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
        p = f"outputs/lua-nav/v35-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def halt_state(self):
        g = self.g
        name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
        return {"ct6": self.u16(CT6), "ea6": self.u8(EA6),
                "live": (name0 & 0xFF000000) == 0x08000000}

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

    def press(self, mask, tag, need=4, pause=1.1, max_iters=36):
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
        while time.time() < end and not self.expired():
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
                        st = self.halt_state()
                        if not st["live"]:
                            self.exited = True
                            return

    def wait_first_pick(self, max_s=75.0, a_every=15.0, max_a=4):
        """Press nothing; one A per a_every seconds without a pick."""
        t0 = time.time()
        n_a = 0
        last_a = 0.0
        p = None
        while time.time() - t0 < max_s and not self.expired():
            if self.picks:
                print(f"  first pick t={self.picks[0]['t']} "
                      f"actor={self.picks[0]['actor']} (A presses={n_a})")
                return True
            if n_a < max_a and time.time() - t0 - last_a >= a_every:
                p = self.cap(f"intro{n_a}")
                print(f"  no pick yet (t={self.now():.0f}, "
                      f"screen={screen_brief(p) if p else '?'}); one A")
                self.press(0x01, f"intro-A#{n_a}", need=3, pause=1.0)
                n_a += 1
                last_a = time.time() - t0
            self.pump(0.5, "intro-wait")
        p = self.cap("no-pick")
        print(f"  no pick in {max_s:.0f}s "
              f"(screen={screen_brief(p) if p else '?'}, A presses={n_a})")
        return False

    def commit_drive(self, tag, attempts=3):
        for attempt in range(1, attempts + 1):
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
            self.cap(f"{tag}-no{attempt}")
            if self.exited:
                return False
        return False

    def compress(self):
        self.g.interrupt()
        assert self.g.send(f"M{CT6:x},2:{10:04x}") == "OK"
        self.g.cont()

    def wait_marche_pick(self, timeout_s):
        end = time.time() + timeout_s
        g = self.g
        g.sock.settimeout(0.4)
        while time.time() < end and not self.expired():
            try:
                g.cont()
                stop = g._read_packet()
            except Exception:
                continue
            if stop and stop[:1] in ("S", "T"):
                regs = g.read_registers()
                if regs:
                    pc = regs[15]
                    self.log_stop(pc, regs, "watch")
                    if pc == BP_PICK and regs[0] == 6:
                        return self.picks[-1]
                    if pc not in BP_NAMES:
                        g.interrupt()
                        if not self.halt_state()["live"]:
                            self.exited = True
                            return None
        return None


def correlate(picks, seeds):
    """For each pick: seeds in [pick.t, next pick.t)."""
    res = []
    for i, p in enumerate(picks):
        nxt = picks[i + 1]["t"] if i + 1 < len(picks) else p["t"] + 12.0
        window = [s for s in seeds if p["t"] <= s["t"] < nxt]
        res.append({"pick": p, "seeds": len(window),
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
        out["baseline"] = r.halt_state()
        natural_ea = r.u8(EA6)
        out["natural_ea"] = natural_ea
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        try:
            assert g.send("M3000005,1:01") == "OK"
        except AssertionError:
            print("enable write rejected (non-fatal)")
        g.cont()

        # ---- intro: guarded, pick-anchored ----------------------------------
        got = r.wait_first_pick()
        out["intro"] = {"first_pick": r.picks[0] if r.picks else None,
                        "a_presses": None}

        # ---- passive correlation round --------------------------------------
        if got:
            n_seed = len(r.seeds)
            n_pick = len(r.picks)
            r.pump(35.0, "correlate")
            table = correlate(r.picks[n_pick:], r.seeds)
            out["correlation"] = table
            marche_windows = [x for x in table if x["pick"]["actor"] == 6]
            ai_windows = [x for x in table if x["pick"]["actor"] != 6]
            out["verdict_control"] = (
                f"Marche picks with seeds: {sum(1 for x in marche_windows if x['seeds'])}"
                f"/{len(marche_windows)}; AI-actor picks with seeds: "
                f"{sum(1 for x in ai_windows if x['seeds'])}/{len(ai_windows)}"
                if table else "no picks during correlation window")
            print(f"control: {out['verdict_control']}")

        # ---- drive rounds -----------------------------------------------------
        rounds = []
        plan = [("r2", None), ("r3", 1), ("r4", 0)]
        for tag, bit in plan:
            if r.exited or r.expired():
                break
            if bit is not None:
                g.interrupt()
                ea = r.u8(EA6)
                new = (ea | 0x80) if bit else (ea & 0x7F)
                assert g.send(f"M{EA6:x},1:{new:02x}") == "OK"
                print(f"{tag}: ea6 -> {r.u8(EA6):02x} (bit7={bit})")
            pick = r.wait_marche_pick(30.0)
            if not pick:
                rounds.append({"tag": tag, "bit7": bit, "pick": None})
                break
            n_seed = len(r.seeds)
            n_ev = len(r.events)
            t_pick = pick["t"]
            r.pump(2.0, f"pre-drive-{tag}")
            rec = {"tag": tag, "bit7": bit, "pick": pick,
                   "pre_drive_seeds": [s for s in r.seeds[n_seed:]
                                       if s["t"] >= t_pick],
                   "pbody_in_window": any(e["bp"] == "pbody"
                                          for e in r.events[n_ev:])}
            rec["committed"] = r.commit_drive(tag, attempts=2)
            if rec["committed"]:
                r.compress()
            else:
                g.interrupt()
                st = r.halt_state()
                n_pick = len(r.picks)
                r.pump(8.0, f"ai-check-{tag}")
                g.interrupt()
                st2 = r.halt_state()
                rec["ai_turn"] = (st["ct6"] == 0 or st2["ct6"] == 0
                                  or len(r.picks) > n_pick)
                rec["ct6_after"] = st2["ct6"]
            rounds.append(rec)
            print(f"{tag}: bit7={bit} committed={rec.get('committed')} "
                  f"ai_turn={rec.get('ai_turn')} "
                  f"pre_seeds={len(rec.get('pre_drive_seeds', []))} "
                  f"pbody={rec.get('pbody_in_window')}")
        out["rounds"] = rounds

        r3 = next((x for x in rounds if x.get("tag") == "r3"), None)
        r4 = next((x for x in rounds if x.get("tag") == "r4"), None)
        out["verdict_reverse"] = (
            "bit7=1: menu committed => bit7 alone does not hand a player "
            "unit to the AI"
            if r3 and r3.get("committed") else
            "bit7=1: turn ran without a committable menu (auto/seed) => "
            "reverse handout works"
            if r3 and r3.get("ai_turn") else
            "bit7=0 control committed => polarity test valid, bit7=1 "
            "inconclusive"
            if r4 and r4.get("committed") else
            "inconclusive (see rounds)")
        print(f"reverse: {out['verdict_reverse']}")

        # ---- restore -----------------------------------------------------------
        if not r.exited and not r.expired():
            g.interrupt()
            ea = r.u8(EA6)
            target = natural_ea if natural_ea is not None else (ea & 0x7F)
            assert g.send(f"M{EA6:x},1:{target:02x}") == "OK"
            out["restored_ea"] = r.u8(EA6)
            pick = r.wait_marche_pick(25.0)
            if pick:
                out["restoration_committed"] = r.commit_drive("restore",
                                                              attempts=2)

        # ---- wrap -----------------------------------------------------------------
        g.interrupt()
        out["final"] = {**r.halt_state(), "seeds_total": len(r.seeds),
                        "picks": r.picks,
                        "battle_exited": r.exited,
                        "budget_exceeded": r.expired()}
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
