"""Causal test of the arena pool law (docs/ai-findings.md).

The chooser (0x080C07C8) applies a regime-dependent sign check on the
candidate's projected-magnitude score: regime 0 (mode=0 arena) accepts only
negative scores, regime 1 (mode=1 arena) only positive ones. Retail in the
snowball battle: all scores positive -> regime 0 rejected, regime 1 record 0
accepted.

Modes:

  --negate      inject a negative score (0xFFFF) into every candidate in BOTH
                arenas, keeping their damage rules. Observed result: the walk
                rejects everything (passive turn) - a damage rule with a
                negative score is malformed and the gate's sign-coupled checks
                reject it.

  --heal        rewrite the mode=0 (help pool) candidates into recovery-form
                candidates (rule 0x26, score -1) WITHOUT touching target HP.
                Observed result: still rejected - rule 0x26's handler
                (0x080C3E7A) requires the target's current HP to be at or
                below max/3 (HP getter 0x080C7EA4: +0x13 = current HP u16 at
                unit+0x18, +0x14 = max HP u16 at unit+0x1A; compare vs
                max_hp / 3 via 0x08142AB0), so full-HP targets hard-reject.

  --heal-wound  --heal PLUS wound every mode=0 candidate's target to exactly
                max/3 before the chooser runs. Prediction: rule 0x26 passes,
                and since the chooser walks regime 0 first, the heal candidate
                is ACCEPTED (the pool flip, certifying the law causally).

Usage: mGBA with the facing savestate, then
  python tools/probe_pool_law.py --heal-wound
  python tools/probe_pool_law.py --heal
  python tools/probe_pool_law.py --negate
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402
from dump_candidates import BREAK_AT  # noqa: E402

RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_BYTES = "0121c046"
PATCH_ORIG = "811c5940"

ARENA_M0 = 0x5C        # mode=0 arena base (help pool)
ARENA_M1 = 0x2968      # mode=1 arena base (harm pool)
REC_STRIDE = 0x328
REC_COUNT_REL = 0x324
CAND_SCORE = 0x0C      # s16 inside the 20-byte candidate at rec+4

CHOOSER = 0x080C07C8
CHOOSE_RET = 0x080C09C2
GATE_RET = 0x080C082C      # chooser: after bl 0x080C32C0 (validity gate)
RULE26 = 0x080C3E7A        # gate: rule 0x26 (recovery) handler entry
RULE26_HPFAIL = 0x080C3EA6  # gate: rule 0x26 hp > max/3 reject path
RULE26_ADV = 0x080C3EE6    # gate: rule 0x26 roll-fail advance (bl 0x477A)
NEG = "ffff"


def rd(gdb, addr, n):
    for _ in range(3):
        d = gdb.read_mem(addr, n)
        if d and len(d) == n:
            return d
        time.sleep(0.05)
    return None


def rd16(gdb, addr):
    d = rd(gdb, addr, 2)
    return d[0] | (d[1] << 8) if d else None


def rd32(gdb, addr):
    d = rd(gdb, addr, 4)
    return int.from_bytes(d, "little") if d else None


def wr(gdb, addr, data):
    gdb.send(f"M{addr:x},{len(data):x}:{bytes(data).hex()}")


def heal_candidates(gdb, ai, wound):
    """Rewrite mode=0 (help pool) candidates to well-formed recovery form."""
    injected = 0
    for k in range(4):
        rec = ai + ARENA_M0 + REC_STRIDE * k
        count = rd16(gdb, rec + REC_COUNT_REL)
        if not count:
            continue
        # The record's target unit: rec+0 -> 0x90-stride action entry,
        # entry+0 -> target unit pointer (docs/ai-findings.md).
        entry = rd32(gdb, rec)
        unit = rd32(gdb, entry) if entry else None
        if wound and unit:
            cur = rd16(gdb, unit + 0x18)
            mx = rd16(gdb, unit + 0x1A)
            if cur is None or mx is None or not (0 < mx <= 999):
                print(f"  rec{k}: unit read failed at {unit:#010x} "
                      f"(hp={cur}, max={mx})")
            else:
                floor = mx // 3
                print(f"  rec{k}: unit {unit:#010x} hp {cur}/{mx} "
                      f"(rule 0x26 needs <= {floor})")
                if cur > floor:
                    wr(gdb, unit + 0x18, floor.to_bytes(2, "little"))
                    print(f"    wounded -> {floor}")
        for c in range(min(count, 10)):
            addr = rec + 4 + 0x14 * c
            base = rd(gdb, addr, 0x14)
            if not base:
                continue
            cand = bytearray(base)
            if wound and unit:
                pass  # unit already wounded above (shared per record)
            cand[0x04:0x06] = (0x26).to_bytes(2, "little")  # recovery rule
            cand[0x0A:0x0C] = (1).to_bytes(2, "little")     # rule count
            cand[0x0E:0x10] = (0x26).to_bytes(2, "little")  # rule id copy
            cand[CAND_SCORE:CAND_SCORE + 2] = bytes.fromhex(NEG)
            wr(gdb, addr, bytes(cand))
            injected += 1
    print(f"recovery-rewrote {injected} mode=0 (help pool) candidates "
          f"(wound={wound})")
    return injected


def inject_arena(gdb, ai, base_rel, label, max_recs=4):
    """Negate scores (the malformed-injection control)."""
    injected = 0
    for k in range(max_recs):
        rec = ai + base_rel + REC_STRIDE * k
        count = rd16(gdb, rec + REC_COUNT_REL)
        if not count:
            continue
        for c in range(min(count, 10)):
            addr = rec + 4 + 0x14 * c
            base = rd(gdb, addr, 0x14)
            if not base:
                continue
            cand = bytearray(base)
            old = cand[CAND_SCORE] | (cand[CAND_SCORE + 1] << 8)
            if old < 0x8000:          # only flip positive scores
                cand[CAND_SCORE:CAND_SCORE + 2] = bytes.fromhex(NEG)
            else:
                continue
            wr(gdb, addr, bytes(cand))
            injected += 1
    print(f"negated {injected} {label} candidates")
    return injected


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--heal", action="store_true",
                   help="rewrite mode=0 candidates to recovery form "
                        "(targets untouched - rule 0x26 rejects full-HP)")
    p.add_argument("--heal-wound", action="store_true",
                   help="--heal plus wound targets to max/3 so rule 0x26 "
                        "passes")
    p.add_argument("--negate", action="store_true",
                   help="negate every candidate's score (both arenas)")
    args = p.parse_args()
    gdb = Gdb("127.0.0.1", 2345, timeout=20)
    gdb.send("?")
    # Gate-trace breakpoints: rule-0x26 internals + the gate return site.
    trace_bps = (GATE_RET, RULE26, RULE26_HPFAIL, RULE26_ADV) \
        if (args.heal_wound or args.heal) else ()
    for bp in trace_bps:
        gdb.send(f"Z0,{bp:x},2")
    gdb.send(f"M{RNG:x},4:78563412")
    gdb.send(f"Z0,{BREAK_AT:x},2")
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
    gdb.cont()
    time.sleep(10 / 30)
    pending = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")

    # Reach the mode=1 sort entry (r2=1, r1=8) where r0 = the AI struct.
    gdb.sock.settimeout(90)
    hit = None
    for _ in range(4):
        if pending is None:
            gdb.cont()
            pending = gdb._read_packet()
        if not pending or pending[:1] not in ("S", "T"):
            break
        r = gdb.read_registers()
        if r and r[15] == BREAK_AT and r[2] == 1 and r[1] == 8:
            hit = r
            break
        pending = None
    if not hit:
        print("mode=1 sort entry not reached")
        gdb.close()
        return 1
    ai = hit[0]
    gdb.send(f"z0,{BREAK_AT:x},2")
    print(f"at mode=1 sort entry, ai={ai:#x}")

    if args.heal_wound:
        n0 = heal_candidates(gdb, ai, wound=True)
        n1 = 0
    elif args.heal:
        n0 = heal_candidates(gdb, ai, wound=False)
        n1 = 0
    else:  # default = negate both (the malformed-injection control)
        n0 = inject_arena(gdb, ai, ARENA_M0, "mode=0 (help pool)")
        n1 = inject_arena(gdb, ai, ARENA_M1, "mode=1 (harm pool)")
    if not (n0 or n1):
        print("nothing injected - aborting")
        gdb.close()
        return 1

    # Watch the chooser walk.
    for bp in (CHOOSER, CHOOSE_RET):
        gdb.send(f"Z0,{bp:x},2")
    accepted = None
    walk = []
    pending = None
    try:
        for _ in range(40):
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                raise RuntimeError("register read failed")
            pc = regs[15]
            if pc in trace_bps:
                if pc == GATE_RET:
                    ctx = regs[7]
                    w = rd(gdb, ctx + 0x54AC, 3)
                    regime, cand_i, rec_i = w if w else (0, 0, 0)
                    print(f"  gate ret: regime={regime} rec={rec_i} "
                          f"cand={cand_i} r0={regs[0]:#x} "
                          f"{'PASS' if regs[0] else 'REJECT'}")
                else:
                    name = {RULE26: "rule26 enter",
                            RULE26_HPFAIL: "rule26 HP>max/3 reject",
                            RULE26_ADV: "rule26 roll-fail advance"}[pc]
                    print(f"  {name} (lr={regs[14]:#x})")
                pending = None
                continue
            if pc == CHOOSER:
                ctx = regs[7]
                w = rd(gdb, ctx + 0x54AC, 3)
                regime, cand, rec = w if w else (0, 0, 0)
                walk.append((regime, rec, cand))
            elif pc == CHOOSE_RET:
                ctx = regs[7]
                w = rd(gdb, ctx + 0x54AC, 3)
                regime, cand, rec = w if w else (0, 0, 0)
                accepted = (regime, rec, cand)
                print(f"ACCEPTED at regime={regime} rec={rec} cand={cand}")
                break
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"walk ended: {exc}")

    for bp in (CHOOSER, CHOOSE_RET) + trace_bps:
        gdb.send(f"z0,{bp:x},2")
    try:
        gdb.cont()
    except Exception:
        pass
    gdb.close()

    print(f"\nwalk (regime, rec, cand): {walk[:12]}")
    if accepted is None:
        print("RESULT: no candidate accepted (passive turn)")
        return 0
    print(f"RESULT: accepted at regime {accepted[0]} "
          f"({'help pool' if accepted[0] == 0 else 'harm pool'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
