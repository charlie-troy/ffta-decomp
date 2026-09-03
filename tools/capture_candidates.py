"""In-vivo candidate capture for the snowball battle.

Injection path (no emulator scripting frontend available):
  1. Freeze gRngState (0x030034B0) to the documented seed 0x12345678.
  2. Patch the key-poll at 0x0800048A to force "A held" for ~10 frames,
     then restore the retail bytes (the confirm press).
  3. Collect sub_080C2940 breakpoint hits and snapshot the candidate
     arenas with tools/dump_candidates.snapshot.
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
PATCH_LEN = 4
PATCH_BYTES = "0121c046"   # movs r1, #1 ; nop  (forces A held)
PATCH_ORIG = "811c5940"    # adds r1, r2, #0 ; eors r1, r3 (retail)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="outputs/mgba-snowball/candidates.json")
    p.add_argument("--hits", type=int, default=6,
                   help="stop after this many sort hits")
    p.add_argument("--idle-timeout", type=float, default=90.0,
                   help="seconds to wait between hits before giving up")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")

    print(f"seed before freeze: {gdb.read_mem(RNG, 4).hex()}")
    print(f"freeze RNG -> {gdb.send(f'M{RNG:x},4:78563412')!r}")
    print(f"sort breakpoint {BREAK_AT:#010x} -> "
          f"{gdb.send(f'Z0,{BREAK_AT:x},2')!r}")

    # Confirm press: force A for ~10 frames, then restore.
    reply = gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_BYTES}")
    verify = gdb.read_mem(POLL_PATCH, PATCH_LEN)
    print(f"A-force patch -> {reply!r} verify={verify.hex()}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    reply = gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_ORIG}")
    verify = gdb.read_mem(POLL_PATCH, PATCH_LEN)
    print(f"restore retail -> {reply!r} verify={verify.hex()}")

    hits = []
    pending = stop  # the interrupt may already have delivered a sort stop
    gdb.sock.settimeout(args.idle_timeout)
    try:
        while len(hits) < args.hits:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                raise RuntimeError("register read failed")
            if regs[15] == BREAK_AT:
                hits.append(snapshot(gdb, regs, len(hits) + 1))
                with open(args.out, "w", newline="\n") as fh:
                    json.dump({"mode": "candidates", "address": BREAK_AT,
                               "hits": hits}, fh, indent=1)
            pending = None
    except (TimeoutError, OSError) as exc:
        print(f"stopped after {len(hits)} hits: {exc}")
    finally:
        try:
            gdb.send(f"z0,{BREAK_AT:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    print(f"\nwrote {args.out} ({len(hits)} hit(s))")
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
