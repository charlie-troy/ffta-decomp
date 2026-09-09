"""A2.3 v4: does the turn loop clear the injected Controlled flag?

Marche's menu is open (post-round). One GDB session:
1. Read the enemy's current control bytes -- did Controlled survive its turn?
2. Re-set Controlled (controller id = Marche's +0x104 id) if cleared.
3. Arm breakpoints on the clear site (0x0809E272), the Controlled getter
   (0x080CDCA4), and the search-by-controller helper (0x080970E8).
4. Drive Wait (DOWN DOWN A A) and log every hit for 90s -- the sequence around
   the controlled enemy's turn names the mechanism.

Usage:
    python tools/exp_controlled_watch.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
CLEAR_SITE = 0x0809E272
CTRL_GETTER = 0x080CDCA4
SEARCH_HELPER = 0x080970E8
MARCHE = 0x02001F1C
ENEMY = 0x02002FC4

NAMES = {MARCHE: "marche", ENEMY: "ENEMY-CTRL", 0x0200080: "0x2000080"}


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

    # 1. did Controlled survive the round?
    gdb.interrupt()
    mid = gdb.read_mem(MARCHE + 0x104, 2)
    d = gdb.read_mem(ENEMY + 0xEC, 2)
    print(f"marche id={mid[0]:02x}  enemy now ec/ed={d[0]:02x}/{d[1]:02x}")
    out["enemy_after_round"] = [d[0], d[1]]

    # 2. ensure Controlled is set with the real controller id
    gdb.send(f"M{ENEMY + 0xEC:x},2=" + bytes([mid[0], d[1] | 0x08]).hex())
    d = gdb.read_mem(ENEMY + 0xEC, 2)
    print(f"re-set: ec/ed={d[0]:02x}/{d[1]:02x} (controller={mid[0]:#04x})")
    out["reset"] = [d[0], d[1]]
    gdb.cont()

    # 3. arm the three watchpoints
    for bp in (CLEAR_SITE, CTRL_GETTER, SEARCH_HELPER):
        print(f"arm {bp:#010x}: {gdb.send(f'Z0,{bp:x},2')!r}")

    # 4. drive Wait and log
    print("menu: DOWN, DOWN, A, A ...")
    press(gdb, 0x80, 4, 0.8, "DOWN->Action")
    press(gdb, 0x80, 4, 0.8, "DOWN->Wait")
    press(gdb, 0x01, 4, 1.2, "A=select")
    press(gdb, 0x01, 4, 1.2, "A=confirm")

    events = []
    t0 = time.time()
    try:
        while time.time() - t0 < 90:
            gdb.cont()
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if not regs:
                continue
            pc = regs[15]
            if pc == CLEAR_SITE:
                events.append(("clear", regs[0], regs[1]))
                print(f"CLEAR actor={regs[0]:#010x} arg={regs[1]:#x}")
            elif pc == CTRL_GETTER:
                events.append(("get", regs[0], None))
                nm = NAMES.get(regs[0], "")
                print(f"GET   unit={regs[0]:#010x} {nm}")
            elif pc == SEARCH_HELPER:
                events.append(("search", regs[0], regs[1]))
                print(f"SEARCH r0={regs[0]:#010x} r1={regs[1]:#010x}")
            else:
                print(f"? pc={pc:#010x}")
            if len(events) >= 120:
                break
    except (TimeoutError, OSError) as exc:
        print(f"watch ended: {exc}")
    finally:
        for bp in (CLEAR_SITE, CTRL_GETTER, SEARCH_HELPER):
            try:
                gdb.send(f"z0,{bp:x},2")
            except Exception:
                pass
        try:
            gdb.cont()
        except Exception:
            pass

    out["events"] = [
        {"kind": k, "a": hex(a), "b": hex(b) if b is not None else None}
        for k, a, b in events
    ]
    gdb.close()

    os.makedirs("outputs/lua-nav", exist_ok=True)
    with open("outputs/lua-nav/controlled-watch.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print("wrote outputs/lua-nav/controlled-watch.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
