"""Identify the sort's key law in vivo: engineer candidates, read the order.

The mode=1 sort orders candidates *within* each 0x328-stride record. This
tool engineers record 0's candidate list at the mode=1 sort entry with a
per-plan (score, priority) assignment, snapshots the record at internal
stages (sort head, post-sort, append head, post-append), and at the caller's
return reads the resulting permutation.

Plans (k1..k5) discriminate the candidate laws:

  score-primary    -> scores end descending, priorities irrelevant
  priority-primary -> priorities end ascending, scores untouched
  sign-gate laws   -> a negative-score candidate is demoted regardless of
                      its priority byte

Executed result (see docs/ai-findings.md): sign gates first, then priority
byte ASCENDING as the real key, scores moving non-monotonically; the earlier
"score is the primary key" doc reading was corrected on this evidence.

Note: the arena count is a little-endian u16 -- write `0400` for count 4,
not `0004` (big-endian 0x0400 = 1024 garbage slots).

Usage: python tools/probe_key_law.py <plan-key>   (one run per process;
relaunch mGBA between runs -- established pattern)
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
OUT = "outputs/mgba-snowball/keylaw.jsonl"

STAGES = [
    ("sort-head", 0x080C2D14),
    ("post-sort", 0x080C2FE8),
    ("append-head", 0x080C30B2),
    ("post-append", 0x080C310A),
]

# (score, priority) engineered into candidates 0..3, seeded per run for the
# tie-coin sample. cand1/cand3 stay identical -> full tie.
PLANS = {
    # k1: score tie 50/50, prio breaks it (run 1 result: ascending score,
    # prio descending within equal score)
    "k1": [(30, 90), (50, 80), (50, 90), (70, 10)],
    # k2: reversed input order of the same key multiset -> order-independence
    "k2": [(90, 10), (70, 70), (50, 80), (30, 90)],
    # k3: prio tie-break sampled with a different arrangement
    "k3": [(30, 10), (50, 90), (50, 80), (70, 90)],
    # k4: negative INCUMBENT with prio already ascending -> does the
    # incumbent<=0 sign-gate force a swap the prio order does not want?
    "k4": [(-5, 10), (60, 90), (61, 95), (62, 99)],
    # k5: negative CHALLENGER where prio wants a swap -> does the
    # challenger<0 sign-gate block it?
    "k5": [(60, 90), (-5, 10), (61, 95), (62, 99)],
}
SEEDS = {
    "k1": 0x11111111,
    "k2": 0x22222222,
    "k3": 0x33333333,
    "k4": 0x44444444,
    "k5": 0x55555555,
}


def u8(gdb, addr):
    d = gdb.read_mem(addr, 1)
    return d[0] if d else None


def snapshot(gdb, arena, count):
    out = []
    for i in range(min(count, 8)):
        rec = read_chunked(gdb, arena + 4 + i * 0x14, 0x14)
        if rec is None:
            return None
        out.append({
            "idx": i,
            "score": int.from_bytes(rec[0x0C:0x0E], "little", signed=True),
            "prio": int.from_bytes(rec[0x10:0x11], "little", signed=True),
            "head": rec[0x00:0x04].hex(),
        })
    return out


def main():
    rom_label = sys.argv[1] if len(sys.argv) > 1 else "rom"
    plan_key = rom_label if rom_label in PLANS else "k1"
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

    # Teleport the players next to the enemy actor for a full arena.
    lo = 0x02015B00
    blob = read_chunked(gdb, lo, 0xA00)
    recs = {}
    for name, p in ([( "enemy", ENEMY)]
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
    rec0 = arena
    count_raw = read_chunked(gdb, rec0 + 0x324, 2)
    count = int.from_bytes(count_raw, "little") if count_raw else 0
    before = snapshot(gdb, rec0, count)
    print("entry:", json.dumps({"count": count, "cands": before}))

    # Freeze the RNG at the entry so the tie coin is seed-controlled.
    seed = SEEDS[plan_key]
    gdb.send(f"M{RNG:x},4:{seed:08x}")

    # Engineer record 0: count=4 with orthogonal keys (base each candidate on
    # the real cand0 so validity/effect bytes stay plausible).
    base = read_chunked(gdb, rec0 + 4, 0x14)
    if base is None:
        print("candidate read failed")
        gdb.close()
        return 1
    plan = PLANS[plan_key]
    for i, (score, prio) in enumerate(plan):
        cand = bytearray(base)
        cand[0x0C:0x0E] = (score & 0xFFFF).to_bytes(2, "little")
        cand[0x10:0x11] = bytes([prio & 0xFF])
        addr = rec0 + 4 + i * 0x14
        gdb.send(f"M{addr:x},20:{bytes(cand).hex()}")
    count = len(plan)
    # Count is a little-endian u16: for count=4 write bytes 04 00.
    gdb.send(f"M{rec0 + 0x324:x},2:{count:02x}00")
    mid = snapshot(gdb, rec0, count)
    print("engineered:", json.dumps(mid))

    # Timeline: snapshot rec0 at each internal stage. The stages:
    #   0x080C2D14  sort double-loop head (per candidate pass)
    #   0x080C2FE8  post-sort / pre-BST-walk decision point
    #   0x080C30B2  append loop head
    #   0x080C310A  post-append
    STAGES = [
        ("sort-head", 0x080C2D14),
        ("post-sort", 0x080C2FE8),
        ("append-head", 0x080C30B2),
        ("post-append", 0x080C310A),
    ]
    timeline = []
    for label, addr in STAGES:
        gdb.send(f"Z0,{addr:x},2")
        for _ in range(3):
            gdb.cont()
            s = gdb._read_packet()
            if not s or s[:1] not in ("S", "T"):
                break
            r = gdb.read_registers()
            if r and r[15] == addr:
                snap = snapshot(gdb, rec0, max(count, 1))
                cnt = read_chunked(gdb, rec0 + 0x324, 2)
                timeline.append({
                    "stage": label,
                    "pc": hex(addr),
                    "count": int.from_bytes(cnt, "little") if cnt else None,
                    "slots": snap,
                })
                print(f"[{label}]", json.dumps(timeline[-1]))
                break
        else:
            timeline.append({"stage": label, "pc": hex(addr), "missed": True})
            print(f"[{label}] missed")
        gdb.send(f"z0,{addr:x},2")

    # Break at the sort's return and read the final permutation.
    gdb.send(f"Z0,{SORT_RETURN:x},2")
    gdb.cont()
    s = gdb._read_packet()
    r = gdb.read_registers()
    gdb.send(f"z0,{SORT_RETURN:x},2")
    if not s or s[:1] not in ("S", "T") or not r or r[15] != SORT_RETURN:
        print(f"return stop unexpected: {s!r} pc={r[15]:#010x}" if r else f"{s!r}")
        gdb.close()
        return 1
    after = snapshot(gdb, rec0, max(count, 1))
    cnt = read_chunked(gdb, rec0 + 0x324, 2)
    final_count = int.from_bytes(cnt, "little") if cnt else None
    order = [c["idx"] for c in after] if after else None
    print("final:", json.dumps({"count": final_count, "slots": after}))
    result = {
        "rom": rom_label,
        "seed": seed,
        "count": count,
        "entry": before,
        "engineered": mid,
        "timeline": timeline,
        "sorted": after,
        "final_count": final_count,
        "order": order,
    }
    print("order:", order)
    with open(OUT, "a", newline="\n") as fh:
        fh.write(json.dumps(result) + "\n")
    try:
        gdb.cont()
    except Exception:
        pass
    gdb.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
