"""Read-only diagnostic of the fix3 battle fixture (single GDB session).

Dumps the battle container header, all 8 battle-slot records, the turn-manager
actor field, and the flag byte, so the A2 slot model can be verified against
what the game is actually doing before any experiment writes.

Usage:
    mgba -g -t outputs/lua-nav/fix3-battle-start.ss0 baserom.gba   # fresh box
    python tools/exp_fixture_diag.py
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402

CONT = 0x020159E4
SLOT0 = 0x020159E8
FLAG0D = 0x0200203D
OUT_JSON = "outputs/lua-nav/fixture-diag.json"


def mgba_pid():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process mgba -ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip() or 0)


def u16(gdb, a):
    d = gdb.read_mem(a, 2)
    return int.from_bytes(d, "little") if d else None


def u32(gdb, a):
    d = gdb.read_mem(a, 4)
    return int.from_bytes(d, "little") if d else None


def main():
    pid = mgba_pid()
    if not pid:
        print("no mGBA process")
        return 1
    print(f"mGBA pid {pid}")
    gdb = Gdb("127.0.0.1", 2345, timeout=10)
    gdb.send("?")
    gdb.interrupt()
    print("GDB attached; CPU halted")

    out = {}
    hdr = [u32(gdb, CONT + i * 4) for i in range(8)]
    out["container_header"] = [f"{h:08x}" if h is not None else None for h in hdr]
    print("container header:", out["container_header"])

    slots = []
    for i in range(8):
        s = SLOT0 + 0x210 * i
        name = u32(gdb, s)
        ct = u16(gdb, s + 0xD0)
        e8 = gdb.read_mem(s + 0xE8, 1)
        e9 = gdb.read_mem(s + 0xE9, 1)
        e6 = gdb.read_mem(s + 0xE6, 1)
        ed = gdb.read_mem(s + 0xED, 1)
        mid = gdb.read_mem(s + 0x104, 1)
        slots.append({
            "slot": i, "name": f"{name:08x}" if name else None,
            "ct": ct, "e6": e6[0] if e6 else None, "e8": e8[0] if e8 else None,
            "e9": e9[0] if e9 else None, "ed": ed[0] if ed else None,
            "mid": mid[0] if mid else None,
        })
        print(f"slot{i}: name={slots[-1]['name']} ct={ct} "
              f"e6={slots[-1]['e6']} e8={slots[-1]['e8']:02x} "
              f"e9={slots[-1]['e9']:02x} ed={slots[-1]['ed']:02x} "
              f"mid={slots[-1]['mid']}")
    out["slots"] = slots

    # turn-manager live state: current actor, ctx phase, sequencer fields
    tm = {
        "actor_0x02015A28": u32(gdb, 0x02015A28),
        "ctx_0x02016750": u32(gdb, 0x02016750),
        "phase_0x02016754": gdb.read_mem(0x02016754, 1),
        "flag0D": gdb.read_mem(FLAG0D, 1),
        "iwram_pc": None,
    }
    tm["phase_0x02016754"] = tm["phase_0x02016754"][0] if tm["phase_0x02016754"] else None
    tm["flag0D"] = tm["flag0D"][0] if tm["flag0D"] else None
    regs = gdb.read_registers()
    if regs:
        tm["pc"] = f"{regs[15]:08x}"
    out["turn_manager"] = tm
    print("turn manager:", tm)

    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {OUT_JSON}")
    gdb.cont()
    return 0


if __name__ == "__main__":
    sys.exit(main())
