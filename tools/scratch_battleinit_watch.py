"""One-off: does the game re-enter battle-init after the traced battle?

Loads state-facing, syncs at the mode=1 sort entry, then breaks on battle
init 0x08096BA0 and lets the game run unattended. If a later battle starts
(the tutorial scripting another encounter), the stop reports it and the
caller can arm a write watch on [battle_obj+4] to catch the entry-array
builder. The stub stays open for follow-up.
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
BATTLE_INIT = 0x08096BA0
BATTLE_OBJ = 0x0200F4E8
WATCH_OBJ4 = BATTLE_OBJ + 4


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
        print(f"sort entry synced, ai={hit[0]:#x}")
        gdb.send(f"z0,{BREAK_AT:x},2")

        # now arm battle-init and run unattended
        gdb.send(f"Z0,{BATTLE_INIT:x},2")
        gdb.sock.settimeout(240)
        for i in range(3):
            gdb.cont()
            try:
                reply = gdb._read_packet()
            except TimeoutError:
                print(f"[{i}] no battle-init in 240s - tutorial does not "
                      "restart battle unattended")
                return 1
            if not reply or reply[:1] not in ("S", "T"):
                print(f"[{i}] unexpected reply: {reply!r}")
                return 1
            r = gdb.read_registers()
            pc = r[15] if r else 0
            print(f"[{i}] battle-init hit! reply={reply!r} pc={pc:#x}")
            obj4 = gdb.read_mem(WATCH_OBJ4, 4)
            print(f"    [battle_obj+4] = "
                  f"{int.from_bytes(obj4, 'little'):#010x}"
                  if obj4 else "    obj+4 read failed")
            # stay halted; leave battle-init breakpoint armed for follow-up
            return 0
        return 0
    finally:
        try:
            gdb.close()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
