"""Minimal deadlock diagnostic: does the game run, do CTs tick, does a pick fire?

No input injection. Boot (boot_fixture_gdb first), attach, then:
  1. read CT0/CT6/name0; cont 10 s with NO BPs; halt; read again.
  2. arm BP_PICK only; pump 25 s logging every stop.
  3. report whether the game runs (CTs move) and whether the battle starts.
"""
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

SLOT0 = 0x020159E8
STRIDE = 0x108
CT0 = SLOT0 + 0xD0
CT6 = SLOT0 + STRIDE * 6 + 0xD0
NAME0 = SLOT0
BP_PICK = 0x0809E260


def main():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    pid = int(r.stdout.strip() or 0)
    print(f"mGBA pid {pid}")
    g = Gdb("127.0.0.1", 2345, timeout=10)
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")

        def snap(tag):
            ct0 = int.from_bytes(g.read_mem(CT0, 2) or b"\0\0", "little")
            ct6 = int.from_bytes(g.read_mem(CT6, 2) or b"\0\0", "little")
            name0 = int.from_bytes(g.read_mem(NAME0, 4) or b"\0\0\0\0",
                                   "little")
            ks = g.read_mem(0x03000000, 8)
            print(f"  [{tag}] ct0={ct0} ct6={ct6} "
                  f"name0={name0:08x} ks={ks.hex() if ks else '?'}")
            return ct0, ct6

        ct0a, ct6a = snap("t=0")
        g.cont()
        time.sleep(10.0)
        g.interrupt()
        ct0b, ct6b = snap("after 10s cont")
        print(f"  GAME {'RUNS' if (ct0a, ct6a) != (ct0b, ct6b) else 'FROZEN or CTs static'}")

        assert g.send(f"Z0,{BP_PICK:x},2") == "OK"
        t0 = time.time()
        g.sock.settimeout(0.5)
        stops = []
        while time.time() - t0 < 25:
            try:
                g.cont()
                st = g._read_packet()
            except Exception:
                continue
            if st and st[:1] in ("S", "T"):
                regs = g.read_registers()
                if regs:
                    t = round(time.time() - t0, 1)
                    stops.append((t, regs[15], regs[0]))
                    print(f"  STOP t={t} pc={regs[15]:08x} r0={regs[0]:08x}")
                    g.interrupt()
                    snap(f"after stop t={t}")
        g.send(f"z0,{BP_PICK:x},2")
        print(f"total stops in 25s: {len(stops)}")
        g.cont()
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
