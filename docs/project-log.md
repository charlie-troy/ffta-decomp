# Project log

Last updated: 2026-08-26

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
| Current work package | AI5.5d — resolve stat `0x00` and classify address regions `+0x34/+0xfc` |
| Last closed package | AI5.5c — named removal counters and saved tile position |
| Baseline | 172 matched functions / 4,536 bytes; byte-identical 16 MB rebuild |
| Core gates | `make check` 172/172; AI 8/8; missions 13/13; maps 14/14; items 8/8; statuses/state 20/20; matching ROM SHA1 |

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
| AI5.1a | 2026-08-24 | Joined Speed Down, Slow, and Haste to unit bits and application cases | Executed getter/setters, speed shifts, and independent naming anchors |
| AI5.1b | 2026-08-24 | Added the raw-effect descriptor join, corrected Sleep to case 45, and named Poison case 61 | `validate_statuses.py` 7/7; five named ability/effect/handler/getter chains execute |
| AI5.1c | 2026-08-24 | Expanded descriptor-backed names to 15 status bits | 15 named ability/effect/handler joins and bit round-trips; four secondary-effect confirmations |
| AI5.2a | 2026-08-24 | Named stat `0x16` / unit `+0x1e` as max MP and corrected the direct-load count | Executed four-field stat reads; restoration clamp at `0x0809308A..C4` |
| AI5.2b | 2026-08-24 | Named stats `0x17..0x1a` as Attack, Defense, Magic Power, and Resistance | Executed stat reads and item-property joins through four combat-total helpers |
| AI5.2c | 2026-08-24 | Named stat `0x1b` as persistent-status flags and bit `0x0800` as persistent Zombie | Zombify descriptor/handler chain; executed live/persistent effective predicate; initializer setter join |
| AI5.2d | 2026-08-24 | Named persistent bit `0x0040` as Yellow Card and corrected the field's overly narrow innate label | Yellow Card descriptor/case-92 join; executed handler write to target `+0x28` |
| AI5.2e | 2026-08-25 | Confirmed Yellow Clip as the exact inverse and held eight other persistent masks numeric | Executed `0x0000 -> 0x0040 -> 0x0000`; complete caller sweep found no unique named joins for the remainder |
| AI5.3a | 2026-08-25 | Named base job, active job, secondary job, level, and experience in the one-byte unit block | Direct accessor reads; executed job switch and EXP award; level-up cap at 50/99 |
| AI5.3b | 2026-08-25 | Named unit type/race and nine damage-resistance fields; closed packed slot 2 | Constructor/job initialization; five executed Fire outcomes; retail Wind/Earth source proof |
| AI5.3c | 2026-08-25 | Named stats `0x1d..0x21` as five equipped-item ids | Direct stat reads plus four combat-total helpers iterating all five slots |
| AI5.3d | 2026-08-25 | Named stat `0x08` / unit `+0x0b` as innate element and closed identity-through-equipment scalar coverage | Jelly Fire initializer; 12 elemental monster families; 31 early/equipment fields named |
| AI5.4a | 2026-08-25 | Fixed the stat extractor's r0-indirect load handling and corrected coverage | 63 scalar loads / 6 address returns; full 69-case numeric layout |
| AI5.4b | 2026-08-25 | Named stats `0x23..0x26` as CT, Speed, CT carry, and Judge Points | Executed Speed/item join; one-unit CT tick; 9/10 JP Totema boundary and decoded UI command |
| AI5.4c | 2026-08-25 | Corrected `+0xd8` from capability state to a status-state array and named ten duration counters | Ten named handler/live-bit/reconciler/counter/stat joins; statuses 10/10 |
| AI5.4d | 2026-08-25 | Named `+0xea` bit 4 as Doom and stat `0x29` / `+0xd9` as its countdown | Executed Checkmate application produces live Doom/count 3; expiry call chain clears battle statuses; statuses 11/11 |
| AI5.4e | 2026-08-25 | Named `+0xeb` bits 6/7 as Immobilize/Disable and stats `0x33/0x34` as their durations | Executed Aim: Legs/Arm handlers; movement mode 5→0 under Immobilize; Disable ability-usability rejection; statuses 12/12 |
| AI5.4f | 2026-08-25 | Named stat `0x36` / `+0xe6` as a shared status link id | Executed Cover copies target unit id 42; dedicated/stat getters return 42; linked-state comparison consumers |
| AI5.4g | 2026-08-25 | Named stat `0x28` / `+0xd8` as the Zombie revival countdown | Executed effective-Zombie reset seeds 3 while blank stays 0; dead-Zombie turn path decrements and schedules revival at zero |
| AI5.4h | 2026-08-25 | Named stat `0x37` / `+0xe7` as packed recent target ids | Executed MRU insertion/promotion/eviction and membership; four action writers join to the AI reader |
| AI5.5a | 2026-08-25 | Named stats `0x39/0x3a` / `+0xf1/+0xf2` as KOs inflicted/suffered | Forced-KO execution zeros target HP and increments actor/target counters 9/11→10/12 |
| AI5.5b | 2026-08-25 | Named stats `0x3e..0x40` as tile X/Y/height and `0x43` as battle-list index | Executed movement-origin copy and two-node list insertion index; range/list consumers preserved |
| AI5.5c | 2026-08-26 | Named stats `0x3b..0x3d` as removal counters and `0x41/0x42` as saved tile X/Y | Executed Wyrmtamer/Parley/Oust outcome accounting, shared purge formula, and live-to-saved X/Y copy; statuses 20/20 |

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

### D-019 — Join ability effects to internal cases through descriptors

- The ability table's raw effect id is not the status-handler index. Each raw
  id selects a four-byte descriptor at `0x08553E70`; descriptor byte `+0x01`
  selects one of the 92 internal cases.
- The application table at `0x083A87B4` has 92 twelve-byte records. Known
  joins are Speed Down 49→20, Sleep 97→45, Slow 104→51, Haste 105→52, and
  Poison 125→61.
- Decision: name a status from the named ability → raw effect → descriptor →
  handler setter chain, plus execution where practical. Never infer equality
  between raw effect ids and internal case ids.

### D-020 — Name one-byte unit fields from state transitions

- Job identity: `sub_080C8C24` writes the selected job to unit `+0x07`, also
  synchronizes `+0x05` for ordinary units, and clears `+0x08` when it would
  duplicate the selected job. A later A-ability lookup reads nonzero `+0x08`
  as the secondary job.
- Progression: `sub_080C9B8C` increments `+0x09`, clears `+0x0a`, and caps the
  pair at 50/99; the award path at `0x080A718E` adds earned EXP to `+0x0a`.
- Decision: expose the five fields as base job, active job, secondary job,
  level, and experience. Keep neighboring `+0x04/+0x06` numeric until their
  broader value domains have equally specific behavioral joins.

### D-021 — Treat the unit array as combat truth for elemental resistance

- Construction evidence: unit `+0x0c..+0x14` is filled as neutral followed by
  job accessor properties `0x0e..0x15`. The resulting element order is Fire,
  Wind, Earth, Water, Ice, Lightning, Holy, Dark.
- Consumption evidence: `sub_0812FE38` loads stats `0x0a..0x12`, indexes the
  array by the ability's element id, and applies codes 0–4. Executed Fire
  outcomes are weak 33, normal 24, nullify 0, absorb -19, resist 11 under the
  same RNG seed.
- Slot-2 boundary: packed job slots 1 and 2 are equal in all 116 entries, but
  the accessor and initializer explicitly read slot 1 twice for unit Wind and
  Earth. No battle path reads packed slot 2 directly.
- Decision: expose the nine unit fields by element and document packed slot 2
  as combat-inert. Do not silently reroute Earth to slot 2 in modding tools;
  that would change retail behavior.

### D-022 — Separate innate element from resistance behavior

- Job `+0x11` / unit `+0x0b` is an element id, not the previously guessed
  `unit_class`. The constructor places it immediately before the affinity
  array; the unit getter exposes it as stat `0x08`.
- Population evidence is exact: only twelve elemental monsters are nonzero,
  using Fire 1, Ice 5, Lightning 6, Holy 7, and Dark 8 consistently with the
  ability element namespace.
- Decision: name it `innate_element_id`, but keep resistance behavior assigned
  to the separate `+0x0c..+0x14` array. Do not imply that innate element alone
  changes damage.

### D-023 — Treat CT and Judge Points as directly executable unit state

- CT/Speed/carry are named from the complete turn-tick dataflow, not field
  order: Speed and carry are added to CT, and normalization records the common
  advance back into carry at the 1000 action threshold.
- `+0xd6` is Judge Points because the retail selector crosses at 10, produces
  Human command id `0x50`, and UI string `0x50` is `Totema`; combo damage also
  uses the field as `JP * 4 + 10`. UI string 751 independently reads
  `Judge Pts?`.
- Consequence: these four scalar names are stable modding vocabulary; the next
  pass starts at the separate `+0xd8` address/byte region.

### D-024 — `+0xd8` is status state, not capability state

- The parallel functions at `0x080CE3A0..0x080CE488` are byte getters/setters.
  Named status application handlers write them, per-turn paths decrement them,
  and `sub_08131C58` clears them when the corresponding live bit is absent.
- The previous "capability setter" label described only the observed clearing
  relationship and is retracted. Most are duration counters; `+0xe6` is a
  linked-unit id, so the enclosing region is status state.
- Promote only the ten one-to-one named joins. Keep `+0xd8/+0xd9/+0xe3/+0xe4/
  +0xe6/+0xe7` numeric until their overlapping or candidate semantics are
  distinguished by another behavioral anchor.

### D-025 — Name Doom from its countdown-to-clear behavior

- Case 42 is not named merely because its abilities sound lethal. Executing
  Checkmate sets `+0xea` bit 4 and `+0xd9` to 3; the turn processor decrements
  the counter and, at expiry, clears the live bit and calls the complete
  battle-status clear routine.
- Decision: name the bit Doom and the byte Doom countdown. This behavioral
  sequence distinguishes it from an immediate KO/death flag.

### D-026 — Distinguish Immobilize from Disable by their consumers

- Aim: Legs/Aim: Arm and cases 24/22 identify candidates, but do not alone
  distinguish movement from action restriction.
- Executed result: `+0xeb` bit 6 forces a synthetic movement mode from 5 to 0,
  so it is Immobilize. The ability-usability predicate rejects on bit 7 before
  success, so bit 7 is Disable. Their paired counters are `+0xe3/+0xe4`.

### D-027 — Keep the shared link separate from duration semantics

- Cover copies target unit byte `+0x104` into actor `+0xe6`; other status
  consumers compare `+0xe6` against candidate unit ids. Values are identities,
  not turn counts.
- Decision: name stat `0x36` `status_link_id` and widen stat `0x27` from
  `status_duration_array` to `status_state_array`.

### D-028 — Name `+0xd8` from the complete Zombie revival lifecycle

- Battle-status reset writes 3 only when the unit satisfies the effective
  Zombie predicate; an ordinary unit receives 0.
- The per-turn path requires effective Zombie and zero HP, decrements the same
  byte, and schedules battle result `0x2000` when the value reaches zero.
- Decision: name stat `0x28` `zombie_revive_countdown`; this is a delayed
  revival counter, not a generic status duration.

### D-029 — Treat `+0xe7` as action-target history, not status state

- Battle initialization writes `0xff`; both nibbles use `0xf` as empty and
  otherwise store the target unit's 4-bit `+0x104` id.
- Four sites in action resolution call the rolling writer. Repeated older ids
  are promoted, third distinct ids evict the oldest, and the AI evaluator calls
  the paired membership helper.
- Decision: name stat `0x37` `recent_target_ids`. Keep the packed representation
  visible because it holds two identities rather than one scalar id.

### D-030 — Name the KO pair by actor/target mutation direction

- Two independent result paths saturating-increment actor `+0xf1` when an
  action reduces its target to zero HP. The target's `+0xf2` increments in the
  same transition unless its exclusion flag is set.
- Executing the forced-KO path produces target HP `123 -> 0`, actor `+0xf1`
  `9 -> 10`, and target `+0xf2` `11 -> 12`; generic stats return both results.
- Decision: name them `ko_inflicted_count` and `ko_suffered_count`. Do not
  generalize the adjacent numeric bytes from proximity.

### D-031 — Separate spatial state from late battle counters

- `+0xf6/+0xf7` are copied into movement-search origin X/Y and used by
  Manhattan-distance consumers; `+0xf8` is passed as the adjacent signed
  vertical component in combat range formulas.
- Battle-object creation computes the current unit-list length, uses it as the
  insertion key, and stores the same byte at unit `+0xfb`.
- Decision: name stats `0x3e..0x40` `tile_x/tile_y/tile_height` and stat `0x43`
  `battle_list_index`. These are runtime placement/identity, not counters.

## Risks and controls

| Risk | Impact | Control |
|---|---|---|
| Plausible values are mistaken for semantics | Incorrect modding API becomes durable | Require an identifiable reader and preferably execution evidence |
| Documentation drifts from tools | Future sessions repeat closed work | Update docs, roadmap, project log, and code in one commit |
| ROM revision mismatch | Offsets and hashes become invalid | Keep the USA SHA1 gate; never commit ROM bytes |
| Generated CSV applies unintended bytes | User ROM is corrupted | Require unedited round-trip equality and single-field diff checks |
| Live trace is generalized beyond its scope | AI claims become overstated | State the exact mission/turn/path covered by each trace |

## Session log

### 2026-08-26 — Removal counters and saved tile position

Objective:

- Resolve or explicitly classify the five remaining late scalar bytes.

Completed:

- Named stats `0x3b..0x3d` / `+0xf3..+0xf5` as other, Parley, and Oust
  removal counters.
- Named stats `0x41/0x42` / `+0xf9/+0xfa` as saved tile X/Y.
- Increased behavior-backed scalar coverage from 57/63 to 62/63.

Evidence recorded during the batch:

- Executed the removal-result fragment with Wyrmtamer, Parley, and Oust;
  seeded counters `9/11/13` became `10/11/13`, `9/12/13`, and `9/11/14`.
- All three abilities' raw-effect descriptors select the same purge formula.
  With 3 KOs and target HP 10/100, Parley counts 0/1/5 produce retail hit
  rates 78/82/89, proving the `+10 * count` threshold contribution.
- Executed a placement snapshot copying live X/Y `12/9` into `+0xf9/+0xfa`;
  stats `0x41/0x42` return the saved pair, and four identical copy anchors
  remain present in the ROM.
- Status/state validation is 20/20.

Next action:

- Resolve stat `0x00` from its direct consumers, then classify the two unnamed
  address-return regions at `+0x34` and `+0xfc` to close the unit layout pass.

### 2026-08-25 — Battle tile position and list index

Objective:

- Close the high-traffic spatial fields and independently resolve `+0xfb`.

Completed:

- Named stats `0x3e..0x40` / `+0xf6..+0xf8` as tile X, tile Y, and tile height.
- Named stat `0x43` / `+0xfb` as the zero-based battle-list index.
- Increased behavior-backed scalar coverage to 57/63.

Evidence recorded during the batch:

- Executed synthetic tile state `12/9/4`; the movement-search fragment copied
  X/Y `12/9` into its origin and the generic stat getter returned all three.
- Range formulas consume the same signed X/Y/height triplet.
- A synthetic two-node battle list returns length 2; battle-object creation
  stores that value both as its insertion key and unit `+0xfb`.
- Status/state validation is 18/18.

Next action:

- Complete the mutation/read census for `+0xf3/+0xf4/+0xf5/+0xf9/+0xfa`.
  Promote `+0xf4` only if its formula role can be named; classify fields with
  no non-initializer access as dormant rather than guessing.

### 2026-08-25 — Paired KO counters

Objective:

- Start the `+0xf1..+0xfb` family with fields whose actor/target roles can be
  executed directly.

Completed:

- Named stat `0x39` / unit `+0xf1` as `ko_inflicted_count` and stat `0x3a` /
  `+0xf2` as `ko_suffered_count`.
- Increased behavior-backed scalar coverage to 53/63 without projecting names
  onto the remaining adjacent bytes.

Evidence recorded during the batch:

- The forced-KO path zeroes target HP and increments the actor/target fields
  from 9/11 to 10/12; the generic stat getter returns both new values.
- Both writes use the same saturating-at-255 pattern. A second ordinary damage
  resolution path independently increments target `+0xf2`, while `+0xf1` has
  two formula consumers.
- Status/state validation is 16/16.

Next action:

- Separate unused stats from live state among `+0xf3..+0xfb`; prioritize
  generic-stat `0x3c` / `+0xf4` and the direct `+0xfb` initialization reader.

### 2026-08-25 — Packed recent-target history

Objective:

- Resolve the final byte in the `+0xd8..+0xe7` status-state region.

Completed:

- Named stat `0x37` / unit `+0xe7` as `recent_target_ids`.
- Closed all sixteen scalar bytes in the status-state region and increased
  behavior-backed scalar coverage to 51/63.

Evidence recorded during the batch:

- Executed history states are `ff -> f5 -> 56 -> 65 -> 57` for target ids
  `5, 6, 5, 7`, proving insertion, promotion, and oldest-entry eviction.
- Final membership accepts ids 5 and 7 and rejects evicted id 6; generic stat
  `0x37` returns each packed byte.
- The writer has four call sites in action resolution and the AI ability
  evaluator consumes the membership result. Status/state validation is 15/15.

Next action:

- Trace the eleven remaining `+0xf1..+0xfb` scalars as one mutation family,
  starting from the saturating counters already visible in action resolution.

### 2026-08-25 — Zombie revival countdown

Objective:

- Resolve `+0xd8` from its reset, eligibility, and expiry behavior.

Completed:

- Named stat `0x28` / unit `+0xd8` as `zombie_revive_countdown`.
- Added an executed lifecycle check and increased named scalar coverage to
  50/63.

Evidence recorded during the batch:

- Battle-status reset gives a persistent Zombie count 3 and a blank unit 0;
  generic stat `0x28` independently returns 3.
- The per-turn consumer requires effective Zombie and zero HP, decrements via
  the dedicated getter/setter pair, and schedules the revival result at zero.
- Status validation is 14/14.

Next action:

- Resolve the final `+0xe7` status-state byte by joining its two-id rolling
  writer to the action-resolution call sites and AI membership test.

### 2026-08-25 — Shared status-link id

Objective:

- Determine whether the shared `+0xe6` field is a duration or status payload.

Completed:

- Named stat `0x36` / unit `+0xe6` as `status_link_id`.
- Corrected the region/pointer name from status-duration array to status-state
  array.
- Added a thirteenth status check and increased named scalar coverage to 49/63.

Evidence recorded during the batch:

- Executing Cover with target unit id 42 sets the actor's Cover live bit and
  copies 42 to `+0xe6`; dedicated and generic stat getters both return 42.
- Two other application handlers also write identifiers, and battle selection
  paths compare this field to other units' `+0x104` ids.
- Status validation is 13/13.

Next action:

- Resolve the last two status-state bytes: `+0xd8` is tied to zero-HP state and
  `+0xe7` lacks the parallel accessor family. Trace their full mutation sets
  before moving to the eleven `+0xf1..+0xfb` fields.

### 2026-08-25 — Disable and Immobilize closure

Objective:

- Resolve `+0xe3/+0xe4` using consumers rather than Aim ability names alone.

Completed:

- Named live `+0xeb` bit 6 / stat `0x33` as Immobilize and its duration.
- Named live `+0xeb` bit 7 / stat `0x34` as Disable and its duration.
- Expanded the status registry to 19 live statuses / 13 durations and the
  status gate to 12 checks.
- Increased behavior-backed scalar coverage from 46 to 48 of 63.

Evidence recorded during the batch:

- Executing Aim: Legs applies Immobilize/count `1/3`; Aim: Arm applies
  Disable/count `1/3`.
- With the same synthetic movement object, no status preserves mode 5 and
  Immobilize forces mode 0.
- `sub_08133E18`, the ability-usability predicate, checks Disable and returns
  through its failure path when set.
- Status validation is 12/12.

Next action:

- Resolve the shared `+0xe6` counter across Cover and monster-state handlers,
  then isolate `+0xd8` and `+0xe7`. Do not force a single status name onto
  `+0xe6` if its three live-bit consumers intentionally share generic state.

### 2026-08-25 — Doom countdown closure

Objective:

- Resolve `+0xd9` without choosing between Death and Doom from ability names.

Completed:

- Added Doom as the seventeenth named live status and `+0xd9` / stat `0x29` as
  its countdown.
- Extended the duration registry to eleven counters and status validation to
  eleven checks.
- Increased behavior-backed scalar coverage from 45 to 46 of 63.

Evidence recorded during the batch:

- Executing Checkmate's case-42 handler on a blank target sets live bit
  `+0xea:0x10` and countdown 3.
- The isolated per-turn path reads both, decrements the counter, and at expiry
  calls the live-bit clearer plus `sub_08097298`, which clears the full battle
  status set.
- Status validation is 11/11.

Next action:

- Resolve `+0xe3/+0xe4` together from cases 22–25 and Bind, testing the
  Disable/Immobilize candidates against movement/action consumers. Then inspect
  the shared `+0xe6` counter and isolated `+0xd8/+0xe7` bytes.

### 2026-08-25 — Named status-duration counters

Objective:

- Resolve the `+0xd8..+0xe7` address region from its writers and consumers.

Completed:

- Corrected the old capability-state hypothesis: stat `0x27` returns the
  status-duration array.
- Named Haste, Slow, Stop, Shell, Protect, Sleep, Silence, Confuse, Charm, and
  Addle counters at `+0xda..+0xe2/+0xe5` (stats `0x2a..0x32/0x35`).
- Added duration metadata to the status registry and a tenth status gate.
- Increased behavior-backed scalar coverage from 35 to 45 of 63.

Evidence recorded during the batch:

- Every named status handler calls its live-bit setter and the matching
  duration setter; `sub_08131C58` pairs the same live getter/counter setter.
- Dedicated getters return the exact synthetic value written by each setter,
  and the generic stat accessor returns that value through the mapped stat id.
- Status validation is 10/10 across ten handler/live-bit/counter joins.

Next action:

- Separate the six remaining bytes `+0xd8/+0xd9/+0xe3/+0xe4/+0xe6/+0xe7`.
  Start with `+0xd9`, whose live bit, case-42 handler, value 3, and per-turn
  decrement path are already isolated; retain numeric labels if the exact
  player-facing status name cannot be joined.

### 2026-08-25 — CT, Speed, carry, and Judge Points

Objective:

- Name the first four later battle-state scalars from executable consumers.

Completed:

- Named stat `0x23` / unit `+0xd0` as charge time (CT), `0x24` / `+0xd2` as
  Speed, `0x25` / `+0xd4` as CT carry, and `0x26` / `+0xd6` as Judge Points.
- Extended AI check 4 with direct reads, Speed's signed item-property join, a
  complete one-unit CT tick, and the Totema JP boundary.
- Reduced the unnamed later-scalar count from 32 to 28.

Evidence recorded during the batch:

- `sub_080CA580` reads base Speed and adds item property 14 across all five
  equipment slots; the level-up routine grows the same `+0xd2` field.
- Executing `sub_0809DF7C` changes CT 900 / Speed 100 / carry 25 into CT 1000
  / carry 25 after its over-threshold normalization, correcting the prior
  zero-carry interpretation.
- With identical Human units, `sub_080260E0` leaves command `0x0e` at 9 JP
  and selects `0x50` at 10 JP; UI string `0x50` decodes to `Totema`.
- Combo damage separately uses the same stat as `JP * 4 + 10`; UI string 751
  is `Judge Pts?`.

Next action:

- Map the address at stat `0x27` / unit `+0xd8` and its sixteen scalar bytes
  (`0x28..0x37`) from constructors, mutation sites, and battle consumers.

### 2026-08-25 — Stat-accessor coverage correction

Objective:

- Begin the address-region pass by making the extractor report every case
  accurately.

Completed:

- Fixed `dump_stats.py` to follow offsets accumulated in `r0` before an
  indirect load and to stop each case at its branch boundary.
- Corrected the accessor classification from 31 scalar / 38 address cases to
  63 scalar / 6 address cases.
- Added the complete later layout: four values at `+0xd0..+0xd6`, sixteen at
  `+0xd8..+0xe7`, eleven at `+0xf1..+0xfb`, plus address returns at `+0x34`,
  `+0xd8`, `+0xe8`, and `+0xfc`.

Evidence recorded during the batch:

- The only address-returning stat ids are `0x09`, `0x1c`, `0x22`, `0x27`,
  `0x38`, and `0x44`.
- AI check 4 executes all six and gets unit `+0x0c/+0x2a/+0x34/+0xd8/+0xe8/
  +0xfc` exactly; the extractor asserts the same id set.
- The 31 existing semantic names remain valid; the corrected boundary is that
  32 later battle-state scalar loads still need names.

Next action:

- Name the four `+0xd0..+0xd6` values and the `+0xd8..+0xe7` block from their
  constructors and battle consumers, retaining numeric labels where behavior
  does not distinguish a field.

### 2026-08-25 — Innate element and early-scalar milestone

Objective:

- Resolve the last unnamed direct-load byte, stat `0x08` / unit `+0x0b`.

Completed:

- Corrected job `+0x11` from the unsupported `unit_class` label to
  `innate_element_id` in the editor and documentation.
- Named unit stat `0x08` from its constructor position and elemental-monster
  population.
- Closed all 31 scalar fields from identity through equipment. A later parser
  audit corrected the full accessor total to 63 scalar and six address cases.

Evidence recorded during the batch:

- Jelly job 46 initializes unit `+0x0b` to Fire id 1 and reads it through stat
  `0x08`.
- The only nonzero job values are twelve Fire/Ice/Lightning/Holy/Dark monster
  entries, all in the shared ability element namespace.
- Job CSV now exposes `innate_element_id`; byte layout and write behavior are
  unchanged by the label correction.

Next action:

- Audit and name the later battle-state scalar and address cases.

### 2026-08-25 — Equipped-item stat fields

Objective:

- Close the final five direct-load halfwords after the status field.

Completed:

- Named stats `0x1d..0x21` / unit `+0x2a..+0x32` as equipped item ids 0–4.
- Extended AI check 4 to read all five ids through the stat accessor before
  executing the existing Attack/Defense/Magic Power/Resistance item totals.

Evidence recorded during the batch:

- Synthetic ids `1/3/7/10/0` read back unchanged through stats `0x1d..0x21`.
- Each of the four retail total-stat helpers iterates the same five halfwords
  and adds the independently named item property.

Next action:

- Isolate stat `0x08` / unit `+0x0b` from behavioral consumers. If no unique
  meaning closes, leave it numeric and shift to the address-returning stat ids
  that expose movement, abilities, and state/duration substructures.

### 2026-08-25 — Unit identity and elemental resistance array

Objective:

- Close unit `+0x04/+0x06` and the job-derived damage-affinity bytes using
  constructor and battle execution.

Completed:

- Named stat `0x01` / unit `+0x04` as unit type and stat `0x03` / `+0x06` as
  race id.
- Named stats `0x0a..0x12` / unit `+0x0c..+0x14` as neutral, Fire, Wind,
  Earth, Water, Ice, Lightning, Holy, and Dark resistance.
- Closed the packed job-table slot-2 question and documented the retail
  duplicated-Wind Earth source.
- Extended AI check 4 through constructor, job initialization, direct stat
  reads, and the full damage consumer.

Evidence recorded during the batch:

- Constructing Jelly job 46 writes unit type 1 and race 7.
- Jelly's packed Fire absorb and Ice weakness reach the expected unit bytes.
- Fire under resistance codes 0/1/2/3/4 produces `33/24/0/-19/11` with fixed
  RNG, proving weak/normal/nullify/absorb/resist semantics.
- Packed Wind and Earth slots match in 116/116 jobs; only Wind is copied, twice.
- AI validation remains 8/8.

Next action:

- Name direct equipment slots at stats `0x1d..0x21` from the already-executed
  combat-total helpers, then isolate stat `0x08` / unit `+0x0b` without
  inheriting the job table's unsupported historical label.

### 2026-08-25 — Job identity, level, and experience fields

Objective:

- Name the highest-confidence members of the direct one-byte unit-stat block
  and make each interpretation executable.

Completed:

- Named stat `0x02` / unit `+0x05` as base job, stat `0x04` / `+0x07` as
  active job, and stat `0x05` / `+0x08` as secondary job.
- Named stat `0x06` / `+0x09` as level and stat `0x07` / `+0x0a` as
  experience.
- Extended the AI stat gate with direct accessor reads plus job-change,
  EXP-award, and level-cap execution.

Evidence recorded during the batch:

- An ordinary unit switching to its existing secondary job changes
  base/active/secondary from `2/0/7` to `7/7/0`.
- The retail award fragment changes 40 EXP plus 5 to 45.
- Calling the level-up routine at level 50 / EXP 99 attempts the increment,
  then restores the retail ceiling of 50/99 before stat growth.
- AI validation remains 8/8; check 4 now protects all five new meanings.

Next action:

- Trace unit `+0x04` and `+0x06` from constructors and canonicalization
  readers. Then map the job-derived byte run at `+0x0b..+0x14` only where a
  job property and a gameplay consumer agree.

### 2026-08-25 — Yellow Clip inverse and persistent-mask boundary

Objective:

- Finish the caller/application sweep for unit `+0x28` before moving to the
  one-byte stat block.

Completed:

- Joined Yellow Clip to raw effect 206, descriptor case 91, and handler
  `0x08133758`.
- Extended the Yellow Card execution test through the inverse clear.
- Recorded the eight remaining observed masks as intentionally numeric.

Evidence recorded during the batch:

- Yellow Card case 92 writes `0x0040`; Yellow Clip case 91 checks that same
  predicate and clears the same mask.
- A synthetic target now executes `0x0000 -> 0x0040 -> 0x0000` across the two
  retail handlers.
- The other mask predicates have category/capability callers, but no named
  ability descriptor or unique behavioral join strong enough to promote.

Next action:

- Name the direct one-byte fields for base/active job, level, and experience,
  then continue only where a constructor or gameplay formula closes the name.

### 2026-08-24 — Yellow Card and persistent-field correction

Objective:

- Continue mapping the remaining `+0x28` bits and test whether the field is
  exclusively innate.

Completed:

- Named `+0x28` bit `0x0040` as Yellow Card.
- Corrected `innate_status_flags` to `persistent_status_flags`; Yellow Card is
  applied during battle, so “innate” was too narrow for the whole field.
- Added a ninth status validator check that executes the Yellow Card handler.

Evidence recorded during the batch:

- Yellow Card ability 344 stores raw effect 207; its descriptor selects case
  92 and handler `0x081337F4`.
- With a synthetic action context and target, executing that handler through
  its store changes target `+0x28` from zero to exactly `0x0040`.

Next action:

- Trace the seven other observed `+0x28` masks from their accessor callers;
  retain numeric names where a unique status or capability anchor is absent.

### 2026-08-24 — Persistent Zombie bridge

Objective:

- Determine the role of stat `0x1b` / unit `+0x28` from its two retail readers.

Completed:

- Named `+0x28` as a persistent-status bitfield and bit `0x0800` as Zombie.
- Added Zombie as the sixteenth behavior-backed live status.
- Extended the status validator from seven to eight checks.
- Added behavior-backed names to `dump_stats.py` so regenerated output carries
  the semantic overlay instead of losing it.

Evidence recorded during the batch:

- Zombify's raw effect 127 selects descriptor case 63; the case-63 handler at
  `0x081331F8` calls the `+0xe9` bit-3 setter.
- `sub_081308F4` returns true for either live `+0xe9` bit 3 or stat `0x1b`
  bit `0x0800`; execution returns 0/1/1 for blank/live/persistent samples.
- The battle-status initializer at `0x08133A58` calls the same Zombie setter
  when the effective predicate succeeds.

Next action:

- Map the remaining `+0x28` persistent bits through their effective-status readers;
  retain numeric labels for any bit without a unique application/status join.

### 2026-08-24 — Base combat-stat joins

Objective:

- Resolve the four packed `u16` fields at unit `+0x20..+0x26` without relying
  on their order or a published structure alone.

Completed:

- Named stat ids `0x17..0x1a` as Attack, Defense, Magic Power, and Resistance.
- Extended the AI execution gate across all eight named `u16` stats.
- Added an equipped-item test that exercises the four total-stat helpers.

Evidence recorded during the batch:

- `sub_080CA624`, `sub_080CA6B4`, `sub_080CA66C`, and `sub_080CA6FC` load unit
  `+0x20/+0x22/+0x24/+0x26` respectively.
- With equipment enabled, those functions add item properties 10/11/12/13,
  already mapped independently as Attack/Defense/Magic Power/Resistance.
- The same four values are the combat terms used by the dispatch scorer, and
  the ROM's unit serializer preserves all 16 bits of each field.

Next action:

- Trace stat `0x1b` / unit `+0x28`, whose known reader tests bit `0x800`, then
  move backward into the 17 one-byte stats at unit `+0x04..+0x14`.

### 2026-08-24 — Max-MP execution anchor and stat-map correction

Objective:

- Start the unit-stat half of AI5.1 with the smallest unnamed `u16` whose
  consumer has an identifiable boundary behavior.

Completed:

- Named stat id `0x16` / unit `+0x1e` as max MP.
- Extended the AI execution gate to cover HP, max HP, MP, and max MP together.
- Corrected an earlier 65/4 estimate to 31/38. A subsequent complete case-body
  parser superseded both estimates with the verified 63 scalar / 6 address
  classification.

Evidence recorded during the batch:

- At `0x0809308A..0x080930C4`, the retail restoration path reads current MP
  (`0x15`), adds recovery, reads `0x16`, clamps to it, and writes the result to
  unit `+0x1c`.
- Four synthetic boundary samples return the exact values written to
  `+0x18/+0x1a/+0x1c/+0x1e` through stat ids `0x13..0x16`.

Next action:

- Trace stat ids `0x17..0x1a` through their packing and combat consumers; keep
  them numeric if the bitfields do not expose a unique game-facing meaning.

### 2026-08-24 — Descriptor-backed status expansion

Objective:

- Apply the corrected raw-effect descriptor method to the highest-confidence
  named status abilities without inferring from effect ordering.

Completed:

- Expanded `tools/status_flags.py` from five descriptor-backed entries to 15.
- Added Frog, Stop, Blind, Confuse, Charm, Addle, Protect, and Shell; folded
  the existing Silence and Reflect names into the same executable registry.
- Kept ambiguous candidates such as Break/Petrify, Aim: Arm/Disable, and
  Aim: Legs/Immobilize out of the registry pending a direct ROM name anchor.

Evidence recorded during the batch:

- Every named ability resolves to its expected raw effect and internal case;
  all 15 case handlers call the expected setters and all 15 bit pairs execute.
- Poison Frog/Frogsong converge on Frog case 12; Stopshot/Stop converge on
  Stop case 19; Blindshot/Blind converge on Blind case 35; Poison Claw/Poison
  converge on Poison case 61.
- Confushot and Charmshot select their named statuses in secondary effect slot
  1, exercising the validator's slot-aware path.

Next action:

- Resolve the three high-value action-prevention candidates (Petrify,
  Disable, Immobilize) from ROM-owned labels or behavioral readers, then move
  to remaining unit-stat fields if those names cannot be pinned cleanly.

### 2026-08-24 — Effect-descriptor correction and Poison join

Objective:

- Continue from the first status batch without carrying forward an unverified
  assumption that raw ability-effect ids and internal cases align directly.

Completed:

- Located the four-byte effect-descriptor table at `0x08553E70` through
  `sub_0812F230` and `sub_0812F328`.
- Corrected Sleep from the provisional case-37 hypothesis to internal case 45,
  getter `sub_080CDB24`, and `+0xeb` bit 2.
- Named Poison as internal case 61, getter `sub_080CD974`, and `+0xe9` bit 1.
- Expanded the status gate to assert the named ability, raw effect,
  descriptor, handler setter, and executed getter/setter chain.

Evidence recorded during the batch:

- Sleep ability 32 stores raw effect 97; descriptor 97 selects case 45; its
  handler calls `sub_080CE0B8`. The executed bit raises the tested ordinary
  hit chance from 95 to 100 and does not change effective speed.
- Poison ability 64 stores raw effect 125; descriptor 125 selects case 61;
  its handler calls `sub_080CDE38`. Poison Claw raw effect 124 selects the same
  internal case.
- The former case-37 bit still halves speed and raises hit chance, but is now
  deliberately unidentified rather than mislabeled Sleep.

Next action:

- Use the descriptor join to name additional single-effect status abilities,
  prioritizing action-prevention bits and then unit-stat readers.

### 2026-08-24 — First behavior-backed speed-status batch

Objective:

- Begin AI5.1 by naming status bits from executable consequences and their
  retail application handlers.

Completed:

- Added a shared status-name registry consumed by `tools/flag_map.py`.
- Joined Speed Down, Slow, and Haste to their unit bits, setters, and one-based
  application cases. A provisional Sleep identification was tested further
  and corrected in the immediately following batch above.
- Added a standalone status validator and corrected the turn-order and
  item-speed documentation.

Evidence recorded during the batch:

- All 92 application-table entries are executable Thumb handlers at a
  12-byte stride; cases 20/51/52 call the expected setters.
- The getter/setter pairs clear and set their unit bits in execution.
- With base speed 100, Speed Down and Slow return 50; Haste returns 200; Slow
  plus Haste returns 100. Speed Down independently selects the red stat-display
  palette.

Next action:

- Find and validate the raw-effect-to-internal-case conversion before naming
  another bit. This is completed by the correction batch above.

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
