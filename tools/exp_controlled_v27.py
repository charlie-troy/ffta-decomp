"""A2.3 v27: the pick-side handout — marks + player-side bit, no flag0D.

Session decode (v22/v25/v26 evidence):
- flag0D (0x0200203D) is a TRANSIENT init flag: with it set, every unit whose
  class byte (0x0809AA10) != 0 routes its whole turn into the displacement
  chain 0xB->11->12->13, which deadlocks on a zero queued target (v22/v26
  freeze). It must stay 0. The ctx-init gate 0x080C1B2C is only consulted
  when flag0D != 0.
- The real player/AI branch is at the PICK: sub_0809E1E0 returns the chosen
  slot; the loop tests +0xEA bit 7 (0x080CDADC) — set -> player path
  0x0809E398, clear -> AI path 0x0809E2DA.
- Control marks: +0xED bit 3, controller id +0xE6, duration +0xDC (cleared
  each pick via 0x080CE2F0; duration decremented via 0x080CE3C0/0x080CE050).

v27 writes on slot0: +0xE6=6 (Marche), +0xDC=6, +0xED|=8, +0xEA|=0x80.
flag0D and IWRAM stay untouched. Then Marche's turn is ended with the
proven menu route (DOWN x2, A x2) and the round is watched through the
three branch points. Expected: normal-seed fires for every unit turn
(~6-7), 0xB never, player-path fires when slot0's turn arrives (~second
position, CT 45), and the screen shows the player command menu on the
enemy unit.

Usage: python tools/exp_controlled_v27.py
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
BP_0B = 0x080C03B4        # displacement seed (should NOT fire)
BP_NORM = 0x080C03C2      # normal seed (every unit turn)
BP_PLAYER = 0x0809E398    # player pick path (the handout)
BP_AI = 0x0809E2DA        # AI pick path
OUT_JSON = "outputs/lua-nav/controlled-v27.json"

BP_NAMES = {BP_0B: "0xB-seed", BP_NORM: "normal-seed",
            BP_PLAYER: "player-path", BP_AI: "ai-path"}


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
            "ct": u16(g, base + 0xD0),
        }
    print(f"  [{tag}] " + " ".join(
        f"s{i}(ct={r['ct']},e6={r['e6']},dc={r['dc']},"
        f"ed={r['ed']:02x},ea={r['ea']:02x})" for i, r in row.items()))
    return row


def press(g, pid, mask, frames=5, pause=1.2, tag=""):
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
                print(f"  (BP {BP_NAMES[regs[15]]} during key {tag}; "
                      f"continuing)")
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
        stop = g.interrupt()
        print(f"GDB attached; stop={stop}")
        out["baseline"] = dump_slots(g, "baseline")
        out["baseline_flag0D"] = u8(g, FLAG0D)

        # -- writes: marks + side bit + duration ONLY ---------------------------
        mid = u8(g, SLOT0 + STRIDE * 6 + 0x104)
        e6 = u8(g, SLOT0 + 0xE6)
        dc = u8(g, SLOT0 + 0xDC)
        ea = u8(g, SLOT0 + 0xEA)
        ed = u8(g, SLOT0 + 0xED)
        assert g.send(f"M{SLOT0 + 0xE6:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xDC:x},1:{mid:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xED:x},1:{ed | 8:02x}") == "OK"
        assert g.send(f"M{SLOT0 + 0xEA:x},1:{ea | 0x80:02x}") == "OK"
        out["written"] = {
            "marche_id": mid, "s0.e6": u8(g, SLOT0 + 0xE6),
            "s0.dc": u8(g, SLOT0 + 0xDC), "s0.ea": u8(g, SLOT0 + 0xEA),
            "s0.ed": u8(g, SLOT0 + 0xED), "flag0D": u8(g, FLAG0D),
        }
        print(f"  written: {out['written']}")

        # -- arm BPs, end Marche's turn ------------------------------------------
        # FFTA's idle timer disables menu input (key struct +5 enable=0) after
        # ~16 s with the menu open and no keys — which the boot+bootstrap wait
        # always exceeds. Re-enable input right before driving the menu.
        ks = g.read_mem(0x03000000, 8)
        out["keystruct_at_attach"] = ks.hex() if ks else None
        print(f"  keystruct: {out['keystruct_at_attach']} (enable={ks[5]:#04x} "
              f"mode={ks[7]:#04x})" if ks else "  keystruct read failed")
        assert g.send("M3000005,1:01") == "OK", "enable write rejected"
        for bp in (BP_0B, BP_NORM, BP_PLAYER, BP_AI):
            assert g.send(f"Z0,{bp:x},2") == "OK", f"BP {bp:#x} rejected"
        g.cont()
        time.sleep(0.8)
        window_capture(pid, "outputs/lua-nav/v27-0-menu.png")
        for mask, tag in [(0x80, "DOWN1"), (0x80, "DOWN2"),
                          (0x01, "A-wait"), (0x01, "A-confirm")]:
            press(g, pid, mask, 5, tag=tag)
        window_capture(pid, "outputs/lua-nav/v27-1-committed.png")

        # -- watch the round ------------------------------------------------------
        events = []
        samples = []
        t0 = time.time()
        last_sample = 0.0
        last_event_t = {k: None for k in BP_NAMES.values()}
        player_cap = False
        g.sock.settimeout(3.0)
        while time.time() - t0 < 130:
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
                          "r0": f"{regs[0]:08x}", "r4": f"{regs[4]:08x}",
                          "r7": f"{regs[7]:08x}"}
                    events.append(ev)
                    first = last_event_t[name] is None
                    if first:
                        last_event_t[name] = ev["t"]
                    if first or name == "player-path":
                        print(f"  HIT {name} t={ev['t']} r0={ev['r0']} "
                              f"r4={ev['r4']} r7={ev['r7']}")
                    if name == "player-path" and not player_cap:
                        player_cap = True
                        time.sleep(1.0)
                        window_capture(pid, "outputs/lua-nav/v27-player-menu.png")
                        print("  player-path first hit: capture taken")
                continue
            if now - last_sample >= 10.0:
                try:
                    g.interrupt()
                    row = dump_slots(g, f"t+{now:.0f}s")
                    samples.append({"t": round(now, 1),
                                    "s": {str(k): v for k, v in row.items()}})
                    last_sample = now
                except Exception as exc:
                    print(f"  sample fail: {exc}")

        for bp in (BP_0B, BP_NORM, BP_PLAYER, BP_AI):
            g.send(f"z0,{bp:x},2")
        counts = {}
        for e in events:
            counts[e["bp"]] = counts.get(e["bp"], 0) + 1
        out["events"] = events
        out["counts"] = counts
        out["samples"] = samples
        g.interrupt()
        out["final"] = dump_slots(g, "final")
        out["final"]["flag0D"] = u8(g, FLAG0D)
        g.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/v27-final.png")
        print(f"branch counts: {counts}")
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
