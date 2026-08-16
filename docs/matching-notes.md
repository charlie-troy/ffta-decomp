# Matching notes

## Where things stand

**Matched: 2 functions.** Both are branch-free.

| Function | Bytes | Status |
|---|---|---|
| `sub_08005BB0` | 18 | match, first try |
| `sub_080DBD5C` | 20 | match, first try |

**Not matched: the three large accessor clusters (~100 functions).** All of them
contain a conditional branch, and all of them plateau at a small, *constant*
residual difference no matter how the C is spelled.

## The open problem

agbcc reproduces straight-line code exactly and branchy code almost-but-not-quite.
That split is the whole story so far, and it is the thing to solve next.

### Cluster A: byte flag getter (43 functions)

Original, e.g. `sub_080CD92C` (offset `0xE8`, mask `0x40`):

```
push {lr}
adds r0, #0xe8
movs r1, #0x40      <- mask into r1
ldrb r0, [r0]       <- value into r0, reusing the dead pointer
ands r0, r1
cmp  r0, #0
beq  .L0
movs r0, #1
b    .L1
.L0: movs r0, #0
.L1: pop {r1}
     bx r1
```

Two independent discrepancies were found, one solved and one not:

1. **Branch polarity — solved.** Writing the condition positively
   (`if (x & m) return 1; return 0;`) yields the mirror-image layout. Writing it
   negated (`if (!(x & m)) return 0; return 1;`) yields the original layout.
   This took the diff from 7 bytes to 4.

2. **Operand order — unsolved.** The original puts the mask in `r1` and loads
   the value into `r0`; agbcc does the reverse, costing exactly 4 bytes (two
   instructions). Thirteen spellings were tried, all landing on 4:
   plain if, `!=0`, `==0`, negated, ternary, mask-first (`0x40 & x`), u8 temp,
   int temp, pointer temp, separate mask variable, bitfield read, bitfield in an
   if, and an explicit else. Every one produced an identical 4-byte residual.

That invariance across spellings is the important datum: the difference is not
expressible in the source, so it is coming from the compiler.

### Cluster B: byte flag setter (45 functions)

Structurally solved, register allocation not. Using an `int` temporary
reproduces the distinctive `movs r3, #0x11; rsbs r3, r3, #0` (the mask kept as a
32-bit `~0x10` = `0xFFFFFFEF` rather than narrowed to `0xEF`), which is the
tell that the cleared value lives in an int-width temporary and is reused.

Remaining: the original allocates `r2`/`r3` the other way round, and its final
or-in is three instructions (`adds r0, r3, #0; movs r1, #0x10; orrs r0, r1`)
against agbcc's two (`movs r0, #0x10; orrs r2, r0`), implying the store target
and the or-ed value are distinct variables in the original source.

### Cluster C: halfword flag getter (9 functions)

The original does the naive thing: `and`, truncate to u16 via `lsl #16; lsr #16`,
then test `!= 0` via `rsbs r0, r0, #0; lsrs r1, r0, #31`. agbcc instead optimises
`(x & 0x8000) != 0` into a single shift. Forcing a `u16` temporary gets the
truncation back but not the rest.

## What was ruled out

- **Compiler revision.** `agbcc` beats `old_agbcc` decisively (4 vs 22 bytes off
  on the getter), so `agbcc` is the right one of the two.
- **Optimisation level.** `-O0/-O1/-O2/-O3/-Os` were swept across both compiler
  revisions. `-O2` and `-O3` tie for best; nothing matches. `-O0` is far worse,
  confirming the ROM is an optimised build.

## Next things to try

1. **A permuter.** This is exactly what `decomp-permuter` exists for: it mutates
   a source that is already close and searches for the spelling that matches.
   Hand-permuting has hit its limit at 4 bytes.
2. **Other agbcc forks.** Several GBA decomp projects maintain their own agbcc
   patches. A fork whose branch and register-allocation behaviour differs
   slightly may be the actual answer, given how uniform the residual is.
3. **A different SDK compiler revision.** agbcc reports itself as
   `gcc 2.9-arm-000512`. The AGB SDK shipped more than one build, and Square was
   not Game Freak; pret's agbcc is tuned to reproduce Game Freak's ROMs
   specifically.
4. **Confirm on more branch-free functions.** Cheap sanity check: if every
   branch-free leaf matches first try and every branchy one does not, that
   sharpens the diagnosis considerably.
