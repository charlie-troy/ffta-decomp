# The job table

116 entries of 0x34 bytes at `0x08521A14`. It holds what a job or monster
family is: its sprite, its base stats and growths, what it may equip, and the
AI priority the evaluator reads.

Everything below that names a field was checked by running the ROM's own
accessor, `sub_080C8570(index, 0, fieldId)`, on an emulated CPU across all 116
entries. Where execution disagrees with the published layout, the execution
result is what is recorded, and the disagreement is called out.

## What the field accessor actually does

`sub_080C8570` dispatches through a 48-entry jump table. It is tempting to read
that table statically, recover a byte offset per field id, and call the layout
solved. That is what `tools/dump_unit_fields.py` does, and it is only partly
right.

Running every field id against every entry and comparing to the raw byte
separates the three cases:

| result | fields | meaning |
|---|---|---|
| matches on all 116 entries | 16 | the offset is correct and it is a plain byte load |
| never matches | 7 | not a byte load; these are the packed resistances |
| matches on some entries | 22 | the accessor computes rather than loads |

So **16 of the 45 in-range offsets are confirmed as simple fields.** The rest
were reported as solved by static decoding and are not. The high field ids
(`0x1b` and up) mostly fall in the conditional group, which is consistent with
them deriving a value rather than fetching one — several of them sit on the
growth rates, and a stat-at-level computation would look exactly like this.

Reproduce with:

```bash
python tools/audit_field_map.py
```

Duplicate field ids are normal in this table: `0x02`/`0x03`, `0x06`/`0x07`,
`0x0f`/`0x10` and `0x22`/`0x23` each resolve to the same source.

## Elemental resistances are packed, not four bytes

The published layout describes `+0x12` as "Element Resistances (4 bytes)",
which reads naturally as four one-byte values. It is not that.

Field ids `0x0e`–`0x15` never equal any raw byte, and one function at
`0x08099228` calls ids `0x0d` through `0x15` back to back. Solving each id
against `+0x11`–`+0x15` treated as a single little-endian bit stream gives a
regular structure:

- **eight slots**, on a **3-bit stride**, starting at **`+0x12` bit 3**
- each slot holds **0–3**; the third bit of every slot is clear in all 116
  entries, so two bits are used of the three allotted
- bits 4–10 of `+0x11` and the top of `+0x15` are zero in every entry

The value distribution is what settles the interpretation. Every slot holds
**1 in 108–113 of the 116 entries**, with a handful of 0, 2 and 3. That is a
resistance table with 1 as the neutral default, not an index or a bitmask.

| slot | stream bit | byte and bits | reached by field id |
|---|---|---|---|
| 0 | 11 | `+0x12` bits 3–4 | `0x0e` |
| 1 | 14 | `+0x12` bits 6–7 | `0x0f`, `0x10` |
| 2 | 17 | `+0x13` bits 1–2 | **none** |
| 3 | 20 | `+0x13` bits 4–5 | `0x11` |
| 4 | 23 | `+0x13` bit 7 – `+0x14` bit 0 | `0x12` |
| 5 | 26 | `+0x14` bits 2–3 | `0x13` |
| 6 | 29 | `+0x14` bits 5–6 | `0x14` |
| 7 | 32 | `+0x15` bits 0–1 | `0x15` |

Slot 2 is a real slot — its values carry the same 1-dominant distribution as
the other seven — but no field id in the accessor resolves to it, because
`0x10` duplicates slot 1 instead. Anything that reads resistances through this
accessor therefore cannot see slot 2. Whether another path reads it has not
been established, so **treat editing slot 2 as unverified**.

Because the slots straddle byte boundaries, editing them by hand in the
byte-level CSV is error-prone. Use the dedicated commands, which are
bit-exact — an identity rewrite of all 116 entries changes zero bytes, and a
single slot edit touches exactly one byte:

```bash
python tools/ability_table.py dump-resist baserom.gba resist.csv
python tools/ability_table.py apply-resist baserom.gba resist.csv out.gba
```

## Fields named in this pass

| offset | name | basis |
|---|---|---|
| `+0x04` | `race` | see below |
| `+0x11` | `unit_class` | field id `0x0d`, low nibble, values 0–8 |
| `+0x12`–`+0x15` | packed resistances | the table above |
| `+0x27` | `growth_magic_res_copy` | byte-for-byte equal to `+0x26` in all 116 entries |

**`+0x04` is Race, and the published layout is right.** I had rejected that
name on the grounds that the values run 0–23 while FFTA has five races. The
distribution shows the objection was wrong: entries 0–71 run in contiguous
ascending blocks, with values 0–5 taking the large blocks (7, 24, 7, 8, 12 and
9 entries) and 6–18 taking exactly two entries each. That is five playable
races with their job lists, followed by monster families. The table covers
monsters, so a wider family enum is expected.

**`+0x27` duplicates `+0x26`.** Not approximately — identically, in all 116
entries. Field ids `0x2a` and `0x2b` both reach the pair. It is listed as
Unknown in the published layout. Editing `+0x27` alone is unlikely to do
anything useful; if you change magic resistance growth, change both.

## `+0x05` is not a checksum, and does not redirect

The published layout marks `+0x05` as "Checksum?". Only four entries carry
`0xFF` there (80, 81, 82 and 85); the other 112 hold `0x00`. The accessor
guards on it before loading, which suggested it might redirect a read to
another entry.

Running every field id on those four entries against controls shows it does
not. No field on a `0xFF` entry resolves to another entry's value, and the
differences that do appear turn up on control entries too, because they come
from the conditional fields described above rather than from this guard. What
`+0x05` selects is still open, but a checksum it is not: a checksum over a
0x34-byte entry would vary per entry, and this takes two values.

## Finding a field's meaning

Two things read this table, and both had to be swept to cover the last
offsets:

1. **The accessor**, `sub_080C8570(index, ?, fieldId)`. `tools/field_callers.py`
   decodes every `BL` to it and recovers the constant field id from the
   preceding `movs r2, #imm`, giving 73 of 74 call sites.
2. **Direct indexing.** Code that reaches the table itself is recognisable as
   an idiom — multiply by the 0x34 stride, add the base from a literal pool,
   add a constant offset, load a byte. `tools/job_getters.py` scans for it
   ROM-wide.

The second matters because the interesting fields are not reached through the
accessor at all. `+0x33` has three direct readers and no accessor call site.

Both scans also settled a detail worth stating plainly: the direct getters take
a **unit pointer** and read `[unit + 5]` to get the job index. Unit struct
`+0x05` is the job index, and the job table's own `+0x05` is unrelated to it.

## `+0x33` is the unarmed attack power

`sub_08130820(unit)` returns `job_table[unit->job].b33` and nothing else. Its
meaning comes from the two other readers, at `0x0812fee2` and `0x0812ff16`,
which sit in the damage path and share one shape:

```
if (weapon == NULL)  power = job_table[unit->job].b33;
else                 power = item_property(weapon, 10);
...
power = power * 3 / 2;
result = power * base;
```

`sub_080CA7A4(item, prop)` is the item property getter — it multiplies by the
item table's 0x20 stride and bounds-checks the property id against 19. So the
field stands in for a weapon's attack power when no weapon is equipped, and
both paths feed the same term.

The values agree: 53 entries hold 10, and the range runs to 48, which is what
innate attack power looks like across jobs and monsters.

Verified by execution. `tools/probe_unarmed.py` runs the getter against
synthetic units for all 116 jobs and matches every one, and patching the field
moves the return value with it, so the link is causal rather than a
correlation.

## `+0x06` is a unit kind

Values are 0, 1 and 2, and they track `race` at `+0x04` almost exactly:

| `+0x06` | entries | which races |
|---|---|---|
| 0 | 7 | exactly the race-0 entries (0, 1, 72–76) |
| 1 | 63 | the five playable races |
| 2 | 46 | the monster families |

Read as 0 = placeholder, 1 = character, 2 = monster.

## `+0x09` is one u16, so `+0x0a` is not a field

The same twelve entries hold `0xFF` at `+0x09` and at `+0x0a`, which is
`0xFFFF` read as a halfword and is the "none" sentinel. Of the rest, 43 are
zero and the others fall in `0x00bc`–`0x00f7`. `+0x0a` is the high byte.

That leaves eight unnamed offsets rather than nine. `+0x01` and `+0x08` are the
same kind of thing — high bytes of the u16 at `+0x00` (`name_id`) and `+0x07`
(`sprite_index`), zero only because those values stay below 256.

## `+0x0f` is a portrait graphic

Read once, at `0x08035540`, alongside `portrait_palette`. The two are packed as
`(palette << 8) | this` and passed to `sub_08013108` with a constant of
`0x24c0`, which is a graphics request rather than anything gameplay-facing.

## What is left, and why

Four offsets have no reader at all — no accessor call site passes their field
id, and no direct getter reads them. Nothing here can name them, so this is
what they look like instead:

| offset | shape |
|---|---|
| `+0x02` | zero except the last four entries (112–115), which hold 1, 2, 3, 4 |
| `+0x0c` | zero in all 116 entries; reachable as field id `0x08`, never called |
| `+0x2c` | zero except entries 62 and 63, holding 3 and 7 |
| `+0x31` | 0, 1, 2 or 4 — never two bits at once, in three disjoint groups of 20, 5 and 7 entries |

`+0x31` being single-bit throughout suggests a flag byte with three flags
defined, but with no code reading it that is a shape, not a meaning. `+0x0c` is
a real field the accessor supports that nothing varies and nothing calls, which
is what a feature cut before release looks like.

## Reproducing

```bash
python tools/audit_field_map.py       # which offsets execution confirms
python tools/field_callers.py         # call sites grouped by field id
python tools/solve_resist_bits.py    # bit position of each resistance slot
python tools/check_resist_gaps.py     # slot widths and the unread ranges
```
