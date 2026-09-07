# Customizable auto-battle roadmap

Updated 2026-09-06. Planning baseline: `f9d9493`, clean worktree before this documentation change.

## Product outcome

Charlie chooses jobs, equipment, abilities, and each character's tactics, then lets battles run autonomously at an adjustable speed. Manual takeover remains available. Success means less repetitive battle input while preserving character building, leveling, and the game's normal combat rules.

First release scope: Windows mGBA companion plus guarded ROM patches where needed. This is a proposed implementation default, not a claim of emulator or hardware portability. Keep strategy evaluation separate from emulator transport so a later ROM-native implementation is possible. Do not automate equipment, job changes, mission selection, or spending as part of battle automation.

## What exists and what is still missing

| Capability | Evidence and limit |
|---|---|
| Matching decomp/toolchain | Repository reports 173 functions / 9,888 bytes and a byte-identical rebuild. Full rebuild was not rerun for this roadmap. |
| Safe profile compiler | `tools/ai_strategy.py`: schema v1, ordered selectors, ability/job priorities, status gates, preview/apply, exact base-ROM guard, atomic output. These are shared table/code changes, not individual character assignments. |
| Deterministic controls | `tools/ai_targeting.py` and `tools/ai_action.py` remove specific ordering/action-selection draws. This does not remove damage RNG or guarantee optimal tactics. |
| Current regression evidence | Fresh run: `python tools/validate_ai_strategy.py baserom.gba` passed 9/9; aggressive changes 435 bytes, deterministic-actions 460 bytes. SHA1 verified as `4ac05441f4de70a4ec3dd932116346c61b8783d9`. |
| AI internals | Candidate construction, sign-gated priority ordering, help/harm pools, evaluator and turn phases are documented and probed. Impact magnitude is not a retail ranking key. Do not revive the old magnitude-based interpretation. |
| Live scenario | A frozen snowball enemy turn is reproducible. It cannot demonstrate normal approach movement, full-party automation, or contrasting profiles across complete battles. |
| Normal-battle access | Windows mGBA navigation and Lua/UIA helpers exist. Project log records reaching an in-game field scene with a local endgame save; a repeatable normal-battle fixture remains open. |
| Missing product pieces | Player-control handoff, per-character runtime assignment, conditional tactics, resource/movement policy, full-battle recovery, measured acceleration, usable configuration workflow. |

Read `CLAUDE.md`, the current section of `docs/project-log.md`, `docs/dead-ends.md`, and the task-specific files below. Historical entries are evidence, not an instruction to reopen completed investigations.

## Milestones and order

1. **M1 — Hands-off battle:** capture a normal battle, enable AI for player units, finish a battle with takeover and stall handling.
2. **M2 — My characters, my tactics:** independent assignments and ordered conditional rules, with observable reasons for each decision.
3. **M3 — Faster, usable play:** measured acceleration, an editor/launcher, and a small complete-battle acceptance suite.

Critical path: A1 → A2 → A3 → A4 → A5 → A6/A7 → A9. A8 can run after A3 independently of policy research. A10 follows A5's stable contract. Do not hold M1 hostage to solving every movement or evaluator branch.

## Agent work packets

Each packet ends with one reviewable deliverable, a reproducible check, and a project-log entry. Proposed filenames below are new files unless identified as existing. Research packets must produce evidence and a decision before an implementation packet is commissioned; unknown ROM hooks must never be filled in by guesswork.

### A1 — Capture a normal-battle fixture (P0, prerequisite)

Read existing `tools/steer_mgba.py`, `tools/lua_drive.lua`, `tools/uia_lua.ps1`, `tools/scenario_capture.py`, and the 2026-09-06 log entries.

- [x] Consolidate the successful Windows navigation into `tools/capture_normal_battle.py`; reuse a proven transport rather than rewriting the debugger.
- [x] Preserve the current battery save and operate on a working copy. Record save provenance without distributing save or ROM bytes.
- [x] Capture a battle-start state containing player units, several enemies, and an actual out-of-range melee approach opportunity.
- [x] Write `docs/battle-fixtures.md` and a metadata-only `configs/battle-scenarios/normal-battle.json`: scenario id, ROM hash, emulator version, local state path/hash, initial roster, replay steps, and expected first observable events.
- [x] Reload twice and show the same initial state and an actual enemy tile transition followed by a legal action. Distinguish animation/live coordinates from the phase-8 canonical restore.

Status (2026-09-07): all A1 boxes done. Two identical runs from `engage.ss0` settle at the same battle-start (1.7% grid diff = animation noise). Enemy turn observed hands-off: Schneider banner → red move tile → tile transition → phoenix cutscene → "55" damage popup. Fixture chain + constraints documented in `docs/battle-fixtures.md`.

Done: another agent can load this fixture without navigating the intro. If navigation fails after two materially different approaches, return screenshots, observed state, and a precise blocker; do not spend another session teleporting snowball units.

### A2 — Find the player-to-AI handoff (P0, research gate)

Depends on A1. Read `docs/turn-order.md`, `docs/ai-findings.md`, and `tools/trace_turn_march.py`.

- [ ] Add `tools/probe_player_ai_control.py` to compare a normal player turn with an enemy turn at controller dispatch.
- [ ] Identify the control decision separately from team membership, Charm/Confuse, turn order, and targeting allegiance.
- [ ] Make a reversible runtime experiment that sends one player unit through a complete AI move/action/end-turn cycle.
- [ ] Write `docs/player-ai-control.md` with exact hook bytes/addresses, preconditions, restoration procedure, and before/after traces.
- [ ] Verify allies remain allies, the next unit gets its turn, enemies retain their original behavior, and manual control can be restored at a safe turn boundary.

Done: a causal control experiment, not a side-bit flip that makes the party hostile. Orchestrator reviews this evidence before A3. If no safe handoff exists, compare sequencer delegation with external legal-action selection in a separate design decision; do not silently substitute menu macros.

### A3 — Minimal autonomous battle runner (P0)

Depends on reviewed A2. Create `tools/autobattle_runtime.py`, `tools/run_autobattle.py`, and `tools/validate_autobattle_runtime.py`; reuse the existing emulator transport.

- [ ] Expose CLI `run_autobattle.py --rom PATH --scenario PATH --mode retail-ai`; default to paused until the fixture and ROM guards pass.
- [ ] Implement explicit idle/running/takeover/completed/stalled states using A2's verified control boundary. Stop issuing input after completion, takeover, connection loss, or an unknown modal.
- [ ] Append turn events to `outputs/autobattle/<run-id>/events.jsonl`: scenario, turn, actor, control mode, selected action/target, position before/after, and reason for stopping. Unknown fields must be null, not inferred labels.
- [ ] Bound stall detection by no-progress frames plus a wall-clock timeout; release held keys and restore temporary hooks on exit where the connection remains available.
- [ ] Validate disconnect, repeated start/stop, unknown-dialog, and takeover paths using recorded transport responses; then finish one normal battle with no tactical clicks.

Done: one uninterrupted normal battle plus a separate mid-battle takeover demonstration. Preserve the user's save. This milestone uses retail AI and makes no claim of sophisticated custom strategy yet.

### A4 — Per-character assignment feasibility (P1, research gate)

Depends on A3. Existing schema-v1 profiles remain supported unchanged.

- [ ] Add `tools/probe_strategy_scope.py` and `docs/strategy-runtime-scope.md` to identify stable party identity across turns, reloads, and battle-local slot reuse.
- [ ] Prove a player-only policy interception point; demonstrate different behavior for two same-job allies while an enemy of that job remains unaffected.
- [ ] Select runtime lookup or another proven method. If shared table values are temporarily changed, prove restoration on every exit and no contamination of enemy turns before accepting that architecture.
- [ ] Specify precedence: explicit character assignment, then job default, then party default, then retail behavior.

Done: identity and isolation evidence, with the actual runtime adapter contract recorded. Do not add persistent save fields or promise native-console support at this stage.

### A5 — Ordered tactical rules and decision receipts (P1)

Depends on A4. Create `tools/tactics_policy.py`, `tools/validate_tactics_policy.py`, `configs/tactics/`, and `docs/tactics-policy.md`. Extend the runner through A4's reviewed adapter; keep the existing global ROM profile compiler separate.

Proposed pure interface: `choose_action(snapshot: dict, policy: dict) -> dict | None`. The adapter supplies an actor id and only engine-legal candidate actions, each with an action id, target id, actor/target HP and MP, cost, relation, and verified status data. Missing required facts make a rule ineligible. Return a candidate id plus matched rule id/reason, or `None` for retail fallback. Freeze the exact JSON schema in this packet before A6/A7/A10 start.

- [ ] Implement ordered first-matching-eligible rules, enabled flags, explicit fallback, and deterministic tie handling. Reject unknown keys and invalid thresholds.
- [ ] Support only verified initial predicates: self/ally/enemy, HP percentage threshold, known status present/absent, named/identified available ability, and remaining MP after cost.
- [ ] Add contrasting fixtures: wounded ally vs healthy ally, insufficient MP, no matching ability, duplicate ability names, equal-priority targets, and no legal action. For each fixture assert the selected candidate and rule reason.
- [ ] Connect policy choices through the verified adapter and show two same-job characters follow different rules in the normal battle.

Done: reproducible per-character conditional tactics, with unsupported predicates rejected. Engine legality always wins over policy preference. Policy presets change decisions, not damage, stats, AP, or reward tables.

### A6 — Resource and recovery tactics (P1)

Depends on A5. Modify `tools/tactics_policy.py` and its validator; add a healer preset under `configs/tactics/`.

- [ ] Trace missing item-count/MP consumers only as required by concrete rules; document the evidence in `docs/tactics-policy.md`.
- [ ] Add heal-under-threshold, revive-before-attack where a legal revive candidate exists, MP reserve, and never-use-item rules. Consumables default to disabled.
- [ ] Test exact threshold boundaries, zero max HP, KO vs living targets, insufficient MP, no revive ability, and the last consumable.
- [ ] Replay a wounded-party fixture and compare its chosen actions to a damage-focused policy.

Done: the rule changes the executed action, consumes the expected resource, and explains fallback when unavailable. Do not invent a heal/revive candidate that the engine rejected.

### A7 — Movement tactics (P1, bounded research then implementation)

Depends on A1/A5. Reuse `tools/trace_turn_march.py`; create `tools/probe_movement_policy.py` and `docs/movement-policy.md`.

- [ ] Observe a real approach walk, locate candidate destination selection, and distinguish reachability, placement rendering, live record state, and turn-end synchronization.
- [ ] Prove one control at a time: approach-to-attack, hold position, then preferred range if the candidate interface supports it. Add only proven controls to A5's schema.
- [ ] Test occupied tiles, height differences, blocked paths, Immobilize, unreachable enemies, and no legal attack from the selected tile.
- [ ] Record action destination and actual committed destination over two turns; prove a failed preference falls back legally rather than hanging.

Done: at least approach and hold produce contrasting legal movement on the same fixture. Kiting, hazard avoidance, and formation behavior remain later work unless supported by this evidence.

### A8 — Adjustable battle speed (P1, independent after A3)

Modify `tools/run_autobattle.py`; create `docs/autobattle-speed.md` and extend runtime validation.

- [ ] Inspect the installed emulator's supported acceleration mechanism; expose normal speed and a verified accelerated setting without changing CT, damage, or game timers in ROM.
- [ ] Keep takeover responsive and restore the previous speed on stop where possible.
- [ ] Measure wall-clock duration, emulated frames, input count, and outcome from the same starting state at both speeds; repeat three times per setting.
- [ ] Verify no missed turn transitions, modal overrun, or additional tactical input is required. Publish actual speedup, including any tracing overhead.

Done: measurable battle-time reduction with equivalent game progression. Animation-skipping ROM patches are deferred until emulator acceleration is measured and insufficient.

### A9 — Complete-battle acceptance matrix (P1)

Depends on A6/A7/A8. Extend existing `tools/scenario_capture.py` or add `tools/validate_autobattle_scenarios.py` if its debugger assumptions are incompatible; avoid a second parallel harness without justification.

- [ ] Add metadata-only fixtures covering melee approach, mixed healer/ranged party, and a law/status-constrained battle. Local states remain untracked.
- [ ] Run retail AI, damage-focused, and preservation-focused policies from the same fixture/seed. Capture actions, movement, resources, KO count, turns, manual interventions, stalls, and duration.
- [ ] Require three consecutive completed runs per selected fixture, no unexplained hangs, and deliberate policy divergence where the fixture makes its rule applicable. Do not require a win regardless of party strength.
- [ ] Test manual takeover, defeat, result screen, and an unexpected prompt. Stop at results; world-map automation is outside scope.
- [ ] Run `python tools/validate_all.py baserom.gba` before integrating ROM changes; extend strict attribution for every new patch surface.

Done: evidence identifies exactly which scenarios passed and which remain unsupported. A synthetic policy test or snowball trace cannot substitute for complete-battle results.

### A10 — Configuration and launch workflow (P2, after A5)

Create a local editor in `tools/tactics_editor/` only after the policy schema and runner interface are stable.

- [ ] Let the player choose a roster member, assign a preset, reorder/edit rules, preview validation errors, and save/export the same JSON the runner consumes.
- [ ] Provide Start, Pause/Take over, speed selection, current matched rule, and a clear stopped/stalled reason. Keep addresses and debugger details in diagnostics.
- [ ] Ship three tested presets: damage-focused, healer, and resource preservation, using supported controls only.
- [ ] Verify an edit/export/reload round trip and the entire configure → start → takeover → resume → results workflow in the actual UI.

Done: Charlie can configure and launch without editing Python or navigating a debugger. Review desktop screenshots and runtime behavior before calling the workflow usable.

## Delegation and cost controls

- Give cheaper implementation agents one packet, its prerequisite evidence, and its owned files. They should not read the entire multi-thousand-line project log or undertake open-ended reverse engineering.
- Routine agents fit A3 after hook approval, A5's pure evaluator, A8 after API discovery, and A10 after schema freeze. The orchestrator owns A2/A4 architecture decisions and reviews A7's causal evidence. Escalate uncertain semantics; do not buy repeated speculative experiments.
- A1/A2 share one emulator session and run serially. Pure evaluator/editor work can run independently once interfaces are frozen. Never let two agents attach to or mutate the same mGBA process/save.
- Limit a research slice to one hypothesis and two distinct experiments. Return a useful negative result with exact evidence if unresolved; the orchestrator chooses the next slice.
- Require the return format: commit/base, files changed, claim, command/evidence, observed result, limitations, and next dependency unlocked. Report historical checks separately from checks run now.
- Integrate one packet at a time. Review behavior and patch attribution; run relevant domain checks for each change and the complete release gate for an integrated ROM release. Do not replace meaningful execution evidence with tests that restate the implementation.

Suggested dispatch prompt:

> Implement packet [ID] in docs/auto-battle-roadmap.md only. Read CLAUDE.md, docs/dead-ends.md, and the packet's named source files. Verify the checkout and prerequisite evidence first. Preserve unrelated work and local saves. Do not expand scope or infer unproven ROM semantics. Deliver the packet's tests/evidence and a project-log entry. If a dependency is missing, report the exact blocker and the smallest evidence-producing next step.

## Deferred work

Map seams/metatile naming, further matching for its own sake, mission-table expansion, automated grinding outside battles, native hardware packaging, advanced formation tactics, and a polished editor before the runtime contract. Reopen these only when they directly unblock the milestones above.
