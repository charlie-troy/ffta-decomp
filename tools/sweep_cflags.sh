#!/bin/bash
# Try individual agbcc optimisation flags against the non-matching sources.
#
#   tools/sweep_cflags.sh [srcdir] [outroot]
#
# The stuck functions all fail on register allocation or instruction ordering,
# and agbcc exposes switches for exactly those passes. Per-file flags are
# normal in decomp projects, so a flag that fixes one file is usable even if it
# is wrong globally.
set -u

cd "$(dirname "$0")/.." || exit 1
SRC="${1:-nonmatching}"
OUTROOT="${2:-build/cflags}"
BASE="-mthumb-interwork -Wimplicit -Wparentheses -O2"

FLAGS=(
  "baseline:"
  "no-regmove:-fno-regmove"
  "no-opt-reg-move:-fno-optimize-register-move"
  "no-caller-saves:-fno-caller-saves"
  "no-cse-follow-jumps:-fno-cse-follow-jumps"
  "no-cse-skip-blocks:-fno-cse-skip-blocks"
  "no-thread-jumps:-fno-thread-jumps"
  "no-expensive:-fno-expensive-optimizations"
  "no-strength-reduce:-fno-strength-reduce"
  "no-rerun-cse:-fno-rerun-cse-after-loop"
  "no-rerun-loop:-fno-rerun-loop-opt"
  "no-peephole:-fno-peephole"
  "force-addr:-fforce-addr"
  "force-mem:-fforce-mem"
  "no-defer-pop:-fno-defer-pop"
  "no-function-cse:-fno-function-cse"
  "no-gcse:-fno-gcse"
  "no-move-all-movables:-fno-move-all-movables"
  "no-reduce-all-givs:-fno-reduce-all-givs"
  "no-opt-comparisons:-fno-optimize-comparisons"
  "prologue-bugfix:-fprologue-bugfix"
  "omit-frame-pointer:-fomit-frame-pointer"
)

for entry in "${FLAGS[@]}"; do
  tag="${entry%%:*}"
  flag="${entry#*:}"
  AGBCC_CFLAGS="$BASE $flag" bash tools/build_all.sh "$SRC" "$OUTROOT/$tag" \
    >/dev/null 2>&1
done

echo "swept ${#FLAGS[@]} flag settings into $OUTROOT"
