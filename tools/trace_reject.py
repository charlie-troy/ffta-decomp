"""Attribute every gate rejection in the retail battle to its check site.

The validity gate (0x080C32C0) funnels every failing check through one
shared return-0 tail, `0x080C478C`. A breakpoint there + the return address
(LR; minus 4 recovers the bl that reached the tail) names the exact check
that rejected each candidate. Walk position comes from the fixed sequencer
context (0x020101F8): regime byte at +0x54AC, candidate index at +0x54AD,
record index at +0x54AE.

Retail (frozen RNG, facing state): ZERO tail hits — the chooser's pre-gate
sign check rejects every regime-0 candidate before the gate is called, and
no regime-1 candidate fails. With --negate (all seven candidates rewritten
damage-rule + score -1, malformed by design) every candidate is rejected
by rule 0x15's positive-score helper `0x080C442E` (the mirror of rule
0x26's negative-score inline check).

Usage: mGBA with the facing savestate, then
  python tools/trace_reject.py           # retail: expect no tail hits
  python tools/trace_reject.py --negate  # malformed: rule-0x15 sign rejects
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402
from dump_candidates import BREAK_AT  # noqa: E402
from probe_pool_law import inject_arena, ARENA_M0, ARENA_M1  # noqa: E402

RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_BYTES = "0121c046"
PATCH_ORIG = "811c5940"

TAIL = 0x080C478C          # the gate's shared reject tail
GATE_LO, GATE_HI = 0x080C32C0, 0x080C4790
CTX = 0x020101F8           # fixed sequencer context (docs/ai-findings.md)

CHECKS = {   # keyed by the bl (call-site) address; lr - 4 recovers it
    0x080C32E0: "cand+0x11 flag bit0",
    0x080C32EC: "cand+0x11 flag bit1",
    0x080C3312: "ability 0x109 special case",
    0x080C3328: "cost meter empty (field 0x13)",
    0x080C3346: "cost exceeds caster meter (+0x1C)",
    0x080C337C: "ability class +0x19==2 but target HP >= max/2",
    0x080C3390: "self-target guard A (0x080CDB54)",
    0x080C33A0: "self-target guard B (0x080CDB6C)",
    0x080C33BA: "caster status 0x080CDB54 + negative score",
    0x080C3E84: "rule-0x26 score not negative (inline check)",
    0x080C3B22: "rule-0x15 score not positive (helper 0x080C442E)",
    0x080C3EA6: "rule-0x26 target HP > max/3",
}


def rd(gdb, addr, n):
    for _ in range(3):
        d = gdb.read_mem(addr, n)
        if d and len(d) == n:
            return d
        time.sleep(0.05)
    return None


def walk_state(gdb):
    d = rd(gdb, CTX + 0x54AC, 3)
    if not d:
        return None
    return d[0], d[1], d[2]   # regime, cand, rec


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--negate", action="store_true",
                   help="negate every candidate's score first (malformed "
                        "damage+negative candidates exercise the gate)")
    args = p.parse_args()

    gdb = Gdb("127.0.0.1", 2345, timeout=20)
    gdb.send("?")
    print(f"freeze RNG -> {gdb.send(f'M{RNG:x},4:78563412')!r}")
    # Sync at the sort entry first: the turn's gate rejections all happen
    # after this point, so syncing here avoids racing the pre-turn frames.
    print(f"bp sort {BREAK_AT:#010x} -> {gdb.send(f'Z0,{BREAK_AT:x},2')!r}")
    print(f"bp tail {TAIL:#010x} -> {gdb.send(f'Z0,{TAIL:x},2')!r}")
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
    gdb.cont()
    time.sleep(10 / 30)
    pending = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")

    # Consume stops until the mode=1 sort entry (r2=1, r1=8).
    gdb.sock.settimeout(90)
    synced = False
    for _ in range(6):
        if pending is None:
            gdb.cont()
            pending = gdb._read_packet()
        if not pending or pending[:1] not in ("S", "T"):
            break
        regs = gdb.read_registers()
        if regs and len(regs) >= 16 and regs[15] == BREAK_AT:
            synced = True
            break
        pending = None
    if not synced:
        print("sort entry never reached")
        gdb.close()
        return 1
    gdb.send(f"z0,{BREAK_AT:x},2")
    print("synced at sort entry; watching the reject tail")
    if args.negate:
        r = gdb.read_registers()
        inject_arena(gdb, r[0], ARENA_M0, "mode=0 (help pool)")
        inject_arena(gdb, r[0], ARENA_M1, "mode=1 (harm pool)")

    events = []
    gdb.sock.settimeout(60)
    try:
        for _ in range(30):
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                pending = None
                continue
            pc = regs[15] & ~1
            if pc != TAIL:
                pending = None
                continue
            lr = regs[14] & ~1
            if not (GATE_LO <= lr < GATE_HI):
                pending = None
                continue
            w = walk_state(gdb)
            site_addr = lr - 4          # bl call site that reached the tail
            site = CHECKS.get(site_addr, f"unknown check at {site_addr:#010x}")
            print(f"REJECT regime={w[0] if w else '?'} "
                  f"rec={w[2] if w else '?'} cand={w[1] if w else '?'} "
                  f"by {site}")
            events.append({"lr": lr, "site": site, "walk": w})
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"ended after {len(events)} events: {exc}")
    gdb.send(f"z0,{TAIL:x},2")
    try:
        gdb.cont()
    except Exception:
        pass
    gdb.close()
    return 0 if events else 1


if __name__ == "__main__":
    sys.exit(main())
