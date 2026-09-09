"""A2.3 v44: long-watch retail observation + actor-at-seed + bit7 flip.

v43 breakthroughs this builds on:
- The fixture battle self-plays, but wake time after resume is 40-120 s
  (nondeterministic scene flow); earlier runs' windows were too short.
- ctx-init wrapper caller: single, lr=0x0809345b (battle main loop).
- The pick BP (0x0809E260) is a per-frame scan point; the SEED is the
  per-turn marker; the actor of a turn = the pick hit within ~0.15 s of
  its seed (the turn-manager's same-frame scan).

v44 protocol (retail: no slot0 writes, no presses):
  1. boot, attach, verify, arm wrapper/seed/pick/pbody/ai BPs, enable=1,
     release, watch up to 220 s. Log raw picks (no dedup), seeds, wrappers;
     sample all CTs every 15 s. Battle-exit detection via name0.
  2. actor-at-seed: pair each seed with the pick hit closest in time
     (< 0.2 s); report per-actor seed counts — Marche's auto-turns seeding
     = the control question answered retail.
  3. once >= 6 seeds: write ea6 |= 0x80 (reverse handout candidate);
     keep watching 90 s: subsequent Marche-attributed turns hitting pbody
     (0x0809E796) vs ai (0x0809E2DA) decide the reverse question. Restore.
  4. fallback: if no seed by t=120, one v27 drive pass (harmless mid-fight,
     per v43) and continue watching. JSON verdicts.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v44.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
SLOT0 = 0x020159E8
STRIDE = 0x108
SLOT6 = SLOT0 + STRIDE * 6
EA6 = SLOT6 + 0xEA
CT6 = SLOT6 + 0xD0
NAME0 = SLOT0
BP_WRAP = 0x080C144C
BP_NORM = 0x080C03C2
BP_PICK = 0x0809E260
BP_PBODY = 0x0809E796
BP_AI = 0x0809E2DA
BP_NAMES = {BP_WRAP: "wrap", BP_NORM: "seed", BP_PICK: "pick",
            BP_PBODY: "pbody", BP_AI: "ai"}
OUT = "outputs/lua-nav/controlled-v44.json"
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


class Run:
    def __init__(self, g, pid):
        self.g = g
        self.pid = pid
        self.t0 = time.time()
        self.wraps = []
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
        p = f"outputs/lua-nav/v44-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def live(self):
        name0 = int.from_bytes(self.g.read_mem(NAME0, 4) or b"\0\0\0\0",
                               "little")
        return (name0 & 0xFF000000) == 0x08000000

    def all_cts(self):
        return [self.u16(SLOT0 + STRIDE * s + 0xD0) for s in range(7)]

    def log_stop(self, pc, regs, during=None):
        name = BP_NAMES.get(pc)
        t = self.now()
        if name == "seed":
            self.seeds.append({"t": t, "r4": regs[4], "r7": regs[7],
                               "during": during})
            print(f"  SEED t={t} r4={regs[4]:08x}")
        elif name == "pick":
            self.picks.append({"t": t, "actor": regs[0]})
        elif name == "wrap":
            self.wraps.append({"t": t, "lr": regs[14], "r0": regs[0]})
        elif name:
            self.events.append({"t": t, "bp": name, "r0": regs[0]})
            if name == "pbody":
                print(f"  PBODY t={t} r0={regs[0]:08x}")

    def press(self, mask, tag, need=5, pause=1.2, max_iters=60):
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
                if regs[15] == KEY_BL:
                    val = (regs[1] | mask) & 0x3FF
                    g.send("P1=" + val.to_bytes(4, "little").hex())
                    hits += 1
                else:
                    self.log_stop(regs[15], regs, f"press:{tag}")
        finally:
            try:
                g.send(f"z0,{KEY_BL:x},2")
                g.cont()
            except Exception:
                pass
        time.sleep(pause)
        return hits

    def pump(self, seconds, during=None, sample_every=15.0):
        g = self.g
        end = time.time() + seconds
        last_s = 0.0
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
            if sample_every and self.now() - last_s >= sample_every:
                last_s = self.now()
                g.interrupt()
                if not self.live():
                    self.exited = True
                    print(f"  battle exited (t={self.now()})")
                    return
                self.samples.append({"t": self.now(), "cts": self.all_cts(),
                                     "ea6": self.u8(EA6)})
                print(f"  [t={self.now()}] cts={self.samples[-1]['cts']} "
                      f"seeds={len(self.seeds)} ea6="
                      f"{self.samples[-1]['ea6']:#04x}")

    def drive(self, tag):
        for mask, name in ROUTE:
            self.press(mask, f"{tag}:{name}")


def attribute_actors(picks, seeds, tol=0.2):
    """For each seed, the closest real-slot pick (0..6) within tol.

    The pick BP fires every frame; when no turn is pending the turn
    manager returns a sentinel (not a slot), so ignore actors > 6.
    """
    real = [p for p in picks if p["actor"] is not None and p["actor"] <= 6]
    res = []
    for s in seeds:
        best = None
        bestd = tol
        for p in real:
            d = abs(p["t"] - s["t"])
            if d <= bestd:
                best = p
                bestd = d
        res.append({"t": s["t"], "r4": f"{s['r4']:08x}",
                    "actor": best["actor"] if best else None,
                    "pick_dt": round(bestd, 2) if best else None})
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
        for bp in (BP_WRAP, BP_NORM, BP_PICK, BP_PBODY, BP_AI):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        assert g.send("M3000005,1:01") == "OK"
        g.cont()
        print("retail observation (no writes but enable, no presses)...")

        # ---- long watch with a mid-watch fallback drive -----------------------
        r.pump(120.0, "watch1", sample_every=15.0)
        if not r.seeds and not r.exited:
            print("no seeds by t=120; fallback drive pass")
            r.drive("fallback")
        r.pump(100.0, "watch2", sample_every=15.0)
        out["seeds_before_flip"] = len(r.seeds)

        # ---- actor attribution -------------------------------------------------
        att = attribute_actors(r.picks, r.seeds)
        out["seed_actors"] = att
        per_actor = {}
        for a in att:
            k = a["actor"]
            per_actor[k] = per_actor.get(k, 0) + 1
        out["seeds_per_actor"] = per_actor
        marche_n = per_actor.get(6, 0)
        others_n = sum(v for k, v in per_actor.items() if k != 6)
        out["verdict_control"] = (
            f"seeds per actor: {per_actor} => " +
            ("Marche auto-turns ctx-init the sequencer (control question "
             "ANSWERED: yes)" if marche_n else
             "no Marche-attributed seeds (player turns do NOT ctx-init)"
             if others_n else "no attributed seeds"))
        print(f"control: {out['verdict_control']}")

        # ---- bit7 reverse flip ---------------------------------------------------
        rev = {"attempted": False}
        if r.live() and len(r.seeds) >= 4:
            g.interrupt()
            ea = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea | 0x80:02x}") == "OK"
            rev = {"attempted": True, "ea_before": ea,
                   "ea_written": r.u8(EA6), "t": r.now()}
            print(f"bit7 SET at t={r.now()} ({ea:#04x} -> "
                  f"{rev['ea_written']:#04x})")
            n_seed = len(r.seeds)
            n_ev = len(r.events)
            r.pump(90.0, "bit7", sample_every=15.0)
            att_after = attribute_actors(r.picks, r.seeds[n_seed:])
            rev["seeds_after"] = att_after
            rev["pbody_after"] = sum(1 for e in r.events[n_ev:]
                                     if e["bp"] == "pbody")
            rev["ai_after"] = sum(1 for e in r.events[n_ev:]
                                  if e["bp"] == "ai")
            rev["marche_seeds_after"] = sum(1 for a in att_after
                                            if a["actor"] == 6)
            rev["verdict"] = (
                "pbody hit with Marche-attributed turns => bit7 keeps "
                "player units on the player body (no reverse handout)"
                if rev["pbody_after"] else
                "Marche-attributed seeds with ai-path activity => reverse "
                "handout (player unit -> AI turn) works" if
                rev["marche_seeds_after"] and rev["ai_after"] else
                "no Marche-attributed turn after the flip (inconclusive)")
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
                        "wraps": r.wraps[:5], "battle_exited": r.exited,
                        "samples": r.samples}
        out["raw_picks"] = r.picks
        out["raw_seeds"] = r.seeds
        for bp in (BP_WRAP, BP_NORM, BP_PICK, BP_PBODY, BP_AI):
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
