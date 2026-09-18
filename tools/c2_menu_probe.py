"""C2 identified-action selector, step 1: find the menu cursor in RAM.

The chooser route (DOWN DOWN A A) commits a real action, but nothing reads
WHAT is highlighted before driving. The command menu always reopens with the
cursor on Move (run 13), so the highlighted index must live somewhere in RAM
and tick 0,1,2 as the cursor walks Move -> Action -> Wait.

Method (differential, two agreeing cycles):
  1. wait for Marche's first menu (`player_menu_settled`: stable low CT).
  2. bulk-sweep EWRAM 0x02000000-0x0202FFFF and IWRAM 0x03000000-0x03007FFF,
     keeping only bytes whose value is a plausible cursor index (0..7).
  3. press DOWN (Move->Action), sweep, diff -> candidate set B1.
  4. press DOWN (Action->Wait), sweep, diff -> intersect -> B2.
  5. press UP twice (back to Move), sweep after each, keep addresses that
     returned to their A-value -> B3 (cycle 1).
  6. repeat the whole down/down/up/up cycle -> candidates agreeing in BOTH
     cycles with the same value trajectory.
  7. then probe the action submenu: from cursor=Action press A (opens the
     submenu), sweep-diff -> submenu state candidates; press DOWN (submenu
     cursor move), diff -> intersect (submenu cursor candidates).
  8. B (cancel) out of the submenu; report everything as JSON + log.

Every sweep is timestamped and screenshot-anchored so later humans can match
candidates to visible UI states. No commit is driven; cleanup kills the owned
emulator (no handoff to preserve).
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import FixtureSession, u8          # noqa: E402
from probe_control_handoff import Probe, PARK_CT_MAX  # noqa: E402

EWRAM_LO, EWRAM_HI = 0x02000000, 0x02030000
IWRAM_LO, IWRAM_HI = 0x03000000, 0x03008000
# mGBA 0.10.5 stub packet buffer caps 'm' replies: 0x200 works, >=0x800 is
# dropped (measured live: size 0x10/0x200 -> data, 0x800/0x1000 -> None).
CHUNK = 0x200

OUT_DIR = os.path.join("outputs", "autobattle", "c2-menu-probe")


def sweep(g, regions=((EWRAM_LO, EWRAM_HI), (IWRAM_LO, IWRAM_HI))):
    """Read every bulk-readable byte once; return {addr: value}."""
    snap = {}
    for lo, hi in regions:
        for base in range(lo, hi, CHUNK):
            data = g.read_mem(base, CHUNK)
            if data:
                snap.update({base + i: v for i, v in enumerate(data)})
    return snap


def plausible_cursor(snap):
    return {a: v for a, v in snap.items() if v <= 7}


def diff(old, new):
    return {a for a in set(old) & set(new) if old[a] != new[a]}


def capture(pid, name):
    out = os.path.join(OUT_DIR, name)
    try:
        subprocess.run(["powershell", "-NoProfile", "-File",
                        "tools/capture_window.ps1", "-ProcId", str(pid),
                        "-Out", out],
                       timeout=25, capture_output=True)
    except Exception as exc:                       # noqa: BLE001
        print(f"  capture {name} failed: {exc}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state",
                    default=os.path.join("outputs", "lua-nav",
                                         "battle-start.ss0"))
    ap.add_argument("--rom", default="baserom.gba")
    ap.add_argument("--settle-seconds", type=float, default=150.0)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    log_lines = []

    def say(msg):
        line = f"[{time.time() - t0:7.1f}s] {msg}"
        print(line, flush=True)
        log_lines.append(line)

    with FixtureSession(args.state, rom=args.rom) as s:
        pid = getattr(s, "pid", None) or getattr(getattr(s, "proc", None),
                                                 "pid", None)
        probe = Probe(s, intervene="none")
        g = s.g

        # NOTE: no key-enable scratch write here — the plain fixture works
        # without one (c2-bisect evidence). The boot state IS Marche's open
        # menu: his roster CT reads a stable 0 from t=0 (the run-17/18
        # re-opened-menu signature, value-agnostic). Settle must therefore
        # be value-agnostic (allow_zero): the old allow_zero=False loop
        # rejected the stable 0 and spun 150 s, while the runtime's frozen
        # check accepted the same state and drove it immediately.

        # Marche's menu must be open and parked before sweeping: stable low
        # CT on the player slot, 0 allowed (boot state parks at 0).
        say(f"waiting up to {args.settle_seconds:.0f}s for the player menu "
            "to open (player_menu_settled, allow_zero)")
        deadline = time.time() + args.settle_seconds
        settled = False
        last_ct_dump = 0.0
        while time.time() < deadline:
            if time.time() - last_ct_dump >= 15.0:
                last_ct_dump = time.time()
                say(f"cts={probe.cts()} player_ct="
                    f"{probe.unit_u16(probe.player_slot(), 0xD0) if probe.player_slot() is not None else None}")
            if probe.player_menu_settled(2, tick_secs=2.0, allow_zero=True):
                settled = True
                break
            time.sleep(1.0)
        if not settled:
            say("menu never settled; aborting probe (no sweep data)")
            probe.disarm()
            raise SystemExit(2)
        say("menu settled (parked CT); starting sweeps")

        # turn the trace breakpoints OFF: sweeps read memory, nothing needs
        # to stop the CPU; press() manages its own arm/disarm anyway.
        probe.disarm()

        trajectory = []          # (phase, candidates-count, capture-name)
        results = {"cycle1": None, "cycle2": None, "submenu": None,
                   "survivors": []}

        def press(mask, tag):
            n = probe.press(mask, pause=1.2, tag=tag)
            say(f"press {tag}: hits={n}")
            time.sleep(2.0)      # let the UI finish redrawing
            return n

        def phase(tag):
            snap = plausible_cursor(sweep(g))
            shot = capture(pid, f"menu-{tag}.png")
            say(f"phase {tag}: {len(snap)} plausible bytes "
                f"(shot {shot})")
            trajectory.append({"phase": tag, "n": len(snap), "shot": shot,
                               "t": round(time.time() - t0, 1)})
            return snap

        # ---- cycle 1 and 2: DOWN DOWN UP UP -----------------------------
        for cyc in ("cycle1", "cycle2"):
            a = phase(f"{cyc}-a")
            press(0x80, f"{cyc} down1")           # Move -> Action
            b = phase(f"{cyc}-b")
            press(0x80, f"{cyc} down2")           # Action -> Wait
            c = phase(f"{cyc}-c")
            press(0x40, f"{cyc} up2")             # Wait -> Action
            d = phase(f"{cyc}-d")
            press(0x40, f"{cyc} up1")             # Action -> Move
            e = phase(f"{cyc}-e")

            # cursor candidates: moved at b and c, back to baseline at e
            cand = diff(a, b) & diff(b, c)
            returned = {x for x in cand if a.get(x) == e.get(x)}
            detail = sorted(
                ({"addr": f"{x:08x}", "a": a.get(x), "b": b.get(x),
                  "c": c.get(x), "d": d.get(x), "e": e.get(x)}
                 for x in returned),
                key=lambda r: r["addr"])
            results[cyc] = detail
            say(f"{cyc}: {len(cand)} moved-and-moved-again, "
                f"{len(returned)} returned to baseline")

        # ---- submenu probe from cursor=Action ---------------------------
        # menu reopened on Move; walk to Action then open the submenu.
        press(0x80, "sub down1")                  # Move -> Action
        a = phase("sub-a")
        press(0x01, "sub open")                   # A: open action submenu
        b = phase("sub-b")
        press(0x80, "sub down")                   # submenu cursor down
        c = phase("sub-c")
        press(0x02, "sub cancel")                 # B: close submenu
        d = phase("sub-d")

        cand = diff(a, b) & diff(b, c)
        restored = {x for x in cand if b.get(x) == d.get(x)}
        results["submenu"] = sorted(
            ({"addr": f"{x:08x}", "closed": a.get(x), "open": b.get(x),
              "down": c.get(x), "restored": d.get(x)}
             for x in restored),
            key=lambda r: r["addr"])
        say(f"submenu: {len(cand)} candidates, {len(restored)} restored")

        # ---- survivors: addresses agreeing across both menu cycles ------
        c1 = {r["addr"]: r for r in results["cycle1"]}
        c2 = {r["addr"]: r for r in results["cycle2"]}
        for addr, r1 in c1.items():
            r2 = c2.get(addr)
            if r2 and (r1["a"], r1["b"], r1["c"]) == (r2["a"], r2["b"],
                                                      r2["c"]):
                results["survivors"].append({"addr": addr,
                                             "trajectory": [r1["a"],
                                                            r1["b"],
                                                            r1["c"],
                                                            r1["d"],
                                                            r1["e"]]})
        say(f"SURVIVORS (both cycles, same trajectory): "
            f"{[s['addr'] for s in results['survivors']]}")

        # value sanity dump for each survivor: exact bytes around it in the
        # final sweep (neighbors often hold the full menu struct)
        if results["survivors"]:
            final = sweep(g)
            for s_row in results["survivors"][:12]:
                addr = int(s_row["addr"], 16)
                lo = addr - 8
                s_row["context"] = final.get(lo) is not None and [
                    final.get(lo + i) for i in range(24)]
                s_row["context_lo"] = f"{lo:08x}"

        probe.disarm()

    out = {
        "run": "c2-menu-probe",
        "t_elapsed_s": round(time.time() - t0, 1),
        "trajectory": trajectory,
        **results,
    }
    with open(os.path.join(OUT_DIR, "probe.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    with open(os.path.join(OUT_DIR, "probe.log"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    print(json.dumps(out.get("survivors"), indent=2))


if __name__ == "__main__":
    main()
