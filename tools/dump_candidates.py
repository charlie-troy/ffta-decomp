"""Dump the live AI target-candidate arenas at sub_080C2940's entry.

`docs/ai-findings.md` decodes the target sort from static analysis plus
synthetic-unit execution. This tool adds the missing in-vivo evidence: run the
frozen-RNG snowball battle under mGBA's GDB stub, break at the sort's entry,
and snapshot every 0x328-stride record with its 20-byte target candidates —
ability id, target id, validity, the s16 impact score that is the sort's
primary key, and the priority byte that is its secondary key.

Breakpoint hits record the entry registers, so each dump names its regime
(`r2`: 1 = score-path comparator, 0 = list-scan) and arena source (`r0` is the
arg struct; regime 1 reads its list at +0x2980, regime 0 at +0x5c).

Usage (with mGBA started via tools/run_mgba.sh):
    python tools/dump_candidates.py outputs/mgba-snowball/candidates.json \
        [--host H] [--port P] [--hits N] [--timeout S]
"""
import argparse
import json
import socket
import sys

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_mgba import Gdb  # noqa: E402

BREAK_AT = 0x080C2940
RNG_ADDR = 0x030034B0
STRIDE = 0x328
MAX_RECORDS = 20
CAND_STRIDE = 0x14
MAX_CANDIDATES = 0x0A


def s16(value):
    value &= 0xFFFF
    return value - 0x10000 if value >= 0x8000 else value


def read_chunked(gdb, addr, length, chunk=0x200):
    # The mGBA stub rejects 'm' packets much above 0x200 bytes, so read in
    # small chunks; each failure is silent (None) and would otherwise look
    # like an empty arena.
    out = bytearray()
    while len(out) < length:
        part = gdb.read_mem(addr + len(out), min(chunk, length - len(out)))
        if not part:
            return None
        out.extend(part)
    return bytes(out)


def decode_record(rec):
    """Decode one 0x328-stride record: header + target candidates."""
    count = int.from_bytes(rec[0x324:0x326], "little")
    entry = {
        "ability_id": int.from_bytes(rec[0x00:0x02], "little"),
        "ability_arg": int.from_bytes(rec[0x02:0x04], "little"),
        "count": count,
        "candidates": [],
    }
    for k in range(min(count, MAX_CANDIDATES)):
        c = rec[4 + k * CAND_STRIDE:4 + (k + 1) * CAND_STRIDE]
        entry["candidates"].append({
            "index": k,
            "target_id": int.from_bytes(c[0x00:0x02], "little"),
            "rules": [int.from_bytes(c[i:i + 2], "little") for i in (4, 6, 8)],
            "valid": c[0x0a],
            "effect_flags": c[0x0b],
            "score": s16(int.from_bytes(c[0x0c:0x0e], "little")),
            "rule_id_copy": int.from_bytes(c[0x0e:0x10], "little"),
            "priority": c[0x10],
            "flags": c[0x11],
        })
    return entry


def dump_arena(gdb, base, label, hit):
    """Walk up to MAX_RECORDS 0x328 records at base, decoding non-empty ones."""
    blob = read_chunked(gdb, base, STRIDE * MAX_RECORDS)
    if blob is None:
        return {"label": label, "base": f"0x{base:08x}", "error": "read failed",
                "records": []}
    records = []
    counts = []
    for i in range(MAX_RECORDS):
        rec = blob[i * STRIDE:(i + 1) * STRIDE]
        decoded = decode_record(rec)
        counts.append(decoded["count"])
        # A record is live when its candidate count is in the plausible range.
        if 0 < decoded["count"] <= MAX_CANDIDATES:
            decoded["index"] = i
            decoded["record_addr"] = f"0x{base + i * STRIDE:08x}"
            records.append(decoded)
    if not records:
        print(f"  {label}: full read ok but no live records; "
              f"counts[0:6]={counts[:6]}")
    return {"label": label, "base": f"0x{base:08x}", "records": records}


def probe_counts(gdb, base, strides=20):
    """Read the running-count halfword of the first `strides` 0x328 records."""
    blob = read_chunked(gdb, base + 0x324, 2 * strides)
    if blob is None:
        return None
    return [int.from_bytes(blob[i:i + 2], "little")
            for i in range(0, len(blob), 2)]


def snapshot(gdb, regs, hit_index):
    r0, r1, r2, r3 = regs[0], regs[1], regs[2], regs[3]
    rng = gdb.read_mem(RNG_ADDR, 4)
    hit = {
        "index": hit_index,
        "pc": regs[15],
        "r0": f"0x{r0:08x}",
        "r1": f"0x{r1:08x}",
        "r2": r2,
        "r3": f"0x{r3:08x}",
        "rng_seed": f"0x{int.from_bytes(rng, 'little'):08x}" if rng else None,
        "regime": "score-path (mode=1)" if r2 else "list-scan (mode=0)",
    }
    print(f"hit {hit_index}: r0={hit['r0']} r1={hit['r1']} r2={r2} "
          f"r3={hit['r3']} rng={hit['rng_seed']} [{hit['regime']}]")
    arenas = []
    for base, label in ((r0 + 0x2968, "arg0+0x2968 (mode=1 input list)"),
                        (r0 + 0x5C, "arg0+0x5c (mode=0 input list)"),
                        (r3, "r3 (output buffer)")):
        counts = probe_counts(gdb, base)
        if counts is None:
            print(f"  {label} @ {base:#010x}: read failed")
            continue
        print(f"  {label} @ {base:#010x}: counts={counts}")
        arena = dump_arena(gdb, base, label, hit)
        if arena and arena["records"]:
            arenas.append(arena)
            live = ", ".join(
                f"rec{r['index']}#{r['ability_id']:03x}x{r['count']}"
                for r in arena["records"])
            print(f"  {label}: {len(arena['records'])} live record(s): {live}")
    hit["arenas"] = arenas
    return hit


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2345)
    p.add_argument("--hits", type=int, default=8)
    p.add_argument("--timeout", type=float, default=300.0)
    args = p.parse_args(argv)

    gdb = Gdb(args.host, args.port)
    print(f"connected to mGBA gdb stub at {args.host}:{args.port}")
    initial = gdb.send("?")
    if not initial or initial[:1] not in ("S", "T"):
        gdb.close()
        raise RuntimeError(f"unexpected initial GDB status: {initial!r}")

    reply = gdb.send(f"Z0,{BREAK_AT:x},2")
    if reply != "OK":
        gdb.close()
        raise RuntimeError(f"mGBA rejected breakpoint at {BREAK_AT:#010x}: "
                           f"{reply!r}")
    print(f"breakpoint armed at {BREAK_AT:#010x} (sub_080C2940 entry), "
          f"waiting for up to {args.hits} hits")

    hits = []
    gdb.sock.settimeout(args.timeout)
    try:
        while len(hits) < args.hits:
            gdb.cont()
            stop = gdb._read_packet()
            if not stop or stop[:1] not in ("S", "T"):
                raise RuntimeError(f"unexpected stop reply: {stop!r}")
            regs = gdb.read_registers()
            if not regs or len(regs) < 16:
                raise RuntimeError("could not read ARM registers at breakpoint")
            hits.append(snapshot(gdb, regs, len(hits) + 1))
            with open(args.out, "w", newline="\n") as fh:
                json.dump({"mode": "candidates", "address": BREAK_AT,
                           "hits": hits}, fh, indent=1)
    except (EOFError, socket.timeout, ConnectionError, OSError) as exc:
        print(f"stopped after {len(hits)} hits: {exc}")
    finally:
        try:
            gdb.send(f"z0,{BREAK_AT:x},2")
            gdb.cont()
        except (EOFError, socket.timeout, OSError):
            pass
        gdb.close()

    with open(args.out, "w", newline="\n") as fh:
        json.dump({"mode": "candidates", "address": BREAK_AT, "hits": hits},
                  fh, indent=1)
    print(f"\nwrote {args.out} ({len(hits)} hit(s))")
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
