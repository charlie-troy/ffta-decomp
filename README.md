# ffta-decomp

A matching decompilation of **Final Fantasy Tactics Advance** (GBA, USA).

The goal is C source that rebuilds the original ROM byte for byte.

> **No ROM data lives in this repository.** You supply your own dump. The build
> verifies its SHA1 and extracts what it needs at build time. `.gitignore`
> excludes `*.gba` and `*.bin`; keep it that way.

---

## Status

**The full 16 MB ROM rebuilds byte-identical.** 140 functions are compiled from
C and placed at their real addresses; everything else is pulled from the base
ROM with `.incbin`. `make rom` fails unless the SHA1 matches, so no change can
silently break the build.

| | |
|---|---|
| Target ROM | FFTA (USA), `AFXE`, rev 0 |
| SHA1 | `4ac05441f4de70a4ec3dd932116346c61b8783d9` |
| Compiler | **agbcc** (pret's patched gcc 2.95.3, the AGB SDK compiler) |
| Flags | `-mthumb-interwork -Wimplicit -Wparentheses -O2` |
| Functions matched | **140** (3,780 bytes) |
| Full ROM rebuild | **matching** |
| Functions discovered | 3,394 call targets, 212 leaf candidates |

```bash
make setup && make rom
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

1. Match a batch of the 124 leaf candidates to establish conventions and build a struct catalogue.
2. Write the linker script and splitter; get a full ROM rebuild passing with everything still as assembly.
3. Wire up a CI SHA1 check so the rebuild is verified on every commit.
4. Add progress reporting (matched bytes / total code bytes).
