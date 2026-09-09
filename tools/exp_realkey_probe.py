"""Probe: do real keyboard A presses reach the game key struct?

Attaches GDB (observation only), then sends real keyboard 'x' (mGBA default
A) pulses via UIA SendKeys to the main window, sampling the key struct
(0x03000000, 8 bytes) immediately after each press while halted. Also
captures the screen per press. Answers:
  - does a real A produce held/newly-pressed bits?
  - does the enable byte stay 0 (overlay block) or open?
  - does anything visibly change (captures)?

Usage: python tools/boot_fixture_gdb.py && python tools/exp_realkey_probe.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

KEYSTRUCT = 0x03000000
OUT = "outputs/lua-nav/realkey-probe.json"


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def uia_send(pid, keys):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/uia_sendkey.ps1", "-ProcId", str(pid), "-Keys", keys],
        capture_output=True, text=True, timeout=45)
    return (r.stdout or "").strip()


def capture(pid, path):
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-ProcId", str(pid), "-Out", path],
        capture_output=True, text=True, timeout=45)


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    out = {"steps": []}
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        ks0 = g.read_mem(KEYSTRUCT, 8)
        print(f"ks at attach: {ks0.hex() if ks0 else '?'}")
        g.cont()
        for i in range(8):
            capture(pid, f"outputs/lua-nav/rk-{i}-before.png")
            # a clean keypress: key down, 180 ms hold, release
            before = g.interrupt()
            ks_a = g.read_mem(KEYSTRUCT, 8)
            g.cont()
            s1 = uia_send(pid, "x")
            time.sleep(0.18)
            g.interrupt()
            ks_b = g.read_mem(KEYSTRUCT, 8)
            g.cont()
            time.sleep(0.5)
            g.interrupt()
            ks_c = g.read_mem(KEYSTRUCT, 8)
            g.cont()
            time.sleep(1.2)
            row = {"i": i, "send": s1,
                   "ks_before": ks_a.hex() if ks_a else None,
                   "ks_during": ks_b.hex() if ks_b else None,
                   "ks_after": ks_c.hex() if ks_c else None}
            out["steps"].append(row)
            print(f"x#{i}: before={row['ks_before']} "
                  f"during={row['ks_during']} after={row['ks_after']} "
                  f"({s1})")
            capture(pid, f"outputs/lua-nav/rk-{i}-after.png")
        g.cont()
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
