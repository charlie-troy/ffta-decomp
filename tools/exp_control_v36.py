"""A2.3 v36: the a2-battle-start fixture (menu already open) + full protocol.

Session root cause: every failing experiment today booted fix3-battle-start,
whose resume state sits inside the battle-start sequence (law card, skit,
fades — boot-to-boot nondeterministic). The DOCUMENTED A2 fixture is
a2-battle-start.ss0: 'Marche Lv50 solo vs 6 monsters, menu open, WT 1/7',
'reloads deterministically' (docs/player-ai-control.md). v27's success is
consistent with that state; today's failures all fought the intro instead.

v36 protocol (on a2-battle-start):
  1. boot, attach, verify fixture signature, arm pick/pbody/ai/seed BPs,
     enable=1.
  2. screen sanity: capture; the menu-open state should be a mid-tone field
     (not dark law card / white flash). Log it; drive immediately regardless
     (v27 timing) — the route itself is the test.
  3. round 1: proven route (DOWN DOWN A A); commit = CT6 leaves 0.
  4. compressed correlation rounds (r2..r4): compress CT6=10 after each
     commit; at each Marche pick log a 2 s pre-drive seed window (control
     question: retail player turns ctx-init?) and watch enemy picks as the
     positive control. Round 3 writes Marche +0xEA bit7=1; round 4 resets
     bit7=0 (reverse-handout polarities; pbody vs ai BPs decide the path).
  5. restore natural ea, final round, JSON verdicts.

Usage: python tools/boot_fixture_gdb.py a2-battle-start.ss0 && python tools/exp_control_v36.py
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
OUT = "outputs/lua-nav/controlled-v36.json"
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
    dark = bright = tanp = green = n = 0
    for y in range(40, 351, 8):
        for x in range(0, 480, 8):
            r, g, b = px[x, y][:3]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            n += 1
            if lum < 60:
                dark += 1
            elif lum > 200:
                bright += 1
            if r > 200 and g > 180 and b > 140:
                tanp += 1
            if g > 90 and g > r + 15 and g > b + 15:
                green += 1
    return (f"dark={dark / n:.2f} bright={bright / n:.2f} "
            f"tan={tanp / n:.2f} green={green / n:.2f}")


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
        p = f"outputs/lua-nav/v36-{self.cap_i:02d}-{tag}.png"
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

    def wait_marche_pick(self, timeout_s):
        if self.picks and self.picks[-1]["actor"] == 6:
            return self.picks[-1]
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
        assert g.send("M3000005,1:01") == "OK"
        g.cont()
        time.sleep(0.8)
        p0 = r.cap("start")
        out["start_screen"] = screen_brief(p0) if p0 else "?"
        print(f"start screen: {out['start_screen']}")

        # ---- round 1: immediate drive (menu is open per fixture doc) --------
        r1 = {}
        n_seed = len(r.seeds)
        r1["committed"] = r.commit_drive("r1")
        if r1["committed"]:
            r.compress()
        out["round1"] = r1
        print(f"round1: committed={r1['committed']}")

        # ---- compressed rounds with correlation + bit7 polarities ------------
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

        # ---- verdicts ---------------------------------------------------------
        all_pre = [s for x in rounds if x.get("pre_drive_seeds")
                   for s in x["pre_drive_seeds"]]
        enemy_picks = [p for p in r.picks if p["actor"] not in (6, None)]
        out["verdict_control"] = (
            f"seeds in Marche pre-drive windows: {len(all_pre)}; enemy picks "
            f"observed: {len(enemy_picks)} => " +
            ("retail player turns ctx-init the sequencer" if all_pre else
             "retail player turns do NOT ctx-init (enemy picks = controls)")
            if r.picks else "inconclusive: no picks observed")
        print(f"control: {out['verdict_control']}")

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

        # ---- wrap ----------------------------------------------------------------
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
