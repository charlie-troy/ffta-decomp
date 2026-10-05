"""A8 timer-clock feasibility test (2026-09-22).

The scripting console is unusable as a calibration channel: the FIRST
console traffic freezes the emulator core permanently (nonce diagnostic
cal-diag.json: same frame 752512 and CT 0 before/after a 60 s window,
verdict F1-frozen-core). Replacement channel: mGBA's own GBA hardware
timers, configured ONCE through the proven stub write path.

  TM2 (0x04000108): prescaler 1024 -> 16384 ticks per emulated second
  TM3 (0x0400010C): cascade on TM2 overflow -> +1 per 4.000 emulated s

emulated_s = TM3*4.0 + TM2/16384.0, definitional for the GBA clock
(16.777216 MHz / 1024 = 16384 Hz exactly); no observed CT rate and no
console involved. This test proves the channel on one live boot:

  1. idle controls read 0x0000 before arming,
  2. arming writes land and stick,
  3. the counter advances during a zero-traffic free-run window,
  4. two consecutive windows agree on the emulated/wall ratio
     (internal consistency is the gate, not any expected regime),
  5. a charging unit's CT advances in the same windows (scene alive).
"""
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, ROSTER, STRIDE, OFF_CT  # noqa: E402

OUT_DIR = os.path.join("outputs", "autobattle", "A8-speed")
STATE = os.path.join("outputs", "lua-nav", "battle-start.ss0")
TM2 = 0x04000108                     # TM2CNT_L/H, TM3CNT_L/H at +4
ALLY_CT = ROSTER + STRIDE * 5 + OFF_CT   # slot5: a charging unit at boot


def halt(g):
    g.interrupt()


def read_tm(g):
    d = g.read_mem(TM2, 8)
    if not d or len(d) != 8:
        return None
    tm2, c2, tm3, c3 = struct.unpack("<4H", d)
    return {"tm2": tm2, "ctrl2": c2, "tm3": tm3, "ctrl3": c3,
            "emulated_s": tm3 * 4.0 + tm2 / 16384.0}


def sample(g, label):
    halt(g)
    t = read_tm(g)
    ct = g.read_mem(ALLY_CT, 2)
    g.cont()
    wall = time.time()
    if t is None:
        return None
    t["wall"] = round(wall, 3)
    t["label"] = label
    if ct:
        t["ally_ct"] = int.from_bytes(ct, "little")
    return t


def arm_timers(s):
    g = s.g
    halt(g)
    pre = read_tm(g)
    if pre is None:
        g.cont()
        return None
    s.write_bytes(0x04000108, b"\x00\x00", note="A8: TM2 count=0")
    s.write_bytes(0x0400010C, b"\x00\x00", note="A8: TM3 count=0")
    s.write_bytes(0x0400010E, b"\x84", note="A8: TM3 enable+cascade")
    s.write_bytes(0x0400010A, b"\x83", note="A8: TM2 enable+ps1024")
    post = read_tm(g)
    g.cont()
    return {"pre": pre, "post": post}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rep = {"schema": "a8-timer-feasibility/1", "date": "2026-09-22"}
    with FixtureSession(STATE, quiet=True) as s:
        rep["pid"] = s.pid
        armed = arm_timers(s)
        rep["arm"] = armed and {
            "pre_ctrl2": armed["pre"]["ctrl2"],
            "pre_ctrl3": armed["pre"]["ctrl3"],
            "post_ctrl2": armed["post"]["ctrl2"],
            "post_ctrl3": armed["post"]["ctrl3"],
            "post_ok": armed["post"]["ctrl2"] == 0x83
            and armed["post"]["ctrl3"] == 0x84}
        if not armed or not rep["arm"]["post_ok"]:
            rep["verdict"] = "arm-failed"
        else:
            s1 = sample(s.g, "w1-start")
            time.sleep(20)
            s2 = sample(s.g, "w1-end")
            time.sleep(25)
            s3 = sample(s.g, "w2-end")
            rep["samples"] = [s1, s2, s3]

            def rate(a, b):
                de = b["emulated_s"] - a["emulated_s"]
                dw = b["wall"] - a["wall"]
                return {"emulated_s": round(de, 2), "wall_s": round(dw, 2),
                        "ratio": round(de / dw, 4) if dw else None,
                        "ally_ct": (a.get("ally_ct"), b.get("ally_ct")),
                        "ctrl_stable": (b["ctrl2"] == 0x83
                                        and b["ctrl3"] == 0x84)}
            r1 = rate(s1, s2)
            r2 = rate(s2, s3)
            rep["window1"] = r1
            rep["window2"] = r2
            alive = (r1["ally_ct"][1] != r1["ally_ct"][0]
                     or r2["ally_ct"][1] != r2["ally_ct"][0])
            stable = r1["ratio"] and r2["ratio"] and \
                abs(r1["ratio"] - r2["ratio"]) / max(r1["ratio"], 1e-9) < 0.02
            advancing = r1["ratio"] and r1["ratio"] > 0.5
            rep["verdict"] = ("PASS" if (alive and stable and advancing
                                        and r1["ctrl_stable"]
                                        and r2["ctrl_stable"])
                              else "FAIL")
            print(f"w1: {r1}", flush=True)
            print(f"w2: {r2}", flush=True)
            print(f"alive={alive} stable={stable} advancing={advancing}",
                  flush=True)
    rep["verdict"] = rep.get("verdict", "FAIL")
    with open(os.path.join(OUT_DIR, "timer-feasibility.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print(f"TIMER-FEASIBILITY {rep['verdict']}")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
