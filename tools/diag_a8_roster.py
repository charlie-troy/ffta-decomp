"""A8 v5 design diagnostic: where does Marche's CT live after the commit?

v4's fixed slot-6 CT trajectory read mostly zeros with spikes, so the
recharge window could not be tracked. Suspect: the roster REORDERS when
the committed unit's turn ends (DE-016: slots shuffle as units act).
This diagnostic dumps every roster slot's identity (name pointer) and
CT every ~2 s for ~24 s after the identified-Wait commit, so the v5
trace can lock onto Marche by NAME POINTER (identity-stable) instead of
slot index.

Evidence: outputs/autobattle/A8-speed/roster-diag.json
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import (  # noqa: E402
    FixtureSession, ROSTER, STRIDE, OFF_CT, u8, u16, u32)
from probe_control_handoff import Probe  # noqa: E402

OUT_DIR = os.path.join("outputs", "autobattle", "A8-speed")
STATE = os.path.join("outputs", "lua-nav", "battle-start.ss0")
N_SLOTS = 8
SAMPLES = 12
GAP_S = 2.0


def roster_dump(g):
    rows = []
    for i in range(N_SLOTS):
        base = ROSTER + STRIDE * i
        nm = u32(g, base)
        rows.append({
            "slot": i,
            "name_ptr": f"{nm:08x}" if nm else None,
            "ct": u16(g, base + OFF_CT),
        })
    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {"state": STATE, "samples": []}
    with FixtureSession(STATE, quiet=True) as s:
        g = s.g
        probe = Probe(s, verbose=False)
        plan = probe.plan_identified_wait()
        if not plan:
            print("FAIL: no plan", flush=True)
            return
        probe.disarm()
        completed, _ = probe.commit_identified_wait(plan)
        out["committed"] = bool(completed)
        print(f"committed={completed}", flush=True)

        g.interrupt()
        g.cont()
        t0 = time.time()
        for k in range(SAMPLES):
            rows = None
            for _ in range(4):
                try:
                    g.interrupt()
                    rows = roster_dump(g)
                    g.cont()
                    break
                except Exception:
                    try:
                        g.cont()
                    except Exception:
                        pass
                    time.sleep(0.5)
            out["samples"].append({
                "t": round(time.time() - t0, 2), "slots": rows})
            if rows:
                line = " ".join(
                    f"{r['slot']}:{(r['name_ptr'] or '----------')[2:]}:"
                    f"{r['ct']}" for r in rows)
                print(f"t={out['samples'][-1]['t']:6.1f} {line}", flush=True)
            time.sleep(GAP_S)
    with open(os.path.join(OUT_DIR, "roster-diag.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("saved roster-diag.json", flush=True)


if __name__ == "__main__":
    main()
