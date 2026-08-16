#!/bin/bash
# Build the FFTA decomp toolchain. Idempotent, safe to re-run, needs no root.
#
# Installs into $HOME/ffta-toolchain:
#   agbcc/           pret's patched gcc 2.95.3 (the AGB SDK compiler)
#   local/usr/bin/   arm-none-eabi binutils, extracted from the .deb
#
# Run from WSL:  bash tools/setup_toolchain.sh
set -u

TC="$HOME/ffta-toolchain"
mkdir -p "$TC/debs" "$TC/local"

echo "=== [1/2] agbcc ==="
if [ -x "$TC/agbcc/agbcc" ]; then
  echo "already built: $TC/agbcc/agbcc"
else
  cd "$TC" || exit 1
  [ -d agbcc/.git ] || git clone --depth 1 https://github.com/pret/agbcc.git
  cd agbcc || exit 1
  # build.sh also builds libgcc/libc, which needs an ARM assembler. The
  # compilers themselves are produced before that step, so a non-zero exit
  # here is expected and harmless until binutils is in place.
  ./build.sh > "$TC/agbcc_build.log" 2>&1
  for b in agbcc old_agbcc agbcc_arm; do
    [ -x "$TC/agbcc/$b" ] && echo "built: $b"
  done
fi

echo "=== [2/2] arm-none-eabi binutils ==="
if [ -x "$TC/local/usr/bin/arm-none-eabi-as" ]; then
  echo "already installed"
else
  cd "$TC/debs" || exit 1
  apt-get download binutils-arm-none-eabi || {
    echo "download failed; if apt lists are stale run: sudo apt-get update"
    exit 1
  }
  for d in *.deb; do dpkg -x "$d" "$TC/local"; done
fi

echo "=== versions ==="
"$TC/local/usr/bin/arm-none-eabi-as" --version | head -1
echo "agbcc: $("$TC/agbcc/agbcc" --version 2>&1 | head -1 || echo present)"
echo "toolchain ready at $TC"
