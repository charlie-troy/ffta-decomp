"""A2.3 v47: corrected unit layout + v27 wake marks + both A2.3 verdicts.

Ground truth from the live instance (15:5x dump, 2026-09-09):
  records @0x020159E8, stride 0x108, six live units + one free slot:
    slot0 name=085671EE ct=45  id=00  (MARCHE; fixture "ct0")
    slot1 name=0856702F ct=464 id=01  (boot validates this as "name0")
    slots2-5 names/cts 850/821/515/315; slot6 @02016018 = FREE (RAM ptr, ct=0)
  => all "slot6/EA6/CT6" sampling in v44-v46 hit a phantom or slot1 fields.
  => v27's wake marks (slot0 e6/dc=id, ed|=8, ea|=0x80) are the missing
     ingredient in every dormant boot: slot0's pending turn must be routed
     (forward handout) before the drive can commit anything.

v47 protocol:
  1. attach; verify slot0 name=085671EE + slot1 name=0856702F; enable=1.
  2. WAKE: v27 marks on slot0 (e6/dc=id(0), ed|=8, ea|=0x80), then the
     v27 route (DOWN DOWN A A) with v27's verbatim press. Watch 40 s for
     a seed (BP_NORM); retry drive once.
  3. CONTROL (retail player turn -> ctx-init?):
     clear Marche ea bit7, compress Marche CT=10; watch 45 s. His turn:
     pbody burst (r4 ~ 0x020159E8) then seed <=6 s => YES.
     Attribution: name word at [r4-4] or [r4] in 0x0855-0x0857 range.
  4. REVERSE (bit7 -> AI body?): set ea bit7 again, compress CT=10,
     watch 45 s: menu-driven turn vs auto-execution, pbody/seed pattern.
  5. restore bit7=0 (natural), final capture + JSON.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v47.py
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
NAME_M = 0x085671EE          # slot0 record's name pointer (Marche)
NAME1 = 0x0856702F           # slot1 (boot's signature)
EAM = SLOT0 + 0xEA           # Marche +0xEA (0x02015AD2)
CTM = SLOT0 + 0xD0           # Marche CT   (0x02015AB8)
IDM = SLOT0 + 0x104          # unit id byte (0)
KEY_BL = 0x08000494
BP_NORM = 0x080C03C2
BP_PBODY = 0x0809E796
BP_AI = 0x0809E2DA
BP_NAMES = {BP_NORM: "seed", BP_PBODY: "pbody", BP_AI: "ai"}
OUT = "outputs/lua-nav/controlled-v47.json"
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


def u8(g, a):
    d = g.read_mem(a, 1)
    return d[0] if d else None


def u16(g, a):
    d = g.read_mem(a, 2)
    return int.from_bytes(d, "little") if d else None


def u32(g, a):
    d = g.read_mem(a, 4)
    return int.from_bytes(d, "little") if d else None


class Run:
    def __init__(self, g, pid):
        self.g = g
        self.pid = pid
        self.t0 = time.time()
        self.pbody = []
        self.ai = []
        self.seeds = []
        self.samples = []
        self.caps = []
        self.cap_i = 0

    def now(self):
        return round(time.time() - self.t0, 1)

    def cap(self, tag):
        if not self.pid:
            return
        self.cap_i += 1
        p = f"outputs/lua-nav/v47-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        self.caps.append({"t": self.now(), "tag": tag, "path": p})

    def sample(self, tag):
        s = {"t": self.now(), "tag": tag,
             "ct_m": u16(self.g, CTM),
             "ea_m": u8(self.g, EAM),
             "cts": [u16(self.g, SLOT0 + STRIDE * s + 0xD0) for s in range(6)]}
        self.samples.append(s)
        print(f"  [t={s['t']} {tag}] ctM={s['ct_m']} eaM={s['ea_m']:#04x} "
              f"cts={s['cts']} seeds={len(self.seeds)} pb={len(self.pbody)}")
        return s

    # ---- v27-verbatim press -------------------------------------------------
    def press(self, mask, frames=5, pause=1.2, tag=""):
        g = self.g
        hits = 0
        try:
            if g.send(f"Z0,{KEY_BL:x},2") != "OK":
                print(f"  FAIL: KEY_BL BP rejected ({tag})")
                return 0
            for _ in range(frames):
                g.cont()
                stop = g._read_packet()
                if not stop or stop[:1] not in ("S", "T"):
                    break
                regs = g.read_registers()
                if regs and regs[15] == KEY_BL:
                    val = (regs[1] | mask) & 0x3FF
                    g.send("P1=" + val.to_bytes(4, "little").hex())
                    hits += 1
                elif regs and BP_NAMES.get(regs[15]):
                    print(f"  (BP {BP_NAMES[regs[15]]} during key {tag})")
        finally:
            try:
                g.send(f"z0,{KEY_BL:x},2")
                g.cont()
            except Exception:
                pass
        time.sleep(pause)
        print(f"  key {mask:#04x} x{hits} {tag} t={self.now()}")
        return hits

    def drive(self, tag):
        for mask, name in ROUTE:
            self.press(mask, tag=f"{tag}:{name}")

    # ---- BP handling ---------------------------------------------------------
    def handle_stop(self, during=None):
        g = self.g
        regs = g.read_registers()
        if not regs:
            return None
        pc = regs[15]
        name = BP_NAMES.get(pc)
        t = self.now()
        if name == "pbody":
            r4 = regs[4]
            nm = u32(g, r4 - 4) if r4 else None
            nm2 = u32(g, r4) if r4 else None
            rec = None
            for cand in (nm, nm2):
                if cand and 0x08550000 <= cand <= 0x0857FFFF:
                    rec = cand
                    break
            ct = u16(g, r4 - 4 + 0xD0) if rec == nm else \
                (u16(g, r4 + 0xD0) if rec == nm2 else None)
            self.pbody.append({"t": t, "r4": f"{r4:08x}",
                               "name_m1": f"{nm:08x}" if nm else None,
                               "name_0": f"{nm2:08x}" if nm2 else None,
                               "name": f"{rec:08x}" if rec else None,
                               "ct": ct, "r7": f"{regs[7]:08x}",
                               "during": during})
            if len(self.pbody) <= 4 or len(self.pbody) % 10 == 1:
                print(f"  PBODY t={t} r4={r4:08x} name={rec and hex(rec)} "
                      f"ct={ct} during={during}")
        elif name == "ai":
            self.ai.append({"t": t, "r7": f"{regs[7]:08x}", "during": during})
        elif name == "seed":
            self.seeds.append({"t": t, "r4": f"{regs[4]:08x}",
                               "r7": f"{regs[7]:08x}", "during": during})
            print(f"  SEED t={t} r4={regs[4]:08x} during={during}")
        return regs

    def pump(self, seconds, during=None, sample_every=10.0, bps=("seed",)):
        """Free pump: cont and wait for BP stops; periodic CT samples."""
        g = self.g
        addrs = {"seed": BP_NORM, "pbody": BP_PBODY, "ai": BP_AI}
        end = time.time() + seconds
        last_s = self.now()
        last_tbl = 0.0
        table = [NAME_M, NAME1] + [None] * 5
        while time.time() < end:
            try:
                g.cont()
                stop = g._read_packet()
            except socket.timeout:
                stop = None
            except Exception:
                stop = None
                time.sleep(0.05)
            if stop and stop[:1] in ("S", "T"):
                regs = g.read_registers()
                if regs and BP_NAMES.get(regs[15]) in bps:
                    if BP_NAMES.get(regs[15]) == "pbody" and \
                            self.now() - last_tbl > 5.0:
                        last_tbl = self.now()
                    try:
                        self.handle_stop(during)
                    except Exception as e:
                        print(f"  handle_stop error: {e}")
            if self.now() - last_s >= sample_every:
                last_s = self.now()
                self.sample(during or "watch")

    def compress(self):
        g = self.g
        g.interrupt()
        ok = g.send(f"M{CTM:x},2:0a00")
        g.cont()
        print(f"  compress ctM=10 ({ok}) t={self.now()}")

    def set_bit7(self, on):
        g = self.g
        g.interrupt()
        ea = u8(g, EAM)
        want = (ea | 0x80) if on else (ea & 0x7F)
        ok = g.send(f"M{EAM:x},1:{want:02x}")
        g.cont()
        got = u8(g, EAM)
        print(f"  eaM {ea:#04x} -> {got:#04x} ({ok}) t={self.now()}")
        return got


def pair_bursts_to_seeds(pbody, seeds, window=6.0):
    bursts = []
    for p in pbody:
        if bursts and p["t"] - bursts[-1]["t_end"] < 2.0:
            bursts[-1]["t_end"] = p["t"]
            bursts[-1]["hits"] += 1
        else:
            bursts.append({"t_start": p["t"], "t_end": p["t"], "hits": 1,
                           "name": p["name"], "ct": p["ct"],
                           "during": p["during"]})
    for b in bursts:
        after = [s for s in seeds if 0 <= s["t"] - b["t_end"] <= window]
        b["seed_after"] = after[0]["t"] if after else None
    return bursts


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    r = Run(g, pid)
    out = {}
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        n0, n1 = u32(g, SLOT0), u32(g, SLOT0 + STRIDE)
        print(f"slot0 name={n0:08x} (want {NAME_M:08x}), "
              f"slot1 name={n1:08x} (want {NAME1:08x})")
        if n0 != NAME_M or n1 != NAME1:
            print("fixture signature mismatch")
            return 1
        out["baseline"] = {
            "ct_m": u16(g, CTM), "ea_m": u8(g, EAM),
            "id_m": u8(g, IDM), "ed_m": u8(g, SLOT0 + 0xED),
            "e6_m": u8(g, SLOT0 + 0xE6), "dc_m": u8(g, SLOT0 + 0xDC),
            "cts": [u16(g, SLOT0 + STRIDE * s + 0xD0) for s in range(6)]}
        print(f"baseline: {out['baseline']}")
        r.cap("attach")
        assert g.send("M3000005,1:01") == "OK"

        # ---- WAKE: v27 marks + route ----------------------------------------
        g.interrupt()
        mid = u8(g, IDM)
        e6, dc, ea, ed = (u8(g, SLOT0 + 0xE6), u8(g, SLOT0 + 0xDC),
                          u8(g, SLOT0 + 0xEA), u8(g, SLOT0 + 0xED))
        for a, v in ((SLOT0 + 0xE6, mid), (SLOT0 + 0xDC, mid),
                     (SLOT0 + 0xED, ed | 8), (SLOT0 + 0xEA, ea | 0x80)):
            assert g.send(f"M{a:x},1:{v:02x}") == "OK"
        out["wake_marks"] = {"mid": mid, "e6": mid, "dc": mid,
                             "ed": ed | 8, "ea": ea | 0x80}
        print(f"wake marks written (mid={mid}) t={r.now()}")
        assert g.send(f"Z0,{BP_NORM:x},2") == "OK"
        g.cont()
        time.sleep(0.8)
        r.drive("wake1")
        r.pump(40.0, "wake1", sample_every=10.0, bps=("seed",))
        if not r.seeds:
            print("no seed after wake1; second drive pass")
            r.drive("wake2")
            r.pump(40.0, "wake2", sample_every=10.0, bps=("seed",))
        out["seeds_after_wake"] = len(r.seeds)
        out["wake_worked"] = len(r.seeds) > 0
        if not r.seeds:
            r.cap("wake-fail")
            r.sample("wake-fail")
            print("WAKE FAILED on both passes")

        # ---- CONTROL: bit7 clear, compressed Marche turn --------------------
        ctl = {"attempted": False}
        if r.seeds:
            g.interrupt()
            for bp in (BP_PBODY, BP_AI):
                assert g.send(f"Z0,{bp:x},2") == "OK"
            g.cont()
            ctl["attempted"] = True
            ctl["ea_after_clear"] = r.set_bit7(False)
            n0s = {"seeds": len(r.seeds), "pb": len(r.pbody)}
            r.compress()
            ctl["t"] = r.now()
            r.cap("control-start")
            r.pump(45.0, "control", sample_every=10.0,
                   bps=("seed", "pbody", "ai"))
            r.cap("control-end")
            ctl["pbody_bursts"] = pair_bursts_to_seeds(
                [p for p in r.pbody if p["t"] >= ctl["t"]],
                [s for s in r.seeds if s["t"] >= ctl["t"]])
            ctl["seeds_after"] = len(r.seeds) - n0s["seeds"]
            ctl["pbody_after"] = len(r.pbody) - n0s["pb"]
            marche = [b for b in ctl["pbody_bursts"]
                      if b["name"] == f"{NAME_M:08x}"]
            paired = [b for b in marche if b["seed_after"] is not None]
            ctl["marche_bursts"] = len(marche)
            ctl["verdict"] = (
                f"{len(paired)}/{len(marche)} Marche pbody bursts seed-paired"
                " => retail player turns DO ctx-init the sequencer"
                if paired else
                f"{len(marche)} Marche pbody bursts, none seed-paired; "
                f"bursts={ctl['pbody_bursts']}")
            print(f"CONTROL: {ctl['verdict']}")
        out["phase_control"] = ctl
        r.write_json = None
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)

        # ---- REVERSE: bit7 set, compressed Marche turn ----------------------
        rev = {"attempted": False}
        if ctl["attempted"] and u16(g, CTM) is not None:
            rev["attempted"] = True
            rev["ea_after_set"] = r.set_bit7(True)
            n0s = {"seeds": len(r.seeds), "pb": len(r.pbody),
                   "ai": len(r.ai)}
            r.compress()
            rev["t"] = r.now()
            r.cap("reverse-start")
            r.pump(45.0, "reverse", sample_every=10.0,
                   bps=("seed", "pbody", "ai"))
            r.cap("reverse-end")
            rev["bursts_after"] = pair_bursts_to_seeds(
                [p for p in r.pbody if p["t"] >= rev["t"]],
                [s for s in r.seeds if s["t"] >= rev["t"]])
            rev["seeds_after"] = len(r.seeds) - n0s["seeds"]
            rev["pbody_after"] = len(r.pbody) - n0s["pb"]
            rev["ai_after"] = len(r.ai) - n0s["ai"]
            mb = [b for b in rev["bursts_after"]
                  if b["name"] == f"{NAME_M:08x}"]
            rev["marche_bursts"] = len(mb)
            rev["verdict"] = (
                f"bit7 set: {len(mb)} Marche pbody bursts "
                f"(seed-paired: {sum(1 for b in mb if b['seed_after'])}), "
                f"ai={rev['ai_after']} seeds={rev['seeds_after']}"
                f" => bit7 turn still routes through pbody"
                if mb else
                f"bit7 set: NO Marche pbody bursts; ai={rev['ai_after']} "
                f"seeds={rev['seeds_after']} => bit7 reroutes away from pbody")
            print(f"REVERSE: {rev['verdict']}")
            r.set_bit7(False)   # restore natural (0)
        out["phase_reverse"] = rev

        g.interrupt()
        out["final"] = {"ct_m": u16(g, CTM), "ea_m": u8(g, EAM),
                        "cts": [u16(g, SLOT0 + STRIDE * s + 0xD0)
                                for s in range(6)]}
        for bp in (BP_NORM, BP_PBODY, BP_AI):
            g.send(f"z0,{bp:x},2")
        g.cont()
        time.sleep(0.5)
        r.cap("final")
        r.sample("final")
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
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
