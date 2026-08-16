# Non-matching sources

Functions whose C is behaviourally right but does not yet reproduce the ROM
bytes. Kept out of `src/` so that everything under `src/` is known-matching.

Each is a good permuter candidate: the structure is correct and only register
allocation or operand order is off, which is the regime the permuter handles
well.

| Function | Off by | What is wrong |
|---|---|---|
| `sub_08092084` | 2 bytes | Second store computes `offset + p`; the original computes `p + offset`. Assigning through a pointer temp fixed the first store the same way but not the second. |
| `sub_080DD580` | 6 bytes | Was 24 off until the mask became an `int` variable, which forced gcc to emit the compare instead of folding `(v >> 7) & 1 == 1` away. Remainder is register allocation around the result variable. |
| `sub_08017B50` | 8 bytes | The clamp loads its two operands into the opposite registers. The original puts the value in `r0` and the limit in `r1`; agbcc does the reverse, and swapping the declaration order did not move it. |

To attack one, copy it into a `permuter/<name>/` scratch dir following
`permuter/sub_080CD92C/` as the template, and see `docs/matching-notes.md` for
the setup gotchas.
