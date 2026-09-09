"""One-boot timeline: what do mode/phase/CT read while the boot skit runs,
when does the command menu actually open, and what does idle takeover look
like? No key presses at all. Every 2 s (CPU halted): key-struct mode byte
(0x03000007), ctx phase u16 (0x020101F8+0x54F4), Marche CT, liveness. A
screenshot every 4 s labels the visuals.

Run: python tools/boot_fixture_gdb.py && python tools/exp_gate_timeline.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

SLOT0 = 0x020159E8
CT6 = SLOT0 + 0x108 * 6 + 0xD0
MODE = 0x03000007
CTX = 0x020101F8
PHASE = CTX + 0x54F4
NAME0 = SLOT0
OUT = "outputs/lua-nav/gate-timeline.json"


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


def main():
    pid = mgba_pid()
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    rows = []
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")
        t0 = time.time()
        last_cap = 0.0
        g.sock.settimeout(2.0)
        while time.time() - t0 < 40:
            try:
                g.cont()
                g._read_packet()
            except Exception:
                pass
            g.interrupt()
            mode = (g.read_mem(MODE, 1) or b"\0")[0]
            phase = int.from_bytes(g.read_mem(PHASE, 2) or b"\0\0", "little")
            ct6 = int.from_bytes(g.read_mem(CT6, 2) or b"\0\0", "little")
            name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0", "little")
            live = (name0 & 0xFF000000) == 0x08000000
            now = round(time.time() - t0, 1)
            rows.append({"t": now, "mode": mode, "phase": phase,
                         "ct6": ct6, "live": live})
            print(f" t={now:>5} mode={mode:02x} phase={phase:>3} "
                  f"ct6={ct6:>4} live={live}")
            if now - last_cap >= 4.0:
                window_capture(pid, f"outputs/lua-nav/gt-t{now:.0f}.png")
                last_cap = now
        g.cont()
        json.dump(rows, open(OUT, "w"), indent=1)
        print(f"wrote {OUT}")
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
