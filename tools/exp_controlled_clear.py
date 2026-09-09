"""A2.3 v7: catch who clears the Controlled flag on the controlled unit.

Marche's menu is open (fixture reloaded). One GDB session:
1. Set Controlled (controller id = Marche's id) + CT=1000 on the enemy.
2. Arm breakpoints on the setter (0x080CE2F0) and the key-call site.
3. Drive Wait (DOWN DOWN A A); after the last press LEAVE THE SETTER ARMED
   but remove the key breakpoint, so the game runs until the setter fires.
4. Log setter calls (unit + value) for 90s -- the caller that zeroes the
   controlled unit's flag names the clearing mechanism.
5. Remove the breakpoint, resume, disconnect clean.

Usage:
    python tools/exp_controlled_clear.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
SETTER = 0x080CE2F0
MARCHE = 0x02001F1C
ENEMY = 0x02002FC4


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


def main():
    gdb = Gdb("127.0.0.1", 2345, timeout=10)
    gdb.send("?")
    out = {}

    # 1. writes
    gdb.interrupt()
    mid = gdb.read_mem(MARCHE + 0x104, 2)
    d = gdb.read_mem(ENEMY + 0xEC, 2)
    print(f"marche id={mid[0]:02x}  enemy ec/ed={d[0]:02x}/{d[1]:02x}")
    out["baseline"] = [d[0], d[1]]
    gdb.send(f"M{ENEMY + 0xEC:x},2=" + bytes([mid[0], d[1] | 0x08]).hex())
    gdb.send(f"M{ENEMY + 0xD0:x},2=" + bytes([0xE8, 0x03]).hex())  # CT=1000
    d = gdb.read_mem(ENEMY + 0xEC, 2)
    print(f"set: ec/ed={d[0]:02x}/{d[1]:02x} (controller={mid[0]:#04x})")
    out["written"] = [d[0], d[1]]
    gdb.cont()
    time.sleep(0.5)

    # 2. arm setter + key site
    gdb.send(f"Z0,{SETTER:x},2")
    print(f"setter bp armed: {SETTER:#010x}")

    # 3. drive the menu
    print("menu: DOWN, DOWN, A, A ...")
    press(gdb, 0x80, 4, 0.8, "DOWN->Action")
    press(gdb, 0x80, 4, 0.8, "DOWN->Wait")
    press(gdb, 0x01, 4, 1.2, "A=select")
    press(gdb, 0x01, 4, 1.2, "A=confirm")

    # 4. log setter calls (key bp already disarmed by press())
    events = []
    t0 = time.time()
    try:
        while time.time() - t0 < 90:
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if not regs:
                continue
            if regs[15] == SETTER:
                unit = regs[0]
                val = regs[1] & 0xFF
                d = gdb.read_mem(unit + 0xEC, 2) if 0x02000000 <= unit < 0x02040000 else None
                ec_ed = f"{d[0]:02x}/{d[1]:02x}" if d else "?"
                events.append({"unit": hex(unit), "val": val, "ec_ed": ec_ed})
                print(f"SETTER unit={unit:#010x} val={val} ec/ed={ec_ed}")
                if len(events) >= 40:
                    break
            gdb.cont()
    except (TimeoutError, OSError) as exc:
        print(f"watch ended: {exc}")

    # 5. clean up: remove setter bp, resume
    try:
        gdb.send(f"z0,{SETTER:x},2")
        gdb.cont()
    except Exception:
        pass
    out["events"] = events
    gdb.close()

    os.makedirs("outputs/lua-nav", exist_ok=True)
    with open("outputs/lua-nav/controlled-clear.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print("wrote outputs/lua-nav/controlled-clear.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
