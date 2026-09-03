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
candidate sort (inside `sub_080C2940`) compares a signed halfword score at
record `+0x10`, then two signed bytes, and breaks a full tie with one RNG
draw, swapping the pair when `Rand() % 101 <= 49` — about half the time.

- `retail` (default): keep the random tie-break.
- `deterministic_ties`: the roll window (0x080C2F7E..0x080C2F94) becomes an
  unconditional branch to the keep-ordering path, so the earlier candidate
  wins every tie and the battle RNG is untouched. This changes target choice
  only where retail would have flipped a coin.

The window is reachable only by falling through the comparator's equality
compare; no branch, jump-table entry, or ROM pointer targets it. Strict mod
verification attributes its 22 bytes as "AI target tie-break".

## Shipped profiles

- `aggressive.json` establishes a low general baseline, strongly favors
  offensive abilities, keeps healthy-target debuffs competitive, raises the
  shared status gates, and makes equal-candidate target ties deterministic.
- `deterministic-actions.json` sets every retail-enabled ability and job
  fallback priority to 100 and removes the known shared status-gate refusal
  rolls. It is useful for repeatable testing, but deliberately keeps retail
  target ordering (including its tie roll), damage randomness, and
  effect-specific evaluator cases.

## Safety contract

The profile is built entirely in memory and written only after every rule has
validated. Unknown keys, invalid selectors, unexpected match counts, wrong ROM
hashes, out-of-range results, and zero-match rules all fail closed. The
strategy validator proves the shipped profiles change only the four declared
surfaces, executes changed job priorities through the retail getter, and
executes the tie window on retail and patched code: retail swaps about half of
500 seeded ties, the patch swaps none, and the patched window never touches
the RNG.

```bash
python tools/validate_ai_strategy.py baserom.gba
```
