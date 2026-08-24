# Project log

Last updated: 2026-08-24

This is the operational source of truth for resuming the project. `README.md`
describes the product, `CLAUDE.md` describes the working method, and
`docs/roadmap.md` describes the long-range sequence. This file records what is
active now, why it is next, the evidence behind decisions, and what happened in
each work session.

## Working agreement

Every material work batch follows the same loop:

1. Read this file and verify the repository/runtime state before trusting it.
2. Select the highest-priority unblocked item. Finish the smallest useful
   evidence-backed slice instead of opening several speculative branches.
3. Form a static hypothesis, then execute retail ROM code or round-trip data to
   verify it whenever possible.
4. Update the relevant tool, documentation, validation, roadmap status, and
   this log together.
5. Run the proportional gates, inspect the diff, commit, and push. A claim is
   not complete until its evidence is reproducible by another agent.

Log entries are append-only except for correcting factual errors. The current
status and backlog tables are living sections and should be kept current.

## Current status

| Item | State |
|---|---|
| Branch | `master`, tracking `origin/master` |
| Active phase | Phase 2 — finish computed and packed mission properties |
| Current work package | Resolve remaining mission UI properties `0x3e/0x40` |
| Last closed package | Mission cancellation rule |
| Baseline | 172 matched functions / 4,536 bytes; byte-identical 16 MB rebuild |
| Core gates | `make check` 172/172; AI 8/8; missions 12/12; matching ROM SHA1 |

## Prioritized backlog

| ID | Priority | State | Work package | Definition of done |
|---|---:|---|---|---|
| M2.1 | P0 | In progress | Name remaining mission computed/packed properties | A reader gives each name behavioral meaning; fields are exposed and execution- or round-trip-validated |
| M2.2 | P0 | Complete | Name mission-index `+0x00/+0x01` | Ordering/grouping role is proven by an identified reader; CSV names and a check are added |
| MAP3.1 | P1 | Pending | Decode map tile arrangement `+0x04` | Dump/apply round-trips and a known map's layout correlates with terrain |
| MAP3.2 | P1 | Pending | Characterize map block `+0x08` | A reader identifies the block and one safe edit round-trips |
| MAP3.3 | P1 | Pending | Implement GBA Huffman graphics decode | Graphics block decodes reproducibly and malformed/growing data is rejected safely |
| ITEM4.1 | P2 | Pending | Name item `+0x0d/+0x0e` and remaining `+0x0c` bits | Each name has an identifiable reader and byte-identical round-trip |
| AI5.1 | P2 | Pending | Expand unit-status and stat naming | Each new name has a behavioral or execution anchor |
| DEC8.1 | P3 | Pending | Match more C functions | Only pull forward when a modding goal requires code changes |

## Closed work packages

| ID | Closed | Result | Reproducible evidence |
|---|---|---|---|
| BASE0 | 2026-08-24 | Reconciled documentation and re-established the green baseline | `make check`; `validate_ai.py`; `make rom` |
| AI1 | 2026-08-24 | Replayed one full Snowball Fight enemy turn with frozen RNG; four target evaluations repeat exactly | `docs/whole-battle-trace.md`; `tools/validate_ai_trace.py` |
| M2.0 | 2026-08-24 | Named gil, AP, item, and dispatch-threshold mission fields | `docs/mission-data.md`; reward anchors |
| M2.1a | 2026-08-24 | Named clan points and all eight clan-skill point rewards at `+0x2a..+0x32` | `tools/validate_missions.py`; `mission_table.py clan-rewards` |
| M2.1b | 2026-08-24 | Named required and blocked dispatch jobs, base pub fee, and the retail-unused item exclusion | `validate_missions.py` 7/7; `mission_table.py job-rules`; byte-identical round-trip |
| M2.2 | 2026-08-24 | Corrected mission index to 256 records at `0x08563A70`; named map-symbol and script-trigger ids | `mission_table.py index`; executed placement and trigger-selection paths; missions 8/8 |
| M2.1c | 2026-08-24 | Exposed packed mission behavior and effective public type at `+0x02` | 1,024 accessor reads; packed edit checks; official-manual type anchors |
| M2.1d | 2026-08-24 | Named availability days, clear-condition code, and clear count | 1,536 accessor reads; published mission anchors; packed edit checks |
| M2.1e | 2026-08-24 | Named required clan skill/level and corrected four reward labels | 1,024 accessor reads; executed Combat 9/10 boundary; published anchors |
| M2.1f | 2026-08-24 | Named the cancellation flag at `+0x41` bit 2 | 512 accessor reads; three executed formatter paths; packed edit check |

## Decisions and evidence

### D-001 — Optimize for modding reach, not decompilation percentage

- Decision: widen the no-compiler editing surface before matching unrelated
  functions.
- Reason: the project exists to make FFTA behavior modifiable; table and field
  discoveries deliver that directly, while a complete decomp would take years.
- Consequence: the roadmap keeps function matching last unless a chosen mod
  requires it.

### D-002 — No semantic field name without a behavioral reader

- Decision: distributions, value ranges, and plausible id resolution can form
  hypotheses but cannot name fields.
- Required evidence: a function must read the value and do something
  identifiable with it, ideally confirmed by executing the ROM's own code.
- Reason: earlier plausible interpretations were disproven by second anchors or
  runtime behavior.

### D-003 — `+0x2a..+0x32` are clan progression rewards

- Static evidence: `sub_08046850` adds `mission[+0x2a + index]` to one of nine
  paired level/progress counters starting at `0x020021B4`; 100 points advances
  the corresponding level.
- UI evidence: `sub_080461D4` labels the first value `Clan Pts:` and renders the
  eight skill levels. The requirement UI's consecutive string entries establish
  the internal order as Combat, Magic, Smithing, Craft, Appraise, Gather,
  Negotiate, Track. The official manual's visual grid is not storage order.
- Execution evidence: `tools/validate_missions.py` performs 4,608 mission
  accessor reads and calls `sub_08046850` for all nine tracks.
- Product consequence: the mission CSV now exposes nine named, directly
  editable progression rewards and has a focused `clan-rewards` export.

### D-004 — Use the generic caller analyzer for mission properties

- Decision: use `tools/accessor_callers.py --target 0x080CE4DC --reg r1`.
- Reason: `tools/field_callers.py` is hard-coded to the job accessor at
  `0x080C8570` and assumes the field id is in `r2`; using it for missions would
  produce irrelevant evidence.

### D-005 — Required and blocked dispatch jobs are separate packed fields

- Required job: accessor property 48, packed across `+0x39` bits 3–7 and
  `+0x3a` bit 0; `sub_080611F0` filters the roster to matching canonical jobs.
- Blocked job: `+0x3c` bits 2–7; `sub_080CF310` returns rating 0 for a matching
  canonical job. Executed anchor: The Match rejects Soldier but rates Paladin
  5 under otherwise-identical synthetic state.
- Product consequence: the CSV exposes computed job codes/names and applies
  edits without changing adjacent packed bits.

### D-006 — `+0x3e × 200` is the base pub information fee

- Static evidence: property 54 multiplies by 200; `sub_080CEC78` applies a
  percentage based on town/turf state before acceptance checks clan funds.
- Execution evidence: unliberated-town pricing changes Herb Picking 200→300
  gil and Thesis Hunt 600→900 gil.
- Scope: this is the pre-modifier fee, not a mission reward.

### D-007 — Preserve the dormant dispatch-item exclusion as validated dead content

- Every retail mission has zero at `+0x3d`, so no retail behavior depends on it.
- The accessor maps an injected raw 7 to item id 382, while the enabled rating
  gate rejects either dispatch item slot when it contains raw 7; disabling the
  gate returns the normal rating.
- Product consequence: expose the safe computed item id for modders, but label
  it dormant and do not invent a retail mission meaning.

### D-008 — The mission index starts at its zero sentinel

- Decision: use base `0x08563A70`, stride 12, count 256. The prior
  `0x08563A7C`/255 model skipped the all-zero record 0.
- Boundary evidence: dozens of Thumb literal loads point to `0x08563A70`; the
  next table begins exactly at `0x08564670`. The only interior base,
  `0x085644FC`, deliberately addresses records 224–255.
- Field evidence: `+0x00` selects the persistent world-map symbol placement;
  the script handler at `0x08123898` scans `+0x01` as its trigger key and then
  selects the record's `+0x02` mission id.

### D-009 — Track argument-register aliases in caller reports

- Problem: the old backward scan searched for any prior immediate assignment
  to `r1`. At `0x08019512`, `movs r3, #0x3e; adds r1, r3, #0` caused the tool
  to skip the real property and misreport an older mask constant `3`.
- Decision: follow zero-cost `mov`/`adds #0`/`lsls #0` aliases backward and
  stop at any other write to the live register.
- Evidence: the regenerated 57-site report now assigns `0x08019512` to `0x3e`
  and `0x080195A2` to `0x40`, while preserving the known `0x30` and `0x36`
  readers.

### D-010 — Separate internal behavior from player-facing mission type

- Decision: expose `+0x02` bits 0–2 as a numeric behavior code, not a guessed
  six-value enum. Expose bits 3–5 plus the behavior-1 override as the effective
  public type.
- Evidence: `sub_080CEBF8` selects the icon assets; the official manual defines
  the corresponding Regular, Non-Battle, Encounter and Free-Area categories.
- Product consequence: modders can safely edit both packed values while the
  tool presents reliable public labels and preserves unknown subtype nuance.

### D-011 — Properties 16–18 are deadline and clear-progress fields

- Property 16 packs a six-bit availability deadline across `+0x0f/+0x10`;
  zero renders as no deadline and nonzero values render as days.
- Property 17 selects the clear-condition label. Retail and published anchors
  establish codes 0–2 as Win battle, Days, and Battles; other codes stay
  numeric rather than receiving speculative names.
- Property 18 packs the associated six-bit count across `+0x10/+0x11`.
- Execution evidence: all 1,536 reads agree with the raw packing, and safe
  setters preserve every adjacent bit. Published Dueling Sub, Watching You,
  Run For Fun, and Hungry Ghost listings agree with the decoded pairs.

### D-012 — Properties `0x2e/0x2f` are the clan-skill acceptance gate

- Property `0x2e` is `+0x38` bits 0–3. Nonzero values index consecutive UI
  labels Combat through Track and select the corresponding clan-state pair.
- Property `0x2f` is a seven-bit level packed across `+0x38/+0x39`.
  `sub_080CEECC` rejects when the selected clan-skill level is lower.
- Execution evidence: Twin Swords rejects Combat 9 and accepts Combat 10.
  All 1,024 accessor reads and boundary setter probes also pass.
- Correction: this independently proves the internal clan-state order, so the
  old `+0x2d..+0x30` reward labels were corrected from Appraise/Gather/
  Smithing/Craft to Smithing/Craft/Appraise/Gather. The bytes and prior
  application tests were sound; only those four semantic labels were wrong.

### D-013 — Property `0x37` controls mission cancellation

- The property is `+0x41` bit 2. Its sole reader is the mission-information
  text formatter's control code `0x13`.
- Set selects `Cancellations Accepted`; clear selects `No Cancellations`.
  Special icon group 3 overrides the flag with `Mission Begins Immediately`.
- Execution evidence: the formatter returns the three distinct retail outputs
  for Wanted!, Snowball Fight, and Pam Le Fey. All 512 accessor reads and the
  packed setter also pass.

## Risks and controls

| Risk | Impact | Control |
|---|---|---|
| Plausible values are mistaken for semantics | Incorrect modding API becomes durable | Require an identifiable reader and preferably execution evidence |
| Documentation drifts from tools | Future sessions repeat closed work | Update docs, roadmap, project log, and code in one commit |
| ROM revision mismatch | Offsets and hashes become invalid | Keep the USA SHA1 gate; never commit ROM bytes |
| Generated CSV applies unintended bytes | User ROM is corrupted | Require unedited round-trip equality and single-field diff checks |
| Live trace is generalized beyond its scope | AI claims become overstated | State the exact mission/turn/path covered by each trace |

## Session log

### 2026-08-24 — Cancellation-rule closure

Objective:

- Resolve property `0x37` from its isolated mission-information reader.

Completed:

- Named `+0x41` bit 2 as the cancellation-allowed flag.
- Added a computed CSV column and a setter preserving the other seven bits.
- Executed all 512 accessor reads and all three formatter outcomes.

Evidence recorded during the batch:

- Snowball Fight: No Cancellations.
- Wanted!: Cancellations Accepted.
- Pam Le Fey: Mission Begins Immediately via the special-group override.
- Mission validation: 12/12.

Next action:

- Resolve properties `0x3e/0x40` from their remaining mission-information UI
  readers, then reassess whether Phase 2 has any high-confidence callers left.

### 2026-08-24 — Clan-skill requirement closure and reward-label correction

Objective:

- Resolve properties `0x2e/0x2f` through their shared acceptance reader.

Completed:

- Named the required clan-skill code and seven-bit required level.
- Added computed CSV columns and safe setters across `+0x38/+0x39`.
- Executed all 1,024 accessor reads and the full Twin Swords acceptance gate.
- Corrected the four middle clan-reward column labels after the requirement UI
  proved the internal state order.

Evidence recorded during the batch:

- Twin Swords: Combat 10; Den of Evil: Combat 25.
- Adaman Alloy: Smithing 15; Ghosts Of War: Track 40; T.L.C.: Magic 25.
- Twin Swords returns false at Combat 9 and true at Combat 10.
- Mission validation: 11/11.

Next action:

- Trace property `0x37` from its isolated UI reader and leave it numeric if the
  presentation path does not establish a concrete player-facing meaning.

### 2026-08-24 — Availability and clear-condition closure

Objective:

- Resolve mission accessor properties 16–18 from their isolated UI readers.

Completed:

- Named the six-bit availability deadline, three-bit clear-condition code,
  and six-bit clear count across their three shared packed bytes.
- Added computed CSV columns and safe setters that preserve adjacent fields.
- Added 1,536 executed accessor reads, published mission anchors, and boundary
  packing probes to the mission gate.

Evidence recorded during the batch:

- Availability anchors span 10, 15, 20, 35, and 40 days.
- Dueling Sub is 3 Days; Hungry Ghost is 10 Days.
- Run For Fun is 1 Battle; Watching You is 2 Battles.
- Mission validation: 10/10.

Next action:

- Resolve the next corrected-caller-report family, prioritizing properties
  `0x2e/0x2f` because their shared requirement reader is already identified.

### 2026-08-24 — Caller-analysis repair and mission-type closure

Objective:

- Resume packed mission properties from the multi-caller report without
  accepting a faulty analysis artifact.

Completed:

- Fixed `accessor_callers.py` to follow register aliases and stop at clobbers;
  two properties previously reported as `3` are correctly `0x3e` and `0x40`.
- Identified `+0x02` bits 0–2 as the internal behavior code and bits 3–5 as the
  public icon group; behavior 1 overrides the icon to Encounter.
- Added editable computed fields for behavior code, icon group, and effective
  public mission type while preserving adjacent bits.
- Added 1,024 executed accessor reads, anchor classification, and setter checks
  to mission validation.

Evidence recorded during the batch:

- Dueling Sub: behavior 0 / Non-Battle.
- The Bounty: behavior 1 / Encounter.
- Free Sprohm!: behavior 2 / Free-Area.
- Herb Picking: behavior 3 / Regular.
- Pam Le Fey: behavior 2 / Special.
- Mission validation: 9/9.

Next action:

- Regenerate and use the corrected caller report to resolve the next packed
  mission family, preferring properties 16–18 because their UI readers are
  small and already isolated.

### 2026-08-24 — Mission-index correction and field closure

Objective:

- Prove the leading mission-index fields without naming them from value
  distributions.

Completed:

- Corrected the table base from `0x08563A7C` to `0x08563A70` and count from
  255 to 256, restoring the omitted zero sentinel.
- Named `+0x00` `map_symbol_id`: availability code uses it to resolve the
  corresponding persistent world-map placement record.
- Named `+0x01` `script_trigger_id`: a script handler scans backward for this
  key, stores the matched index, and selects `+0x02` as the mission id.
- Updated the focused index CSV and added both executed paths to mission
  validation.

Evidence recorded during the batch:

- Exact boundary: `0x08563A70 + 256 × 12 = 0x08564670`.
- Sentinel: record 0 is 12 zero bytes; all 256 mission ids are in range.
- Map-symbol execution: index record 2 resolves symbol 2's injected placement
  17 as zero-based placement 16.
- Trigger execution: script trigger 1 selects index record 1 and mission 30
  (`Wanted!`).
- Mission validation: 8/8.

Next action:

- Resume the remaining mission accessor properties using the generic caller
  report, selecting the smallest multi-caller reader with identifiable state
  or UI behavior.

### 2026-08-24 — Dispatch constraints and pub-fee closure

Objective:

- Continue Phase 2 by resolving the highest-value mission properties with
  identifiable behavioral readers.

Completed:

- Identified property 48 as the packed required dispatch job and normalized
  job codes through `sub_080C93F0`.
- Corrected the prior `+0x3c` interpretation: it blocks a matching dispatch
  job rather than requiring one.
- Identified `+0x3e × 200` as the base pub information fee before turf pricing.
- Characterized `+0x3d` as a dormant dispatch-item exclusion; all 512 retail
  entries are clear, but both item-slot rejection branches execute under an
  in-memory synthetic patch.
- Extended the mission CSV with safe computed fields for both packed job rules
  and the dormant item id, plus a focused `job-rules` export.

Evidence recorded during the batch:

- Job-rule accessor: 1,024/1,024 executed reads.
- Required-job anchors: Dueling Sub/Soldier, Run For Fun/Juggler,
  Clocktower/Gadgeteer.
- Blocked-job execution: The Match Soldier rating 0, Paladin rating 5.
- Base fee accessor: 512/512 executed reads; adjusted-price anchors 300/900.
- Dormant item execution: raw 7 maps to item 382; slot 4 and slot 5 each return
  rating 0; disabled gate returns rating 5.
- Mission validation: 7/7; unedited CSV apply changed zero fields; source and
  output SHA-256 both
  `43FC8204C6DCEEE58828AEBC7AF0C72EB807E99F35AD641C8BB0A4FA8B6EDC19`.

Next action:

- Trace readers of the 256-record mission index at `0x08563A70` and prove the
  role of leading fields `+0x00/+0x01`. If no reader supports a semantic name,
  return to the remaining mission accessor properties rather than guessing.

### 2026-08-24 — Project-management system and Phase 2 continuation

Objective:

- Establish a durable, self-maintaining project log and continue the highest
  priority technical work without waiting for another planning round.

Completed:

- Created this log and made it mandatory resume/update context in `CLAUDE.md`
  and `README.md`.
- Corrected the Phase 2 workflow: the generic accessor caller analyzer is the
  mission tool; the older field-caller script is job-specific.
- Traced the mission `+0x2a..+0x32` block from raw table bytes through
  `sub_08046850` into the clan level/progress state.
- Resolved the nine rewards as clan points plus Combat, Magic, Appraise,
  Gather, Smithing, Craft, Negotiate, and Track points.
- Named those fields in `tools/mission_table.py` and added a focused
  `clan-rewards` CSV command.
- Added `tools/validate_missions.py` so the result is independently
  reproducible by execution.

Evidence recorded during the batch:

- Mission id echo: 512/512.
- Clan reward property accessor: 4,608/4,608 executed reads.
- Reward application: nine of nine tracks reached the matching paired counter.
- Gil/AP anchors: Herb Picking `(600, 40)` and Over The Hill `(28,600, 80)`.
- Mission CSV dump/apply: zero changed fields; SHA-256 remained
  `43FC8204C6DCEEE58828AEBC7AF0C72EB807E99F35AD641C8BB0A4FA8B6EDC19`.
- AI execution suite: 8/8.
- Decompiled-function gate: 172/172 exact objects.
- Full rebuild: 16,777,216 bytes; SHA1
  `4ac05441f4de70a4ec3dd932116346c61b8783d9` (`ROM MATCHES`).

Next action:

- Generate a caller/context report for the remaining constant mission
  properties, select the smallest reader with identifiable UI or state
  behavior, and close the next field family. Prioritize properties already
  used at multiple call sites over dynamic-only properties.

### 2026-08-24 — Whole-battle trace closure

- Reached the opening Snowball Fight from New Game under mGBA automation.
- Captured the live evaluator at `sub_080C32C0`: one enemy actor evaluated four
  distinct targets.
- Froze RNG at `0x12345678`; two exact traces matched at all five checkpoints.
- Restored the original save byte-for-byte and kept trace output untracked.
- Committed and pushed as `6445ee3` (`Trace a reproducible live AI turn`).
