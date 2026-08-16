# Non-matching sources

Functions whose C is behaviourally right but does not yet reproduce the ROM
bytes. Kept out of `src/` so that everything under `src/` is known-matching.

| Function | Off by | What is wrong |
|---|---|---|
| `sub_080DD580` | 6 bytes | Register allocation around the result variable. Was 24 off until the mask became an `int` variable, which stopped gcc folding `((v >> 7) & 1) == 1` down to no branch at all. A 5-minute permuter run reached a best score of 60 without matching. |
| `sub_08006B9C` | 20 bytes | Register roles are swapped: the original keeps the index in `r0` and the struct pointer in `r1`, agbcc does the reverse. Two hand rewrites, including an explicit pointer temp, did not move it. |

Also unmatched, still assembly rather than C: the 9 halfword flag getters of
cluster C (21 bytes off).

**Not for decompilation:** `sub_08142A94` is libgcc's `__negdi2`, not game code.
See the libgcc section of `docs/matching-notes.md`.

To attack one, build a scratch dir with
`python tools/make_permuter_dir.py build/leaf_candidates.json <name> <base.c>`,
verify it with `tools/permuter_setup.sh`, then run `tools/run_permuter.sh`.
