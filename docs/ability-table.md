# Ability table

Base `0x0855187C`, stride **0x1C** (28 bytes), **347 entries**; entry 0 is a
null row. Layout below is cross-checked against the public documentation on
[Data Crystal](https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance/Abilities),
which describes the same table at the same offset, and verified against the ROM.

## Layout

| offset | size | field | notes | verified |
|---|---|---|---|---|
| `+0x00` | 2 | Name ID |  | values 0-542 |
| `+0x02` | 1 | Element | 0 none, 1 fire, 2 wind, 3 earth, 4 water, 5 ice, 6 lightning, 7 holy, 8 dark | observed 0-8 exactly |
| `+0x03` | 1 | **AP cost / 10** | in-game AP is this x10 | 19/19 vs published |
| `+0x04` | 1 | **MP cost** |  | 19/19 vs published, and the AI compares it to unit MP |
| `+0x05` | 1 | Weapon required | 0 no, 1 yes, 2 spear, 3 bow | observed 0-3 |
| `+0x06` | 1 | Horizontal range | `0x40` line, `0x80` weapon range |  |
| `+0x07` | 1 | Vertical range | 0 ignores height |  |
| `+0x08` | 1 | Targeting mode | 0-7: cursor, auto, directional, pierce, in front, etc. | observed 0-7 |
| `+0x09` | 1 | Horizontal AoE | 1 single, 2 spear, 4 breath, 5 aura, 0x0D big aura, 0x40 map, 0x80 line | observed exactly that set |
| `+0x0A` | 1 | Vertical AoE | 0 ignores height |  |
| `+0x0B` | 1 | **Power** | damage multiplier | 19/19 vs published |
| `+0x0C` | 4 | Effect indices | four effect ids |  |
| `+0x10` | 4 | Property flags | 21 live bits, see below |  |
| `+0x14` | 2 | Animation ID |  | near-sequential across entries |
| `+0x16` | 2 | Description ID |  | 0-400, 346 distinct |
| `+0x18` | 1 | **AI condition** | 0 normal, 1 judge, 2 mug, 3 sensor, ... | 306 of 347 are 0 |
| `+0x19` | 1 | **AI behaviour** | 0 unknown, 1 low HP, 2 healthy, 3 last resort | 60/185/97/5 |
| `+0x1A` | 1 | **AI priority** | higher means less likely to be chosen | 13 distinct, 0-100 |
| `+0x1B` | 1 | padding |  | always 0 |

## The AI tuning surface

Three of the 28 bytes are AI-specific, per ability, for all 347 abilities:

- **`+0x1A` AI priority** — a single byte deciding how eagerly the AI reaches
  for an ability. Higher is less likely. This is the most direct behaviour
  knob in the game and it needs no code changes at all.
- **`+0x19` AI behaviour** — when the ability is considered. Value 2
  ("healthy") is the one `sub_080C32C0` implements by rejecting the ability
  when the target is below half HP.
- **`+0x18` AI condition** — special-case handling; 306 of 347 abilities use
  the default.

Editing these changes AI behaviour without touching a single instruction.

## Property flags at `+0x10`

Bits 1-4 are never set in any entry. The AI reads properties `0x11`, `0x12`
and `0x13`, which are bits 6, 7 and 8.

| bit | meaning | set in |
|---|---|---|
| 0 | Self-targetable | 104/347 |
| 1 | unused | 0/347 |
| 2 | unused | 0/347 |
| 3 | unused | 0/347 |
| 4 | unused | 0/347 |
| 5 | Offensive | 236/347 |
| 6 | Ignore reaction  **(AI reads)** | 7/347 |
| 7 | Reflectable  **(AI reads)** | 27/347 |
| 8 | Double cast  **(AI reads)** | 92/347 |
| 9 | Ignore silence | 212/347 |
| 10 | Enable beastmaster | 55/347 |
| 11 | Trigger learning | 20/347 |
| 12 | Blocked by cover | 145/347 |
| 13 | *not publicly documented* | 308/347 |
| 14 | Stealable | 246/347 |
| 15 | Return magic | 42/347 |
| 16 | Throw/hurl | 2/347 |
| 17 | Trigger absorb-MP | 71/347 |
| 18 | Physical | 94/347 |
| 19 | Enable morpher | 55/347 |
| 20 | *not publicly documented* | 327/347 |

Bits 13 and 20 are set on most entries but appear in no public flag list, so
their meaning is open. That is one place this analysis adds something rather
than reproducing what was already known.

## Corrections

Two earlier readings in this file were wrong and are worth recording:

- `+0x1A` was guessed as **accuracy** because its values cluster on 30/60/70/80
  and cap at 100. It is **AI priority**. The value profile fits both, which is
  exactly why it should not have been asserted.
- `+0x16` was measured as two separate `u8` columns. It is a single `u16`
  description id; the apparent boolean at `+0x17` was just its high byte.
