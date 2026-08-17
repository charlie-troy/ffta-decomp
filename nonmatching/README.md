# Non-matching sources

Functions whose C is behaviourally right but does not yet reproduce the ROM
bytes. Kept out of `src/` so that everything under `src/` is known-matching.

| Function | Off by | Permuter best | What is wrong |
|---|---|---|---|
| `sub_080DD580` | 6 bytes | 60 | Register allocation around the result variable. Was 24 off until the mask became an `int` variable, which stopped gcc folding `((v >> 7) & 1) == 1` down to no branch at all. Has failed the permuter twice, at two different bases. |
| `sub_080DBEB4` | 12 bytes | 35 | See the u32 flag pair below. |
| `sub_0809993C` | 12 bytes | not run | See the u32 flag pair below. |
| `sub_0804E014` | 18 bytes | 225 | The original places its literal pool mid-function, after an unconditional branch, and keeps a two-armed if/else; agbcc collapses the if/else and puts the pool at the end. Tried with both a literal address and an extern symbol: 18 bytes off either way, so this is **not** the folding problem. |

Skipped deliberately: `sub_0800AF8C`, which contains two mask computations whose
results are discarded. Dead code like that is unlikely to come out of any
natural C.

**Not for decompilation:** `sub_08142A94` is libgcc's `__negdi2`, not game code.
See the libgcc section of `docs/matching-notes.md`.

## The u32 flag set/clear pair

`sub_080DBEB4` and `sub_0809993C` are the same shape: a `u32` field is either
or-ed with a bit or and-ed with its complement, chosen by a branch, then stored
once at the join.

```
    ldr  r0, [r2, #0x30]     <- value in r0
    movs r1, #2              <- constant in r1
    rsbs r1, r1, #0
    ands r0, r1
```

agbcc puts the value in `r1` and the constant in `r0`, the reverse. Both
functions come out **exactly 12 bytes off**, which is what makes this one
problem rather than two. Promoting the constants to `int` variables, the fix
that works for the cluster-A getters, does not move either of them.

Solving one solves both, and probably others of the shape. This is the best
remaining lead in this directory.

## Solved: the literal-pool blocker

Four functions used to sit here failing the same way, and all four now match.
The cause was declaring globals as cast literal addresses instead of real
`extern` symbols: agbcc folds a constant address with a constant offset, and
cannot fold a symbol. See `docs/matching-notes.md`. If a function that touches a
global will not match, check that first.

## Before queueing another permuter run

**Compile the base first.** In one queue, `sub_080C8240`'s base already matched
at iteration 1 and the search was spent confirming it. One build is cheaper
than five minutes of searching.

A permuter "best score" is only meaningful within a single run: the `output-*`
directories persist between runs, so reading them back can report a stale score
from an earlier attempt.
