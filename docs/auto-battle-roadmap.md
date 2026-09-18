# Customizable auto-battle roadmap

Updated 2026-09-17. Planning baseline: `398bdc0`. Current acceptance status
is maintained here; dated discoveries remain in `docs/project-log.md`.
For every auto-battle implementation or completion claim, follow
[Worker acceptance contract](autobattle-worker-contract.md). It defines the
checks needed to finish a packet and continue without orchestrator approval.
Earlier “closed” log entries are historical claims, not dependency clearance.

## Product outcome

Charlie chooses jobs, equipment, abilities, and each character's tactics, then lets battles run autonomously at an adjustable speed. Manual takeover remains available. Success means less repetitive battle input while preserving character building, leveling, and the game's normal combat rules.

First release scope: Windows mGBA companion plus guarded ROM patches where needed. This is a proposed implementation default, not a claim of emulator or hardware portability. Keep strategy evaluation separate from emulator transport so a later ROM-native implementation is possible. Do not automate equipment, job changes, mission selection, or spending as part of battle automation.

## What exists and what is still missing

| Capability | Evidence and limit |
|---|---|
| Matching decomp/toolchain | Repository reports 173 functions / 9,888 bytes and a byte-identical rebuild. Full rebuild was not rerun for this roadmap. |
| Safe profile compiler | `tools/ai_strategy.py`: schema v1, ordered selectors, ability/job priorities, status gates, preview/apply, exact base-ROM guard, atomic output. These are shared table/code changes, not individual character assignments. |
| Deterministic controls | `tools/ai_targeting.py` and `tools/ai_action.py` remove specific ordering/action-selection draws. This does not remove damage RNG or guarantee optimal tactics. |
| Current regression evidence | Historical run (2026-09-06): `python tools/validate_ai_strategy.py baserom.gba` passed 9/9; aggressive changes 435 bytes, deterministic-actions 460 bytes. SHA1 verified as `4ac05441f4de70a4ec3dd932116346c61b8783d9`. |
| AI internals | Candidate construction, sign-gated priority ordering, help/harm pools, evaluator and turn phases are documented and probed. Impact magnitude is not a retail ranking key. Do not revive the old magnitude-based interpretation. |
| Live scenario | A frozen snowball enemy turn is reproducible. It cannot demonstrate normal approach movement, full-party automation, or contrasting profiles across complete battles. |
| Normal-battle access | A1 captured a repeatable encounter and enemy movement/action (`123ea91`). A2 introduced additional fixture variants; their identity, roster metadata, and boot guards need reconciliation before more causal experiments (A2.4a). |
| Missing product pieces | Player-control handoff, per-character runtime assignment, conditional tactics, resource/movement policy, full-battle recovery, measured acceleration, usable configuration workflow. |

Read `CLAUDE.md`, the current section of `docs/project-log.md`, `docs/dead-ends.md`, and the task-specific files below. Historical entries are evidence, not an instruction to reopen completed investigations.

## Milestones and order

1. **M1 — Hands-off battle:** capture a normal battle, enable AI for player units, finish a battle with takeover and stall handling.
2. **M2 — My characters, my tactics:** independent assignments and ordered conditional rules, with observable reasons for each decision.
3. **M3 — Faster, usable play:** measured acceleration, an editor/launcher, and a small complete-battle acceptance suite.

Critical path: A1 → A2 → A3 → A4 → A5 → A6/A7 → A9. A8 can run after A3 independently of policy research. A10 follows A5's stable contract. Do not hold M1 hostage to solving every movement or evaluator branch.

## Worker start and dispatch order

| Order | Packet | Current status | Completion unlocks |
|---|---|---|---|
| 1 | C1 cancellation and handoff | 11/11 acceptance criteria PASS per `docs/receipts/autobattle/C1.json` (2026-09-17, round-4 update): all six STOP-timing rows, both CLI cleanup paths (leave-running + kill via real `__exit__`), guard-failure receipt, disconnect, the 2 s latency bound (measured 0.19–1.2 s), and the manual-command row closed with an agent-driven player input proof | C2 |
| 2 | C2 validated player action | Active: snapshot plausibility + validated target decode landed; the identified-candidate selector and the identity→selection→execution receipt remain | C3 |
| 3 | C3 integration and acceptance | Blocked on C1/C2 | Close A2.5/A3; start A4 or A8 |
| Later | A4–A10 | Existing product scope retained | Follow declared dependencies |

A1 and A2.4a supplied normal-battle fixtures. A2.4b supplied useful negative
control results. A3 has an unattended failed-encounter result (`a3-natural6`),
and the CLI now preserves its process on pause. These are reusable evidence,
not proof of player action selection or complete cancellation behavior.

**Default assignment:** complete C1 → C2 → C3, in that order, within an
ongoing request to continue auto-battle work. Read the contract and the current
packet only; load linked research references when that packet needs them.
A passing packet unlocks the next packet automatically. No additional human
or orchestrator sign-off is required for scoped, reversible implementation,
local tests, evidence capture, or commit of owned files.

The initial implementation path is external engine-legal player action
selection through the existing Windows mGBA transport. Workers may decode the
minimum menu/action boundary and build a small selector to prove it. This is
not a claim that the player's turn uses retail AI. Persistent save changes,
new platforms, and world-map automation remain outside this assignment.

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

### A2 — Prove a reversible player-to-AI handoff (P0, still open)

A2.3 answered a pipeline question, not the product acceptance gate. Existing
`tools/probe_player_ai_control.py` and `docs/player-ai-control.md` are delivered;
do not recreate them. `1334849` established register-based battle input and a
Wait/enemy-turn loop. `cda503c` established shared sequencer initialization and
corrected actor attribution. Neither a sequencer seed, a merged-continuation
hit, nor repeated Wait confirms proves that the player selected and executed
an autonomous tactical action. A3 remains blocked on the evidence below.

Read `docs/player-ai-control.md` (especially A2.3 verdicts),
`tools/exp_control_v48.py`, `tools/boot_fixture_gdb.py`,
`tools/gdb_force_key.py`, and the 2026-09-09 project-log entry. Consult
`docs/turn-order.md`, `docs/unit-flags.md`, and `docs/dead-ends.md` for the
specific hypothesis, not the entire experiment corpus.

#### A2.4a — Repair the experiment baseline (dispatch first)

Own: `tools/boot_fixture_gdb.py`, fixture guard helpers if needed,
`configs/battle-scenarios/normal-battle.json`, `docs/battle-fixtures.md`.
Update `docs/player-ai-control.md` and the project log with the resulting receipt.

- [x] Inventory local `battle-start`, `a2-battle-start`, and `fix3-battle-start`
  variants. Record exact path, SHA-256, emulator version, ROM SHA1, source
  save provenance, pre-existing modifications, and which variant each claim
  used. Do not overwrite or commit states, saves, ROMs, or extracted bytes.
- [x] Resolve conflicting roster claims: scenario JSON says six clan members;
  control docs say solo Marche vs six monsters but A2.3 says six live units.
  Count live records from observed engine state and distinguish roster slots
  from turn scratch. Do not infer party size from WT display or array capacity.
- [x] Correct the boot guard: its `NAME0_ADDR` currently samples slot1 and
  `MID6_ADDR` samples the now-refuted slot6/scratch region. Verify Marche via
  slot0 identity, actual live roster bounds, scene, and progressing turn state.
  A plausible name pointer or CT=45 alone is insufficient.
- [x] Replace global `taskkill /IM mgba.exe` with ownership of the launched
  process; accept explicit ROM/state/emulator paths and operate on a save copy.
  Keep one GDB connection through boot and experiment. Reconnection behavior
  conflicts between older notes and the boot helper: test it only if required,
  rather than depending on reconnect working.
- [x] Reload the chosen fixture twice and capture a live baseline: valid PC,
  actor identity, roster/scratch pointers, menu state, and a committed turn
  followed by an enemy action. Classify a wedge separately from a negative
  control result. Check wrong/missing fixture rejection before memory writes.

Done: one reproducible command and metadata receipt let the next worker start
on the same verified, live fixture. If states are unavailable, return the exact
missing paths and documented rebuild route; do not silently use snowball.

Status (2026-09-10): all boxes done. Receipt `outputs/autobattle/A2.4a/`;
metadata in `docs/battle-fixtures.md` and
`configs/battle-scenarios/normal-battle.json`. Only `battle-start.ss0`,
`battle-start-r1.ss0` and `fix3-battle-start.ss0` hold the roster;
`a2-battle-start.ss0` fails the guard and its attributed claims were
re-attributed. The roster is seven units with the player at slot6.

#### A2.4b — Isolate the control lever (after A2.4a)

Own: one reusable `tools/probe_control_handoff.py` built from existing transport
and v48 logging, plus `docs/player-ai-control.md`. Keep numbered experiments as
historical evidence; do not create another unbounded v49–v70 search chain.

- [x] Capture an unmodified control, then vary one hypothesis per slice.
  First test enemy bit7 -> menu routing on a progressing instance, immediately
  before that actor's pick. This validates direction only; it cannot satisfy
  player-to-AI acceptance. Observe the routing branch and visible/input
  behavior, not merely `0x0809E796` (shared by both paths).
- [x] Next isolate Controlled (`+0xED` bit3 and controller-id fields) from
  menu-router and wake marks. Trace roster-to-turn-record copying and the
  `0x0809E272` clear so the intervention survives to its intended consumer.
  Enemy-to-player control is a diagnostic, not the desired product direction.
- [x] Use baseline / intervention / restored-baseline runs from the same
  fixture. Save original values before writes; restore only owned changes at
  a verified safe boundary. Report every write (address, width, old/new value,
  timing, rationale), including key-enable, CT, and temporary breakpoints.
- [x] Log actor identity (`r7` at the documented continuation), record (`r4`),
  relevant flags before consumption, seed actor, action/target, committed
  position, next actor, and screenshots. Missing decoded facts remain null.
  Prove game progress before interpreting absence of a breakpoint hit.

Experiment protocol: use the poll at `0x08000494` with five-frame presses and
running/release intervals; verify the key-enable state and preserve its original
value. Never single-step through the key updater. PC `0x00000004`/`S04`, static
CT with an undriven menu, and no seed on a stalled instance invalidate the trial.
Wake marks are a combined intervention, not a proven standalone AI switch.
Do not compress CT in the primary causal comparison; if needed diagnostically,
record it as a separate condition and restore it.

Done: a causal lever with exact preconditions and restoration, or a bounded
negative result that rules out that lever. Limit each slice to one hypothesis
and two materially different experiments. If neither identifies a safe
player-to-AI route, stop and deliver a design comparison of sequencer delegation
versus external engine-legal action selection; do not implement menu macros
under the name retail AI.

Status (2026-09-10): all boxes done; the result is the bounded negative case.
Receipt `outputs/autobattle/A2.4b/`, comparison in `docs/player-ai-control.md`.
Slice 1: `+0xEA` bit7 is the **Stop** skip, side-agnostic — all seven units
including the player take `ai_path_0x0809E3BA`, and forcing bit7 on one enemy
moved exactly that one turn to `shortcut_0x0809E3B8` with no menu and no extra
input. Slice 2: Controlled (`+0xED` bit3 + `+0xE6` id) is cleared at the actor's
turn start by `0x0809E272`, and when forced to survive past it the router and
the end CT vector are unchanged. Recommended path: external engine-legal action
selection; the `+0x8000` side-flag dispatcher remains unproven.

#### A2.5 / A3 — Acceptance open; close through C1–C3

Existing runtime, CLI, fixture guard, probes, and transport tests are the
implementation baseline. Preserve them and fix the remaining contracts.
Detailed checks and receipt requirements live in
[autobattle-worker-contract.md](autobattle-worker-contract.md).

### C1 — Cancellation and usable handoff (P0)

Own: `tools/autobattle_runtime.py`, `tools/run_autobattle.py`,
`tools/probe_control_handoff.py`, `tools/fixture_guard.py`,
`tools/validate_transport_paths.py`, `tools/handoff_cli_probe.py`, and focused
regressions required by the contract. Reuse the existing transport.

- [x] Reproduce STOP during the initial progress wait causing a subsequent
  recovery B press and full route; add a regression that fails on the old code.
  (Done 2026-09-17: Astra round 3 reproduced it; the strict-press transport
  scenario reproduces it — its first run failed with exactly the escaped-press
  shape on the old code, then passed with the gate: 5 presses, none after the
  STOP was observed, with an ABORTED-press record.)
- [x] Implement the contract's single cancellation check at every input
  boundary, including each key in a route, recovery, and supplemental waits.
  (Done 2026-09-17: `press()` checks before firing and returns -1 on abort;
  `drive()` aborts mid-route and skips redelivery; the B-recovery loop checks
  before EACH press and re-drive; waits already carried `stop_check`.)
- [x] Exercise the actual CLI and session cleanup for leave-running, kill,
  guard failure, and connection loss. Preserve the known process-lifetime fix.
  (2026-09-17: `tools/handoff_cli_probe.py` now covers BOTH paths through the
  real `FixtureSession.__exit__` — leave-running survives the owned pid,
  kill-path `--kill-path` terminates only it and releases the port;
  disconnect is the transport suite's connection_lost scenario.)
- [x] Demonstrate live STOP → manual choice with the emulator still usable;
  record input ordering, process survival, and cleanup of owned hooks/state.
  (Done 2026-09-17: process survival, input ordering via the timestamped
  `input-log.jsonl`, disarm/detach all proven; the visible manual command is
  proven agent-side by `tools/manual_input_probe.py` — the runner detaches,
  the agent sends real player input through the mGBA window via SendInput
  (never the GDB stub), the screen visibly changes, and the stub write log
  shows zero post-handoff writes. Astra round 4 confirmed an agent-driven
  player is sufficient; a human is not required.)

Done: all C1 checks in the contract pass. Continue to C2 without review.

### C2 — Identify and deliberately execute one player action (P0)

Own: probe/action decoding, runtime event attribution, scenario metadata,
`tools/validate_autobattle_runtime.py`, and focused action tests. Add a small
pure selector only as needed; the broader tactics language remains A5.
Read `docs/player-ai-control.md`, `include/ffta.h`, and the specific accessors
needed to verify field semantics. Treat prior fixed-address effects as suspect.

- [ ] Reject invalid/transient roster snapshots before policy decisions or
  effect attribution. Validate identity, record lifetime, and field bounds.
- [ ] Identify one legal non-Wait command and its target/destination at a
  player boundary; choose that identified candidate rather than inferring
  an action from the key sequence sent.
- [ ] Tie player identity → selection → engine acceptance → execution →
  turn end into one receipt. Add the contract's negative controls.
- [ ] Repeat from reload twice. An action ID with verified semantics is enough;
  human-readable name decoding is optional. Record uncertainty as unknown.

Done: two valid live executions and all C2 checks pass. If the decoded action
has no HP/MP effect, verify its specific observable result (e.g. committed
movement) at the correct boundary. Continue to C3 without review.

### C3 — Integrate and close the milestone (P0)

Own: integration fixes in C1/C2 files, validators, metadata receipts,
`docs/player-ai-control.md`, this roadmap, and the current project-log summary.

- [ ] Run the contract's offline failure suite against the final implementation.
- [ ] Complete one live battle with the verified selector; defeat is a valid
  completion outcome. Verify results state and cease input there.
- [ ] Demonstrate pause → manual action → automated continuation of the same
  battle, with a documented command/interface; restarting the fixture does
  not count as continuation. Keep connection ownership explicit.
- [ ] Publish the criterion-to-evidence receipt and reconcile current status,
  then commit only owned files. Preserve existing uncommitted work.

Done: every required C1/C2/C3 criterion has passing evidence applicable to the
final revision. Mark A2.5/A3 accepted and advance to A4 or A8. Any failed or
unknown criterion keeps the packet open; keep fixing it within scope.

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

## Autonomous execution and handoff

Use the acceptance contract's execution loop and evidence template. Workers
may choose implementation details, add focused probes, fix discovered defects,
and select the next evidence-producing hypothesis within the assigned packet.
Each research slice tests one hypothesis with at most two distinct experiments;
then record the result and select the next hypothesis. This bounds each slice,
not the whole task, and does not require an orchestrator reply.

Escalate only when progress requires unavailable inputs/access, conflicting
user requirements, destructive changes, or a product-scope decision outside
the route above. Report the exact missing dependency and continue independent
in-scope work where possible. Difficult debugging or a failed test is ordinary
worker work. Preserve exclusive ownership of the emulator and its save copy.

Dispatch prompt:

> Continue the first unaccepted packet in docs/auto-battle-roadmap.md. Read
> docs/autobattle-worker-contract.md and the packet's named sources. Reproduce
> the known failure, fix it, run its positive and adversarial checks, inspect
> live evidence, reconcile status, and commit owned files. Continue through
> C1–C3 without waiting for review when their criteria pass. Report observed
> facts and unresolved criteria; never replace a criterion with a weaker proxy.

## Deferred work

Map seams/metatile naming, further matching for its own sake, mission-table expansion, automated grinding outside battles, native hardware packaging, advanced formation tactics, and a polished editor before the runtime contract. Reopen these only when they directly unblock the milestones above.
