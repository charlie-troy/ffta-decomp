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
| Current work package | Identify the next mission property with an interpretable reader |
| Last closed package | Clan progression rewards at mission `+0x2a..+0x32` |
| Baseline | 172 matched functions / 4,536 bytes; byte-identical 16 MB rebuild |
| Core gates | `make check` 172/172; AI 8/8; missions 4/4; matching ROM SHA1 |

## Prioritized backlog

| ID | Priority | State | Work package | Definition of done |
|---|---:|---|---|---|
| M2.1 | P0 | In progress | Name remaining mission computed/packed properties | A reader gives each name behavioral meaning; fields are exposed and execution- or round-trip-validated |
| M2.2 | P0 | Pending | Name mission-index `+0x00/+0x01` | Ordering/grouping role is proven by an identified reader; CSV names and a check are added |
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
  eight skill levels. The official manual names the displayed order Combat,
  Magic, Appraise, Gather, Smithing, Craft, Negotiate, Track.
- Execution evidence: `tools/validate_missions.py` performs 4,608 mission
  accessor reads and calls `sub_08046850` for all nine tracks.
- Product consequence: the mission CSV now exposes nine named, directly
  editable progression rewards and has a focused `clan-rewards` export.

### D-004 — Use the generic caller analyzer for mission properties

- Decision: use `tools/accessor_callers.py --target 0x080CE4DC --reg r1`.
- Reason: `tools/field_callers.py` is hard-coded to the job accessor at
  `0x080C8570` and assumes the field id is in `r2`; using it for missions would
  produce irrelevant evidence.

## Risks and controls

| Risk | Impact | Control |
|---|---|---|
| Plausible values are mistaken for semantics | Incorrect modding API becomes durable | Require an identifiable reader and preferably execution evidence |
| Documentation drifts from tools | Future sessions repeat closed work | Update docs, roadmap, project log, and code in one commit |
| ROM revision mismatch | Offsets and hashes become invalid | Keep the USA SHA1 gate; never commit ROM bytes |
| Generated CSV applies unintended bytes | User ROM is corrupted | Require unedited round-trip equality and single-field diff checks |
| Live trace is generalized beyond its scope | AI claims become overstated | State the exact mission/turn/path covered by each trace |

## Session log

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
