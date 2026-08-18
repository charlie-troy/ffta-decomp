# Modding the battle AI

Two ways to change AI behaviour, in increasing order of effort.

## 1. Edit the ability table (no code, no compiler)

The AI's per-ability tuning is data. Three bytes of each 28-byte entry decide
how the AI treats that ability, for all 347 of them:

| field | effect |
|---|---|
| `ai_priority` | how eagerly the AI reaches for it. **Higher means less likely.** |
| `ai_behaviour` | when it is considered: `1` low HP, `2` healthy target, `3` last resort |
| `ai_condition` | special-case handling; `0` on 306 of 347 abilities |

```bash
python tools/ability_table.py dump  baserom.gba abilities.csv
# edit abilities.csv in any spreadsheet
python tools/ability_table.py apply baserom.gba abilities.csv ffta-mod.gba
```

The flag word at `+0x10` is expanded into named boolean columns
(`f_offensive`, `f_reflectable`, `f_ignore_silence`, ...) so bits can be
toggled without hex. Bits with no known meaning keep a `f_bitN` label so the
word still round-trips exactly. Verified: re-applying an unedited dump produces
a byte-identical ROM, and flipping one flag changes exactly one byte.

`apply` rewrites only the fields that differ and prints every change, so a
stray edit is visible rather than silent. It refuses values that do not fit the
field width and leaves the ROM size untouched.

Worked example, making the AI much keener on Cure, Cura and Curaga:

```
  id   1 ai_priority: 80 -> 10
  id   2 ai_priority: 65 -> 10
  id   3 ai_priority: 50 -> 10
```

That produced a ROM differing from the base by exactly three bytes, all at
offset `0x1A` of the three entries.

`ai_behaviour` is worth understanding before changing it. Value `2` is what
`sub_080C32C0` implements by **rejecting** the ability when the target is below
half HP, which is why status and debuff abilities carry it: there is no point
blinding something about to die. Setting a healing ability to `2` would make the
AI refuse to heal badly hurt allies.

## 2. Change the evaluator itself

`sub_080C32C0` is the AI's ability evaluator: an eligibility gauntlet followed
by a 92-case switch on the ability's effect id. Rules live there rather than in
the table, for example rejecting an ability whose MP cost exceeds the unit's
current MP.

That function is not yet decompiled. Doing so means writing C that matches, then
editing it and building with `make mod`, which does not require a SHA1 match and
reports which functions changed:

```bash
make mod
```

Anything reported outside a function you deliberately edited is a bug.

## What is known

- `docs/ability-table.md` — all 28 bytes of an ability entry
- `docs/unit-struct.md` — 65 of 69 unit stat fields, including HP at `+0x18` and MP at `+0x1C`
- `docs/unit-flags.md` — 56 status/capability bits and the accessors for each
- `docs/ai-findings.md` — the evaluator, its data tables and the rules read so far
