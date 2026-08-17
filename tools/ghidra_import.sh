#!/bin/bash
# Import the base ROM into a Ghidra project and run auto-analysis.
#
#   tools/ghidra_import.sh [rom]
#
# Slow (the ROM is 16 MB), but done once: the project is reused by
# tools/ghidra_decompile.sh. The GBA has no built-in Ghidra loader, so the ROM
# is imported as a raw binary with the ARMv4T language and based at 0x08000000.
set -u

TC="$HOME/ffta-toolchain"
export JAVA_HOME="$TC/jdk"
export PATH="$TC/jdk/bin:$PATH"

cd "$(dirname "$0")/.." || exit 1
ROM="${1:-baserom.gba}"
[ -f "$ROM" ] || { echo "no ROM at $ROM"; exit 1; }

PROJ="$TC/ghidra-proj"
mkdir -p "$PROJ"

"$TC/ghidra/support/analyzeHeadless" "$PROJ" ffta \
  -import "$ROM" \
  -processor ARM:LE:32:v4t \
  -loader BinaryLoader \
  -loader-baseAddr 0x08000000 \
  -overwrite \
  2>&1 | grep -vE '^(WARN|INFO) ' | tail -30

echo "GHIDRA IMPORT DONE"
