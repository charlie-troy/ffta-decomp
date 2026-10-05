"""A8: find the game's own per-frame counter in RAM (2026-09-22).

Every other calibration channel failed on this host: IO writes are
discarded by the stub, the scripting console freezes the core or hangs
the bridge, and stub detach pauses the game. Remaining channel: the
game's own bookkeeping. FFTA surely maintains a frame/vblank counter;
if one is found and verified, emulated time = (count2 - count1) / rate,
readable via pure stub reads with no side effects.

Method: snapshot candidate regions twice, ~20 s apart (stub-attached,
halted reads only). Report every aligned u16/u32 cell whose value
increased by 500..3000 u16 (or 500..3000<<16 u32: too big) — i.e. a
small integer that plausibly ticks at ~60/s over 20 s — and whose
delta is positive and consistent. Regions: IWRAM 0x03000000-0x03007FFF
(work RAM the kernel/IRQ uses) and EWRAM 0x02000000-0x0203FFFF.
"""
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, ROSTER, STRIDE, OFF_CT  # noqa: E402
from probe_control_handoff import Probe  # noqa: E402

OUT_DIR = os.path.join("outputs", "autobattle", "A8-speed")
STATE = os.path.join("outputs", "lua-nav", "battle-start.ss0")

REGIONS = [("iwram", 0x03000000, 0x8000), ("ewram-low", 0x02000000, 0x40000),
           ("ewram-mid", 0x02040000, 0x40000)]


def snap(g, region):
    _, base, size = region
    halt = g.interrupt()
    out = bytearray()
    chunk = 0x8000
    for off in range(0, size, chunk):
        d = g.read_mem(base + off, min(chunk, size - off))
        if d:
            out += d
        else:
            out += b"\x00" * min(chunk, size - off)
    g.cont()
    return bytes(out)


def ct_read(g, addr, tries=4):
    """The v3 pattern: interrupt, read, cont, retry with settle."""
    for _ in range(tries):
        try:
            g.interrupt()
            d = g.read_mem(addr, 2)
            g.cont()
            if d:
                return int.from_bytes(d, "little")
        except Exception:
            try:
                g.cont()
            except Exception:
                pass
        time.sleep(0.4)
    return None


def ct_vector(g):
    """Proven slot CTs (ROSTER + k*STRIDE + OFF_CT); aliveness = change."""
    return [ct_read(g, ROSTER + k * STRIDE + OFF_CT) for k in (1, 2, 3)]


def find_counters(a, b, base, wall):
    hits = []
    n = len(a)
    for fmt, width in (("<u16", 2), ("<u32", 4)):
        step = width
        for off in range(0, n - width + 1, step):
            va = int.from_bytes(a[off:off + width], "little")
            vb = int.from_bytes(b[off:off + width], "little")
            if va == vb or vb <= va:
                continue
            d = vb - va
            # plausibility: small integer ticking at a frame-ish rate; the
            # wall window includes snapshot time, so accept 5..160/s and
            # let the per_s column speak (30/60 fps counters land here
            # for 20-70 s windows).
            if 100 <= d <= 11200 and va < 0x01000000:
                hits.append({"addr": f"{base + off:08x}", "fmt": fmt,
                             "before": va, "after": vb, "delta": d,
                             "per_s": round(d / wall, 2)})
    return hits


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rep = {"schema": "a8-frame-counter-hunt/1", "date": "2026-09-22"}
    with FixtureSession(STATE, quiet=True) as s:
        # Commit one identified Wait first (the v3 pattern): before the
        # commit the scene sits in intro/menu states where nothing charges,
        # which a naive aliveness check misreads as "frozen".
        probe = Probe(s, verbose=False)
        plan = probe.plan_identified_wait()
        completed, _ = probe.commit_identified_wait(plan) if plan else (False, None)
        if not completed:
            rep["verdict"] = "COMMIT-FAILED"
            with open(os.path.join(OUT_DIR, "frame-counter-hunt.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(rep, fh, indent=2)
            print("COUNTER-HUNT COMMIT-FAILED")
            return 2
        ct1 = ct_vector(s.g)
        snaps1 = {}
        for r in REGIONS:
            snaps1[r[0]] = snap(s.g, r)
        t0 = time.time()
        time.sleep(20)
        wall = time.time() - t0
        ct2 = ct_vector(s.g)
        alive = ct1 is not None and ct2 is not None and ct1 != ct2
        rep["window_s"] = round(wall, 2)
        rep["ct1"] = ct1
        rep["ct2"] = ct2
        rep["scene_alive"] = alive
        print(f"window={wall:.1f}s alive={alive} ct1={ct1} ct2={ct2}",
              flush=True)
        if not alive:
            rep["verdict"] = "SCENE-FROZEN"
            with open(os.path.join(OUT_DIR, "frame-counter-hunt.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(rep, fh, indent=2)
            print("COUNTER-HUNT SCENE-FROZEN (rerun needed)")
            return 2
        all_hits = []
        for r in REGIONS:
            s2 = snap(s.g, r)
            hits = find_counters(snaps1[r[0]], s2, r[1], wall)
            rep[f"{r[0]}_hits"] = hits
            all_hits += [(r[0], h) for h in hits]
            print(f"{r[0]}: {len(hits)} candidates", flush=True)
        # stability re-read: any candidate must advance AGAIN at the same
        # per-second rate on a second window, else it is animation noise.
        time.sleep(10)
        verified = []
        for region_name, h in all_hits:
            r = next(x for x in REGIONS if x[0] == region_name)
            s2 = snap(s.g, r)
            off = int(h["addr"], 16) - r[1]
            width = 2 if h["fmt"] == "<u16" else 4
            va = int.from_bytes(s2[off:off + width], "little")
            t1 = time.time()
            time.sleep(10)
            s3 = snap(s.g, r)
            vb = int.from_bytes(s3[off:off + width], "little")
            d2 = vb - va
            w2 = time.time() - t1
            rate2 = round(d2 / w2, 2) if d2 > 0 else None
            ok = d2 > 0 and abs(rate2 - h["per_s"]) / h["per_s"] < 0.25 \
                if rate2 else False
            h2 = dict(h)
            h2["delta2"] = d2
            h2["per_s2"] = rate2
            h2["verified"] = bool(ok)
            if ok:
                verified.append(h2)
            print(f"{h['addr']} {h['fmt']} {h['per_s']}/s -> "
                  f"{rate2}/s verified={ok}", flush=True)
        rep["verified"] = verified
        rep["verdict"] = "FOUND" if verified else "NOT-FOUND"
    with open(os.path.join(OUT_DIR, "frame-counter-hunt.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print(f"COUNTER-HUNT {rep['verdict']} ({len(verified)} verified)")
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
