#!/bin/bash
# Decompile functions from the analysed Ghidra project.
#
#   tools/ghidra_decompile.sh <outfile> <addr>...
#
# Reuses the project built by tools/ghidra_import.sh, so this does not
# re-analyse the ROM.
set -u

TC="$HOME/ffta-toolchain"
export JAVA_HOME="$TC/jdk"
export PATH="$TC/jdk/bin:$PATH"

cd "$(dirname "$0")/.." || exit 1
REPO="$PWD"

OUT="${1:?usage: ghidra_decompile.sh <outfile> <addr>...}"
shift
case "$OUT" in
  /*) ;;
  *) OUT="$REPO/$OUT" ;;
esac
mkdir -p "$(dirname "$OUT")"

"$TC/ghidra/support/analyzeHeadless" "$TC/ghidra-proj" ffta \
  -process baserom.gba \
  -noanalysis \
  -scriptPath "$REPO/tools/ghidra" \
  -postScript DecompileFunctions.java "$OUT" "$@" \
  2>&1 | grep -E 'decompiled|ERROR|Exception' | head -20

echo "--- $OUT ---"
cat "$OUT"
