"""Live confirmation of the phase-3 AI action chooser (docs/ai-findings.md).

The sequencer state machine (head 0x080C045C, phase u16 at ctx+0x54F4,
jump table 0x080C048C) runs its AI phase as:

  phase 0 (0x080C0720)  AI setup -> sub_080C47A8
  phase 1 (0x080C0750)  fill batches -> thunk 0x080C47FC
  phase 2 (0x080C0770)  sorts 0x080C2940 x2, picks 0x080C486C/0x080C4830,
                        resets the AI struct, sets phase 3
  phase 3 (0x080C07C8)  THE CHOOSER: walks the ctx's shadow copies of the
                        sorted arenas (base ctx+0x74 + 0x290C*regime,
                        0x328-stride records), validates each 20-byte
                        candidate through 0x080C32C0, and on the first
                        accepted candidate calls the decision builder
                        0x080C01D0 (result -> ctx+0x528C, then phase 4)
  no-candidate tail     0x080C1222 sets phase 5 directly

This tool breaks at the chooser head (0x080C07C8), the choose-call return
(0x080C09B4, r0 = decision struct) and the no-candidate tail (0x080C1226),
logging the walk indices and the winner.

Prediction to falsify: the walk visits records in sorted order and accepts
the FIRST candidate that passes the validity gate - i.e. the top-ranked
candidate under the priority-ascending key law - so the profile tables'
priority bytes decide which action the enemy takes.

Usage: launch mGBA (WSL, GDB stub on :2345) with the facing savestate, then
  python tools/trace_choose.py [--out outputs/mgba-snowball/choose-trace.json]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_BYTES = "0121c046"   # movs r1, #1 ; nop  (forces A held)
PATCH_ORIG = "811c5940"    # retail

CHOOSER = 0x080C07C8       # phase 3 head
CHOOSE_RET = 0x080C09C2    # after handler store + phase=4 store
NO_CAND = 0x080C1226       # no-candidate tail (sets phase 5)

CTX_PHASE = 0x54F4
CTX_WALK_CAND = 0x54AD    # candidate index byte (marches within a record)
CTX_WALK_REC = 0x54AE     # record index byte
CTX_REGIME = 0x54AC       # regime byte (0 = mode=0 shadow, 1 = mode=1)
SHADOW_BASE = 0x74         # ctx+0x74 + 0x290C*regime = arena shadow
REC_STRIDE = 0x328
REC_COUNT_REL = 0x324      # candidate count halfword inside a record
DECISION_PTR = 0x528C      # chooser's stored action handler
DECISION_STRUCT = 0x5290   # 0x21C-byte decision struct (memset on reject)


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


def rd16(gdb, addr):
    d = rd(gdb, addr, 2)
    return d[0] | (d[1] << 8) if d else None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="outputs/mgba-snowball/choose-trace.json")
    p.add_argument("--max-stops", type=int, default=40)
    p.add_argument("--idle-timeout", type=float, default=60.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    print(f"freeze RNG -> {gdb.send(f'M{RNG:x},4:78563412')!r}")
    for bp in (CHOOSER, CHOOSE_RET, NO_CAND):
        print(f"bp {bp:#010x} -> {gdb.send(f'Z0,{bp:x},2')!r}")

    reply = gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
    print(f"A-force patch -> {reply!r} "
          f"verify={gdb.read_mem(POLL_PATCH, 4).hex()}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")
    verify = None
    for _ in range(5):
        verify = gdb.read_mem(POLL_PATCH, 4)
        if verify:
            break
        time.sleep(0.1)
    print(f"restore retail -> {verify.hex() if verify else 'unreadable'}")

    events = []
    ctx = None
    pending = stop
    gdb.sock.settimeout(args.idle_timeout)
    try:
        while len(events) < args.max_stops:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                raise RuntimeError("register read failed")
            pc = regs[15]
            if pc not in (CHOOSER, CHOOSE_RET, NO_CAND):
                # Interrupt landed between breakpoints; keep waiting.
                pending = None
                continue
            ctx = regs[7]
            ev = {"pc": pc, "ctx": ctx,
                  "phase": rd16(gdb, ctx + CTX_PHASE)}
            if pc == CHOOSER:
                rec = rd8(gdb, ctx + CTX_WALK_REC)
                cand = rd8(gdb, ctx + CTX_WALK_CAND)
                regime = rd8(gdb, ctx + CTX_REGIME)
                ev.update(rec=rec, cand=cand, regime=regime)
                if regime in (0, 1) and rec is not None:
                    base = ctx + SHADOW_BASE + 0x290C * regime + REC_STRIDE * rec
                    ev["count"] = rd16(gdb, base + REC_COUNT_REL)
                print(f"chooser entry: rec={rec} cand={cand} "
                      f"regime={regime} count={ev.get('count')}")
            elif pc == CHOOSE_RET:
                # Decision builder 0x080C01D0 fills arg0 = ctx+0x5290
                # (0x21C bytes; the same area memset on reject) and the
                # returned action handler is stored at ctx+0x528C.
                dec = ctx + DECISION_STRUCT
                ev["decision"] = dec
                handler = None
                d = rd(gdb, ctx + DECISION_PTR, 4)
                if d:
                    handler = int.from_bytes(d, "little")
                ev["handler"] = handler
                raw = rd(gdb, dec, 0x40)
                if raw:
                    ev["struct_head"] = raw.hex()
                entry = int.from_bytes(raw[8:12], "little") if raw else None
                ev["entry"] = entry
                cand_ptr = None
                d = rd(gdb, dec + 0x14, 4)
                if d:
                    cand_ptr = int.from_bytes(d, "little")
                ev["candidate"] = cand_ptr
                print(f"choose -> decision {dec:#x} handler={handler:#x} "
                      f"entry={entry:#x} candidate={ev.get('candidate')}")
                if raw:
                    print("  head: " + " ".join(
                        f"{raw[i] | (raw[i+1] << 8):04x}"
                        for i in range(0, 0x40, 2)))
            else:
                print(f"no candidate accepted -> phase {ev['phase']}")
            events.append(ev)
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"collection ended after {len(events)} stops: {exc}")

    for bp in (CHOOSER, CHOOSE_RET, NO_CAND):
        gdb.send(f"z0,{bp:x},2")
    try:
        gdb.cont()
    except Exception:
        pass
    gdb.close()

    out = {
        "mode": "choose-trace",
        "chooser": CHOOSER,
        "ctx_fields": {
            "phase": CTX_PHASE, "walk_rec": CTX_WALK_REC,
            "walk_cand": CTX_WALK_CAND, "regime": CTX_REGIME,
            "shadow_base": SHADOW_BASE, "rec_stride": REC_STRIDE,
            "rec_count_rel": REC_COUNT_REL, "decision_ptr": DECISION_PTR,
        },
        "ctx": ctx,
        "events": events,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwrote {args.out}: {len(events)} stops")
    return 0 if events else 1


if __name__ == "__main__":
    sys.exit(main())
