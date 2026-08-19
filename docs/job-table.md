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

## Fields still unnamed

`+0x02`, `+0x06`, `+0x09`, `+0x0a`, `+0x0c`, `+0x0f`, `+0x2c`, `+0x31`, `+0x33`.

Of these, `+0x0c` and `+0x0f` are confirmed readable through field ids `0x08`
and `0x0b`, so they are real fields rather than padding. `+0x0c` is zero in
every entry, which makes it a real field that nothing varies — most likely
something switched off before release.

`+0x01` and `+0x08` are not fields at all. They are the high bytes of the u16
at `+0x00` (`name_id`) and `+0x07` (`sprite_index`), and are zero only because
those values stay below 256.

## Reproducing

```bash
python tools/audit_field_map.py       # which offsets execution confirms
python tools/field_callers.py         # call sites grouped by field id
python tools/solve_resist_bits.py    # bit position of each resistance slot
python tools/check_resist_gaps.py     # slot widths and the unread ranges
```
