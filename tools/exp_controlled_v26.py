"""A2.3 v26: full-retail Controlled-handout test with the complete menu route.

v25 lesson: pressing only DOWN+A leaves Marche's menu open (round waits, CTs
frozen — normal FFTA behavior). v26 performs the proven A1 sequence
DOWN x2 -> A x2 (Wait + facing confirm) to actually end Marche's turn, then
watches the sequencer branch points while the round plays out:

  expected timeline with the handout writes applied
  (slot0: +0xE6=6 controller, +0xDC=6 duration, +0xED|=8 mark, +0xEA|=0x80
   side bit; flag0D=1; IWRAM 0x030028A0|=8):
  - five enemy turns (ctx inits hit 'normal-seed' per the 0x080C1B2C gate,
    since flag0D!=0 and IWRAM bit3 grants the normal route)
  - then slot0's turn: if the side bit routes the pick to the player path
    (0x0809E398), a player menu opens on the enemy unit.

Boot protocol (hard-won): instance 1 boot = -g -t fixture; connection 1 sends
a bare framed 'c' (un-pauses the paused -g boot); the experiment connects as
connection 2 (interrupt returns a real stop; cont() actually runs).

Usage: python tools/exp_controlled_v26.py
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
OUT_JSON = "outputs/lua-nav/controlled-v26.json"

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
        f"s{i}(ct={r['ct']},e6={r['e6']},ed={r['ed']:02x},ea={r['ea']:02x})"
        for i, r in row.items()))
    return row


def press(g, pid, mask, frames=5, pause=1.2, tag=""):
    """Inject one key press; tolerate/tolerate-and-log unexpected BP stops."""
    hits = 0
    extra = []
    try:
        if g.send(f"Z0,{KEY_BL:x},2") != "OK":
            print(f"  FAIL: KEY_BL BP rejected ({tag})")
            return 0, extra
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
            elif regs:
                extra.append(regs[15])
                if BP_NAMES.get(regs[15]):
                    print(f"  (ctx BP {BP_NAMES[regs[15]]} during key {tag})")
                break
    finally:
        try:
            g.send(f"z0,{KEY_BL:x},2")
            g.cont()
        except Exception:
            pass
    time.sleep(pause)
    print(f"  key {mask:#04x} x{hits} {tag}"
          + (f" extra={ [hex(p) for p in extra]}" if extra else ""))
    return hits, extra


def watch(g, pid, seconds, events, samples):
    """Watch branch points, sampling slots periodically. CPU keeps running."""
    t0 = time.time()
    last_sample = 0.0
    g.sock.settimeout(3.0)
    while time.time() - t0 < seconds:
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
                      "r0": f"{regs[0]:08x}", "r4": f"{regs[4]:08x}"}
                events.append(ev)
                print(f"  HIT {name} t={ev['t']} r0={ev['r0']} r4={ev['r4']}")
                if sum(1 for e in events if e["bp"] == name) == 1:
                    window_capture(pid, f"outputs/lua-nav/v26-first-{name}.png")
                continue
        if now - last_sample >= 8.0:
            try:
                g.interrupt()
                dump_slots(g, f"t+{now:.0f}s")
                samples.append(round(now, 1))
                last_sample = now
            except Exception as exc:
                print(f"  sample fail: {exc}")
    # leave halted for final dump
    g.interrupt()


def main():
    pid = mgba_pid()
    if not pid:
        print("no mGBA process")
        return 1
    print(f"mGBA pid {pid}")
    out = {}
    g = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        stop = g.interrupt()
        print(f"GDB attached; stop={stop}")
        out["baseline"] = dump_slots(g, "baseline")
        out["baseline_flag0D"] = u8(g, FLAG0D)
        out["baseline_iwram"] = u8(g, IWRAM_MODE)

        # -- writes ------------------------------------------------------------
        mid = u8(g, SLOT0 + STRIDE * 6 + 0x104)
        e6 = u8(g, SLOT0 + 0xE6)
        dc = u8(g, SLOT0 + 0xDC)
        ea = u8(g, SLOT0 + 0xEA)
        ed = u8(g, SLOT0 + 0xED)
        im = u8(g, IWRAM_MODE)
        assert g.send(f"M{SLOT0 + 0xE6:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xDC:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xED:x},1:{ed | 8:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xEA:x},1:{ea | 0x80:02x}") == "OK"
        assert g.send(f"M{FLAG0D:x},1:01") == "OK"
        assert g.send(f"M{IWRAM_MODE:x},1:{im | 8:02x}") == "OK"
        out["written"] = {
            "marche_id": mid, "s0.e6": u8(g, SLOT0 + 0xE6),
            "s0.dc": u8(g, SLOT0 + 0xDC), "s0.ea": u8(g, SLOT0 + 0xEA),
            "s0.ed": u8(g, SLOT0 + 0xED), "flag0D": u8(g, FLAG0D),
            "iwram_mode": u8(g, IWRAM_MODE),
        }
        print(f"  written: {out['written']}")

        # -- arm ctx BPs BEFORE the turn ends -----------------------------------
        for bp in (BP_0B, BP_NORM, BP_PLAYER):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"

        # -- end Marche's turn: DOWN x2, A x2 ------------------------------------
        g.cont()
        time.sleep(0.8)
        window_capture(pid, "outputs/lua-nav/v26-0-menu.png")
        for mask, tag in [(0x80, "DOWN1"), (0x80, "DOWN2"),
                          (0x01, "A-wait"), (0x01, "A-confirm")]:
            press(g, pid, mask, 5, tag=tag)
        window_capture(pid, "outputs/lua-nav/v26-1-committed.png")

        # -- watch the round: enemies act, then slot0 ----------------------------
        events, samples = [], []
        watch(g, pid, 100, events, samples)
        for bp in (BP_0B, BP_NORM, BP_PLAYER):
            g.send(f"z0,{bp:x},2")
        out["events"] = events
        out["n_0b"] = sum(1 for e in events if e["bp"] == "0xB-seed")
        out["n_norm"] = sum(1 for e in events if e["bp"] == "normal-seed")
        out["n_player"] = sum(1 for e in events if e["bp"] == "player-path")
        out["final"] = dump_slots(g, "final")
        out["final"]["flag0D"] = u8(g, FLAG0D)
        out["final"]["iwram_mode"] = u8(g, IWRAM_MODE)
        g.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/v26-final.png")
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
