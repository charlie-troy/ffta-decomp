"""Measure exact RNG draws inside one mode=1 sort call, live in battle.

Method: break at sub_080C2940 entry (mode=1 hit), optionally engineer a
full-tie arena (count=3, all priority bytes equal), then break at the
caller's return (0x080C0782) and count LCG steps between the two RNG states.
The ANSI C 32-bit LCG makes the step count exact, so one roll shows up as
+1 draw.

Re-certified matrix (2026-09-03, after fixing the count endianness bug --
see tools/probe_key_law.py and docs/ai-findings.md):

  retail, no tie            -> 1 (kind-1 behaviour coin)
  retail, tie               -> 4 (coin + 3 tie rolls; the old +2 came from
                               a big-endian count write looping 768 slots)
  action_selection first,
  targeting retail, tie     -> 3 (coin patched out; tie rolls remain)
  aggressive (ties), no tie -> 1 (coin)
  aggressive + first, tie   -> 0

Usage: python tools/measure_sort_rng.py <rom-label> [--tie]
One run per process; relaunch mGBA between runs.
"""
import json
import sys
import time

sys.path.insert(0, "tools")
from trace_mgba import Gdb  # noqa: E402
from dump_candidates import BREAK_AT, read_chunked  # noqa: E402

RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_BYTES = "0121c046"
PATCH_ORIG = "811c5940"
TICK = 0x0809DF7C
ENEMY = 0x02002FC4
PLAYERS = [0x020030CC, 0x020031D4, 0x020032DC, 0x020034EC]
ADJACENT = [(1, 0), (-1, 0), (0, 1), (0, -1)]
SORT_RETURN = 0x080C0782
OUT = "outputs/mgba-snowball/tie-live.json"
LCG_MAX_STEPS = 2_000_000

LCGS = {
    "ansi": (1103515245, 12345, 1 << 32),
    "msvc": (214013, 2531011, 1 << 32),
}


def lcg_steps(a, b):
    for name, (mul, add, mod) in LCGS.items():
        x, n = a, 0
        while n < LCG_MAX_STEPS:
            if x == b:
                return name, n
            x = (x * mul + add) % mod
            n += 1
    return None, None


def u8(gdb, addr):
    d = gdb.read_mem(addr, 1)
    return d[0] if d else None


def main():
    rom_label = sys.argv[1] if len(sys.argv) > 1 else "rom"
    with_tie = "--tie" in sys.argv
    gdb = Gdb("127.0.0.1", 2345, timeout=20)
    gdb.send("?")
    gdb.send(f"M{RNG:x},4:78563412")
    gdb.send(f"Z0,{TICK:x},2")
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")
    pending, regs = stop, None
    gdb.sock.settimeout(60)
    for _ in range(3):
        if pending is None:
            gdb.cont()
            pending = gdb._read_packet()
        if pending and pending[:1] in ("S", "T"):
            regs = gdb.read_registers()
            if regs and regs[15] == TICK:
                break
            pending = None
    if not regs or regs[15] != TICK:
        print("tick never hit")
        gdb.close()
        return 1
    gdb.send(f"z0,{TICK:x},2")

    # Teleport for context (also exercises engineered positions).
    lo = 0x02015B00
    blob = read_chunked(gdb, lo, 0xA00)
    recs = {}
    for name, p in ([("enemy", ENEMY)]
                    + [(f"p{i}", p) for i, p in enumerate(PLAYERS)]):
        x, y, h = (u8(gdb, p + a) for a in (0xF6, 0xF7, 0xF8))
        sig = bytes([x, y, h, x, y])
        hits_ = [lo + o for o in range(0xA00 - 4) if blob[o:o + 5] == sig]
        recs[name] = hits_[0] if len(hits_) == 1 else None
    if all(v for k, v in recs.items() if k != "enemy"):
        ex, ey = u8(gdb, ENEMY + 0xF6), u8(gdb, ENEMY + 0xF7)
        eh = u8(gdb, ENEMY + 0xF8)
        for (dx, dy), name in zip(ADJACENT, ["p0", "p1", "p2", "p3"]):
            base = recs[name]
            nx, ny = ex + dx, ey + dy
            for o, v in ((0, nx), (1, ny), (2, eh), (3, nx), (4, ny)):
                gdb.send(f"M{base + o:x},1:{v & 0xFF:02x}")
        print("teleports applied")
    else:
        print("teleport skipped (ambiguous records)")

    # Wait for the mode=1 sort entry.
    gdb.send(f"Z0,{BREAK_AT:x},2")
    hit = None
    gdb.sock.settimeout(90)
    for _ in range(4):
        gdb.cont()
        s = gdb._read_packet()
        if not s or s[:1] not in ("S", "T"):
            break
        r = gdb.read_registers()
        if r and r[15] == BREAK_AT and r[2] == 1 and r[1] == 8:
            hit = r
            break
    if not hit:
        print("mode=1 sort hit not reached")
        gdb.close()
        return 1

    arena = hit[0] + 0x2968
    rng_entry = int.from_bytes(gdb.read_mem(RNG, 4), "little")
    if with_tie:
        cand0 = arena + 4
        base_cand = gdb.read_mem(cand0, 0x14)
        cand1 = bytearray(base_cand)
        cand1[0x00:0x02] = (0x1111).to_bytes(2, "little")
        cand2 = bytearray(base_cand)
        cand2[0x00:0x02] = (0x2222).to_bytes(2, "little")
        cand2[0x0C:0x0E] = (40).to_bytes(2, "little", signed=True)
        gdb.send(f"M{cand0 + 0x14:x},20:{bytes(cand1).hex()}")
        gdb.send(f"M{cand0 + 0x28:x},20:{bytes(cand2).hex()}")
        # Count is a little-endian u16: for count=3 write bytes 03 00.
        gdb.send(f"M{arena + 0x324:x},2:{3:02x}00")
        print("tie engineered: count=3, scores 51/51/40")
    else:
        print("control run: no engineering")

    # Break at the caller's return and measure.
    gdb.send(f"Z0,{SORT_RETURN:x},2")
    gdb.send(f"z0,{BREAK_AT:x},2")
    gdb.cont()
    s = gdb._read_packet()
    r = gdb.read_registers()
    gdb.send(f"z0,{SORT_RETURN:x},2")
    if not s or s[:1] not in ("S", "T") or not r or r[15] != SORT_RETURN:
        print(f"return stop unexpected: {s!r} pc={r[15]:#010x}" if r else f"{s!r}")
        gdb.close()
        return 1
    rng_exit = int.from_bytes(gdb.read_mem(RNG, 4), "little")
    kind, steps = lcg_steps(rng_entry, rng_exit)
    result = {
        "rom": rom_label,
        "tie": with_tie,
        "rng_entry": rng_entry,
        "rng_exit": rng_exit,
        "lcg": kind,
        "draws": steps,
    }
    print(json.dumps(result))
    with open(OUT, "a", newline="\n") as fh:
        fh.write(json.dumps(result) + "\n")
    try:
        gdb.cont()
    except Exception:
        pass
    gdb.close()
    return 0 if steps is not None else 1


if __name__ == "__main__":
    sys.exit(main())
