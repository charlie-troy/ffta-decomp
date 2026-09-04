"""Multi-turn scenario capture: force K consecutive enemy turns, snapshot
every sort call's arena summary, and diff retail vs patched behaviour.

Method: from the frozen-seed snowball state, catch the CT tick
(sub_0809DF7C, r0 = battle struct), force the acting enemy's CT to 1000 and
every other unit's CT to a low value through the battle-object records (the
tile mirror the per-frame sync copies into the unit structs). The turn
manager then chains enemy AI turns. At each sort entry hit, snapshot a
per-call summary: mode (r2), per-record count and candidate-0 score/priority,
plus the RNG seed. The per-call sequence is the divergence fingerprint.

Usage: python tools/scenario_capture.py <rom-label> [--turns K]
One run per process; relaunch mGBA between runs. Output appends to
outputs/mgba-snowball/scenario-<rom-label>.jsonl.
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
CT_READY = 1000
CT_HOLD = 0

RECORD_STRIDE = 0x328
MAX_RECORDS = 8
CAND_STRIDE = 0x14


def read_u16(gdb, addr):
    d = read_chunked(gdb, addr, 2)
    return int.from_bytes(d, "little") if d else None


def arena_summary(gdb, arena):
    recs = []
    for i in range(MAX_RECORDS):
        rec = read_chunked(gdb, arena + i * RECORD_STRIDE, 0x328)
        if rec is None:
            return None
        count = int.from_bytes(rec[0x324:0x326], "little")
        if count == 0:
            recs.append({"rec": i, "count": 0})
            continue
        cands = []
        for k in range(min(count, 4)):
            c = rec[4 + k * CAND_STRIDE: 6 + k * CAND_STRIDE]
            s = rec[4 + k * CAND_STRIDE + 0x0C: 4 + k * CAND_STRIDE + 0x0E]
            p = rec[4 + k * CAND_STRIDE + 0x10: 4 + k * CAND_STRIDE + 0x11]
            cands.append({
                "head": c.hex(),
                "score": int.from_bytes(s, "little", signed=True),
                "prio": p[0],
            })
        recs.append({"rec": i, "count": count, "cands": cands})
    return recs


def stop_once(gdb, timeout=30):
    """Continue until the next stop; return registers or None on timeout."""
    try:
        gdb.sock.settimeout(timeout)
        gdb.cont()
        s = gdb._read_packet()
    except Exception:
        return None
    if not s or s[:1] not in ("S", "T"):
        return None
    return gdb.read_registers()


def main():
    args = sys.argv[1:]
    rom_label = args[0] if args else "rom"
    turns = 6
    if "--turns" in args:
        turns = int(args[args.index("--turns") + 1])

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
    battle = regs[0]
    gdb.send(f"z0,{TICK:x},2")

    # Enumerate the battle struct's slot records directly: count at +0x00,
    # records at +0x04 + i*0x108 (unit pointer at +0x00, CT u16 at +0xD0).
    # Force CT ready on every unit that is NOT one of the four known player
    # units, so all enemy-side actors chain turns; players charge naturally.
    count_blob = read_chunked(gdb, battle, 4)
    unit_count = int.from_bytes(count_blob, "little") if count_blob else 0
    print(f"battle struct {hex(battle)}: unit count {unit_count}")

    enemy_slots = []
    player_set = set(PLAYERS)
    for i in range(min(unit_count, 16)):
        ptr_blob = read_chunked(gdb, battle + 4 + i * 0x108, 4)
        if not ptr_blob:
            continue
        uptr = int.from_bytes(ptr_blob, "little")
        if not uptr or uptr in player_set:
            continue
        enemy_slots.append((i, battle + 4 + i * 0x108, uptr))
    print("enemy-side slots:", [(i, hex(u)) for i, _, u in enemy_slots])
    if not enemy_slots:
        print("no enemy slots found; aborting")
        gdb.close()
        return 1

    def force_cts():
        # CT is u16: ready = 1000 = bytes e8 03. Only enemy-side units are
        # forced; players charge naturally and take their guided turns.
        for _, rec, _ in enemy_slots:
            gdb.send(f"M{rec + 0xD0:x},2:e803")

    force_cts()
    print(f"CT forced ready on {len(enemy_slots)} enemy-side slots")

    # Start with A held so the tutorial's guided prompts auto-advance; the
    # collection loop pulses it on IWRAM-dialog stalls (edge-triggered).
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")

    # Protocol-safe collection loop: interrupt the CPU every ~0.4 s and
    # dispatch on where it lands -- tick (re-force the enemy's CT), sort
    # entry (snapshot the arena), or an IWRAM dialog loop (pulse A with a
    # short patched window so edge-triggered modals advance). All writes
    # happen while the CPU is stopped, so the stub stream never desyncs.
    calls = []
    gdb.send(f"Z0,{TICK:x},2")
    gdb.send(f"Z0,{BREAK_AT:x},2")
    mode1_seen = 0
    dialog_pulses = 0
    tick_count = 0
    deadline = time.time() + 480
    a_patched = True
    while mode1_seen < turns and time.time() < deadline:
        try:
            gdb.sock.settimeout(20)
            gdb.interrupt()
            r = gdb.read_registers()
        except Exception:
            break
        if not r:
            break
        pc = r[15]
        if pc == TICK:
            tick_count += 1
            force_cts()
        elif pc == BREAK_AT and r[1] in (8, 0x87):
            mode = 1 if r[1] == 8 else 0
            arena = r[0] + (0x2968 if mode == 1 else 0x5C)
            seed = int.from_bytes(gdb.read_mem(RNG, 4), "little")
            recs = arena_summary(gdb, arena)
            calls.append({
                "index": len(calls),
                "mode": mode,
                "r0": hex(r[0]),
                "seed": seed,
                "records": recs,
            })
            print(f"call {len(calls)}: mode={mode} seed={seed:08x} "
                  f"counts={[rc['count'] for rc in (recs or [])][:6]}")
            if mode == 1:
                mode1_seen += 1
        elif 0x03000000 <= pc < 0x03008000:
            # Parked in IWRAM: a dialog/suspension loop. Give one clean A
            # edge (press for 0.35 s, then release) while the CPU runs.
            if a_patched:
                gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")
                a_patched = False
            else:
                gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
                a_patched = True
            dialog_pulses += 1
        try:
            gdb.cont()
        except Exception:
            break
        time.sleep(0.4)
    try:
        gdb.interrupt()
    except Exception:
        pass
    for bp in (TICK, BREAK_AT):
        gdb.send(f"z0,{bp:x},2")
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")
    print(f"A-patch restored (dialog pulses: {dialog_pulses}, ticks: {tick_count})")

    result = {
        "rom": rom_label,
        "turns_requested": turns,
        "calls": calls,
    }
    out = f"outputs/mgba-snowball/scenario-{rom_label}.jsonl"
    with open(out, "a", newline="\n") as fh:
        fh.write(json.dumps(result) + "\n")
    print("wrote", out)
    try:
        gdb.cont()
    except Exception:
        pass
    gdb.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
