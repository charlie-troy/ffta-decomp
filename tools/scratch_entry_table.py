"""One-off: dump the full 8x0x90 action-entry table at the mode=1 sort entry.

The entry-array base lives at [battle_obj+4] (0x020223AC this battle); each
0x90-byte entry's +0 word is the target unit pointer. Correlating entry
fields with the AI's reads (list builders 0x08099D08/34, fill machine,
candidate ability operands) pins the entry layout.
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
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs",
                       "mgba-snowball")


def rd(gdb, addr, n):
    for _ in range(3):
        d = gdb.read_mem(addr, n)
        if d and len(d) == n:
            return d
        time.sleep(0.05)
    return None


def rd16(gdb, addr):
    d = rd(gdb, addr, 2)
    return d[0] | (d[1] << 8) if d else None


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

        base = rd32(gdb, BATTLE_OBJ + 4)
        print(f"entry-array base = {base:#010x}")
        table = bytearray()
        for k in range(8):
            chunk = rd(gdb, base + k * 0x90, 0x90)
            if not chunk:
                print(f"entry {k}: 0x90-byte read failed")
                chunk = b"\x00" * 0x90
            table.extend(chunk)
        table = bytes(table)
        with open(os.path.join(OUT_DIR, "entry_table_dump.bin"), "wb") as fh:
            fh.write(table)

        for k in range(8):
            e = table[k * 0x90:(k + 1) * 0x90]
            words = [int.from_bytes(e[i:i + 4], "little")
                     for i in range(0, 0x40, 4)]
            u = words[0]
            print(f"entry {k} @ {base + k * 0x90:#010x}: "
                  f"+0 unit={u:#010x} " if u else
                  f"entry {k} @ {base + k * 0x90:#010x}: (empty)")
            if u:
                print(f"  words: " + " ".join(f"{w:08x}" for w in words))
                # unit identity: job/race bytes around unit+0x1C..0x1F, HP
                hp = rd16(gdb, u + 0x18)
                mx = rd16(gdb, u + 0x1A)
                print(f"  unit hp={hp}/{mx}")
        return 0
    finally:
        try:
            gdb.close()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
