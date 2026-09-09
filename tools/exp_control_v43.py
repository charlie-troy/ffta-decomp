"""A2.3 v43: v27's flow + ctx-init caller identification + second drive pass.

Open questions this run settles:
1. The 3 deterministic seeds (t~4.6/14/23.8 across boots) fire only after
   presses — which sequence step calls the ctx-init each time? BP at the
   ctx-init wrapper 0x080C144C captures lr (the higher caller) at each hit.
2. Today's v27 ended with CTs frozen + a text overlay. Does a SECOND drive
   pass (after the first) reach the real menu and commit? (Session-8's
   'committed' verdict used ct6!=0, but frozen CTs show that signal is
   ambiguous.)
3. Do real unit turns (picks + seeds) eventually run, and does Marche's
   commit show as ct6>0 WHILE pick-loop activity continues?

Flow: v27's writes (slot0 e6/dc/ed marks, ea|=0x80), enable=1, drive pass 1
(DOWN DOWN A A), watch 70 s with wrapper/seed/pick BPs + CT samples every
10 s; then drive pass 2 (same route), watch 70 s more; JSON.

Usage: python tools/boot_fixture_gdb.py && python tools/exp_control_v43.py
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
BP_WRAP = 0x080C144C       # ctx-init wrapper entry (lr = higher caller)
BP_NORM = 0x080C03C2       # sequencer normal seed
BP_PICK = 0x0809E260       # per-turn pick (r0 = actor)
BP_NAMES = {BP_WRAP: "wrap", BP_NORM: "seed", BP_PICK: "pick"}
OUT = "outputs/lua-nav/controlled-v43.json"
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
        p = f"outputs/lua-nav/v43-{self.cap_i:02d}-{tag}.png"
        window_capture(self.pid, p)
        return p

    def live(self):
        name0 = int.from_bytes(self.g.read_mem(NAME0, 4) or b"\0\0\0\0",
                               "little")
        return (name0 & 0xFF000000) == 0x08000000

    def log_stop(self, pc, regs, during=None):
        if pc == BP_WRAP:
            self.wraps.append({"t": self.now(), "lr": regs[14],
                               "r0": regs[0], "during": during})
            print(f"  WRAP t={self.now()} lr={regs[14]:08x} "
                  f"r0={regs[0]:08x}")
        elif pc == BP_NORM:
            self.seeds.append({"t": self.now(), "r4": regs[4],
                               "r7": regs[7], "during": during})
            print(f"  SEED t={self.now()} r4={regs[4]:08x} r7={regs[7]:08x}")
        elif pc == BP_PICK:
            rec = {"t": self.now(), "actor": regs[0], "ea6": self.u8(EA6)}
            self.picks.append(rec)
            last = self.picks[-2] if len(self.picks) >= 2 else None
            if not last or last["actor"] != rec["actor"] \
                    or rec["t"] - last["t"] > 1.0:
                print(f"  PICK t={rec['t']} actor={rec['actor']} "
                      f"ea6={rec['ea6']:#04x}")

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
        print(f"  key {mask:#04x} x{hits} {tag} (t={self.now()})")
        return hits

    def pump(self, seconds, during=None, sample_every=10.0):
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
                row = {"t": self.now(), "ct6": self.u16(CT6)}
                # all CTs
                cts = []
                for slot in range(7):
                    cts.append(self.u16(SLOT0 + STRIDE * slot + 0xD0))
                row["cts"] = cts
                self.samples.append(row)
                print(f"  [t={self.now()}] ct6={row['ct6']} cts={cts} "
                      f"wraps={len(self.wraps)} seeds={len(self.seeds)} "
                      f"picks={len(self.picks)}")

    def drive(self, tag):
        for mask, name in ROUTE:
            self.press(mask, f"{tag}:{name}")


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
        # v27's writes on slot0
        mid = r.u8(SLOT6 + 0x104)
        e6 = r.u8(SLOT0 + 0xE6)
        dc = r.u8(SLOT0 + 0xDC)
        ed = r.u8(SLOT0 + 0xED)
        ea = r.u8(SLOT0 + 0xEA)
        assert g.send(f"M{SLOT0 + 0xE6:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xDC:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xED:x},1:{ed | 8:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xEA:x},1:{ea | 0x80:02x}") == "OK"
        out["written"] = {"mid": mid, "e6": mid, "dc": mid,
                          "ed": ed | 8, "ea": ea | 0x80}
        print(f"v27 writes done: {out['written']}")
        for bp in (BP_WRAP, BP_NORM, BP_PICK):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        assert g.send("M3000005,1:01") == "OK"
        g.cont()

        # ---- pass 1 -----------------------------------------------------------
        time.sleep(0.5)
        r.drive("pass1")
        r.pump(70.0, "watch1", sample_every=10.0)
        p = r.cap("after-pass1")
        print(f"pass1 done: wraps={len(r.wraps)} seeds={len(r.seeds)} "
              f"picks={len(r.picks)} ct6={r.u16(CT6)}")

        # ---- pass 2 ------------------------------------------------------------
        if not r.exited:
            r.drive("pass2")
            r.pump(70.0, "watch2", sample_every=10.0)
            r.cap("after-pass2")
            print(f"pass2 done: wraps={len(r.wraps)} seeds={len(r.seeds)} "
                  f"picks={len(r.picks)} ct6={r.u16(CT6)}")

        # ---- verdicts ------------------------------------------------------------
        out["wraps"] = r.wraps
        out["seeds"] = r.seeds
        out["picks"] = r.picks
        out["samples"] = r.samples
        lrs = sorted({f"{w['lr']:08x}" for w in r.wraps})
        out["verdict_callers"] = (f"ctx-init wrapper callers (lr): {lrs}"
                                  if lrs else "wrapper never hit")
        print(f"callers: {out['verdict_callers']}")
        marche_seeds_after_drive = [s for s in r.seeds if s["t"] > 8.0]
        out["verdict_seeds"] = (
            f"{len(marche_seeds_after_drive)} seeds after the drive; "
            f"times: {[s['t'] for s in marche_seeds_after_drive]}")
        print(f"seeds: {out['verdict_seeds']}")

        # restore
        g.interrupt()
        ea2 = r.u8(SLOT0 + 0xEA)
        assert g.send(f"M{SLOT0 + 0xEA:x},1:{ea2 & 0x7F:02x}") == "OK"
        out["restored_ea"] = r.u8(SLOT0 + 0xEA)
        out["final"] = {"ct6": r.u16(CT6), "live": r.live(),
                        "battle_exited": r.exited}
        for bp in (BP_WRAP, BP_NORM, BP_PICK):
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
