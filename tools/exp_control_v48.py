"""A2.3 v48: per-hit register truth + ctx actor scan + enemy-bit7 reverse test.

v47 verdicts and their gaps:
- WAKE (marks+drive) works: 6 seeds, full self-play round. SOLVED.
- Seed t=7.3 fired 0.3 s after Marche's A-ok commit => retail player turn
  DOES ctx-init the sequencer (needs ctx actor scan to confirm attribution).
- Control phase wedged: Marche's compressed turn opened his menu with
  enable=0 -> frozen. The pbody hits carried ct=1000 + scratch 0x02016018
  => the pbody scan runs over TURN records (copies), and the auto-battler
  sets ea bit7 transiently on them (allies hit pbody with roster ea=0).
- sub_080CDADC = (rec+0xEA)&0x80 exactly; router: bit7 -> player body.
  => "reverse handout" as Marche-bit7 is a category error: bit7=1 routes
  TO the menu body (that is the forward handout). The open reverse test is
  bit7 on an ENEMY: does its turn switch to menu navigation?

v48 protocol:
  1. attach; verify signatures; enable=1.
  2. WAKE: v27 marks on slot0 (Marche) + drive route; watch for seeds.
  3. CONTROL: Marche bit7=0 (natural), CT=10, watch 40 s (idle auto-commit
     expected ~16 s with enable=1); if wedged (no new seed), drive as
     fallback. Every pbody/ai/seed hit logs r4, [r4] name, ct, ea, r7.
     Seeds scan ctx [r4-0x90, r4+0x10) for 0x02015xxx unit pointers.
  4. REVERSE: set bit7 on slot1 (enemy id=1), CT=10, watch 40 s: does its
     turn produce pbody (menu navigation) instead of a bare seed?
  5. restore slot1 bit7, final capture, JSON.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v48.py
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
NAME_M = 0x085671EE          # slot0 (Marche)
NAME1 = 0x0856702F           # slot1 (enemy; boot signature)
SLOT1 = SLOT0 + STRIDE
EAM = SLOT0 + 0xEA
CTM = SLOT0 + 0xD0
EA1 = SLOT1 + 0xEA
CT1 = SLOT1 + 0xD0
IDM = SLOT0 + 0x104
KEY_BL = 0x08000494
BP_NORM = 0x080C03C2
BP_PBODY = 0x0809E796
BP_AI = 0x0809E2DA
BP_NAMES = {BP_NORM: "seed", BP_PBODY: "pbody", BP_AI: "ai"}
OUT = "outputs/lua-nav/controlled-v48.json"
ROUTE = [(0x80, "DOWN1"), (0x80, "DOWN2"), (0x01, "A-wait"), (0x01, "A-ok")]
ROSTER_LO, ROSTER_HI = 0x02015900, 0x02016100


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
        self.cap_i = 0

    def now(self):
        return round(time.time() - self.t0, 1)

    def cap(self, tag):
        if not self.pid:
            return
        self.cap_i += 1
        p = f"outputs/lua-nav/v48-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)

    def sample(self, tag):
        g = self.g
        s = {"t": self.now(), "tag": tag,
             "ct_m": u16(g, CTM), "ea_m": u8(g, EAM),
             "ct_1": u16(g, CT1), "ea_1": u8(g, EA1),
             "cts": [u16(g, SLOT0 + STRIDE * i + 0xD0) for i in range(6)]}
        self.samples.append(s)
        print(f"  [t={s['t']} {tag}] ctM={s['ct_m']} ct1={s['ct_1']} "
              f"eaM={s['ea_m']:#04x} ea1={s['ea_1']:#04x} "
              f"cts={s['cts']} seeds={len(self.seeds)} pb={len(self.pbody)} "
              f"ai={len(self.ai)}")
        return s

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
                    try:
                        self.handle_stop(f"press:{tag}")
                    except Exception:
                        pass
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

    def scan_ctx(self, r4):
        """Scan ctx around r4 for roster unit pointers (actor attribution)."""
        g = self.g
        lo, hi = r4 - 0x90, r4 + 0x10
        blob = g.read_mem(lo, hi - lo)
        hits = []
        if blob:
            for off in range(0, len(blob) - 3, 4):
                v = int.from_bytes(blob[off:off + 4], "little")
                if ROSTER_LO <= v <= ROSTER_HI:
                    hits.append({"off": lo + off - r4, "v": f"{v:08x}"})
        return hits

    def handle_stop(self, during=None):
        g = self.g
        regs = g.read_registers()
        if not regs:
            return None
        pc = regs[15]
        name = BP_NAMES.get(pc)
        t = self.now()
        r7 = regs[7]
        if name == "pbody":
            r4 = regs[4]
            nm = u32(g, r4) if r4 else None
            ct = u16(g, r4 + 0xD0) if r4 else None
            ea = u8(g, r4 + 0xEA) if r4 else None
            roster = nm and ROSTER_LO <= (r4 & ~0xFF) < ROSTER_HI
            self.pbody.append({"t": t, "r4": f"{r4:08x}",
                               "name": f"{nm:08x}" if nm else None,
                               "ct": ct, "ea": ea, "r7": f"{r7:08x}",
                               "roster_addr": bool(roster),
                               "during": during})
            if len(self.pbody) <= 6 or len(self.pbody) % 20 == 0:
                print(f"  PBODY t={t} r4={r4:08x} nm={nm and hex(nm)} "
                      f"ct={ct} ea={ea and hex(ea)} r7={r7:08x} {during}")
        elif name == "ai":
            self.ai.append({"t": t, "r4": f"{regs[4]:08x}",
                            "r7": f"{r7:08x}", "during": during})
            if len(self.ai) <= 4:
                print(f"  AI t={t} r4={regs[4]:08x} r7={r7:08x} {during}")
        elif name == "seed":
            r4 = regs[4]
            hits = self.scan_ctx(r4) if r4 else []
            self.seeds.append({"t": t, "r4": f"{r4:08x}",
                               "r7": f"{r7:08x}", "ctx_units": hits,
                               "during": during})
            print(f"  SEED t={t} r4={r4:08x} ctx_units={hits} {during}")
        return regs

    def pump(self, seconds, during=None, sample_every=8.0, tick=2.0):
        """Free pump with an interrupt-driven sample tick so quiet periods
        still produce CT/ea samples."""
        g = self.g
        end = time.time() + seconds
        last_s = self.now()
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
                try:
                    self.handle_stop(during)
                except Exception as e:
                    print(f"  handle_stop error: {e}")
            if self.now() - last_s >= tick:
                try:
                    g.interrupt()
                except Exception:
                    pass
                if self.now() - last_s >= sample_every:
                    last_s = self.now()
                    self.sample(during or "watch")

    def write_mem_byte(self, addr, val):
        g = self.g
        g.interrupt()
        ok = g.send(f"M{addr:x},1:{val:02x}")
        g.cont()
        return ok

    def set_bit(self, addr, on, bit=0x80):
        g = self.g
        g.interrupt()
        cur = u8(g, addr) or 0
        want = (cur | bit) if on else (cur & ~bit & 0xFF)
        ok = g.send(f"M{addr:x},1:{want:02x}")
        g.cont()
        got = u8(g, addr)
        print(f"  [{addr:08X}] {cur:#04x} -> {got:#04x} ({ok}) t={self.now()}")
        return got

    def compress(self, addr):
        g = self.g
        g.interrupt()
        ok = g.send(f"M{addr:x},2:0a00")
        g.cont()
        print(f"  compress [{addr:08X}]=10 ({ok}) t={self.now()}")


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    r = Run(g, pid)
    out = {}
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        n0, n1 = u32(g, SLOT0), u32(g, SLOT1)
        print(f"slot0 name={n0:08x} (want {NAME_M:08x}) "
              f"slot1 name={n1:08x} (want {NAME1:08x})")
        if n0 != NAME_M or n1 != NAME1:
            print("fixture signature mismatch")
            return 1
        out["baseline"] = {
            "ct_m": u16(g, CTM), "ea_m": u8(g, EAM),
            "ct_1": u16(g, CT1), "ea_1": u8(g, EA1),
            "id_m": u8(g, IDM),
            "cts": [u16(g, SLOT0 + STRIDE * i + 0xD0) for i in range(6)]}
        print(f"baseline: {out['baseline']}")
        r.cap("attach")
        assert g.send("M3000005,1:01") == "OK"
        for bp in (BP_NORM, BP_PBODY, BP_AI):
            assert g.send(f"Z0,{bp:x},2") == "OK"

        # ---- WAKE: v27 marks + route ----------------------------------------
        g.interrupt()
        mid = u8(g, IDM)
        e6, dc = u8(g, SLOT0 + 0xE6), u8(g, SLOT0 + 0xDC)
        ed, ea = u8(g, SLOT0 + 0xED), u8(g, SLOT0 + 0xEA)
        for a, v in ((SLOT0 + 0xE6, mid), (SLOT0 + 0xDC, mid),
                     (SLOT0 + 0xED, ed | 8), (SLOT0 + 0xEA, ea | 0x80)):
            assert g.send(f"M{a:x},1:{v:02x}") == "OK"
        out["wake_marks"] = {"mid": mid, "ed|8": ed | 8, "ea|80": ea | 0x80}
        print(f"wake marks written t={r.now()}")
        g.cont()
        time.sleep(0.8)
        r.drive("wake1")
        r.pump(35.0, "wake1")
        if len(r.seeds) < 2:
            r.drive("wake2")
            r.pump(35.0, "wake2")
        out["seeds_after_wake"] = len(r.seeds)
        out["wake_ok"] = len(r.seeds) >= 2
        print(f"wake: seeds={len(r.seeds)} pb={len(r.pbody)} "
              f"ai={len(r.ai)} t={r.now()}")

        # ---- CONTROL: natural Marche auto turn ------------------------------
        ctl = {"attempted": False}
        if out["wake_ok"]:
            ctl["attempted"] = True
            r.set_bit(EAM, False)          # bit7 clear (natural)
            n0s = {"seeds": len(r.seeds), "pb": len(r.pbody),
                   "ai": len(r.ai)}
            r.compress(CTM)
            ctl["t"] = r.now()
            r.cap("control-start")
            r.pump(40.0, "control")
            new_seeds = len(r.seeds) - n0s["seeds"]
            if new_seeds == 0:             # wedged? drive fallback
                print("  control wedged; drive fallback")
                r.drive("ctl-drive")
                r.pump(30.0, "control-fb")
            ctl["seeds_after"] = len(r.seeds) - n0s["seeds"]
            ctl["pb_after"] = len(r.pbody) - n0s["pb"]
            ctl["ai_after"] = len(r.ai) - n0s["ai"]
            # seeds during control with roster ctx units:
            ctl["seeds_detail"] = [s for s in r.seeds
                                   if s["t"] >= ctl["t"] and s["ctx_units"]]
            print(f"CONTROL: seeds={ctl['seeds_after']} pb={ctl['pb_after']} "
                  f"ai={ctl['ai_after']} attributed={len(ctl['seeds_detail'])}")
        out["phase_control"] = ctl

        # ---- REVERSE: enemy bit7 --------------------------------------------
        rev = {"attempted": False}
        if out["wake_ok"] and u16(g, CT1) is not None:
            rev["attempted"] = True
            rev["ea1_after_set"] = r.set_bit(EA1, True)
            n0s = {"seeds": len(r.seeds), "pb": len(r.pbody),
                   "ai": len(r.ai)}
            r.compress(CT1)
            rev["t"] = r.now()
            r.cap("reverse-start")
            r.pump(40.0, "reverse")
            new_seeds = len(r.seeds) - n0s["seeds"]
            if new_seeds == 0:
                print("  reverse quiet; drive fallback (menu may be open)")
                r.drive("rev-drive")
                r.pump(30.0, "reverse-fb")
            rev["seeds_after"] = len(r.seeds) - n0s["seeds"]
            rev["pb_after"] = len(r.pbody) - n0s["pb"]
            rev["ai_after"] = len(r.ai) - n0s["ai"]
            # pbody hits during reverse carrying slot1's name:
            rev["pb_slot1"] = [p for p in r.pbody
                               if p["t"] >= rev["t"]
                               and p["name"] == f"{NAME1:08x}"]
            rev["seeds_slot1"] = [s for s in r.seeds
                                  if s["t"] >= rev["t"]
                                  and any(h["v"] == f"{SLOT1:08x}"
                                          for h in s["ctx_units"])]
            rev["verdict"] = (
                f"slot1 bit7=1: {len(rev['pb_slot1'])} pbody hits with "
                f"slot1 name, {len(rev['seeds_slot1'])} slot1-attributed "
                f"seeds => menu-body routing {'ON' if rev['pb_slot1'] else 'OFF'}"
                ) if (rev["pb_slot1"] or rev["seeds_slot1"]) else \
                f"slot1 bit7=1: no slot1 turn observed in window"
            print(f"REVERSE: {rev['verdict']}")
            r.set_bit(EA1, False)
        out["phase_reverse"] = rev

        g.interrupt()
        out["final"] = {"ct_m": u16(g, CTM), "ea_m": u8(g, EAM),
                        "ct_1": u16(g, CT1), "ea_1": u8(g, EA1),
                        "cts": [u16(g, SLOT0 + STRIDE * i + 0xD0)
                                for i in range(6)]}
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
