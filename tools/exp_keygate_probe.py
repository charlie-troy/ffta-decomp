"""Live probe of the failed v27c state: why do injected keys not navigate?

Facts: poll BP 0x08000494 hits every frame; P1 r1-write verified working
(A1 session, v24, v27). In failed runs the key struct read 0000000000000083
(mode +7 = 0x83); in a successful-run probe it read ...8b (bit 3 set).
This probe, on the live instance:
  1. dump key struct before/after an injected press (do pressed bits appear?)
  2. set mode bit 3 (+7), press again, watch struct + screen
  3. read menu/round state (slot CTs) around each step
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
OUT = "outputs/lua-nav/keygate-probe.json"


def cap(path):
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         "tools/capture_window.ps1", "-Out", path],
        capture_output=True, timeout=45)


def main():
    g = Gdb("127.0.0.1", 2345, timeout=12)
    log = {}
    try:
        stop = g.interrupt()
        print(f"attach: {stop}")

        def ks():
            return g.read_mem(0x03000000, 8).hex()

        def cts():
            return [int.from_bytes(g.read_mem(SLOT0 + STRIDE * i + 0xD0, 2),
                                   "little") for i in range(7)]

        def press(mask, frames=6):
            hits = 0
            g.send(f"Z0,{KEY_BL:x},2")
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
            g.send(f"z0,{KEY_BL:x},2")
            g.cont()
            time.sleep(1.5)
            return hits

        log["ks0"] = ks()
        log["cts0"] = cts()
        print(f"keystruct: {log['ks0']}  cts: {log['cts0']}")
        cap("outputs/lua-nav/kg-0-before.png")

        # step 1: plain A press - do pressed bits appear at all?
        h = press(0x01)
        time.sleep(0.3)
        g.interrupt()
        log["ks_after_A"] = ks()
        log["cts_after_A"] = cts()
        print(f"A x{h}: keystruct {log['ks_after_A']} cts {log['cts_after_A']}")
        cap("outputs/lua-nav/kg-1-afterA.png")

        # step 2: set mode bit 3 (+7), press again
        mode = g.read_mem(0x03000007, 1)[0]
        g.send(f"M3000007,1:{mode | 8:02x}")
        log["mode_before"] = mode
        print(f"mode {mode:#04x} -> {mode | 8:#04x}")
        g.cont()
        h = press(0x01)
        time.sleep(0.3)
        g.interrupt()
        log["ks_after_modeA"] = ks()
        log["cts_after_modeA"] = cts()
        print(f"A after bit3: keystruct {log['ks_after_modeA']} "
              f"cts {log['cts_after_modeA']}")
        cap("outputs/lua-nav/kg-2-afterModeA.png")

        # step 3: also set enable byte (+5)=1 with bit3 held, press A again
        g.send("M3000005,1:01")
        g.cont()
        h = press(0x01)
        time.sleep(0.3)
        g.interrupt()
        log["ks_after_both"] = ks()
        log["cts_after_both"] = cts()
        print(f"A after enable+bit3: {log['ks_after_both']} "
              f"cts {log['cts_after_both']}")
        cap("outputs/lua-nav/kg-3-afterBoth.png")

        g.cont()
        json.dump(log, open(OUT, "w"), indent=1)
        print(f"wrote {OUT}")
        return 0
    finally:
        try:
            g.cont()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
