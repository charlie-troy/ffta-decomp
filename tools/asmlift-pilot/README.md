# asmlift pilot: attack the two parked functions with a structural decompiler

## Why

`sub_080DD580` (6 bytes off) and `sub_080BDC20` (13 bytes off) are parked:
hand iteration and both permuters (pret's and the ARMv4T fork) converged to
the same local optima, so more random search is waste. The gambiconf write-up
of Macabeus's Klonoa project reports **asmlift** - an agent-built, programmatic
matching decompiler for exactly these retro compilers - matching non-trivial
functions in one shot, which is the class of tool that can break a converged
diff where random mutation cannot.

## Status (2026-09-02): vendored, not yet run

The two parked functions were targeted as pilots because each is a decisive
test: if a structural decompiler cannot crack a 6-byte diff, nothing will,
and the "parked, not open" verdict gains a second independent method behind it.

This machine has no Rust toolchain (WSL has no cargo), so the pilot is
prepared rather than executed:

- `tools/asmlift-pilot/setup.sh` - clones asmlift, builds it, emits the two
  pilot inputs in the exact format this repo already trusts. Run under WSL.
- `tools/asmlift-pilot/README.md` - what to run, what counts as success,
  and what to do with the result.

The inputs are derived from `data/functions.json` + `data/symbols.txt`, so
they are byte-faithful to the same evidence the permuters used.

The parked baselines for comparison live in `permuter/sub_080BDC20/` and the
`nonmatching/` table (best diffs: 6 and 13 bytes).

## Success criteria

1. `setup.sh` completes and produces a `.c` candidate for each function.
2. `make match SRC=nonmatching/sub_080DD580.c AT=0xdd580 LEN=32` (or the
   asmlift candidate fed through the same pipeline) shows a smaller diff,
   ideally zero. `sub_080BDC20` likewise at its address.
3. If it matches: move the file into `src/`, `make index`, `make check`,
   `make rom`, then delete the `nonmatching/` row. If it reduces but does not
   match: record the new diff in the nonmatching table as the new baseline.

Failure is informative either way; do not iterate indefinitely. If asmlift's
candidate is worse than the parked baseline, keep the baseline and say so in
the nonmatching table.
