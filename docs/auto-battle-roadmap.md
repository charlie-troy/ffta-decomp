# Customizable auto-battle roadmap

Updated 2026-09-17. Baseline reviewed at `cda503c`; the closure work since (validator gate, runtime stop checks, chooser, handoff proof) landed in `a55e29f` and the closure packet that follows. A2.4a's receipt is `outputs/autobattle/A2.4a/`; A2.4b's is `outputs/autobattle/A2.4b/`. Earlier review text (2026-09-09) inspected commits, source, and recorded findings; it did not rerun the emulator or ROM gates.

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

| Order | Packet | Current state | Unlocks |
|---|---|---|---|
| 1 | A2.4a fixture and harness repair | Done 2026-09-10; receipt `outputs/autobattle/A2.4a/` | Trustworthy control experiments |
| 2 | A2.4b causal control experiments | Active (2026-09-10); bounded negative result + design comparison | A verified lever or explicit architecture decision |
| 3 | A2.5 reversible player-turn proof | Done with limits (2026-09-15, corrected 2026-09-16/17): boundary, delegation, and reversibility proven in `outputs/autobattle/A2.5/`; the runtime contract is frozen in `docs/player-ai-control.md`; deliberate non-Wait selection demonstrated live in `a3-chooser3` (turns 1/5/6 via the ability-evidence chooser with engine deltas; command id→name still undecoded, chooser honestly declines without evidence) | A3 runtime implementation |
| 4 | A3 hands-off runner | Done 2026-09-16 (post-review closure same day): `a3-natural6` finished one normal battle hands-off (12 committed turns, natural `completed` at t≈888 s, zero tactical clicks; the battle ended in Marche's defeat — a failed encounter, not an automation failure); manual takeover reworked into real pause semantics; receipt validator hardened after a live adversarial check; transport suite (eight shapes) validates offline. A reliable tactical auto-battle still needs the decoded action menu | A4 identity/isolation and A8 speed |
| Later | A4–A10 | Keep existing dependency gates | Per-character tactics and usable release |

Before editing: run `git status --short` and `git log -5 --oneline`; read
`CLAUDE.md` and this packet. Preserve any new concurrent changes. Verify local
ROM SHA1 with `Get-FileHash -Algorithm SHA1 -LiteralPath .\baserom.gba` before
ROM-dependent work. Inspect helpers before execution: older scripts can kill
all emulator processes or rely on stale fixture addresses. Never attach to
another worker's or the user's active emulator.

For each handoff, provide: base/head, owned files, exact command, fixture hash,
run id, hypothesis, observed result, evidence paths, all interventions and their
restoration, checks run now versus historical checks, limitations, and the
single next packet unlocked. Keep evidence under `outputs/autobattle/<run-id>/`;
commit only metadata/summaries without game bytes. Source syntax checks support
tooling edits; live baseline/intervention/restoration evidence supports control
claims. Run domain validators for affected ROM surfaces and the full release
gate only when integrating a ROM release, not for documentation-only updates.

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

#### A2.5 — Acceptance proof and runtime contract (after A2.4b)

Own: `docs/player-ai-control.md`, the reusable probe, and evidence metadata.

- [x] From the verified normal fixture, make Marche autonomously choose and
  execute a legal non-Wait action and movement when required by its range.
  Record the actor-specific decision -> action -> turn-end -> next-actor chain.
  (Partially met, NOT fully: the delegated turn's action selection is the
  engine's own retail AI and the manual route selects Wait. What IS proven:
  a full non-Wait menu cycle exists and reads unit-specific data (a3-full2's
  route committed a Move), movement/target legality stayed engine-side, and
  the decision-action-turn-end-next-actor chain is recorded in the receipts'
  seed/router/turn traces. Verified 2026-09-17 in `a3-chooser3`: the runtime
  chooser (`choose_non_wait` over the inline ability-state scan) accepted at
  three boundaries and drove the action-submenu route — a deliberately
  selected non-Wait action, not the fixed Wait route — with an engine-side
  effect delta recorded per commit; at boundaries without evidence it
  declined fail-closed to the fixed route. Still open: the committed
  command's id→name decode (`command_id` stays null).)
- [x] Confirm side/alliance values and legal targeting remain unchanged, enemy
  behavior remains retail, and a second player turn is also delegated.
  (Receipts `a25-acceptance-repeat1.json` / `a25-acceptance.json`: enemy turns
  observed via router+seed traces after both manual commits; second player turn
  delegated via the same input channel; `battle_torn_down` false in both.)
- [x] Restore manual control at a safe boundary, visibly execute a manual
  choice, then re-enable delegation. Repeat the complete experiment twice
  from reload; report fixture/RNG differences rather than promising determinism.
  (Runs 19/20, 2026-09-15: manual takeover at the settled/frozen menu boundary,
  full DOWN DOWN A A route committed visually at the open menu, re-delegation
  completed; seed/router traces differ between runs as RNG predicts.)
- [x] Freeze a runtime contract: detect boundary/actor, enable one turn,
  observe completion, request takeover, restore, and detect invalid state.
  Include expected original hook bytes if code is patched, allowed ROM hash,
  record lifetime, owned writes, failure behavior, and reproducible commands.
  (Frozen in `docs/player-ai-control.md` "A2.5 result": four boundary shapes,
  the only proven commit shape, transport rules, visual-channel rules, and
  honest limitations. No ROM code is patched — the probe owns RAM writes only,
  all restored at exit; reproducible via `python tools/probe_control_handoff.py
  a25 --runs 1 --seconds 150`.)

Done: reviewer can follow the receipts to a reversible player AI turn with
unchanged allegiance. Only this acceptance unlocks A3. A Wait-only loop stays
an input/turn-flow diagnostic even if enemies eventually end the battle.

**Re-scope needed (2026-09-10).** A2.4b removed both candidate engine-internal
levers, so this packet as written has no instrument. Two options, from the
comparison in `docs/player-ai-control.md`: (A) find and prove the battle
caller that branches on the `+0x28` bit `0x8000` side flag, then delegate the
chosen actor's turn internally; or (B) re-scope A2.5 to freeze the boundary
contract for externally selected, engine-legal player actions over the proven
`0x08000494` input channel, with A5's pure `choose_action` interface supplying
the choice. Option B is recommended; the orchestrator owns this decision.

### A3 — Minimal autonomous battle runner (P0)

Depends on reviewed A2.5 and its frozen runtime contract. Create `tools/autobattle_runtime.py`, `tools/run_autobattle.py`, and `tools/validate_autobattle_runtime.py`; reuse the existing emulator transport.

- [x] Expose CLI `run_autobattle.py --rom PATH --scenario PATH --mode retail-ai`; default to paused until the fixture and ROM guards pass.
  (Built 2026-09-15; the live guard decodes all seven roster names before
  input is issued and a wrong fixture fails closed — observed on the first
  boot when name decoding was broken.)
- [x] Implement explicit idle/running/takeover/completed/stalled states using A2's verified control boundary. Stop issuing input after completion, takeover, connection loss, or an unknown modal.
  (`tools/autobattle_runtime.py`; boundary = `player_menu_frozen`, drive =
  the only proven route. `completed` observed live in a3-natural6: the
  battle-end signature held and the run closed on its own. A post-Move
  submenu shape gets bounded B-recovery — navigation, not tactical input —
  before an inert route is treated as an unknown modal and bounds the
  run, per DE-020. Post-review correction: a STOP request is a real pause
  handoff (`paused` state) — input stops, breakpoints disarm, and with the
  CLI's `--on-stop leave-running`  the emulator survives for the player — proven 2026-09-17 through the
  REAL `FixtureSession.__exit__` cleanup path, not a mock
  (`tools/handoff_cli_probe.py`, receipt `outputs/autobattle/a3-handoff-probe/`:
  STOP at t=55.5, event `state: paused`, and the emulator pid survived
  `__exit__` with `--on-stop leave-running`). The stop file is additionally
  checked inside long progress waits and B-recovery loops, so input stops
  mid-wait, not only between waits. The automation-driven boundary state
  `takeover` is NOT a manual handoff.)
- [x] Append turn events to `outputs/autobattle/<run-id>/events.jsonl`: scenario, turn, actor, control mode, selected action/target, position before/after, and reason for stopping. Unknown fields must be null, not inferred labels.
  (`selected_action` stays null for the fixed route — a3-full2 proved the
  route commits whatever the open menu resolves to, so the action is NOT
  claimed as Wait. When the chooser drives the action-submenu route —
  demonstrated live at three boundaries in `a3-chooser3` and at all five
  boundaries in `a3-chooser4` (turn 1's diff carries non-CT deltas for the
  affected unit: hp/mp/tg/position; magnitude decoding is still stride-
  suspect) — the
  event records a structured `selected_action` of kind
  `deliberate-non-wait-route` with `command_id: null` (the id→name mapping
  is not decoded) plus an engine-side effect diff in the note.
  `tools/validate_autobattle_runtime.py` enforces the schema offline and,
  since the 2026-09-16 adversarial check, fails on any input-kind event
  after the terminal stop.)
- [x] Bound stall detection by no-progress frames plus a wall-clock timeout; release held keys and restore temporary hooks on exit where the connection remains available.
  (Stall = seed silence beyond 150 s — recalibrated from a3-natural3, whose
  healthy boundary waits reached 93 s — plus a debounced dead-player check;
  a held defeat with seed silence enters grace: takeover and the stall bound
  are suppressed so the engine's own defeat→results conclusion classifies
  the run (a3-natural1 lesson). Wall timeout checked every pump and inside
  progress waits; `disarm()` removes all breakpoints on exit; no key writes
  are held — the key-enable scratch is re-written per press. Positions still
  read transient garbage at boundary detection; position_after is reliable.)
- [x] Validate disconnect, repeated start/stop, unknown-dialog, and takeover paths using recorded transport responses; then finish one normal battle with no tactical clicks.
  (`tools/validate_transport_paths.py` drives the real `BattleRuntime`
  against a wall-clock fake engine — 60 fps frames, recorded ~12.9 CT/s —
  across seven recorded shapes: takeover, unknown-dialog swallow, transport
  disconnect, repeated start/stop, mid-battle player defeat, natural
  results end, and the post-Move submenu wedge; every artifact passes
  `tools/validate_autobattle_runtime.py`. Live: `a3-natural6` finished one
  normal battle with zero tactical clicks — 12 committed routes with retail
  enemy AI between them, defeat grace at t≈880, `completed` at t≈887.8.)

Done 2026-09-16: one uninterrupted normal battle (`a3-natural6`, 12 turns, completed) plus the transport-path suite covering the recorded failure shapes. Closure 2026-09-17: the deliberate chooser route was accepted at every boundary of a live run (`a3-chooser4`, 5/5 with engine-side diffs; its 420 s wall budget expired inside the ending sequence with the results dialog already up — the all-1000 CT tail is end-of-battle state, and `a3-chooser5` reran it with headroom), and the manual handoff survived the real CLI cleanup path (`a3-handoff-probe`). Preserve the user's save. This milestone uses retail AI and makes no claim of sophisticated custom strategy yet.

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

- Give implementation agents one packet, its prerequisite evidence, and its owned files. They should not read the entire multi-thousand-line project log or undertake open-ended reverse engineering.
- Routine agents fit A3 after hook approval, A5's pure evaluator, A8 after API discovery, and A10 after schema freeze. The orchestrator owns A2/A4 architecture decisions and reviews A7's causal evidence. Escalate uncertain semantics; do not buy repeated speculative experiments.
- A2.4a → A2.4b → A2.5 run serially with exclusive ownership of the emulator session. Pure evaluator/editor work can run independently once interfaces are frozen. Never let two agents attach to or mutate the same mGBA process/save.
- Limit a research slice to one hypothesis and two distinct experiments. Return a useful negative result with exact evidence if unresolved; the orchestrator chooses the next slice.
- Require the return format: commit/base, files changed, claim, command/evidence, observed result, limitations, and next dependency unlocked. Report historical checks separately from checks run now.
- Integrate one packet at a time. Review behavior and patch attribution; run relevant domain checks for each change and the complete release gate for an integrated ROM release. Do not replace meaningful execution evidence with tests that restate the implementation.

Suggested dispatch prompt:

> Implement packet [ID] in docs/auto-battle-roadmap.md only. Read CLAUDE.md, docs/dead-ends.md, and the packet's named source files. Verify the checkout and prerequisite evidence first. Preserve unrelated work and local saves. Do not expand scope or infer unproven ROM semantics. Deliver the packet's tests/evidence and a project-log entry. If a dependency is missing, report the exact blocker and the smallest evidence-producing next step.

## Deferred work

Map seams/metatile naming, further matching for its own sake, mission-table expansion, automated grinding outside battles, native hardware packaging, advanced formation tactics, and a polished editor before the runtime contract. Reopen these only when they directly unblock the milestones above.
