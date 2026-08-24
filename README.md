# ffta-decomp

Reverse engineering **Final Fantasy Tactics Advance** (GBA, USA), aimed at
making the battle AI understandable and modifiable.

Two things live here:

1. **A modding path that needs no compiler.** The AI's per-ability tuning is
   data, so changing how the AI behaves is a CSV edit. Start at
   [docs/modding.md](docs/modding.md).
2. **A matching decompilation** underneath it, so the parts that are code and
   not data can be changed too. The full 16 MB ROM rebuilds byte-identical.

> **No ROM data lives in this repository.** You supply your own dump. The build
> verifies its SHA1 and extracts what it needs at build time. `.gitignore`
> excludes `*.gba` and `*.bin`; keep it that way.

---

## What is known about the AI

The evaluator `sub_080C32C0` decides whether the AI wants a given ability
against a given target. Its rules are readable, and two layers of tuning are
exposed:

| lever | where | needs a compiler? |
|---|---|---|
| per-ability likelihood (`ai_priority`, a percentage) | ability table | no |
| when an ability is considered (`ai_behaviour`) | ability table | no |
| per-job AI priority | job table | no |
| per-job elemental resistances | job table | no |
| the 11%/50% self-versus-other gate on status effects | code | yes |
| the eligibility rules (MP cost, healthy-target, reflect) | code | yes |

**The text is decoded**, so every dump carries real names rather than ids:
abilities read as `Cure` and `Curaga`, items as `Shortsword`, jobs as
`Soldier`, missions as `Snowball Fight`. 99.7% of the game's strings decode
with no unknown codes. See [docs/text.md](docs/text.md).

Mission data is mapped in [docs/mission-data.md](docs/mission-data.md), which
was undocumented anywhere and had to be found by scanning the ROM for table
accessors. Rewards, clan progression, required and blocked dispatch jobs, pub
information fees, and dispatch difficulty are directly editable. That scan
also settles a negative: there is no formation table, because battle setups
are scripted one unit at a time.

Map data is mapped as well, in [docs/map-data.md](docs/map-data.md). The
blocks are compressed, the codec is implemented in both directions, and
terrain is editable tile by tile with a guard that refuses any block that
would no longer fit.

The item table is mapped too, in [docs/item-table.md](docs/item-table.md):
all 19 of its accessor properties are plain loads, and weapon attack power
feeds the same damage term as the job table's unarmed attack.

Written up in [docs/ai-findings.md](docs/ai-findings.md),
[docs/ability-table.md](docs/ability-table.md),
[docs/ai-case-rules.md](docs/ai-case-rules.md),
[docs/unit-ai-table.md](docs/unit-ai-table.md),
[docs/job-table.md](docs/job-table.md) and
[docs/turn-order.md](docs/turn-order.md).

Two results in there disagree with published documentation, with the derivation
shown in each case: `ai_priority` runs the opposite direction, and the job
table's `+0x32` is not unknown.

**The AI's rules are validated by execution.** `tools/validate_ai.py` runs the
ROM's own functions on an emulated CPU against synthetic units, and all eight
checks pass: the priority filter, the ability property accessor, flag decoding,
the stat-id mapping, the healthy-target rule at its exact boundaries, the
11%/50% status gate, packed resistance decoding, and unarmed attack power. See
[docs/validation.md](docs/validation.md).

Whole-battle behaviour is now traced through a real enemy turn: one actor calls
`sub_080C32C0` for four distinct targets, and a frozen-RNG replay reproduces the
registers and stack exactly. See [docs/whole-battle-trace.md](docs/whole-battle-trace.md).
What remains unvalidated is 22 computed job-accessor properties and resistance
slot 2. The four still-unnamed job-table offsets are
not an open validation task: exhaustive reachability analysis proves the retail
ROM never reads them. The job table itself is written up in
[docs/job-table.md](docs/job-table.md), including two corrections to the
published layout: the elemental resistances are eight packed 3-bit slots rather
than four bytes, and `+0x27` is an exact duplicate of `+0x26` in every entry.

## Decompilation status

**The full 16 MB ROM rebuilds byte-identical.** 172 functions are compiled from
C and placed at their real addresses; everything else is pulled from the base
ROM with `.incbin`. `make rom` fails unless the SHA1 matches, so no change can
silently break the build. `make mod` is the same build with the SHA1 gate
relaxed, for deliberate changes.

| | |
|---|---|
| Target ROM | FFTA (USA), `AFXE`, rev 0 |
| SHA1 | `4ac05441f4de70a4ec3dd932116346c61b8783d9` |
| Compiler | **agbcc** (pret's patched gcc 2.95.3, the AGB SDK compiler) |
| Flags | `-mthumb-interwork -Wimplicit -Wparentheses -O2` |
| Functions matched | **172** (4,536 bytes) |
| Full ROM rebuild | **matching** |
| Functions discovered | 3,594 (via luvdis + local analysis) |

```bash
make setup && make rom     # verify the decomp still reproduces the ROM
make mod                   # build with deliberate changes
```

Modding the AI needs none of that:

```bash
python tools/ability_table.py preset always baserom.gba ffta-always.gba
```

### Evidence for agbcc

- `crt0` at `0x080000C0` is the stock Nintendo AGB SDK startup, followed by the
  SDK's `IntrMain` dispatcher reading `REG_IE/IF`.
- No ARM ADS/RVCT runtime anywhere: no `__main`/`__scatterload` chain, no
  `__rt_*` helpers, no ARM Ltd strings.
- Returns use `pop {rN}` + `bx rN` rather than `pop {pc}`, which is what gcc
  emits under `-mthumb-interwork` on ARMv4T.
- Leaf functions still `push {lr}`, and register moves appear as
  `add rD, rS, #0`. Both are gcc 2.95 artifacts.
- Two functions compiled byte-identical on the first attempt, with no
  permuting: `sub_08005BB0` (18 bytes) and `sub_080DBD5C` (20 bytes).

### ROM shape

- 16 MiB cart, 10.24 MiB of real content; `0xFF` filler from `0xA3A000`.
- Essentially 100% Thumb. Only 3 ARM-mode prologues in the entire ROM, so
  there is no meaningful ARM/Thumb split to manage.
- Code is dense from `0x000000` to roughly `0x360000`; the rest is data,
  graphics and audio.
- MP2K/m4a song table candidate at `0x014BB48`, 640 entries, so the standard
  GBA audio tooling applies.

---

## Setup

Requires WSL (Ubuntu). The toolchain is Linux-native; Windows only runs the
Python analysis tools.

```bash
bash tools/setup_toolchain.sh
```

Builds into `$HOME/ffta-toolchain`, needs no root, and is safe to re-run:

- `agbcc/` — pret's gcc 2.95.3, built from source
- `local/usr/bin/` — `arm-none-eabi` binutils, extracted from the .deb

Then confirm your ROM is the right revision:

```bash
make verify ROM="/mnt/d/path/to/Final Fantasy Tactics Advance.gba"
```

---

## Workflow

Find a function worth attacking:

```bash
make funcs
```

`tools/find_leaf_funcs.py` discovers functions from their **call sites**, not by
scanning for `push {..., lr}` bytes. Linear scanning finds mostly graphics data
that happens to contain the right byte; resolving every Thumb `BL` and keeping
targets with multiple callers finds real code. Leaf functions come first because
they compile without any other symbol being known.

Write a candidate in `src/`, then:

```bash
make match SRC=src/match_test.c AT=0x5bb0 LEN=18
```

That preprocesses, compiles with agbcc, assembles, and prints an
instruction-by-instruction diff against the original ROM bytes.

---

## CI, and what it can and cannot check

CI **cannot run the full ROM rebuild**. That needs `baserom.gba`, which is never
committed and never will be. Any CI setup that did run it would require shipping
the ROM to a build server.

What CI runs instead is a genuine per-function regression gate. `data/functions.json`
records each function's address, size, and the **SHA-256 of the bytes it must
compile to**. Hashes, not bytes, so the file carries no ROM content and is safe
to commit. CI builds agbcc, compiles every function, and checks each object's
`.text` against that hash.

That catches the failure that actually matters day to day: a change that makes a
function stop compiling to the right code. It does **not** prove the ROM links
or that placement is correct, because nothing without the ROM can.

```bash
make check    # what CI runs; no ROM needed
make rom      # the real gate; needs your own dump
make index    # refresh data/functions.json after adding a function
```

After adding a function to `src/`, run `make index` locally and commit the
updated `data/functions.json`, or CI will report it as missing.

## How the rebuild works

`tools/build_rom.sh` runs the whole pipeline:

1. Compile every `src/**/sub_*.c` with agbcc, one object each.
2. Check each object's `.text` size against the function's real ROM size.
3. Generate `asm/rom.s` and `ldscript.txt` **from the objects just built**, so
   placement reflects real section sizes rather than assumed ones.
4. Assemble `asm/rom.s`, which `.incbin`s every stretch of ROM not yet
   decompiled, one named section per gap.
5. Link at absolute addresses, extract with objcopy, compare SHA1.

Three things about agbcc's output make this fiddlier than it looks, all handled
in `build_rom.sh`:

- **`.text` gets padded.** agbcc opens with `.align 2, 0`, which sets the
  section alignment to 4 and makes GAS round the section size up. A 26-byte
  function then occupies 28 and overruns the next thing in the ROM. The leading
  directive is stripped, since the linker script already places each function at
  its true address.
- **Literal pools still need their alignment.** Stripping *every* `.align`
  breaks any function with a pool, so only the first is removed.
- **Tail padding is a nop, not zeros.** Where a pool forces alignment 4 anyway,
  GAS fills the section tail with `0xC046` (`mov r8, r8`) and the ROM has zeros
  there. An explicit zero-filled `.align 2, 0` is appended to exactly those
  objects.

Placement uses `. = <offset>` assignments in the linker script. Inside an output
section ld treats those as offsets from the section start, not absolute
addresses, and since the section begins at `0x08000000` the ROM file offset is
the right value. If a function ever assembles to the wrong size the location
counter collides and ld fails loudly rather than silently shifting the rest of
the ROM.

## Layout

```
/src        C sources, one per matched function or translation unit
/asm        split assembly, shrinking as src/ grows
/include    shared headers and struct definitions
/data       non-code binaries and asset manifests
/tools      analysis and match tooling
```

### Tools

| File | Purpose |
|---|---|
| `tools/setup_toolchain.sh` | Build agbcc + binutils, no root required |
| `tools/verify_rom.py` | SHA1 gate; refuses unknown or wrong-revision dumps |
| `tools/thumb.py` | Strict ARMv4T Thumb decoder |
| `tools/find_leaf_funcs.py` | Call-site-driven function discovery |
| `tools/match.sh` | cpp -> agbcc -> as -> raw Thumb bytes |
| `tools/verify_match.py` | Byte and instruction diff against the ROM |

`tools/thumb.py` exists because capstone's Thumb mode decodes ARMv6T2+
encodings (`cbz`, `it`, `movw`) that an ARM7TDMI cannot execute. Accepting
those silently turns data into plausible-looking functions, which is the main
way ROM maps go wrong. Capstone is used for display only.

---

## Prior art

No FFTA decompilation exists. These are worth reading before duplicating work:

- [LeonarthCG/FFTA_Engine_Hacks](https://github.com/LeonarthCG/FFTA_Engine_Hacks) — modular ASM engine hacks via Event Assembler. Real engine knowledge, no symbols.
- [spiiin/FFTAUtils](https://github.com/spiiin/FFTAUtils) — C# map arrangement/height data and compressors.
- [kwsch/FF_TA](https://github.com/kwsch/FF_TA) — damage calculator; battle formulas already reversed.
- [Data Crystal](https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance) — ROM map is a stub, but the jobs/items/abilities/strings subpages have content.

## Next steps

The remaining work, in order, is written up as a step-by-step roadmap in
[docs/roadmap.md](docs/roadmap.md).

Current execution state, decisions, risks, and dated evidence are maintained in
[docs/project-log.md](docs/project-log.md). Start there when resuming work and
update it with every material batch.

All four of the original goals are done: the leaf batch, the linker script and
full rebuild, the CI gate, and progress reporting.

The job table is finished, in the sense that the four still-unnamed offsets are
provably dead: no code in the ROM reads them, so there is nothing left to
discover about them. See [docs/job-table.md](docs/job-table.md).

The former highest-risk live-validation item is now closed.

1. **Mission fields.** Rewards, clan progression, dispatch job rules, pub fees,
   and dispatch difficulty are named; remaining computed/packed properties and
   mission-index grouping still need identifiable readers.
2. **The rest of the map blocks.** Terrain decodes; tile arrangement, the
   `+0x08` block and the Huffman-compressed graphics do not yet.
