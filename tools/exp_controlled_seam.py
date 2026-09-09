"""A2.3 v9: Controlled-seam via the retail Control-mode route.

Static decode this session (all in docs/player-ai-control.md):
- ctx init (0x080C034C) at 0x080C0360 reads global flag[0x0D] = byte
  0x02022130; when set and gate 0x080C1B2C == 0, it seeds phase 0xB with
  return-phase 8 (walk-to-queued-tile then end-of-turn) instead of the
  phase-9 AI march. Gate returns 0 for monsters unconditionally.
- flag[0x0D] has exactly one set site: 0x080623CE inside the table-dispatched
  Control-action handler, which also pushes phase 1 (pop UI) via 0x080C71B4.
- The controller link is unit[0xE6] = caster id, written by the case-86
  application handler (0x0813363C) through sub_080CE488; the getter search
  sub_080970E8 compares entry[0xE6] == requester[0x104] on the LIVE
  battle-slot records (0x020159E8 + n*0x108), not the roster copies at
  0x02002FC4 that v8 patched.

Experiment:
1. Caller loads a2-battle-start.ss0 first.
2. Read Marche's id from his battle-slot record; scan battle-slot records.
3. On the first enemy battle-slot: +0xE6 = Marche id, +0xED |= 8, CT=1000.
4. Set flag[0x0D] = 1 (byte 0x02022130).
5. End Marche's turn (DOWN DOWN A A via r1 patches at 0x08000494).
6. Zero breakpoints during the outcome window; disconnect; caller observes.

Usage:
    python tools/exp_controlled_seam.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

KEY_BL = 0x08000494
SLOTS = 0x020159E8      # battle-slot unit records (live copies)
STRIDE = 0x108
FLAG0D = 0x02022130     # global flag block 0x02022030 + 0x0D*0x100


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
    """Arm, force, disarm -- leaves NO breakpoint between presses."""
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
    mid = gdb.read_mem(SLOTS + 0x104, 2)[0]
    print(f"marche id={mid:02x} (slot0)")
    out["marche_id"] = mid

    enemies = []
    for n in range(0, 8):
        base = SLOTS + n * STRIDE
        d = gdb.read_mem(base, 0x110)
        if not d:
            continue
        side = d[0x28] | (d[0x29] << 8)
        uid = d[0x104]
        ct = d[0xD0] | (d[0xD1] << 8)
        hp = d[0x1C] | (d[0x1D] << 8)
        print(f"  slot{n} {base:#010x}: side={side:04x} id={uid:02x} ct={ct:4d} "
              f"hp~{hp} e6={d[0xE6]:02x} ed={d[0xED]:02x}")
        if side & 0x8000:
            enemies.append(base)
    out["enemies"] = [hex(e) for e in enemies]
    if not enemies:
        print("NO ENEMY SLOTS -- aborting")
        gdb.cont()
        gdb.close()
        return 1

    enemy = enemies[0]
    d = gdb.read_mem(enemy, 0x110)
    out["baseline"] = {"enemy": hex(enemy), "e6": d[0xE6], "ed": d[0xED],
                       "ct": d[0xD0] | (d[0xD1] << 8)}

    # the corrected write: live battle-slot record gets the link + flag + CT
    gdb.send(f"M{enemy + 0xE6:x},1={mid:02x}")
    gdb.send(f"M{enemy + 0xED:x},1={d[0xED] | 0x08:02x}")
    gdb.send(f"M{enemy + 0xD0:x},2=E803")  # CT=1000
    # retail Control mode: the flag itself
    gdb.send(f"M{FLAG0D:x},1=01")
    d = gdb.read_mem(enemy, 0x110)
    flag = gdb.read_mem(FLAG0D, 1)[0]
    ct = d[0xD0] | (d[0xD1] << 8)
    print(f"written: e6={d[0xE6]:02x} ed={d[0xED]:02x} ct={ct} flag0D={flag:02x}")
    out["written"] = {"e6": d[0xE6], "ed": d[0xED], "ct": ct, "flag0D": flag}
    gdb.cont()
    time.sleep(0.5)

    print("menu: DOWN, DOWN, A, A ...")
    press(gdb, 0x80, 4, 0.8, "DOWN->Action")
    press(gdb, 0x80, 4, 0.8, "DOWN->Wait")
    press(gdb, 0x01, 4, 1.2, "A=select")
    press(gdb, 0x01, 4, 1.2, "A=confirm")

    out["note"] = ("v9: battle-slot writes + flag[0x0D]=1; zero breakpoints in "
                   "outcome window")
    gdb.close()
    print("disconnected clean; game running free")

    os.makedirs("outputs/lua-nav", exist_ok=True)
    with open("outputs/lua-nav/controlled-seam.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print("wrote outputs/lua-nav/controlled-seam.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
