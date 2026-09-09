"""A2.3 v10: patch the REAL slot record (battle-struct slot1 = 0x02015AF0).

Marche's menu is open (fixture reloaded). One GDB session:
1. Verify slot1 (0x02015AF0) is the enemy with name_ptr 0x0856702F.
2. Write Controlled (controller id = Marche's id) at +0xEC and CT=1000 at
   +0xD0 directly on the slot record.
3. Drive Wait (DOWN DOWN A A) and catch turn-manager picks; dump slot CTs at
   the first pick -- the picked slot is whichever dropped below 1000.
4. Remove breakpoints, resume, disconnect; caller screenshots the outcome.

Usage:
    python tools/exp_controlled_pick.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
TURN_MGR = 0x0809E05C
STRUCT = 0x020159E4
SLOT1 = 0x02015AF0
MARCHE = 0x02001F1C


def set_reg(gdb, n, value):
    return gdb.send(f"P{n:x}=" + value.to_bytes(4, "little").hex())


def force_key(gdb, mask, frames, tag=""):
    hits = 0
    for _ in range(frames):
        gdb.cont()
        stop = gdb._read_packet()
        regs = gdb.read_registers()
        if not regs or regs[15] != KEY_BL:
            if regs:
                print(f"  ! stop at {regs[15]:#010x}")
            continue
        set_reg(gdb, 1, (regs[1] | mask) & 0x3FF)
        hits += 1
    print(f"  forced {mask:#04x} x{hits} {tag}")
    return hits


def press(gdb, mask, frames=4, pause=0.6, tag=""):
    gdb.send(f"Z0,{KEY_BL:x},2")
    force_key(gdb, mask, frames, tag)
    gdb.send(f"z0,{KEY_BL:x},2")
    gdb.cont()
    time.sleep(pause)


def dump_slots(gdb, count=7, tag=""):
    rows = []
    for i in range(count):
        base = STRUCT + 4 + i * 0x108
        ptr = int.from_bytes(gdb.read_mem(base, 4) or b"\x00\x00\x00\x00", "little")
        ct = gdb.read_mem(base + 0xD0, 2) or b"\x00\x00"
        ctrl = gdb.read_mem(base + 0xEC, 2) or b"\x00\x00"
        uid = gdb.read_mem(base + 0x104, 2) or b"\x00\x00"
        rows.append({"slot": i, "unit": hex(ptr), "ct": ct[0] | ct[1] << 8,
                     "ec": ctrl[0], "ed": ctrl[1], "id": uid[0]})
        print(f"  [{tag}] slot{i} unit={ptr:#010x} ct={rows[-1]['ct']:5d} "
              f"ec/ed={ctrl[0]:02x}/{ctrl[1]:02x} id={uid[0]:02x}")
    return rows


def main():
    gdb = Gdb("127.0.0.1", 2345, timeout=10)
    gdb.send("?")
    out = {}

    gdb.interrupt()
    # 1. verify slot1 identity
    ptr = int.from_bytes(gdb.read_mem(STRUCT + 4 + 0x108, 4) or b"\x00\x00\x00\x00", "little")
    nm = gdb.read_mem(SLOT1, 4) or b"\x00\x00\x00\x00"
    print(f"slot1 ptr={ptr:#010x} name_ptr={int.from_bytes(nm, 'little'):#010x}")
    assert ptr == SLOT1, f"slot1 pointer mismatch: {ptr:#010x}"
    mid = gdb.read_mem(MARCHE + 0x104, 2)
    d = gdb.read_mem(SLOT1 + 0xEC, 2)
    print(f"marche id={mid[0]:02x}  slot1 ec/ed={d[0]:02x}/{d[1]:02x}")
    out["baseline"] = dump_slots(gdb, tag="pre")

    # 2. write Controlled + CT on the REAL slot
    gdb.send(f"M{SLOT1 + 0xEC:x},2=" + bytes([mid[0], d[1] | 0x08]).hex())
    gdb.send(f"M{SLOT1 + 0xD0:x},2=" + bytes([0xE8, 0x03]).hex())  # CT=1000
    d = gdb.read_mem(SLOT1 + 0xEC, 2)
    ct = gdb.read_mem(SLOT1 + 0xD0, 2)
    print(f"slot1 now: ec/ed={d[0]:02x}/{d[1]:02x} ct={ct[0] | ct[1] << 8}")
    out["written"] = dump_slots(gdb, tag="post")
    gdb.cont()
    time.sleep(0.5)

    # 3. drive Wait and catch picks
    print("menu: DOWN, DOWN, A, arm, A ...")
    press(gdb, 0x80, 4, 0.8, "DOWN->Action")
    press(gdb, 0x80, 4, 0.8, "DOWN->Wait")
    press(gdb, 0x01, 4, 1.2, "A=select")
    gdb.send(f"Z0,{TURN_MGR:x},2")
    press(gdb, 0x01, 4, 0.1, "A=confirm")

    picks = []
    t0 = time.time()
    try:
        while time.time() - t0 < 30:
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if regs and regs[15] == TURN_MGR:
                print(f"PICK r1={regs[1]:#010x}")
                picks.append({"r1": hex(regs[1])})
                if len(picks) == 1:
                    out["at_pick"] = dump_slots(gdb, tag="pick")
                if len(picks) >= 8:
                    break
            gdb.cont()
    except (TimeoutError, OSError) as exc:
        print(f"pick watch ended: {exc}")

    try:
        gdb.send(f"z0,{TURN_MGR:x},2")
        gdb.cont()
    except Exception:
        pass
    out["picks"] = picks
    gdb.close()

    os.makedirs("outputs/lua-nav", exist_ok=True)
    with open("outputs/lua-nav/controlled-pick.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print("wrote outputs/lua-nav/controlled-pick.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
