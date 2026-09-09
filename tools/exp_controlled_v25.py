"""A2.3 v25: the complete Controlled-handout experiment with branch tracing.

Decoded this session (see docs update):
- Player-vs-AI per-unit branch after pick: +0xEA bit 7 (side bit) -> 0x0809E398
  player path; else AI path at 0x0809E2DA.
- ctx-init gate 0x080C1B2C (only consulted when flag0D 0x0200203D != 0):
  grants a normal phase-9 turn to a unit that CONTROLS someone
  (0x080970E8 finds units with +0xDC == unit id among Controlled-marked
  units, best position wins), else falls back to IWRAM 0x030028A0 bit 3
  (player-control mode). Gate==0 routes the turn into the displacement
  chain 0xB -> 11 -> 12 -> 13 (v22's freeze).
- Control mark = +0xED bit 3 with controller id at +0xE6 and duration at
  +0xDC (0x080CE410); pick loop clears the mark at 0x0809E272.

Recipe under test: slot0 gets +0xE6=6 (Marche), +0xDC=6, +0xED|=8,
+0xEA|=0x80 (player-side bit); flag0D=1; IWRAM 0x030028A0 |= 8.
Breakpoints: 0x080C03B4 (0xB seed), 0x080C03C2 (normal seed),
0x0809E398 (player pick path). Keys are injected mid-run to test menu
response; captures classify the screen.

Usage: python tools/exp_controlled_v25.py  (fixture must be booted with -t)
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
FLAG0D = 0x0200203D
IWRAM_MODE = 0x030028A0
BP_0B = 0x080C03B4        # strh 0xB -> displacement route seeded
BP_NORM = 0x080C03C2      # normal (phase-9 family) route
BP_PLAYER = 0x0809E398    # player-side pick path
OUT_JSON = "outputs/lua-nav/controlled-v25.json"

BP_NAMES = {BP_0B: "0xB-seed", BP_NORM: "normal-seed", BP_PLAYER: "player-path"}


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def window_capture(pid, path):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=45)
    print(f"  capture {path}: {'ok' if r.returncode == 0 else 'FAIL'}")


def rd(g, a, n):
    d = g.read_mem(a, n)
    return d.hex() if d else None


def u8(g, a):
    d = g.read_mem(a, 1)
    return d[0] if d else None


def u16(g, a):
    d = g.read_mem(a, 2)
    return int.from_bytes(d, "little") if d else None


def dump_slots(g, tag):
    row = {}
    for i in range(7):
        base = SLOT0 + STRIDE * i
        row[i] = {
            "e6": u8(g, base + 0xE6), "dc": u8(g, base + 0xDC),
            "ea": u8(g, base + 0xEA), "ed": u8(g, base + 0xED),
            "id104": u8(g, base + 0x104), "ct": u16(g, base + 0xD0),
        }
    print(f"  [{tag}] " + " ".join(
        f"s{i}(id{r['id104']},e6={r['e6']},dc={r['dc']},ea={r['ea']:02x},"
        f"ed={r['ed']:02x},ct={r['ct']})" for i, r in row.items()))
    return row


def press(g, mask, frames=4, pause=1.0, tag=""):
    hits = 0
    try:
        if g.send(f"Z0,{KEY_BL:x},2") != "OK":
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
    finally:
        try:
            g.send(f"z0,{KEY_BL:x},2")
            g.cont()
        except Exception:
            pass
    time.sleep(pause)
    print(f"  key {mask:#04x} x{hits} {tag}")
    return hits


def main():
    pid = mgba_pid()
    if not pid:
        print("no mGBA process")
        return 1
    print(f"mGBA pid {pid}")
    out = {}
    g = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        # NOTE: never send "?" first — on a running/halted CPU it can hang and
        # the abandoned exchange poisons mGBA's single-connection stub.
        stop = g.interrupt()
        print(f"GDB attached; stop={stop}")

        # -- baseline ---------------------------------------------------------
        out["baseline"] = dump_slots(g, "baseline")
        out["baseline"]["flag0D"] = u8(g, FLAG0D)
        out["baseline"]["iwram_mode"] = u8(g, IWRAM_MODE)
        print(f"  flag0D={out['baseline']['flag0D']} "
              f"iwram[{IWRAM_MODE:#x}]={out['baseline']['iwram_mode']:#04x}")

        # -- writes: marks + flag0D + player-mode bit --------------------------
        mid = u8(g, SLOT0 + STRIDE * 6 + 0x104)  # Marche id
        e6 = u8(g, SLOT0 + 0xE6)
        dc = u8(g, SLOT0 + 0xDC)
        ea = u8(g, SLOT0 + 0xEA)
        ed = u8(g, SLOT0 + 0xED)
        assert g.send(f"M{SLOT0 + 0xE6:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xDC:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xED:x},1:{ed | 8:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xEA:x},1:{ea | 0x80:02x}") == "OK"
        assert g.send(f"M{FLAG0D:x},1:01") == "OK"
        im = u8(g, IWRAM_MODE)
        assert g.send(f"M{IWRAM_MODE:x},1:{im | 8:02x}") == "OK"
        out["written"] = {
            "marche_id": mid, "s0.e6": u8(g, SLOT0 + 0xE6),
            "s0.dc": u8(g, SLOT0 + 0xDC), "s0.ea": u8(g, SLOT0 + 0xEA),
            "s0.ed": u8(g, SLOT0 + 0xED), "flag0D": u8(g, FLAG0D),
            "iwram_mode": u8(g, IWRAM_MODE),
        }
        print(f"  written: {out['written']}")

        # -- branch-trace BPs ---------------------------------------------------
        for bp in (BP_0B, BP_NORM, BP_PLAYER):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        g.cont()

        events = []
        samples = []
        t0 = time.time()
        last_sample = 0.0
        keys_done = False
        g.sock.settimeout(2.0)
        while time.time() - t0 < 75:
            stop = None
            try:
                g.cont()
                stop = g._read_packet()
            except Exception:
                stop = None
            now = time.time() - t0
            if stop and stop[:1] in ("S", "T"):
                regs = g.read_registers()
                pc = regs[15] if regs else 0
                name = BP_NAMES.get(pc)
                if name:
                    ev = {"t": round(now, 1), "bp": name,
                          "r0": f"{regs[0]:08x}", "r1": f"{regs[1]:08x}",
                          "r4": f"{regs[4]:08x}", "r5": f"{regs[5]:08x}"}
                    events.append(ev)
                    print(f"  HIT {name} t={ev['t']} r0={ev['r0']} "
                          f"r1={ev['r1']} r4={ev['r4']} r5={ev['r5']}")
                    if len(events) == 1:
                        window_capture(pid, "outputs/lua-nav/v25-first-branch.png")
                    continue
            # timeout: sample state (interrupt briefly)
            if now - last_sample >= 6.0:
                try:
                    g.interrupt()
                    row = dump_slots(g, f"t+{now:.0f}s")
                    row["flag0D"] = u8(g, FLAG0D)
                    row["iwram_mode"] = u8(g, IWRAM_MODE)
                    samples.append({"t": round(now, 1), "slots": {
                        str(k): v for k, v in row.items()}})
                    window_capture(pid, f"outputs/lua-nav/v25-t{now:.0f}.png")
                    last_sample = now
                    g.cont()
                except Exception as exc:
                    print(f"  sample fail: {exc}")
                    g.cont()
            # once the round has had time to reach slot0, test the menu
            if not keys_done and now > 40:
                keys_done = True
                window_capture(pid, "outputs/lua-nav/v25-prekey.png")
                for mask, tag in [(0x80, "DOWN"), (0x01, "A")]:
                    press(g, mask, 4, tag=tag)
                window_capture(pid, "outputs/lua-nav/v25-postkey.png")

        for bp in (BP_0B, BP_NORM, BP_PLAYER):
            g.send(f"z0,{bp:x},2")
        out["events"] = events
        out["samples"] = samples
        g.interrupt()
        out["final"] = dump_slots(g, "final")
        out["final"]["flag0D"] = u8(g, FLAG0D)
        out["final"]["iwram_mode"] = u8(g, IWRAM_MODE)
        g.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/v25-final.png")
        out["n_0b"] = sum(1 for e in events if e["bp"] == "0xB-seed")
        out["n_norm"] = sum(1 for e in events if e["bp"] == "normal-seed")
        out["n_player"] = sum(1 for e in events if e["bp"] == "player-path")
        print(f"branch counts: 0xB={out['n_0b']} normal={out['n_norm']} "
              f"player={out['n_player']}")
        with open(OUT_JSON, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"wrote {OUT_JSON}")
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
