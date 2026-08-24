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
| Active phase | Phase 5 — AI condition space |
| Current work package | AI5.1 — expand unit-status and stat naming from behavioral readers |
| Last closed package | AI5.1a — Speed Down, Sleep, Slow, and Haste status joins |
| Baseline | 172 matched functions / 4,536 bytes; byte-identical 16 MB rebuild |
| Core gates | `make check` 172/172; AI 8/8; missions 13/13; maps 14/14; items 8/8; statuses 6/6; matching ROM SHA1 |

## Prioritized backlog

| ID | Priority | State | Work package | Definition of done |
|---|---:|---|---|---|
| M2.1 | P0 | Complete | Name caller-backed mission computed/packed properties | All 50 constant-property call sites are assigned to named, validated families; seven variable-id calls remain numeric |
| M2.2 | P0 | Complete | Name mission-index `+0x00/+0x01` | Ordering/grouping role is proven by an identified reader; CSV names and a check are added |
| MAP3.1 | P1 | Complete | Decode map tile arrangement `+0x04` | Dump/apply round-trips and map 0's two-layer layout is anchored against its 14x14 terrain grid |
| MAP3.2 | P1 | Complete | Characterize map block `+0x08` | The clipping loader/consumer are identified and a guarded descriptor edit round-trips |
| MAP3.3 | P1 | Complete | Decode custom-LZSS map graphics | All 50 unique streams match the retail decoder and malformed data is rejected |
| MAP3.4 | P1 | Complete | Characterize animation blocks and mode bytes | Readers name the controls and reproducible exports cover all present blocks |
| ITEM4.1 | P2 | Complete | Name item `+0x0d/+0x0e` and remaining `+0x0c` bits | Icon paths execute end to end; behavioral flags have readers; hand bits have explicit population evidence; CSV round-trips |
| AI5.1 | P2 | Active | Expand unit-status and stat naming | Each new name has a behavioral or execution anchor |
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
| M2.1g | 2026-08-24 | Named four hidden item/law-card reward-preview flags and closed the constant caller sweep | 2,048 accessor reads; live visible/hidden formatters; dormant branch injection |
| MAP3.1 | 2026-08-24 | Decoded sparse two-layer arrangement runs and corrected the terrain packed-run codec | `validate_maps.py` 6/6; two byte-identical CSV round-trips; compressed/raw edit anchors |
| MAP3.2 | 2026-08-24 | Identified and exposed the two-layer clipping tilemap at `+0x08` | `validate_maps.py` 8/8; loader/visibility readers; byte-identical and edited round-trips |
| MAP3.3 | 2026-08-24 | Corrected the Huffman assumption and decoded custom-LZSS 4bpp graphics | 50/50 retail byte matches; malformed-input rejection; 162-row/50-file export |
| MAP3.4 | 2026-08-24 | Decoded animation metadata/frames, corrected `+0x1c`, and executed render-mode selection | maps 14/14; 83/28 animation coverage; 324 mode selections; 124-frame export |
| ITEM4.1 | 2026-08-24 | Named icon graphics/palette and all eight item flags; closed Phase 4 | `validate_items.py` 8/8; 7,144 accessor loads; 375 icon paths; executed price boundary; byte-identical/edit round-trips |
| AI5.1a | 2026-08-24 | Joined Speed Down, Sleep, Slow, and Haste to unit bits and application cases | `validate_statuses.py` 6/6; executed getter/setters, speed shifts, Sleep accuracy, and independent naming anchors |

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

### D-014 — Close the constant mission-caller sweep and advance to maps

- Properties `0x3d..0x40` hide two generated item and two law-card reward
  preview slots behind `????`. The second law-card flag is dormant in retail
  but its injected formatter path executes.
- Naming remains behavioral: published examples correlate hidden slots with
  random rewards, but the formatter proves concealment rather than generation.
- The repaired report contains 57 call sites: 50 have recoverable constant
  property ids and every one now belongs to a named family. The remaining seven
  pass variable ids and do not justify names for positional fields by themselves.
- Decision: mark M2.1 complete at the high-confidence caller boundary and move
  to MAP3.1. Reopen variable-id mission research only when a modding goal gives
  it a concrete payoff.

### D-015 — Treat arrangement and terrain as separate packed coordinate systems

- Arrangement begins with a metatile-definition pointer and then sparse
  destination/count runs. Destinations place 16x8 visual metatiles on two
  32x64 layers; ids are 16-bit on 121 logical maps and 8-bit on 41.
- Terrain is also a sparse run stream, not the flat pair array the first tool
  assumed. Its destinations address two-byte gameplay cells on a 16-column
  grid. Map 0 is 14x14 with 196 explicit cells, not 228.
- The earlier height values above 127 and nine "undecodable" maps were decoder
  artifacts: packed headers were read as cells and redirects were skipped.
- Decision: one shared resolver handles compressed, uncompressed, and redirect
  forms; both apply paths preserve record topology and refuse growing blocks.

### D-016 — Name `+0x08` from its runtime buffer and consumers

- `sub_0801F2EC` resolves table `+0x08`, decompresses it, clears the
  `0x2000`-byte destination at `0x0200D1A0`, and invokes the sparse-halfword
  expander `sub_0801EFB0`.
- Destinations cover two 32x64 halfword layers. Render/occlusion code reads
  both halves, and the consumer at `0x0801D7A8` tests entries for visibility.
- Decision: call it the clipping tilemap, agreeing with the independent editor,
  while keeping each payload named only `tile_descriptor` until graphics
  decoding proves more detailed bit semantics.

### D-017 — `0x20`/`0x22` graphics are custom LZSS, not BIOS Huffman

- The retail map loader passes wrapper `+4` or `+8` to `sub_0800543C`. The
  inner stream begins with a big-endian decompressed size and uses six custom
  token families, matching the independent FFTAUtils decoder.
- The new strict Python decoder matches all 50 unique retail outputs exactly;
  all outputs are whole 32-byte GBA 4bpp tiles.
- Decision: export decoded graphics now, but do not add an apply command until
  a compatible encoder and original-allocation guard exist.

### D-018 — Separate animation pointers, VRAM destination, and render modes

- `+0x14` metadata supplies byte count, frame count, duration, and source-tile
  indices; `+0x18` points to raw 4bpp frame tiles.
- `+0x1c` is the DMA destination `0x06000020` on all 83 animated maps, not a
  third relative pointer. The table exporter now treats it accordingly.
- `sub_0801DB98` selects `+0x54` in the primary state and `+0x55` in the
  alternate state. `+0x56` is consumed as a shared-palette index; `+0x57` is
  reserved zero.
- Decision: close Phase 3 with decode/export coverage. Editing compressed
  graphics remains withheld until a compatible encoder exists.

### D-019 — Keep ability effects and status application cases separate

- The ability table's raw effect id selects effect metadata and is not the
  status handler table index.
- The application table at `0x083A87B4` has 92 twelve-byte records; its
  one-based cases 20, 37, 51, and 52 join to the setters for Speed Down,
  Sleep, Slow, and Haste respectively.
- Decision: name a status only from its handler join plus independent runtime
  behavior. Do not infer equality between the two numeric namespaces.

## Risks and controls

| Risk | Impact | Control |
|---|---|---|
| Plausible values are mistaken for semantics | Incorrect modding API becomes durable | Require an identifiable reader and preferably execution evidence |
| Documentation drifts from tools | Future sessions repeat closed work | Update docs, roadmap, project log, and code in one commit |
| ROM revision mismatch | Offsets and hashes become invalid | Keep the USA SHA1 gate; never commit ROM bytes |
| Generated CSV applies unintended bytes | User ROM is corrupted | Require unedited round-trip equality and single-field diff checks |
| Live trace is generalized beyond its scope | AI claims become overstated | State the exact mission/turn/path covered by each trace |

## Session log

### 2026-08-24 — First behavior-backed status batch

Objective:

- Begin AI5.1 by naming status bits from executable consequences and their
  retail application handlers.

Completed:

- Added a shared status-name registry consumed by `tools/flag_map.py`.
- Joined Speed Down, Sleep, Slow, and Haste to their unit bits, setters, and
  one-based application cases.
- Added a standalone six-check status validator and corrected the turn-order
  and item-speed documentation to include all four speed-affecting states.

Evidence recorded during the batch:

- All 92 application-table entries are executable Thumb handlers at a
  12-byte stride; cases 20/37/51/52 call the expected setters.
- All four getter/setter pairs clear and set their unit bits in execution.
- With base speed 100, Speed Down, Sleep, and Slow return 50; Haste returns
  200; Slow plus Haste returns 100.
- Sleep raises a synthetic ordinary hit chance from 95 to 100; Speed Down
  independently selects the red stat-display palette.

Next action:

- Continue AI5.1 at the per-turn status processor to identify Poison from HP
  loss, then propagate that name through the same handler/bit registry.

### 2026-08-24 — Item icons, flags, and Phase 4 closure

Objective:

- Name item `+0x0d/+0x0e`, resolve the `+0x0c` bitfield, and make the claims
  executable rather than distribution-only.

Completed:

- Traced `+0x0e` through the sprite constructor to the resource-pointer table
  and named it `icon_graphics`.
- Traced `+0x0d` through the object setter/getter to OAM attribute 2 palette
  bits and named it `icon_palette`.
- Named bit 3 as discount eligibility, bits 4–6 as cumulative shop tiers, and
  bit 7 as the Mythril/consumable special pool from direct retail readers.
- Classified bits 0–2 as dual-wield, one-handed, and two-handed rules. Bit 1
  has a direct equip-validator reader; bit 0/2 remain explicitly marked as
  exact population classifications rather than isolated-reader proofs.
- Added a standalone eight-check item gate and renamed the CSV columns.

Evidence recorded during the batch:

- All 7,144 item-accessor loads match raw fields; all 375 real items resolve
  their graphics pointers and round-trip their palette selector.
- The renderer adds object byte `+0x1d` to OAM attr2 bits 12–15.
- A forced 2% discount returns 294 gil for the Shortsword with bit 3 set and
  300 gil when only bit 3 is cleared.
- Unedited CSV application is byte-identical; editing both icon fields changes
  exactly two bytes and both are returned by the retail accessor.

Next action:

- Start AI5.1 with behavioral unit-status readers: prioritize per-turn damage,
  clear-on-hit, and action-prevention sites because they can name status bits
  without relying on data distributions.

### 2026-08-24 — Animations, render modes, and Phase 3 closure

Objective:

- Characterize animation blocks and mode bytes, then decide whether the map
  phase is complete.

Completed:

- Added animation metadata/frame decoding and indexed raw 4bpp export.
- Corrected table `+0x1c` from a relative pointer to the absolute VRAM DMA
  destination `0x06000020`.
- Named and executed the primary/alternate render mode selector and named the
  shared-palette index at `+0x56` from its loader.
- Extended the map gate from 11 to 14 checks and closed Phase 3.

Evidence recorded during the batch:

- 83 animated logical maps share 28 metadata/tile sets and 124 unique frames;
  every frame size is a whole 32-byte 4bpp tile count.
- All 324 primary/alternate selections match `+0x54/+0x55`; `+0x57` is zero in
  all 162 entries.
- Animation exports contain 162 index rows, 124 metadata rows, and 124 files.

Next action:

- Resume item-table reader work at `+0x0d/+0x0e` and the unnamed `+0x0c`
  bits, using the same caller/read/round-trip evidence boundary.

### 2026-08-24 — Custom-LZSS map graphics

Objective:

- Decode map-table `+0x00` graphics reproducibly and reject malformed data.

Completed:

- Retracted the GBA Huffman hypothesis after tracing the retail loader to the
  custom decoder at `0x0800543C`.
- Implemented all six custom-LZSS token families with input/output/backref
  bounds and unknown-token rejection.
- Added indexed graphics export: 50 unique `.4bpp` files and 162 logical-map
  rows with source, wrapper, size, tile-count, and hash metadata.
- Extended the map gate from 8 to 11 checks.

Evidence recorded during the batch:

- All 50 unique streams byte-match the ROM's own decoder under ARM7TDMI
  emulation; wrappers split 82 type-`0x20` and 80 type-`0x22` logical maps.
- Four malformed classes are refused: truncated header, unknown token,
  impossible back-reference, and declared-size overrun.
- Map 0 decodes to 14,368 bytes with SHA-256
  `97B4B12A1C4146375C45D3CC31C68FCD45F56CC53BFB8798EB8AE5B6E07061FA`.

Next action:

- Trace animation blocks `+0x14/+0x18/+0x1c` and mode bytes `+0x54/+0x55`,
  then decide whether they form one coherent editing package.

### 2026-08-24 — Clipping tilemap

Objective:

- Identify map-table `+0x08` through retail readers and make one safe edit
  round-trip.

Completed:

- Traced the loader, sparse halfword expander, `0x0200D1A0` destination, and
  zero/nonzero visibility consumer.
- Added `clipping` and `apply-clipping` CSV commands using the shared redirect,
  alias-conflict, and allocation-growth controls.
- Extended the map gate from 6 to 8 checks, including all-map format coverage,
  byte-identical CSV application, and an edited re-read.

Evidence recorded during the batch:

- 156 maps store local LZ77 clipping data; six redirect. All 120,448 logical
  populated entries are halfword-aligned and stay within layers 0/1.
- Map 0 contains 112 runs and 771 descriptors.
- Descriptor `0x0160 -> 0x0161` recompresses to 1,483/1,485 bytes and re-reads
  as `0x0161` through the production parser.

Next action:

- Implement the GBA Huffman graphics decoder for map-table `+0x00`, including
  malformed-input checks and reproducible decode anchors.

### 2026-08-24 — Map arrangement and packed-terrain correction

Objective:

- Decode map-table `+0x04`, correlate a retail map with gameplay terrain, and
  expose a guarded editing surface.

Completed:

- Recovered the arrangement grammar from retail blocks and independently
  checked it against FFTAUtils: four-byte header, sparse placement runs,
  8/16-bit ids, two layers, and a zero destination terminator.
- Added `arrangement` and `apply-arrangement` commands with shared-storage
  conflict detection, raw in-place writes, LZ77 allocation checks, and redirect
  resolution.
- Found and corrected the pre-existing terrain decoder: its decompressed bytes
  are packed runs, not flat cells. The new exporter resolves all 162 maps.
- Added `tools/validate_maps.py` with six independent format, anchor, fit, and
  byte-identical round-trip checks.

Evidence recorded during the batch:

- All 119,749 logical placements are four-byte aligned and occupy layers 0/1.
- Map 0 has 107 arrangement runs and 770 visual placements over a separate
  14x14/196-cell terrain grid.
- Unedited arrangement and terrain CSVs reproduce SHA-256
  `43FC8204C6DCEEE58828AEBC7AF0C72EB807E99F35AD641C8BB0A4FA8B6EDC19`.
- A compressed arrangement edit fits at 2,510/2,511 bytes; a raw 8-bit edit is
  written in place; a 139/137-byte terrain edit is refused.

Next action:

- Characterize map-table `+0x08`, identify its reader and record grammar, then
  give it the same dump/apply/size-guard treatment.

### 2026-08-24 — Hidden reward previews and Phase 2 closure

Objective:

- Resolve the last constant mission UI pair and decide whether the mission
  sweep still outranks map work.

Completed:

- Expanded properties `0x3e/0x40` into their full four-property family:
  hidden previews for two item and two law-card reward slots.
- Added four computed CSV flags with adjacency-preserving setters.
- Executed 2,048 accessor reads, visible/hidden item and law-card formatters,
  and the retail-dormant second-card branch via an in-memory injection.
- Audited the corrected caller report: all 50 constant-property sites are now
  assigned; only seven variable-id calls remain.
- Closed M2.1 and promoted MAP3.1 to the active work package.

Evidence recorded during the batch:

- Unhidden item slot renders Shortsword; hidden slots render `????`.
- Fire Sigil's hidden second-item slot agrees with its published random-item
  reward listing.
- Mission validation: 13/13.

Next action:

- Decode the map tile-arrangement block at map-table `+0x04`, correlate one
  known map against its terrain dimensions, then build guarded dump/apply tools.

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
