"""A2 probe: compare a player turn with an enemy turn at the battle sequencer.

Connects to the mGBA GDB stub, interrupts periodically, and dumps the battle
context (0x020101F8): the sequencer's active actor, its unit record, allegiance
(+0x28 bit 15), control-related status bits (+0xe8..+0xef), live tile, and a
scan of the ctx control window (ctx+0x54A0..0x54FF). Samples until the actor
changes, so a player turn and the following enemy turn land in one capture.

Preconditions: mGBA running with the A1 battle-start fixture (or any live
battle turn boundary), GDB stub reachable on 127.0.0.1:2345, no other client.

Usage:
    python tools/probe_player_ai_control.py [--out FILE] [--max-samples N]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

CTX = 0x020101F8
ENTRIES = CTX + 4
PHASE = CTX + 0x54F4
BRANCH = CTX + 0x54AF
CTRL_WINDOW_LO = CTX + 0x54A0
CTRL_WINDOW_HI = CTX + 0x5500

STATUS_BYTES = list(range(0xE8, 0xF0))


def u32(b):
    return int.from_bytes(b, "little")


def u16(b):
    return int.from_bytes(b, "little")


def sample(gdb):
    """One consistent sample taken while the CPU is stopped."""
    entries = u32(gdb.read_mem(ENTRIES, 4))
    unit = 0
    if entries:
        unit = u32(gdb.read_mem(entries, 4))
    s = {
        "phase": u16(gdb.read_mem(PHASE, 2)),
        "branch": gdb.read_mem(BRANCH, 1)[0],
        "entries": entries,
        "unit": unit,
    }
    if unit:
        flags16 = u16(gdb.read_mem(unit + 0x28, 2))
        s["side_ai"] = bool(flags16 & 0x8000)
        s["status"] = {f"0x{off:02x}": gdb.read_mem(unit + off, 1)[0]
                       for off in STATUS_BYTES}
        s["controlled"] = bool(s["status"]["0xed"] & 0x8)
        s["confuse"] = bool(s["status"]["0xeb"] & 0x10)
        s["charm"] = bool(s["status"]["0xeb"] & 0x20)
        s["tile"] = list(gdb.read_mem(unit + 0xF6, 2))
        s["ctx_saved_tile"] = list(gdb.read_mem(CTX + 0x54CA, 2))
    s["ctrl_window"] = gdb.read_mem(CTRL_WINDOW_LO,
                                    CTRL_WINDOW_HI - CTRL_WINDOW_LO).hex()
    return s


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    p.add_argument("--max-samples", type=int, default=120)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--out", default="outputs/lua-nav/player-ai-probe.json")
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    samples = []
    actor_seen = None
    try:
        for i in range(args.max_samples):
            stop = gdb.interrupt()
            if stop is None:
                print(f"[{i:3d}] interrupt failed")
                break
            try:
                s = sample(gdb)
            finally:
                gdb.cont()
            s["i"] = i
            s["t"] = round(time.time(), 3)
            samples.append(s)
            actor = s["unit"]
            tag = ""
            if actor_seen is None:
                actor_seen = actor
                tag = " (first actor)"
            elif actor != actor_seen:
                tag = "  <== ACTOR CHANGED"
                actor_seen = actor
            print(f"[{i:3d}] unit={actor:#09x} side_ai={s.get('side_ai')} "
                  f"ctrl={s.get('controlled')} conf={s.get('confuse')} "
                  f"charm={s.get('charm')} phase={s['phase']} "
                  f"branch={s['branch']:#04x}{tag}", flush=True)
            if tag.startswith("  <==") and len(samples) > 4:
                # keep sampling a few more of the new actor, then stop
                extra = 0
                for j in range(i + 1, min(i + 4, args.max_samples)):
                    stop = gdb.interrupt()
                    if stop is None:
                        break
                    try:
                        s2 = sample(gdb)
                    finally:
                        gdb.cont()
                    s2["i"] = j
                    s2["t"] = round(time.time(), 3)
                    samples.append(s2)
                    print(f"[{j:3d}] unit={s2['unit']:#09x} "
                          f"side_ai={s2.get('side_ai')} phase={s2['phase']}")
                break
            time.sleep(args.interval)
    finally:
        try:
            gdb.cont()
        except Exception:
            pass
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", newline="\n") as fh:
            json.dump(samples, fh, indent=1)
        gdb.close()
        print(f"wrote {len(samples)} samples -> {args.out}")

    # Auto-diff: last sample of the first actor vs first sample of the second.
    if len(samples) > 4:
        a = samples[0]
        b = next(s for s in samples if s["unit"] != samples[0]["unit"])
        print("\n=== diff first-actor vs second-actor ===")
        keys = ("side_ai", "controlled", "confuse", "charm",
                "phase", "branch", "tile", "ctx_saved_tile")
        for k in keys:
            if a.get(k) != b.get(k):
                print(f"  {k}: {a.get(k)} -> {b.get(k)}")
        wa, wb = a.get("ctrl_window", ""), b.get("ctrl_window", "")
        if wa != wb:
            diffs = [(j, wa[j*2:j*2+2], wb[j*2:j*2+2])
                     for j in range(min(len(wa), len(wb)) // 2)
                     if wa[j*2:j*2+2] != wb[j*2:j*2+2]]
            print(f"  ctrl_window byte diffs: {len(diffs)} "
                  f"(ctx offsets "
                  f"{[hex(0x54A0 + d[0]) for d in diffs[:16]]}...)")
    return 0 if samples else 1


if __name__ == "__main__":
    sys.exit(main())
