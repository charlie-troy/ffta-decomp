# Matching notes

## Where things stand

**Matched: 57 functions, 1,284 bytes.**

| Group | Count | Status |
|---|---|---|
| `sub_08005BB0`, `sub_080DBD5C` | 2 | match, hand-written, first try |
| Cluster A, byte flag getters | 43 | match, template found by permuter |
| Batch 1, assorted small leaves | 12 | match, hand-written |
| Cluster A-alt, getters with swapped setup order | 3 | 4 bytes off |
| Cluster B, byte flag setters | 45 | stalled at 20 bytes off |
| Cluster C, halfword flag getters | 9 | stalled, permuter regressed |

## Branch polarity depends on the test, not a house rule

The single most useful rule so far, and it cuts both ways:

- **Masked flag tests** (`x & mask`) want the **negated** form:
  `if (!(x & m)) return 0; return 1;`
- **Equality tests** (`x == k`) want the **positive** form:
  `if (x == k) return 1; return 0;`

Applying the getter's negation lesson blindly to `sub_08010FF0` produced exactly
the mirror-image layout. Flipping it matched. Do not generalise polarity across
test kinds; check the `beq`/`bne` in the target and pick to suit.

Second rule from batch 1: **statement order in the source shows up in the
output.** `sub_0800C614` needed the halfword load written before the zero-init
of the result variable, because the original emits `ldrh` before `movs r2, #0`.
Reading the target's instruction order and mirroring it in the source is worth
doing before reaching for the permuter.

Batch 1 hit 10/12 on the first attempt and 12/12 after applying these two
rules, which is a far better rate than the permuter managed on the stuck
clusters. Hand-writing with the target disassembly open is the productive mode;
the permuter is for when that plateaus.

## The lesson that unlocked cluster A

Three independent details all had to be right at once, and getting two of three
still leaves a stable non-zero diff. This is why hand-permuting stalled:

1. **The condition must be negated.** `if (x & m) return 1; return 0;` produces
   the mirror-image branch layout. `if (!(x & m)) return 0; return 1;` produces
   the original. Worth 3 bytes.
2. **The field must be reached through a pointer temp**, not `obj->flags`
   directly.
3. **The mask must be an `int` variable, not a literal.** A literal `0x40` and a
   variable holding `0x40` allocate registers differently; the literal puts the
   mask in `r0` and the value in `r1`, the original wants the reverse.

Final matching form:

```c
u8 sub_080CD92C(struct Obj *obj)
{
    u8 *p = &obj->flags;
    int mask = 0x40;

    if (!(*p & mask))
        return 0;
    return 1;
}
```

Thirteen hand-written spellings all plateaued at exactly 4 bytes off, because
each one got at most two of the three details right. decomp-permuter found the
combination at iteration 2496, in under four minutes.

The generated template in `tools/gen_bitfield.py` applies this to all 43
functions in the cluster, varying only the struct offset and mask, and every one
matches.

**Caveat worth keeping in mind:** matching is not the same as being the original
source. `int mask = 0x40;` is unlikely to be literally what Square wrote. It
reproduces the codegen exactly, which is what a matching decomp requires, but
the shape of the real source may become clearer once neighbouring functions are
done and a house style emerges.

## Setting up the permuter

Non-obvious bits, all handled by the checked-in scripts:

- `prelude.inc` in decomp-permuter is **MIPS-only**. ARM targets must not
  include it; `permuter/*/target.s` is plain Thumb with its own header.
- `compile.sh` is invoked as `./compile.sh input.c -o output.o`, so the output
  path is `$3`, not `$2`.
- `arm-none-eabi-objdump` must be on `PATH` for the ARM32 scorer.
- Ubuntu 24.04 is PEP668-managed, so the permuter's `toml` and `pycparser` live
  in a venv at `~/ffta-toolchain/permuter-venv`.
- `target.s` is worth verifying: `tools/permuter_setup.sh` assembles it and
  dumps the bytes so they can be checked against the ROM before any search runs.
  A wrong target silently searches for the wrong thing.

## What was ruled out earlier

- **Compiler revision.** `agbcc` beats `old_agbcc` decisively (4 vs 22 bytes off
  on the getter). `agbcc` is correct.
- **Optimisation level.** `-O0/-O1/-O2/-O3/-Os` swept across both revisions.
  `-O2` is right; `-O0` is far worse, confirming an optimised build.

The earlier hypothesis that a different compiler revision was needed turned out
to be wrong. The residual was a source-spelling problem after all, just a
three-dimensional one that hand-search was poorly suited to.

## Next

1. Finish clusters B and C via the permuter, then template them.
2. Chase the 3-function A-alt shape, where the mask setup precedes the pointer
   arithmetic.
3. Move on to the 111 single-member shapes, which will need individual work.
4. Linker script and full-ROM rebuild with everything else still assembly.
