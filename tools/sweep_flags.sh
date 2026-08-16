#!/bin/bash
# Build one source tree under every (compiler revision, optimisation) combo.
#
#   tools/sweep_flags.sh <srcdir> <outroot>
#
# pret's agbcc ships two compiler revisions and projects differ in which one
# reproduces a given ROM, so the compiler is a variable to solve for, not a
# constant to assume.
set -u

TC="$HOME/ffta-toolchain"
SRCDIR="${1:?usage: sweep_flags.sh <srcdir> <outroot>}"
OUTROOT="${2:?usage: sweep_flags.sh <srcdir> <outroot>}"
HERE="$(dirname "$0")"

for cc in agbcc old_agbcc; do
  [ -x "$TC/agbcc/$cc" ] || continue
  for opt in O2 O1 Os O3 O0; do
    tag="${cc}_${opt}"
    echo "=== $tag ==="
    AGBCC_BIN="$TC/agbcc/$cc" \
    AGBCC_CFLAGS="-mthumb-interwork -Wimplicit -Wparentheses -$opt" \
      bash "$HERE/build_all.sh" "$SRCDIR" "$OUTROOT/$tag" 2>&1 | tail -2
  done
done
