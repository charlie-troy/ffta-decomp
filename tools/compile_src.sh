#!/bin/bash
# Compile every decompiled function to build/obj/<name>.o.
#
#   tools/compile_src.sh [objdir]
#
# Shared by the full ROM build and by CI, so the agbcc quirk handling below
# only exists in one place.
set -u

TC="${FFTA_TOOLCHAIN:-$HOME/ffta-toolchain}"
AGBCC="$TC/agbcc/agbcc"
AS="${ARM_AS:-$TC/local/usr/bin/arm-none-eabi-as}"
CFLAGS="-mthumb-interwork -Wimplicit -Wparentheses -O2"
ASFLAGS="-mcpu=arm7tdmi -mthumb-interwork"
PROJECT_CPPFLAGS="${FFTA_CPPFLAGS:-}"

cd "$(dirname "$0")/.." || exit 1
OBJ="${1:-build/obj}"
mkdir -p "$OBJ"

for t in "$AGBCC" "$AS"; do
  [ -x "$t" ] || { echo "missing tool: $t"; exit 1; }
done

ok=0
fail=0
for src in src/*/*.c src/*.c; do
  [ -f "$src" ] || continue
  name="$(basename "$src" .c)"

  # agbcc opens .text with `.align 2, 0`, which sets the section alignment to 4
  # and makes GAS round the section size up to a multiple of 4. A 26-byte
  # function would then occupy 28 and overrun whatever follows it in the ROM.
  # The linker script places every function at its true address, so dropping
  # that first directive is safe.
  #
  # Only the FIRST one may go: later .align directives keep literal pools
  # aligned, and removing those breaks any function that has one.
  #
  # Where a pool forces alignment 4 anyway, GAS fills the section tail with a
  # Thumb nop (0xC046) while the ROM has zeros there, so an explicit
  # zero-filled align is appended to exactly those objects.
  if cpp -undef -nostdinc -P $PROJECT_CPPFLAGS -o "$OBJ/$name.i" "$src" 2>"$OBJ/$name.err" \
     && "$AGBCC" $CFLAGS -o "$OBJ/$name.raw.s" "$OBJ/$name.i" 2>>"$OBJ/$name.err" \
     && awk '!d && /^\t\.align\t2, 0$/ { d=1; next } { print }' \
          "$OBJ/$name.raw.s" > "$OBJ/$name.s" \
     && { # grep BRE does not treat \t as a tab, so match .align alone
          if grep -q '\.align' "$OBJ/$name.s"; then
            printf '\t.align\t2, 0\n' >> "$OBJ/$name.s"
          fi
          "$AS" $ASFLAGS -o "$OBJ/$name.o" "$OBJ/$name.s" 2>>"$OBJ/$name.err"; }
  then
    ok=$((ok + 1))
    rm -f "$OBJ/$name.err" "$OBJ/$name.i"
  else
    fail=$((fail + 1))
    echo "COMPILE FAIL: $name"
    head -3 "$OBJ/$name.err"
  fi
done

echo "compiled $ok object(s), $fail failure(s)"
[ "$fail" -eq 0 ]
