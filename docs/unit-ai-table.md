# Fallback AI table (0x08521A14)

Stride `0x34` (52 bytes), **123 entries** (index 123-124 are zero, 125 onward
is unrelated data). Indexed by the unit byte at `+0x05`.

`sub_0813413C` reads `+0x32` from here as the AI priority when an action
carries no ability id, on the same 0-100 scale as the ability table.

## Field accessor

`sub_080C8570(index, ?, fieldId)` dispatches through a 48-entry jump table,
the third table in this codebase with that shape after the unit stat getter
and the ability property getter. Each case guards on a `0xFF` sentinel and
loads one byte.

Two things make the mapping trustworthy rather than a guess:

- field `0x24` resolves to `+0x32` and field `0x25` to `+0x33`, both of which
  were already known independently from `sub_0813413C` and `sub_08130820`
- three fields resolve past the end of a 52-byte entry and are reported as
  suspect rather than accepted

Regenerate with `python tools/dump_unit_fields.py <rom>`.

## field id to offset

| field | offset |
|---|---|
| `0x00` | `+0x0` |
| `0x01` | `+0x4` |
| `0x02` | `+0x6` |
| `0x03` | `+0x6` |
| `0x04` | `+0x7` |
| `0x05` | `+0x9` |
| `0x06` | `+0xb` |
| `0x07` | `+0xb` |
| `0x08` | `+0xc` |
| `0x09` | `+0xd` |
| `0x0a` | `+0xe` |
| `0x0b` | `+0xf` |
| `0x0c` | `+0x10` |
| `0x0d` | `+0x11` |
| `0x0e` | `+0x12` |
| `0x0f` | `+0x12` |
| `0x10` | `+0x13` |
| `0x11` | `+0x13` |
| `0x12` | `+0x13` |
| `0x13` | `+0x14` |
| `0x14` | `+0x14` |
| `0x15` | `+0x15` |
| `0x16` | `+0x16` |
| `0x17` | `+0x17` |
| `0x18` | `+0x18` |
| `0x19` | `+0x19` |
| `0x1a` | `+0x1a` |
| `0x1b` | `+0x1b` |
| `0x1c` | `+0x1d` |
| `0x1d` | `+0x1e` |
| `0x1e` | `+0x2d` |
| `0x1f` | `+0x2e` |
| `0x20` | `+0x2f` |
| `0x21` | `+0x31` |
| `0x22` | `+0x2b` |
| `0x23` | `+0x2b` |
| `0x24` | `+0x32` |
| `0x25` | `+0x33` |
| `0x29` | `+0x25` |
| `0x2a` | `+0x26` |
| `0x2b` | `+0x27` |
| `0x2c` | `+0x28` |
| `0x2d` | `+0x29` |
| `0x2e` | `+0x2a` |
| `0x2f` | `+0x26` |

suspect, resolve beyond the 0x34-byte entry:
  field 0x26 -> +0x34
  field 0x27 -> +0x35
  field 0x28 -> +0x36

## Editing

```bash
python tools/ability_table.py dump-units  baserom.gba units.csv
python tools/ability_table.py apply-units baserom.gba units.csv ffta-mod.gba
```

All 52 bytes are exposed. Only `+0x32` carries a name (`ai_priority`); every
other byte keeps a `bNN` label. The field-id map above says which accessor
reads which byte, but not what any of them mean, and naming a byte on a guess
is how unit data gets corrupted.
