# Non-matching sources

Functions whose C is behaviourally right but does not yet reproduce the ROM
bytes. Kept out of `src/` so that everything under `src/` is known-matching.

Each has now had a 5-minute permuter run at its listed base. Best permuter
score is shown where it beat or failed to beat the hand-written starting point.

| Function | Off by | Permuter best | What is wrong |
|---|---|---|---|
| `sub_080DD580` | 6 bytes | 60 | Register allocation around the result variable. Has now failed the permuter twice, at two different bases. |
| `sub_080DBEB4` | 12 bytes | 35 | Value and mask in swapped registers, and the pointer temp is set up after the parameter truncation. The permuter improved on the base but did not match. |
| `sub_0801AD1C` | 15 bytes | 400 | gcc folds `base + 0x2000` into a second literal-pool constant instead of materialising it in a register. The permuter regressed well past the base. |
| `sub_0804E014` | 18 bytes | 225 | The original places its literal pool mid-function and keeps a two-armed if/else; agbcc collapses the if/else and puts the pool at the end. |
| `sub_0800A024` | 23 bytes | 300 | Two halfword reads from a global at offsets beyond the `ldrh` immediate range. Still undiagnosed. |

## The literal-pool blocker

Three of these now fail the same way, and it is the main thing standing between
the current state and the next batch of matches:

| Function | Off by | Pool problem |
|---|---|---|
| `sub_0801AD1C` | 15 bytes | gcc folds `base + 0x2000` into a second pool constant; the original materialises `0x2000` in a register and adds at runtime |
| `sub_080099A4` | 25 bytes | gcc emits `ldr r0, [r0, #4]`; the original adds 4 to the pool-loaded base at runtime, then loads with no offset |
| `sub_0800BC08` | 29 bytes | global array store, same family |

The pattern: when a constant address and a constant offset meet, agbcc folds
them and the original does not. Promoting the offset to an `int` variable, which
fixes the analogous register-allocation problems, does **not** stop the folding.
Whatever forces the split is not yet understood, and finding it would likely
unlock all three at once plus much of the remaining global-accessing code.

Also skipped deliberately: `sub_0800AF8C`, which contains two mask computations
whose results are discarded. Dead code like that is unlikely to come out of any
natural C.

**Not for decompilation:** `sub_08142A94` is libgcc's `__negdi2`, not game code.
See the libgcc section of `docs/matching-notes.md`.

## Before queueing another permuter run

**Compile the base first.** In the last queue, `sub_080C8240`'s base already
matched at iteration 1 and the search was wasted confirming it. One build is
cheaper than five minutes of searching.

Note also that a permuter "best score" is only meaningful within one run: the
`output-*` directories persist between runs, so reading them back can report a
stale score from an earlier attempt.
