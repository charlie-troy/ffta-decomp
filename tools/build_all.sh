#!/bin/bash
# Compile every C file in a directory to raw Thumb bytes.
#
#   tools/build_all.sh <srcdir> <outdir>
#
# One WSL invocation for the whole batch; per-file failures are reported but
# do not stop the run.
set -u

TC="$HOME/ffta-toolchain"
AS="$TC/local/usr/bin/arm-none-eabi-as"
OBJCOPY="$TC/local/usr/bin/arm-none-eabi-objcopy"

# Overridable so the flag matrix can sweep compiler revision and opt level.
AGBCC="${AGBCC_BIN:-$TC/agbcc/agbcc}"
CFLAGS="${AGBCC_CFLAGS:--mthumb-interwork -Wimplicit -Wparentheses -O2}"

SRCDIR="${1:?usage: build_all.sh <srcdir> <outdir>}"
OUT="${2:?usage: build_all.sh <srcdir> <outdir>}"
mkdir -p "$OUT"

ok=0
fail=0
for src in "$SRCDIR"/*.c; do
  [ -f "$src" ] || continue
  name="$(basename "$src" .c)"
  if cpp -undef -nostdinc -P -o "$OUT/$name.i" "$src" 2>"$OUT/$name.err" \
     && "$AGBCC" $CFLAGS -o "$OUT/$name.s" "$OUT/$name.i" 2>>"$OUT/$name.err" \
     && "$AS" -mcpu=arm7tdmi -mthumb-interwork -o "$OUT/$name.o" "$OUT/$name.s" 2>>"$OUT/$name.err" \
     && "$OBJCOPY" -O binary --only-section=.text "$OUT/$name.o" "$OUT/$name.bin" 2>>"$OUT/$name.err"
  then
    ok=$((ok + 1))
    rm -f "$OUT/$name.err" "$OUT/$name.i" "$OUT/$name.o"
  else
    fail=$((fail + 1))
    echo "COMPILE FAIL: $name"
    head -3 "$OUT/$name.err"
  fi
done

echo "compiled $ok, failed $fail"
