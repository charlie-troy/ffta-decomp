# Non-matching sources

Functions whose C is behaviourally right but does not yet reproduce the ROM
bytes. Kept out of `src/` so that everything under `src/` is known-matching.

| Function | Off by | What is wrong |
|---|---|---|
| `sub_080DD580` | 6 bytes | Register allocation around the result variable. Was 24 off until the mask became an `int` variable, which stopped gcc folding `((v >> 7) & 1) == 1` down to no branch at all. A 5-minute permuter run got to a best score of 60 without matching. |

Also unmatched, still as assembly rather than C: the 3 `sub_080CD9xx`-family
getters whose mask setup precedes the pointer arithmetic (4 bytes off), and the
9 halfword flag getters of cluster C.

To attack one, build a scratch dir with
`python tools/make_permuter_dir.py build/leaf_candidates.json <name> <base.c>`,
verify it with `tools/permuter_setup.sh`, then run `tools/run_permuter.sh`.
See `docs/matching-notes.md` for the setup gotchas.
