"""Dump the battle-record region + sample the PC (one GDB session, read-only).

Establishes the true battle-slot record layout for the A2 fixture: the old
0x108-stride "slot0/slot6" model disagrees with the 0x210-stride reading, so
this dumps raw memory for offline structure analysis and samples the PC to
see whether the turn manager (0x0809E05C) is executing.

Usage:
    mgba -g -t outputs/lua-nav/fix3-battle-start.ss0 baserom.gba   # fresh box
    python tools/exp_slot_scan.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

LO = 0x02015900
HI = 0x02016900            # 4 KiB around the container
OUT_JSON = "outputs/lua-nav/slot-scan.json"
TM = 0x0809E05C


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def main():
    pid = mgba_pid()
    if not pid:
        print("no mGBA process")
        return 1
    print(f"mGBA pid {pid}")
    gdb = Gdb("127.0.0.1", 2345, timeout=10)
    gdb.send("?")
    gdb.interrupt()
    print("GDB attached; CPU halted")

    blob = bytearray()
    for a in range(LO, HI, 0x100):
        chunk = gdb.read_mem(a, 0x100)
        if chunk is None:
            print(f"read failed at {a:08x}")
            return 1
        blob.extend(chunk)

    # sample the PC while the game runs: is the turn manager executing?
    pcs = []
    gdb.cont()
    time.sleep(0.4)
    for _ in range(40):
        gdb.interrupt()
        regs = gdb.read_registers()
        if regs:
            pcs.append(regs[15])
        gdb.cont()
        time.sleep(0.03)
    tm_hits = sum(1 for pc in pcs if pc == TM)
    print(f"PC samples: {len(pcs)}, turn-manager hits: {tm_hits}")
    print("top PCs:", sorted({f'{p:08x}' for p in pcs})[:12])

    with open(OUT_JSON, "wb") as fh:
        pass
    out = {
        "lo": LO,
        "hi": HI,
        "mem": blob.hex(),
        "pcs": [f"{p:08x}" for p in pcs],
        "tm_hits": tm_hits,
    }
    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {OUT_JSON} ({len(blob)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
