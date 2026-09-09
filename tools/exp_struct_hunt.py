"""A2.3 v11: catch a live turn-manager hit and map the real battle struct.

Marche's menu is open. One GDB session:
1. Arm the turn-manager breakpoint (0x0809E05C).
2. Drive Wait via the key-call register patch (DOWN DOWN A A).
3. At the first hit: dump r0's struct slots (unit pointers, CT, control
   bytes, ids), and scan EWRAM for words pointing into the roster region
   0x02002FC4..0x02003C30 -- where do live pointers to the roster live?
4. Remove breakpoints, resume, disconnect.

Usage:
    python tools/exp_struct_hunt.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
TURN_MGR = 0x0809E05C
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

    gdb.interrupt()
    mid = gdb.read_mem(MARCHE + 0x104, 2)
    print(f"marche id={mid[0]:02x}")
    gdb.cont()

    print("menu: DOWN, DOWN, A, arm, A ...")
    press(gdb, 0x80, 4, 0.8, "DOWN->Action")
    press(gdb, 0x80, 4, 0.8, "DOWN->Wait")
    press(gdb, 0x01, 4, 1.2, "A=select")
    gdb.send(f"Z0,{TURN_MGR:x},2")
    press(gdb, 0x01, 4, 0.1, "A=confirm")

    got = None
    t0 = time.time()
    try:
        while time.time() - t0 < 30:
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                break
            regs = gdb.read_registers()
            if regs and regs[15] == TURN_MGR:
                got = regs
                break
            gdb.cont()
    except (TimeoutError, OSError) as exc:
        print(f"watch ended: {exc}")

    if got:
        r0 = got[0]
        print(f"PICK: r0={r0:#010x} r1={got[1]:#010x}")
        out["pick"] = {"r0": hex(r0), "r1": hex(got[1])}
        count = int.from_bytes(gdb.read_mem(r0, 4) or b"\x00\x00\x00\x00", "little")
        print(f"struct count={count}")
        for i in range(min(count, 8)):
            ptr = int.from_bytes(gdb.read_mem(r0 + 4 + i * 0x108, 4) or b"\x00\x00\x00\x00", "little")
            ct = gdb.read_mem(r0 + 4 + i * 0x108 + 0xD0, 2) or b"\x00\x00"
            ctrl = gdb.read_mem(r0 + 4 + i * 0x108 + 0xEC, 2) or b"\x00\x00"
            uid = gdb.read_mem(r0 + 4 + i * 0x108 + 0x104, 2) or b"\x00\x00"
            nm = gdb.read_mem(ptr, 4) if ptr else None
            nmp = int.from_bytes(nm, "little") if nm else 0
            print(f"  slot{i}: unit={ptr:#010x} ct={ct[0] | ct[1] << 8:5d} "
                  f"ec/ed={ctrl[0]:02x}/{ctrl[1]:02x} id={uid[0]:02x} name={nmp:#010x}")
            out.setdefault("slots", []).append(
                {"slot": i, "unit": hex(ptr), "ct": ct[0] | ct[1] << 8,
                 "ec": ctrl[0], "ed": ctrl[1], "id": uid[0], "name": hex(nmp)})

        # scan EWRAM for pointers into the roster region
        import struct
        found = {}
        for off in range(0, 0x40000, 0x1000):
            data = gdb.read_mem(0x02000000 + off, 0x1000)
            if not data:
                continue
            for j in range(0, len(data) - 3, 4):
                v = int.from_bytes(data[j:j + 4], "little")
                if 0x02002FC4 <= v < 0x02003C30:
                    found.setdefault(v, []).append(0x02000000 + off + j)
        print("live roster pointers:")
        for v in sorted(found):
            print(f"  {v:#010x} <- {[hex(h) for h in found[v][:6]]}")
        out["roster_ptrs"] = {hex(v): [hex(h) for h in l[:6]] for v, l in sorted(found.items())}

    try:
        gdb.send(f"z0,{TURN_MGR:x},2")
        gdb.cont()
    except Exception:
        pass
    gdb.close()

    os.makedirs("outputs/lua-nav", exist_ok=True)
    with open("outputs/lua-nav/struct-hunt.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print("wrote outputs/lua-nav/struct-hunt.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
