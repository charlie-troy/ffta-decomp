"""One-off: cold-boot write-watchpoint on the action-entry table.

Launch mGBA WITHOUT a savestate, arm a write watch on 0x020223AC (entry 0's
unit-pointer word of the 0x90-stride action-entry table) before any battle
exists, then let the game run. Every stop reports pc/lr/regs + surrounding
memory, attributing the table's first write to its builder — including
IWRAM-resident builders (matched back into the ROM afterwards).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

WATCH = 0x020223AC
MAX_STOPS = 12


def regs_str(r):
    names = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7",
             "r8", "r9", "r10", "r11", "r12", "sp", "lr", "pc"]
    return " ".join(f"{n}={v:08x}" for n, v in zip(names, r))


def main():
    # connect with retries (the stub may lag the window a little)
    gdb = None
    for _ in range(20):
        try:
            gdb = Gdb("127.0.0.1", 2345, timeout=10)
            break
        except OSError:
            time.sleep(0.5)
    if gdb is None:
        print("could not connect to mGBA gdb stub")
        return 1
    try:
        gdb.interrupt()
        r = gdb.read_registers()
        print(f"halted at boot: {regs_str(r) if r else 'reg read failed'}")
        # clear any stale breakpoints from prior probes, then arm the watch
        gdb.send("z0,0,2")
        gdb.send(f"Z2,{WATCH:x},2")
        gdb.sock.settimeout(600)
        for stop_i in range(MAX_STOPS):
            gdb.cont()
            try:
                reply = gdb._read_packet()
            except TimeoutError:
                print(f"[{stop_i}] no watch hit in 600s - done")
                return 0
            if not reply or reply[:1] not in ("S", "T"):
                print(f"[{stop_i}] unexpected reply: {reply!r}")
                return 1
            r = gdb.read_registers()
            if not r or len(r) < 16:
                print(f"[{stop_i}] register read failed after {reply!r}")
                continue
            pc, lr = r[15], r[14]
            print(f"[{stop_i}] reply={reply!r}")
            print(f"    {regs_str(r)}")
            word = gdb.read_mem(WATCH, 4)
            print(f"    [{WATCH:#x}] = "
                  f"{int.from_bytes(word, 'little'):#010x}" if word else
                  f"    [{WATCH:#x}] read failed")
            # peek a small window around the watch for context
            ctx = gdb.read_mem(WATCH - 0x10, 0x30)
            if ctx:
                print("    ctx: " + ctx.hex())
            # if the writer is in IWRAM, grab bytes to match into ROM later
            if 0x03000000 <= pc < 0x03008000:
                blob = gdb.read_mem(pc - 0x20, 0x40)
                print(f"    IWRAM code around pc: {blob.hex() if blob else '?'}")
        return 0
    finally:
        try:
            gdb.close()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
