# Remaining-work roadmap

How to read this: the repo's own rule (CLAUDE.md) is **widen the no-compiler
modding surface first; match more functions last.** This roadmap follows that.
Each phase lists the objective, why it is worth doing now, concrete steps using
tools that already exist, and a definition of done. The reusable loop for any
"map a table / name a field" step is stated once at the end.

State snapshot: 172 functions matched (4,536 bytes) · full 16 MB ROM rebuilds
byte-identical · CI hash gate on every function · 3,594 functions discovered ·
abilities, jobs, items, missions and map terrain mapped and editable · text
decodes at 99.7% · 8/8 execution checks pass (`tools/validate_ai.py`).

Phase 0 was re-verified on 2026-08-24: `make check` verified 172/172 function
hashes, `tools/validate_ai.py` passed 8/8 checks, and `make rom` reproduced the
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
     entries; "b04 unknown" vs race confirmed; four dead offsets now closed).
     Mark it superseded.
   - `docs/ai-findings.md` still guesses ability `+0x1A` is "accuracy";
     `docs/ability-table.md` proved it is `ai_priority`. Fix the stale table.
2. Run the full gate and record a green baseline:
   ```bash
   make check                              # CI gate, no ROM needed
   python tools/validate_ai.py baserom.gba # must stay 8/8
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
   unit with a fractional carry. Three status bits acquire behavioural handles
   (`+0xe8` bits 1/6, `+0xed` bit 6). The live turn is captured in
   `docs/whole-battle-trace.md`.
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
   Magic, Appraise, Gather, Smithing, Craft, Negotiate and Track skill points.
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
5. Name the mission index fields at `0x08563A7C`: `+0x00` (0–30) and `+0x01`
   (0–179). The table boundary is now corrected to 255 records; the two leading
   fields remain positional until a reader proves their ordering/grouping role.
6. Expose every newly-named field in `tools/mission_table.py`,
   round-trip-verified, and add a validation check. **Done for the nine clan
   progression fields, dispatch job rules, dormant dispatch item rule, and pub
   fee**; repeat for later discoveries.

**Done when:** a known mission's full reward is reproducible from named data,
and every new field round-trips byte-identically.

---

## Phase 3 — Map blocks beyond terrain

**Objective:** decode and make editable the tile arrangement, the `+0x08`
block, and the graphics.

**Why:** the README lists it; terrain already round-trips and the LZ77 codec
works both directions, so the pipeline exists and this is pure extension.

**Steps:**

1. **Tile arrangement** (`+0x04`): decompress and infer the layout — map 0's
   228 tiles should correlate with the terrain `(height, permission)` pairs.
2. **The `+0x08` block**: decompress, characterize, and find its readers.
3. **Graphics** (`+0x00`): implement the GBA **Huffman** variant (the
   `0x20`/`0x22` first-byte range) in `tools/ffta_lz.py`, which today only does
   LZ77.
4. **Animation blocks** (`+0x14/+0x18/+0x1c`, on 83/162 maps) and the **mode
   bytes** (`+0x54/+0x55`).
5. Resolve the **height >127 flag** (every 16th tile in map 0, bit 7 set — a
   flag, not elevation).
6. Handle the **9 maps** whose height block lacks the `11 FF FF FF` header,
   currently skipped.
7. Give each newly-decoded block a dump/apply command with the same
   grow-refusal guard `apply-terrain` uses.

**Done when:** arrangement plus one more block are editable with byte-identical
round-trip and a size guard.

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
2. `+0x0d` and `+0x0e` — unnamed accessor properties.
3. `+0x0c` flag byte — only bit 1 is understood; test the other bits against
   observable item behaviour.

**Done when:** each is named from a reader that does something identifiable,
and round-trips byte-identically.

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
   ids.
3. Name the remaining **unit struct** stats — the 17 `u8` stats
   (`+0x04`–`+0x14`) and the unnamed `u16`s — by finding code that reads a stat
   and does something identifiable, exactly as the HP pair was pinned.
4. Decompile the **capability setters** `0x080CE420`–`0x080CE480`.
5. Resolve whether **resistance slot 2** (a real slot no field id reaches) is
   read by any path.

**Done when:** each new name is backed by execution or an identifiable reader,
and reflected in `tools/flag_map.py` / `tools/dump_stats.py` plus a
`validate_ai.py` check.

---

## Phase 6 — Job table: the 22 computed fields

**Objective:** determine what the accessor's 22 conditional fields compute.

**Why:** closes the last genuinely-unknown *live* job fields (the four dead
offsets are already closed by enumeration; these 22 are reachable but
computed).

**Steps:**

1. Decompile the conditional branches of `sub_080C8570` that fall in the
   "matches on some entries" group.
2. Test the hypothesis the docs already name: most sit on growth rates and look
   like a **stat-at-level** computation.
3. Execution-verify each formula against all 116 entries (the same audit
   technique as `tools/audit_field_map.py`).

**Done when:** each of the 22 has a stated formula verified across all 116
entries.

---

## Phase 7 — Make the evaluator's *rules* editable (the long-horizon decomp)

**Objective:** byte-match `sub_080C32C0` (5,350 bytes) so rule changes ship via
`make mod`.

**Why last:** it is *the* function for AI behaviour, and today only its
*constants* are patchable (the priority CSV and the 10/49 gates). Changing
rules needs it matching under `src/` — the single biggest decomp effort, and
the repo explicitly ranks it below widening the table surface.

**Steps:**

1. Convert the already-readable `reference/ai_ability_eval.c` gauntlet into
   matching C under `src/`, applying the lessons in `docs/matching-notes.md`
   (ternary vs if/else for shared stores; globals as extern symbols, never cast
   literal addresses; literal-vs-`int`-variable register allocation; branch
   polarity by test kind).
2. Match the **66 distinct case bodies** one at a time — each is small and
   depends only on already-matched helpers (flag getters/setters,
   `sub_080C7EA4`, the RNG, `__modsi3`).
3. Iterate with `make match SRC=... AT=... LEN=...` → `make index` → `make
   check` → `make rom` after each batch.
4. Ship the first **rule mod** (e.g., make the AI play its best option every
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
- **No re-opening the four dead job offsets** (`+0x02`, `+0x0c`, `+0x2c`,
  `+0x31`) — proven unreachable by enumeration.
- **No full 3,594-function decomp** — it was tracking under 1%, would take
  years, and conflicts with the stated goal.
- **No trusting published docs unverified** — Data Crystal has already been
  wrong three times here.
