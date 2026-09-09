"""A2.3 v24: marks-only Controlled seam + actor-pick watch.

v22 finding: with flag0D=1 set at Marche's turn end, ctx init seeds phase 0xB
(walk-to-queued-tile) with nothing queued -> the round deadlocks (control run
without writes runs fine). v24 replicates the retail Control state more
closely: Controlled marks on slot0 (+0xE6=Marche id, +0xED|=8) but NO flag0D;
the pick loop clears the Controlled bit at 0x0809E272 when it picks the actor,
so that breakpoint is the authoritative "who acts next" observable.

Sequence: fixture boot -> marks-only writes -> menu keys (Marche Wait) ->
watchpoint 0x0809E272 while sampling CTs for ~60 s -> captures.

Usage: python tools/exp_controlled_seam_v24.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
PICK_CLEAR = 0x0809E272
SLOT0 = 0x020159E8
STRIDE = 0x108
OUT_JSON = "outputs/lua-nav/controlled-v24.json"


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


def cts(gdb, tag):
    row = []
    for i in range(7):
        d = gdb.read_mem(SLOT0 + STRIDE * i + 0xD0, 2)
        row.append(int.from_bytes(d, "little") if d else None)
    print(f"  [{tag}] cts={row}")
    return row


def main():
    pid = mgba_pid()
    if not pid:
        print("no mGBA process")
        return 1
    print(f"mGBA pid {pid}")
    out = {}
    gdb = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        gdb.send("?")
        gdb.interrupt()
        print("GDB attached; halted")

        # -- marks-only writes ------------------------------------------------
        mid = gdb.read_mem(SLOT0 + STRIDE * 6 + 0x104, 1)[0]
        ed = gdb.read_mem(SLOT0 + 0xED, 1)[0]
        assert gdb.send(f"M{SLOT0 + 0xE6:x},1:{mid:02x}") == "OK"
        assert gdb.send(f"M{SLOT0 + 0xED:x},1:{ed | 8:02x}") == "OK"
        wv = {
            "e6": gdb.read_mem(SLOT0 + 0xE6, 1)[0],
            "ed": gdb.read_mem(SLOT0 + 0xED, 1)[0],
            "flag0D": gdb.read_mem(0x0200203D, 1)[0],
        }
        out["written"] = wv
        print(f"  marks (no flag0D): {wv}")
        gdb.cont()

        # -- Marche: DOWN, DOWN, A, A -----------------------------------------
        def press(mask, frames=4, pause=1.1, tag=""):
            hits = 0
            try:
                if gdb.send(f"Z0,{KEY_BL:x},2") != "OK":
                    return 0
                for _ in range(frames):
                    gdb.cont()
                    stop = gdb._read_packet()
                    if not stop or stop[:1] not in ("S", "T"):
                        break
                    regs = gdb.read_registers()
                    if regs and regs[15] == KEY_BL:
                        val = (regs[1] | mask) & 0x3FF
                        gdb.send("P1=" + val.to_bytes(4, "little").hex())
                        hits += 1
            finally:
                try:
                    gdb.send(f"z0,{KEY_BL:x},2")
                    gdb.cont()
                except Exception:
                    pass
            time.sleep(pause)
            print(f"  key {mask:#04x} x{hits} {tag}")
            return hits

        time.sleep(0.8)
        for mask, tag in [(0x80, "DOWN1"), (0x80, "DOWN2"),
                          (0x01, "A-wait"), (0x01, "A-confirm")]:
            press(mask, 4, tag=tag)
        window_capture(pid, "outputs/lua-nav/v24-0-committed.png")

        # -- watch picks + sample CTs ------------------------------------------
        picks = []
        samples = []
        if gdb.send(f"Z0,{PICK_CLEAR:x},2") != "OK":
            print("FAIL: pick watchpoint rejected")
            return 1
        t0 = time.time()
        last_sample = 0.0
        while time.time() - t0 < 60:
            gdb.sock.settimeout(2.0)
            gdb.cont()
            try:
                stop = gdb._read_packet()
            except Exception:
                stop = None
            now = time.time() - t0
            if stop and stop[:1] in ("S", "T"):
                regs = gdb.read_registers()
                if regs and regs[15] == PICK_CLEAR:
                    row = {"t": round(now, 1), "r0": f"{regs[0]:08x}",
                           "r1": f"{regs[1]:08x}"}
                    picks.append(row)
                    print(f"  PICK t={row['t']} r0={row['r0']} r1={row['r1']}")
                    if len(picks) == 1:
                        window_capture(pid, "outputs/lua-nav/v24-pick1.png")
                    continue
            # timeout: sample the CTs (game keeps running; interrupt briefly)
            if now - last_sample >= 4.0:
                gdb.interrupt()
                row = cts(gdb, f"t+{now:.0f}s")
                samples.append({"t": round(now, 1), "cts": row})
                last_sample = now
                if len(samples) in (3, 6):
                    window_capture(pid, f"outputs/lua-nav/v24-t{now:.0f}.png")
        gdb.send(f"z0,{PICK_CLEAR:x},2")
        gdb.sock.settimeout(10)
        out["picks"] = picks
        out["samples"] = samples

        gdb.interrupt()
        out["final_state"] = {
            "s0.e6": gdb.read_mem(SLOT0 + 0xE6, 1)[0],
            "s0.ed": gdb.read_mem(SLOT0 + 0xED, 1)[0],
            "flag0D": gdb.read_mem(0x0200203D, 1)[0],
        }
        gdb.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/v24-final.png")
        out["round_advanced"] = len({tuple(s["cts"]) for s in samples}) > 1
        print(f"picks: {len(picks)}, round advanced: {out['round_advanced']}")
        with open(OUT_JSON, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"wrote {OUT_JSON}")
        return 0
    finally:
        try:
            gdb.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
