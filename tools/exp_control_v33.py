"""A2.3 v33: pick-anchored protocol — full game speed, no starvation.

v32 diagnosis: BP_TAIL (0x0809E398) is a PER-FRAME scan point (~60 hits/s);
arming it starved the game to ~14 frames per press, so dismissal presses and
the skit never advanced, and the r0-based actor read was wrong anyway (r0 is
always 0 at the tail; v27's events prove it).

v33 anchors on the real per-turn pick point 0x0809E260 (r0 = actor slot,
fires once per unit turn — cheap) and keeps the game at full speed.

Phases:
  0. dismiss dialogs by screen class at full speed (A only on 'dialog'),
     then drive Marche's first pick (menu opens with the pick).
  A. control question, per compressed round: at each pick event record the
     actor; run 2.0 s WITHOUT input and count seeds in that window.
     Enemy picks are the positive control (v27: a seed fires at every enemy
     turn start). If Marche's pick window also seeds => retail player turns
     ctx-init the sequencer; else not.
  B. reverse handout, one polarity per compressed round:
     round 3: Marche +0xEA bit7 = 1 before his pick; expect his frames to
       hit pbody 0x0809E796 instead of ai 0x0809E2DA; observe whether a
       seed still fires and whether his menu still opens (drive commits).
     round 4: bit7 = 0 (natural) — same observations as baseline.
  restore: natural bit7, final drive.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v33.py
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
OUT = "outputs/lua-nav/controlled-v33.json"
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
    """'dialog' (tan>=40) / 'fade' (dark>=50%) / 'field' (green>=15%)."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None
    if img.size != (480, 351):
        return None
    px = img.load()
    tan = 0
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
            tan = max(tan, cnt)
    dark = green = n = 0
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
        self.picks = []
        self.exited = False
        self.budget = 300.0
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
        p = f"outputs/lua-nav/v33-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def halt_state(self):
        g = self.g
        name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
        return {"ct6": self.u16(CT6), "ea6": self.u8(EA6),
                "live": (name0 & 0xFF000000) == 0x08000000}

    def press(self, mask, tag, need=4, pause=1.1, max_iters=24):
        """v27-faithful press; tolerates pick/ai/seed stops; CPU resumed."""
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

    def log_stop(self, pc, regs, during=None):
        name = BP_NAMES.get(pc)
        if name == "seed":
            self.seeds.append({"t": self.now(), "r4": regs[4],
                               "r7": regs[7], "during": during})
            print(f"  SEED t={self.now()} r4={regs[4]:08x} r7={regs[7]:08x}"
                  + (f" ({during})" if during else ""))
        elif name == "pick":
            actor = regs[0]
            rec = {"t": self.now(), "actor": actor, "ea6": self.u8(EA6),
                   "r0": regs[0]}
            self.picks.append(rec)
            print(f"  PICK t={rec['t']} actor={actor} ea6={rec['ea6']}")
        elif name:
            self.events.append({"t": self.now(), "bp": name, "r0": regs[0],
                                "r7": regs[7], "during": during})

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

    def dismiss(self, max_s=70.0, max_presses=30):
        """Full-speed screen-classified dismissal: A on every non-field state.
        Law card = dark, skit pages = tan dialog, page flips = white 'other'.
        """
        t0 = time.time()
        n = 0
        last = None
        while time.time() - t0 < max_s and not self.expired():
            if self.exited:
                return False
            p = self.cap(f"cls{n}")
            cls = screen_class(p) if p else None
            last = cls
            if cls == "field":
                print(f"  screen: field (t={self.now()}, presses={n})")
                return True
            if n < max_presses:
                hits = self.press(0x01, f"dismiss#{n}", need=3, pause=1.0)
                n += 1
                if hits == 0:
                    time.sleep(0.5)
            else:
                self.g.cont()
                time.sleep(1.2)
        print(f"  dismissal ended (last={last}, presses={n})")
        return False

    def watch_pick(self, timeout_s, actor_slot=6):
        """Wait for a pick event with r0 == actor_slot; log all picks."""
        g = self.g
        end = time.time() + timeout_s
        g.sock.settimeout(0.4)
        while time.time() < end and not self.expired():
            try:
                g.cont()
                stop = g._read_packet()
            except Exception:
                continue
            if not stop or stop[:1] in ("S", "T"):
                regs = g.read_registers()
                if regs:
                    pc = regs[15]
                    self.log_stop(pc, regs, "watch")
                    if pc == BP_PICK and regs[0] == actor_slot:
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


def seed_window(r, start_idx, t_start, t_end):
    return [s for s in r.seeds[start_idx:] if t_start <= s["t"] <= t_end]


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
        for bp in (BP_PICK, BP_PBODY, BP_AI, BP_NORM):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        g.cont()

        # ---- dismissal at full speed ----------------------------------------
        r.dismiss()
        out["dismissal_t"] = r.now()

        # ---- round 1: drive Marche's first turn ------------------------------
        if r.exited:
            print("battle exited during dismissal")
            out["final"] = {**r.halt_state(), "battle_exited": True}
            with open(OUT, "w") as fh:
                json.dump(out, fh, indent=1)
            return 1
        print(f"waiting for Marche's pick (t={r.now()})...")
        pick = r.watch_pick(90.0, actor_slot=6)
        out["first_pick"] = pick
        if not pick:
            print("no Marche pick in 90 s")
        r1 = {}
        if pick:
            # pre-drive control window: 2 s of silence
            n_seed = len(r.seeds)
            t_pick = pick["t"]
            r.pump(2.0, "pre-drive-r1")
            r1["pre_drive_seeds"] = seed_window(r, n_seed, t_pick,
                                                r.now())
            r1["committed"] = r.commit_drive("r1")
            if r1["committed"]:
                r.compress()
        out["round1"] = r1
        print(f"round1: {r1}")

        # ---- rounds 2..4: compressed rounds with per-polarity phase B --------
        rounds = []
        natural_ea = r.u8(EA6)
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
            n_ev = len(r.events)
            pick = r.watch_pick(25.0, actor_slot=6)
            if not pick:
                rounds.append({"round": rnd, "pick": None})
                break
            n_seed = len(r.seeds)
            t_pick = pick["t"]
            r.pump(2.0, f"pre-drive-r{rnd}")
            ev_win = r.events[n_ev:]
            rec = {
                "round": rnd, "bit7": bit, "pick": pick,
                "pre_drive_seeds": seed_window(r, n_seed, t_pick, r.now()),
                "pbody_in_window": any(e["bp"] == "pbody" for e in ev_win),
                "ai_in_window": any(e["bp"] == "ai" for e in ev_win),
            }
            rec["committed"] = r.commit_drive(f"r{rnd}") if not r.expired() else None
            if rec["committed"]:
                r.compress()
            rounds.append(rec)
            print(f"round {rnd}: {rec}")
        out["rounds"] = rounds
        out["natural_ea"] = natural_ea

        pre_seeds_marche = [s for x in rounds if x.get("pre_drive_seeds")
                            for s in x["pre_drive_seeds"]]
        out["verdict_control"] = (
            "seeds in Marche pre-drive windows => retail player turns "
            "ctx-init the sequencer" if pre_seeds_marche else
            "no seeds in any Marche pre-drive window => retail player turns "
            "do NOT ctx-init (enemy picks are the positive control)")
        print(f"control verdict: {out['verdict_control']}")

        r3 = next((x for x in rounds if x.get("round") == 3), None)
        r4 = next((x for x in rounds if x.get("round") == 4), None)
        out["verdict_reverse"] = (
            "bit7=1: Marche hit pbody and his menu still opened => bit7 is "
            "not a reverse lever for player units"
            if r3 and r3.get("pbody_in_window") and r3.get("committed") else
            "bit7=1: seed without a committable menu => reverse handout "
            "(Marche -> AI turn) works"
            if r3 and r3.get("pre_drive_seeds") and not r3.get("committed")
            else "inconclusive (see rounds)")
        print(f"reverse verdict: {out['verdict_reverse']}")

        # ---- restore ----------------------------------------------------------
        if not r.exited and not r.expired():
            g.interrupt()
            ea = r.u8(EA6)
            target = natural_ea if natural_ea is not None else (ea & 0x7F)
            assert g.send(f"M{EA6:x},1:{target:02x}") == "OK"
            out["restored_ea"] = r.u8(EA6)
            pick = r.watch_pick(25.0, actor_slot=6)
            if pick:
                out["restoration_committed"] = r.commit_drive("restore")

        # ---- wrap --------------------------------------------------------------
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
