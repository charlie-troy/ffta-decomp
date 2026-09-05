"""Log the full per-turn sequencer phase march in the live snowball battle.

Breaks at the phase dispatcher entry (0x080C045C) every frame while a turn is
active and records, for each stop: the phase index (ctx+0x54F4), the branch-key
byte (ctx+0x54AF), the actor's unit record pointer (entries[0] -> entry+0),
its live tile (unit+0xF6/+0xF7) and the tile saved at ctx init
(ctx+0x54CA/+0x54CB).  A divergence between the live tile and the saved tile
is movement during the turn; the phase row where it appears points at the
moving phase.

Injection flow matches capture_candidates.py: freeze the RNG, arm the
dispatcher breakpoint, force the facing-confirm A press by briefly patching
the key poll at 0x0800048A, then collect stops until the actor changes (the
next turn) or the hit budget runs out.

Usage:
    python tools/trace_turn_march.py [--hits N] [--out FILE] [--port P]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

CTX = 0x020101F8
PHASE = CTX + 0x54F4
FLAGS = CTX + 0x54AF
SAVED_XY = CTX + 0x54CA
DISPATCH = 0x080C045C
RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_LEN = 4
PATCH_BYTES = "0121c046"   # movs r1, #1 ; nop  (forces A held)
PATCH_ORIG = "811c5940"    # adds r1, r2, #0 ; eors r1, r3 (retail)
KNOWN_ACTOR = 0x02002FC4   # this battle's enemy unit record


def u16(b):
    return int.from_bytes(b, "little")


def u32(b):
    return int.from_bytes(b, "little")


def row(gdb):
    phase = u16(gdb.read_mem(PHASE, 2))
    flags = gdb.read_mem(FLAGS, 1)[0]
    entries = u32(gdb.read_mem(CTX + 4, 4))
    unit = u32(gdb.read_mem(entries, 4)) if entries else 0
    sx, sy = gdb.read_mem(SAVED_XY, 2)
    lx, ly = 0, 0
    if unit:
        lx, ly = gdb.read_mem(unit + 0xF6, 2)
    return {
        "phase": phase,
        "flags": flags,
        "entries": entries,
        "unit": unit,
        "tile": [lx, ly],
        "saved": [sx, sy],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hits", type=int, default=250)
    p.add_argument("--idle-timeout", type=float, default=45.0)
    p.add_argument("--out", default="outputs/mgba-snowball/turn-march.json")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    print(f"seed before freeze: {gdb.read_mem(RNG, 4).hex()}")
    gdb.send(f"M{RNG:x},4:78563412")
    print(f"freeze RNG -> seed now {gdb.read_mem(RNG, 4).hex()}")
    print(f"dispatcher break {DISPATCH:#010x} -> "
          f"{gdb.send(f'Z0,{DISPATCH:x},2')!r}")

    gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_BYTES}")
    print(f"A-force verify={gdb.read_mem(POLL_PATCH, PATCH_LEN).hex()}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_ORIG}")
    print(f"restore verify={gdb.read_mem(POLL_PATCH, PATCH_LEN).hex()}")

    rows = []
    pending = stop
    gdb.sock.settimeout(args.idle_timeout)
    actor_seen = None
    try:
        while len(rows) < args.hits:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                raise RuntimeError("register read failed")
            if regs[15] == DISPATCH:
                r = row(gdb)
                if actor_seen is None:
                    actor_seen = r["unit"]
                r["i"] = len(rows)
                moved = (r["unit"] == actor_seen
                         and r["tile"] != r["saved"])
                r["moved"] = moved
                rows.append(r)
                mark = "  <-- MOVED" if moved else ""
                print(f"[{r['i']:3d}] phase={r['phase']:2d} "
                      f"flags={r['flags']:#04x} unit={r['unit']:#x} "
                      f"tile={r['tile']} saved={r['saved']}{mark}",
                      flush=True)
                # The actor's own turn is over once the dispatcher runs for a
                # different unit.
                if r["unit"] != actor_seen and len(rows) > 2:
                    print("actor changed - stopping")
                    break
                with open(args.out, "w", newline="\n") as fh:
                    json.dump({"address": DISPATCH, "rows": rows}, fh,
                              indent=1)
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"stopped after {len(rows)} rows: {exc}")
    finally:
        try:
            gdb.send(f"z0,{DISPATCH:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    phases = [r["phase"] for r in rows]
    print(f"\nphase march ({len(rows)} rows): {phases}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
