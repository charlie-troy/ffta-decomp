"""Live check of the pick stage: what do sub_080C486C/sub_080C4830 copy?

Both breakpoints are set up front and stops are dispatched on PC:
  - 0x080C2940 (sort entry): record the pre-sort arena counts;
  - 0x080C078E (after both sorts): read the count fields again plus the
    sequencer's outputs at battle+8 (mode=0 entry heads), battle+0x3c
    (mode=1 entry heads), battle+0x70 and battle+0x72 (counts).

Executed result: the counts read 4/4 before AND after the sorts - they
are the arena initializer's live record counts (sub_080C1B8C, see
ai-findings.md), not sort outputs, and the pick copies include records
whose candidates were all rejected (empty 20-byte blocks).
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
PATCH_BYTES = "0121c046"
PATCH_ORIG = "811c5940"
SORT_ENTRY = 0x080C2940
SORTS_DONE = 0x080C07AE   # after both strh stores into the ctx
OFF_CNT_MODE0 = 0x2964
OFF_CNT_MODE1 = 0x5270


def rd16(gdb, addr):
    for _ in range(3):
        d = gdb.read_mem(addr, 2)
        if d and len(d) == 2:
            return d[0] | (d[1] << 8)
        time.sleep(0.05)
    return None


def rd_words(gdb, addr, n):
    for _ in range(3):
        d = gdb.read_mem(addr, 4 * n)
        if d and len(d) == 4 * n:
            return [int.from_bytes(d[i:i + 4], "little")
                    for i in range(0, len(d), 4)]
        time.sleep(0.05)
    return None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="outputs/mgba-snowball/pick-trace.json")
    p.add_argument("--max-stops", type=int, default=40)
    p.add_argument("--idle-timeout", type=float, default=90.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    print(f"freeze RNG -> {gdb.send(f'M{RNG:x},4:78563412')!r}")
    print(f"sort-entry bp -> {gdb.send(f'Z0,{SORT_ENTRY:x},2')!r}")
    print(f"sorts-done bp -> {gdb.send(f'Z0,{SORTS_DONE:x},2')!r}")

    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_BYTES}")
    verify = gdb.read_mem(POLL_PATCH, 4)
    print(f"A-force patch -> verify={verify.hex() if verify else '?'}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},4:{PATCH_ORIG}")
    verify = gdb.read_mem(POLL_PATCH, 4)
    print(f"restore retail -> {verify.hex() if verify else '?'}")

    ai = None
    pre = None
    post = None
    pending = stop
    gdb.sock.settimeout(args.idle_timeout)
    try:
        while post is None and len([1]) <= args.max_stops:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                pending = None
                continue
            pc = regs[15]
            if pc == SORT_ENTRY:
                ai = regs[0]
                if pre is None:
                    pre = {
                        "mode0_count": rd16(gdb, ai + OFF_CNT_MODE0),
                        "mode1_count": rd16(gdb, ai + OFF_CNT_MODE1),
                    }
                    print(f"sort entry: ai={ai:#x} pre-sort counts {pre}")
            elif pc == SORTS_DONE and ai is not None:
                # r7 at 0x080C078E is the sequencer ctx; it is still
                # live at 0x080C07AE (used for both strh targets).
                ctx = regs[7]
                post = {
                    "ctx": ctx,
                    "mode0_count": rd16(gdb, ai + OFF_CNT_MODE0),
                    "mode1_count": rd16(gdb, ai + OFF_CNT_MODE1),
                    "ctx8": rd_words(gdb, ctx + 8, 13),
                    "ctx3c": rd_words(gdb, ctx + 0x3C, 13),
                    "ctx70": rd16(gdb, ctx + 0x70),
                    "ctx72": rd16(gdb, ctx + 0x72),
                }
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"collection ended: {exc}")

    if post:
        print(f"post-sort: counts "
              f"{post['mode0_count']}/{post['mode1_count']}, "
              f"ctx+0x70={post['ctx70']} ctx+0x72={post['ctx72']}")
        print(f"ctx+8   (mode=0 heads): "
              f"{[hex(w) for w in post['ctx8']]}")
        print(f"ctx+0x3c (mode=1 heads): "
              f"{[hex(w) for w in post['ctx3c']]}")
    else:
        print("no post-sort sample collected")

    try:
        gdb.send(f"z0,{SORT_ENTRY:x},2")
        gdb.send(f"z0,{SORTS_DONE:x},2")
        gdb.cont()
    except Exception:
        pass
    gdb.close()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="\n") as fh:
        json.dump({"ai": ai, "pre": pre, "post": post}, fh, indent=1)
    print(f"wrote {args.out}")
    return 0 if post else 1


if __name__ == "__main__":
    sys.exit(main())
