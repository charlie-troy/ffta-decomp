"""A3 minimal autonomous battle runtime.

Built directly on the A2.5 frozen contract (docs/player-ai-control.md,
"A2.5 result") and the Probe transport from tools/probe_control_handoff.py:

- States: idle -> running -> (takeover -> running)* -> completed | stalled |
  connection_lost | paused. The runtime stops issuing input after completion,
  a bounded stop, connection loss, or an unknown modal. A STOP request pauses
  the battle for manual resume: input stops immediately, breakpoints are
  disarmed, and (with the CLI's --on-stop handoff) the emulator is left
  running so the player can continue from the live screen.
- Boundary detection uses the value-agnostic frozen-CT menu signature
  (`player_menu_frozen`): a re-opened menu freezes its owner's roster CT at
  any value. The only proven commit shape is the full route DOWN DOWN A A at
  frames=5; single keys are refuted (docs/dead-ends.md DE-020).
- In `retail-ai` mode the runtime never overrides engine choices: enemy turns
  run with retail AI and the runtime supplies the one proven engine-legal
  player action (Wait) at each player menu boundary. Non-Wait choices need
  A5's chooser and are out of scope here.
- Turn events append to outputs/autobattle/<run-id>/events.jsonl. Unknown
  fields are null, never inferred labels.
- Stall detection is bounded by seed silence plus a wall-clock timeout.

No ROM code is patched: the Probe owns RAM breakpoints only, removed at exit.
"""

from __future__ import annotations

import json
import os
import time

from probe_control_handoff import Probe

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
}


class BattleRuntime:
    # roster tile offsets (A2.5 contract, probe_control_handoff constants)
    _TILE_X = 0xF6
    _TILE_Y = 0xF7
    # B is pure menu-back navigation on the key-poll channel: it can never
    # commit a choice, so bounded B-escape cycles are recovery, not tactical
    # clicks (the A3 no-tactical-clicks contract stays intact)
    B_MASK = 0x02
    B_RECOVERY_LIMIT = 3      # escape cycles before declaring an unknown modal
    B_SETTLE_SECONDS = 60.0   # post-redrive commit lands within ~40 s (recorded)
    """Drive one battle from the verified fixture with bounded stopping."""

    def __init__(self, session, scenario, run_id, out_dir,
                 mode="retail-ai", stall_seed_seconds=150.0,
                 wall_timeout=600.0, max_turns=None, verbose=True):
        self.s = session
        self.p = Probe(session, verbose=verbose)
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
        self.t0 = time.time()
        self._last_seed_count = 0
        self._last_seed_t = time.time()
        self._terminal_reason = None
        self._saw_unknown_modal = False
        self._dead_polls = 0  # debounce: roster copies can read 0 transiently
        self._dead_seed_mark = 0  # seed count when the current dead streak began
        self._dead_grace_t = None  # wall time the defeat debounce first held
        self._stop_requested = False  # Astra 2026-09-17: checked INSIDE long
        #                              waits, so a pause ends waits promptly

    def _stop_check(self):
        """Poll the STOP file cheaply; latches the first sighting."""
        if not self._stop_requested and os.path.exists(self.stop_file):
            self._stop_requested = True
        return self._stop_requested

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
            if k in rec:
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
        from probe_control_handoff import ROSTER, STRIDE
        from fixture_guard import (BATTLE_STRUCT, COUNT_OFF, OFF_NAME,
                                   decode_ram_name, u16, u8)
        count = u16(g, BATTLE_STRUCT + COUNT_OFF)
        rom = self.s.read_rom_bytes()
        names = []
        for i in range(min(count, 8)):
            base = ROSTER + STRIDE * i
            ptr = u16(g, base + OFF_NAME) | (u16(g, base + OFF_NAME + 2) << 16)
            names.append(decode_ram_name(g, ptr, rom=rom) if ptr else None)
        expect = self.scenario.get("guard_expectations", {})
        ok_count = count == expect.get("struct_count", count)
        marche_ok = "Marche" in [n for n in names if n]
        slot0_ok = bool(names) and names[0] is not None and \
            names[0] != expect.get("player_name_text", "Marche")
        self.event("guard", note=f"count={count} names={names}",
                   control_mode=None)
        return ok_count and marche_ok and slot0_ok

    # -- state classification ---------------------------------------------
    def _all_cts_zero(self):
        cts = self.p.cts()
        return all(c == 0 for c in cts)

    def _classify(self):
        """Return the next state from live engine observations."""
        if self._saw_unknown_modal:
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
        if self._marche_dead():
            self._dead_polls += 1
            if len(self.p.seeds) > self._dead_seed_mark:
                self._dead_polls = 0  # traffic during the wipe: copy, not death
            self._dead_seed_mark = len(self.p.seeds)
        else:
            self._dead_polls = 0
            self._dead_seed_mark = len(self.p.seeds)
            self._dead_grace_t = None
        # a3-natural1 lesson: after Marche is defeated the battle still ends
        # naturally (defeat animation -> results screen) ~30 s later. Stopping
        # the run at the debounce pre-empted that conclusion, so a held defeat
        # suppresses takeover (menus no longer belong to him) and the stall
        # bound, but still lets the engine's own end classify the run below.
        # Only bounds may end it while the conclusion has not arrived.
        in_grace = self._dead_polls >= 3
        if in_grace and self._dead_grace_t is None:
            self._dead_grace_t = time.time()
            self.event("note", actor="Marche", actor_slot=6,
                       note="player defeat held 3 polls with seed silence; "
                            "suppressing takeover until battle end")
        # completion: the contract's battle-end shape — all CTs zero, seed
        # silence, roster still allocated (not torn down), router idle
        if (self._all_cts_zero() and quiet >= 45.0 and not torn
                and self._last_seed_count > 0):
            return COMPLETED
        if torn and quiet >= 45.0:
            return COMPLETED
        # Excluded when the whole CT vector is zero: the results screen parks
        # every CT at a stable 0 (run 20 end shape), which is also a stable
        # player CT — driving there would send a route into a non-battle UI.
        # The zero-vector guard is RE-evaluated after the (slow, 9 s) frozen
        # check: the battle end can transition charging -> results INSIDE the
        # check's stability window, and a guard evaluated before the check
        # would be stale — the 2026-09-17 victory-path wedge (a drive into
        # the results screen, bounded by B-recovery) was exactly that race.
        if (not in_grace and self.p.player_menu_frozen(2)
                and not self._all_cts_zero()):
            return TAKEOVER
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
        self.event("start", control_mode=self.mode)
        try:
            while True:
                # latched stop (seen inside a wait or recovery) exits before
                # any further classification or input (Astra 2026-09-17:
                # "input stops immediately" must include mid-wait)
                if self._stop_requested or os.path.exists(self.stop_file):
                    # manual takeover request: stop OUR input now and leave
                    # the battle live. `takeover` (the driven boundary state)
                    # is automation-owned; `paused` is the real handoff to
                    # the player — no further input, breakpoints disarmed,
                    # emulator survival decided by the CLI's --on-stop.
                    self._finish(PAUSED,
                                 "STOP requested: battle left running for "
                                 "manual play")
                    break
                self.p.pump(3.0, "runtime", sample_every=60.0, tick=3.0)
                nxt = self._classify()
                if nxt == TAKEOVER:
                    self._drive_player_boundary()
                elif nxt == COMPLETED:
                    self._finish(COMPLETED, "battle end signature held")
                    break
                elif nxt == STALLED:
                    reason = ("player unit defeated (hp block zeroed); "
                              "battle end did not arrive within budget"
                              if self._marche_dead()
                              else "no-progress bound reached")
                    self._finish(STALLED, reason)
                    break
        except (OSError, ConnectionError) as exc:
            self.state = CONNECTION_LOST
            self._finish(CONNECTION_LOST, f"transport lost: {exc}")
        return self.state

    def _marche_pos(self):
        from probe_control_handoff import ROSTER, STRIDE, u8
        ps = self.p.player_slot()
        if ps is None:
            return None
        base = ROSTER + STRIDE * ps
        return {"x": u8(self.g, base + self._TILE_X),
                "y": u8(self.g, base + self._TILE_Y)}

    def _marche_dead(self):
        """True when the tracked player record lost its HP block.

        a3-full1 evidence: Wait-only never attacks or heals; once Marche is
        defeated his roster tile/hp read 0 while the engine keeps running
        (the router keeps serving the remaining units). The unit can no
        longer act, so every menu the runtime sees from then on belongs to
        someone else — driving there is a partial route into unknown UI.
        """
        from probe_control_handoff import ROSTER, STRIDE, u16
        ps = self.p.player_slot()
        if ps is None:
            return False
        base = ROSTER + STRIDE * ps
        return u16(self.g, base + 0x18) == 0 and u16(self.g, base + 0x1A) == 0

    def _effect_diff(self, before, after):
        """Engine-observed deltas between two effect snapshots.

        Diffs mp and tg (engine-recorded recent-target ids) alongside hp/ct/
        tile: Astra 2026-09-17 — CT-only deltas cannot distinguish a
        committed Wait from a real command, so a non-Wait claim must ride an
        actor-specific field (the actor's MP cost and/or the engine's own
        target record).
        """
        if before is None or after is None:
            return None
        b = {r["slot"]: r for r in before}
        deltas = []
        for r in after:
            old = b.get(r["slot"])
            if old is None:
                deltas.append({"slot": r["slot"], "new": r})
                continue
            changed = {k: [old[k], r[k]] for k in ("hp", "ct", "mp", "tg", "x", "y")
                       if old[k] != r[k]}
            if changed:
                deltas.append({"slot": r["slot"], **changed})
        return deltas

    def _decode_target(self, after):
        """Engine-recorded recent-target ids (+0xE7) for the player record.

        include/ffta.h / unit-struct.md: action resolution packs the two
        most recent distinct targets as two 4-bit unit ids. When the player
        actor's field is nonzero after a commit, that is the engine's own
        target evidence — decoded into selected_target (null otherwise;
        unknown fields stay null, never inferred).
        """
        if not after:
            return None
        ps = self.p.player_slot()
        for r in after:
            if r["slot"] == ps and r.get("tg", 0):
                # packed pair of 4-bit unit ids; any nonzero byte is the
                # engine's own record (0 would mean no recent targets)
                return {"source": "engine-recent-target-ids",
                        "unit_ids": [r["tg"] >> 4, r["tg"] & 0xF]}
        return None

    def _drive_player_boundary(self):
        prev = self.state
        self.state = TAKEOVER
        before = self._marche_pos() or {"x": None, "y": None}
        shot = None
        try:
            shot = self.s.screenshot(os.path.join(
                os.path.dirname(self.events_path),
                f"boundary-turn{self.turn + 1}.png"))
        except Exception:
            shot = None
        self.event("boundary", actor="Marche", actor_slot=6,
                   control_mode="external", position_before=before,
                   note=shot)
        # Deliberate selection: when live engine evidence supports it, the
        # chooser picks the action-submenu route instead of the fixed
        # Wait-shape route. Whatever the menu resolves to, the commit's
        # meaning is recorded as an engine-side effect diff below — never
        # an assumed label.
        before_effects = None
        try:
            before_effects = self.p.effect_snapshot()
        except Exception:
            before_effects = None
        choice = None
        try:
            choice = self.p.choose_non_wait()
        except Exception:
            choice = None
        if choice is not None:
            self.p.drive(f"a3-{self.run_id}", route=choice["route"])
            route_note = "deliberate action-submenu route (chooser)"
        else:
            # The only proven commit shape (A2.5 contract); never leave a
            # menu undriven.
            self.p.drive(f"a3-{self.run_id}")
            route_note = "fixed proven route (chooser declined: no ability/tile evidence)"
        # wall-aware progress wait; 150 s covers the healthiest recorded
        # boundary gap (92.9 s in a3-natural3) with margin — the original
        # 90 s bound sat inside natural late-game pacing and bounded a live
        # run mid-charge
        remaining = max(10.0, self.wall_timeout - (time.time() - self.t0))
        committed = self.p.wait_progress(seconds=min(150.0, remaining),
                                         min_new_seeds=1,
                                         stop_check=self._stop_check)
        # Honest labels only (roadmap rule: unknown fields must be null, not
        # inferred). The route kind records WHAT was deliberately selected;
        # the effect diff records what the engine actually did. The decoded
        # command id/name stays null — that mapping is not built yet.
        note = f"committed via {route_note}; effect diff follows"
        sel_action = None
        if choice is not None:
            sel_action = {"kind": "deliberate-non-wait-route",
                          "command_id": None,
                          "route": "action-submenu"}
        if not committed:
            # a3-natural5 evidence: the post-Move re-opened menu can present
            # a different UI shape (a submenu) that the plain route cannot
            # commit — presses land, nothing commits, and the engine idles
            # awaiting input. B backs out of submenus without committing,
            # so bounded B-escape cycles plus a re-drive are recovery.
            # After B_RECOVERY_LIMIT fruitless cycles the shape is a true
            # unknown modal and the run bounds honestly (DE-020).
            recovered = False
            for cycle in range(1, self.B_RECOVERY_LIMIT + 1):
                self.event("note", note=f"no sequencer progress after route: "
                            f"B-recovery cycle {cycle}/{self.B_RECOVERY_LIMIT} "
                            f"(backing out of a possible submenu; no tactical "
                            f"input)")
                # exactly one B: from a submenu it returns to the parent
                # command menu; a second B would close the parent entirely
                # and strand the unit on the map (proved offline: the first
                # submenu run drove B twice and the re-drive landed on a
                # closed menu with zero progress)
                self.p.press(self.B_MASK, tag=f"a3-{self.run_id}:B{cycle}")
                # the proven route then re-drives the parent menu. Without
                # the re-drive the backed-out menu just sits awaiting input.
                self.p.drive(f"a3-{self.run_id}:rec{cycle}")
                remaining = max(10.0, self.wall_timeout - (time.time() - self.t0))
                if self._stop_check():
                    break  # a pause request ends recovery immediately (Astra)
                if self.p.wait_progress(
                        seconds=min(self.B_SETTLE_SECONDS, remaining),
                        min_new_seeds=1,
                        stop_check=self._stop_check):
                    recovered = True
                    break
            if not recovered:
                # strongest unknown-modal signal without a frame; bound the
                # run instead of pressing further (DE-020)
                self._saw_unknown_modal = True
                after = self._marche_pos() or {"x": None, "y": None}
                self.event("note", turn=self.turn, actor="Marche",
                           actor_slot=6, control_mode="external",
                           position_before=before, position_after=after,
                           note="route and B-recovery produced no sequencer "
                                "progress: bounding run (committed action "
                                "not decoded)")
                self.state = RUNNING
                return
            note = "committed after B-recovery (plain route); action not decoded"
            sel_action = None  # recovery re-drives the plain route, not the chooser route
        after = self._marche_pos() or {"x": None, "y": None}
        # Astra 2026-09-17: the first seed can precede the committed action's
        # execution — an after-snapshot there records only CT churn and a
        # Wait would be mislabeled non-Wait. The commit's evidence window is
        # the action's EXECUTION: charge ~2 s, then one ~3 s pump. Only
        # actor-specific deltas (mp cost / engine-recorded target / hp /
        # tile) extend it; CT-only change does not.
        try:
            after_effects = self.p.effect_snapshot()
        except Exception:
            after_effects = None
        effect = self._effect_diff(before_effects, after_effects)
        actor_specific = effect is not None and any(
            k in d for d in effect for k in ("mp", "tg", "hp", "x", "y"))
        if not actor_specific:
            try:
                self.p.wait_progress(seconds=5.0, min_new_seeds=9999999)
            except Exception:
                pass
            try:
                after_effects = self.p.effect_snapshot()
            except Exception:
                after_effects = None
            effect = self._effect_diff(before_effects, after_effects)
            actor_specific = effect is not None and any(
                k in d for d in effect for k in ("mp", "tg", "hp", "x", "y"))
        if effect:
            note += f"; engine deltas: {json.dumps(effect)}"
            if not actor_specific:
                note += ("; ct-only (execution window may not have closed: "
                         "action not identified)")
        else:
            note += "; no engine deltas decoded (action not decoded yet)"
        self.turn += 1
        sel_target = None
        if sel_action is not None:
            sel_target = self._decode_target(after_effects)
        self.event("turn", turn=self.turn, actor="Marche", actor_slot=6,
                   control_mode="external", selected_action=sel_action,
                   selected_target=sel_target,
                   position_before=before, position_after=after,
                   note=note)
        self.state = prev if prev in (RUNNING,) else RUNNING

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
        self.event("stop", note=note)
        # release/restore: breakpoints removed, no key writes owned (the
        # press path re-writes the key-enable scratch before each press).
        # Paused runs MUST actually detach: Astra's review showed a stop
        # that only renamed the automation end leaves the player's battle
        # wedged with our breakpoints armed.
        try:
            self.p.disarm()
        except Exception:
            pass
