"""Live confirmation of the execution engine's per-frame polling.

Sequencer phase 4 (0x080C09EC) calls the action handler through the
0x0814224C veneer (r2 = [ctx+0x528C] = 0x080BF7C5) with r0 = the decision
struct (ctx+0x5290) and r1 = the turn object (ctx[0]), then yields a frame
while the handler returns 0; nonzero hands off to phase 5. The handler is
itself a 5-phase state machine (dispatch u16 at +0x1B8, table 0x080BF7EC).

This tool breaks at the handler head (0x080BF7C4) and at the sequencer's
post-call site (0x080C09FC, r0 = handler return; 0 = finished, nonzero =
keep polling), logging the machine's phase and per-call results.

Prediction: many head stops (one per frame) with the +0x1B8 phase marching
0 -> 1 -> 3 -> 4, and the final call returning 0 (0 = finished, nonzero =
poll again next frame).

Usage: mGBA with the facing savestate, then
  python tools/trace_exec.py
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

HANDLER = 0x080BF7C4   # execution machine head
POST_CALL = 0x080C09FC # sequencer: after the veneer call, r0 = return


def rd(gdb, addr, n):
    for _ in range(3):
        d = gdb.read_mem(addr, n)
        if d and len(d) == n:
            return d
        time.sleep(0.05)
    return None


def main():
    gdb = Gdb("127.0.0.1", 2345, timeout=20)
    gdb.send("?")
    print(f"freeze RNG -> {gdb.send(f'M{RNG:x},4:78563412')!r}")
    for bp in (HANDLER, POST_CALL):
        print(f"bp {bp:#010x} -> {gdb.send(f'Z0,{bp:x},2')!r}")
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
    gdb.cont()
    time.sleep(10 / 30)
    pending = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")

    events = []
    gdb.sock.settimeout(90)
    try:
        while len(events) < 400:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                raise RuntimeError("register read failed")
            pc = regs[15]
            if pc == HANDLER:
                dec = regs[0]
                d = rd(gdb, dec + 0x1B8, 2)
                phase = (d[0] | (d[1] << 8)) if d else None
                events.append({"pc": pc, "phase": phase})
            elif pc == POST_CALL:
                ctx = regs[7]
                events.append({"pc": pc, "ret": regs[0]})
                print(f"handler returned {regs[0]:#x} after "
                      f"{sum(1 for e in events if e['pc'] == HANDLER)} calls")
                # Polarity: 0 = the action finished (sequencer advances to
                # phase 5); nonzero = keep polling next frame.
                if regs[0] == 0:
                    break
            else:
                pending = None
                continue
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"ended after {len(events)} events: {exc}")
    for bp in (HANDLER, POST_CALL):
        gdb.send(f"z0,{bp:x},2")
    try:
        gdb.cont()
    except Exception:
        pass
    gdb.close()

    heads = [e["phase"] for e in events if e["pc"] == HANDLER]
    print(f"\n{len(heads)} handler calls; phase sequence (first 40): "
          f"{heads[:40]}")
    print("transitions:", [p for i, p in enumerate(heads)
                           if i == 0 or p != heads[i - 1]])
    rets = [e["ret"] for e in events if e["pc"] == POST_CALL]
    print("returns per call (first 12):", rets[:12])
    return 0 if events else 1


if __name__ == "__main__":
    sys.exit(main())
