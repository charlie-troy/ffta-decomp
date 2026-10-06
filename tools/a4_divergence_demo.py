"""A4 same-job cross-side divergence demo on the multi-ally fixture.

Roadmap item (A4): "demonstrate different behavior for two same-job allies
while an enemy of that job remains unaffected."

Fixture: `outputs/lua-nav/a4-multi-ally-battle-start.ss0` (built by
tools/a4_fixture_build.py) — two player units with job 5 (Marche,
Montblanc) plus enemy Velasquez with job 5 among five enemies.

Method (Option B, player-menu boundary; no memory writes at all):
  1. boot + guard roster; assert the fixture shape (2 players job J,
     >=1 enemy job J),
  2. owner-aware menu wait: the engine identifies its own menu owner
     through the target cursor — at a freshly opened menu TARGET_X/Y
     reads the OWNER's own tile (C2 law), so the owner is the live
     player slot standing on the cursor tile, held across two ticks.
     CT cannot attribute on this fixture: run 2 (2026-10-05) showed the
     owner parking ABOVE PARK_CT_MAX (306/353) while the other ally
     sat stable at 0, so flash+park picked the frozen ally and swapped
     BOTH attributions — the commits themselves were engine-correct
     (the real owner's tile changed both times, which is how the swap
     was caught), only the labels were wrong,
  3. first distinct ally -> identified-MOVE with effect snapshots; the
     pre-open move-target cursor on this fixture holds walk-in residue
     (11,5 — not any live unit's tile), so the plan's dest is forced
     back to the step-search path: the destination is read from RAM only
     after the engine itself opens target mode (C2 law),
  4. second distinct ally -> identified-WAIT with effect snapshots,
  5. pump enemy phases (retail AI; sequencer seeds attribute actors by
     decoded name) until the same-job enemy (Velasquez) is attributed a
     retail turn or the budget expires,
  6. verdicts: fixture shape, two distinct same-job allies, move-vs-wait
     divergence with engine-observed tile change/no-change, writes audit
     (no memory writes at all), retail enemy turn.

Evidence: outputs/autobattle/A4-demo/demo.json (committed via force-add;
no game bytes).
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixture_guard import (  # noqa: E402
    FixtureSession, OFF_CT, ROSTER, STRIDE, u8, u16)
from probe_control_handoff import PARK_CT_MAX, Probe  # noqa: E402
from probe_a8_speed import drain_paired  # noqa: E402

STATE = os.path.join("outputs", "lua-nav", "a4-multi-ally-battle-start.ss0")
OUT_DIR = os.path.join("outputs", "autobattle", "A4-demo")
KEY_ENABLE = 0x03000005
SAME_JOB = 5
SAME_JOB_ENEMY = "Velasquez"
A_MASK, B_MASK, DOWN_MASK = 0x01, 0x02, 0x80


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state", default=STATE)
    ap.add_argument("--rom", default="baserom.gba")
    ap.add_argument("--turn-budget", type=int, default=4,
                    help="max player menus to drive")
    ap.add_argument("--menu-budget", type=float, default=200.0,
                    help="seconds to wait for one player menu")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    log = []

    def say(msg):
        line = f"[{time.time() - t0:7.1f}s] {msg}"
        print(line, flush=True)
        log.append(line)

    report = {              "schema": "a4-divergence-demo/3",
              "date": time.strftime("%Y-%m-%d"),
              "fixture": os.path.basename(args.state),
              "same_job": SAME_JOB,
              "menus": [], "attempts": [], "seeds_by_phase": [],
              "effect_snapshots": [], "verdicts": {}}

    def arm_quiet(probe):
        try:
            probe.arm()
        except Exception as exc:      # pragma: no cover - defensive
            say(f"  WARN: arm failed: {exc}")

    def roster_tiles(probe, slots):
        vals = {}
        for s in slots:
            base = ROSTER + STRIDE * s
            vals[s] = (u8(probe.g, base + 0xF6),
                       u8(probe.g, base + 0xF7))
        return vals

    def wait_tiles(probe, slots, budget=90.0):
        """Walk-in lands roster tiles seconds after boot; menu settle and
        move planning must wait for them (menu parks before the copy
        completes — the 0,0 read at menu1, 2026-10-05)."""
        deadline = time.time() + budget
        vals = {}
        while time.time() < deadline:
            drain_paired(probe.g)
            vals = roster_tiles(probe, slots)
            probe.g.cont()
            if all(x or y for (x, y) in vals.values()):
                say(f"  roster tiles populated: {vals}")
                return vals
            time.sleep(3.0)
        say(f"  WARN: tiles still {vals} after {budget}s")
        return vals

    def tiles_ready(probe, slots):
        """All player slots have walked in (nonzero roster tiles)."""
        return all(x or y for (x, y) in
                   roster_tiles(probe, slots).values())

    def wait_menu(probe, player_slots, budget, exclude=frozenset(),
                  tick_secs=3.0):
        """Owner-aware menu settle for a multi-ally fixture.

        Owner identity comes from the engine itself (run 2, 2026-10-05):
        at a freshly opened menu TARGET_X/Y reads the OWNER's own tile
        (C2 law, the same read plan_identified_move gates on). CT cannot
        attribute here — run 2 proved the owner parks ABOVE
        PARK_CT_MAX (306/353) while the frozen ally sits stable at 0,
        so flash+park attributed menu1 to slot 5 when the engine moved
        slot 7, and menu 2 to slot 7 when the engine moved slot 5.

        A settle requires, in order:
          * at least one player slot byte-stable across 2 ticks (a
            parked menu freezes the battle; charging changes ~38 CT per
            3 s) — but stability is NOT owner proof,
          * roster tiles populated (walk-in guard: an un-copied record
            reads a stable 0 mid-walk-in),
          * the cursor tile matching exactly ONE player slot, held
            across two consecutive ticks, and that slot stable —
            residue cursors (11,5 mid-walk-in) match nobody,
          * the match must not be in `exclude` (allies already
            committed this battle): a stale cursor left on the last
            committed ally while the next menu opens cannot mislabel
            the wait's owner.

        Fallback after 60 % of the budget: the unique stable slot with
        a nonzero CT that is not excluded (observed owner signature:
        owner stable at 306/353, the other ally at 0), logged as such.

        CT polling mirrors player_menu_settled (pump then read, no raw
        drain) so armed breakpoint stops are consumed by pump's handler
        instead of being swallowed.

        Returns (owner_slot, evidence dict) or (None, evidence). The
        evidence records which rule identified the owner.
        """
        deadline = time.time() + budget
        hold = {s: (None, 0) for s in player_slots}
        flashed = set()
        trace = []
        owner = None
        rule = None
        prior_match = None
        last = {"cursor": None, "match": None, "stable": None}
        while time.time() < deadline:
            probe.pump(tick_secs, "menu-wait", sample_every=60.0,
                       tick=tick_secs)
            cts = {s: probe.unit_u16(s, OFF_CT) for s in player_slots}
            for s, ct in cts.items():
                if ct == 1000:
                    flashed.add(s)
                prev, n = hold[s]
                hold[s] = (ct, n + 1 if ct == prev else 1)
            trace.append(dict(cts))
            stable = [s for s in player_slots
                      if cts[s] is not None and hold[s][1] >= 2]
            if not stable:
                continue
            # tiles gate: a park before walk-in completes is not a menu
            if not tiles_ready(probe, player_slots):
                continue
            tiles = roster_tiles(probe, player_slots)
            cursor = probe.read_target_cursor()
            match = ([s for s in player_slots if tiles.get(s) == cursor]
                     if cursor is not None else [])
            last = {"cursor": list(cursor) if cursor else None,
                    "match": match, "stable": stable}
            if len(match) == 1 and match[0] in stable \
                    and match[0] not in exclude:
                if prior_match == match[0]:
                    owner, rule = match[0], "target-cursor-own-tile"
                    break
                prior_match = match[0]
            else:
                prior_match = None
            if time.time() >= deadline - budget * 0.4:
                # fallback after 60 % of the budget: the unique stable
                # nonzero, non-excluded slot; logged as such
                nz = [s for s in stable if cts.get(s) and s not in exclude]
                if len(nz) == 1:
                    owner, rule = nz[0], "stable-nonzero-fallback"
                    break
        ev = {"ticks": len(trace), "flashed": sorted(flashed),
              "rule": rule, "trace_head": trace[:6],
              "trace_tail": trace[-6:],
              "cts": trace[-1] if trace else None,
              "exclude": sorted(exclude), **last}
        return owner, ev

    def commit_for(probe, kind, owner_slot, say, player_slots):
        """Plan+commit one behavior for the identified menu owner.

        Unpacks the probe's real return contract (commit_identified_move
        -> (completed, dest_used, legs), commit_identified_wait ->
        (completed, legs)) — run-1's bool(tuple) logged every attempt as
        ok=True regardless of outcome (2026-10-05).
        """
        drain_paired(probe.g)
        pre = probe.effect_snapshot()
        rec = {"kind": kind, "owner_slot": owner_slot, "pre": pre}
        owner_tile = None
        base = ROSTER + STRIDE * owner_slot
        ox, oy = u8(probe.g, base + 0xF6), u8(probe.g, base + 0xF7)
        probe.g.cont()
        if ox is not None and oy is not None:
            owner_tile = (ox, oy)
            rec["owner_tile"] = [ox, oy]

        if kind == "move":
            plan = probe.plan_identified_move()
            if plan is not None:
                plan["from"] = list(owner_tile) if owner_tile else None
                if plan.get("dest") is not None:
                    # Pre-open cursor residue on this fixture: it read
                    # (11,5) — no live unit stands there — while the
                    # owner tile was (4,10)/(5,10). The cursor is only
                    # authoritative INSIDE target mode (C2: it reads the
                    # unit's own tile after the engine opens it), so a
                    # fresh menu's plan must take the step-search path:
                    # open target mode, step, READ the reached tile,
                    # confirm there. Destination still RAM-identified
                    # before the confirming input.
                    rec["stale_dest"] = list(plan["dest"])
                    plan["dest"] = None
                    rec["dest_policy"] = (
                        "pre-open target cursor is walk-in residue, not "
                        "the owner tile; forced dest=None step-search "
                        "(engine sets the cursor on open)")
        else:
            plan = probe.plan_identified_wait()
            if plan is not None:
                plan["from"] = list(owner_tile) if owner_tile else None

        if plan is None:
            rec.update(plan=None, completed=False,
                       cmd_cursor=probe.read_cmd_cursor(),
                       target_cursor=probe.read_target_cursor())
            say(f"  no identified-{kind} plan (slot {owner_slot}, "
                f"tile={owner_tile}, cursor={rec['cmd_cursor']}, "
                f"target={rec['target_cursor']})")
            drain_paired(probe.g)
            return rec
        rec["plan_kind"] = plan.get("kind")
        rec["plan_dest"] = plan.get("dest")

        if kind == "move":
            completed, dest_used, legs = probe.commit_identified_move(plan)
            rec["dest_used"] = list(dest_used) if dest_used else None
        else:
            completed, legs = probe.commit_identified_wait(plan)
        rec["completed"] = bool(completed)
        rec["legs"] = legs
        if not completed:
            # an aborted commit can leave target mode or a panel open;
            # one bounded B returns to the command menu so the next
            # settle is not looking at a modal
            hits = probe.press(B_MASK, tag="a4:recovery-b")
            rec["recovery_b"] = hits
            say(f"  commit {kind} ABORTED (recovery B x{hits}); "
                f"last legs: {[l.get('leg') for l in legs[-4:]]}")
        drain_paired(probe.g)
        post = probe.effect_snapshot()
        rec["post"] = post
        pre_map = {r["slot"]: r for r in pre}
        post_map = {r["slot"]: r for r in post}
        # engine-level ground truth: which player slot's tile actually
        # changed across this commit (the engine moves exactly the menu
        # owner, so this attributes the owner independently of any CT
        # theory — run 2's labels were both wrong, these were right)
        rec["moved_slots"] = sorted(
            s for s in player_slots
            if s in pre_map and s in post_map
            and (pre_map[s]["x"], pre_map[s]["y"]) !=
                (post_map[s]["x"], post_map[s]["y"]))
        pre_row = next((r for r in pre if r["slot"] == owner_slot), None)
        post_row = next((r for r in post if r["slot"] == owner_slot), None)
        if pre_row and post_row:
            rec["owner_moved"] = ((pre_row["x"], pre_row["y"]) !=
                                  (post_row["x"], post_row["y"]))
        if owner_slot in rec["moved_slots"]:
            rec["owner_moved"] = True
        return rec

    with FixtureSession(args.state, rom=args.rom) as session:
        probe = Probe(session, verbose=False)
        arm_quiet(probe)     # seeds from the very first enemy turn
        roster = session.receipt["roster"]["slots"]
        players = [s for s in roster
                   if s.get("live") and not s.get("side_bit")
                   and s.get("type") != 20]
        enemies = [s for s in roster if s.get("live") and s.get("side_bit")]
        shape = {
            "players": [(s["slot"], s.get("name_text"), s.get("job"))
                        for s in players],
            "enemies": [(s["slot"], s.get("name_text"), s.get("job"))
                        for s in enemies],
            "two_same_job_players": (len(players) >= 2
                                     and all(s.get("job") == SAME_JOB
                                             for s in players[:2])),
            "same_job_enemy": any(s.get("job") == SAME_JOB
                                  for s in enemies),
        }
        report["fixture_shape"] = shape
        say(f"fixture shape: {shape}")
        if not (shape["two_same_job_players"] and shape["same_job_enemy"]):
            report["verdicts"]["fixture_shape"] = False
            _write(report, log)
            print("A4-DEMO FAIL (fixture shape)")
            return 1
        report["verdicts"]["fixture_shape"] = True

        player_slots = [s["slot"] for s in players]
        slot_name = {s["slot"]: s.get("name_text") for s in roster}
        slot_job = {s["slot"]: s.get("job") for s in roster}

        # ---- menus: first = move, next distinct owner = wait -----------
        commits = []      # successful real behaviors (incl. filler waits)
        for m in range(1, args.turn_budget + 1):
            # exclude already-committed allies from owner attribution so
            # a stale cursor cannot label the next menu with the wrong
            # slot (the distinct ally's behavior is what the demo needs)
            exclude = {c.get("owner_slot") for c in commits
                       if not c.get("filler") and
                       c.get("owner_slot") is not None}
            owner, ev = wait_menu(probe, player_slots, args.menu_budget,
                                  exclude=exclude)
            probe.disarm()          # clean reads for plan/snapshot phase
            if owner is None:
                say(f"menu {m} never settled "
                    f"(flashed={ev['flashed']} cts={ev['cts']})")
                report["menus"].append({"menu": m, "settled": False,
                                        "wait_ev": ev})
                _write(report, log)
                break
            drain_paired(probe.g)
            name = slot_name.get(owner)
            say(f"menu {m}: owner={name} slot={owner} "
                f"job={slot_job.get(owner)} flashed={ev['flashed']}")
            wait_tiles(probe, player_slots)
            report["menus"].append({"menu": m, "slot": owner, "name": name,
                                    "job": slot_job.get(owner),
                                    "wait_ev": ev})

            committed_owners = {c.get("owner") for c in commits}
            if not commits:
                kind = "move"       # first real behavior must be a move
            else:
                kind = "wait"       # distinct ally or filler repeat
            rec = commit_for(probe, kind, owner, say, player_slots)
            rec["owner"] = name
            rec["menu"] = m

            ok_move = (kind == "move" and rec.get("completed")
                       and _moved(rec))
            ok_wait = (kind == "wait" and rec.get("completed")
                       and not _moved(rec))
            say(f"  commit {kind}: plan={rec.get('plan_kind')} "
                f"completed={rec.get('completed')} "
                f"moved={rec.get('owner_moved')}")
            if not (ok_move or ok_wait):
                # not a behavior: keep it out of the verdict set; the
                # next menu retries the same kind (commits stays empty
                # for a failed move, or gains only real records)
                report["attempts"].append(
                    {"menu": m, "owner": name, "kind": kind,
                     "plan": rec.get("plan_kind"),
                     "completed": rec.get("completed"),
                     "owner_moved": rec.get("owner_moved"),
                     "moved_slots": rec.get("moved_slots"),
                     "owner_tile": rec.get("owner_tile"),
                     "stale_dest": rec.get("stale_dest"),
                     "dest_used": rec.get("dest_used"),
                     "legs": [l.get("leg") for l in
                              (rec.get("legs") or [])]})
                _write(report, log)
            else:
                rec["filler"] = (kind == "wait" and name
                                 in committed_owners)
                commits.append(rec)
                report["effect_snapshots"].append(
                    {"menu": m, "owner": name, "slot": owner,
                     "kind": kind, "plan_kind": rec.get("plan_kind"),
                     "completed": rec.get("completed"),
                     "owner_moved": rec.get("owner_moved"),
                     "moved_slots": rec.get("moved_slots"),
                     "owner_tile": rec.get("owner_tile"),
                     "stale_dest": rec.get("stale_dest"),
                     "dest_used": rec.get("dest_used"),
                     "legs": [l.get("leg") for l in
                              (rec.get("legs") or [])]})
                _write(report, log)

            real = [c for c in commits if not c.get("filler")]
            if len(real) >= 2:
                say("two real behaviors committed; pumping for the "
                    "same-job enemy turn")
                break
            # enemy phases between menus
            arm_quiet(probe)
            end = time.time() + 45.0
            while time.time() < end:
                probe.pump(3.0, f"m{m}-enemy", sample_every=60.0)
            report["seeds_by_phase"].append(
                {"after_menu": m, "actors": _actors(probe)})
            say(f"  seeds after menu {m}: "
                f"{report['seeds_by_phase'][-1]}")

        # final pump for the same-job enemy's retail turn
        arm_quiet(probe)
        seen = set()
        end = time.time() + 150.0
        while time.time() < end:
            probe.pump(3.0, "final", sample_every=60.0)
            seen = set(_actors(probe))
            if SAME_JOB_ENEMY in seen:
                break
        report["seeds_by_phase"].append({"final": True,
                                         "actors": _actors(probe)})
        report["seeds_total"] = len(probe.seeds)
        report["turns_router"] = len(probe.turns)
        report["t_elapsed_s"] = round(time.time() - t0, 1)

        # ---- verdicts ----------------------------------------------------
        real = [c for c in commits if not c.get("filler")]
        ally1 = next((c for c in real if c.get("kind") == "move"), None)
        ally2 = next((c for c in real if c.get("kind") == "wait"
                      and c.get("owner") != (ally1 or {}).get("owner")),
                     None)

        v = report["verdicts"]
        v["two_same_job_allies_distinct"] = bool(
            ally1 and ally2 and ally1["owner"] != ally2["owner"]
            and all(slot_job.get(c["owner_slot"]) == SAME_JOB
                    for c in (ally1, ally2)))
        v["divergence_move_vs_wait"] = bool(
            ally1 and ally2
            and ally1.get("plan_kind") == "identified-move"
            and ally2.get("plan_kind") == "identified-wait"
            and ally1.get("completed") is True
            and ally2.get("completed") is True
            and _moved(ally1)
            and not _moved(ally2))
        writes = getattr(session, "writes", []) or []

        def _addr(w):
            a = w.get("addr")
            try:
                return int(a, 16) if isinstance(a, str) else int(a)
            except (TypeError, ValueError):
                return -1

        report["writes"] = [
            {"addr": (f"0x{_addr(w):08x}" if _addr(w) >= 0 else str(
                w.get("addr"))),
             "note": w.get("note")} for w in writes]
        only_key_enable = all(_addr(w) == KEY_ENABLE for w in writes)
        v["interception_no_memory_writes"] = bool(only_key_enable)
        v["same_job_enemy_retail_turn"] = bool(SAME_JOB_ENEMY in seen)
        v["enemy_unaffected"] = bool(only_key_enable
                                     and SAME_JOB_ENEMY in seen)
        demo_ok = all(v.get(k) is True for k in
                      ("fixture_shape",
                       "two_same_job_allies_distinct",
                       "divergence_move_vs_wait",
                       "enemy_unaffected"))
        report["same_job_enemy_actors_seen"] = sorted(seen)
        _write(report, log)

    print(f"A4-DEMO {'PASS' if demo_ok else 'FAIL'} "
          f"({report.get('t_elapsed_s')}s)", flush=True)
    print(json.dumps(report["verdicts"], indent=2), flush=True)
    return 0 if demo_ok else 1


def _moved(rec):
    """Engine-observed movement across this commit (any player slot).

    The engine moves exactly the menu owner, so a nonempty moved_slots
    OR a changed owner tile means the committed unit moved. Run 2
    lesson: labels can be wrong, the tile delta never is.
    """
    if rec.get("owner_moved") is True:
        return True
    return bool(rec.get("moved_slots"))


def _actors(probe):
    return sorted({u["name"] for s in probe.seeds
                   for u in s.get("ctx_units", []) if u.get("name")})


def _write(report, log):
    path = os.path.join(OUT_DIR, "demo.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    with open(os.path.join(OUT_DIR, "demo.log"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(log) + "\n")


if __name__ == "__main__":
    sys.exit(main())
