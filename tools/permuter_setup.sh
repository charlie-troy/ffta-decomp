#!/bin/bash
# Assemble target.s -> target.o for a permuter scratch dir, and dump the bytes
# so they can be checked against the ROM before any search is trusted.
#
#   tools/permuter_setup.sh permuter/sub_080CD92C
set -eu

TC="$HOME/ffta-toolchain"
AS="$TC/local/usr/bin/arm-none-eabi-as"
OBJCOPY="$TC/local/usr/bin/arm-none-eabi-objcopy"

DIR="${1:?usage: permuter_setup.sh <scratchdir>}"
chmod +x "$DIR/compile.sh"

"$AS" -mcpu=arm7tdmi -mthumb-interwork -o "$DIR/target.o" "$DIR/target.s"
"$OBJCOPY" -O binary --only-section=.text "$DIR/target.o" "$DIR/target.bin"

echo "=== target.bin ==="
od -An -tx1 -v "$DIR/target.bin" | tr -s ' '

echo "=== base.c sanity compile ==="
"$DIR/compile.sh" "$DIR/base.c" -o "$DIR/base.o"
"$OBJCOPY" -O binary --only-section=.text "$DIR/base.o" "$DIR/base.bin"
od -An -tx1 -v "$DIR/base.bin" | tr -s ' '
echo "setup ok"
