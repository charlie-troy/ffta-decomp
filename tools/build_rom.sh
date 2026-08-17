#!/bin/bash
# Full ROM rebuild: compile every decompiled function, assemble the rest from
# the base ROM, link at absolute addresses, and verify the SHA1.
#
#   tools/build_rom.sh [path/to/baserom.gba]
#
# The ROM is never committed. It is staged as ./baserom.gba for .incbin.
set -u

TC="${FFTA_TOOLCHAIN:-$HOME/ffta-toolchain}"
AS="${ARM_AS:-$TC/local/usr/bin/arm-none-eabi-as}"
LD="${ARM_LD:-$TC/local/usr/bin/arm-none-eabi-ld}"
OBJCOPY="${ARM_OBJCOPY:-$TC/local/usr/bin/arm-none-eabi-objcopy}"
ASFLAGS="-mcpu=arm7tdmi -mthumb-interwork"

cd "$(dirname "$0")/.." || exit 1
REPO="$PWD"
OBJ="build/obj"
mkdir -p "$OBJ"

TARGET_SHA1=4ac05441f4de70a4ec3dd932116346c61b8783d9

# Canonical function manifest. functions_all.json merges luvdis's discovery
# with local scanning and covers functions the local scan cannot see; the older
# leaf_candidates.json is the fallback if the merge has not been run.
MANIFEST=build/functions_all.json
[ -f "$MANIFEST" ] || MANIFEST=build/leaf_candidates.json

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

# ---- compile ----
echo "=== compiling C ==="
bash tools/compile_src.sh "$OBJ" || exit 1

# Informational: the linker script is generated from real object sizes below,
# so padding is tolerated as long as it covers zero bytes in the ROM. A padded
# section is still worth seeing.
echo "=== object size check ==="
python3 tools/check_obj_sizes.py "$MANIFEST" "$OBJ" || true

# ---- generate placement from the objects just built ----
echo "=== generating rom.s and ldscript.txt ==="
python3 tools/gen_build.py "$MANIFEST" \
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
