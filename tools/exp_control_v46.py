"""A2.3 v46: v27-faithful drive to wake + direct attribution + bit7 flip.

Cross-run comparison settles the wake question:
- Every WAKING run executed the 4-press route (v27 at attach; v43 at
  attach + second pass; v44's t=120 fallback drive preceded its t~126
  wake). Every PRESSLESS run (v38/v39/v42/v45 x3) stayed dormant for
  5+ min. Conclusion: from fix3-battle-start the menu does NOT idle into
  auto-battle by itself; the turn loop starts once the route commits
  Marche's Wait.

v46 protocol:
  1. attach, verify, enable=1, arm seed BP.
  2. DRIVE: DOWN DOWN A A via the r1-patch channel (v27 press semantics:
     CPU keeps running between presses).
  3. watch 40 s for a seed; if none, drive again (v43's second pass);
     watch 40 s more.
  4. ATTRIB phase (heavy): pbody/ai/seed BPs 120 s. Marche pbody bursts
     followed <=6 s by a seed => retail player turns DO ctx-init.
  5. BIT7 flip ea6|=0x80, watch 90 s (does Marche's next auto turn
     switch body?), restore.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v46.py
"""
import json
import socket
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

SLOT0 = 0x020159E8
STRIDE = 0x108
SLOT6 = SLOT0 + STRIDE * 6
EA6 = SLOT6 + 0xEA
CT6 = SLOT6 + 0xD0
NAME0 = SLOT0
KEY_BL = 0x08000494
BP_NORM = 0x080C03C2
BP_PBODY = 0x0809E796
BP_AI = 0x0809E2DA
BP_NAMES = {BP_NORM: "seed", BP_PBODY: "pbody", BP_AI: "ai"}
UNIT_LO, UNIT_HI = 0x02015900, 0x02015D00
OUT = "outputs/lua-nav/controlled-v46.json"
ROUTE = [(0x80, "DOWN1"), (0x80, "DOWN2"), (0x01, "A-wait"), (0x01, "A-ok")]


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
        self.pbody = []
        self.ai = []
        self.seeds = []
        self.samples = []
        self.pump_fails = 0
        self.pump_cycles = 0
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

    def u32(self, a):
        d = self.g.read_mem(a, 4)
        return int.from_bytes(d, "little") if d else None

    def name_table(self):
        return [self.u32(SLOT0 + STRIDE * s) for s in range(7)]

    def slot_for_name(self, name, table):
        if name and (UNIT_LO <= name <= UNIT_HI or name in table):
            for s, n in enumerate(table):
                if n == name:
                    return s
        return None

    def cap(self, tag):
        if not self.pid:
            return None
        self.cap_i += 1
        p = f"outputs/lua-nav/v46-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def live(self):
        name0 = self.u32(NAME0)
        return (name0 & 0xFF000000) == 0x08000000

    def all_cts(self):
        return [self.u16(SLOT0 + STRIDE * s + 0xD0) for s in range(7)]

    def press(self, mask, tag):
        """One key press via the r1-patch at the key poll; CPU runs free
        again immediately after the patch (v27 semantics)."""
        g = self.g
        try:
            if g.send(f"Z0,{KEY_BL:x},2") != "OK":
                self.pump_fails += 1
                return
            g.cont()
            try:
                stop = g._read_packet()
            except socket.timeout:
                stop = None
            if stop and stop[:1] in ("S", "T"):
                regs = g.read_registers()
                if regs and regs[15] == KEY_BL:
                    val = (regs[1] | mask) & 0x3FF
                    g.send("P1=" + val.to_bytes(4, "little").hex())
                    print(f"  press {tag} t={self.now()}")
                else:
                    self.handle_stop("press", None)
            g.send(f"z0,{KEY_BL:x},2")
            g.cont()
        except Exception:
            self.pump_fails += 1

    def drive(self, tag, pause=0.9):
        for mask, name in ROUTE:
            self.press(mask, f"{tag}:{name}")
            time.sleep(pause)

    def handle_stop(self, during=None, table=None):
        regs = self.g.read_registers()
        if not regs:
            self.pump_fails += 1
            return None
        pc = regs[15]
        name = BP_NAMES.get(pc)
        t = self.now()
        if name == "pbody":
            unit = regs[4]
            nm = self.u32(unit) if unit else None
            ct = self.u16(unit + 0xD0) if unit else None
            slot = self.slot_for_name(nm, table or [])
            self.pbody.append({"t": t, "r4": unit, "name": nm, "ct": ct,
                               "slot": slot, "r7": regs[7], "during": during})
            if len(self.pbody) % 10 == 1:
                print(f"  PBODY t={t} r4={unit:08x} "
                      f"name={f'{nm:08x}' if nm else '0'} ct={ct} slot={slot}")
        elif name == "ai":
            self.ai.append({"t": t, "r7": regs[7], "during": during})
        elif name == "seed":
            ctx = regs[7]
            hits = []
            blob = self.g.read_mem(ctx, 0x400)
            if blob:
                for off in range(0, len(blob) - 3, 4):
                    v = int.from_bytes(blob[off:off + 4], "little")
                    if UNIT_LO <= v <= UNIT_HI:
                        hits.append({"off": off, "v": v})
                    elif (v & 0xFF000000) == 0x08000000 and \
                            0x08560000 <= v <= 0x08580000:
                        hits.append({"off": off, "name": v})
            self.seeds.append({"t": t, "r4": regs[4], "r7": ctx,
                               "ctx_hits": hits, "during": during})
            print(f"  SEED t={t} r4={regs[4]:08x} ctx_hits={len(hits)} "
                  f"during={during}")
        return regs

    def pump(self, seconds, during=None, sample_every=15.0, heavy=True):
        g = self.g
        end = time.time() + seconds
        last_s = self.now()
        last_tbl = 0.0
        table = None
        g.sock.settimeout(2.0)
        dead = 0
        while time.time() < end and not self.exited:
            self.pump_cycles += 1
            stop = None
            try:
                g.cont()
                try:
                    stop = g._read_packet()
                except socket.timeout:
                    stop = None
                dead = 0
            except Exception:
                dead += 1
                self.pump_fails += 1
                try:
                    g.interrupt()
                except Exception:
                    pass
                if dead >= 20:
                    print(f"  pump dead after 20 bad cycles (t={self.now()})")
                    self.exited = True
                    return
            if stop and stop[:1] in ("S", "T"):
                try:
                    if heavy:
                        pc_probe = g.read_pc()
                        if BP_NAMES.get(pc_probe) == "pbody" and \
                                self.now() - last_tbl >= 5.0:
                            last_tbl = self.now()
                            table = self.name_table()
                    self.handle_stop(during, table)
                except Exception:
                    self.pump_fails += 1
            if self.now() - last_s >= min(2.0, sample_every):
                try:
                    g.interrupt()
                    if self.now() - last_s >= sample_every:
                        last_s = self.now()
                        if not self.live():
                            self.exited = True
                            print(f"  battle exited (t={self.now()})")
                            return
                        self.samples.append({
                            "t": self.now(), "cts": self.all_cts(),
                            "ea6": self.u8(EA6)})
                        print(f"  [t={self.now()}] "
                              f"cts={self.samples[-1]['cts']} "
                              f"seeds={len(self.seeds)} ea6="
                              f"{self.samples[-1]['ea6']:#04x}")
                except Exception:
                    self.pump_fails += 1

    def write_partial(self, extra=None):
        out = dict(extra or {})
        out.update({
            "pbody": self.pbody, "ai": self.ai, "seeds": self.seeds,
            "samples": self.samples, "pump_fails": self.pump_fails,
            "pump_cycles": self.pump_cycles, "battle_exited": self.exited,
            "t_end": self.now()})
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)


def summarize(r):
    bursts = []
    for p in r.pbody:
        if p["slot"] is None:
            continue
        if bursts and p["t"] - bursts[-1]["t_end"] < 1.5 and \
                bursts[-1]["slot"] == p["slot"]:
            bursts[-1]["t_end"] = p["t"]
            bursts[-1]["hits"] += 1
        else:
            bursts.append({"slot": p["slot"], "t_start": p["t"],
                           "t_end": p["t"], "hits": 1})
    for b in bursts:
        after = [s for s in r.seeds if 0 <= s["t"] - b["t_end"] <= 6.0]
        b["seed_after"] = after[0]["t"] if after else None
        b["seed_ctx_hits"] = len(after[0]["ctx_hits"]) if after else 0
    return bursts


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    r = Run(g, pid)
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        if not r.live():
            print(f"fixture signature missing: name0={r.u32(NAME0):08x}")
            return 1
        base = {"name_table": r.name_table(), "ct6": r.u16(CT6),
                "ea6": r.u8(EA6)}
        print(f"baseline: {base}")
        out = {"baseline": base}
        assert g.send("M3000005,1:01") == "OK"
        assert g.send(f"Z0,{BP_NORM:x},2") == "OK"
        r.cap("attach")

        # ---- phase 1: DRIVE to wake ----------------------------------------
        print("drive pass 1 (v27 route)...")
        r.drive("d1")
        r.pump(40.0, "wake1", sample_every=10.0, heavy=False)
        if not r.seeds and not r.exited:
            print("no seed after drive 1; drive pass 2")
            r.drive("d2")
            r.pump(40.0, "wake2", sample_every=10.0, heavy=False)
        out["seeds_after_wake"] = len(r.seeds)

        # ---- phase 2: ATTRIB ------------------------------------------------
        if len(r.seeds) >= 1 and not r.exited:
            g.interrupt()
            for bp in (BP_PBODY, BP_AI):
                assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
            print(f"attrib phase: {len(r.seeds)} seeds; watching "
                  "pbody/ai/seed for 120 s")
            r.pump(120.0, "attrib", sample_every=15.0, heavy=True)
        else:
            print(f"wake failed: seeds={len(r.seeds)} exited={r.exited}")
            r.cap("wake-fail")

        bursts = summarize(r)
        out["pbody_bursts"] = bursts
        out["seeds_n"] = len(r.seeds)
        marche_bursts = [b for b in bursts if b["slot"] == 6]
        paired = [b for b in marche_bursts if b["seed_after"] is not None]
        out["verdict_control"] = (
            f"{len(marche_bursts)} Marche pbody bursts, {len(paired)} "
            "followed by a seed <=6s => retail player turns DO ctx-init "
            "the sequencer" if paired else
            f"{len(marche_bursts)} Marche pbody bursts, none seed-paired; "
            f"bursts={bursts}")
        print(f"control: {out['verdict_control']}")
        r.write_partial(out)

        # ---- phase 3: BIT7 flip ---------------------------------------------
        rev = {"attempted": False}
        if r.live() and len(r.seeds) >= 2 and not r.exited:
            g.interrupt()
            ea = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea | 0x80:02x}") == "OK"
            rev = {"attempted": True, "ea_before": ea,
                   "ea_written": r.u8(EA6), "t": r.now()}
            print(f"bit7 SET t={r.now()} ({ea:#04x} -> "
                  f"{rev['ea_written']:#04x})")
            n0 = {"pb": len(r.pbody), "ai": len(r.ai),
                  "seeds": len(r.seeds)}
            r.pump(90.0, "bit7", sample_every=15.0, heavy=True)
            rev["ea_seen_after"] = [s["ea6"] for s in r.samples
                                    if s["t"] > rev["t"]]
            bursts2 = summarize(r)
            rev["bursts_after"] = [b for b in bursts2
                                   if b["t_start"] > rev["t"]]
            rev["seeds_after"] = len(r.seeds) - n0["seeds"]
            rev["ai_after"] = len(r.ai) - n0["ai"]
            mb = [b for b in rev["bursts_after"] if b["slot"] == 6]
            rev["verdict"] = (
                "Marche pbody bursts continue after flip (bit7 does not "
                "reroute idle-auto turns)" if mb else
                "no Marche pbody bursts after flip; ai hits=%d seeds=%d"
                % (rev["ai_after"], rev["seeds_after"]))
            print(f"reverse: {rev['verdict']}")
            g.interrupt()
            ea2 = r.u8(EA6)
            assert g.send(f"M{EA6:x},1:{ea2 & 0x7F:02x}") == "OK"
            rev["ea_restored_to"] = r.u8(EA6)
        out["phase_bit7"] = rev

        g.interrupt()
        out["final"] = {"ct6": r.u16(CT6), "ea6": r.u8(EA6),
                        "live": r.live()}
        for bp in (BP_NORM, BP_PBODY, BP_AI):
            g.send(f"z0,{bp:x},2")
        g.cont()
        time.sleep(0.5)
        r.cap("final")
        r.write_partial(out)
        print(f"wrote {OUT}")
        return 0
    finally:
        try:
            g.interrupt()
            for bp in (BP_NORM, BP_PBODY, BP_AI, KEY_BL):
                g.send(f"z0,{bp:x},2")
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
