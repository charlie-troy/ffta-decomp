#!/bin/bash
# Full ROM rebuild: compile every decompiled function, assemble the rest from
# the base ROM, link at absolute addresses, and verify the SHA1.
#
#   tools/build_rom.sh [path/to/baserom.gba]
#
# The ROM is never committed. It is staged as ./baserom.gba for .incbin.
set -u

TC="$HOME/ffta-toolchain"
AGBCC="$TC/agbcc/agbcc"
AS="$TC/local/usr/bin/arm-none-eabi-as"
LD="$TC/local/usr/bin/arm-none-eabi-ld"
OBJCOPY="$TC/local/usr/bin/arm-none-eabi-objcopy"
CFLAGS="-mthumb-interwork -Wimplicit -Wparentheses -O2"
ASFLAGS="-mcpu=arm7tdmi -mthumb-interwork"

cd "$(dirname "$0")/.." || exit 1
REPO="$PWD"
OBJ="build/obj"
mkdir -p "$OBJ"

TARGET_SHA1=4ac05441f4de70a4ec3dd932116346c61b8783d9

# ---- stage the base ROM ----
SRC_ROM="${1:-/mnt/d/Nintendo - Game Boy Advance/Final Fantasy Tactics Advance.gba}"
if [ ! -f baserom.gba ]; then
  [ -f "$SRC_ROM" ] || { echo "base ROM not found: $SRC_ROM"; exit 1; }
  cp "$SRC_ROM" baserom.gba
fi
have=$(sha1sum baserom.gba | cut -d' ' -f1)
if [ "$have" != "$TARGET_SHA1" ]; then
  echo "baserom.gba is not the expected revision"
  echo "  expected $TARGET_SHA1"
  echo "  got      $have"
  exit 1
fi

# ---- compile every decompiled function ----
echo "=== compiling C ==="
ok=0
fail=0
for src in src/*/*.c src/*.c; do
  [ -f "$src" ] || continue
  name="$(basename "$src" .c)"
  # agbcc opens .text with `.align 2, 0`, which sets the section alignment to 4
  # and makes GAS pad the section size up to a multiple of 4. A 26-byte function
  # then occupies 28 bytes and overruns whatever follows it in the ROM. The
  # linker script already places every function at its true (aligned) address,
  # so dropping that first directive is safe. Later .align directives, which
  # keep literal pools aligned, are left alone.
  if cpp -undef -nostdinc -P -o "$OBJ/$name.i" "$src" 2>"$OBJ/$name.err" \
     && "$AGBCC" $CFLAGS -o "$OBJ/$name.raw.s" "$OBJ/$name.i" 2>>"$OBJ/$name.err" \
     && awk '!d && /^\t\.align\t2, 0$/ { d=1; next } { print }' \
          "$OBJ/$name.raw.s" > "$OBJ/$name.s" \
     && { # Any remaining .align (a literal pool needs one) keeps the section
          # alignment at 4, so GAS rounds the section size up and fills the tail
          # with a Thumb nop, 0xC046. The ROM has zeros there. Appending an
          # explicit zero-filled align makes the padding zeros instead. Objects
          # with no remaining .align are not padded at all, and must not get
          # this, or they would grow into the following ROM bytes.
          # Note: grep BRE does not treat \t as a tab, so match .align alone.
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
[ "$fail" -eq 0 ] || exit 1

# Report any .text that is not exactly the size of the function it replaces.
# This is informational: the linker script is generated from the real object
# sizes below, so padding is tolerated as long as the ROM bytes it covers are
# zeros. It stays visible because a padded object is worth knowing about.
echo "=== object size check ==="
python3 tools/check_obj_sizes.py build/leaf_candidates.json "$OBJ" || true

# Generate rom.s and ldscript.txt from the objects that were just built, so
# placement reflects real section sizes rather than assumed ones.
echo "=== generating rom.s and ldscript.txt ==="
python3 tools/gen_build.py build/leaf_candidates.json \
  --objdir "$OBJ" --rom baserom.gba || exit 1

# ---- assemble the rest of the ROM ----
echo "=== assembling rom.s ==="
"$AS" $ASFLAGS -I "$REPO" -o "$OBJ/rom.o" asm/rom.s || exit 1

# ---- link and extract ----
echo "=== linking ==="
"$LD" -T ldscript.txt -o build/ffta.elf --no-warn-rwx-segments 2>/dev/null \
  || "$LD" -T ldscript.txt -o build/ffta.elf || exit 1
"$OBJCOPY" -O binary build/ffta.elf build/ffta.gba || exit 1

# ---- verify ----
echo "=== verifying ==="
size=$(stat -c %s build/ffta.gba)
got=$(sha1sum build/ffta.gba | cut -d' ' -f1)
echo "size: $size bytes"
echo "sha1: $got"
if [ "$got" = "$TARGET_SHA1" ]; then
  echo "ROM MATCHES"
  exit 0
fi
echo "ROM DOES NOT MATCH (expected $TARGET_SHA1)"
cmp -l baserom.gba build/ffta.gba 2>/dev/null | head -20
echo "differing bytes: $(cmp -l baserom.gba build/ffta.gba 2>/dev/null | wc -l)"
exit 1
