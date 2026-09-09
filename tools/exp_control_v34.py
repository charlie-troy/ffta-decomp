"""A2.3 v34: v27-faithful immediate drive + pick-anchored windows.

Evidence chain driving this design:
- v27 committed its drive ~1-2 s after attach (enable=1 write ONLY, no mode
  byte, cont-in-finally press) even with per-frame BPs armed. Every later
  variant that delayed the drive (v27c gate wait, v29-33 dismissal loops)
  failed to commit.
- v33's blind dismissal A-presses ended on a static bright panel (likely a
  status/submenu view) and no pick ever fired in 90+ s — blind pressing
  without an anchor is unsafe.
- The pick BP 0x0809E260 (r0=actor slot) is the universal 'battle running'
  signal: it fires once per unit turn regardless of overlays.

v34 protocol:
  1. arm pick/pbody/ai/seed BPs; dismiss with A presses BUT abort the
     instant any pick fires (pick anchor replaces screen classification).
  2. round 1: if Marche's pick already fired, drive immediately (v27
     timing); else wait for it. Pre-drive 2 s window counts seeds (control
     question), then the proven route; commit verified by CT6 leaving 0.
  3. compressed rounds 2-4: same window+drive each round; round 3 writes
     Marche +0xEA bit7=1, round 4 bit7=0 (reverse handout polarities).
     Verdict per round: committed => player path; ct6 hit 0 / next pick
     arrived without a commit => AI path (a seed supports this).
  4. restore natural ea, final drive if his menu reopens.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v34.py
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
CT6 = SLOT6 + 0xD0
NAME0 = SLOT0
BP_PICK = 0x0809E260        # adds r7,r0 -- r0 = actor slot, once per turn
BP_PBODY = 0x0809E796       # bit7-set player body
BP_AI = 0x0809E2DA          # bit7-clear AI path
BP_NORM = 0x080C03C2        # sequencer ctx-init seed
BP_NAMES = {BP_PICK: "pick", BP_PBODY: "pbody", BP_AI: "ai", BP_NORM: "seed"}
OUT = "outputs/lua-nav/controlled-v34.json"
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
    """Rough luminance mix for the log; not used for decisions."""
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
        self.events = []
        self.seeds = []
        self.picks = []
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
        p = f"outputs/lua-nav/v34-{self.cap_i:02d}-{tag}.png"
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
            self.events.append({"t": self.now(), "bp": name, "r0": regs[0],
                                "r7": regs[7], "during": during})

    def press(self, mask, tag, need=4, pause=1.1, max_iters=36):
        """v27-faithful press; tolerates pick/pbody/ai/seed stops."""
        g = self.g
        hits = 0
        iters = 0
        try:
            if g.send(f"Z0,{KEY_BL:x},2") != "OK":
                print(f"  FAIL: KEY_BL BP rejected ({tag})")
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

    def dismiss_until_pick(self, max_s=60.0, max_presses=14):
        """A presses advance law card/skit; the FIRST pick aborts dismissal
        (battle running => stop touching input)."""
        t0 = time.time()
        n = 0
        start_picks = len(self.picks)
        while time.time() - t0 < max_s and n < max_presses:
            if self.expired() or self.exited:
                return False
            if len(self.picks) > start_picks:
                print(f"  dismissal aborted: pick fired "
                      f"(actor={self.picks[-1]['actor']}, t={self.now()}, "
                      f"presses={n})")
                return True
            p = self.cap(f"d{n}")
            hits = self.press(0x01, f"dismiss#{n}", need=3, pause=1.0)
            n += 1
            if hits == 0:
                time.sleep(0.5)
        print(f"  dismissal ended without pick (presses={n}, "
              f"t={self.now()}, screen={screen_brief(p) if p else '?'})")
        return False

    def pump(self, seconds, during=None):
        """Run the CPU, logging BP stops, for `seconds` wall time."""
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

    def wait_for_marche_pick(self, timeout_s):
        """Wait for a pick event with r0 == 6 (or reuse the last one)."""
        if self.picks and self.picks[-1]["actor"] == 6:
            return self.picks[-1]
        g = self.g
        end = time.time() + timeout_s
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
        """Proven route until CT6 leaves 0 (commit) — v27-faithful."""
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
        g.cont()

        # ---- dismissal, pick-anchored ---------------------------------------
        r.dismiss_until_pick()
        out["dismissal"] = {"t": r.now(), "picks": list(r.picks)}

        # ---- round 1: immediate v27-faithful drive ---------------------------
        pick = r.wait_for_marche_pick(45.0)
        out["first_pick"] = pick
        r1 = {"pick": pick}
        if pick:
            n_seed = len(r.seeds)
            t_pick = pick["t"]
            r.pump(2.0, "pre-drive-r1")
            r1["pre_drive_seeds"] = [s for s in r.seeds[n_seed:]
                                     if s["t"] >= t_pick]
            r1["committed"] = r.commit_drive("r1")
            if r1["committed"]:
                r.compress()
        out["round1"] = r1
        print(f"round1: committed={r1.get('committed')} "
              f"pre_seeds={len(r1.get('pre_drive_seeds', []))}")

        # ---- rounds 2-4: compressed windows + bit7 polarities ---------------
        rounds = []
        plan = [(2, None), (3, 1), (4, 0)]
        for rnd, bit in plan:
            if r.exited or r.expired():
                break
            if bit is not None:
                g.interrupt()
                ea = r.u8(EA6)
                new = (ea | 0x80) if bit else (ea & 0x7F)
                assert g.send(f"M{EA6:x},1:{new:02x}") == "OK"
                print(f"round {rnd}: ea6 -> {r.u8(EA6):02x} (bit7={bit})")
            pick = r.wait_for_marche_pick(25.0)
            if not pick:
                rounds.append({"round": rnd, "bit7": bit, "pick": None})
                break
            n_seed = len(r.seeds)
            n_ev = len(r.events)
            t_pick = pick["t"]
            r.pump(2.0, f"pre-drive-r{rnd}")
            rec = {
                "round": rnd, "bit7": bit, "pick": pick,
                "pre_drive_seeds": [s for s in r.seeds[n_seed:]
                                    if s["t"] >= t_pick],
                "pbody_in_window": any(e["bp"] == "pbody"
                                       for e in r.events[n_ev:]),
            }
            rec["committed"] = r.commit_drive(f"r{rnd}", attempts=2)
            if rec["committed"]:
                r.compress()
            else:
                # AI-turn check: did his turn end by itself (ct6 -> 0) or did
                # the round advance (another pick) within ~10 s?
                g.interrupt()
                st = r.halt_state()
                n_pick = len(r.picks)
                r.pump(8.0, f"ai-check-r{rnd}")
                g.interrupt()
                st2 = r.halt_state()
                rec["ai_turn"] = (st["ct6"] == 0 or st2["ct6"] == 0
                                  or len(r.picks) > n_pick)
                rec["ct6_after"] = st2["ct6"]
            rounds.append(rec)
            print(f"round {rnd}: bit7={bit} committed={rec.get('committed')} "
                  f"ai_turn={rec.get('ai_turn')} "
                  f"pre_seeds={len(rec.get('pre_drive_seeds', []))}")
        out["rounds"] = rounds

        # ---- verdicts ---------------------------------------------------------
        all_pre = [s for x in ([r1] + rounds) if x.get("pre_drive_seeds")
                   for s in x["pre_drive_seeds"]]
        out["verdict_control"] = (
            "seeds in Marche pre-drive windows => retail player turns "
            "ctx-init the sequencer" if all_pre else
            "no seeds in any Marche pre-drive window => retail player turns "
            "do NOT ctx-init (enemy picks are the positive control)"
            if r.picks else "inconclusive: no picks observed")
        print(f"control verdict: {out['verdict_control']}")

        r3 = next((x for x in rounds if x.get("round") == 3), None)
        r4 = next((x for x in rounds if x.get("round") == 4), None)
        out["verdict_reverse"] = (
            "bit7=1: menu committed => bit7 alone does not hand a player "
            "unit to the AI"
            if r3 and r3.get("committed") else
            "bit7=1: turn ran without a menu (auto-ended / seed) => reverse "
            "handout works"
            if r3 and r3.get("ai_turn") else
            "bit7=0 control: menu committed => polarity test valid"
            if r4 and r4.get("committed") else
            "inconclusive (see rounds)")
        print(f"reverse verdict: {out['verdict_reverse']}")

        # ---- restore -----------------------------------------------------------
        if not r.exited and not r.expired():
            g.interrupt()
            ea = r.u8(EA6)
            target = natural_ea if natural_ea is not None else (ea & 0x7F)
            assert g.send(f"M{EA6:x},1:{target:02x}") == "OK"
            out["restored_ea"] = r.u8(EA6)
            pick = r.wait_for_marche_pick(25.0)
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
