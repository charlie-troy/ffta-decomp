"""A2.3 v32: pick-driven experiment — no timing guesswork.

v31 diagnosis: the dismissal A-press landed during the battle-start fade
(dark screen scores ~21, same as the field), so the skit survived and every
drive pressed into it; the 16 s idle timer then auto-battled and the battle
ended. Screens: dialog tan>=40, fade dark>=50%, field green.

v32 anchors on the pick instead of the clock:
- BP_TAIL 0x0809E398 (pick tail, hit for every pick scan), BP_PBODY
  0x0809E796 (bit7-set player body), BP_AI 0x0809E2DA (AI path), BP_NORM
  0x080C03C2 (sequencer ctx-init seed).
- At every TAIL hit: log r0/r7 and the +0xEA of slot0 and slot6 (Marche).
  This answers the open question: what is Marche's bit7 AT THE PICK?
- Phase A: wait for a TAIL hit while Marche is the actor (r0/r7 == 6),
  dismiss any dialog by screen class, drive the proven route immediately.
  On commit compress CT=10; his next pick arrives ~2 s later; log seeds in
  every pick->commit window (the control question: retail player turns and
  the ctx-init).
- Phase B (reverse handout), one polarity per compressed round:
  round 3: write Marche +0xEA bit7 = 0 (clear) before his pick;
  round 4: write bit7 = 1 (set). Observe per round: PBODY hit (player body
  -> menu; drive it) vs AI/seed without PBODY (his turn ran as an AI turn).
- Restore natural bit7, drive to commit, report.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v32.py
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
EA0 = SLOT0 + 0xEA
CT6 = SLOT6 + 0xD0
NAME0 = SLOT0
BP_TAIL = 0x0809E398
BP_PBODY = 0x0809E796
BP_AI = 0x0809E2DA
BP_NORM = 0x080C03C2
BP_NAMES = {BP_TAIL: "tail", BP_PBODY: "pbody", BP_AI: "ai", BP_NORM: "seed"}
OUT = "outputs/lua-nav/controlled-v32.json"
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


def screen_class(path):
    """'dialog' (tan>=40) / 'fade' (dark>=50%) / 'field' / None."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None
    if img.size != (480, 351):
        return None
    px = img.load()
    tan = dark = green = n = 0
    for cy in range(40, 344, 8):
        for cx in range(0, 472, 8):
            cnt = 0
            for yy in range(cy, min(cy + 32, 351), 4):
                for xx in range(cx, min(cx + 64, 480), 4):
                    r, g, b = px[xx, yy][:3]
                    if (r > 200 and g > 180 and b > 140
                            and not (abs(r - g) < 8 and abs(g - b) < 8
                                     and r > 245)):
                        cnt += 1
            best = cnt
            tan = max(tan, best)
    for y in range(40, 351, 6):
        for x in range(0, 480, 6):
            r, g, b = px[x, y][:3]
            n += 1
            if r < 60 and g < 60 and b < 60:
                dark += 1
            elif g > 90 and g > r + 15 and g > b + 15:
                green += 1
    if tan >= 40:
        return "dialog"
    if dark / n >= 0.5:
        return "fade"
    if green / n >= 0.15:
        return "field"
    return "other"


class Run:
    def __init__(self, g, pid):
        self.g = g
        self.pid = pid
        self.t0 = time.time()
        self.events = []
        self.seeds = []
        self.pick_log = []
        self.exited = False
        self.budget = 280.0
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
        p = f"outputs/lua-nav/v32-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def halt_state(self):
        g = self.g
        name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
        return {"ct6": self.u16(CT6), "ea6": self.u8(EA6),
                "live": (name0 & 0xFF000000) == 0x08000000}

    def press(self, mask, tag, need=3, pause=1.1):
        """v27-faithful press; tolerates foreign BP stops; CPU resumed after."""
        g = self.g
        hits = 0
        iters = 0
        try:
            if g.send(f"Z0,{KEY_BL:x},2") != "OK":
                print(f"  FAIL: KEY_BL BP rejected ({tag})")
                return 0
            while hits < need and iters < 14:
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
                elif pc == BP_NORM:
                    self.seeds.append({"t": self.now(), "r4": regs[4],
                                       "during": tag})
                    print(f"  SEED during press {tag} r4={regs[4]:08x}")
                elif pc in BP_NAMES:
                    self.events.append({"t": self.now(), "bp": BP_NAMES[pc],
                                        "r0": regs[0], "r7": regs[7],
                                        "during": tag})
        finally:
            try:
                g.send(f"z0,{KEY_BL:x},2")
                g.cont()
            except Exception:
                pass
        time.sleep(pause)
        print(f"  key {mask:#04x} x{hits} {tag} (t={self.now()})")
        return hits

    def dismiss(self, max_s=25.0):
        """Screen-classified: press A on dialog; wait out fade; done on field."""
        t0 = time.time()
        n = 0
        while time.time() - t0 < max_s and not self.expired():
            if self.exited:
                return False
            p = self.cap(f"cls{n}")
            cls = screen_class(p) if p else None
            if cls == "field":
                if n:
                    print(f"  screen: field after {n} actions (t={self.now()})")
                return True
            if cls == "dialog":
                self.press(0x01, f"dismiss#{n}", need=2, pause=1.2)
                n += 1
            else:
                g = self.g
                try:
                    g.cont()
                except Exception:
                    pass
                time.sleep(0.8)
        print(f"  screen never reached field (last={cls})")
        return False

    def watch_pick(self, timeout_s, actor_slot=None):
        """Wait for a TAIL hit; log ea of slot0/slot6; return hit dict."""
        g = self.g
        end = time.time() + timeout_s
        g.sock.settimeout(0.5)
        while time.time() < end and not self.expired():
            try:
                g.cont()
                stop = g._read_packet()
            except Exception:
                continue
            if not stop or stop[:1] not in ("S", "T"):
                continue
            regs = g.read_registers()
            if not regs:
                continue
            pc = regs[15]
            ev = {"t": self.now(), "bp": BP_NAMES.get(pc, f"{pc:08x}"),
                  "r0": regs[0], "r7": regs[7]}
            if pc == BP_NORM:
                self.seeds.append({"t": self.now(), "r4": regs[4]})
                continue
            if pc == BP_TAIL:
                ev["ea0"] = self.u8(EA0)
                ev["ea6"] = self.u8(EA6)
                self.pick_log.append(ev)
                actor = None
                for cand in (regs[0], regs[7]):
                    if 0 <= cand <= 7:
                        actor = cand
                        break
                ev["actor"] = actor
                if actor is None or actor_slot is None or actor == actor_slot:
                    print(f"  PICK t={ev['t']} actor={actor} ea0={ev['ea0']}"
                          f" ea6={ev['ea6']} r0={regs[0]:08x} r7={regs[7]:08x}")
                    return ev
            elif pc in BP_NAMES:
                self.events.append(ev)
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
            if not self.dismiss():
                if self.exited:
                    return False
        return False

    def compress(self):
        self.g.interrupt()
        assert self.g.send(f"M{CT6:x},2:{10:04x}") == "OK"
        self.g.cont()

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
                if not regs:
                    continue
                pc = regs[15]
                if pc == BP_NORM:
                    self.seeds.append({"t": self.now(), "r4": regs[4],
                                       "during": tag})
                    print(f"  SEED t={self.now()} r4={regs[4]:08x} ({tag})")
                elif pc in BP_NAMES:
                    self.events.append({"t": self.now(),
                                        "bp": BP_NAMES[pc], "r0": regs[0],
                                        "r7": regs[7], "during": tag})


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
        out["baseline"]["ea6"] = r.u8(EA6)
        for bp in (BP_TAIL, BP_PBODY, BP_AI, BP_NORM):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        g.cont()

        # wait out boot fade + dismiss skit; then wait for Marche's pick ------
        r.dismiss()
        print(f"waiting for Marche's first pick (t={r.now()})...")
        pick = r.watch_pick(60.0, actor_slot=6)
        out["first_pick"] = pick
        if not pick:
            print("no Marche pick observed in 60 s")
            out["final"] = {**r.halt_state(), "battle_exited": r.exited}
            g.send(f"z0,{BP_TAIL:x},2")
            g.send(f"z0,{BP_PBODY:x},2")
            g.send(f"z0,{BP_AI:x},2")
            g.send(f"z0,{BP_NORM:x},2")
            g.cont()
            return 1

        # ---- round 1..2: drive + compressed control windows ------------------
        rounds = []
        for rnd in (1, 2):
            if r.exited or r.expired():
                break
            ok = r.commit_drive(f"r{rnd}")
            rounds.append({"round": rnd, "committed": ok,
                           "seeds_in_window": [s for s in r.seeds
                                               if s.get("during", "").startswith(f"r{rnd}")]})
            if not ok:
                break
            r.compress()
            n_before = len(r.seeds)
            r.listen(8.0, f"r{rnd}->pre-menu")
            rounds[-1]["pre_menu_seeds"] = r.seeds[n_before:]
            if r.exited:
                break
            # wait for his next pick; the menu reopens by itself
            pick = r.watch_pick(20.0, actor_slot=6)
            rounds[-1]["next_pick"] = pick
            if not pick:
                break
        out["phase_a"] = {
            "rounds": rounds,
            "seeds": r.seeds,
            "verdict": ("seeds in a pre-menu window => retail player turns "
                        "ctx-init the sequencer"
                        if any(x.get("pre_menu_seeds") for x in rounds) else
                        "no seeds in any pre-menu window => retail player "
                        "turns do not ctx-init"),
        }
        print(f"phase A verdict: {out['phase_a']['verdict']}")

        # ---- phase B: bit7 polarity rounds -----------------------------------
        bres = []
        natural_ea = r.u8(EA6)
        for rnd, bit in ((3, 0), (4, 1)):
            if r.exited or r.expired():
                break
            g.interrupt()
            ea = r.u8(EA6)
            new = (ea | 0x80) if bit else (ea & 0x7F)
            assert g.send(f"M{EA6:x},1:{new:02x}") == "OK"
            r.compress()
            n_ev = len(r.events)
            n_seed = len(r.seeds)
            pick = r.watch_pick(20.0, actor_slot=6)
            ev_window = r.events[n_ev:]
            seed_window = r.seeds[n_seed:]
            pbody = any(e["bp"] == "pbody" for e in ev_window)
            res = {"round": rnd, "bit7_written": bit, "ea_before": ea,
                   "ea_written": r.u8(EA6), "pick": pick,
                   "pbody_hit": pbody, "events": ev_window,
                   "seeds": seed_window,
                   "ai_turn": bool(seed_window) and not pbody}
            if pick and pbody:
                # his turn is on the player path: drive it
                res["committed"] = r.commit_drive(f"b{rnd}")
                if res["committed"]:
                    r.compress()
            elif pick and res["ai_turn"]:
                # AI turn executes by itself; wait for it to finish
                r.listen(10.0, f"b{rnd}-ai-exec")
                res["committed"] = None
            bres.append(res)
            print(f"phase B r{rnd} bit7={bit}: pbody={pbody} "
                  f"seeds={len(seed_window)} ai_turn={res['ai_turn']}")
        out["phase_b"] = {
            "natural_ea": natural_ea,
            "rounds": bres,
            "verdict": ("AI turn (seed, no pbody) on some polarity => "
                        "reverse handout works"
                        if any(x.get("ai_turn") for x in bres) else
                        "player body on every polarity => bit7 alone does "
                        "not hand a player unit to the AI"),
        }
        print(f"phase B verdict: {out['phase_b']['verdict']}")

        # ---- restore ----------------------------------------------------------
        g.interrupt()
        ea = r.u8(EA6)
        assert g.send(f"M{EA6:x},1:{(ea & 0x7F) if natural_ea is not None and natural_ea < 0x80 else (ea | 0x80):02x}") == "OK"
        out["restored_ea"] = r.u8(EA6)
        if not r.exited and not r.expired():
            pick = r.watch_pick(20.0, actor_slot=6)
            if pick:
                out["restoration_committed"] = r.commit_drive("restore")
            else:
                out["restoration_committed"] = None

        # ---- wrap --------------------------------------------------------------
        g.interrupt()
        out["final"] = {**r.halt_state(), "seeds_total": len(r.seeds),
                        "battle_exited": r.exited,
                        "budget_exceeded": r.expired(),
                        "pick_log_tail": r.pick_log[-12:]}
        for bp in (BP_TAIL, BP_PBODY, BP_AI, BP_NORM):
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
