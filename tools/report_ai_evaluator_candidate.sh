#!/bin/bash
# Compile the readable evaluator with agbcc and report the whole-function
# matching baseline without flooding the terminal with generated assembly.
set -euo pipefail

SRC="${1:-reference/ai_ability_eval.c}"
OUT="${2:-build/ai_eval_probe}"
TARGET_SIZE=5352
NM="$HOME/ffta-toolchain/local/usr/bin/arm-none-eabi-nm"

mkdir -p "$OUT"
bash tools/match.sh "$SRC" "$OUT" > "$OUT/compile.log" 2>&1

NAME="$(basename "$SRC" .c)"
OBJ="$OUT/$NAME.o"
ASM="$OUT/$NAME.s"
SIZE_HEX="$($NM -S --size-sort "$OBJ" | awk '$4 == "AiEvaluateAbility" { print $2 }')"

if [ -z "$SIZE_HEX" ]; then
    echo "AiEvaluateAbility was not emitted" >&2
    exit 1
fi

SIZE=$((16#$SIZE_HEX))
DELTA=$((SIZE - TARGET_SIZE))
RNG_CALLS=$(grep -c $'\tbl\tsub_08002804' "$ASM" || true)
MOD_CALLS=$(grep -c $'\tbl\tsub_08142950' "$ASM" || true)

grep -q $'\tadd\tsp, sp, #-20' "$ASM"
grep -q $'\tstr\tr2, \[sp, #12\]' "$ASM"
grep -Eq '^[[:space:]]+str[[:space:]]+r0, \[sp, #16\]' "$ASM"
grep -Eq '^[[:space:]]+str[[:space:]]+r2, \[sp, #16\]' "$ASM"
test "$RNG_CALLS" -eq 85
test "$MOD_CALLS" -eq 85

printf 'AiEvaluateAbility: %d / %d bytes (%+d)\n' "$SIZE" "$TARGET_SIZE" "$((SIZE - TARGET_SIZE))"
printf 'frame: 20 bytes; action sp+12; candidate index sp+16\n'
printf 'probability calls: RNG %d / modulo %d\n' "$RNG_CALLS" "$MOD_CALLS"
if [ "$DELTA" -gt 0 ]; then
    printf 'remaining shaping delta: remove %d bytes\n' "$DELTA"
elif [ "$DELTA" -lt 0 ]; then
    printf 'remaining shaping delta: add %d bytes\n' "$((-DELTA))"
else
    printf 'remaining shaping delta: size aligned; byte comparison still required\n'
fi
