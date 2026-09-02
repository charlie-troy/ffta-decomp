# Text

Every table stores names as an index into a pointer table of strings. Decoding
those turns each modding CSV from a wall of numbers into something readable,
which matters more for this project than any single field name.

## Finding the string tables

Strings are addressed by tables of ascending ROM pointers, so scanning for long
ascending pointer runs finds them all without knowing where any of them are.
`tools/strings.py list` does that and decodes a sample of each.

| table | count | contents |
|---|---|---|
| `0x08526680` | 753 | jobs, monsters, clans, then items from index 124 |
| `0x085567F0` | 767 | menus and UI; **ability names** at 200-599 |
| `0x0855A64C` | 512 | mission names, indexed by mission id |
| `0x08565F14` | 128 | clan names |
| `0x085680DC` | 725 | character first names |
| `0x085668B0` | 84 | location and shop names |
| `0x08569034` | 52 | clan name adjectives |
| `0x085516D0` | 107 | story character names |

## Two encodings

**Two-byte.** A bank byte then a glyph byte. Bank `0x80` holds the alphabet
with `0xB0`–`0xC9` as A–Z and `0xCA`–`0xE3` as a–z; bank `0x40` holds spaces.

**Single-byte.** One byte a character, with the same alphabet shifted up by
one: `0xB1` is A and `0xCB` is a. Character names and much of the UI use this.

Both terminate on `0x00`, and both mix in single-byte control codes below
`0x20` plus `0xFF`. That mixing is what makes a naive two-byte reader
desynchronise partway through a string and emit garbage from there on.

`tools/ffta_text.py` implements both and scores the output, so callers can just
ask for whichever reads more cleanly.

## Deriving the alphabet

The mapping was not looked up. Decoding the 512-entry table at `0x0855A64C`
under the assumption `0xB0` is A produced `Snowball Fight`, `Another World`,
`Herb Picking` and `Thesis Hunt` for entries 1 to 4, which are the first four
missions in the game, so the assumption was right.

Punctuation was pinned the same way, from strings whose text is known
independently:

| code | glyph | evidence |
|---|---|---|
| `80 EB` | `!` | `Materite Now!`, `Fire! Fire!` |
| `80 F4` | `'` | `Raven's Oath`, `A Dragon's Aid` |
| `80 FE` | `-` | `Castle Sit-In`, `LV3 Def-less` |
| `80 EE` | `:` | `Aim: Armor`, `Steal: Ability` |
| `80 EC` | `,` | `Sorry, Friend`, `You, Immortal` |
| `80 EA` | `?` | `Who Am I?`, `Human Help?` |
| `80 FD` | `+` | `Weapon Atk+`, `Magic Pow+` |
| `81 03` | `>` | `Damage > MP`, `HP > 1/2` |
| `81 08` | `&` | `Flesh & Bones`, `Blade & Turtle` |
| `80 F1` | `/` | `HP > 1/2` |
| `81 02` | `<` | `Heal < 50`, `Heal < 100` |
| `81 07` | `%` | `100% Wool` |
| `80 F7` / `80 F8` | `(` / `)` | `(not used)`, `(---)` |
| `80 FB` / `80 FC` | `〖` / `〗` | `〖Enhance〗` |

**All 2,757 strings in the four primary tables now decode with no unknown
codes.** The final seven were two comparison labels, one percentage label, a
parenthesized unused marker, two parenthesized placeholders, and a decorated
menu label. `tools/validate_text.py` locks both complete coverage and those
seven edge-case readings. Their contextual readings agree with the published
[FFTA character table](https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance/Strings).

## Which table a name id points at is not uniform

This is the part worth knowing before using the ids. Abilities index the **UI**
table; items and jobs index the **main** table. Using the wrong one silently
produces plausible but incorrect text — an ability's name id read against the
main table gives an item name, which is how this was noticed.

| table | name id points at |
|---|---|
| abilities | `0x085567F0` (UI) |
| items | `0x08526680` (main) |
| jobs | `0x08526680` (main) |
| missions | `0x0855A64C`, by mission id rather than a stored field |

The check that settles it: ability 1 resolves to `Cure`, 2 to `Cura`, 3 to
`Curaga`, 4 to `Esuna` and 5 to `Life`, which matches the MP costs and powers
already recorded for those ids in `tools/validate_ai.py` from published
documentation.

## Using it

Every dump now carries a `name` column, and `make verify-mod` names what it
reports:

```
  ability   1 Cure              ai_priority             80 -> 100
  ability   2 Cura              ai_priority             65 -> 100

        ability   id     priority            keep rate    delta
           Cure    1    80 -> 100      82.2% ->  100.0%    +17.8
```

```bash
python tools/strings.py list baserom.gba
python tools/strings.py dump baserom.gba 0x0855A64C 512 missions.csv
python tools/validate_text.py baserom.gba
```

The name column is informational: `apply` ignores it, and every table still
round-trips to a byte-identical ROM with it present.
