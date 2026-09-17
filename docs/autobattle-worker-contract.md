# Auto-battle worker acceptance contract

Applies whenever a worker implements, validates, or closes an auto-battle
packet. The roadmap owns priority and status. This file owns completion rules.
The project log owns dated observations. Resolve conflicts by checking the
current implementation and evidence; leave historical entries intact and add
a correction. A checkbox or a tool's `PASS` label is not independent evidence.

## Execute without a review loop

1. Inspect `git status --short` and the current revision. Read `CLAUDE.md`, the
   roadmap's current packet, and its named references. Record prerequisite
   evidence and preserve unrelated changes. Inspect launchers before running.
2. List the packet's required criteria in a receipt, initially `unknown`.
   For a defect, reproduce it before editing and preserve that failing case as
   a regression. Define expected observations before changing the implementation.
3. Implement the smallest complete behavior. Exercise the real public entry
   point for integration claims; replace external hardware/processes in offline
   tests, not the cleanup/state-machine functions being tested.
4. Run positive and negative checks below. Fix failures and rerun affected
   checks. A mocked engine can test transport behavior; ROM semantics require
   independent accessor/trace or live evidence. Altering a fake to emit expected
   target/MP values is not proof that those fields mean that in the game.
5. Inspect raw receipts and required screenshots. Compare the exact observation
   to every criterion. Record `pass`, `fail`, or `unknown`; required unknowns
   block completion. Keep good partial results without marking the packet done.
6. Perform a final adversarial pass: attempt cancellation at the worst time,
   invalidate the actor record, inject a misleading enemy effect, and corrupt
   a receipt. For each applicable case, prove the guard actually rejects it.
7. Update the living status and append a concise log entry. Commit owned files
   with revision-linked evidence; continue to the next unlocked packet within
   the assignment. Routine closure needs no additional approval.

Tests should verify the observable contract, not helper names or incidental
implementation. Run each new regression against the pre-fix code where practical
and record why it fails. Broaden testing only for changed behavior or unresolved
risk; documentation-only changes need link/diff checks, not a live battle.

## C1: cancellation and handoff acceptance

Cancellation has a precise boundary: record `stop_requested` when STOP is
observed. From that point, zero further gameplay key injections are allowed.
Releasing a held key and restoring owned state are permitted cleanup operations
and must be labeled separately. Poll before every new key injection, at each
route/recovery step, and within blocking progress loops. Use bounded transport
reads so STOP is observed within two seconds outside an already pending OS or
transport call; record any such call's explicit timeout as a latency limitation.
A successful action wait does not cancel an already latched stop request.

| Case | Required observation |
|---|---|
| STOP before first input | No gameplay input; paused receipt |
| STOP during initial progress wait | Wait exits; zero recovery B/route writes after observation |
| STOP between route keys | Remaining keys are suppressed |
| STOP during B recovery | Remaining recovery inputs are suppressed |
| STOP during supplemental evidence wait | Cancellation propagates to paused state |
| STOP coincides with progress | Cancellation wins; no new turn starts |
| CLI leave-running | Actual CLI/finally/`__exit__` keeps owned PID alive, disarms owned hooks, releases keys, and detaches/resumes appropriately |
| CLI kill | Actual cleanup terminates only the owned process |
| Guard failure/disconnect | No further gameplay input; truthful terminal reason and receipt; cleanup attempted where transport permits |
| Live handoff | Emulator survives cleanup and a manual player command visibly works |

The regression must run through `run_autobattle.main` and real session cleanup
code for CLI claims. A test stopping at `BattleRuntime.run` misses `__exit__`.
Use timestamped input-write logs to check ordering, not just the final state.
For C3, also prove automation can resume the same live battle after the manual
command. A fresh load proves repeatability, not resume.

## C2: valid state and causal action acceptance

A candidate is engine-legal only when the engine's availability/acceptance path
supports it in the current state. Learned abilities alone do not establish
range, MP, status, target, or law legality. The small selector may use one
verified action and a narrow fixture; broad policy coverage is not required.

An accepted action receipt must establish:

- Stable actor identity and the correct live record at selection and execution.
  Record the source pointer and validity interval. Validate against independently
  established roster/map/stat bounds. Invalid snapshots remain unknown and
  prevent input; fallback input is not a remedy for an unreadable state.
- A verified command ID or engine operation with known non-Wait semantics,
  plus target identity/destination where applicable, selected before execution.
  Keep requested action separate from engine-observed executed action.
- An actor-associated execution event or decoded action record linking that
  selection to acceptance and turn completion. Global seed count, CT changes,
  a generic submenu route, or an unchanged recent-target byte is insufficient.
- If effects support the proof, establish their causal relation to that actor's
  action: validated pre/post snapshots across the execution boundary and the
  expected affected target. An enemy's action or an unrelated unit's movement
  does not prove a player command. Unknown field semantics cannot be cured by
  plausible-looking values. HP 319→2313 with suspect decoding is invalid proof.
- Two reload-based demonstrations with commands, hashes, actor/action/target
  evidence, and inspected visual confirmation. A verified numeric command ID
  is enough; display-name decoding is not a completion dependency.

Required negative controls: Wait-only progression; enemy-only HP/MP/movement
changes; stale unchanged target; invalid/transient actor pointer; out-of-bounds
stats/coordinates; unavailable selected action; and CT-only progression. Each
must fail the non-Wait proof or produce an explicit unknown/fallback result.
None may acquire a successful execution label merely because a route was sent.

## C3: integrated runtime and receipt acceptance

Reuse valid historical evidence for unchanged components, naming its revision
and limits. Run final live integration on the current behavior; if subsequent
changes affect input, actor decoding, cleanup, or end detection, rerun the
affected live path. No full ROM rebuild is needed for transport-only changes.

The complete-battle receipt must contain fixture/ROM/emulator identity, exact
command, run ID, start/end observations, actor/action evidence, input count,
terminal reason, and outcome. Verify the visible result screen or an independently
validated engine-end flag. A silent CT vector alone is not a universal end flag.
Stop at battle results; world-map input is outside scope. Defeat is an acceptable
outcome. The live suite must also cover C1 handoff and same-battle continuation.

The offline receipt gate must reject:

- Gameplay input after observed STOP or terminal stop, even if no matching
  high-level event was emitted. Cross-check raw transport/input logs.
- Invalid lifecycle order, duplicate terminal events, and action events without
  the corresponding actor boundary. Validate every turn, not only the first.
- A `completed` claim with only a timeout/stall observation.
- An executed action claim with missing, unrelated, stale, or invalid evidence.
- Inconsistent run/event/actor identifiers or counts, and reused run directories
  that silently append old events. Reuse must reject or explicitly isolate runs.
- Missing guard-failure/disconnect receipts and omitted stop reasons.

Simulated cases may certify control flow and rejection behavior only. Keep
fixture observations separate from fake-engine assumptions in test descriptions.
Before closure, all applicable failure cases and the live requirements must pass.

## Evidence and completion record

Use one metadata-only receipt per packet, e.g.
`docs/receipts/autobattle/C1.json`. Extend the existing validator or add a
focused packet validator as needed; these packet receipts are not yet an
implemented command. The worker supplies and verifies the exact CLI command
in the receipt. Keep large raw output/screenshots local under a unique run ID;
commit hashes and concise excerpts sufficient to audit the claim without ROM
or extracted game bytes. Verify JSON artifacts contain no bulk memory dumps
before committing them. Record unavailable local artifacts explicitly.

Required receipt shape (values below are illustrative):

```json
{
  "packet": "C1",
  "base_revision": "<sha>",
  "tested_revision": "<sha or base plus patch hash>",
  "status": "unknown",
  "criteria": [
    {
      "id": "stop-during-progress",
      "status": "unknown",
      "command": "<exact reproducible command>",
      "expected": "zero gameplay writes after stop_requested",
      "observed": null,
      "evidence": [],
      "negative_control": "pre-fix runtime emits B plus route"
    }
  ],
  "live_runs": [],
  "limitations": [],
  "next_packet": null
}
```

Every required criterion must be present, including failed cases. The final
summary states what behavior works, what was tested now, any reused historical
evidence, and the next unlocked packet. Acceptance depends on observations,
not the packet validator's label alone. If evidence changes a claim, correct
the living docs in the same change; retain the failed run for diagnosis.
