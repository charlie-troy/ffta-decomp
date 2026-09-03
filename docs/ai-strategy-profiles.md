# Auto-battle strategy profiles

Strategy profiles turn the AI controls already verified in the retail ROM into
one repeatable JSON configuration. A profile can currently control:

- per-ability likelihood and rule selectors;
- per-job fallback-action likelihood;
- the shared self-target and other-target status-effect gates;
- the target-candidate tie-break policy.

This is the first layer of a broader tactics system. It controls which actions
survive eligibility filtering and how equal candidates are ordered. The
candidate score model itself, movement intent, resource budgets, ally/enemy
weighting, and multi-turn planning still require additional code mapping and
are tracked as the rest of Phase 9.

## Normal workflow

Start with one of the shipped profiles or copy it under a new name:

```bash
python tools/ai_strategy.py validate configs/ai-strategies/aggressive.json
python tools/ai_strategy.py preview baserom.gba configs/ai-strategies/aggressive.json
python tools/ai_strategy.py apply baserom.gba configs/ai-strategies/aggressive.json ffta-aggressive.gba
python tools/verify_mod.py baserom.gba ffta-aggressive.gba --strict
```

`preview` runs the complete selector and safety logic without writing a ROM.
`apply` refuses to overwrite its input or an existing output unless `--force`
is explicit, and publishes through a same-directory atomic replace. Profiles
currently support only the verified FFTA USA base SHA1 shown below, preventing
accidental application to another revision or an already modified ROM.

## Profile shape

```json
{
  "schema_version": 1,
  "name": "My strategy",
  "description": "What this profile is trying to accomplish.",
  "base_sha1": "4ac05441f4de70a4ec3dd932116346c61b8783d9",
  "status_gates": {"self": 25, "other": 75},
  "target_ordering": "retail",
  "ability_rules": [],
  "job_rules": []
}
```

The status values range from 0 to 100. They change how often the evaluator
accepts status-effect plays against the acting unit itself versus any other
target.

## Ability rules

Rules select abilities using the original input ROM, then apply in file order.
Later rules can intentionally override earlier broad defaults. This makes a
profile readable as “establish a baseline, specialize categories, then add
exceptions.”

```json
{
  "name": "Prefer strong fire attacks",
  "match": {
    "fields": {
      "element": 1,
      "power": {"min": 40},
      "ai_priority": {"min": 1}
    },
    "flags_all": ["offensive"],
    "flags_none": ["reflectable"]
  },
  "set": {"ai_priority": 95},
  "expect_matches": 4
}
```

Selectors are combined with AND:

- `ids`: exact numeric ability ids;
- `names`: case-insensitive exact displayed names;
- `name_contains`: case-insensitive fragments, with any fragment matching;
- `fields`: any ability-table field with an exact value, a value array, or a
  condition using `eq`, `ne`, `in`, `not_in`, `min`, and `max`;
- `flags_all`, `flags_any`, `flags_none`: semantic ability flags, with or
  without the `f_` prefix.

Ability actions may `set`, `add`, or `multiply` `ai_priority`, `ai_behaviour`,
or `ai_condition`. A field can appear in only one action per rule. Priority is
limited to 0–100 and behavior to the verified 0–3 range; an out-of-range result
rejects the whole profile. `expect_matches` is optional but strongly
recommended for important rules because it detects selector drift.

Use ids when a displayed name is duplicated. For example, `Judge Sword`
appears more than once in the retail data; a name rule intentionally selects
every occurrence.

## Job rules

Fallback actions use the job table's priority byte. Job rules support
`indices`, `names`, `name_contains`, and conditions on `ai_priority`:

```json
{
  "name": "Raise Soldier fallback priority",
  "match": {"names": ["Soldier"]},
  "set": {"ai_priority": 90},
  "expect_matches": 1
}
```

Only `ai_priority` is writable through a strategy rule. The broader job editor
still exposes the rest of the table, but combat statistics are balance data,
not tactical policy, and remain deliberately separate.

## Target ordering

`target_ordering` selects how the game orders equal target candidates. The
candidate sort (inside `sub_080C2940`) compares a signed halfword **impact
score** at candidate `+0x0c` (see the candidate-layout section in
[ai-findings.md](ai-findings.md)), then the two candidates' AI-priority bytes,
and breaks a full tie with one RNG draw, swapping the pair when
`Rand() % 101 <= 49` — about half the time.

- `retail` (default): keep both random draws.
- `deterministic_ties`: each roll window becomes an unconditional branch to
  the keep-ordering path. The mode=1 window (0x080C2F7E..0x080C2F94) makes
  equal candidates keep the earlier one; the mode=0 window
  (0x080C2E9E..0x080C2EB6) makes an unexempted negative-score challenger
  never swap instead of coin-flipping. Both keep the conservative side of the
  retail coin, and the battle RNG is untouched.

The window is reachable only by falling through the comparator's equality
compare; no branch, jump-table entry, or ROM pointer targets it. Strict mod
verification attributes its 22 bytes as "AI target tie-break".

**Scope.** `sub_080C2940` runs two comparator regimes, selected by its second
argument, and the whole-ROM BL scan finds exactly two callers: the
candidate-sort call at `0x080C077C` (`mode=1`, argument 8) and the sibling
call at `0x080C078A` (`mode=0`, argument 0x87 — the slot walk is skipped and
the record walk dispatches straight to its case-7 regime, which owns the
HP-weighted enumeration roll: healthy targets get the random BST key
`Rand() % 0x201 + 0x10000`, low-HP targets their current HP; a live battle
consumes one roll per healthy-target record, 3 in the traced fight).
`deterministic_ties` pins three sites: the mode=1 full-tie roll, the mode=0
probabilistic order gate at `0x080C2E9E` (reached when the challenger's score
is negative and three exemption scans — KO, healing, Heaver effects — find
nothing; it decides whether the swap is even considered before the
ally-safety checks), and the mode=0 enumeration branch at `0x080C2C58`, so
mode=0 full ties break by ascending current HP instead of a random
enumeration order. The regimes are disjoint (nothing in the `mode=0` block
branches into the mode=1 window), and all windows are reached only by
falling through their preceding compares, so the same-size patches are safe.

With this control shipped, no RNG draw remains anywhere in
`sub_080C2940`.

The sort's primary key is the impact score that `sub_080C2314` writes per
candidate (estimated numeric effect, clamped to death/overheal bounds), and
the secondary key is the ability's AI-priority byte. A strategy profile that
wants different target choices therefore has two future levers: rewriting the
score after `sub_080C2314` returns, and the already-shipped priority
(`ai_priority`) control. Both are unverified as profile controls and remain
roadmap work.

## Action selection

`action_selection` selects how the game picks which behaviour slot an actor
acts on, upstream of target ordering. The slot walk (inside `sub_080C2940`,
0x080C29A2..0x080C2A8C) holds the actor's behaviour array (count at
arg0+0x527e, kind bytes at arg0+0x5276+i) and steps slot index i from 0:
every non-last slot survives only on a `Rand() % 101 > 50` roll (window
0x080C29BE..0x080C29D4), and the selected slot's kind dispatches through a
jump table at 0x080C29FC. Two of the eight kinds flip their own coin: kind 1
(0x080C2A22) sets flag 0x80 or 0x81, kind 2 (0x080C2A42) sets 0x80 or 0x82.

- `retail` (default): keep all three draws.
- `first`: the walk's conditional branch becomes unconditional (slot 0 is
  always processed and the roll code is never reached), and each coin's
  `Rand()` call becomes `movs r0, #0` + NOP, so flag 0x80 wins. Every forced
  value — slot 0, flag 0x80 twice — is an outcome retail itself produces, so
  the patch cannot construct a state the retail AI could not reach. The
  battle RNG is never consulted.

Each site is a same-size patch verified against the exact retail bytes, and
no branch, jump-table entry, or ROM pointer lands inside any of them. Strict
mod verification attributes the 9 changed bytes as "AI action walk roll" and
"AI kind-1/kind-2 behaviour coin".

**Live proof.** In the real frozen-seed snowball battle, retail consumes 1
draw inside one sort call (a Rand() breakpoint pins the caller at
lr=0x080C2A27, the kind-1 coin); NOPing exactly that call with everything
else retail drops the battle to 0 draws. With `action_selection: first`, the
live battle consumes 0 draws, and composed with `deterministic_ties` an
engineered three-candidate tie also costs 0 draws (retail: 3).

The validator executes the walk window over 500 seeds per coin-bearing kind:
retail draws in 500/500 runs per kind, the patched ROM in 0/500 with the RNG
state untouched and only flag 0x80 produced.

## Shipped profiles

- `aggressive.json` establishes a low general baseline, strongly favors
  offensive abilities, keeps healthy-target debuffs competitive, raises the
  shared status gates, and makes equal-candidate target ties deterministic.
- `deterministic-actions.json` sets every retail-enabled ability and job
  fallback priority to 100, removes the known shared status-gate refusal
  rolls, and pins action selection (`action_selection: first`). It is useful
  for repeatable testing, but deliberately keeps retail target ordering
  (including its tie roll), damage randomness, and effect-specific evaluator
  cases.

## Safety contract

The profile is built entirely in memory and written only after every rule has
validated. Unknown keys, invalid selectors, unexpected match counts, wrong ROM
hashes, out-of-range results, and zero-match rules all fail closed. The
strategy validator proves the shipped profiles change only the declared
table fields and patch windows, executes changed job priorities through the
retail getter, and executes the tie window, the mode=0 order gate, and the
action-selection walk on retail and patched code: retail rolls about half of
500 seeded runs, the patches pin the conservative side every time, and no
patched window ever touches the RNG.

```bash
python tools/validate_ai_strategy.py baserom.gba
```

A live census (frozen-seed snowball battle, exact LCG-step counting)
measures the retail sort calls at 1 draw (mode=1) and 3 draws (mode=0, one
HP-weighted enumeration roll per healthy-target record), and every patched
build at 0 — with an engineered three-candidate tie costing retail 3 draws
in the mode=1 call and 0 under the patches.
