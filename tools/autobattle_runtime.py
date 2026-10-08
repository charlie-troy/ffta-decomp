"""A3 minimal autonomous battle runtime.

Built directly on the A2.5 frozen contract (docs/player-ai-control.md,
"A2.5 result") and the Probe transport from tools/probe_control_handoff.py:

- States: idle -> running -> (takeover -> running)* -> completed | stalled |
  connection_lost | paused. The runtime stops issuing input after completion,
  a bounded stop, connection loss, or an unknown modal. A STOP request pauses
  the battle for manual resume: input stops immediately, breakpoints are
  disarmed, and (with the CLI's --on-stop handoff) the emulator is left
  running so the player can continue from the live screen.
- A5.1 resolves the verified fresh-menu owner by cursor-own-tile plus
  stable CT and boot-verified name/id/job/side. CT values never name actors.
  Targeting keeps a pinned identity; every new input revalidates that actor.
- In the legacy `retail-ai` mode, enemies run unchanged retail AI and the
  companion selects identified Move/Wait for player menus. Scenario actions
  are a narrow fixture seam; ordered conditional tactics remain A5.2+ work.
- Turn events append to outputs/autobattle/<run-id>/events.jsonl. Unknown
  fields are null, never inferred labels.
- Stall detection is bounded by seed silence plus a wall-clock timeout.

No ROM code is patched: the Probe owns RAM breakpoints only, removed at exit.
"""

from __future__ import annotations

import json
import math
import os
import time

from probe_control_handoff import Probe
from autobattle_identity import ActorAdapter, IdentityError, key
from tactics_adapter import TacticsAdapter

# Runtime states (roadmap A3: explicit state machine)
IDLE = "idle"
RUNNING = "running"
TAKEOVER = "takeover"
COMPLETED = "completed"
STALLED = "stalled"
CONNECTION_LOST = "connection_lost"
PAUSED = "paused"

EVENT_SCHEMA = {
    "t": None, "kind": None, "scenario": None, "turn": None,
    "actor": None, "actor_slot": None, "control_mode": None,
    "selected_action": None, "selected_target": None,
    "position_before": None, "position_after": None,
    "state": None, "seeds": None, "router_hits": None, "note": None,
    # round 6: the start event must CARRY the input-log filename — the
    # receipt validator's missing-log check keys off it, and the old
    # silently-dropped-field behavior is exactly the bug class Astra
    # flagged in round 4 (a passed kwarg that never reaches the artifact).
    "input_log": None,
    "actor_identity": None, "engine_result": None, "next_actor": None,
    # A5.3: the conditional-tactics receipt (policy, outcome, reason, matched
    # scope/rule, observation age, offered candidates). None without a policy.
    "tactics": None,
    "recovery": None,
}


class BattleRuntime:
    # roster tile offsets (A2.5 contract, probe_control_handoff constants)
    _TILE_X = 0xF6
    _TILE_Y = 0xF7
    """Drive one battle from the verified fixture with bounded stopping."""

    def __init__(self, session, scenario, run_id, out_dir,
                 mode="retail-ai", stall_seed_seconds=150.0,
                 wall_timeout=600.0, max_turns=None, verbose=True,
                 resume=False, pause_at_boundary=False,
                 tactics_policy=None, tactics_policy_source=None, bounded_self_cure=False,
                 bounded_ally_cure=False,bounded_ally_life=False):
        self.s = session
        if bounded_ally_life:
            from recovery_life_trace import LifeExecutionProbe
            self.p = LifeExecutionProbe(session,verbose=verbose)
        else:self.p = Probe(session, verbose=verbose)
        # A5.3: with a policy, the scenario's fixed per-actor assignment is
        # replaced by the frozen chooser (docs/tactics-policy.md). The
        # adapter is read-only; a bad policy raises here, before any input.
        self.tactics_policy_source = tactics_policy_source
        self.tactics = (TacticsAdapter(self.p, tactics_policy)
                        if tactics_policy is not None else None)
        self._tactics_meta = None
        self.bounded_self_cure = bool(bounded_self_cure)
        self.bounded_ally_cure = bool(bounded_ally_cure)
        self.bounded_ally_life = bool(bounded_ally_life)
        if sum((self.bounded_self_cure,self.bounded_ally_cure,self.bounded_ally_life))>1:
            raise ValueError('recovery fixture opt-ins are mutually exclusive')
        self._owner_observed_at = None
        self.scenario = scenario
        self.scenario_id = scenario.get("scenario_id", "unknown")
        self.run_id = run_id
        self.mode = mode
        self.stall_seed_seconds = stall_seed_seconds
        self.wall_timeout = wall_timeout
        self.max_turns = max_turns
        self.state = IDLE
        self.turn = 0
        self.stop_file = os.path.join(out_dir, "STOP")
        self.events_path = os.path.join(out_dir, "events.jsonl")
        # C3 resume: a resumed leg APPENDS to the same events/input logs
        # (one battle, two runner legs) and re-bases the shared wall clock
        # so all cross-checks (stop latency, write ordering) stay on one
        # timeline. `t` is rounded to 0.1 s — a fractional resume base
        # would make leg-2's first event sort before leg-1's last.
        self.resume = bool(resume)
        if self.resume:
            # Re-base on the LAST recorded event t (not the first stop): leg
            # 2's t=0 must sit strictly after leg 1's final event or the
            # validator's monotonic-timestamp rule trips on the appended
            # records. t is rounded to 0.1 s, so the +1.0 guard clears the
            # rounding slop with room to spare.
            max_t = 0.0
            for clock_path in (self.events_path, os.path.join(out_dir, "input-log.jsonl")):
                try:
                    with open(clock_path, encoding="utf-8") as fh:
                        for line in fh:
                            line = line.strip()
                            if line:
                                rec = json.loads(line)
                                t = rec.get("t")
                                if type(t) in (int, float) and math.isfinite(t):
                                    max_t = max(max_t, float(t))
                except (OSError, ValueError):
                    pass
            self.t0 = time.time() - (max_t + 1.0)
        else:
            self.t0 = time.time()
        # C1 contract: a timestamped raw input-write log the receipt
        # validator cross-checks against stop/terminal events — ordering
        # proof from the transport level, not just final state
        self.input_log_path = os.path.join(out_dir, "input-log.jsonl")
        self._input_log = open(self.input_log_path, "a", encoding="utf-8")
        if self.resume:
            self._log_input({"event": "resume",
                             "t": round(time.time() - self.t0, 3)})
        self._stop_requested_t = None  # wall-clock latency measurement
        # shared wall clock with the probe's write log (validator rule: a
        # write is "after stop_requested" relative to the SAME t0)
        self.p.t0 = self.t0
        # boundary bounds: the re-arming menu wait may not run past the
        # wall budget (resume rebases t0, so the probe must see the same
        # clock) and may not press past a latched stop
        self.p.wall_seconds = self.wall_timeout
        self.p.bound_t0 = 0.0
        self._last_seed_count = 0
        self._last_seed_t = time.time()
        # A5.1 manual-handoff entry point: pause ON PURPOSE at the first
        # identified player menu instead of driving it. The old handoff
        # raced a STOP file against the boundary drive, so whether the pause
        # landed with the player's menu open (the C3 shape) was luck.
        self.pause_at_boundary = bool(pause_at_boundary)
        self._boundary_pause_used = False
        self._terminal_reason = None
        self._saw_unknown_modal = False
        self._failed_boundaries = 0  # consecutive echo-failed drives (c3-live-a5)
        self._dead_polls = 0  # debounce: roster copies can read 0 transiently
        self._dead_seed_mark = 0  # seed count when the current dead streak began
        self._dead_grace_t = None  # wall time the defeat debounce first held
        self._stop_requested = False  # Astra 2026-09-17: checked INSIDE long
        self.adapter = None
        self.owner = None
        self._pre_players = None
        self._engine_result = None
        self._boundary_seed_count = len(self.p.seeds)
        #                              waits, so a pause ends waits promptly

    def _stop_check(self):
        """Poll the STOP file cheaply; latches the first sighting."""
        if not self._stop_requested and os.path.exists(self.stop_file):
            self._stop_requested = True
            self._stop_requested_t = time.time()
            # C1: detection latency = observation time minus the stop file's
            # own mtime (when the requester dropped it). Contract bound: 2 s
            # outside an already-pending OS/transport call; the runtime's
            # 3 s pump tick is the recorded worst case.
            try:
                latency = round(self._stop_requested_t -
                                os.path.getmtime(self.stop_file), 3)
            except OSError:
                latency = None
            self._log_input({"event": "stop_requested",
                             "t": round(time.time() - self.t0, 3),
                             "detection_latency_s": latency,
                             "note": "STOP file observed; no further "
                                     "gameplay key injections permitted"})
        return self._stop_requested

    def _log_input(self, rec):
        """Append one raw input/stop record to input-log.jsonl (C1)."""
        try:
            self._input_log.write(json.dumps(rec) + "\n")
            self._input_log.flush()
        except Exception:
            pass

    def log_manual_write(self, val):
        """Record a NON-automation key write (C1 gap 4: after the runner
        detaches from a paused handoff, input the player — human or agent —
        sends through the emulator is manual, and the validator must not
        fail it as escaped automation input)."""
        self._log_input({"event": "manual_key_write", "val": val,
                         "t": round(time.time() - self.t0, 3)})

    # -- events ------------------------------------------------------------
    def event(self, kind, **fields):
        rec = dict(EVENT_SCHEMA)
        rec.update({
            "t": round(time.time() - self.t0, 1),
            "kind": kind,
            "scenario": self.scenario_id,
            "state": self.state,
            "seeds": len(self.p.seeds),
            "router_hits": self.p.router_hits,
        })
        for k, v in fields.items():
            if k not in rec:
                # round 6: a kwarg that the schema would silently drop is a
                # caller bug — Astra round 4 caught `reason` vanishing this
                # way. Fail loudly at the call site instead.
                raise TypeError(f"event() got an unexpected field {k!r} "
                                f"(not in EVENT_SCHEMA)")
            rec[k] = v
        with open(self.events_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        if self.p.verbose:
            print("  EV " + json.dumps(rec))
        return rec

    # -- guards ------------------------------------------------------------
    def live_guard(self):
        """Verify the fixture live before leaving `idle` (paused until then)."""
        g = self.g = self.s.g
        try:
            if not self.s.receipt.get("ok"):
                raise IdentityError("session fixture guard rejected")
            self.adapter = ActorAdapter(self.s)
            rows = self.adapter.snapshot()
            actions = self.scenario.get("actor_actions", [])
            if (not isinstance(actions, list) or any(
                    not isinstance(a, dict) or set(a) != {"name", "id", "action"}
                    or not isinstance(a["name"], str) or type(a["id"]) is not int
                    for a in actions)):
                raise IdentityError("malformed fixture action assignment")
            keys = [(a.get("name"), a.get("id")) for a in actions]
            if len(set(keys)) != len(keys) or any(k not in {key(r) for r in rows} for k in keys):
                raise IdentityError("duplicate or absent action assignment")
            if any(a.get("action") not in ("move", "wait") for a in actions):
                raise IdentityError("unsupported action assignment")
            self.event("guard", note=f"verified player identities: {[key(r) for r in rows]}")
            return True
        except IdentityError as exc:
            self.event("guard", note=f"identity guard rejected: {exc}")
            return False

    def _actor_fields(self):
        row = self.owner or {}
        return {"actor": row.get("name_text"), "actor_slot": row.get("slot"),
                "actor_identity": {f: row.get(f) for f in
                                   ("name_text", "id", "job", "side_bit", "addr")}}

    def _actor_valid_for_input(self):
        if self._stop_check():
            return False
        try:
            rows = self.adapter.snapshot()
            row = next((r for r in rows if key(r) == key(self.owner)), None)
            if row is None or row["slot"] != self.owner["slot"] or row["hp"] <= 0:
                raise IdentityError("active actor invalidated during drive")
        except IdentityError as exc:
            self._saw_unknown_modal = True
            self._terminal_reason_identity = str(exc)
            self.event("note", **self._actor_fields(), note=f"input identity rejected: {exc}")
            return False
        return True

    # -- state classification ---------------------------------------------
    def _all_cts_zero(self):
        cts = self.p.cts()
        return all(c == 0 for c in cts)

    def _classify(self):
        """Return the next state from live engine observations."""
        if time.time() - self.t0 >= self.wall_timeout or (self.max_turns and self.turn >= self.max_turns):
            return STALLED
        seeds_now = len(self.p.seeds)
        if seeds_now > self._last_seed_count:
            self._last_seed_count = seeds_now
            self._last_seed_t = time.time()
        quiet = time.time() - self._last_seed_t
        torn = self.p.battle_torn_down()
        # player boundary: any frozen-CT menu owned by the player record
        # dead check is debounced (~9 s of consecutive zeroed hp) because a
        # roster record can read wiped during action execution (run 6 lesson)
        # a3-natural2 lesson: a transient wipe also shows seed traffic, so
        # seeds seen during the debounce window prove "mid-action copy",
        # not a real death — only a *silent* debounce trips the grace.
        if self._party_dead():
            self._dead_polls += 1
            if len(self.p.seeds) > self._dead_seed_mark:
                self._dead_polls = 0  # traffic during the wipe: copy, not death
            self._dead_seed_mark = len(self.p.seeds)
        else:
            self._dead_polls = 0
            self._dead_seed_mark = len(self.p.seeds)
            self._dead_grace_t = None
        # a3-natural1 lesson: after the player party is defeated the battle still ends
        # naturally (defeat animation -> results screen) ~30 s later. Stopping
        # the run at the debounce pre-empted that conclusion, so a held defeat
        # suppresses takeover (menus no longer belong to him) and the stall
        # bound, but still lets the engine's own end classify the run below.
        # Only bounds may end it while the conclusion has not arrived.
        in_grace = self._dead_polls >= 3
        if in_grace and self._dead_grace_t is None:
            self._dead_grace_t = time.time()
            self.event("note", **self._actor_fields(),
                       note="party defeat held 3 polls with seed silence; "
                            "suppressing takeover until battle end")
        # completion: the contract's battle-end shape — all CTs zero, seed
        # silence, roster still allocated (not torn down), router idle
        if (len(self.adapter.expected) == 1 and self._all_cts_zero() and quiet >= 45.0 and not torn
                and self._last_seed_count > 0):
            return COMPLETED
        if len(self.adapter.expected) == 1 and torn and quiet >= 45.0:
            return COMPLETED
        if self._saw_unknown_modal:
            # Results may clear the actor before a commit result is read.
            # Suppress all input and claims while allowing the previously
            # verified solo end signature to settle; do not call a timeout
            # a completed battle or an unverified move a successful turn.
            if len(self.adapter.expected) == 1 and self._all_cts_zero():
                return RUNNING
            return STALLED
        # Excluded when the whole CT vector is zero: the results screen parks
        # every CT at a stable 0 (run 20 end shape), which is also a stable
        # player CT — driving there would send a route into a non-battle UI.
        # The zero-vector guard is RE-evaluated after the (slow, 9 s) frozen
        # check: the battle end can transition charging -> results INSIDE the
        # check's stability window, and a guard evaluated before the check
        # would be stale — the 2026-09-17 victory-path wedge (a drive into
        # the results screen, bounded by B-recovery) was exactly that race.
        if not in_grace and not self._all_cts_zero():
            try:
                rows = self.adapter.snapshot()
                owner = self.adapter.observe(self.p, rows)
                if owner is not None:
                    self.owner = owner
                    self.p.active_player_slot = owner["slot"]
                    # A5.3: the tactics snapshot's age is measured from THIS
                    # observation (the fresh-menu pairing that authorizes the
                    # turn) to the policy decision, never assumed.
                    self._owner_observed_at = time.time()
                    return TAKEOVER
            except IdentityError:
                # Transient copies during enemy execution have no input
                # authority. Bound by the existing no-progress timeout.
                self.adapter.prior = None
        if in_grace:
            # defeat held but the engine's conclusion never arrived: bounds
            # only, so a live battle with a dead tracked player is bounded,
            # not abandoned mid-sequence
            if time.time() - self.t0 >= self.wall_timeout:
                return STALLED
            if self.max_turns and self.turn >= self.max_turns:
                return STALLED
            if time.time() - self._dead_grace_t >= self.wall_timeout:
                return STALLED  # conclusion never arrived within the budget
            return RUNNING
        # stall bound: seed silence beyond the bound with no driveable menu
        if quiet >= self.stall_seed_seconds:
            return STALLED
        if time.time() - self.t0 >= self.wall_timeout:
            return STALLED
        if self.max_turns and self.turn >= self.max_turns:
            return STALLED
        return RUNNING

    # -- main loop ---------------------------------------------------------
    def run(self):
        self.state = RUNNING
        if self.resume:
            # C3 resume leg: marks the continuation of ONE battle whose
            # first leg ended `paused` — the validator's resume rule keys
            # on this and on the final receipt's `resumed: true`.
            self.event("start", control_mode=self.mode,
                       input_log="input-log.jsonl",
                       note="resume: continuation of a battle whose first "
                            "leg ended paused (manual handoff returned "
                            "control)")
        else:
            self.event("start", control_mode=self.mode,
                       input_log="input-log.jsonl")
        try:
            self.p.arm()
            while True:
                # latched stop (seen inside a wait or recovery) exits before
                # any further classification or input (Astra 2026-09-17:
                # "input stops immediately" must include mid-wait). Goes
                # through _stop_check so the latch + input-log record happen
                # on this path too (C1: stop-before-start row).
                if self._stop_check():
                    # manual takeover request: stop OUR input now and leave
                    # the battle live. `takeover` (the driven boundary state)
                    # is automation-owned; `paused` is the real handoff to
                    # the player — no further input, breakpoints disarmed,
                    # emulator survival decided by the CLI's --on-stop.
                    # Round 3: the boundary handler can finalize the pause
                    # itself when the stop lands mid-drive — in that case
                    # _terminal_reason is already set and the stop event is
                    # already written; finalizing twice would emit two
                    # terminal stops (caught by the strict-press gate).
                    if self._terminal_reason is None:
                        self._finish(PAUSED,
                                     "STOP requested: battle left running for "
                                     "manual play")
                    break
                # C1 latency: evaluate the stop check inside the pump's
                # packet cycle (stop_when), not only between pump ticks —
                # worst case otherwise is one full 3 s tick (measured
                # 3.005 s in stop-coincides-with-progress, over the 2 s
                # contract bound)
                self.p.pump(3.0, "runtime", sample_every=60.0, tick=3.0,
                            stop_when=lambda _probe: self._stop_check())
                nxt = self._classify()
                if nxt == TAKEOVER:
                    if self.pause_at_boundary and not self._boundary_pause_used:
                        self._boundary_pause_used = True
                        self._pause_at_player_boundary()
                        break
                    self._drive_player_boundary()
                    if self._terminal_reason is not None:
                        break
                elif nxt == COMPLETED:
                    self._finish(COMPLETED, "battle end signature held")
                    break
                elif nxt == STALLED:
                    reason = (getattr(self, "_terminal_reason_identity", None)
                              or ("turn budget reached" if self.max_turns and self.turn >= self.max_turns else None)
                              or ("party defeated (hp block zeroed); "
                              "battle end did not arrive within budget"
                              if self._party_dead()
                              else (self.adapter.last_rejection or "no-progress bound reached")))
                    self._finish(STALLED, reason)
                    break
        except (OSError, ConnectionError) as exc:
            self.state = CONNECTION_LOST
            self._finish(CONNECTION_LOST, f"transport lost: {exc}")
        return self.state

    def _actor_pos(self):
        from probe_control_handoff import ROSTER, STRIDE, u8
        ps = self.p.player_slot()
        if ps is None:
            return None
        base = ROSTER + STRIDE * ps
        return {"x": u8(self.g, base + self._TILE_X),
                "y": u8(self.g, base + self._TILE_Y)}

    def _party_dead(self):
        # A dead known actor cannot suppress or authorize another ally.
        # Missing/transient identities are unknown, never evidence of defeat.
        if self.adapter is None:
            return False
        try:
            rows = self.adapter.snapshot()
            return bool(rows) and all(r["hp"] == 0 for r in rows)
        except IdentityError:
            return False

    def _pause_at_player_boundary(self):
        """Deliberate manual handoff at the identified player menu (A5.1).

        The C3 handoff reproduced by racing a STOP file against the boundary
        drive, so the pause point — and whether automation input had already
        fired — was luck. This path latches the SAME handoff contract on
        purpose: the fresh player menu is identified from RAM, left OPEN and
        untouched, no input is issued, the raw input log records the latch
        exactly as a STOP request does, and the emulator is left running for
        the player (the CLI's --on-stop decides survival).
        """
        owner = self.owner or {}
        before = {"x": owner.get("x"), "y": owner.get("y")}
        shot = None
        try:
            shot = self.s.screenshot(os.path.join(
                os.path.dirname(self.events_path),
                f"boundary-turn{self.turn + 1}.png"))
        except Exception:
            shot = None
        self.event("boundary", **self._actor_fields(),
                   control_mode="external", position_before=before,
                   note=shot)
        self._stop_requested = True
        self._stop_requested_t = time.time()
        self._log_input({"event": "stop_requested",
                         "t": round(time.time() - self.t0, 3),
                         "detection_latency_s": 0.0,
                         "note": "pause-at-boundary: intentional latch at "
                                 "the identified player menu; no input issued"})
        self.event("note", **self._actor_fields(), control_mode="external",
                   note="pause-at-boundary: identified player menu left open "
                        "with no input issued (manual handoff)")
        self._finish(PAUSED, "pause-at-boundary: identified player menu left "
                             "open for manual play (no input issued)")

    def _drive_player_boundary(self):
        try:
            self._pre_players = self.adapter.revalidate(self.owner, self.p)
        except IdentityError as exc:
            self._saw_unknown_modal = True
            self.event("note", note=f"fresh-menu identity rejected: {exc}; no input")
            return
        self._engine_result = None
        self._boundary_seed_count = len(self.p.seeds)
        prev = self.state
        self.state = TAKEOVER
        before = self._actor_pos() or {"x": None, "y": None}
        shot = None
        try:
            shot = self.s.screenshot(os.path.join(
                os.path.dirname(self.events_path),
                f"boundary-turn{self.turn + 1}.png"))
        except Exception:
            shot = None
        self.event("boundary", **self._actor_fields(),
                   control_mode="external", position_before=before,
                   note=shot)
        # -- C2 identified-candidate path -----------------------------------
        # When the open menu's decoded command cursor reads Move and the
        # decoded target cursor is readable, THAT is the candidate: the
        # command and the destination are identified from RAM before the
        # confirming input, never inferred from the key sequence. The driver
        # navigates the real cursors (re-reading RAM between legs) and
        # finishes the turn with the proven Wait commit (probe5/6: the move
        # re-opens the command menu, so the turn only closes after Wait).
        self.adapter.prior = None
        self._tactics_meta = None
        if self.bounded_self_cure or self.bounded_ally_cure or self.bounded_ally_life:
            self._drive_recovery_boundary(before)
            return
        # -- A5.3 conditional tactics --------------------------------------
        # With a policy configured, the adapter supplies only the commands
        # the engine currently offers (read from RAM) and the frozen chooser
        # picks one. A decision the engine no longer offers cancels the
        # commit — it never falls back to a command the policy did not
        # choose (the scenario path keeps its identified-Wait fallback).
        policy_choice = None
        if self.tactics is not None:
            evaluation = self.tactics.choose(self.owner, self._owner_observed_at)
            decision = evaluation["decision"]
            self._tactics_meta = {
                "policy": self.tactics_policy_source,
                "outcome": evaluation["outcome"],
                "reason": evaluation["reason"],
                "scope": evaluation["scope"],
                "rule_id": evaluation["rule_id"],
                "detail": evaluation["detail"],
                "age_seconds": self.tactics.last_age,
                "candidates": list(self.tactics.last_candidate_ids),
                # Keep the actual chooser input, rather than making later
                # audits reconstruct HP/MP from a nearby engine-result row.
                "snapshot": self.tactics.last_snapshot,
            }
            if decision is None:
                self.event("note", **self._actor_fields(),
                           control_mode="external",
                           note=("tactics policy selected no candidate ("
                                 + evaluation["reason"]
                                 + (": " + str(evaluation["detail"])
                                    if evaluation["detail"] else "")
                                 + "); no input issued"))
                self._saw_unknown_modal = True
                self.state = prev
                return
            policy_choice = decision["kind"]
            self.event("note", **self._actor_fields(),
                       control_mode="external",
                       note=(f"tactics policy matched rule "
                             f"{evaluation['rule_id']!r} in the "
                             f"{evaluation['scope']!r} scope -> "
                             f"{decision['candidate_id']} "
                             f"({evaluation['reason']}, "
                             f"age {self.tactics.last_age:.2f}s)"))
        action = policy_choice or next(
            (a["action"] for a in self.scenario.get("actor_actions", [])
             if (a["name"], a["id"]) == key(self.owner)), "move")
        plan = None
        try:
            plan = self.p.plan_identified_move() if action == "move" else None
        except Exception:
            plan = None
        if plan is None:
            # C3: a KNOWN command cursor (0/1/2) with an unplannable move
            # is still an IDENTIFIED menu — Wait closes the turn from any
            # command. This is the complete-battle fallback: menus parked
            # on Action (re-opened post-move, the c2-live3 "non-standard"
            # shape) and post-handoff menus now close honestly instead of
            # bounding the run. The plan is still read from RAM before any
            # input; an unknown cursor byte rejects exactly as before.
            try:
                waitplan = self.p.plan_identified_wait()
            except Exception:
                waitplan = None
            # A5.3: the identified-Wait fallback belongs to the scenario
            # path only. When a policy chose Move, a move the engine no
            # longer offers must CANCEL (no input), not silently commit the
            # policy's unselected Wait.
            if waitplan is not None and policy_choice in (None, "wait"):
                self.event("note", **self._actor_fields(),
                           control_mode="external",
                           note="identified-wait candidate (sticky cursor "
                                f"byte {waitplan['command_id']}) — echo-gated "
                                "Wait commit: the first DOWN must move the "
                                "decoded cursor or the menu is not open and "
                                "no further input fires")
                wdone, _wlog = self.p.commit_identified_wait(
                    waitplan, stop_check=self._stop_check,
                    input_guard=self._actor_valid_for_input,
                    log_leg=lambda rec: self._log_input(rec))
                if wdone:
                    self._failed_boundaries = 0
                    self._record_identified_turn(
                        plan_kind="identified-wait", plan=waitplan,
                        dest_used=None, drove=wdone, before=before,
                        fail_log=_wlog)
                    return
                if self._stop_check():
                    self._record_identified_turn(
                        plan_kind="identified-wait", plan=waitplan,
                        dest_used=None, drove=wdone, before=before,
                        fail_log=_wlog)
                    return
                # c3-live-a5 law: a landed echo with no byte change is a
                # panel over a NOT-YET-OPEN menu as often as a dead UI —
                # one panel-B is probed inside the driver; after that, the
                # honest handling is to WAIT for the menu (re-arm the
                # boundary), not to kill the run. Bounded by wall budget,
                # re-arm count, and consecutive failed drives (3 in a row
                # = the menu never really opens: bound for manual play).
                self._failed_boundaries += 1
                if self._failed_boundaries >= 3:
                    self._saw_unknown_modal = True
                    self.event("note", **self._actor_fields(),
                               note="menu never answered after 3 "
                                    "echo-ladder boundaries: bounding run "
                                    "— battle left on the open menu for "
                                    "manual play")
                    self.state = prev
                    return
                self.event("note", **self._actor_fields(),
                           note="menu not answering (echo landed, byte "
                                "frozen): turn-transition panel suspected "
                                "— re-arming the menu boundary (no further "
                                "input until a real menu echoes)"
                                + (f" [last leg: {_wlog[-1]}]" if _wlog
                                   else ""))
                self.state = prev
                return
            # Astra round-6 gap 3: an invalid snapshot must PREVENT input.
            # A planner rejection is a rejected candidate, not a degraded
            # one: driving a fixed route from here would select by key
            # sequence (the exact unfalsifiable claim the contract bans).
            self.event("note", **self._actor_fields(),
                       note="identified-move plan rejected: menu state "
                            "not identified from RAM — no input issued "
                            "(candidate rejected, battle left on the "
                            "open menu)"
                            + (" [tactics policy chose the move candidate, "
                               "which the engine menu no longer offers: "
                               "commit cancelled, no input]"
                               if policy_choice == "move" else ""))
            self._saw_unknown_modal = True
            self.state = prev
            return
        # The driver publishes what ACTUALLY closed the turn as a `finish`
        # leg (probe4: an occupied-tile repair cancels the planned move
        # and closes via the Wait tail) — the claim must name the finish,
        # never the cancelled plan (c3-live round 7 honesty rule).
        finish = {"kind": "identified-move", "reason": None}

        def _move_leg(rec):
            self._log_input(rec)
            if rec.get("event") == "finish":
                finish["kind"] = rec.get("kind") or finish["kind"]
                finish["reason"] = rec.get("reason")

        drove, dest_used, _leglog = self.p.commit_identified_move(
            plan, stop_check=self._stop_check,
            input_guard=self._actor_valid_for_input,
            log_leg=_move_leg)
        if drove:
            self._failed_boundaries = 0
            if finish["kind"] == "identified-wait":
                plan = {"kind": "identified-wait",
                        "command_id": 2, "from": plan["from"]}
                dest_used = None       # the move was cancelled: no tile claim
            self._record_identified_turn(plan_kind=finish["kind"],
                                         plan=plan, dest_used=dest_used,
                                         drove=drove, before=before,
                                         fail_log=_leglog)
            return
        if self._stop_check():
            # a latched STOP owns this exit: the recorder finishes paused
            self._record_identified_turn(plan_kind=finish["kind"],
                                         plan=plan, dest_used=dest_used,
                                         drove=drove, before=before,
                                         fail_log=_leglog)
            return
        # c3-live-a5 law, move path: a landed echo with a frozen byte is a
        # transition panel over a NOT-YET-OPEN menu as often as a dead UI
        # (the driver's dest-search legs all echo-landed here). Re-arm the
        # boundary under the same bounded 3-strikes law as the Wait path;
        # the driver's own b-ladder already probed one panel-B inside the
        # failed drive.
        self._failed_boundaries += 1
        if self._failed_boundaries >= 3:
            self._saw_unknown_modal = True
            self.event("note", **self._actor_fields(),
                       note="menu never answered after 3 echo-ladder "
                            "boundaries: bounding run — battle left on the "
                            "open menu for manual play")
            self.state = prev
            return
        self.event("note", **self._actor_fields(),
                   note="identified-move drive did not close the turn "
                        "(echo landed, byte frozen): turn-transition "
                        "panel suspected — re-arming the menu boundary "
                        "(no further input until a real menu echoes)"
                        + (f" [last leg: {_leglog[-1]}]" if _leglog else ""))
        self.state = prev

    def _drive_recovery_boundary(self, before):
        from recovery_runtime import drive_recovery
        from party_recovery_runtime import drive_party_recovery
        from life_recovery_runtime import drive_life_recovery
        from recovery_executor import RecoveryStopped
        journal = {}
        def capture_confirmation(observation):
            suffix = "" if self.turn == 0 else f"-turn{self.turn + 1}"
            self.s.screenshot(os.path.join(os.path.dirname(self.events_path),
                                           f"recovery-{observation.state}{suffix}.png"))
        try:
            drive = (drive_life_recovery if self.bounded_ally_life else
                     drive_party_recovery if self.bounded_ally_cure else drive_recovery)
            confirmed = drive(self, journal, before_confirmation=capture_confirmation)
        except RecoveryStopped as exc:
            self.event("note", **self._actor_fields(), recovery=journal, note=str(exc))
            self._finish(PAUSED, "STOP requested during bounded recovery: manual handoff")
            return
        except (ValueError, TimeoutError) as exc:
            self.event("note", **self._actor_fields(), recovery=journal,
                       note=f"bounded recovery rejected: {exc}; no retry")
            self._finish(STALLED, "bounded recovery rejected: " + str(exc))
            return
        except (OSError, ConnectionError) as exc:
            self.event("note", **self._actor_fields(), recovery=journal,
                       note=f"bounded recovery transport lost: {exc}; no retry")
            raise
        # The scoped transport has restored tracing before any terminal or
        # turn event. No fixed-roster adapter reads were used while targeting.
        if self._stop_check():
            self.event("note", **self._actor_fields(), recovery=journal, note="STOP after recovery cleanup")
            self._finish(PAUSED, "STOP requested after bounded recovery: manual handoff")
            return
        if not confirmed:
            self.event("note", **self._actor_fields(), recovery=journal, note="policy left Wait unexecuted")
            self._finish(STALLED, "bounded recovery: policy selected no Wait; no retry")
            return
        if self.bounded_ally_cure or self.bounded_ally_life:
            baseline = {r['id']:r for r in journal['post_Life_roster'] if r['live']} if self.bounded_ally_life else {r['id']:r for r in journal['baseline_roster']}
            after_rows = []
            continuation=(journal['Life_effect']['continuation'] if self.bounded_ally_life else journal['continuations'][0])
            for row in continuation['party_after']:
                observed = {f:baseline[row['id']][f] for f in
                            ('name','name_text','id','type','base_job','race','job','level','side_raw',
                             'side_bit','unaffiliated','max_hp','max_mp','slot','live')}
                observed.update(hp=row['hp'],mp=row['mp'],x=row['tile'][0],y=row['tile'][1])
                after_rows.append(observed)
            after_row = next(r for r in after_rows if r['id']==self.owner['id'])
        else:
            after_row = journal["continuations"][0]["player_after"]
            after_rows = [after_row]
        accepted = self.bounded_ally_life or journal["recovery"]["outcome"] in ("accepted", "accepted-effect-only")
        self._engine_result = {"verified": True, "players_before": self._pre_players,
                               "players_after": after_rows, "source": "recovery independent continuation"}
        self.turn += 1
        self.event("turn", turn=self.turn, **self._actor_fields(), control_mode="external",
                   selected_action={"kind": ("identified-ally-life" if self.bounded_ally_life else "identified-ally-cure" if self.bounded_ally_cure else "identified-self-cure") if accepted else "identified-wait",
                                    "ability_id": (5 if self.bounded_ally_life else 1) if accepted else None},
                   selected_target={"kind": "unit", "id": 7 if self.bounded_ally_life else 5 if self.bounded_ally_cure else self.owner["id"]} if accepted else None,
                   position_before=before, position_after={"x": after_row["x"], "y": after_row["y"]},
                   engine_result=self._engine_result, recovery=journal,
                   note=("bounded party recovery: guarded Wait and one independently joined next enemy"
                         if self.bounded_ally_cure or self.bounded_ally_life else "bounded recovery: guarded Wait and two independently joined later enemies"))
        self.state = RUNNING

    def _record_identified_turn(self, plan_kind, plan, dest_used, drove,
                                before, fail_log=None):
        """Finish an identified boundary turn and record it (C3).

        Shared by the identified-move and identified-wait paths: a latched
        STOP owns the exit (paused handoff), a failed drive without a stop
        is an unidentified UI (bounded, no recovery input — c2-live3
        lesson), and a turn event may only claim what the engine's own
        board state verified.
        """
        if not drove:
            if self._stop_check():
                # a latched STOP owns this exit: no turn event after the
                # stop record, hand the battle over here
                self._finish(PAUSED,
                             "STOP requested: battle left running for "
                             "manual play")
                return
            self._saw_unknown_modal = True
            self.event("note", **self._actor_fields(),
                       note=f"{plan_kind} drive failed without a stop "
                            "(menu shape did not answer the identified "
                            "legs): bounding run — battle left on the "
                            "open menu for manual play"
                            + (f" [last leg: {fail_log[-1]}]"
                               if fail_log else ""))
            self.state = RUNNING
            return
        if plan_kind == "identified-move":
            route_note = ("identified-move: cmd_cursor=Move and target "
                          "cursor read from RAM before input")
        else:
            route_note = (f"identified-wait: cmd cursor "
                          f"{plan['command_id']} read from RAM before input")
        sel_action = {"kind": plan_kind,
                      "command_id": plan["command_id"],
                      "dest": list(dest_used) if dest_used else None,
                      "from": plan["from"]}
        sel_target = None
        if dest_used is not None:
            sel_target = {"kind": "tile", "dest": list(dest_used),
                          "identified_from":
                              "RAM target cursor read before confirm"}
        deadline = time.time() + 20.0
        result_error = None
        while True:
            if self._stop_check():
                self._finish(PAUSED, "STOP requested: battle left running for manual play")
                return
            try:
                post = self.adapter.snapshot()
                self._engine_result = self.adapter.result(
                    self.owner, self._pre_players, post, plan_kind, dest_used)
                break
            except IdentityError as exc:
                result_error = str(exc)
                if time.time() >= deadline:
                    self._saw_unknown_modal = True
                    self.event("note", **self._actor_fields(),
                               note=f"engine result rejected: {result_error}; no action claimed")
                    self.state = RUNNING
                    return
                self.p.pump(2.0, "result-copy", sample_every=60.0,
                            stop_when=lambda _p: self._stop_check())
        # the Wait commit ends the turn: same wall-aware progress wait
        # as the route paths
        committed = self.p.wait_progress(
            seconds=min(150.0, max(10.0, self.wall_timeout -
                                   (time.time() - self.t0))),
            want_seeds=self._boundary_seed_count + 1, stop_check=self._stop_check)
        if not committed:
            # C1 rule: a latched STOP owns the exit — the wait returns
            # False on stop too, and a paused handoff must win over the
            # bounding note (no "battle left on the open menu" mislabel).
            if self._stop_check():
                self._finish(PAUSED,
                             "STOP requested: battle left running for "
                             "manual play")
                return
            # the identified commit shape did not close the turn (the
            # engine refused or the menu changed shape): bounding honestly,
            # with NO recovery input — recovery drives un-identified routes,
            # which the contract bans from a rejected/unidentified state.
            self._saw_unknown_modal = True
            self.event("note", **self._actor_fields(),
                       note=f"{plan_kind} commit shape produced no "
                            "sequencer progress: bounding run — battle "
                            "left on the open menu for manual play (no "
                            "recovery input: recovery routes are not "
                            "RAM-identified)")
            self.state = RUNNING
            return
        if self._stop_check():
            # stop landed inside the post-commit wait (C1 rule: no turn
            # event after the latched stop; hand the battle over here)
            self._finish(PAUSED,
                         "STOP requested: battle left running for "
                         "manual play")
            return
        # Report the actor's independently checked commit snapshot, rather
        # than a later enemy-phase read that can transiently wipe the record.
        row = next(r for r in self._engine_result["players_after"]
                   if key(r) == key(self.owner))
        after = {"x": row["x"], "y": row["y"]}
        if dest_used is not None:
            route_note += f"; full-party result verified at ({row['x']}, {row['y']})"
        self.turn += 1
        self.event("turn", turn=self.turn, **self._actor_fields(),
                   control_mode="external", selected_action=sel_action,
                   selected_target=sel_target,
                   position_before=before, position_after=after,
                   engine_result=self._engine_result,
                   next_actor=self._next_seed_actor(),
                   tactics=self._tactics_meta,
                   note=f"committed via {route_note}")
        self.state = RUNNING

    def _next_seed_actor(self):
        # Only independently decoded sequencer context names are reported.
        if not self.p.seeds:
            return None
        names = [u.get("name") for u in self.p.seeds[-1].get("ctx_units", [])
                 if u.get("off") == 0 and u.get("name")]
        matches = [r for r in self.s.receipt["roster"]["slots"]
                   if r.get("name_text") in names and r.get("live")]
        if len(matches) != 1:
            return None
        row = matches[0]
        return {"source": "sequencer actor context", "name": row["name_text"],
                "id": row["id"], "job": row["job"], "side_bit": row["side_bit"]}

    def _finish(self, state, reason):
        self.state = state
        self._terminal_reason = reason
        # a3-natural4 lesson: every bounded stop needs a terminal frame,
        # otherwise the post-silence engine state is unknowable and the
        # bound's honesty cannot be audited
        shot_name = None
        try:
            shot_name = f"terminal-{state}.png"
            self.s.screenshot(os.path.join(
                os.path.dirname(self.events_path), shot_name))
        except Exception:
            shot_name = None
        note = reason + (f" [terminal screenshot: {shot_name}]" if shot_name
                         else " [terminal screenshot failed]")
        if self._stop_requested_t is not None:
            note += " [stop was latched; see input-log.jsonl for latency]"
        self.event("stop", note=note)
        try:
            self._input_log.close()
        except Exception:
            pass
        # release/restore: breakpoints removed, no key writes owned (the
        # press path re-writes the key-enable scratch before each press).
        # Paused runs MUST actually detach: Astra's review showed a stop
        # that only renamed the automation end leaves the player's battle
        # wedged with our breakpoints armed.
        try:
            self.p.disarm()
        except Exception:
            pass
