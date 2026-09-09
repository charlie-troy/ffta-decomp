"""Finish the A2.3 takeover round: commit the facing picker, then sample.

The v21 run ended with Marche's menu still open -- after Wait+confirm FFTA
shows the facing-direction picker, so the turn never completed. This session:
  1. verify the takeover state survived (flag0D=1, s0.ct=1000, e6=6, ed|=8),
  2. press A (r1 patch at 0x08000494) to commit the facing,
  3. resume and sample slot CTs for ~30 s,
  4. capture the screen at the end.

Usage (emulator already in the mid-turn state):
    python tools/exp_controlled_finish.py
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
OUT_JSON = "outputs/lua-nav/controlled-finish.json"


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
    gdb = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        gdb.send("?")
        gdb.interrupt()
        flag = gdb.read_mem(FLAG0D, 1)[0]
        st = {
            "flag0D": flag,
            "s0.ct": int.from_bytes(gdb.read_mem(SLOT0 + 0xD0, 2), "little"),
            "s0.e6": gdb.read_mem(SLOT0 + 0xE6, 1)[0],
            "s0.ed": gdb.read_mem(SLOT0 + 0xED, 1)[0],
        }
        print(f"  state: {st}")
        out = {"state_before": st}
        if flag != 1:
            print("FAIL: takeover state gone (fixture was reloaded?)")
            with open(OUT_JSON, "w") as fh:
                json.dump(out, fh, indent=1)
            gdb.cont()
            return 1

        # -- A press: commit facing / confirm --------------------------------
        if gdb.send(f"Z0,{KEY_BL:x},2") != "OK":
            print("FAIL: bp rejected")
            gdb.cont()
            return 1
        hits = 0
        for _ in range(6):
            gdb.cont()
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if regs and regs[15] == KEY_BL:
                val = (regs[1] | 0x01) & 0x3FF
                gdb.send("P1=" + val.to_bytes(4, "little").hex())
                hits += 1
        try:
            gdb.send(f"z0,{KEY_BL:x},2")
        except Exception:
            pass
        gdb.cont()
        print(f"  A press: {hits} frames injected; CPU resumed")

        # -- sample the round --------------------------------------------------
        samples = []
        for i in range(12):
            time.sleep(2.5)
            gdb.interrupt()
            row = cts(gdb, f"t+{(i + 1) * 2.5:.1f}s")
            samples.append(row)
            gdb.cont()
        out["samples"] = samples

        gdb.interrupt()
        out["state_after"] = {
            "flag0D": gdb.read_mem(FLAG0D, 1)[0],
            "s0.ct": int.from_bytes(gdb.read_mem(SLOT0 + 0xD0, 2), "little"),
            "s0.e6": gdb.read_mem(SLOT0 + 0xE6, 1)[0],
        }
        gdb.cont()
        time.sleep(0.5)
        window_capture(pid, "outputs/lua-nav/finish-final.png")
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
