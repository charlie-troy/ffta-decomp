# Tactics policy contract (A5.2, frozen 2026-10-06)

This is the frozen JSON contract between the **engine-legal candidate
adapter** (live, A5.3+) and the **pure policy chooser**
(`tools/tactics_policy.py`). It freezes before A6/A7/A10 start, so those
packets extend by adding a schema version, not by editing these meanings.

Status: **A5.2 v1 frozen; A6 v2 host extension reviewed, live recovery open**
(`python tools/validate_tactics_policy.py`). No engine semantics are claimed
by that suite: only the adapter's live legality read can establish that a
candidate is engine-legal, and only live runs can show a chosen candidate
was accepted.

Related: [strategy-runtime-scope.md](strategy-runtime-scope.md) (identity,
interception point, precedence contract), [unit-flags.md](unit-flags.md)
(status-bit evidence), [player-ai-control.md](player-ai-control.md)
(why the companion selects actions instead of delegating to retail AI).

## Position in the architecture

```
engine (owns the turn; no ROM patch)
  -> adapter: verified identity + ONLY engine-legal candidates + fresh facts
    -> tactics_policy.choose_action(snapshot, policy) -> candidate | None
      -> adapter: drives that one candidate through the proven input channel
```

The policy layer **never** writes game memory, **never** presses keys, and
never decides that a candidate is legal. It only *orders preferences among
facts the adapter already proved*. Removal of the policy layer changes no
game state, so the seam is reversible by construction.

## Frozen interface

```python
choose_action(snapshot: dict, policy: dict) -> dict | None
evaluate(snapshot: dict, policy: dict) -> dict          # outcome + reason + decision
validate_policy(policy: dict) -> dict                   # normalized copy, else PolicyError
validate_snapshot(snapshot: dict) -> dict               # normalized copy, else SnapshotError
load_policy_file(path: str) -> dict
hp_percent(hp, max_hp) -> int | None
statuses_present(unit) -> set[str] | None
target_statuses(actor, candidate) -> set[str] | None
```

* `None` from `choose_action` is the **documented no-match path** and means
  *commit nothing* — the adapter must pause (or apply its own explicitly
  documented fallback); it must never treat `None` as permission to press
  keys by itself.
* `evaluate` returns:
  `{"outcome": "selected"|"fallback"|"none", "reason": <code>,
    "scope": "character"|"job"|"party"|null, "rule_id": str|null,
    "decision": <decision|null>, "detail": str|null}`.
* A decision is
  `{"candidate_id", "kind", "action_id", "target", "target_id",
    "scope", "rule_id", "fallback", "reason"}`.

Reason codes (frozen vocabulary): `rule:matched`, `fallback:wait`,
`no-rule-match`, `no-legal-candidate`, `actor-identity-unverified`,
`snapshot-stale`, `snapshot-invalid`.

`validate_policy` raises `PolicyError` for a bad document (a configuration
error that the runner must treat as a boot failure). `evaluate` never raises
for a bad *snapshot*: an invalid, unverified or stale observation becomes
`outcome: "none"` with the matching reason, because at runtime "no
observation" must mean "no commit".

## Policy document

```json
{
  "schema": "ffta-tactics-policy/1",
  "fallback": "wait",
  "observation": { "max_age_seconds": 3.0 },
  "assignments": {
    "characters": { "Marche#7": { "rules": [ ... ] } },
    "jobs":       { "5":        { "rules": [ ... ] } },
    "party":      { "player":   { "rules": [ ... ] } }
  },
  "note": "free text, never executed"
}
```

| key | required | meaning |
|---|---|---|
| `schema` | yes | exactly `"ffta-tactics-policy/1"` |
| `fallback` | no (default `"wait"`) | `"wait"` = the identified legal Wait; `"none"` = commit nothing |
| `observation.max_age_seconds` | no (default `3.0`) | a snapshot older than this never commits |
| `assignments.characters` | no | key `"<name>#<unit id>"` (canonical decimal, id 0..254) |
| `assignments.jobs` | no | key = canonical decimal active job id |
| `assignments.party` | no | key `"player"` or `"enemy"` (the `+0x28` bit `0x8000` side) |
| `note` | no | documentation only |

A **rule set** is `{"rules": [ <rule>, ... ], "fallback": "wait"|"none", "note": ...}`.
Its `fallback` overrides the policy default when that scope matched.

A **rule** is:

```json
{
  "id": "finish-wounded-enemy",
  "enabled": true,
  "when": { "relation": "enemy", "target_hp_pct": { "lte": 25 } },
  "select": "lowest-target-hp",
  "note": "free text"
}
```

| key | required | meaning |
|---|---|---|
| `id` | yes | non-empty, unique within its rule set |
| `enabled` | no (default `true`) | a disabled rule is skipped, never partially applied |
| `when` | no (default `{}` = every legal candidate) | all predicates must hold simultaneously |
| `select` | yes | one of the frozen selectors below |

### Assignment precedence (frozen)

`character -> job -> party`, **first match wins**:

1. a `characters` entry whose key equals `"<actor name>#<actor id>"`;
2. else a `jobs` entry whose key equals the actor's active job id;
3. else a `party` entry whose key equals the actor's side.

A **matched** scope governs: its rules are walked in order and the first rule
that selects wins. If that scope's rules select nothing, the run goes to the
scope's (or policy's) fallback — it does **not** fall through to a lower
scope. Falling through would silently apply a party rule to a character whose
own rules were merely ineligible, which is the exact confusion the
precedence contract exists to prevent. A *missing* assignment (nobody named
that actor at that scope) does fall through.

### Predicates (`when`)

Only these facts are supported. Every one of them must already be present;
a missing fact makes the predicate false, so the rule is ineligible.

| predicate | value | matches when |
|---|---|---|
| `relation` | `"self"` \| `"ally"` \| `"enemy"` | the candidate's engine relation |
| `kind` | `"move"` \| `"wait"` \| `"ability"` | the candidate's command kind |
| `action_id` | integer >= 0 | the candidate's engine command/ability id |
| `ability_name` | non-empty string | an `ability` candidate whose **identified** name equals it |
| `actor_hp_pct` | comparison object | the actor's floored integer HP percent |
| `target_hp_pct` | comparison object | the candidate target's floored integer HP percent |
| `remaining_mp_after_cost` | comparison object | `actor MP - candidate cost` (negative is ineligible) |
| `actor_status_present` / `actor_status_absent` | list of status names | the actor's decoded live status bits |
| `target_status_present` / `target_status_absent` | list of status names | the candidate target's decoded live status bits |

A **comparison object** is exactly one operator from `lt`, `lte`, `gt`,
`gte`, `eq`, e.g. `{"lte": 25}`. HP percents are floored integers in
`0..100` (`hp_percent(25, 100) == 25`); MP thresholds are integers >= 0.
A bare number, a float, a bool, a string, two operators, or an unknown
operator is rejected at load time.

`target_status_*` on a `relation: "self"` candidate reads the actor's own
bytes. `ability_name` matches only `kind: "ability"` candidates: a Move that
happens to carry a name is not an ability.

### Status vocabulary (frozen)

Names are exactly these strings (case-sensitive); they decode the live
`+0xe8..+0xed` block carried as `status_bytes` with keys `"0xe8"`..`"0xed"`.
Every entry is backed by an application-handler join in
[unit-flags.md](unit-flags.md).

| byte | names (bit) |
|---|---|
| `0xe8` | Quicken (0x02), Auto-Life (0x04), Regen (0x08), Astra (0x10), Reflect (0x20), Petrify (0x40), Berserk (0x80) |
| `0xe9` | Frog (0x01), Poison (0x02), Blind (0x04), Zombie (0x08), Conceal (0x10), Boost (0x20), Defending (0x40), Hibernate (0x80) |
| `0xea` | Advice (0x01), Mow Down Speed Down (0x02), Morphed (0x04), Cover (0x08), Doom (0x10), Haste (0x20), Slow (0x40), Stop (0x80) |
| `0xeb` | Shell (0x01), Protect (0x02), Sleep (0x04), Silence (0x08), Confuse (0x10), Charm (0x20), Immobilize (0x40), Disable (0x80) |
| `0xec` | Addle (0x01), Expert Guard (0x02), Speed Down (0x04), Attack Up (0x08), Magic Up (0x10), Attack Down (0x20), Defense Up (0x40), Magic Down (0x80) |
| `0xed` | Resistance Up (0x01), Resistance Down (0x02), Defense Down (0x04), Controlled (0x08), Petrify Critical (0x10) |

Deliberately **not** exposed (fail closed until a packet proves them):
`+0xe8` bit 0, the numeric `+0xed` bits 5–7 (no unique game-facing meaning —
see unit-flags.md), the persistent `+0x28` bits other than the side bit
already used for `party`, and every status *duration* field
(`+0xd9..+0xe7`): a policy cannot yet say "Doom countdown is 1".

### Selectors and determinism

| selector | picks |
|---|---|
| `first` | the first matching candidate in adapter order |
| `lowest-target-hp` / `highest-target-hp` | by `target_hp`, ascending / descending |
| `lowest-remaining-mp` / `highest-remaining-mp` | by `actor MP - cost`, ascending / descending |

Candidates that lack the selector's fact are not orderable and are excluded
from that rule's selection; if none is orderable, the rule selects nothing
(fail closed). **Ties always break on the candidate id ascending
(lexicographic)**, so a rule's choice is independent of adapter ordering and
reproducible from the snapshot alone. Snapshot candidate ids must be unique.

## Snapshot (adapter -> chooser)

```json
{
  "schema": "ffta-tactics-snapshot/1",
  "identity": "verified",
  "age_seconds": 0.4,
  "observed_at": 1760000000.0,
  "actor": {
    "name": "Marche", "id": 7, "job_id": 5, "side": "player",
    "hp": 88, "max_hp": 100, "mp": 12, "max_mp": 20, "ct": 353,
    "tile": [4, 10], "status_bytes": { "0xe9": 0, "0xea": 0 }
  },
  "candidates": [
    {
      "id": "ability:12:unit:20", "kind": "ability", "action_id": 12,
      "legal": true, "cost": 6, "relation": "enemy",
      "target": { "kind": "unit", "id": 20 },
      "target_hp": 21, "target_max_hp": 100,
      "target_status_bytes": { "0xe9": 2 },
      "ability_name": "Cure"
    },
    { "id": "wait", "kind": "wait", "action_id": 2, "legal": true, "cost": 0 }
  ]
}
```

| field | required | meaning |
|---|---|---|
| `schema` | yes | exactly `"ffta-tactics-snapshot/1"` |
| `identity` | yes | `"verified"` to commit anything; any other string means no commit |
| `age_seconds` | yes | observation age the adapter measured; compared to `max_age_seconds` |
| `actor` | yes | name, id (0..254), job_id, side (required); hp/max_hp/mp/max_mp/ct/tile/status_bytes optional |
| `candidates` | yes | list; empty is legal (then only an explicit `fallback: "none"` outcome exists) |
| `observed_at`, `note` | no | metadata (never read by the chooser) |

Each candidate requires `id` (unique, non-empty), `kind`, `action_id`,
`legal` (**the adapter's assertion that the engine offers/accepts it**) and
`cost`. `relation`, `target` (`{"kind":"unit","id":n}` or
`{"kind":"tile","x":…,"y":…}`), `target_hp`, `target_max_hp`, `target_mp`,
`target_status_bytes`, `ability_name` are optional: absence is honest and
makes the dependent predicates ineligible.

A `legal: false` candidate is a **valid observation** (the adapter saw it and
the engine rejects it) but is never selectable, including as the Wait
fallback.

Candidate ids are the adapter's; the recommended convention is
`"<kind>:<action_id>:<target>"` (for example `"move:0:tile:4,11"` or
`"ability:12:unit:20"`), and `"wait"` for the identified Wait. The chooser
treats them as opaque strings — only their uniqueness and their tie-break
role are contractual.

## Fallback semantics

`fallback` is the **explicit** supported fallback, in the A4 precedence
contract's sense: the identified legal Wait where its validity is
established. It is applied only when no rule of the matched scope selected a
candidate.

* `"wait"`: commit the legal `kind: "wait"` candidate (reason
  `fallback:wait`, `rule_id: "fallback"`, `fallback: true`). If the snapshot
  contains no legal Wait, the outcome is `none` / `no-legal-candidate`.
* `"none"`: commit nothing (outcome `none` / `no-rule-match`).

This is **not** retail AI: it is the companion's own explicit no-tactics
behavior. Calling a Wait fallback "the game's AI" would misdescribe the
architecture.

## Validation and rejection

Rejected at load time (`PolicyError`): unknown keys at the policy,
`observation`, `assignments`, rule-set, rule and `when` levels; a wrong
`schema`; unknown `fallback`, `selector`, `relation`, `kind`, `party` key,
status name (case-sensitive) or comparison operator; a threshold that is not
a single integer in range (including bools, floats, strings, `{}`, two
operators); a malformed assignment key (`Marche` / `Marche#07` / `05` /
`PLAYER`); a duplicate rule id; a non-object policy.

Rejected as a snapshot (`SnapshotError` -> `none` / `snapshot-invalid`):
missing/blank identity, missing actor name/id/job/side, non-integer stats,
out-of-range tile or status byte, unknown key at any snapshot level,
duplicate candidate id, missing `age_seconds`, negative age, wrong schema.

Never committed (no exception, `outcome: "none"`): identity other than
`"verified"`; snapshot older than `max_age_seconds`; any malformed snapshot.

## A6 resource/recovery extension (schema v2, 2026-10-06)

`ffta-tactics-policy/2` retains v1's ordering, fallback, freshness and identity
rules. `ffta-tactics-snapshot/2` adds item candidates. These are host contracts;
the current live adapter still emits v1 Move/Wait snapshots, so loading a
healer policy does not enable casting, targeting or inventory access.

| v2 addition | Meaning |
|---|---|
| policy/ruleset `consumables` | Boolean, default false. The governing scope may override the policy value; no lower-scope inheritance. When false, all item candidates are removed before rule evaluation. |
| `when.target_hp` | Absolute nonnegative HP comparison (`lt/lte/gt/gte/eq`). Missing HP makes the rule ineligible. `eq: 0` separates KO from living 1/200 HP, which also floors to 0 percent. |
| candidate `kind: item` | Requires nonempty `item_name` and nonnegative integer `count`, alongside the ordinary candidate fields. `count: 0` is unusable even if marked legal. |
| `when.item_name`, `when.item_count` | Exact item name and remaining-count comparison. Enabled item predicates, including `kind: item`, require consumables opt-in. Disabled rules may document future intent. |

V1 documents reject v2-only keys and item kinds. The existing
`remaining_mp_after_cost` predicate implements the MP reserve; absent actor MP
or a negative remainder rejects the candidate. Inventory count consumers and
live ability cost/target availability are **not decoded by this extension**.

The deliberately narrow `healer.json` preset names **Life** for a KO ally and
**Cure** for a living wounded ally/self. Each cast keeps eight MP in reserve.
Ally relation and low HP alone do not establish recovery semantics: a legal
Protect candidate must not satisfy a heal or revive rule. Ability names are
contract inputs here, not evidence that the live engine offers those casts.
Future adapter work must prove their legal targets and actual effects (including
status interactions), then verify HP/MP deltas. Consumables remain disabled.

Reviewed host evidence: `outputs/autobattle/a6-review-policy/checks.json`,
119 checks including non-vacuity mutants and regressions for unrelated ally
abilities, Cure on KO, Life's reserve boundary and kind-only item opt-in.
See [A6 receipt](receipts/autobattle/A6.json) for required unknown live gates.

## Remaining unsupported live capabilities

Position/distance predicates, reachability, damage or hit-chance estimation,
item/consumable reads, ability/revive execution, law constraints, multi-turn planning,
movement preference (approach/hold/kite), enemy-party control, and any
predicate naming a status that is not in the frozen vocabulary above. A
policy with an unknown predicate fails to load. Supported host predicates whose
facts the live adapter cannot supply remain ineligible. A6's schema support
does not establish live recovery support. A7 will extend the contract explicitly.

## Shipped presets (`configs/tactics/`)

| file | behavior |
|---|---|
| `default.json` | no rules; every turn uses the explicit legal-Wait fallback |
| `damage-focused.json` | party-player rules: finish an enemy at `<= 25%` HP, else pressure the lowest-HP enemy offered |
| `contrast-two-ally.json` | per-character divergence on the proven Move/Wait candidates (`Marche#7` takes a Move, `Montblanc#5` holds with Wait) — a contract demonstration, not tactics quality |
| `hp-split.json` | one party rule set conditioned on the actor's own engine-read HP percent (`<= 80%` holds, otherwise advance); calibrated to the A4 two-ally fixture so one live run exercises both rules |
| `hold-below-30.json` | the A5.4 condition-change twin of `hp-split.json`: identical rules, one value different (threshold 30 instead of 80) |
| `healer.json` | v2 host preset: Life on KO ally, Cure on living wounded ally/self, eight-MP reserve; items disabled. Live adapter currently cannot offer these abilities. |

All are validated by the host suite on every run. Resource preservation and
live healer execution remain A6 work.

## Live adapter seam (A5.3, 2026-10-06)

`tools/tactics_adapter.py` is the impure half: it reads the engine (read-only)
and builds the snapshot. `run_autobattle.py --tactics-policy PATH` replaces the
scenario's fixed per-actor assignment with the chooser; the policy is validated
*before* the emulator is touched and a bad document exits 2.

Facts the adapter supplies live, and what proves each one:

| fact | source |
|---|---|
| actor name/id/job/side | the A5.1 verified fresh-menu owner row (boot-guard identity + cursor-own-tile pairing) |
| actor hp/max_hp/mp/max_mp/ct | the same roster record (`+0x18`, `+0x1A`, `+0x1C`, `+0x1E`, `+0xD0`) |
| actor tile | the same record `+0xF6`/`+0xF7`, already part of identity validation |
| `move` candidate | `plan_identified_move` returns a plan (decoded command cursor reads Move 0 and the target cursor is readable) |
| `wait` candidate | `plan_identified_wait` returns a plan (decoded command cursor reads a known command 0/1/2) |
| `age_seconds` | owner observation -> decision, measured by the caller; live runs measured 1.5-1.6 s, dominated by the boundary screenshot |

Candidate `legal: true` means **the menu offers that command in this state**, not
that a Move destination is reachable: the C2 driver steps the real cursor,
reads the reached tile from RAM before confirming, and the runtime independently
verifies the whole party's tile delta against the RAM-read destination. Rows the
narrow family cannot supply (relation/target/ability facts, MP cost, range) stay
absent, so predicates needing them are ineligible rather than assumed.

A decision the engine no longer offers **cancels the commit** (zero key
writes); it never falls back to a command the policy did not choose. The
scenario path keeps its identified-Wait fallback; the policy path does not.

### Live evidence (2026-10-06)

* `outputs/autobattle/a53-live-contrast-01` — `contrast-two-ally.json`: turn 1
  Marche (slot 7) matched `marche-takes-the-walk` in the `character` scope, took
  the Move, engine moved only Marche `(4,10)->(4,11)`; turn 2 Montblanc
  (slot 5) matched `montblanc-holds-position` and took the Wait with no
  movement. Ages 1.57 s / 1.51 s.
* `outputs/autobattle/a53-live-hp-split-01` — `hp-split.json`, one party rule
  set over the same fixture (Marche 442/442 = 100%, Montblanc 177/241 = 73%):
  turn 1 Marche matched `advance-when-above-threshold` and moved; turn 2
  Montblanc matched `hold-when-below-threshold` and waited. Same-job allies,
  one engine-read fact, contrasting decisions, both engine-verified.

During both runs the enemy clan took ~178 router hits of retail activity and
the verified result still attributed movement only to the acting player — the
misleading-enemy-effect control holds on live data.

### Explicitly not proven by A5.3

`insufficient MP` and `illegal range/target` controls are **not applicable** to
this family: neither live candidate carries an MP cost, a ranged target, or an
ability. They remain open for the ability family, which needs the Action
submenu decoded (command cursor 1 -> ability list -> target mode). Until then no
ability predicate can become an enabled option: the schema rejects any
predicate the adapter cannot supply facts for, and the adapter offers only what
the menu names.

## Conditional-tactics closure (A5.4, 2026-10-06)

The A5 requirements are met with host **and** live evidence, for the narrow
family: the public runner follows per-character rules (two job-5 allies take
different commands in one battle) and an engine-read condition changes the
decision and the result. Full detail and criteria live in the `a5_4` object of
`docs/receipts/autobattle/A5.json`; the decisive live pair is
`hp-split.json` vs `hold-below-30.json` on the same starting state — identical
rules and notes, one threshold changed:

| policy | Marche (100% HP) | Montblanc (HP differs; see audit below) |
|---|---|---|
| `hp-split.json` (`<= 80`) | `advance-when-above-threshold` -> Move `(4,10)->(4,11)` | `hold-when-below-threshold` -> Wait, no movement |
| `hold-below-30.json` (`<= 30`) | `advance-when-above-threshold` -> Move `(4,10)->(4,11)` | `advance-when-above-threshold` -> Move `(5,10)->(5,11)` |

Audit correction (2026-10-06): Montblanc was **177/241 (73%)** in the
threshold-80 run, but **84/241 (34%, floored)** in the threshold-30 run.
The second figure agrees between `engine_result.players_before` and the
boundary screenshot. The saved fixture is identical; intervening damage
differs, so these are not identical decision states. Both HP values lie in
the interval where threshold 80 selects Wait and threshold 30 selects Move.
The live pair is consistent with the rule contrast, but does not isolate
one changed input at the decision boundary. Future turn metadata includes
the exact chooser `snapshot`, allowing direct host replay without inferring
policy facts from nearby engine-result observations.

Marche is the control (unchanged decision in both runs); Montblanc's decision
and engine result both change with the condition. Runs:
`outputs/autobattle/a53-live-hp-split-01`, `a53-live-hp-split-30-01`.

Two integration defects were found by this evidence and are fixed with their
own regressions:

* **Adopted-session cleanup.** `--resume` adopts the emulator by pid without a
  `Popen`, so `FixtureSession.stop()`'s old `self.proc is not None` gate skipped
  the kill and logged nothing while the CLI receipt said `terminated` —
  observed live (receipt `terminated pid: 57716`, mGBA 57716 still listening).
  `tools/validate_session_cleanup.py` pins the intended decisions (4/4, with a
  pre-fix negative control where the old gate fails the suite).
* **Resume scenario mismatch.** The fixture guard expectations come from the
  scenario file, which the receipt does not carry, so resuming with the wrong
  `--scenario` failed as a 45 s "struct_count=8 expected=7" roster guard.
  `--resume` now refuses a scenario whose id differs from the resumed run's.

Still explicitly **not** claimed: complete-battle/defeat behaviour under a
policy, law or status-conditioned tactics, ability targeting (MP/range), and
movement preference. The retained STOP, monitor-client handoff and resumed
continuation gates are C1/C3 shapes re-run on this revision, not new
capability.

## Host evidence

A6 live research is recorded in [a6-recovery-research.md](a6-recovery-research.md):
two constructed-fixture self-Cure casts consume six MP and increase HP;
five-MP Cure is disabled and rejected. The decoded effective-MP reader matches
2,429 executions of the retail cost function. These are research results;
the public adapter still offers only Move/Wait. Recovery-policy and
wounded-party acceptance remain open until modal actor/target identity and
confirmation guards are integrated and validated.

`python tools/validate_tactics_policy.py` -> **94/94 PASS**, writing
`outputs/autobattle/a52-tactics-policy/checks.json`. Coverage: every
supported predicate; HP/MP threshold boundaries; `lte` inclusive vs `lt`
strict; floored percent; missing/zero-max facts; precedence and
non-fall-through; scope fallback override; disabled rules; ties and
duplicate ability names across both adapter orders; repeated evaluation
identity; empty candidate sets; `fallback: none`; unverified identity; stale
and malformed snapshots; illegal candidates; ~40 rejection cases; every
shipped preset; and a **non-vacuity check** that mutates the module five ways
(legality gate, identity gate, staleness gate, fallback legality, tie-break)
and requires each mutant to fail the suite.

Limits of that evidence: it is *pure host control-flow* evidence. It does not
show that any candidate is engine-legal, that a real menu accepts the chosen
command, or that the decision improves battle outcomes. Those are A5.3/A5.4
live requirements.
