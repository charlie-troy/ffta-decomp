"""Live check of the arena/container split in the snowball battle.

Confirms the static decode of sub_080C1EB4 / sub_080C1B8C:
  - ai+4 = the 0x90-stride entry array base (entry 0 = the actor's own entry);
  - C = [entry0 + 0x80] = the container object with two linked lists at +0x14
    and +0x18 (nodes {data@0, prev@4, next@8}, list head {owner@0, first@4});
  - the mode=0 (help) arena is built over the +0x14 list and the mode=1 (harm)
    arena over the +0x18 list;
  - each entry's unit record (entry+0) carries the side bit at +0x28 bit 15
    (0x080C8240) used by the record gate, plus the Conceal (+0xE9 bit 4) and
    gone (+0xED bit 6) exclusion bits.

Run with mGBA started via tools/run_mgba.sh baserom.gba outputs/mgba-snowball/state-facing.ss0
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

RNG = 0x030034B0
BREAK_AT = 0x080C2940            # sort entry (fill machinery head)
ENTRY_STRIDE = 0x90
POLL_PATCH = 0x0800048A
PATCH_LEN = 4
PATCH_BYTES = "0121c046"         # movs r1, #1 ; nop  (forces A held)
PATCH_ORIG = "811c5940"          # adds r1, r2, #0 ; eors r1, r3 (retail)


def read_chunked(gdb, addr, length, chunk=0x200):
    out = bytearray()
    while len(out) < length:
        part = gdb.read_mem(addr + len(out), min(chunk, length - len(out)))
        if not part:
            return None
        out.extend(part)
    return bytes(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="outputs/mgba-snowball/pool-sides.json")
    p.add_argument("--idle-timeout", type=float, default=100.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port, timeout=20)
    gdb.send("?")
    print(f"seed: {gdb.read_mem(RNG, 4).hex()}")
    print(f"freeze RNG -> {gdb.send(f'M{RNG:x},4:78563412')!r}")
    print(f"sort breakpoint {BREAK_AT:#x} -> {gdb.send(f'Z0,{BREAK_AT:x},2')!r}")

    # Confirm press (advances the facing menu / starts the AI turn).
    gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_BYTES}")
    print(f"A-force verify={gdb.read_mem(POLL_PATCH, PATCH_LEN).hex()}")
    gdb.cont()
    time.sleep(10 / 30)
    stop = gdb.interrupt()
    gdb.send(f"M{POLL_PATCH:x},{PATCH_LEN}:{PATCH_ORIG}")
    print(f"restored retail verify={gdb.read_mem(POLL_PATCH, PATCH_LEN).hex()}")

    result = {"hits": 0, "error": None}
    gdb.sock.settimeout(args.idle_timeout)
    try:
        pending = stop
        while True:
            if pending is None:
                gdb.cont()
                pending = gdb._read_packet()
            if not pending or pending[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop: {pending!r}")
            regs = gdb.read_registers()
            if regs and len(regs) >= 16 and regs[15] == BREAK_AT:
                result = snapshot(gdb, regs)
                result["hits"] = 1
                break
            pending = None
    except (TimeoutError, OSError) as exc:
        result["error"] = f"stopped waiting for sort hit: {exc}"
        print(result["error"])
    finally:
        try:
            gdb.send(f"z0,{BREAK_AT:x},2")
            gdb.cont()
        except Exception:
            pass
        gdb.close()

    with open(args.out, "w", newline="\n") as fh:
        json.dump(result, fh, indent=1)
    print(f"\nwrote {args.out}")
    return 0 if result.get("hits") else 1


def snapshot(gdb, regs):
    """Read the arena bases, the entry table, the container lists, and sides."""
    ai = regs[0]
    E = int.from_bytes(gdb.read_mem(ai + 4, 4), "little")
    print(f"ai={ai:#x} entries base E={E:#x}")

    # Arena record counts live at arena+0x2908 (u16); records start at base.
    counts = {}
    records = {}
    for label, base in (("mode0_help", ai + 0x5C), ("mode1_harm", ai + 0x2968)):
        c = int.from_bytes(gdb.read_mem(base + 0x2908, 2), "little")
        counts[label] = c
        recs = []
        for i in range(min(c, 16)):
            ep = int.from_bytes(gdb.read_mem(base + i * 0x328, 4), "little")
            if ep >= E and (ep - E) % ENTRY_STRIDE == 0:
                recs.append((ep - E) // ENTRY_STRIDE)
            else:
                recs.append(f"0x{ep:x}")
        records[label] = recs
    print("arena counts:", counts)
    print("arena record entry indices:", records)

    # Entries: record ptr + side bits of each entry's unit.
    entries = []
    for k in range(8):
        ep = E + ENTRY_STRIDE * k
        rec = int.from_bytes(gdb.read_mem(ep, 4), "little")
        u = {}
        if rec:
            st28 = int.from_bytes(gdb.read_mem(rec + 0x28, 2), "little")
            e9 = gdb.read_mem(rec + 0xE9, 1)
            ed = gdb.read_mem(rec + 0xED, 1)
            u = {
                "side_bit": bool(st28 & 0x8000),
                "alone_bit12": bool(st28 & 0x1000),
                "conceal_e9_10": bool((e9[0] if e9 else 0) & 0x10),
                "gone_ed_40": bool((ed[0] if ed else 0) & 0x40),
            }
        entries.append({"index": k, "entry_addr": f"0x{ep:x}",
                        "unit_rec": f"0x{rec:x}", **u})
    print("entries:", [(e["index"], e["unit_rec"], e["side_bit"]) for e in entries])

    # Container: C = [E + 0x80].
    C = int.from_bytes(gdb.read_mem(E + 0x80, 4), "little")
    print(f"container C = [E+0x80] = {C:#x}")
    lists = {}
    for off in (0x10, 0x14, 0x18):
        head = int.from_bytes(gdb.read_mem(C + off, 4), "little")
        order = []
        if head:
            node = int.from_bytes(gdb.read_mem(head + 4, 4), "little")
            guard = 0
            while node and guard < 64:
                data = int.from_bytes(gdb.read_mem(node, 4), "little")
                if data >= E and (data - E) % ENTRY_STRIDE == 0 and data < E + ENTRY_STRIDE * 8:
                    order.append((data - E) // ENTRY_STRIDE)
                else:
                    order.append(f"0x{data:x}")
                node = int.from_bytes(gdb.read_mem(node + 8, 4), "little")
                guard += 1
        lists[f"c+0x{off:x}"] = {"head": f"0x{head:x}", "entries": order}
    print("container lists:", {k: v["entries"] for k, v in lists.items()})

    return {"ai": f"0x{ai:x}", "entries_base": f"0x{E:x}", "container": f"0x{C:x}",
            "arena_counts": counts, "arena_records": records,
            "entries": entries, "lists": lists}


if __name__ == "__main__":
    sys.exit(main())
