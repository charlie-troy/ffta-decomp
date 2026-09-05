"""One-off: dump battle-object globals at the mode=1 sort entry.

battle-init (0x08096BA0) template-copies 0x1B8 bytes to static 0x0200F4E8
(global 0x0200F4A8) and the scheduler passes it to the sequencer chain;
its +4 field is the 0x90-stride action-entry-array base (0x020223AC in the
snowball battle). Matching the dumped bytes against the ROM tells us which
fields the template bakes in and which battle setup writes.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402
from dump_candidates import BREAK_AT  # noqa: E402

RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_BYTES = "0121c046"
PATCH_ORIG = "811c5940"

BATTLE_OBJ = 0x0200F4E8
G_A8 = 0x0200F4A8
G_AC = 0x0200F4AC
G_B0 = 0x0200F4B0
G_B4 = 0x0200F4B4
G_B8 = 0x0200F4B8

OUT = os.path.join(os.path.dirname(__file__), "..", "outputs",
                   "mgba-snowball", "battle_obj_dump.bin")


def rd(gdb, addr, n):
    for _ in range(3):
        d = gdb.read_mem(addr, n)
        if d and len(d) == n:
            return d
        time.sleep(0.05)
    return None


def rd32(gdb, addr):
    d = rd(gdb, addr, 4)
    return int.from_bytes(d, "little") if d else None


def main():
    gdb = Gdb("127.0.0.1", 2345, timeout=20)
    try:
        gdb.send("?")
        gdb.send(f"M{RNG:x},4:78563412")
        gdb.send(f"Z0,{BREAK_AT:x},2")
        gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
        gdb.cont()
        time.sleep(10 / 30)
        gdb.interrupt()
        gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")

        gdb.sock.settimeout(90)
        pending = None
        hit = None
        for _ in range(4):
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                break
            r = gdb.read_registers()
            if r and r[15] == BREAK_AT and r[2] == 1 and r[1] == 8:
                hit = r
                break
            pending = None
        if not hit:
            print("mode=1 sort entry not reached")
            return 1
        print(f"at mode=1 sort entry, ai={hit[0]:#x}")

        for name, a in (("G_A8", G_A8), ("G_AC", G_AC), ("G_B0", G_B0),
                        ("G_B4", G_B4), ("G_B8", G_B8)):
            print(f"  [{a:#x}] {name} = {rd32(gdb, a):#010x}")

        obj = rd(gdb, BATTLE_OBJ, 0x1B8)
        if not obj:
            print("battle object read failed")
            return 1
        with open(OUT, "wb") as fh:
            fh.write(obj)
        words = [int.from_bytes(obj[i:i + 4], "little")
                 for i in range(0, 0x60, 4)]
        print(f"battle_obj ({BATTLE_OBJ:#x}) first 0x60 bytes as words:")
        for i, w in enumerate(words):
            print(f"  +{i * 4:#05x}: {w:#010x}")
        base = rd32(gdb, BATTLE_OBJ + 4)
        print(f"[battle_obj+4] = {base:#010x} (entry-array base should be "
              f"0x020223ac)")

        # the [0x200f4b0] constructor object's key fields
        b0 = rd32(gdb, G_B0)
        if b0:
            for off in (0, 4, 8, 0xC, 0x10, 0x14, 0x18, 0x1C, 0x20):
                v = rd32(gdb, b0 + off)
                print(f"  ctor_obj {b0:#x}+{off:#x} = {v:#010x}")
        return 0
    finally:
        try:
            gdb.close()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
