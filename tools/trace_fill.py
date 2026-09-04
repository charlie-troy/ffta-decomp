"""Live confirmation of the AI candidate fill machine (docs/ai-findings.md).

The fill chain is traced statically: sequencer 0x080C0752 -> thunk
0x080C47FC -> fill machine sub_080C286C -> arena builder sub_080C26EC ->
sub_080C2618 -> sub_080C2314. This tool watches the machine run:

  - breakpoint at the machine's entry (0x080C286C) and log, per batch,
    phase byte [ai+0x5280], resume index [ai+0x527f], pass counter
    [ai+0x5a], cap [ai+0x58], entry count [ai+0x2908];
  - when the pass counter reaches the cap, switch to the sort breakpoint
    and snapshot both arenas at sub_080C2940's entry.

Predictions to falsify: the resume index marches upward per batch until
0xFF, then the arena retires (phase flip, counter increment); after the
cap-th increment the machine returns 0 and the sorts run on complete
arenas. Note: the arena records themselves are pre-created by the setup
stage (sub_080C1B8C initializes them from the target lists), so the
builder's "limit" is the record count the initializer wrote.
"""

Usage: launch mGBA (WSL, GDB stub on :2345), then
  python tools/trace_fill.py [--out outputs/mgba-snowball/fill-trace.json]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402
from dump_candidates import BREAK_AT, snapshot  # noqa: E402

RNG = 0x030034B0
POLL_PATCH = 0x0800048A
PATCH_BYTES = "0121c046"   # movs r1, #1 ; nop  (forces A held)
PATCH_ORIG = "811c5940"    # retail
MACHINE = 0x080C286C

OFF_RESUME = 0x527F
OFF_PHASE = 0x5280
OFF_COUNTER = 0x5A
OFF_CAP = 0x58
# The builder's arg0 is the arena base itself (ai+0x2968 phase 0,
# ai+0x5c phase 1); its record-count limit is the u16 at arena+0x2908.
ARENA = {0: 0x2968, 1: 0x5C}
LIMIT_REL = 0x2908


def rd8(gdb, addr):
    for _ in range(3):
        d = gdb.read_mem(addr, 1)
        if d:
            return d[0]
        time.sleep(0.05)
    return None


def rd16(gdb, addr):
    for _ in range(3):
        d = gdb.read_mem(addr, 2)
        if d and len(d) == 2:
            return d[0] | (d[1] << 8)
        time.sleep(0.05)
    return None


def machine_state(gdb, ai):
    phase = rd8(gdb, ai + OFF_PHASE)
    state = {
        "ai": ai,
        "resume": rd8(gdb, ai + OFF_RESUME),
        "phase": phase,
        "counter": rd16(gdb, ai + OFF_COUNTER),
        "cap": rd16(gdb, ai + OFF_CAP),
    }
    if phase in ARENA:
        state["limit"] = rd16(gdb, ai + ARENA[phase] + LIMIT_REL)
    return state


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="outputs/mgba-snowball/fill-trace.json")
    p.add_argument("--max-batches", type=int, default=80)
    p.add_argument("--idle-timeout", type=float, default=90.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    print(f"freeze RNG -> {gdb.send(f'M{RNG:x},4:78563412')!r}")
    print(f"machine breakpoint {MACHINE:#010x} -> "
          f"{gdb.send(f'Z0,{MACHINE:x},2')!r}")

    reply = gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
    print(f"A-force patch -> {reply!r} "
          f"verify={gdb.read_mem(POLL_PATCH, 4).hex()}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")
    for _ in range(5):
        verify = gdb.read_mem(POLL_PATCH, 4)
        if verify:
            break
        time.sleep(0.1)
    print(f"restore retail -> {verify.hex() if verify else 'unreadable'}")

    batches = []
    ai = None
    pending = stop
    gdb.sock.settimeout(args.idle_timeout)
    try:
        while len(batches) < args.max_batches:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                raise RuntimeError("register read failed")
            if regs[15] != MACHINE:
                # Interrupt landed between batches; keep waiting.
                pending = None
                continue
            ai = regs[0]
            state = machine_state(gdb, ai)
            state["batch"] = len(batches) + 1
            batches.append(state)
            print(f"batch {state['batch']:2d}: phase={state['phase']} "
                  f"resume={state['resume']:#04x} "
                  f"counter={state['counter']}/{state['cap']} "
                  f"limit={state.get('limit')}")
            pending = None
            if state["counter"] >= state["cap"]:
                break
    except (TimeoutError, OSError) as exc:
        print(f"collection ended after {len(batches)} batches: {exc}")

    # Hand off to the sort entry for the final arena state.
    gdb.send(f"z0,{MACHINE:x},2")
    gdb.send(f"Z0,{BREAK_AT:x},2")
    sort_snapshot = None
    try:
        if pending is None:
            gdb.cont()
            pending = gdb._read_packet()
        for _ in range(8):
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if regs[15] == BREAK_AT:
                sort_snapshot = snapshot(gdb, regs, 0)
                break
            pending = None
            gdb.cont()
            pending = gdb._read_packet()
    except (TimeoutError, OSError) as exc:
        print(f"sort wait ended: {exc}")

    out = {
        "mode": "fill-trace",
        "machine": MACHINE,
        "fields": {
            "resume": OFF_RESUME, "phase": OFF_PHASE,
            "counter": OFF_COUNTER, "cap": OFF_CAP,
            "arenas": ARENA, "limit_rel": LIMIT_REL,
        },
        "ai": ai,
        "batches": batches,
        "sort_snapshot": sort_snapshot,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    try:
        gdb.send(f"z0,{BREAK_AT:x},2")
        gdb.cont()
    except Exception:
        pass
    gdb.close()

    print(f"\nwrote {args.out}: {len(batches)} batches, "
          f"sort_snapshot={'yes' if sort_snapshot else 'none'}")
    return 0 if batches else 1


if __name__ == "__main__":
    sys.exit(main())
