"""A8 calibration diagnostic: why does the second atomic sample go stale?

Three suspects for "S2 frame == S1 frame" after a 180 s free-run window:

  F1  frozen core        -> the running CT vector does not change between
                            two direct stub reads separated by real sleep.
  F2  log-widget cap     -> two fresh nonce samples land, but the echoed
                            widget value only ever contains the oldest A8S
                            line (the newest never appears).
  F3  console paused     -> both fresh nonces appear with FRESH frames, and
                            frames advance between them: the console was
                            wedged earlier and recovered.

Sequence per boot: arm console -> nonce A -> free-run 60 s -> nonce B ->
nonce C immediately -> two running-CT reads with sleep between (F1 check) ->
last 1200 chars of the echoed log for the F2 inspection.
"""
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, ROSTER, STRIDE, OFF_CT  # noqa: E402
from probe_control_handoff import Probe  # noqa: E402

OUT_DIR = os.path.join("outputs", "autobattle", "A8-speed")
STATE = os.path.join("outputs", "lua-nav", "battle-start.ss0")
CT_BASE = ROSTER + STRIDE * 6 + OFF_CT
CT_FULL = 998
TOOLS = os.path.dirname(os.path.abspath(__file__))
LUA_NONCE = os.path.join(TOOLS, "lua_a8_nonce.lua").replace("\\", "/")


def lua(pid, code, timeout=120):
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", os.path.join(TOOLS, "uia_lua2.ps1"),
         "-Cmd", code, "-ProcId", str(pid)],
        capture_output=True, text=True, timeout=timeout)


def console_open(pid):
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", os.path.join(TOOLS, "uia_invoke_item.ps1"),
         "-ProcId", str(pid), "-MenuName", "Tools",
         "-ItemName", "Scripting...", "-ItemIndex", "1"],
        capture_output=True, text=True, timeout=120)
    return (r.stdout or "").strip()


def nonce_sample(pid, n):
    """One nonce-tagged atomic sample; returns (line, log_tail)."""
    r = lua(pid, f'A8N={n} dofile("{LUA_NONCE}")')
    out = r.stdout or ""
    found = None
    for raw in out.splitlines():
        line = raw[5:] if raw.startswith("LOG: ") else raw
        for chunk in line.split("A8S "):
            if chunk == "":
                continue
            p = chunk.split()
            if len(p) >= 4:
                try:
                    found = {"nonce": int(p[0]), "frame": int(p[1]),
                             "ct": int(p[2]), "wall": int(p[3])}
                except ValueError:
                    pass
    tail = out[-1200:]
    return found, tail


def ct_vector(g):
    try:
        g.interrupt()
        d = g.read_mem(CT_BASE, 2)
        g.cont()
        return int.from_bytes(d, "little") if d else None
    except Exception:
        try:
            g.cont()
        except Exception:
            pass
        return None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    report = {"schema": "a8-cal-diag/1", "date": "2026-09-22",
              "steps": []}
    with FixtureSession(STATE, quiet=True) as s:
        report["pid"] = s.pid
        inv = console_open(s.pid)
        report["console_open"] = inv
        time.sleep(2.0)

        a, tail_a = nonce_sample(s.pid, 101)
        report["steps"].append({"step": "A", "sample": a})
        print(f"A: {a}", flush=True)

        time.sleep(60)

        b, tail_b = nonce_sample(s.pid, 102)
        report["steps"].append({"step": "B", "sample": b})
        print(f"B: {b}", flush=True)

        c, tail_c = nonce_sample(s.pid, 103)
        report["steps"].append({"step": "C", "sample": c})
        print(f"C: {c}", flush=True)

        ct1 = ct_vector(s.g)
        time.sleep(10)
        ct2 = ct_vector(s.g)
        f1 = {}
        try:
            s.g.interrupt()
            f1["frame_probe_pc"] = s.g.read_mem(0x08000494, 4) is not None
            s.g.cont()
        except Exception:
            try:
                s.g.cont()
            except Exception:
                pass
        report["steps"].append({"step": "F1", "ct1": ct1, "ct2": ct2,
                                "core_advancing": (ct1 is not None
                                                   and ct2 is not None
                                                   and ct2 != ct1)})
        print(f"F1: ct {ct1} -> {ct2}", flush=True)

        report["log_tail_b"] = tail_b
        report["log_tail_c"] = tail_c

        verdict = "F3-console-paused"
        if ct1 is not None and ct2 == ct1:
            verdict = "F1-frozen-core"
        elif a and b and c and b["nonce"] == 102 and c["nonce"] == 103:
            if b["frame"] > a["frame"] and c["frame"] > b["frame"]:
                verdict = "F3-console-paused-recovered"
            else:
                verdict = "F1-frozen-core"
        elif b is None or c is None:
            verdict = "F2-or-noecho"
        report["verdict"] = verdict
        print(f"VERDICT: {verdict}", flush=True)

    with open(os.path.join(OUT_DIR, "cal-diag.json"), "w",
              encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
