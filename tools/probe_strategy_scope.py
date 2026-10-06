"""A4 strategy-scope probe: stable party identity across turns and reloads.

Per-character policy needs an identity key that (1) names the same unit at
every turn boundary within one battle, (2) names the same unit after a
reload/fresh boot of the same fixture, and (3) maps cleanly onto the AI
mirror array the sequencer actually references (DE-016: slot indexes do not
even name the same units across the two arrays). This probe measures all
three on the verified `battle-start.ss0` fixture and records every claim
with the observation that supports it.

Method (read-only except the proven Wait-commit key route):
  * boot 1 — settle Marche's menu, snapshot the full identity vector
    (decoded name, type, base/active job, race, level, hp/max, mp, id,
    side bit) for every live roster slot, plus the AI mirror array at
    `0x02002FC4` decoded the same way,
  * drive two player turns with the proven route (DOWN DOWN A A: Wait);
    between and after them, resample both arrays and collect sequencer
    seed contexts (actors attributed by decoded name, never slot index),
  * stop, boot 2 from the same fixture fresh, snapshot boot identity
    again — the two boots must agree on every immutable identity field.
  * report per-slot: immutable fields equal across boot/turns/reload,
    mutable fields (ct/hp/tile) listed separately.

Identity law under test: (type, base_job, race, job, level, name, id) is
stable within a battle and across reloads; hp/mp/ct/tile are state, not
identity; the mirror maps to the roster 1:1 by decoded name (enemies)
with Marche absent by construction.

Evidence: outputs/autobattle/A4-scope/ (untracked; no game bytes).
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import (FixtureSession, OFF_CT, ROSTER, STRIDE,  # noqa: E402
                           decode_ram_name, u8, u16, u32)
from probe_control_handoff import Probe, ROUTE  # noqa: E402

MIRROR = 0x02002FC4          # AI mirror: twelve 0x108-byte unit records
MIRROR_COUNT = 12
MIRROR_ACTIVE = 0x04         # pre-seed active flag (ai-findings.md)

OUT_DIR = os.path.join("outputs", "autobattle", "A4-scope")

# Fields that NAME a unit (must be identical at every observation)
IDENTITY_FIELDS = ("name_text", "type", "base_job", "job", "race",
                   "level", "id", "side_bit")
# Fields that are battle STATE (reported, never identity)
STATE_FIELDS = ("ct", "hp", "max_hp", "mp", "x", "y")


def mirror_records(g, rom):
    """Decode the AI mirror array the way read_roster decodes the roster."""
    out = []
    for k in range(MIRROR_COUNT):
        base = MIRROR + STRIDE * k
        rec = {"index": k, "addr": f"{base:08x}"}
        rec["active"] = u8(g, base + MIRROR_ACTIVE)
        rec["name"] = u32(g, base)
        if rec["name"] is None or rec["name"] == 0:
            out.append(rec)
            continue
        rec["name_text"] = decode_ram_name(g, rec["name"], rom=rom)
        rec["type"] = u8(g, base + 0x04)
        rec["base_job"] = u8(g, base + 0x05)
        rec["race"] = u8(g, base + 0x06)
        rec["job"] = u8(g, base + 0x07)
        rec["level"] = u8(g, base + 0x09)
        rec["hp"] = u16(g, base + 0x18)
        rec["max_hp"] = u16(g, base + 0x1A)
        rec["ct"] = u16(g, base + OFF_CT)
        rec["side_raw"] = u16(g, base + 0x28)
        rec["id"] = u8(g, base + 0x104)
        out.append(rec)
    return out


def roster_identity(probe, session):
    """Identity vector for every live roster slot (guard's own decoder)."""
    roster = session.receipt["roster"]
    rows = []
    g = probe.g
    for s in roster["slots"]:
        if not s.get("live"):
            continue
        base = ROSTER + STRIDE * s["slot"]
        rows.append({
            "slot": s["slot"],
            "name_text": s.get("name_text"),
            "type": s.get("type"),
            "base_job": s.get("base_job"),
            "job": s.get("job"),
            "race": s.get("race"),
            "level": s.get("level"),
            "id": s.get("id"),
            "side_bit": s.get("side_bit"),
            "ct": u16(g, base + OFF_CT),
            "hp": u16(g, base + 0x18),
            "max_hp": u16(g, base + 0x1A),
            "mp": u16(g, base + 0x1C),
            "x": u8(g, base + 0xF6),
            "y": u8(g, base + 0xF7),
        })
    return rows


def seed_actors(probe):
    """Decoded names from sequencer contexts since the last call."""
    names = sorted({u["name"] for s in probe.seeds
                    for u in s.get("ctx_units", []) if u.get("name")})
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state",
                    default=os.path.join("outputs", "lua-nav",
                                         "battle-start.ss0"))
    ap.add_argument("--rom", default="baserom.gba")
    ap.add_argument("--turns", type=int, default=2,
                    help="player turns to drive on boot 1")
    ap.add_argument("--settle-seconds", type=float, default=150.0)
    ap.add_argument("--boot", choices=("1", "2", "both"), default="both",
                    help="which boot to run (each invocation is a fresh "
                         "reload; boot 2 merges into the existing report)")
    args = ap.parse_args()
    boots = (1, 2) if args.boot == "both" else (int(args.boot),)

    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    log_lines = []
    trace = []

    def say(msg):
        line = f"[{time.time() - t0:7.1f}s] {msg}"
        print(line, flush=True)
        log_lines.append(line)

    def phase(tag):
        snap = {"t": round(time.time() - t0, 1), "tag": tag}
        return snap

    out_path = os.path.join(OUT_DIR, "probe.json")
    report = {"schema": "a4-strategy-scope/1",
              "fixture": os.path.basename(args.state),
              "identity_fields": list(IDENTITY_FIELDS),
              "state_fields": list(STATE_FIELDS),
              "boots": []}
    if os.path.exists(out_path):
        try:
            prev = json.load(open(out_path, encoding="utf-8"))
            if prev.get("schema") == report["schema"]:
                # keep earlier boots: boot 2's invocation merges into them
                report["boots"] = [b for b in prev.get("boots", [])
                                   if b.get("boot") not in boots]
        except Exception:
            pass

    def run_boot(boot_no, turns):
        rec = {"boot": boot_no, "phases": [], "seeds_actors": [],
               "turns_driven": 0}
        with FixtureSession(args.state, rom=args.rom) as session:
            pid = getattr(session, "pid", None)
            probe = Probe(session, verbose=False)
            rom = session.read_rom_bytes()

            say(f"boot {boot_no}: pid={pid}, waiting for Marche's menu")
            if not probe.player_menu_settled(2, tick_secs=3.0,
                                             allow_zero=True):
                say(f"boot {boot_no}: menu never settled; aborting boot")
                rec["error"] = "menu-never-settled"
                return rec
            probe.disarm()          # sweeps read memory; no breakpoints yet

            rec["phases"].append({**phase(f"boot{boot_no}-menu1"),
                                  "roster": roster_identity(probe, session),
                                  "mirror": mirror_records(probe.g, rom)})
            say(f"boot {boot_no}: menu-1 identity captured "
                f"({len(rec['phases'][-1]['roster'])} live slots)")

            for turn in range(1, turns + 1):
                # drive the proven Wait commit through drive() (per-press
                # zero-hit redelivery + the stop law); its finally-blocks
                # re-arm the trace breakpoints, so seeds are collected here
                route_ok = probe.drive(f"t{turn}")
                say(f"boot {boot_no} turn {turn}: route driven "
                    f"(ok={route_ok}); waiting for the engine phase")
                # sample the enemy phase: pump ~45 s collecting seeds
                end = time.time() + 45.0
                while time.time() < end:
                    probe.pump(3.0, f"t{turn}-enemy", sample_every=60.0)
                actors = seed_actors(probe)
                rec["seeds_actors"].append({"turn": turn, "actors": actors})
                rec["seeds_total"] = len(probe.seeds)
                rec["turns_driven"] = turn
                rec["phases"].append({**phase(f"boot{boot_no}-post-t{turn}"),
                                      "roster": roster_identity(probe,
                                                                session),
                                      "mirror": mirror_records(probe.g,
                                                               rom)})
                say(f"boot {boot_no} turn {turn}: post-commit identity "
                    f"captured; seed actors={actors}")
                # wait for the next player menu (bounded; pump() keeps the
                # trace breakpoints collecting — re-armed by press()'s
                # finally, not cleared). Marche recharges from 0 at
                # ~12.9 CT/s, so the next menu needs ~80-120 s after a
                # commit: retry the 12 s settle window until the budget
                # is spent.
                if turn < turns:
                    settled = False
                    menu_end = time.time() + 150.0
                    while time.time() < menu_end and not settled:
                        settled = probe.player_menu_settled(
                            2, tick_secs=3.0, allow_zero=True)
                    if not settled:
                        say(f"boot {boot_no}: menu {turn + 1} never settled")
                        rec["error"] = f"menu-{turn + 1}-never-settled"
                        return rec
                rec["turns_driven"] = turn
            rec["pid"] = pid
        return rec

    for boot_no in boots:
        rec = run_boot(boot_no, args.turns)
        report["boots"].append(rec)
        trace.append(rec)
        say(f"boot {boot_no} complete: turns={rec.get('turns_driven')}, "
            f"phases={len(rec.get('phases', []))}")

    # -- analysis ----------------------------------------------------------
    def immutable(r):
        return {f: r.get(f) for f in IDENTITY_FIELDS}

    analysis = {"per_slot": [], "mirror_map": [], "verdicts": {}}
    b1 = report["boots"][0] if report["boots"] else None
    b2 = report["boots"][1] if len(report["boots"]) > 1 else None
    if b1 and b1.get("phases"):
        slots = {r["slot"] for r in b1["phases"][0]["roster"]}
        for slot in sorted(slots):
            obs = [immutable(r) for p in b1["phases"]
                   for r in p["roster"] if r["slot"] == slot]
            same_within = all(o == obs[0] for o in obs)
            entry = {"slot": slot, "identity": obs[0],
                     "n_observations": len(obs),
                     "stable_within_battle": same_within}
            # reload comparison: boot2 menu1 vs boot1 menu1
            if b2 and b2.get("phases"):
                obs2 = [immutable(r) for p in b2["phases"][:1]
                        for r in p["roster"] if r["slot"] == slot]
                entry["stable_across_reload"] = bool(
                    obs2 and obs2[0] == obs[0])
            analysis["per_slot"].append(entry)
        # mirror map: match boot1-menu1 mirror actives to roster by name
        mirror = b1["phases"][0]["mirror"]
        roster = {r["name_text"]: r for r in b1["phases"][0]["roster"]}
        mirror_names = {m.get("name_text") for m in mirror
                        if m.get("active") and m.get("name_text")}
        for m in mirror:
            if m.get("active") and m.get("name_text"):
                roster_slot = None
                for r in b1["phases"][0]["roster"]:
                    if r["name_text"] == m["name_text"]:
                        roster_slot = r["slot"]
                        break
                analysis["mirror_map"].append({
                    "mirror_index": m["index"],
                    "name": m["name_text"],
                    "mirror_job": m.get("job"),
                    "mirror_id": m.get("id"),
                    "roster_slot": roster_slot,
                    "roster_id": roster.get(m["name_text"], {}).get("id"),
                    "jobs_agree": (m.get("job") is not None
                                   and m.get("job")
                                   == roster.get(m["name_text"], {})
                                   .get("job")),
                })
        # roster units with NO mirror record: player-side units are absent
        # by construction (the mirror is the AI-side copy). A1's fixture had
        # one player (Marche); the A4 multi-ally fixture has two — the law is
        # "every player-side unit is absent", not a hardcoded name list.
        missing = [r["name_text"] for r in b1["phases"][0]["roster"]
                   if r["name_text"] not in mirror_names]
        player_side = [r["name_text"]
                       for r in b1["phases"][0]["roster"]
                       if not r.get("side_bit") and r.get("type") != 20]
        analysis["verdicts"]["mirror_absent"] = missing
        analysis["verdicts"]["mirror_absent_expected_names"] = player_side
        analysis["verdicts"]["mirror_absent_expected"] = (
            set(missing) == set(player_side))
        analysis["verdicts"]["identity_stable_within_battle"] = all(
            e["stable_within_battle"] for e in analysis["per_slot"]) \
            if analysis["per_slot"] else False
        analysis["verdicts"]["identity_stable_across_reload"] = (
            all(e.get("stable_across_reload") for e in analysis["per_slot"])
            if analysis["per_slot"] and b2 else None)
        n_active = sum(1 for m in analysis["mirror_map"]
                       if m.get("roster_slot") is not None) \
            if analysis["mirror_map"] else 0
        analysis["verdicts"]["mirror_maps_1to1_by_name"] = (
            all(m["jobs_agree"] and m["mirror_id"] == m["roster_id"]
                for m in analysis["mirror_map"])
            and len(analysis["mirror_map"]) == n_active
            and len(analysis["mirror_map"]) >= 6)
        report["analysis"] = analysis

    report["t_elapsed_s"] = round(time.time() - t0, 1)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    with open(os.path.join(OUT_DIR, "probe.log"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")

    # Marche's own mirror presence: he should be ABSENT by construction,
    # but the probe must VERIFY that rather than assume it — a unit the AI
    # mirror does name changes the mirror-map law.
    if b1 and b1.get("phases"):
        mirror_names = {m.get("name_text") for m in b1["phases"][0]["mirror"]
                        if m.get("active") and m.get("name_text")}
        for r in b1["phases"][0]["roster"]:
            if r["name_text"] == "Marche":
                print(f"Marche in mirror: {r['name_text'] in mirror_names}")

    v = report.get("analysis", {}).get("verdicts", {})
    print(json.dumps(v, indent=2), flush=True)
    ok = (v.get("identity_stable_within_battle") is True
          and v.get("mirror_absent_expected") is True
          and v.get("mirror_maps_1to1_by_name") is True)
    print(f"A4-SCOPE {'PASS' if ok else 'FAIL'} "
          f"({report['t_elapsed_s']}s)", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
