# Non-matching sources

Functions whose C is behaviourally right but does not yet reproduce the ROM
bytes. Kept out of `src/` so that everything under `src/` is known-matching.

| Function | Off by | Permuter best | What is wrong |
|---|---|---|---|
| `sub_080DD580` | 6 bytes | 60 | Register allocation around the result variable. Was 24 off until the mask became an `int` variable, which stopped gcc folding `((v >> 7) & 1) == 1` down to no branch at all. Has failed the permuter twice, at two different bases. |
| `sub_080DBEB4` | 12 bytes | 35 | Value and mask in swapped registers, and the pointer temp is set up after the parameter truncation. Promoting both constants to `int` variables did not move it. |
| `sub_0804E014` | 18 bytes | 225 | The original places its literal pool mid-function, after an unconditional branch, and keeps a two-armed if/else; agbcc collapses the if/else and puts the pool at the end. Tried with both a literal address and an extern symbol: 18 bytes off either way, so this is **not** the folding problem. |

Skipped deliberately: `sub_0800AF8C`, which contains two mask computations whose
results are discarded. Dead code like that is unlikely to come out of any
natural C.

**Not for decompilation:** `sub_08142A94` is libgcc's `__negdi2`, not game code.
See the libgcc section of `docs/matching-notes.md`.

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
