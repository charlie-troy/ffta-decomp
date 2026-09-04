"""Which gate check rejects the regime-0 candidates? (in-vivo verdict)

The chooser (0x080C07C8) calls the validity gate 0x080C32C0 at 0x080C0828;
after the call it requires r0 != 0 AND the shadow record's s16 at +0x84 > 0
before building the decision. This tracer breaks at 0x080C082C (gate
returned), logs r0 plus the candidate address/ability, and at the reject
tails (0x080C1222/0x080C1226) logs the walk position - so each rejection is
attributed to either the gate (r0 == 0) or the +0x84 sign check (r0 != 0).

Usage: mGBA with the facing savestate, then
  python tools/trace_gate.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_BYTES = "0121c046"
PATCH_ORIG = "811c5940"

GATE_RET = 0x080C082C   # instruction after bl 0x080C32C0
REJECT_A = 0x080C1222   # regime-0 reject tail
REJECT_B = 0x080C1226   # regime-1 reject tail
CTX = None


def rd(gdb, addr, n):
    for _ in range(3):
        d = gdb.read_mem(addr, n)
        if d and len(d) == n:
            return d
        time.sleep(0.05)
    return None


def rd8(gdb, addr):
    d = rd(gdb, addr, 1)
    return d[0] if d else None


def main():
    gdb = Gdb("127.0.0.1", 2345, timeout=20)
    gdb.send("?")
    print(f"freeze RNG -> {gdb.send(f'M{RNG:x},4:78563412')!r}")
    for bp in (GATE_RET, REJECT_A, REJECT_B):
        print(f"bp {bp:#010x} -> {gdb.send(f'Z0,{bp:x},2')!r}")
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")

    events = []
    pending = stop
    gdb.sock.settimeout(60)
    try:
        while len(events) < 24:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                raise RuntimeError("register read failed")
            pc = regs[15]
            if pc not in (GATE_RET, REJECT_A, REJECT_B):
                pending = None
                continue
            ctx = regs[7]
            if pc == GATE_RET:
                # r2 still holds the candidate pointer arg (saved at sp+0xc
                # by the callee, but r2 is dead by now) - use the walk regs.
                cand_i = rd8(gdb, ctx + 0x54AD)
                rec_i = rd8(gdb, ctx + 0x54AE)
                regime = rd8(gdb, ctx + 0x54AC)
                r0 = regs[0]
                verdict = "GATE-PASS" if r0 else "GATE-REJECT"
                # The chooser's sign-check s16 (code formula verbatim:
                # ctx + 0x74 + 0x290C*regime + 0x328*rec + 0x14*cand + 0x10
                # = candidate + 0x0C = the impact score).
                score = None
                d = rd(gdb, ctx + 0x74 + 0x290C * regime + 0x328 * rec_i
                       + 0x14 * cand_i + 0x10, 2)
                if d:
                    v = d[0] | (d[1] << 8)
                    if v >= 0x8000:
                        v -= 0x10000
                    score = v
                print(f"gate ret: regime={regime} rec={rec_i} cand={cand_i} "
                      f"r0={r0:#x} {verdict} score={score}")
                events.append({"pc": pc, "r0": r0, "regime": regime,
                               "rec": rec_i, "cand": cand_i, "score": score})
            else:
                cand_i = rd8(gdb, ctx + 0x54AD)
                rec_i = rd8(gdb, ctx + 0x54AE)
                regime = rd8(gdb, ctx + 0x54AC)
                print(f"reject tail {pc:#x}: regime={regime} rec={rec_i} "
                      f"cand={cand_i}")
                events.append({"pc": pc, "regime": regime, "rec": rec_i,
                               "cand": cand_i})
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"ended after {len(events)} events: {exc}")
    for bp in (GATE_RET, REJECT_A, REJECT_B):
        gdb.send(f"z0,{bp:x},2")
    try:
        gdb.cont()
    except Exception:
        pass
    gdb.close()
    return 0 if events else 1


if __name__ == "__main__":
    sys.exit(main())
