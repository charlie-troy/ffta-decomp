#!/bin/bash
# Compile a candidate C file with agbcc and emit raw Thumb bytes for comparison.
#
#   tools/match.sh <src.c> [outdir]
#
# Runs inside WSL. Assumes the toolchain built by tools/setup_toolchain.sh.
set -u

TC="$HOME/ffta-toolchain"
AGBCC="$TC/agbcc/agbcc"
AS="$TC/local/usr/bin/arm-none-eabi-as"
OBJCOPY="$TC/local/usr/bin/arm-none-eabi-objcopy"

SRC="${1:?usage: match.sh <src.c> [outdir]}"
OUT="${2:-$(dirname "$SRC")/../build}"
mkdir -p "$OUT"
NAME="$(basename "$SRC" .c)"

CFLAGS="-mthumb-interwork -Wimplicit -Wparentheses -O2"

for t in "$AGBCC" "$AS" "$OBJCOPY"; do
  [ -x "$t" ] || { echo "missing tool: $t"; exit 1; }
done

echo "=== preprocess ==="
# agbcc is cc1 proper: it never runs the preprocessor, and being gcc 2.95 it
# does not accept // comments either. Both are cpp's job.
cpp -undef -nostdinc -P -o "$OUT/$NAME.i" "$SRC" || exit 1

echo "=== agbcc $CFLAGS ==="
"$AGBCC" $CFLAGS -o "$OUT/$NAME.s" "$OUT/$NAME.i" || exit 1
cat "$OUT/$NAME.s"

echo "=== assemble ==="
"$AS" -mcpu=arm7tdmi -mthumb-interwork -o "$OUT/$NAME.o" "$OUT/$NAME.s" || exit 1
"$OBJCOPY" -O binary --only-section=.text "$OUT/$NAME.o" "$OUT/$NAME.bin" || exit 1

echo "=== bytes ==="
od -An -tx1 -v "$OUT/$NAME.bin" | tr -s ' '
echo "OK $OUT/$NAME.bin"
