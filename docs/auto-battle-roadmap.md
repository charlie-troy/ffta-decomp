# Customizable auto-battle roadmap

Updated 2026-10-07. Reviewed checkout: `9532cb4` plus the A6.1 public integration packet. Current acceptance status
is maintained here; dated discoveries remain in `docs/project-log.md`.
For every auto-battle implementation or completion claim, follow
[Worker acceptance contract](autobattle-worker-contract.md). It defines the
checks needed to finish a packet and continue without orchestrator approval.
Earlier “closed” log entries are historical claims, not dependency clearance.

## Current worker assignment

**A6.4 engine KO lifecycle and independent scratch reload now have bounded PASS
evidence. Continue native action-set/menu reconstruction to expose enabled Life;
target acceptance and revival remain UNKNOWN.**
Two public ally casts, damage-policy refusal/Wait, both STOP/manual/same-PID
handoffs, two unsupported-family zero-input controls, the six-case self-Cure
matrix and ordinary live Move/Wait pass on current production sources.
See `docs/a63-public-ally-recovery.md` and `A6.3.json` for exact hashes.
The opt-in public self-Cure matrix now has six passing current-source cases:
two accepted casts, reserve decline, engine-disabled Cure and both no-match
fallbacks. Both final STOP/manual/same-PID receipts pass, including eight
rejected mutations each; the real two-ally fixture rejects with zero input.
A6's wounded-party, ally/KO and item criteria remain open.
A5 is closed for the narrow family (2026-10-06): the public runner follows
per-character rules (two job-5 allies take different commands in one battle),
and on equivalent starting states changing one condition value changes both the
decision and the engine result (Montblanc: 177/241 HP, Wait under `<= 80`;
84/241 HP, Move under `<= 30`), with Marche as an unchanged control. Audit:
the saved fixture matches but intervening damage differs, so these are not
identical decision states; both HP values fall between the thresholds. STOP, the
monitor-client handoff and same-PID resume were re-run on this revision, and two
integration defects found by that evidence are fixed with regressions (adopted-
session cleanup; resume scenario mismatch). Ability targeting, movement
preference, law/status-conditioned play and complete-battle outcomes under a
policy remain open and are named in the receipt.
A5.1 is accepted (2026-10-06): the public runner drives the two-ally fixture
with validated actor-linked Move/Wait, and the live manual takeover plus
same-process resume pass on one battle (see `docs/a51-integration.md`).
A5.3 is proven (2026-10-06) for a deliberately **narrow** family: with
`run_autobattle.py --tactics-policy PATH` the adapter offers only the commands
the decoded menu names (Move/Wait), one live run followed per-character rules
(Marche Move, Montblanc Wait on the same battle) and another followed one
engine-read condition (actor HP percent, 100% -> Move, 73% -> Wait), both
engine-verified. Ability candidates, MP cost and range targeting remain
unproven and cannot become enabled options (`docs/tactics-policy.md`).
A5.2 is frozen (2026-10-06): `tools/tactics_policy.py` + `configs/tactics/`
implement the frozen schema in `docs/tactics-policy.md`, with a pure host
suite at 94/94 (`python tools/validate_tactics_policy.py`). No live wiring or
engine-legality claim belongs to A5.2; A5.3 proves the adapter seam.
A4 remains a bounded feasibility demonstration, not a completed
multi-character product. C1–C3 are accepted for the documented fixture and
same-process handoff. A8 investigation is complete; selectable acceleration
and two-speed equivalence remain UNKNOWN. A6/A7/A10 are unlocked; A9 final
acceptance also waits for A8.

This checkout remains the decompilation/modding and Windows companion project.
The independent ROM-native hack has its own ROM-XX roadmap and evidence.
General function matching and map cleanup remain deferred; this review does
not change the established product priority.

### Review evidence and limits (2026-10-06)

| Observed work | Worker consequence |
|---|---|
| C3 receipt at `docs/receipts/autobattle/C3.json`; accepted at `88b1072` | Preserve STOP, monitor-client handoff and resume contracts. Completion includes a defeat, not demonstrated tactical strength. |
| A4 receipt and `outputs/autobattle/A4-demo/demo.json` at `7c6f1b8` | Two job-5 allies execute different Move/Wait choices; same-job enemy remains retail. Reuse the demo and its actor attribution, not CT-only identity. |
| `tools/autobattle_runtime.py` still emits `actor="Marche", actor_slot=6` and uses single-player position/death helpers | A4 demo acceptance does not certify the public runner on multiple allies. Closed by A5.1 (`0bb4fd4`/`1132bee`): the runner resolves the verified fresh-menu owner by name+id with job/side agreement and cross-checks the whole party's movement. |
| `docs/receipts/autobattle/A8.json`, revised 2026-10-05 | Measured roughly 0.87–0.97x nominal on this host; no selectable acceleration. Withdrawn 4.1x/Lua/extrapolated figures stay withdrawn. |
| Last log records `validate_all.py` PASS at A4 closure | Historical validation, not rerun by this documentation review. No new gameplay or release certification is claimed. |

Read the current packet and its named sources first. Use historical sections
below only for the relevant research question; superseded next-step language
there does not override this queue.

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
| Live scenario | Normal-battle C3 completion/handoff and A4 two-ally divergence are accepted within named fixtures. Snowball remains a narrow enemy-turn research fixture. |
| Normal-battle access | A1 captured a repeatable encounter and enemy movement/action (`123ea91`). A2.4a reconciled fixture identity/guards; A4 added a purpose-built two-ally fixture. Revalidate each fixture for its named use. |
| Missing product pieces | Ability/item conditional tactics, resource/movement policy, broader battle recovery, selectable acceleration, usable configuration workflow. |

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
| 2 | C2 validated player action | Accepted for the documented Move fixture; 237aebe live6/live7 evidence retained | C3 |
| 3 | C3 integration and acceptance | Accepted 2026-09-21 at 88b1072: complete live battle plus same-process manual Move/Wait and resumed completion; fresh resume regression passed | A2.5/A3 accepted within documented scope; enabled A4 and A8 |
| 4 | A4 assignment feasibility | Bounded PASS, 2026-10-05 at `7c6f1b8`; two-ally demo and identity receipts | A5.1 runner integration |
| 5 | A5 ordered tactics | **A5.1 accepted, A5.2 frozen, A5.3 proven, A5.4 closed** (2026-10-06) for the narrow Move/Wait family; ability targeting stays unsupported | A6/A7/A10 |
| Independent | A8 acceleration | Investigation complete; product UNKNOWN | A9 remains gated on actual speed acceptance |
| Later | A6/A7/A9/A10 | GATED by declared prerequisites | Follow the packet gates |

A1 and A2.4a supplied normal-battle fixtures. A2.4b supplied useful negative
control results. A3 has an unattended failed-encounter result (`a3-natural6`),
and the CLI now preserves its process on pause. These are reusable evidence,
not proof of player action selection or complete cancellation behavior.

**Default assignment:** continue A6; revisit A8 only for a new discriminating
mechanism/host hypothesis. C1–C3 and A4 are
accepted for the documented fixture and one-handoff flow. Work within an
ongoing request to continue auto-battle work. Read the contract and the current
packet only; load linked research references when that packet needs them.
A passing packet unlocks the next packet automatically. No additional human
or orchestrator sign-off is required for scoped, reversible implementation,
local tests, evidence capture, or commit of owned files.

A5.2's frozen contract is `docs/tactics-policy.md`: the adapter supplies only
engine-legal candidates plus verified identity and fresh facts, and
`choose_action(snapshot, policy)` orders preferences among them (or returns
`None`). Unsupported predicates fail to load, so A6/A7 extend the schema
rather than silently enabling anything.

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

### A2 — Prove a reversible player-to-AI handoff (historical discovery; A2.5 accepted through C3)

The open/blocking language in the investigation below describes its original
checkpoint. C1–C3 later accepted the external identified-action route; native
retail-AI delegation is not this project's accepted architecture.

A2.3 answered a pipeline question, not the product acceptance gate. Existing
`tools/probe_player_ai_control.py` and `docs/player-ai-control.md` are delivered;
do not recreate them. `1334849` established register-based battle input and a
Wait/enemy-turn loop. `cda503c` established shared sequencer initialization and
corrected actor attribution. Neither a sequencer seed, a merged-continuation
hit, nor repeated Wait confirms proves that the player selected and executed
an autonomous tactical action. At that historical checkpoint A3 was blocked; C3 later supplied acceptance for the external route.

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
  shape on the old code, then passed with the gate. Round 6: the identified
  flow gates BETWEEN legs, so a between-legs STOP suppresses the next press
  attempt entirely — the scenario asserts no press STARTS after stop_requested
  instead of an ABORTED record.)
- [x] Implement the contract's single cancellation check at every input
  boundary, including each key in a route, recovery, and supplemental waits.
  (Done 2026-09-17; round 6: B-recovery and fixed-route fallback are GONE —
  the identified-only boundary drives only RAM-identified candidates, and the
  identified drive's inter-leg settles poll the stop gate every 100 ms,
  restoring the 2 s observation bound that fixed sleeps broke to 2.8 s.)
- [x] Exercise the actual CLI and session cleanup for leave-running, kill,
  guard failure, and connection loss. Preserve the known process-lifetime fix.
  (2026-09-17: `tools/handoff_cli_probe.py` now covers BOTH paths through the
  real `FixtureSession.__exit__` — leave-running survives the owned pid,
  kill-path `--kill-path` terminates only it and releases the port;
  disconnect is the transport suite's connection_lost scenario.)
- [x] Demonstrate live STOP → manual choice with the emulator still usable;
  record input ordering, process survival, and cleanup of owned hooks/state.
  (Done 2026-09-17; round 6: the manual command is proven by IDENTITY, not a
  screenshot — `tools/manual_input_probe.py` (schema /3) re-attaches read-only,
  resumes the core (the stub halts on connect and serves stale reads while
  running — r6c's recorded lesson), waits for the genuine player-command
  window from RAM (decoded cursor at 0 with Marche's roster CT frozen), sends
  one window SendInput DOWN, and requires the DECODED command cursor to move
  (live: 0→1 Move→Action). Zero stub key writes after handoff. Astra round 4
  confirmed an agent-driven player is sufficient; a human is not required.)

Done: all C1 checks in the contract pass (round-6 update 2026-09-18: identified-
only boundary, decoded-command manual proof, abortable settles). Continue to C2
without review.

### C2 — Identify and deliberately execute one player action (P0)

Own: probe/action decoding, runtime event attribution, scenario metadata,
`tools/validate_autobattle_runtime.py`, and focused action tests. Add a small
pure selector only as needed; the broader tactics language remains A5.
Read `docs/player-ai-control.md`, `include/ffta.h`, and the specific accessors
needed to verify field semantics. Treat prior fixed-address effects as suspect.

- [x] Reject invalid/transient roster snapshots before policy decisions or
  effect attribution. Validate identity, record lifetime, and field bounds.
  (Done 2026-09-17: `plan_identified_move` rejects unreadable/(0,0) tiles, a
  command cursor outside {0,1,2}, and implausible target cursors (out of map
  bounds, (0,0), None); live probe4 showed the engine itself rejects out-of-
  range destinations — the decoder never plans past an illegal state.)
- [x] Identify one legal non-Wait command and its target/destination at a
  player boundary; choose that identified candidate rather than inferring
  an action from the key sequence sent.
  (Done 2026-09-17: menu cursors decoded from live RAM — command cursor
  0x0202ddd9 (Move=0/Action=1/Wait=2, two-cycle differential sweep) and move-
  target cursor 0x0200ffc9/ffca (+ mirror 0x02010058/59, end-to-end commit
  probe6). The runtime's identified branch reads cmd+target cursors, plans,
  and drives leg-by-leg with RAM re-reads between legs; the destination is
  read before the confirming input.)
- [x] Tie player identity → selection → engine acceptance → execution →
  turn end into one receipt. Add the contract's negative controls.
  (Done 2026-09-17; round 6: planner rejection PREVENTS input — the boundary
  handler is identified-only, the chooser/fixed-route/B-recovery fallback is
  deleted, and a rejected candidate ends the run honestly with zero presses
  (negative control `identified-move-invalid`); one turn event carries actor,
  selected_action {identified-move, command_id, dest}, selected_target
  (RAM-read), and the engine-side verification (roster tile reached the
  RAM-read dest). Negative control `identified-move-wrong` (engine executes a
  different tile than the cursor named) demotes the claim — receipt
  `docs/receipts/autobattle/C2.json`.)
- [x] Repeat from reload twice. An action ID with verified semantics is enough;
  human-readable name decoding is optional. Record uncertainty as unknown.
  (Done 2026-09-17 under c2-live4/c2-live5; re-proven 2026-09-18 under the
  final round-6 code — c2-live6 committed TWO identified verified moves in one
  run ((4,10)->(4,11) then (4,11)->(5,11)) and c2-live7 one plus an honest
  bound at a later non-standard menu; ability-submenu decode remains a
  candidate pair (uncertainty recorded); c2-live3's failed-drive-was-paused
  defect found and fixed.)

Done: two valid live executions and all C2 checks pass (round-6 update
2026-09-18: the boundary is identified-only — rejection prevents input).
If the decoded action has no HP/MP effect, verify its specific observable
result (e.g. committed movement) at the correct boundary. Continue to C3
without review.

### C3 — Integrate and close the milestone (P0)

Own: integration fixes in C1/C2 files, validators, metadata receipts,
`docs/player-ai-control.md`, this roadmap, and the current project-log summary.

- [x] Run the contract's offline failure suite against the final implementation.
  (22/22 PASS on the committed code, 2026-09-20 — `outputs/autobattle/transport-checks/`.)
- [x] Complete one live battle with the verified selector; defeat is a valid
  completion outcome. Verify results state and cease input there.
  (`c3-live-a`: final_state=completed after 4 identified turns — 2 verified
  moves + 2 identified waits; input ceased at the battle-end signature.)
- [x] Demonstrate pause → manual action → automated continuation of the same
  battle, with a documented command/interface; restarting the fixture does
  not count as continuation. Keep connection ownership explicit.
  (`c3-live-b2`: leg 1 paused and left pid 784 running; the manual layer
  committed move (4,11)→(5,11) + Wait through the window channel only
  (SendInput, zero stub writes, one held monitor connection per the
  take-22 law); leg 2 `--resume` adopted the same pid, continued from the
  manually walked tile (boundary position_before=(5,11)), and drove the
  same battle to completion. Receipt:
  `docs/receipts/autobattle/C3.json`.)
- [x] Publish the criterion-to-evidence receipt and reconcile current status,
  then commit only owned files. Preserve existing uncommitted work.

Done: every required C1/C2/C3 criterion has passing evidence applicable to the
final revision. Mark A2.5/A3 accepted and advance to A4 or A8. Any failed or
unknown criterion keeps the packet open; keep fixing it within scope.

### A4 — Per-character assignment feasibility (P1, research gate)

Depends on A3. Existing schema-v1 profiles remain supported unchanged.

- [x] Add `tools/probe_strategy_scope.py` and `docs/strategy-runtime-scope.md` to identify stable party identity across turns, reloads, and battle-local slot reuse.
  (2026-09-21: identity vector (decoded name, type, base/active job, race, level, id, side bit) stable 7/7 slots across 3 phases × 2 boots; AI mirror maps 6/6 by name+job+id, Marche absent verified; receipt `docs/receipts/autobattle/A4.json`.)
- [x] Prove a player-only policy interception point; demonstrate different behavior for two same-job allies while an enemy of that job remains unaffected.
  (Interception point selected and proven by construction: the player-menu boundary chooser (Option B) — no side-flag write, A2.4b's Stop-bit refutation recorded. The same-job divergence demo ran **PASS 2026-10-05** on the purpose-built two-ally fixture `a4-multi-ally-battle-start.ss0` (Marche + Montblanc job 5 vs five enemies incl. same-job Velasquez): move committed by Marche (`moved_slots=[7]`), wait committed by distinct ally Montblanc (`moved_slots=[]`), Velasquez took a retail turn unaffected, zero memory writes — `outputs/autobattle/A4-demo/demo.json` (schema `a4-divergence-demo/3`), receipt `docs/receipts/autobattle/A4.json`.)
- [x] Select runtime lookup or another proven method. If shared table values are temporarily changed, prove restoration on every exit and no contamination of enemy turns before accepting that architecture.
  (2026-09-21: runtime identity lookup via the adapter contract — no shared-table writes, nothing to restore; the chooser reads RAM and never writes memory.)
- [x] Specify precedence: explicit character assignment, then job default, then party default, then retail behavior.
  (2026-09-21: frozen in `docs/strategy-runtime-scope.md` with fail-closed boot validation.)

Done: identity and isolation evidence, with the actual runtime adapter contract recorded. Do not add persistent save fields or promise native-console support at this stage.

### A5 — Ordered tactical rules and decision receipts (P1)

Execute these subpackets in order. Each writes a criterion table into the planned
`docs/receipts/autobattle/A5.json`, with separate host, adapter and live results.
The file/interface names below are deliverables, not claims they already exist.

#### A5.1 — Put verified actor identity into the public runner (ACCEPTED)

Accepted 2026-10-06. The public runner resolves the fresh-menu owner from
verified identity (name/id with job/side agreement) and drives the two-ally
fixture with actor-linked Move/Wait plus full-party result checks. The live
manual takeover now passes too, on purpose and reproducible: `run_autobattle.py
--pause-at-boundary` leaves the identified player menu OPEN with zero
automation input, `tools/c3_manual_layer.py` commits a window-SendInput Move
whose destination is verified from a whole-board tile delta, and `--resume`
adopts the SAME pid and continues from that tile
(`outputs/autobattle/a51-live-manual-05`; repeat `a51-live-manual-04` moves
out of it). Both
previously-failing gates are in `docs/receipts/autobattle/A5.json` with the
DE-032 turn-transition trap that had masked the resume. Scope limits (verified
fixtures, identified Move/Wait, no multi-player end signature) are recorded
there; A5.2 starts from that scope, not from a broader claim.

Read `docs/strategy-runtime-scope.md`, `tools/a4_divergence_demo.py`,
`tools/autobattle_runtime.py`, `tools/probe_control_handoff.py` and the A4 receipt.
Own the runner/adapter integration and focused transport regressions.

1. Extract/reuse the demo's fresh-menu actor resolution and full-snapshot
   cross-check. Resolve by validated identity (name + id), with job/side agreement;
   ambiguous, missing, stale or duplicate identities prevent gameplay input.
2. Replace fixed actor labels, slot assumptions, single-Marche terminal/death
   decisions and fixture guards wherever they affect the runner's active actor.
   A known actor dying must not make another ally's menu an authorized action.
3. Preserve the C2 candidate/echo checks and C1 cancellation ordering. The policy
   layer must neither inject keys nor write game memory. Scope the fresh-menu
   cursor rule to its proven validity window; do not reuse it mid-targeting.
4. Exercise `tools/run_autobattle.py` on the one-player and A4 two-player fixtures.
   Receipts must name the actual actor, selected command/destination, engine
   result and next actor; show both allies and an unaffected enemy. Reproduce
   same-process pause/manual command/resume after changing transport integration.

PASS: the public runner, not only the demo, produces correct actor-linked
actions on both fixtures; ambiguous-owner and wrong-result controls reject;
existing STOP/resume checks remain green. UNKNOWN on either fixture blocks A5.2.
Commit only owned changes when implementing; preserve other workers' files.

#### A5.2 — Freeze policy and candidate contracts (FROZEN 2026-10-06)

Frozen as delivered: `tools/tactics_policy.py` (strict schema validation +
`choose_action`/`evaluate`), `configs/tactics/{default,damage-focused,contrast-two-ally}.json`,
`docs/tactics-policy.md`, and a 94/94 pure host suite including a five-mutant
non-vacuity check. Criteria are recorded under `a5_2` in
`docs/receipts/autobattle/A5.json`. The remaining bullets below stay the
guide for **A5.3/A5.4** (live adapter wiring and divergent rules in a real
battle); they are not reopened by this freeze.

Own `tools/tactics_policy.py`, `tools/validate_tactics_policy.py`,
`docs/tactics-policy.md` and `configs/tactics/`. Start with proven Move/Wait
candidates; inventory missing engine fields before enabling spell predicates.
Define schema versions, identity, candidate IDs, observation freshness, supported
facts, deterministic ordering, reason codes and explicit fallback semantics.
Assignment precedence remains character → job → party → supported fallback.

PASS: pure host tests cover every supported rule, threshold boundaries, unknown
keys, absent/stale facts, duplicate identity/ability names, ties and empty sets.
Do not equate learned abilities with legal candidates. Missing legality or actor
identity means no commit. An identified legal Wait may be an explicit fallback;
calling it "retail AI" would misdescribe the companion architecture.

#### A5.3 — Prove the minimum conditional-action adapter (PROVEN 2026-10-06, narrow family)

Delivered: `tools/tactics_adapter.py` (read-only snapshot builder + frozen
chooser), `run_autobattle.py --tactics-policy PATH` (validated before the
emulator is touched), `tools/validate_tactics_adapter.py` (12/12 host checks
including the real runtime cancellation path), and the events/receipt schema
field `tactics` carrying outcome/reason/scope/rule/candidates/age. Live:
`a53-live-contrast-01` (per-character rules -> Marche Move, Montblanc Wait)
and `a53-live-hp-split-01` (one engine-read condition -> Move at 100% HP, Wait
at 73%). Criteria are under `a5_3` in `docs/receipts/autobattle/A5.json`; the
remaining bullets below are still the guide for the ability family, which A5.4
does not require but A6 does.

Own focused research/adapter changes and their evidence. Identify command,
target, range, MP/status restrictions and acceptance for one useful conditional
action family. Record the engine observations supporting every exposed field.
At commit, revalidate actor, candidate and target; a changed candidate cancels
the commit. Bound each hypothesis to two materially different experiments,
then record the result and choose the next discriminating hypothesis.

PASS: positive execution links actor → rule → candidate → engine result;
insufficient MP, illegal range/target, stale snapshot and misleading enemy-effect
controls reject without confirming an action. Host-generated effects do not
certify this interface. A narrow proven interface is acceptable; unsupported
families stay explicit and cannot silently become enabled policy options.

#### A5.4 — Integrate and close conditional tactics (CLOSED 2026-10-06, narrow family)

Closed for the delivered family: contrasting per-character rules through the
public runner (Marche Move / Montblanc Wait, same job), the condition-change
pair (`hp-split.json` `<= 80` vs `hold-below-30.json` `<= 30`, one value
different, flipping Montblanc's decision and result while Marche stays the
control), retained STOP and handoff/resume gates re-run on this revision, plus
`tools/validate_session_cleanup.py` (4/4) and the resume scenario guard.
Criteria are under `a5_4` in `docs/receipts/autobattle/A5.json`. Not closed and
not claimed: HP/MP/ability conditional behaviour on real ability candidates,
complete-battle outcomes under a policy, movement preference, laws.

Use the public runner with contrasting per-character policies. Demonstrate two
same-job allies following distinct rules, then change a relevant condition on
equivalent starting states and show the expected decision/result change. Retain
enemy isolation, STOP, monitor-client handoff and resumed continuation evidence.
Move/Wait divergence alone does not close HP/MP/ability conditional behavior.

PASS: every A5 requirement below has applicable host AND live evidence, the
schema is frozen, unsupported predicates fail closed, and the receipt names
exact remaining capability limits. Then continue A6, A7, and A10 as dependencies
permit; A8's open product criteria do not block policy work.

Implementation checks (PowerShell from this repository; use a fresh output root):

```powershell
python tools/validate_transport_paths.py --scenario all --out-root outputs/autobattle/A5-transport-<unique-run>
python tools/validate_autobattle_runtime.py outputs/autobattle/<actual-live-run>
python tools/validate_tactics_policy.py
python tools/validate_tactics_adapter.py      # A5.3
```

The policy and adapter validators are A5 deliverables; their exact CLIs are in
the receipt. `python tools/run_autobattle.py ... --tactics-policy PATH` is the
live policy entry point.
For ROM changes, also run `python tools/validate_all.py baserom.gba` and the WSL
build gates. A receipt validator checks consistency, not independently the game.

Depends on A4. Create `tools/tactics_policy.py`, `tools/validate_tactics_policy.py`, `configs/tactics/`, and `docs/tactics-policy.md`. Extend the runner through A4's reviewed adapter; keep the existing global ROM profile compiler separate.

Proposed pure interface: `choose_action(snapshot: dict, policy: dict) -> dict | None`. The adapter supplies an actor id and only engine-legal candidate actions, each with an action id, target id, actor/target HP and MP, cost, relation, and verified status data. Missing required facts make a rule ineligible. Return a candidate id plus matched rule id/reason, or `None` for the explicitly documented no-match path. Freeze the exact JSON schema in this packet before A6/A7/A10 start.

- [ ] Implement ordered first-matching-eligible rules, enabled flags, explicit fallback, and deterministic tie handling. Reject unknown keys and invalid thresholds.
- [ ] Support only verified initial predicates: self/ally/enemy, HP percentage threshold, known status present/absent, named/identified available ability, and remaining MP after cost.
- [ ] Add contrasting fixtures: wounded ally vs healthy ally, insufficient MP, no matching ability, duplicate ability names, equal-priority targets, and no legal action. For each fixture assert the selected candidate and rule reason.
- [ ] Connect policy choices through the verified adapter and show two same-job characters follow different rules in the normal battle.

Done: reproducible per-character conditional tactics, with unsupported predicates rejected. Engine legality always wins over policy preference. Policy presets change decisions, not damage, stats, AP, or reward tables.

### A6 — Resource and recovery tactics (P1)

Depends on A5. Modify `tools/tactics_policy.py` and its validator; add a healer preset under `configs/tactics/`.

2026-10-06 status: **host contract reviewed; guarded policy self-Cure research proven; public recovery open**. Schema v2,
the healer preset and 119 host checks are reviewed. The preset now names Life
and Cure, excludes KO from Cure, and applies the MP reserve to Life too;
enabled kind-only item rules require opt-in. See
[`A6.json`](receipts/autobattle/A6.json). Self-Cure now heals 100→163 HP and
spends 6 MP; a five-MP negative control rejects selection without resource
changes. MP-cost semantics match 2,429 executed retail-function cases. See
[`a6-recovery-research.md`](a6-recovery-research.md). The pinned modal reader and state-driven research executor now join active
target-processor ownership to canonical actor identity before policy-driven
confirmation. MP6 is enabled by the engine but declined by the eight-MP
reserve; guarded cancellation preserves resources. Guarded facing research now
confirms Wait and joins two subsequent enemy actors after roster restoration;
fourteen reader controls and nine receipt mutations reject wrong ownership.
The ROM facing branch passes 1,024 input cases. State-driven policy-decline
Wait research now passes reserve/insufficient-MP reloads, a live facing STOP
control and fifteen host flow checks; retained receipts reject thirteen mutations
each. Guarded successful-Cure turn finishing is now exercised independently;
see the research notes and receipt for accepted reloads and its passive-only
settling retry. Next dependencies: public-runner integration and ally/KO targeting. The
roster is scratch during targeting; do not bypass identity rejection or
substitute a fixed research route for an adapter.

- [ ] Trace missing item-count/MP consumers only as required by concrete rules; document the evidence in `docs/tactics-policy.md`.
- [ ] Add heal-under-threshold, revive-before-attack where a legal revive candidate exists, MP reserve, and never-use-item rules. Consumables default to disabled.
- [x] Test exact threshold boundaries, zero max HP, KO vs living targets, insufficient MP, no revive ability, and the last consumable (host contract only; 119 checks).
- [x] Replay a wounded-party fixture and compare its chosen actions to a damage-focused policy (A6.3 bounded ally Cure versus declined Cure/fallback Wait; no attack claim).

Done: the rule changes the executed action, consumes the expected resource, and explains fallback when unavailable. Do not invent a heal/revive candidate that the engine rejected.

#### A6.1 — Integrate the bounded self-Cure path before widening targets

Prerequisite: accepted current-source successful-Cure/Wait continuation reloads
in `A6.json`, plus the policy-decline/STOP receipt. Keep their fixture limits.
This is an integration packet, not closure of the wounded-party/ally/KO gates.

Transport prerequisite has bounded research evidence (2026-10-07): scoped
explicit halts, strict hook acknowledgments, complete modal raw ledgers and
restored real sequencer tracing after guarded Cure/Wait reloads. Command opening
states reject input and permit bounded passive retry. See `A6.1.json` and A6
research notes. Accepted 2026-10-07: the public opt-in integration passes its
six-case matrix and both source-pinned STOP/manual/same-PID handoffs. Manual
continuation proves Wait; resume proves the established Move/Wait path, not
an additional resumed Cure. One earlier resumed Cure healed but could identify
only one later enemy, so its continuation remains unknown with zero verified
turns. See the retained failures and exact source hashes in `A6.1.json`.

- Reuse `RecoveryMenu`, `SelfCureExecutor` and `WaitFacingExecutor` through
  `BattleRuntime._drive_player_boundary`; preserve the existing fresh-owner
  adapter. Never call its fixed-roster revalidation while targeting borrows
  that storage. The canonical modal pin owns only the validated interval.
- Extend `TacticsAdapter` deliberately: navigation/engine acceptance must
  establish Cure legality before it becomes a chooser candidate. Do not
  advertise learned Cure, item counts or generic ability targeting. Keep
  unsupported actor/job/target shapes fail-closed and Move/Wait regressions.
- Add runtime event fields explicitly to `EVENT_SCHEMA` and CLI receipt input
  hashes. Record exact chooser snapshots, canonical actor/target, six-MP cost,
  consumed Action, separate Wait confirmation and independent continuation.
  Missing fields must fail receipt validation rather than disappear silently.
- Reconcile Probe router tracing with the recovery observer's explicit halts;
  do not copy the research probe's disabled tracing into the public runtime.
  Restore required tracing only after the terminal input latch, without
  introducing another gameplay key or accepting an unsolicited stop packet.
- Translate `RecoveryStopped` to the existing paused lifecycle. Preserve raw
  writes across all modal legs and never retry an ambiguous final input. Keep
  research fixture edits and screenshot subprocesses outside the public action
  executor. STOP during targeting/facing must leave the live process usable.
- Run the real public CLI on an owned constructed fixture: accepted Cure,
  reserve decline, engine-disabled Cure and no-match/disabled fallback; then
  STOP before Cure confirmation and before Wait facing confirmation. Inspect
  screenshots, reject post-terminal/raw-input mutations, and prove manual
  continuation plus same-PID resume under the worker contract. Host-only tests
  and standalone probe receipts cannot close this integration gate.

Then continue A6's wounded-party policy comparison and ally/KO/resource facts;
keep item execution disabled until engine inventory/availability is proven.

#### A6.2 — Identify one living ally target before public party recovery

Prerequisite: A6.1's bounded public gates pass. Start with read-only target
research on a disposable copy of `a4-multi-ally-battle-start.ss0`, using the
`a4-two-player.json` eight-unit guard and the existing fresh-owner adapter.
This is a new fixture/target scope; seven-unit self-Cure acceptance does not
clear its actor, targeting or continuation gates.

Ownership: add a separate research probe and read-only target decoder/tests;
keep `RecoveryMenu`'s self-only peer/target rejection and public opt-in bounds
until the new target contract is independently proven. Record exact sources,
fixture changes and binary-capture hashes; raw RAM/states remain local.

Acceptance (2026-10-07): bounded target contract PASS. Two fresh research
Cure/Wait reloads independently reach Schneider/id3; live STOP and reserve
refusal pass. Context peer stays the caster; processor+8 independently joins
the accepted ally. Explicit target/disabled-row controls pass13 cases. The
preview uses a cached name bitmap; its earlier draw remains unknown, while
canonical and UI-payload identity agree. See `docs/a62-ally-target-research.md`
and `A6.2.json` for exact scope. Public integration is not cleared by research.

- Pin the caster and one living wounded ally by canonical name/id, job/race,
  side, maxima and tile. Verify both battle mirrors before entering targeting;
  never use the borrowed roster as an identity lookup during the modal interval.
- Observe target cursor movement, target-processor/controller state, canonical
  target references and accepted final confirmation. Derive the target from
  the observed fields; do not assume the self-Cure `peer` field means the same
  thing for another unit. Stop before final input while any join is unknown.
- Prove that the engine accepts that other ally for Cure. Only then add a
  bounded guarded research confirmation. Require the caster to spend exactly
  the decoded MP cost, the intended ally to heal, and the caster and other
  allies to retain their own HP. Guarded Wait and independently attributed
  continuation remain separate proof obligations.
- Require two fresh guarded reloads and negative controls for wrong identity,
  stale target/tile, cross-side or KO target, disabled ability, changed MP and
  missing final policy. Coherent aliasing of two same-job allies must reject.
  No final-input retries after ambiguous delivery, STOP or terminal facing.
- Host/retained decoder checks may clear a reader prerequisite, not live
  targeting or public party recovery. Keep PASS/FAIL/UNKNOWN per obligation.
  Only after the target contract passes should a later integration packet
  expose that bounded ally candidate through the public policy adapter.

Next integration comparison: replay the same wounded-party fixture with the
healer policy versus the damage preset, reporting only candidates actually
offered. A damage preset falling back to Wait is not a demonstrated attack.
Revive/KO, item inventory and broader tactical quality remain later A6 gates.

#### A6.3 — Bounded public ally-Cure integration

Prerequisite: the A6.2 target contract above. Keep the public self-only flag
unchanged; add a mutually exclusive opt-in for the exact eight-unit wounded
party family, with schema2 policy required. Pin both canonical/mirror allies
before targeting and use the independent final target reader for candidates.

- Route the candidate through the public tactics adapter and re-evaluate
  after observations. Record target/resource facts, raw input and fresh
  source hashes in the public journal. Unsupported caster/party fails before
  input; unexecuted policy results cannot count a turn.
- Require two fresh public casts with attributed ally HP, exact caster MP,
  unchanged other party HP, guarded Wait and independent next enemy. Compare
  healer versus damage preset on the same fixture; fallback Wait is not attack.
- Exercise STOP at Do-it and facing, manual handoff and same-PID resume;
  no post-STOP or post-terminal input. Retain raw ledgers and adversarially
  reject missing logs, wrong target, stale policy and false effect/continuation.
- Re-run the accepted seven-unit self-Cure matrix and ordinary Move/Wait
  regressions. Research receipts do not substitute for these public gates.

Status: PASS within the exact eight-unit fixture (2026-10-07). Two public
casts heal target100->157/153 with caster85->79MP; both stop/manual/resume
cases and all named regressions pass. A6 broader KO/item criteria remain open.

#### A6.4 — Bounded KO/Life target research

Prerequisite: A6.3. Follow `docs/a64-ko-target-research.md` and initialize every
required criterion in `docs/receipts/autobattle/A6.4.json` as UNKNOWN. First
prove genuine engine KO lifecycle and independently reload a disposable
fixture. Keep living-only pins/Cure readers unchanged. Observe enabled Life,
effective MP cost and canonical KO-target acceptance before a guarded final
input; require two attributed revivals, separate Wait/continuation, STOP,
reserve and adversarial controls. Public revive integration is a later packet.
Read-only table Life ID5/base cost10 is metadata, not target/availability proof.


### A7 — Movement tactics (P1, bounded research then implementation)

Depends on A1/A5. Reuse `tools/trace_turn_march.py`; create `tools/probe_movement_policy.py` and `docs/movement-policy.md`.

- [ ] Observe a real approach walk, locate candidate destination selection, and distinguish reachability, placement rendering, live record state, and turn-end synchronization.
- [ ] Prove one control at a time: approach-to-attack, hold position, then preferred range if the candidate interface supports it. Add only proven controls to A5's schema.
- [ ] Test occupied tiles, height differences, blocked paths, Immobilize, unreachable enemies, and no legal attack from the selected tile.
- [ ] Record action destination and actual committed destination over two turns; prove a failed preference falls back legally rather than hanging.

Done: at least approach and hold produce contrasting legal movement on the same fixture. Kiting, hazard avoidance, and formation behavior remain later work unless supported by this evidence.

### A8 — Adjustable battle speed (P1, independent after A3)

Worker re-entry rule: read the receipt and `docs/autobattle-speed.md` before
running any probe. Pick a genuinely new supported emulator/host mechanism;
retain the pre-registered 1.30x separation gate and timestamped frame/wall-time
measurement. Repeating inert flags is not progress. If no available mechanism
can be tested, report that dependency and continue A5 work. Do not relax A8/A9
acceptance, promise an accelerated setting, or introduce ROM timer/animation
changes to close this packet without a separately scoped design.

Modify `tools/run_autobattle.py`; create `docs/autobattle-speed.md` and extend runtime validation.

- [ ] Inspect the installed emulator's supported acceleration mechanism; expose normal speed and a verified accelerated setting without changing CT, damage, or game timers in ROM.
  (2026-10-05: inspect half COMPLETE and quantified — full mechanism matrix plus probe v12's timestamped free-run brackets: the single existing speed runs at **0.87–0.97× GBA nominal** on this host (slightly UNDER real time — the earlier "always accelerated/unthrottled" reading is refuted), fpsTarget/fastForwardRatio/FF-hotkey/audio inert on this Qt build, videoSync=1 bounded to best-case 1.11× separation (below the 1.30× gate), mgba-sdl has no stub. Expose half OPEN — no tested mechanism selects normal (1x) or a controlled multiplier; product acceptance row `expose-normal-and-accelerated-setting` = unknown in the receipt.)
- [x] Keep takeover responsive and restore the previous speed on stop where possible.
  (2026-10-05: takeover responsiveness proven live with DURABLE artifacts — a8-resp2 executed this round under outputs/autobattle/a8-takeover-resp2/: STOP dropped on turn 1 (mid-recharge), final_state=paused, emulator survived the real CLI cleanup path, and input-log.jsonl proves ZERO automation key writes after stop_requested; screenshots retained. Restore-on-stop moot: one speed (0.87–0.97× nominal, v12); execution stops with the run — the detach law is the pause primitive. Round-9 reconciliation stands: leave-running hands over a PAUSED battle; continuation requires a monitoring client (the C3 manual-layer pattern), recorded as receipt row `handoff-continuation-requires-monitor-client`.)
- [ ] Measure wall-clock duration, emulated frames, input count, and outcome from the same starting state at both speeds; repeat three times per setting.
  (2026-10-05: OPEN as a product criterion — only ONE speed exists on this host, so no two-speed comparison is possible (receipt `equivalent-outcomes-at-both-speeds` = unknown). The measurement methodology is now complete and baseline-free: probe v12 measures the same definitional event on two independent timestamped channels — traced frames (N = 1126–1190 pooled across boots, park 296 verified, end ≥998, per-stop epochs) and free-run wall brackets (D = 20.5–21.5 s, cont/read windows with drain_paired pairing proof, start/end samples retained with absolute epochs; laws DE-028/DE-029) — giving fps 52.5–58.0 (0.87–0.97× nominal). The earlier Lua emu:currentFrame calibration is WITHDRAWN (console channel dead, DE-024). Re-opens automatically if a second speed is achieved.)
- [x] Verify no missed turn transitions, modal overrun, or additional tactical input is required. Publish actual speedup, including any tracing overhead.
  (2026-10-05: published honestly from v12: the actual speed is **0.87–0.97× nominal — no speedup exists** (bracketed, timestamped, baseline-free), and the tracing overhead is published separately (traced cycle 18.5–18.7 fps = stop-reply transport bound ≈ 3× wall vs free-run). All earlier numbers withdrawn: the v1 "4.1×" (divided by a derived ~54 s prediction), the v2 Lua-channel calibration (dead console, DE-024), the 13.21 s stability table (predates start-CT gating + frame counting), and the whole-battle conversion of the C3 ~14.8-min run into "~60 min of hardware time" (traced/untraced mixture, unmeasured). No runtime change made — the runtime classified identically at both fake speeds offline.)

Done: measurable battle-time reduction with equivalent game progression is NOT achievable on this host as things stand — there is one speed and it is ~0.9× nominal. Animation-skipping ROM patches are deferred until emulator acceleration is measured and insufficient (now measured: any future lever must come from the emulator host/config or ROM-side animation skips).
(2026-10-05, round-10 close: A8 is NOT closed as a product packet. Status: investigation complete, product acceptance open — the speed law is measured on timestamped two-channel evidence with no baseline assumption, but no selectable normal/accelerated setting exists on this host and two-speed equivalence is therefore unproven. The path on a suitable host is documented (60 Hz monitor + videoSync=1).)

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
> A5's subpackets and later unlocked work without waiting for review when their criteria pass. Report observed
> facts and unresolved criteria; never replace a criterion with a weaker proxy.

## Deferred work

Map seams/metatile naming, further matching for its own sake, mission-table expansion, automated grinding outside battles, native hardware packaging, advanced formation tactics, and a polished editor before the runtime contract. Reopen these only when they directly unblock the milestones above.
