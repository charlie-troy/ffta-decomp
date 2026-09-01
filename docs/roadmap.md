# Remaining-work roadmap

How to read this: the repo's own rule (CLAUDE.md) is **widen the no-compiler
modding surface first; match more functions last.** This roadmap follows that.
Each phase lists the objective, why it is worth doing now, concrete steps using
tools that already exist, and a definition of done. The reusable loop for any
"map a table / name a field" step is stated once at the end.

State snapshot: 172 functions matched (4,536 bytes) · full 16 MB ROM rebuilds
byte-identical · CI hash gate on every function · 3,594 functions discovered ·
abilities, jobs, items, missions and map terrain mapped and editable · text
decodes at 99.7% · 10/10 execution checks pass (`tools/validate_ai.py`).
The separate job-field gate passes 4/4, covering 5,568 retail formula reads,
causal redirect/resistance patches, and the morph-family flag.

Phase 0 was re-verified on 2026-08-24: `make check` verified 172/172 function
hashes, `tools/validate_ai.py` passed 8/8 checks at that checkpoint (10/10 as
of 2026-08-31), and `make rom` reproduced the
expected 16 MB ROM SHA1. The documentation inconsistencies listed below were
reconciled in the same batch.

---

## Phase 0 — Reconcile the docs, re-verify the baseline (half a day)

**Why first:** the project's central lesson is that wrong claims get enshrined,
and the docs have drifted. Stale claims are the cheapest source of future wrong
turns.

**Steps:**

1. Reconcile the specific inconsistencies that exist as of this writing:
   - `docs/validation.md` says "six checks"; `tools/validate_ai.py` has
     **eight** (priority, properties, flags, stat_ids, healthy_rule, gate,
     resist_slots, unarmed). The README repeats "six checks".
   - `docs/matching-notes.md` says "113 functions, 3,044 bytes"; the README and
     `data/functions.json` say **172 / 4,536**.
   - `docs/unit-ai-table.md` is superseded by `docs/job-table.md` (123 vs 116
     entries; "b04 unknown" vs race confirmed; four dead/raw offsets now closed).
     Mark it superseded.
   - `docs/ai-findings.md` still guesses ability `+0x1A` is "accuracy";
     `docs/ability-table.md` proved it is `ai_priority`. Fix the stale table.
2. Run the full gate and record a green baseline:
   ```bash
   make check                              # CI gate, no ROM needed
   python tools/validate_ai.py baserom.gba # must stay 10/10
   make rom                                # byte-identical rebuild (WSL + ROM)
   ```
3. Add a "superseded by" header to any partially-wrong doc rather than editing
   it into ambiguity.

**Done when:** no doc contradicts another, and all three gates pass clean.

---

## Phase 1 — Whole-battle behavioural validation (completed 2026-08-24)

**Objective:** watch a real AI turn run end to end, and prove (or refute) that
no unmodeled rule dominates the individually-verified decision inputs.

**Why first of the real work:** README and CLAUDE.md both list it as the #1
open item. Every AI finding so far — the priority filter, the 10/49 gates, the
healthy-target rule — is verified *in isolation*. Calling fragments proves the
rules; it does not prove there is no further rule that dominates them.

**Steps:**

1. **Get a battle-positioned save state — done.** The working save was blank,
   so `tools/mgba_reach_snowball.lua` drives New Game to the opening engagement.
   The canonical local replay artifact is `outputs/mgba-snowball/state-facing.ss0`.
2. **Trace it — done.** Exact breakpoint mode records registers, RNG and stack
   context at `0x080C32C0`, checkpointing each hit. Statistical sampling remains
   available for subsystem discovery.
3. **Attribute the IWRAM samples.** Done in tooling: `trace_mgba.py --rom` now
   reads the bytes around an IWRAM PC and matches them back into the ROM (the
   copy is verbatim), then resolves that ROM address against the manifest. The
   completed evaluator trace uses an exact ROM breakpoint and does not need the
   statistical IWRAM fallback.
4. **Confirm the candidate-list model.** Static confirmation is done (see
   `docs/ai-findings.md`): `sub_080C2618` builds one record per ability with
   the priority byte at `+0x10`, `sub_080C1EB4` filters a list by zeroing out
   entries that fail the priority predicate, and `sub_080C32C0` re-applies the
   gate while scoring.
5. **Identify the turn-order code.** Done — see `docs/turn-order.md`. The
   chain is `sub_0809E1E0` -> `sub_0809E05C` (turn manager) -> `sub_0809DF7C`
   (CT tick). CT accumulates by the slow/haste-adjusted speed, a unit acts at
   CT > 1000, and the advance subtracts `min(max_CT - 1000, 500)` from every
   unit with a fractional carry. The relevant flags are now Quicken, Petrify,
   Speed Down, Mow Down's distinct speed penalty, Slow, Haste, and one numeric
   inactive-like suppressor whose retail setter is unreferenced. The live turn
   is captured in `docs/whole-battle-trace.md`.
6. **Freeze the RNG — done.** `tools/mgba_replay_ai_turn.lua` writes
   `0x12345678` at `0x030034B0`; two traces reproduce exactly.
7. **Write it up — done.** See `docs/whole-battle-trace.md` and the repeat-pair
   validator `tools/validate_ai_trace.py`.

**Done:** a reproducible trace shows a full enemy turn resolving through
`sub_080C32C0`. No upstream rule bypasses the evaluator in this turn; broader
mission-, law-, and effect-specific paths remain outside that scoped verdict.

---

## Phase 2 — Mission fields: finish the computed and packed properties

**Objective:** finish the mission table — the newest and least-labeled of the
mapped tables.

**Why next:** missions are already editable, but 30 of 65 properties are
"computed or packed" and unnamed. The reward puzzle is now solved — gil is
`+0x33` (×200), AP is `+0x34` (×10) and the item reward is `+0x35` — so the
remaining work is naming the other computed/packed properties.

**Steps:**

1. For each non-plain-load property, find a reader using
   `tools/accessor_callers.py --target 0x080CE4DC --reg r1`. Do not use
   `tools/field_callers.py` here; that older script is hard-coded to the job
   accessor and its `r2` field-id convention.
2. **Properties 33–41 — done 2026-08-24.** The nine bytes at
   `+0x2a`–`+0x32` are clan progression rewards: clan points, then Combat,
   Magic, Smithing, Craft, Appraise, Gather, Negotiate and Track skill points.
   `sub_08046850` applies each byte to the matching progress counter, and
   `tools/validate_missions.py` checks all 4,608 accessor reads plus one
   executed application per track. The dispatch path instead uses
   `+0x43`/`+0x44`, the separately named dispatch threshold.
3. **Reward source — done.** The rewards are stored, not computed: gil is
   `+0x33` ×200, AP is `+0x34` ×10, item reward is `+0x35`. The earlier
   "not in the table" result was wrong on two counts: the gil scale factor
   (200) was not in the searched set, and the second anchor was mislabeled —
   "Thesis Hunt = 28,600 gil / 80 AP" is actually **Over The Hill** (mission
   25). Thesis Hunt is 4,000 gil / 40 AP. See `docs/mission-data.md`.
4. **Dispatch jobs and pub fee — done 2026-08-24.** Property 48 is the packed
   required job; `+0x3c` bits 2–7 are the opposite, a blocked job; `+0x3e`
   ×200 is the base pub information fee before turf pricing. The dormant
   `+0x3d` dispatch-item exclusion is validated but clear in every retail
   mission. `validate_missions.py` executes all relevant readers and rating
   branches, and computed CSV edits preserve adjacent packed bits.
5. **Mission index leading fields — done 2026-08-24.** The true base is
   `0x08563A70`, with 256 records including a zero sentinel. `+0x00` selects a
   world-map symbol's persistent placement record; `+0x01` is the key used by
   a script handler to select the record's `+0x02` mission. Both paths execute
   in the standalone validator.
6. **Behavior and public type — done 2026-08-24.** `+0x02` bits 0–2 select the
   internal behavior path and bits 3–5 select the icon group. The effective
   player-facing types are Non-Battle, Regular, Encounter, Free-Area, plus a
   small internal Special group. All accessor reads and packed edits execute
   in validation.
7. **Availability and clear conditions — done 2026-08-24.** Properties 16–18
   are the six-bit availability deadline, three-bit clear-condition code, and
   six-bit clear count. Published mission examples anchor Days and Battles;
   all 1,536 accessor reads and packed setters execute in validation.
8. **Clan-skill requirement — done 2026-08-24.** Properties `0x2e/0x2f` select
   one of the eight clan-skill levels and its required threshold. The complete
   acceptance predicate rejects Twin Swords at Combat 9 and accepts it at 10.
   This path also corrected four previously swapped reward-column labels.
9. **Cancellation rule — done 2026-08-24.** Property `0x37` is `+0x41` bit 2.
   The executed mission formatter selects Cancellations Accepted, No
   Cancellations, or the special-group Mission Begins Immediately path.
10. **Reward-preview flags — done 2026-08-24.** Properties `0x3d..0x40` hide
    two item and two law-card reward slots behind `????`. All four formatter
    paths execute, including the retail-dormant second-card flag when injected.
11. Expose every newly-named field in `tools/mission_table.py`,
   round-trip-verified, and add a validation check. **Done for the nine clan
   progression fields, dispatch job rules, dormant dispatch item rule, pub
   fee, mission type, availability/clear fields, and clan-skill
   requirements, cancellation, and reward-preview flags**.

**Done 2026-08-24:** a known mission's full reward is reproducible from named
data, every new field round-trips byte-identically, and all 50 constant-property
call sites in the corrected report belong to a named family. Seven variable-id
calls remain available for future goal-driven research, but no longer block the
higher-value map phase.

---

## Phase 3 — Map blocks beyond terrain

**Objective:** decode and make editable the tile arrangement, the `+0x08`
block, and the graphics.

**Why:** the README lists it; terrain already round-trips and the LZ77 codec
works both directions, so the pipeline exists and this is pure extension.

**Steps:**

1. **Tile arrangement — done 2026-08-24.** The sparse two-layer placement
   runs, 8/16-bit variants, redirects, and raw/compressed storage are decoded
   and editable. Map 0 has 770 visual placements over a separate 14x14 terrain
   grid; the former 228-tile count was packed-stream bytes misread as cells.
2. **Clipping tilemap (`+0x08`) — done 2026-08-24.** Sparse halfword runs
   expand into two 32x64 layers at `0x0200D1A0`; the loader and visibility
   consumer are identified, and dump/apply plus a real edit round-trip pass.
3. **Graphics (`+0x00`) — done 2026-08-24.** The `0x20`/`0x22` bytes are FFTA
   wrappers, not GBA Huffman. The strict custom-LZSS decoder byte-matches the
   retail routine on all 50 unique streams and exports indexed 4bpp tiles.
4. **Animations and modes — done 2026-08-24.** `+0x14/+0x18` describe 28
   unique uncompressed 4bpp animation sets on 83 maps; `+0x1c` is their VRAM
   destination, not a pointer. Primary/alternate render modes `+0x54/+0x55`
   execute through the retail selector, and `+0x56` indexes shared palettes.
5. ~~Resolve the height >127 flag.~~ **Closed 2026-08-24:** it was a decoder
   error; packed run headers were being read as terrain cells.
6. ~~Handle the 9 skipped height maps.~~ **Done 2026-08-24:** all nine are
   ordinary redirects and now resolve through the shared packed-block loader.
7. Give each newly-decoded block a dump/apply command with the same
   grow-refusal guard `apply-terrain` uses.

**Complete 2026-08-24:** arrangement, terrain, and clipping are editable with
byte-identical round-trips and size guards; graphics and animation frames
export reproducibly, with graphics matched against the retail decoder.

---

## Phase 4 — Item-table stragglers

**Objective:** name the last unnamed item bytes.

**Why:** items are fully editable and the accessor is clean (all 19 properties
are plain loads), so this is cheap and closes the table.

**Steps:**

1. `+0x18` — **done.** It is the random-item category: 0 marks the 81
   unique/quest items excluded from random generation, and 1–30 classify the
   rest (19 weapon types, then shield/helm/headgear/armor/clothing/robe/
   footwear/gloves/accessory/consumable, plus Mythril). `sub_080CC788` is the
   reader that filters on `+0x18 != 0` when drawing random items. See
   `docs/item-table.md`.
2. `+0x0d` and `+0x0e` — **done 2026-08-24.** They select icon palette bank
   and graphics resource respectively, traced through the sprite constructor
   to OAM output.
3. `+0x0c` flag byte — **done 2026-08-24.** Hand-use classes occupy bits 0–2,
   bit 3 gates shop discounts, bits 4–6 are cumulative shop tiers, and bit 7
   adds Mythril/consumables to the special random pool. The hand-use bit 0/2
   names are exact population classifications; the remaining bits have direct
   retail readers.

**Done when:** each is named from an identifiable reader or an exact exhaustive
population invariant whose inference boundary is explicit, and round-trips
byte-identically.

**Complete 2026-08-24:** the eight-check item gate executes 7,144 accessor
loads, all 375 icon resource/palette paths, the discount boundary, and both
unedited and two-field edited CSV round-trips.

---

## Phase 5 — Name the AI's condition space (status bits and unit stats)

**Objective:** name the 56 unit status/capability bits and the remaining
unit-stat fields.

**Why:** the evaluator branches directly on many of these bits; naming them
names the conditions under which the AI refuses to act — most of what a
behaviour mod needs to reach.

**Steps:**

1. Extend the two naming patterns that already worked — **exemption pairing**
   (status || ignore-flag, which named Silence) and **avoidance** (ability flag
   + unit predicate, which named Reflect) — to more bits.
2. Find the **behavioural sites**: per-turn damage = Poison, clear-on-hit =
   Sleep, etc. Each names one bit, and the already-mapped **inflict/cancel
   adjacency** (46 of 60 case bodies ↔ bits) propagates the name to its case
   ids. **In progress 2026-08-24:** the 92-entry application table and executed
   descriptor and executed behavior name Speed Down (`+0xec` bit 2 / case
   20), Sleep (`+0xeb` bit 2 / case 45), Slow (`+0xea` bit 6 / case 51), Haste
   (`+0xea` bit 5 / case 52), and Poison (`+0xe9` bit 1 / case 61).
   `tools/validate_statuses.py` is the twenty-one-check regression gate. Raw ability
   effect ids remain a separate numeric namespace joined to internal cases by
   the four-byte descriptor table at `0x08553E70`. Forty-four live bits now have
   behavior-backed names, including Frog, Stop, Blind, Confuse, Charm, Addle,
   Protect, Shell, Zombie, Silence, and Reflect.
3. Name the remaining **unit struct** stats — the 17 `u8` stats
   (`+0x04`–`+0x14`) and the unnamed `u16`s — by finding code that reads a stat
   and does something identifiable, exactly as the HP pair was pinned. **In
   progress 2026-08-24:** stat `0x16` / unit `+0x1e` is now max MP; the executed
   restoration path clamps current MP to it before writing `+0x1c`. Stats
   `0x17..0x1a` / unit `+0x20..+0x26` are now Attack, Defense, Magic Power, and
   Resistance; the four total-stat helpers join them to item properties 10–13.
   The AI validator executes both groups. Stat `0x1b` / unit `+0x28` is now an
   persistent-status bitfield with bit `0x0040` proven as Yellow Card and bit
   `0x0800` proven as persistent Zombie. Yellow Clip is the executed inverse
   of Yellow Card; eight other observed masks remain numeric after a complete
   caller sweep found no unique named application join. **Continued
   2026-08-25:** stats `0x02/0x04..0x07` name base job, active job, secondary
   job, level, and experience at unit `+0x05/+0x07..+0x0a`. Retail job-change,
   EXP-award, and level-cap paths execute in the AI gate, including the
   level-50 / EXP-99 ceiling. Stats `0x01/0x03` are now constructor-backed unit
   type/race. Stats `0x0a..0x12` are neutral plus Fire/Wind/Earth/Water/Ice/
   Lightning/Holy/Dark resistance; executed damage proves all five affinity
   codes. **Corrected 2026-08-31:** a distinct synthetic packing proves Earth
   reads independent job resistance slot 2; retail Wind/Earth equality hid the
   former field-map error.
4. ~~Decompile the **capability setters** `0x080CE420`–`0x080CE480`.~~
   **Corrected/closed 2026-08-25:** they are status-duration setters, paired
   with getters at `0x080CE3A0..0x080CE410`; ten counters are named and tested.
5. ~~Resolve whether resistance slot 2 is read by any path.~~ **Corrected and
   closed 2026-08-31:** field `0x10` reads slot 2 and unit initialization copies
   it to Earth. Slots 1/2 are equal in retail, but distinct synthetic values
   0–7 survive the accessor and initializer independently.
6. **Continued 2026-08-25:** stats `0x1d..0x21` / unit `+0x2a..+0x32` are the
   five equipped item ids. Direct stat reads and all four item-derived combat
   totals execute in the AI gate.
7. **Early/equipment scalar milestone complete 2026-08-25:** stat `0x08` /
   unit `+0x0b` is innate element id, copied from the matching job field. All
   31 scalar fields through equipment are named. **Coverage correction:** the
   accessor contains 63 scalar loads and six address returns, not 31/38; the
   additional 32 battle-state scalars at `+0xd0..+0xfb` remain numeric.
8. **Later scalar batch started 2026-08-25:** stats `0x23..0x26` / unit
   `+0xd0..+0xd6` are CT, Speed, CT carry, and Judge Points. The execution gate
   covers Speed's item join, a complete CT tick/normalization, and the 9/10 JP
   Totema boundary. This leaves 28 scalar loads at `+0xd8..+0xfb` numeric.
9. **Duration block advanced 2026-08-25:** stat `0x27` is the status-duration
   array; ten counters at `+0xda..+0xe2/+0xe5` are named Haste, Slow, Stop,
   Shell, Protect, Sleep, Silence, Confuse, Charm, and Addle. Handler, live-bit,
   reconciler, dedicated accessor, and generic-stat joins execute. Six bytes in
   this block remain numeric rather than inheriting candidate names.
10. **Doom countdown closed 2026-08-25:** stat `0x29` / unit `+0xd9` starts at
   3 when Checkmate applies live Doom. The per-turn path decrements it, then
   clears the live bit and battle statuses on expiry. The handler executes in
   the status gate (now thirteen checks after later packages).
11. **Action restrictions closed 2026-08-25:** stats `0x33/0x34` are
   Immobilize/Disable durations. Aim: Legs/Aim: Arm handlers execute with count
   3; Immobilize zeros movement mode and Disable is a hard ability-usability
   rejection. Only `+0xd8/+0xe6/+0xe7` remained numeric at this stage.
12. **Shared link closed 2026-08-25:** stat `0x36` / `+0xe6` is a status link
   id, not a duration. Cover copies target unit id `+0x104`; linked-state
   consumers compare that id. Only `+0xd8/+0xe7` remained numeric at this stage.
13. **Zombie revival closed 2026-08-25:** stat `0x28` / `+0xd8` is seeded to
   3 when battle statuses reset on an effective Zombie, stays 0 for an ordinary
   unit, and the zero-HP Zombie turn path decrements it before scheduling
   revival at zero. Only `+0xe7` remains numeric in this region.
14. **Recent target history closed 2026-08-25:** stat `0x37` / `+0xe7` packs
   the two most recent distinct action-target unit ids into nibbles, newest
   first. Action resolution writes it and the AI evaluator tests membership.
   All sixteen scalar bytes in the status-state region are now named.
15. **KO counters closed 2026-08-25:** stats `0x39/0x3a` / `+0xf1/+0xf2`
   count KOs inflicted by the actor and suffered by the target. A forced-KO
   path executes target HP `123 -> 0` and counters `9/11 -> 10/12`; both
   increments saturate. Nine bytes at `+0xf3..+0xfb` remain numeric.
16. **Battle position/index closed 2026-08-25:** stats `0x3e..0x40` /
   `+0xf6..+0xf8` are tile X, Y, and height; stat `0x43` / `+0xfb` is the
   zero-based battle-list index assigned at battle-object insertion. Executed
   movement-origin and list-length paths cover both families. Five bytes in
   this late block remain numeric.
17. **Late scalar block closed 2026-08-26:** stats `0x3b..0x3d` /
   `+0xf3..+0xf5` count other, Parley, and Oust removals; stats `0x41/0x42`
   are saved tile X/Y. Executed outcome accounting, purge rates, and placement
   snapshots raise named load coverage to 62/63.
18. **Unit-stat layout complete 2026-08-26:** stat `0x00` is the encoded-name
   text pointer, stat `0x22` addresses the bounded ability-state array, and
   stat `0x44` addresses the movement profile. All 63 load cases and six
   address-return cases are now named and execution-gated.
19. **Mow Down penalty closed 2026-08-26:** the ability's sole secondary raw
   effect `0x16` selects internal case 37, whose handler sets `+0xea` bit 1.
   Executing the handler halves Speed 100→50 and raises incoming hit chance
   95→100. It is named separately from ordinary Speed Down because the retail
   implementation uses distinct bits.
20. **Astra/Petrify closed 2026-08-26:** Astra and Mog Shield effect `0x25`
   select case 10 / `+0xe8` bit 4. Break, Rockseal, and Blaster effect `0x62`
   select case 46 / `+0xe8` bit 6, while Soft selects paired cancel case 47.
   Execution proves Astra is consumed while blocking Petrify; unprotected
   Petrify then zeros CT/carry `900/25→0/0` in the retail tick.
21. **Quicken closed 2026-08-26:** Quicken and Smile effect `0x1d` select case
   2 and `+0xe8` bit 1. Execution applies the bit; the turn manager builds its
   priority list from marked units and the consumed-turn path calls the same
   setter with zero. The former “present/alive” description was incorrect.
22. **Remaining CT suppressor classified 2026-08-26:** `+0xed` bit 6 blocks
   CT charging, actor selection, targeting, and result processing. Its retail
   setter at `0x080CE35C` has zero direct or pointer callers and no raw-effect
   join. Set/clear execution produces CT/carry `0/0` versus `1000/25`; the bit
   stays numeric rather than receiving an unsupported lifecycle name. The
   flag-map generator now includes this and adjacent dormant bit-5 setter.
23. **Direct descriptor sweep 2026-08-26:** twelve additional bits now have
   one-to-one published-effect, descriptor-case, handler-setter, and bit
   round-trip joins: Advice, Berserk, Regen, Auto-Life, Conceal, Attack Down,
   Boost, Defense Down/Up, Magic Down, and Resistance Down/Up. Coverage rises
   from 23 to 35 named live bits, with eighteen alternate-ability joins.
24. **Handler-only direct residues closed 2026-08-26:** Defending, Hibernate,
   Morphed, Cover, Expert Guard, and Controlled map through cases 84/58/87/
   14/55/86 to six exact setters. The Morph and Control tables repeat across
   nine and thirteen race-named actions. Coverage reaches 41 of 47 represented
   live bits; the six residues are composite or lifecycle-only.
25. **Dragon Force pair separated 2026-08-26:** its case-3 handler sets four
   stat buffs. Independent combat execution identifies `+0xec` bits 3/5 as
   Attack Up/Magic Up: base 100 becomes 109 only in the matching physical or
   magic channel, while the paired Down bit yields 89. Coverage reaches 43 of
   47 represented live bits.
26. **Lifecycle/presentation residue sweep closed 2026-08-31:** Petrify's
   companion `+0xed` bit 4 is a frozen critical-HP snapshot: Petrified units
   classify from the bit, while ordinary units use the exact 25/26-of-100 HP
   boundary. The final three bits stay numeric with an executable census:
   bit 5 has three presentation readers and a dormant setter, bit 6 has
   thirteen inactive-like battle readers and a dormant setter, and setter-only
   bit 7 has two placement writers. Coverage is 44 named of 47 represented
   live bits; every remaining bit has an explicit non-semantic classification.

**Phase 5 status:** complete 2026-08-31. All 69 generic unit-stat cases are
named, all 47 represented live bits are either behavior-backed or explicitly
classified numeric, and the 21/21 status/state gate reproduces the boundary
and residue evidence.

**Done when:** each new name is backed by execution or an identifiable reader,
and reflected in `tools/flag_map.py` / `tools/dump_stats.py` plus a
`validate_ai.py` check.

---

## Phase 6 — Job table accessor formulas

**Objective:** determine why the old raw-offset audit reported partial matches
and map all 48 accessor fields exactly.

**Result:** complete 2026-08-31. The audit premise was wrong: there are 23, not
22, partial matches, and none is a stat-at-level computation. Byte `+0x05`
redirects 47 fields to the caller fallback (`0xff`) or a direct job index
(other nonzero values); field `0x02` returns the marker itself. Packed fields
account for the other guessed-offset mismatches.

**Steps:**

1. ~~Decompile the partial-match branches.~~ All 48 jump-table cases mapped.
2. ~~Test stat-at-level computation.~~ Rejected by control flow and execution;
   the behavior is record redirection plus direct packed/load formulas.
3. ~~Execute every formula across all 116 entries.~~ 5,568/5,568 reads match;
   synthetic `+0x05=7` and resistance values 0–7 prove both causal paths.
   Field `0x28` / `+0x31` bit 0 additionally executes through the supported
   twenty-entry morph-family index.

**Done:** `tools/job_fields.py`, `tools/audit_field_map.py`, and
`tools/validate_job_fields.py` are the reproducible source of truth.

---

## Phase 7 — Make the evaluator's *rules* editable (the long-horizon decomp)

**Objective:** byte-match `sub_080C32C0` (5,350 bytes) so rule changes ship via
`make mod`.

**Why last:** it is *the* function for AI behaviour, and today only its
*constants* are patchable (the priority CSV and the 10/49 gates). Changing
rules needs it matching under `src/` — the single biggest decomp effort, and
the repo explicitly ranks it below widening the table surface.

**Steps:**

1. **Partition complete 2026-08-31.** `tools/partition_ai_evaluator.py`
   recursively follows ARMv4T control flow from all 66 roots, separating 3,958
   case-owned bytes, 88 shared bytes, four evaluator exits, and embedded data.
2. **Dominant family complete 2026-08-31.** Cases 1/2 and the 30-root
   probability-plus-absent-state shape are readable in
   `reference/ai_ability_eval.c`; CT boundaries execute and the shape census is
   locked by validation. The seven-root inverse/present-state cancellation
   family is also translated, with remove-Frog executed absent and present.
   Both zero-byte dispatch roots are explicit: eight ids accept immediately
   and eleven reject-next immediately. Cases 65-67 retain the same probability
   gate but require a positive two-short effect estimate.
3. **Readable reconstruction complete 2026-08-31.** All 92 ids / 66 roots are
   represented, including the four final calculation-heavy roots. The AI gate
   asserts complete switch coverage and the file passes a C89 syntax check.
4. Convert the readable `reference/ai_ability_eval.c` gauntlet into
   matching C under `src/`, applying the lessons in `docs/matching-notes.md`
   (ternary vs if/else for shared stores; globals as extern symbols, never cast
   literal addresses; literal-vs-`int`-variable register allocation; branch
   polarity by test kind).
   **Current compiler baseline:** explicit return/redispatch control, direct
   state calls, duplicated self/other RNG arms, and corrected cases 9/92 produce
   one 5,338-byte agbcc function versus retail's 5,350 (12 bytes short). Its
   20-byte frame and `sp+12`/`sp+16` action/index slots match retail. The inline
   modes 4–11 dispatch now retains all three scratch-pair paths and shared
   joins; the effect table is at `+0x35c` versus retail `+0x364`. Remaining work
   is instruction/root layout, not missing high-level rule families.
5. Match the **66 distinct case bodies** one at a time — each is small and
   depends only on already-matched helpers (flag getters/setters,
   `sub_080C7EA4`, the RNG, `__modsi3`).
6. Iterate with `make match SRC=... AT=... LEN=...` → `make index` → `make
   check` → `make rom` after each batch.
7. Ship the first **rule mod** (e.g., make the AI play its best option every
   time by removing the randomness) as proof the pipeline works end to end.

**Done when:** `sub_080C32C0` compiles byte-identical, and a rule edit builds
via `make mod` with `verify_mod` reporting exactly that one function changed.

---

## Phase 8 — Long tail and cleanup

- The **7 undecoded text strings** (0.3%).
- The **9 skipped maps** and the **height-flag**, if not closed in Phase 3.
- The **mission index** fields, if not closed in Phase 2.
- Revisit the deliberately-ugly matching constructs (e.g. `sub_080CDD88`'s
  load-bearing duplicated branch) once surrounding code clarifies the real
  idiom — never at the cost of the match.

---

## The standard loop (for any "map a new table / name a field" step)

1. **Static hypothesis:** `tools/find_accessors.py` (property accessors),
   `tools/job_getters.py` (direct indexing), `tools/accessor_callers.py
   --target 0xADDR --reg r1`, `tools/map_table.py`.
2. **Execution check:** `tools/emulate.py` calls the ROM's own function on
   synthetic state — a static decoder is not wrong about instructions, only
   about what they mean.
3. **Second data point:** never enshrine a meaning from one example.
4. **Round-trip:** dump → apply unedited → byte-identical ROM, or the tool is
   wrong.
5. **Regression:** add a `tools/validate_ai.py` check so the claim cannot
   silently rot.

## Explicitly do NOT do (negative results to preserve)

- **No formation table** — battle setups are scripted, one Place Character
  opcode per unit.
- **No speculative naming of four dead/raw job offsets** (`+0x02`, `+0x0c`,
  `+0x27`, `+0x2c`) — two lack accessor fields and two have no constant call
  site or direct reader.
- **No full 3,594-function decomp** — it was tracking under 1%, would take
  years, and conflicts with the stated goal.
- **No trusting published docs unverified** — Data Crystal has already been
  wrong three times here.
