# Job table (0x08521A14)

Stride `0x34` (52 bytes). Valid job data runs through index **115**, so 116
entries. The layout is documented publicly on
[Data Crystal](https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance/Jobs);
what follows is that layout checked against the ROM, plus one field it does
not cover.

This is the table `sub_0813413C` falls back to when an action carries no
ability id, which is how it entered this project.

## Verified against the ROM

| offset | field | observed |
|---|---|---|
| `+0x00` | name_id | small ids |
| `+0x17` | base_hp | 0-85 |
| `+0x18` | base_mp | 0-86 |
| `+0x19` | base_speed | 0-165 |
| `+0x20-0x26` | growth rates | HP, MP, speed, attack, defense, magic power, magic resist |
| `+0x28` | movement | 0-8 |
| `+0x29` | jump | 0-4 |
| `+0x2A` | evade | 0-70 |
| `+0x30` | job_requirement | 0-19 |

Also adopted without independent checking, since they are structural rather
than numeric: sprite and portrait indices and palettes, the A-ability index,
the four-byte element resistance field, status defense, base melee and magic
triples, movement style, equip index, and the ability start/end pair.

## Two places the published layout does not hold

**`+0x04` is documented as Race, but its values run 0-23.** FFTA has five
races, so either the field is something broader or the label is wrong. It
keeps a `b04` label here rather than a name that might mislead.

**`+0x32` is documented as unknown** (part of a `0x31-0x33` unknown run). It
is the **AI priority percentage**, established from `sub_0813413C`, which
reads exactly this byte on the no-ability path and feeds it to the same
percentage predicate the ability table uses. Its values run 0-100 over 14
distinct settings, matching that scale. This is the one field this project
contributes back rather than adopts.

## Entry count

The published figure is 115. Index 115 still reads as a real job here (a
small name id, movement 3, AI priority 80) while index 116 clearly does not
(movement 33, a name id in the thousands), so the editor uses 116.

An earlier bound of 123 in this project was wrong. It came from assuming the
priority byte stayed within 0-100, which some non-job bytes happen to do, and
it would have let someone edit past the end of the table.

## Editing

```bash
python tools/ability_table.py dump-units  baserom.gba jobs.csv
python tools/ability_table.py apply-units baserom.gba jobs.csv ffta-mod.gba
```

All 52 bytes are exposed. Named columns use the verified names above;
everything else keeps a `bNN` label.

## Field accessor

`sub_080C8570(index, ?, fieldId)` dispatches through a 48-entry jump table,
the same shape as the unit stat getter and the ability property getter. The
field-id to offset map is produced by `python tools/dump_unit_fields.py <rom>`;
45 of 48 ids land inside the entry and three resolve past its end and are
reported as suspect.