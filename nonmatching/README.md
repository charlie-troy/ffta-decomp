# Non-matching sources

Functions whose C is behaviourally right but does not yet reproduce the ROM
bytes. Kept out of `src/` so that everything under `src/` is known-matching.

| Function | Off by | Permuter best | What is wrong |
|---|---|---|---|
| `sub_080DD580` | 6 bytes | 60 | Register allocation around the result variable. Was 24 off until the mask became an `int` variable, which stopped gcc folding `((v >> 7) & 1) == 1` down to no branch at all. Has failed the permuter twice, at two different bases. |
| `sub_0804E014` | 18 bytes | 225 | See the pool-placement pair below. |
| `sub_0800395C` | 21 bytes | not run | See the pool-placement pair below. |

Skipped deliberately: `sub_0800AF8C`, which contains two mask computations whose
results are discarded. Dead code like that is unlikely to come out of any
natural C.

**Not for decompilation:** `sub_08142A94` is libgcc's `__negdi2`, not game code.
See the libgcc section of `docs/matching-notes.md`.

## The pool-placement pair

`sub_0804E014` and `sub_0800395C` both put their literal pool **mid-function**,
immediately after an unconditional branch and before the following label:

```
    b    .L2
    <pool word>
.L1:
    ...
```

agbcc puts the pool at the end of the function instead, which shifts every
pc-relative load offset and the branch distances with it. Both also keep a
two-armed structure that agbcc collapses.

`sub_0804E014` was tried with both a literal address and an extern symbol and is
18 bytes off either way, so this is **not** the folding problem that was solved
earlier. Two functions with the same signature makes it a class worth one probe
rather than more per-function guessing: the question to answer is what makes
agbcc emit a pool early.

## Solved, and what solved them

Two blocker classes that each held several functions have been cleared. Both
fell to the same method: write one probe file containing every plausible
spelling, compile it, and read agbcc's assembly, rather than iterating on the
real function.

- **The literal-pool blocker** (4 functions). Globals must be real `extern`
  symbols, not cast literal addresses; agbcc folds a constant address with a
  constant offset and cannot fold a symbol.
- **The u32 flag pair** (2 functions). The branch must be written as a ternary,
  not an if/else, or the value and the constant land in swapped registers.

Both are written up in `docs/matching-notes.md`. If a function will not match,
check those two before reaching for the permuter.

## Before queueing another permuter run

**Compile the base first.** In one queue, `sub_080C8240`'s base already matched
at iteration 1 and the search was spent confirming it. One build is cheaper
than five minutes of searching.

A permuter "best score" is only meaningful within a single run: the `output-*`
directories persist between runs, so reading them back can report a stale score
from an earlier attempt.
