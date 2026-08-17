# Non-matching sources

Functions whose C is behaviourally right but does not yet reproduce the ROM
bytes. Kept out of `src/` so that everything under `src/` is known-matching.

| Function | Off by | What is wrong |
|---|---|---|
| `sub_080DD580` | 6 bytes | Register allocation around the result variable. Was 24 off until the mask became an `int` variable, which stopped gcc folding `((v >> 7) & 1) == 1` down to no branch at all. |
| `sub_080DBEB4` | 12 bytes | Value and mask in swapped registers, and the pointer temp is set up after the parameter truncation rather than before. Promoting both constants to `int` variables did not move it. |
| `sub_0801AD1C` | 15 bytes | gcc folds `base + 0x2000` into a second literal-pool constant instead of materialising `0x2000` in a register. An `int` offset variable did not stop the folding. |
| `sub_0804E014` | 18 bytes | The original places its literal pool mid-function, between an unconditional branch and the following label, and keeps a two-armed if/else. agbcc collapses the if/else into init-then-conditional-set and puts the pool at the end. |
| `sub_08006B9C` | 20 bytes | Register roles swapped: the original keeps the index in `r0` and the struct pointer in `r1`. |
| `sub_0800A024` | 23 bytes | Two halfword reads from a global at offsets beyond the `ldrh` immediate range. Not yet diagnosed. |

Also unmatched, still assembly rather than C: the 9 halfword flag getters of
cluster C (21 bytes off), and `sub_0800AF8C`, which contains two mask
computations whose results are discarded. Dead code like that is unlikely to
come out of any natural C and was skipped deliberately.

**Not for decompilation:** `sub_08142A94` is libgcc's `__negdi2`, not game code.
See the libgcc section of `docs/matching-notes.md`.

To attack one, build a scratch dir with
`python tools/make_permuter_dir.py build/leaf_candidates.json <name> <base.c>`,
verify it with `tools/permuter_setup.sh`, then run `tools/run_permuter.sh`.
Every one of these has correct structure with only register allocation or
instruction ordering wrong, which is the regime the permuter suits.
