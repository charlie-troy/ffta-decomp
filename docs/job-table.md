# The job table

The retail table contains 116 records of `0x34` bytes at `0x08521A14`.
`sub_080C8570(job, fallback_job, field_id)` exposes exactly 48 fields
(`0x00..0x2f`). Every formula below is executed against all 116 records by
`tools/validate_job_fields.py`; the gate currently covers 5,568 reads with no
mismatches.

## The accessor redirects records; it does not compute stats at a level

Earlier documentation compared each return value with a guessed raw offset.
That produced 23 partial matches and was interpreted as 22 conditional
stat-at-level formulas. The count and interpretation were both wrong.

For every field except field `0x02`, the accessor first reads record byte
`+0x05`:

| marker | behavior |
|---|---|
| `0x00` | read the selected record |
| `0xff` | read `fallback_job`, the accessor's second argument |
| any other value | read that job index |

Field `0x02` returns the marker itself without redirecting. Retail has 112
zero markers and four `0xff` proxy records (indices 80, 81, 82, and 85). A
synthetic `+0x05 = 7` patch proves the third path: all other 47 fields read
record 7, while field `0x02` returns 7. Cyclic or out-of-range redirects are
invalid edited data.

## Exact field formulas

| id | name | formula after redirect resolution |
|---|---|---|
| `0x00` | name id | `u16(+0x00)` |
| `0x01` | race | `u8(+0x04)` |
| `0x02` | redirect marker | `u8(+0x05)`; never redirected |
| `0x03` | unit kind | `u8(+0x06)` |
| `0x04` | sprite index | `u16(+0x07)` |
| `0x05` | unnamed u16 | `u16(+0x09)` |
| `0x06` | palette low | `+0x0b & 0x0f` |
| `0x07` | palette high | `+0x0b >> 4` |
| `0x08` | raw `+0x0c` | `u8(+0x0c)` |
| `0x09` | portrait palette | `u8(+0x0d)` |
| `0x0a` | portrait index | `u8(+0x0e)` |
| `0x0b` | portrait graphic | `u8(+0x0f)` |
| `0x0c` | A-ability index | `u8(+0x10)` |
| `0x0d` | innate element id | `u8(+0x11)` |
| `0x0e..0x15` | resistance slots 0..7 | eight consecutive 3-bit slots beginning at `+0x12` bit 3 |
| `0x16` | status defense | `u8(+0x16)` |
| `0x17` | base HP | `u8(+0x17)` |
| `0x18` | base MP | `u8(+0x18)` |
| `0x19` | base Speed | `u8(+0x19)` |
| `0x1a` | base Attack | 12 bits: `+0x1a`, then low nibble of `+0x1b` |
| `0x1b` | base Defense | 12 bits: high nibble of `+0x1b`, then `+0x1c` |
| `0x1c` | base Magic Power | 12 bits: `+0x1d`, then low nibble of `+0x1e` |
| `0x1d` | base Resistance | 12 bits: high nibble of `+0x1e`, then `+0x1f` |
| `0x1e` | movement | `u8(+0x28)` |
| `0x1f` | jump | `u8(+0x29)` |
| `0x20` | evade | `u8(+0x2a)` |
| `0x21` | raw `+0x2c` | `u8(+0x2c)` |
| `0x22` | movement style low | `+0x2b & 0x0f` |
| `0x23` | movement style high | `+0x2b >> 4` |
| `0x24` | equipment-set index | `u8(+0x2d)` |
| `0x25` | ability-list start | `u8(+0x2e)` |
| `0x26` | ability-list end | `u8(+0x2f)` |
| `0x27` | job-requirement index | `u8(+0x30)` |
| `0x28` | morph-family flags | `u8(+0x31)`; bit 0 enables the compact family index |
| `0x29` | HP growth | `u8(+0x20)` |
| `0x2a` | MP growth | `u8(+0x21)` |
| `0x2b` | Speed growth | `u8(+0x22)` |
| `0x2c` | Attack growth | `u8(+0x23)` |
| `0x2d` | Defense growth | `u8(+0x24)` |
| `0x2e` | Magic Power growth | `u8(+0x25)` |
| `0x2f` | Resistance growth | `u8(+0x26)` |

The source-of-truth registry is `tools/job_fields.py`; print the same table
with executable results via:

```bash
python tools/audit_field_map.py baserom.gba
```

## Resistance packing

The eight elemental slots occupy a 24-bit stream starting at `+0x12` bit 3.
Each slot is three bits wide and field ids `0x0e..0x15` reach them in order:

| slot | byte/bits | field id |
|---|---|---|
| 0 | `+0x12` bits 3–5 | `0x0e` |
| 1 | `+0x12` bits 6–7, `+0x13` bit 0 | `0x0f` |
| 2 | `+0x13` bits 1–3 | `0x10` |
| 3 | `+0x13` bits 4–6 | `0x11` |
| 4 | `+0x13` bit 7, `+0x14` bits 0–1 | `0x12` |
| 5 | `+0x14` bits 2–4 | `0x13` |
| 6 | `+0x14` bits 5–7 | `0x14` |
| 7 | `+0x15` bits 0–2 | `0x15` |

Retail values stay in 0–3 and leave every third bit clear. Slots 1 and 2 are
equal in all 116 retail records, which hid the former mapping error: an audit
that excluded field `0x10` could appear to reproduce retail output by reading
slot 1 twice. Patching the slots to distinct values 0–7 makes the accessor and
unit initializer preserve all eight independently. Earth uses slot 2, not a
second copy of Wind.

The editor now preserves the full three-bit format (0–7), while ordinary
retail affinity meanings are established only for the values the game uses:

```bash
python tools/ability_table.py dump-resist baserom.gba resist.csv
python tools/ability_table.py apply-resist baserom.gba resist.csv out.gba
```

## Other established layout facts

- `+0x04` is race/family. Playable jobs occupy the familiar large race blocks;
  monster families account for the wider 0–23 value range.
- `+0x06` is unit kind: 0 for placeholders, 1 for playable characters, and 2
  for monster families.
- `+0x09/+0x0a` form one u16. `0xffff` is the none sentinel; `+0x0a` is not an
  independent field.
- `+0x0f` is a portrait graphic. Its reader combines it with the portrait
  palette before requesting graphics.
- `+0x11` is innate element id. The nonzero records align with elemental
  monsters, and unit initialization copies it immediately before the
  resistance array.
- `+0x1a..+0x1f` hold four packed 12-bit base combat stats, not six unrelated
  bytes.
- `+0x27` is byte-for-byte equal to Resistance growth at `+0x26` in retail,
  but no accessor field reads `+0x27`; field `0x2f` reads `+0x26`.
- `+0x31` bit 0 enables the compact monster/morph-family index. Its sole
  accessor consumer maps the twenty supported jobs (Goblin through Ahriman,
  excluding Toughskin/Blade Biter/Tonberry/Masterberry) to 0–19; clear returns
  `-1`. Retail bits 1/2 have no consumer in this path and remain numeric.
- `+0x33` is unarmed attack power. Direct damage readers substitute it for an
  equipped weapon's attack-power property, and `tools/probe_unarmed.py`
  executes the link across all 116 jobs.

## Reachability and intentionally raw bytes

Constant call-site recovery finds 73 of 74 accessor calls. Fields `0x08` and
`0x21` expose raw bytes `+0x0c` and `+0x2c`, but no constant call site uses
them. Offsets `+0x02` and `+0x27` have no accessor field. The complete
table-base scan finds no separate direct reader for these four offsets, so
they remain numeric rather than receiving guessed names. Field `0x28` has one
caller and is the morph-family flag join above.

The four `0xff` proxy records have blank names because their own name fields
redirect through the caller-provided fallback. This is a runtime selection
mechanism, not a checksum or a stat formula.

## Editing and validation

All 52 raw bytes remain available in the guarded CSV editor; known bytes use
stable names and unresolved/dead bytes retain `bNN` labels:

```bash
python tools/ability_table.py dump-units  baserom.gba jobs.csv
python tools/ability_table.py apply-units baserom.gba jobs.csv ffta-mod.gba
python tools/validate_job_fields.py baserom.gba  # 4/4
```

An unedited resistance CSV round-trips byte-identically. The formula validator
also executes a non-retail direct redirect and distinct resistance values, so
the result does not rely only on coincidental retail equality.
